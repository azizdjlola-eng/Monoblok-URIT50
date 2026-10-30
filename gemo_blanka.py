"""
Umumiy qon tahlili (gemotologiya) BLANKASI — mijozga moslash sozlamasi.

Har laboratoriyada analizator har xil (3-diff / 5-diff, qo'shimcha IG#, NRBC,
P-LCR ...) va ko'rsatkichlar blankada har xil nomlanadi ("Monotsit + Eozinofil +
Bazofil soni" ↔ "O'rta hujayralar (MID)" ...). Shu sababli blanka qatorlari
kodga yozilmaydi — shu modul orqali sozlanadi:

  • qator nomi (Ko'rsatkich), qisqa nomi, birligi, standart normasi
  • tartibi (↑/↓) va ko'rinishi: auto / doim / natija bo'lsa / yashirin
  • YANGI qator — analizator yuboradigan, lekin dastur tanimaydigan parametr
    (masalan IG#, NRBC%); "Analizator kodlari" ga OBX/ASTM kodi yoziladi
  • gistogramma, "Qisqa nom" ustuni, analizator qatori, sarlavha

Saqlanadi: analizator_config.json → "gemo_blanka" (Tizim Sozlamalari →
🔵 Gemotologiya → «🧾 Blanka ko'rinishi»). Yo'q bo'lsa — DEFAULT_QATORLAR
(oldingi CBC_HEMA_ROWS bilan bir xil, blanka o'zgarmaydi).

Kod (kalit) = CBC JSON kaliti = gemo_protokol.DB_NAME_MAP qiymati
(WBC, Lymph#, Mid%, Neu# ...). Multi-ref norma (yosh/jins) ham shu kod bo'yicha.
"""

import json
import os

# ─────────────────────────────────────────────────────────────────────────────
#  STANDART QATORLAR (sozlama bo'lmasa shu)
# ─────────────────────────────────────────────────────────────────────────────
def _q(nom, kod, birlik, norma, korsat="auto"):
    return {"kod": kod, "nom": nom, "qisqa": kod, "birlik": birlik, "norma": norma,
            "korsat": korsat, "kodlar": []}


DEFAULT_QATORLAR = [
    _q("Leykotsitlar soni", "WBC", "10⁹/L", "4.0 – 9.0"),
    _q("Neytrofillar soni", "Neu#", "10⁹/L", "2.0 – 7.0"),
    _q("Limfotsitlar soni", "Lymph#", "10⁹/L", "0.8 – 4.0"),
    _q("Monotsitlar soni", "Mon#", "10⁹/L", "0.1 – 1.0"),
    _q("Eozinofillar soni", "Eos#", "10⁹/L", "0.02 – 0.5"),
    _q("Bazofillar soni", "Bas#", "10⁹/L", "0 – 0.1"),
    _q("Monotsit + Eozinofil + Bazofil soni", "Mid#", "10⁹/L", "0.1 – 1.5"),
    _q("Neytrofillar soni", "Gran#", "10⁹/L", "2.0 – 7.0"),
    _q("Neytrofillar ulushi", "Neu%", "%", "50 – 70"),
    _q("Limfotsitlar ulushi", "Lymph%", "%", "20 – 40"),
    _q("Monotsitlar ulushi", "Mon%", "%", "3 – 10"),
    _q("Eozinofillar ulushi", "Eos%", "%", "0.5 – 5"),
    _q("Bazofillar ulushi", "Bas%", "%", "0 – 1"),
    _q("Monotsit + Eozinofil + Bazofil ulushi", "Mid%", "%", "3 – 15"),
    _q("Neytrofillar ulushi", "Gran%", "%", "40 – 70"),
    _q("Eritrotsitlar soni", "RBC", "10¹²/L", "3.8 – 5.5"),
    _q("Gemoglobin", "HGB", "g/L", "120 – 160"),
    _q("Gematokrit", "HCT", "%", "36 – 48"),
    _q("Eritrotsitlarning o'rtacha hajmi", "MCV", "fL", "80 – 100"),
    _q("Eritrotsitdagi o'rtacha gemoglobin", "MCH", "pg", "27 – 34"),
    _q("Eritrotsitdagi gemoglobin konsentratsiyasi", "MCHC", "g/L", "310 – 360"),
    _q("Eritrotsitlar hajmi variatsiyasi", "RDW-CV", "%", "11 – 16"),
    _q("Eritrotsitlar hajmi tarqalish kengligi", "RDW-SD", "fL", "35 – 56"),
    _q("Trombotsitlar soni", "PLT", "10⁹/L", "100 – 400"),
    _q("Trombotsitlarning o'rtacha hajmi", "MPV", "fL", "7 – 12"),
    _q("Trombotsitlar hajmi variatsiyasi", "PDW", "%", "9 – 17"),
    _q("Trombotsitlar hajmi tarqalish kengligi", "PDW-SD", "fL", "9 – 17"),
    _q("Trombokrit", "PCT", "%", "0.10 – 0.28"),
    _q("Yirik trombotsitlar ulushi", "P-LCR", "%", "13 – 43"),
    _q("Yirik trombotsitlar soni", "P-LCC", "10⁹/L", "30 – 90"),
    _q("Neytrofil / Limfotsit nisbati", "NLR", "—", "1 – 3"),
    _q("Trombotsit / Limfotsit nisbati", "PLR", "—", "100 – 300"),
]
DEFAULT_KODLAR = {q["kod"] for q in DEFAULT_QATORLAR}

