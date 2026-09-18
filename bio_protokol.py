# -*- coding: utf-8 -*-
"""
Bioximiya (avtomat) analizatorlari uchun UNIVERSAL ulanish, parse va WORKLIST (shtrix-kod) moduli.

O'zbekistonda uchraydigan avtomat bioximik analizatorlar:
  Mindray BS-120/200/240/360E/430/800, Biobase BK-200/280/400/600 (Mindray andozasi),
  Zybio EXC-200/400, Genrui GS-series, Dirui CS-T240/400/600, URIT-8021A/8030/8210,
  Rayto Chemray 240/420/800, Erba XL-200/640, Human HumaStar 100/200/300,
  BioSystems A15/A25/BA200/400, Roche Cobas c111/Integra, Sinnowa, Getein ...

Ikki oila:
  * HL7 v2.3.1 (MLLP, TCP) — Mindray andozasi: natija ORU^R01; SHTRIX-KOD so'rovi QRY^Q02 →
    LIS javobi QCK^Q02 + DSR^Q03 (29 ta DSP + har tahlil uchun DSP "kanal^^^").
    Ba'zilari (URIT, Zybio, Rayto) so'rovni ORM^O01 bilan yuboradi → ORR^O02.
  * ASTM E1394 (LIS2-A2) — Erba, Human, BioSystems, Roche: natija R yozuvlar;
    shtrix-kod so'rovi Q yozuv → LIS javobi H/P/O(^^^kod\\^^^kod...)/L.

SHTRIX-KOD ISHLASHI UCHUN ASOSIY SHART — analizator o'z KANAL KODI (test ID) bilan ishlaydi.
LIS worklistda bizning tahlil ID (35, 37 ...) emas, ANALIZATOR kodi ketishi kerak. Shuning uchun
"kod xaritasi" (bio_kod_xarita.json, Tizim Sozlamalari → Bioximiya → Tahlil kodlari) bor:
    analizator kodi/nomi  ←→  kanonik LIS kodi (BK-280 raqamlari: 272=Glyukoza, 236=ALT ...)
Kanonik kodlar dastur ichida hamma joyda ishlatiladi (biochemistry_window, on_biochemistry_import).
Yangi analizatorda kodlar tanilmasa — "Noma'lum kodlar" ro'yxatida chiqadi, oynada bog'lanadi.
"""

import os
import re
import json
from datetime import datetime

import gemo_protokol as _gp          # Transport, _hl7_time, _decode_cyrillic (umumiy)
from siydik_protokol import detect_format as _detect_format, MLLP_SB, MLLP_EB

# ─────────────────────────────────────────────────────────────────────────────
#  KANONIK TAHLILLAR — LIS kodi (BK-280 raqamlari) → (ko'rsatish nomi, tahlillar.id, nom variantlari)
#  tahlillar.id — LIMS katalogi (worklist uchun teskari xarita). None = ID ga bog'lanmaydi.
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL_TESTS = {
    "236": ("ALT", 39, ["ALT", "GPT", "ALAT", "SGPT", "ALANIN"]),
    "246": ("AST", 40, ["AST", "GOT", "ASAT", "SGOT", "ASPARTAT"]),
    "319": ("GGT", 46, ["GGT", "GAMMA-GT", "G-GT", "GAMMAGT", "GAMMA GT"]),
    "235": ("IF", 53, ["ALP", "IF", "ALKP", "ALK PHOS", "ALKALINE", "ISHQORIY", "IFERMENT"]),
    "287": ("LDG", 45, ["LDH", "LDG", "LD", "LDGFERMENT", "LACTATE"]),
    "320": ("Umumiy bilirubin", 55, ["TBIL", "T-BIL", "BIL-T", "TBILI", "BILT", "TOTAL BIL", "UM BILR", "UMUMIY BIL", "T BIL"]),
    "321": ("Bog'langan bilirubin", 55, ["DBIL", "D-BIL", "BIL-D", "DBILI", "BILD", "DIRECT BIL", "BOG BILR", "BOG'LANGAN BIL", "D BIL", "CONJ"]),
    "313": ("Mochevina", 42, ["UREA", "BUN", "MOCHEVINA", "UREA-N"]),
    "323": ("Kreatinin", 41, ["CREA", "CRE", "CREAT", "CREATININE", "KREATININ", "CR"]),
    "310": ("Siydik kislotasi", 50, ["UA", "URIC", "URIC ACID", "MOCH KIS", "SIYDIK KIS", "UREA ACID"]),
    "272": ("Glyukoza", 37, ["GLU", "GLUC", "GLUCOSE", "GLUKOZA", "GLYUKOZA", "GLU-HK"]),
    "317": ("Umumiy oqsil", 36, ["TP", "TPROT", "T-PROT", "TOTAL PROTEIN", "OQSIL", "PROT", "TPR"]),
    "233": ("Albumin", 35, ["ALB", "ALBUMIN"]),
    "254": ("Xolesterol", 43, ["CHOL", "TC", "CHO", "TCHO", "CHOLESTEROL", "XOLEST", "T-CHO", "CHOL-T"]),
    "308": ("Trigliserid", 44, ["TG", "TRIG", "TRIGLYCERIDE", "TRIGLIS", "TGL"]),
    "277": ("HDL-xolesterin", 124, ["HDL", "HDL-C", "HDLC", "HDL-CHO", "HDL CHOL"]),
    "289": ("LDL-xolesterin", 123, ["LDL", "LDL-C", "LDLC", "LDL-CHO", "LDL CHOL"]),
    "252": ("Kalsiy", 47, ["CA", "CALCIUM", "KALSIY", "CA++"]),
    "284": ("Kaliy", 48, ["K", "K+", "POTASSIUM", "KALIY"]),
    "296": ("Magniy", 51, ["MG", "MAGNESIUM", "MAGNIY", "MG++"]),
    "297": ("Natriy", 52, ["NA", "NA+", "SODIUM", "NATRIY"]),
    "267": ("Temir", 49, ["FE", "IRON", "TEMIR", "SI"]),
    "237": ("Alfa-amilaza", 56, ["AMY", "AMYL", "AMYLASE", "A-AMILAZA", "AMILAZA", "ALPHA-AMYLASE", "A-PANKRIAT"]),
    "305": ("R faktor", 59, ["RF", "R FAKTOR", "RHEUMATOID", "REVMATOID"]),
    "245": ("ASO", 61, ["ASO", "ASLO", "ASL", "ANTISTREPTOLIZIN", "ANTISTREPTOLYSIN"]),
    "322": ("CRB", 60, ["CRP", "CRB", "SRB", "HSCRP", "HS-CRP", "C-REAKTIV", "S-REAKTIV"]),
    "230": ("Timol", 54, ["TIMOL", "TTT", "THYMOL"]),
    "275": ("HbA1c", None, ["HBA1C", "A1C", "GHB"]),
    "253": ("Xolinesteraza (CHE)", 128, ["CHE", "CHOLINESTERASE", "XOLINESTERAZA", "PSEUDOCHOLINEST"]),
}

