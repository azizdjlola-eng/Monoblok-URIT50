# -*- coding: utf-8 -*-
r"""
Bioximiya LIS xizmati — monoblok tomonidagi boshqaruv (23.10.2026).

MUAMMO: bioximiya listener monoblok jarayoni ICHIDA ishlardi. Monoblok har
yopilganda/qayta ochilganda (kuniga 2-5 marta) TCP ulanish uziladi, BK-280
(CRYSTAL) esa o'zi QAYTA ULANMAYDI: keyingi natijada "LIS server yo'q"
oynasini chiqaradi va real vaqtli yuborishni o'chiradi. Laborant analizatorda
LIS sozlamasi → "Ulanish" ni bosmaguncha (loglarda 1 soatgacha) shtrix-kod
ham, natija ham ishlamaydi. 23.10.2026 ertalab listener umuman ochilmagan
(08:26-09:25) — analizator dasturi qotgan.

YECHIM: listener alohida fon jarayonida ishlaydi:
    pythonw bk280_listener.py --xizmat
Monoblok ishga tushganda uni ochadi (yoki ishlab turganini ko'radi), lekin
yopilganda TO'XTATMAYDI. Bitta nusxa — nomli mutex. Holat:
%ProgramData%\AzizMedLine\BK280\xizmat_holat.json (har 2 s).
"""

import json
import os
import subprocess
import sys
import time

_BASE = os.path.dirname(os.path.abspath(__file__))
_BK_DATA = os.environ.get("BIO_DATA_DIR") or os.path.join(
    os.environ.get("ProgramData") or r"C:\ProgramData", "AzizMedLine", "BK280")
HOLAT_FAYL = os.path.join(_BK_DATA, "xizmat_holat.json")
BUYRUQ_FAYL = os.path.join(_BK_DATA, "xizmat_buyruq.txt")
SKRIPT = os.path.join(_BASE, "bk280_listener.py")

# Holat fayli shundan eski bo'lsa — xizmat javob bermayapti deb hisoblanadi
HOLAT_ESKIRISH_S = 15


def holat_oqi():
    """Xizmat holati (dict) yoki None. "_yosh" — necha soniya oldin yozilgan."""
    try:
        with open(HOLAT_FAYL, "r", encoding="utf-8") as f:
            h = json.load(f)
        h["_yosh"] = time.time() - float(h.get("time", 0) or 0)
        return h
    except Exception:
        return None


def ishlayaptimi() -> bool:
    """Xizmat jarayoni bormi (nomli mutex bo'yicha)."""
    try:
        from bk280_listener import xizmat_ishlayaptimi
        return xizmat_ishlayaptimi()
    except Exception:
        return False


def _pythonw() -> str:
    exe = sys.executable or "python"
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return pw if os.path.exists(pw) else exe


def _pid_tirikmi(pid) -> bool:
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        h = k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return code.value == 259                        # STILL_ACTIVE
    except Exception:
        return False


def mavjudmi() -> bool:
    """Xizmat rejimi shu o'rnatmada ishlaydimi. EXE (PyInstaller) da sys.executable — butun
    dasturning o'zi: uni "--xizmat" bilan ochsak ikkinchi Natija oynasi ochilib ketardi."""
    return not getattr(sys, "frozen", False) and os.path.exists(SKRIPT)


def ishga_tushir() -> bool:
    """Fon jarayonini ochadi: konsolsiz, monoblokdan mustaqil (u yopilsa ham yashaydi)."""
    if not mavjudmi():
        return False
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=_BASE, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    # Monoblok "py.exe" orqali ochilgan bo'lsa u job object ichida bo'lishi mumkin —
    # job yopilganda bolalar ham o'ladi. Avval jobdan ajralib ochishga harakat qilamiz.
    for extra in (0x01000000, 0):                       # CREATE_BREAKAWAY_FROM_JOB, keyin oddiy
        try:
            subprocess.Popen([_pythonw(), SKRIPT, "--xizmat"], creationflags=flags | extra, **kw)
            return True
        except OSError:
            continue
    return False