DEFAULT = {
    "sarlavha": "UMUMIY QON TAHLILI",
    "analizator_nomi": "",        # bo'sh = Tizim Sozlamalaridagi model nomi
    "meta_qatori": True,          # "Avtomatik gematologik analizator: ... namuna sample № ..."
    "qisqa_nom_ustuni": True,
    "gistogramma": True,
    "qatorlar": DEFAULT_QATORLAR,
}

# Ko'rinish rejimlari: kalit → UI yozuvi
KORSAT = {
    "auto": "Avto",
    "doim": "Doim",
    "natija": "Natija bo'lsa",
    "yashirin": "Yashirin",
}

# "auto" rejimi qoidasi (oldingi qattiq kod bilan bir xil):
#   5-diff qatorlar — faqat natija bo'lsa; 3-diff (Mid/Gran) — 5-diff natijada
#   yashiriladi, 3-diff natijada "-" bilan ham chiqadi; asosiy ko'rsatkichlar — doim;
#   qo'shimcha (P-LCR, PDW-SD, foydalanuvchi qo'shgan) — faqat natija bo'lsa.
DIFF5_KODLAR = {"Neu#", "Neu%", "Mon#", "Mon%", "Eos#", "Eos%", "Bas#", "Bas%"}
DIFF3_KODLAR = {"Mid#", "Mid%", "Gran#", "Gran%"}
NATIJA_BOLSA_KODLAR = {"PDW-SD", "P-LCR", "P-LCC"}

# CBC JSON kaliti (blanka kodi) → muqobil kalit / multi-ref (HL7) kaliti
KOD_ALIAS = {'Lymph#': 'LYM#', 'Lymph%': 'LYM%', 'Mid#': 'MID#', 'Mid%': 'MID%',
             'Gran#': 'GRAN#', 'Gran%': 'GRAN%',
             'Neu#': 'NEU#', 'Neu%': 'NEU%', 'Mon#': 'MON#', 'Mon%': 'MON%',
             'Eos#': 'EOS#', 'Eos%': 'EOS%', 'Bas#': 'BAS#', 'Bas%': 'BAS%'}


# ─────────────────────────────────────────────────────────────────────────────
#  O'QISH / SAQLASH (analizator_config.json → "gemo_blanka")
# ─────────────────────────────────────────────────────────────────────────────
_KESH = {"mtime": None, "cfg": None}


