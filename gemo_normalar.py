"""
Gemotologiya normalari (yosh × jins) — laboratoriyaga moslash.

Standart normalar hematology_window.MULTI_REF_NORMALS da (kodda). Har laboratoriya
o'z analizatori / reagenti normasini ishlatadi — shu modul orqali parametr bo'yicha
almashtiriladi. Almashtirilgan parametr butunlay sozlamadagi qatorlardan olinadi,
qolganlari standartdan.

Ta'sir qiladi: gemotologiya oynasidagi ↑/↓ va Flag, blankadagi norma va rang
(hammasi hematology_window.get_multi_ref orqali).

Saqlanadi: bazada (markaziy_sozlama, kalit "gemo_normalar") — hamma kompyuterda bir xil.
Format: {"WBC": [[yoshdan, yoshgacha, "B"|"M"|"F", min, max], ...], ...}
"""

import json

KALIT = "gemo_normalar"
JINS = {"B": "Ikkalasi", "M": "Erkak", "F": "Ayol"}
_KESH = {"mtime": None, "cfg": None}


def _son(x):
    return float(str(x).replace(",", ".").strip())


def _toza_qator(r):
    """[yoshdan, yoshgacha, jins, min, max] — noto'g'ri bo'lsa ValueError."""
    amin, amax, g, lo, hi = r
    amin, amax, lo, hi = int(_son(amin)), int(_son(amax)), _son(lo), _son(hi)
    g = str(g or "B").strip().upper()[:1]
    if g not in JINS:
        raise ValueError(f"jins B/M/F bo'lishi kerak: {g}")
    if amin < 0 or amax < amin:
        raise ValueError(f"yosh oralig'i noto'g'ri: {amin}-{amax}")
    if hi < lo:
        raise ValueError(f"min > max: {lo}-{hi}")
    return [amin, amax, g, lo, hi]


def _toza(raw) -> dict:
    out = {}
    if isinstance(raw, dict):
        for p, rows in raw.items():
            if not isinstance(rows, list):
                continue
            ok = []
            for r in rows:
                try:
                    ok.append(_toza_qator(r))
                except Exception:
                    continue
            if ok:
                out[str(p)] = ok
    return out


def sozlama(force=False) -> dict:
    import markaziy_sozlama as _ms
    return _ms.modul_sozlama(KALIT, _toza, _KESH, force)


def saqla(s: dict) -> bool:
    import markaziy_sozlama as _ms
    return _ms.modul_saqla(KALIT, _toza, s, _KESH)


def ol(param):
    """Parametr uchun laboratoriya normasi [(yoshdan, yoshgacha, jins, min, max)] yoki None."""
    try:
        rows = sozlama().get(param)
    except Exception:
        return None
    return [tuple(r) for r in rows] if rows else None


