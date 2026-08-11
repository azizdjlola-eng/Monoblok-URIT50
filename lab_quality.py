# -*- coding: utf-8 -*-
"""
LABORATORIYA SIFATI — DELTA-CHECK va KRITIK QIYMAT (PANIC VALUE).

Bu modul natija SAQLANAYOTGANDA ikkita qo'shimcha himoyani beradi:

1) DELTA-CHECK — "oldingi natija bilan solishtirish"
   Bemorning shu tahlil bo'yicha OLDINGI natijasini topib, bugungisi bilan
   solishtiradi. Keskin farq bo'lsa ogohlantiradi.
   Nima uchun muhim: lineynost chegarasi ushlay olmaydigan xatoni ushlaydi —
   masalan probirka almashib ketgan bo'lsa, natija chegara ICHIDA bo'ladi,
   lekin bu bemorga umuman to'g'ri kelmaydi. Jahon amaliyotida laboratoriya
   xatolarining katta qismi shunday "analitikagacha" xatolar.

2) KRITIK QIYMAT (panic value) — "hayotga xavf, shifokorga darhol xabar ber"
   Natija to'g'ri o'lchangan bo'lsa ham, bemor hayotiga xavf soladigan
   darajada bo'lsa — laborantni ogohlantiradi VA xabar berilgani
   (kimga / kim / qachon / qanday usulda) bazaga yozib qo'yiladi.
   Bu akkreditatsiya talabi va shifokorlar oldida laboratoriya obro'sining
   eng kuchli dalili.

╔══════════════════════════════════════════════════════════════════════════════╗
║  SOZLAMALARNI QAYERDA O'ZGARTIRISH KERAK                                     ║
║                                                                              ║
║  Fayl: `lab_quality.json` (shu skript/exe yonida, birinchi ishga tushganda   ║
║  avtomatik yaratiladi). Kodga tegmasdan tahrirlash mumkin.                   ║
║                                                                              ║
║  • "delta"  → oldingi natija bilan solishtirish chegaralari                  ║
║      max_days  — oldingi natija shundan eski bo'lsa solishtirilmaydi         ║
║      analytes  — kalit = `tahlillar.id` yoki "{tahlil_id}.{komponent}"       ║
║          pct      — necha % o'zgarish ogohlantirsin                          ║
║          abs_min  — shundan kichik MUTLAQ farqda ogohlantirmasin             ║
║                     (past qiymatlarda yolg'on signalni kamaytiradi)          ║
║                                                                              ║
║  • "panic"  → kritik (hayotga xavfli) qiymatlar                              ║
║      analytes  — kalit = `tahlillar.id` yoki "{tahlil_id}.{komponent}"       ║
║          low / high — shundan past / baland bo'lsa KRITIK                    ║
║                                                                              ║
║  ⚠ MUHIM: pastdagi kritik qiymatlar KENG TARQALGAN adabiyotdan olingan       ║
║  BOSHLANG'ICH taklif. Har bir laboratoriya o'z kritik qiymat ro'yxatini      ║
║  o'zi tasdiqlashi shart (laboratoriya mudiri / klinisist bilan kelishilgan   ║
║  holda). Ishlatishdan oldin ko'rib chiqing va tuzating.                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Uch xil signalni chalkashtirmaslik kerak:
  • critical_alert.py    — analizatordan kelgan natijada reagent/namuna muammosi
  • result_validator.py  — natija NOTO'G'RI YOZILGAN bo'lishi mumkin (format/lineynost)
  • lab_quality.py       — natija to'g'ri, lekin (a) oldingidan keskin farq qiladi
                           yoki (b) hayotga xavfli darajada
"""

import os
import re
import sys
import json
from datetime import datetime

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(BASE_DIR, "lab_quality.json")


