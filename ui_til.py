# -*- coding: utf-8 -*-
"""
DASTUR OYNALARI YOZUVI — LOTIN (standart) yoki KIRILL (Ўзбек).

Har kompyuter o'zi tanlaydi: %ProgramData%\\AzizMedLine\\interfeys.json
    {"yozuv": "lotin"}   yoki   {"yozuv": "kirill"}
Registratsiya va Natija bir xil faylni o'qiydi (bir kompyuterda — bir xil yozuv).
Sozlash: Registratsiya → Sozlamalar → «🔤 Dastur yozuvi», Natija → Sozlamalar →
«🌐 Blanka tili» → «Dastur oynalari yozuvi…». O'zgarish dastur QAYTA OCHILGANDA
kuchga kiradi.

QANDAY ISHLAYDI
  Kodda matnlar lotincha yozilgan va shunday qoladi. Kirill tanlangan bo'lsa
  `yoq()` dastur boshida tkinter'ga bitta «filtr» qo'yadi: oynaga CHIQAYOTGAN
  yozuvlar (tugma, yorliq, menyu, oyna sarlavhasi, jadval ustuni, xabar oynasi,
  bo'lim yorlig'i) kirillga o'giriladi. Lotin tanlangan bo'lsa HECH NARSA
  o'zgarmaydi — dastur avvalgidek ishlaydi.

O'GIRILMAYDI (atayin):
  • bemor ma'lumoti — Entry/Text/Combobox qiymatlari, jadval qatorlari
    (bazaga yoziladigan qiymat o'zgarib qolmasin);
  • tahlil kodlari (WBC, HGB, ALT ...), brendlar (Mindray, Telegram ...),
    CamelCase nomlar (AzizMedLine, AnyDesk), sana andozalari (YYYY-MM-DD),
    havola / e-pochta / fayl nomi / papka yo'li;
  • «admin / admin» kabi kirish namunasi (xodim uni lotinda yozadi);
  • xom(widget, matn) bilan qo'yilgan yozuv — masalan «Lotin» tanlovi doim
    lotincha ko'rinsin. (Kodga ko'rinmas belgi QO'SHMANG — lotin rejimida
    u ekranda katakcha bo'lib chiqishi mumkin.)

KOD MANTIQI BUZILMAYDI: dastur yorliq matnini qayta o'qisa (cget('text'),
w['text'], title(), StringVar.get()) — unga ASL lotin matn qaytariladi.
"""

import json
import os
import re
from functools import lru_cache

YOZUVLAR = ("lotin", "kirill")
QOLDIR = "\u2060"          # matn boshida bo'lsa — o'girilmaydi (ko'rinmaydi)
_FAYL = "interfeys.json"

_YOQILGAN = False
XATO = None                # yoq() da xato bo'lsa — matni (dastur yiqilmaydi)


# ─────────────────────────────── sozlama ────────────────────────────────
def _papka():
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(pd, "AzizMedLine")


def fayl_yoli():
    return os.path.join(_papka(), _FAYL)


def yozuv():
    """Shu kompyuterda tanlangan yozuv: 'lotin' (standart) yoki 'kirill'."""
    try:
        with open(fayl_yoli(), encoding="utf-8") as f:
            v = str(json.load(f).get("yozuv", "lotin")).strip().lower()
        return v if v in YOZUVLAR else "lotin"
    except Exception:
        return "lotin"


def saqla(v):
    """Yozuvni saqlash (keyingi ochilishda kuchga kiradi)."""
    v = str(v).strip().lower()
    if v not in YOZUVLAR:
        raise ValueError(f"Noma'lum yozuv: {v}")
    os.makedirs(_papka(), exist_ok=True)
    d = {}
    try:
        with open(fayl_yoli(), encoding="utf-8") as f:
            d = json.load(f) or {}
    except Exception:
        d = {}
    d["yozuv"] = v
    tmp = fayl_yoli() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, fayl_yoli())


def faolmi():
    """Kirill filtri shu jarayonda yoqilganmi."""
    return _YOQILGAN


