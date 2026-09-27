# -*- coding: utf-8 -*-
"""
Siydik analizatorlari uchun UNIVERSAL ulanish va parse moduli.

Mijozlarda turli siydik analizatorlari bo'lishi mumkin (URIT-50, Dirui H-100/H-300,
Mindray UA-66, Uriscan, Combilyzer, yoki HL7/ASTM yuboradigan kattaroq modellar).
Shu modul ularning hammasini bitta umumiy natija lug'atiga keltiradi:

    {"NO": "...", "ID": "...", "DATE": "...", "TIME": "...",
     "LEU": "...", "KET": "...", ..., "ABNORMAL": ["LEU", ...]}

Bu lug'at urit50_service.py (blanka + baza) va urine_window.py (RAW ko'rish)
tomonidan bir xil ishlatiladi — analizator o'zgarsa, faqat sozlama o'zgaradi.

Uch qatlam:
  1) PROFIL  — analizator modeli (kod nomlari, standart ulanish, freym turi)
  2) TRANSPORT — serial (COM), tcp_server (analizator bizga ulanadi),
                 tcp_client (biz analizatorga ulanamiz)
  3) PARSER  — 'text' (STX...ETX printer-uslubidagi matn), 'hl7' (ORU^R01, MLLP),
               'astm' (E1394 yozuvlar, E1381 freymlar)

O'rganilgan hujjatlar (2026-09):
  * URIT-50 — RAW loglar (Urit/RAW_LOGS): STX, "ID:", "NO.xxxxxx YYYY-MM-DD",
    "HH:MM:SS", so'ng " LEU -  0 CELL/uL" ko'rinishidagi qatorlar, '*' = patologiya, ETX.
  * Dirui H-100/H-300 User Manual, Appendix B "Interface for Communicating with
    Computer": RS-232 9600/1200 8N1, STX(02H) ... ETX(03H), CRLF qatorlar,
    "Date:YYYY-MM-DD HH:MM", "No. xxxx", "ID：..." (to'liq kenglikdagi ikki nuqta!),
    kodlar: UBG BIL KET CRE BLD PRO ALB NIT LEU GLU SG PH VC Ca A:C RT;
    SP1=0xAB ajratuvchi bayt ishlatiladi (kodirovkada buziladi → bo'sh joyga almashtiramiz).
  * Mindray UA-66 — RS-232, 11 parametr (URO BIL KET BLD PRO NIT LEU GLU SG VC PH),
    printer-uslubidagi matn bloki; Mindray UA-600/UA-1600 — HL7 (MLLP, TCP).
  * Dirui H-500/H-800/FUS — HL7 yoki ASTM (LIS sozlamasiga qarab).
"""

import re
import socket
import time
from datetime import datetime

try:
    import serial  # pyserial
except Exception:  # pragma: no cover
    serial = None

# ─────────────────────────────────────────────────────────────────────────────
#  KANONIK KODLAR — dastur ichida ishlatiladigan kalitlar (blanka/baza shu bilan ishlaydi)
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL = ["LEU", "KET", "NIT", "URO", "BIL", "PRO", "GLU", "SG", "pH", "BLD",
             "Vc", "MA", "Ca", "CR", "ACR"]

# Analizatorlar ishlatadigan barcha nom variantlari → kanonik kod.
# Kalitlar UPPERCASE, '.' ':' '-' ' ' olib tashlangan holda solishtiriladi.
CODE_ALIASES = {
    # Leykotsit
    "LEU": "LEU", "LEUKO": "LEU", "LEUKOCYTES": "LEU", "WBC": "LEU", "LEUC": "LEU",
    # Keton
    "KET": "KET", "KETONE": "KET", "KETONES": "KET", "KETO": "KET",
    # Nitrit
    "NIT": "NIT", "NITRITE": "NIT", "NITRIT": "NIT",
    # Urobilinogen
    "URO": "URO", "UBG": "URO", "UROBILINOGEN": "URO", "URB": "URO",
    # Bilirubin
    "BIL": "BIL", "BILIRUBIN": "BIL", "BILI": "BIL",
    # Oqsil
    "PRO": "PRO", "PROT": "PRO", "PROTEIN": "PRO", "PRT": "PRO",
    # Glyukoza
    "GLU": "GLU", "GLUCOSE": "GLU", "GLUC": "GLU", "GLC": "GLU",
    # Nisbiy zichlik
    "SG": "SG", "SPECIFICGRAVITY": "SG", "S.G": "SG", "DENS": "SG", "SPG": "SG",
    # pH
    "PH": "pH",
    # Qon
    "BLD": "BLD", "BLOOD": "BLD", "ERY": "BLD", "ERYTHROCYTES": "BLD", "BLO": "BLD",
    "OB": "BLD", "HB": "BLD", "RBC": "BLD", "OCCULTBLOOD": "BLD",
    # Askorbin kislota
    "VC": "Vc", "ASC": "Vc", "ASCORBICACID": "Vc", "AA": "Vc", "VITC": "Vc",
    # Mikroalbumin
    "MA": "MA", "ALB": "MA", "MALB": "MA", "MAU": "MA", "MICROALBUMIN": "MA", "UALB": "MA",
    # Kalsiy
    "CA": "Ca", "CALCIUM": "Ca",
    # Kreatinin
    "CR": "CR", "CRE": "CR", "CREA": "CR", "CREATININE": "CR", "UCR": "CR",
    # Albumin/kreatinin nisbati
    "ACR": "ACR", "AC": "ACR", "A:C": "ACR", "UACR": "ACR", "ALBCR": "ACR", "MACR": "ACR",
}