def _fmt(x):
    return str(int(x)) if float(x) == int(float(x)) else f"{float(x):g}"


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI
# ─────────────────────────────────────────────────────────────────────────────
def ochish_oyna(parent, standart: dict, qoshimcha_parametrlar=()):
    """standart — hematology_window.MULTI_REF_NORMALS; qoshimcha_parametrlar —
    foydalanuvchi blankaga qo'shgan parametrlar (IG# ...), ularga ham norma berish uchun."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    s = json.loads(json.dumps(sozlama(force=True)))
    params = list(standart) + [p for p in qoshimcha_parametrlar if p not in standart]

    def _joriy(p):
        if p in s:
            return s[p]
        return [list(r) for r in standart.get(p, [])]

    win = tk.Toplevel(parent)
    win.title("📏 Gemotologiya normalari (yosh × jins)")
    win.geometry("900x600")
    win.minsize(760, 480)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=860, text=(
        "Chapdan parametrni tanlang, o'ngda uning normalari: yosh oralig'i (yil), jins va "
        "min–max. Bemorning yoshi va jinsiga mos qator olinadi (jinsga mos qator ikkalasiga "
        "mos qatordan ustun). O'zgartirilgan parametrlar ko'k rangda. Ta'sir: gemotologiya "
        "oynasidagi ↑/↓ va blankadagi norma.")).pack(fill=tk.X, padx=10, pady=(8, 4))

    body = ttk.Frame(win)
    body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    pl = ttk.Treeview(body, columns=("p",), show="headings", selectmode="browse", height=20)
    pl.heading("p", text="Parametr")
    pl.column("p", width=150, anchor=tk.W)
    pl.tag_configure("ozg", foreground="#1565C0")
    pl.pack(side=tk.LEFT, fill=tk.Y)
    psb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=pl.yview)
    pl.configure(yscrollcommand=psb.set)
    psb.pack(side=tk.LEFT, fill=tk.Y)

    right = ttk.Frame(body)
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
    rt = ttk.Treeview(right, columns=("amin", "amax", "g", "lo", "hi"), show="headings", selectmode="browse")
    for c, t, w in (("amin", "Yoshdan", 80), ("amax", "Yoshgacha", 90), ("g", "Jins", 90),
                    ("lo", "Min", 90), ("hi", "Max", 90)):
        rt.heading(c, text=t)
        rt.column(c, width=w, anchor=tk.CENTER)
    rt.pack(fill=tk.BOTH, expand=True)

    def _plist(sel=None):
        pl.delete(*pl.get_children())
        for p in params:
            pl.insert("", tk.END, iid=p, values=(p + ("  ✎" if p in s else ""),),
                      tags=("ozg",) if p in s else ())
        if sel:
            pl.selection_set(sel)
            pl.see(sel)

    def _param():
        sel = pl.selection()
        return sel[0] if sel else None

    def _rlist(*_a):
        rt.delete(*rt.get_children())
        p = _param()
        if not p:
            return
        for i, r in enumerate(_joriy(p)):
            amax = "∞" if r[1] >= 9999 else r[1]
            rt.insert("", tk.END, iid=str(i), values=(r[0], amax, JINS.get(r[2], r[2]), _fmt(r[3]), _fmt(r[4])))

    def _belgila(p, rows):
        rows = sorted(rows, key=lambda r: (r[0], r[1], r[2]))
        std = [list(r) for r in standart.get(p, [])]
        if [[float(x) if not isinstance(x, str) else x for x in r] for r in rows] == \
           [[float(x) if not isinstance(x, str) else x for x in r] for r in std]:
            s.pop(p, None)       # standart bilan bir xil — saqlanmaydi
        else:
            s[p] = rows
        _plist(p)
        _rlist()

    def _tahrir(idx=None):
        p = _param()
        if not p:
            return
        rows = [list(r) for r in _joriy(p)]
        cur = rows[idx] if idx is not None else [18, 9999, "B", "", ""]
        d = tk.Toplevel(win)
        d.title(f"{p} — norma qatori")
        d.transient(win)
        try:
            d.grab_set()
        except Exception:
            pass
        vs = []
        for r, (lbl, val) in enumerate((("Yoshdan (yil):", cur[0]),
                                        ("Yoshgacha (yil, 9999 = cheksiz):", cur[1]),
                                        ("Min:", _fmt(cur[3]) if cur[3] != "" else ""),
                                        ("Max:", _fmt(cur[4]) if cur[4] != "" else ""))):
            ttk.Label(d, text=lbl).grid(row=r, column=0, sticky=tk.W, padx=8, pady=4)
            v = tk.StringVar(value=str(val))
            ttk.Entry(d, textvariable=v, width=14).grid(row=r, column=1, sticky=tk.W, padx=8, pady=4)
            vs.append(v)
        ttk.Label(d, text="Jins:").grid(row=4, column=0, sticky=tk.W, padx=8, pady=4)
        vg = tk.StringVar(value=JINS.get(cur[2], "Ikkalasi"))
        ttk.Combobox(d, textvariable=vg, values=list(JINS.values()), state="readonly", width=12
                     ).grid(row=4, column=1, sticky=tk.W, padx=8, pady=4)

        def _ok(_e=None):
            g = next((k for k, t in JINS.items() if t == vg.get()), "B")
            try:
                q = _toza_qator([vs[0].get(), vs[1].get(), g, vs[2].get(), vs[3].get()])
            except Exception as e:
                messagebox.showwarning("Norma", f"Qiymat noto'g'ri:\n{e}", parent=d)
                return
            if idx is None:
                rows.append(q)
            else:
                rows[idx] = q
            d.destroy()
            _belgila(p, rows)

        bf = ttk.Frame(d)
        bf.grid(row=5, column=0, columnspan=2, sticky=tk.E, padx=8, pady=8)
        ttk.Button(bf, text="OK", command=_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="Bekor", command=d.destroy).pack(side=tk.RIGHT, padx=4)
        d.bind("<Return>", _ok)
        d.bind("<Escape>", lambda e: d.destroy())

    def _tanlangan_qator():
        sel = rt.selection()
        return int(sel[0]) if sel else None

    def _ochir():
        p, i = _param(), _tanlangan_qator()
        if p is None or i is None:
            return
        rows = [list(r) for r in _joriy(p)]
        if len(rows) == 1 and p in standart:
            messagebox.showinfo("Norma", "Oxirgi qatorni o'chirib bo'lmaydi — tahrirlang.", parent=win)
            return
        del rows[i]
        _belgila(p, rows)

    def _std():
        p = _param()
        if p and p in s and messagebox.askyesno("Standart", f"{p} normasi standartga qaytarilsinmi?", parent=win):
            s.pop(p, None)
            _plist(p)
            _rlist()

    rb = ttk.Frame(right)
    rb.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(rb, text="＋ Qator", command=lambda: _tahrir(None)).pack(side=tk.LEFT, padx=2)
    ttk.Button(rb, text="✎ Tahrirlash", command=lambda: (_tanlangan_qator() is not None) and _tahrir(_tanlangan_qator())
               ).pack(side=tk.LEFT, padx=2)
    ttk.Button(rb, text="✖ O'chirish", command=_ochir).pack(side=tk.LEFT, padx=2)
    ttk.Button(rb, text="↺ Shu parametr standart", command=_std).pack(side=tk.LEFT, padx=12)
    rt.bind("<Double-1>", lambda e: (_tanlangan_qator() is not None) and _tahrir(_tanlangan_qator()))
    pl.bind("<<TreeviewSelect>>", _rlist)

    def _saqla():
        if saqla(s):
            messagebox.showinfo("Saqlandi", "[OK] Gemotologiya normalari saqlandi.\n"
                                "Gemotologiya oynasi va blankalarda darhol qo'llanadi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Saqlab bo'lmadi!", parent=win)

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    _plist(params[0] if params else None)
    _rlist()
    win.bind("<Escape>", lambda e: win.destroy())
    return win