# ────────────────────────── lotin → kirill ─────────────────────────────
APOS = "'‘’ʻʼ`"
HARF = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ", "i": "и",
    "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ",
    "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "x": "х", "y": "й", "z": "з",
    "c": "с", "w": "в",
}
QOSH = {"sh": "ш", "ch": "ч", "yo": "ё", "yu": "ю", "ya": "я", "ye": "е"}

# O'zbek kirillida yumshoq belgi (ь) yoki boshqacha yoziladigan o'zlashma so'zlar.
# Kalit — so'z O'ZAGI (kichik harf); ortidan o'zbekcha qo'shimcha kelishi mumkin
# (parolni → парольни, oktyabrda → октябрда).
OZAK = {
    "kompyuter": "компьютер", "filtr": "фильтр", "parol": "пароль", "profil": "профиль",
    "model": "модель", "kontrol": "контроль", "rol": "роль", "stil": "стиль",
    "kalendar": "календарь", "yanvar": "январь", "fevral": "февраль", "aprel": "апрель",
    "iyun": "июнь", "iyul": "июль", "sentyabr": "сентябрь", "oktyabr": "октябрь",
    "noyabr": "ноябрь", "dekabr": "декабрь", "konsultatsiya": "консультация",
    "konsultant": "консультант", "ultratovush": "ультратовуш",
    "online": "онлайн", "onlayn": "онлайн", "offline": "офлайн", "oflayn": "офлайн",
    "pechat": "печать", "alkogol": "алкоголь", "pult": "пульт", "avtomobil": "автомобиль",
    "feldsher": "фельдшер", "ob'ekt": "объект", "obyekt": "объект", "ob'yekt": "объект",
    "sub'ekt": "субъект", "subyekt": "субъект", "albom": "альбом", "volt": "вольт",
}
_QOSHIMCHA = re.compile(
    r"(?:lar)?(?:i|si|im|imiz|ing|ingiz|ni|ning|ga|ka|da|dan|dagi|gacha|siz|li|lik|chi)?(?:ni|ga|da|dan|ning)?")

# KATTA harfli qisqa so'zlar odatda kod (WBC, SMS, QR) — lotincha qoladi.
# Lekin bular o'zbekcha so'z — o'giriladi:
OZBEK_KATTA = {
    "QON", "VA", "BILAN", "UCHUN", "SOAT", "KUN", "OY", "YIL", "TEST", "TESTI", "ERKAK", "AYOL",
    "YOSH", "NOMI", "SANA", "TEL", "NORMA", "KOD", "KODNI", "TURI", "JINS", "XATO", "SHU", "FAQAT",
    "BITTA", "YANGI", "ESKI", "JAMI", "EMAS", "BIR", "MARTA", "ENG", "QABUL", "NAQD", "KARTA",
    "XUDDI", "UZI", "MAZOK", "BEPUL", "ADMIN", "OLISH", "FARQ", "BOR", "OCHIQ", "BEMOR", "QARZ",
    "PUL", "FOYDA", "OLDIN", "OYGA", "FAYL", "NAJAS", "QAYTA", "HAR", "XIL", "MKB", "FISH", "SH",
    "HA", "ISM", "NARX", "BUGUN", "KIRIM", "HAMMA", "YOPIQ", "BOSH", "SHART", "KERAK", "EKG",
    "IFA", "OAK", "DIQQAT", "TAYYOR", "VRACH", "KASSA", "CHEK", "TO'LOV", "YO'Q", "O'ZI", "KO'P",
    "QO'LDA", "MUHIM", "FAOL", "SINOV", "PAST", "HOLAT", "TANLOV", "HOZIR", "KECHA", "DASTUR",
    "IKKI", "KIM", "YOKI", "BEKOR", "YETDI", "NIMA", "RANG", "DEMO", "REJIM", "YURAK", "SOHA",
    "HAYZ", "OYLIK", "SEF", "BREND",
}
# Katta harfli, lekin Q harfi bo'lsa ham kod bo'lib qoladiganlar
KOD_KATTA = {"SQL", "QR", "QC", "QA"}
# Brendlar va lotincha qolishi odat bo'lgan so'zlar (kichik harf)
BRENDLAR = {
    "mindray", "urit", "biobase", "dirui", "genrui", "edan", "dymind", "zybio", "sysmex", "erba",
    "human", "rayto", "roche", "biosystems", "uriscan", "combilyzer", "crystal", "medline",
    "telegram", "whatsapp", "instagram", "facebook", "youtube", "google", "gmail", "drive",
    "windows", "excel", "word", "android", "chrome", "python", "mysql", "anydesk", "rustdesk",
    "teamviewer", "wifi", "wi-fi", "bluetooth", "logs", "log", "click", "payme", "uzum",
    "cloudflare", "ngrok", "github", "e-mail", "email", "gateway", "update", "backup", "redmi",
    "xiaomi", "samsung", "asus", "xprinter", "hikvision", "dmed", "lims", "azizmedline",
    "elisa", "ifa", "monoblok_dastur", "localhost", "ok", "user", "sample", "client", "relay",
    "service", "watcher", "phonelink", "github",
}