# ══════════════════════════════════════════════════════════════════════════
#  STANDART SOZLAMALAR
# ══════════════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "version": 1,

    # ── 1) DELTA-CHECK ────────────────────────────────────────────────────
    "delta": {
        "enabled": True,
        # Oldingi natija shundan eski bo'lsa — solishtirmaymiz (kun).
        "max_days": 365,
        # Oldingi natija shundan yangi bo'lsa ham solishtiramiz (0 = cheklov yo'q).
        "min_hours": 0,
        # Kalit = tahlillar.id  yoki  "{tahlil_id}.{komponent_kaliti}"
        #   pct     — necha foiz o'zgarish ogohlantirsin
        #   abs_min — shundan kichik mutlaq farqda ogohlantirmaslik
        "analytes": {
            # --- Bioximiya ---
            "41":  {"name": "Kreatinin",        "unit": "mkmol/l", "pct": 50,  "abs_min": 30},
            "42":  {"name": "Mochevina",        "unit": "mmol/l",  "pct": 60,  "abs_min": 3},
            "48":  {"name": "Kaliy K",          "unit": "mmol/l",  "pct": 20,  "abs_min": 0.8},
            "52":  {"name": "Natriy Na",        "unit": "mmol/l",  "pct": 8,   "abs_min": 8},
            "47":  {"name": "Kalsiy Ca",        "unit": "mmol/l",  "pct": 15,  "abs_min": 0.3},
            "37":  {"name": "Glyukoza",         "unit": "mmol/l",  "pct": 60,  "abs_min": 2.5},
            "36":  {"name": "Umumiy oqsil",     "unit": "g/l",     "pct": 20,  "abs_min": 10},
            "35":  {"name": "Albumin",          "unit": "g/l",     "pct": 25,  "abs_min": 7},
            "39":  {"name": "ALT",              "unit": "E/l",     "pct": 100, "abs_min": 40},
            "40":  {"name": "AST",              "unit": "E/l",     "pct": 100, "abs_min": 40},
            "43":  {"name": "Umumiy xolesterin","unit": "mmol/l",  "pct": 35,  "abs_min": 1.5},
            "50":  {"name": "Siydik kislota",   "unit": "mkmol/l", "pct": 40,  "abs_min": 80},
            "106": {"name": "TTG (TSH)",        "unit": "mME/l",   "pct": 100, "abs_min": 1.0},
            "105": {"name": "Ferritin",         "unit": "ng/ml",   "pct": 80,  "abs_min": 30},

            # --- Gemotologiya (CBC) ---
            "27.HGB": {"name": "Gemoglobin (HGB)",   "unit": "g/l",    "pct": 15, "abs_min": 20},
            "27.RBC": {"name": "Eritrotsitlar (RBC)","unit": "10^12/l","pct": 20, "abs_min": 0.8},
            "27.PLT": {"name": "Trombotsitlar (PLT)","unit": "10^9/l", "pct": 50, "abs_min": 80},
            "27.WBC": {"name": "Leykotsitlar (WBC)", "unit": "10^9/l", "pct": 70, "abs_min": 4},

            # --- Panellar ichidagi komponentlar ---
            "127.kreatinin": {"name": "Kreatinin (panel)", "unit": "mkmol/l", "pct": 50, "abs_min": 30},
            "127.mochevina": {"name": "Mochevina (panel)", "unit": "mmol/l",  "pct": 60, "abs_min": 3},
            "126.tc":        {"name": "Xolesterin (panel)","unit": "mmol/l",  "pct": 35, "abs_min": 1.5},
        },
    },

    # ── 2) KRITIK QIYMAT (PANIC VALUE) ────────────────────────────────────
    # ⚠ Laboratoriya mudiri tasdiqlashi SHART. Bu boshlang'ich taklif.
    "panic": {
        "enabled": True,
        # Xabar berish jurnali (kritik_xabar_log jadvali) yuritilsinmi
        "log_enabled": True,
        "analytes": {
            # --- Bioximiya ---
            "37":  {"name": "Glyukoza",     "unit": "mmol/l",  "low": 2.5,  "high": 25},
            "48":  {"name": "Kaliy K",      "unit": "mmol/l",  "low": 2.8,  "high": 6.2},
            "52":  {"name": "Natriy Na",    "unit": "mmol/l",  "low": 120,  "high": 160},
            "47":  {"name": "Kalsiy Ca",    "unit": "mmol/l",  "low": 1.65, "high": 3.5},
            "51":  {"name": "Magniy Mg",    "unit": "mmol/l",  "low": 0.4,  "high": 2.0},
            "41":  {"name": "Kreatinin",    "unit": "mkmol/l", "low": None, "high": 600},
            "42":  {"name": "Mochevina",    "unit": "mmol/l",  "low": None, "high": 30},
            "39":  {"name": "ALT",          "unit": "E/l",     "low": None, "high": 1000},
            "40":  {"name": "AST",          "unit": "E/l",     "low": None, "high": 1000},
            "66":  {"name": "Troponin T",   "unit": "ng/ml",   "low": None, "high": 0.1},

            # --- Gemostaz ---
            "75":  {"name": "Fibrinogen",   "unit": "g/l",     "low": 1.0,  "high": None},
            "76":  {"name": "ACHTV",        "unit": "sek",     "low": None, "high": 100},

            # --- Gemotologiya (CBC) ---
            "27.HGB": {"name": "Gemoglobin (HGB)",    "unit": "g/l",    "low": 60,  "high": 200},
            "27.PLT": {"name": "Trombotsitlar (PLT)", "unit": "10^9/l", "low": 30,  "high": 1000},
            "27.WBC": {"name": "Leykotsitlar (WBC)",  "unit": "10^9/l", "low": 1.5, "high": 50},

            # --- Ko'p komponentli / panellar ---
            "55.umumiy":     {"name": "Umumiy bilirubin",   "unit": "mkmol/l", "low": None, "high": 250},
            "73.pt_mno":     {"name": "MNO / INR",          "unit": "INR",     "low": None, "high": 5},
            "73.fibrinogen": {"name": "Fibrinogen (koag.)", "unit": "g/l",     "low": 1.0,  "high": None},
            "73.achtv":      {"name": "ACHTV (koag.)",      "unit": "sek",     "low": None, "high": 100},
            "74.pt_mno":     {"name": "MNO / INR",          "unit": "INR",     "low": None, "high": 5},
            "127.kreatinin": {"name": "Kreatinin (panel)",  "unit": "mkmol/l", "low": None, "high": 600},
            "127.mochevina": {"name": "Mochevina (panel)",  "unit": "mmol/l",  "low": None, "high": 30},
        },
    },
}

