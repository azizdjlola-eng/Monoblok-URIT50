# -*- coding: utf-8 -*-
"""
Gemotologiya analizatorlari uchun UNIVERSAL ulanish va parse moduli.

O'zbekistonda uchraydigan brendlar: Mindray (BC-20s/30s/5150/6800), Genrui (KT-6300/6610/8000),
Edan (H30 Pro/H60), Dymind (DH-36/DF-50), Zybio (Z3/Z50), URIT (3000Plus/5160), Dirui (BCC),
Biobase (BK-6100/6190), Erba (Elite 3/5, H360), Cypress Cyan Hemato, Human (HumaCount),
Sysmex (XP-300/XN), Diatron (Abacus), Rayto, Getein ...

Deyarli hammasi ikki oilaga bo'linadi:
  * HL7 v2.3.1 ORU^R01 (MLLP) — TCP (analizator mijoz YOKI server) yoki RS-232
    (Mindray, Genrui, Edan, Dymind, Zybio, URIT, Dirui, Biobase, Erba, Cyan, Rayto ...)
    Ko'pchiligi Mindray andozasidan nusxa: OBX-3 = LOINC^nom^LN yoki 100xx^nom^99MRC.
  * ASTM E1394 (LIS2-A2) yozuvlar + E1381 (ENQ/ACK/EOT) freymlar — RS-232 yoki TCP
    (Sysmex, Diatron Abacus, Human HumaCount, ba'zi Erba/Rayto)

Ikkalasi ham shu modul orqali BITTA kanonik bemor lug'atiga keltiriladi:
    {"time", "sample_id", "name", "age", "gender", "abnormal",
     "tests": {"WBC": {"name","value","unit","ref","flag","abnormal"}, ...}}
Kalitlar: CANONICAL (3-diff: LYM/MID/GRAN; 5-diff: NEU/LYM/MON/EOS/BAS + indekslar).
bc20s_listener.py (jonli qabul) va hematology_window.py (TXT ko'rish) shu modulni ishlatadi.

O'rganilgan manbalar (2026-09-18):
  * Mindray BC-20S — jonli HL7 (BC-20s/*.txt): OBX-3 LOINC (6690-2 WBC ...) + 99MRC (10027 MID# ...),
    30525-0 Age (yr/mo), 01002 Ref Group, 15000-15200 gistogrammalar, OBR-3 = sample ID.
  * Genrui KT-6600/6610 Operation Manual (denis.uz) — Setup → System Setup → Communication:
    TCP/IP, "Comm. Protocol" ro'yxati (HL7), ACK sinxron (10 s), "Auto Fetch Info from LIS"
    (worklist = ORM^O01 → ORR^O02), gistogramma/skattergramma "Bitmap/Data/Not transmitted".
  * BLIS Interface Client (GitHub) — URIT-3000Plus: HL7 RS-232 orqali; Mindray BC-5000/BC-3600:
    TCP, analizator SERVER, port 5100 (BC-20S kabi); Mindray BC-2800: xususiy fiksatsiyalangan
    kenglikdagi format (QO'LLAB-QUVVATLANMAYDI — kodsiz parametrlar tartibi tasdiqlanmagan).
  * Sysmex XP-300 — ASTM E1394 RS-232/LAN; Diatron Abacus — HL7 / ASTM / Diatron serial.
"""

import re
import socket
import threading
import time
from datetime import datetime, date

try:
    import serial  # pyserial
except Exception:  # pragma: no cover
    serial = None

# Freym/transport mantiqi siydik moduli bilan umumiy (MLLP / ASTM / STX-ETX)
from siydik_protokol import _Framer, MLLP_SB, MLLP_EB, detect_format as _detect_format

# ─────────────────────────────────────────────────────────────────────────────
#  KANONIK PARAMETRLAR
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL = [
    "WBC",
    "NEU#", "NEU%", "LYM#", "LYM%", "MON#", "MON%", "EOS#", "EOS%", "BAS#", "BAS%",   # 5-diff
    "MID#", "MID%", "GRAN#", "GRAN%",                                                # 3-diff
    "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC", "RDW-CV", "RDW-SD",
    "PLT", "MPV", "PDW", "PDW-SD", "PCT", "P-LCR", "P-LCC",
    "NLR", "PLR",
]

# DB/blanka nomlari (result_items.tahlil_nomi, CBC JSON kalitlari, CBC_HEMA_ROWS "kod" ustuni)
DB_NAME_MAP = {
    "WBC": "WBC",
    "LYM#": "Lymph#", "LYM%": "Lymph%", "MID#": "Mid#", "MID%": "Mid%",
    "GRAN#": "Gran#", "GRAN%": "Gran%",
    "NEU#": "Neu#", "NEU%": "Neu%", "MON#": "Mon#", "MON%": "Mon%",
    "EOS#": "Eos#", "EOS%": "Eos%", "BAS#": "Bas#", "BAS%": "Bas%",
    "RBC": "RBC", "HGB": "HGB", "HCT": "HCT", "MCV": "MCV", "MCH": "MCH", "MCHC": "MCHC",
    "RDW-CV": "RDW-CV", "RDW-SD": "RDW-SD",
    "PLT": "PLT", "MPV": "MPV", "PDW": "PDW", "PDW-SD": "PDW-SD", "PCT": "PCT",
    "P-LCR": "P-LCR", "P-LCC": "P-LCC",
    "NLR": "NLR", "PLR": "PLR",
}

