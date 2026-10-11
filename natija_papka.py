# -*- coding: utf-8 -*-
r"""
Natija oynasi — analizator fayllari va sozlamalar papkasi (YAGONA QOIDA).

NEGA (2026-10-11, mijoz klinikasi): URIT-50 / BC-20s fayl yo'llari kodda
qattiq `G:\DASTUR\URIT 50\...` edi. Mijoz kompyuterida G: disk yo'q —
analizator natijasi keldi, lekin RAW/TXT fayl yozilmadi va Natija oynasi
«RAW fayllari topilmadi / DAT papkada yangi fayl yo'q» dedi.

Endi papka shu tartibda aniqlanadi:
  1) Tizim Sozlamalari > «📁 Papkalar» da ko'rsatilgani
     (analizator_config.json → papkalar.natija_fayllari);
  2) bo'sh bo'lsa — STANDART:
       • koddan ishlaganda (bizning ish xonasi)  → shu skript papkasi
         (= G:\DASTUR\URIT 50 — ilgarigidek, eski fayllar joyida qoladi);
       • EXE (mijoz/filial)                      → %ProgramData%\AzizMedLine\Natija
         (Program Files ga oddiy foydalanuvchi yoza olmaydi).

Yozuvchi (urit50_service, bc20s_listener) va o'quvchi (urine_window,
hematology_window, bc20s_csv_import) AYNAN shu funksiyalardan foydalanadi —
ikkalasi har xil papkaga qarab qolmasin.
"""

import os
import sys


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _skript_papka() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def programdata_papka() -> str:
    return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                        "AzizMedLine", "Natija")


def standart_papka() -> str:
    """Sozlamada papka ko'rsatilmaganda ishlatiladigan papka."""
    return programdata_papka() if frozen() else _skript_papka()


def sozlangan_papka() -> str:
    """Sozlamada qo'lda ko'rsatilgan papka ('' — ko'rsatilmagan)."""
    try:
        from monoblok_db_config import load_config
        return str((load_config().get("papkalar") or {}).get("natija_fayllari") or "").strip()
    except Exception:
        return ""


def asosiy_papka() -> str:
    """Analizator fayllari ildiz papkasi (Urit\\, BC-20s\\ shu ichida)."""
    p = sozlangan_papka()
    if p:
        try:
            os.makedirs(p, exist_ok=True)
            return p
        except Exception as e:
            # Sozlamadagi disk yo'q/ruxsat yo'q (masalan flesh olib qo'yilgan) —
            # natija yo'qolmasin, standart papkaga yozamiz.
            print(f"[papka] Sozlamadagi papka ishlamadi ({p}): {e} → standart")
    return standart_papka()


def _tayyor(p: str) -> str:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception as e:
        print(f"[papka] Yaratib bo'lmadi: {p}: {e}")
    return p


def urit_raw() -> str:
    """URIT-50 (siydik) RAW loglari: <asosiy>\\Urit\\RAW_LOGS\\YYYYMM\\urit_raw_*.txt"""
    return _tayyor(os.path.join(asosiy_papka(), "Urit", "RAW_LOGS"))


def bc20s_dat() -> str:
    """BC-20s (gemotologiya) TXT: <asosiy>\\BC-20s\\YYYYMM\\BC-20s_*.txt"""
    return _tayyor(os.path.join(asosiy_papka(), "BC-20s"))


def sozlama_papka() -> str:
    """Kichik sozlama fayllari (urit_prefs.json ...) — yozish mumkin bo'lgan joy."""
    return _tayyor(programdata_papka()) if frozen() else _skript_papka()


def ichki_fayl(nom: str) -> str:
    """EXE ichiga qo'shilgan (PyInstaller datas) faylning yo'li; koddan — skript yonidagi."""
    if frozen():
        baza = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(baza, nom)
    return os.path.join(_skript_papka(), nom)


def birinchi_mavjud(*yollar: str) -> str:
    """Berilgan yo'llardan birinchi mavjudini qaytaradi (hech biri yo'q — birinchisi)."""
    for y in yollar:
        if y and os.path.exists(y):
            return y
    return yollar[0] if yollar else ""
