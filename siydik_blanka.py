"""
Siydikning umumiy tahlili — BLANKA va KIRITISH sozlamasi (mijozga moslash).

Har laboratoriyada siydik tahlili har xil qilinadi:
  • analizator (URIT-50, Mindray UA-66, Dirui H ...) yoki analizatorsiz — TEST POLOSKA
    bilan ko'z bilan o'qiladi (kichik laboratoriyalar);
  • poloska 11 / 12 / 14 parametrli, darajalari (±, +1 (70) ...) brendga qarab farq qiladi;
  • ko'rsatkichlar blankada har xil nomlanadi, ba'zi bo'limlar kerak emas.

Shu modul orqali sozlanadi (kodga tegmasdan):
  • Kiritish usuli: "analizator" (natija analizatordan, kelmasa qo'lda taklif) yoki
    "qolda" (analizator yo'q — test poloska oynasi darhol ochiladi)
  • Kimyoviy qatorlar: nom, kod, birlik, norma, tartib, ko'rinish, qo'lda kiritish
    variantlari (poloska darajalari), analizator kodlari (boshqa nom bilan yuborsa)
  • Mikroskopiya qatorlari: nom, norma, birlik, tartib, ko'rinish, yangi qator
  • Fizik xossalar / mikroskopiya bo'limi, "Kod" ustuni, analizator nomi

Saqlanadi: analizator_config.json → "siydik_blanka" (Tizim Sozlamalari → 🟡 Siydik →
«🧾 Blanka va kiritish»). Yo'q bo'lsa — standart (oldingi blanka bilan bir xil).
"""

import json
import os
import re

# ─────────────────────────────────────────────────────────────────────────────
#  STANDART QATORLAR
# ─────────────────────────────────────────────────────────────────────────────
ACR_BOSQICH_NORMA = ("A1 (norma): 0-3.3; "
                     "A2 (mikroalbuminuriya): 3.4-33.9; "
                     "A3 (klinik albuminuriya): 34-999")


def _k(kod, nom, birlik, norma, variantlar=()):
    return {"kod": kod, "nom": nom, "qisqa": kod, "birlik": birlik, "norma": norma,
            "korsat": "auto", "variantlar": list(variantlar), "kodlar": []}


DEFAULT_KIMYOVIY = [
    _k("LEU", "Leykotsit", "Leyk/mkl", "(0) manfiy",
       ["manfiy", "± (15)", "+1 (70)", "+2 (125)", "+3 (500)"]),
    _k("KET", "Keton", "Mmol/l", "(0) manfiy",
       ["manfiy", "± (0.5)", "+1 (1.5)", "+2 (4.0)", "+3 (8.0)"]),
    _k("NIT", "Nitritlar", "Mmol/l", "(0) manfiy", ["manfiy", "musbat"]),
    _k("URO", "Urobilinogen", "Mkmol/l", "(3.2-16)  normal",
       ["normal", "+1 (33)", "+2 (66)", "+3 (131)"]),
    _k("BIL", "Bilirubin", "Mkmol/l", "(0) manfiy",
       ["manfiy", "+1 (8.6)", "+2 (33)", "+3 (100)"]),
    _k("GLU", "Glyukoza", "Mmol/l", "<2.8",
       ["manfiy", "± (5.5)", "+1 (14)", "+2 (28)", "+3 (55)", "+4 (111)"]),
    _k("PRO", "Oqsil", "G/l", "<0.15",
       ["manfiy", "± (0.15)", "+1 (0.3)", "+2 (1.0)", "+3 (3.0)"]),
    _k("SG", "Nisbiy zich.", "g/l", "1.010-1.025",
       ["1.000", "1.005", "1.010", "1.015", "1.020", "1.025", "1.030"]),
    _k("PH", "pH", "", "5.5-7.0",
       ["5.0", "5.5", "6.0", "6.5", "7.0", "7.5", "8.0", "8.5", "9.0"]),
    _k("BLD", "Qon", "Erit/mkl", "<10",
       ["manfiy", "± (10)", "+1 (25)", "+2 (80)", "+3 (200)"]),
    _k("Vc", "Askorbin", "Mmol/l", "(0) manfiy",
       ["manfiy", "± (0.6)", "+1 (1.4)", "+2 (2.8)"]),
    _k("MA", "Mikroalbumin", "Mg/l", "<20", ["10", "30", "80", "150"]),
    _k("Ca", "Kalsiy", "Mmol/l", "1.5-9.0", ["1.0", "2.5", "5.0", "7.5", "10"]),
    _k("CR", "Kreatinin", "Mmol/l", "2.0-22.0", ["0.9", "4.4", "8.8", "17.7", "26.5"]),
    _k("ACR", "Mikroalbumin/Kreatinin nisbati", "mg/mmol", ACR_BOSQICH_NORMA),
]