# LOINC / Mindray 99MRC / boshqa raqamli kodlar → kanonik
CODE_MAP = {
    "6690-2": "WBC", "789-8": "RBC", "718-7": "HGB", "4544-3": "HCT", "787-2": "MCV",
    "785-6": "MCH", "786-4": "MCHC", "788-0": "RDW-CV", "21000-5": "RDW-SD", "777-3": "PLT",
    "32623-1": "MPV", "32207-3": "PDW", "731-0": "LYM#", "736-9": "LYM%",
    "751-8": "NEU#", "770-8": "NEU%", "742-7": "MON#", "5905-5": "MON%",
    "711-2": "EOS#", "713-8": "EOS%", "704-7": "BAS#", "706-2": "BAS%",
    "48386-7": "P-LCR", "26474-7": "LYM#", "26478-8": "MON#", "26449-9": "EOS#", "26444-0": "BAS#",
    # Mindray 99MRC (BC-20s/30s/5150 ...) — Genrui/Dymind/Zybio ham shu raqamlarni ishlatadi
    "10002": "PCT", "10027": "MID#", "10029": "MID%", "10028": "GRAN#", "10030": "GRAN%",
    "10057": "NLR", "10058": "PLR", "10004": "P-LCC", "10003": "P-LCR", "10001": "PDW-SD",
}

# Nomlar → kanonik (UPPERCASE, bo'sh joysiz). Suffiks (# / % / A / P) alohida qayta ishlanadi.
_BASE_ALIASES = {
    "WBC": "WBC", "LEU": "WBC", "LEUKOCYTES": "WBC",
    "RBC": "RBC", "ERY": "RBC", "ERYTHROCYTES": "RBC",
    "HGB": "HGB", "HB": "HGB", "HEMOGLOBIN": "HGB", "HAEMOGLOBIN": "HGB",
    "HCT": "HCT", "HTC": "HCT", "HEMATOCRIT": "HCT", "PCV": "HCT",
    "MCV": "MCV", "MCH": "MCH", "MCHC": "MCHC",
    "RDW": "RDW-CV", "RDW-CV": "RDW-CV", "RDWCV": "RDW-CV", "RDWC": "RDW-CV", "RDW-C": "RDW-CV",
    "RDW-SD": "RDW-SD", "RDWSD": "RDW-SD", "RDWS": "RDW-SD", "RDW-S": "RDW-SD",
    "PLT": "PLT", "PLATELETS": "PLT", "TRO": "PLT",
    "MPV": "MPV", "PDW": "PDW", "PDW-CV": "PDW", "PDWCV": "PDW", "PDWC": "PDW",
    "PDW-SD": "PDW-SD", "PDWSD": "PDW-SD", "PDWS": "PDW-SD",
    "PCT": "PCT", "THROMBOCRIT": "PCT",
    "P-LCR": "P-LCR", "PLCR": "P-LCR", "LPCR": "P-LCR", "P-LCC": "P-LCC", "PLCC": "P-LCC",
    "NLR": "NLR", "PLR": "PLR",
    # differensial (suffikssiz asos)
    "LYM": "LYM", "LYMPH": "LYM", "LY": "LYM", "LYMPHOCYTES": "LYM", "LYM#": "LYM#",
    "MID": "MID", "MXD": "MID", "MIX": "MID",
    "GRAN": "GRAN", "GRA": "GRAN", "GR": "GRAN", "GRANULOCYTES": "GRAN",
    "NEU": "NEU", "NEUT": "NEU", "NE": "NEU", "NEUTROPHILS": "NEU",
    "MON": "MON", "MONO": "MON", "MO": "MON", "MONOCYTES": "MON",
    "EOS": "EOS", "EO": "EOS", "EOSINOPHILS": "EOS",
    "BAS": "BAS", "BASO": "BAS", "BA": "BAS", "BASOPHILS": "BAS",
}
_DIFF_BASES = {"LYM", "MID", "GRAN", "NEU", "MON", "EOS", "BAS"}