def normalize_code(code: str):
    """Analizator kodini kanonik kodga keltiradi. Noma'lum bo'lsa None."""
    if not code:
        return None
    key = re.sub(r"[\s.\-_/]", "", str(code)).upper()
    if key in CODE_ALIASES:
        return CODE_ALIASES[key]
    key2 = key.replace(":", "")
    return CODE_ALIASES.get(key2)


# ─────────────────────────────────────────────────────────────────────────────
#  PROFILLAR — analizator modellari. UI da tanlanadi, sozlamaga standart qiymat beradi.
#  "protocol": text | hl7 | astm   (bitta model ikkisini ham qo'llashi mumkin —
#  o'shanda foydalanuvchi sozlamada tanlaydi; parser baribir avtomatik aniqlaydi)
# ─────────────────────────────────────────────────────────────────────────────
PROFILES = {
    "urit50": {
        "name": "URIT-50 / URIT-30 / URIT-31 (Urit)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "Analizatorda 'RS232' tugmasi → natija yuboriladi. STX...ETX matn bloki.",
    },
    "urit_hl7": {
        "name": "URIT-500 / URIT-1000+ (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5200,
        "hint": "Analizator LIS sozlamasida kompyuter IP + shu port yoziladi.",
    },
    "dirui_h": {
        "name": "Dirui H-100 / H-300 / H-50 (RS-232)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "Analizatorda Setup → 'PC Port' = ON, Baud 9600. Kodlar: UBG BIL KET CRE BLD PRO ALB NIT LEU GLU SG PH VC Ca A:C",
    },
    "dirui_hl7": {
        "name": "Dirui H-500 / H-800 / FUS (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5200,
        "hint": "Analizator LIS sozlamasida 'HL7', Server IP = kompyuter IP, Port = shu port.",
    },
    "mindray_ua66": {
        "name": "Mindray UA-66 (RS-232)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "11 parametr: URO BIL KET BLD PRO NIT LEU GLU SG VC PH. Setup → Communication → Transmit ON.",
    },
    "mindray_ua_hl7": {
        "name": "Mindray UA-600 / UA-1600 / UA-5600 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5200,
        "hint": "Analizator Setup → Communication → LIS: HL7, IP = kompyuter IP, Port = shu port.",
    },
    "uriscan": {
        "name": "Uriscan Optima / Pro (YD Diagnostics, RS-232)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "Matn yoki ASTM — protokolni analizator 'Interface' sozlamasiga mos tanlang.",
    },
    "combilyzer": {
        "name": "Combilyzer 13 / Urilyzer 100 / DocUReader (77 Elektronika)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "Analizator Settings → Output → 'Unidirectional text' yoki 'LIS2-A2 (ASTM)'. Mos protokolni tanlang.",
    },
    "astm_generic": {
        "name": "Boshqa (ASTM E1394 — Sysmex, Roche, Siemens, Erba ...)",
        "connection_type": "serial", "protocol": "astm",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "ENQ/ACK qo'l berish avtomatik. TCP orqali ham ishlaydi (ulanish turini o'zgartiring).",
    },
    "hl7_generic": {
        "name": "Boshqa (HL7 ORU^R01, MLLP, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5200,
        "hint": "Har qanday HL7 yuboradigan siydik analizatori. OBX-3 kodlari avtomatik moslanadi.",
    },
    "text_generic": {
        "name": "Boshqa (matnli STX/ETX, RS-232)",
        "connection_type": "serial", "protocol": "text",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1,
        "hint": "Printer-uslubidagi matn: har qatorda KOD + qiymat. Noma'lum kodlar logda ko'rsatiladi.",
    },
}
DEFAULT_MODEL = "urit50"


def profile_for(cfg: dict) -> dict:
    return PROFILES.get((cfg or {}).get("model") or DEFAULT_MODEL, PROFILES[DEFAULT_MODEL])