BIRLIK = [
    ("mkmol/l", "мкмоль/л"), ("mkmol/L", "мкмоль/л"), ("µmol/L", "мкмоль/л"), ("µmol/l", "мкмоль/л"),
    ("mmol/l", "ммоль/л"), ("mmol/L", "ммоль/л"), ("mg/dl", "мг/дл"), ("mg/l", "мг/л"),
    ("mg/L", "мг/л"), ("ng/ml", "нг/мл"), ("pg/ml", "пг/мл"), ("mkg/l", "мкг/л"),
    ("ME/ml", "МЕ/мл"), ("mME/l", "мМЕ/л"), ("U/l", "Е/л"), ("g/l", "г/л"), ("g/L", "г/л"),
    ("so'm", "сўм"), ("so‘m", "сўм"), ("so’m", "сўм"), ("soʻm", "сўм"),
]
_BIRLIK_RE = re.compile(r"(?<![A-Za-z])(?:" + "|".join(
    re.escape(a) for a, _ in sorted(BIRLIK, key=lambda x: -len(x[0]))) + r")(?![A-Za-z])")
_BIRLIK_MAP = dict(BIRLIK)

_SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹"
# So'z bo'lagi: harf/raqam/tutuq/defis/nuqta/@/#/% — '/', ':', '\' AJRATADI
_TOKEN = re.compile(r"[A-Za-z0-9" + _SUPER + APOS + r"#%_.@\-–]*[A-Za-z][A-Za-z0-9" + _SUPER + APOS + r"#%_.@\-–]*")
_SON_QOSHIMCHA = re.compile(r"(\d+)([-–]?)([A-Za-z" + APOS + r"]+)")


def _sozni_ogir(w):
    """Bitta lotin so'zini (faqat harf va tutuq) kirillga."""
    out = []
    i, n = 0, len(w)
    low = w.lower()
    harflar = re.sub(r"[^A-Za-z]", "", w)
    butun_katta = w.isupper() and len(harflar) > 1
    while i < n:
        c, lc = w[i], low[i]
        if lc in "og" and i + 1 < n and w[i + 1] in APOS:
            k, step = ("ў" if lc == "o" else "ғ"), 2
        elif lc == "y" and i + 2 < n and low[i + 1] in "og" and w[i + 2] in APOS:
            k, step = "й", 1                       # yo'q → йўқ (ё + ъ emas)
        elif low[i:i + 2] in QOSH and not (low[i:i + 2] == "ye" and i > 0 and low[i - 1] not in "aeiou"):
            k, step = QOSH[low[i:i + 2]], 2
        elif low[i:i + 2] == "ts" and i + 2 < n and low[i + 2] in "ie":
            k, step = "ц", 2                       # litsenziya, leykotsit (o'tsa — т+с)
        elif lc == "e":
            k, step = ("э" if i == 0 or low[i - 1] in "aeiou" or w[i - 1] in APOS else "е"), 1
        elif c in APOS:
            k, step = "ъ", 1                       # ma'lumot → маълумот
        elif lc in HARF:
            k, step = HARF[lc], 1
        else:
            k, step = c, 1
        if butun_katta:
            k = k.upper()
        elif c.isupper():
            k = k[:1].upper() + k[1:]
        out.append(k)
        i += step
    return "".join(out)


