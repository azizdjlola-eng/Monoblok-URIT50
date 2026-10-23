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
# BIO_DATA_DIR / BIO_LOG_DIR / BIO_XIZMAT_SUFFIX / BIO_XIZMAT_CFG — faqat SINOV uchun
# (jonli xizmat, port, holat fayli va loglarga tegmasdan boshqa portda sinash).
_BK_DATA = os.environ.get("BIO_DATA_DIR") or os.path.join(
    os.environ.get("ProgramData", r"C:\ProgramData"), "AzizMedLine", "BK280")
BASE_DIR = os.path.join(_BK_DATA, "RAW_LOGS")
ERRORS_DIR = os.path.join(_BK_DATA, "ERRORS")
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)
_LOG_DIR = os.environ.get("BIO_LOG_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

ACK = b'\x06'   # BK-280 natija portida kutadigan bir baytli tasdiq


# Konsolga yozish ALOHIDA oqimda, faylga — to'g'ridan-to'g'ri (bc20s_listener bilan bir xil).
# 23.10.2026: dastur 08:26 da ochilgan, lekin bioximiya logida 09:25 gacha BIRORTA qator
# yo'q — listener birinchi _log() dayoq to'xtagan (avval print() edi, fayl keyin). Windows
# konsoli bloklansa print() cheksiz kutadi va port umuman ochilmaydi; analizator esa LIS
# ga ulana olmay "LIS server yo'q" deb qotadi. Endi print hech qachon listenerni ushlamaydi.
import queue as _queue
_print_q = _queue.Queue(maxsize=2000)
_log_lock = threading.Lock()


def _console_printer():
    while True:
        line = _print_q.get()
        try:
            print(line, flush=True)
        except Exception:
            pass


threading.Thread(target=_console_printer, daemon=True, name="bio-log").start()


def _log(msg):
    line = f"[BIO {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with _log_lock:
            os.makedirs(_LOG_DIR, exist_ok=True)
            with open(os.path.join(_LOG_DIR, f"bio_{datetime.now().strftime('%Y%m%d')}.log"),
                      "a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")
    except Exception:
        pass
    try:
        _print_q.put_nowait(line)
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
    if os.environ.get("BIO_XIZMAT_SUFFIX"):     # sinov rejimi — jonli bazaga yozilmasin
        return
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
_pending_retest_sid = None   # qayta o'lchov DSR i yuborilgan barkod (ACK kutilmoqda)
_cfg_live = dict(_bio_eff)

# ── DSR ni avtomatik qayta yuborish (22.10.2026) ──
# BK-280 (CRYSTAL Listrans) har Send dan keyin YANGI BeginReceive zanjirini ochadi; natija
# yuborgan Listrans nusxasining zanjirlari ham o'sha bitta socketda qoladi. Bizning QCK/DSR
# bo'lagi navbatdagi eng eski zanjirga tushadi — u natija yuboruvchi nusxaniki bo'lsa, DSR
# LIS oynasiga yetmaydi (ACK^Q03 kelmaydi). Natijalar to'plamidan keyingi 1-so'rov ~22%
# shu sabab yiqilardi va laborant 5-10 s kutib qayta bosardi. Endi ACK kelmasa o'zimiz
# qayta yuboramiz. Haqiqiy qayta ishlash <= ~2.2 s (1 s Thread.Join + baza), shuning
# uchun 2.5 s dan keyin qayta yuborish ikki marta qayta ishlashga olib kelmaydi.
_qlock = threading.Lock()     # QCK→pauza→DSR ketma-ketligi bo'linmasin (javob ↔ qayta yuborish)
_resend = None                # {"sid","payload"|"parts","send","sock","tries","due"}
_resend_thread = None
_last_dsr = None              # (barkod, yuborilgan vaqt) — "muddatidan oldin ACK" nazorati


def _combine_ok() -> bool:
    model = str(_cfg_live.get("model", _bp.DEFAULT_MODEL) or "")
    return bool(_bp._tune("qck_dsr_combine", model.startswith("biobase")))


def _resend_cfg():
    model = str(_cfg_live.get("model", _bp.DEFAULT_MODEL) or "")
    default_after = 2.5 if model.startswith("biobase") else 0
    try:
        after = float(_bp._tune("dsr_resend_after", default_after))
        tries = int(_bp._tune("dsr_resend_max", 3))
    except (TypeError, ValueError):
        after, tries = default_after, 3
    return after, tries


def _cancel_resend(reason: str = ""):
    """_qlock ichida chaqiriladi."""
    global _resend
    if _resend and reason:
        _log(f"  [QAYTA YUBORISH] {_resend['sid']}: bekor — {reason}")
    _resend = None


def _resend_worker():
    global _resend
    while _running:
        time.sleep(0.2)
        rec = _resend
        if not rec or time.time() < rec["due"]:
            continue
        with _qlock:
            if _resend is not rec:          # shu orada ACK yoki yangi so'rov keldi
                continue
            tr = getattr(rec["send"], "__self__", None)
            if tr is not None and getattr(tr, "_sock", None) is not rec["sock"]:
                _cancel_resend("ulanish almashdi")
                continue
            _after, max_tries = _resend_cfg()
            if rec["tries"] >= max_tries:
                _log(f"  [QAYTA YUBORISH] {rec['sid']}: {max_tries} marta yuborildi, ACK kelmadi — "
                     f"analizatorda LIS ni qayta bosing")
                _resend = None
                continue
            rec["tries"] += 1
            try:
                if rec["payload"] is not None:
                    rec["send"](rec["payload"])
                else:
                    rec["send"](rec["parts"][0])
                    time.sleep(float(_bp._tune("dsr_delay", 0.6)))
                    rec["send"](rec["parts"][1])
                _log(f"  [QAYTA YUBORISH] {rec['sid']}: ACK kelmadi → QCK+DSR qayta yuborildi "
                     f"({rec['tries']}/{max_tries})")
            except Exception as e:
                _log(f"  [QAYTA YUBORISH] {rec['sid']}: yuborilmadi ({e})")
                _resend = None
                continue
            rec["due"] = time.time() + max(_after, 1.5)


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
    # Callback — faqat barcode bazadagi buyurtmaga mos kelsa. Xizmat rejimida callback yo'q:
    # hodisa holat fayliga yoziladi, monoblok uni o'qib ochiq bemorni yangilaydi.
    sid = res.get("sample_id", "")
    if sid:
        try:
            order_id = get_order_by_sample_id(sid)
            if order_id:
                _note_event(order_id, sid)
                if _callback:
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
    with _qlock:
        _cancel_resend("yangi so'rov keldi")
        _handle_query_hl7_qry_locked(message, send)


def _handle_query_hl7_qry_locked(message: str, send):
    global _resend, _last_query_time
    _last_query_time = datetime.now()
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
    qck_b = _bp.wrap_mllp(qck, ENCODING)
    if not od:
        send(qck_b)
        save_query_raw("out_qck", qck)
        _log("  -> bemor topilmadi: QCK NF")
        return
    # Qayta o'lchov navbati: shu barkod uchun laborant RAW oynada tanlagan tahlillar
    # bo'lsa — FAQAT ular yuboriladi (analizatorda yangi namuna ochilgan bo'ladi).
    global _pending_retest_sid, _last_dsr
    only = None
    try:
        only = _bp.retest_queue_get(sid)
    except Exception as e:
        _log(f"[OGOHLANTIRISH] qayta o'lchov navbati o'qilmadi: {e}")
    skipped = []
    items = _bp.worklist_items(od, model, skipped_out=skipped, only_codes=only)
    if skipped:
        _log(f"  [DIQQAT] Analizator taniymaydigan tahlil worklistga qo'shilmadi: {skipped} "
             f"— bu tahlilni analizatorda QO'LDA tanlang")
    if only is not None:
        _log(f"  [QAYTA O'LCHOV] {sid}: faqat {sorted(only)} yuboriladi (yangi namuna)")
        _pending_retest_sid = sid
    else:
        _pending_retest_sid = None
    dsr = _bp.build_dsr(q, od, model, only_codes=only)
    dsr_b = _bp.wrap_mllp(dsr, ENCODING)
    # QCK + DSR — BITTA bo'lak (22.10.2026). Analizator (Listrans) kalit so'zli HAR bo'lak
    # uchun 1 s dan keyin ishlovchini chaqiradi, lekin ishlovchiga o'sha bo'lakni emas,
    # nusxadagi ENG OXIRGI matnni beradi. Alohida QCK va DSR = 2 chaqiruv: 1-si DSR ni
    # to'g'ri qayta ishlaydi, 2-si (to'plamli LIS da) o'sha DSR ni ro'yxatdagi KEYINGI
    # namunaga yozardi — 261022121202 ga 199 ning ismi tushgan. Bitta bo'lak = bitta
    # chaqiruv. Bufer ~1024 bayt: sig'masa eski usul (QCK, pauza, DSR).
    combined = qck_b + dsr_b
    t_first = time.time()          # birinchi bo'lak vaqti (alohida rejimda QCK)
    if _combine_ok() and len(combined) <= int(_bp._tune("combine_max_bytes", 1000)):
        send(combined)
        parts = None
    else:
        send(qck_b)
        time.sleep(float(_bp._tune("dsr_delay", 0.6)))
        send(dsr_b)
        parts = (qck_b, dsr_b)
        if _combine_ok():
            _log(f"  [DIQQAT] QCK+DSR {len(combined)} bayt — bitta bo'lakka sig'madi, alohida "
                 f"yuborildi. To'plamli LIS da bu namunadan keyingisining ismini tekshiring")
    save_query_raw("out_qck", qck)
    save_query_raw("out_dsr", dsr)
    _last_dsr = (sid, t_first)
    after, _tries = _resend_cfg()
    if after > 0:
        _resend = {"sid": sid, "payload": combined if parts is None else None, "parts": parts,
                   "send": send, "sock": getattr(getattr(send, "__self__", None), "_sock", None),
                   "tries": 0, "due": time.time() + max(after, 1.5)}
    how = " (QCK bilan bitta bo'lak)" if parts is None else ""
    _log(f"  -> DSR^Q03: {od['patient'].get('fish')} | tahlillar: {[a for a, *_ in items]} "
         f"| {len(dsr)} bayt{how}")
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
        # MSA qatori ham yoziladi: shtrix-kod so'rovi 1-urinishda o'tmay qolganda
        # (28.09.2026 — ~50% holatda ACK umuman kelmadi) analizator AE/AR bilan
        # rad etdimi yoki umuman javob bermadimi — shundan ajratiladi.
        msa = next((ln.strip() for ln in re.split(r"[\r\n]+", message) if ln.strip().startswith("MSA|")), "")
        with _qlock:
            rec = _resend
            if rec and rec["tries"]:
                _log(f"  [QAYTA YUBORISH] {rec['sid']}: {rec['tries']}-qayta yuborishdan keyin qabul qilindi")
            _cancel_resend()
            # Analizator DSR ni bo'lak kelganidan kamida 1 s keyin qayta ishlaydi
            # (Thread.Join(1000)). Undan tezroq kelgan ACK = u bizning oxirgi DSR ni
            # emas, ESKI matnni qayta ishlagan: bu namunaga boshqa bemor ismi/tahlillari
            # yozilgan bo'lishi mumkin (22.10.2026: 202 ← 199, 205 ← 203).
            global _last_dsr
            if _last_dsr and "ACK^Q03" in message:
                dt = time.time() - _last_dsr[1]
                if dt < float(_bp._tune("early_ack_sec", 0.9)):
                    _log(f"  [DIQQAT!] {_last_dsr[0]}: analizator javobni {dt:.2f} s da tasdiqladi "
                         f"(<1 s — imkonsiz). Analizatorda shu namunaning ISMI va TAHLILLARINI "
                         f"barkod bilan solishtiring — boshqa bemorniki yozilgan bo'lishi mumkin")
                _last_dsr = None
        _log(f"◄ ACK (analizator tasdiqladi) {msa[:80]}")
        # Qayta o'lchov DSR i qabul qilindi — navbatdan olib tashlaymiz (bir martalik)
        global _pending_retest_sid
        if _pending_retest_sid and "|AA|" in msa:
            try:
                _bp.retest_queue_remove(_pending_retest_sid)
                _log(f"  [QAYTA O'LCHOV] {_pending_retest_sid}: analizator qabul qildi, navbatdan olindi")
            except Exception as e:
                _log(f"[OGOHLANTIRISH] qayta o'lchov navbatidan o'chirilmadi: {e}")
            _pending_retest_sid = None
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
_gen = 0                      # har start_bk280_listener da +1 — eski oqimlar portni qayta egallamasin
_status_thread = None


def _alive(gen: int) -> bool:
    return _running and gen == _gen


def _run_transport(cfg: dict, label: str, gen: int):
    tr = _gp.Transport(cfg, log=_log)
    _transports.append(tr)
    _log(f"{ANALYZER_NAME} [{label}] — {tr.describe()}")

    def handler(message, send):
        try:
            _handle_message(message, send)
        except Exception as e:
            log_error(f"handler: {e}\n{traceback.format_exc()}")
    try:
        tr.run(handler, lambda: _alive(gen))
    finally:
        tr.close()


def start_bk280_listener(host=None, port=None, order_update_callback=None, cfg=None):
    """
    Bioximiya listener (background thread). Natija porti + (agar farq qilsa) LIS so'rov porti.
    Returns: birinchi Thread yoki None
    """
    global _running, _callback, _cfg_live, ANALYZER_NAME, _threads, _transports, _gen
    global _resend_thread, _status_thread, _started_at
    if _running:
        _log("Allaqachon ishlayapti")
        return _threads[0] if _threads else None

    full = dict(cfg) if cfg else dict(_bio_cfg)
    if host:
        full["ip"] = host
    if port:
        full["port"] = int(port)
    eff = _bp.effective_config(full)
    if eff.get("connection_type") == "tcp_server" and not _port_egasi_ol():
        _log("[DIQQAT] Bioximiya porti boshqa jarayonda ochiq (fon xizmati) — bu yerda ochilmadi")
        return None
    _cfg_live = eff
    ANALYZER_NAME = _bp.PROFILES.get(eff.get("model", _bp.DEFAULT_MODEL), {}).get("name", eff.get("model"))
    _callback = order_update_callback
    _gen += 1
    gen = _gen
    _running = True
    _threads = []
    _transports = []
    _started_at = datetime.now()

    t = threading.Thread(target=_run_transport, args=(eff, "natija", gen), daemon=True, name="bio-listener")
    t.start()
    _threads.append(t)

    if _resend_thread is None or not _resend_thread.is_alive():
        _resend_thread = threading.Thread(target=_resend_worker, daemon=True, name="bio-dsr-resend")
        _resend_thread.start()
    if _status_thread is None or not _status_thread.is_alive():
        _status_thread = threading.Thread(target=_status_writer, daemon=True, name="bio-holat")
        _status_thread.start()

    lis_port = int(eff.get("lis_port") or 0)
    if eff.get("connection_type") == "tcp_server" and lis_port and lis_port != int(eff.get("port", 0)):
        cfg2 = dict(eff)
        cfg2["port"] = lis_port
        cfg2["ack_style"] = "hl7"   # so'rov portida to'liq HL7 javoblar
        t2 = threading.Thread(target=_run_transport, args=(cfg2, "shtrix-kod", gen), daemon=True, name="bio-lis")
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
    _write_status()


def is_running() -> bool:
    return _running and any(t.is_alive() for t in _threads)


# ───────────── HOLAT: monoblok "● Bioximiya" tugmasi va xizmat nazorati uchun ─────────────
# 23.10.2026: listener monoblok ICHIDA ishlaganda dastur har yopilganda/qayta ochilganda
# (kuniga 2-5 marta) analizator ulanishi uziladi. BK-280 (CRYSTAL) o'zi QAYTA ULANMAYDI:
# keyingi natijada "LIS server yo'q" oynasini chiqaradi va real vaqtli yuborishni o'chiradi —
# laborant LIS sozlamasida "Ulanish" ni bosmaguncha (loglarda 1 soatgacha) LIS ishlamaydi.
# Endi listener ALOHIDA fon jarayonida ("xizmat") ishlaydi: monoblok uni ishga tushiradi,
# lekin yopilganda to'xtatmaydi. Holat shu faylga har 2 s yoziladi.
HOLAT_FAYL = os.path.join(_BK_DATA, "xizmat_holat.json")
BUYRUQ_FAYL = os.path.join(_BK_DATA, "xizmat_buyruq.txt")
_SUFFIX = os.environ.get("BIO_XIZMAT_SUFFIX", "")
XIZMAT_MUTEX = "Local\\AzizMedLine_BioLIS_xizmat" + _SUFFIX
# Portni FAQAT bitta jarayon ochsin: Windows SO_REUSEADDR bilan ikkinchi jarayon ham
# o'sha portni "egallay oladi" va ulanishlar ular orasida tasodifan bo'linadi.
PORT_MUTEX = "Local\\AzizMedLine_BioLIS_port" + _SUFFIX
_port_mutex = None
_mode = "ichki"          # ichki = monoblok jarayoni ichida | xizmat = alohida fon jarayoni
_started_at = None
_last_query_time = None
_event = None            # oxirgi natija hodisasi: {"seq", "order_id", "sample_id", "time"}
_event_seq = 0
_event_lock = threading.Lock()
_mutex_handle = None


def _kod_mtime() -> float:
    base = os.path.dirname(os.path.abspath(__file__))
    m = 0.0
    for n in ("bk280_listener.py", "bio_protokol.py", "gemo_protokol.py"):
        try:
            m = max(m, os.path.getmtime(os.path.join(base, n)))
        except OSError:
            pass
    return m


KOD_MTIME = _kod_mtime()   # xizmat qaysi kod bilan ishga tushgan (yangilanganini bilish uchun)


_events = []             # oxirgi 20 ta natija hodisasi (monoblok har 5 s o'qiydi)


def _note_event(order_id, sample_id):
    global _event, _event_seq
    with _event_lock:
        _event_seq += 1
        _event = {"seq": _event_seq, "order_id": order_id, "sample_id": sample_id,
                  "time": datetime.now().isoformat(timespec="seconds")}
        _events.append(_event)
        del _events[:-20]


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt else ""


def get_status() -> dict:
    trs = list(_transports)
    conn = next((t for t in trs if t.connected), None)
    rx = [t.last_rx for t in trs if getattr(t, "last_rx", None)]
    main_port = int(_cfg_live.get("port", 0) or 0)
    natija = [t for t in trs if int(t.cfg.get("port", 0) or 0) == main_port] or trs[:1]
    if natija and natija[0].cfg.get("connection_type") == "tcp_server":
        listening = bool(getattr(natija[0], "listening", False))
    else:
        listening = is_running()
    return {
        "pid": os.getpid(), "mode": _mode, "running": is_running(),
        "listening": bool(_running and listening),
        "connected": conn is not None,
        "peer": (f"{conn.peer[0]}:{conn.peer[1]}" if conn is not None and conn.peer else ""),
        "conn_since": _iso(conn.conn_since) if conn is not None else "",
        "last_rx": _iso(max(rx)) if rx else "",
        "last_result": _iso(_last_result_time),
        "last_query": _iso(_last_query_time),
        "event": _event,
        "events": list(_events),
        "analyzer": ANALYZER_NAME,
        "transports": [t.describe() for t in trs],
        "started": _iso(_started_at),
        "code_mtime": KOD_MTIME,
        "time": time.time(),
    }


def _write_status():
    try:
        os.makedirs(_BK_DATA, exist_ok=True)
        tmp = f"{HOLAT_FAYL}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(get_status(), f, ensure_ascii=False)
        os.replace(tmp, HOLAT_FAYL)
    except Exception:
        pass


def _status_writer():
    while _running:
        _write_status()
        time.sleep(2)


def _k32():
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.OpenMutexW.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    return ctypes, k32


def _mutex_ol() -> bool:
    """Bitta nusxa (nomli mutex). False — boshqa xizmat nusxasi allaqachon ishlayapti."""
    global _mutex_handle
    if os.name != "nt":
        return True
    try:
        ctypes, k32 = _k32()
        h = k32.CreateMutexW(None, False, XIZMAT_MUTEX)
        err = ctypes.get_last_error()
        if not h:
            return True          # mutex yaratilmadi — port bandligi baribir himoya qiladi
        if err == 183:           # ERROR_ALREADY_EXISTS
            k32.CloseHandle(h)
            return False
        _mutex_handle = h        # jarayon tugaguncha ushlab turiladi
        return True
    except Exception:
        return True


def _port_egasi_ol() -> bool:
    """Shu jarayon bioximiya portining yagona egasi bo'ladi. False — port boshqa jarayonda
    (masalan fon xizmati) — bu yerda ochilmasin."""
    global _port_mutex
    if _port_mutex is not None or os.name != "nt":
        return True
    try:
        ctypes, k32 = _k32()
        h = k32.CreateMutexW(None, False, PORT_MUTEX)
        err = ctypes.get_last_error()
        if not h:
            return True
        if err == 183:           # ERROR_ALREADY_EXISTS — boshqa jarayon egasi
            k32.CloseHandle(h)
            return False
        _port_mutex = h          # jarayon tugaguncha ushlab turiladi
        return True
    except Exception:
        return True


def xizmat_ishlayaptimi() -> bool:
    """Alohida bioximiya LIS xizmati (fon jarayoni) ishlayaptimi — nomli mutex bo'yicha."""
    if os.name != "nt":
        return False
    try:
        _ctypes, k32 = _k32()
        h = k32.OpenMutexW(0x00100000, False, XIZMAT_MUTEX)   # SYNCHRONIZE
        if h:
            k32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False


# Shu kalitlar o'zgarsa xizmat transportlarni qayta ochadi (port/IP/model ...).
# Qolganlari (ack_style, qayta yuborish, bo'lak ...) har chaqiruvda jonli o'qiladi.
_KALIT_ULANISH = ("enabled", "model", "protocol", "connection_type", "ip", "port", "lis_port",
                  "encoding", "com_port", "baudrate", "bytesize", "parity", "stopbits")


def _bio_sozlama() -> dict:
    test_cfg = os.environ.get("BIO_XIZMAT_CFG")
    if test_cfg:
        try:
            with open(test_cfg, "r", encoding="utf-8") as f:
                return dict(json.load(f))
        except Exception:
            pass
    try:
        from monoblok_db_config import get_analyzer as _ga
        return dict(_ga("bioximiya") or {})
    except Exception:
        return dict(_bio_cfg)


def _ulanish_imzosi(cfg: dict) -> str:
    return json.dumps({k: cfg.get(k) for k in _KALIT_ULANISH}, sort_keys=True, default=str)


def _buyruq_oqi() -> str:
    try:
        with open(BUYRUQ_FAYL, "r", encoding="utf-8") as f:
            cmd = f.read().strip().lower()
        os.remove(BUYRUQ_FAYL)
        return cmd
    except Exception:
        return ""


def xizmat_main() -> int:
    """Alohida fon jarayoni:  pythonw bk280_listener.py --xizmat
    Monoblok uni ishga tushiradi (bio_xizmat.xizmatni_taminla), yopilganda to'xtatmaydi.
    To'xtatish/qayta ishga tushirish: BUYRUQ_FAYL ga "stop" / "restart"."""
    global _mode, _cfg_live
    _mode = "xizmat"
    if not _mutex_ol():
        _log("[XIZMAT] Boshqa nusxa allaqachon ishlayapti — bu nusxa chiqdi")
        return 0
    try:
        os.remove(BUYRUQ_FAYL)
    except OSError:
        pass
    cfg = _bio_sozlama()
    if not cfg.get("enabled", True):
        _log("[XIZMAT] Bioximiya sozlamalarda o'chirilgan — xizmat ishga tushmadi")
        return 0
    _log(f"[XIZMAT] Bioximiya LIS xizmati ishga tushdi (pid {os.getpid()}) — "
         f"monoblok yopilsa ham analizator ulanishi saqlanadi")
    start_bk280_listener(cfg=cfg)
    imzo = _ulanish_imzosi(cfg)
    oxirgi = time.time()
    while True:
        try:
            time.sleep(1)
            cmd = _buyruq_oqi()
            if cmd == "stop":
                _log("[XIZMAT] To'xtatish buyrug'i olindi")
                break
            sabab = "buyruq (restart)" if cmd == "restart" else ""
            if not sabab and _running and not is_running():
                sabab = "listener oqimlari to'xtab qolgan"
            yangi = None
            if not sabab and time.time() - oxirgi >= 10:
                oxirgi = time.time()
                yangi = _bio_sozlama()
                if not yangi.get("enabled", True):
                    _log("[XIZMAT] Bioximiya sozlamalarda o'chirildi — xizmat to'xtaydi")
                    break
                if _ulanish_imzosi(yangi) != imzo:
                    sabab = "ulanish sozlamasi o'zgardi"
                else:
                    _cfg_live = _bp.effective_config(yangi)   # ack_style va h.k. jonli
            if sabab:
                yangi = yangi or _bio_sozlama()
                _log(f"[XIZMAT] Qayta ishga tushirilmoqda: {sabab}")
                stop_bk280_listener()
                time.sleep(1.5)
                start_bk280_listener(cfg=yangi)
                imzo = _ulanish_imzosi(yangi)
        except Exception as e:
            _log(f"[XIZMAT] [XATO] {e}")
            time.sleep(2)
    stop_bk280_listener()
    return 0


def main():
    if "--xizmat" in sys.argv:
        sys.exit(xizmat_main())
    t = start_bk280_listener()
    try:
        while t and t.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_bk280_listener()


if __name__ == "__main__":
    main()
