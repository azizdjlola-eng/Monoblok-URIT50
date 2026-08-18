# -*- coding: utf-8 -*-
r"""Natija (Monoblok) dasturini konsol oynasisiz ishga tushiradi.

IKKI TUZATISH (2026-08-15):

1) Python yo'li QATTIQ YOZILMAYDI. Ilgari bu yerda
   `C:\Users\1111111111\...\python.exe` turardi — boshqa nomdagi
   foydalanuvchida fayl jimgina hech narsa qilmasdi.

2) CREATE_NO_WINDOW bilan bolaga konsol berilmaydi → `sys.stdout is None`
   bo'ladi va monoblokning birinchi print() i ("Monoblok Dastur ishga
   tushmoqda...") AttributeError bilan dasturni DARHOL o'ldiradi: oyna
   ochilmaydi, xato ham ko'rinmaydi. Shuning uchun chiqish DEVNULL ga
   yo'naltiriladi — sys.stdout haqiqiy bo'ladi, print() lar bemalol ishlaydi.
"""

import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monoblok_dastur.py")


def python_topish():
    """Bu kompyuterdagi python.exe. Topilmasa joriy interpretator."""
    yonidagi = os.path.join(os.path.dirname(sys.executable), "python.exe")
    nomzodlar = [yonidagi]
    lokal = os.environ.get("LOCALAPPDATA", "")
    if lokal:
        for v in ("Python313", "Python312", "Python311", "Python310"):
            nomzodlar.append(os.path.join(lokal, "Programs", "Python", v, "python.exe"))
    for yol in nomzodlar:
        if os.path.exists(yol):
            return yol
    return sys.executable


os.chdir(os.path.dirname(SCRIPT))
subprocess.Popen(
    [python_topish(), SCRIPT],
    creationflags=subprocess.CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
