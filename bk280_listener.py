# -*- coding: utf-8 -*-
"""
Bioximiya analizatori listener — UNIVERSAL (Biobase BK-280, Mindray BS, Zybio, Dirui, URIT,
Rayto, Erba, Human, BioSystems, Roche ...). Modul nomi tarixiy (BK-280 bilan boshlangan),
import API o'zgarmagan:
    from bk280_listener import start_bk280_listener, stop_bk280_listener

Sozlama: analizator_config.json → "bioximiya" (Tizim Sozlamalari → Bioximiya):
  model, connection_type (tcp_server / tcp_client / serial), protocol (auto/hl7/astm),
  port (natija), lis_port (shtrix-kod so'rovi; 0 = natija porti bilan bir xil), ack_style, query_type.

Vazifalari:
  * Natija (HL7 ORU^R01 / ASTM R) → RAW fayl (RAW_LOGS/YYYYMM/bk280_raw_*.txt) + hl7_inbox jadvali
    + ACK + callback(order_id) (barcode bazadagi buyurtmaga mos kelsa).
    Natijani bazaga YOZMAYDI — laborant biochemistry_window orqali tasdiqlab import qiladi
    (analizator namuna raqami 22 ni 22-buyurtmaga xato biriktirish xavfi bor edi).
  * SHTRIX-KOD so'rovi: QRY^Q02 → QCK + DSR^Q03 (Mindray/Biobase), ORM^O01 → ORR^O02 (URIT ...),
    ASTM Q → H/P/O/L (Erba/Human/Roche). Tahlil kodlari = analizator kanal kodlari
    (bio_protokol kod xaritasi).
Transport va parser: gemo_protokol.Transport + bio_protokol.
"""

import os
import re
import sys
import json
import time
import threading
import traceback
from datetime import datetime

# Konsol UTF-8 (dastur "start /min" bilan ochilganda ham xato bermasin)
try:
    if hasattr(sys.stdout, "buffer") and \
            (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from monoblok_db_config import DB_CONFIG

try:
    from monoblok_db_config import get_analyzer
    _bio_cfg = get_analyzer("bioximiya")
except Exception as _e:
    print(f"[OGOHLANTIRISH] bioximiya config yuklanmadi: {_e}")
    _bio_cfg = {}

import gemo_protokol as _gp
import bio_protokol as _bp

_bio_eff = _bp.effective_config(_bio_cfg)
ANALYZER_MODEL = _bio_eff.get("model", _bp.DEFAULT_MODEL)
ANALYZER_NAME = _bp.PROFILES.get(ANALYZER_MODEL, {}).get("name", ANALYZER_MODEL)
SERVER_IP = _bio_eff.get("ip", "0.0.0.0")
SERVER_PORT = int(_bio_eff.get("port", 8087))
ENCODING = _bio_eff.get("encoding", "utf-8")

# Frozen-aware yozish papkasi (mijozda G: bo'lmasligi mumkin)
_BK_DATA = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "AzizMedLine", "BK280")
BASE_DIR = os.path.join(_BK_DATA, "RAW_LOGS")
ERRORS_DIR = os.path.join(_BK_DATA, "ERRORS")
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

ACK = b'\x06'   # BK-280 natija portida kutadigan bir baytli tasdiq


