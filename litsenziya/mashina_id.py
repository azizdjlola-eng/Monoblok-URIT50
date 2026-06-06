# -*- coding: utf-8 -*-
"""
Hardware fingerprint — har bir kompyuter uchun barqaror, noyob ID.

Asos: Windows MachineGuid + Protsessor ID + Anakart seriyasi.
  - Barqaror: qayta yuklanganda o'zgarmaydi.
  - Noyob: boshqa kompyuterga (disk/Windows ko'chirilsa ham protsessor boshqa) o'tsa o'zgaradi.
  - Windows qayta o'rnatilsa MachineGuid o'zgaradi → yangi litsenziya kerak (atayin shunday).

Natija: 24 belgili HEX (masalan: 8BF2F0A35AECA930BBFB5F88).
"""

import os
import sys
import uuid
import hashlib
import subprocess

try:
    import winreg
except ImportError:
    winreg = None

# "Chaqaloq" qiymatlar — ishonchsiz, hisobga olinmaydi
_AXLAT = {
    "", "none", "null", "default string", "to be filled by o.e.m.",
    "system serial number", "0", "00000000", "unknown", "not specified",
    "system manufacturer", "n/a", "filled by oem",
}


def _ps(buyruq: str) -> str:
    """PowerShell orqali bitta qiymat olish (xato bo'lsa bo'sh)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", buyruq],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _toza(qiymat: str) -> str:
    q = (qiymat or "").strip()
    return "" if q.lower() in _AXLAT else q


def _machine_guid() -> str:
    """Windows o'rnatish GUID — eng barqaror identifikator."""
    if winreg is not None:
        try:
            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            val, _ = winreg.QueryValueEx(k, "MachineGuid")
            winreg.CloseKey(k)
            return _toza(val)
        except Exception:
            pass
    return _toza(_ps(r"(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid"))


def _processor_id() -> str:
    return _toza(_ps("(Get-CimInstance Win32_Processor).ProcessorId"))


def _baseboard_serial() -> str:
    return _toza(_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber"))


def tafsilot() -> dict:
    """Yig'ilgan hardware qismlari (debug/ko'rsatish uchun)."""
    return {
        "machine_guid": _machine_guid(),
        "processor_id": _processor_id(),
        "baseboard": _baseboard_serial(),
    }


_KESH_ID = None


def mashina_id() -> str:
    """
    24 belgili HEX hardware fingerprint (sessiyada bir marta hisoblanadi — memoized).

    MachineGuid + ProcessorId + Baseboard birlashtiriladi.
    Hech bo'lmaganda bittasi bo'lsa barqaror ID chiqadi; hech narsa topilmasa
    (juda kam holat) MAC-manzilga tushadi.
    """
    global _KESH_ID
    if _KESH_ID:
        return _KESH_ID
    qismlar = [p for p in (_machine_guid(), _processor_id(), _baseboard_serial()) if p]
    if not qismlar:
        # Oxirgi chora — MAC manzil (kamroq barqaror, lekin hech bo'lmaganda biror narsa)
        qismlar = [f"MAC:{uuid.getnode():012X}"]
    xom = "||".join(sorted(qismlar))
    digest = hashlib.sha256(("AZIZMED-HW::" + xom).encode("utf-8")).hexdigest()
    _KESH_ID = digest[:24].upper()
    return _KESH_ID


if __name__ == "__main__":
    print("Machine ID :", mashina_id())
    print("Tafsilot   :")
    for k, v in tafsilot().items():
        print(f"   {k:14s}= {v or '(topilmadi)'}")