_CFG_CACHE = [None]


def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(force=False):
    """lab_quality.json ni o'qish (bo'lmasa standartni yozib qo'yadi)."""
    if _CFG_CACHE[0] is not None and not force:
        return _CFG_CACHE[0]
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _deep_merge(cfg, json.load(f))
        else:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[OGOHLANTIRISH] lab_quality.json yuklashda xato: {e}")
    _CFG_CACHE[0] = cfg
    return cfg


# ══════════════════════════════════════════════════════════════════════════
#  Natijadan sonli qiymatlarni ajratib olish
# ══════════════════════════════════════════════════════════════════════════
# JSON natija ichidagi XIZMAT kalitlari — natija emas, meta-ma'lumot.
# Analizatordan kelgan natija shunday saqlanadi:
#   {"result": "19.85", "unit": "mmol/l", "flag": "H", "lis_code": ..., "sid": ...}
# (result_validator._META_JSON_KEYS bilan bir xil bo'lishi kerak.)
_SKIP_JSON_KEYS = {
    "type", "source", "sid", "sno", "unit", "flag", "lis_code", "analyzer_ref",
    "patient_age", "patient_gender", "abnormal_params", "all_analytes", "vazn_kg",
}


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    for ch in ("↑", "↓", "<", ">", " ", "\t"):
        s = s.replace(ch, "")
    s = s.replace(",", ".")
    if not re.fullmatch(r"-?\d*\.?\d+", s):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _norm_name(name):
    s = str(name or "").lower().strip()
    for ch in ("'", "‘", "’", "`", "ʻ"):
        s = s.replace(ch, "")
    return re.sub(r"\s+", " ", s)


