"""
O'zbek KIRILL yozuvidagi blanka — tayyor (lotin) blankani kirillga o'giradi.

Ko'p laboratoriya va shifokorlar hali kirill yozuvida ishlaydi. Blanka odatdagidek
lotinda yaratiladi, saqlashdan oldin shu modul HAR RUN matnini kirillga o'giradi
(formatlash — qalin, rang, o'lcham — saqlanadi). Ruscha tarjima yoqilgan bo'lsa,
avval u qo'shiladi (lotin matnga qarab), keyin kirillga o'giriladi.

O'GIRILMAYDI (lotincha qoladi):
  • tahlil kodlari va qisqartmalar: 5 harfgacha KATTA harfli so'zlar (WBC, HGB, MCHC,
    ALT, CRP ...) — lekin QON, VA kabi o'zbekcha so'zlar o'giriladi;
  • raqam yoki #, % bor so'zlar (Lymph#, RDW-CV, 10⁹/L, BC-20s);
  • havola, e-pochta, sayt (http, www, @, .uz);
  • brendlar (Mindray, URIT ...) va sozlamadagi «Lotincha qoladigan so'zlar».
Birliklar o'zbek kirill blankalaridagidek: mmol/l → ммоль/л, g/l → г/л ...
"""

import re

APOS = "'‘’ʻ`"
UNLI = set("aeiouAEIOU")
HARF = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ", "i": "и",
    "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ",
    "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "x": "х", "y": "й", "z": "з",
    "c": "с", "w": "в",
}
QOSH = {"sh": "ш", "ch": "ч", "yo": "ё", "yu": "ю", "ya": "я", "ye": "е"}

# O'zbekcha qisqa katta harfli so'zlar — kod emas, o'giriladi
OZBEK_QISQA = {"QON", "VA", "BILAN", "UCHUN", "SOAT", "KUN", "TEST", "ERKAK", "AYOL", "YOSH",
               "NOMI", "SANA", "TEL", "NORMA", "KOD", "TURI", "JINS"}
# Brendlar / lotincha qolishi odat bo'lgan so'zlar
STANDART_QOLDIR = {"mindray", "urit", "biobase", "dirui", "genrui", "edan", "dymind", "zybio",
                   "sysmex", "erba", "human", "rayto", "roche", "biosystems", "uriscan", "combilyzer",
                   "crystal", "medline", "telegram", "whatsapp", "instagram", "ifa", "elisa"}

BIRLIK = [
    ("mkmol/l", "мкмоль/л"), ("mkmol/L", "мкмоль/л"), ("µmol/L", "мкмоль/л"), ("µmol/l", "мкмоль/л"),
    ("mmol/l", "ммоль/л"), ("mmol/L", "ммоль/л"), ("Mmol/l", "ммоль/л"), ("Mkmol/l", "мкмоль/л"),
    ("mg/dl", "мг/дл"), ("mg/l", "мг/л"), ("Mg/l", "мг/л"), ("mg/L", "мг/л"),
    ("ng/ml", "нг/мл"), ("pg/ml", "пг/мл"), ("mkg/l", "мкг/л"), ("ME/ml", "МЕ/мл"), ("mME/l", "мМЕ/л"),
    ("E/l", "Е/л"), ("U/l", "Е/л"), ("g/l", "г/л"), ("g/L", "г/л"), ("G/l", "г/л"),
    ("Leyk/mkl", "лейк/мкл"), ("Erit/mkl", "эр/мкл"), ("mg/mmol", "мг/ммоль"),
    ("ko'ruv maydonida", "кўрув майдонида"),
]
_BIRLIK_RE = re.compile("|".join(re.escape(a) for a, _ in sorted(BIRLIK, key=lambda x: -len(x[0]))))
_BIRLIK_MAP = dict(BIRLIK)

# So'z: harflar + ichidagi tutuq belgisi (o'g'il, ma'lumot); raqam/#/% yopishgan bo'lsa — butun bo'lak
_TOKEN = re.compile(r"[A-Za-z0-9#%⁰¹²³⁴⁵⁶⁷⁸⁹\-_.@/:]*[A-Za-z][A-Za-z0-9#%⁰¹²³⁴⁵⁶⁷⁸⁹\-_.@/:" + APOS + r"]*")


