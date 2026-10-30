"""
Blanka qatorlarini tahrirlash jadvali — gemo_blanka va siydik_blanka uchun umumiy.

Jadvalda har qator = blankadagi bitta ko'rsatkich (kod, nom, birlik, norma, ko'rinish ...).
Amallar: ▲/▼ tartib, tahrirlash (ikki marta bosish), ko'rinishni almashtirish (Bo'sh joy),
yangi qator, o'chirish (standart qator faqat yashiriladi), standartga qaytarish.

Ishlatish:
    jad = QatorJadvali(frame, qatorlar, DEFAULT_QATORLAR, MAYDONLAR, KORSAT, toza_fn, yordam)
    jad.qatorlar   # tahrirlangan ro'yxat (joyida o'zgaradi)
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox


class QatorJadvali:
    """maydonlar: [(kalit, sarlavha, kenglik_px, royxatmi)] — "korsat" ustuni avtomatik
    birinchi turadi; royxatmi=True maydon (kodlar, variantlar) vergul bilan kiritiladi."""

    def __init__(self, parent, qatorlar, standart, maydonlar, korsat, toza_fn, yordam="",
                 faqat_oqish=(), yangi_qator=True):
        """faqat_oqish — tahrirlash oynasida o'zgarmaydigan maydonlar (masalan katalog nomi);
        yangi_qator=False — «Yangi qator» va «O'chirish» tugmalari yo'q (ro'yxat tashqaridan)."""
        self.faqat_oqish = set(faqat_oqish)
        self.qatorlar = qatorlar
        self.standart = standart
        self.standart_kodlar = {q["kod"] for q in standart}
        self.maydonlar = maydonlar
        self.korsat = korsat
        self.toza_fn = toza_fn
        self.yordam = yordam
        self.top = parent.winfo_toplevel()

        frm = ttk.Frame(parent)
        frm.pack(fill=tk.BOTH, expand=True)
        cols = ["korsat"] + [m[0] for m in maydonlar]
        self.tree = tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        tree.heading("korsat", text="Ko'rinish")
        tree.column("korsat", width=95, anchor=tk.CENTER, stretch=False)
        for k, sarl, w, _r in maydonlar:
            tree.heading(k, text=sarl)
            tree.column(k, width=w, anchor=tk.W if w >= 150 else tk.CENTER, stretch=(k == "nom"))
        tree.tag_configure("yashirin", foreground="#999999")
        tree.tag_configure("yangi", foreground="#1565C0")
        sb = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)

        side = ttk.Frame(frm)
        side.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
        tugmalar = [("▲ Yuqoriga", lambda: self._kochir(-1)), ("▼ Pastga", lambda: self._kochir(1)),
                    ("✎ Tahrirlash", self._tahrir_tanlangan)]
        if len(korsat) > 1:
            tugmalar.append(("👁 Ko'rinish", self._korinish))
        if yangi_qator:
            tugmalar += [("＋ Yangi qator", lambda: self._tahrir(None)), ("✖ O'chirish", self._ochir)]
        for txt, cmd in tugmalar:
            ttk.Button(side, text=txt, command=cmd, width=16).pack(fill=tk.X, pady=2)

        tree.bind("<Double-1>", self._tahrir_tanlangan)
        tree.bind("<Return>", self._tahrir_tanlangan)
        if len(korsat) > 1:
            tree.bind("<space>", self._korinish)
        if yangi_qator:
            tree.bind("<Delete>", lambda e: self._ochir())
        self.yangila(0)

    # ── ko'rsatish ────────────────────────────────────────────────────
    def yangila(self, sel_idx=None):
        tree = self.tree
        tree.delete(*tree.get_children())
        for i, q in enumerate(self.qatorlar):
            tags = []
            if q.get("korsat") == "yashirin":
                tags.append("yashirin")
            elif q["kod"] not in self.standart_kodlar:
                tags.append("yangi")
            vals = [self.korsat.get(q.get("korsat"), q.get("korsat"))]
            for k, _s, _w, royxat in self.maydonlar:
                v = q.get(k, "")
                vals.append(", ".join(v) if royxat else v)
            tree.insert("", tk.END, iid=str(i), tags=tags, values=vals)
        if sel_idx is not None and 0 <= sel_idx < len(self.qatorlar):
            tree.selection_set(str(sel_idx))
            tree.see(str(sel_idx))

    def standartga(self):
        self.qatorlar[:] = json.loads(json.dumps(self.standart))
        self.yangila(0)

    def _tanlangan(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ── amallar ───────────────────────────────────────────────────────
    def _kochir(self, delta):
        i = self._tanlangan()
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(self.qatorlar):
            self.qatorlar[i], self.qatorlar[j] = self.qatorlar[j], self.qatorlar[i]
            self.yangila(j)

    def _korinish(self, _e=None):
        i = self._tanlangan()
        if i is None:
            return
        keys = list(self.korsat)
        q = self.qatorlar[i]
        cur = q.get("korsat") if q.get("korsat") in keys else keys[0]
        q["korsat"] = keys[(keys.index(cur) + 1) % len(keys)]
        self.yangila(i)

    def _ochir(self):
        i = self._tanlangan()
        if i is None:
            return
        q = self.qatorlar[i]
        if q["kod"] in self.standart_kodlar:
            if messagebox.askyesno("Standart qator",
                                   f"«{q['nom']}» standart qator — o'chirib bo'lmaydi.\n"
                                   "Yashirin qilinsinmi?", parent=self.top):
                q["korsat"] = "yashirin"
                self.yangila(i)
            return
        if messagebox.askyesno("O'chirish", f"«{q['nom']}» ({q['kod']}) qatori o'chirilsinmi?",
                               parent=self.top):
            del self.qatorlar[i]
            self.yangila(min(i, len(self.qatorlar) - 1))

    def _tahrir_tanlangan(self, _e=None):
        i = self._tanlangan()
        if i is not None:
            self._tahrir(i)

    def _tahrir(self, idx):
        yangi = idx is None
        q = self.toza_fn({"kod": "", "korsat": "auto"}) if yangi else dict(self.qatorlar[idx])
        d = tk.Toplevel(self.top)
        d.title("Yangi qator" if yangi else f"Qator: {q['kod']}")
        d.transient(self.top)
        try:
            d.grab_set()
        except Exception:
            pass
        vs = {}
        for r, (k, sarl, _w, royxat) in enumerate(self.maydonlar):
            ttk.Label(d, text=sarl + ":").grid(row=r, column=0, sticky=tk.W, padx=8, pady=4)
            val = ", ".join(q.get(k) or []) if royxat else q.get(k, "")
            v = tk.StringVar(value=val)
            e = ttk.Entry(d, textvariable=v, width=52 if (k == "nom" or royxat) else 30)
            e.grid(row=r, column=1, sticky=tk.W, padx=8, pady=4)
            if (k == "kod" and not yangi) or k in self.faqat_oqish:
                e.configure(state="readonly")   # kod = natija kaliti; mavjud qatorda o'zgarmaydi
            vs[k] = v
        r = len(self.maydonlar)
        ttk.Label(d, text="Ko'rinish:").grid(row=r, column=0, sticky=tk.W, padx=8, pady=4)
        v_k = tk.StringVar(value=self.korsat.get(q.get("korsat"), list(self.korsat.values())[0]))
        ttk.Combobox(d, textvariable=v_k, values=list(self.korsat.values()), state="readonly",
                     width=16).grid(row=r, column=1, sticky=tk.W, padx=8, pady=4)
        if self.yordam:
            ttk.Label(d, foreground="#555", justify=tk.LEFT, wraplength=540, text=self.yordam
                      ).grid(row=r + 1, column=0, columnspan=2, sticky=tk.W, padx=8, pady=(6, 4))

        def _ok():
            kod = vs["kod"].get().strip()
            if not kod:
                messagebox.showwarning("Kod", "Kod bo'sh bo'lmasin.", parent=d)
                return
            if yangi and any(x["kod"].upper() == kod.upper() for x in self.qatorlar):
                messagebox.showwarning("Kod", f"«{kod}» kodi allaqachon bor.", parent=d)
                return
            raw = dict(q)
            raw.update({k: v.get() for k, v in vs.items()})
            raw["korsat"] = next((k for k, t in self.korsat.items() if t == v_k.get()), "auto")
            if not raw.get("nom", "").strip():
                raw["nom"] = kod
            nq = self.toza_fn(raw)
            if yangi:
                pos = self._tanlangan()
                pos = len(self.qatorlar) if pos is None else pos + 1
                self.qatorlar.insert(pos, nq)
            else:
                pos = idx
                self.qatorlar[idx] = nq
            d.destroy()
            self.yangila(pos)

        bf = ttk.Frame(d)
        bf.grid(row=r + 2, column=0, columnspan=2, sticky=tk.E, padx=8, pady=8)
        ttk.Button(bf, text="OK", command=_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="Bekor", command=d.destroy).pack(side=tk.RIGHT, padx=4)
        d.bind("<Return>", lambda e: _ok())
        d.bind("<Escape>", lambda e: d.destroy())
