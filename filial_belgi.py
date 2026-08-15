# -*- coding: utf-8 -*-
r"""
Filial mijozini aniqlash — Natija (monoblok) va Registratsiya uchun UMUMIY mantiq.

QOIDA (2026-08-14 da egasi bilan kelishilgan):
    Buyurtma qaysi filialda RO'YXATGA OLINGAN bo'lsa, qog'oz blanka O'SHA YERDA
    chiqadi. Boshqa filialning mijozi bo'lsa:
      • ekranda ochiq belgi ko'rsatiladi (laborant adashmasin),
      • blanka avtomatik CHOP ETILMAYDI — qog'oz behuda ketmasin, chunki bemor
        u yerda emas.
    Bemor baribir natijasini oladi: natija PDF chiqishi bilan SMS ketadi va
    Telegram botdan yuklab oladi (sms_tizimi.SMS_SHABLON).

NEGA ALOHIDA MODUL: bir xil qoida IKKI dasturda kerak, lekin ular turli
papkalarda yashaydi (D:\AzizMedLine_LIMS va G:\DASTUR\URIT 50). Qoida ikki
joyda nusxalansa, birini tuzatib ikkinchisini unutish muqarrar. Shuning uchun
build paneli shu faylni G: ga ko'chiradi (build_panel.EXTRA_G) va natija.spec
uni hiddenimports ga qo'shadi — EXE ichida ham AYNAN shu fayl ishlaydi.

SXEMA O'ZGARISHI YO'Q: `bemorlar.filial_id` va `orders.filial_id` ustunlari
allaqachon mavjud va sinxron qilinadi. Ya'ni bu modul yangi ustun talab
QILMAYDI → SCHEMA_VERSION bump kerak emas → sinxron mantiqiga umuman tegmaydi.
"""

import json
import os
import sys

# `local_filial_id` ni aniqlab bo'lmaganini bildiradi (fayl umuman topilmadi).
# MUHIM: bu holatda HECH NARSA to'sib qo'yilmaydi — blanka avvalgidek chop
# etiladi. Sozlama nosozligi tufayli filial O'Z mijozining blankasini chop
# eta olmay qolishi — chop etilmagan qog'ozdan ANCHA yomon nosozlik bo'lardi.
NOMA_LUM = None


# ─────────────────────────── mahalliy filial ─────────────────────────────────

def konfig_papka() -> str:
    """Barcha dasturlar uchun UMUMIY sozlama papkasi (db_config.txt shu yerda)."""
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(pd, "AzizMedLine")


def filial_fayl() -> str:
    r"""Kompyuterning filial raqami saqlanadigan YAGONA joy.

    NEGA ALOHIDA FAYL KERAK BO'LDI: `local_settings.json` har dasturning O'Z
    papkasida yashaydi (`baza_sinxron._DIR` = `sinxron_toliq.holat_papkasi()`).
    Manba rejimida u repo papkasi — D:\AzizMedLine_LIMS. Natija (monoblok)
    esa BUTUNLAY boshqa papkadan ishga tushadi (G:\DASTUR\URIT 50) va o'sha
    faylni umuman ko'rmaydi. Ya'ni asosiy laboratoriyada — filial belgisi eng
    kerak bo'lgan joyda — xususiyat hech qachon yonmasdi.

    Yechim `db_config.txt` dagi bilan AYNAN bir xil: bitta kanonik fayl
    %ProgramData%\AzizMedLine\ da. Uni har dastur (Registratsiya D: dan,
    Natija G: dan, EXE bo'lsa o'z papkasidan) bir xil ko'radi.
    """
    return os.path.join(konfig_papka(), "filial.txt")


def saqla(filial_id: int):
    """Kompyuterning filial raqamini kanonik joyga yozadi (Sozlama oynasidan).

    `local_settings.json` ga yozish SAQLANADI (aloqa_widget uni yozaveradi) —
    bu qo'shimcha, dasturlararo ko'rinadigan nusxa."""
    os.makedirs(konfig_papka(), exist_ok=True)
    with open(filial_fayl(), "w", encoding="utf-8") as f:
        f.write("# AzizMedLine — bu kompyuter qaysi filialda (kipiy_filiallar.id)\n")
        f.write(f"FILIAL_ID={int(filial_id)}\n")