def normalize_param(code: str = "", name: str = ""):
    """OBX-3 / ASTM R-3 dagi kod va nomdan kanonik parametrni topadi. Topilmasa None."""
    for cand in (code, name):
        if not cand:
            continue
        c = str(cand).strip()
        if c in CODE_MAP:
            return CODE_MAP[c]
        k = c.upper().replace(" ", "")
        if k in ("PCT", "HCT", "MCHC", "MCH", "MCV", "MPV", "PDW", "PLT", "RBC", "WBC", "HGB"):
            return _BASE_ALIASES[k]
        # suffiks: % / P / PCT(oxiri) → foiz; # / A / ABS → absolyut
        base, suffix = k, ""
        m = re.match(r"^(.+?)[\-_]?(%|#|ABS|A|P|PCT|PERCENT)$", k)
        if m and m.group(1) in _BASE_ALIASES and _BASE_ALIASES[m.group(1)] in _DIFF_BASES:
            base = m.group(1)
            suffix = "%" if m.group(2) in ("%", "P", "PCT", "PERCENT") else "#"
        canon = _BASE_ALIASES.get(base)
        if canon is None:
            canon = _BASE_ALIASES.get(base.replace("-", "").replace("_", ""))
        if canon is None:
            continue
        if canon in _DIFF_BASES:
            return canon + (suffix or "#")
        return canon
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  PROFILLAR
# ─────────────────────────────────────────────────────────────────────────────
PROFILES = {
    "mindray_bc20s": {
        "name": "Mindray BC-20s / BC-30s / BC-5000 / BC-5150 (HL7, analizator = server)",
        "connection_type": "tcp_client", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Analizator Setup → Communication: LIS IP = shu kompyuter, port 5100, 'Server' rejimi. Dastur analizatorga ulanadi.",
    },
    "mindray_bc_client": {
        "name": "Mindray BC-3600 / BC-6800 / BC-2300 (HL7, analizator = mijoz)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Analizator Communication sozlamasida 'Client' rejimi, IP = shu kompyuter, port = shu port.",
    },
    "mindray_bc3000plus": {
        "name": "Mindray BC-3000 Plus / BC-3200 (HL7, RS-232)",
        "connection_type": "serial", "protocol": "hl7",
        "baudrate": 115200, "bytesize": 8, "parity": "N", "stopbits": 1, "worklist": False,
        "hint": "Setup → Transmission: Protocol = HL7, Baud 115200 (yoki 9600). BC-2800 xususiy formati qo'llanmaydi.",
    },
    "genrui_kt": {
        "name": "Genrui KT-6300 / KT-6610 / KT-8000 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Setup → System Setup → Communication: Comm. Protocol = HL7, LIS IP = shu kompyuter, port = shu port; 'Auto Communicate' + 'Auto Fetch Info from LIS' yoqing; gistogramma = 'Not transmitted'.",
    },
    "edan_h": {
        "name": "Edan H30 Pro / H60 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Settings → Communication → LIS: HL7, Server IP = shu kompyuter, port = shu port.",
    },
    "dymind": {
        "name": "Dymind DH-36 / DF-50 / DF-52 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Setup → Communication: LIS IP/port = shu kompyuter. Mindray andozasi (99MRC kodlar).",
    },
    "zybio": {
        "name": "Zybio Z3 / Z50 / Z5 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Setup → Communication: HL7, LIS IP/port = shu kompyuter.",
    },
    "urit_hema": {
        "name": "URIT-3000 Plus / 5160 / 5380 (HL7, TCP yoki RS-232)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": False,
        "hint": "URIT-3000Plus faqat RS-232 (ulanish turi = serial, HL7). URIT-5xxx TCP: LIS IP = shu kompyuter.",
    },
    "dirui_bcc": {
        "name": "Dirui BCC-3000 / BCC-3600 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "LIS sozlamasi: HL7, Server IP = shu kompyuter, port = shu port.",
    },
    "biobase": {
        "name": "Biobase BK-6100 / BK-6190 / BK-6300 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Settings → Communication: HL7, LIS IP/port = shu kompyuter.",
    },
    "erba": {
        "name": "Erba Elite 3 / Elite 5 / H360 (HL7 yoki ASTM)",
        "connection_type": "tcp_server", "protocol": "auto", "port": 5100, "worklist": False,
        "hint": "Analizator LIS sozlamasida HL7 yoki ASTM — protokol 'auto' ikkalasini ham taniydi.",
    },
    "cyan_hemato": {
        "name": "Cypress Cyan Hemato / Hemato 380 (HL7, TCP)",
        "connection_type": "tcp_server", "protocol": "auto", "port": 5100, "worklist": False,
        "hint": "Settings → LIS: HL7 (yoki ASTM), Server IP = shu kompyuter, port = shu port.",
    },
    "human_humacount": {
        "name": "Human HumaCount 30TS / 5L / 80TS (ASTM)",
        "connection_type": "serial", "protocol": "astm",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "worklist": False,
        "hint": "Settings → Communication: ASTM (LIS2-A2), RS-232 9600 8N1 yoki TCP (ulanish turini o'zgartiring).",
    },
    "sysmex_xp": {
        "name": "Sysmex XP-300 / KX-21N / XN-350 (ASTM)",
        "connection_type": "serial", "protocol": "astm",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "worklist": False,
        "hint": "Settings → Host Computer: Format = ASTM (E1394), Serial 9600 8N1 yoki LAN (tcp_server).",
    },
    "diatron_abacus": {
        "name": "Diatron Abacus 3 / Abacus Junior / Aquila (ASTM yoki HL7)",
        "connection_type": "serial", "protocol": "auto",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "worklist": False,
        "hint": "Settings → Communication: ASTM yoki HL7 (Diatron serial formati qo'llanmaydi).",
    },
    "hl7_generic": {
        "name": "Boshqa (HL7 ORU^R01, MLLP)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "worklist": True,
        "hint": "Har qanday HL7 yuboradigan gemotologiya analizatori. OBX-3 kodlari/nomlari avtomatik moslanadi.",
    },
    "astm_generic": {
        "name": "Boshqa (ASTM E1394 / LIS2-A2)",
        "connection_type": "serial", "protocol": "astm",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "worklist": False,
        "hint": "ENQ/ACK/EOT qo'l berish avtomatik. TCP orqali ham ishlaydi.",
    },
}
DEFAULT_MODEL = "mindray_bc20s"


