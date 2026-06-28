# -*- coding: utf-8 -*-
"""
BC-20S MLLP Client — Mindray BC-20S gematologiya analizatoriga ulanish

MUHIM: BC-20S analizator TCP SERVER (port 5100).
       LIS (biz) TCP CLIENT sifatida ulanamiz.
       (mindray_integration.py dan isbotlangan arxitektura)

Protokol: HL7 v2.3.1 + MLLP
  - Heartbeat: analizator har 3 soniyada \x02 yuboradi
  - ORM^O01 (Worklist Query)  → DB dan bemor topib ORR^O02 qaytaramiz
  - ORU^R01 (Result Message)  → TXT fayliga DARHOL yozamiz + DB ga saqlaymiz
                                  + hematologiya oynasiga xabar beramiz

Ishga tushirish:
    from bc20s_listener import start_bc20s_listener, stop_bc20s_listener
    thread = start_bc20s_listener(result_callback=on_new_result)
"""

import os
import re
import sys
import glob
import json
import socket
import select
import threading
import traceback
import time
from datetime import datetime, date

# ─────────────────────────── CONFIG ───────────────────────────
# Sozlamalar analizator_config.json dan yuklanadi (Tizim Sozlamalari oynasi
# orqali kod tegmasdan o'zgartiriladi). Fayl/modul yo'q bo'lsa — standart.
try:
    from monoblok_db_config import get_analyzer
    _gema_cfg = get_analyzer("gemotologiya")
except Exception as _e:
    print(f"[OGOHLANTIRISH] gemotologiya config yuklanmadi: {_e}")
    _gema_cfg = {}

ANALYZER_IP     = _gema_cfg.get("ip", "192.168.0.2")        # BC-20S analizator IP manzili
ANALYZER_PORT   = int(_gema_cfg.get("port", 5100))          # BC-20S TCP server porti
ENCODING        = _gema_cfg.get("encoding", "utf-8")        # Matn kodirovkasi

MLLP_START      = b"\x0b"         # <VT>  - Start Block
MLLP_END        = b"\x1c\x0d"     # <FS><CR> - End Block
HEARTBEAT       = b"\x02"         # Analizator heartbeat bayti

SOCKET_TIMEOUT  = 10.0            # Socket timeout
RECONNECT_INTERVAL = int(_gema_cfg.get("reconnect_interval", 5))  # Qayta ulanish kutishi (sek)
MAX_RECONNECT   = 0               # 0 = cheksiz qayta ulanish (siydik analizatori kabi)

# BC-20S natijalar papkasi — oyma-oy tartibda: G:\DASTUR\URIT 50\BC-20s\YYYYMM\
MINDRAY_DAT_BASE = r"G:\DASTUR\URIT 50\BC-20s"

# ─────────────────────────── GLOBAL STATE ─────────────────────
_running         = False
_client_thread   = None
_result_callback = None   # fn(sample_id, patient_info_dict)
_socket          = None
_connected       = False
_lock            = threading.Lock()

# ─────────────────────────── LOGGING ──────────────────────────
def _log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[BC-20S {ts}] {msg}", flush=True)

# ─────────────────────────── MLLP ─────────────────────────────
def _wrap_mllp(hl7: str) -> bytes:
    return MLLP_START + hl7.encode(ENCODING, errors="replace") + MLLP_END

def _unwrap_mllp(buf: bytes):
    """buf dan HL7 xabarlar ro'yxati va qolgan qismni qaytaradi"""
    messages = []
    idx = 0
    while True:
        try:
            s = buf.index(MLLP_START, idx)
        except ValueError:
            break
        try:
            e = buf.index(MLLP_END, s + 1)
        except ValueError:
            break
        msg = buf[s + 1:e].decode(ENCODING, errors="ignore")
        messages.append(msg)
        idx = e + len(MLLP_END)
    return messages, buf[idx:]

# ─────────────────────────── HL7 PARSE ────────────────────────
def _hl7_fields(segment: str):
    return segment.split("|")

def _decode_cyrillic(raw: str) -> str:
    """Windows-1251 kabi yozilgan kirill matnini UTF-8 ga o'girish"""
    if not raw:
        return ""
    try:
        fixed = raw.encode("latin-1").decode("utf-8")
        if any("\u0400" <= c <= "\u04ff" for c in fixed):
            return fixed.strip()
    except Exception:
        pass
    return raw.strip()