def _kut_tinglash(kutish: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < kutish:
        h = holat_oqi()
        if h and h.get("mode") == "xizmat" and h["_yosh"] < 5 and h.get("listening"):
            return True
        time.sleep(0.5)
    return False


def taminla(kutish: float = 12.0):
    """Xizmat ishlab, port tinglanayotganiga ishonch hosil qiladi; kerak bo'lsa ochadi.
    Qaytaradi (ok, xabar)."""
    if not mavjudmi():
        return False, "Fon xizmati bu o'rnatmada yo'q (EXE) — listener dastur ichida ishlaydi"
    if ishlayaptimi():
        h = holat_oqi()
        if h and h.get("mode") == "xizmat" and h["_yosh"] < HOLAT_ESKIRISH_S and h.get("listening"):
            return True, "Bioximiya LIS xizmati ishlab turibdi"
        if _kut_tinglash(min(kutish, 8.0)):
            return True, "Bioximiya LIS xizmati ishlab turibdi"
        return False, "Xizmat jarayoni bor, lekin port tinglanmayapti (logs/bio_*.log ga qarang)"
    if not ishga_tushir():
        return False, "Xizmatni ishga tushirib bo'lmadi"
    if _kut_tinglash(kutish):
        return True, "Bioximiya LIS xizmati ishga tushdi"
    return False, "Xizmat ochildi, lekin port tinglanmayapti (logs/bio_*.log ga qarang)"


def toxtat(kutish: float = 8.0) -> bool:
    """Xizmatni to'xtatadi (avval buyruq bilan, javob bermasa — majburan)."""
    try:
        os.makedirs(_BK_DATA, exist_ok=True)
        with open(BUYRUQ_FAYL, "w", encoding="utf-8") as f:
            f.write("stop")
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < kutish:
        if not ishlayaptimi():
            return True
        time.sleep(0.3)
    h = holat_oqi()
    pid = h.get("pid") if h else None
    if pid and _pid_tirikmi(pid):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=10)
        except Exception:
            pass
        time.sleep(1.0)
    return not ishlayaptimi()


def qayta_ishga_tushir():
    """To'xtatib qayta ochadi. DIQQAT: analizator ulanishi uziladi — BK-280 da
    LIS sozlamasi → "Ulanish" ni qayta bosish kerak bo'ladi."""
    toxtat()
    time.sleep(1.0)
    return taminla()


def kod_eskirganmi(h) -> bool:
    """Xizmat eski kod bilan ishlayaptimi (bk280_listener/bio_protokol/gemo_protokol keyin
    yangilangan). Analizator ulanmagan paytda qayta ochish xavfsiz."""
    try:
        from bk280_listener import _kod_mtime
        return float((h or {}).get("code_mtime", 0) or 0) + 1 < _kod_mtime()
    except Exception:
        return False


def holat_matni(h) -> str:
    """Tugma ustidagi izoh uchun qisqa matn."""
    if not h:
        return "LIS xizmati ishlamayapti"
    q = []
    if h.get("connected"):
        q.append(f"Analizator ulangan: {h.get('peer', '')}")
        if h.get("conn_since"):
            q.append(f"ulanish: {h['conn_since'].replace('T', ' ')}")
    elif h.get("listening"):
        q.append("Analizator ULANMAGAN — BK-280 da: LIS sozlamasi → «Ulanish» (Подключить)")
    else:
        q.append("LIS server porti tinglanmayapti")
    if h.get("last_result"):
        q.append(f"oxirgi natija: {h['last_result'].replace('T', ' ')}")
    if h.get("last_query"):
        q.append(f"oxirgi shtrix-kod so'rovi: {h['last_query'].replace('T', ' ')}")
    q.append(f"rejim: {'fon xizmati' if h.get('mode') == 'xizmat' else 'dastur ichida'}"
             f" (pid {h.get('pid')})")
    return "\n".join(q)