def profile_for(cfg: dict) -> dict:
    return PROFILES.get((cfg or {}).get("model") or DEFAULT_MODEL, PROFILES[DEFAULT_MODEL])


def effective_config(cfg: dict) -> dict:
    prof = profile_for(cfg)
    out = {k: v for k, v in prof.items() if k not in ("name", "hint")}
    for k, v in (cfg or {}).items():
        if v not in (None, ""):
            out[k] = v
    out.setdefault("connection_type", "tcp_client")
    out.setdefault("protocol", "auto")
    out.setdefault("encoding", "utf-8")
    out.setdefault("ip", "192.168.0.2")
    out.setdefault("port", 5100)
    out.setdefault("reconnect_interval", 5)
    out.setdefault("timeout", 1.0)
    out.setdefault("idle_timeout", 3.0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  YORDAMCHI
# ─────────────────────────────────────────────────────────────────────────────
def _decode_cyrillic(raw: str) -> str:
    """Analizator UTF-8 baytlarni latin-1 deb yuborgan bo'lsa (Mindray) — tiklaymiz."""
    if not raw:
        return ""
    try:
        return raw.encode("latin-1").decode("utf-8")
    except Exception:
        return raw


def _hl7_time(s: str, fallback: str = "") -> str:
    s = (s or "").strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", s)
    if not m:
        return fallback
    y, mo, d, hh, mm = m.groups()
    return f"{d}.{mo}.{y} {hh or '00'}:{mm or '00'}"


def _age_from_birth(birth: str) -> str:
    try:
        bs = (birth or "").strip()
        if len(bs) >= 8 and bs[:8].isdigit():
            by, bm, bd = int(bs[:4]), int(bs[4:6]), int(bs[6:8])
            today = date.today()
            return str(today.year - by - ((today.month, today.day) < (bm, bd)))
    except Exception:
        pass
    return ""


def _age_to_years(value_str, unit_str) -> str:
    """'7' + 'mo' → '0'; '42' + 'yr' → '42'. Butun yil (multi-ref norma uchun)."""
    try:
        v = float(str(value_str).strip())
    except Exception:
        return str(value_str or "").strip()
    u = (unit_str or "").strip().lower()
    if u.startswith(("mo", "mon", "ой", "oy")):
        return str(int(v // 12))
    if u.startswith(("d", "дн", "kun")):
        return str(int(v // 365))
    if u.startswith(("w", "нед", "haf")):
        return str(int(v // 52))
    if u.startswith(("h", "час", "soat")):
        return "0"
    return str(int(v))


def _gender(raw: str) -> str:
    """M/F/Муж/Жен/Erkak/Ayol/'Взрос.муж' (Mindray Ref Group) → 'Erkak' | 'Ayol' | ''"""
    g = _decode_cyrillic((raw or "").strip()).upper()
    if not g:
        return ""
    if g in ("M", "MALE", "E", "1") or "МУЖ" in g or "ERKAK" in g or "ERK" in g or "MUJ" in g:
        return "Erkak"
    if g in ("F", "FEMALE", "A", "W", "2") or "ЖЕН" in g or "AYOL" in g or "FEMALE" in g or "JEN" in g:
        return "Ayol"
    if g == "М":
        return "Erkak"
    if g == "Ж":
        return "Ayol"
    return ""


def _flag_abnormal(flag: str) -> bool:
    """Faqat H/L (HH, LL, H~N, L~N ...) — 'A' (Mindray: ma'lumot uchun) patologiya emas."""
    fu = (flag or "").strip().upper()
    return bool(fu) and fu != "N" and ("H" in fu or "L" in fu)


def _new_patient():
    return {
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"), "sample_id": "", "name": "",
        "age": "", "gender": "", "tests": {}, "abnormal": False,
    }


def _finalize(patient: dict) -> dict:
    """3-diff analizator (Sysmex XP: NEUT/LYMPH/MXD) NEU deb yuborsa → GRAN (blanka 3-diff qatorlari).
    5-diff belgisi = MON/EOS/BAS dan birortasi bor."""
    t = patient["tests"]
    has_mid = "MID#" in t or "MID%" in t
    has_5 = any(k in t for k in ("MON#", "MON%", "EOS#", "EOS%", "BAS#", "BAS%"))
    if has_mid and not has_5:
        for a, b in (("NEU#", "GRAN#"), ("NEU%", "GRAN%")):
            if a in t and b not in t:
                t[b] = t.pop(a)
    return patient


def _add_test(patient: dict, key: str, name: str, value: str, unit: str, ref: str, flag: str):
    value = (value or "").strip()
    if not value or key in patient["tests"]:
        return
    ab = _flag_abnormal(flag)
    if ab:
        patient["abnormal"] = True
    patient["tests"][key] = {"name": name or key, "value": value, "unit": (unit or "").strip(),
                             "ref": (ref or "").strip(), "flag": (flag or "").strip(), "abnormal": ab}


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER: HL7 ORU^R01
# ─────────────────────────────────────────────────────────────────────────────
def parse_hl7_oru(message: str) -> dict:
    """ORU^R01 → bemor lug'ati. Mindray/Genrui/Dymind/Edan/URIT... uchun umumiy."""
    p = _new_patient()
    extra = {}
    for seg in re.split(r"[\r\n]+", message or ""):
        seg = seg.strip().lstrip("\x0b")
        if len(seg) < 3:
            continue
        tag = seg[:3]
        f = seg.split("|")
        if tag == "MSH":
            if len(f) > 6 and f[6]:
                p["time"] = _hl7_time(f[6], p["time"])
        elif tag == "PID":
            if len(f) > 5 and f[5]:
                parts = f[5].split("^")
                given = _decode_cyrillic(parts[0]) if parts else ""
                family = _decode_cyrillic(parts[1]) if len(parts) > 1 else ""
                p["name"] = (f"{family} {given}".strip() if family and given else (given or family)).strip()
            if len(f) > 7 and f[7]:
                p["age"] = _age_from_birth(f[7]) or p["age"]
            # PID-8 = jins; Mindray BC-20S uni PID-9 ga yozadi ("...||19930101000000||M")
            for gi in (8, 9):
                if len(f) > gi and f[gi].strip():
                    g = _gender(f[gi])
                    if g:
                        p["gender"] = g
                        break
        elif tag == "OBR":
            if len(f) > 3 and f[3]:
                p["sample_id"] = f[3].split("^")[0].strip() or p["sample_id"]
            elif len(f) > 2 and f[2] and not p["sample_id"]:
                p["sample_id"] = f[2].split("^")[0].strip()
            if len(f) > 7 and f[7]:
                p["time"] = _hl7_time(f[7], p["time"])
        elif tag == "SPM":
            if len(f) > 2 and f[2] and not p["sample_id"]:
                p["sample_id"] = f[2].split("^")[0].split("&")[0].strip()
        elif tag == "OBX":
            if len(f) < 6:
                continue
            vtype = f[2].strip().upper() if len(f) > 2 else ""
            parts = f[3].split("^")
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else code
            value = f[5].strip()
            unit = f[6].split("^")[0].strip() if len(f) > 6 else ""
            ref = f[7].strip() if len(f) > 7 else ""
            flag = f[8].strip() if len(f) > 8 else ""
            # Yosh / jins / gistogramma
            if code == "30525-0":
                if not p["age"]:
                    p["age"] = _age_to_years(value, unit)
                continue
            if code == "01002":
                if not p["gender"]:
                    p["gender"] = _gender(value)
                continue
            if vtype == "ED" or (code.isdigit() and 15000 <= int(code) <= 15200):
                continue
            key = normalize_param(code, name)
            if key is None:
                if vtype in ("NM", "ST", "") and value:
                    extra[code or name] = value
                continue
            _add_test(p, key, name, value, unit, ref, flag)
    if extra:
        p["_extra"] = extra
    p["_raw_hl7"] = message
    p["_format"] = "hl7"
    return _finalize(p)


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER: ASTM E1394
# ─────────────────────────────────────────────────────────────────────────────
_ASTM_FRAME_RE = re.compile(r"\x02\d?|[\x03\x17][0-9A-Fa-f]{2}\r?\n?|\x04|\x05|\x06|\x15")


def parse_astm(message: str) -> dict:
    p = _new_patient()
    extra = {}
    clean = _ASTM_FRAME_RE.sub("", message or "")
    for rec in re.split(r"[\r\n]+", clean):
        rec = rec.strip()
        if not rec:
            continue
        f = rec.split("|")
        rt = f[0].lstrip("0123456789").strip()
        if rt == "H":
            if len(f) > 13 and f[13]:
                p["time"] = _hl7_time(f[13], p["time"])
        elif rt == "P":
            if len(f) > 5 and f[5]:
                parts = f[5].split("^")
                p["name"] = " ".join(x for x in parts[:2] if x).strip()
            if len(f) > 7 and f[7]:
                p["age"] = _age_from_birth(f[7]) or p["age"]
            if len(f) > 8 and f[8]:
                p["gender"] = _gender(f[8]) or p["gender"]
            if len(f) > 3 and f[3] and not p["sample_id"]:
                p["sample_id"] = f[3].strip()
        elif rt == "O":
            sid = ""
            for idx in (2, 3):
                if len(f) > idx and f[idx].strip():
                    sid = f[idx].split("^")[0].strip()
                    if sid:
                        break
            if sid:
                p["sample_id"] = sid
            if len(f) > 7 and f[7]:
                p["time"] = _hl7_time(f[7], p["time"])
        elif rt == "R":
            if len(f) < 4:
                continue
            parts = [x for x in f[2].split("^") if x]
            key = None
            for cand in reversed(parts):
                key = normalize_param(cand, "")
                if key:
                    break
            value = f[3].replace("^", " ").strip()
            unit = f[4].strip() if len(f) > 4 else ""
            ref = f[5].strip() if len(f) > 5 else ""
            flag = f[6].strip() if len(f) > 6 else ""
            if key is None:
                if value:
                    extra["^".join(parts)] = value
                continue
            _add_test(p, key, parts[-1] if parts else key, value, unit, ref, flag)
    if extra:
        p["_extra"] = extra
    p["_raw_hl7"] = message
    p["_format"] = "astm"
    return _finalize(p)


def detect_format(raw: str) -> str:
    return _detect_format(raw)


def parse_message(raw: str) -> dict:
    return parse_astm(raw) if detect_format(raw) == "astm" else parse_hl7_oru(raw)


def split_messages(content: str) -> list:
    """TXT fayl ichidagi bir nechta xabarni ajratadi (HL7: MSH| bloklar; ASTM: H| bloklar)."""
    if not content:
        return []
    if "MSH|" in content:
        return [b for b in re.split(r"(?=MSH\|)", content) if b.strip().startswith("MSH|")]
    clean = _ASTM_FRAME_RE.sub("", content)
    blocks = re.split(r"(?=(?:^|[\r\n])\d?H\|)", clean)
    return [b.strip("\r\n") for b in blocks if re.match(r"^[\r\n]*\d?H\|", b)]


def message_kind(raw: str) -> str:
    """'oru' | 'orm' | 'astm_result' | 'astm_query' | 'other'"""
    s = (raw or "").lstrip("\x0b\x02\x05\r\n ")
    if s.startswith("MSH|"):
        first = s.split("\r")[0]
        if "ORM" in first:
            return "orm"
        if "ORU" in first:
            return "oru"
        return "other"
    if detect_format(s) == "astm":
        clean = _ASTM_FRAME_RE.sub("", s)
        if re.search(r"(^|[\r\n])\d?Q\|", clean):
            return "astm_query"
        if re.search(r"(^|[\r\n])\d?R\|", clean):
            return "astm_result"
    return "other"


def astm_query_sample_id(raw: str) -> str:
    """Q|1|^sampleID^... dan namuna ID."""
    clean = _ASTM_FRAME_RE.sub("", raw or "")
    for rec in re.split(r"[\r\n]+", clean):
        f = rec.strip().split("|")
        if f and f[0].lstrip("0123456789") == "Q" and len(f) > 2:
            parts = [x for x in f[2].split("^") if x]
            if parts:
                return parts[0].strip()
    return ""


def build_astm_worklist(sample_id: str, patient: dict | None) -> str:
    """ASTM so'roviga javob: H P O L (bemor topilsa) yoki H L."""
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    lines = [f"H|\\^&|||AzizMedLine^LIS|||||||P|LIS2-A2|{now}"]
    if patient:
        name = (patient.get("patient_name") or "").replace("|", " ")
        dob = (patient.get("dob") or "")
        gender = "M" if (patient.get("gender") or "").lower().startswith(("e", "m", "м")) else \
                 "F" if (patient.get("gender") or "").lower().startswith(("a", "f", "ж", "w")) else "U"
        lines.append(f"P|1|{patient.get('patient_id', '')}||{sample_id}|{name}||{dob}|{gender}")
        lines.append(f"O|1|{sample_id}||^^^CBC|R||{now}|||||||||||||||||O")
    lines.append("L|1|N")
    return "\r".join(lines) + "\r"


def astm_frames(text: str) -> bytes:
    """Matnni ASTM E1381 freymlariga o'raydi (≤ 240 belgi, checksum)."""
    out = b""
    n = 1
    recs = [r for r in text.split("\r") if r]
    for i, r in enumerate(recs):
        body = (str(n) + r + "\r").encode("utf-8", errors="replace")
        term = b"\x03" if i == len(recs) - 1 else b"\x17"
        chk = (sum(body) + term[0]) % 256
        out += b"\x02" + body + term + f"{chk:02X}".encode() + b"\r\n"
        n = n % 7 + 1
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  TRANSPORT — uzluksiz qabul (thread ichida), reply yuborish imkoni bilan
# ─────────────────────────────────────────────────────────────────────────────
class Transport:
    """cfg bo'yicha ulanadi va har to'liq xabar uchun handler(msg_str, send) ni chaqiradi.
    send(bytes) — javob yuborish (ACK/ORR). Uzilsa qayta ulanadi (tcp_client/serial) yoki
    yangi ulanishni kutadi (tcp_server). run() to'xtash uchun is_running() False qaytarsin."""

    def __init__(self, cfg: dict, log=print):
        self.cfg = effective_config(cfg)
        self.log = log
        self.connected = False
        self.last_rx = None
        self._sock = None
        self._srv = None
        self._ser = None
        self._lock = threading.Lock()

    def describe(self) -> str:
        c = self.cfg
        if c["connection_type"] == "serial":
            return f"{c.get('com_port', 'COM1')} {c.get('baudrate', 9600)} [{c['protocol']}]"
        return f"{c['connection_type']} {c['ip']}:{c['port']} [{c['protocol']}]"

    def _framer(self):
        return _Framer(self.cfg["protocol"], self.cfg.get("encoding", "utf-8"),
                       float(self.cfg.get("idle_timeout", 3.0)), hl7_auto_ack=False)

    # ── yuborish ──
    def send(self, data: bytes):
        with self._lock:
            if self._sock is not None:
                self._sock.sendall(data)
            elif self._ser is not None:
                self._ser.write(data)
            else:
                raise RuntimeError("ulanish yo'q")

    def close(self):
        with self._lock:
            for attr in ("_sock", "_ser", "_srv"):
                obj = getattr(self, attr)
                if obj is not None:
                    try:
                        obj.close()
                    except Exception:
                        pass
                    setattr(self, attr, None)
            self.connected = False

    # ── asosiy sikl ──
    def run(self, handler, is_running):
        ct = self.cfg["connection_type"]
        rc = float(self.cfg.get("reconnect_interval", 5))
        while is_running():
            try:
                if ct == "tcp_client":
                    self._run_tcp_client(handler, is_running)
                elif ct == "tcp_server":
                    self._run_tcp_server(handler, is_running)
                elif ct == "serial":
                    self._run_serial(handler, is_running)
                else:
                    self.log(f"[XATO] Noma'lum ulanish turi: {ct}")
                    return
            except Exception as e:
                if is_running():          # to'xtatishda socket yopilishi — xato emas
                    self.log(f"[XATO] Transport: {e}")
            self.close()
            if is_running():
                self.log(f"Ulanish uzildi — {int(rc)} s dan keyin qayta...")
                self._sleep(rc, is_running)

    @staticmethod
    def _sleep(sec, is_running):
        end = time.time() + sec
        while time.time() < end and is_running():
            time.sleep(0.1)

    def _pump(self, recv, handler, is_running):
        """recv() -> bytes | None(yopildi) | b''(timeout). Xabarlarni handler ga beradi."""
        fr = self._framer()
        while is_running():
            data = recv()
            if data is None:
                return
            if data:
                self.last_rx = datetime.now()
            blocks, reply = fr.feed(data)
            if reply:
                try:
                    self.send(reply)
                except Exception as e:
                    self.log(f"[XATO] ACK yuborishda: {e}")
            for msg in blocks:
                try:
                    handler(msg, self.send)
                except Exception as e:
                    self.log(f"[XATO] handler: {e}")

    def _sock_recv(self, sock):
        def recv():
            try:
                d = sock.recv(8192)
                return None if d == b"" else d
            except socket.timeout:
                return b""
            except Exception:
                return None
        return recv

    def _run_tcp_client(self, handler, is_running):
        ip, port = self.cfg["ip"], int(self.cfg["port"])
        self.log(f"Analizatorga ulanmoqda: {ip}:{port} ...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.settimeout(10)
        s.connect((ip, port))
        s.settimeout(1.0)
        with self._lock:
            self._sock = s
            self.connected = True
        self.log(f"Analizatorga ulandi: {ip}:{port}")
        self._pump(self._sock_recv(s), handler, is_running)
        self.log("Analizator ulanishni yopdi")

    def _run_tcp_server(self, handler, is_running):
        ip, port = self.cfg["ip"], int(self.cfg["port"])
        if self._srv is None:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((ip, port))
            srv.listen(2)
            srv.settimeout(1.0)
            self._srv = srv
            self.log(f"LIS server tinglayapti: {ip}:{port} (analizator ulanishini kutyapman)")
        while is_running():
            try:
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            conn.settimeout(1.0)
            with self._lock:
                self._sock = conn
                self.connected = True
            self.log(f"Analizator ulandi: {addr[0]}:{addr[1]}")
            self._pump(self._sock_recv(conn), handler, is_running)
            with self._lock:
                try:
                    conn.close()
                except Exception:
                    pass
                self._sock = None
                self.connected = False
            self.log("Analizator ulanishni yopdi — yangi ulanish kutilmoqda")

    def _run_serial(self, handler, is_running):
        if serial is None:
            raise RuntimeError("pyserial o'rnatilmagan")
        c = self.cfg
        bs = {5: serial.FIVEBITS, 6: serial.SIXBITS, 7: serial.SEVENBITS, 8: serial.EIGHTBITS}
        pr = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
        sb = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}
        ser = serial.Serial(port=c.get("com_port", "COM1"), baudrate=int(c.get("baudrate", 9600)),
                            bytesize=bs.get(int(c.get("bytesize", 8)), serial.EIGHTBITS),
                            parity=pr.get(str(c.get("parity", "N")).upper()[:1], serial.PARITY_NONE),
                            stopbits=sb.get(int(c.get("stopbits", 1)), serial.STOPBITS_ONE),
                            timeout=float(c.get("timeout", 1.0)))
        with self._lock:
            self._ser = ser
            self.connected = True
        self.log(f"COM port ochildi: {self.describe()}")

        def recv():
            try:
                return ser.read(ser.in_waiting or 1) or b""
            except Exception:
                return None
        self._pump(recv, handler, is_running)


# ─────────────────────────────────────────────────────────────────────────────
#  SINOV
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    hl7_5diff = ("MSH|^~\\&|||||20260918085601||ORU^R01|13|P|2.3.1||||||UNICODE\r"
                 "PID|1||1882^^^^MR||^Quvatova Nargiza||19840101000000|F\rOBR|1||260918118069|00001^Automated Count^99MRC||20260918083900\r"
                 "OBX|4|NM|30525-0^Age^LN||7|mo|||||F\rOBX|5|NM|6690-2^WBC^LN||8.4|10*9/L|4.0-10.0|N|||F\r"
                 "OBX|6|NM|751-8^NEU#^LN||5.1|10*9/L|2.0-7.0|N|||F\rOBX|7|NM|770-8^NEU%^LN||60.7|%|50-70|N|||F\r"
                 "OBX|8|NM|731-0^LYM#^LN||2.2|10*9/L|0.8-4.0|N|||F\rOBX|9|NM|736-9^LYM%^LN||26.7|%|20.0-40.0|N|||F\r"
                 "OBX|10|NM|742-7^MON#^LN||0.5|10*9/L||N|||F\rOBX|11|NM|5905-5^MON%^LN||6.0|%||N|||F\r"
                 "OBX|12|NM|711-2^EOS#^LN||0.2|10*9/L||N|||F\rOBX|13|NM|704-7^BAS#^LN||0.0|10*9/L||N|||F\r"
                 "OBX|14|NM|718-7^HGB^LN||107|g/L|120-160|L~N|||F\rOBX|15|NM|777-3^PLT^LN||376|10*9/L|100-300|H~N|||F\r"
                 "OBX|16|NM|10057^NLR^99MRC||2.55|||N|||F\rOBX|33|ED|15000^WBC Histogram. Binary^99MRC||^Application^Octer-stream^Base64^AAAA||||||F\r")
    p = parse_hl7_oru(hl7_5diff)
    print("HL7 5-diff:", p["name"], p["age"], p["gender"], p["sample_id"], p["time"])
    print("  ", {k: v["value"] for k, v in p["tests"].items()}, "abnormal:", p["abnormal"])
    astm = ("H|\\^&|||XP-300^00-01|||||||P|E1394-97|20260918091500\rP|1|||260918118070|Aliyev^Vali||19900505|M\r"
            "O|1|260918118070||^^^^CBC|R||20260918091200\rR|1|^^^^WBC^1|6.8|10*3/uL|4.0-10.0|N||F\r"
            "R|2|^^^^LYMPH%^1|35.2|%|||F\rR|3|^^^^MXD#^1|0.6|10*3/uL|||F\rR|4|^^^^NEUT#^1|4.1|10*3/uL|||F\r"
            "R|5|^^^^HGB^1|13.5|g/dL|||F\rR|6|^^^^RDW-SD^1|41.2|fL|||F\rR|7|^^^^P-LCR^1|22.1|%|||F\rL|1|N\r")
    q = parse_astm(astm)
    print("ASTM:", q["name"], q["age"], q["gender"], q["sample_id"], q["time"])
    print("  ", {k: v["value"] for k, v in q["tests"].items()})
    for cand in ["LYM", "LYM%", "LY#", "Lymph#", "GRA", "GRA%", "NEUT#", "NEUT%", "MONO#", "EO%", "BASO#", "RDWc", "RDWs", "PDWc",
                 "HB", "PLCR", "MXD%", "NE#", "PCT", "MPV", "6690-2", "10027", "Neut", "MID%", "Mid#", "Gran%"]:
        print(f"  {cand:8} → {normalize_param(cand)}")
    print("kinds:", message_kind(hl7_5diff), message_kind(astm),
          message_kind("MSH|^~\\&|||||1||ORM^O01|1|P|2.3.1\rORC|RF\rOBR|1||123\r"),
          message_kind("H|\\^&|||XP\rQ|1|^123||ALL\rL|1|N\r"), astm_query_sample_id("H|\\^&\rQ|1|^123||ALL\rL|1|N\r"))
    print(split_messages(hl7_5diff + hl7_5diff).__len__(), split_messages(astm + astm).__len__())
