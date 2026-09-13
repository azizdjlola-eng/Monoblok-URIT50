# -*- coding: utf-8 -*-
"""
BC-20S analizatorining USB eksporti (Review → Export → CSV) ni dasturga import qilish.

NIMA UCHUN: analizator LIS ga natija yubormay qo'ysa (12.09.2026 — avtопередача
o'chib qolgan), yoki ilgari LIS siz ishlagan klinikada eski natijalarni olish
kerak bo'lsa — analizatorning o'zidan USB ga CSV eksport qilinadi va shu modul
uni dastur tushunadigan HL7 TXT (BC-20s/YYYYMM/BC-20s_YYYYMMDD_NNN.txt) ga
aylantiradi. Keyin hamma narsa odatdagidek: gemotologiya oynasi ko'rsatadi,
bazaga sample_id bo'yicha saqlanadi, blankaga chiqadi.

CSV xususiyatlari (Mindray BC-20S, rus interfeysi):
  - kodirovka GB2312 (xitoycha codepage!) — cp1251/utf-8 da "§б§в" bo'lib chiqadi
  - qator ajratkichi faqat \\r
  - qiymat oldida bayroq: "↑ 13.0", "Р↓ 0.7", "Р 16.57"  (↑=H, ↓=L, Р=A/review)
  - norma diapazoni YO'Q — mavjud TXT fayllardan (shu Ref Group uchun) olinadi,
    bo'lmasa DEFAULT_REFS
  - "Background" (fon) qatorlari — bemor emas, o'tkazib yuboriladi
"""

import os
import re
import csv
import io
import glob
import json
from datetime import datetime, date

try:
    from bc20s_listener import MINDRAY_DAT_BASE
except Exception:
    MINDRAY_DAT_BASE = r"G:\DASTUR\URIT 50\BC-20s"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFS_PATH = os.path.join(BASE_DIR, "bc20s_import_prefs.json")

# ── Parametrlar: CSV kaliti → HL7 (kod, nom, tizim, birlik). Tartib analizator
#    HL7 xabaridagi kabi (parse_hl7_file va _save_to_db shu kodlarni biladi).
PARAMS = [
    ("WBC",    "6690-2",  "WBC",    "LN",    "10*9/L"),
    ("LYM#",   "731-0",   "LYM#",   "LN",    "10*9/L"),
    ("LYM%",   "736-9",   "LYM%",   "LN",    "%"),
    ("NLR",    "10057",   "NLR",    "99MRC", ""),
    ("PLR",    "10058",   "PLR",    "99MRC", ""),
    ("RBC",    "789-8",   "RBC",    "LN",    "10*12/L"),
    ("HGB",    "718-7",   "HGB",    "LN",    "g/L"),
    ("MCV",    "787-2",   "MCV",    "LN",    "fL"),
    ("MCH",    "785-6",   "MCH",    "LN",    "pg"),
    ("MCHC",   "786-4",   "MCHC",   "LN",    "g/L"),
    ("RDW-CV", "788-0",   "RDW-CV", "LN",    "%"),
    ("RDW-SD", "21000-5", "RDW-SD", "LN",    "fL"),
    ("HCT",    "4544-3",  "HCT",    "LN",    "%"),
    ("PLT",    "777-3",   "PLT",    "LN",    "10*9/L"),
    ("MPV",    "32623-1", "MPV",    "LN",    "fL"),
    ("PDW",    "32207-3", "PDW",    "LN",    ""),
    ("PCT",    "10002",   "PCT",    "99MRC", "%"),
    ("MID#",   "10027",   "MID#",   "99MRC", "10*9/L"),
    ("MID%",   "10029",   "MID%",   "99MRC", "%"),
    ("GRAN#",  "10028",   "GRAN#",  "99MRC", "10*9/L"),
    ("GRAN%",  "10030",   "GRAN%",  "99MRC", "%"),
]

