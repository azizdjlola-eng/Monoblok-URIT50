# -*- coding: utf-8 -*-
"""
Litsenziya MANAGER — mijoz (filial/klient) tomonida ishlaydi.

`.azlic` faylni topadi, Ed25519 imzosini OCHIQ kalit bilan tekshiradi va
quyidagilarni nazorat qiladi:
  - imzo haqiqiyligi      (soxta litsenziya emasligini)
  - machine_id mosligi    (boshqa kompyuterga ko'chirilmaganini)
  - anti-rollback vaqt    (soat orqaga surilmaganini)
  - muddat (expires_at)   (tugamaganini)

Internet shart EMAS — barcha tekshiruv offline bajariladi.
"""

import os
import json
import time
import hashlib
from enum import Enum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from . import mashina_id as _mid
from . import vaqt_himoya
from . import yollar

try:
    from .ochiq_kalit import OCHIQ_KALIT_HEX
except Exception:
    OCHIQ_KALIT_HEX = ""


class Holat(Enum):
    OK = "ok"
    YOQ = "yoq"                      # fayl topilmadi (faollashtirilmagan)
    SOXTA = "soxta"                 # imzo noto'g'ri / fayl buzilgan / kalit yo'q
    BOSHQA_KOMPYUTER = "boshqa"     # litsenziya boshqa machine_id uchun
    MUDDATI_TUGAGAN = "tugagan"     # expires_at o'tib ketgan
    VAQT_ORQAGA = "vaqt"            # tizim vaqti orqaga qaytarilgan
    BLOKLANGAN = "bloklangan"       # masofadan (VPS) bloklangan


_LIC_NOM = "litsenziya.azlic"


def lic_fayl_yollari() -> list:
    """Litsenziya fayli qidiriladigan joylar (ustuvorlik tartibida, frozen-aware)."""
    yol = []
    env = os.environ.get("AZIZMED_LIC")
    if env:
        yol.append(env)
    for d in yollar.baza_papkalar():
        yol.append(os.path.join(d, _LIC_NOM))
    # paket papkasi (dev zahira)
    yol.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), _LIC_NOM))
    return yol


def faylni_top():
    for y in lic_fayl_yollari():
        if y and os.path.exists(y):
            return y
    return None


def _ochiq_kalit():
    if not OCHIQ_KALIT_HEX:
        return None
    try:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(OCHIQ_KALIT_HEX))
    except Exception:
        return None


