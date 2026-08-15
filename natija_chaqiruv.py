# -*- coding: utf-8 -*-
r"""
Registratsiya → Natija (monoblok) oynasini CHAQIRISH: bemor ochilgan holda.

MUAMMO: filialda hamshira bemorga natija blankasini berishi kerak. Registratsiya
oynasida blanka chiqaradigan joy YO'Q, Natija oynasida esa hammasi bor — blanka
yaratish, saqlash, nazorat signallari, chop etish. Hamshira Natija dasturini
alohida ochib, bemorni QAYTA qidirib o'tirishi vaqt oladi.

YECHIM (egasi g'oyasi, 2026-08-15): registratsiya ro'yxatidan «Natija chiqarish»
bosiladi → Natija oynasi O'SHA BEMOR ochilgan holda oldinga chiqadi. Hamshira
odatdagidek chop etadi va X bilan yopadi. Ya'ni mavjud oyna QAYTA ISHLATILADI,
uning funksiyalari nusxalanmaydi.

NEGA FAYL ORQALI (port/soket emas):
  • internetsiz va tarmoqsiz ishlaydi — filialda shart,
  • fayrvol so'ramaydi, port band bo'lmaydi,
  • ikkala dastur turli papkada (D:\ va G:\) va turli Python'da ishlaydi.
Umumiy joy `db_config.txt` bilan bir xil: %ProgramData%\AzizMedLine.

ISHLASH TARTIBI:
  registratsiya:  soro_yoz(sample_id)  →  yurib_turibdimi() ? (hech narsa) : dasturni ochadi
  monoblok:       har soniyada soro_oqi() — yangi so'rov bo'lsa bemorni ochadi
                  va har 5 soniyada yurishni_belgila() (tirikman deb bildiradi)
"""

import json
import os
import time

# So'rov necha soniya "yangi" hisoblanadi. Eski so'rov dastur qayta
# ochilganda ishlab ketmasligi kerak — aks holda hamshira kechagi bemorni
# ko'rib hayron bo'lardi.
SORO_MUDDAT = 90

# Monoblok tirikligi shu muddat ichida belgilansa — ishlab turibdi deymiz.
YURISH_MUDDAT = 20


def _papka() -> str:
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    yol = os.path.join(pd, "AzizMedLine")
    os.makedirs(yol, exist_ok=True)
    return yol


def _soro_yoli() -> str:
    return os.path.join(_papka(), "natija_soro.json")


def _yurish_yoli() -> str:
    return os.path.join(_papka(), "natija_yurib_turibdi.txt")


# ─────────────────────────── registratsiya tomoni ────────────────────────────

def soro_yoz(sample_id: str) -> bool:
    """Natija oynasida shu bemorni ochishni so'raydi."""
    sample_id = str(sample_id or "").strip()
    if not sample_id:
        return False
    try:
        with open(_soro_yoli(), "w", encoding="utf-8") as f:
            json.dump({"sample_id": sample_id, "vaqt": time.time()}, f)
        return True
    except Exception:
        return False


def yurib_turibdimi() -> bool:
    """Natija dasturi hozir ochiqmi (yurak urishi belgisiga qarab)."""
    try:
        with open(_yurish_yoli(), "r", encoding="utf-8") as f:
            oxirgi = float((f.read() or "0").strip())
        return (time.time() - oxirgi) < YURISH_MUDDAT
    except Exception:
        return False


# ─────────────────────────── monoblok (Natija) tomoni ────────────────────────

def yurishni_belgila():
    """«Men ochiqman» — registratsiya shunga qarab dasturni qayta ochmaydi."""
    try:
        with open(_yurish_yoli(), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def soro_oqi(korilgan_vaqt: float = 0.0):
    """Yangi so'rov bo'lsa (sample_id, vaqt) qaytaradi, aks holda (None, korilgan_vaqt).

    `korilgan_vaqt` — oxirgi bajarilgan so'rov vaqti. Chaqiruvchi uni saqlab
    turadi, shuning uchun bitta so'rov IKKI MARTA bajarilmaydi.
    """
    try:
        with open(_soro_yoli(), "r", encoding="utf-8") as f:
            data = json.load(f)
        vaqt = float(data.get("vaqt") or 0)
        sid = str(data.get("sample_id") or "").strip()
    except Exception:
        return None, korilgan_vaqt

    if not sid or vaqt <= korilgan_vaqt:
        return None, korilgan_vaqt
    if (time.time() - vaqt) > SORO_MUDDAT:
        # Eskirgan so'rov — bajarmaymiz, lekin ko'rilgan deb belgilaymiz
        return None, vaqt
    return sid, vaqt