# CSV sarlavhasidagi nom → bizning kalit (birlik qavsi va '*' olib tashlangandan keyin)
CSV_PARAM_ALIASES = {
    "WBC": "WBC", "LYMPH#": "LYM#", "LYM#": "LYM#", "LYMPH%": "LYM%", "LYM%": "LYM%",
    "MID#": "MID#", "MID%": "MID%", "GRAN#": "GRAN#", "GRAN%": "GRAN%",
    "RBC": "RBC", "HGB": "HGB", "HCT": "HCT", "MCV": "MCV", "MCH": "MCH", "MCHC": "MCHC",
    "RDW-CV": "RDW-CV", "RDW-SD": "RDW-SD", "PLT": "PLT", "MPV": "MPV", "PDW": "PDW",
    "PCT": "PCT", "NLR": "NLR", "PLR": "PLR",
}

# Analizatorning "Общая" guruhi normalari (12.09.2026 dagi HL7 dan) — zaxira
DEFAULT_REFS = {
    "WBC": "4.0-10.0", "LYM#": "0.8-4.0", "LYM%": "20.0-40.0", "RBC": "3.50-5.50",
    "HGB": "120-160", "MCV": "80.0-100.0", "MCH": "27.0-34.0", "MCHC": "320-360",
    "RDW-CV": "11.0-16.0", "RDW-SD": "35.0-56.0", "HCT": "37.0-54.0", "PLT": "100-300",
    "MPV": "6.5-12.0", "PDW": "15.0-17.0", "PCT": "0.108-0.282", "MID#": "0.1-1.5",
    "MID%": "3.0-15.0", "GRAN#": "2.0-7.0", "GRAN%": "50.0-70.0", "NLR": "", "PLR": "",
}

# Ma'lumot ustunlari: bizning kalit → sarlavha variantlari (rus / ingliz), kichik harfda
META_COLS = {
    "sample":       ["id пробы", "sample id", "sample no", "sample no.", "sample id.", "№ пробы", "sampleid"],
    "status":       ["состоян.пробы", "sample status"],
    "name":         ["имя", "first name", "name", "patient name", "фио", "имя пациента"],
    "surname":      ["фамилия", "last name", "surname"],
    "mode":         ["режим", "mode"],
    "date":         ["дата", "date", "test date", "дата теста", "дата анализа"],
    "time":         ["время", "time", "test time", "время теста", "время анализа"],
    "patient_id":   ["id пациента", "patient id"],
    "sex":          ["пол", "gender", "sex"],
    "ref_group":    ["конт.группа", "ref. group", "ref group"],
    "dob":          ["дата рождения", "birthday", "date of birth"],
    "age":          ["возраст", "age", "age(year)"],
    "dept":         ["отделение", "department"],
    "collect_date": ["дата отбора", "sampling date", "collection date"],
    "collect_time": ["время отбора", "sampling time", "collection time"],
    "deliver_date": ["дата доставки", "delivery date"],
    "deliver_time": ["время доставки", "delivery time"],
    "doctor":       ["врач", "physician", "doctor"],
    "operator":     ["оператор", "operator"],
}


# ══════════════════════════════════════════════════════════════════════════
#  Sozlamalar (oxirgi USB papka)
# ══════════════════════════════════════════════════════════════════════════
def load_prefs():
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(d):
    try:
        cur = load_prefs()
        cur.update(d or {})
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════
#  CSV O'QISH
# ══════════════════════════════════════════════════════════════════════════
def _decode_csv_bytes(b: bytes) -> str:
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", errors="replace")
    # Mindray: GB2312/GBK. Kirill harflar shu kodda 2 baytli bo'lib yoziladi.
    for enc in ("gb18030", "utf-8", "cp1251"):
        try:
            t = b.decode(enc)
            # gb18030 hamma narsani "o'qiydi" — kirill chiqdimi tekshiramiz
            if enc == "gb18030" and not re.search(r"[\u0400-\u04ff]", t):
                # kirill yo'q — balki ingliz interfeysi; baribir qabul qilamiz
                pass
            return t
        except Exception:
            continue
    return b.decode("latin-1", errors="replace")


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _param_key_from_header(h: str):
    """'Lymph# (10^9/L)' → 'LYM#', '*NLR ( )' → 'NLR', boshqa → None"""
    base = re.sub(r"\(.*?\)", "", h or "").strip().lstrip("*").strip().upper()
    return CSV_PARAM_ALIASES.get(base)


