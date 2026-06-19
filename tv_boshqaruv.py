"""
tv_boshqaruv.py — LIMS uchun TV Boshqaruv oynasi.

Vazifa:
  - TV jadvalini (kunlik media dastur) boshqarish
  - Ticker matnini yangilash
  - tv_server.py bilan HTTP orqali aloqa qiladi

Ishlatish:
  monoblok_dastur.py dan:
      from tv_boshqaruv import TvBoshqaruvOynasi
      TvBoshqaruvOynasi(self.root)

  Standalone test (LIMS dan tashqari):
      python tv_boshqaruv.py

Bog'liqliklar:
  - tv_server.py — http://127.0.0.1:8765 da ishga tushgan bo'lishi kerak
  - requests, tkinter
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

import requests

# ─────────────────────────────────────────────────────────────────
# Sozlamalar
# ─────────────────────────────────────────────────────────────────

TV_SERVER_URL = "http://127.0.0.1:8765"  # tv_server.py shu mashinada ishlaydi
HTTP_TIMEOUT = 5  # sekund

# Window standard (reference_window_standard.md)
WIN_W = 1520
WIN_H = 790
WIN_MIN_W = 900
WIN_MIN_H = 560

PRESET_TICKER_TEXTS = [
    "AzizMedLine — ishonchli tahlil markazi · Ish vaqti 08:00-18:00",
    "Vitamin D analizi chegirmada · 50,000 so'm o'rniga 35,000 so'm · Faqat bugun!",
    "Yangi: HIV ekspres tahlil · Natija 15 daqiqada",
    "Instagram @azizmedline — obuna bo'ling, 10% chegirma!",
    "Telegram guruh a'zolariga 7% chegirma",
]

TEZLIK_LABELS = {"slow": "Sekin", "normal": "Normal", "fast": "Tez"}


# ─────────────────────────────────────────────────────────────────
# Asosiy oyna
# ─────────────────────────────────────────────────────────────────

class TvBoshqaruvOynasi(tk.Toplevel):
    """LIMS Toplevel oyna — TV jadval + ticker boshqarish.

    parent — odatda monoblok_dastur.MonoblokApp.root.
             Standalone test'da withdraw qilingan tk.Tk() berish kerak.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("📺 TV Boshqaruvi — AzizMedLine")
        self._setup_geometry()

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self.jadval_tab = JadvalTab(self.notebook)
        self.ticker_tab = TickerTab(self.notebook)
        self.navbat_vaqt_tab = NavbatVaqtTab(self.notebook)
        self.tv_buyruq_tab = TvBuyruqlarTab(self.notebook)

        self.notebook.add(self.jadval_tab, text="  📅  Jadval  ")
        self.notebook.add(self.ticker_tab, text="  📢  Ticker  ")
        self.notebook.add(self.navbat_vaqt_tab, text="  🕐  Navbat Vaqti  ")
        self.notebook.add(self.tv_buyruq_tab, text="  📺  TV Buyruqlari  ")

        # Status bar (server URL ko'rsatadi)
        self.status_var = tk.StringVar(value=f"Server: {TV_SERVER_URL}")
        status_bar = ttk.Label(self, textvariable=self.status_var,
                               relief=tk.SUNKEN, padding=(8, 4))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Server bilan ulanishni tekshirish
        self._check_server_async()

    def _setup_geometry(self):
        """Window standard: 1520x790, markazda, hech qanday transient/grab."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = min(WIN_W, sw - 80)
        wh = min(WIN_H, sh - 100)
        x = (sw - ww) // 2
        y = max(20, (sh - wh) // 2)
        self.geometry(f"{ww}x{wh}+{x}+{y}")
        self.minsize(WIN_MIN_W, WIN_MIN_H)
        self.resizable(True, True)
        # transient/grab_set/zoomed ishlatmaymiz
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _check_server_async(self):
        def worker():
            try:
                r = requests.get(f"{TV_SERVER_URL}/status", timeout=2)
                r.raise_for_status()
                self.after(0, lambda: self.status_var.set(
                    f"✓ Server: {TV_SERVER_URL} — ulangan"))
            except Exception as e:
                self.after(0, lambda: self.status_var.set(
                    f"⚠️ Server: {TV_SERVER_URL} — JAVOB BERMAYAPTI"))
        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
# Tab 1: Jadval
# ─────────────────────────────────────────────────────────────────

class JadvalTab(ttk.Frame):
    """Kunlik media dastur jadvali (server /playlist/all CRUD)."""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()
        self.after(200, self._load_data)  # Yuklash UI tayyor bo'lgach

    def _build_ui(self):
        # ── Top bar ──
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top, text="Sana filter:").pack(side=tk.LEFT, padx=(0, 4))
        self.sana_filter = tk.StringVar(value="BUGUN")
        sana_combo = ttk.Combobox(
            top, textvariable=self.sana_filter,
            values=["BUGUN", "HAR_KUN", "BARCHASI"],
            state="readonly", width=12
        )
        sana_combo.pack(side=tk.LEFT)
        sana_combo.bind("<<ComboboxSelected>>", lambda e: self._load_data())

        ttk.Button(top, text="↻ Yangilash",
                   command=self._load_data, width=12).pack(side=tk.LEFT, padx=(12, 4))

        # Bo'sh joy
        ttk.Frame(top).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # CRUD tugmalari (o'ng tomonda)
        ttk.Button(top, text="🗑️ O'chirish",
                   command=self._delete_item, width=14).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="✎ Tahrirlash",
                   command=self._edit_item, width=14).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="+ Yangi qo'shish",
                   command=self._add_item, width=16).pack(side=tk.RIGHT, padx=2)

        # ── Jadval (Treeview) ──
        tree_wrap = ttk.Frame(self)
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        cols = ("id", "boshlash", "tugash", "turi", "fayl",
                "davom", "tartib", "sana", "faol")
        self.tree = ttk.Treeview(tree_wrap, columns=cols,
                                 show="headings", selectmode="browse")
        for col, label, w, anchor in [
            ("id", "ID", 50, "center"),
            ("boshlash", "Boshlash", 80, "center"),
            ("tugash", "Tugash", 80, "center"),
            ("turi", "Turi", 80, "center"),
            ("fayl", "Fayl/URL", 380, "w"),
            ("davom", "Davom (sek)", 90, "center"),
            ("tartib", "Tartib", 60, "center"),
            ("sana", "Sana", 110, "center"),
            ("faol", "Faol", 60, "center"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor=anchor)

        vscroll = ttk.Scrollbar(tree_wrap, orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=vscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.pack(side=tk.LEFT, fill=tk.Y)

        self.tree.bind("<Double-1>", lambda e: self._edit_item())

        # ── Info bar ──
        self.info_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self.info_var,
                  foreground="#666", padding=(10, 4)).pack(side=tk.BOTTOM, fill=tk.X)

    # ── Server bilan ishlash ──
    def _load_data(self):
        def worker():
            try:
                sana = self.sana_filter.get()
                params = {} if sana == "BARCHASI" else {"sana": sana}
                r = requests.get(f"{TV_SERVER_URL}/playlist/all",
                                 params=params, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                items = r.json().get("playlist", [])
                self.after(0, lambda: self._populate(items))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self._on_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, items):
        self.tree.delete(*self.tree.get_children())
        for it in items:
            fayl = it.get("fayl_nomi") or it.get("manba", "")
            self.tree.insert("", "end", values=(
                it.get("id", ""),
                it.get("boshlash_vaqt", "") or "—",
                it.get("tugash_vaqt", "") or "—",
                it.get("manba_turi", "local"),
                fayl,
                it.get("davomiylik_sec", ""),
                it.get("tartib", 0),
                it.get("sana") or "har kun",
                "✓" if it.get("faol") else "✗",
            ))
        self.info_var.set(f"Jami: {len(items)} ta yozuv")

    def _on_error(self, msg):
        self.info_var.set(f"⚠️ Xato: {msg}")
        messagebox.showerror("Server xatosi",
                             f"Ma'lumotni olib bo'lmadi:\n\n{msg}\n\n"
                             f"tv_server.py ishga tushganligini tekshiring.",
                             parent=self)

    # ── CRUD ──
    def _add_item(self):
        dlg = JadvalDialog(self, title="+ Yangi jadval yozuvi")
        if dlg.result:
            self._save_new(dlg.result)

    def _edit_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Tanlang",
                                "Tahrirlash uchun ro'yxatdan bitta yozuv tanlang",
                                parent=self)
            return
        values = self.tree.item(sel[0], "values")
        item_id = values[0]
        prefill = {
            "boshlash_vaqt": values[1] if values[1] != "—" else "",
            "tugash_vaqt": values[2] if values[2] != "—" else "",
            "manba_turi": values[3],
            "manba": values[4],
            "davomiylik_sec": values[5],
            "tartib": values[6],
            "sana": values[7] if values[7] != "har kun" else "",
            "faol": values[8] == "✓",
        }
        dlg = JadvalDialog(self,
                           title=f"✎ Yozuv #{item_id} ni tahrirlash",
                           prefill=prefill)
        if dlg.result:
            self._save_update(item_id, dlg.result)

    def _delete_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Tanlang", "O'chirish uchun yozuv tanlang", parent=self)
            return
        values = self.tree.item(sel[0], "values")
        item_id = values[0]
        if not messagebox.askyesno(
                "Tasdiqlash",
                f"Yozuv #{item_id} ({values[4]}) o'chirilsinmi?",
                parent=self):
            return

        def worker():
            try:
                r = requests.post(
                    f"{TV_SERVER_URL}/playlist/delete/{item_id}",
                    timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, self._load_data)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: messagebox.showerror(
                    "Xato", f"O'chirib bo'lmadi:\n{msg}", parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _save_new(self, data):
        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/playlist/add",
                                  json=data, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, self._load_data)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: messagebox.showerror(
                    "Xato", f"Saqlanmadi:\n{msg}", parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _save_update(self, item_id, data):
        def worker():
            try:
                r = requests.post(
                    f"{TV_SERVER_URL}/playlist/update/{item_id}",
                    json=data, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, self._load_data)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: messagebox.showerror(
                    "Xato", f"Yangilanmadi:\n{msg}", parent=self))

        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
# Jadval qo'shish/tahrirlash dialogi
# ─────────────────────────────────────────────────────────────────

class JadvalDialog(tk.Toplevel):
    """Yangi yozuv yoki tahrirlash dialogi."""

    def __init__(self, parent, title, prefill=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x500")
        self.resizable(False, False)
        self.result = None
        prefill = prefill or {}

        frm = ttk.Frame(self, padding=18)
        frm.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Manba turi
        ttk.Label(frm, text="Manba turi:").grid(row=row, column=0, sticky="w", pady=6)
        self.var_turi = tk.StringVar(value=prefill.get("manba_turi", "local"))
        turi_combo = ttk.Combobox(frm, textvariable=self.var_turi,
                                  values=["local", "url", "youtube"],
                                  state="readonly", width=20)
        turi_combo.grid(row=row, column=1, sticky="ew", pady=6)
        row += 1

        # Manba
        ttk.Label(frm, text="Fayl/URL:").grid(row=row, column=0, sticky="w", pady=6)
        self.var_manba = tk.StringVar(value=prefill.get("manba", ""))
        ttk.Entry(frm, textvariable=self.var_manba).grid(
            row=row, column=1, sticky="ew", pady=6)
        row += 1

        ttk.Label(frm,
                  text="• local: tv_media/ ichidagi fayl nomi (masalan: reklama.mp4)\n"
                       "• url: to'liq URL (https://...)\n"
                       "• youtube: video ID yoki to'liq URL",
                  foreground="#666", font=("Arial", 9),
                  justify="left").grid(row=row, column=1, sticky="w", pady=(0, 8))
        row += 1

        # Boshlash vaqti
        ttk.Label(frm, text="Boshlash vaqti (HH:MM):").grid(
            row=row, column=0, sticky="w", pady=6)
        self.var_boshlash = tk.StringVar(value=prefill.get("boshlash_vaqt", "08:00"))
        ttk.Entry(frm, textvariable=self.var_boshlash, width=10).grid(
            row=row, column=1, sticky="w", pady=6)
        row += 1

        # Tugash vaqti
        ttk.Label(frm, text="Tugash vaqti (HH:MM):").grid(
            row=row, column=0, sticky="w", pady=6)
        self.var_tugash = tk.StringVar(value=prefill.get("tugash_vaqt", "18:00"))
        ttk.Entry(frm, textvariable=self.var_tugash, width=10).grid(
            row=row, column=1, sticky="w", pady=6)
        row += 1

        # Davomiylik
        ttk.Label(frm, text="Davomiylik (sek):").grid(
            row=row, column=0, sticky="w", pady=6)
        try:
            init_davom = int(prefill.get("davomiylik_sec") or 30)
        except (ValueError, TypeError):
            init_davom = 30
        self.var_davom = tk.IntVar(value=init_davom)
        ttk.Spinbox(frm, from_=1, to=3600, textvariable=self.var_davom,
                    width=10).grid(row=row, column=1, sticky="w", pady=6)
        row += 1

        # Tartib
        ttk.Label(frm, text="Tartib (kichik = oldin):").grid(
            row=row, column=0, sticky="w", pady=6)
        try:
            init_tartib = int(prefill.get("tartib") or 0)
        except (ValueError, TypeError):
            init_tartib = 0
        self.var_tartib = tk.IntVar(value=init_tartib)
        ttk.Spinbox(frm, from_=0, to=999, textvariable=self.var_tartib,
                    width=10).grid(row=row, column=1, sticky="w", pady=6)
        row += 1

        # Sana
        ttk.Label(frm, text="Sana (YYYY-MM-DD\nbo'sh = har kun):").grid(
            row=row, column=0, sticky="w", pady=6)
        self.var_sana = tk.StringVar(value=prefill.get("sana") or "")
        ttk.Entry(frm, textvariable=self.var_sana, width=14).grid(
            row=row, column=1, sticky="w", pady=6)
        row += 1

        # Faol
        self.var_faol = tk.BooleanVar(value=bool(prefill.get("faol", True)))
        ttk.Checkbutton(frm, text="Faol (TV da ko'rsatish)",
                        variable=self.var_faol).grid(
            row=row, column=1, sticky="w", pady=12)
        row += 1

        # Tugmalar
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=14)
        tk.Button(btn_frame, text="✓ Saqlash", command=self._save,
                  bg="#10B981", fg="white", font=("Arial", 11, "bold"),
                  padx=20, pady=6).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Bekor", command=self.destroy,
                   width=12).pack(side=tk.LEFT, padx=6)

        frm.columnconfigure(1, weight=1)

        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.wait_window()

    def _save(self):
        manba = self.var_manba.get().strip()
        if not manba:
            messagebox.showwarning("Bo'sh", "Fayl/URL kiriting", parent=self)
            return
        # Vaqt formati tekshirish (oddiy)
        for label, val in [("Boshlash", self.var_boshlash.get()),
                           ("Tugash", self.var_tugash.get())]:
            if val and (len(val) != 5 or val[2] != ":"):
                messagebox.showwarning("Format xato",
                                       f"{label} vaqti HH:MM formatda bo'lishi kerak",
                                       parent=self)
                return
        self.result = {
            "manba_turi": self.var_turi.get(),
            "manba": manba,
            "fayl_nomi": manba,
            "boshlash_vaqt": self.var_boshlash.get() or "08:00",
            "tugash_vaqt": self.var_tugash.get() or "18:00",
            "davomiylik_sec": int(self.var_davom.get()),
            "tartib": int(self.var_tartib.get()),
            "sana": self.var_sana.get().strip() or None,
            "faol": bool(self.var_faol.get()),
        }
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Tab 2: Ticker
# ─────────────────────────────────────────────────────────────────

class TickerTab(ttk.Frame):
    """Ticker boshqarish — yuguruvchi matn (server /ticker)."""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()
        self.after(200, self._load_current)

    def _build_ui(self):
        wrap = ttk.Frame(self, padding=20)
        wrap.pack(fill=tk.BOTH, expand=True)

        ttk.Label(wrap, text="📢  Ticker — yuguruvchi matn (TV ekrani pastida)",
                  font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 14))

        # ── Joriy holat ──
        joriy_frame = ttk.LabelFrame(wrap, text="Hozir TV da ko'rsatilayotgan",
                                     padding=12)
        joriy_frame.pack(fill=tk.X, pady=(0, 14))

        self.joriy_matn = tk.StringVar(value="Yuklanmoqda...")
        self.joriy_holat = tk.StringVar(value="—")

        ttk.Label(joriy_frame, textvariable=self.joriy_matn,
                  wraplength=1200, font=("Arial", 11), foreground="#1e40af",
                  justify="left").pack(anchor="w")
        ttk.Label(joriy_frame, textvariable=self.joriy_holat,
                  foreground="#666", font=("Arial", 10)).pack(
            anchor="w", pady=(6, 0))

        btn_refresh = ttk.Frame(joriy_frame)
        btn_refresh.pack(anchor="e", pady=(8, 0))
        ttk.Button(btn_refresh, text="↻ Yangilash",
                   command=self._load_current, width=14).pack(side=tk.LEFT)

        # ── Yangi ticker ──
        new_frame = ttk.LabelFrame(wrap, text="Yangi ticker yozish", padding=12)
        new_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 14))

        ttk.Label(new_frame, text="Matn:").pack(anchor="w")
        self.matn_text = tk.Text(new_frame, height=4, font=("Arial", 11), wrap=tk.WORD)
        self.matn_text.pack(fill=tk.X, pady=(4, 12))

        # Tezlik + Faol
        opt_frame = ttk.Frame(new_frame)
        opt_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(opt_frame, text="Tezlik:").pack(side=tk.LEFT, padx=(0, 8))
        self.tezlik_var = tk.StringVar(value="normal")
        for label, val in [("Sekin", "slow"), ("Normal", "normal"), ("Tez", "fast")]:
            ttk.Radiobutton(opt_frame, text=label, value=val,
                            variable=self.tezlik_var).pack(side=tk.LEFT, padx=4)

        self.faol_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Faol (TV da ko'rsatish)",
                        variable=self.faol_var).pack(side=tk.LEFT, padx=(30, 0))

        # Saqlash tugmasi
        save_btn = tk.Button(new_frame,
                             text="✓  Saqlash va TV ga darhol yuborish",
                             command=self._save,
                             bg="#10B981", fg="white",
                             font=("Arial", 12, "bold"),
                             padx=20, pady=10, cursor="hand2")
        save_btn.pack(pady=8)

        # ── Tezkor matnlar ──
        preset_frame = ttk.LabelFrame(
            wrap, text="Tezkor matnlar (bosing — yuqoridagi maydonga qo'yiladi)",
            padding=10)
        preset_frame.pack(fill=tk.BOTH, expand=True)

        for txt in PRESET_TICKER_TEXTS:
            short = txt if len(txt) <= 90 else (txt[:87] + "…")
            ttk.Button(preset_frame, text="📌  " + short,
                       command=lambda t=txt: self._set_text(t)).pack(
                fill=tk.X, pady=2)

    def _set_text(self, t):
        self.matn_text.delete("1.0", "end")
        self.matn_text.insert("1.0", t)

    def _load_current(self):
        def worker():
            try:
                r = requests.get(f"{TV_SERVER_URL}/ticker", timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                self.after(0, lambda: self._populate(
                    data.get("matn", ""),
                    bool(data.get("faol", False)),
                    data.get("tezlik", "normal"),
                ))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.joriy_matn.set(
                    f"⚠️ Server javob bermayapti: {msg}"))

        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, matn, faol, tezlik):
        self.joriy_matn.set(matn or "(bo'sh)")
        tezlik_label = TEZLIK_LABELS.get(tezlik, tezlik)
        holat = f"Tezlik: {tezlik_label}  ·  "
        holat += "✓ Faol" if faol else "✗ O'chirilgan"
        self.joriy_holat.set(holat)
        # Yangi matn maydoniga ham nusxa (faqat bo'sh bo'lsa)
        current_text = self.matn_text.get("1.0", "end-1c").strip()
        if not current_text and matn:
            self.matn_text.insert("1.0", matn)
        self.tezlik_var.set(tezlik if tezlik in TEZLIK_LABELS else "normal")
        self.faol_var.set(faol)

    def _save(self):
        matn = self.matn_text.get("1.0", "end-1c").strip()
        if not matn and self.faol_var.get():
            messagebox.showwarning(
                "Bo'sh matn",
                "Matn bo'sh — yoki matn yozing yoki 'Faol' belgisini olib tashlang",
                parent=self)
            return
        data = {
            "matn": matn,
            "faol": bool(self.faol_var.get()),
            "tezlik": self.tezlik_var.get(),
        }

        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/ticker/update",
                                  json=data, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, lambda: (
                    messagebox.showinfo(
                        "Saqlandi",
                        "✓ Ticker saqlandi va TV ga darhol yuborildi",
                        parent=self),
                    self._load_current()
                ))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: messagebox.showerror(
                    "Xato",
                    f"Saqlanmadi:\n{msg}\n\ntv_server.py ishlayotganini tekshiring.",
                    parent=self))

        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
# Tab 3: Navbat Vaqti (kechikish + qayta qo'yish)
# ─────────────────────────────────────────────────────────────────

class NavbatVaqtTab(ttk.Frame):
    """Natija vaqtini boshqarish — global kechikish + individual bemor."""

    def __init__(self, parent):
        super().__init__(parent)
        self._navbat_list = []  # [(order_id, ism, raqam, vaqt), ...]
        self._build_ui()
        self.after(300, self._load_navbat)

    def _build_ui(self):
        wrap = ttk.Frame(self, padding=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── Global kechikish ──
        glob_frame = ttk.LabelFrame(wrap, text="⏱ Barcha kutayotganlarga kechikish qo'shish",
                                    padding=14)
        glob_frame.pack(fill=tk.X, pady=(0, 16))

        btn_row = ttk.Frame(glob_frame)
        btn_row.pack(fill=tk.X)

        for mins in [15, 30, 60]:
            tk.Button(btn_row, text=f"+{mins} min",
                      command=lambda m=mins: self._global_kechikish(m),
                      bg="#F59E0B", fg="white",
                      font=("Arial", 12, "bold"),
                      width=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=6)

        custom_row = ttk.Frame(glob_frame)
        custom_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(custom_row, text="Boshqa:").pack(side=tk.LEFT)
        self.glob_daqiqa = tk.IntVar(value=20)
        ttk.Spinbox(custom_row, from_=1, to=480, textvariable=self.glob_daqiqa,
                    width=6).pack(side=tk.LEFT, padx=6)
        ttk.Label(custom_row, text="daqiqa").pack(side=tk.LEFT)
        tk.Button(custom_row, text="Kechiktirish",
                  command=lambda: self._global_kechikish(self.glob_daqiqa.get()),
                  bg="#F59E0B", fg="white",
                  font=("Arial", 11, "bold"),
                  padx=12, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=10)

        self.glob_status = tk.StringVar(value="")
        ttk.Label(glob_frame, textvariable=self.glob_status,
                  foreground="#10B981", font=("Arial", 10)).pack(anchor="w", pady=(8, 0))

        # ── Individual bemor ──
        ind_frame = ttk.LabelFrame(wrap, text="👤 Alohida bemor uchun",
                                   padding=14)
        ind_frame.pack(fill=tk.BOTH, expand=True)

        sel_row = ttk.Frame(ind_frame)
        sel_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(sel_row, text="Bemor:").pack(side=tk.LEFT)
        self.bemor_var = tk.StringVar()
        self.bemor_combo = ttk.Combobox(sel_row, textvariable=self.bemor_var,
                                        state="readonly", width=40)
        self.bemor_combo.pack(side=tk.LEFT, padx=8)
        ttk.Button(sel_row, text="↻", command=self._load_navbat, width=4).pack(side=tk.LEFT)

        act_row = ttk.Frame(ind_frame)
        act_row.pack(fill=tk.X)

        for mins in [15, 30, 60]:
            tk.Button(act_row, text=f"+{mins} min",
                      command=lambda m=mins: self._ind_uzaytir(m),
                      bg="#3B82F6", fg="white",
                      font=("Arial", 11, "bold"),
                      width=9, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=4)

        tk.Button(act_row, text="🔄 Qayta qo'yish",
                  command=self._qayta_qoyish,
                  bg="#8B5CF6", fg="white",
                  font=("Arial", 11, "bold"),
                  padx=14, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=12)

        self.ind_status = tk.StringVar(value="")
        ttk.Label(ind_frame, textvariable=self.ind_status,
                  foreground="#10B981", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))

    def _load_navbat(self):
        def worker():
            try:
                r = requests.get(f"{TV_SERVER_URL}/navbat/all", timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                rows = r.json().get("navbatlar", [])
                kutmoqdalar = [
                    row for row in rows
                    if row.get("holat", "kutmoqda") not in ("ketdi", "bekor")
                ]
                self.after(0, lambda: self._populate_navbat(kutmoqdalar))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.ind_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()

    def _populate_navbat(self, rows):
        self._navbat_list = []
        labels = []
        for r in rows:
            oid = r.get("order_id") or r.get("id")
            ism = r.get("bemor_ism") or r.get("ism") or "Noma'lum"
            raqam = r.get("navbat_raqami") or r.get("raqam") or "?"
            vaqt = r.get("kutilgan_vaqt") or r.get("vaqt") or "—"
            if oid:
                self._navbat_list.append((oid, ism, raqam, vaqt))
                labels.append(f"#{raqam} — {ism}  ({vaqt})")
        self.bemor_combo["values"] = labels
        if labels:
            self.bemor_combo.current(0)

    def _selected_order_id(self):
        idx = self.bemor_combo.current()
        if idx < 0 or idx >= len(self._navbat_list):
            messagebox.showwarning("Tanlang", "Bitta bemor tanlang", parent=self)
            return None
        return self._navbat_list[idx][0]

    def _global_kechikish(self, daqiqa: int):
        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/navbat/kechikish",
                                  json={"daqiqa": daqiqa}, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                n = data.get("navbatlar_soni", "?")
                self.after(0, lambda: self.glob_status.set(
                    f"✓ +{daqiqa} daqiqa — {n} ta bemorga qo'shildi"))
                self.after(0, self._load_navbat)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.glob_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()

    def _ind_uzaytir(self, daqiqa: int):
        order_id = self._selected_order_id()
        if not order_id:
            return
        def worker():
            try:
                r = requests.post(
                    f"{TV_SERVER_URL}/navbat/vaqt-uzaytir/{order_id}",
                    json={"daqiqa": daqiqa}, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                yangi = data.get("yangi_vaqt", "?")
                self.after(0, lambda: self.ind_status.set(
                    f"✓ +{daqiqa} daqiqa → yangi vaqt: {yangi}"))
                self.after(0, self._load_navbat)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.ind_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()

    def _qayta_qoyish(self):
        order_id = self._selected_order_id()
        if not order_id:
            return
        ism = self._navbat_list[self.bemor_combo.current()][1]
        if not messagebox.askyesno(
                "Tasdiqlash",
                f"{ism} — keyingi batch oynasiga qayta qo'yilsinmi?",
                parent=self):
            return
        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/navbat/qayta-qoyish",
                                  json={"order_id": order_id}, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                data = r.json()
                yangi = data.get("yangi_vaqt", "?")
                self.after(0, lambda: self.ind_status.set(
                    f"✓ Qayta qo'yildi → yangi vaqt: {yangi}"))
                self.after(0, self._load_navbat)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.ind_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
# Tab 4: TV Buyruqlari (layout, stop_all, reboot)
# ─────────────────────────────────────────────────────────────────

class TvBuyruqlarTab(ttk.Frame):
    """TV ga tezkor buyruqlar yuborish — layout, stop_all, reboot."""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        wrap = ttk.Frame(self, padding=20)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── Layout ──
        layout_frame = ttk.LabelFrame(wrap, text="📐 TV Layout (ekran nisbati)",
                                      padding=14)
        layout_frame.pack(fill=tk.X, pady=(0, 16))

        lbl_row = ttk.Frame(layout_frame)
        lbl_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(lbl_row,
                  text="Media (chap) / Navbat (o'ng) nisbati — navbat paneli har doim ko'rinadi",
                  foreground="#555").pack(anchor="w")

        btn_row = ttk.Frame(layout_frame)
        btn_row.pack(fill=tk.X)

        presets = [("70 / 30", 70, 30), ("65 / 35", 65, 35),
                   ("60 / 40", 60, 40), ("50 / 50", 50, 50)]
        self._layout_btns = []
        for lbl, m, n in presets:
            b = tk.Button(btn_row, text=lbl,
                          command=lambda mv=m, nv=n: self._set_layout(mv, nv),
                          bg="#1D4ED8", fg="white",
                          font=("Arial", 12, "bold"),
                          width=10, pady=6, cursor="hand2")
            b.pack(side=tk.LEFT, padx=6)
            self._layout_btns.append(b)

        custom_row = ttk.Frame(layout_frame)
        custom_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(custom_row, text="Custom: Media").pack(side=tk.LEFT)
        self.custom_media = tk.IntVar(value=70)
        ttk.Spinbox(custom_row, from_=30, to=90, textvariable=self.custom_media,
                    width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(custom_row, text="% | Navbat").pack(side=tk.LEFT, padx=(8, 4))
        self.custom_navbat = tk.IntVar(value=30)
        ttk.Spinbox(custom_row, from_=10, to=70, textvariable=self.custom_navbat,
                    width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(custom_row, text="%").pack(side=tk.LEFT)
        tk.Button(custom_row, text="Yuborish",
                  command=lambda: self._set_layout(
                      self.custom_media.get(), self.custom_navbat.get()),
                  bg="#1D4ED8", fg="white",
                  font=("Arial", 11), padx=12, pady=4, cursor="hand2").pack(
            side=tk.LEFT, padx=10)

        # ── Tezkor buyruqlar ──
        cmd_frame = ttk.LabelFrame(wrap, text="⚡ Tezkor buyruqlar", padding=14)
        cmd_frame.pack(fill=tk.X, pady=(0, 16))

        row1 = ttk.Frame(cmd_frame)
        row1.pack(fill=tk.X, pady=(0, 8))

        tk.Button(row1, text="■  Hammasini to'xtatish",
                  command=self._stop_all,
                  bg="#DC2626", fg="white",
                  font=("Arial", 13, "bold"),
                  padx=20, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=6)

        tk.Button(row1, text="🔄  TV qayta yuklash",
                  command=self._reboot_app,
                  bg="#6B7280", fg="white",
                  font=("Arial", 12, "bold"),
                  padx=16, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=6)

        tk.Button(row1, text="📢  Ticker yangilash",
                  command=self._reload_ticker,
                  bg="#059669", fg="white",
                  font=("Arial", 12, "bold"),
                  padx=16, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=6)

        self.cmd_status = tk.StringVar(value="")
        ttk.Label(cmd_frame, textvariable=self.cmd_status,
                  foreground="#10B981", font=("Arial", 11)).pack(anchor="w", pady=(8, 0))

        # ── Web Admin havolasi ──
        web_frame = ttk.LabelFrame(wrap, text="🌐 Web Admin Panel", padding=14)
        web_frame.pack(fill=tk.X)

        ttk.Label(web_frame,
                  text="To'liq boshqaruv (media yuklash, navbat sozlash, playlist) uchun:",
                  foreground="#555").pack(anchor="w")
        url_label = tk.Label(web_frame,
                             text=f"{TV_SERVER_URL}/admin",
                             fg="#1D4ED8", cursor="hand2",
                             font=("Arial", 12, "underline"))
        url_label.pack(anchor="w", pady=(4, 0))
        url_label.bind("<Button-1>", lambda e: self._open_browser())
        ttk.Label(web_frame,
                  text="Tarmoqdagi har qanday kompyuter yoki planshetdan brauzerda ochsa bo'ladi.",
                  foreground="#888", font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

    def _send_command(self, action: str, extra: dict = None):
        payload = {"action": action, **(extra or {})}
        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/command",
                                  json=payload, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, lambda: self.cmd_status.set(f"✓ '{action}' TV ga yuborildi"))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.cmd_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()

    def _set_layout(self, media: int, navbat: int):
        def worker():
            try:
                r = requests.post(f"{TV_SERVER_URL}/command",
                                  json={"action": "set_layout",
                                        "media": media, "navbat": navbat},
                                  timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                self.after(0, lambda: self.cmd_status.set(
                    f"✓ Layout: {media}% media / {navbat}% navbat"))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.cmd_status.set(f"⚠️ {msg}"))
        threading.Thread(target=worker, daemon=True).start()

    def _stop_all(self):
        if messagebox.askyesno("Tasdiqlash",
                               "TV dagi barcha media to'xtatilsinmi?\n"
                               "(Navbat ko'rinib qoladi)",
                               parent=self):
            self._send_command("stop_all")

    def _reboot_app(self):
        if messagebox.askyesno("Tasdiqlash", "TV APK qayta yuklansinmi?", parent=self):
            self._send_command("reboot_app")

    def _reload_ticker(self):
        self._send_command("ticker_reload")

    def _open_browser(self):
        import webbrowser
        webbrowser.open(f"{TV_SERVER_URL}/admin")


# ─────────────────────────────────────────────────────────────────
# Standalone test (LIMS dan tashqari)
# ─────────────────────────────────────────────────────────────────

def main():
    """python tv_boshqaruv.py — mustaqil sinov."""
    root = tk.Tk()
    root.withdraw()  # Asosiy bo'sh oynani yashiramiz
    win = TvBoshqaruvOynasi(parent=root)
    win.protocol("WM_DELETE_WINDOW", lambda: root.quit())
    root.mainloop()


if __name__ == "__main__":
    main()
