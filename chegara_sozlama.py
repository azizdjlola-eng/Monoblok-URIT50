"""
Kritik qiymat, delta-check va analizator signal chegaralari — sozlash oynasi.

Ilgari bu chegaralar faqat JSON fayllarda edi (lab_quality.json, alert_config.json) —
o'zgartirish uchun fayl ochish kerak edi, har kompyuterda alohida. Bundan tashqari
kritik qiymat / delta-check KATALOG ID si bo'yicha (41 = Kreatinin, 27 = Umumiy qon ...)
yozilgan — boshqa mijoz katalogida bu ID boshqa tahlil bo'lishi mumkin.

Endi:
  • Tizim Sozlamalari → 🧩 Maxsus tahlillar → «🚨 Kritik qiymat va signal chegaralari»;
  • har ID yonida KATALOGDAGI nomi ko'rsatiladi; mos kelmasa — «⚠» (yangi o'rnatishda
    darhol ko'rinadi);
  • saqlanadi bazada (markaziy_sozlama: "lab_quality", "alert_config") — hamma
    kompyuterda bir xil; lab_quality / critical_alert load_config() uni fayl ustidan qo'yadi.
"""

import json

KORSAT = {"auto": "Yoqilgan", "yashirin": "O'chirilgan"}


def _f(x):
    s = str(x if x is not None else "").strip().replace(",", ".")
    if s == "" or s.lower() in ("none", "-"):
        return None
    return float(s)


def _fs(x):
    return "" if x is None else (str(int(x)) if float(x) == int(float(x)) else f"{float(x):g}")


def _royxat_matn(lst):
    """['temir', ' fe'] → 'temir;  fe' (birinchidan keyingi «; » ajratuvchi)."""
    return "; ".join(lst or [])


def _royxat(matn):
    """'temir;  fe' → ['temir', ' fe']. Ataylab qo'yilgan bo'shliq saqlanadi (" fe" —
    "ferritin" ga mos kelmasin); faqat «; » ajratuvchidagi bitta bo'shliq olinadi.
    «;» bo'lmasa — vergul bilan (to'liq tozalab)."""
    s = str(matn or "")
    if ";" not in s:
        return [x.strip().lower() for x in s.split(",") if x.strip()]
    out = []
    for i, x in enumerate(s.split(";")):
        if i and x.startswith(" "):
            x = x[1:]
        if x.strip():
            out.append(x.lower())
    return out


def _katalog():
    try:
        import mysql.connector
        from monoblok_db_config import DB_CONFIG
        c = mysql.connector.connect(**DB_CONFIG)
        cur = c.cursor()
        cur.execute("SELECT id, nomi FROM tahlillar")
        d = {int(i): str(n or "") for i, n in cur.fetchall()}
        c.close()
        return d
    except Exception as e:
        print(f"[OGOHLANTIRISH] chegara_sozlama: katalog o'qilmadi: {e}")
        return {}


def _norm(s):
    s = str(s or "").lower()
    for ch in ("'", "‘", "’", "`", "ʻ", "(", ")", ",", "."):
        s = s.replace(ch, " ")
    return set(w for w in s.split() if len(w) > 2)


def _katalog_nomi(kalit, nom, kat):
    """ID (yoki "ID.komponent") ning katalogdagi nomi; nom bilan mos kelmasa «⚠»."""
    try:
        tid = int(str(kalit).split(".")[0])
    except ValueError:
        return "⚠ kalit ID emas"
    if not kat:
        return "(katalog o'qilmadi)"
    kn = kat.get(tid)
    if kn is None:
        return "⚠ katalogda yo'q"
    if "." not in str(kalit) and _norm(nom) and not (_norm(nom) & _norm(kn)):
        return f"⚠ {kn}"
    return kn


# ── lab_quality (panic / delta) ↔ jadval qatorlari ────────────────────────
def _lq_qatorlar(section, kat, maydonlar):
    out = []
    for k, v in (section or {}).items():
        if str(k).startswith("_") or not isinstance(v, dict):
            continue
        q = {"kod": str(k), "name": v.get("name", ""), "unit": v.get("unit", ""),
             "katalog": _katalog_nomi(k, v.get("name", ""), kat), "korsat": "auto"}
        for m in maydonlar:
            q[m] = _fs(v.get(m))
        out.append(q)
    return out


def _lq_dict(qatorlar, maydonlar):
    out = {}
    for q in qatorlar:
        if q.get("korsat") == "yashirin":
            continue
        d = {"name": q.get("name", ""), "unit": q.get("unit", "")}
        for m in maydonlar:
            d[m] = _f(q.get(m))
        out[q["kod"]] = d
    return out