def _m(kod, nom, norma, birlik):
    return {"kod": kod, "nom": nom, "qisqa": kod, "birlik": birlik, "norma": norma,
            "korsat": "auto", "variantlar": [], "kodlar": []}


DEFAULT_MIKRO = [
    _m("SEC", "Epiteliy: yassi", "1.0-15", "ko'ruv maydonida"),
    _m("TEC", "Epiteliy: o'tuvchi", "manfiy", "preparatda"),
    _m("RTEC", "Epiteliy: buyrak", "manfiy", "preparatda"),
    _m("WBC", "Leykotsitlar", "0-7", "ko'ruv maydonida"),
    _m("RBC-D", "Eritrotsitlar: o'zgargan", "1-2", "ko'ruv maydonida"),
    _m("RBC-U", "Eritrotsitlar: o'zgarmagan", "0-1", "ko'ruv maydonida"),
    _m("CAST", "Silindrlar", "manfiy", "preparatda"),
    _m("MUC", "Shilliq", "manfiy", "preparatda"),
    _m("CRY", "Tuzlar", "manfiy", "preparatda"),
    _m("BACT", "Bakteriyalar", "manfiy", "preparatda"),
    _m("YEAST", "Zamburug'lar", "manfiy", "preparatda"),
]
DEFAULT_KIM_KODLAR = {q["kod"] for q in DEFAULT_KIMYOVIY}
DEFAULT_MIKRO_KODLAR = {q["kod"] for q in DEFAULT_MIKRO}

# Faqat natija bo'lsa chiqadigan standart kimyoviy qatorlar (14 parametrli poloska)
NATIJA_BOLSA_KODLAR = {"MA", "Ca", "CR", "ACR"}

KIRITISH = {
    "analizator": "Analizator (natija analizatordan keladi; kelmasa qo'lda kiritish taklif qilinadi)",
    "qolda": "Qo'lda — test poloska (analizator yo'q: oyna darhol qo'lda kiritish rejimida ochiladi)",
}

DEFAULT = {
    "kiritish": "analizator",
    "analizator_nomi": "",        # bo'sh = Tizim Sozlamalari → Siydik dagi model nomi
    "kod_ustuni": True,
    "fizik_bolim": True,
    "mikroskopiya_bolim": True,
    "kimyoviy": DEFAULT_KIMYOVIY,
    "mikroskopiya": DEFAULT_MIKRO,
}

KORSAT = {
    "auto": "Avto",
    "doim": "Doim",
    "natija": "Natija bo'lsa",
    "yashirin": "Yashirin",
}


# ─────────────────────────────────────────────────────────────────────────────
#  O'QISH / SAQLASH (analizator_config.json → "siydik_blanka")
# ─────────────────────────────────────────────────────────────────────────────
_KESH = {"mtime": None, "cfg": None}


def _config_path():
    try:
        import monoblok_db_config as _mc
        return _mc.CONFIG_PATH
    except Exception:
        return ""


def _royxat(x):
    if isinstance(x, str):
        x = x.replace(";", ",").split(",")
    return [str(v).strip() for v in (x or []) if str(v).strip()]


