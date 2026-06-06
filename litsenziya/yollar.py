# -*- coding: utf-8 -*-
"""
Fayl yo'llarini aniqlash — manba (dev) va EXE (PyInstaller, frozen) uchun bir xil ishlaydi.

EXE ichida __file__ vaqtinchalik _MEIPASS papkasiga ishora qiladi (har ishga tushganda
o'chadi). Shu sababli litsenziya fayli va anti-rollback belgisi EXE yonida / barqaror
foydalanuvchi papkasida qidiriladi va saqlanadi.
"""

import os
import sys


def baza_papkalar() -> list:
    """
    Litsenziya/belgi fayllari qidiriladigan barqaror papkalar (ustuvorlik tartibida):
      1. EXE yonidagi papka (frozen)
      2. Manba (LIMS root) — dev rejimi
      3. %LOCALAPPDATA%\\AzizMedLine
      4. %ProgramData%\\AzizMedLine
    """
    yollar = []
    if getattr(sys, "frozen", False):
        yollar.append(os.path.dirname(sys.executable))
    yollar.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # manba root
    la = os.environ.get("LOCALAPPDATA")
    if la:
        yollar.append(os.path.join(la, "AzizMedLine"))
    pd = os.environ.get("ProgramData")
    if pd:
        yollar.append(os.path.join(pd, "AzizMedLine"))

    natija, korilgan = [], set()
    for y in yollar:
        if y and y not in korilgan:
            korilgan.add(y)
            natija.append(y)
    return natija


def yoziladigan_papka() -> str:
    """Yozish mumkin bo'lgan birinchi barqaror papka (yaratib beradi)."""
    for d in baza_papkalar():
        try:
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, ".w_test")
            with open(t, "w") as f:
                f.write("x")
            os.remove(t)
            return d
        except Exception:
            continue
    return baza_papkalar()[0]