def _log(msg):
    line = f"[BIO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(os.path.join(_LOG_DIR, f"bio_{datetime.now().strftime('%Y%m%d')}.log"),
                  "a", encoding="utf-8", errors="replace") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def log_error(error_msg):
    """Xatolarni ERRORS papkasiga saqlash"""
    try:
        error_file = os.path.join(ERRORS_DIR, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{error_msg}\n")
    except Exception:
        pass
    _log(f"[XATO] {error_msg}")


def db():
    import pymysql
    return pymysql.connect(host=DB_CONFIG["host"], user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                           database=DB_CONFIG["database"], port=DB_CONFIG["port"],
                           charset="utf8mb4", connect_timeout=5)


def get_order_by_sample_id(sample_id):
    """Barcode (orders.sample_id / bemor kodlari) → order_id. orders.id bo'yicha QIDIRMAYDI."""
    try:
        od = _bp.lookup_order(sample_id)
    except _bp.LookupUnavailable as e:
        _log(f"[XATO] Baza javob bermadi, buyurtma aniqlanmadi ({sample_id}): {e}")
        return None
    return od["patient"]["order_id"] if od else None


def save_raw(raw):
    """Raw xabarni oylik papkaga saqlash: BASE_DIR/YYYYMM/bk280_raw_YYYYMMDD_HHMMSS.txt
    (biochemistry_window shu nom/papkadan o'qiydi — o'zgartirmang)"""
    dt = datetime.now()
    month_folder = os.path.join(BASE_DIR, dt.strftime("%Y%m"))
    os.makedirs(month_folder, exist_ok=True)
    path = os.path.join(month_folder, dt.strftime("bk280_raw_%Y%m%d_%H%M%S.txt"))
    if os.path.exists(path):   # bir soniyada 2 ta natija
        path = path.replace(".txt", f"_{dt.microsecond // 1000:03d}.txt")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(raw)
    _log(f"RAW saqlandi: {path}")
    return path


def _save_inbox(raw_msg):
    try:
        con = db()
        try:
            with con.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS hl7_inbox(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT NOW()
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
                cur.execute("INSERT INTO hl7_inbox(raw_text, created_at) VALUES(%s, NOW())", (raw_msg,))
                con.commit()
        finally:
            con.close()
    except Exception as e:
        _log(f"[OGOHLANTIRISH] hl7_inbox saqlanmadi: {e}")


# ─────────────────────────── XABARLARNI QAYTA ISHLASH ─────────────
_running = False
_threads = []
_transports = []
_callback = None
_last_result_time = None
_cfg_live = dict(_bio_eff)


def _ack_bytes(kind_msh: dict, kind="R01") -> list:
    style = _cfg_live.get("ack_style", "hl7")
    out = []
    if style in ("byte", "both"):
        out.append(ACK)
    if style in ("hl7", "both"):
        out.append(_bp.wrap_mllp(_bp.build_hl7_ack(kind_msh, kind), ENCODING))
    return out


def _handle_result(message: str, send, fmt: str):
    global _last_result_time
    _last_result_time = datetime.now()
    model = _cfg_live.get("model", _bp.DEFAULT_MODEL)
    res = _bp.parse_message(message, model)
    # ACK
    try:
        if fmt == "hl7":
            for b in _ack_bytes(res.get("msh", {})):
                send(b)
    except Exception as e:
        _log(f"[XATO] ACK yuborishda: {e}")
    _log(f"◄ Natija: sample={res.get('sample_id') or '-'} (№{res.get('sample_no') or '-'}) "
         f"| {res.get('name') or '?'} | {len(res.get('tests', {}))} ta test | {fmt}")
    if res.get("unknown"):
        _log(f"  Noma'lum kodlar (Tahlil kodlari oynasida bog'lang): {res['unknown']}")
    save_raw(message)
    _save_inbox(message)
    # Callback — faqat barcode bazadagi buyurtmaga mos kelsa
    sid = res.get("sample_id", "")
    if sid and _callback:
        try:
            order_id = get_order_by_sample_id(sid)
            if order_id:
                _callback(order_id)
        except Exception as e:
            _log(f"[OGOHLANTIRISH] callback: {e}")


def save_query_raw(direction: str, text: str):
    """Shtrix-kod so'rovi/javobini xom holda saqlash — analizator javobimizni qabul
    qilmasa, aynan qanday baytlar ketganini keyin ko'rish uchun (24.09.2026 sinovi)."""
    try:
        dt = datetime.now()
        folder = os.path.join(BASE_DIR, dt.strftime("%Y%m"), "QUERY")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, dt.strftime(f"qry_%Y%m%d_%H%M%S_%f_{direction}.txt"))
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)
    except Exception as e:
        _log(f"[OGOHLANTIRISH] so'rov xom fayli saqlanmadi: {e}")


