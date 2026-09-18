# -*- coding: utf-8 -*-
"""
Gematologiya (BC-20S) - RAW fayllarni ko'rsatish oynasi
Database bilan ishlamaydi, faqat diskdagi fayllarni o'qiydi
HL7 ORU^R01 formatini parse qiladi
1 OBR = 1 bemor = 1 qator
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import glob
import re
import json

try:
    import critical_alert
except Exception:
    critical_alert = None

# ══════════════════════════════════════════════════════════════════
#  MULTI-REFERENCE NORMALS (yosh va jinsga qarab)
#  Har parametr uchun: [(age_min, age_max, gender, low, high)]
#  age: yillarda; gender: 'M'=erkak, 'F'=ayol, 'B'=ikkalasi
#  age_min=0, age_max=9999 → cheklov yo'q
# ══════════════════════════════════════════════════════════════════
# age_min: shu yoshdan (inclusive), age_max: shu yoshgacha (inclusive)
MULTI_REF_NORMALS = {
    # ── WBC 10^9/L ──────────────────────────────────────────────
    "WBC": [
        (0,   0,    "B",  9.0,  30.0),   # Yangi tug'ilgan (0 yosh)
        (1,   1,    "B",  6.0,  17.0),   # 1 yosh
        (2,   5,    "B",  5.0,  15.0),   # 2-5 yosh
        (6,   11,   "B",  4.5,  13.5),   # 6-11 yosh
        (12,  17,   "B",  4.5,  11.0),   # 12-17 yosh
        (18,  9999, "B",  4.0,  10.0),   # Kattalar
    ],
    # ── RBC 10^12/L ─────────────────────────────────────────────
    "RBC": [
        (0,   0,    "B",  3.9,  5.9),
        (1,   1,    "B",  3.6,  5.2),
        (2,   11,   "B",  3.8,  5.0),
        (12,  17,   "M",  4.1,  5.5),
        (12,  17,   "F",  3.8,  5.1),
        (18,  9999, "M",  4.3,  5.7),
        (18,  9999, "F",  3.8,  5.1),
    ],
    # ── HGB g/L ─────────────────────────────────────────────────
    "HGB": [
        (0,   0,    "B",  140,  220),    # Yangi tug'ilgan
        (1,   1,    "B",  110,  135),    # 1-12 oylik → 1 yosh sifatida
        (2,   5,    "B",  110,  140),
        (6,   11,   "B",  115,  145),
        (12,  17,   "M",  120,  160),
        (12,  17,   "F",  115,  150),
        (18,  9999, "M",  130,  160),
        (18,  9999, "F",  115,  145),
    ],
    # ── HCT % ───────────────────────────────────────────────────
    "HCT": [
        (0,   0,    "B",  42,   68),
        (1,   1,    "B",  33,   42),
        (2,   11,   "B",  33,   43),
        (12,  17,   "M",  36,   50),
        (12,  17,   "F",  34,   46),
        (18,  9999, "M",  40,   54),
        (18,  9999, "F",  36,   48),
    ],
    # ── MCV fL ──────────────────────────────────────────────────
    "MCV": [
        (0,   0,    "B",  96,   108),
        (1,   1,    "B",  70,   88),
        (2,   5,    "B",  73,   89),
        (6,   11,   "B",  75,   90),
        (12,  9999, "B",  80,   100),
    ],
    # ── MCH pg ──────────────────────────────────────────────────
    "MCH": [
        (0,   0,    "B",  31,   37),
        (1,   1,    "B",  23,   31),
        (2,   9999, "B",  27,   34),
    ],
    # ── MCHC g/L ────────────────────────────────────────────────
    "MCHC": [
        (0,   0,    "B",  310,  370),
        (1,   9999, "B",  320,  360),
    ],
    # ── PLT 10^9/L ──────────────────────────────────────────────
    "PLT": [
        (0,   0,    "B",  100,  400),
        (1,   9999, "B",  100,  400),
    ],
    # ── LYM# 10^9/L ─────────────────────────────────────────────
    "LYM#": [
        (0,   0,    "B",  2.0,  11.0),
        (1,   1,    "B",  2.0,  9.0),
        (2,   5,    "B",  1.5,  7.0),
        (6,   11,   "B",  1.5,  6.5),
        (12,  9999, "B",  0.8,  4.0),
    ],
    # ── LYM% % ──────────────────────────────────────────────────
    "LYM%": [
        (0,   1,    "B",  25,   60),
        (2,   5,    "B",  30,   60),
        (6,   11,   "B",  25,   50),
        (12,  9999, "B",  20,   40),
    ],
    # ── GRAN# 10^9/L ─────────────────────────────────────────────
    "GRAN#": [
        (0,   0,    "B",  6.0,  26.0),
        (1,   1,    "B",  1.0,  8.5),
        (2,   5,    "B",  1.5,  8.5),
        (6,   9999, "B",  2.0,  7.0),
    ],
    # ── GRAN% % ──────────────────────────────────────────────────
    "GRAN%": [
        (0,   0,    "B",  40,   80),
        (1,   1,    "B",  15,   60),
        (2,   5,    "B",  25,   65),
        (6,   9999, "B",  50,   70),
    ],
    # ── MID# 10^9/L ──────────────────────────────────────────────
    "MID#": [
        (0,   9999, "B",  0.1,  1.5),
    ],
    # ── MID% % ───────────────────────────────────────────────────
    "MID%": [
        (0,   9999, "B",  3.0,  15.0),
    ],
    # ── RDW-CV % ─────────────────────────────────────────────────
    "RDW-CV": [
        (0,   9999, "B",  11.0, 16.0),
    ],
    # ── RDW-SD fL ────────────────────────────────────────────────
    "RDW-SD": [
        (0,   9999, "B",  35.0, 56.0),
    ],
    # ── MPV fL ───────────────────────────────────────────────────
    "MPV": [
        (0,   9999, "B",  6.5,  12.0),
    ],
    # ── PDW % ────────────────────────────────────────────────────
    "PDW": [
        (0,   9999, "B",  15.0, 17.0),
    ],
    # ── PCT % ────────────────────────────────────────────────────
    "PCT": [
        (0,   9999, "B",  0.108, 0.282),
    ],
    # ── NLR (nisbat) ─────────────────────────────────────────────
    "NLR": [
        (0,   9999, "B",  1.0,  3.0),
    ],
    # ── PLR (nisbat) ─────────────────────────────────────────────
    "PLR": [
        (0,   9999, "B",  50,   150),
    ],
    # ── 5-DIFF (Genrui KT-6610/8000, Edan H60, Mindray BC-5150 ...) ──
    # NEU = neytrofillar (3-diff GRAN bilan bir xil diapazon)
    "NEU#": [
        (0,   0,    "B",  6.0,  26.0),
        (1,   1,    "B",  1.0,  8.5),
        (2,   5,    "B",  1.5,  8.5),
        (6,   9999, "B",  2.0,  7.0),
    ],
    "NEU%": [
        (0,   0,    "B",  40,   80),
        (1,   1,    "B",  15,   60),
        (2,   5,    "B",  25,   65),
        (6,   9999, "B",  50,   70),
    ],
    "MON#": [
        (0,   9999, "B",  0.1,  1.0),
    ],
    "MON%": [
        (0,   9999, "B",  3.0,  10.0),
    ],
    "EOS#": [
        (0,   9999, "B",  0.02, 0.5),
    ],
    "EOS%": [
        (0,   9999, "B",  0.5,  5.0),
    ],
    "BAS#": [
        (0,   9999, "B",  0.0,  0.1),
    ],
    "BAS%": [
        (0,   9999, "B",  0.0,  1.0),
    ],
    "PDW-SD": [
        (0,   9999, "B",  9.0,  17.0),
    ],
    "P-LCR": [
        (0,   9999, "B",  13.0, 43.0),
    ],
    "P-LCC": [
        (0,   9999, "B",  30,   90),
    ],
}


def _hl7_age_to_years(value_str, unit_str) -> str:
    """HL7 OBX Age (30525-0) qiymatini BUTUN YIL songa aylantiradi.

    BC-20S 1 yoshdan kichik bemorlar uchun yoshni "mo" (oy) yoki "d" (kun)
    birligida yuboradi (masalan "7|mo"). MULTI_REF_NORMALS jadvali esa
    doim BUTUN YIL kutadi — birlik hisobga olinmasa, masalan 7 oylik chaqaloq
    xato ravishda "7 yoshli bola" normasi bilan solishtiriladi. Shu funksiya
    buni oldini oladi (7 oy → 0 yosh, 45 kun → 0 yosh, 18 oy → 1 yosh).
    """
    try:
        v = float(str(value_str).strip())
    except (ValueError, TypeError):
        return str(value_str).strip()
    u = (unit_str or "yr").strip().lower()
    if u in ("d", "day", "days", "кун", "kun"):
        return str(int(v // 365))
    if u in ("mo", "mon", "month", "months", "oy"):
        return str(int(v // 12))
    if u in ("wk", "week", "weeks", "hafta"):
        return str(int(v // 52))
    return str(int(v))


def get_multi_ref(param: str, age_str, gender: str) -> tuple:
    """
    Yosh va jinsga qarab norma oralig'ini qaytaradi.
    Qaytaradi: (low, high, ref_str) yoki (None, None, '') agar topilmasa.
    """
    norms = MULTI_REF_NORMALS.get(param)
    if not norms:
        return None, None, ""

    try:
        age = float(str(age_str).strip()) if age_str else -1
    except (ValueError, TypeError):
        age = -1

    g = (gender or "").strip().upper()
    g_code = ("M" if g in ("ERKAK", "M", "МУЖ") else
              "F" if g in ("AYOL", "F", "ЖЕН") else "")

    # Mos qatorni topish (avval jinsga mos, keyin ikkalasiga mos)
    best = None
    for (amin, amax, ng, lo, hi) in norms:
        if age >= 0 and not (amin <= age <= amax):
            continue
        if ng == "B" or ng == g_code or not g_code:
            if best is None or ng == g_code:
                best = (lo, hi)
            if ng == g_code:
                break

    if best:
        lo, hi = best
        # Formatlash
        lo_s = str(int(lo)) if lo == int(lo) else str(round(lo, 3))
        hi_s = str(int(hi)) if hi == int(hi) else str(round(hi, 3))
        return lo, hi, f"{lo_s}-{hi_s}"
    return None, None, ""

# Database ulanish
try:
    import mysql.connector
    from monoblok_db_config import DB_CONFIG
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

def db_conn():
    """MySQL ulanish"""
    if not DB_AVAILABLE:
        return None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"[XATO] DB ulanish xatosi: {e}")
        return None

# BC-20S natijalar papkasi — oyma-oy tartibda: G:\DASTUR\URIT 50\BC-20s\YYYYMM\
BC20S_DAT_BASE = r"G:\DASTUR\URIT 50\BC-20s"

# HL7 parametr nomlarini DB nomlariga moslashtirish
# Analyzer → DB/Blanka nomlari
# HL7/ASTM kaliti → DB tahlil nomi (3-diff + 5-diff). Yagona manba: gemo_protokol.DB_NAME_MAP
import gemo_protokol as _gp
HL7_TO_DB_NAME = dict(_gp.DB_NAME_MAP)

# Klinik muhim ko'rsatkichlar — ko'rsatish tartibi (faqat bular olinadi)
CLINICAL_PARAMETERS = {k: k for k in _gp.CANONICAL}


def open_window(parent=None, on_import_callback=None):
    """Gematologiya oynasini ochish.
    on_import_callback(sample_id, patient_info) → int  — asosiy oynaga natija o'tkazish uchun
    """
    import copy

    window = tk.Toplevel(parent)
    window.title("Gematologiya - BC-20S RAW Ma'lumotlar")
    window.geometry("1800x900")

    # ── Closure state ────────────────────────────────────────────────
    patients_data    = {}     # {sample_id: patient_info}
    edited_values    = {}     # {sample_id: {param_key: qo'lda_o'zgartirilgan_qiymat}}
    current_sid      = [None] # Hozir tanlangan sample_id
    result_entry_ref = [None] # Ochiq inline entry widget
    _auto_refresh_id = [None] # window.after() ID (to'xtatish uchun)
    _last_file_mtimes = {}    # {filepath: mtime} — fayl o'zgarishini kuzatish

    # ── Asosiy container ──────────────────────────────────────────────
    main_frame = ttk.Frame(window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # ── Boshqaruv paneli ──────────────────────────────────────────────
    control_frame = ttk.Frame(main_frame)
    control_frame.pack(fill=tk.X, pady=5)

    left_control = ttk.Frame(control_frame)
    left_control.pack(side=tk.LEFT, padx=5)

    center_control = ttk.Frame(control_frame)
    center_control.pack(side=tk.LEFT, expand=True, padx=20)
    ttk.Label(center_control, text="Sana:").pack(side=tk.LEFT, padx=5)
    date_from_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
    ttk.Entry(center_control, textvariable=date_from_var, width=12).pack(side=tk.LEFT, padx=5)
    ttk.Label(center_control, text="-").pack(side=tk.LEFT, padx=2)
    date_to_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
    ttk.Entry(center_control, textvariable=date_to_var, width=12).pack(side=tk.LEFT, padx=5)

    # ── Qidiruv / filtr (tarix uchun: familiya — kirill/lotin farqsiz, yosh, jins) ──
    filter_frame = ttk.Frame(main_frame)
    filter_frame.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(filter_frame, text="🔎 Qidiruv (F.I.SH / Sample ID):").pack(side=tk.LEFT, padx=(5, 2))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=32)
    search_entry.pack(side=tk.LEFT, padx=2)
    ttk.Label(filter_frame, text="Jinsi:").pack(side=tk.LEFT, padx=(12, 2))
    gender_var = tk.StringVar(value="Hammasi")
    ttk.Combobox(filter_frame, textvariable=gender_var, values=("Hammasi", "Erkak", "Ayol"),
                 width=9, state="readonly").pack(side=tk.LEFT, padx=2)
    ttk.Label(filter_frame, text="Yosh:").pack(side=tk.LEFT, padx=(12, 2))
    age_from_var = tk.StringVar()
    age_to_var = tk.StringVar()
    ttk.Entry(filter_frame, textvariable=age_from_var, width=5).pack(side=tk.LEFT)
    ttk.Label(filter_frame, text="-").pack(side=tk.LEFT, padx=2)
    ttk.Entry(filter_frame, textvariable=age_to_var, width=5).pack(side=tk.LEFT)
    sort_state = [("Sana/Vaqt", True)]   # (ustun, teskari) — standart: eng yangisi birinchi

    def _filters():
        return {"text": search_var.get(), "gender": gender_var.get(),
                "age_from": age_from_var.get().strip(), "age_to": age_to_var.get().strip()}

    def _clear_filters():
        search_var.set(""); gender_var.set("Hammasi"); age_from_var.set(""); age_to_var.set("")
        _apply_filter()

    ttk.Button(filter_frame, text="Tozalash", command=_clear_filters, width=9).pack(side=tk.LEFT, padx=(10, 2))
    ttk.Label(filter_frame, text="(ustun sarlavhasini bosib saralang)", foreground="#777777").pack(side=tk.LEFT, padx=10)

    right_control = ttk.Frame(control_frame)
    right_control.pack(side=tk.RIGHT, padx=5)
    status_var = tk.StringVar(value="Tayyor")
    ttk.Label(right_control, textvariable=status_var).pack(side=tk.LEFT, padx=5)

    # Auto-refresh belgisi
    auto_refresh_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(right_control, text="Auto (5s)",
                    variable=auto_refresh_var).pack(side=tk.LEFT, padx=8)

    # ── 2 panelli kontent ─────────────────────────────────────────────
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # ===== CHAP PANEL: BEMORLAR RO'YXATI =====
    left_panel = ttk.LabelFrame(content_frame, text="Bemorlar Ro'yxati", padding="5")
    left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
    left_panel.config(width=500)

    patient_columns = ("Sana/Vaqt", "Sample ID", "F.I.SH", "Yoshi", "Jinsi", "Status", "Key")
    patient_tree = ttk.Treeview(left_panel, columns=patient_columns, show="headings", height=30,
                                displaycolumns=patient_columns[:6])  # "Key" — yashirin kalit
    patient_tree.heading("Sana/Vaqt", text="Sana/Vaqt")
    patient_tree.column("Sana/Vaqt", width=130, anchor=tk.CENTER)
    patient_tree.heading("Sample ID", text="Sample ID")
    patient_tree.column("Sample ID", width=120, anchor=tk.CENTER)
    patient_tree.heading("F.I.SH", text="F.I.SH")
    patient_tree.column("F.I.SH", width=200, anchor=tk.W)
    patient_tree.heading("Yoshi", text="Yoshi")
    patient_tree.column("Yoshi", width=80, anchor=tk.CENTER)
    patient_tree.heading("Jinsi", text="Jinsi")
    patient_tree.column("Jinsi", width=80, anchor=tk.CENTER)
    patient_tree.heading("Status", text="Status")
    patient_tree.column("Status", width=100, anchor=tk.CENTER)

    patient_scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=patient_tree.yview)
    patient_tree.configure(yscrollcommand=patient_scrollbar.set)
    patient_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    patient_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _apply_filter(*_):
        """Fayllarni qayta o'qimasdan ro'yxatni filtr/saralash bo'yicha qayta chizish."""
        results_tree.delete(*results_tree.get_children())
        n = populate_patient_tree(patient_tree, patients_data, _filters(), sort_state[0])
        total = len(patients_data)
        status_var.set(f"Ko'rsatildi: {n} / {total} ta bemor" if n != total else f"Yuklandi: {total} ta bemor")
        col, rev = sort_state[0]
        for c in patient_columns[:6]:
            mark = (" ▼" if rev else " ▲") if c == col else ""
            patient_tree.heading(c, text=c + mark)

    def _sort_by(col):
        cur_col, cur_rev = sort_state[0]
        if cur_col == col:
            sort_state[0] = (col, not cur_rev)
        else:
            sort_state[0] = (col, col == "Sana/Vaqt")   # ism/yosh — o'sish, sana — kamayish
        _apply_filter()

    for _c in patient_columns[:6]:
        patient_tree.heading(_c, command=lambda c=_c: _sort_by(c))

    _search_after = [None]
    def _on_search_change(*_):
        if _search_after[0]:
            window.after_cancel(_search_after[0])
        _search_after[0] = window.after(300, _apply_filter)   # yozib bo'lguncha kutish
    search_var.trace_add("write", _on_search_change)
    gender_var.trace_add("write", _on_search_change)
    age_from_var.trace_add("write", _on_search_change)
    age_to_var.trace_add("write", _on_search_change)

    # ===== O'NG PANEL: NATIJALAR =====
    right_panel = ttk.LabelFrame(
        content_frame,
        text="Tahlil Natijalari  ✏ Natijani o'zgartirish uchun ikki marta bosing",
        padding="5"
    )
    right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

    results_columns = ("No.", "Tahlil nomi", "Natija", "Birlik", "Norma", "Flag")
    results_tree = ttk.Treeview(right_panel, columns=results_columns, show="headings", height=30)
    results_tree.heading("No.",         text="No.")
    results_tree.column("No.",         width=50,  anchor=tk.CENTER)
    results_tree.heading("Tahlil nomi", text="Tahlil nomi")
    results_tree.column("Tahlil nomi", width=150, anchor=tk.W)
    results_tree.heading("Natija",      text="Natija ✏")
    results_tree.column("Natija",      width=120, anchor=tk.CENTER)
    results_tree.heading("Birlik",      text="Birlik")
    results_tree.column("Birlik",      width=100, anchor=tk.CENTER)
    results_tree.heading("Norma",       text="Norma")
    results_tree.column("Norma",       width=150, anchor=tk.W)
    results_tree.heading("Flag",        text="Flag")
    results_tree.column("Flag",        width=80,  anchor=tk.CENTER)

    results_tree.tag_configure("high",       foreground="red")
    results_tree.tag_configure("low",        foreground="blue")
    results_tree.tag_configure("normal_res", foreground="black")
    results_tree.tag_configure("edited",     foreground="#006600",
                                             font=("Arial", 9, "bold"))
    # Kritik natija — qizil fon
    results_tree.tag_configure("critical",   background="#ffcccc", foreground="#a00000",
                                             font=("Arial", 9, "bold"))
    patient_tree.tag_configure("crit_patient", background="#ffe0e0", foreground="#a00000")
    _alerted_sids = set()   # takror ovoz bermaslik uchun

    results_scrollbar = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=results_scrollbar.set)
    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ══════════════════════════════════════════════════════════════════
    #  NATIJANI QO'LDA O'ZGARTIRISH — inline edit (2x click)
    # ══════════════════════════════════════════════════════════════════
    def _close_entry():
        if result_entry_ref[0]:
            try:
                result_entry_ref[0].destroy()
            except Exception:
                pass
            result_entry_ref[0] = None

    def on_result_double_click(event):
        """Natija (#3) ustuniga 2x bosilganda inline entry ochish"""
        region = results_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = results_tree.identify_column(event.x)
        if col != "#3":           # faqat Natija ustuni
            return
        row_id = results_tree.identify_row(event.y)
        if not row_id:
            return
        bbox = results_tree.bbox(row_id, "#3")
        if not bbox:
            return

        _close_entry()

        values     = results_tree.item(row_id, "values")
        param_name = values[1] if len(values) > 1 else ""
        raw_val    = values[2] if len(values) > 2 else ""
        clean_val  = raw_val.lstrip("↑↓ ")   # ↑ / ↓ prefixini olib tashlash

        entry = tk.Entry(results_tree, font=("Arial", 10), justify="center",
                         relief=tk.SOLID, borderwidth=1)
        entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        entry.insert(0, clean_val)
        entry.select_range(0, tk.END)
        entry.focus()
        result_entry_ref[0] = entry

        def _save_edit(event=None):
            new_val = entry.get().strip()
            _close_entry()
            sid = current_sid[0]
            if not sid or not new_val:
                return
            # HL7 param_key ni param_name orqali topish
            param_key = None
            for k, tdata in (patients_data.get(sid, {}).get('tests', {})).items():
                if tdata.get('name', k) == param_name or k == param_name:
                    param_key = k
                    break
            if param_key:
                edited_values.setdefault(sid, {})[param_key] = new_val
            # TreeView qatorni yangilash
            old_vals    = list(results_tree.item(row_id, "values"))
            old_vals[2] = new_val
            results_tree.item(row_id, values=tuple(old_vals), tags=("edited",))

        entry.bind("<Return>",   _save_edit)
        entry.bind("<FocusOut>", _save_edit)
        entry.bind("<Escape>",   lambda e: _close_entry())

    results_tree.bind("<Double-1>", on_result_double_click)

    # ══════════════════════════════════════════════════════════════════
    #  NATIJALARNI KO'RSATISH (edited_values hisobga olinadi)
    # ══════════════════════════════════════════════════════════════════
    def _show_results_local(event=None):
        results_tree.delete(*results_tree.get_children())
        sel = patient_tree.selection()
        if not sel:
            current_sid[0] = None
            return
        sample_id         = _row_key(patient_tree, sel[0])
        current_sid[0]    = sample_id
        if not sample_id or sample_id not in patients_data:
            return

        pinfo  = patients_data[sample_id]
        tests  = pinfo.get('tests', {})
        edits  = edited_values.get(sample_id, {})
        age    = pinfo.get('age', '')
        gender = pinfo.get('gender', '')
        no     = 1

        # ── Kritik natija: qaysi ko'rsatkichlar qizil bo'lishi kerak ──
        crit_keys = set()
        if critical_alert is not None:
            try:
                vmap = {}
                for pk in ("WBC", "RBC", "HGB", "PLT"):
                    if pk in tests:
                        vmap[pk] = edits.get(pk, tests[pk].get('value', ''))
                _al, crit_keys = critical_alert.check_hematology(vmap)
            except Exception:
                crit_keys = set()

        for param_key in CLINICAL_PARAMETERS:
            if param_key not in tests:
                continue
            tdata    = tests[param_key]
            raw_flag = tdata.get('flag', '').strip().upper()

            # ── Multi-ref norma ──────────────────────────────────
            lo, hi, ref_str = get_multi_ref(param_key, age, gender)
            if not ref_str:
                ref_str = tdata.get('ref', '')  # analyzer dan kelgan norma (fallback)

            if param_key in edits:
                display_value = edits[param_key]
                row_tag       = "edited"
                flag_display  = raw_flag
            else:
                value = tdata.get('value', '')
                # Multi-ref asosida flag qayta hisoblash
                if lo is not None and hi is not None:
                    try:
                        fval = float(value)
                        if fval > hi:
                            display_value = f"↑ {value}"
                            row_tag       = "high"
                            flag_display  = "H"
                        elif fval < lo:
                            display_value = f"↓ {value}"
                            row_tag       = "low"
                            flag_display  = "L"
                        else:
                            display_value = value
                            row_tag       = "normal_res"
                            flag_display  = "N"
                    except (ValueError, TypeError):
                        # Raqamga o'girib bo'lmasa analyzer flagini ishlatamiz
                        has_high = 'H' in raw_flag and raw_flag != 'N'
                        has_low  = 'L' in raw_flag and raw_flag != 'N'
                        if has_high and not has_low:
                            display_value = f"↑ {value}"; row_tag = "high"
                        elif has_low and not has_high:
                            display_value = f"↓ {value}"; row_tag = "low"
                        else:
                            display_value = value; row_tag = "normal_res"
                        flag_display = raw_flag
                else:
                    # Multi-ref yo'q — analyzer flagini ishlatamiz
                    has_high = 'H' in raw_flag and raw_flag != 'N'
                    has_low  = 'L' in raw_flag and raw_flag != 'N'
                    if has_high and not has_low:
                        display_value = f"↑ {value}"; row_tag = "high"
                    elif has_low and not has_high:
                        display_value = f"↓ {value}"; row_tag = "low"
                    else:
                        display_value = value; row_tag = "normal_res"
                    flag_display = raw_flag

            if param_key in crit_keys:
                row_tag = "critical"
            results_tree.insert("", tk.END, values=(
                str(no),
                tdata.get('name', param_key),
                display_value,
                tdata.get('unit', ''),
                ref_str,
                flag_display
            ), tags=(row_tag,))
            no += 1

    def show_results_with_data(event):
        _close_entry()
        _show_results_local(event)

    def _scan_criticals(play=True):
        """Barcha bemorlarni tekshirib, kritiklarni qizil belgilash;
        yangi kritik bemor uchun ovoz + popup."""
        if critical_alert is None:
            return
        new_crit = []
        for item in patient_tree.get_children():
            vals = patient_tree.item(item, "values")
            if not vals or len(vals) < 2:
                continue
            sid = _row_key(patient_tree, item)
            pdata = patients_data.get(sid)
            if not pdata:
                continue
            tests = pdata.get('tests', {})
            vmap = {pk: tests[pk].get('value', '') for pk in ("WBC", "RBC", "HGB", "PLT") if pk in tests}
            try:
                alerts, _ = critical_alert.check_hematology(vmap)
            except Exception:
                alerts = []
            if critical_alert.has_critical(alerts):
                # ABNORMAL statusi bo'yicha rangni buzmasdan qizil fon qo'shamiz
                patient_tree.item(item, tags=("crit_patient",))
                if sid not in _alerted_sids:
                    _alerted_sids.add(sid)
                    new_crit.append((pdata.get('name', sid), alerts))
        if new_crit and play:
            names = ", ".join(n for n, _ in new_crit)
            all_alerts = []
            for _, al in new_crit:
                all_alerts.extend(al)
            critical_alert.notify(window, names, all_alerts)

    # ══════════════════════════════════════════════════════════════════
    #  AUTO-REFRESH — har 5 sekundda fayl o'zgarishini kuzatish
    # ══════════════════════════════════════════════════════════════════
    def _get_current_file_mtimes():
        """Hozirgi oy papkasidagi TXT fayllarning mtime lari"""
        try:
            ym = datetime.now().strftime("%Y%m")
            folder = os.path.join(BC20S_DAT_BASE, ym)
            if not os.path.exists(folder):
                return {}
            mtimes = {}
            for fp in glob.glob(os.path.join(folder, "BC-20s_*.txt")):
                try:
                    mtimes[fp] = os.path.getmtime(fp)
                except Exception:
                    pass
            return mtimes
        except Exception:
            return {}

    def _auto_refresh_tick():
        """5 sekundda bir fayl o'zgarganmi tekshirish, o'zgarsa yangilash"""
        if not auto_refresh_var.get():
            _auto_refresh_id[0] = window.after(5000, _auto_refresh_tick)
            return
        try:
            current_mtimes = _get_current_file_mtimes()
            changed = (current_mtimes != _last_file_mtimes)
            if changed:
                _last_file_mtimes.clear()
                _last_file_mtimes.update(current_mtimes)
                # Qaysi bemor tanlangan edi?
                sel_before = patient_tree.selection()
                sel_sid = None
                if sel_before:
                    sel_sid = _row_key(patient_tree, sel_before[0])

                refresh_patient_list(patient_tree, results_tree, status_var,
                                     date_from_var, date_to_var, patients_data,
                                     _filters(), sort_state[0])
                _scan_criticals(play=True)

                # Avvalgi tanlovni tiklash
                if sel_sid:
                    for item in patient_tree.get_children():
                        if _row_key(patient_tree, item) == sel_sid:
                            patient_tree.selection_set(item)
                            patient_tree.see(item)
                            _show_results_local()
                            break
        except Exception:
            pass
        _auto_refresh_id[0] = window.after(5000, _auto_refresh_tick)

    def _on_window_close():
        if _auto_refresh_id[0]:
            try:
                window.after_cancel(_auto_refresh_id[0])
            except Exception:
                pass
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", _on_window_close)
    # Dastlabki mtime snapshot
    _last_file_mtimes.update(_get_current_file_mtimes())

    # ══════════════════════════════════════════════════════════════════
    #  ⬆  NATIJANI QO'SHISH — asosiy oynaga o'tkazish
    # ══════════════════════════════════════════════════════════════════
    def import_to_main():
        if not on_import_callback:
            messagebox.showinfo(
                "Ma'lumot",
                "Bu funksiya faqat asosiy oynaning 'Gemologiya' tugmasi orqali\n"
                "ochilganda ishlaydi."
            )
            return
        sel = patient_tree.selection()
        if not sel:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        sample_id = _row_key(patient_tree, sel[0])
        if not sample_id or sample_id not in patients_data:
            messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi!")
            return

        # Qo'lda o'zgartirishlarni asl nusxaga qo'llash
        pinfo = copy.deepcopy(patients_data[sample_id])
        edits = edited_values.get(sample_id, {})
        sample_id = pinfo.get('sample_id') or sample_id   # kalit emas, HAQIQIY sample ID
        for pk, nv in edits.items():
            if pk in pinfo['tests']:
                pinfo['tests'][pk]['value'] = nv

        # ── Kritik natija bo'lsa import oldidan tasdiqlash ──
        if critical_alert is not None:
            try:
                vmap = {pk: pinfo['tests'][pk].get('value', '')
                        for pk in ("WBC", "RBC", "HGB", "PLT") if pk in pinfo['tests']}
                alerts, _ = critical_alert.check_hematology(vmap)
                if not critical_alert.confirm_save(window, pinfo.get('name', sample_id) or sample_id, alerts):
                    return
            except Exception:
                pass

        try:
            count = on_import_callback(sample_id, pinfo)
            name  = pinfo.get('name', sample_id) or sample_id
            msg   = f"✅ Natijalar asosiy oynaga o'tkazildi!\n\nBemor: {name}"
            if count:
                msg += f"\nO'tkazilgan natijalar: {count} ta"
            # Bloklamaydigan xabar — bu yerda hech qanday QAROR kerak emas,
            # OK bosish kuniga o'nlab marta vaqt yo'qotardi (oyna_xabar.py).
            try:
                from oyna_xabar import toast
                toast(window.master if window.master else window, msg)
            except Exception:
                messagebox.showinfo("Muvaffaqiyat", msg)
            # Muvaffaqiyatli import'dan keyin oynani yopish
            try:
                window.destroy()
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Xato", f"Natijani o'tkazishda xato:\n{exc}")

    # ══════════════════════════════════════════════════════════════════
    #  TAXRIRLASH / O'CHIRISH / SAQLASH funksiyalari
    # ══════════════════════════════════════════════════════════════════
    def _get_selected_patient():
        """Tanlangan bemorni qaytarish: (sample_id, patient_info) yoki (None, None)"""
        sel = patient_tree.selection()
        if not sel:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return None, None
        sample_id = _row_key(patient_tree, sel[0])
        if not sample_id or sample_id not in patients_data:
            messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi!")
            return None, None
        return sample_id, patients_data[sample_id]

    def _rewrite_txt_file(file_path, pinfo, edited_vals=None):
        """TXT fayldagi PID, OBR va OBX segmentlarini yangi ma'lumotlar bilan qayta yozish.
        edited_vals: {param_key: yangi_qiymat} — tahrirlangan natijalar OBX da ham yangilanadi."""
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Xato", f"Faylni o'qishda xato:\n{e}")
            return False

        new_name = pinfo.get('name', '').strip()
        new_age = str(pinfo.get('age', '')).strip()
        new_sid = pinfo.get('sample_id', '').strip()

        # Ismni HL7 formatga o'girish: Given^Family
        name_parts = new_name.split(None, 1)
        if len(name_parts) >= 2:
            hl7_name = f"{name_parts[1]}^{name_parts[0]}"
        else:
            hl7_name = f"{new_name}^"

        # Tug'ilgan yilni yoshdan hisoblash
        birth_year_str = ''
        if new_age:
            try:
                age_int = int(float(new_age))
                birth_year = date.today().year - age_int
                birth_year_str = f"{birth_year}0101000000"
            except Exception:
                pass

        lines = re.split(r'[\r\n]+', content)
        new_lines = []
        for line in lines:
            if not line.strip():
                continue
            f = line.split('|')
            seg = line[:3] if len(line) >= 3 else ''

            if seg == 'PID' and len(f) > 5:
                f[5] = hl7_name
                if len(f) > 7 and birth_year_str:
                    f[7] = birth_year_str
                new_lines.append('|'.join(f))
            elif seg == 'OBR' and len(f) > 3 and new_sid:
                f[3] = new_sid
                new_lines.append('|'.join(f))
            elif seg == 'OBX' and edited_vals and len(f) > 5:
                # Tahrirlangan natijani OBX-5 ga yozish
                tc = f[3].split('^')[0].strip().upper() if len(f) > 3 and f[3] else ''
                tn = f[3].split('^')[1].strip().upper() if len(f) > 3 and '^' in f[3] else ''
                matched_key = None
                for key in CLINICAL_PARAMETERS:
                    if tc == key.upper() or tn == key.upper():
                        matched_key = key
                        break
                if matched_key and matched_key in edited_vals:
                    f[5] = str(edited_vals[matched_key])
                new_lines.append('|'.join(f))
            else:
                new_lines.append(line)

        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write('\r'.join(new_lines))
                if not new_lines[-1].endswith('\r'):
                    f.write('\r')
            return True
        except Exception as e:
            messagebox.showerror("Xato", f"Faylni yozishda xato:\n{e}")
            return False

    def _edit_patient():
        """Tanlangan bemorning ID, ism, yoshini tahrirlash dialogi."""
        sample_id, pinfo = _get_selected_patient()
        if not pinfo:
            return

        edit_win = tk.Toplevel(window)
        edit_win.title("Bemor ma'lumotlarini tahrirlash")
        edit_win.geometry("450x220")
        edit_win.transient(window)
        edit_win.grab_set()

        frame = ttk.Frame(edit_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        # Sample ID
        ttk.Label(frame, text="Sample ID:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        sid_var = tk.StringVar(value=pinfo.get('sample_id', ''))
        ttk.Entry(frame, textvariable=sid_var, width=30, font=("Arial", 11)).grid(row=0, column=1, pady=5, padx=10)

        # F.I.SH
        ttk.Label(frame, text="F.I.SH:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=pinfo.get('name', ''))
        ttk.Entry(frame, textvariable=name_var, width=30, font=("Arial", 11)).grid(row=1, column=1, pady=5, padx=10)

        # Yosh
        ttk.Label(frame, text="Yoshi:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        age_var = tk.StringVar(value=str(pinfo.get('age', '')))
        ttk.Entry(frame, textvariable=age_var, width=30, font=("Arial", 11)).grid(row=2, column=1, pady=5, padx=10)

        def _do_save():
            new_sid = sid_var.get().strip()
            new_name = name_var.get().strip()
            new_age = age_var.get().strip()

            if not new_name:
                messagebox.showwarning("Diqqat", "Ism bo'sh bo'lishi mumkin emas!", parent=edit_win)
                return

            # patients_data ni yangilash
            old_sid = sample_id
            if new_sid == (pinfo.get('sample_id') or ''):
                new_sid = old_sid   # haqiqiy ID o'zgarmadi — kalitni ham o'zgartirmaymiz
            pinfo['name'] = new_name
            pinfo['age'] = new_age

            if new_sid and new_sid != old_sid:
                pinfo['sample_id'] = new_sid
                patients_data[new_sid] = pinfo
                if old_sid in patients_data and old_sid != new_sid:
                    del patients_data[old_sid]
                # edited_values ni ham ko'chirish
                if old_sid in edited_values:
                    edited_values[new_sid] = edited_values.pop(old_sid)

            status_var.set(f"Tahrirlandi: {new_name}")
            edit_win.destroy()

            # Treeview ni yangilash (qo'lda)
            sel = patient_tree.selection()
            if sel:
                patient_tree.item(sel[0], values=(
                    pinfo.get('time', ''),
                    pinfo.get('sample_id', ''),
                    new_name,
                    new_age,
                    pinfo.get('gender', ''),
                    "ABNORMAL" if pinfo.get('abnormal') else "NORMAL"
                ))
            _show_results_local()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)
        tk.Button(btn_frame, text="Saqlash", command=_do_save,
                  bg="#28a745", fg="white", font=("Arial", 10, "bold"),
                  padx=20, pady=3).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Bekor qilish", command=edit_win.destroy,
                  font=("Arial", 10), padx=20, pady=3).pack(side=tk.LEFT, padx=10)

    def _delete_patient():
        """Tanlangan bemorni va uning TXT faylini o'chirish."""
        sample_id, pinfo = _get_selected_patient()
        if not pinfo:
            return

        name = pinfo.get('name', sample_id)
        file_path = pinfo.get('file_path', '')

        msg = f"Bemorni o'chirmoqchimisiz?\n\n" \
              f"Bemor: {name}\n" \
              f"Sample ID: {sample_id}"
        if file_path:
            msg += f"\n\nTXT fayl ham o'chiriladi:\n{os.path.basename(file_path)}"

        if not messagebox.askyesno("Tasdiqlash", msg, parent=window):
            return

        # TXT faylini o'chirish
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                status_var.set(f"O'chirildi: {name} + {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Xato", f"Faylni o'chirishda xato:\n{e}", parent=window)
                return
        else:
            status_var.set(f"O'chirildi: {name} (fayl topilmadi)")

        # patients_data dan olib tashlash
        if sample_id in patients_data:
            del patients_data[sample_id]
        if sample_id in edited_values:
            del edited_values[sample_id]

        # Treeview dan olib tashlash
        sel = patient_tree.selection()
        if sel:
            patient_tree.delete(sel[0])
        results_tree.delete(*results_tree.get_children())
        current_sid[0] = None

    def _save_to_txt():
        """Tahrirlangan bemor ma'lumotlarini TXT faylga saqlash."""
        sample_id, pinfo = _get_selected_patient()
        if not pinfo:
            return

        file_path = pinfo.get('file_path', '')
        if not file_path:
            messagebox.showwarning("Diqqat", "Bu bemor uchun TXT fayl yo'q!", parent=window)
            return
        if not os.path.exists(file_path):
            messagebox.showwarning("Diqqat", f"TXT fayl topilmadi:\n{file_path}", parent=window)
            return

        name = pinfo.get('name', sample_id)
        if not messagebox.askyesno("Tasdiqlash",
                f"TXT faylga saqlash:\n\n"
                f"Bemor: {name}\n"
                f"Sample ID: {sample_id}\n"
                f"Fayl: {os.path.basename(file_path)}",
                parent=window):
            return

        ev = edited_values.get(sample_id, {})
        if _rewrite_txt_file(file_path, pinfo, edited_vals=ev):
            status_var.set(f"Saqlandi: {name} → {os.path.basename(file_path)}")
            messagebox.showinfo("Muvaffaqiyat", f"Ma'lumotlar saqlandi:\n{os.path.basename(file_path)}", parent=window)
        else:
            messagebox.showerror("Xato", "Saqlashda xato yuz berdi!", parent=window)

    # ── Tugmalar ─────────────────────────────────────────────────────
    # 1) Natijani qo'shish (yashil, birinchi)
    import_btn_state = tk.NORMAL if on_import_callback else tk.DISABLED
    import_btn_bg    = "#28a745" if on_import_callback else "#aaaaaa"
    tk.Button(
        left_control,
        text="⬆ Natijani qo'shish",
        command=import_to_main,
        bg=import_btn_bg, fg="white",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=10, pady=3,
        cursor="hand2",
        state=import_btn_state
    ).pack(side=tk.LEFT, padx=(0, 12))

    # 2) Yangilash
    def refresh_with_data():
        refresh_patient_list(patient_tree, results_tree, status_var,
                             date_from_var, date_to_var, patients_data,
                             _filters(), sort_state[0])
        _apply_filter()
        _scan_criticals(play=True)
    ttk.Button(left_control, text="🔄 Yangilash",
               command=refresh_with_data).pack(side=tk.LEFT, padx=5)

    # 3) O'chirish (qizil)
    tk.Button(
        left_control, text="o'chirish", command=_delete_patient,
        bg="#dc3545", fg="white", font=("Arial", 9, "bold"),
        relief=tk.RAISED, padx=8, pady=2, cursor="hand2"
    ).pack(side=tk.LEFT, padx=3)

    # 4) Taxrirlash (yashil chegarali)
    tk.Button(
        left_control, text="Taxrirlash", command=_edit_patient,
        bg="white", fg="#28a745", font=("Arial", 9, "bold"),
        relief=tk.SOLID, padx=8, pady=2, cursor="hand2",
        highlightbackground="#28a745", highlightthickness=2, bd=2
    ).pack(side=tk.LEFT, padx=3)

    # 5) Saqlash (yashil chegarali)
    tk.Button(
        left_control, text="saqlash", command=_save_to_txt,
        bg="white", fg="#28a745", font=("Arial", 9, "bold"),
        relief=tk.SOLID, padx=8, pady=2, cursor="hand2",
        highlightbackground="#28a745", highlightthickness=2, bd=2
    ).pack(side=tk.LEFT, padx=3)

    # Separator (ajratuvchi chiziq)
    ttk.Separator(left_control, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

    # 6) Bazaga saqlash
    def save_selected_to_db():
        save_patient_to_db(patient_tree, status_var, patients_data)
    ttk.Button(left_control, text="Bazaga Saqlash",
               command=save_selected_to_db).pack(side=tk.LEFT, padx=5)

    # 7) Barchasini saqlash
    def save_all_to_db():
        save_all_patients_to_db(patients_data, status_var)
    ttk.Button(left_control, text="Barchasini Saqlash",
               command=save_all_to_db).pack(side=tk.LEFT, padx=5)

    # 8) USB / CSV import — analizator LIS ga yubormay qo'yganda (yoki eski
    #    natijalarni olish uchun) analizatorning o'zidan eksport qilingan CSV
    #    ni dastur formatiga (HL7 TXT, to'g'ri oy papkasi) o'giradi
    ttk.Separator(left_control, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
    ttk.Button(left_control, text="📥 USB / CSV import",
               command=lambda: open_csv_import_dialog(window, date_from_var, date_to_var,
                                                      refresh_with_data)).pack(side=tk.LEFT, padx=5)

    # ── Event binding ─────────────────────────────────────────────────
    patient_tree.bind("<<TreeviewSelect>>", show_results_with_data)

    # Dastlabki yuklash — kritiklarni qizil belgilaymiz, lekin ochilishda ovoz/popup bermaymiz
    refresh_patient_list(patient_tree, results_tree, status_var,
                         date_from_var, date_to_var, patients_data,
                         _filters(), sort_state[0])
    _apply_filter()
    _scan_criticals(play=False)
    _auto_refresh_id[0] = window.after(5000, _auto_refresh_tick)
    return window

def open_csv_import_dialog(parent, date_from_var=None, date_to_var=None, on_done=None):
    """Analizator USB eksportini (CSV) import qilish oynasi.

    Oqim: fayl(lar)ni tanlash → sana oralig'i → "Ko'rish" (reja: nima yangi,
    nima allaqachon bor) → "Import" → TXT fayllar to'g'ri oy papkasiga yoziladi,
    xohlasa bazaga ham saqlanadi → ro'yxat yangilanadi.
    """
    try:
        import bc20s_csv_import as imp
    except Exception as e:
        messagebox.showerror("Import", f"bc20s_csv_import.py yuklanmadi:\n{e}", parent=parent)
        return
    from tkinter import filedialog

    prefs = imp.load_prefs()

    win = tk.Toplevel(parent)
    win.title("📥 Analizator USB eksportini import qilish (BC-20S CSV)")
    win.geometry("980x600")
    win.transient(parent)

    top = ttk.Frame(win, padding=8)
    top.pack(fill=tk.X)

    ttk.Label(top, text="CSV fayl(lar):").grid(row=0, column=0, sticky="w")
    files_var = tk.StringVar(value="")
    ttk.Entry(top, textvariable=files_var, width=90).grid(row=0, column=1, sticky="we", padx=4)
    selected_files = []

    def _pick():
        init = prefs.get("last_dir") or "D:\\"
        paths = filedialog.askopenfilenames(
            parent=win, title="Analizator eksport CSV faylini tanlang",
            initialdir=init if os.path.isdir(init) else None,
            filetypes=[("Mindray CSV eksport", "*.csv"), ("Barcha fayllar", "*.*")])
        if paths:
            selected_files[:] = list(paths)
            files_var.set("; ".join(os.path.basename(p) for p in paths))
            imp.save_prefs({"last_dir": os.path.dirname(paths[0])})
            _preview()

    def _pick_folder():
        init = prefs.get("last_dir") or "D:\\"
        folder = filedialog.askdirectory(parent=win, title="USB papkasini tanlang (ichidagi barcha CSV)",
                                         initialdir=init if os.path.isdir(init) else None)
        if folder:
            paths = sorted(glob.glob(os.path.join(folder, "**", "*.csv"), recursive=True))
            if not paths:
                messagebox.showwarning("Import", "Bu papkada CSV fayl topilmadi.", parent=win)
                return
            selected_files[:] = paths
            files_var.set("; ".join(os.path.basename(p) for p in paths))
            imp.save_prefs({"last_dir": folder})
            _preview()

    ttk.Button(top, text="Fayl…", command=_pick).grid(row=0, column=2, padx=2)
    ttk.Button(top, text="Papka…", command=_pick_folder).grid(row=0, column=3, padx=2)

    ttk.Label(top, text="Sana oralig'i:").grid(row=1, column=0, sticky="w", pady=(6, 0))
    rng = ttk.Frame(top)
    rng.grid(row=1, column=1, sticky="w", pady=(6, 0))
    d_from = tk.StringVar(value=(date_from_var.get() if date_from_var else datetime.now().strftime("%d.%m.%Y")))
    d_to = tk.StringVar(value=(date_to_var.get() if date_to_var else datetime.now().strftime("%d.%m.%Y")))
    ttk.Entry(rng, textvariable=d_from, width=12).pack(side=tk.LEFT)
    ttk.Label(rng, text=" - ").pack(side=tk.LEFT)
    ttk.Entry(rng, textvariable=d_to, width=12).pack(side=tk.LEFT)

    def _set_today():
        d_from.set(datetime.now().strftime("%d.%m.%Y")); d_to.set(d_from.get()); _preview()

    def _set_all():
        d_from.set("01.01.2000"); d_to.set("31.12.2099"); _preview()

    ttk.Button(rng, text="Bugun", command=_set_today, width=7).pack(side=tk.LEFT, padx=(8, 2))
    ttk.Button(rng, text="Hammasi", command=_set_all, width=9).pack(side=tk.LEFT, padx=2)

    # Standart: faqat TXT (bazaga YOZILMAYDI) — laborant "Natijani qo'shish" bilan o'zi biriktiradi
    save_db_var = tk.BooleanVar(value=False)
    overwrite_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(rng, text="Bazaga ham saqlash (odatda kerak emas)", variable=save_db_var).pack(side=tk.LEFT, padx=(16, 4))
    ttk.Checkbutton(rng, text="Mavjudlarini ham qayta yozish",
                    variable=overwrite_var, command=lambda: _preview()).pack(side=tk.LEFT, padx=4)
    top.columnconfigure(1, weight=1)

    cols = ("Sana/Vaqt", "Sample ID", "F.I.SH", "Yoshi", "Holat")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
    for c, w, a in (("Sana/Vaqt", 130, tk.CENTER), ("Sample ID", 130, tk.CENTER),
                    ("F.I.SH", 240, tk.W), ("Yoshi", 60, tk.CENTER), ("Holat", 360, tk.W)):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor=a)
    tree.tag_configure("yangi", foreground="#006600", font=("Arial", 9, "bold"))
    tree.tag_configure("skip", foreground="#777777")
    tree.tag_configure("xato", foreground="#a00000")
    tree.tag_configure("done", background="#DFF5DF")
    sb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8)
    sb.place(relx=1.0, rely=0.3, relheight=0.55, anchor="ne")

    bottom = ttk.Frame(win, padding=8)
    bottom.pack(fill=tk.X)
    info_var = tk.StringVar(value="Fayl tanlang.")
    ttk.Label(bottom, textvariable=info_var).pack(side=tk.LEFT)

    plan_holder = [[]]

    def _parse_range():
        try:
            f = datetime.strptime(d_from.get().strip(), "%d.%m.%Y").date()
            t = datetime.strptime(d_to.get().strip(), "%d.%m.%Y").date()
            return f, t
        except ValueError:
            messagebox.showwarning("Sana", "Sana formati: DD.MM.YYYY", parent=win)
            return None, None

    def _fill(plan):
        tree.delete(*tree.get_children())
        n_new = 0
        for r in plan:
            act = r.get("action", "")
            if act == "yangi":
                n_new += 1
            tag = "yangi" if act == "yangi" else ("xato" if act == "xato" else "skip")
            if r.get("txt"):
                tag = "done"
            label = imp.ACTION_LABEL.get(act, act)
            if r.get("txt"):
                label = "✓ yozildi: " + os.path.basename(r["txt"]) + \
                        ("  | bazaga saqlandi" if r.get("db") else
                         ("  | bazada buyurtma topilmadi" if r.get("db") is False else ""))
            if r.get("error"):
                label += " — " + r["error"]
            tree.insert("", tk.END, values=(
                r["dt"].strftime("%d.%m.%Y %H:%M") if r.get("dt") else "—",
                r.get("sample", ""), r.get("full_name", ""),
                (r.get("age") or ("", ""))[0], label), tags=(tag,))
        return n_new

    def _preview():
        if not selected_files:
            return
        f, t = _parse_range()
        if not f:
            return
        try:
            plan = imp.plan_import(selected_files, f, t, overwrite=overwrite_var.get())
        except Exception as e:
            messagebox.showerror("Import", f"CSV o'qishda xato:\n{e}", parent=win)
            return
        plan_holder[0] = plan
        n_new = _fill(plan)
        info_var.set(f"{len(plan)} ta qator o'qildi, {n_new} tasi import qilinadi.")

    def _run():
        plan = plan_holder[0]
        new_rows = [r for r in plan if r.get("action") == "yangi"]
        if not new_rows:
            messagebox.showinfo("Import", "Import qilinadigan yangi natija yo'q.", parent=win)
            return
        if not messagebox.askyesno(
                "Import", f"{len(new_rows)} ta natija TXT ga yoziladi"
                + (" va bazaga saqlanadi" if save_db_var.get() else "") + ".\nDavom etamizmi?",
                parent=win):
            return
        stats = imp.run_import(plan, save_db=save_db_var.get())
        _fill(plan)
        info_var.set(f"Yozildi: {stats['yozildi']}  |  bazaga: {stats['db']}  |  "
                     f"buyurtma topilmadi: {stats['db_topilmadi']}  |  xato: {stats['xato']}")
        if on_done:
            try:
                on_done()
            except Exception as e:
                print(f"[Import] yangilashda xato: {e}")
        messagebox.showinfo("Import tugadi",
                            f"TXT yozildi: {stats['yozildi']}\nBazaga saqlandi: {stats['db']}\n"
                            f"Buyurtma topilmadi: {stats['db_topilmadi']}\nXato: {stats['xato']}",
                            parent=win)

    ttk.Button(bottom, text="Yopish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bottom, text="📥 Import", command=_run).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bottom, text="🔍 Ko'rish", command=_preview).pack(side=tk.RIGHT, padx=4)
    return win


def get_current_month_folder():
    """Joriy oy papkasini aniqlash (YYYYMM formatida)"""
    today = datetime.now()
    year_month = today.strftime("%Y%m")
    return year_month

def load_raw_files(date_from=None, date_to=None):
    """
    BC-20S DAT papkasidan fayllarni yuklash
    Joriy oy papkasini avtomatik aniqlaydi
    """
    files = []
    
    # Asosiy DAT papka mavjudligini tekshirish
    if not os.path.exists(BC20S_DAT_BASE):
        print(f"⚠️ BC-20S DAT papkasi topilmadi: {BC20S_DAT_BASE}")
        return files
    
    # Oy papkalari: sana oralig'i qamrab olgan HAMMA oylar (ilgari faqat joriy
    # oy o'qilardi — o'tgan oyga USB dan import qilingan natija ko'rinmasdi)
    months = [get_current_month_folder()]
    if date_from and date_to:
        try:
            fd = datetime.strptime(date_from, "%d.%m.%Y").date()
            td = datetime.strptime(date_to, "%d.%m.%Y").date()
            months = []
            y, mo = fd.year, fd.month
            while (y, mo) <= (td.year, td.month) and len(months) < 36:
                months.append(f"{y:04d}{mo:02d}")
                y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        except Exception:
            months = [get_current_month_folder()]

    all_files = []
    for ym in months:
        month_folder = os.path.join(BC20S_DAT_BASE, ym)
        if os.path.exists(month_folder):
            all_files.extend(glob.glob(os.path.join(month_folder, "BC-20s_*.txt")))
    if not all_files:
        print(f"⚠️ Oy papkasida fayl topilmadi: {months}")
        return files
    
    # Sana bo'yicha filtr
    if date_from and date_to:
        try:
            from_date = datetime.strptime(date_from, "%d.%m.%Y").date()
            to_date = datetime.strptime(date_to, "%d.%m.%Y").date()
            
            filtered_files = []
            for file_path in all_files:
                # Fayl nomidan sana olish: BC-20s_YYYYMMDD_XXX.txt
                file_name = os.path.basename(file_path)
                match = re.search(r'BC-20s_(\d{4})(\d{2})(\d{2})_', file_name)
                if match:
                    year, month, day = match.groups()
                    file_date = date(int(year), int(month), int(day))
                    if from_date <= file_date <= to_date:
                        filtered_files.append(file_path)
                else:
                    # Agar fayl nomidan sana olinmasa, modification time dan olish
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_date = file_time.date()
                    if from_date <= file_date <= to_date:
                        filtered_files.append(file_path)
            
            files = filtered_files
        except Exception as e:
            print(f"⚠️ Sana filtr xatosi: {e}")
            files = all_files
    else:
        files = all_files
    
    # Sana bo'yicha saralash (eng yangisi birinchi)
    # Fayl nomidan sana bo'yicha saralash
    def get_file_date(file_path):
        file_name = os.path.basename(file_path)
        match = re.search(r'BC-20s_(\d{4})(\d{2})(\d{2})_', file_name)
        if match:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day))
        return datetime.fromtimestamp(os.path.getmtime(file_path))
    
    files.sort(key=get_file_date, reverse=True)
    
    return files[:50000]  # Tarix (LIS gacha bo'lgan yillar) ham sig'sin

def _decode_name(raw):
    """
    HL7 PID-5 dagi ismni to'g'rilash.
    Windows-1251 bytes UTF-8 sifatida o'qilsa mojibake bo'ladi.
    Masalan: РђС‚С…Р°Рј → Атхам
    """
    if not raw:
        return ''
    # Avval latin-1 orqali decode qilib ko'rish
    try:
        fixed = raw.encode('latin-1').decode('utf-8')
        # Agar kirill harflari bo'lsa, shu versiyani ishlatamiz
        if any('\u0400' <= c <= '\u04ff' for c in fixed):
            return fixed.strip()
    except Exception:
        pass
    return raw.strip()


def _parse_hl7_time(dt_str, fallback=''):
    """YYYYMMDDHHMMSS → DD.MM.YYYY HH:MM"""
    try:
        if dt_str and len(dt_str) >= 8:
            y, mo, d = dt_str[:4], dt_str[4:6], dt_str[6:8]
            h = dt_str[8:10] if len(dt_str) >= 10 else '00'
            mi = dt_str[10:12] if len(dt_str) >= 12 else '00'
            return f"{d}.{mo}.{y} {h}:{mi}"
    except Exception:
        pass
    return fallback


def _save_to_dict(patients_dict, patient):
    """patients_dict ga bemorni qo'shish yoki vaqt bo'yicha yangilash.
    Barkod skanerlanmagan bemorlar uchun ham ishlaydi (time+name asosida kalit).
    """
    sid = patient.get('sample_id', '').strip()
    if not patient.get('tests'):
        return
    if not sid:
        # Barkod yo'q → vaqt + nom asosida ichki kalit yaratish
        time_val  = patient.get('time', datetime.now().strftime("%d.%m.%Y %H:%M"))
        name_raw  = patient.get('name', '').strip()
        # Faqat harf va raqamlarni olib, 12 ta belgiga qadar qisqartirish
        safe_name = ''.join(c for c in name_raw if c.isalpha() or c.isdigit())[:12]
        time_key  = time_val.replace(' ', '').replace('.', '').replace(':', '')
        sid       = f"NOBC_{time_key}_{safe_name}" if safe_name else f"NOBC_{time_key}"
        patient['sample_id'] = sid
    if sid not in patients_dict:
        patients_dict[sid] = patient
    else:
        # Eng yangi vaqtni saqlash
        try:
            old_t = datetime.strptime(patients_dict[sid]['time'], "%d.%m.%Y %H:%M")
            new_t = datetime.strptime(patient['time'], "%d.%m.%Y %H:%M")
            if new_t > old_t:
                patients_dict[sid] = patient
        except Exception:
            patients_dict[sid] = patient


def parse_hl7_file(file_path):
    """
    Gemotologiya TXT fayldan barcha bemorlarni parse qilish.
    Fayl bir nechta xabardan iborat bo'lishi mumkin (HL7: MSH| bloklar; ASTM: H| bloklar).
    Parser gemo_protokol da — Mindray, Genrui, Edan, Dymind, Sysmex (ASTM) ... uchun umumiy.
    Qaytaradi: {sample_id: {time, name, age, gender, tests, abnormal, file_path}}
    """
    patients_dict = {}

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ Fayl o'qishda xato: {file_path} - {e}")
        return patients_dict

    # Fayl modification vaqti (fallback)
    try:
        fallback_time = datetime.fromtimestamp(
            os.path.getmtime(file_path)
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        fallback_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    for block in _gp.split_messages(content):
        try:
            patient = _gp.parse_message(block)
        except Exception as e:
            print(f"⚠️ Parse xato ({os.path.basename(file_path)}): {e}")
            continue
        if not patient.get('tests'):
            continue
        # Xabar ichida vaqt bo'lmasa — fayl vaqti
        if not patient.get('time'):
            patient['time'] = fallback_time
        # Faqat klinik ko'rsatkichlar (CLINICAL_PARAMETERS tartibida) — gistogramma va h.k. tashlanadi
        patient['tests'] = {k: v for k, v in patient['tests'].items() if k in CLINICAL_PARAMETERS}
        patient.pop('_extra', None)
        patient['file_path'] = file_path  # Qaysi fayldan kelganini saqlash
        _save_to_dict(patients_dict, patient)

    return patients_dict


# ══════════════════════════════════════════════════════════════════════
#  QIDIRUV / SARALASH yordamchilari
#  Tarix (LIS gacha bo'lgan 1.5 yil) import qilinganda ismlar KIRILL da,
#  sample ID lar esa har kuni 1 dan qayta boshlangan (takrorlanadi).
# ══════════════════════════════════════════════════════════════════════
_CYR2LAT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'j','з':'z','и':'i',
    'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
    'у':'u','ф':'f','х':'x','ц':'ts','ч':'ch','ш':'sh','щ':'sh','ъ':'','ы':'i','ь':'',
    'э':'e','ю':'yu','я':'ya','ў':'o','қ':'q','ғ':'g','ҳ':'h','ӯ':'o',
}

def normalize_name(s):
    """Kirill/lotin, apostrof va bo'shliqdan mustaqil qidiruv kaliti.
    'Абдуалимова Мунира' → 'abdualimovamunira', "O'ralbek" → 'oralbek'"""
    out = []
    for ch in (s or "").lower():
        if ch in _CYR2LAT:
            out.append(_CYR2LAT[ch])
        elif ch.isalnum():
            out.append(ch)
        # apostrof (' ` ʼ ’ ‘), bo'shliq, nuqta — tashlab yuboriladi
    t = "".join(out)
    # lotin yozuvdagi x/h va sh/ch variantlari — bir xil qilib beramiz
    return t.replace("kh", "x").replace("h", "x")


def _row_key(tree, item):
    """Treeview qatori → patients_data kaliti (7-yashirin ustun; bo'lmasa Sample ID)."""
    vals = tree.item(item, "values")
    if not vals:
        return None
    if len(vals) > 6 and vals[6]:
        return vals[6]
    return vals[1] if len(vals) > 1 else None


def _time_key(pinfo):
    try:
        return datetime.strptime(pinfo.get('time', ''), "%d.%m.%Y %H:%M")
    except Exception:
        return datetime.min


def _age_int(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return -1


def patient_matches(pinfo, filters):
    """filters: {'text': str, 'gender': 'Hammasi'|'Erkak'|'Ayol', 'age_from': str, 'age_to': str}"""
    if not filters:
        return True
    text = (filters.get('text') or "").strip()
    if text:
        q = normalize_name(text)
        hay = normalize_name(pinfo.get('name', '')) + "|" + str(pinfo.get('sample_id', '')).lower()
        if q not in hay and text.lower() not in str(pinfo.get('sample_id', '')).lower():
            return False
    g = filters.get('gender') or "Hammasi"
    if g != "Hammasi":
        pg = (pinfo.get('gender') or "").lower()
        if g == "Erkak" and not (pg.startswith("e") or pg.startswith("m") or "муж" in pg):
            return False
        if g == "Ayol" and not (pg.startswith("a") or pg.startswith("f") or "жен" in pg):
            return False
    af, at = filters.get('age_from', ''), filters.get('age_to', '')
    if af or at:
        a = _age_int(pinfo.get('age', ''))
        if a < 0:
            return False
        if af and a < _age_int(af):
            return False
        if at and a > _age_int(at):
            return False
    return True


def populate_patient_tree(patient_tree, patients_data, filters=None, sort=None):
    """patients_data → ro'yxat (filtr + saralash). sort = (ustun, teskari) yoki None (sana↓)."""
    patient_tree.delete(*patient_tree.get_children())
    items = [(k, p) for k, p in patients_data.items() if patient_matches(p, filters)]

    col, rev = (sort or ("Sana/Vaqt", True))
    if col == "Sana/Vaqt":
        items.sort(key=lambda kp: _time_key(kp[1]), reverse=rev)
    elif col == "Sample ID":
        items.sort(key=lambda kp: str(kp[1].get('sample_id', '')), reverse=rev)
    elif col == "F.I.SH":
        items.sort(key=lambda kp: (normalize_name(kp[1].get('name', '')) or "￿", _time_key(kp[1])), reverse=rev)
    elif col == "Yoshi":
        items.sort(key=lambda kp: _age_int(kp[1].get('age', '')), reverse=rev)
    elif col == "Jinsi":
        items.sort(key=lambda kp: (kp[1].get('gender') or "", _time_key(kp[1])), reverse=rev)
    elif col == "Status":
        items.sort(key=lambda kp: (bool(kp[1].get('abnormal')), _time_key(kp[1])), reverse=rev)

    for key, p in items:
        patient_tree.insert("", tk.END, values=[
            p.get('time', ''), p.get('sample_id', ''), p.get('name', ''),
            p.get('age', ''), p.get('gender', ''),
            "ABNORMAL" if p.get('abnormal') else "NORMAL",
            key,
        ])
    return len(items)


# Parse keshi: {path: (mtime, {key: pinfo})} — tarix (minglab fayl) yuklanganda
# har yangilashda hammasini qayta o'qimaslik uchun
_PARSE_CACHE = {}

def _parse_cached(file_path):
    try:
        mt = os.path.getmtime(file_path)
    except Exception:
        return parse_hl7_file(file_path)
    hit = _PARSE_CACHE.get(file_path)
    if hit and hit[0] == mt:
        return hit[1]
    res = parse_hl7_file(file_path)
    _PARSE_CACHE[file_path] = (mt, res)
    return res


def refresh_patient_list(patient_tree, results_tree, status_var, date_from_var, date_to_var, patients_data,
                         filters=None, sort=None):
    """Bemorlar ro'yxatini yangilash - 1 bemor = 1 qator"""
    status_var.set("Yuklanmoqda...")
    patient_tree.delete(*patient_tree.get_children())
    results_tree.delete(*results_tree.get_children())

    # Sana filtrlarni olish
    date_from = date_from_var.get().strip()
    date_to = date_to_var.get().strip()

    files = load_raw_files(date_from if date_from else None, date_to if date_to else None)

    if not files:
        status_var.set("Fayllar topilmadi")
        current_month = get_current_month_folder()
        month_folder = os.path.join(BC20S_DAT_BASE, current_month)
        messagebox.showinfo(
            "Ma'lumot",
            f"BC-20S DAT papkada yangi fayl yo'q.\n\n"
            f"Joriy oy papkasi: {month_folder}\n"
            f"Asosiy papka: {BC20S_DAT_BASE}"
        )
        return

    # patients_data ni tozalash
    patients_data.clear()

    # Barcha fayllarni parse qilish
    for file_path in files:
        file_patients = _parse_cached(file_path)
        for sample_id, patient_info in file_patients.items():
            if sample_id not in patients_data:
                patients_data[sample_id] = patient_info
                continue
            old = patients_data[sample_id]
            old_day = (old.get('time') or '')[:10]
            new_day = (patient_info.get('time') or '')[:10]
            if old_day == new_day:
                # Bir kunda bir sample qayta o'tkazilgan — eng yangisini saqlaymiz
                if _time_key(patient_info) > _time_key(old):
                    patients_data[sample_id] = patient_info
            else:
                # BOSHQA kundagi bir xil raqam (tarixda sample ID har kuni 1 dan
                # boshlangan) — bu boshqa bemor, alohida kalit bilan saqlaymiz
                alt = f"{sample_id}@{new_day}"
                if alt not in patients_data or _time_key(patient_info) > _time_key(patients_data[alt]):
                    patients_data[alt] = patient_info

    total_patients = populate_patient_tree(patient_tree, patients_data, filters, sort)
    n_all = len(patients_data)
    if total_patients != n_all:
        status_var.set(f"Ko'rsatildi: {total_patients} / {n_all} ta bemor ({len(files)} ta fayl)")
    else:
        status_var.set(f"Yuklandi: {total_patients} ta bemor ({len(files)} ta fayl)")

def show_patient_results(patient_tree, results_tree, event, patients_data):
    """Tanlangan bemor natijalarini ko'rsatish"""
    results_tree.delete(*results_tree.get_children())
    
    selection = patient_tree.selection()
    if not selection:
        return
    
    item = selection[0]
    sample_id = _row_key(patient_tree, item)
    if not sample_id or sample_id not in patients_data:
        return
    
    patient_info = patients_data[sample_id]
    tests = patient_info.get('tests', {})
    
    no = 1
    for param_key in CLINICAL_PARAMETERS.keys():
        if param_key in tests:
            test_data = tests[param_key]
            raw_flag = test_data.get('flag', '').strip().upper()
            value = test_data.get('value', '')
            
            # BC-20S flaglari: H, HH, H~N, L, LL, L~N, A, N
            has_high = 'H' in raw_flag and raw_flag not in ('', 'N')
            has_low  = 'L' in raw_flag and raw_flag not in ('', 'N')
            
            if has_high and not has_low:
                # H, HH, H~N → baland (qizil, ↑)
                display_value = f"↑ {value}"
                row_tag = "high"
            elif has_low and not has_high:
                # L, LL, L~N → past (ko'k, ↓)
                display_value = f"↓ {value}"
                row_tag = "low"
            else:
                display_value = value
                row_tag = "normal_res"
            
            results_tree.insert("", tk.END, values=(
                str(no),
                test_data.get('name', param_key),
                display_value,
                test_data.get('unit', ''),
                test_data.get('ref', ''),
                raw_flag
            ), tags=(row_tag,))
            no += 1


def save_patient_to_db(patient_tree, status_var, patients_data):
    """Tanlangan bemorni bazaga saqlash"""
    selection = patient_tree.selection()
    if not selection:
        messagebox.showwarning("Diqqat", "Avval bemorni tanlang")
        return
    
    item = selection[0]
    sample_id = _row_key(patient_tree, item)
    if not sample_id or sample_id not in patients_data:
        messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi")
        return
    
    patient_info = patients_data[sample_id]
    _do_save_patient(patient_info, status_var)


def save_all_patients_to_db(patients_data, status_var):
    """Barcha bemorlarni bazaga saqlash"""
    if not patients_data:
        messagebox.showwarning("Diqqat", "Saqlash uchun bemorlar yo'q")
        return
    
    count = len(patients_data)
    confirm = messagebox.askyesno(
        "Tasdiqlash",
        f"{count} ta bemorning natijalarini bazaga saqlashni tasdiqlaysizmi?\n\n"
        f"DIQQAT: Faqat Sample ID bo'yicha orders jadvalida topilgan\n"
        f"bemorlar uchun natijalar saqlanadi.\n\n"
        f"Bazada natijasi BOR bemorlarda eski natija YANGILANADI\n"
        f"(ustiga yoziladi). Har biri uchun alohida so'ralmaydi."
    )
    if not confirm:
        return
    
    saved = 0
    not_found = []
    errors = []
    
    for sample_id, patient_info in patients_data.items():
        result = _do_save_patient(patient_info, status_var, silent=True)
        if result == 'saved':
            saved += 1
        elif result == 'not_found':
            not_found.append(f"Sample ID: {sample_id} ({patient_info.get('name', '?')})")
        elif result == 'error':
            errors.append(f"Sample ID: {sample_id}")
    
    msg = f"✅ Saqlandi: {saved} ta bemor\n"
    if not_found:
        msg += f"\n⚠️ Bazada topilmadi ({len(not_found)} ta):\n" + "\n".join(not_found[:10])
    if errors:
        msg += f"\n❌ Xatolik ({len(errors)} ta):\n" + "\n".join(errors[:5])
    
    messagebox.showinfo("Natija", msg)
    status_var.set(f"Saqlandi: {saved} ta, topilmadi: {len(not_found)} ta")


def _do_save_patient(patient_info, status_var, silent=False):
    """
    Bir bemorning natijalarini bazaga saqlash.
    Qaytaradi: 'saved' | 'not_found' | 'error' | 'no_db'
    """
    if not DB_AVAILABLE:
        if not silent:
            messagebox.showerror("Xato", "MySQL moduli o'rnatilmagan!\npip install mysql-connector-python")
        return 'no_db'
    
    sample_id = patient_info.get('sample_id', '')
    name = patient_info.get('name', '')
    tests = patient_info.get('tests', {})
    
    if not tests:
        if not silent:
            messagebox.showwarning("Diqqat", "Saqlash uchun natijalar yo'q")
        return 'error'
    
    conn = db_conn()
    if not conn:
        if not silent:
            messagebox.showerror(
                "DB Ulanish Xatosi",
                f"MySQL serverga ulana olmadi!\n"
                f"Server: {DB_CONFIG.get('host')}\n"
                f"Tekshirishlar:\n"
                f"1. MySQL server ishlayotganini tekshiring\n"
                f"2. Firewall port 3306 ochiqligini tekshiring"
            )
        return 'error'
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # orders jadvalidan sample_id bo'yicha order_id topish
        cursor.execute("""
            SELECT o.id as order_id, b.fish, o.sample_id
            FROM orders o
            INNER JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sample_id = %s
               OR b.sample_id = %s
               OR b.kod_yollanma = %s
               OR o.id = %s
            ORDER BY o.sana_vaqt DESC
            LIMIT 1
        """, (sample_id, sample_id, sample_id, sample_id if sample_id.isdigit() else 0))
        
        order_row = cursor.fetchone()
        
        if not order_row:
            if not silent:
                messagebox.showwarning(
                    "Topilmadi",
                    f"Sample ID: {sample_id}\n"
                    f"Bemor: {name}\n\n"
                    f"Bu sample ID bazada topilmadi.\n"
                    f"Avval monoblok dasturida buyurtma yarating."
                )
            cursor.close()
            conn.close()
            return 'not_found'
        
        order_id = order_row['order_id']
        db_name = order_row.get('fish', name)
        
        if not silent:
            # Bu buyurtmada natija ALLAQACHON bormi? Bo'lsa — ustiga yoziladi,
            # laborant buni bilib turishi kerak (xato bemorga yozib yubormaslik uchun).
            _mavjud = 0
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM test_results WHERE order_id = %s",
                    (str(order_id),))
                _row_cnt = cursor.fetchone()
                _mavjud = int((_row_cnt or {}).get('n', 0) or 0)
            except Exception:
                _mavjud = 0

            _ogoh = ""
            if _mavjud:
                _ogoh = (f"\nDIQQAT: bu buyurtmada allaqachon {_mavjud} ta natija bor.\n"
                         f"Ular YANGILANADI — eski qiymat o'chadi.\n"
                         f"Haqiqatan ham natijani yangilamoqchimisiz?\n")

            confirm = messagebox.askyesno(
                "Tasdiqlash",
                f"Quyidagi bemor natijalarini saqlash:\n\n"
                f"Analyzer: {name} (Sample: {sample_id})\n"
                f"Bazadagi bemor: {db_name} (Order ID: {order_id})\n\n"
                f"Natijalar soni: {len(tests)} ta\n"
                f"{_ogoh}\n"
                f"Davom etasizmi?"
            )
            if not confirm:
                cursor.close()
                conn.close()
                return 'cancelled'
        
        test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # results jadvalida yozuv topish yoki yaratish
        # DIQQAT (2026-08-19): bu yerda status='ready' QO'YILMAYDI.
        # Gematologiya natijasi saqlanishi — buyurtmadagi bioximiya/IFA/siydik
        # tahlillari ham bajarildi degani emas. Yakuniy holatni pastdagi
        # natija_tugallik moduli HISOBLAB yozadi.
        cursor.execute("SELECT id FROM results WHERE order_id = %s", (order_id,))
        result_row = cursor.fetchone()

        if result_row:
            result_id = result_row['id']
            cursor.execute("""
                UPDATE results SET updated_at = %s WHERE id = %s
            """, (test_time, result_id))
        else:
            cursor.execute("""
                INSERT INTO results (order_id, status, created_at, updated_at)
                VALUES (%s, 'draft', %s, %s)
            """, (order_id, test_time, test_time))
            result_id = cursor.lastrowid
        
        # Har bir test natijasini saqlash
        saved_count = 0
        for param_key, test_data in tests.items():
            value = test_data.get('value', '')
            if not value:
                continue
            
            # DB uchun tahlil nomini aniqlash
            db_test_name = HL7_TO_DB_NAME.get(param_key, param_key)
            unit = test_data.get('unit', '')
            ref = test_data.get('ref', '')
            flag = test_data.get('flag', '')
            
            # result_items jadvaliga saqlash
            cursor.execute("""
                DELETE FROM result_items WHERE result_id = %s AND tahlil_nomi = %s
            """, (result_id, db_test_name))
            
            cursor.execute("""
                INSERT INTO result_items (result_id, tahlil_nomi, qiymat, birlik, norma, note)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (result_id, db_test_name, value, unit, ref, f"BC-20S | {test_time} | Flag: {flag}"))
            
            # test_results jadvaliga saqlash (yagona blanka uchun)
            result_json = json.dumps({
                'result': value, 'unit': unit, 'ref': ref, 'flag': flag,
                'source': 'BC-20S', 'sample_id': sample_id
            }, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO test_results (order_id, test_name, test_type, result_data, status)
                VALUES (%s, %s, 'numeric', %s, 'Saqlandi')
                ON DUPLICATE KEY UPDATE
                result_data = VALUES(result_data),
                status = 'Saqlandi',
                updated_at = CURRENT_TIMESTAMP
            """, (str(order_id), db_test_name, result_json))
            
            saved_count += 1

        # ── "Qonning umumiy tahlili" (yagona qator) ni HAM yangilash ─────────
        # Buyurtmada alohida WBC/HGB emas, bitta umumiy qon tahlili bo'lsa —
        # blankaga AYNAN shu kompozit qator tushadi. Faqat alohida qatorlarni
        # yangilash yetarli emas edi: natija tuzatilgach ham blankada ESKI
        # qiymat qolib ketardi.
        try:
            cursor.execute("SELECT nomi FROM order_items WHERE order_id = %s", (order_id,))
            _CBC_EXACT   = ('qonning umumiy tahlili', 'umumiy qon tahlili', 'umumiy qon')
            _CBC_EXCLUDE = ('qon guruhi', 'qon guruh', 'rezus', 'ivish', 'qib', 'echt')
            cbc_names = []
            for _r in cursor.fetchall():
                _nm  = (_r.get('nomi') or '')
                _low = _nm.lower()
                if any(e in _low for e in _CBC_EXACT) and not any(x in _low for x in _CBC_EXCLUDE):
                    cbc_names.append(_nm)

            if cbc_names:
                all_vals = {}
                for _pk, _td in tests.items():
                    _v = (_td.get('value') or '').strip()
                    if _v:
                        all_vals[HL7_TO_DB_NAME.get(_pk, _pk)] = _v
                if all_vals:
                    cbc_json = json.dumps({
                        'result': sample_id, 'type': 'hematology_cbc',
                        'source': 'BC-20S', 'sid': sample_id,
                        'patient_age':    patient_info.get('age', ''),
                        'patient_gender': patient_info.get('gender', ''),
                        **all_vals
                    }, ensure_ascii=False)
                    for _nm in cbc_names:
                        cursor.execute("""
                            DELETE FROM result_items WHERE result_id = %s AND tahlil_nomi = %s
                        """, (result_id, _nm))
                        cursor.execute("""
                            INSERT INTO result_items (result_id, tahlil_nomi, qiymat, birlik, norma, note)
                            VALUES (%s, %s, %s, '', '', %s)
                        """, (result_id, _nm, cbc_json, f"BC-20S | {test_time}"))
                        cursor.execute("""
                            INSERT INTO test_results (order_id, test_name, test_type, result_data, status)
                            VALUES (%s, %s, 'hematology_cbc', %s, 'Saqlandi')
                            ON DUPLICATE KEY UPDATE
                            result_data = VALUES(result_data),
                            status = 'Saqlandi',
                            updated_at = CURRENT_TIMESTAMP
                        """, (str(order_id), _nm, cbc_json))
                        saved_count += 1
                        print(f"[BC-20S] Umumiy qon tahlili yangilandi: {_nm} (order {order_id})")
        except Exception as _cbc_err:
            print(f"[OGOHLANTIRISH] Umumiy qon tahlilini yangilashda xato: {_cbc_err}")

        # orders jadvalini yangilash
        try:
            cursor.execute("UPDATE orders SET updated_at = %s WHERE id = %s", (test_time, order_id))
        except:
            pass

        # Natija holatini QAYTA HISOBLASH: 'ready' faqat buyurtmadagi HAMMA
        # laboratoriya tahlili saqlangan bo'lsa qo'yiladi, aks holda 'draft'.
        try:
            from natija_tugallik import natija_holatini_yangila
            natija_holatini_yangila(cursor, order_id, vaqt=test_time)
        except Exception as _he:
            print(f"[OGOHLANTIRISH] natija holati hisoblanmadi: {_he}")

        conn.commit()
        
        if not silent:
            messagebox.showinfo(
                "Muvaffaqiyat",
                f"✅ Natijalar saqlandi!\n\n"
                f"Bemor: {db_name}\n"
                f"Order ID: {order_id}\n"
                f"Saqlangan natijalar: {saved_count} ta"
            )
        
        if status_var:
            status_var.set(f"✅ Saqlandi: {db_name} (Order: {order_id}, {saved_count} natija)")
        
        return 'saved'
    
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        if not silent:
            messagebox.showerror("Xatolik", f"Saqlashda xato:\n{e}")
        import traceback
        traceback.print_exc()
        return 'error'
    
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