def effective_config(cfg: dict) -> dict:
    """Profil standartlari ustiga foydalanuvchi sozlamasini qo'yadi."""
    prof = profile_for(cfg)
    out = {k: v for k, v in prof.items() if k not in ("name", "hint")}
    for k, v in (cfg or {}).items():
        if v not in (None, ""):
            out[k] = v
    out.setdefault("connection_type", "serial")
    out.setdefault("protocol", "auto")
    out.setdefault("encoding", "utf-8")
    out.setdefault("ip", "0.0.0.0")
    out.setdefault("port", 5200)
    out.setdefault("timeout", 1.0)
    out.setdefault("idle_timeout", 3.0)   # ETX kelmasa — shuncha soniya jimlikdan keyin blok yopiladi
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  FORMAT ANIQLASH
# ─────────────────────────────────────────────────────────────────────────────
STX, ETX, EOT, ENQ, ACK, NAK, ETB = "\x02", "\x03", "\x04", "\x05", "\x06", "\x15", "\x17"
MLLP_SB, MLLP_EB = b"\x0b", b"\x1c\x0d"


def detect_format(raw: str) -> str:
    """'hl7' | 'astm' | 'text'"""
    s = (raw or "").lstrip("\x0b\x02\x05\r\n\t ")
    if s.startswith("MSH|"):
        return "hl7"
    # ASTM: 'H|\^&' sarlavha yozuvi (freym raqami bilan: '1H|')
    if re.match(r"^\d?H\|\\\^&", s) or re.search(r"(^|\r|\n)\d?[POR]\|\d+\|", s):
        return "astm"
    return "text"


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER: MATN (URIT-50, Dirui H, UA-66, Uriscan, ...)
# ─────────────────────────────────────────────────────────────────────────────
# Qator boshidagi kod: "LEU", "pH", "A:C", "S.G", "Vc" ... (birinchi token, bo'sh joygacha)
_CODE_LINE_RE = re.compile(r"^\s*([*!#]?)\s*([A-Za-z][A-Za-z:.]{0,14})(?=\s|$|[=:\-+<>0-9])(.*)$")

# Qiymat shakllarini URIT uslubiga keltirish ("1+" → "+1", "neg" → "-", "trace" → "+-").
# Blanka/mikroskopiya mantiqi shu shaklga moslangan.
_GRADE_RE = re.compile(r"^\s*(\d)\s*\+")
_NEG_RE = re.compile(r"^\s*(negative|negativ|nega|neg|отриц|отр)\.?(?![A-Za-zА-Яа-я])", re.IGNORECASE)
_TRACE_RE = re.compile(r"^\s*(trace|tr\.|±|\+/-|\+-|след\.?)(?![A-Za-z])\s*", re.IGNORECASE)
_POS_RE = re.compile(r"^\s*(positive|pos|полож)\.?(?![A-Za-zА-Яа-я])", re.IGNORECASE)


def normalize_value(text: str) -> str:
    """Analizatorlar turlicha yozadigan sifat natijalarini bir shaklga keltiradi."""
    if not text:
        return text
    t = str(text).strip()
    t = t.replace("CELL/uL", "CELL/µL").replace("Cell/uL", "CELL/µL").replace("cell/uL", "CELL/µL")
    if _NEG_RE.match(t):
        t = _NEG_RE.sub("-", t, count=1)
    elif _TRACE_RE.match(t):
        t = _TRACE_RE.sub("+- ", t, count=1).strip()
    elif _GRADE_RE.match(t):
        t = _GRADE_RE.sub(lambda m: "+" + m.group(1), t, count=1)
    elif _POS_RE.match(t):
        t = _POS_RE.sub("+", t, count=1)
    return re.sub(r"\s{2,}", " ", t).strip() if t.count(" ") > 6 else t
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_DATE_RE = re.compile(r"\b(\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}[-./]\d{1,2}[-./]\d{4})\b")


def _empty_result():
    r = {"NO": None, "ID": None, "DATE": None, "TIME": None}
    return r


