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
    """Joriy sozlama — bazadan (hamma kompyuterda bir xil), baza ishlamasa mahalliy
    nusxa (markaziy_sozlama). Faqat o'zgarganda qayta quriladi."""
    import markaziy_sozlama as _ms
    return _ms.modul_sozlama("gemo_blanka", _toza, _KESH, force)


def saqla(s: dict) -> bool:
    """Bazaga (va mahalliy nusxaga) yozish."""
    import markaziy_sozlama as _ms
    return _ms.modul_saqla("gemo_blanka", _toza, s, _KESH)



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
    from blanka_qator_ui import QatorJadvali

    s = json.loads(json.dumps(sozlama(force=True)))

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
    jad = QatorJadvali(
        mid, s["qatorlar"], DEFAULT_QATORLAR,
        [("kod", "Kod", 70, False), ("nom", "Blankadagi nomi (Ko'rsatkich)", 330, False),
         ("qisqa", "Qisqa nom", 80, False), ("birlik", "Birlik", 70, False),
         ("norma", "Standart norma", 100, False), ("kodlar", "Analizator kodlari", 160, True)],
        KORSAT, _toza_qator,
        yordam=("• Kod — analizatordan kelgan natija kaliti (WBC, Lymph#, Mid% ...). Yangi parametr "
                "uchun istalgan qisqa kod yozing (masalan IG#, NRBC%).\n"
                "• Analizator kodlari — analizator shu ko'rsatkichni qanday nom/raqam bilan yuborsa "
                "(OBX-3 / ASTM), vergul bilan: masalan  IG#, 10014. Dastur tanimagan kodlar "
                "logs\\bc20s_YYYYMMDD.log faylida «Noma'lum kodlar» qatorida ko'rinadi.\n"
                "• Avto — 5-diff qatorlar faqat natija bo'lsa, Mid/Gran 5-diff natijada yashiriladi, "
                "qo'shimcha qatorlar faqat natija bo'lsa chiqadi.\n"
                "• Standart norma — yosh/jinsga mos norma topilmasa ishlatiladi."))

    def _standart():
        if not messagebox.askyesno("Standart", "Barcha qatorlar va sozlamalar standart holatga "
                                   "qaytarilsinmi?\n(Qo'shilgan qatorlar o'chadi.)", parent=win):
            return
        jad.standartga()
        v_sarl.set(DEFAULT["sarlavha"]); v_anal.set("")
        v_meta.set(True); v_qisq.set(True); v_hist.set(True)

    def _yig():
        return {"sarlavha": v_sarl.get().strip() or DEFAULT["sarlavha"],
                "analizator_nomi": v_anal.get().strip(),
                "meta_qatori": bool(v_meta.get()), "qisqa_nom_ustuni": bool(v_qisq.get()),
                "gistogramma": bool(v_hist.get()), "qatorlar": jad.qatorlar}

    def _namuna():
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
    ttk.Button(bot, text="↺ Standart", command=_standart).pack(side=tk.RIGHT, padx=4)
    if namuna_fn is not None:
        ttk.Button(bot, text="👁 Namuna blanka (Word)", command=_namuna).pack(side=tk.LEFT, padx=4)

    win.bind("<Escape>", lambda e: win.destroy())
    return win
