# -*- coding: utf-8 -*-
"""
Siydik (URIT-50) - RAW fayllarni ko'rsatish oynasi
Canvas-based table: per-cell coloring, 1520x790
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import glob
import re

try:
    import mysql.connector
    from monoblok_db_config import DB_CONFIG
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

URIT_RAW_PATH = r"G:\DASTUR\URIT 50\Urit\RAW_LOGS"
URIT_PREFS_FILE = r"G:\DASTUR\URIT 50\urit_prefs.json"

def _load_strip_pref():
    """Oxirgi tanlangan poloska turini fayldan yuklash (0=Avto, 11=11-param, 14=14-param)."""
    try:
        import json
        with open(URIT_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get('strip', 0)
    except Exception:
        return 0

def _save_strip_pref(val):
    """Tanlangan poloska turini faylga saqlash."""
    try:
        import json
        os.makedirs(os.path.dirname(URIT_PREFS_FILE), exist_ok=True)
        with open(URIT_PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'strip': val}, f)
    except Exception:
        pass

ANALYTES = ['LEU','KET','NIT','URO','BIL','GLU','PRO','SG','PH','BLD','Vc','MA','Ca','CR','ACR']

# 11-parametrli poloskalar: faqat asosiy ko'rsatkichlar
ANALYTES_11 = ['LEU','KET','NIT','URO','BIL','GLU','PRO','SG','PH','BLD','Vc']

PARAM_NAMES = {
    'LEU': 'Leykotsit', 'KET': 'Keton', 'NIT': 'Nitritlar',
    'URO': 'Urobilinogen', 'BIL': 'Bilirubin', 'GLU': 'Glyukoza',
    'PRO': 'Oqsil', 'SG': 'Nisbiy zich.', 'PH': 'pH',
    'BLD': 'Qon', 'Vc': 'Askorbin', 'MA': 'Mikroalbumin',
    'Ca': 'Kalsiy', 'CR': 'Kreatinin', 'ACR': 'MA/CR nisbati'
}


def detect_strip_type(sdata):
    """MA satri faylda mavjud bo'lsa — 14-param, bo'lmasa — 11-param.
    Natija qiymatiga qaralmas — faqat MA satri borligiga qaraladi.
    """
    return 14 if sdata.get('MA', '').strip() else 11

INFO_WIDTHS = [130, 60, 120, 155]   # Sana/Vaqt, Sample NO, Sample ID, F.I.SH
ANALYTE_W   = 67
ROW_H  = 20
HDR_H  = 24


class CanvasTable(tk.Frame):
    def __init__(self, parent, columns, col_widths):
        super().__init__(parent, bg='white')
        self.columns    = columns
        self.col_widths = col_widths
        self.total_w    = sum(col_widths)
        self._row_count = 0

        # Header
        hdr = tk.Canvas(self, height=HDR_H, bg='#1a2940', highlightthickness=0)
        hdr.pack(fill=tk.X, side=tk.TOP)
        x = 0
        for col, w in zip(columns, col_widths):
            hdr.create_rectangle(x, 0, x+w, HDR_H, fill='#1a2940', outline='#2c4060')
            hdr.create_text(x+w//2, HDR_H//2, text=col,
                            fill='white', font=('Arial', 8, 'bold'), anchor='center')
            x += w

        # Body
        body = tk.Frame(self, bg='white')
        body.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        self.canvas = tk.Canvas(body, bg='white', highlightthickness=0)
        vs = ttk.Scrollbar(body, orient=tk.VERTICAL,   command=self.canvas.yview)
        hs = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<Button-4>',   self._wheel)
        self.canvas.bind('<Button-5>',   self._wheel)

    def _wheel(self, e):
        delta = -1 if (getattr(e,'delta',0) > 0 or getattr(e,'num',0) == 4) else 1
        self.canvas.yview_scroll(delta, 'units')

    def clear(self):
        self.canvas.delete('all')
        self._row_count = 0

    def add_row(self, values, abnormal_indices=None):
        if abnormal_indices is None:
            abnormal_indices = set()
        idx = self._row_count
        y0  = idx * ROW_H
        y1  = y0 + ROW_H
        row_bg = '#fff5f5' if abnormal_indices else ('#f9f9f9' if idx%2==0 else 'white')
        x = 0
        for ci, (val, w) in enumerate(zip(values, self.col_widths)):
            self.canvas.create_rectangle(x, y0, x+w, y1,
                                          fill=row_bg, outline='#e2e2e2')
            if ci < 4:
                color  = '#000000'
                fnt    = ('Arial', 8, 'bold') if ci==3 else ('Arial', 8)
                anchor = 'w' if ci==3 else 'center'
                tx     = x+4 if ci==3 else x+w//2
            elif ci in abnormal_indices:
                color  = '#cc0000'
                fnt    = ('Arial', 8, 'bold')
                anchor = 'center'
                tx     = x+w//2
            else:
                color  = '#222222'
                fnt    = ('Arial', 8)
                anchor = 'center'
                tx     = x+w//2
            self.canvas.create_text(tx, y0+ROW_H//2, text=str(val) if val else '',
                                     fill=color, font=fnt, anchor=anchor)
            x += w
        self._row_count += 1
        self.canvas.configure(scrollregion=(0, 0, self.total_w, self._row_count*ROW_H))


# ── DB ────────────────────────────────────────────────────────────
def get_patient_name_from_db(sample_id):
    if not DB_AVAILABLE or not sample_id:
        return ''
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur  = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT b.fish FROM orders o
            INNER JOIN bemorlar b ON o.bemor_id=b.id
            WHERE o.sample_id=%s ORDER BY o.sana_vaqt DESC LIMIT 1
        """, (sample_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return row['fish'] if row else ''
    except Exception:
        return ''


# ── Oyna ──────────────────────────────────────────────────────────
def open_window(parent=None, on_import_callback=None):
    """Siydik oynasini ochish.
    on_import_callback(sample_id, patient_info) → int  — asosiy oynaga natija o'tkazish uchun
    """
    import copy

    window = tk.Toplevel(parent)
    window.title("Siydik - URIT-50 RAW Ma'lumotlar")
    window.geometry("1520x790")
    window.minsize(1200, 600)

    # ── Closure state ─────────────────────────────────────────────────
    all_samples      = {}     # {sno: sdata}
    edited_values    = {}     # {sno: {analyte_code: yangi_qiymat}}
    current_sno      = [None]
    result_entry_ref = [None]
    # 0=avto, 11=11-param, 14=14-param
    strip_override   = [0]

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

    # ── Strip turi tanlash ──────────────────────────────────────────────
    ttk.Separator(center_control, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
    ttk.Label(center_control, text="Poloskа:").pack(side=tk.LEFT)
    _saved_strip = _load_strip_pref()
    strip_var = tk.IntVar(value=_saved_strip)
    strip_override[0] = _saved_strip  # boshlang'ich qiymatni ham o'rnatish

    def _on_strip_change():
        val = strip_var.get()
        strip_override[0] = val
        _save_strip_pref(val)
        _show_results()

    tk.Radiobutton(center_control, text="Avto", variable=strip_var, value=0,
                   command=_on_strip_change).pack(side=tk.LEFT, padx=2)
    tk.Radiobutton(center_control, text="11-param", variable=strip_var, value=11,
                   command=_on_strip_change).pack(side=tk.LEFT, padx=2)
    tk.Radiobutton(center_control, text="14-param", variable=strip_var, value=14,
                   command=_on_strip_change).pack(side=tk.LEFT, padx=2)

    strip_label_var = tk.StringVar(value="")
    ttk.Label(center_control, textvariable=strip_label_var,
              foreground="blue", font=("Arial", 8, "italic")).pack(side=tk.LEFT, padx=4)

    right_control = ttk.Frame(control_frame)
    right_control.pack(side=tk.RIGHT, padx=5)
    status_var = tk.StringVar(value="Tayyor")
    ttk.Label(right_control, textvariable=status_var).pack(side=tk.LEFT, padx=5)

    # ── 2 panelli kontent ─────────────────────────────────────────────
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # ===== CHAP PANEL: BEMORLAR RO'YXATI =====
    left_panel = ttk.LabelFrame(content_frame, text="Bemorlar Ro'yxati", padding="5")
    left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
    left_panel.config(width=540)

    patient_cols = ("Sana/Vaqt", "Sample NO", "Sample ID", "F.I.SH", "Status")
    patient_tree = ttk.Treeview(left_panel, columns=patient_cols, show="headings", height=30)
    patient_tree.heading("Sana/Vaqt",  text="Sana/Vaqt")
    patient_tree.column("Sana/Vaqt",  width=145, anchor=tk.CENTER)
    patient_tree.heading("Sample NO",  text="Sample NO")
    patient_tree.column("Sample NO",  width=80,  anchor=tk.CENTER)
    patient_tree.heading("Sample ID",  text="Sample ID")
    patient_tree.column("Sample ID",  width=110, anchor=tk.CENTER)
    patient_tree.heading("F.I.SH",    text="F.I.SH")
    patient_tree.column("F.I.SH",    width=160, anchor=tk.W)
    patient_tree.heading("Status",    text="Status")
    patient_tree.column("Status",    width=80,  anchor=tk.CENTER)

    pt_scroll = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=patient_tree.yview)
    patient_tree.configure(yscrollcommand=pt_scroll.set)
    patient_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    pt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ===== O'NG PANEL: NATIJALAR =====
    right_panel = ttk.LabelFrame(
        content_frame,
        text="Tahlil Natijalari  \u270f Natijani o'zgartirish uchun ikki marta bosing",
        padding="5"
    )
    right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

    results_cols = ("No.", "Tahlil nomi", "Natija")
    results_tree = ttk.Treeview(right_panel, columns=results_cols, show="headings", height=30)
    results_tree.heading("No.",        text="No.")
    results_tree.column("No.",        width=50,  anchor=tk.CENTER)
    results_tree.heading("Tahlil nomi", text="Tahlil nomi")
    results_tree.column("Tahlil nomi", width=200, anchor=tk.W)
    results_tree.heading("Natija",     text="Natija \u270f")
    results_tree.column("Natija",     width=250, anchor=tk.W)

    results_tree.tag_configure("abnormal", foreground="red",   font=("Arial", 9, "bold"))
    results_tree.tag_configure("normal",   foreground="black")
    results_tree.tag_configure("edited",   foreground="#006600", font=("Arial", 9, "bold"))

    rt_scroll = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=rt_scroll.set)
    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    rt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

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
        if col != "#3":   # faqat Natija ustuni
            return
        row_id = results_tree.identify_row(event.y)
        if not row_id:
            return
        bbox = results_tree.bbox(row_id, "#3")
        if not bbox:
            return

        _close_entry()

        values     = results_tree.item(row_id, "values")
        code_tag   = results_tree.item(row_id, "tags")
        analyte_code = code_tag[0] if code_tag else ''
        raw_val    = values[2] if len(values) > 2 else ''

        entry = tk.Entry(results_tree, font=("Arial", 10), justify="left",
                         relief=tk.SOLID, borderwidth=1)
        entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        entry.insert(0, raw_val)
        entry.select_range(0, tk.END)
        entry.focus()
        result_entry_ref[0] = entry

        def _save_edit(event=None):
            new_val = entry.get().strip()
            _close_entry()
            sno = current_sno[0]
            if not sno or not new_val:
                return
            if analyte_code:
                edited_values.setdefault(sno, {})[analyte_code] = new_val
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
    def _show_results(event=None):
        _close_entry()
        results_tree.delete(*results_tree.get_children())
        sel = patient_tree.selection()
        if not sel:
            current_sno[0] = None
            strip_label_var.set("")
            return
        sno = sel[0]   # iid = fayl nomi (unikal kalit)
        current_sno[0] = sno
        if sno not in all_samples:
            return
        sdata = all_samples[sno]
        edits = edited_values.get(sno, {})
        ab_set = set(sdata.get('abnormal_params', []))

        # Strip turi aniqlash
        auto_type = sdata.get('strip_type', 14)
        override  = strip_override[0]
        active_type = override if override in (11, 14) else auto_type
        active_analytes = ANALYTES_11 if active_type == 11 else ANALYTES
        strip_label_var.set(f"(avto: {auto_type}-param)")

        no = 1
        for code in active_analytes:
            if code in edits:
                val     = edits[code]
                row_tag = "edited"
            else:
                val     = str(sdata.get(code, '')).strip()
                if not val:
                    continue
                row_tag = "abnormal" if code in ab_set else "normal"
            name = PARAM_NAMES.get(code, code)
            results_tree.insert("", tk.END,
                                 values=(str(no), name, val),
                                 tags=(code, row_tag))
            no += 1

    # ══════════════════════════════════════════════════════════════════
    #  NATIJANI QO'SHISH — asosiy oynaga o'tkazish
    # ══════════════════════════════════════════════════════════════════
    def import_to_main():
        if not on_import_callback:
            messagebox.showinfo(
                "Ma'lumot",
                "Bu funksiya faqat asosiy oynaning 'Siydik' tugmasi orqali\n"
                "ochilganda ishlaydi."
            )
            return
        sel = patient_tree.selection()
        if not sel:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        sno = sel[0]   # iid = fayl nomi (unikal kalit)
        if sno not in all_samples:
            messagebox.showwarning("Diqqat", "Bemor ma'lumotlari topilmadi!")
            return

        sdata = copy.deepcopy(all_samples[sno])
        edits = edited_values.get(sno, {})

        # Strip turi aniqlash (import uchun)
        auto_type = sdata.get('strip_type', 14)
        override  = strip_override[0]
        active_type = override if override in (11, 14) else auto_type
        active_analytes = ANALYTES_11 if active_type == 11 else ANALYTES

        # Tests dict qurish — faqat aktiv analitlar
        tests = {}
        for code in active_analytes:
            val = edits.get(code) or str(sdata.get(code, '')).strip()
            if val:
                tests[code] = {
                    'name':  PARAM_NAMES.get(code, code),
                    'value': val,
                    'code':  code
                }

        pinfo = {
            'name':      sdata.get('patient_name', sdata.get('sample_no', sno)),
            'sample_id': sdata.get('sample_id', ''),
            'sample_no': sdata.get('sample_no', ''),   # 000031 kabi haqiqiy raqam
            'tests':     tests,
            'strip_type': active_type,
            'abnormal_params': list(sdata.get('abnormal_params', [])),
        }

        try:
            count = on_import_callback(sdata.get('sample_id', ''), pinfo)
            name  = pinfo['name'] or sno
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

    # ── Tugmalar ──────────────────────────────────────────────────────
    # 1) Natijani qo'shish (yashil, birinchi)
    import_btn_state = tk.NORMAL if on_import_callback else tk.DISABLED
    import_btn_bg    = "#28a745" if on_import_callback else "#aaaaaa"
    tk.Button(
        left_control,
        text="\u2b06 Natijani qo'shish",
        command=import_to_main,
        bg=import_btn_bg, fg="white",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=10, pady=3,
        cursor="hand2",
        state=import_btn_state
    ).pack(side=tk.LEFT, padx=(0, 12))

    # 2) Yangilash
    def do_refresh():
        _close_entry()
        refresh_samples(patient_tree, status_var, date_from_var, date_to_var, all_samples)
        results_tree.delete(*results_tree.get_children())
        current_sno[0] = None

    ttk.Button(left_control, text="\U0001f504 Yangilash",
               command=do_refresh).pack(side=tk.LEFT, padx=5)

    # ── Helper functions ───────────────────────────────────────────────
    def _get_selected_patient():
        sel = patient_tree.selection()
        if not sel:
            return None, None
        sno = sel[0]   # iid = fayl nomi (unikal kalit)
        sdata = all_samples.get(sno)
        return sno, sdata

    def _rewrite_urit_txt(file_path, new_sample_id=None, edited_vals=None):
        """URIT-50 plain text faylini yangilash (ID satri va analitlar)."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                lc = line.strip()
                # ID satrini yangilash
                if new_sample_id is not None and lc.startswith('ID:'):
                    new_lines.append(f"ID:{new_sample_id}\n")
                    continue
                # Analitik qiymatlarni yangilash
                if edited_vals:
                    matched_code = None
                    line_no_star = line.replace('*', '')
                    for code in ANALYTES:
                        if re.search(r'\b' + re.escape(code) + r'\b', line_no_star, re.IGNORECASE):
                            matched_code = code
                            break
                    if matched_code and matched_code in edited_vals:
                        m = re.search(r'\b' + re.escape(matched_code) + r'\b',
                                      line_no_star, re.IGNORECASE)
                        if m:
                            prefix = line[:m.end()]
                            new_val = edited_vals[matched_code]
                            new_lines.append(f"{prefix}  {new_val}\n")
                            continue
                new_lines.append(line)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            messagebox.showerror("Xato", f"Faylni yangilashda xato:\n{e}")
            return False

    def _delete_patient():
        sno, sdata = _get_selected_patient()
        if not sdata:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        fp = sdata.get('file_path', '')
        if not fp or not os.path.exists(fp):
            messagebox.showerror("Xato", "Fayl topilmadi!")
            return
        sid = sdata.get('sample_id', sno)
        if not messagebox.askyesno("O'chirish",
                                   f"'{sid}' faylini o'chirasizmi?\n{fp}"):
            return
        try:
            os.remove(fp)
            del all_samples[sno]
            # Treeviewdan olib tashlash
            for item in patient_tree.get_children():
                if patient_tree.item(item, "values")[1] == sno:
                    patient_tree.delete(item)
                    break
            results_tree.delete(*results_tree.get_children())
            current_sno[0] = None
            status_var.set(f"O'chirildi: {fp}")
            window.lift()
            window.focus_force()
        except Exception as e:
            messagebox.showerror("Xato", f"O'chirishda xato:\n{e}")
            window.lift()
            window.focus_force()

    def _edit_patient():
        sno, sdata = _get_selected_patient()
        if not sdata:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        fp = sdata.get('file_path', '')
        if not fp or not os.path.exists(fp):
            messagebox.showerror("Xato", "Fayl topilmadi!")
            return

        dlg = tk.Toplevel(window)
        dlg.title("Bemor ma'lumotlarini tahrirlash")
        dlg.geometry("380x140")
        dlg.resizable(False, False)
        dlg.grab_set()

        ttk.Label(dlg, text="Sample ID:").grid(row=0, column=0, padx=10, pady=8, sticky="e")
        sid_var = tk.StringVar(value=sdata.get('sample_id', ''))
        ttk.Entry(dlg, textvariable=sid_var, width=28).grid(row=0, column=1, padx=10, pady=8)

        def _apply():
            new_sid = sid_var.get().strip()
            if not _rewrite_urit_txt(fp, new_sample_id=new_sid or None):
                return
            if new_sid:
                sdata['sample_id'] = new_sid
                # DB dan ism yangilash
                sdata['patient_name'] = get_patient_name_from_db(new_sid)
            # Treeview satrini yangilash
            for item in patient_tree.get_children():
                if patient_tree.item(item, "values")[1] == sno:
                    patient_tree.item(item, values=(
                        sdata.get('time', ''),
                        sno,
                        sdata.get('sample_id', ''),
                        sdata.get('patient_name', ''),
                        patient_tree.item(item, "values")[4]
                    ))
                    break
            status_var.set("Saqlandi")
            dlg.destroy()
            window.lift()
            window.focus_force()

        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Saqlash", command=_apply).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Bekor", command=dlg.destroy).pack(side=tk.LEFT, padx=8)

    def _save_to_txt():
        sno, sdata = _get_selected_patient()
        if not sdata:
            messagebox.showwarning("Diqqat", "Avval bemorni tanlang!")
            return
        fp = sdata.get('file_path', '')
        if not fp or not os.path.exists(fp):
            messagebox.showerror("Xato", "Fayl topilmadi!")
            return
        ev = edited_values.get(sno, {})
        if not ev:
            messagebox.showinfo("Ma'lumot", "O'zgartirilgan qiymat yo'q.")
            return
        if _rewrite_urit_txt(fp, edited_vals=ev):
            status_var.set(f"Saqlandi: {os.path.basename(fp)}")
            messagebox.showinfo("Muvaffaqiyat", "O'zgarishlar TXT faylga saqlandi!")
            window.lift()
            window.focus_force()

    # 3) O'chirish
    tk.Button(
        left_control, text="🗑 O'chirish",
        command=_delete_patient,
        bg="#dc3545", fg="white",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=8, pady=3, cursor="hand2"
    ).pack(side=tk.LEFT, padx=4)

    # 4) Taxrirlash
    tk.Button(
        left_control, text="✏ Taxrirlash",
        command=_edit_patient,
        bg="white", fg="#28a745",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=8, pady=3, cursor="hand2",
        highlightbackground="#28a745", highlightthickness=1
    ).pack(side=tk.LEFT, padx=4)

    # 5) Saqlash (TXT ga)
    tk.Button(
        left_control, text="💾 Saqlash",
        command=_save_to_txt,
        bg="white", fg="#28a745",
        font=("Arial", 10, "bold"),
        relief=tk.RAISED, padx=8, pady=3, cursor="hand2",
        highlightbackground="#28a745", highlightthickness=1
    ).pack(side=tk.LEFT, padx=4)

    # ── Event binding ─────────────────────────────────────────────────
    patient_tree.bind("<<TreeviewSelect>>", _show_results)

    do_refresh()
    return window


# ── Fayllarni yuklash ─────────────────────────────────────────────
def load_raw_files(date_from=None, date_to=None):
    if not os.path.exists(URIT_RAW_PATH):
        return []
    # Rekursiv qidirish (oylik papkalar + root) — set() bilan takrorlanishni oldini olamiz
    seen = set()
    all_files = []
    for fp in glob.glob(os.path.join(URIT_RAW_PATH, "**", "urit_raw_*.txt"), recursive=True):
        norm = os.path.normpath(fp)
        if norm not in seen:
            seen.add(norm)
            all_files.append(norm)
    if date_from and date_to:
        try:
            fd = datetime.strptime(date_from, "%d.%m.%Y").date()
            td = datetime.strptime(date_to,   "%d.%m.%Y").date()
            filtered = []
            for fp in all_files:
                m = re.search(r'urit_raw_(\d{4})(\d{2})(\d{2})_', os.path.basename(fp))
                if m:
                    yr, mo, dy = m.groups()
                    if fd <= date(int(yr), int(mo), int(dy)) <= td:
                        filtered.append(fp)
            all_files = filtered
        except Exception:
            pass
    all_files.sort(key=lambda fp: os.path.basename(fp), reverse=True)
    return all_files   # limit yo'q — barcha fayllar


def parse_result(file_path):
    result_dict = {}
    try:
        with open(file_path,'r',encoding='utf-8',errors='ignore') as f:
            content = f.read()
        fn = os.path.basename(file_path)
        m  = re.search(r'urit_raw_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', fn)
        if m:
            yr,mo,dy,hh,mm,ss = m.groups()
            time_str = f"{dy}.{mo}.{yr} {hh}:{mm}:{ss}"
        else:
            time_str = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%d.%m.%Y %H:%M:%S")

        lines     = [ln.strip("\r") for ln in content.splitlines()]
        sample_no = ''; date_time = ''; sample_id = ''

        for line in lines:
            lc = line.strip()
            if not lc: continue
            if lc.startswith('NO.'):
                m2 = re.search(r'NO\.(\d+)', lc)
                if m2: sample_no = m2.group(1)
            if lc.startswith('ID:'):
                sample_id = lc.replace('ID:','').strip()
            if 'DATE' in lc or 'TIME' in lc:
                m3 = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', lc)
                if m3:
                    dp,tp = m3.groups(); pt = dp.split('-')
                    if len(pt)==3: date_time = f"{pt[2]}.{pt[1]}.{pt[0]} {tp}"

        final_no = sample_no or sample_id or ''
        # final_no bo'sh bo'lsa ham faylni o'tkazib yubormaymiz — fname_key kalit bo'ladi

        # Fayl nomi — unikal kalit (sample_no qayta-qayta 000001 dan boshlanishi mumkin)
        fname_key = re.sub(r'\.txt$', '', os.path.basename(file_path))

        result_dict[fname_key] = {
            'time': date_time or time_str,
            'sample_no': final_no,    # ko'rsatish uchun (000031 kabi)
            'sample_id': sample_id, 'patient_name': '', 'abnormal_params': [],
            'strip_type': 14,  # after parsing analytes, will be recalculated below
            'file_path': file_path
        }
        for code in ANALYTES:
            result_dict[fname_key][code] = ''

        for i,line in enumerate(lines):
            starred = '*' in line
            line_ns = line.replace('*','')
            for analyte in ANALYTES:
                if re.search(r'\b'+re.escape(analyte)+r'\b', line_ns, re.IGNORECASE):
                    parts = re.split(r'\b'+re.escape(analyte)+r'\b',
                                     line_ns, maxsplit=1, flags=re.IGNORECASE)
                    if len(parts)<2: continue
                    raw_after = parts[1]
                    after = raw_after.strip(' :-\t')
                    j = i+1
                    while j<len(lines) and not any(
                        re.search(r'\b'+re.escape(a)+r'\b',lines[j],re.IGNORECASE)
                        for a in ANALYTES
                    ):
                        after += ' '+lines[j].replace('*','').strip(); j+=1
                    after = after.replace('CELL/uL','CELL/µL').strip()
                    # NIT (va boshqa) uchun manfiy natija: '-' belgisini saqlash
                    if not after and '-' in raw_after:
                        after = '-'
                    result_dict[fname_key][analyte] = after
                    # Patologiya aniqlash: faqat * (analizator belgisi) yoki + (musbat natija)
                    # '<' va '>' belgilar detection limit bo'lib, patologiya emas
                    is_ab = (starred or '+' in after) \
                            and 'Normal' not in after and 'normal' not in after
                    if is_ab and analyte not in result_dict[fname_key]['abnormal_params']:
                        result_dict[fname_key]['abnormal_params'].append(analyte)
                    break
        # Strip turini analiz qilingan qiymatlar asosida aniqlash
        if fname_key in result_dict:
            result_dict[fname_key]['strip_type'] = detect_strip_type(result_dict[fname_key])
    except Exception as e:
        print(f"⚠️ Parse xato: {file_path} — {e}")
    return result_dict


def refresh_samples(patient_tree, status_var, date_from_var, date_to_var, all_samples):
    """Bemorlar ro'yxatini yangilash (yangi split-panel dizayn uchun)"""
    status_var.set("Yuklanmoqda...")
    patient_tree.delete(*patient_tree.get_children())
    df = date_from_var.get().strip()
    dt = date_to_var.get().strip()
    files = load_raw_files(df or None, dt or None)
    if not files:
        status_var.set("Fayllar topilmadi")
        messagebox.showinfo("Ma'lumot",
                            "URIT-50 RAW fayllari topilmadi.\nPapka: " + URIT_RAW_PATH)
        return

    all_samples.clear()
    for fp in files:
        for fname_key, sdata in parse_result(fp).items():
            all_samples[fname_key] = sdata   # fayl nomi unikal — dedup shart emas

    for sno in sorted(all_samples.keys(), reverse=True):
        sdata = all_samples[sno]
        sid = sdata.get('sample_id', '')
        if sid:
            sdata['patient_name'] = get_patient_name_from_db(sid)
        ab = bool(sdata.get('abnormal_params'))
        status = "ABNORMAL" if ab else "NORMAL"
        patient_tree.insert("", tk.END, iid=sno, values=(
            sdata.get('time', ''),
            sdata.get('sample_no', ''),   # 000031 kabi — ko'rsatish uchun
            sid,
            sdata.get('patient_name', ''),
            status
        ))

    status_var.set(f"Yuklandi: {len(all_samples)} ta natija | {len(files)} ta fayl")