def iter_numeric_values(raw):
    """
    Saqlangan natijadan (matn yoki JSON) sonli qiymatlarni ajratadi.
    Yields: (komponent_kaliti yoki None, float qiymat)
    """
    if raw is None:
        return
    s = raw if isinstance(raw, str) else str(raw)
    s = s.strip()
    if not s:
        return

    if s.startswith("{"):
        try:
            data = json.loads(s)
        except Exception:
            data = None
        if isinstance(data, dict):
            # Siydik natijasi — sonli solishtirishga yaramaydi
            if str(data.get("type", "")).lower() == "urine":
                return
            comps = {k: v for k, v in data.items() if k not in _SKIP_JSON_KEYS}
            others = [k for k in comps if k != "result"]
            if not others:
                # Analizatordan kelgan oddiy natija — skalyar
                v = _to_float(comps.get("result"))
                if v is not None:
                    yield None, v
                return
            comps.pop("result", None)   # haqiqiy komponentlar bor — "result" ortiqcha
            for k, v in comps.items():
                fv = _to_float(v)
                if fv is not None:
                    yield k, fv
            return

    v = _to_float(s)
    if v is not None:
        yield None, v


def _spec_for(section, tahlil_id, comp_key):
    """Sozlamadan spec topish: '{id}.{key}' yoki '{id}'."""
    if tahlil_id is None:
        return None, None
    key = f"{tahlil_id}.{comp_key}" if comp_key else str(tahlil_id)
    spec = section.get(key)
    if spec:
        return spec, key
    return None, None


# ══════════════════════════════════════════════════════════════════════════
#  DB DAN QO'LDA KIRITILGAN "Ogohlantirish" CHEGARASI (Tahlil Qo'shish oynasi,
#  2026-08-11 qo'shildi). Faqat BIR KOMPONENTLI tahlillarga tegishli (nomdan
#  qidiriladi) — panel/ko'p-komponentli sub-testlar bu yerga aralashmaydi.
#  STATIK "panic.analytes" konfiguratsiyasidan USTUVOR.
# ══════════════════════════════════════════════════════════════════════════
def apply_db_overrides(cfg, rows):
    """rows: [(tahlil_nomi, ogohlantirish_past, ogohlantirish_baland, birlik), ...]"""
    db_map = {}
    for row in rows or []:
        nomi = row[0] if len(row) > 0 else None
        lo = row[1] if len(row) > 1 else None
        hi = row[2] if len(row) > 2 else None
        unit = row[3] if len(row) > 3 else ""
        if lo is None and hi is None:
            continue
        nm = _norm_name(nomi)
        if not nm:
            continue
        db_map[nm] = {
            "name": nomi, "unit": unit or "",
            "low": float(lo) if lo is not None else None,
            "high": float(hi) if hi is not None else None,
        }
    cfg.setdefault("panic", {})["_db_by_name"] = db_map
    return cfg