def _kanonik(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class Natija:
    def __init__(self, holat: Holat, xabar: str = "", payload=None,
                 qolgan_kun=None, machine_id: str = ""):
        self.holat = holat
        self.xabar = xabar
        self.payload = payload or {}
        self.qolgan_kun = qolgan_kun
        self.machine_id = machine_id
        self.yaroqli = (holat == Holat.OK)

    def __repr__(self):
        return f"<Litsenziya {self.holat.value}: {self.xabar}>"


def _blobni_tekshir(paket: dict, mid: str):
    """Imzo + machine_id tekshiradi. (payload, holat) — holat: 'ok'|'soxta'|'boshqa'|'kalit_yoq'."""
    try:
        payload = paket["data"]
        imzo = bytes.fromhex(paket["imzo"])
    except Exception:
        return None, "soxta"
    pub = _ochiq_kalit()
    if pub is None:
        return None, "kalit_yoq"
    try:
        pub.verify(imzo, _kanonik(payload))
    except Exception:
        return None, "soxta"
    if str(payload.get("machine_id", "")).upper() != mid:
        return payload, "boshqa"
    return payload, "ok"


def _online_tekshir(mid: str):
    """
    VPS dan holat (best-effort). Qaytaradi:
      'blok'       — masofadan bloklangan
      'yangilandi' — yangiroq litsenziya lokalga saqlandi (avto-uzaytirish)
      None         — o'zgarish yo'q / internet yo'q / yozuv yo'q
    Online 'ok' o'zi ruxsat bermaydi — faqat uy imzolagan blobni qabul qiladi.
    """
    try:
        import socket
        import requests
        from urllib.parse import urlparse
        from . import server_config
    except Exception:
        return None
    url = server_config.vps_url()
    # Tezkor ulanish tekshiruvi — VPS yo'q bo'lsa startup'ni kutdirmaydi (darhol offline)
    try:
        u = urlparse(url)
        port = u.port or (443 if u.scheme == "https" else 80)
        s = socket.create_connection((u.hostname, port), timeout=1.2)
        s.close()
    except Exception:
        return None
    try:
        r = requests.get(url + "/litsenziya/holat", params={"mid": mid}, timeout=3)
        if r.status_code != 200:
            return None
        paket = r.json()
        if not isinstance(paket, dict) or "imzo" not in paket:
            return None
    except Exception:
        return None

    payload, holat = _blobni_tekshir(paket, mid)
    if holat != "ok":
        return None
    if payload.get("bloklangan"):
        return "blok"

    online_exp = int(payload.get("expires_at", 0))
    lokal_exp = 0
    fayl = faylni_top()
    if fayl:
        try:
            with open(fayl, "r", encoding="utf-8") as f:
                lokal_exp = int(json.load(f).get("data", {}).get("expires_at", 0))
        except Exception:
            lokal_exp = 0
    if online_exp > lokal_exp:
        try:
            nishon = os.path.join(yollar.yoziladigan_papka(), _LIC_NOM)
            with open(nishon, "w", encoding="utf-8") as f:
                json.dump(paket, f, ensure_ascii=False)
            return "yangilandi"
        except Exception:
            return None
    return None


def holatni_tekshir(online: bool = True) -> Natija:
    mid = _mid.mashina_id()

    # Online qatlam (best-effort): masofadan blok yoki avto-uzaytirish
    if online:
        try:
            if _online_tekshir(mid) == "blok":
                return Natija(Holat.BLOKLANGAN,
                              "Litsenziya masofadan bloklangan. Administrator bilan bog'laning.",
                              machine_id=mid)
        except Exception:
            pass

    fayl = faylni_top()
    if not fayl:
        return Natija(Holat.YOQ, "Litsenziya topilmadi. Dastur faollashtirilmagan.",
                      machine_id=mid)
    try:
        with open(fayl, "r", encoding="utf-8") as f:
            paket = json.load(f)
    except Exception:
        return Natija(Holat.SOXTA, "Litsenziya fayli buzilgan yoki noto'g'ri.",
                      machine_id=mid)

    payload, holat = _blobni_tekshir(paket, mid)
    if holat == "kalit_yoq":
        return Natija(Holat.SOXTA,
                      "Ochiq kalit sozlanmagan — ishlab chiqaruvchiga murojaat qiling.",
                      machine_id=mid)
    if holat == "soxta":
        return Natija(Holat.SOXTA, "Imzo noto'g'ri — soxta litsenziya.", machine_id=mid)
    if holat == "boshqa":
        return Natija(Holat.BOSHQA_KOMPYUTER,
                      "Litsenziya boshqa kompyuter uchun berilgan.",
                      payload=payload, machine_id=mid)

    if payload.get("bloklangan"):
        return Natija(Holat.BLOKLANGAN, "Litsenziya bloklangan.",
                      payload=payload, machine_id=mid)

    # Anti-rollback
    vaqt_ok, ishonchli_hozir = vaqt_himoya.tekshir_va_yangila(mid)
    if not vaqt_ok:
        return Natija(Holat.VAQT_ORQAGA,
                      "Tizim vaqti orqaga qaytarilgan — litsenziya bloklandi.",
                      payload=payload, machine_id=mid)

    expires = int(payload.get("expires_at", 0))
    if ishonchli_hozir > expires:
        return Natija(Holat.MUDDATI_TUGAGAN, "Litsenziya muddati tugagan.",
                      payload=payload, machine_id=mid)

    qolgan_sek = expires - ishonchli_hozir
    qolgan = int(qolgan_sek // 86400)
    if qolgan_sek < 3600:
        matn = f"Litsenziya yaroqli. {int(qolgan_sek // 60)} daqiqa qoldi."
    elif qolgan_sek < 86400:
        matn = f"Litsenziya yaroqli. {int(qolgan_sek // 3600)} soat qoldi."
    else:
        matn = f"Litsenziya yaroqli. {qolgan} kun qoldi."
    return Natija(Holat.OK, matn, payload=payload, qolgan_kun=qolgan, machine_id=mid)


_data_kalit_cache = {"k": None}


def data_kalit():
    """
    Baza IP himoyasi uchun AES-256 kalit (32 bayt) yoki None.

    FAQAT yaroqli litsenziyada (imzo + machine_id + muddat tugamagan) qaytadi.
    Litsenziya yo'q / soxta / boshqa PC / muddati tugagan bo'lsa → None →
    shifrlangan katalog/norma OCHILMAYDI (baza boshqa dasturda ishlamaydi).
    Kalit litsenziya ichidagi `data_key` dan olinadi (oylik yangilashda o'zgarmaydi).
    Keshlanadi (har DB amalda qayta o'qilmaydi).
    """
    if _data_kalit_cache["k"] is not None:
        return _data_kalit_cache["k"]
    k = None
    try:
        fayl = faylni_top()
        if fayl:
            with open(fayl, "r", encoding="utf-8") as f:
                paket = json.load(f)
            mid = _mid.mashina_id()
            payload, holat = _blobni_tekshir(paket, mid)
            if holat == "ok" and not payload.get("bloklangan"):
                expires = int(payload.get("expires_at", 0))
                if expires == 0 or time.time() <= expires:
                    dk = payload.get("data_key")
                    if dk:
                        k = hashlib.sha256(
                            ("azizmed-data-v1:" + str(dk) + ":" + mid).encode("utf-8")
                        ).digest()
    except Exception:
        k = None
    if k is not None:
        _data_kalit_cache["k"] = k
    return k


def data_kalit_reset():
    """Faollashtirishdan keyin keshni tozalash (yangi litsenziya o'qilsin)."""
    _data_kalit_cache["k"] = None


def faollashtir(azlic_yoli: str) -> Natija:
    """
    Berilgan .azlic faylni LIMS root'ga `litsenziya.azlic` nomi bilan ko'chiradi,
    so'ng holatni qayta tekshiradi. (Faollashtirish oynasi shuni chaqiradi.)
    """
    try:
        with open(azlic_yoli, "r", encoding="utf-8") as f:
            mazmun = f.read()
        json.loads(mazmun)  # to'g'ri JSON ekanini tasdiqlash
    except Exception:
        return Natija(Holat.SOXTA, "Tanlangan fayl litsenziya emas.")
    nishon = os.path.join(yollar.yoziladigan_papka(), _LIC_NOM)
    try:
        with open(nishon, "w", encoding="utf-8") as f:
            f.write(mazmun)
    except Exception as e:
        return Natija(Holat.SOXTA, f"Faylni saqlab bo'lmadi: {e}")
    data_kalit_reset()  # yangi litsenziya kaliti o'qilsin
    return holatni_tekshir()
