# -*- coding: utf-8 -*-
"""
Bioximiya (BK-280) - RAW fayllarni ko'rsatish oynasi

BK-280 HL7 OBR formati:
  OBR|seq|BARCODE|PRIMER_N|BIOBASE^BK-280|...
  field[2] = Barcode/Sample ID (260225001064) ← TO'G'RI MAYDON
  field[3] = Primer raqami (kyuveta N) ← LIS bilan bog'liq EMAS

Asosiy tuzatishlar:
  1. OBR field[2] → sample_id (oldin field[3] noto'g'ri edi → "1" kelardi)
  2. Sana oralig'i to'g'ri ishlaydi (25-26 ikkalasi ham chiqadi)
  3. DB dan BIO tahlil nomlari yuklanadi
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
import glob
import re

try:
    import critical_alert
except Exception:
    critical_alert = None

try:
    import mysql.connector
    from monoblok_db_config import DB_CONFIG
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

def db_conn():
    if not DB_AVAILABLE:
        return None
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        print(f"[XATO] DB ulanish: {e}")
        return None

# BK-280 RAW fayllar papkasi — listener bilan BIR XIL bo'lishi shart.
# Listener (bk280_listener.py) fayllarni ProgramData ga yozadi (mijozda G: bo'lmasligi mumkin).
_BK_DATA = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "AzizMedLine", "BK280")
BK280_RAW_PATH = os.path.join(_BK_DATA, "RAW_LOGS")   # asosiy (yangi) yo'l — listener shu yerga yozadi

# Eski fayllar ham ko'rinib tursin: yangi + eski (legacy) papkalar birga qidiriladi
BK280_RAW_PATHS = [
    BK280_RAW_PATH,
    r"G:\DASTUR\URIT 50\BK280\RAW_LOGS",   # eski (legacy) yo'l
]

# LIS nomer → LIMS tahlillar.id (birlamchi bog'lanish — LIS nomer kabi ishlaydi)
# Tahlil nomi DB da o'zgarsa ham bu bog'lanish o'zgarmaydi.
# load_db_names() bu ID lar orqali DB dan haqiqiy nomni tortadi va fuzzy matchingdan himoya qiladi.
LIS_TO_TAHLIL_ID = {
    # Lipid spektri tarkibi (LIPID_PANEL_MEMBER_IDS = [43,44,123,124])
    '254': 43,   # Umumiy xolesterin (TC)
    '277': 124,  # HDL — Yuqori zichlikli lipoprotein
    '289': 123,  # LDL — Past zichlikli lipoprotein
    '308': 44,   # Trigliseridlar (TG)
    # Buyrak paneli tarkibi (BUYRAK_PANEL_MEMBER_IDS = [42,41,35,50])
    '313': 42,   # Mochevina
    '323': 41,   # Kreatinin
    '310': 50,   # Siydik kislotasi
    '316': 50,   # Siydik kislotasi (zaxira kod)
    '233': 35,   # Albumin
    '253': 128,  # Xolinesteraza (CHE)
    # Boshqa asosiy tahlillar
    '272': 37,   # Glyukoza
    # Qolganlar load_db_names() da DB dan avtomatik to'ldiriladi
}

# LIS kodlar HECH QACHON avtomatik ID ga bog'lanmasin (multi-komponentli yoki qo'lda kiritiladigan)
LIS_NO_ID_CODES = {
    '320', '321',        # Umumiy bilirubin, Bog'langan bilirubin (multi-komponent)
    '305', '245',        # R faktor, ASO (Revmoproba — qo'lda yoki ekspress)
    '322', '271',        # CRB/SRB (ikkala LIS kodi)
    '230',               # Timol proba (analizatorda ko'rinmaydi)
    '275',               # HbA1c (maxsus analizator)
}

# LIS nomer → ko'rsatish nomi (zaxira — load_db_names() bu nomlarni DB dan yangilaydi)
LIS_CODE_MAP = {
    '236': 'ALT',
    '246': 'AST',
    '319': 'GGT',
    '235': 'IF',
    '287': 'LDG',
    '320': 'Umumiy bilirubin',
    '321': "Bog'langan bilirubin",
    '313': 'Mochevina',
    '323': 'Kreatinin',
    '310': 'Siydik kislotasi',
    '316': 'Siydik kislotasi',
    '272': 'Glyukoza',
    '317': 'Umumiy oqsil',
    '233': 'Albumin',
    '254': 'Xolesterol',
    '308': 'Trigliserid',
    '277': 'HDL-xolesterin',
    '289': 'LDL-xolesterin',
    '252': 'Kalsiy',
    '284': 'Kaliy',
    '296': 'Magniy',
    '297': 'Natriy',
    '267': 'Temir',
    '237': 'Alfa-amilaza',
    '305': 'R faktor',
    '245': 'ASO',
    '322': 'CRB',
    '271': 'CRB',
    '230': 'Timol',
    '275': 'HbA1c',
    '253': 'Xolinesteraza (CHE)',
}

# Kalit so'z → LIS kodlar(i): DB nomida ushbu so'z bo'lsa shu kod yangilanadi
# Bu load_db_names da ishlatiladi (BIO bo'lmagan guruhlar uchun)
_EXTRA_ALIASES = {
    # ASO / ASLO / Antistreptolizin-O
    'antistreptolizin': ['245'],
    'aslo':             ['245'],
    # RF / Revmatoid faktor / R faktor
    'revmatoid':        ['305'],
    'r faktor':         ['305'],
    # CRB / SRB / S-reaktiv belok / C-reaktiv protein
    'reaktiv belok':    ['271', '322'],
    'c-reaktiv':        ['271', '322'],
    'srb':              ['271', '322'],
    'crb':              ['271', '322'],
    # Xolesterol / Xolesterin (umumiy TC)
    'xolester':         ['254'],
    # HDL — Yuqori zichlikli lipoprotein (LIS 277) — aniq kalit so'z, "non-hdl" ni tutmasligi uchun
    'yuqori zichlikli lipoprotein': ['277'],
    'hdl-xolesterin':               ['277'],
    # LDL — Past zichlikli lipoprotein (LIS 289)
    'past zichlikli lipoprotein':   ['289'],
    'ldl-xolesterin':               ['289'],
    # Trigliseridlar (LIS 308)
    'trigliserid':      ['308'],
    # Xolinesteraza — turli yozuvlar
    'xolinesteraza':    ['253'],
    'che':              ['253'],
    # Siydik kislotasi — turli yozuvlar
    'siydik kislot':    ['310', '316'],
    # Bilirubin
    "bog'langan bil":   ['321'],
    'umumiy bil':       ['320'],
}

ANALYZER_TO_DB = {
    'ALT':              'ALT',
    'AST':              'AST',
    'GGT':              'GGT',
    'IF':               'IF',
    'UM BILR-N':        'Umumiy bilirubin',
    'UMUMIY BIL':       'Umumiy bilirubin',
    'TOTAL BIL':        'Umumiy bilirubin',
    'BOG BILR-N':       "Bog'langan bilirubin",
    'DIRECT BIL':       "Bog'langan bilirubin",
    "BOG'LANGAN BIL":   "Bog'langan bilirubin",
    'GLUKOZA':          'Glyukoza',
    'GLUCOSE':          'Glyukoza',
    'MOCHEVINA':        'Mochevina',
    'UREA':             'Mochevina',
    'KREATININ':        'Kreatinin',
    'CREATININE':       'Kreatinin',
    'MOCH KIS-A':       'Siydik kislotasi',
    'URIC ACID':        'Siydik kislotasi',
    'SIYDIK KIS':       'Siydik kislotasi',
    'OQSIL':            'Umumiy oqsil',
    'TOTAL PROTEIN':    'Umumiy oqsil',
    'ALBUMIN':          'Albumin',
    'XOLESTERIN':       'Xolesterol',
    'XOLESTEROL':       'Xolesterol',
    'CHOLESTEROL':      'Xolesterol',
    'TRIG':             'Trigliserid',
    'TRIGLYCERIDE':     'Trigliserid',
    'HDL':              'HDL-xolesterin',
    'LDL':              'LDL-xolesterin',
    'KALSIY':           'Kalsiy',
    'CALCIUM':          'Kalsiy',
    'KALIY':            'Kaliy',
    'POTASSIUM':        'Kaliy',
    'MAGNIY':           'Magniy',
    'MAGNESIUM':        'Magniy',
    'NATRIY':           'Natriy',
    'SODIUM':           'Natriy',
    'TEMIR':            'Temir',
    'IRON':             'Temir',
    'A-PANKRIAT':       'Alfa-amilaza',
    'AMYLASE':          'Alfa-amilaza',
    'LDGFERMENT':       'LDG',
    'LDH':              'LDG',
    # RF / Revmatoid faktor
    'R FAKTOR':         'R faktor',
    'RF':               'R faktor',
    'REVMATOID':        'R faktor',
    'RHEUMATOID':       'R faktor',
    # ASO / ASLO
    'ASO':              'ASO',
    'ASLO':             'ASO',
    'ANTISTREPTOLIZIN': 'ASO',
    # CRB / SRB / S-reaktiv belok
    'CRB':              'CRB',
    'SRB':              'CRB',
    'C-REAKTIV':        'CRB',
    'S-REAKTIV':        'CRB',
    'CRP':              'CRB',
    'TIMOL':            'Timol',
    'HBA1C':            'HbA1c',
    'CHE':              'Xolinesteraza (CHE)',
    'XOLINESTERAZA':    'Xolinesteraza (CHE)',
    'CHOLINESTERASE':   'Xolinesteraza (CHE)',
    'PSEUDOCHOLINEST':  'Xolinesteraza (CHE)',
}


def load_db_names():
    """tahlillar jadvalidan ID orqali, keyin tahlillar_norma dan nom yuklash."""
    global LIS_CODE_MAP, ANALYZER_TO_DB, LIS_TO_TAHLIL_ID
    if not DB_AVAILABLE:
        return
    conn = db_conn()
    if not conn:
        return

    # 1-QADAM: LIS_TO_TAHLIL_ID dagi ID lar orqali tahlillar jadvalidan haqiqiy nomni olish
    # Bu eng ishonchli bog'lanish — nom o'zgarsa ham ID o'zgarmaydi
    try:
        cur = conn.cursor()
        id_list = list(set(LIS_TO_TAHLIL_ID.values()))
        if id_list:
            ph = ','.join(['%s'] * len(id_list))
            cur.execute(f"SELECT id, nomi FROM tahlillar WHERE id IN ({ph})", id_list)
            id_to_name = {row[0]: row[1] for row in cur.fetchall()}
            cur.close()
            for lis_code, tid in LIS_TO_TAHLIL_ID.items():
                if tid in id_to_name and id_to_name[tid]:
                    LIS_CODE_MAP[lis_code] = id_to_name[tid]
            print(f"[DB] LIS_TO_TAHLIL_ID: {len(id_to_name)} ta tahlil nomi yuklandi")
    except Exception as e:
        print(f"[DB] LIS_TO_TAHLIL_ID nomlarini yuklashda xato: {e}")

    # 2-QADAM: tahlillar_norma dan qolgan nomlarni yangilash (avvalgi mantiq)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT tahlil_nomi FROM tahlillar_norma "
            "WHERE guruh IN ('BIO','TEST','REVMOPROBA','COAG') "
            "OR tahlil_nomi IS NOT NULL"
        )
        db_names = [r['tahlil_nomi'] for r in cur.fetchall() if r['tahlil_nomi']]
        cur.close(); conn.close()

        updated = 0
        for dn in db_names:
            dn_lower = dn.lower()
            dc = dn.upper().replace(' ', '').replace('-', '').replace("'", '')

            # 1) _EXTRA_ALIASES orqali aniq moslik (ASO/RF/CRB kabi maxsus testlar)
            for keyword, codes in _EXTRA_ALIASES.items():
                if keyword in dn_lower:
                    for code in codes:
                        # LIS_TO_TAHLIL_ID da bog'langan kodlarga tegmaslik
                        if code in LIS_TO_TAHLIL_ID or code in LIS_NO_ID_CODES:
                            continue
                        if LIS_CODE_MAP.get(code) != dn:
                            LIS_CODE_MAP[code] = dn
                            updated += 1
                    for an, cv in list(ANALYZER_TO_DB.items()):
                        if keyword in cv.lower():
                            ANALYZER_TO_DB[an] = dn
                    break

            # 2) Odatiy avtomatik moslik — LIS_TO_TAHLIL_ID va LIS_NO_ID_CODES kodlari o'TKAZIB YUBORILADI
            for code, cn in list(LIS_CODE_MAP.items()):
                if code in LIS_TO_TAHLIL_ID or code in LIS_NO_ID_CODES:
                    continue  # ID orqali bog'langan yoki maxsus kod — fuzzy matching QILMASLIK
                cc = cn.upper().replace(' ', '').replace('-', '').replace("'", '')
                if cc == dc or (len(dc) > 4 and (dc in cc or cc in dc)):
                    if LIS_CODE_MAP[code] != dn:
                        LIS_CODE_MAP[code] = dn
                        updated += 1
            for an, cn in list(ANALYZER_TO_DB.items()):
                cc = cn.upper().replace(' ', '').replace('-', '').replace("'", '')
                if cc == dc or (len(dc) > 4 and (dc in cc or cc in dc)):
                    ANALYZER_TO_DB[an] = dn

        print(f"[DB] {len(db_names)} ta nom yuklandi, {updated} ta xarita yangilandi")
    except Exception as e:
        print(f"[DB] Nom yuklanmadi: {e}")

    # 3-QADAM: Qolgan BIO testlar uchun DB dan tahlil ID ni avtomatik qurish
    # (LIS_TO_TAHLIL_ID va LIS_NO_ID_CODES da bo'lmagan kodlar uchun)
    try:
        conn3 = db_conn()
        if conn3:
            cur3 = conn3.cursor()
            cur3.execute(
                "SELECT id, nomi FROM tahlillar "
                "WHERE sample IN ('BIO','GEN') OR sample IS NULL "
                "ORDER BY id"
            )
            bio_tests = [(row[0], row[1], row[1].lower()) for row in cur3.fetchall() if row[1]]
            cur3.close(); conn3.close()

            def _name_match(lis_nm, db_nm_lower):
                """LIS nomi DB nomi bilan mos keladimi (xavfsiz tekshirish)."""
                if lis_nm == db_nm_lower:
                    return True
                if len(lis_nm) >= 4 and db_nm_lower.startswith(lis_nm) and len(db_nm_lower) < len(lis_nm) + 15:
                    return True  # Prefiks: "kalsiy" → "kalsiy ca"
                if len(lis_nm) >= 3 and f"({lis_nm})" in db_nm_lower:
                    return True  # Abbreviatura: "(alt)", "(ggt)", "(ldg)"
                if len(lis_nm) >= 6 and lis_nm in db_nm_lower:
                    return True  # Qism (faqat uzun nomlar): "albumin", "mochevina"
                return False

            auto_mapped = 0
            for lis_code, lis_name in list(LIS_CODE_MAP.items()):
                if lis_code in LIS_TO_TAHLIL_ID or lis_code in LIS_NO_ID_CODES:
                    continue
                ln = lis_name.lower().replace('-', '').replace("'", '').strip()
                for db_id, db_nomi, db_lower in bio_tests:
                    db_clean = db_lower.replace('-', '').replace("'", '')
                    if _name_match(ln, db_clean):
                        LIS_TO_TAHLIL_ID[lis_code] = db_id
                        LIS_CODE_MAP[lis_code] = db_nomi  # Haqiqiy DB nomi
                        auto_mapped += 1
                        break
            if auto_mapped:
                print(f"[DB] Avtomatik ID xaritasi: {auto_mapped} ta qo'shimcha tahlil bog'landi")
    except Exception as e:
        print(f"[DB] Auto ID mapping xato: {e}")


def get_db_name(lis_code, analyzer_name):
    if lis_code and lis_code in LIS_CODE_MAP:
        return LIS_CODE_MAP[lis_code]
    if analyzer_name:
        au = analyzer_name.upper().strip()
        # To'liq moslik
        if au in ANALYZER_TO_DB:
            return ANALYZER_TO_DB[au]
        # Qisman moslik (uzun nomlar uchun)
        for k, v in ANALYZER_TO_DB.items():
            if len(k) >= 3 and (k in au or au in k):
                return v
        # Analyzer nomini tozalab qayta sinash (belgilar olib tashlangan)
        au_clean = au.replace('-', '').replace(' ', '').replace("'", '')
        for k, v in ANALYZER_TO_DB.items():
            kc = k.replace('-', '').replace(' ', '').replace("'", '')
            if len(kc) >= 3 and (kc in au_clean or au_clean in kc):
                return v
    return analyzer_name if analyzer_name else f"Kod:{lis_code}"


def open_window(parent=None, on_import_callback=None):
    """Bioximiya oynasini ochish.
    on_import_callback(sample_id, patient_info) → int  — asosiy oynaga natija o'tkazish uchun
    """
    import copy

    window = tk.Toplevel(parent)
    window.title("Bioximiya - BK-280 RAW Ma'lumotlar")
    window.geometry("1600x800")
    load_db_names()

    # ── Closure state ─────────────────────────────────────────────────
    patients_data    = {}
    edited_values    = {}     # {sid: {lis_code: yangi_qiymat}}
    current_sid      = [None]
    result_entry_ref = [None]

    main = ttk.Frame(window, padding="10")
    main.pack(fill=tk.BOTH, expand=True)

    ctrl = ttk.Frame(main)
    ctrl.pack(fill=tk.X, pady=5)

    lc = ttk.Frame(ctrl)
    lc.pack(side=tk.LEFT, padx=5)

    cc = ttk.Frame(ctrl)
    cc.pack(side=tk.LEFT, expand=True, padx=20)
    ttk.Label(cc, text="Sana:").pack(side=tk.LEFT, padx=5)
    date_from_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
    ttk.Entry(cc, textvariable=date_from_var, width=12).pack(side=tk.LEFT, padx=5)
    ttk.Label(cc, text="-").pack(side=tk.LEFT, padx=2)
    date_to_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
    ttk.Entry(cc, textvariable=date_to_var, width=12).pack(side=tk.LEFT, padx=5)

    rc = ttk.Frame(ctrl)
    rc.pack(side=tk.RIGHT, padx=5)
    status_var = tk.StringVar(value="Tayyor")
    ttk.Label(rc, textvariable=status_var).pack(side=tk.LEFT, padx=5)

    cf = ttk.Frame(main)
    cf.pack(fill=tk.BOTH, expand=True, pady=5)

    lp = ttk.LabelFrame(cf, text="Bemorlar Ro'yxati", padding="5")
    lp.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
    lp.config(width=640)

    pcols = ("Sana/Vaqt", "Sample ID", "F.I.SH", "№")
    ptree = ttk.Treeview(lp, columns=pcols, show="headings", height=30)
    for col, w, a in [("Sana/Vaqt",145,tk.CENTER),("Sample ID",120,tk.CENTER),
                       ("F.I.SH",220,tk.W),("№",60,tk.CENTER)]:
        ptree.heading(col, text=col); ptree.column(col, width=w, anchor=a)
    ps = ttk.Scrollbar(lp, orient=tk.VERTICAL, command=ptree.yview)
    ptree.configure(yscrollcommand=ps.set)
    ptree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    ps.pack(side=tk.RIGHT, fill=tk.Y)

    rp = ttk.LabelFrame(
        cf,
        text="Tahlil Natijalari  \u270f Natijani o'zgartirish uchun ikki marta bosing",
        padding="5"
    )
    rp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

    rcols = ("LIS", "Tahlil nomi", "Natija", "Birlik", "Norma", "Flag")
    rtree = ttk.Treeview(rp, columns=rcols, show="headings", height=30)
    for col, w, a in [("LIS",55,tk.CENTER),("Tahlil nomi",240,tk.W),
                       ("Natija",105,tk.CENTER),("Birlik",90,tk.CENTER),
                       ("Norma",120,tk.W),("Flag",55,tk.CENTER)]:
        rtree.heading(col, text=col); rtree.column(col, width=w, anchor=a)
    rtree.tag_configure("high",       foreground="red")
    rtree.tag_configure("low",        foreground="blue")
    rtree.tag_configure("normal_res", foreground="black")
    rtree.tag_configure("edited",     foreground="#006600",
                                      font=("Arial", 9, "bold"))
    # Kritik natija — qizil fon
    rtree.tag_configure("critical",   background="#ffcccc", foreground="#a00000",
                                      font=("Arial", 9, "bold"))
    ptree.tag_configure("crit_patient", background="#ffe0e0", foreground="#a00000")
    _alerted_sids = set()   # allaqachon ovoz berilgan bemorlar (takror bermaslik)
    rs = ttk.Scrollbar(rp, orient=tk.VERTICAL, command=rtree.yview)
    rtree.configure(yscrollcommand=rs.set)
    rtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    rs.pack(side=tk.RIGHT, fill=tk.Y)

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
        region = rtree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = rtree.identify_column(event.x)
        if col != "#3":           # faqat Natija ustuni
            return
        row_id = rtree.identify_row(event.y)
        if not row_id:
            return
        bbox = rtree.bbox(row_id, "#3")
        if not bbox:
            return

        _close_entry()

        values   = rtree.item(row_id, "values")
        lis_code = values[0] if len(values) > 0 else ''
        raw_val  = values[2] if len(values) > 2 else ''
        clean_val = raw_val.lstrip("\u2191\u2193 ")   # ↑ / ↓ prefixini olib tashlash

        entry = tk.Entry(rtree, font=("Arial", 10), justify="center",
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
            if lis_code:
                edited_values.setdefault(sid, {})[lis_code] = new_val
            old_vals    = list(rtree.item(row_id, "values"))
            old_vals[2] = new_val
            rtree.item(row_id, values=tuple(old_vals), tags=("edited",))

        entry.bind("<Return>",   _save_edit)
        entry.bind("<FocusOut>", _save_edit)
        entry.bind("<Escape>",   lambda e: _close_entry())

    rtree.bind("<Double-1>", on_result_double_click)

    # ══════════════════════════════════════════════════════════════════
    #  NATIJALARNI KO'RSATISH (edited_values hisobga olinadi)
    # ══════════════════════════════════════════════════════════════════
    def do_show_full(event=None):
        _close_entry()
        rtree.delete(*rtree.get_children())
        sel = ptree.selection()
        if not sel:
            current_sid[0] = None
            return
        vals = ptree.item(sel[0], 'values')
        if not vals or len(vals) < 2:
            return
        sid = str(vals[1])
        current_sid[0] = sid
        if sid not in patients_data:
            return
        tests = patients_data[sid].get('tests', {})
        edits = edited_values.get(sid, {})

        # ── Kritik natija tekshiruvi (nom bo'yicha qizil qilinadigan qatorlar) ──
        crit_names = set()
        if critical_alert is not None:
            try:
                rows_for_check = []
                for k, t in tests.items():
                    lc = t.get('lis_code', k)
                    val = edits.get(lc, t.get('value', ''))
                    rows_for_check.append((t.get('name', ''), val))
                _al, crit_names = critical_alert.check_biochemistry(rows_for_check)
            except Exception:
                crit_names = set()

        for key in sorted(tests, key=lambda k: int(k) if str(k).isdigit() else 9999):
            t    = tests[key]
            flag = t.get('flag', '').strip().upper()
            lis_code = t.get('lis_code', key)
            if lis_code in edits:
                display_value = edits[lis_code]
                row_tag       = "edited"
            else:
                value = t.get('value', '')
                if flag in ('H', 'HH'):
                    display_value = f"\u2191 {value}"
                    row_tag       = "high"
                elif flag in ('L', 'LL'):
                    display_value = f"\u2193 {value}"
                    row_tag       = "low"
                else:
                    display_value = value
                    row_tag       = "normal_res"
            ref = t.get('ref', '').replace('~', ' - ')
            if t.get('name', '') in crit_names:
                row_tag = "critical"
            rtree.insert("", tk.END, values=(
                lis_code, t.get('name', ''),
                display_value, t.get('unit', ''),
                ref, flag
            ), tags=(row_tag,))

    # ══════════════════════════════════════════════════════════════════
    #  NATIJANI QO'SHISH — asosiy oynaga o'tkazish
    # ══════════════════════════════════════════════════════════════════
    def import_to_main():
        if not on_import_callback:
            messagebox.showinfo(
                "Ma'lumot",
                "Bu funksiya faqat asosiy oynaning 'Bioximiya' tugmasi orqali\n"
                "ochilganda ishlaydi."
            )
            return
        sel = ptree.selection()
        if not sel:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        vals = ptree.item(sel[0], 'values')
        if not vals or len(vals) < 2:
            return
        sid = str(vals[1])
        if not sid or sid not in patients_data:
            messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi!")
            return

        pinfo = copy.deepcopy(patients_data[sid])
        edits = edited_values.get(sid, {})
        for lis_code, new_val in edits.items():
            if lis_code in pinfo['tests']:
                pinfo['tests'][lis_code]['value'] = new_val

        # ── Kritik natija bo'lsa import oldidan tasdiqlash ──
        if critical_alert is not None:
            try:
                rows = [(t.get('name', ''), t.get('value', '')) for t in pinfo['tests'].values()]
                alerts, _ = critical_alert.check_biochemistry(rows)
                if not critical_alert.confirm_save(window, pinfo.get('name', sid), alerts):
                    return
            except Exception:
                pass

        try:
            count = on_import_callback(sid, pinfo)
            name  = pinfo.get('name', sid)
            msg   = f"\u2705 Natijalar asosiy oynaga o'tkazildi!\n\nBemor: {name}"
            if count:
                msg += f"\nO'tkazilgan natijalar: {count} ta"
            # Bloklamaydigan xabar (oyna_xabar.py izohiga qarang)
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

    # ── TXT tahrirlash yordamchi funksiyalari ─────────────────────────
    def _get_selected_patient():
        sel = ptree.selection()
        if not sel:
            return None, None
        vals = ptree.item(sel[0], 'values')
        if not vals or len(vals) < 2:
            return None, None
        sid = str(vals[1])
        return sid, patients_data.get(sid)

    def _rewrite_bk280_txt(file_path, pinfo, edited_vals=None):
        """BK-280 HL7 fayldagi PID ism, OBR sample_id va OBX natijalarini qayta yozish."""
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Xato", f"Faylni o'qishda xato:\n{e}", parent=window)
            return False

        new_name = pinfo.get('name', '').strip()
        new_sid  = pinfo.get('sample_id', '').strip()
        lines = re.split(r'[\r\n]+', content)
        new_lines = []
        for line in lines:
            if not line.strip():
                continue
            f2 = line.split('|')
            seg = line[:3] if len(line) >= 3 else ''
            if seg == 'PID' and new_name:
                for idx in [4, 5]:
                    if len(f2) > idx:
                        f2[idx] = new_name
                        break
                new_lines.append('|'.join(f2))
            elif seg == 'OBR' and new_sid and len(f2) > 2:
                f2[2] = new_sid
                new_lines.append('|'.join(f2))
            elif seg == 'OBX' and edited_vals and len(f2) > 5:
                lis_code = f2[3].strip() if len(f2) > 3 else ''
                if lis_code in edited_vals:
                    f2[5] = str(edited_vals[lis_code])
                new_lines.append('|'.join(f2))
            else:
                new_lines.append(line)
        try:
            with open(file_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write('\n'.join(new_lines))
            return True
        except Exception as e:
            messagebox.showerror("Xato", f"Faylni yozishda xato:\n{e}", parent=window)
            return False

    def _delete_patient():
        sid, pinfo = _get_selected_patient()
        if not pinfo:
            return
        name = pinfo.get('name', sid or '?')
        fp = pinfo.get('file_path', '')
        msg = f"Bemorni o'chirmoqchimisiz?\n\nBemor: {name}\nSample ID: {sid}"
        if fp:
            msg += f"\n\nTXT fayl ham o'chiriladi:\n{os.path.basename(fp)}"
        if not messagebox.askyesno("Tasdiqlash", msg, parent=window):
            return
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
                status_var.set(f"O'chirildi: {name} + {os.path.basename(fp)}")
            except Exception as e:
                messagebox.showerror("Xato", f"Faylni o'chirishda xato:\n{e}", parent=window)
                return
        else:
            status_var.set(f"O'chirildi: {name} (fayl topilmadi)")
        if sid in patients_data:
            del patients_data[sid]
        if sid in edited_values:
            del edited_values[sid]
        sel = ptree.selection()
        if sel:
            ptree.delete(sel[0])
        rtree.delete(*rtree.get_children())
        current_sid[0] = None

    def _edit_patient():
        sid, pinfo = _get_selected_patient()
        if not pinfo:
            return
        edit_win = tk.Toplevel(window)
        edit_win.title("Bemor ma'lumotlarini tahrirlash")
        edit_win.geometry("420x150")
        edit_win.transient(window)
        edit_win.grab_set()
        frame = ttk.Frame(edit_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Sample ID:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        sid_var = tk.StringVar(value=pinfo.get('sample_id', sid or ''))
        ttk.Entry(frame, textvariable=sid_var, width=30, font=("Arial", 11)).grid(row=0, column=1, pady=5, padx=10)
        ttk.Label(frame, text="F.I.SH:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=pinfo.get('name', ''))
        ttk.Entry(frame, textvariable=name_var, width=30, font=("Arial", 11)).grid(row=1, column=1, pady=5, padx=10)
        def _do_save():
            pinfo['sample_id'] = sid_var.get().strip()
            pinfo['name']      = name_var.get().strip()
            status_var.set(f"Tahrirlandi: {pinfo['name']}")
            edit_win.destroy()
            sel = ptree.selection()
            if sel:
                ptree.item(sel[0], values=(pinfo.get('time',''), sid, pinfo.get('name',''), pinfo.get('_display_num','')))
        ttk.Button(frame, text="Saqlash", command=_do_save).grid(row=2, column=1, sticky=tk.E, pady=8)

    def _save_to_txt():
        sid, pinfo = _get_selected_patient()
        if not pinfo:
            return
        fp = pinfo.get('file_path', '')
        if not fp:
            messagebox.showwarning("Diqqat", "Bu bemor uchun TXT fayl yo'q!", parent=window)
            return
        if not os.path.exists(fp):
            messagebox.showwarning("Diqqat", f"TXT fayl topilmadi:\n{fp}", parent=window)
            return
        name = pinfo.get('name', sid or '?')
        if not messagebox.askyesno("Tasdiqlash",
                f"TXT faylga saqlash:\nBemor: {name}\nFayl: {os.path.basename(fp)}", parent=window):
            return
        ev = edited_values.get(sid, {})
        if _rewrite_bk280_txt(fp, pinfo, edited_vals=ev):
            status_var.set(f"Saqlandi: {name} → {os.path.basename(fp)}")
            messagebox.showinfo("Muvaffaqiyat", f"Saqlandi:\n{os.path.basename(fp)}", parent=window)
        else:
            messagebox.showerror("Xato", "Saqlashda xato yuz berdi!", parent=window)

    # ── Tugmalar ──────────────────────────────────────────────────────
    # 1) Natijani qo'shish (yashil, birinchi)
    import_btn_state = tk.NORMAL if on_import_callback else tk.DISABLED
    import_btn_bg    = "#28a745" if on_import_callback else "#aaaaaa"
    tk.Button(
        lc,
        text="\u2b06 Natijani qo'shish",
        command=import_to_main,
        bg=import_btn_bg, fg="white",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=10, pady=3,
        cursor="hand2",
        state=import_btn_state
    ).pack(side=tk.LEFT, padx=(0, 12))

    def _scan_criticals(play=True):
        """Barcha yuklangan bemorlarni tekshirib, kritiklarni qizil belgilash;
        yangi kritik bemor uchun ovoz + popup berish."""
        if critical_alert is None:
            return
        new_crit = []
        for item in ptree.get_children():
            vals = ptree.item(item, 'values')
            if not vals or len(vals) < 2:
                continue
            sid = str(vals[1])
            pdata = patients_data.get(sid)
            if not pdata:
                continue
            rows = [(t.get('name', ''), t.get('value', '')) for t in pdata.get('tests', {}).values()]
            try:
                alerts, _ = critical_alert.check_biochemistry(rows)
            except Exception:
                alerts = []
            if critical_alert.has_critical(alerts):
                ptree.item(item, tags=("crit_patient",))
                if sid not in _alerted_sids:
                    _alerted_sids.add(sid)
                    new_crit.append((pdata.get('name', sid), alerts))
        if new_crit and play:
            names = ", ".join(n for n, _ in new_crit)
            all_alerts = []
            for _, al in new_crit:
                all_alerts.extend(al)
            critical_alert.notify(window, names, all_alerts)

    def do_refresh():
        refresh_patient_list(ptree, rtree, status_var, date_from_var, date_to_var, patients_data)
        _scan_criticals(play=True)

    ttk.Button(lc, text="\U0001f504 Yangilash", command=do_refresh).pack(side=tk.LEFT, padx=5)
    tk.Button(lc, text="o'chirish", command=_delete_patient,
              bg="#dc3545", fg="white", font=("Arial", 9, "bold"),
              relief=tk.RAISED, padx=8, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=3)
    tk.Button(lc, text="Taxrirlash", command=_edit_patient,
              bg="white", fg="#28a745", font=("Arial", 9, "bold"),
              relief=tk.SOLID, padx=8, pady=2, cursor="hand2",
              highlightbackground="#28a745", highlightthickness=2, bd=2).pack(side=tk.LEFT, padx=3)
    tk.Button(lc, text="saqlash", command=_save_to_txt,
              bg="white", fg="#28a745", font=("Arial", 9, "bold"),
              relief=tk.SOLID, padx=8, pady=2, cursor="hand2",
              highlightbackground="#28a745", highlightthickness=2, bd=2).pack(side=tk.LEFT, padx=3)

    ptree.bind("<<TreeviewSelect>>", do_show_full)
    # Dastlabki yuklash — kritiklarni belgilaymiz, lekin ochilishda ovoz/popup bermaymiz
    refresh_patient_list(ptree, rtree, status_var, date_from_var, date_to_var, patients_data)
    _scan_criticals(play=False)
    return window


def load_raw_files(date_from=None, date_to=None):
    """
    BK-280 RAW fayllarni sana oralig'i bo'yicha yuklash.
    date_from va date_to IKKALASI INCLUSIVE (shu kunlar ham kiradi).
    """
    # Barcha qidiruv papkalari (yangi ProgramData + eski G:) dan fayllarni yig'ish
    all_files = []
    for root in BK280_RAW_PATHS:
        if not os.path.exists(root):
            continue
        # Oylik papkalar va to'g'ridan-to'g'ri fayllarni qidirish (rekursiv)
        all_files += glob.glob(os.path.join(root, "**", "*.txt"), recursive=True)
        all_files += glob.glob(os.path.join(root, "*.txt"))

    # Bir xil fayl ikki marta kelmasin (rekursiv + to'g'ridan qidiruv ustma-ust tushishi mumkin)
    all_files = list(dict.fromkeys(all_files))

    if not all_files:
        return []

    if date_from and date_to:
        try:
            from_d = datetime.strptime(date_from, "%d.%m.%Y").date()
            to_d   = datetime.strptime(date_to,   "%d.%m.%Y").date()

            filtered = []
            for fp in all_files:
                fname = os.path.basename(fp)
                # Fayl nomidan sana: bk280_raw_YYYYMMDD_HHMMSS.txt
                m = re.search(r'(\d{4})(\d{2})(\d{2})_\d{6}', fname)
                if m:
                    fd = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    # MSH ichidan olish
                    fd = _get_file_date_from_content(fp)
                    if not fd:
                        fd = datetime.fromtimestamp(os.path.getmtime(fp)).date()

                # INCLUSIVE: from_d <= fd <= to_d
                if from_d <= fd <= to_d:
                    filtered.append(fp)
            files = filtered
        except Exception as e:
            print(f"⚠️ Sana filtr: {e}")
            files = all_files
    else:
        files = all_files

    files.sort(key=os.path.getmtime, reverse=True)
    return files[:1000]


def _get_file_date_from_content(fp):
    """MSH-7 dan sana olish."""
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(500)
        m = re.search(r'MSH\|(?:[^|]*\|){5}(\d{8})', head)
        if m:
            ds = m.group(1)
            return date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
    except Exception:
        pass
    return None


def _fmt_time(dt_str, fallback=''):
    try:
        if dt_str and len(dt_str) >= 8:
            return (f"{dt_str[6:8]}.{dt_str[4:6]}.{dt_str[:4]} "
                    f"{dt_str[8:10] if len(dt_str)>=10 else '00'}:"
                    f"{dt_str[10:12] if len(dt_str)>=12 else '00'}")
    except Exception:
        pass
    return fallback


def _get_norma_decimals(ref_str):
    """Norma stringidan maksimal kasr xonalar sonini aniqlash.
    Masalan: '3.89 - 6.1' → 2, '0 - 41' → 0, '44 - 115' → 0
    """
    if not ref_str:
        return None
    import re as _re
    nums = _re.findall(r'\d+\.?\d*', str(ref_str))
    if not nums:
        return None
    max_dec = 0
    for n in nums:
        if '.' in n:
            dec = len(n.split('.')[1])
            if dec > max_dec:
                max_dec = dec
    return max_dec


def _fmt_val(val, ref=''):
    """Qiymatni norma kasr aniqligiga moslab formatlash."""
    try:
        fv = float(val)
    except Exception:
        return val
    dec = _get_norma_decimals(ref)
    if dec is not None:
        return f"{fv:.{dec}f}"
    return f"{fv:.4g}"


def _extract_test_date(dt_str):
    """MSH-7 yoki OBR-7 dan YYYYMMDD olish."""
    if dt_str and len(dt_str) >= 8:
        return dt_str[:8]
    return ''


def parse_hl7_file(file_path):
    """
    BK-280 RAW fayldan parse qilish.

    OBR field[2] = Barcode (12 xonali) → sample_id.
    12 xonali bo'lmasa sample_id = '', filename fallback ishlatilmaydi.
    """
    result = {}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ {file_path}: {e}")
        return result

    fname = os.path.basename(file_path)
    m = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', fname)
    fallback_time = (
        f"{m.group(3)}.{m.group(2)}.{m.group(1)} {m.group(4)}:{m.group(5)}"
        if m else datetime.now().strftime("%d.%m.%Y %H:%M")
    )

    sample_id = ''
    name = ''
    test_time = fallback_time
    test_date = ''
    tests = {}
    has_ab = False
    obr_seq = ''

    for line in re.split(r'[\r\n]+', content):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        seg = line[:3]
        f = line.split('|')

        if seg == 'MSH':
            if len(f) > 6 and f[6].strip():
                raw = f[6].strip()
                test_date = test_date or _extract_test_date(raw)
                t = _fmt_time(raw, fallback_time)
                if t:
                    test_time = t

        elif seg == 'PID':
            for idx in [4, 5]:
                if len(f) > idx and f[idx].strip() and not f[idx].strip().isdigit():
                    name = f[idx].strip()
                    break

        elif seg == 'OBR':
            obr_seq = f[1].strip() if len(f) > 1 and f[1].strip() else ''
            if len(f) > 2 and f[2].strip():
                cand = f[2].strip()
                if cand and not cand.upper().startswith('BIOBASE'):
                    sample_id = cand if (len(cand) == 12 and cand.isdigit()) else ''
            if len(f) > 6 and f[6].strip():
                raw = f[6].strip()
                test_date = test_date or _extract_test_date(raw)
                t = _fmt_time(raw, test_time)
                if t:
                    test_time = t

        elif seg == 'OBX':
            if len(f) < 5:
                continue
            lis_code = f[3].strip() if len(f) > 3 else ''
            aname = f[4].strip() if len(f) > 4 else ''
            value = f[5].strip() if len(f) > 5 else ''
            unit = f[6].strip() if len(f) > 6 else ''
            ref = f[7].strip() if len(f) > 7 else ''
            flag = f[8].strip() if len(f) > 8 else ''
            if not value:
                continue

            display = get_db_name(lis_code, aname)
            tahlil_id = LIS_TO_TAHLIL_ID.get(lis_code)  # LIMS DB tahlil ID (LIS nomer kabi)
            is_ab = bool(flag) and flag.upper() not in ('N',) and (
                'H' in flag.upper() or 'L' in flag.upper())
            if is_ab:
                has_ab = True

            ref_clean = ref.replace('~', ' - ')
            tests[lis_code or aname] = {
                'lis_code': lis_code,
                'tahlil_id': tahlil_id,  # None bo'lsa — LIS_TO_TAHLIL_ID da yo'q
                'analyzer_name': aname,
                'name': display,
                'value': _fmt_val(value, ref_clean),
                'unit': unit,
                'ref': ref_clean,
                'flag': flag,
                'abnormal': is_ab,
            }

    if not tests:
        return result

    normalized_name = name.replace('^', ' ').strip().upper() if name else 'NONAME'
    if not test_date:
        test_date = datetime.now().strftime("%Y%m%d")

    key = sample_id if sample_id else f"{test_date}|{normalized_name}"
    result[key] = {
        'time': test_time,
        'sample_id': sample_id,
        'name': name,
        'obr_seq': obr_seq,
        'tests': tests,
        'abnormal': has_ab,
    }
    return result


def refresh_patient_list(ptree, rtree, status_var,
                         date_from_var, date_to_var, patients_data):
    status_var.set("Yuklanmoqda...")
    ptree.delete(*ptree.get_children())
    rtree.delete(*rtree.get_children())

    files = load_raw_files(
        date_from_var.get().strip() or None,
        date_to_var.get().strip()   or None
    )
    # Eski → yangi tartibda (merge da eng oxirgi natija qolishi uchun)
    files.sort(key=os.path.getmtime)

    if not files:
        status_var.set("Fayllar topilmadi")
        messagebox.showinfo("Ma'lumot",
            "BK-280 RAW fayllari topilmadi.\n\nQidirilgan papkalar:\n" +
            "\n".join(f"  • {p}" for p in BK280_RAW_PATHS))
        return

    patients_data.clear()

    def _merge_patient(ex, info):
        """Birlashtirish: testlar merge, bir xil LIS code 2 marta kelsa eng oxirgi qolsin (fayllar eski→yangi tartibda)."""
        for code, td in info['tests'].items():
            ex['tests'][code] = td
        if not ex['name'] and info['name']:
            ex['name'] = info['name']
        if info['abnormal']:
            ex['abnormal'] = True
        try:
            if datetime.strptime(info['time'], "%d.%m.%Y %H:%M") > datetime.strptime(ex['time'], "%d.%m.%Y %H:%M"):
                ex['time'] = info['time']
        except Exception:
            pass

    for fp in files:
        parsed = parse_hl7_file(fp)
        for key, info in parsed.items():
            info['file_path'] = fp  # fayl yo'lini saqlash
            if key not in patients_data:
                patients_data[key] = info
            else:
                _merge_patient(patients_data[key], info)
                patients_data[key]['file_path'] = fp  # eng oxirgi fayl

    def sort_key_asc(sid):
        p = patients_data[sid]
        # To'liq sana+vaqt bo'yicha o'sib ketish (eng eski birinchi → №1)
        try:
            dt = datetime.strptime(p['time'], "%d.%m.%Y %H:%M")
        except Exception:
            dt = datetime.min
        try:
            seq = int(p.get('obr_seq', 9999))
        except (ValueError, TypeError):
            seq = 9999
        return (dt, seq)

    # Eski→yangi tartibda saralab, har biriga tartib raqam beramiz
    sorted_sids = sorted(patients_data, key=sort_key_asc)
    for i, sid in enumerate(sorted_sids):
        patients_data[sid]['_display_num'] = i + 1  # 1=eng eski

    # Eng yangi yuqorida bo'lishi uchun position=0 ga qo'shamiz (stack usuli)
    for sid in sorted_sids:
        p = patients_data[sid]
        ptree.insert("", 0, values=(
            p['time'], sid, p.get('name', ''),
            p['_display_num']
        ))


    status_var.set(f"Yuklandi: {len(patients_data)} ta bemor ({len(files)} ta fayl)")


def show_patient_results(ptree, rtree, event, patients_data):
    rtree.delete(*rtree.get_children())
    sel = ptree.selection()
    if not sel:
        return
    vals = ptree.item(sel[0], 'values')
    if not vals or len(vals) < 2:
        return
    sid = str(vals[1])
    if sid not in patients_data:
        return
    tests = patients_data[sid].get('tests', {})
    for key in sorted(tests, key=lambda k: int(k) if str(k).isdigit() else 9999):
        t = tests[key]
        flag = t.get('flag', '').strip().upper()
        value = t.get('value', '')
        lis_code = t.get('lis_code', key)
        if flag in ('H', 'HH'):
            display_value = f"↑ {value}"
            row_tag = "high"
        elif flag in ('L', 'LL'):
            display_value = f"↓ {value}"
            row_tag = "low"
        else:
            display_value = value
            row_tag = "normal_res"
        ref = t.get('ref', '').replace('~', ' - ')
        rtree.insert("", tk.END, values=(
            lis_code, t.get('name', ''),
            display_value, t.get('unit', ''),
            ref, flag
        ), tags=(row_tag,))


def save_patient_to_db(ptree, status_var, patients_data):
    sel = ptree.selection()
    if not sel:
        messagebox.showwarning("Diqqat", "Avval bemorni tanlang")
        return
    vals = ptree.item(sel[0], 'values')
    sid  = str(vals[1]) if vals and len(vals) > 1 else ''
    if not sid or sid not in patients_data:
        messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi")
        return
    _do_save(patients_data[sid], status_var)


def save_all_patients_to_db(patients_data, status_var):
    if not patients_data:
        messagebox.showwarning("Diqqat", "Saqlash uchun bemorlar yo'q")
        return
    if not messagebox.askyesno("Tasdiqlash",
            f"{len(patients_data)} ta bemor natijalarini saqlash?\n"
            "Faqat bazada buyurtma bor bemorlar saqlanadi."):
        return
    saved, not_found, errors = 0, [], []
    for sid, info in patients_data.items():
        r = _do_save(info, status_var, silent=True)
        if r == 'saved':      saved += 1
        elif r == 'not_found': not_found.append(f"ID:{sid} ({info.get('name','?')})")
        elif r == 'error':     errors.append(f"ID:{sid}")
    msg = f"✅ Saqlandi: {saved} ta\n"
    if not_found: msg += f"\n⚠️ Topilmadi ({len(not_found)}):\n" + "\n".join(not_found[:10])
    if errors:    msg += f"\n❌ Xatolik ({len(errors)}):\n" + "\n".join(errors[:5])
    messagebox.showinfo("Natija", msg)
    status_var.set(f"Saqlandi: {saved} ta, topilmadi: {len(not_found)} ta")


def _do_save(patient_info, status_var, silent=False):
    if not DB_AVAILABLE:
        if not silent: messagebox.showerror("Xato", "MySQL moduli yo'q!")
        return 'no_db'

    sid   = patient_info.get('sample_id', '')
    name  = patient_info.get('name', '')
    tests = patient_info.get('tests', {})
    if not tests:
        return 'error'

    conn = db_conn()
    if not conn:
        if not silent:
            messagebox.showerror("DB Xato",
                f"MySQL ga ulanib bo'lmadi!\nServer: {DB_CONFIG.get('host')}")
        return 'error'

    try:
        cur = conn.cursor(dictionary=True)

        # Barcode bo'yicha topish: orders.sample_id = '260225001064'
        cur.execute("""
            SELECT o.id AS order_id, b.fish
            FROM orders o
            INNER JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sample_id = %s
               OR o.id = %s
            ORDER BY o.sana_vaqt DESC LIMIT 1
        """, (sid, sid if str(sid).isdigit() else '0'))

        row = cur.fetchone()
        if not row:
            if not silent:
                messagebox.showwarning("Topilmadi",
                    f"Barcode: {sid}\n"
                    f"Bemor nomi: {name}\n\n"
                    f"Bu barcode (sample_id) bazada topilmadi.\n\n"
                    f"❗ Yechim:\n"
                    f"BK-280 da «Primer shtrix-kod» maydoniga\n"
                    f"barcode skaneri bilan monoblokdagi\n"
                    f"sample_id ni kiriting.\n\n"
                    f"Yoki monoblokda orders.sample_id = {sid}\n"
                    f"bo'lgan buyurtma yarating.")
            cur.close(); conn.close()
            return 'not_found'

        order_id = row['order_id']
        db_name  = row.get('fish', name)

        if not silent:
            if not messagebox.askyesno("Tasdiqlash",
                    f"Analyzer: {name}\n"
                    f"Barcode: {sid}\n"
                    f"Baza: {db_name} (Order: {order_id})\n"
                    f"Natijalar: {len(tests)} ta\n\nSaqlash?"):
                cur.close(); conn.close()
                return 'cancelled'

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # DIQQAT (2026-08-19): bu yerda status='ready' QO'YILMAYDI.
        # BK-280 bioximiya natijasi kelishi — buyurtmadagi qon/siydik/IFA
        # tahlillari ham tayyor degani emas. Holatni natija_tugallik hisoblaydi.
        cur.execute("SELECT id FROM results WHERE order_id=%s", (order_id,))
        res_row = cur.fetchone()
        if res_row:
            result_id = res_row['id']
            cur.execute("UPDATE results SET updated_at=%s WHERE id=%s",
                        (now, result_id))
        else:
            cur.execute("INSERT INTO results(order_id,status,created_at,updated_at)"
                        " VALUES(%s,'draft',%s,%s)", (order_id, now, now))
            result_id = cur.lastrowid

        saved_count = 0
        for code, td in tests.items():
            val = td.get('value', '')
            if not val: continue
            tn   = td.get('name', f"Kod:{code}")
            unit = td.get('unit', '')
            ref  = td.get('ref', '')
            flag = td.get('flag', '')
            lis  = td.get('lis_code', code)

            cur.execute("DELETE FROM result_items WHERE result_id=%s AND tahlil_nomi=%s",
                        (result_id, tn))
            cur.execute("INSERT INTO result_items(result_id,tahlil_nomi,qiymat,birlik,norma,note)"
                        " VALUES(%s,%s,%s,%s,%s,%s)",
                        (result_id, tn, val, unit, ref,
                         f"BK-280|LIS:{lis}|{now}|Flag:{flag}"))

            rj = json.dumps({'result':val,'unit':unit,'ref':ref,'flag':flag,
                             'lis_code':lis,'source':'BK-280','sample_id':sid},
                            ensure_ascii=False)
            cur.execute("INSERT INTO test_results(order_id,test_name,test_type,result_data,status)"
                        " VALUES(%s,%s,'numeric',%s,'Saqlandi')"
                        " ON DUPLICATE KEY UPDATE"
                        " result_data=VALUES(result_data),status='Saqlandi',"
                        " updated_at=CURRENT_TIMESTAMP",
                        (str(order_id), tn, rj))
            saved_count += 1

        try:
            cur.execute("UPDATE orders SET updated_at=%s WHERE id=%s", (now, order_id))
        except Exception:
            pass

        # Natija holatini QAYTA HISOBLASH (buyurtmadagi hamma tahlil bajarilsa 'ready')
        try:
            from natija_tugallik import natija_holatini_yangila
            natija_holatini_yangila(cur, order_id, vaqt=now)
        except Exception as _he:
            print(f"[OGOHLANTIRISH] natija holati hisoblanmadi: {_he}")

        conn.commit()

        if not silent:
            messagebox.showinfo("Muvaffaqiyat",
                f"✅ Saqlandi!\nBemor: {db_name}\n"
                f"Order: {order_id}\nNatijalar: {saved_count} ta")
        if status_var:
            status_var.set(f"✅ {db_name} (Order:{order_id}, {saved_count} ta)")
        return 'saved'

    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        if not silent: messagebox.showerror("Xatolik", f"Saqlashda xato:\n{e}")
        import traceback; traceback.print_exc()
        return 'error'
    finally:
        try: cur.close(); conn.close()
        except Exception: pass