def _toza_qator(q: dict) -> dict:
    kod = str(q.get("kod") or "").strip()
    return {
        "kod": kod,
        "nom": str(q.get("nom") or kod).strip(),
        "qisqa": str(q.get("qisqa") if q.get("qisqa") is not None else kod).strip(),
        "birlik": str(q.get("birlik") or "").strip(),
        "norma": str(q.get("norma") or "").strip(),
        "korsat": q.get("korsat") if q.get("korsat") in KORSAT else "auto",
        "variantlar": _royxat(q.get("variantlar")),
        "kodlar": _royxat(q.get("kodlar")),
    }


def _toza_royxat(raw, standart):
    if not (isinstance(raw, list) and raw):
        return json.loads(json.dumps(standart))
    qs = [_toza_qator(q) for q in raw if isinstance(q, dict)]
    qs = [q for q in qs if q["kod"]]
    bor = {q["kod"] for q in qs}
    return qs + [dict(q) for q in standart if q["kod"] not in bor]


def _toza(raw) -> dict:
    s = json.loads(json.dumps(DEFAULT))
    if isinstance(raw, dict):
        if raw.get("kiritish") in KIRITISH:
            s["kiritish"] = raw["kiritish"]
        if isinstance(raw.get("analizator_nomi"), str):
            s["analizator_nomi"] = raw["analizator_nomi"].strip()
        for k in ("kod_ustuni", "fizik_bolim", "mikroskopiya_bolim"):
            if k in raw:
                s[k] = bool(raw[k])
        s["kimyoviy"] = _toza_royxat(raw.get("kimyoviy"), DEFAULT_KIMYOVIY)
        s["mikroskopiya"] = _toza_royxat(raw.get("mikroskopiya"), DEFAULT_MIKRO)
    return s


def sozlama(force=False) -> dict:
    """Joriy sozlama (fayl o'zgarmaguncha keshdan)."""
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
                raw = (json.load(f) or {}).get("siydik_blanka")
        except Exception as e:
            print(f"[OGOHLANTIRISH] siydik_blanka sozlamasi o'qilmadi: {e}")
    cfg = _toza(raw)
    _KESH.update(mtime=mt, cfg=cfg, xarita_cfg=None)
    return cfg