# Ko'p komponentli / panel tahlillar: LIMS tahlil ID → worklistga ketadigan kanonik kodlar
WORKLIST_EXPAND = {
    55:  ["320", "321"],                 # Bilirubin (umumiy + bog'langan)
    58:  ["305", "245", "322"],          # REVMOPROBA to'liq (avtomat)
    126: ["254", "308", "277", "289"],   # LIPID SPEKTRI
    127: ["313", "323", "233", "310"],   # BUYRAK PANELI
}

_ALIAS_INDEX = {}
for _code, (_nm, _tid, _aliases) in CANONICAL_TESTS.items():
    for _a in [_nm] + list(_aliases):
        _ALIAS_INDEX[_a.upper().replace(" ", "").replace("-", "").replace("'", "")] = _code


def canonical_name(code: str) -> str:
    return CANONICAL_TESTS.get(str(code), ("", None, []))[0] or f"Kod:{code}"


def canonical_tahlil_id(code: str):
    return CANONICAL_TESTS.get(str(code), ("", None, []))[1]


def guess_canonical(raw_code: str = "", raw_name: str = ""):
    """Analizator kodi/nomidan kanonik LIS kodini taxmin qiladi (nom variantlari bo'yicha)."""
    for cand in (raw_code, raw_name):
        if not cand:
            continue
        c = str(cand).strip()
        if c in CANONICAL_TESTS:
            return c
        k = c.upper().replace(" ", "").replace("-", "").replace("'", "").replace("_", "")
        if k in _ALIAS_INDEX:
            return _ALIAS_INDEX[k]
        # "ALT (GPT)" / "GLU-HK" kabi: birinchi so'z / qavs ichidagi
        for piece in re.split(r"[\s()/,;]+", c.upper()):
            pk = piece.replace("-", "").replace("'", "")
            if pk and pk in _ALIAS_INDEX:
                return _ALIAS_INDEX[pk]
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  KOD XARITASI (bio_kod_xarita.json) — {model: {analizator_kodi: kanonik_kod}}
# ─────────────────────────────────────────────────────────────────────────────
def _map_path() -> str:
    try:
        from monoblok_db_config import CONFIG_PATH
        return os.path.join(os.path.dirname(CONFIG_PATH), "bio_kod_xarita.json")
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "bio_kod_xarita.json")


def _unknown_path() -> str:
    return _map_path().replace("bio_kod_xarita.json", "bio_nomalum_kodlar.json")