def _hl7_time(s: str, fallback: str = "") -> str:
    """YYYYMMDDHHMMSS → DD.MM.YYYY HH:MM"""
    try:
        if s and len(s) >= 8:
            y, mo, d = s[:4], s[4:6], s[6:8]
            h  = s[8:10]  if len(s) >= 10 else "00"
            mi = s[10:12] if len(s) >= 12 else "00"
            return f"{d}.{mo}.{y} {h}:{mi}"
    except Exception:
        pass
    return fallback

def _extract_msg_id(message: str) -> str:
    try:
        msh = message.split("\r")[0]
        f = msh.split("|")
        return f[9].strip() if len(f) > 9 else ""
    except Exception:
        return ""

def _extract_sample_id_from_orm(message: str) -> str:
    """ORM^O01 dan Sample ID (ORC-3 yoki OBR-3)"""
    for seg in message.split("\r"):
        if seg.startswith("ORC"):
            f = _hl7_fields(seg)
            if len(f) > 3 and f[3].strip():
                return f[3].split("^")[0].strip()
        if seg.startswith("OBR"):
            f = _hl7_fields(seg)
            if len(f) > 3 and f[3].strip():
                return f[3].split("^")[0].strip()
    return ""

def _parse_oru_r01(message: str) -> dict:
    """ORU^R01 dan bemor va natijalarni chiqarish"""
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    patient = {
        "time": now_str, "sample_id": "", "name": "",
        "age": "", "gender": "", "tests": {}, "abnormal": False
    }

    CLINICAL = {
        "WBC","LYM#","LYM%","MID#","MID%","GRAN#","GRAN%",
        "RBC","HGB","HCT","MCV","MCH","MCHC",
        "RDW-CV","RDW-SD","PLT","MPV","PDW","PCT","NLR","PLR"
    }
    NAME_MAP = {
        "6690-2":"WBC","731-0":"LYM#","736-9":"LYM%",
        "789-8":"RBC","718-7":"HGB","787-2":"MCV","785-6":"MCH",
        "786-4":"MCHC","788-0":"RDW-CV","21000-5":"RDW-SD",
        "4544-3":"HCT","777-3":"PLT","32623-1":"MPV","32207-3":"PDW",
        "10002":"PCT","10027":"MID#","10029":"MID%",
        "10028":"GRAN#","10030":"GRAN%","10057":"NLR","10058":"PLR",
    }

    raw_hl7 = message  # saqlash uchun

    for seg in message.split("\r"):
        seg = seg.strip()
        if not seg:
            continue
        tag = seg[:3]
        f   = _hl7_fields(seg)

        if tag == "MSH":
            if len(f) > 7 and f[7]:
                t = _hl7_time(f[7], now_str)
                if t:
                    patient["time"] = t

        elif tag == "PID":
            if len(f) > 5 and f[5]:
                parts = f[5].split("^")
                given  = _decode_cyrillic(parts[0]) if parts else ""
                family = _decode_cyrillic(parts[1]) if len(parts) > 1 else ""
                patient["name"] = (f"{family} {given}".strip()
                                   if family and given else given or family)
            if len(f) > 7 and f[7]:
                try:
                    bs = f[7].strip()
                    if len(bs) >= 8:
                        by, bm, bd = int(bs[:4]), int(bs[4:6]), int(bs[6:8])
                        today = date.today()
                        age = today.year - by - ((today.month, today.day) < (bm, bd))
                        patient["age"] = str(age)
                except Exception:
                    pass
            if len(f) > 8 and f[8]:
                g = f[8].strip().upper()
                try:
                    g = g.encode("latin-1").decode("utf-8").upper()
                except Exception:
                    pass
                if "М" in g or g in ("M","МУЖ","ERKAK"):
                    patient["gender"] = "Erkak"
                elif "Ж" in g or g in ("F","ЖЕН","AYOL","ЖЕНЩИНА"):
                    patient["gender"] = "Ayol"

        elif tag == "OBR":
            if len(f) > 3 and f[3]:
                sid = f[3].split("^")[0].strip()
                if sid:
                    patient["sample_id"] = sid
            if len(f) > 7 and f[7]:
                t = _hl7_time(f[7].strip(), patient["time"])
                if t:
                    patient["time"] = t

        elif tag == "OBX":
            if len(f) < 6:
                continue
            code_str = f[3] if len(f) > 3 else ""
            parts = code_str.split("^")
            test_code = parts[0].strip()
            test_name = parts[1].strip() if len(parts) > 1 else test_code

            # Yosh (30525-0) va jins guruhi (01002)
            if test_code == "30525-0" and len(f) > 5 and f[5] and not patient["age"]:
                patient["age"] = f[5].strip()
                continue
            if test_code == "01002" and len(f) > 5 and f[5]:
                rg = f[5].strip()
                try:
                    rg = rg.encode("latin-1").decode("utf-8")
                except Exception:
                    pass
                rl = rg.lower()
                if not patient["gender"]:
                    if "жен" in rl or "ayol" in rl:
                        patient["gender"] = "Ayol"
                    elif "муж" in rl or "erkak" in rl:
                        patient["gender"] = "Erkak"
                continue

            # Histogramlarni o'tkazib yuborish
            try:
                if test_code.isdigit() and 15000 <= int(test_code) <= 15200:
                    continue
            except Exception:
                pass

            # Parametr kalitini topish
            param_key = (NAME_MAP.get(test_code)
                         or (test_name.upper() if test_name.upper() in CLINICAL else None)
                         or (test_code.upper() if test_code.upper() in CLINICAL else None))
            if not param_key:
                continue

            value = f[5].strip() if len(f) > 5 else ""
            unit  = f[6].strip() if len(f) > 6 else ""
            ref   = f[7].strip() if len(f) > 7 else ""
            flag  = f[8].strip() if len(f) > 8 else ""
            fu    = flag.upper()
            if ("H" in fu or "L" in fu) and fu != "N":
                patient["abnormal"] = True

            patient["tests"][param_key] = {
                "name": test_name or param_key,
                "value": value, "unit": unit,
                "ref": ref, "flag": flag,
                "abnormal": ("H" in fu or "L" in fu) and fu != "N"
            }

    patient["_raw_hl7"] = raw_hl7
    return patient