def _config_path():
    try:
        import monoblok_db_config as _mc
        return _mc.CONFIG_PATH
    except Exception:
        return ""


def _toza_qator(q: dict) -> dict:
    """Bitta qatorni to'liq va to'g'ri shaklga keltirish."""
    kod = str(q.get("kod") or "").strip()
    kodlar = q.get("kodlar") or []
    if isinstance(kodlar, str):
        kodlar = [x for x in kodlar.replace(";", ",").split(",")]
    korsat = q.get("korsat") if q.get("korsat") in KORSAT else "auto"
    return {
        "kod": kod,
        "nom": str(q.get("nom") or kod).strip(),
        "qisqa": str(q.get("qisqa") if q.get("qisqa") is not None else kod).strip(),
        "birlik": str(q.get("birlik") or "").strip(),
        "norma": str(q.get("norma") or "").strip(),
        "korsat": korsat,
        "kodlar": [str(x).strip() for x in kodlar if str(x).strip()],
    }


def _toza(raw) -> dict:
    """Saqlangan sozlamani standart ustiga qo'yish. Yangi versiyada qo'shilgan
    standart qatorlar (saqlangan ro'yxatda yo'q) oxiriga qo'shiladi."""
    s = json.loads(json.dumps(DEFAULT))
    if isinstance(raw, dict):
        for k in ("sarlavha", "analizator_nomi"):
            if isinstance(raw.get(k), str):
                s[k] = raw[k]
        for k in ("meta_qatori", "qisqa_nom_ustuni", "gistogramma"):
            if k in raw:
                s[k] = bool(raw[k])
        if isinstance(raw.get("qatorlar"), list) and raw["qatorlar"]:
            qs = [_toza_qator(q) for q in raw["qatorlar"] if isinstance(q, dict)]
            qs = [q for q in qs if q["kod"]]
            bor = {q["kod"] for q in qs}
            qs += [dict(q) for q in DEFAULT_QATORLAR if q["kod"] not in bor]
            s["qatorlar"] = qs
    if not str(s.get("sarlavha") or "").strip():
        s["sarlavha"] = DEFAULT["sarlavha"]
    return s


def sozlama(force=False) -> dict:
    """Joriy blanka sozlamasi (fayl o'zgarmaguncha keshdan)."""
    path = _config_path()
    try:
        mt = os.path.getmtime(path) if path and os.path.exists(path) else None
    except Exception:
        mt = None
    if not force and _KESH["cfg"] is not None and _KESH["mtime"] == mt:
        return _KESH["cfg"]
    raw = None
    if mt is not None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = (json.load(f) or {}).get("gemo_blanka")
        except Exception as e:
            print(f"[OGOHLANTIRISH] gemo_blanka sozlamasi o'qilmadi: {e}")
    cfg = _toza(raw)
    _KESH.update(mtime=mt, cfg=cfg)
    return cfg