def _ozak_bilan(p):
    """O'zlashma so'z o'zagi (OZAK) bo'lsa — o'zak + o'zbekcha qo'shimcha."""
    low = p.lower()
    for oz, kir in OZAK.items():
        if low.startswith(oz) and _QOSHIMCHA.fullmatch(low[len(oz):]):
            if kir.endswith("ь") and low[len(oz):len(oz) + 1] in ("a", "e", "i", "o", "u"):
                kir = kir[:-1]                     # parolini → паролини (unlidan oldin ь yo'q)
            if p[:1].isupper():
                kir = kir[:1].upper() + kir[1:]
            if p.isupper() and len(p) > 1:
                kir = kir.upper()
            return kir + _sozni_ogir(p[len(oz):])
    return None


def _qoldirmi(p):
    """Defis bilan ajratilgan BITTA bo'lak lotincha qolsinmi."""
    t = p.strip(APOS)
    if not t:
        return True
    low = t.lower()
    if low in BRENDLAR:
        return True
    harflar = re.sub(r"[^A-Za-z]", "", t)
    if not harflar:
        return True
    if re.search(r"[0-9#%_@" + _SUPER + r"]", t):
        return True                                # BC-20s, Lymph#, 10⁹
    if re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]?\.?", t) and len(harflar) <= 4:
        return False                               # A.X., F.I.SH → А.Х.
    if re.search(r"[A-Za-z]{2,}\.[A-Za-z]{2,}", t):
        return True                                # config.json, app.log
    if re.search(r"[a-z][A-Z]", t):
        return True                                # AzizMedLine, AnyDesk, IgM, HBsAg, pH
    if harflar.isupper():
        katta = t.upper().replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("ʼ", "'")
        if katta in OZBEK_KATTA or harflar in OZBEK_KATTA:
            return False
        if harflar in KOD_KATTA:
            return True
        if any(ch in APOS for ch in t):
            return False                           # TO'LOV, YO'Q — o'zbekcha
        if len(harflar) <= 5 and "Q" not in harflar:
            return True                            # WBC, SMS, PDF, YYYY
        if len(harflar) <= 2:
            return True
    return False


def _bolak(p):
    """Bitta bo'lakni (defissiz) o'girish."""
    # SMS'lar, QR'ni — kod qoladi, o'zbekcha qo'shimcha o'giriladi
    m = re.fullmatch(r"([A-Z]{2,6})([" + APOS + r"])([a-z]+)", p)
    if m and _qoldirmi(m.group(1)):
        return m.group(1) + m.group(2) + _sozni_ogir(m.group(3))
    if _qoldirmi(p):
        m = _SON_QOSHIMCHA.fullmatch(p)            # 10ta → 10та
        if m:
            return m.group(1) + m.group(2) + _sozni_ogir(m.group(3))
        return p
    oz = _ozak_bilan(p)
    if oz is not None:
        return oz
    return _sozni_ogir(p)


def _token(tok):
    # chekkadagi qo'shtirnoq/tutuq so'zga tegishli emas (o'/g' oxiridagisi — tegishli)
    bosh = len(tok) - len(tok.lstrip(APOS))
    ich = tok[bosh:]
    oxir = ""
    while ich and ich[-1] in APOS and not (len(ich) >= 2 and ich[-2].lower() in "og"):
        oxir = ich[-1] + oxir
        ich = ich[:-1]
    # chekkadagi nuqta (gap oxiri) — alohida
    nuqta = ""
    while ich.endswith("."):
        if re.fullmatch(r"(?:[A-Za-z]\.)+", ich):  # bosh harflar: A.X.
            break
        nuqta += "."
        ich = ich[:-1]
    low = ich.lower()
    if low in BRENDLAR or any(x in low for x in ("http", "www.", "@")) \
            or low.endswith((".uz", ".com", ".ru", ".org", ".net")):
        return tok
    qismlar = re.split(r"([-–])", ich)
    yangi = "".join(q if q in "-–" else _bolak(q) for q in qismlar)
    return tok[:bosh] + yangi + nuqta + oxir