# ─────────────────────────── TXT YOZISH ───────────────────────
def _next_mindray_txt_path() -> str:
    """Keyingi BC-20s_YYYYMMDD_NNN.txt fayl yo'lini qaytaradi"""
    now = datetime.now()
    ym  = now.strftime("%Y%m")
    ymd = now.strftime("%Y%m%d")
    folder = os.path.join(MINDRAY_DAT_BASE, ym)
    os.makedirs(folder, exist_ok=True)

    existing = sorted(glob.glob(os.path.join(folder, f"BC-20s_{ymd}_*.txt")))
    if existing:
        last_name = os.path.basename(existing[-1])
        m = re.search(r"_(\d+)\.txt$", last_name)
        next_n = (int(m.group(1)) + 1) if m else len(existing) + 1
    else:
        next_n = 1
    return os.path.join(folder, f"BC-20s_{ymd}_{next_n:03d}.txt")

def _write_to_mindray_txt(hl7_message: str) -> str:
    """HL7 xabarni Mindray-mos TXT fayliga yozish (har natija uchun alohida fayl)"""
    try:
        fpath = _next_mindray_txt_path()
        content = hl7_message
        if not content.endswith("\r"):
            content += "\r"
        with open(fpath, "w", encoding="utf-8", errors="replace", newline="") as fh:
            fh.write(content)
        _log(f"TXT yozildi: {fpath}")
        return fpath
    except Exception as e:
        _log(f"[XATO] TXT yozishda xato: {e}")
        return ""