# ══════════════════════════════════════════════════════════════════════════
#  1) DELTA-CHECK
# ══════════════════════════════════════════════════════════════════════════
def fetch_previous_results(conn, bemor_id, exclude_order_id, max_days=365):
    """
    Bemorning OLDINGI (shu buyurtmadan oldingi) natijalarini oladi.

    Qaytaradi: {tahlil_nomi: (qiymat_matn, sana)} — har tahlil uchun eng oxirgisi.
    Xato bo'lsa bo'sh lug'at (delta-check jim o'tkaziladi).
    """
    out = {}
    if not conn or not bemor_id:
        return out
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ri.tahlil_nomi, ri.qiymat, o.sana_vaqt
            FROM result_items ri
            JOIN results r ON ri.result_id = r.id
            JOIN orders  o ON r.order_id  = o.id
            WHERE o.bemor_id = %s
              AND o.id <> %s
              AND o.deleted_at IS NULL
              AND o.sana_vaqt IS NOT NULL
              AND o.sana_vaqt >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND ri.qiymat IS NOT NULL AND ri.qiymat <> ''
            ORDER BY o.sana_vaqt DESC
            """,
            (bemor_id, exclude_order_id or 0, int(max_days)),
        )
        for nomi, qiymat, sana in cur.fetchall():
            if nomi and nomi not in out:      # ORDER BY DESC — birinchisi eng yangisi
                out[nomi] = (qiymat, sana)
    except Exception as e:
        print(f"[OGOHLANTIRISH] Delta-check: oldingi natijalarni olishda xato: {e}")
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
    return out


def check_delta(rows, previous, cfg=None):
    """
    rows:     [(tahlil_id, tahlil_nomi, raw_value), ...] — bugungi natijalar
    previous: fetch_previous_results() qaytargan lug'at

    Qaytaradi: [(nom, qiymat_matni, sabab), ...] — result_validator bilan bir xil format,
    shuning uchun bitta ogohlantirish oynasida ko'rsatsa bo'ladi.
    """
    cfg = cfg or load_config()
    d = cfg.get("delta", {})
    if not d.get("enabled", True) or not previous:
        return []

    analytes = d.get("analytes", {})
    issues = []

    for tahlil_id, nomi, raw in rows:
        prev = previous.get(nomi)
        if not prev:
            continue
        prev_raw, prev_sana = prev
        prev_map = dict(iter_numeric_values(prev_raw))
        if not prev_map:
            continue

        for comp_key, val in iter_numeric_values(raw):
            spec, _ = _spec_for(analytes, tahlil_id, comp_key)
            if not spec:
                continue
            if comp_key not in prev_map:
                continue
            old = prev_map[comp_key]
            if old == 0:
                continue

            diff = val - old
            adiff = abs(diff)
            pct = abs(diff / old) * 100.0

            lim_pct = spec.get("pct")
            abs_min = spec.get("abs_min") or 0
            if lim_pct is None or pct < lim_pct or adiff < abs_min:
                continue

            unit = spec.get("unit") or ""
            u = f" {unit}" if unit else ""
            when = ""
            try:
                when = f" ({prev_sana:%d.%m.%Y})" if prev_sana else ""
            except Exception:
                when = ""
            arrow = "oshgan" if diff > 0 else "kamaygan"
            label = f"{nomi} — {spec.get('name', comp_key or '')}" if comp_key else nomi

            issues.append((
                label,
                f"{val:g}{u}",
                f"oldingi natijadan keskin farq qiladi: {old:g}{u}{when} -> "
                f"{val:g}{u}  ({pct:.0f}% {arrow}). Namuna to'g'ri bemornikimi?"
            ))

    return issues


# ══════════════════════════════════════════════════════════════════════════
#  2) KRITIK QIYMAT (PANIC VALUE)
# ══════════════════════════════════════════════════════════════════════════
def check_panic(rows, cfg=None):
    """
    rows: [(tahlil_id, tahlil_nomi, raw_value), ...]
    Qaytaradi: [{'nom','qiymat','chegara','tomon','unit'}, ...]
    """
    cfg = cfg or load_config()
    p = cfg.get("panic", {})
    if not p.get("enabled", True):
        return []
    analytes = p.get("analytes", {})
    db_by_name = p.get("_db_by_name") or {}
    found = []

    for tahlil_id, nomi, raw in rows:
        for comp_key, val in iter_numeric_values(raw):
            spec, _ = _spec_for(analytes, tahlil_id, comp_key)
            if not spec and comp_key is None:
                # DB'da UI orqali kiritilgan Ogohlantirish (faqat bir komponentli)
                spec = db_by_name.get(_norm_name(nomi))
            if not spec:
                continue
            lo, hi = spec.get("low"), spec.get("high")
            unit = spec.get("unit") or ""
            label = f"{nomi} — {spec.get('name', comp_key)}" if comp_key else nomi

            if lo is not None and val < lo:
                found.append({"nom": label, "qiymat": val, "chegara": lo,
                              "tomon": "past", "unit": unit})
            elif hi is not None and val > hi:
                found.append({"nom": label, "qiymat": val, "chegara": hi,
                              "tomon": "baland", "unit": unit})
    return found


def ensure_log_table(conn):
    """kritik_xabar_log jadvali yo'q bo'lsa yaratadi. True = tayyor."""
    if not conn:
        return False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kritik_xabar_log (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                order_id        INT NULL,
                bemor_id        INT NULL,
                bemor_fish      VARCHAR(200) NULL,
                tahlil_nomi     VARCHAR(255) NULL,
                qiymat          VARCHAR(64)  NULL,
                chegara         VARCHAR(64)  NULL,
                tomon           VARCHAR(16)  NULL,
                xabar_berildi   TINYINT(1)   NOT NULL DEFAULT 0,
                kimga           VARCHAR(200) NULL,
                kim_xabar_berdi VARCHAR(200) NULL,
                usul            VARCHAR(50)  NULL,
                izoh            VARCHAR(500) NULL,
                created_at      DATETIME     NULL,
                INDEX idx_kxl_order (order_id),
                INDEX idx_kxl_bemor (bemor_id),
                INDEX idx_kxl_sana  (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        return True
    except Exception as e:
        print(f"[OGOHLANTIRISH] kritik_xabar_log jadvalini yaratishda xato: {e}")
        return False
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass


def log_panic(conn, order_id, bemor_id, bemor_fish, panics, notified,
              kimga="", kim="", usul="", izoh=""):
    """Kritik qiymatlar va xabar berish holatini jurnalga yozadi."""
    if not conn or not panics:
        return False
    if not ensure_log_table(conn):
        return False
    cur = None
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in panics:
            cur.execute("""
                INSERT INTO kritik_xabar_log
                    (order_id, bemor_id, bemor_fish, tahlil_nomi, qiymat, chegara,
                     tomon, xabar_berildi, kimga, kim_xabar_berdi, usul, izoh, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                order_id, bemor_id, (bemor_fish or "")[:200],
                (p.get("nom") or "")[:255],
                f"{p.get('qiymat')}"[:64],
                f"{p.get('chegara')}"[:64],
                (p.get("tomon") or "")[:16],
                1 if notified else 0,
                (kimga or "")[:200], (kim or "")[:200],
                (usul or "")[:50], (izoh or "")[:500], now,
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[OGOHLANTIRISH] kritik_xabar_log ga yozishda xato: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _play_sound():
    try:
        import critical_alert
        critical_alert.play_alert_sound()
        return
    except Exception:
        pass
    try:
        import winsound
        winsound.MessageBeep(-1)
    except Exception:
        pass


def show_panic_dialog(parent, bemor_fish, panics, default_vrach=""):
    """
    Kritik qiymat oynasi — laborant shifokorga xabar berganini qayd etadi.

    Qaytaradi: dict yoki None
        {'notified': bool, 'kimga': str, 'kim': str, 'usul': str, 'izoh': str}
    """
    if not panics:
        return None

    _play_sound()

    import tkinter as tk
    from tkinter import ttk

    out = {"notified": False, "kimga": "", "kim": "", "usul": "", "izoh": ""}

    try:
        dlg = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    except Exception:
        print("[KRITIK QIYMAT]", panics)
        return None

    dlg.title("KRITIK QIYMAT — SHIFOKORGA DARHOL XABAR BERING")
    dlg.configure(bg="#FFF8E1")
    try:
        dlg.transient(parent)
    except Exception:
        pass
    dlg.grab_set()

    tk.Label(
        dlg, text="⚠  KRITIK QIYMAT ANIQLANDI",
        font=("Arial", 15, "bold"), bg="#B71C1C", fg="white",
        anchor="w", padx=14, pady=11
    ).pack(fill=tk.X)

    tk.Label(
        dlg,
        text=f"Bemor: {bemor_fish}\n"
             "Bu natija bemor hayotiga xavf soladigan darajada.\n"
             "Davolovchi shifokorga DARHOL xabar bering va quyida qayd eting.",
        font=("Arial", 10), bg="#FFF8E1", fg="#7F1D1D",
        anchor="w", justify=tk.LEFT, padx=14, pady=8
    ).pack(fill=tk.X)

    # Kritik qiymatlar ro'yxati
    lf = tk.LabelFrame(dlg, text=" Kritik natijalar ", bg="#FFF8E1",
                       font=("Arial", 10, "bold"), fg="#B71C1C", padx=8, pady=6)
    lf.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 8))

    for p in panics:
        u = f" {p['unit']}" if p.get("unit") else ""
        row = tk.Frame(lf, bg="#FFEBEE")
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=f"{p['nom']}", font=("Arial", 10, "bold"),
                 bg="#FFEBEE", fg="#B00020", anchor="w", width=40).pack(side=tk.LEFT, padx=6, pady=4)
        tk.Label(row, text=f"{p['qiymat']:g}{u}", font=("Consolas", 13, "bold"),
                 bg="#FFEBEE", fg="#0B3D91").pack(side=tk.LEFT, padx=8)
        tk.Label(row, text=f"({p['tomon']} — chegara {p['chegara']:g}{u})",
                 font=("Arial", 9), bg="#FFEBEE", fg="#555555").pack(side=tk.LEFT, padx=6)

    # Xabar berish qaydi
    nf = tk.LabelFrame(dlg, text=" Xabar berish qaydi (jurnalga yoziladi) ",
                       bg="#FFF8E1", font=("Arial", 10, "bold"), padx=10, pady=8)
    nf.pack(fill=tk.X, padx=12, pady=(0, 8))
    nf.columnconfigure(1, weight=1)

    v_kimga = tk.StringVar(value=default_vrach or "")
    v_kim = tk.StringVar(value=os.environ.get("USERNAME", ""))
    v_usul = tk.StringVar(value="Telefon")
    v_izoh = tk.StringVar()

    def field(r, text, var, widget="entry", values=None):
        tk.Label(nf, text=text, bg="#FFF8E1", font=("Arial", 10),
                 anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
        if widget == "combo":
            w = ttk.Combobox(nf, textvariable=var, values=values, state="readonly",
                             font=("Arial", 10), width=18)
            w.grid(row=r, column=1, sticky="w", pady=3)
        else:
            w = ttk.Entry(nf, textvariable=var, font=("Arial", 10))
            w.grid(row=r, column=1, sticky="ew", pady=3)
        return w

    e_kimga = field(0, "Kimga xabar berildi (shifokor):", v_kimga)
    field(1, "Kim xabar berdi (laborant):", v_kim)
    field(2, "Usul:", v_usul, "combo", ["Telefon", "Shaxsan", "SMS", "Boshqa"])
    field(3, "Izoh:", v_izoh)

    err = tk.Label(dlg, text="", bg="#FFF8E1", fg="#B00020", font=("Arial", 9, "bold"))
    err.pack(fill=tk.X, padx=14)

    btns = tk.Frame(dlg, bg="#FFF8E1")
    btns.pack(fill=tk.X, padx=12, pady=(4, 12))

    def do_notified():
        if not v_kimga.get().strip():
            err.config(text="«Kimga xabar berildi» maydonini to'ldiring.")
            e_kimga.focus_set()
            return
        out.update(notified=True, kimga=v_kimga.get().strip(), kim=v_kim.get().strip(),
                   usul=v_usul.get().strip(), izoh=v_izoh.get().strip())
        dlg.destroy()

    def do_later():
        out.update(notified=False, kimga="", kim=v_kim.get().strip(),
                   usul="", izoh=v_izoh.get().strip())
        dlg.destroy()

    tk.Button(btns, text="✔  Xabar berildi — qayd etilsin", command=do_notified,
              font=("Arial", 11, "bold"), bg="#2E7D32", fg="white",
              padx=16, pady=8, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT)
    tk.Button(btns, text="Keyinroq xabar beraman", command=do_later,
              font=("Arial", 10), bg="#E0E0E0", fg="#333333",
              padx=14, pady=8, cursor="hand2", relief=tk.FLAT).pack(side=tk.RIGHT)

    dlg.bind("<Escape>", lambda e: do_later())

    dlg.update_idletasks()
    w = max(640, min(860, dlg.winfo_reqwidth()))
    h = max(380, min(700, dlg.winfo_reqheight()))
    try:
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        dlg.geometry(f"{w}x{h}+{max(0, px)}+{max(0, py)}")
    except Exception:
        dlg.geometry(f"{w}x{h}")

    e_kimga.focus_set()
    dlg.wait_window()
    return out