def saqla(s: dict) -> bool:
    """Sozlamani analizator_config.json ga yozish (boshqa bo'limlarga tegmaydi)."""
    try:
        import monoblok_db_config as _mc
        cfg = _mc.load_config()
        cfg["gemo_blanka"] = _toza(s)
        ok = _mc.save_config(cfg)
        _KESH.update(mtime=None, cfg=None)
        return ok
    except Exception as e:
        print(f"[XATO] gemo_blanka saqlanmadi: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  BLANKA / PARSER UCHUN YORDAMCHILAR
# ─────────────────────────────────────────────────────────────────────────────
def qiymat(vals: dict, kod: str) -> str:
    """CBC JSON dan kod (yoki muqobil kaliti) bo'yicha natija matni."""
    v = vals.get(kod)
    if v is None or str(v).strip() == "":
        v = vals.get(KOD_ALIAS.get(kod, ""))
    return "" if v is None else str(v).strip()


def has_5diff(vals: dict) -> bool:
    return any(qiymat(vals, k) for k in DIFF5_KODLAR)


def korinadigan_qatorlar(vals: dict, s: dict = None) -> list:
    """Blankada chiqadigan qatorlar tartibda: [{kod, nom, qisqa, birlik, norma, natija}].
    natija bo'sh bo'lishi mumkin (blankada "-")."""
    s = s or sozlama()
    d5 = has_5diff(vals)
    out = []
    for q in s["qatorlar"]:
        kod = q["kod"]
        natija = qiymat(vals, kod)
        rej = q.get("korsat", "auto")
        if rej == "yashirin":
            continue
        if rej == "natija" and not natija:
            continue
        if rej == "auto" and not natija:
            if kod in DIFF5_KODLAR or (kod in DIFF3_KODLAR and d5):
                continue
            if kod in NATIJA_BOLSA_KODLAR or kod not in DEFAULT_KODLAR:
                continue
        r = dict(q)
        r["natija"] = natija
        out.append(r)
    return out


def barcha_kodlar(s: dict = None) -> list:
    """Sozlamadagi barcha qator kodlari (tartibda)."""
    return [q["kod"] for q in (s or sozlama())["qatorlar"]]


def qoshimcha_kodlar(s: dict = None) -> list:
    """Foydalanuvchi qo'shgan (standartda yo'q) qator kodlari — parser/oyna ularni tashlab yubormasin."""
    return [k for k in barcha_kodlar(s) if k not in DEFAULT_KODLAR]


def _norm_kod(x: str) -> str:
    return str(x or "").strip().upper().replace(" ", "")


def analizator_kod_xaritasi(s: dict = None) -> dict:
    """{ANALIZATOR_KODI (upper, bo'sh joysiz): qator kodi} — "Analizator kodlari" ustunidan
    va foydalanuvchi qo'shgan qatorning o'z kodidan."""
    if s is None:
        s = sozlama()
        if _KESH.get("xarita_cfg") is s:      # parser har OBX da chaqiradi — kesh
            return _KESH["xarita"]
    m = {}
    for q in s["qatorlar"]:
        for raw in q.get("kodlar") or []:
            if _norm_kod(raw):
                m[_norm_kod(raw)] = q["kod"]
        if q["kod"] not in DEFAULT_KODLAR:
            m.setdefault(_norm_kod(q["kod"]), q["kod"])
    if s is _KESH.get("cfg"):
        _KESH.update(xarita_cfg=s, xarita=m)
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI (Tizim Sozlamalari → 🔵 Gemotologiya → «🧾 Blanka ko'rinishi»)
# ─────────────────────────────────────────────────────────────────────────────
def ochish_oyna(parent, namuna_fn=None):
    """Blanka qatorlarini tahrirlash oynasi.
    namuna_fn(sozlama_dict) — joriy (saqlanmagan) sozlama bilan namuna blanka ochadi."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    s = json.loads(json.dumps(sozlama(force=True)))
    qatorlar = s["qatorlar"]

    win = tk.Toplevel(parent)
    win.title("🧾 Umumiy qon tahlili — blanka ko'rinishi")
    win.geometry("1100x700")
    win.minsize(900, 560)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    # ── Umumiy sozlamalar ─────────────────────────────────────────────
    top = ttk.LabelFrame(win, text="Blanka")
    top.pack(fill=tk.X, padx=8, pady=(8, 4))
    v_sarl = tk.StringVar(value=s["sarlavha"])
    v_anal = tk.StringVar(value=s["analizator_nomi"])
    v_meta = tk.BooleanVar(value=s["meta_qatori"])
    v_qisq = tk.BooleanVar(value=s["qisqa_nom_ustuni"])
    v_hist = tk.BooleanVar(value=s["gistogramma"])
    ttk.Label(top, text="Sarlavha:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=3)
    ttk.Entry(top, textvariable=v_sarl, width=36).grid(row=0, column=1, sticky=tk.W, padx=4)
    ttk.Label(top, text="Analizator nomi (bo'sh = model nomi):").grid(row=0, column=2, sticky=tk.W, padx=(16, 4))
    ttk.Entry(top, textvariable=v_anal, width=26).grid(row=0, column=3, sticky=tk.W, padx=4)
    ttk.Checkbutton(top, text="Analizator / namuna № qatori", variable=v_meta).grid(
        row=1, column=0, columnspan=2, sticky=tk.W, padx=6, pady=3)
    ttk.Checkbutton(top, text="«Qisqa nom» ustuni", variable=v_qisq).grid(
        row=1, column=2, sticky=tk.W, padx=(16, 4))
    ttk.Checkbutton(top, text="Gistogrammalar (WBC / RBC / PLT)", variable=v_hist).grid(
        row=1, column=3, sticky=tk.W, padx=4)

    # ── Qatorlar jadvali ──────────────────────────────────────────────
    mid = ttk.Frame(win)
    mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    cols = ("korsat", "kod", "nom", "qisqa", "birlik", "norma", "kodlar")
    hdrs = {"korsat": "Ko'rinish", "kod": "Kod", "nom": "Blankadagi nomi (Ko'rsatkich)",
            "qisqa": "Qisqa nom", "birlik": "Birlik", "norma": "Standart norma",
            "kodlar": "Analizator kodlari"}
    widths = {"korsat": 95, "kod": 70, "nom": 330, "qisqa": 80, "birlik": 70, "norma": 100, "kodlar": 160}
    tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")
    for c in cols:
        tree.heading(c, text=hdrs[c])
        tree.column(c, width=widths[c], anchor=tk.W if c in ("nom", "kodlar") else tk.CENTER,
                    stretch=(c == "nom"))
    tree.tag_configure("yashirin", foreground="#999999")
    tree.tag_configure("yangi", foreground="#1565C0")
    sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.LEFT, fill=tk.Y)

    def _yangila(sel_idx=None):
        tree.delete(*tree.get_children())
        for i, q in enumerate(qatorlar):
            tags = []
            if q["korsat"] == "yashirin":
                tags.append("yashirin")
            elif q["kod"] not in DEFAULT_KODLAR:
                tags.append("yangi")
            tree.insert("", tk.END, iid=str(i), tags=tags, values=(
                KORSAT.get(q["korsat"], q["korsat"]), q["kod"], q["nom"], q["qisqa"],
                q["birlik"], q["norma"], ", ".join(q.get("kodlar") or [])))
        if sel_idx is not None and 0 <= sel_idx < len(qatorlar):
            tree.selection_set(str(sel_idx))
            tree.see(str(sel_idx))

    def _tanlangan():
        sel = tree.selection()
        return int(sel[0]) if sel else None

    # ── Bitta qatorni tahrirlash ──────────────────────────────────────
    def _tahrir(idx=None):
        yangi = idx is None
        q = _toza_qator({"kod": "", "korsat": "auto"}) if yangi else dict(qatorlar[idx])
        d = tk.Toplevel(win)
        d.title("Yangi qator" if yangi else f"Qator: {q['kod']}")
        d.transient(win)
        try:
            d.grab_set()
        except Exception:
            pass
        vs = {}
        maydonlar = [
            ("kod", "Kod (kalit):"), ("nom", "Blankadagi nomi:"), ("qisqa", "Qisqa nom:"),
            ("birlik", "Birlik:"), ("norma", "Standart norma:"), ("kodlar", "Analizator kodlari:"),
        ]
        for r, (k, lbl) in enumerate(maydonlar):
            ttk.Label(d, text=lbl).grid(row=r, column=0, sticky=tk.W, padx=8, pady=4)
            val = ", ".join(q.get("kodlar") or []) if k == "kodlar" else q.get(k, "")
            v = tk.StringVar(value=val)
            e = ttk.Entry(d, textvariable=v, width=52 if k == "nom" else 30)
            e.grid(row=r, column=1, sticky=tk.W, padx=8, pady=4)
            if k == "kod" and not yangi:
                e.configure(state="readonly")   # kod = natija kaliti; standart qatorda o'zgarmaydi
            vs[k] = v
        r = len(maydonlar)
        ttk.Label(d, text="Ko'rinish:").grid(row=r, column=0, sticky=tk.W, padx=8, pady=4)
        v_k = tk.StringVar(value=KORSAT[q["korsat"]])
        ttk.Combobox(d, textvariable=v_k, values=list(KORSAT.values()), state="readonly",
                     width=16).grid(row=r, column=1, sticky=tk.W, padx=8, pady=4)
        ttk.Label(d, foreground="#555", justify=tk.LEFT, wraplength=520, text=(
            "• Kod — analizatordan kelgan natija kaliti (WBC, Lymph#, Mid% ...). Yangi parametr "
            "uchun istalgan qisqa kod yozing (masalan IG#, NRBC%).\n"
            "• Analizator kodlari — analizator shu ko'rsatkichni qanday nom/raqam bilan yuborsa "
            "(OBX-3 / ASTM), vergul bilan: masalan  IG#, 10014. Dastur tanimagan kodlar "
            "logs\\bc20s_YYYYMMDD.log faylida «Noma'lum kodlar» qatorida ko'rinadi.\n"
            "• Avto — 5-diff qatorlar faqat natija bo'lsa, Mid/Gran 5-diff natijada yashiriladi, "
            "qo'shimcha qatorlar faqat natija bo'lsa chiqadi.\n"
            "• Standart norma — yosh/jinsga mos norma topilmasa ishlatiladi.")
        ).grid(row=r + 1, column=0, columnspan=2, sticky=tk.W, padx=8, pady=(6, 4))

        def _ok():
            kod = vs["kod"].get().strip()
            if not kod:
                messagebox.showwarning("Kod", "Kod bo'sh bo'lmasin.", parent=d)
                return
            if yangi and any(x["kod"].upper() == kod.upper() for x in qatorlar):
                messagebox.showwarning("Kod", f"«{kod}» kodi allaqachon bor.", parent=d)
                return
            rej = next((k for k, t in KORSAT.items() if t == v_k.get()), "auto")
            nq = _toza_qator({
                "kod": kod, "nom": vs["nom"].get(), "qisqa": vs["qisqa"].get(),
                "birlik": vs["birlik"].get(), "norma": vs["norma"].get(),
                "kodlar": vs["kodlar"].get(), "korsat": rej})
            if not vs["nom"].get().strip():
                nq["nom"] = kod
            if yangi:
                pos = _tanlangan()
                pos = len(qatorlar) if pos is None else pos + 1
                qatorlar.insert(pos, nq)
            else:
                pos = idx
                qatorlar[idx] = nq
            d.destroy()
            _yangila(pos)

        bf = ttk.Frame(d)
        bf.grid(row=r + 2, column=0, columnspan=2, sticky=tk.E, padx=8, pady=8)
        ttk.Button(bf, text="OK", command=_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="Bekor", command=d.destroy).pack(side=tk.RIGHT, padx=4)
        d.bind("<Return>", lambda e: _ok())
        d.bind("<Escape>", lambda e: d.destroy())

    def _tahrir_tanlangan(_e=None):
        i = _tanlangan()
        if i is not None:
            _tahrir(i)

    def _kochir(delta):
        i = _tanlangan()
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(qatorlar):
            qatorlar[i], qatorlar[j] = qatorlar[j], qatorlar[i]
            _yangila(j)

    def _korinish_almashtir(_e=None):
        """Bo'sh joy — Ko'rinish rejimini navbat bilan almashtirish."""
        i = _tanlangan()
        if i is None:
            return
        keys = list(KORSAT)
        qatorlar[i]["korsat"] = keys[(keys.index(qatorlar[i]["korsat"]) + 1) % len(keys)]
        _yangila(i)

    def _ochir():
        i = _tanlangan()
        if i is None:
            return
        q = qatorlar[i]
        if q["kod"] in DEFAULT_KODLAR:
            if messagebox.askyesno("Standart qator",
                                   f"«{q['nom']}» standart qator — o'chirib bo'lmaydi.\n"
                                   "Yashirin qilinsinmi?", parent=win):
                q["korsat"] = "yashirin"
                _yangila(i)
            return
        if messagebox.askyesno("O'chirish", f"«{q['nom']}» ({q['kod']}) qatori o'chirilsinmi?", parent=win):
            del qatorlar[i]
            _yangila(min(i, len(qatorlar) - 1))

    def _standart():
        if not messagebox.askyesno("Standart", "Barcha qatorlar va sozlamalar standart holatga "
                                   "qaytarilsinmi?\n(Qo'shilgan qatorlar o'chadi.)", parent=win):
            return
        qatorlar[:] = json.loads(json.dumps(DEFAULT_QATORLAR))
        v_sarl.set(DEFAULT["sarlavha"]); v_anal.set("")
        v_meta.set(True); v_qisq.set(True); v_hist.set(True)
        _yangila(0)

    def _yig():
        return {"sarlavha": v_sarl.get().strip() or DEFAULT["sarlavha"],
                "analizator_nomi": v_anal.get().strip(),
                "meta_qatori": bool(v_meta.get()), "qisqa_nom_ustuni": bool(v_qisq.get()),
                "gistogramma": bool(v_hist.get()), "qatorlar": qatorlar}

    def _namuna():
        if namuna_fn is None:
            return
        try:
            namuna_fn(_toza(_yig()))
        except Exception as e:
            messagebox.showerror("Namuna", f"Namuna blanka yaratilmadi:\n{e}", parent=win)

    def _saqla():
        if saqla(_yig()):
            messagebox.showinfo("Saqlandi", "[OK] Blanka sozlamasi saqlandi.\n"
                                "Keyingi yaratiladigan blankalarda qo'llanadi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Sozlamani saqlab bo'lmadi!", parent=win)

    side = ttk.Frame(mid)
    side.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
    for txt, cmd in [("▲ Yuqoriga", lambda: _kochir(-1)), ("▼ Pastga", lambda: _kochir(1)),
                     ("✎ Tahrirlash", _tahrir_tanlangan), ("👁 Ko'rinish", _korinish_almashtir),
                     ("＋ Yangi qator", lambda: _tahrir(None)), ("✖ O'chirish", _ochir),
                     ("↺ Standart", _standart)]:
        ttk.Button(side, text=txt, command=cmd, width=16).pack(fill=tk.X, pady=2)

    tree.bind("<Double-1>", _tahrir_tanlangan)
    tree.bind("<Return>", _tahrir_tanlangan)
    tree.bind("<space>", _korinish_almashtir)
    tree.bind("<Delete>", lambda e: _ochir())

    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1060, text=(
        "Ikki marta bosing — tahrirlash; Bo'sh joy — ko'rinishni almashtirish; ▲/▼ — tartib. "
        "Ko'k — siz qo'shgan qator, kulrang — yashirin. Rus tilidagi blankada faqat standart "
        "nomlar tarjima qilinadi (o'zgartirilgan nom o'zidek chiqadi)."
    )).pack(fill=tk.X, padx=10, pady=(2, 2))

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    if namuna_fn is not None:
        ttk.Button(bot, text="👁 Namuna blanka (Word)", command=_namuna).pack(side=tk.LEFT, padx=4)

    _yangila(0)
    win.bind("<Escape>", lambda e: win.destroy())
    return win