# ─────────────────────────── DB SAQLASH ───────────────────────
def _save_to_db(patient: dict) -> bool:
    """ORU natijasini bazaga saqlash (order topilsa)"""
    try:
        from monoblok_db_config import DB_CONFIG
        import mysql.connector

        sample_id = patient.get("sample_id", "")
        tests     = patient.get("tests", {})
        if not sample_id or not tests:
            return False

        conn = mysql.connector.connect(**DB_CONFIG)
        cur  = conn.cursor(dictionary=True)

        # Order topish
        cur.execute("""
            SELECT o.id AS order_id, b.fish
            FROM orders o
            JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sample_id=%s OR b.sample_id=%s
               OR b.kod_yollanma=%s OR b.natija_kodi=%s
            ORDER BY o.sana_vaqt DESC LIMIT 1
        """, (sample_id, sample_id, sample_id, sample_id))
        row = cur.fetchone()

        if not row:
            _log(f"DB: order topilmadi sample_id={sample_id}")
            cur.close(); conn.close()
            return False

        order_id = row["order_id"]
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # results jadvali
        cur.execute("SELECT id FROM results WHERE order_id=%s", (order_id,))
        res_row = cur.fetchone()
        if res_row:
            result_id = res_row["id"]
            cur.execute("UPDATE results SET status='ready', updated_at=%s WHERE id=%s",
                        (now_str, result_id))
        else:
            cur.execute("""INSERT INTO results (order_id, status, created_at, updated_at)
                           VALUES (%s,'ready',%s,%s)""",
                        (order_id, now_str, now_str))
            result_id = cur.lastrowid

        HL7_TO_DB = {
            "WBC":"WBC","LYM#":"Lymph#","LYM%":"Lymph%","MID#":"Mid#","MID%":"Mid%",
            "GRAN#":"Gran#","GRAN%":"Gran%","RBC":"RBC","HGB":"HGB","HCT":"HCT",
            "MCV":"MCV","MCH":"MCH","MCHC":"MCHC","RDW-CV":"RDW-CV","RDW-SD":"RDW-SD",
            "PLT":"PLT","MPV":"MPV","PDW":"PDW","PCT":"PCT","NLR":"NLR","PLR":"PLR"
        }
        for pk, tdata in tests.items():
            val = tdata.get("value", "")
            if not val:
                continue
            db_name = HL7_TO_DB.get(pk, pk)
            unit    = tdata.get("unit", "")
            ref     = tdata.get("ref", "")
            flag    = tdata.get("flag", "")

            cur.execute("DELETE FROM result_items WHERE result_id=%s AND tahlil_nomi=%s",
                        (result_id, db_name))
            cur.execute("""INSERT INTO result_items
                           (result_id, tahlil_nomi, qiymat, birlik, norma, note)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (result_id, db_name, val, unit, ref,
                         f"BC-20S | {now_str} | Flag: {flag}"))

            rj = json.dumps({"result": val, "unit": unit, "ref": ref,
                             "flag": flag, "source": "BC-20S",
                             "sample_id": sample_id}, ensure_ascii=False)
            cur.execute("""INSERT INTO test_results
                           (order_id, test_name, test_type, result_data, status)
                           VALUES (%s,%s,'numeric',%s,'Saqlandi')
                           ON DUPLICATE KEY UPDATE
                           result_data=VALUES(result_data),
                           status='Saqlandi', updated_at=CURRENT_TIMESTAMP""",
                        (str(order_id), db_name, rj))

        conn.commit()
        cur.close(); conn.close()
        _log(f"DB: order_id={order_id} ga {len(tests)} natija saqlandi")
        return True
    except Exception as e:
        _log(f"[XATO] DB saqlashda xato: {e}")
        return False

# ─────────────────────────── HL7 BUILDER ──────────────────────
def _build_ack(msg_id: str, code: str = "AA", error: str = "") -> str:
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    msh = f"MSH|^~\\&|LIS||||{now}||ACK^R01|{msg_id}|P|2.3.1||||||UNICODE"
    msa = f"MSA|{code}|{msg_id}" + (f"|{error}" if error else "")
    return f"{msh}\r{msa}"

def _build_orr_o02(patient_data: dict, msg_id: str, req_msg_id: str = "") -> str:
    """Worklist Response (ORR^O02) — analizatorga bemor ismi yuboriladi

    OBR segment vaqtlari:
      OBR-6  = collection_time = ro'yxatdan o'tgan vaqt (order_time)  → "Время отбора"
      OBR-14 = delivery_time   = hozirgi vaqt (tahlil qilinayotgan)  → "Время доставки"
    """
    now  = datetime.now().strftime("%Y%m%d%H%M%S")
    name = str(patient_data.get("patient_name", "")).strip()
    pid_val = str(patient_data.get("patient_id", "")).strip()
    gender  = str(patient_data.get("gender", "U")).strip()
    age     = patient_data.get("age", 0)
    sample  = str(patient_data.get("sample_id", pid_val)).strip()
    dob     = str(patient_data.get("date_of_birth") or "19000101")
    if len(dob) > 10:
        dob = dob[:10].replace("-", "")
    op  = str(patient_data.get("operator", "admin")).strip()

    # Vaqtlar
    delivery_time = now  # hozirgi vaqt → "Время доставки"

    # collection_time = ro'yxatdan o'tgan vaqt → "Время отбора"
    order_time = patient_data.get("order_time")
    if order_time:
        try:
            if hasattr(order_time, "strftime"):
                collection_time = order_time.strftime("%Y%m%d%H%M%S")
            else:
                # "2026-03-17 10:09:10" formatdan
                ot = str(order_time).replace("-", "").replace(":", "").replace(" ", "")
                collection_time = ot[:14]
        except Exception:
            collection_time = now
    else:
        collection_time = now

    msh = f"MSH|^~\\&|LIS||||{now}||ORR^O02|{msg_id}|P|2.3.1||||||UNICODE"
    msa = f"MSA|AA|{req_msg_id or msg_id}"
    pid = f"PID|1||{pid_val}^^{pid_val}^^MR||{name}||{dob}000000||{gender}"
    pv1 = "PV1|1||ICU"
    orc = f"ORC|AF|{sample}"
    # OBR: [6]=collection_time(Время отбора), [10]=operator, [14]=delivery_time(Время доставки), [24]=HM, [32]=operator
    obr = f"OBR|1||{sample}|00001^Automated Count^99MRC||{collection_time}||||{op}||||{delivery_time}||||||||||HM||||||||{op}"
    obx1 = "OBX|1|IS|08002^Blood Mode^99MRC||W||||||F"
    obx2 = "OBX|2|IS|08003^Test Mode^99MRC||CBC||||||F"
    obx3 = f"OBX|3|NM|30525-0^Age^LN||{age}|yr|||||F"
    return "\r".join([msh, msa, pid, pv1, orc, obr, obx1, obx2, obx3])

# ─────────────────────────── DB QUERY (WORKLIST) ──────────────
def _get_patient_for_worklist(sample_id: str) -> dict | None:
    """Sample ID bo'yicha DB dan bemor ma'lumotini olish"""
    try:
        from monoblok_db_config import DB_CONFIG
        import mysql.connector

        conn = mysql.connector.connect(**DB_CONFIG)
        cur  = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT b.id AS bemor_id, b.fish, b.yosh, b.jins,
                   b.tugilgan_sana, b.natija_kodi, b.kod_yollanma,
                   b.shifokor,
                   o.id AS order_id, o.sample_id AS order_sample_id,
                   o.sana_vaqt AS order_time
            FROM orders o
            JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sample_id=%s OR b.sample_id=%s
               OR b.natija_kodi=%s OR b.kod_yollanma=%s
            ORDER BY o.sana_vaqt DESC LIMIT 1
        """, (sample_id, sample_id, sample_id, sample_id))
        row = cur.fetchone()
        cur.close(); conn.close()

        if not row:
            return None

        jins = (row.get("jins") or "").lower()
        gender = ("M" if ("erkak" in jins or jins.startswith("e") or jins == "m") else
                  "F" if ("ayol" in jins or jins.startswith("a") or jins == "f") else "U")

        dob = ""
        if row.get("tugilgan_sana"):
            try:
                dob = str(row["tugilgan_sana"]).replace("-", "")[:8]
            except Exception:
                pass

        return {
            "patient_id":   row.get("natija_kodi") or row.get("kod_yollanma") or str(row["bemor_id"]),
            "patient_name": row.get("fish") or "",
            "gender":       gender,
            "age":          row.get("yosh") or 0,
            "date_of_birth": dob,
            "sample_id":    row.get("order_sample_id") or sample_id,
            "order_time":   row.get("order_time"),
            "operator":     row.get("shifokor") or "admin"
        }
    except Exception as e:
        _log(f"[XATO] Worklist DB query: {e}")
        return None