def _find_meta_index(headers_norm, key):
    for i, h in enumerate(headers_norm):
        if h in META_COLS[key]:
            return i
    return None


_VAL_RE = re.compile(r"^\s*([^\d\-\.\+]*)\s*([\-\+]?\d+(?:[\.,]\d+)?)\s*$")


def _parse_value_cell(cell: str):
    """'Р↓ 0.7 ' → ('0.7', 'L~A');  '↑ 13.0' → ('13.0','H~N');  ' 3.83' → ('3.83','N')
    Qiymat yo'q/*** bo'lsa → (None, '')"""
    if cell is None:
        return None, ""
    m = _VAL_RE.match(str(cell))
    if not m:
        return None, ""
    prefix, num = m.group(1), m.group(2).replace(",", ".")
    hl = "H" if "↑" in prefix else ("L" if "↓" in prefix else "")
    review = bool(re.search(r"[РRrр]", prefix))
    if hl:
        flag = f"{hl}~{'A' if review else 'N'}"
    else:
        flag = "A" if review else "N"
    return num, flag


def _parse_date(s: str):
    """'12/09/2026' (dd/mm/yyyy) | '2026-09-12' | '2026/09/12' → date yoki None"""
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(s: str):
    s = (s or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _combine(d, t):
    if not d:
        return None
    return datetime.combine(d, t) if t else datetime.combine(d, datetime.min.time())


def _parse_age(s: str):
    """'41 Лет' → ('41','yr'); '7 Мес' → ('7','mo'); '20 Дн' → ('20','d')"""
    s = (s or "").strip()
    m = re.match(r"(\d+)\s*(.*)", s)
    if not m:
        return "", ""
    v, u = m.group(1), m.group(2).strip().lower()
    if u.startswith(("мес", "mo", "month")):
        return v, "mo"
    if u.startswith(("дн", "d", "day")):
        return v, "d"
    if u.startswith(("нед", "w")):
        return v, "wk"
    return v, "yr"


def _parse_sex(s: str):
    u = (s or "").strip().upper()
    if not u:
        return ""
    if u.startswith(("М", "M")):
        return "M"
    if u.startswith(("Ж", "F", "W")):
        return "F"
    return ""


def read_csv_rows(path: str) -> list:
    """CSV → [dict] (har qator: sample, name, dt, params{key:(val,flag)}, ...)"""
    with open(path, "rb") as f:
        text = _decode_csv_bytes(f.read())
    # Mindray faqat \r ishlatadi; csv moduli uchun universal qilamiz
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []

    headers = rows[0]
    hn = [_norm_header(h) for h in headers]
    param_idx = {}
    for i, h in enumerate(headers):
        k = _param_key_from_header(h)
        if k and k not in param_idx:
            param_idx[k] = i
    meta_idx = {k: _find_meta_index(hn, k) for k in META_COLS}

    def g(r, key):
        i = meta_idx.get(key)
        return r[i].strip() if i is not None and i < len(r) else ""

    out = []
    for r in rows[1:]:
        sample = g(r, "sample")
        params = {}
        for k, i in param_idx.items():
            if i < len(r):
                v, fl = _parse_value_cell(r[i])
                if v is not None:
                    params[k] = (v, fl)
        d = _parse_date(g(r, "date"))
        t = _parse_time(g(r, "time"))
        dt = _combine(d, t)
        name = g(r, "name")
        surname = g(r, "surname")
        is_bg = (not sample) or sample.lower().startswith("background") or not params
        out.append({
            "sample": sample,
            "name": name, "surname": surname,
            "full_name": (f"{surname} {name}".strip() if surname and name else (name or surname)),
            "dt": dt,
            "collect_dt": _combine(_parse_date(g(r, "collect_date")), _parse_time(g(r, "collect_time"))),
            "deliver_dt": _combine(_parse_date(g(r, "deliver_date")), _parse_time(g(r, "deliver_time"))),
            "patient_id": g(r, "patient_id"),
            "sex": _parse_sex(g(r, "sex")),
            "ref_group": g(r, "ref_group") or "Общая",
            "dob": _parse_date(g(r, "dob")),
            "age": _parse_age(g(r, "age")),
            "dept": g(r, "dept"),
            "doctor": g(r, "doctor"),
            "operator": g(r, "operator"),
            "mode": g(r, "mode"),
            "params": params,
            "background": is_bg,
            "source_file": os.path.basename(path),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════
#  NORMA DIAPAZONLARI — mavjud TXT fayllardan o'rganish
# ══════════════════════════════════════════════════════════════════════════
_OBX_NM_RE = re.compile(r"^OBX\|\d+\|NM\|([^\^|]+)\^([^\^|]*)\^[^|]*\|\|([^|]*)\|([^|]*)\|([^|]*)\|")


def learn_ref_ranges(max_files=40) -> dict:
    """{ref_group: {param_key: ref}} — oxirgi TXT fayllardan. Ref Group OBX 01002."""
    code_to_key = {code: key for key, code, *_ in PARAMS}
    learned = {}
    try:
        files = sorted(glob.glob(os.path.join(MINDRAY_DAT_BASE, "*", "BC-20s_*.txt")),
                       key=os.path.getmtime, reverse=True)[:max_files]
    except Exception:
        files = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        for block in re.split(r"(?=MSH\|)", content):
            if not block.startswith("MSH|"):
                continue
            group = "Общая"
            refs = {}
            for ln in re.split(r"[\r\n]+", block):
                if "|01002^Ref Group^" in ln:
                    parts = ln.split("|")
                    if len(parts) > 5 and parts[5].strip():
                        group = parts[5].strip()
                m = _OBX_NM_RE.match(ln)
                if m:
                    key = code_to_key.get(m.group(1))
                    ref = m.group(5).strip()
                    if key and ref:
                        refs[key] = ref
            if refs:
                learned.setdefault(group, {}).update({k: v for k, v in refs.items()
                                                      if k not in learned.get(group, {})})
    return learned


def _ref_for(learned, group, key):
    return (learned.get(group, {}).get(key)
            or learned.get("Общая", {}).get(key)
            or DEFAULT_REFS.get(key, ""))


# ══════════════════════════════════════════════════════════════════════════
#  HL7 QURISH (analizator ORU^R01 bilan bir xil shakl)
# ══════════════════════════════════════════════════════════════════════════
def _ts(dt):
    return dt.strftime("%Y%m%d%H%M%S") if dt else ""


def build_hl7(row: dict, learned_refs=None, msg_id="1") -> str:
    learned_refs = learned_refs or {}
    dt = row["dt"] or datetime.now()
    name_field = f"{row.get('surname','')}^{row.get('name','')}"
    dob = row["dob"].strftime("%Y%m%d") + "000000" if row.get("dob") else ""
    pid = f"PID|1||{row.get('patient_id','')}^^^^MR||{name_field}||{dob}"
    if row.get("sex"):
        pid += f"||{row['sex']}"
    pv1 = f"PV1|1||{row.get('dept','')}"
    collect = _ts(row.get("collect_dt")) or _ts(dt)
    deliver = _ts(row.get("deliver_dt"))
    obr = (f"OBR|1||{row['sample']}|00001^Automated Count^99MRC||{collect}|{_ts(dt)}|||"
           f"{row.get('doctor','')}||||{deliver}||||||||||HM||||||||{row.get('operator','')}")
    blood_mode = "W" if (row.get("mode") or "WB").upper().startswith("W") else "P"

    segs = [
        f"MSH|^~\\&|||||{_ts(dt)}||ORU^R01|{msg_id}|P|2.3.1||||||UNICODE",
        pid, pv1, obr,
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        f"OBX|2|IS|08002^Blood Mode^99MRC||{blood_mode}||||||F",
        f"OBX|3|IS|01002^Ref Group^99MRC||{row.get('ref_group') or 'Общая'}||||||F",
    ]
    n = 4
    age_v, age_u = row.get("age") or ("", "")
    if age_v:
        segs.append(f"OBX|{n}|NM|30525-0^Age^LN||{age_v}|{age_u}|||||F")
        n += 1
    group = row.get("ref_group") or "Общая"
    for key, code, hname, system, unit in PARAMS:
        if key not in row["params"]:
            continue
        val, flag = row["params"][key]
        ref = _ref_for(learned_refs, group, key)
        segs.append(f"OBX|{n}|NM|{code}^{hname}^{system}||{val}|{unit}|{ref}|{flag}|||F")
        n += 1
    return "\r".join(segs) + "\r"


# ══════════════════════════════════════════════════════════════════════════
#  TXT YOZISH (sana bo'yicha to'g'ri oy papkasiga) + mavjudlik tekshiruvi
# ══════════════════════════════════════════════════════════════════════════
def _folder_for(d: date) -> str:
    return os.path.join(MINDRAY_DAT_BASE, d.strftime("%Y%m"))


def next_txt_path(d: date) -> str:
    folder = _folder_for(d)
    os.makedirs(folder, exist_ok=True)
    ymd = d.strftime("%Y%m%d")
    existing = sorted(glob.glob(os.path.join(folder, f"BC-20s_{ymd}_*.txt")))
    nums = []
    for p in existing:
        m = re.search(r"_(\d+)\.txt$", os.path.basename(p))
        if m:
            nums.append(int(m.group(1)))
    return os.path.join(folder, f"BC-20s_{ymd}_{(max(nums) + 1) if nums else 1:03d}.txt")


def existing_samples_for_date(d: date) -> dict:
    """{sample_id: [txt_path, ...]} — shu kunga yozilgan TXT fayllardagi OBR-3."""
    out = {}
    folder = _folder_for(d)
    for p in glob.glob(os.path.join(folder, f"BC-20s_{d.strftime('%Y%m%d')}_*.txt")):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        for ln in re.split(r"[\r\n]+", content):
            if ln.startswith("OBR|"):
                parts = ln.split("|")
                if len(parts) > 3 and parts[3].strip():
                    out.setdefault(parts[3].split("^")[0].strip(), []).append(p)
    return out


def write_txt(hl7: str, d: date) -> str:
    path = next_txt_path(d)
    with open(path, "w", encoding="utf-8", errors="replace", newline="") as f:
        f.write(hl7)
    return path


# ══════════════════════════════════════════════════════════════════════════
#  REJA (preview) va IMPORT
# ══════════════════════════════════════════════════════════════════════════
def plan_import(csv_paths, date_from=None, date_to=None, overwrite=False) -> list:
    """Nima import bo'lishini hisoblaydi (hali hech narsa yozmaydi).
    Har element: row + 'action' ('yangi' | 'mavjud' | 'fon' | 'sanasiz' | 'eski_takror' | 'sana_tashqarida')
    """
    rows = []
    for p in csv_paths:
        rows.extend(read_csv_rows(p))

    # Bir sample bir kunda bir necha marta o'tkazilgan bo'lsa — faqat OXIRGISI
    latest = {}
    for r in rows:
        if r["background"] or not r["dt"]:
            continue
        k = (r["sample"], r["dt"].date())
        if k not in latest or r["dt"] > latest[k]["dt"]:
            latest[k] = r

    exist_cache = {}
    for r in rows:
        if r["background"]:
            r["action"] = "fon"
            continue
        if not r["dt"]:
            r["action"] = "sanasiz"
            continue
        d = r["dt"].date()
        if (date_from and d < date_from) or (date_to and d > date_to):
            r["action"] = "sana_tashqarida"
            continue
        if latest.get((r["sample"], d)) is not r:
            r["action"] = "eski_takror"
            continue
        if d not in exist_cache:
            exist_cache[d] = existing_samples_for_date(d)
        if r["sample"] in exist_cache[d] and not overwrite:
            r["action"] = "mavjud"
            r["existing"] = exist_cache[d][r["sample"]]
            continue
        r["action"] = "yangi"
    rows.sort(key=lambda r: (r["dt"] or datetime.min), reverse=True)
    return rows


def run_import(planned, save_db=False, log=print) -> dict:
    """Rejadagi 'yangi' qatorlarni TXT ga yozadi. Natija: {yozildi, db, xato}.

    save_db=False (standart): BAZAGA YOZILMAYDI — faqat TXT. Gemotologiya oynasi
    shu fayllarni ko'rsatadi; laborant kerakli bemorni (ism bo'yicha ham) topib
    "Natijani qo'shish" bilan o'zi buyurtmaga biriktiradi. Eski (LIS gacha)
    natijalarda sample ID bizning buyurtmaga mos kelmaydi — avtomatik saqlash
    noto'g'ri buyurtmaga tushishi mumkin."""
    learned = learn_ref_ranges()
    stats = {"yozildi": 0, "db": 0, "db_topilmadi": 0, "xato": 0, "files": []}
    parse_oru = save_db_fn = None
    if save_db:
        try:
            from bc20s_listener import _parse_oru_r01 as parse_oru, _save_to_db as save_db_fn
        except Exception as e:
            log(f"[Import] DB saqlash moduli yuklanmadi: {e}")
            parse_oru = save_db_fn = None

    n = 1
    for r in planned:
        if r.get("action") != "yangi":
            continue
        try:
            hl7 = build_hl7(r, learned, msg_id=f"CSV{n}")
            n += 1
            path = write_txt(hl7, r["dt"].date())
            r["txt"] = path
            stats["yozildi"] += 1
            stats["files"].append(path)
            log(f"[Import] TXT: {os.path.basename(path)}  {r['sample']}  {r['full_name']}")
            if parse_oru and save_db_fn:
                try:
                    ok = save_db_fn(parse_oru(hl7))
                    r["db"] = bool(ok)
                    if ok:
                        stats["db"] += 1
                    else:
                        stats["db_topilmadi"] += 1
                except Exception as e:
                    r["db"] = False
                    log(f"[Import] DB xato {r['sample']}: {e}")
        except Exception as e:
            r["action"] = "xato"
            r["error"] = str(e)
            stats["xato"] += 1
            log(f"[Import] XATO {r.get('sample')}: {e}")
    return stats


ACTION_LABEL = {
    "yangi": "YANGI — import qilinadi",
    "mavjud": "mavjud (dasturda bor) — o'tkaziladi",
    "fon": "fon (Background) — o'tkaziladi",
    "sanasiz": "sana yo'q — o'tkaziladi",
    "eski_takror": "takror o'tkazish (eskisi) — o'tkaziladi",
    "sana_tashqarida": "sana oralig'idan tashqarida",
    "xato": "XATO",
}


if __name__ == "__main__":
    import sys
    paths = [a for a in sys.argv[1:] if not a.startswith("--")] or glob.glob(r"D:\*\Review_*\*.csv")
    if not paths:
        print("CSV topilmadi. Foydalanish: python bc20s_csv_import.py <fayl.csv> [...]")
        sys.exit(1)
    plan = plan_import(paths)
    for r in plan:
        print(f"{(r['dt'].strftime('%d.%m.%Y %H:%M') if r['dt'] else '—'):17} "
              f"{r['sample']:14} {r['full_name'][:24]:24} {ACTION_LABEL.get(r['action'], r['action'])}")
    if "--yes" in sys.argv:
        print(run_import(plan, save_db="--db" in sys.argv))