def parse_text_block(block: str) -> dict:
    """STX...ETX matn blokini (URIT-50 / Dirui H / UA-66 va h.k.) lug'atga aylantiradi."""
    text = (block or "").replace("\xab", " ").replace("\x02", "").replace("\x03", "")
    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    result = _empty_result()
    values, abnormal, extra = {}, set(), {}

    # 1) Sarlavha: ID / NO / sana / vaqt
    for line in lines:
        lc = line.strip()
        if not lc:
            continue
        m = re.match(r"^\*?\s*ID\s*[:：]\s*(.*)$", lc, re.IGNORECASE)
        if m and result["ID"] is None:
            result["ID"] = m.group(1).strip()
            continue
        # "NO.000009", "No. 0012", "No: 12" — lekin "Normal" emas (NO dan keyin . : yoki bo'sh joy shart)
        m = re.match(r"^\*?\s*NO(?:\.|\s*[:：]|\s+)\s*(\S+)(.*)$", lc, re.IGNORECASE)
        if m and result["NO"] is None:
            result["NO"] = m.group(1).strip()
            rest = m.group(2)
            dm = _DATE_RE.search(rest)
            if dm and result["DATE"] is None:
                result["DATE"] = dm.group(1)
            tm = _TIME_RE.search(rest)
            if tm and result["TIME"] is None:
                result["TIME"] = tm.group(0)
            continue
        if re.match(r"^\*?\s*(DATE|TIME)\b", lc, re.IGNORECASE) or (
                result["DATE"] is None and _DATE_RE.search(lc) and not _CODE_LINE_RE.match(lc)):
            dm = _DATE_RE.search(lc)
            if dm and result["DATE"] is None:
                result["DATE"] = dm.group(1)
            tm = _TIME_RE.search(lc)
            if tm and result["TIME"] is None:
                result["TIME"] = tm.group(0)
            continue
        # URIT: alohida qatorda faqat vaqt ("            04:30:20")
        if result["TIME"] is None and re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", lc):
            result["TIME"] = lc

    # 2) Analitlar
    def _code_of(line):
        m = _CODE_LINE_RE.match(line.replace("*", " ").replace("!", " "))
        if not m:
            return None, None
        tok = m.group(2)
        code = normalize_code(tok) or normalize_code(tok.rstrip(":."))
        return code, m
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        lc = line.strip()
        i += 1
        if not lc or re.match(r"^\*?\s*(ID\s*[:：]|NO(?:\.|\s*[:：]|\s)|DATE|TIME)", lc, re.IGNORECASE):
            continue
        starred = "*" in line or "!" in line
        code, m = _code_of(line)
        if code is None:
            # noma'lum kod (masalan Dirui 'RT') — logga
            m2 = _CODE_LINE_RE.match(lc)
            if m2:
                extra[m2.group(2)] = m2.group(3).strip()
            continue
        after = m.group(3).replace("*", "").strip(" :=\t")
        raw_after = m.group(3)
        # Davomi qatorlar (kod bo'lmagan, bo'sh bo'lmagan) — qiymatga qo'shiladi
        while i < n:
            nxt = lines[i].strip()
            if not nxt:
                break
            c2, _ = _code_of(lines[i])
            # boshqa kod qatori (ma'lum yoki noma'lum qisqa kod, masalan Dirui 'RT') — davomi emas
            is_hdr = re.match(r"^\*?\s*(ID\s*[:：]|NO(?:\.|\s*[:：]|\s)|DATE|TIME)", nxt, re.IGNORECASE)
            is_code_like = re.match(r"^[*!]?\s*[A-Za-z][A-Za-z:.]{0,4}(\s|$)", nxt)
            if c2 is not None or is_hdr or is_code_like:
                break
            after += " " + nxt.replace("*", "").strip()
            i += 1
        after = normalize_value(after)
        # URIT uslubi: bosh '-' (manfiy belgisi) olib tashlanadi — "- 0 CELL/uL" → "0 CELL/uL";
        # faqat belgi bo'lsa ("NIT -", "neg") → "-"
        had_neg = after.startswith("-") or "-" in raw_after
        after = after.strip(" :=-	")
        if not after and had_neg:
            after = "-"   # manfiy natija ("NIT -")
        if code in values and values[code]:
            continue      # birinchi qiymat ustun
        values[code] = after
        if starred:
            abnormal.add(code)

    result.update(values)
    result["ABNORMAL"] = sorted(abnormal)
    if extra:
        result["EXTRA"] = extra
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER: HL7 ORU^R01
# ─────────────────────────────────────────────────────────────────────────────
def _hl7_ts(ts: str):
    ts = (ts or "").strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", ts)
    if not m:
        return None, None
    y, mo, d, hh, mm, ss = m.groups()
    date = f"{y}-{mo}-{d}"
    tm = f"{hh or '00'}:{mm or '00'}:{ss or '00'}" if hh else None
    return date, tm