# ─────────────────────────── MESSAGE HANDLER ──────────────────
_msg_counter = [1]

def _process_message(message: str, sock: socket.socket):
    """Kelgan HL7 xabarni qayta ishlash"""
    global _result_callback

    msh_line = message.split("\r")[0] if "\r" in message else message[:200]

    # ── ORM^O01 — Worklist query (barcode skanerda o'qilganda) ─
    if "ORM^O01" in msh_line or "ORM" in msh_line:
        _log("◄ ORM^O01 (Worklist) qabul qilindi")
        sample_id = _extract_sample_id_from_orm(message)
        req_msg_id = _extract_msg_id(message)

        if sample_id:
            patient = _get_patient_for_worklist(sample_id)
            if patient:
                _log(f"  -> Bemor topildi: {patient['patient_name']} (sample={sample_id})")
                resp_id = str(_msg_counter[0])
                _msg_counter[0] += 1
                hl7_resp = _build_orr_o02(patient, resp_id, req_msg_id)
                try:
                    sock.sendall(_wrap_mllp(hl7_resp))
                    _log(f"  >>> ORR^O02 yuborildi (ism: {patient['patient_name']})")
                except Exception as e:
                    _log(f"[XATO] ORR^O02 yuborishda: {e}")
            else:
                _log(f"  -> Bemor topilmadi (sample={sample_id}), AR javob")
                ack = _build_ack(req_msg_id, "AR", "204^Unknown patient ID")
                try:
                    sock.sendall(_wrap_mllp(ack))
                except Exception:
                    pass
        else:
            _log("  -> Sample ID topilmadi, AE javob")
            ack = _build_ack(req_msg_id, "AE", "202^Sample ID not found")
            try:
                sock.sendall(_wrap_mllp(ack))
            except Exception:
                pass

    # ── ORU^R01 — Natija ──────────────────────────────────────
    elif "ORU^R01" in msh_line or "ORU" in msh_line:
        _log("◄ ORU^R01 (Natija) qabul qilindi")
        msg_id = _extract_msg_id(message)

        # 1. ACK darhol yuborish
        ack = _build_ack(msg_id, "AA")
        try:
            sock.sendall(_wrap_mllp(ack))
            _log("  >>> ACK yuborildi")
        except Exception as e:
            _log(f"[XATO] ACK yuborishda: {e}")

        # 2. Parse qilish
        patient = _parse_oru_r01(message)
        sid = patient.get("sample_id", "")
        _log(f"  Sample: {sid} | Ism: {patient.get('name', '?')} | Tests: {len(patient.get('tests', {}))}")

        # 3. TXT ga DARHOL yozish (hematologiya oynasi shu fayldan o'qiydi)
        _write_to_mindray_txt(message)

        # 4. DB ga saqlash (order topilsa)
        db_ok = _save_to_db(patient)

        # 5. UI ga signal (hematologiya oynasini yangilash)
        cb = _result_callback
        if cb:
            try:
                cb(sid, patient)
            except Exception as e:
                _log(f"[XATO] result_callback: {e}")

        _log(f"  OK: TXT=yozildi, DB={'saqlandi' if db_ok else 'order topilmadi'}")

    else:
        _log(f"  Noma'lum xabar: {msh_line[:60]}")
        msg_id = _extract_msg_id(message)
        if msg_id:
            ack = _build_ack(msg_id, "AE", "200^Unknown message type")
            try:
                sock.sendall(_wrap_mllp(ack))
            except Exception:
                pass