def _qoldirmi(tok, qoldir):
    t = tok.strip(APOS)
    low = t.lower()
    if low in qoldir or low in STANDART_QOLDIR:
        return True
    if any(x in low for x in ("http", "www", "@")) or low.endswith(".uz") or low.endswith(".com"):
        return True
    if re.search(r"[0-9#%⁰¹²³⁴⁵⁶⁷⁸⁹_/]", t):
        return True                        # Lymph#, 10⁹/L, BC-20s
    if re.fullmatch(r"(?:[A-Z]\.)+[A-Z]?\.?:?", t):
        return False                       # ism bosh harflari: A.X → А.Х
    harflar = re.sub(r"[^A-Za-z]", "", t)
    if harflar and len(harflar) <= 5 and any(ch.isupper() for ch in harflar[1:]) and not harflar.isupper():
        return True                        # IgM, IgG, HBsAg, pH, fL
    if low.strip(".:") in ("ph", "fl"):
        return True
    if harflar and harflar.isupper() and len(harflar) <= 5 and harflar not in OZBEK_QISQA:
        return True                        # WBC, HGB, ALT, CRP, MCHC, RDW-CV
    if "-" in t and any(p.isupper() and len(p) <= 5 for p in t.split("-") if p):
        return True                        # RDW-CV, P-LCR, Anti-HAV
    return False


def _sozni_ogir(w):
    out = []
    i, n = 0, len(w)
    low = w.lower()
    butun_katta = w.isupper() and len(re.sub(r"[^A-Za-z]", "", w)) > 1
    while i < n:
        c, lc = w[i], low[i]
        if lc in "og" and i + 1 < n and w[i + 1] in APOS:
            k, step = ("ў" if lc == "o" else "ғ"), 2
        elif low[i:i + 2] in QOSH and not (low[i:i + 2] == "ye" and i > 0 and low[i - 1] not in "aeiou"):
            k, step = QOSH[low[i:i + 2]], 2
        elif low[i:i + 2] == "ts" and i + 2 < n and low[i + 2] in "ie":
            k, step = "ц", 2               # Leykotsit, Kaltsiy (lekin o'tsa, ketsa — т+с)
        elif lc == "e":
            k, step = ("э" if i == 0 or low[i - 1] in "aeiou" or w[i - 1] in APOS else "е"), 1
        elif c in APOS:
            k, step = "ъ", 1               # ma'lumot → маълумот
        elif lc in HARF:
            k, step = HARF[lc], 1
        else:
            k, step = c, 1
        if butun_katta or c.isupper():
            k = k.upper() if butun_katta else k[:1].upper() + k[1:]
        out.append(k)
        i += step
    return "".join(out)


def kirillga(matn, qoldir=frozenset()):
    """Bitta matnni (run) kirillga o'girish."""
    if not matn or not re.search(r"[A-Za-z]", matn):
        return matn
    qoldir = {q.lower() for q in qoldir}
    # 1) birliklar
    matn = _BIRLIK_RE.sub(lambda m: _BIRLIK_MAP[m.group(0)], matn)

    # 2) so'zlar
    def _rep(m):
        tok = m.group(0)
        if _qoldirmi(tok, qoldir):
            return tok
        # chekkadagi tutuq/qo'shtirnoq belgilari so'zga tegishli emas
        bosh = len(tok) - len(tok.lstrip(APOS))
        tok2 = tok[bosh:]
        oxir_q = ""
        while tok2 and tok2[-1] in APOS and not (len(tok2) >= 2 and tok2[-2].lower() in "og"):
            oxir_q = tok2[-1] + oxir_q
            tok2 = tok2[:-1]
        return tok[:bosh] + "-".join(_sozni_ogir(p) for p in tok2.split("-")) + oxir_q
    return _TOKEN.sub(_rep, matn)


def _paragraflar(pars, qoldir):
    for p in pars:
        for r in p.runs:
            if r.text:
                r.text = kirillga(r.text, qoldir)


def _jadvallar(tables, qoldir):
    for t in tables:
        for row in t.rows:
            for cell in row.cells:
                _paragraflar(cell.paragraphs, qoldir)
                _jadvallar(cell.tables, qoldir)


def hujjatga(doc, qoldir=()):
    """Butun hujjat (asosiy qism, jadvallar, kolontitullar) kirillga — joyida."""
    q = frozenset(x.strip() for x in qoldir if str(x).strip())
    try:
        _paragraflar(doc.paragraphs, q)
        _jadvallar(doc.tables, q)
        for sec in doc.sections:
            for hf in (sec.header, sec.footer):
                if hf is None or hf.is_linked_to_previous:
                    continue
                _paragraflar(hf.paragraphs, q)
                _jadvallar(hf.tables, q)
    except Exception as e:
        print(f"[KIRILL] blanka kirillga o'girilmadi: {e}")
    return doc