def parse_hl7_block(msg: str) -> dict:
    """ORU^R01 xabarini lug'atga aylantiradi (OBX-3 kod → kanonik)."""
    result = _empty_result()
    values, abnormal, extra = {}, set(), {}
    result["PATIENT_NAME"] = ""
    segs = [s for s in re.split(r"[\r\n]+", msg or "") if s.strip()]
    sample_from_obr, sample_from_pid, sample_from_spm = None, None, None
    for seg in segs:
        f = seg.split("|")
        tag = f[0].lstrip("\x0b")
        if tag == "MSH":
            d, t = _hl7_ts(f[6] if len(f) > 6 else "")
            result["DATE"], result["TIME"] = result["DATE"] or d, result["TIME"] or t
        elif tag == "PID":
            if len(f) > 3 and f[3]:
                sample_from_pid = f[3].split("^")[0].strip()
            if len(f) > 5 and f[5]:
                result["PATIENT_NAME"] = " ".join(x for x in f[5].split("^")[:2] if x).strip()
        elif tag == "OBR":
            if len(f) > 3 and f[3]:
                sample_from_obr = f[3].split("^")[0].strip()
            elif len(f) > 2 and f[2]:
                sample_from_obr = f[2].split("^")[0].strip()
            if len(f) > 7 and f[7]:
                d, t = _hl7_ts(f[7])
                if d:
                    result["DATE"], result["TIME"] = d, t
        elif tag == "SPM":
            if len(f) > 2 and f[2]:
                sample_from_spm = f[2].split("^")[0].split("&")[0].strip()
        elif tag == "OBX":
            if len(f) < 6:
                continue
            ident = f[3]
            parts = ident.split("^")
            code = None
            for cand in parts[:3]:
                code = normalize_code(cand)
                if code:
                    break
            val = (f[5] or "").replace("^", " ").strip()
            unit = (f[6].split("^")[0].strip() if len(f) > 6 and f[6] else "")
            flag = (f[8].strip() if len(f) > 8 else "")
            if code is None:
                extra[parts[0] or ident] = val
                continue
            text = normalize_value(val if not unit or unit.lower() in val.lower() or not re.search(r"\d", val) else f"{val} {unit}")
            if code not in values:
                values[code] = text
            if flag and flag.upper() not in ("N", ""):
                abnormal.add(code)
    result["ID"] = sample_from_obr or sample_from_spm or sample_from_pid
    result["NO"] = sample_from_obr or sample_from_spm or sample_from_pid
    result.update(values)
    result["ABNORMAL"] = sorted(abnormal)
    if extra:
        result["EXTRA"] = extra
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER: ASTM E1394 (yozuvlar H/P/O/R/L)
# ─────────────────────────────────────────────────────────────────────────────
_ASTM_FRAME_RE = re.compile(r"\x02\d?|[\x03\x17][0-9A-Fa-f]{2}\r?\n?|\x04|\x05|\x06|\x15")


def parse_astm_block(msg: str) -> dict:
    result = _empty_result()
    values, abnormal, extra = {}, set(), {}
    result["PATIENT_NAME"] = ""
    clean = _ASTM_FRAME_RE.sub("", msg or "")
    records = [r for r in re.split(r"[\r\n]+", clean) if r.strip()]
    for rec in records:
        f = rec.split("|")
        rt = f[0].strip().lstrip("0123456789")   # '1H' → 'H'
        if rt == "H":
            if len(f) > 13:
                d, t = _hl7_ts(f[13])
                result["DATE"], result["TIME"] = d, t
        elif rt == "P":
            if len(f) > 5 and f[5]:
                result["PATIENT_NAME"] = " ".join(x for x in f[5].split("^")[:2] if x).strip()
            if len(f) > 3 and f[3] and result["ID"] is None:
                result["ID"] = f[3].strip()
        elif rt == "O":
            if len(f) > 2 and f[2]:
                sid = f[2].split("^")[0].strip()
                if sid:
                    result["ID"] = sid
                    result["NO"] = sid
            if len(f) > 3 and f[3] and not result["NO"]:
                result["NO"] = f[3].split("^")[0].strip()
            if len(f) > 7 and f[7]:
                d, t = _hl7_ts(f[7])
                if d:
                    result["DATE"], result["TIME"] = d, t
        elif rt == "R":
            if len(f) < 4:
                continue
            parts = f[2].split("^")
            code = None
            for cand in reversed(parts):
                code = normalize_code(cand)
                if code:
                    break
            val = (f[3] or "").replace("^", " ").strip()
            unit = f[4].strip() if len(f) > 4 else ""
            flag = f[6].strip() if len(f) > 6 else ""
            if code is None:
                extra["^".join(parts)] = val
                continue
            text = normalize_value(val if not unit or unit.lower() in val.lower() or not re.search(r"\d", val) else f"{val} {unit}")
            if code not in values:
                values[code] = text
            if flag and flag.upper() not in ("N", ""):
                abnormal.add(code)
    result.update(values)
    result["ABNORMAL"] = sorted(abnormal)
    if extra:
        result["EXTRA"] = extra
    return result


def parse_block(raw: str, protocol: str = "auto") -> dict:
    """Har qanday formatdagi natija blokini kanonik lug'atga aylantiradi."""
    fmt = protocol if protocol in ("text", "hl7", "astm") else detect_format(raw)
    # Foydalanuvchi 'text' desa ham xabar aniq HL7/ASTM bo'lsa — avtomatik
    auto = detect_format(raw)
    if fmt == "text" and auto != "text":
        fmt = auto
    if fmt == "hl7":
        r = parse_hl7_block(raw)
    elif fmt == "astm":
        r = parse_astm_block(raw)
    else:
        r = parse_text_block(raw)
    r["FORMAT"] = fmt
    return r