def ochish_oyna(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from blanka_qator_ui import QatorJadvali
    import lab_quality
    import critical_alert
    import markaziy_sozlama as _ms

    kat = _katalog()
    lq = json.loads(json.dumps(lab_quality.load_config(force=True)))
    ca = json.loads(json.dumps(critical_alert.load_config(force=True)))
    lq_std = json.loads(json.dumps(lab_quality.DEFAULT_CONFIG))
    ca_std = json.loads(json.dumps(critical_alert.DEFAULT_CONFIG))

    win = tk.Toplevel(parent)
    win.title("🚨 Kritik qiymat va signal chegaralari")
    win.geometry("1150x680")
    win.minsize(950, 520)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass
    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1100, text=(
        "«Kalit» = katalogdagi tahlil ID si (ko'p komponentli tahlilda «ID.komponent», masalan "
        "73.pt_mno). «Katalogdagi nomi» ustunida ⚠ bo'lsa — bu ID katalogingizda BOSHQA tahlil: "
        "tahrirlab to'g'ri ID yozing yoki o'chiring. Bo'sh chegara = tekshirilmaydi. "
        "Bir komponentli tahlil uchun «Tahlil Qo'shish» oynasidagi «Ogohlantirish» chegarasi "
        "bu yerdagidan ustun.")).pack(fill=tk.X, padx=10, pady=(8, 4))
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def _toza(fields):
        def t(q):
            d = dict(q)
            for k in fields:
                v = str(d.get(k, "") or "").strip().replace(",", ".")
                if v:
                    try:
                        float(v)
                    except ValueError:
                        v = ""      # son emas — bo'sh (tekshirilmaydi)
                d[k] = v
            d["kod"] = str(d.get("kod") or "").strip()
            d["katalog"] = _katalog_nomi(d["kod"], d.get("name", ""), kat)
            d["korsat"] = d.get("korsat") if d.get("korsat") in KORSAT else "auto"
            return d
        return t

    # 1) Kritik qiymat
    t1 = ttk.Frame(nb, padding=6)
    nb.add(t1, text="  Kritik qiymat (panic)  ")
    v_pe = tk.BooleanVar(value=bool(lq.get("panic", {}).get("enabled", True)))
    ttk.Checkbutton(t1, text="Kritik qiymat tekshiruvi yoqilgan", variable=v_pe).pack(anchor="w", pady=(0, 4))
    pf = ("low", "high")
    jad_p = QatorJadvali(
        t1, _lq_qatorlar(lq.get("panic", {}).get("analytes"), kat, pf),
        _lq_qatorlar(lq_std.get("panic", {}).get("analytes"), kat, pf),
        [("kod", "Kalit (ID)", 90, False), ("katalog", "Katalogdagi nomi", 260, False),
         ("name", "Nomi", 200, False), ("unit", "Birlik", 80, False),
         ("low", "Past (kritik)", 100, False), ("high", "Baland (kritik)", 100, False)],
        KORSAT, _toza(pf), faqat_oqish=("katalog",),
        yordam="Past / Baland — shundan past yoki baland natija KRITIK (vrachga darhol xabar).")

    # 2) Delta-check
    t2 = ttk.Frame(nb, padding=6)
    nb.add(t2, text="  Delta-check  ")
    dd = lq.get("delta", {})
    fr = ttk.Frame(t2)
    fr.pack(anchor="w", pady=(0, 4))
    v_de = tk.BooleanVar(value=bool(dd.get("enabled", True)))
    v_dk = tk.StringVar(value=str(dd.get("max_days", 365)))
    ttk.Checkbutton(fr, text="Delta-check yoqilgan", variable=v_de).pack(side=tk.LEFT)
    ttk.Label(fr, text="   Oldingi natija necha kundan eski bo'lsa solishtirilmaydi:").pack(side=tk.LEFT)
    ttk.Entry(fr, textvariable=v_dk, width=6).pack(side=tk.LEFT, padx=4)
    df = ("pct", "abs_min")
    jad_d = QatorJadvali(
        t2, _lq_qatorlar(dd.get("analytes"), kat, df),
        _lq_qatorlar(lq_std.get("delta", {}).get("analytes"), kat, df),
        [("kod", "Kalit (ID)", 90, False), ("katalog", "Katalogdagi nomi", 260, False),
         ("name", "Nomi", 200, False), ("unit", "Birlik", 80, False),
         ("pct", "O'zgarish %", 100, False), ("abs_min", "Kamida farq", 100, False)],
        KORSAT, _toza(df), faqat_oqish=("katalog",),
        yordam="O'zgarish % — oldingi natijadan shuncha foiz farq qilsa ogohlantiradi; "
               "Kamida farq — mutlaq farq bundan kichik bo'lsa ogohlantirmaydi.")

    # 3) Analizator signali (critical_alert)
    t3 = ttk.Frame(nb, padding=6)
    nb.add(t3, text="  Analizator signali  ")
    fr3 = ttk.Frame(t3)
    fr3.pack(anchor="w", pady=(0, 4))
    v_ae = tk.BooleanVar(value=bool(ca.get("enabled", True)))
    v_ap = tk.BooleanVar(value=bool(ca.get("popup", True)))
    v_as = tk.BooleanVar(value=bool(ca.get("sound", True)))
    for t, v in (("Signal yoqilgan", v_ae), ("Oyna chiqsin", v_ap), ("Ovoz", v_as)):
        ttk.Checkbutton(fr3, text=t, variable=v).pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(t3, text="Gemotologiya (kam / ko'p):", font=("Arial", 9, "bold")).pack(anchor="w")

    def _hema_q(h):
        return [{"kod": k, "low": _fs(v.get("low")), "high": _fs(v.get("high")), "korsat": "auto"}
                for k, v in (h or {}).items() if isinstance(v, dict)]
    hf = ttk.Frame(t3, height=150)
    hf.pack(fill=tk.X)
    hf.pack_propagate(False)
    jad_h = QatorJadvali(hf, _hema_q(ca.get("hematology")), _hema_q(ca_std.get("hematology")),
                         [("kod", "Parametr", 100, False), ("low", "Past", 100, False),
                          ("high", "Baland", 100, False)],
                         KORSAT, _toza(("low", "high")), yangi_qator=False)   # faqat WBC/RBC/HGB/PLT tekshiriladi
    ttk.Label(t3, text="Bioximiya (nom bo'yicha topiladi — katalog ID ga bog'liq emas):",
              font=("Arial", 9, "bold")).pack(anchor="w", pady=(8, 0))

    def _bio_q(tests):
        out = []
        for t in tests or []:
            out.append({"kod": t.get("key", ""), "match": _royxat_matn(t.get("match")),
                        "exclude": _royxat_matn(t.get("exclude")),
                        "low": _fs(t.get("low")), "high": _fs(t.get("high")),
                        "zero": "Ha" if t.get("zero") else "", "neg": "Ha" if t.get("neg") else "",
                        "_asl": t, "korsat": "auto"})
        return out
    jad_b = QatorJadvali(t3, _bio_q(ca.get("biochemistry", {}).get("tests")),
                         _bio_q(ca_std.get("biochemistry", {}).get("tests")),
                         [("kod", "Kalit", 110, False), ("match", "Nomida bo'lsa", 230, False),
                          ("exclude", "Nomida bo'lsa — tashla", 180, False),
                          ("low", "Past", 70, False), ("high", "Baland", 70, False),
                          ("zero", "0 = xato (Ha)", 90, False), ("neg", "Manfiy = xato (Ha)", 110, False)],
                         KORSAT, _toza(("low", "high")),
                         yordam="Nomida bo'lsa — nuqtali vergul bilan (masalan: kreatinin; kreatinin "
                                "kinaza). Boshidagi bo'shliq ahamiyatli (« fe» — «ferritin» ga mos "
                                "kelmasin). «0 = xato» / "
                                "«Manfiy = xato» ustuniga Ha yozing yoki bo'sh qoldiring.")

    def _saqla():
        try:
            dk = int(v_dk.get().strip() or 365)
        except ValueError:
            messagebox.showwarning("Delta-check", "Kun soni butun son bo'lishi kerak.", parent=win)
            return
        lq2 = json.loads(json.dumps(lq))
        lq2.setdefault("panic", {}).pop("_db_by_name", None)
        lq2["panic"]["enabled"] = bool(v_pe.get())
        lq2["panic"]["analytes"] = _lq_dict(jad_p.qatorlar, pf)
        lq2.setdefault("delta", {})["enabled"] = bool(v_de.get())
        lq2["delta"]["max_days"] = dk
        lq2["delta"]["analytes"] = _lq_dict(jad_d.qatorlar, df)
        ca2 = json.loads(json.dumps(ca))
        ca2.update(enabled=bool(v_ae.get()), popup=bool(v_ap.get()), sound=bool(v_as.get()))
        ca2["hematology"] = {q["kod"]: {"low": _f(q.get("low")), "high": _f(q.get("high"))}
                             for q in jad_h.qatorlar if q.get("korsat") != "yashirin"}
        tests = []
        for q in jad_b.qatorlar:
            if q.get("korsat") == "yashirin":
                continue
            t = dict(q.get("_asl") or {})      # low_msg, low_level ... saqlanadi
            t["key"] = q["kod"]
            t["match"] = _royxat(q.get("match", ""))
            ex = _royxat(q.get("exclude", ""))
            if ex:
                t["exclude"] = ex
            else:
                t.pop("exclude", None)
            for k in ("low", "high"):
                v = _f(q.get(k))
                if v is None:
                    t.pop(k, None)
                else:
                    t[k] = v
            for k in ("zero", "neg"):
                if str(q.get(k, "")).strip().lower() in ("ha", "1", "true", "x", "+"):
                    t[k] = True
                else:
                    t.pop(k, None)
            if t["match"]:
                tests.append(t)
        ca2.setdefault("biochemistry", {})["tests"] = tests
        ok = _ms.yoz("lab_quality", lq2) and _ms.yoz("alert_config", ca2)
        lab_quality.load_config(force=True)
        critical_alert.load_config(force=True)
        if ok:
            messagebox.showinfo("Saqlandi", "[OK] Chegaralar saqlandi (bazada — hamma kompyuterda).\n"
                                "Bu kompyuterda darhol, boshqalarida dastur qayta ochilganda "
                                "kuchga kiradi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Saqlab bo'lmadi!", parent=win)

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    win.bind("<Escape>", lambda e: win.destroy())
    return win