def refresh(table, status_var, date_from_var, date_to_var):
    status_var.set("Yuklanmoqda...")
    table.clear()
    df = date_from_var.get().strip()
    dt = date_to_var.get().strip()
    files = load_raw_files(df or None, dt or None)
    if not files:
        status_var.set("Fayllar topilmadi")
        messagebox.showinfo("Ma'lumot",
                            "URIT-50 RAW fayllari topilmadi.\nPapka: "+URIT_RAW_PATH)
        return

    all_samples = {}
    for fp in files:
        for sno, sdata in parse_result(fp).items():
            if sno not in all_samples:
                all_samples[sno] = sdata
            else:
                try:
                    ot = datetime.strptime(all_samples[sno]['time'],"%d.%m.%Y %H:%M:%S")
                    nt = datetime.strptime(sdata['time'],           "%d.%m.%Y %H:%M:%S")
                    if nt > ot: all_samples[sno] = sdata
                except Exception:
                    all_samples[sno] = sdata

    for sno, sdata in all_samples.items():
        sid = sdata.get('sample_id','')
        if sid: sdata['patient_name'] = get_patient_name_from_db(sid)

    total = 0
    for sno in sorted(all_samples.keys(), reverse=True):
        sdata  = all_samples[sno]
        ab_set = set(sdata.get('abnormal_params',[]))
        row_vals = [
            sdata.get('time',''), sdata.get('sample_no',''),
            sdata.get('sample_id',''), sdata.get('patient_name','')
        ]
        ab_indices = set()
        for ci, code in enumerate(ANALYTES, start=4):
            val = str(sdata.get(code,'')).replace('↑','').replace('↓','').strip()
            row_vals.append(val)
            if code in ab_set:
                ab_indices.add(ci)
        table.add_row(row_vals, ab_indices)
        total += 1

    status_var.set(f"Yuklandi: {total} ta natija ({len(files)} ta fayl)")