# ─────────────────────────────────────────────────────────────────────────────
#  TRANSPORT — bitta natija blokini o'qib beradi
# ─────────────────────────────────────────────────────────────────────────────
def _build_hl7_ack(message: str, encoding: str) -> bytes:
    msg_id = ""
    for seg in re.split(r"[\r\n]+", message):
        if seg.startswith("MSH"):
            f = seg.split("|")
            msg_id = f[9] if len(f) > 9 else ""
            break
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    ack = f"MSH|^~\\&|LIS||||{now}||ACK^R01|{msg_id or now}|P|2.3.1\rMSA|AA|{msg_id}"
    return MLLP_SB + ack.encode(encoding, errors="replace") + MLLP_EB


class _Framer:
    """Kelayotgan baytlardan to'liq bloklarni ajratadi va javob (ACK) baytlarini beradi.
    feed(bytes) -> (blocks: list[str], reply: bytes)"""

    def __init__(self, protocol: str, encoding: str, idle_timeout: float, hl7_auto_ack: bool = True):
        self.protocol = protocol
        self.encoding = encoding
        self.idle_timeout = idle_timeout
        # hl7_auto_ack=False: HL7 javobini (ACK/ORR) chaqiruvchi o'zi tuzadi
        # (gemotologiya listener'i worklist so'roviga ORR^O02 qaytaradi)
        self.hl7_auto_ack = hl7_auto_ack
        self.buf = b""
        self.last_rx = 0.0
        self.astm_frames = []   # ASTM: EOT gacha yig'iladigan freymlar

    def _dec(self, b: bytes) -> str:
        b = b.replace(b"\xab", b" ")  # Dirui SP1
        return b.decode(self.encoding, errors="ignore")

    def feed(self, data: bytes):
        blocks, reply = [], b""
        if data:
            self.buf += data
            self.last_rx = time.time()

        # 'auto' rejimida bir marta aniqlangan protokol keyingi bloklarda ham saqlanadi
        # (ASTM freymlari orasida ENQ/H yozuvi bo'lmaydi — matn STX/ETX deb adashmasin)
        if self.protocol == "auto":
            if MLLP_SB in self.buf or b"MSH|" in self.buf:
                self.protocol = "hl7"
            elif b"\x05" in self.buf or b"H|\\^&" in self.buf:
                self.protocol = "astm"

        # ── HL7 MLLP ──
        if self.protocol == "hl7" or (self.protocol == "auto" and MLLP_SB in self.buf):
            # Heartbeat (Mindray BC-20S har 3 s da \x02 yuboradi) — MLLP dan tashqarida tashlanadi
            if MLLP_SB not in self.buf and b"\x02" in self.buf:
                self.buf = self.buf.replace(b"\x02", b"")
            while True:
                s = self.buf.find(MLLP_SB)
                if s < 0:
                    break
                e = self.buf.find(MLLP_EB, s + 1)
                if e < 0:
                    break
                msg = self._dec(self.buf[s + 1:e])
                self.buf = self.buf[e + len(MLLP_EB):]
                if msg.strip():
                    blocks.append(msg)
                    if self.hl7_auto_ack:
                        reply += _build_hl7_ack(msg, self.encoding)
            # MLLP'siz kelgan HL7 (ba'zi analizatorlar shunchaki \r bilan yuboradi)
            if self.protocol == "hl7" and MLLP_SB not in self.buf and b"MSH|" in self.buf:
                if self.buf.rstrip().endswith(b"\r") or (
                        self.last_rx and time.time() - self.last_rx > self.idle_timeout):
                    msg = self._dec(self.buf)
                    self.buf = b""
                    blocks.append(msg)
            return blocks, reply

        # ── ASTM E1381 ──
        if self.protocol == "astm" or (self.protocol == "auto" and (b"\x05" in self.buf or b"H|\\^&" in self.buf)):
            while self.buf:
                if self.buf[0:1] == b"\x05":         # ENQ → ACK
                    self.buf = self.buf[1:]
                    reply += b"\x06"
                    continue
                if self.buf[0:1] == b"\x04":         # EOT → blok tugadi
                    self.buf = self.buf[1:]
                    if self.astm_frames:
                        blocks.append("\r".join(self.astm_frames))
                        self.astm_frames = []
                    continue
                s = self.buf.find(b"\x02")
                if s < 0:
                    # freymsiz ASTM (TCP orqali ba'zilari shunday yuboradi)
                    if b"L|1|" in self.buf and (self.buf.endswith(b"\r") or self.buf.endswith(b"\n")):
                        blocks.append(self._dec(self.buf))
                        self.buf = b""
                    break
                if s > 0:
                    self.buf = self.buf[s:]
                m = re.search(rb"[\x03\x17][0-9A-Fa-f]{2}\r?\n?", self.buf)
                if not m:
                    break
                frame = self.buf[1:m.start()]
                self.buf = self.buf[m.end():]
                # freym raqamini olib tashlaymiz (1..7)
                if frame[:1].isdigit():
                    frame = frame[1:]
                self.astm_frames.append(self._dec(frame).rstrip("\r\n"))
                reply += b"\x06"
            return blocks, reply

        # ── MATN: STX ... ETX ──
        while b"\x03" in self.buf:
            block, _, self.buf = self.buf.partition(b"\x03")
            if b"\x02" in block:
                block = block[block.rfind(b"\x02") + 1:]
            if block.strip():
                blocks.append(self._dec(block))
        # ETX kelmagan (ba'zi analizatorlar faqat CR/LF bilan tugatadi) — jimlik bo'yicha
        if not blocks and self.buf.strip() and self.last_rx and \
                time.time() - self.last_rx > self.idle_timeout:
            block = self.buf
            self.buf = b""
            if b"\x02" in block:
                block = block[block.rfind(b"\x02") + 1:]
            if len(block.strip()) > 20:
                blocks.append(self._dec(block))
        return blocks, reply