def saqla(s: dict) -> bool:
    try:
        import monoblok_db_config as _mc
        cfg = _mc.load_config()
        cfg["siydik_blanka"] = _toza(s)
        ok = _mc.save_config(cfg)
        _KESH.update(mtime=None, cfg=None, xarita_cfg=None)
        return ok
    except Exception as e:
        print(f"[XATO] siydik_blanka saqlanmadi: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  YORDAMCHILAR (blanka, kiritish oynasi, parser)
# ─────────────────────────────────────────────────────────────────────────────
def qolda_rejimmi(s: dict = None) -> bool:
    """True — analizator yo'q, siydik natijasi qo'lda (test poloska) kiritiladi."""
    return (s or sozlama()).get("kiritish") == "qolda"


def analizator_nomi(s: dict = None) -> str:
    """Blankadagi analizator nomi: sozlamadagi nom, bo'lmasa Tizim Sozlamalaridagi model."""
    s = s or sozlama()
    if s.get("analizator_nomi"):
        return s["analizator_nomi"]
    try:
        import monoblok_db_config as _mc
        import siydik_protokol as _sp
        model = _mc.get_analyzer("siydik").get("model") or "urit50"
        name = _sp.PROFILES.get(model, {}).get("name", "")
        short = name.split("(")[0].split("/")[0].strip()
        if short and not short.lower().startswith("boshqa"):
            return short
    except Exception:
        pass
    return "URIT-50"


def qiymat(vals: dict, kod: str) -> str:
    """all_analytes / mikroskopiya dan qiymat (PH ↔ pH, katta-kichik harfga chidamli)."""
    if not isinstance(vals, dict):
        return ""
    v = vals.get(kod)
    if v is None or str(v).strip() == "":
        ku = kod.upper()
        v = next((x for k, x in vals.items() if str(k).upper() == ku and str(x).strip()), "")
    return "" if v is None else str(v).strip()


def _korinadimi(q, natija, standart_kodlar, natija_bolsa=()):
    rej = q.get("korsat", "auto")
    if rej == "yashirin":
        return False
    if rej == "natija" or rej == "auto" and (q["kod"] in natija_bolsa or q["kod"] not in standart_kodlar):
        return bool(natija)
    return True


def kimyoviy_qatorlar(vals: dict, s: dict = None) -> list:
    """Blankadagi kimyoviy qatorlar tartibda: [{...qator, natija}]."""
    s = s or sozlama()
    out = []
    for q in s["kimyoviy"]:
        nat = qiymat(vals, q["kod"])
        # ACR — MA va CR dan hisoblanadi (natija bo'lmasa ham ikkalasi bo'lsa chiqadi)
        bor = nat or (q["kod"] == "ACR" and qiymat(vals, "MA") and qiymat(vals, "CR"))
        if _korinadimi(q, bor, DEFAULT_KIM_KODLAR, NATIJA_BOLSA_KODLAR):
            r = dict(q)
            r["natija"] = nat
            out.append(r)
    return out


def mikro_qatorlar(vals: dict, s: dict = None) -> list:
    s = s or sozlama()
    out = []
    for q in s["mikroskopiya"]:
        nat = qiymat(vals, q["kod"])
        # mikroskopiyada "-" = kiritilmagan/topilmadi → "natija bo'lsa" qatori chiqmaydi
        if _korinadimi(q, nat if nat != "-" else "", DEFAULT_MIKRO_KODLAR):
            r = dict(q)
            r["natija"] = nat
            out.append(r)
    return out


def qolda_qatorlar(s: dict = None) -> list:
    """Qo'lda (test poloska) kiritiladigan kimyoviy qatorlar — yashirin va ACR (hisoblanadi)siz."""
    s = s or sozlama()
    return [q for q in s["kimyoviy"] if q.get("korsat") != "yashirin" and q["kod"] != "ACR"]


def mikro_kiritish_qatorlari(s: dict = None) -> list:
    """Mikroskopiya oynasidagi qatorlar (yashirinlarsiz)."""
    s = s or sozlama()
    return [q for q in s["mikroskopiya"] if q.get("korsat") != "yashirin"]


def _son(x):
    m = re.search(r"\d+(?:\.\d+)?", str(x or "").replace(",", "."))
    return float(m.group(0)) if m else None


def patologikmi(q: dict, val: str) -> bool:
    """Qo'lda kiritilgan qiymat normadan chetmi (blankada qizil).
    Norma "a-b" yoki "<b" ko'rinishida bo'lsa — son bilan solishtiriladi;
    aks holda manfiy/normal = norma, boshqa har qanday qiymat = patologiya."""
    v = (val or "").strip().lower()
    if not v:
        return False
    norma = str(q.get("norma") or "").replace(",", ".").replace("–", "-").strip()
    lo = hi = None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", norma)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
    else:
        m = re.fullmatch(r"<\s*(\d+(?:\.\d+)?)", norma)
        if m:
            lo, hi = 0.0, float(m.group(1))
    # Faqat sof son (1.020, 6.5, 30) solishtiriladi; "+1 (14)", "± (10)" — sifat darajasi
    if lo is not None and re.fullmatch(r"[<>]?=?\s*\d+(?:[.,]\d+)?", v):
        return not (lo <= _son(v) <= hi)
    return v not in ("manfiy", "neg", "negative", "-", "(0) manfiy", "normal", "norma")


def qoshimcha_kodlar(s: dict = None) -> list:
    """Foydalanuvchi qo'shgan kimyoviy kodlar — analizator natijasidan tashlanmasin."""
    return [q["kod"] for q in (s or sozlama())["kimyoviy"] if q["kod"] not in DEFAULT_KIM_KODLAR]


def _norm_kod(x: str) -> str:
    return re.sub(r"[\s.\-_/:]", "", str(x or "")).upper()


def analizator_kod_xaritasi(s: dict = None) -> dict:
    """{ANALIZATOR_KODI (normallashgan): kimyoviy qator kodi}."""
    if s is None:
        s = sozlama()
        if _KESH.get("xarita_cfg") is s:
            return _KESH["xarita"]
    m = {}
    for q in s["kimyoviy"]:
        for raw in q.get("kodlar") or []:
            if _norm_kod(raw):
                m[_norm_kod(raw)] = q["kod"]
        if q["kod"] not in DEFAULT_KIM_KODLAR:
            m.setdefault(_norm_kod(q["kod"]), q["kod"])
    if s is _KESH.get("cfg"):
        _KESH.update(xarita_cfg=s, xarita=m)
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI (Tizim Sozlamalari → 🟡 Siydik → «🧾 Blanka va kiritish»)
# ─────────────────────────────────────────────────────────────────────────────
def ochish_oyna(parent, namuna_fn=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from blanka_qator_ui import QatorJadvali

    s = json.loads(json.dumps(sozlama(force=True)))

    win = tk.Toplevel(parent)
    win.title("🧾 Siydik tahlili — blanka va kiritish")
    win.geometry("1100x700")
    win.minsize(900, 560)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

    # ── Umumiy ────────────────────────────────────────────────────────
    t0 = ttk.Frame(nb, padding=10)
    nb.add(t0, text="  Umumiy  ")
    v_kir = tk.StringVar(value=s["kiritish"])
    ttk.Label(t0, text="Kimyoviy qism (poloska) qanday kiritiladi:",
              font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
    for i, (k, t) in enumerate(KIRITISH.items(), start=1):
        ttk.Radiobutton(t0, text=t, value=k, variable=v_kir).grid(
            row=i, column=0, columnspan=2, sticky=tk.W, padx=12, pady=2)
    v_anal = tk.StringVar(value=s["analizator_nomi"])
    ttk.Label(t0, text="Blankadagi analizator nomi:").grid(row=4, column=0, sticky=tk.W, pady=(14, 2))
    ttk.Entry(t0, textvariable=v_anal, width=30).grid(row=4, column=1, sticky=tk.W, padx=6, pady=(14, 2))
    ttk.Label(t0, text=f"bo'sh = model nomi (hozir: {analizator_nomi(_toza({}))})",
              foreground="#777").grid(row=5, column=1, sticky=tk.W, padx=6)
    v_kod = tk.BooleanVar(value=s["kod_ustuni"])
    v_fiz = tk.BooleanVar(value=s["fizik_bolim"])
    v_mik = tk.BooleanVar(value=s["mikroskopiya_bolim"])
    ttk.Checkbutton(t0, text="«Kod» ustuni (LEU, KET ...)", variable=v_kod).grid(
        row=6, column=0, columnspan=2, sticky=tk.W, pady=(12, 2))
    ttk.Checkbutton(t0, text="Fizik xossalar bo'limi (miqdori, rangi, tiniqligi)", variable=v_fiz).grid(
        row=7, column=0, columnspan=2, sticky=tk.W, pady=2)
    ttk.Checkbutton(t0, text="Cho'kma mikroskopiyasi bo'limi", variable=v_mik).grid(
        row=8, column=0, columnspan=2, sticky=tk.W, pady=2)
    ttk.Label(t0, foreground="#555", justify=tk.LEFT, wraplength=900, text=(
        "• Analizator rejimida ham natija kelmasa (yoki analizator ID/barkod yubormasa) — siydik "
        "tahliliga bosilganda «Qo'lda kiritish» yoki «Siydik oynasidan analizator natijasini "
        "tanlash» taklif qilinadi.\n"
        "• Qo'lda rejimida poloska darajalari «Kimyoviy» varag'idagi «Qo'lda variantlar» "
        "ustunidan olinadi — o'z poloskangiz brendiga moslang (masalan Uriscan, Combur, Dirui).\n"
        "• Analizator umuman yo'q bo'lsa — Tizim Sozlamalari → Siydik dagi «Yoqilgan» belgisini "
        "ham olib tashlang (ulanish xizmati behuda ishga tushmasin)."
    )).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=(16, 0))

    # ── Kimyoviy ──────────────────────────────────────────────────────
    t1 = ttk.Frame(nb, padding=6)
    nb.add(t1, text="  Kimyoviy (poloska)  ")
    jad_k = QatorJadvali(
        t1, s["kimyoviy"], DEFAULT_KIMYOVIY,
        [("kod", "Kod", 60, False), ("nom", "Blankadagi nomi", 220, False),
         ("qisqa", "Kod ustunida", 75, False), ("birlik", "Birlik", 75, False),
         ("norma", "Norma", 110, False), ("variantlar", "Qo'lda variantlar", 230, True),
         ("kodlar", "Analizator kodlari", 120, True)],
        KORSAT, _toza_qator,
        yordam=("• Kod — dastur ichidagi kalit (LEU, KET ...). Yangi ko'rsatkich uchun qisqa kod "
                "yozing (masalan ALB).\n"
                "• Qo'lda variantlar — test poloska darajalari, vergul bilan: "
                "manfiy, ± (15), +1 (70) ... (ro'yxatdan tashqari qiymat ham yozish mumkin).\n"
                "• Analizator kodlari — analizator shu ko'rsatkichni boshqa nom bilan yuborsa "
                "(masalan ASC, UBG), vergul bilan.\n"
                "• Norma «a-b» yoki «<b» bo'lsa qo'lda kiritilgan son shu bilan solishtiriladi; "
                "aks holda manfiy/normal = norma, boshqa qiymat — qizil.\n"
                "• Avto — MA, Ca, CR, ACR va siz qo'shgan qatorlar faqat natija bo'lsa chiqadi."))

    # ── Mikroskopiya ──────────────────────────────────────────────────
    t2 = ttk.Frame(nb, padding=6)
    nb.add(t2, text="  Mikroskopiya  ")
    jad_m = QatorJadvali(
        t2, s["mikroskopiya"], DEFAULT_MIKRO,
        [("kod", "Kod", 70, False), ("nom", "Blankadagi nomi", 260, False),
         ("qisqa", "Kod ustunida", 80, False), ("norma", "Norma", 100, False),
         ("birlik", "Birlik", 140, False), ("variantlar", "Tanlov variantlari", 220, True)],
        KORSAT, _toza_qator,
        yordam=("• Yangi qator — masalan Trixomonadalar, Spermatozoidlar, Shilliq iplari.\n"
                "• Tanlov variantlari — kiritish oynasida ro'yxat (vergul bilan); bo'sh = oddiy maydon.\n"
                "• Avto — siz qo'shgan qatorlar faqat natija bo'lsa chiqadi."))

    def _yig():
        return {"kiritish": v_kir.get(), "analizator_nomi": v_anal.get().strip(),
                "kod_ustuni": bool(v_kod.get()), "fizik_bolim": bool(v_fiz.get()),
                "mikroskopiya_bolim": bool(v_mik.get()),
                "kimyoviy": jad_k.qatorlar, "mikroskopiya": jad_m.qatorlar}

    def _standart():
        if not messagebox.askyesno("Standart", "Barcha qatorlar va sozlamalar standart holatga "
                                   "qaytarilsinmi?\n(Qo'shilgan qatorlar o'chadi.)", parent=win):
            return
        jad_k.standartga()
        jad_m.standartga()
        v_kir.set("analizator"); v_anal.set("")
        v_kod.set(True); v_fiz.set(True); v_mik.set(True)

    def _namuna():
        try:
            namuna_fn(_toza(_yig()))
        except Exception as e:
            messagebox.showerror("Namuna", f"Namuna blanka yaratilmadi:\n{e}", parent=win)

    def _saqla():
        if saqla(_yig()):
            messagebox.showinfo("Saqlandi", "[OK] Siydik sozlamasi saqlandi.\n"
                                "Keyingi kiritish va blankalarda qo'llanadi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Sozlamani saqlab bo'lmadi!", parent=win)

    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1060, text=(
        "Ikki marta bosing — tahrirlash; Bo'sh joy — ko'rinishni almashtirish; ▲/▼ — tartib. "
        "Ko'k — siz qo'shgan qator, kulrang — yashirin. Rus tilidagi blankada faqat standart "
        "nomlar tarjima qilinadi."
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