def _handle_query_hl7_qry(message: str, send):
    q = _bp.parse_qry(message)
    sid = q.get("sample_id", "")
    model = _cfg_live.get("model", _bp.DEFAULT_MODEL)
    _log(f"◄ QRY^Q02 (shtrix-kod): {sid or '-'}")
    _log(f"  xom so'rov: {message.strip()[:300]!r}")
    save_query_raw("in", message)

    try:
        od = _bp.lookup_order(sid) if sid else None
    except _bp.LookupUnavailable as e:
        # Baza yotgan — "topilmadi" (NF) deb YOLG'ON aytmaymiz, ilova xatosi (AE)
        _log(f"[XATO] Baza javob bermadi, QCK AE yuborilmoqda: {e}")
        qck_ae = _bp.build_qck(q, False, err_code="207")
        send(_bp.wrap_mllp(qck_ae, ENCODING))
        save_query_raw("out_ae", qck_ae)
        return

    qck = _bp.build_qck(q, bool(od))
    send(_bp.wrap_mllp(qck, ENCODING))
    save_query_raw("out_qck", qck)
    if not od:
        _log("  -> bemor topilmadi: QCK NF")
        return
    # QCK va DSR orasidagi pauza. Analizator ikkala xabarni BITTA o'qishda
    # olsa, ularning yig'indisi 1024 baytlik buferiga sig'maydi. Pauza
    # uzunroq bo'lsa u QCK ni o'qib, buferni bo'shatib ulguradi.
    time.sleep(float(_bp._tune("dsr_delay", 0.6)))
    skipped = []
    items = _bp.worklist_items(od, model, skipped_out=skipped)
    if skipped:
        _log(f"  [DIQQAT] Analizator taniymaydigan tahlil worklistga qo'shilmadi: {skipped} "
             f"— bu tahlilni analizatorda QO'LDA tanlang")
    dsr = _bp.build_dsr(q, od, model)
    send(_bp.wrap_mllp(dsr, ENCODING))
    save_query_raw("out_dsr", dsr)
    _log(f"  -> DSR^Q03: {od['patient'].get('fish')} | tahlillar: {[a for a, *_ in items]} "
         f"| {len(dsr)} bayt")
    if len(dsr) > 1000:
        _log(f"  [OGOHLANTIRISH] Javob {len(dsr)} bayt — analizator buferi ~1024 bayt. "
             f"Katta ro'yxat qabul qilinmasligi mumkin (ACK kelmasa shu sabab).")
    _log(f"  xom javob: {dsr.strip()[:300]!r}")


def _handle_query_hl7_orm(message: str, send):
    sid = _bp.orm_sample_id(message)
    model = _cfg_live.get("model", _bp.DEFAULT_MODEL)
    msh = _bp.parse_qry(message).get("msh", {})
    _log(f"◄ ORM^O01 (shtrix-kod): {sid or '-'}")
    try:
        od = _bp.lookup_order(sid) if sid else None
    except _bp.LookupUnavailable as e:
        _log(f"[XATO] Baza javob bermadi, ORR AE yuborilmoqda: {e}")
        send(_bp.wrap_mllp(_bp.build_hl7_ack(msh, "O02", "AE",
                                             "LIS database unavailable", "207"), ENCODING))
        return
    send(_bp.wrap_mllp(_bp.build_orr(msh, od, sid, model), ENCODING))
    _log(f"  -> ORR^O02: {'topildi ' + str(od['patient'].get('fish')) if od else 'topilmadi (AR)'}")


def _handle_query_astm(message: str, send):
    sid = _gp.astm_query_sample_id(message)
    model = _cfg_live.get("model", _bp.DEFAULT_MODEL)
    _log(f"◄ ASTM Q (shtrix-kod): {sid or '-'}")
    try:
        od = _bp.lookup_order(sid) if sid else None
    except _bp.LookupUnavailable as e:
        _log(f"[XATO] Baza javob bermadi, ASTM worklist yuborilmadi: {e}")
        return
    send(b"\x05")
    send(_gp.astm_frames(_bp.build_astm_worklist(sid, od, model)))
    send(b"\x04")
    _log(f"  -> ASTM worklist: {'topildi ' + str(od['patient'].get('fish')) if od else 'topilmadi'}")


def _handle_message(message: str, send):
    kind = _bp.message_kind(message)
    if kind == "oru":
        _handle_result(message, send, "hl7")
    elif kind == "astm_result":
        _handle_result(message, send, "astm")
    elif kind == "qry":
        _handle_query_hl7_qry(message, send)
    elif kind == "orm":
        _handle_query_hl7_orm(message, send)
    elif kind == "astm_query":
        _handle_query_astm(message, send)
    elif kind == "ack":
        _log("◄ ACK (analizator tasdiqladi)")
    else:
        _log(f"  Noma'lum xabar: {message[:80]!r}")
        try:
            msh = _bp.parse_qry(message).get("msh", {})
            if msh:
                send(_bp.wrap_mllp(_bp.build_hl7_ack(msh, "R01", "AR", "Unsupported message type", "200"), ENCODING))
        except Exception:
            pass


def parse_and_save_hl7(raw_msg):
    """Moslik uchun (eski nom): RAW + inbox saqlaydi, natijani qaytaradi."""
    res = _bp.parse_message(raw_msg, _cfg_live.get("model", _bp.DEFAULT_MODEL))
    save_raw(raw_msg)
    _save_inbox(raw_msg)
    return res


# ─────────────────────────── PUBLIC API ───────────────────────
def _run_transport(cfg: dict, label: str):
    tr = _gp.Transport(cfg, log=_log)
    _transports.append(tr)
    _log(f"{ANALYZER_NAME} [{label}] — {tr.describe()}")

    def handler(message, send):
        try:
            _handle_message(message, send)
        except Exception as e:
            log_error(f"handler: {e}\n{traceback.format_exc()}")
    try:
        tr.run(handler, lambda: _running)
    finally:
        tr.close()