class BlockReader:
    """cfg (effective_config) bo'yicha ulanadi va read_block() bilan navbatdagi
    natija blokini (str) qaytaradi. Xatoda '' qaytaradi — chaqiruvchi kutib qayta uradi."""

    def __init__(self, cfg: dict, log=print):
        self.cfg = effective_config(cfg)
        self.log = log
        self.framer = _Framer(self.cfg.get("protocol", "auto"), self.cfg.get("encoding", "utf-8"),
                              float(self.cfg.get("idle_timeout", 3.0)))
        self.pending = []
        self._ser = None
        self._srv = None
        self._conn = None

    # ── umumiy ──
    def describe(self) -> str:
        c = self.cfg
        ct = c.get("connection_type")
        if ct == "serial":
            return f"{c.get('com_port')} {c.get('baudrate')} {c.get('bytesize')}{c.get('parity')}{c.get('stopbits')} [{c.get('protocol')}]"
        return f"{ct} {c.get('ip')}:{c.get('port')} [{c.get('protocol')}]"

    def read_block(self) -> str:
        if self.pending:
            return self.pending.pop(0)
        ct = self.cfg.get("connection_type", "serial")
        try:
            if ct == "serial":
                return self._read_serial()
            if ct == "tcp_server":
                return self._read_tcp_server()
            if ct == "tcp_client":
                return self._read_tcp_client()
            self.log(f"[XATO] Noma'lum ulanish turi: {ct}")
            return ""
        except Exception as e:
            self.log(f"[XATO] O'qishda xato ({self.describe()}): {e}")
            self.close()
            return ""

    def _drain(self, blocks):
        if not blocks:
            return ""
        first, rest = blocks[0], blocks[1:]
        self.pending.extend(rest)
        return first

    def close(self):
        for attr in ("_ser", "_conn", "_srv"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)

    # ── SERIAL ──
    def _open_serial(self):
        if serial is None:
            raise RuntimeError("pyserial o'rnatilmagan")
        c = self.cfg
        bs = {5: serial.FIVEBITS, 6: serial.SIXBITS, 7: serial.SEVENBITS, 8: serial.EIGHTBITS}
        pr = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
              "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}
        sb = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}
        self._ser = serial.Serial(
            port=c.get("com_port", "COM4"),
            baudrate=int(c.get("baudrate", 9600)),
            bytesize=bs.get(int(c.get("bytesize", 8)), serial.EIGHTBITS),
            parity=pr.get(str(c.get("parity", "N")).upper()[:1], serial.PARITY_NONE),
            stopbits=sb.get(int(c.get("stopbits", 1)), serial.STOPBITS_ONE),
            timeout=float(c.get("timeout", 1.0)),
        )

    def _read_serial(self) -> str:
        if self._ser is None or not self._ser.is_open:
            try:
                self._open_serial()
            except Exception as e:
                port = self.cfg.get("com_port")
                self.log(f"⚠️ COM port ({port}) ochib bo'lmadi: {e}")
                self.log("   Tekshiring: 1) analizator ulanganmi  2) port Device Manager'da bormi  "
                         "3) boshqa dastur portni band qilmaganmi  4) Sozlamalarda port to'g'rimi")
                return ""
        ser = self._ser
        while True:
            chunk = ser.read(ser.in_waiting or 1)
            blocks, reply = self.framer.feed(chunk)
            if reply:
                ser.write(reply)
            if blocks:
                return self._drain(blocks)

    # ── TCP SERVER (analizator bizga ulanadi) ──
    def _read_tcp_server(self) -> str:
        c = self.cfg
        if self._srv is None:
            self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._srv.bind((c.get("ip", "0.0.0.0"), int(c.get("port", 5200))))
            self._srv.listen(2)
            self.log(f"📡 Siydik LIS server tinglayapti: {c.get('ip')}:{c.get('port')}")
        while True:
            if self._conn is None:
                self._srv.settimeout(None)
                conn, addr = self._srv.accept()
                conn.settimeout(1.0)
                self._conn = conn
                self.framer.buf = b""
                self.log(f"🔌 Analizator ulandi: {addr[0]}:{addr[1]}")
            blk = self._pump_socket(self._conn)
            if blk is None:      # ulanish uzildi
                self._conn = None
                continue
            if blk:
                return blk

    # ── TCP CLIENT (biz analizatorga ulanamiz) ──
    def _read_tcp_client(self) -> str:
        c = self.cfg
        while True:
            if self._conn is None:
                try:
                    s = socket.create_connection((c.get("ip"), int(c.get("port", 5200))), timeout=5)
                    s.settimeout(1.0)
                    self._conn = s
                    self.framer.buf = b""
                    self.log(f"🔌 Analizatorga ulanildi: {c.get('ip')}:{c.get('port')}")
                except Exception as e:
                    self.log(f"⚠️ {c.get('ip')}:{c.get('port')} ga ulanib bo'lmadi: {e} — "
                             f"{c.get('reconnect_interval', 5)} s dan keyin qayta")
                    time.sleep(float(c.get("reconnect_interval", 5)))
                    continue
            blk = self._pump_socket(self._conn)
            if blk is None:
                self._conn = None
                continue
            if blk:
                return blk

    def _pump_socket(self, conn):
        """Bitta blok kelguncha o'qiydi. None = ulanish yopildi (recv b'' yoki xato)."""
        while True:
            try:
                data = conn.recv(4096)
                if data == b"":          # peer ulanishni yopdi
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return None
            except socket.timeout:
                data = b""               # jimlik — freymga idle-timeout uchun xabar
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                return None
            blocks, reply = self.framer.feed(data)
            if reply:
                try:
                    conn.sendall(reply)
                except Exception:
                    pass
            if blocks:
                return self._drain(blocks)


