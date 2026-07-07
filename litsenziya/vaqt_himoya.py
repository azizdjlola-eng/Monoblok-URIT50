# -*- coding: utf-8 -*-
"""
Anti-rollback vaqt himoyasi.

Muammo: mijoz tizim soatini orqaga surib, muddati tugagan litsenziyani "tirik"
ko'rsatishi mumkin. Yechim: eng katta ko'rilgan vaqtni (high-water-mark, HWM)
IKKI joyda — yashirin shifrlangan faylda VA registrda — saqlaymiz. Har ishga
tushganda:
  - HWM = max(fayl, registr)
  - agar hozirgi_vaqt < HWM - TOLERANS  →  vaqt orqaga qaytarilgan (BLOK)
  - "ishonchli hozir" = max(hozirgi_vaqt, HWM)  (faqat oldinga harakatlanadi)
  - HWM ikkala joyda yangilanadi.

Shifrlash kaliti machine_id dan hosil qilinadi — boshqa kompyuterda yoki qo'lda
tahrirlab bo'lmaydi (Fernet imzo buziladi → 0 deb hisoblanadi, lekin ikkinchi
nusxa saqlanib qoladi).
"""

import os
import time
import base64
import hashlib

try:
    import winreg
except ImportError:
    winreg = None

from cryptography.fernet import Fernet

from . import yollar

_REG_YOL = r"Software\AzizMedLine\Sys"
_REG_NOM = "tk"
_TOLERANS = 24 * 3600  # 1 kun — vaqt mintaqasi / NTP tuzatishlari uchun zahira


def _kalit(machine_id: str) -> bytes:
    h = hashlib.sha256(("VAQT-HIMOYA::" + machine_id).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(h)


def _shifrla(machine_id: str, qiymat: int) -> str:
    return Fernet(_kalit(machine_id)).encrypt(str(int(qiymat)).encode()).decode()


def _deshifrla(machine_id: str, token: str) -> int:
    try:
        return int(Fernet(_kalit(machine_id)).decrypt(token.encode()).decode())
    except Exception:
        return 0


# ── Fayl nusxasi ──
def _fayl_yoli() -> str:
    return os.path.join(yollar.yoziladigan_papka(), ".vaqt_belgisi")


def _fayldan_oqi(machine_id: str) -> int:
    try:
        with open(_fayl_yoli(), "r", encoding="utf-8") as f:
            return _deshifrla(machine_id, f.read().strip())
    except Exception:
        return 0


def _faylga_yoz(machine_id: str, qiymat: int) -> None:
    try:
        fayl = _fayl_yoli()
        with open(fayl, "w", encoding="utf-8") as f:
            f.write(_shifrla(machine_id, qiymat))
        try:  # yashirin qilish
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(fayl, 0x2)  # FILE_ATTRIBUTE_HIDDEN
        except Exception:
            pass
    except Exception:
        pass


# ── Registr nusxasi ──
def _regdan_oqi(machine_id: str) -> int:
    if winreg is None:
        return 0
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_YOL)
        v, _ = winreg.QueryValueEx(k, _REG_NOM)
        winreg.CloseKey(k)
        return _deshifrla(machine_id, v)
    except Exception:
        return 0


def _regga_yoz(machine_id: str, qiymat: int) -> None:
    if winreg is None:
        return
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_YOL)
        winreg.SetValueEx(k, _REG_NOM, 0, winreg.REG_SZ, _shifrla(machine_id, qiymat))
        winreg.CloseKey(k)
    except Exception:
        pass


def tekshir_va_yangila(machine_id: str):
    """
    (ok, ishonchli_hozir) qaytaradi.
      ok = False  → vaqt sezilarli darajada orqaga qaytarilgan (litsenziyani bloklang)
      ishonchli_hozir = max(tizim_vaqti, HWM) — muddat tekshiruvida shu ishlatiladi
    """
    now = int(time.time())
    hwm = max(_fayldan_oqi(machine_id), _regdan_oqi(machine_id))
    ok = not (now < hwm - _TOLERANS)
    ishonchli_hozir = max(now, hwm)
    # HWM faqat oldinga
    _faylga_yoz(machine_id, ishonchli_hozir)
    _regga_yoz(machine_id, ishonchli_hozir)
    return ok, ishonchli_hozir
