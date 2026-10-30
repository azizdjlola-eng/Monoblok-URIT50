"""
Funksiya paketlari (litsenziya bo'yicha) — Start / Standart / Pro + qo'shimcha modullar.

Litsenziya fayli (.azlic, imzolangan) "data" qismida ixtiyoriy maydonlar:
    "paket":    "start" | "standart" | "pro"
    "modullar": ["gemo_analizator", "siydik_analizator", ...]   — qo'shimcha (add-on)
Yoqilgan modullar = paketdagilar ∪ "modullar".

ESKI LITSENZIYALAR BUZILMAYDI: "paket" ham, "modullar" ham bo'lmasa — HAMMA funksiya
yoqiq (hozirgi mijozlar va bizning o'rnatmalar o'zgarishsiz ishlaydi).

XAVFSIZLIK FUNKSIYALARI HECH QACHON YOPILMAYDI (bu yerda modul sifatida yo'q ham):
kritik natija signali, natija xatoligi (lineynost) tekshiruvi, "Sample ID / barkod ↔ ism
mos emas" ogohlantirishlari — bemor xavfsizligi, har paketda ishlaydi.

Yopiq funksiya YASHIRILMAYDI: bosilganda «… paketida — bog'laning» xabari chiqadi;
ma'lumot o'chmaydi; analizator moduli yopiq bo'lsa natijani qo'lda kiritish ishlaydi.
Litsenziya VPS orqali har ochilishda yangilanadi — paket masofadan o'zgartiriladi.
"""

import time

MODULLAR = {
    # kalit: (UI nomi, eng kichik paket; None = faqat qo'shimcha modul sifatida)
    "gemo_analizator":   ("Gemotologiya analizatori ulanishi", "pro"),
    "siydik_analizator": ("Siydik analizatori ulanishi", "pro"),
    "bio_analizator":    ("Bioximiya analizatori ulanishi (LIS, shtrix-kod)", "pro"),
    "oldingi_natija":    ("Blankada «Oldingi natija» ustuni", "standart"),
    "statistika":        ("Tahlillar statistikasi", "standart"),
    "bulut_pdf":         ("Natija PDF bulutga (OneDrive / Google Drive)", "standart"),
    "qc":                ("Sifat nazorati (QC kontrollari)", "pro"),
    "delta_check":       ("Delta-check (oldingi natija bilan solishtirish)", "pro"),
    "kritik_jurnal":     ("Kritik xabar jurnali", "pro"),
    "ifa_kuzatuv":       ("IFA kuzatuv oynasi", "pro"),
}
PAKET_TARTIB = ["start", "standart", "pro"]
PAKET_NOMI = {"start": "Start", "standart": "Standart", "pro": "Pro"}
ALOQA = "AzizMedLine: +998 99 673 13 42"

_KESH = {"vaqt": 0.0, "holat": None}
_KESH_SEK = 600


def paket_modullari(paket: str) -> set:
    """Paketga kiradigan modullar (analizatorlar Standartda — alohida qo'shimcha modul)."""
    if paket not in PAKET_TARTIB:
        return set()
    i = PAKET_TARTIB.index(paket)
    return {k for k, (_n, p) in MODULLAR.items() if p and PAKET_TARTIB.index(p) <= i}


def _payload():
    """Joriy litsenziya data qismi yoki None (o'qib bo'lmasa / yaroqsiz)."""
    try:
        from litsenziya import litsenziya_manager as _lm
        n = _lm.holatni_tekshir(online=False)
        if not getattr(n, "yaroqli", False):
            return None          # yaroqsiz litsenziyani dastur darvozasi o'zi to'xtatadi
        return getattr(n, "payload", None) or None
    except Exception:
        return None


def holat(force=False) -> dict:
    """{"cheklov": bool, "paket": str|None, "yoqilgan": set} (10 daqiqa kesh)."""
    if not force and _KESH["holat"] is not None and time.time() - _KESH["vaqt"] < _KESH_SEK:
        return _KESH["holat"]
    p = _payload() or {}
    paket = str(p.get("paket") or "").strip().lower() or None
    qosh = p.get("modullar")
    if paket is None and qosh is None:
        h = {"cheklov": False, "paket": None, "yoqilgan": set(MODULLAR)}     # eski litsenziya
    else:
        yoq = paket_modullari(paket) if paket else set()
        if isinstance(qosh, (list, tuple, set)):
            yoq |= {str(x) for x in qosh}
        h = {"cheklov": True, "paket": paket, "yoqilgan": yoq}
    _KESH.update(vaqt=time.time(), holat=h)
    return h


def yoqilganmi(modul: str) -> bool:
    """Modul yoqilganmi. Xato bo'lsa — True (funksiyani bexosdan yopmaslik)."""
    try:
        return modul in holat()["yoqilgan"]
    except Exception:
        return True


def _kerakli_paket(modul):
    p = MODULLAR.get(modul, ("", None))[1]
    if modul.endswith("_analizator"):
        return "Standart paketda qo'shimcha modul sifatida yoki Pro paketda"
    return f"{PAKET_NOMI.get(p, p)} paketda" if p else "qo'shimcha modul sifatida"


def xabar_matni(modul: str) -> str:
    nomi = MODULLAR.get(modul, (modul,))[0]
    h = holat()
    joriy = PAKET_NOMI.get(h.get("paket"), "—")
    return (f"«{nomi}» funksiyasi sizning litsenziyangizda yoqilmagan.\n\n"
            f"Joriy paket: {joriy}.\nBu funksiya {_kerakli_paket(modul)} mavjud.\n\n"
            f"Ulash uchun bog'laning: {ALOQA}\n"
            "(Paket masofadan yoqiladi — dasturni qayta o'rnatish shart emas.)")


def tekshir(modul: str, parent=None) -> bool:
    """UI uchun: yoqilgan bo'lsa True; aks holda tushunarli xabar chiqarib False."""
    if yoqilganmi(modul):
        return True
    try:
        from tkinter import messagebox
        messagebox.showinfo("Funksiya paketda yo'q", xabar_matni(modul), parent=parent)
    except Exception:
        print(f"[PAKET] {modul} yoqilmagan")
    return False


def holat_matni() -> str:
    """Litsenziya varag'i uchun qisqa matn."""
    h = holat(force=True)
    if not h["cheklov"]:
        return "Paket: cheklovsiz (barcha funksiyalar yoqilgan)"
    qator = [f"Paket: {PAKET_NOMI.get(h['paket'], h['paket'] or '—')}"]
    for k, (n, _p) in MODULLAR.items():
        qator.append(f"   {'✓' if k in h['yoqilgan'] else '—'}  {n}")
    return "\n".join(qator)