# Papka yo'li, havola, muhit o'zgaruvchisi — butunicha lotincha qoladi (atrofidagi gap o'giriladi)
# (+ login/parol namunasi «admin / admin» — xodim uni lotinda yozadi)
_MAXSUS = re.compile(r"https?://[^\s«»\"'()]+|www\.[^\s«»\"'()]+|t\.me/[^\s«»\"'()]+"
                     r"|[A-Za-z]:[\\/][^\s«»\"'()]*|\\\\[^\s«»\"'()]+|%[A-Za-z_]+%[^\s«»\"'()]*"
                     r"|\badmin\s*/\s*admin\b")


def _gapni_ogir(matn):
    matn = _BIRLIK_RE.sub(lambda m: _BIRLIK_MAP[m.group(0)], matn)
    return _TOKEN.sub(lambda m: _token(m.group(0)), matn)


def js_jadval():
    """Vrach kabineti (brauzer) uchun — o'sha lug'at va qoidalar JSON ko'rinishida.
    vrach_web/static/ui_til.js shu jadval bilan AYNAN kirillga() dek o'giradi
    (ikki joyda alohida lug'at saqlanmasin)."""
    return {
        "apos": APOS, "super": _SUPER, "harf": HARF, "qosh": QOSH,
        "ozak": [[k, v] for k, v in OZAK.items()],      # tartib muhim
        "qoshimcha": _QOSHIMCHA.pattern,
        "ozbek_katta": sorted(OZBEK_KATTA), "kod_katta": sorted(KOD_KATTA),
        "brendlar": sorted(BRENDLAR), "birlik": [list(x) for x in BIRLIK],
        "maxsus": _MAXSUS.pattern, "qoldir": QOLDIR,
    }


@lru_cache(maxsize=40000)
def kirillga(matn):
    """Bitta oyna yozuvini kirillga o'girish (lotin bo'lmagan qismlar o'zgarmaydi)."""
    if not matn or not re.search(r"[A-Za-z]", matn):
        return matn
    if matn.startswith(QOLDIR):
        return matn[len(QOLDIR):]                  # belgi ekranga chiqmasin
    try:
        out, oxirgi = [], 0
        for m in _MAXSUS.finditer(matn):
            out.append(_gapni_ogir(matn[oxirgi:m.start()]))
            out.append(m.group(0))
            oxirgi = m.end()
        out.append(_gapni_ogir(matn[oxirgi:]))
        return "".join(out)
    except Exception:
        return matn


# ─────────────────── bemor qidiruvi: lotin = kirill ────────────────────
# Bir registrator «Aliyev», boshqasi «Алиев» deb yozsa — bazada ikkalasi bor.
# Qidiruv so'zning IKKALA yozuvdagi shaklini ham izlaydi (bazadagi qiymat o'zgarmaydi).
_KIR_LOT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sh", "ъ": "'", "ь": "", "ы": "i", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
_UNLI_KIR = "аеёиоуўэюяыъь"


def lotinga(matn):
    """O'zbek kirill → lotin (rasmiy qoida: е so'z boshida va unlidan keyin — «ye»)."""
    if not matn:
        return matn
    out = []
    for i, ch in enumerate(matn):
        lc = ch.lower()
        if lc == "е":
            old = matn[i - 1].lower() if i > 0 else ""
            k = "ye" if (not old or not old.isalpha() or old in _UNLI_KIR) else "e"
        elif lc in _KIR_LOT:
            k = _KIR_LOT[lc]
        else:
            out.append(ch)
            continue
        if ch != lc and k:                         # katta harf
            keyingi = matn[i + 1] if i + 1 < len(matn) else ""
            k = k.upper() if (keyingi.isupper() and len(k) > 1) else k[:1].upper() + k[1:]
        out.append(k)
    return "".join(out)


