# -*- coding: utf-8 -*-
"""
Fayl yo'llarini aniqlash — manba (dev) va EXE (PyInstaller, frozen) uchun bir xil ishlaydi.

EXE ichida __file__ vaqtinchalik _MEIPASS papkasiga ishora qiladi (har ishga tushganda
o'chadi). Shu sababli litsenziya fayli va anti-rollback belgisi EXE yonida / barqaror
foydalanuvchi papkasida qidiriladi va saqlanadi.
"""

import os
import sys


# O'rnatma ichidagi komponent papkalari (installer shu nomlar bilan yozadi).
# Bittasida litsenziya bo'lsa — qolganlari ham ko'radi.
KOMPONENTLAR = ("Registratsiya", "Natija", "VrachKabineti", "TVServer",
                "Sozlama", "Ustasi", "Tekshiruv")


def umumiy_papka() -> str:
    """%ProgramData%\\AzizMedLine — BARCHA dastur va BARCHA foydalanuvchi uchun
    yagona joy. Litsenziya shu yerga o'rnatiladi."""
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(pd, "AzizMedLine")


def baza_papkalar() -> list:
    """
    Litsenziya/belgi fayllari qidiriladigan barqaror papkalar (ustuvorlik tartibida).

    EXE (frozen) rejimida:
      1. EXE yonidagi papka                     (masalan ...\\AzizMedLine\\VrachKabineti)
      2. O'rnatma ildizi                        (...\\AzizMedLine)
      3. QO'SHNI komponent papkalari             (Registratsiya, Natija, TVServer ...)
      4. %ProgramData%\\AzizMedLine              ← yagona umumiy joy
      5. %LOCALAPPDATA%\\AzizMedLine

    DIQQAT: frozen rejimda manba (paket) papkasi QO'SHILMAYDI — u PyInstaller ning
    vaqtinchalik `_MEIPASS` papkasiga ishora qiladi va dastur yopilishi bilan
    o'chib ketadi. Ilgari litsenziya o'sha yerga yozilib yo'qolib qolardi.
    """
    yollar = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        yollar.append(exe_dir)
        ildiz = os.path.dirname(exe_dir)          # ...\AzizMedLine
        if ildiz:
            yollar.append(ildiz)
            for nom in KOMPONENTLAR:
                qoshni = os.path.join(ildiz, nom)
                if qoshni.lower() != exe_dir.lower():
                    yollar.append(qoshni)
    else:
        # Dev (manba) — LIMS root
        yollar.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    yollar.append(umumiy_papka())
    la = os.environ.get("LOCALAPPDATA")
    if la:
        yollar.append(os.path.join(la, "AzizMedLine"))

    natija, korilgan = [], set()
    for y in yollar:
        if y and y.lower() not in korilgan:
            korilgan.add(y.lower())
            natija.append(y)
    return natija


def _yozib_boladimi(d: str) -> bool:
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".w_test")
        with open(t, "w") as f:
            f.write("x")
        os.remove(t)
        return True
    except Exception:
        return False


def yoziladigan_papka() -> str:
    """
    Litsenziya YOZILADIGAN papka.

    Frozen: %ProgramData%\\AzizMedLine — bitta faollashtirish o'rnatmadagi
    BARCHA dasturga (Registratsiya, Natija, Vrach kabineti, TV server) va
    barcha Windows foydalanuvchisiga amal qilsin. Yozib bo'lmasa —
    %LOCALAPPDATA%, oxirgi chora sifatida EXE papkasi.

    Dev: manba (LIMS root) — ilgarigidek.
    """
    if getattr(sys, "frozen", False):
        nomzodlar = [umumiy_papka()]
        la = os.environ.get("LOCALAPPDATA")
        if la:
            nomzodlar.append(os.path.join(la, "AzizMedLine"))
        nomzodlar.append(os.path.dirname(sys.executable))
    else:
        nomzodlar = list(baza_papkalar())

    for d in nomzodlar:
        if _yozib_boladimi(d):
            return d
    return nomzodlar[0]