def start_bk280_listener(host=None, port=None, order_update_callback=None, cfg=None):
    """
    Bioximiya listener (background thread). Natija porti + (agar farq qilsa) LIS so'rov porti.
    Returns: birinchi Thread yoki None
    """
    global _running, _callback, _cfg_live, ANALYZER_NAME, _threads, _transports
    if _running:
        _log("Allaqachon ishlayapti")
        return _threads[0] if _threads else None

    full = dict(cfg) if cfg else dict(_bio_cfg)
    if host:
        full["ip"] = host
    if port:
        full["port"] = int(port)
    eff = _bp.effective_config(full)
    _cfg_live = eff
    ANALYZER_NAME = _bp.PROFILES.get(eff.get("model", _bp.DEFAULT_MODEL), {}).get("name", eff.get("model"))
    _callback = order_update_callback
    _running = True
    _threads = []
    _transports = []

    t = threading.Thread(target=_run_transport, args=(eff, "natija"), daemon=True, name="bio-listener")
    t.start()
    _threads.append(t)

    lis_port = int(eff.get("lis_port") or 0)
    if eff.get("connection_type") == "tcp_server" and lis_port and lis_port != int(eff.get("port", 0)):
        cfg2 = dict(eff)
        cfg2["port"] = lis_port
        cfg2["ack_style"] = "hl7"   # so'rov portida to'liq HL7 javoblar
        t2 = threading.Thread(target=_run_transport, args=(cfg2, "shtrix-kod"), daemon=True, name="bio-lis")
        t2.start()
        _threads.append(t2)
    return t


def push_worklist(sample_id: str, style: str = "dsr"):
    """SINOV: so'ramaydigan analizatorga (BK-280 V1) bemor ma'lumotini o'zimiz yuboramiz —
    analizator bizga ochiq ulangan natija porti orqali. style: 'dsr' (DSR^Q03) | 'orm' (ORM^O01).
    Qaytaradi (ok, xabar). Analizator javobi (ACK/boshqa) logda ko'rinadi."""
    sid = (sample_id or "").strip()
    if not sid:
        return False, "shtrix-kod bo'sh"
    tr = next((t for t in _transports if t.connected), None)
    if tr is None:
        return False, "Analizator hozir ulanmagan (natija porti) — yuborib bo'lmaydi"
    try:
        od = _bp.lookup_order(sid)
    except _bp.LookupUnavailable as e:
        return False, f"Bazaga ulanib bo'lmadi: {e}"
    if not od:
        return False, f"{sid} bazada topilmadi (orders.sample_id)"
    model = _cfg_live.get("model", _bp.DEFAULT_MODEL)
    items = _bp.worklist_items(od, model)
    if style == "orm":
        msg = _bp.build_orm_new_order(od, sid, model, app="BIOBASE", fac="BK-280")
    else:
        q = {"sample_id": sid, "query_id": "1", "qrd": "", "qrf": "",
             "msh": {"app": "BIOBASE", "fac": "BK-280", "ctrl": datetime.now().strftime("%H%M%S")}}
        msg = _bp.build_dsr(q, od, model)
    try:
        tr.send(_bp.wrap_mllp(msg, ENCODING))
    except Exception as e:
        return False, f"yuborishda xato: {e}"
    _log(f"► PUSH {style.upper()} yuborildi: {sid} | {od['patient'].get('fish')} | tahlillar: {[a for a, *_ in items]}")
    return True, (f"Yuborildi ({style.upper()}): {od['patient'].get('fish')}, "
                  f"tahlillar: {', '.join(n for _, n, *_ in items)}\n"
                  "Analizator ekranida «Заказ образца» / bemor ro'yxatini tekshiring. "
                  "Analizator javobi logs/bio_*.log da.")


def stop_bk280_listener():
    global _running
    _running = False
    for tr in list(_transports):
        try:
            tr.close()
        except Exception:
            pass
    _log("Bioximiya listener to'xtatilish so'rovi")


def is_running() -> bool:
    return _running and any(t.is_alive() for t in _threads)


def get_status() -> dict:
    return {"running": is_running(), "analyzer": ANALYZER_NAME,
            "connected": any(tr.connected for tr in _transports),
            "last_result": _last_result_time,
            "transports": [tr.describe() for tr in _transports]}


def main():
    t = start_bk280_listener()
    try:
        while t and t.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_bk280_listener()


if __name__ == "__main__":
    main()