def load_code_map() -> dict:
    try:
        with open(_map_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_code_map(m: dict) -> bool:
    try:
        with open(_map_path(), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[XATO] bio_kod_xarita.json saqlanmadi: {e}")
        return False


def load_unknown_codes() -> dict:
    """{model: {analizator_kodi: {"name": ..., "last": "...", "count": n}}}"""
    try:
        with open(_unknown_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _remember_unknown(model: str, code: str, name: str):
    try:
        d = load_unknown_codes()
        m = d.setdefault(model, {})
        e = m.setdefault(code, {"name": name, "count": 0})
        e["name"] = name or e.get("name", "")
        e["count"] = int(e.get("count", 0)) + 1
        e["last"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(_unknown_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def to_canonical(model: str, raw_code: str, raw_name: str = "", code_map: dict = None, remember=True):
    """Analizator kodi → kanonik LIS kodi. Tartib: xarita (kod, nom) → kanonik o'zi → nom taxmini.
    Topilmasa raw_code qaytadi (va noma'lum kodlar ro'yxatiga yoziladi)."""
    cm = (code_map if code_map is not None else load_code_map()).get(model, {})
    rc = (raw_code or "").strip()
    rn = (raw_name or "").strip()
    for key in (rc, rn, rn.upper()):
        if key and key in cm and cm[key]:
            return str(cm[key])
    if rc in CANONICAL_TESTS:
        return rc
    g = guess_canonical(rc, rn)
    if g:
        return g
    if remember and (rc or rn):
        _remember_unknown(model, rc or rn, rn)
    return rc or rn


def analyzer_codes_for(model: str, canonical_code: str, code_map: dict = None) -> list:
    """Kanonik kod → analizator kodlari (worklist uchun teskari xarita). Xaritada bo'lmasa — o'zi."""
    cm = (code_map if code_map is not None else load_code_map()).get(model, {})
    out = [k for k, v in cm.items() if str(v) == str(canonical_code)]
    return out or [str(canonical_code)]


def worklist_codes_for_tahlil(tahlil_id: int, tahlil_nomi: str = "") -> list:
    """LIMS tahlil (id, nom) → kanonik LIS kodlar ro'yxati (panel bo'lsa bir nechta)."""
    if tahlil_id in WORKLIST_EXPAND:
        return list(WORKLIST_EXPAND[tahlil_id])
    for code, (_nm, tid, _al) in CANONICAL_TESTS.items():
        if tid == tahlil_id and tahlil_id is not None:
            return [code]
    g = guess_canonical("", tahlil_nomi)
    return [g] if g else []


# ─────────────────────────────────────────────────────────────────────────────
#  PROFILLAR
# ─────────────────────────────────────────────────────────────────────────────
PROFILES = {
    "biobase_bk": {
        "name": "Biobase BK-200 / BK-280 / BK-400 / BK-600 (HL7, Mindray andozasi)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 8087, "lis_port": 8088,
        "query_type": "qry_dsr", "ack_style": "byte",
        "hint": "Analizator LIS sozlamasi: natija porti = 8087, so'rov (barcode) porti = 8088, IP = shu kompyuter. Kod xaritasi: BK-280 raqamlari (272 Glyukoza ...) — standart.",
    },
    "mindray_bs": {
        "name": "Mindray BS-120 / BS-200 / BS-240 / BS-360E / BS-430 (HL7)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "Setup → LIS: protocol HL7, Server IP = shu kompyuter, port = shu port, 'Bidirectional' + 'Auto query by barcode'. Tahlil kodlari = analizatordagi KANAL raqami (Tahlil kodlari oynasida bog'lang).",
    },
    "zybio_exc": {
        "name": "Zybio EXC-200 / EXC-400 (HL7)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "Settings → LIS: HL7, Server IP/port = shu kompyuter. Kanal kodlarini bog'lang.",
    },
    "dirui_cs": {
        "name": "Dirui CS-T240 / CS-400 / CS-600 (HL7)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "LIS sozlamasi: HL7, Server IP/port = shu kompyuter, 'Query sample by barcode' yoqing.",
    },
    "urit_chem": {
        "name": "URIT-8021A / 8030 / 8210 / 8260 (HL7)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "orm_orr", "ack_style": "hl7",
        "hint": "LIS: HL7, Server IP/port = shu kompyuter. So'rov ORM^O01 → ORR^O02 (QRY ham qo'llanadi).",
    },
    "rayto_chemray": {
        "name": "Rayto Chemray 240 / 420 / 800 (HL7 yoki ASTM)",
        "connection_type": "tcp_server", "protocol": "auto", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "LIS: HL7 (yoki ASTM) — protokol 'auto' ikkalasini taniydi. Server IP/port = shu kompyuter.",
    },
    "genrui_gs": {
        "name": "Genrui GS-series / Dymind chem (HL7)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "Settings → Communication: HL7, LIS IP/port = shu kompyuter.",
    },
    "erba_xl": {
        "name": "Erba XL-200 / XL-640 / EM-200 (ASTM)",
        "connection_type": "tcp_server", "protocol": "astm", "port": 5100, "lis_port": 0,
        "query_type": "astm_q", "ack_style": "hl7",
        "hint": "Settings → Host: ASTM E1394, TCP (yoki RS-232 → serial). Shtrix-kod so'rovi Q yozuv → H/P/O/L.",
    },
    "human_humastar": {
        "name": "Human HumaStar 100 / 200 / 300 (ASTM)",
        "connection_type": "tcp_server", "protocol": "astm", "port": 5100, "lis_port": 0,
        "query_type": "astm_q", "ack_style": "hl7",
        "hint": "Settings → LIS: ASTM (LIS2-A2), TCP yoki serial. Test kodlari = analizatordagi test nomi (masalan GLU, ALT).",
    },
    "biosystems": {
        "name": "BioSystems A15 / A25 / BA200 / BA400 (ASTM)",
        "connection_type": "tcp_server", "protocol": "astm", "port": 5100, "lis_port": 0,
        "query_type": "astm_q", "ack_style": "hl7",
        "hint": "LIS: ASTM, Host = shu kompyuter. Test kodlari = BioSystems test nomi.",
    },
    "roche_cobas": {
        "name": "Roche Cobas c111 / Integra 400 (ASTM)",
        "connection_type": "tcp_server", "protocol": "astm", "port": 5100, "lis_port": 0,
        "query_type": "astm_q", "ack_style": "hl7",
        "hint": "Host communication: ASTM, TCP/IP yoki RS-232 (serial). Test kodlari = Roche test raqami (masalan 20411 GLUC).",
    },
    "hl7_generic": {
        "name": "Boshqa (HL7 ORU^R01 + QRY/DSR yoki ORM/ORR)",
        "connection_type": "tcp_server", "protocol": "hl7", "port": 5100, "lis_port": 0,
        "query_type": "qry_dsr", "ack_style": "hl7",
        "hint": "Har qanday HL7 bioximiya analizatori. Kodlar avtomatik taxmin qilinadi, qolganini Tahlil kodlari oynasida bog'lang.",
    },
    "astm_generic": {
        "name": "Boshqa (ASTM E1394)",
        "connection_type": "serial", "protocol": "astm",
        "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "lis_port": 0,
        "query_type": "astm_q", "ack_style": "hl7",
        "hint": "ENQ/ACK/EOT avtomatik. TCP orqali ham ishlaydi.",
    },
}
DEFAULT_MODEL = "biobase_bk"


def profile_for(cfg: dict) -> dict:
    return PROFILES.get((cfg or {}).get("model") or DEFAULT_MODEL, PROFILES[DEFAULT_MODEL])


def effective_config(cfg: dict) -> dict:
    prof = profile_for(cfg)
    out = {k: v for k, v in prof.items() if k not in ("name", "hint")}
    for k, v in (cfg or {}).items():
        if v not in (None, ""):
            out[k] = v
    out.setdefault("connection_type", "tcp_server")
    out.setdefault("protocol", "auto")
    out.setdefault("encoding", "utf-8")
    out.setdefault("ip", "0.0.0.0")
    out.setdefault("port", 8087)
    out.setdefault("lis_port", 0)
    out.setdefault("query_type", "qry_dsr")
    out.setdefault("ack_style", "hl7")
    out.setdefault("model", DEFAULT_MODEL)
    out.setdefault("reconnect_interval", 5)
    out.setdefault("idle_timeout", 3.0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  PARSER — natija xabari → {sample_id, sample_no, name, time, tests{kanonik: {...}}}
# ─────────────────────────────────────────────────────────────────────────────
_BARCODE_RE = re.compile(r"^[A-Za-z0-9\-]{6,}$")


def _looks_like_barcode(s: str) -> bool:
    s = (s or "").strip()
    return bool(s) and bool(_BARCODE_RE.match(s)) and not s.upper().startswith(("BIOBASE", "MINDRAY"))


def _new_result():
    return {"time": datetime.now().strftime("%d.%m.%Y %H:%M"), "sample_id": "", "sample_no": "",
            "name": "", "tests": {}, "abnormal": False, "msh": {}, "unknown": {}}


def _put_test(res: dict, model: str, raw_code: str, raw_name: str, value: str, unit: str,
              ref: str, flag: str, code_map: dict):
    value = (value or "").strip()
    if not value or value == "*":
        return
    canon = to_canonical(model, raw_code, raw_name, code_map)
    fu = (flag or "").strip().upper()
    ab = bool(fu) and fu != "N" and ("H" in fu or "L" in fu)
    if ab:
        res["abnormal"] = True
    if canon not in CANONICAL_TESTS:
        res["unknown"][canon] = raw_name or raw_code
    key = canon
    if key in res["tests"]:          # takroriy (qayta o'lchov) — oxirgisi
        pass
    res["tests"][key] = {
        "lis_code": canon, "raw_code": raw_code, "analyzer_name": raw_name or canonical_name(canon),
        "name": canonical_name(canon) if canon in CANONICAL_TESTS else (raw_name or raw_code),
        "tahlil_id": canonical_tahlil_id(canon),
        "value": value, "unit": (unit or "").strip(), "ref": (ref or "").strip().replace("~", " - "),
        "flag": (flag or "").strip(), "abnormal": ab,
    }


def parse_hl7_oru(message: str, model: str = DEFAULT_MODEL, code_map: dict = None) -> dict:
    res = _new_result()
    cm = code_map if code_map is not None else load_code_map()
    for seg in re.split(r"[\r\n]+", message or ""):
        seg = seg.strip().lstrip("\x0b")
        if len(seg) < 3:
            continue
        tag, f = seg[:3], seg.split("|")
        if tag == "MSH":
            res["msh"] = {"app": f[2] if len(f) > 2 else "", "fac": f[3] if len(f) > 3 else "",
                          "ctrl": f[9] if len(f) > 9 else "", "ver": f[11] if len(f) > 11 else "2.3.1"}
            if len(f) > 6 and f[6]:
                res["time"] = _gp._hl7_time(f[6], res["time"])
        elif tag == "PID":
            for idx in (5, 4):
                if len(f) > idx and f[idx].strip() and not f[idx].strip().isdigit():
                    parts = f[idx].split("^")
                    nm = " ".join(_gp._decode_cyrillic(p) for p in parts[:2] if p).strip()
                    if nm:
                        res["name"] = nm
                        break
            if len(f) > 3 and f[3] and _looks_like_barcode(f[3].split("^")[0]) and not res["sample_id"]:
                res["_pid_id"] = f[3].split("^")[0].strip()
        elif tag == "OBR":
            c2 = f[2].strip() if len(f) > 2 else ""
            c3 = f[3].strip().split("^")[0] if len(f) > 3 else ""
            for cand in (c2, c3):
                if _looks_like_barcode(cand) and (len(cand) > len(res["sample_id"])):
                    res["sample_id"] = cand
            for cand in (c3, c2):
                if cand and cand.isdigit() and len(cand) < 6:
                    res["sample_no"] = cand
            for idx in (7, 6):
                if len(f) > idx and f[idx].strip():
                    res["time"] = _gp._hl7_time(f[idx].strip(), res["time"])
                    break
        elif tag == "OBX":
            if len(f) < 6:
                continue
            parts = f[3].split("^")
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
            if not name and len(f) > 4 and f[4].strip() and not f[4].strip().replace(".", "").isdigit():
                name = f[4].strip()          # BK-280: OBX-4 da nom
            value = f[5].strip()
            unit = f[6].strip() if len(f) > 6 else ""
            ref = f[7].strip() if len(f) > 7 else ""
            flag = f[8].strip() if len(f) > 8 else ""
            if f[2].strip().upper() == "ED":
                continue
            _put_test(res, model, code, name, value, unit, ref, flag, cm)
    if not res["sample_id"] and res.get("_pid_id"):
        res["sample_id"] = res["_pid_id"]
    res.pop("_pid_id", None)
    res["_raw"] = message
    res["_format"] = "hl7"
    return res


_ASTM_FRAME_RE = _gp._ASTM_FRAME_RE


def parse_astm(message: str, model: str = DEFAULT_MODEL, code_map: dict = None) -> dict:
    res = _new_result()
    cm = code_map if code_map is not None else load_code_map()
    clean = _ASTM_FRAME_RE.sub("", message or "")
    for rec in re.split(r"[\r\n]+", clean):
        rec = rec.strip()
        if not rec:
            continue
        f = rec.split("|")
        rt = f[0].lstrip("0123456789").strip()
        if rt == "H":
            res["msh"] = {"app": f[4] if len(f) > 4 else "", "fac": "", "ctrl": "", "ver": "ASTM"}
            if len(f) > 13 and f[13]:
                res["time"] = _gp._hl7_time(f[13], res["time"])
        elif rt == "P":
            if len(f) > 5 and f[5]:
                res["name"] = " ".join(x for x in f[5].split("^")[:2] if x).strip()
            if len(f) > 3 and f[3].strip() and _looks_like_barcode(f[3]):
                res["_pid_id"] = f[3].strip()
        elif rt == "O":
            for idx in (2, 3):
                if len(f) > idx and f[idx].strip():
                    cand = f[idx].split("^")[0].strip()
                    if _looks_like_barcode(cand) and len(cand) > len(res["sample_id"]):
                        res["sample_id"] = cand
                    elif cand.isdigit() and len(cand) < 6:
                        res["sample_no"] = cand
            if len(f) > 7 and f[7]:
                res["time"] = _gp._hl7_time(f[7], res["time"])
        elif rt == "R":
            if len(f) < 4:
                continue
            parts = [x for x in f[2].split("^") if x]
            code = parts[0] if parts else ""
            name = parts[1] if len(parts) > 1 else ""
            value = f[3].replace("^", " ").strip()
            unit = f[4].strip() if len(f) > 4 else ""
            ref = f[5].strip() if len(f) > 5 else ""
            flag = f[6].strip() if len(f) > 6 else ""
            _put_test(res, model, code, name, value, unit, ref, flag, cm)
    if not res["sample_id"] and res.get("_pid_id"):
        res["sample_id"] = res["_pid_id"]
    res.pop("_pid_id", None)
    res["_raw"] = message
    res["_format"] = "astm"
    return res


def parse_message(raw: str, model: str = DEFAULT_MODEL, code_map: dict = None) -> dict:
    return parse_astm(raw, model, code_map) if _detect_format(raw) == "astm" else parse_hl7_oru(raw, model, code_map)


def message_kind(raw: str) -> str:
    """'oru' | 'qry' | 'orm' | 'ack' | 'astm_result' | 'astm_query' | 'other'"""
    s = (raw or "").lstrip("\x0b\x02\x05\r\n ")
    if s.startswith("MSH|"):
        f = s.split("\r")[0].split("|")
        mt = f[8].upper() if len(f) > 8 else ""
        if mt.startswith("ORU"):
            return "oru"
        if mt.startswith("QRY"):
            return "qry"
        if mt.startswith("ORM"):
            return "orm"
        if mt.startswith("ACK"):
            return "ack"
        return "other"
    return _gp.message_kind(s)


def split_messages(content: str) -> list:
    return _gp.split_messages(content)


# ─────────────────────────────────────────────────────────────────────────────
#  WORKLIST (shtrix-kod) — bazadan bemor + buyurtma tahlillari
# ─────────────────────────────────────────────────────────────────────────────
def lookup_order(sample_id: str):
    """{'patient': {...}, 'tests': [{'test_id','nomi','birlik','norma'}]} yoki None.
    Faqat orders.sample_id (yoki bemor natija_kodi/kod_yollanma) bo'yicha — orders.id bo'yicha EMAS
    (analizator namuna raqami 22 bo'lsa 22-buyurtmaga xato biriktirilmasin)."""
    sid = (sample_id or "").strip()
    if not sid:
        return None
    try:
        from monoblok_db_config import DB_CONFIG
        import mysql.connector
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT b.id AS bemor_id, b.fish, b.yosh, b.jins, b.tugilgan_sana, b.telefon,
                   o.id AS order_id, o.sample_id, o.sana_vaqt
            FROM orders o JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sample_id=%s OR b.sample_id=%s OR b.natija_kodi=%s OR b.kod_yollanma=%s
            ORDER BY o.id DESC LIMIT 1""", (sid, sid, sid, sid))
        patient = cur.fetchone()
        if not patient:
            cur.close(); conn.close()
            return None
        cur.execute("""
            SELECT t.id AS test_id, COALESCE(oi.nomi, t.nomi) AS nomi, t.sample AS guruh
            FROM order_items oi JOIN tahlillar t ON oi.tahlil_id = t.id
            WHERE oi.order_id=%s ORDER BY oi.id""", (patient["order_id"],))
        tests = cur.fetchall()
        cur.close(); conn.close()
        return {"patient": patient, "tests": tests}
    except Exception as e:
        print(f"[bio_protokol] lookup_order xato: {e}")
        return None


def worklist_items(order_data: dict, model: str, code_map: dict = None) -> list:
    """Buyurtma tahlillari → [(analizator_kodi, nom, birlik, norma)] — faqat bioximiya, kanal kodi bilan."""
    cm = code_map if code_map is not None else load_code_map()
    seen, out = set(), []
    for t in (order_data or {}).get("tests", []):
        tid = t.get("test_id")
        for canon in worklist_codes_for_tahlil(tid, t.get("nomi", "")):
            for acode in analyzer_codes_for(model, canon, cm):
                if acode in seen:
                    continue
                seen.add(acode)
                out.append((acode, canonical_name(canon), "", ""))
    return out


def _hl7_ts(dt) -> str:
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%Y%m%d%H%M%S")
        s = str(dt or "")
        return re.sub(r"[^0-9]", "", s)[:14].ljust(14, "0") if s else ""
    except Exception:
        return ""


def _patient_fields(p: dict):
    fish = (p.get("fish") or "").strip()
    dob = _hl7_ts(p.get("tugilgan_sana"))[:8]
    dob = dob + "000000" if len(dob) == 8 else ""
    j = (p.get("jins") or "").lower()
    sex = "M" if j.startswith(("e", "m", "м")) else "F" if j.startswith(("a", "f", "ж", "w")) else "O"
    return fish, dob, sex


def wrap_mllp(text: str, encoding="utf-8") -> bytes:
    return MLLP_SB + text.encode(encoding, errors="replace") + MLLP_EB


def build_hl7_ack(msh: dict, kind="R01", code="AA", text="Message accepted", err="0") -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    app, fac = msh.get("app", ""), msh.get("fac", "")
    ctrl = msh.get("ctrl", "") or ts
    return (f"MSH|^~\\&|LIS||{app}|{fac}|{ts}||ACK^{kind}|{ctrl}|P|2.3.1||||0||ASCII|||\r"
            f"MSA|{code}|{ctrl}|{text}|||{err}|\r")


def parse_qry(message: str) -> dict:
    """QRY^Q02 → {sample_id, query_id, qrd, qrf, msh}"""
    out = {"sample_id": "", "query_id": "1", "qrd": "", "qrf": "", "msh": {}}
    for line in re.split(r"[\r\n]+", (message or "").lstrip("\x0b")):
        line = line.strip()
        if line.startswith("MSH|"):
            f = line.split("|")
            out["msh"] = {"app": f[2] if len(f) > 2 else "", "fac": f[3] if len(f) > 3 else "",
                          "ctrl": f[9] if len(f) > 9 else ""}
        elif line.startswith("QRD|"):
            out["qrd"] = line
            f = line.split("|")
            if len(f) > 8:
                out["sample_id"] = f[8].split("^")[0].strip()
            if len(f) > 4 and f[4].strip():
                out["query_id"] = f[4].strip()
        elif line.startswith("QRF|"):
            out["qrf"] = line
    return out


def build_qck(q: dict, found: bool) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    msh = q.get("msh", {})
    ctrl = msh.get("ctrl", "") or ts
    return (f"MSH|^~\\&|LIS||{msh.get('app', '')}|{msh.get('fac', '')}|{ts}||QCK^Q02|{ctrl}|P|2.3.1|||||ASCII|||\r"
            f"MSA|AA|{ctrl}|Message accepted|||0|\rERR|0|\rQAK|SR|{'OK' if found else 'NF'}|\r")


def build_dsr(q: dict, order_data: dict, model: str, code_map: dict = None) -> str:
    """DSR^Q03 — Mindray/Biobase andozasi: 29 ta DSP + har tahlil uchun DSP 'kanal^nom^birlik^norma'."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    msh = q.get("msh", {})
    ctrl = msh.get("ctrl", "") or ts
    p = order_data["patient"]
    fish, dob, sex = _patient_fields(p)
    barcode = str(p.get("sample_id") or q.get("sample_id") or "")
    qrd = q.get("qrd") or f"QRD|{ts}|R|D|{q.get('query_id', '1')}|||RD|{barcode}|OTH|||T|"
    qrf = q.get("qrf") or f"QRF|LIS|{ts[:8]}000000|{ts}|||RCT|COR|ALL|"
    dsp = ["", "", fish, dob, sex, "", "", "", "", (p.get("telefon") or ""), "", "", "", "", "", "", "",
           "", "", "", barcode, str(p.get("order_id") or ""), _hl7_ts(p.get("sana_vaqt")), "N", "",
           "serum", "", ""]
    segs = [f"MSH|^~\\&|LIS||{msh.get('app', '')}|{msh.get('fac', '')}|{ts}||DSR^Q03|{ctrl}|P|2.3.1|||||ASCII|||",
            f"MSA|AA|{ctrl}|Message accepted|||0|", "ERR|0|", "QAK|SR|OK|", qrd, qrf]
    for i, v in enumerate(dsp, 1):
        segs.append(f"DSP|{i}||{v}|||")
    i = len(dsp) + 1
    for acode, nm, unit, norma in worklist_items(order_data, model, code_map):
        segs.append(f"DSP|{i}||{acode}^{nm}^{unit}^{norma}|||")
        i += 1
    segs.append("DSC||")
    return "\r".join(segs) + "\r"


def orm_sample_id(message: str) -> str:
    for line in re.split(r"[\r\n]+", message or ""):
        f = line.strip().split("|")
        if f[0] in ("ORC", "OBR"):
            for idx in (3, 2):
                if len(f) > idx and f[idx].strip():
                    return f[idx].split("^")[0].strip()
    return ""


def build_orr(msh: dict, order_data, sample_id: str, model: str, code_map: dict = None) -> str:
    """ORR^O02 — ORM^O01 so'roviga javob: PID + har tahlil uchun ORC/OBR (OBR-4 = kanal^nom)."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    ctrl = msh.get("ctrl", "") or ts
    segs = [f"MSH|^~\\&|LIS||{msh.get('app', '')}|{msh.get('fac', '')}|{ts}||ORR^O02|{ctrl}|P|2.3.1||||0||ASCII|||"]
    if not order_data:
        segs.append(f"MSA|AR|{ctrl}|Sample not found|||204|")
        return "\r".join(segs) + "\r"
    p = order_data["patient"]
    fish, dob, sex = _patient_fields(p)
    segs.append(f"MSA|AA|{ctrl}|Message accepted|||0|")
    segs.append(f"PID|1||{p.get('bemor_id', '')}^^^^MR||{fish}||{dob}|{sex}")
    n = 1
    for acode, nm, unit, norma in worklist_items(order_data, model, code_map):
        segs.append(f"ORC|OK|{sample_id}||||||{ts}")
        segs.append(f"OBR|{n}|{sample_id}|{sample_id}|{acode}^{nm}|||{ts}||||||||serum")
        n += 1
    return "\r".join(segs) + "\r"


def build_orm_new_order(order_data: dict, sample_id: str, model: str, code_map: dict = None,
                        app: str = "", fac: str = "") -> str:
    """ORM^O01 (yangi buyurtma) — LIS o'zi analizatorga namuna ma'lumotini YUBORADI (push).
    So'rov qilmaydigan analizatorlar (BK-280 V1) uchun sinov: ORC|NW + har tahlil uchun OBR."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    p = order_data["patient"]
    fish, dob, sex = _patient_fields(p)
    segs = [f"MSH|^~" + chr(92) + f"&|LIS||{app}|{fac}|{ts}||ORM^O01|{ts[-6:]}|P|2.3.1||||0||ASCII|||",
            f"PID|1||{p.get('bemor_id', '')}^^^^MR||{fish}||{dob}|{sex}"]
    n = 1
    for acode, nm, unit, norma in worklist_items(order_data, model, code_map):
        segs.append(f"ORC|NW|{sample_id}|{sample_id}|||||{ts}")
        segs.append(f"OBR|{n}|{sample_id}|{sample_id}|{acode}^{nm}||{ts}|{ts}||||||||serum|||||||||||||")
        n += 1
    return chr(13).join(segs) + chr(13)



def build_astm_worklist(sample_id: str, order_data, model: str, code_map: dict = None) -> str:
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    lines = [f"H|\\^&|||AzizMedLine^LIS|||||||P|LIS2-A2|{now}"]
    if order_data:
        p = order_data["patient"]
        fish, dob, sex = _patient_fields(p)
        tests = "\\".join(f"^^^{acode}" for acode, *_ in worklist_items(order_data, model, code_map))
        lines.append(f"P|1|{p.get('bemor_id', '')}||{sample_id}|{fish}||{dob[:8]}|{sex}")
        lines.append(f"O|1|{sample_id}||{tests}|R||{now}|||||||serum|||||||||||O")
    lines.append("L|1|N")
    return "\r".join(lines) + "\r"


# ─────────────────────────────────────────────────────────────────────────────
#  SINOV
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    bk = ("\x0bMSH|^~\\&|BIOBASE|BK-200|||20260918100959||ORU^R01|65|P|2.3.1||||0||ASCII|||\r"
          "PID|65||||Bozorova Umida|||O|||\rOBR|22|260918118070|22|BIOBASE^BK-200|N|20260918100959|20260918100959||||||||serum|1000|\r"
          "OBX|0|NM|322|CRB|0.10818|mg/L|0~5|N|||||\rOBX|1|NM|305|R FAKTOR|1.289|IU/ml|0~14|N|||||\r"
          "OBX|2|NM|999|NEWTEST|5.5|U/L|0~10|H|||||\r\x1c\r")
    r = parse_hl7_oru(bk, "biobase_bk", {})
    print("BK:", r["sample_id"], r["sample_no"], r["name"], {k: (v["name"], v["value"]) for k, v in r["tests"].items()}, "unknown:", r["unknown"])
    ms = ("MSH|^~\\&|Mindray|BS-240|||20260918||ORU^R01|7|P|2.3.1\rPID|1||ID12||Karimov^Ali||19800101|M\r"
          "OBR|1|33|260918118071|BS-240||20260918101010\rOBX|1|NM|3^GLU^99MRC||5.4|mmol/L|3.9-6.1|N|||F\r"
          "OBX|2|NM|7^ALT^99MRC||41|U/L|0-40|H|||F\rOBX|3|NM|12^TBIL^99MRC||14.1|umol/L||N|||F\r")
    r2 = parse_hl7_oru(ms, "mindray_bs", {"mindray_bs": {"3": "272"}})
    print("BS:", r2["sample_id"], r2["name"], {k: (v["name"], v["value"]) for k, v in r2["tests"].items()}, "unknown:", r2["unknown"])
    astm = ("H|\\^&|||XL-200|||||||P|E1394-97|20260918\rP|1|||260918118072|Aliyev^Vali||19900505|M\r"
            "O|1|260918118072||^^^GLU\\^^^UREA|R\rR|1|^^^GLU^Glucose|5.1|mmol/L|3.9-6.1|N||F\rR|2|^^^UREA|6.3|mmol/L|||F\rL|1|N\r")
    r3 = parse_astm(astm, "erba_xl", {})
    print("ASTM:", r3["sample_id"], r3["name"], {k: (v["name"], v["value"]) for k, v in r3["tests"].items()})
    print("kinds:", message_kind(bk), message_kind(ms), message_kind("MSH|^~\\&|BIOBASE|BK-280|||1||QRY^Q02|9|P|2.3.1\rQRD|1|R|D|5|||RD|260918118070|OTH|||T|\r"),
          message_kind("H|\\^&\rQ|1|^260918118070||ALL\rL|1|N\r"))
    od = {"patient": {"bemor_id": 5, "fish": "Test Bemor", "jins": "Ayol", "tugilgan_sana": "1990-05-05", "order_id": 777,
                      "sample_id": "260918118070", "sana_vaqt": "2026-09-18 10:00:00", "telefon": ""},
          "tests": [{"test_id": 37, "nomi": "Glyukoza"}, {"test_id": 55, "nomi": "Bilirubin"}, {"test_id": 126, "nomi": "LIPID SPEKTRI"}, {"test_id": 999, "nomi": "Vitamin D"}]}
    print("worklist BK:", worklist_items(od, "biobase_bk", {}))
    print("worklist BS:", worklist_items(od, "mindray_bs", {"mindray_bs": {"3": "272", "12": "320", "13": "321"}}))
    q = parse_qry("MSH|^~\\&|BIOBASE|BK-280|||1||QRY^Q02|9|P|2.3.1\rQRD|1|R|D|5|||RD|260918118070|OTH|||T|\rQRF|BK-280|\r")
    print(build_dsr(q, od, "biobase_bk", {}).replace("\r", "\n")[-260:])
    print(build_orr({"app": "URIT", "fac": "8021A", "ctrl": "3"}, od, "260918118070", "urit_chem", {}).replace("\r", "\n"))
    print(build_astm_worklist("260918118070", od, "erba_xl", {"erba_xl": {"GLU": "272", "TBIL": "320", "DBIL": "321"}}).replace("\r", "\n"))