def _nom_kirill(matn):
    """Ism-familiyani kirillga (kod/brend qoidalarisiz — har lotin so'z o'giriladi)."""
    def _bir(m):
        w, oxir = m.group(0), ""
        while w and w[-1] in APOS and not (len(w) >= 2 and w[-2].lower() in "og"):
            oxir, w = w[-1] + oxir, w[:-1]           # chekkadagi tutuq — so'zga tegishli emas
        return _sozni_ogir(w) + oxir
    return re.sub(r"[A-Za-z][A-Za-z" + APOS + r"]*", _bir, matn)


def qidiruv_variantlar(soz):
    """Qidiruv so'zining lotin va kirill shakllari (takrorsiz). Lotin shaklda
    tutuq belgisi (o' / oʻ / o’) LIKE uchun «_» — har qanday tutuqni topadi."""
    soz = (soz or "").strip()
    if not soz:
        return []
    v = [soz]
    if re.search(r"[А-Яа-яЁёЎўҚқҒғҲҳ]", soz):
        v.append(lotinga(soz))
    if re.search(r"[A-Za-z]", soz):
        try:
            v.append(_nom_kirill(soz))
        except Exception:
            pass
    # Rus klaviaturasida yozilgan kirill: Ҳасанов → Хасанов, Қодиров → Кодиров
    _rus = str.maketrans("ЎўҚқҒғҲҳ", "УуКкГгХх")
    v += [x.translate(_rus) for x in list(v) if re.search(r"[ЎўҚқҒғҲҳ]", x)]
    natija = []
    for x in v:
        x = re.sub("[" + APOS + "]", "_", x) if re.search(r"[A-Za-z]", x) else x
        if x and x not in natija:
            natija.append(x)
    return natija


def fish_like(ustun, soz):
    """SQL bo'lagi: «(ustun LIKE %s OR ustun LIKE %s ...)» va parametrlari.
    Misol: sql += " AND " + s;  params += p   (s, p = fish_like("b.fish", soz))"""
    v = qidiruv_variantlar(soz) or [soz or ""]
    return ("(" + " OR ".join(f"{ustun} LIKE %s" for _ in v) + ")", [f"%{x}%" for x in v])


# ────────────────────────── tkinter filtri ──────────────────────────────
_KALITLAR = ("text", "label", "title", "message", "detail")
_KORSATKICH = {"label", "button", "checkbutton", "radiobutton", "menubutton", "labelframe",
               "message", "ttk::label", "ttk::button", "ttk::checkbutton", "ttk::radiobutton",
               "ttk::menubutton", "ttk::labelframe"}
_TESKARI = {}              # kirill → asl lotin (kod qayta o'qisa)
_KORSATISH_VAR = set()     # faqat yorliqqa bog'langan StringVar nomlari


def ogir(matn):
    """Yoqilgan bo'lsa kirillga o'giradi va aslini eslab qoladi; aks holda o'zi."""
    if not _YOQILGAN or not isinstance(matn, str) or not matn:
        return matn
    k = kirillga(matn)
    if k != matn:
        if len(_TESKARI) > 120000:
            _TESKARI.clear()
        _TESKARI[k] = matn
    return k


def asl(matn):
    """Ekrandagi (kirill) matndan asl lotin matnni qaytaradi."""
    if isinstance(matn, str):
        return _TESKARI.get(matn, matn)
    return matn