# ─────────────────────────── TCP CLIENT LOOP ─────────────────
def _close_socket(sock: socket.socket):
    """Socketni xavfsiz yopish"""
    if sock:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

def _connect_once(ip: str, port: int) -> socket.socket | None:
    """Bir marta ulanishga harakat qilish"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.settimeout(SOCKET_TIMEOUT)
        s.connect((ip, port))
        return s
    except Exception as e:
        _log(f"[XATO] Ulanish: {e}")
        try:
            s.close()
        except Exception:
            pass
        return None

def _client_loop(ip: str, port: int):
    """
    Asosiy TCP CLIENT loop:
      1. Analizatorga ulanish (192.168.0.2:5100)
      2. Heartbeat/MLLP xabarlarni qabul qilish
      3. Uzilsa → qayta ulanish (cheksiz)
    Bu URIT siydik analizatori kabi — ma'lumot HECH QACHON yo'qolmaydi.
    """
    global _running, _socket, _connected

    _log(f"BC-20S client ishga tushdi — analizator: {ip}:{port}")

    while _running:
        # ── 1. ULANISH ──
        _log(f"Analizatorga ulanmoqda: {ip}:{port} ...")
        _connected = False
        _socket = None

        attempt = 0
        while _running:
            attempt += 1
            sock = _connect_once(ip, port)
            if sock:
                with _lock:
                    _socket = sock
                    _connected = True
                _log(f"Analizatorga ulandi! (urinish #{attempt})")
                break
            else:
                if MAX_RECONNECT > 0 and attempt >= MAX_RECONNECT:
                    _log(f"[XATO] Maksimal urinishlar soni oshdi ({MAX_RECONNECT})")
                    _running = False
                    return
                _log(f"  Qayta ulanish {RECONNECT_INTERVAL}s dan keyin... (urinish #{attempt})")
                # Kutish — lekin _running tekshiruvi bilan
                for _ in range(RECONNECT_INTERVAL * 10):
                    if not _running:
                        return
                    time.sleep(0.1)

        if not _running:
            break

        # ── 2. QABUL QILISH LOOP ──
        buf = b""
        try:
            while _running and _connected:
                try:
                    ready, _, _ = select.select([_socket], [], [], 1.0)
                    if not ready:
                        continue

                    data = _socket.recv(8192)
                    if not data:
                        # Socket yopilgan
                        _log("Analizator ulanishni yopdi (no data)")
                        break

                    # Heartbeat — analizator har 3 soniyada \x02 yuboradi
                    if data == HEARTBEAT:
                        continue

                    # Heartbeat aralash kelishi mumkin — tozalash
                    data = data.replace(HEARTBEAT, b"")
                    if not data:
                        continue

                    buf += data

                    # MLLP xabarlarni ajratib olish
                    messages, buf = _unwrap_mllp(buf)
                    for msg in messages:
                        if msg:
                            try:
                                _process_message(msg, _socket)
                            except Exception as e:
                                _log(f"[XATO] process_message: {e}")
                                traceback.print_exc()

                except socket.timeout:
                    continue
                except OSError as e:
                    _log(f"[XATO] Socket xatosi: {e}")
                    break
                except Exception as e:
                    _log(f"[XATO] Qabul qilish xatosi: {e}")
                    break
        finally:
            # Ulanishni yopish
            with _lock:
                _connected = False
                _close_socket(_socket)
                _socket = None

        # ── 3. QAYTA ULANISH ──
        if _running:
            _log(f"Ulanish uzildi — {RECONNECT_INTERVAL}s dan keyin qayta ulaniladi...")
            for _ in range(RECONNECT_INTERVAL * 10):
                if not _running:
                    return
                time.sleep(0.1)

    _log("BC-20S client to'xtatildi")

# ─────────────────────────── PUBLIC API ───────────────────────
def start_bc20s_listener(host: str = None,
                         analyzer_ip: str = ANALYZER_IP,
                         port: int = ANALYZER_PORT,
                         result_callback=None) -> threading.Thread | None:
    """
    BC-20S analizatorga CLIENT sifatida ulanish (background thread).

    Args:
        host:            (eskirgan, e'tiborsiz) eski SERVER mode uchun edi
        analyzer_ip:     analizator IP manzili (default: 192.168.0.2)
        port:            analizator porti (default: 5100)
        result_callback: fn(sample_id, patient_info) — har natijada chaqiriladi

    Returns:
        Thread obyekti yoki None (xato bo'lsa)
    """
    global _running, _client_thread, _result_callback

    if _running:
        _log("Allaqachon ishlayapti, qayta ishga tushirilmadi")
        return _client_thread

    _result_callback = result_callback
    _running = True

    t = threading.Thread(target=_client_loop, args=(analyzer_ip, port),
                         daemon=True, name="bc20s-client")
    t.start()
    _client_thread = t
    return t

def stop_bc20s_listener():
    """BC-20S client ni to'xtatish"""
    global _running, _socket, _connected
    _running = False
    with _lock:
        _connected = False
        _close_socket(_socket)
        _socket = None
    _log("BC-20S client to'xtatilish so'rovi")

def is_running() -> bool:
    return _running and _client_thread is not None and _client_thread.is_alive()

# ─────────────────────────── STANDALONE TEST ──────────────────
if __name__ == "__main__":
    def on_result(sid, pinfo):
        print(f"\n  YANGI NATIJA: {pinfo.get('name', '?')} (sample={sid})")
        for k, v in pinfo.get("tests", {}).items():
            print(f"   {k}: {v['value']} {v['unit']} [{v['ref']}] {v['flag']}")

    print("=" * 60)
    print("  BC-20S CLIENT — Analizatorga ulanish")
    print(f"  Analizator: {ANALYZER_IP}:{ANALYZER_PORT}")
    print("=" * 60)

    thread = start_bc20s_listener(result_callback=on_result)
    print("BC-20S client ishlamoqda. Ctrl+C bilan to'xtating...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_bc20s_listener()
        print("To'xtatildi.")