# ─────────────────────────────────────────────────────────────────────────────
#  SINOV
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    urit = "\x02  \r\rID:260917118052\r\rNO.000009 2000-01-01\r\r            04:30:20\r\r\r\r LEU -       0 CELL/uL\r\r KET -        0 mmol/L\r\r NIT -   \r\r URO            Normal\r\r BIL -        0 umol/L\r\r GLU -        0 mmol/L\r\r PRO -           0 g/L\r\r SG         1.020     \r\r pH         7.0       \r\r BLD -       0 CELL/uL\r\r*Vc  +-     0.6 mmol/L\r\r MA          <=10 mg/L\r\r Ca         5.0 mmol/L\r\r CR         8.8 mmol/L\r\r ACR       <3.4mg/mmol\r\r"
    dirui = "\x02\r\n Date:2026-09-17 10:31\r\n No. 0012\r\n ID：260917118052\r\n UBG Normal\r\n BIL neg\r\n KET neg\r\n CRE 8.8 mmol/L\r\n BLD 1+ 25 Ery/uL\r\n PRO neg\r\n ALB 10 mg/L\r\n NIT neg\r\n LEU 2+ 125 Leu/uL\r\n GLU neg\r\n SG  1.015\r\n PH  6.0\r\n VC  neg\r\n Ca  2.5 mmol/L\r\n A:C <3.4 mg/mmol\r\n RT  \r\n\x03"
    hl7 = "MSH|^~\\&|UA-600|Mindray|LIS||20260917103000||ORU^R01|12|P|2.3.1\rPID|1||260917118052||Test^Bemor\rOBR|1||260917118052|URINE\rOBX|1|ST|URO^Urobilinogen||Normal|umol/L|||N\rOBX|2|ST|LEU^Leukocytes||2+ 125|Cell/uL||A\rOBX|3|NM|SG^Specific Gravity||1.015||||N\rOBX|4|NM|PH^pH||6.0||||N\rOBX|5|ST|BLD^Blood||neg||||N\r"
    astm = "H|\\^&|||Combilyzer^1.0|||||||P|LIS2-A2|20260917103000\rP|1|||260917118052|Test^Bemor\rO|1|260917118052||^^^URINE|R\rR|1|^^^LEU|neg|Leu/uL||N\rR|2|^^^GLU|2+|mmol/L||A\rR|3|^^^SG|1.020|||N\rL|1|N\r"
    for name, raw in [("URIT", urit), ("DIRUI", dirui), ("HL7", hl7), ("ASTM", astm)]:
        print("=" * 20, name, detect_format(raw))
        print(parse_block(raw))