def _yamoq():
    import tkinter as tk
    from tkinter import ttk

    asl_options = tk.Misc._options

    def _var_belgila(w, tv):
        try:
            nom = str(tv)
            if nom in _KORSATISH_VAR:
                return
            _KORSATISH_VAR.add(nom)
            joriy = w.tk.globalgetvar(nom)
            if isinstance(joriy, str):
                k = ogir(joriy)
                if k != joriy:
                    w.tk.globalsetvar(nom, k)
        except Exception:
            pass

    def _options(self, cnf, kw=None):
        if kw:
            cnf = tk._cnfmerge((cnf, kw))
        else:
            cnf = tk._cnfmerge(cnf)
        if cnf:
            try:
                yangi = None
                for k in _KALITLAR:
                    v = cnf.get(k)
                    if isinstance(v, str) and v:
                        t = ogir(v)
                        if t != v:
                            if yangi is None:
                                yangi = dict(cnf)
                            yangi[k] = t
                tv = cnf.get("textvariable")
                if tv is not None and getattr(self, "widgetName", "") in _KORSATKICH:
                    _var_belgila(self, tv)
                if yangi is not None:
                    cnf = yangi
            except Exception:
                pass
        return asl_options(self, cnf)

    tk.Misc._options = _options

    # ── qayta o'qish: kodga asl lotin matn ──
    asl_cget = tk.Misc.cget

    def _cget(self, key):
        v = asl_cget(self, key)
        if isinstance(v, str) and str(key).lstrip("-") in _KALITLAR:
            return asl(v)
        return v

    tk.Misc.cget = _cget
    tk.Misc.__getitem__ = _cget

    asl_entrycget = tk.Menu.entrycget

    def _entrycget(self, index, option):
        v = asl_entrycget(self, index, option)
        if isinstance(v, str) and str(option).lstrip("-") in _KALITLAR:
            return asl(v)
        return v

    tk.Menu.entrycget = _entrycget

    # ── oyna sarlavhasi ──
    asl_title = tk.Wm.wm_title

    def _title(self, string=None):
        if string is None:
            return asl(asl_title(self))
        return asl_title(self, ogir(string))

    tk.Wm.wm_title = _title
    tk.Wm.title = _title

    # ── yorliqqa bog'langan StringVar: set → kirill, get → asl ──
    asl_set = tk.Variable.set

    def _set(self, value):
        if isinstance(value, str) and self._name in _KORSATISH_VAR:
            value = ogir(value)
        return asl_set(self, value)

    tk.Variable.set = _set

    asl_sget = tk.StringVar.get

    def _sget(self):
        v = asl_sget(self)
        if self._name in _KORSATISH_VAR:
            return asl(v)
        return v

    tk.StringVar.get = _sget

    # ── ttk: jadval ustuni sarlavhasi, bo'lim (Notebook) yorlig'i ──
    asl_heading = ttk.Treeview.heading

    def _heading(self, column, option=None, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = ogir(kw["text"])
        r = asl_heading(self, column, option, **kw)
        if option == "text":
            return asl(r)
        return r

    ttk.Treeview.heading = _heading

    def _nb_kw(kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = ogir(kw["text"])
        return kw

    asl_add = ttk.Notebook.add
    asl_insert = ttk.Notebook.insert
    asl_tab = ttk.Notebook.tab

    def _add(self, child, **kw):
        return asl_add(self, child, **_nb_kw(kw))

    def _insert(self, pos, child, **kw):
        return asl_insert(self, pos, child, **_nb_kw(kw))

    def _tab(self, tab_id, option=None, **kw):
        r = asl_tab(self, tab_id, option, **_nb_kw(kw))
        if option == "text":
            return asl(r)
        if option is None and not kw and isinstance(r, dict) and isinstance(r.get("text"), str):
            r = dict(r)
            r["text"] = asl(r["text"])
        return r

    ttk.Notebook.add = _add
    ttk.Notebook.insert = _insert
    ttk.Notebook.tab = _tab


def pdf_canvas(c):
    """Registratsiya qog'ozlari (yo'llanma, chek): kirill tanlangan bo'lsa reportlab
    canvas'ga yoziladigan matn ham kirillga o'giriladi. FAQAT shu canvas nusxasiga
    ta'sir qiladi — Natija blankasi o'zining «🌐 Blanka tili» sozlamasi bilan qoladi.
    Lotin rejimida canvas'ga tegilmaydi."""
    if not _YOQILGAN or c is None:
        return c
    try:
        def _ogir(t):
            return kirillga(t) if isinstance(t, str) else t

        for nom in ("drawString", "drawRightString", "drawCentredString", "drawAlignedString"):
            asl_f = getattr(c, nom, None)
            if asl_f is None:
                continue

            def _yoz(x, y, text, *a, _asl=asl_f, **k):
                return _asl(x, y, _ogir(text), *a, **k)
            setattr(c, nom, _yoz)
        asl_sw = c.stringWidth

        def _sw(text, *a, **k):
            return asl_sw(_ogir(text), *a, **k)
        c.stringWidth = _sw
    except Exception:
        pass
    return c


def xom(widget, matn, kalit="text"):
    """Yozuvni filtrsiz qo'yish — kirill rejimida ham AYNAN shunday ko'rinadi
    (masalan «Lotin» tanlovi). Lotin rejimida oddiy configure bilan bir xil."""
    widget.tk.call(widget._w, "configure", "-" + kalit, matn)


def yoq(majburiy=None):
    """Dastur BOSHIDA (birinchi oyna yaratilishidan oldin) chaqiriladi.
    Kirill tanlangan bo'lsa tkinter filtrini qo'yadi. Hech qachon xato otmaydi.
    majburiy='kirill' — sinov uchun sozlamaga qaramay yoqish."""
    global _YOQILGAN, XATO
    if _YOQILGAN:
        return True
    try:
        if (majburiy or yozuv()) != "kirill":
            return False
        _yamoq()
        _YOQILGAN = True
        return True
    except Exception as e:
        XATO = f"{type(e).__name__}: {e}"
        return False


# ───────────────────────────── sozlash oynasi ───────────────────────────
def sozlama_oynasi(parent=None):
    """«Dastur yozuvi» oynasi: Lotin / Кирилл (shu kompyuter uchun)."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    win.title("Dastur yozuvi")
    win.resizable(False, False)
    try:
        if parent is not None:
            win.transient(parent)
        win.grab_set()
    except Exception:
        pass
    joriy = yozuv()
    v = tk.StringVar(value=joriy)
    fr = ttk.Frame(win, padding=16)
    fr.pack(fill=tk.BOTH, expand=True)
    ttk.Label(fr, text="Dastur oynalaridagi yozuvlar (shu kompyuter uchun):",
              font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
    rb_lotin = ttk.Radiobutton(fr, value="lotin", variable=v)
    xom(rb_lotin, "Lotin — O'zbek (standart)")    # kirill rejimida ham lotincha ko'rinsin
    rb_lotin.pack(anchor=tk.W, pady=(10, 2))
    ttk.Radiobutton(fr, text="Кирилл — Ўзбек", value="kirill",
                    variable=v).pack(anchor=tk.W, pady=2)
    ttk.Label(fr, foreground="#555", justify=tk.LEFT, text=(
        "• Tugma, yorliq, menyu, jadval sarlavhalari va xabarlar o'giriladi.\n"
        "• Bemor ma'lumoti (ism, manzil, natija) qanday kiritilgan bo'lsa, shunday qoladi.\n"
        "• Tahlil kodlari (WBC, HGB, ALT …) va brendlar lotincha qoladi.\n"
        "• Blanka yozuvi alohida: Natija → Sozlamalar → «🌐 Blanka tili».\n"
        "• O'zgarish Registratsiya va Natija QAYTA OCHILGANDA kuchga kiradi.")
              ).pack(anchor=tk.W, pady=(10, 0))
    namuna = ttk.Label(fr, foreground="#1f6f8b")
    namuna.pack(anchor=tk.W, pady=(10, 0))
    _misol = "Bemorni ro'yxatga olish · To'lov · Natijani chop etish · Yo'q"

    def _yangila(*_):
        k = kirillga(_misol) if v.get() == "kirill" else _misol
        xom(namuna, ("Намуна: " if v.get() == "kirill" else "Namuna: ") + k)

    v.trace_add("write", _yangila)
    _yangila()

    def _saqla():
        try:
            saqla(v.get())
        except Exception as e:
            messagebox.showerror("Dastur yozuvi", f"Saqlanmadi: {e}", parent=win)
            return
        if v.get() != joriy:
            messagebox.showinfo("Dastur yozuvi",
                                "Saqlandi. Dasturni yopib, qayta oching — yozuv o'zgaradi.",
                                parent=win)
        win.destroy()

    bf = ttk.Frame(fr)
    bf.pack(fill=tk.X, pady=(14, 0))
    ttk.Button(bf, text="💾 Saqlash", command=_saqla).pack(side=tk.RIGHT)
    ttk.Button(bf, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=6)
    return win