def _kanonik_filial_id():
    """filial.txt dan o'qish. Topilmasa/buzuq bo'lsa None."""
    yol = filial_fayl()
    if not os.path.exists(yol):
        return None
    try:
        with open(yol, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                kalit, qiymat = line.split("=", 1)
                if kalit.strip().upper() in ("FILIAL_ID", "LOCAL_FILIAL_ID"):
                    return int(qiymat.strip())
    except Exception:
        return None
    return None


def _sozlama_nomzodlari() -> list:
    """`local_settings.json` qidiriladigan joylar (ustuvorlik tartibida).

    NEGA BIR NECHTA JOY: frozen EXE da har dastur o'z papkasidan ishga tushadi
    va `local_settings.py` faylni O'Z yonidan o'qiydi. Sinxron moduli esa
    `sinxron_toliq.holat_papkasi()` — ya'ni %ProgramData%\\AzizMedLine\\
    sinxron_holat — dan o'qiydi. Ikkalasi TURLI fayl bo'lib qolishi mumkin.
    Shuning uchun kanonik (sinxron ishlatadigan) joyni BIRINCHI ko'ramiz.
    """
    yollar = []
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    yollar.append(os.path.join(pd, "AzizMedLine", "sinxron_holat", "local_settings.json"))

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        yollar.append(os.path.join(exe_dir, "local_settings.json"))
        ildiz = os.path.dirname(exe_dir)
        if ildiz:
            yollar.append(os.path.join(ildiz, "local_settings.json"))

    yollar.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "local_settings.json"))
    return yollar


def mahalliy_filial_id():
    """Bu kompyuter qaysi filialda turibdi. Topilmasa NOMA_LUM (None).

    Qaytadi:
      int       — sozlamada aniq yozilgan (yoki fayl bor, kalit yo'q → 1)
      NOMA_LUM  — hech qayerda sozlama topilmadi
    """
    # 1) Kanonik, dasturlararo fayl — %ProgramData%\AzizMedLine\filial.txt
    kanonik = _kanonik_filial_id()
    if kanonik is not None:
        return kanonik

    # 2) local_settings.json (dastur o'z papkasida saqlagani)
    for yol in _sozlama_nomzodlari():
        if not os.path.exists(yol):
            continue
        try:
            with open(yol, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        try:
            # Fayl bor, lekin kalit yo'q → standart 1 (asosiy laboratoriya).
            # local_settings._DEFAULTS bilan bir xil.
            return int(data.get("local_filial_id", 1) or 1)
        except (TypeError, ValueError):
            return 1
    return NOMA_LUM


# ─────────────────────────── buyurtma filiali ────────────────────────────────

def buyurtma_filial_id(conn, order_id):
    """Buyurtma qaysi filialda ro'yxatga olingan. Topilmasa None.

    `orders.filial_id` NULL bo'lishi normal: filial_id ustuni qo'shilishidan
    OLDINGI eski yozuvlarda (bu bazada 4063 ta) u bo'sh. Ular asosiy
    laboratoriyaniki deb qaraladi — pastdagi `boshqa_filial()` ga qarang.
    """
    if not conn or not order_id:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT filial_id FROM orders WHERE id = %s", (order_id,))
        qator = cur.fetchone()
        if not qator or qator[0] is None:
            return None
        return int(qator[0])
    except Exception:
        return None
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass


def filial_nomi(conn, filial_id) -> str:
    """kipiy_filiallar dagi nom. Topilmasa "Filial {id}"."""
    if not conn or not filial_id:
        return ""
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT nomi FROM kipiy_filiallar WHERE id = %s", (filial_id,))
        qator = cur.fetchone()
        if qator and qator[0]:
            return str(qator[0])
    except Exception:
        pass
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
    return f"Filial {filial_id}"


ASOSIY_FILIAL_ID = 1        # kipiy_filiallar da "Asosiy laboratoriya"


def asosiy_laboratoriyami() -> bool:
    """Bu kompyuter ASOSIY laboratoriyadami?

    Huquqlar shunga tayanadi: asosiy laboratoriya xodimi filial mijozini ham
    o'zgartira oladi (bemor filialda ro'yxatdan o'tib, keyin asosiyga kelib
    tahlil qo'shishi yoki bekor qilishi mumkin — egasi talabi, 2026-08-15).
    Filial xodimi esa FAQAT o'zinikini o'zgartiradi.

    Sozlama topilmasa True — ya'ni hech kim to'silmaydi (fail-safe).
    """
    mahalliy = mahalliy_filial_id()
    if mahalliy is NOMA_LUM:
        return True
    return int(mahalliy) == ASOSIY_FILIAL_ID


def boshqa_filial(conn, order_id):
    """Bu buyurtma BOSHQA filialning mijozimi?

    Qaytadi: (boshqami: bool, nomi: str)

    Fail-safe qoidalar — shubha bo'lsa "o'zimizniki" deb qaraladi, ya'ni
    blanka avvalgidek chop etiladi:
      • buyurtmaning filial_id si NULL (eski yozuv)      → o'zimizniki
      • mahalliy filial_id ni aniqlab bo'lmadi (NOMA_LUM) → o'zimizniki
      • ikkalasi teng                                     → o'zimizniki
    """
    buyurtma_fid = buyurtma_filial_id(conn, order_id)
    if buyurtma_fid is None:
        return False, ""

    mahalliy = mahalliy_filial_id()
    if mahalliy is NOMA_LUM or int(mahalliy) == int(buyurtma_fid):
        return False, ""

    return True, filial_nomi(conn, buyurtma_fid)
