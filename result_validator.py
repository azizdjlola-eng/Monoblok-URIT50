# -*- coding: utf-8 -*-
"""
NATIJA KIRITISH XATOLIGINI ANIQLASH (Xatolik ehtimoli / lineynost tekshiruvi).

Maqsad: klaviatura yopishib qolishi, tugma bosilib ketishi, sichqoncha xatosi yoki
e'tiborsizlik natijasida NOTO'G'RI yozilgan natija saqlanib/chop etilib ketmasligi.
Masalan: "2.37-1", "1.152.01", "00.976", "1111.5".

Bu modul `critical_alert.py` dan FARQ QILADI:
  • critical_alert.py — OGOHLANTIRISH signali: natija to'g'ri yozilgan bo'lsa ham
    klinik/reagent jihatdan xavotirli (analizatordan kelgan natijalar uchun).
  • result_validator.py — XATOLIK EHTIMOLI: natija noto'g'ri YOZILGAN bo'lishi mumkin
    (format + o'lchash chegarasi / lineynost). Barcha tahlillar uchun.

╔══════════════════════════════════════════════════════════════════════════════╗
║  CHEGARALARNI QAYERDA O'ZGARTIRISH KERAK                                     ║
║                                                                              ║
║  1) TEZ YO'L (kodga tegmasdan) — `result_limits.json` faylini tahrirlang.    ║
║     Fayl shu skript/exe yonida turadi, birinchi ishga tushganda avtomatik    ║
║     yaratiladi. U yerdagi qiymat pastdagi DEFAULT_CONFIG ustidan yoziladi.   ║
║                                                                              ║
║  2) KOD ICHIDA — shu faylning pastidagi DEFAULT_CONFIG ichida:               ║
║     • "analytes" bo'limi — ⭐ ENG MUHIM. Bir modda (masalan Kreatinin) ham    ║
║       alohida tahlil sifatida, ham panel ichida (BUYRAK PANELI) uchraydi.    ║
║       Uning chegarasi FAQAT shu yerda bir marta yoziladi, qolgan joylar      ║
║       {"ref": "kreatinin"} orqali shunga havola qiladi. Shu sababli ikki     ║
║       joyda turlicha bo'lib qolishi MUMKIN EMAS.                             ║
║     • "single" bo'limi — bir komponentli tahlillar.                          ║
║       Kalit = `tahlillar.id` (katalog ID, order_items.id EMAS!).             ║
║       Masalan ALT uchun:  "39": {"min": 0, "max": 4000, ...}                 ║
║     • "multi" bo'limi — ko'p komponentli tahlillar.                          ║
║       Kalit = "{tahlil_id}.{komponent_kaliti}".                              ║
║       Masalan bilirubin umumiy:  "55.umumiy": {"min": 0, "max": 400, ...}    ║
║     • "options" bo'limi — sifat (musbat/manfiy) tahlillari uchun ruxsat      ║
║       etilgan javoblar ro'yxati.                                             ║
║                                                                              ║
║  Spec maydonlari:                                                            ║
║     ref   — "analytes" dagi umumiy modda nomi (chegara o'shandan olinadi)    ║
║     name  — ko'rsatiladigan nom (nom bo'yicha qidirishda ham ishlatiladi)    ║
║     unit  — birlik (faqat xabar matni uchun)                                 ║
║     min   — shundan past bo'lsa "o'lchash chegarasidan past" xatosi          ║
║     max   — shundan baland bo'lsa "o'lchash chegarasidan baland" xatosi      ║
║     fmt   — "decimal" (o'nlik son) | "int" (butun son) |                     ║
║             "any" (tekshirilmaydi) | "text" (faqat bo'shligi tekshiriladi)   ║
║                                                                              ║
║  min/max ni olib tashlash uchun null yozing:  "min": null                    ║
║  Butun bir tahlilni tekshiruvdan chiqarish uchun:  "fmt": "any"              ║
║  ref bo'lsa ham alohida qiymat berish mumkin — u ref ustidan yoziladi        ║
║  (lekin bu ATAYLAB farq kerak bo'lgandagina; aks holda drift qaytadi).       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Chegara qiymatlarining manbasi: `docs/natija_chegaralari_taklif.xlsx`
(1-varaq "Xatolik ehtimoli: Min/Max" ustunlari, 3-varaq ko'p komponentlilar uchun).
"""

import os
import re
import sys
import json

# ── Papka (manba yoki EXE) ────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(BASE_DIR, "result_limits.json")


# ══════════════════════════════════════════════════════════════════════════
#  STANDART CHEGARALAR
#  Kalit = tahlillar.id (katalog ID). Manba: docs/natija_chegaralari_taklif.xlsx
# ══════════════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    # Struktura versiyasi. O'zgarganda eski result_limits.json avtomatik
    # .bak ga nusxalanadi va yangi struktura bilan qayta yoziladi.
    "version": 2,

    "enabled": True,
    "sound": True,

    # ══════════════════════════════════════════════════════════════════════
    #  ⭐ UMUMIY MODDALAR (ANALYTES)
    #
    #  Bir modda bir necha joyda uchraydi: alohida tahlil sifatida ham,
    #  ko'p komponentli panel ichida ham. Masalan Kreatinin:
    #     • alohida "Kreatinin" tahlili        (tahlillar.id = 41)
    #     • "BUYRAK PANELI" ichida             (127.kreatinin)
    #  Ularning chegarasi ikki xil bo'lib qolmasligi uchun qiymat FAQAT
    #  shu yerda bir marta yoziladi. Qolgan joylar {"ref": "..."} qiladi.
    #
    #  ⇒ Chegarani o'zgartirish kerak bo'lsa — SHU YERNI tahrirlang,
    #    o'zgarish avtomatik hamma joyga (alohida test + panel) tarqaladi.
    # ══════════════════════════════════════════════════════════════════════
    "analytes": {
        # --- Buyrak paneli va alohida testlar uchun umumiy ---
        "kreatinin":      {"name": "Kreatinin",                "unit": "mkmol/l", "min": 20,  "max": 2800, "fmt": "decimal"},
        "mochevina":      {"name": "Mochevina",                "unit": "mmol/l",  "min": 0.5, "max": 50,   "fmt": "decimal"},
        "siydik_kislota": {"name": "Siydik kislotasi",         "unit": "mkmol/l", "min": 30,  "max": 1500, "fmt": "decimal"},
        "albumin":        {"name": "Albumin",                  "unit": "g/l",     "min": 2,   "max": 60,   "fmt": "decimal"},

        # --- Lipid spektri va alohida testlar uchun umumiy ---
        "xolesterin_tc":  {"name": "Umumiy xolesterin (TC)",   "unit": "mmol/l",  "min": 0.5, "max": 20,   "fmt": "decimal"},
        "hdl":            {"name": "HDL",                      "unit": "mmol/l",  "min": 0.1, "max": 5,    "fmt": "decimal"},
        "ldl":            {"name": "LDL",                      "unit": "mmol/l",  "min": 0.2, "max": 10,   "fmt": "decimal"},
        "trigliserid":    {"name": "Trigliseridlar (TG)",      "unit": "mmol/l",  "min": 0.1, "max": 11.4, "fmt": "decimal"},

        # --- Koagulogramma va alohida testlar uchun umumiy ---
        "achtv":          {"name": "ACHTV",                    "unit": "sek",     "min": 10,  "max": 120,  "fmt": "decimal"},
        "fibrinogen":     {"name": "Fibrinogen",               "unit": "g/l",     "min": 0.3, "max": 10,   "fmt": "decimal"},
        "tt":             {"name": "Trombin vaqti (TT)",       "unit": "sek",     "min": 9,   "max": 60,   "fmt": "decimal"},
        "pt_sek":         {"name": "PT sekundalarda",          "unit": "sek",     "min": 8,   "max": 120,  "fmt": "decimal"},
        "pt_kviku":       {"name": "PT bo'yicha Kviku",        "unit": "%",       "min": 5,   "max": 150,  "fmt": "decimal"},
        "pt_mno":         {"name": "MNO / INR",                "unit": "INR",     "min": 0.5, "max": 8,    "fmt": "decimal"},

        # --- Revmoproba (avtomat) va alohida testlar uchun umumiy ---
        "rf_avtomat":     {"name": "RF (Revmatoidniy faktor) avtomat",  "unit": "ME/ml", "min": 0, "max": 200,  "fmt": "decimal"},
        "crp_avtomat":    {"name": "CRP (S-reaktivniy belok) avtomat",  "unit": "mg/l",  "min": 0, "max": 300,  "fmt": "decimal"},
        "aslo_avtomat":   {"name": "ASLO (Antistreptolizin-O) avtomat", "unit": "ME/ml", "min": 0, "max": 1300, "fmt": "decimal"},
    },

    # ── BIR KOMPONENTLI TAHLILLAR ─────────────────────────────────────────
    # Kalit = tahlillar.id
    "single": {
        # --- Bioximiya ---
        "39":  {"name": "Alanin aminotransferaza (ALT)",      "unit": "E/l",     "min": 0,    "max": 4000,   "fmt": "decimal"},
        "35":  {"ref": "albumin"},                       # ← BUYRAK PANELI bilan umumiy
        "56":  {"name": "Alfa-amilaza",                       "unit": "E/l",     "min": 0,    "max": 1200,   "fmt": "decimal"},
        "57":  {"name": "Alfa-amilaza pankreaticheskiy",      "unit": "E/l",     "min": 0,    "max": 1200,   "fmt": "decimal"},
        "40":  {"name": "Aspartat aminotransferaza (AST)",    "unit": "E/l",     "min": 0,    "max": 4000,   "fmt": "decimal"},
        "46":  {"name": "Gamma-glutamil transferaza (GGT)",   "unit": "E/l",     "min": 0,    "max": 1200,   "fmt": "decimal"},
        "37":  {"name": "Glyukoza",                           "unit": "mmol/l",  "min": 0.3,  "max": 41.6,   "fmt": "decimal"},
        "38":  {"name": "Glyukozaga tolerantlik testi",       "unit": "mmol/l",  "min": 0.3,  "max": 41.6,   "fmt": "decimal"},
        "53":  {"name": "Ishqoriy fosfataza (IF)",            "unit": "E/l",     "min": 0,    "max": 1200,   "fmt": "decimal"},
        "48":  {"name": "Kaliy K",                            "unit": "mmol/l",  "min": 1.5,  "max": 10,     "fmt": "decimal"},
        "47":  {"name": "Kalsiy Ca",                          "unit": "mmol/l",  "min": 1,    "max": 4,      "fmt": "decimal"},
        "41":  {"ref": "kreatinin"},                     # ← BUYRAK PANELI bilan umumiy
        "45":  {"name": "Laktatdegidrogrenaza (LDG)",         "unit": "E/l",     "min": 0,    "max": 1000,   "fmt": "decimal"},
        # DIQQAT: Magniy BK-280 da mg/dl da o'lchanadi (norma 1.7-2.4 mg/dl).
        # mmol/l ga o'tkazilsa: mg/dl = mmol/l * 2.43
        "51":  {"name": "Magniy Mg",                          "unit": "mg/dl",   "min": 0.2,  "max": 12,     "fmt": "decimal"},
        "42":  {"ref": "mochevina"},                     # ← BUYRAK PANELI bilan umumiy
        "52":  {"name": "Natriy Na",                          "unit": "mmol/l",  "min": 100,  "max": 190,    "fmt": "decimal"},
        "50":  {"ref": "siydik_kislota",                 # ← BUYRAK PANELI bilan umumiy
                "name": "Siydik kislota (Mochevaya kislota)"},
        "49":  {"name": "Temir  Fe",                          "unit": "mkmol/l", "min": 0,    "max": 100,    "fmt": "decimal"},
        "54":  {"name": "Timol proba",                        "unit": "ye.",     "min": 0,    "max": 20,     "fmt": "decimal"},
        "44":  {"ref": "trigliserid", "name": "Trigliserid-TG"},          # ← LIPID SPEKTRI bilan umumiy
        "36":  {"name": "Umumiy oqsil",                       "unit": "g/l",     "min": 10,   "max": 150,    "fmt": "decimal"},
        "43":  {"ref": "xolesterin_tc"},                 # ← LIPID SPEKTRI bilan umumiy
        "123": {"ref": "ldl", "name": "LDL-Past zichlikli lipoprotein"},   # ← LIPID SPEKTRI bilan umumiy
        "124": {"ref": "hdl", "name": "HDL-Yuqori zichlikli lipoprotein"}, # ← LIPID SPEKTRI bilan umumiy
        "128": {"name": "Xolinesteraza (CHE)",                "unit": "E/l",     "min": 300,  "max": 19000,  "fmt": "decimal"},   # analizator kasr xona bilan beradi

        # --- Gemostaz (alohida buyurtma qilinganda) ---
        "76":  {"ref": "achtv"},                         # ← KOAGULOGRAMMA bilan umumiy
        "75":  {"ref": "fibrinogen"},                    # ← KOAGULOGRAMMA bilan umumiy
        "74":  {"ref": "pt_sek", "name": "Protrombin Time (PTI, PT/MNO)"}, # ← KOAGULOGRAMMA bilan umumiy
        "77":  {"ref": "tt", "name": "Trombinovoe vremya (TT)"},           # ← KOAGULOGRAMMA bilan umumiy
        # QIB natijasi DIAPAZON bo'lib yoziladi ("2.20-3.00" = boshlandi-tugadi),
        # shuning uchun count_range — chiziqcha bu yerda xato emas, diapazon belgisi.
        "30":  {"name": "Qonning ivish vaqti  QIB",           "unit": "daq",     "min": 1,    "max": 30,     "fmt": "count_range"},
        "29":  {"name": "Eritrotsitlar cho'kish tezligi (ECHT)", "unit": "mm/soat", "min": 0, "max": 140,    "fmt": "int"},

        # --- Revmoproba komponentlari alohida buyurtma qilinganda ---
        "61":  {"ref": "aslo_avtomat"},                  # ← REVMOPROBA (avtomat) bilan umumiy
        "60":  {"ref": "crp_avtomat"},                   # ← REVMOPROBA (avtomat) bilan umumiy
        "59":  {"ref": "rf_avtomat"},                    # ← REVMOPROBA (avtomat) bilan umumiy

        # --- IFA / gormon / onkomarker / vitamin ---
        "129": {"name": "Anti HBsAg (Antitelo) immunitet IFA", "unit": "mME/ml", "min": 0,    "max": 1000,   "fmt": "decimal"},
        "99":  {"name": "Askarida IgG IFA",                   "unit": "KP",      "min": 0,    "max": 15,     "fmt": "decimal"},
        "109": {"name": "AT-TPO IFA",                         "unit": "ME/ml",   "min": 0,    "max": 1000,   "fmt": "decimal"},
        "69":  {"name": "CA 72-4 (oshqozon onkomarkeri)",     "unit": "E/ml",    "min": 0,    "max": 300,    "fmt": "decimal"},
        "70":  {"name": "CA15-3 (ko'krak saratoni belgisi)",  "unit": "E/ml",    "min": 0,    "max": 300,    "fmt": "decimal"},
        "86":  {"name": "Gepatit A (IgG, IFA)",               "unit": "KP",      "min": 0,    "max": 1000,     "fmt": "decimal"},   # KP kuchli musbatda 300+ bo'lishi mumkin
        "82":  {"name": "Gepatit B (HBsAg, IFA)",             "unit": "KP",      "min": 0,    "max": 1000,     "fmt": "decimal"},   # KP kuchli musbatda 300+ bo'lishi mumkin
        "84":  {"name": "Gepatit C (Anti-HCV, IFA)",          "unit": "KP",      "min": 0,    "max": 1000,     "fmt": "decimal"},   # KP kuchli musbatda 300+ bo'lishi mumkin
        "85":  {"name": "Gepatit D (D-antitela, IFA)",        "unit": "KP",      "min": 0,    "max": 1000,     "fmt": "decimal"},   # KP kuchli musbatda 300+ bo'lishi mumkin
        "98":  {"name": "IgE umumiy (Allergiya uchun)",       "unit": "ME/ml",   "min": 0,    "max": 2500,   "fmt": "decimal"},
        "118": {"name": "Insulin IFA",                        "unit": "mkED/ml", "min": 0,    "max": 300,    "fmt": "decimal"},
        "113": {"name": "Estradiol IFA",                      "unit": "nmol/l",   "min": 0,    "max": 100,     "fmt": "decimal"},   # bazadagi norma nmol/l da (0.029-80)
        "105": {"name": "Ferritin",                           "unit": "ng/ml",   "min": 0,    "max": 1500,   "fmt": "decimal"},
        "111": {"name": "FSG (FSH) IFA",                      "unit": "ME/l",  "min": 0,    "max": 200,    "fmt": "decimal"},
        "90":  {"name": "Helicobakter pylori IgG IFA",        "unit": "KP",      "min": 0,    "max": 15,     "fmt": "decimal"},
        "119": {"name": "Kortizol IFA",                       "unit": "nmol/l",  "min": 10,    "max": 1750,   "fmt": "decimal"},
        "110": {"name": "LG (LH) IFA",                        "unit": "ME/l",  "min": 0,    "max": 200,    "fmt": "decimal"},
        "100": {"name": "Lyambliya-antitela IFA",             "unit": "KP",      "min": 0,    "max": 15,     "fmt": "decimal"},
        "67":  {"name": "Pepsinogen I (PGI) IFA",             "unit": "ng/ml",   "min": 0,    "max": 500,    "fmt": "decimal"},
        "68":  {"name": "Pepsinogen II (PGII) IFA",           "unit": "ng/ml",   "min": 0,    "max": 200,    "fmt": "decimal"},
        "114": {"name": "Progesteron IFA",                    "unit": "nmol/l",  "min": 0,    "max": 640,    "fmt": "decimal"},
        "112": {"name": "Prolaktin IFA",                      "unit": "mME/l",  "min": 10,    "max": 10000,  "fmt": "decimal"},   # IFA da butundan keyin 3 xona yoziladi
        "108": {"name": "T3 erkin IFA",                       "unit": "pmol/l",  "min": 0,    "max": 30,     "fmt": "decimal"},
        "107": {"name": "T4 erkin IFA",                       "unit": "pmol/l",  "min": 0,    "max": 100,    "fmt": "decimal"},
        "116": {"name": "Testesteron Erkin IFA",              "unit": "pg/ml",   "min": 0,    "max": 50,     "fmt": "decimal"},
        "115": {"name": "Testesteron IFA",                    "unit": "nmol/l",  "min": 0,    "max": 52,     "fmt": "decimal"},
        "106": {"name": "TTG (TSH) IFA",                      "unit": "mME/l",   "min": 0,    "max": 100,    "fmt": "decimal"},
        "117": {"name": "Umumiy PSA IFA",                     "unit": "ng/ml",   "min": 0,    "max": 100,    "fmt": "decimal"},
        "104": {"name": "Vitamin B12",                        "unit": "pg/ml",   "min": 50,    "max": 2000,   "fmt": "decimal"},   # IFA da butundan keyin 3 xona yoziladi
        "103": {"name": "Vitamin D (25-OH)",                  "unit": "ng/ml",   "min": 0,    "max": 150,    "fmt": "decimal"},
        "120": {"name": "XGCh (Homiladorlik gormoni) IFA",    "unit": "mME/ml",  "min": 0,    "max": 225000, "fmt": "decimal"},   # IFA da butundan keyin 3 xona yoziladi
        "66":  {"name": "Troponin T",                         "unit": "ng/ml",   "min": 0,    "max": 50,     "fmt": "decimal"},
    },

    # ── KO'P KOMPONENTLI TAHLILLAR ────────────────────────────────────────
    # Kalit = "{tahlil_id}.{komponent_kaliti}"
    "multi": {
        # --- 27: Qonning umumiy tahlili (CBC) — BC-20S ---
        "27.WBC": {"name": "Leykotsitlar (WBC)",  "unit": "10^9/l",  "min": 0.1, "max": 100,  "fmt": "decimal"},
        "27.RBC": {"name": "Eritrotsitlar (RBC)", "unit": "10^12/l", "min": 0.5, "max": 10,   "fmt": "decimal"},
        "27.HGB": {"name": "Gemoglobin (HGB)",    "unit": "g/l",     "min": 20,  "max": 250,  "fmt": "int"},
        "27.PLT": {"name": "Trombotsitlar (PLT)", "unit": "10^9/l",  "min": 5,   "max": 2000, "fmt": "int"},

        # --- 55: Bilirubin ---
        "55.umumiy":     {"name": "Umumiy bilirubin",     "unit": "mkmol/l", "min": 0, "max": 400, "fmt": "decimal"},
        "55.bog_langan": {"name": "Bog'langan bilirubin", "unit": "mkmol/l", "min": 0, "max": 200, "fmt": "decimal"},
        "55.erkin":      {"name": "Erkin bilirubin",      "unit": "mkmol/l", "min": 0, "max": 400, "fmt": "decimal"},

        # --- 58: REVMOPROBA to'liq (avtomat) ---
        # Alohida RF/CRP/ASLO avtomat testlari (59/60/61) bilan UMUMIY chegara.
        "58.rf":   {"ref": "rf_avtomat",   "name": "RF avtomat"},
        "58.crp":  {"ref": "crp_avtomat",  "name": "CRP avtomat"},
        "58.aslo": {"ref": "aslo_avtomat", "name": "ASLO avtomat"},

        # --- 62: REVMOPROBA to'liq (qo'lda) ---
        # Dastur bu tahlilda tayyor variantlar (Manfiy/Musbat) Combobox ini ko'rsatadi,
        # shuning uchun raqamli tekshiruv o'chirilgan. Agar kelajakda raqam kiritiladigan
        # bo'lsa — fmt ni "decimal" ga o'zgartiring (chegaralar allaqachon yozilgan).
        "62.rf":   {"name": "RF qo'lda",   "unit": "ME/ml", "min": 0, "max": 200, "fmt": "any"},
        "62.crp":  {"name": "CRP qo'lda",  "unit": "mg/l",  "min": 0, "max": 96,  "fmt": "any"},
        "62.aslo": {"name": "ASLO qo'lda", "unit": "ME/ml", "min": 0, "max": 800, "fmt": "any"},

        # --- 73: KOAGULOGRAMMA to'liq ---
        # Alohida ACHTV/Fibrinogen/TT/PT testlari (76/75/77/74) bilan UMUMIY chegara.
        "73.pt_sek":     {"ref": "pt_sek"},
        "73.pt_kviku":   {"ref": "pt_kviku"},
        "73.pt_mno":     {"ref": "pt_mno"},
        "73.tt":         {"ref": "tt"},
        "73.achtv":      {"ref": "achtv"},
        "73.fibrinogen": {"ref": "fibrinogen"},

        # --- 74: Protrombin Time alohida test (3 sub-qiymat) ---
        "74.pt_sek":   {"ref": "pt_sek"},
        "74.pt_kviku": {"ref": "pt_kviku"},
        "74.pt_mno":   {"ref": "pt_mno"},

        # --- 126: LIPID SPEKTRI ---
        # Alohida TC/HDL/LDL/TG testlari (43/124/123/44) bilan UMUMIY chegara.
        "126.tc":   {"ref": "xolesterin_tc"},
        "126.hdl":  {"ref": "hdl"},
        "126.ldl":  {"ref": "ldl"},
        "126.tg":   {"ref": "trigliserid"},
        "126.vldl": {"name": "VLDL (avtomatik)",               "unit": "mmol/l", "min": 0,   "max": 5,    "fmt": "decimal"},
        "126.ka":   {"name": "Aterogenlik koeffitsienti (KA)", "unit": "",       "min": 0,   "max": 10,   "fmt": "decimal"},

        # --- 127: BUYRAK PANELI ---
        # Alohida Mochevina/Kreatinin/Siydik kislota/Albumin testlari
        # (42/41/50/35) bilan UMUMIY chegara.
        "127.mochevina":      {"ref": "mochevina"},
        "127.kreatinin":      {"ref": "kreatinin"},
        "127.siydik_kislota": {"ref": "siydik_kislota"},
        "127.albumin":        {"ref": "albumin"},
        "127.bun":            {"name": "Mochevina azoti (BUN)",    "unit": "mmol/l",  "min": 0.2, "max": 25,   "fmt": "decimal"},
        # GFR CKD-EPI formulasi bo'yicha AVTOMATIK hisoblanadi va bir kasr
        # xonasigacha yaxlitlanadi (round(gfr, 1) — masalan 98.9), shuning
        # uchun "int" EMAS, "decimal" bo'lishi shart.
        "127.gfr":            {"name": "GFR (avtomatik)",          "unit": "ml/min",  "min": 0,   "max": 200,  "fmt": "decimal"},

        # --- 33: Siydikning Nicheporenko tahlili ---
        "33.leykot":      {"name": "Leykotsitlar", "unit": "1/ml", "min": 0, "max": 100000000, "fmt": "int"},
        "33.eritr":       {"name": "Eritrotsitlar", "unit": "1/ml", "min": 0, "max": 100000000, "fmt": "int"},
        "33.silindirlar": {"name": "Silindrlar",   "unit": "1/ml", "min": 0, "max": 10000000,  "fmt": "int"},

        # --- 34: Siydikning Zimnitskiy tahlili ---
        # miqdori_1..miqdori_8 va solishtirma_1..solishtirma_8 — pastdagi
        # _ZIMNITSKIY_PREFIX qoidasi orqali avtomatik qo'llaniladi.
        "34.miqdori":         {"name": "Porsiya miqdori",       "unit": "ml", "min": 0,     "max": 600,   "fmt": "int"},
        "34.solishtirma":     {"name": "Solishtirma zichlik",   "unit": "",   "min": 1.000, "max": 1.040, "fmt": "decimal", "alt_divisor": 1000},   # "1.020" ham, "1020" ham qabul qilinadi
        "34.kunduzgi_diurez": {"name": "Kunduzgi diurez",       "unit": "ml", "min": 0,     "max": 3000,  "fmt": "int"},
        "34.tungi_diurez":    {"name": "Tungi diurez",          "unit": "ml", "min": 0,     "max": 2000,  "fmt": "int"},
        "34.jami_diurez":     {"name": "Jami diurez",           "unit": "ml", "min": 0,     "max": 4000,  "fmt": "int"},

        # --- 96: Spermogramma — o'zi show_spermogramma_form dialogida ---
        # "Me'yor" ustunidagi qiymatlardan olingan; laborant ODDIY sondir
        # (masalan "55") yoki diapazon ("2-5") kiritishi mumkin — ikkalasi ham
        # count_range fmt bilan qabul qilinadi.
        "96.saqlanish":     {"name": "Saqlanish vaqti",              "unit": "sutka",       "min": 0, "max": 10,   "fmt": "count_range"},
        "96.xajmi":         {"name": "Xajmi",                        "unit": "ml",          "min": 0, "max": 15,   "fmt": "count_range"},
        "96.suyulish":      {"name": "Suyulish vaqti",               "unit": "daq",         "min": 0, "max": 120,  "fmt": "count_range"},
        "96.rn":            {"name": "rN (pH)",                      "unit": "",            "min": 4, "max": 10,   "fmt": "count_range"},
        "96.ilashuv":       {"name": "Ilashuvchanlik",                "unit": "mm",          "min": 0, "max": 100,  "fmt": "count_range"},
        "96.sperma_1ml":    {"name": "Spermatozoidlar 1 mlda",       "unit": "mln",         "min": 0, "max": 1000, "fmt": "count_range"},
        "96.harakat_faol":  {"name": "Harakati — faol",              "unit": "%",           "min": 0, "max": 100,  "fmt": "count_range"},
        "96.harakat_sust":  {"name": "Harakati — sust",              "unit": "%",           "min": 0, "max": 100,  "fmt": "count_range"},
        "96.patologik":     {"name": "Patologik shakllar",           "unit": "%",           "min": 0, "max": 100,  "fmt": "count_range"},
        "96.epitel":        {"name": "Spermatogen epiteliy",         "unit": "k.d.",        "min": 0, "max": 100,  "fmt": "count_range"},
        "96.leykot":        {"name": "Leykotsitlar",                 "unit": "k.d.",        "min": 0, "max": 200,  "fmt": "count_range"},
        "96.fruktoza":      {"name": "Fruktoza",                     "unit": "mkmol/eyak.", "min": 0, "max": 50,   "fmt": "count_range"},
        "96.limon":         {"name": "Limon kislotasi",              "unit": "mkmol/eyak.", "min": 0, "max": 1000, "fmt": "count_range"},
        # sperma_umumiy / harakat_xar / tirik — avtomatik hisoblanadi (readonly), config kerak emas

        # --- 94: Ginekologik surtma — faqat ozod matn maydonlari (leykot/yassi) ---
        # Qolgan hamma ustun (shilliq/gonok/trixom/atipik/lakto/candida/anaerob)
        # OptionMenu dropdown — erkin matn kiritish IMKONSIZ, chegara shart emas.
        "94.leykot_v": {"name": "Leykotsitlar (Qin)",            "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "94.leykot_c": {"name": "Leykotsitlar (Bachadon bo'yni)", "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "94.leykot_u": {"name": "Leykotsitlar (Siydik yo'li)",   "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "94.yassi_v":  {"name": "Yassi epiteliy (Qin)",            "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "94.yassi_c":  {"name": "Yassi epiteliy (Bachadon bo'yni)", "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "94.yassi_u":  {"name": "Yassi epiteliy (Siydik yo'li)",   "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},

        # --- 97: Urologik surtma (Mujskoy mazok) — faqat erkin matn maydonlari ---
        # Qolgani (shilliq/gonok/gramm_*/trixom/xlamid/ureaplaz/zamburuglar/kokklar)
        # OptionMenu dropdown.
        "97.leykot": {"name": "Leykotsitlar", "unit": "k.d.", "min": 0, "max": 200, "fmt": "count_range"},
        "97.eritr":  {"name": "Eritrotsitlar", "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},
        "97.epitel": {"name": "Epiteliy",      "unit": "k.d.", "min": 0, "max": 100, "fmt": "count_range"},

        # --- 102: Najas tahlili — faqat erkin matn maydonlari ---
        # Qolgani (konsistensiya/shakli/rangi/reaksiya/kletchatka/kraxmal/
        # yodofil/shilliq_*/neytral_yog/eritr/zamburuglar/protozoa/gijja)
        # OptionMenu dropdown.
        "102.sutkalik_miqdori": {"name": "Sutkalik miqdori", "unit": "g", "min": 0, "max": 1000, "fmt": "count_range"},
        "102.namuna_miqdori":   {"name": "Namuna miqdori",   "unit": "",  "min": 0, "max": 100,  "fmt": "count_range"},
        "102.leykot":           {"name": "Leykotsitlar",     "unit": "k.d.", "min": 0, "max": 50, "fmt": "count_range"},

        # --- 87: Brutselyoz — titr maydonlari (natija ustuni OptionMenu) ---
        "87.xeddelson_titr": {"name": "Xeddelson titri", "unit": "", "fmt": "titer"},
        "87.rayta_titr":     {"name": "Rayta titri",     "unit": "", "fmt": "titer"},
    },

    # ── SIFAT (musbat/manfiy) TAHLILLARI ──────────────────────────────────
    # Kalit = tahlillar.id, qiymat = ruxsat etilgan javoblar ro'yxati.
    #
    # ⚠ DIQQAT: bu ro'yxat faqat ZAXIRA (baza ochilmaganda ishlatiladi).
    # ASOSIY manba — `tahlillar_norma.response_options` ustuni, ya'ni
    # "Tahlil Qo'shish" oynasidagi "Javob variantlari" maydoni. Natija
    # kiritish oynasi dropdown'ni o'sha ustundan quradi, shuning uchun
    # tekshiruv ham o'shandan o'qiydi (qarang: apply_db_response_options).
    # Shu sababli variantni o'zgartirish uchun SHU FAYLGA TEGISH SHART EMAS —
    # "Tahlil Qo'shish" oynasidan yozing, tekshiruv avtomatik moslashadi.
    #
    # Tekshiruv YUMSHOQ: javob ro'yxatdagi so'zlardan birini o'z ichiga olsa —
    # to'g'ri deb hisoblanadi (masalan "Musbat (+)" ham o'tadi). Umuman
    # tanilgan sifat javobi bo'lsa ham (aniqlandi/aniqlanmadi/manfiy...) xato
    # berilmaydi — faqat mutlaqo begona matn/raqam ushlanadi.
    "options": {
        "81":  ["Manfiy", "Musbat"],
        "83":  ["Manfiy", "Musbat"],
        "89":  ["Manfiy", "Musbat"],
        "91":  ["Manfiy", "Musbat"],
        "121": ["Manfiy", "Musbat"],
        "71":  ["Manfiy", "Musbat"],
        "80":  ["Demodikoz aniqlanmadi", "Demodikoz aniqlandi"],
        "79":  ["Aniqlanmadi", "Qo'tir kanasi aniqlandi", "Qo'tir kanasi axlati topildi"],
        "78":  ["Zamburug' aniqlanmadi", "Zamburug' aniqlandi"],
    },

    # ── MANTIQIY NISBAT QOIDALARI (ko'p komponentli) ──────────────────────
    "rules": {
        # Bog'langan bilirubin >= Umumiy bilirubin -> mumkin emas
        "bilirubin_direct_ge_total": True,
        # Zimnitskiy: kunduzgi + tungi != jami (shu ml dan ortiq farq bo'lsa)
        "zimnitskiy_diurez_tolerance": 1,
        # Lipid: LDL + HDL + VLDL umumiy xolesterindan shu ulushdan ko'p oshsa
        "lipid_sum_tolerance": 1.15,
        # Butundan keyin ruxsat etilgan maksimal kasr xonasi (null = tekshirilmaydi)
        "max_decimals": 3,
    },
}

# Butundan keyin ruxsat etilgan MAKSIMAL kasr xonasi soni.
# 2.817 / 2.87 / 2.9 — hammasi qonuniy; 2.8176566 — xatolik ehtimoli.
# Alohida tahlilga boshqacha qilish uchun spec ga "max_decimals": N yozing,
# butunlay o'chirish uchun "max_decimals": null.
MAX_DECIMALS = 3

# Zimnitskiy raqamlangan kalitlari (miqdori_1 ... solishtirma_8) uchun prefiks moslashuvi
_ZIMNITSKIY_PREFIX = ("miqdori", "solishtirma")

# Raqam o'rniga kelishi mumkin bo'lgan qonuniy sifat javoblari — bularga
# format xatosi berilmaydi.
_QUALITATIVE_OK = (
    "manfiy", "musbat", "salbiy", "topilmadi", "topildi", "aniqlanmadi",
    "aniqlandi", "aniqlanlandi", "shubhali", "kuzatilmadi", "kuzatildi",
    "yo'q", "yoq", "bor", "norma", "neg", "poz", "otr",
    "отриц", "полож", "не обнаруж", "обнаруж",
)

# JSON natija ichidagi XIZMAT kalitlari — bular natija emas, meta-ma'lumot.
# Analizatordan kelgan natija shunday saqlanadi:
#   {"result": "19.85", "unit": "mmol/l", "flag": "H", "lis_code": "...",
#    "analyzer_ref": "...", "sid": "...", "source": "BK-280"}
# Xizmat kalitlari olib tashlanganda faqat "result" qolsa — bu ODDIY (bitta
# qiymatli) natija. Boshqa kalitlar ham qolsa — ko'p komponentli natija.
_META_JSON_KEYS = {
    "type", "source", "sid", "sno", "unit", "flag", "lis_code", "analyzer_ref",
    "patient_age", "patient_gender", "abnormal_params", "all_analytes",
    "vazn_kg",          # BUYRAK PANELI: bemor vazni — kirish parametri, natija emas
}


def _split_json_result(data):
    """
    JSON natijani ajratadi.
    Qaytaradi: ("scalar", qiymat) | ("multi", {kalit: qiymat}) | ("skip", None)
    """
    if str(data.get("type", "")).lower() == "urine":
        return "skip", None
    comps = {k: v for k, v in data.items() if k not in _META_JSON_KEYS}
    others = [k for k in comps if k != "result"]
    if not others:
        return "scalar", comps.get("result")
    comps.pop("result", None)   # haqiqiy komponentlar bor — "result" ortiqcha
    return "multi", comps


_CFG_CACHE = [None]


# ══════════════════════════════════════════════════════════════════════════
#  Config yuklash
# ══════════════════════════════════════════════════════════════════════════
def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(force=False):
    """
    result_limits.json ni o'qish (bo'lmasa standartni yozib qo'yadi).

    Struktura versiyasi o'zgargan bo'lsa (masalan "analytes" qo'shilgan v2),
    eski fayl `result_limits.json.bak` ga nusxalanadi va yangi struktura
    bilan qayta yoziladi — aks holda eski fayldagi aniq qiymatlar yangi
    "ref" havolalari ustidan yozilib, ikki joyda farq qaytib kelardi.
    """
    if _CFG_CACHE[0] is not None and not force:
        return _CFG_CACHE[0]
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # chuqur nusxa
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if int(loaded.get("version", 1)) < int(DEFAULT_CONFIG["version"]):
                # Eski struktura — zaxira olib, yangisi bilan almashtiramiz
                bak = _CONFIG_PATH + ".bak"
                try:
                    with open(bak, "w", encoding="utf-8") as f:
                        json.dump(loaded, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
                print(f"[YANGILANDI] result_limits.json yangi strukturaga o'tkazildi "
                      f"(v{loaded.get('version', 1)} -> v{DEFAULT_CONFIG['version']}). "
                      f"Eski nusxa: {os.path.basename(bak)}")
            else:
                cfg = _deep_merge(cfg, loaded)
        else:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[OGOHLANTIRISH] result_limits.json yuklashda xato: {e}")
    _CFG_CACHE[0] = cfg
    # Kasr xonasi chegarasini konfigdan olish (check_format global konstantani
    # o'qiydi — spec da alohida "max_decimals" bo'lsa u ustunroq)
    global MAX_DECIMALS
    try:
        _md = cfg.get("rules", {}).get("max_decimals", MAX_DECIMALS)
        MAX_DECIMALS = None if _md is None else int(_md)
    except Exception:
        pass
    check_config_consistency(cfg)
    return cfg


def _resolve(spec, cfg):
    """
    {"ref": "kreatinin"} havolasini "analytes" dagi to'liq spec ga aylantiradi.
    Spec ichida aniq yozilgan maydonlar ref ustidan yoziladi (name ni
    o'zgartirish uchun qulay).
    """
    if not spec:
        return spec
    ref = spec.get("ref")
    if not ref:
        return spec
    base = (cfg or {}).get("analytes", {}).get(ref)
    if not base:
        print(f"[OGOHLANTIRISH] result_limits.json: '{ref}' analyte topilmadi")
        return {k: v for k, v in spec.items() if k != "ref"}
    out = dict(base)
    for k, v in spec.items():
        if k != "ref":
            out[k] = v
    return out


def check_config_consistency(cfg=None):
    """
    Bir xil moddaning ikki joyda TURLICHA chegara bilan yozilib qolganini
    topadi (masalan Kreatinin alohida testda 20-2800, panelda 10-1800).

    Odatda bunday bo'lmaydi — umumiy moddalar "ref" orqali bog'langan.
    Lekin kimdir result_limits.json ni qo'lda tahrirlab, ref ustidan aniq
    qiymat yozsa — shu yerda ogohlantirish chiqadi.

    Qaytaradi: [(analyte_nomi, [(joy, min, max), ...]), ...]
    """
    cfg = cfg or _CFG_CACHE[0] or DEFAULT_CONFIG
    seen = {}   # analyte -> [(joy, min, max)]
    for section in ("single", "multi"):
        for key, spec in (cfg.get(section) or {}).items():
            ref = (spec or {}).get("ref")
            if not ref:
                continue
            r = _resolve(spec, cfg)
            seen.setdefault(ref, []).append((f"{section}[{key}]", r.get("min"), r.get("max")))

    drift = []
    for ref, places in seen.items():
        limits = {(p[1], p[2]) for p in places}
        if len(limits) > 1:
            drift.append((ref, places))
            print(f"[OGOHLANTIRISH] '{ref}' chegarasi bir xil emas:")
            for where, lo, hi in places:
                print(f"                {where}: {lo} - {hi}")
    return drift


# ══════════════════════════════════════════════════════════════════════════
#  Yordamchi
# ══════════════════════════════════════════════════════════════════════════
def _norm_name(name):
    s = str(name or "").lower().strip()
    for ch in ("'", "‘", "’", "`", "ʻ"):
        s = s.replace(ch, "")
    return re.sub(r"\s+", " ", s)


# ══════════════════════════════════════════════════════════════════════════
#  DB DAN QO'LDA KIRITILGAN CHEGARALAR ("O'lchash chegarasi" — Tahlil Qo'shish
#  oynasi, 2026-08-11 qo'shildi). Bular STATIK config (yuqoridagi
#  DEFAULT_CONFIG) dan USTUVOR — laborant UI orqali kiritgan qiymat har doim
#  g'olib chiqadi, chunki u eng yangi va tahlilga xos.
#
#  Faqat BIR KOMPONENTLI tahlillarga tegishli (multi-component sub-testlar
#  o'zining "Fraksiyalar Normasi" panelidan boshqariladi, bu yerga aralashmaydi).
#
#  Manba: monoblok_dastur.py `tahlillar_norma.olchash_min/max` ustunlaridan
#  o'qib shu funksiyaga uzatadi (validate_many() chaqirilishidan oldin).
# ══════════════════════════════════════════════════════════════════════════
def apply_db_overrides(cfg, rows):
    """
    rows: [(tahlil_nomi, olchash_min, olchash_max, birlik), ...]
    Ikkalasi ham None bo'lgan qator o'tkazib yuboriladi (hali sozlanmagan).
    cfg ni JOYIDA o'zgartiradi va qulaylik uchun qaytaradi ham.
    """
    db_map = {}
    for row in rows or []:
        nomi = row[0] if len(row) > 0 else None
        mn = row[1] if len(row) > 1 else None
        mx = row[2] if len(row) > 2 else None
        unit = row[3] if len(row) > 3 else ""
        if mn is None and mx is None:
            continue
        nm = _norm_name(nomi)
        if not nm:
            continue
        # Format STATIK config dan olinadi (agar u yerda maxsus fmt bo'lsa).
        # Masalan QIB natijasi diapazon ("2.20-3.00") — DB dan chegara
        # qo'yilgani uchun u "decimal" ga aylanib, xato bermasligi kerak.
        _fmt = "decimal"
        _static = _name_index(cfg.get("single", {}), cfg).get(nm)
        if _static and _static[1].get("fmt"):
            _fmt = _static[1]["fmt"]
        db_map[nm] = {
            "name": nomi,
            "unit": unit or "",
            "min": float(mn) if mn is not None else None,
            "max": float(mx) if mx is not None else None,
            "fmt": _fmt,
        }
    cfg["_db_by_name"] = db_map
    return cfg


def apply_db_response_options(cfg, rows):
    """
    `tahlillar_norma.response_options` ("Javob variantlari" maydoni) ni
    tekshiruvga ulaydi. Natija kiritish oynasidagi dropdown ham SHU ustundan
    quriladi — demak laborant tanlagan har qanday javob avtomatik "to'g'ri"
    bo'ladi va DEFAULT_CONFIG["options"] bilan so'z farqi (masalan
    "Zamburug' aniqlandi" ↔ "Topildi") yolg'on ogohlantirish bermaydi.

    rows: [(tahlil_nomi, "Variant1, Variant2, ..."), ...]
    cfg ni JOYIDA o'zgartiradi va qulaylik uchun qaytaradi ham.
    """
    opt_map = {}
    for row in rows or []:
        nomi = row[0] if len(row) > 0 else None
        raw = row[1] if len(row) > 1 else None
        nm = _norm_name(nomi)
        if not nm or not raw:
            continue
        opts = [o.strip() for o in str(raw).split(",") if o.strip()]
        if opts:
            opt_map[nm] = opts
    cfg["_db_options_by_name"] = opt_map
    return cfg


def _name_index(section, cfg):
    """{normalizatsiyalangan nom: (kalit, resolved_spec)} indeksini quradi."""
    idx = {}
    for key, spec in section.items():
        r = _resolve(spec, cfg)
        nm = _norm_name(r.get("name", ""))
        if nm and nm not in idx:
            idx[nm] = (key, r)
    return idx


def _lookup_single(cfg, tahlil_id, test_name):
    """Bir komponentli tahlil uchun spec topish: avval DB (qo'lda kiritilgan
    override), keyin ID, keyin nom bo'yicha statik config."""
    nm0 = _norm_name(test_name)
    db_hit = (cfg.get("_db_by_name") or {}).get(nm0)
    if db_hit:
        return db_hit
    single = cfg.get("single", {})
    if tahlil_id is not None:
        spec = single.get(str(tahlil_id))
        if spec:
            return _resolve(spec, cfg)
    nm = _norm_name(test_name)
    if nm:
        hit = _name_index(single, cfg).get(nm)
        if hit:
            return hit[1]
    return None


def _lookup_multi(cfg, tahlil_id, test_name, comp_key):
    """Ko'p komponentli tahlil komponenti uchun spec topish."""
    multi = cfg.get("multi", {})
    ck = str(comp_key)

    # Zimnitskiy: miqdori_3 -> miqdori, solishtirma_7 -> solishtirma
    base_ck = ck
    for pref in _ZIMNITSKIY_PREFIX:
        if ck.startswith(pref + "_"):
            base_ck = pref
            break

    if tahlil_id is not None:
        for k in (f"{tahlil_id}.{ck}", f"{tahlil_id}.{base_ck}"):
            if k in multi:
                return _resolve(multi[k], cfg)

    # ID topilmasa — tahlil nomi bo'yicha shu tahlilning boshqa kalitlarini qidiramiz
    nm = _norm_name(test_name)
    if not nm:
        return None
    for k, spec in multi.items():
        if "." not in k:
            continue
        tid_part, key_part = k.split(".", 1)
        if key_part not in (ck, base_ck):
            continue
        # Shu tahlil_id ga tegishli single yozuvi nomi mos kelsa
        owner = cfg.get("single", {}).get(tid_part)
        if owner and _norm_name(_resolve(owner, cfg).get("name", "")) == nm:
            return _resolve(spec, cfg)
    return None


def _lookup_options(cfg, tahlil_id, test_name):
    """Ruxsat etilgan javoblar: avval BAZA ("Javob variantlari" maydoni),
    keyin zaxira statik ro'yxat."""
    db_opts = (cfg.get("_db_options_by_name") or {}).get(_norm_name(test_name))
    if db_opts:
        return db_opts
    opts = cfg.get("options", {})
    if tahlil_id is not None and str(tahlil_id) in opts:
        return opts[str(tahlil_id)]
    return None


def _is_qualitative_text(s):
    low = _norm_name(s)
    return any(w in low for w in _QUALITATIVE_OK)


# ══════════════════════════════════════════════════════════════════════════
#  "N" yoki "N-M" (sanoq/diapazon) maydonlari — Spermogramma, Ginekologik
#  surtma, Mujskoy mazok, Najas kabi dialoglarda "2-5", "30-40", "1-8 k.d."
#  ko'rinishidagi qiymatlar kiritiladi. Bu yerda chiziqcha ODATIY holat
#  (diapazon belgisi) — check_format dagi "X2 o'rtasida chiziqcha" qoidasi
#  bunga NOMOS, shuning uchun alohida funksiya.
# ══════════════════════════════════════════════════════════════════════════
def check_count_range(raw, spec, label):
    issues = []
    s = str(raw if raw is not None else "").strip()
    if not s:
        return issues, None

    if s.count("-") > 1:
        issues.append((label, raw, "bir nechta chiziqcha bor — 'son' yoki 'son-son' shaklida bo'lishi kerak"))
        return issues, None
    if re.search(r"[.,]{2,}", s):
        issues.append((label, raw, "ketma-ket ikkita nuqta/vergul bor"))
        return issues, None

    # Faqat "son" yoki "son-son" — birlik (k.d., mln, %...) alohida ustunda
    # ko'rsatiladi, shuning uchun qiymat maydonida ortiqcha belgi/harf bo'lishi
    # shart emas (masalan "4a" — chalkash, xato deb hisoblanadi).
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(?:-\s*(\d+(?:[.,]\d+)?))?", s)
    if not m:
        issues.append((label, raw,
                       "kutilgan format: son yoki son-son (masalan '2-5'); "
                       "harf yoki ortiqcha belgi bo'lmasligi kerak"))
        return issues, None

    n1 = float(m.group(1).replace(",", "."))
    n2 = float(m.group(2).replace(",", ".")) if m.group(2) else None

    if n2 is not None and n1 > n2:
        issues.append((label, raw,
                       f"chegaralar teskari yozilgan: {n1:g}-{n2:g} (birinchisi ikkinchisidan katta)"))

    lo, hi = spec.get("min"), spec.get("max")
    unit = spec.get("unit") or ""
    u = f" {unit}" if unit else ""
    for n in (n1, n2):
        if n is None:
            continue
        if lo is not None and n < lo:
            issues.append((label, raw, f"o'lchash chegarasidan PAST: {n:g}{u} < {lo:g}{u}"))
        elif hi is not None and n > hi:
            issues.append((label, raw, f"o'lchash chegarasidan BALAND: {n:g}{u} > {hi:g}{u}"))

    return issues, None  # chegara tekshiruvi shu yerda tugadi, tashqarida takrorlanmasin


# ══════════════════════════════════════════════════════════════════════════
#  Titr maydonlari ("1:80", "<1:40") — Brutselyoz (Xeddelson/Rayta)
# ══════════════════════════════════════════════════════════════════════════
def check_titer(raw, spec, label):
    issues = []
    s = str(raw if raw is not None else "").strip()
    if not s:
        return issues, None

    # Titr UMUMAN chiqmagan holat. Laboratoriyada bu "0" yoki "0:0" deb ham
    # yoziladi (shuningdek chiziqcha yoki "Manfiy"), — bu XATO EMAS, balki
    # reaksiya hech bir suyultirishda kuzatilmaganini bildiradi.
    s_norm = re.sub(r"\s+", "", s)
    if s_norm in ("0", "0:0", "0:00", "00", "-", "--", "—", "–", "0.0"):
        return issues, None
    if _is_qualitative_text(s):
        return issues, None

    # Titrdan keyin izoh yozilishi mumkin ("1:50  qayta topshirish") —
    # bu laboratoriya amaliyotida odatiy, xato emas.
    m = re.match(r"^[<>]?\s*1\s*:\s*(\d+)\s*(?:[^\d].*)?$", s)
    if not m:
        issues.append((label, raw,
                       "kutilgan format: '1:NN', '<1:NN' (masalan '1:80') "
                       "yoki titr chiqmaganda '0' / '0:0'"))
    return issues, None


# ══════════════════════════════════════════════════════════════════════════
#  FORMAT TEKSHIRUVI (X1-X11)
#  Qaytaradi: (issues, parsed_float_or_None)
# ══════════════════════════════════════════════════════════════════════════
def check_format(raw, spec, label):
    """
    raw   — foydalanuvchi kiritgan xom matn
    spec  — {"fmt": ..., "min": ..., "max": ..., "unit": ...}
    label — xabar matnida ko'rsatiladigan nom
    """
    issues = []
    fmt = (spec or {}).get("fmt", "decimal")
    if fmt == "any":
        return issues, None
    if fmt == "count_range":
        return check_count_range(raw, spec, label)
    if fmt == "titer":
        return check_titer(raw, spec, label)

    s = str(raw if raw is not None else "").strip()

    # X5 — bo'sh
    if not s:
        return issues, None  # bo'sh natija saqlanmaydi, bu yerda xato emas

    if fmt == "text":
        return issues, None

    # Qonuniy sifat javobi (Manfiy/Musbat/Topilmadi...) — raqamli tekshiruv o'tkazilmaydi
    if _is_qualitative_text(s):
        return issues, None

    # "<0.5" / ">1000" kabi qonuniy prefikslar
    prefix = ""
    if s[:1] in ("<", ">"):
        prefix, s = s[0], s[1:].strip()
        if not s:
            issues.append((label, raw, "faqat '%s' belgisi yozilgan, qiymat yo'q" % prefix))
            return issues, None

    # X6 — ichki probel/tab ("12 .5")
    if re.search(r"\s", s):
        issues.append((label, raw, "ichida ortiqcha probel bor (masalan '12 .5')"))
        s = re.sub(r"\s+", "", s)

    # X11 — qo'sh ajratkich ("..", ",,", ".,")
    if re.search(r"[.,]{2,}", s):
        issues.append((label, raw, "ketma-ket ikkita nuqta/vergul bor (tugma ikki marta bosilgan)"))

    # X1 / X10 — bittadan ortiq o'nlik ajratkich ("1.152.01", "2,37.5")
    n_sep = s.count(".") + s.count(",")
    if n_sep > 1:
        issues.append((label, raw, "bittadan ortiq o'nlik ajratkich (nuqta/vergul) bor"))

    # X2 — chiziqcha o'rtada ("2.37-1")
    if "-" in s[1:]:
        issues.append((label, raw, "o'rtasida chiziqcha bor (masalan '2.37-1')"))

    # Vergulni nuqtaga keltirib normalizatsiya
    norm = s.replace(",", ".")

    # X4 — raqam va nuqta/minusdan boshqa belgi
    if not re.fullmatch(r"-?\d*\.?\d*", norm) or norm in ("", "-", ".", "-."):
        if not any(i[2].startswith("bittadan ortiq") or i[2].startswith("ketma-ket")
                   or i[2].startswith("o'rtasida") for i in issues):
            issues.append((label, raw, "raqam emas — harf yoki noto'g'ri belgi bor"))
        return issues, None

    # X14 — butundan keyin 3 xonadan ortiq raqam ("2.8176566")
    #   Laboratoriya odatda 3 xonagacha yozadi (2.817 / 2.87 / 2.9 — hammasi
    #   qonuniy). 4 va undan ortiq xona — klaviatura yopishib qolgani belgisi.
    #   Chegara: cfg["rules"]["max_decimals"] yoki spec["max_decimals"].
    _maxdec = (spec or {}).get("max_decimals", MAX_DECIMALS)
    if _maxdec is not None and "." in norm:
        _dec = len(norm.split(".", 1)[1])
        if _dec > int(_maxdec):
            issues.append((label, raw,
                           "butundan keyin %d xonadan ortiq raqam yozilgan (%d ta) — "
                           "tugma yopishib qolgan bo'lishi mumkin" % (int(_maxdec), _dec)))

    # X3 — boshida ortiqcha nol ("00.976", "007")
    body = norm[1:] if norm.startswith("-") else norm
    if re.match(r"^0\d", body):
        issues.append((label, raw, "boshida ortiqcha nol bor (masalan '00.976')"))

    try:
        val = float(norm)
    except (ValueError, TypeError):
        issues.append((label, raw, "songa aylantirib bo'lmadi"))
        return issues, None

    # X8 — butun son kutilganda kasr kiritilgan
    if fmt == "int" and abs(val - round(val)) > 1e-9:
        issues.append((label, raw, "butun son bo'lishi kerak, kasr qism kiritilgan"))

    return issues, val


# ══════════════════════════════════════════════════════════════════════════
#  CHEGARA (LINEYNOST) TEKSHIRUVI (X12-X13)
# ══════════════════════════════════════════════════════════════════════════
def check_range(val, spec, label, raw):
    issues = []
    if val is None or not spec:
        return issues
    unit = spec.get("unit") or ""
    u = f" {unit}" if unit else ""
    lo = spec.get("min")
    hi = spec.get("max")

    # Ikki xil yozuv (siydik solishtirma zichligi "1.020" ham, "1020" ham
    # qonuniy) — spec da "alt_divisor" bo'lsa, katta yozuv ham qabul qilinadi
    _div = spec.get("alt_divisor")
    if _div and hi is not None and val > hi:
        try:
            _alt = val / float(_div)
            if (lo is None or _alt >= lo) and _alt <= hi:
                return issues
        except (TypeError, ZeroDivisionError):
            pass

    # X7 — kutilmagan manfiy son
    if val < 0 and (lo is None or lo >= 0):
        issues.append((label, raw, f"manfiy son ({val:g}{u}) — bu tahlilda bo'lishi mumkin emas"))
        return issues

    if lo is not None and val < lo:
        issues.append((label, raw,
                       f"o'lchash chegarasidan PAST: {val:g}{u} < {lo:g}{u} (lineynost min)"))
    elif hi is not None and val > hi:
        issues.append((label, raw,
                       f"o'lchash chegarasidan BALAND: {val:g}{u} > {hi:g}{u} (lineynost max)"))
    return issues


# ══════════════════════════════════════════════════════════════════════════
#  BITTA TAHLILNI TEKSHIRISH
# ══════════════════════════════════════════════════════════════════════════
def validate_result(tahlil_id, test_name, raw_value, cfg=None):
    """
    Bitta tahlil natijasini tekshiradi.

    tahlil_id  — tahlillar.id (katalog ID). None bo'lsa nom bo'yicha qidiriladi.
    test_name  — tahlil nomi
    raw_value  — self.test_results dagi qiymat: oddiy matn YOKI JSON matn

    Qaytaradi: [(nom, kiritilgan_qiymat, sabab), ...] — bo'sh ro'yxat = xato yo'q.
    """
    cfg = cfg or load_config()
    if not cfg.get("enabled", True):
        return []

    issues = []
    if raw_value is None:
        return issues

    sval = raw_value if isinstance(raw_value, str) else str(raw_value)
    sval_strip = sval.strip()
    if not sval_strip:
        return issues

    # ── JSON natija (ko'p komponentli yoki analizator) ────────────────────
    data = None
    if sval_strip.startswith("{"):
        try:
            data = json.loads(sval_strip)
        except Exception:
            data = None

    if isinstance(data, dict):
        kind, payload = _split_json_result(data)

        # Siydik — analizator boshqaradigan matnli natija, tekshirilmaydi
        if kind == "skip":
            return issues

        # Analizatordan kelgan oddiy natija: {"result": "19.85", "unit": ..., ...}
        if kind == "scalar":
            return _validate_single_value(cfg, tahlil_id, test_name, payload)

        # Haqiqiy ko'p komponentli natija (CBC, bilirubin, panellar...)
        numeric_vals = {}
        for ck, cv in payload.items():
            spec = _lookup_multi(cfg, tahlil_id, test_name, ck)
            if not spec:
                continue
            label = f"{test_name} — {spec.get('name', ck)}"
            f_iss, val = check_format(cv, spec, label)
            issues += f_iss
            issues += check_range(val, spec, label, cv)
            if val is not None:
                numeric_vals[ck] = val

        issues += _check_component_rules(cfg, test_name, numeric_vals)
        return issues

    # ── Oddiy matn natija ─────────────────────────────────────────────────
    return _validate_single_value(cfg, tahlil_id, test_name, sval_strip)


def _validate_single_value(cfg, tahlil_id, test_name, raw):
    issues = []
    if raw is None or str(raw).strip() == "":
        return issues

    # Sifat (musbat/manfiy) tahlili bo'lsa — ro'yxat bilan solishtirish
    opts = _lookup_options(cfg, tahlil_id, test_name)
    if opts:
        low = _norm_name(raw)
        if any(_norm_name(o) in low for o in opts):
            return issues
        # Ro'yxatdagi so'z bilan aynan mos kelmasa ham, javob TANILGAN sifat
        # javobi bo'lsa (aniqlandi / aniqlanmadi / manfiy / topildi ...) —
        # bu shunchaki boshqacha ifoda, xato emas. Masalan bazada
        # "Zamburug' aniqlanmadi" turib, eski natijada "Aniqlanmadi" yozilgan.
        if _is_qualitative_text(raw):
            return issues
        # Raqam kiritilgan va bu tahlil uchun raqamli chegara ham belgilangan
        # bo'lsa (masalan Troponin T — ham ekspress, ham miqdoriy) — raqamli
        # tekshiruvga o'tamiz, "ro'yxatda yo'q" deb xato bermaymiz.
        if re.match(r"^[<>]?\s*\d", str(raw).strip()) and _lookup_single(cfg, tahlil_id, test_name):
            pass
        else:
            issues.append((test_name, raw,
                           "javob ro'yxatda yo'q — kutilgan: " + " / ".join(opts)))
            return issues

    spec = _lookup_single(cfg, tahlil_id, test_name)
    if not spec:
        return issues  # bu tahlil uchun chegara belgilanmagan — tekshirmaymiz

    label = test_name
    f_iss, val = check_format(raw, spec, label)
    issues += f_iss
    issues += check_range(val, spec, label, raw)
    return issues


def _check_component_rules(cfg, test_name, vals):
    """Ko'p komponentli tahlillar uchun mantiqiy nisbat qoidalari (R1-R4)."""
    issues = []
    rules = cfg.get("rules", {})
    tn = _norm_name(test_name)

    # R1/R2 — Bilirubin: bog'langan >= umumiy bo'lishi mumkin emas
    if rules.get("bilirubin_direct_ge_total") and "bilirubin" in tn:
        tot = vals.get("umumiy")
        dir_ = vals.get("bog_langan")
        if tot is not None and dir_ is not None and dir_ >= tot > 0:
            issues.append((test_name, f"umumiy={tot:g}, bog'langan={dir_:g}",
                           "bog'langan bilirubin umumiydan katta yoki teng — bu mumkin emas"))

    # R4 — Zimnitskiy: kunduzgi + tungi = jami
    tol = rules.get("zimnitskiy_diurez_tolerance")
    if tol is not None and "zimnitskiy" in tn:
        k = vals.get("kunduzgi_diurez")
        t = vals.get("tungi_diurez")
        j = vals.get("jami_diurez")
        if None not in (k, t, j) and abs((k + t) - j) > tol:
            issues.append((test_name, f"kunduzgi={k:g} + tungi={t:g} != jami={j:g}",
                           "kunduzgi va tungi diurez yig'indisi jami diurezga teng emas"))

    # R3 — Lipid: LDL + HDL + VLDL umumiy xolesterindan ortiq
    lt = rules.get("lipid_sum_tolerance")
    if lt and "lipid" in tn:
        tc = vals.get("tc")
        parts = [vals.get("ldl"), vals.get("hdl"), vals.get("vldl")]
        if tc and all(p is not None for p in parts):
            s = sum(parts)
            if s > tc * lt:
                issues.append((test_name, f"LDL+HDL+VLDL={s:.2f}, TC={tc:.2f}",
                               "fraksiyalar yig'indisi umumiy xolesterindan sezilarli ko'p"))

    return issues


# ══════════════════════════════════════════════════════════════════════════
#  KO'P TAHLILNI BIRDANIGA TEKSHIRISH
# ══════════════════════════════════════════════════════════════════════════
def validate_many(rows, cfg=None):
    """
    rows: [(tahlil_id, test_name, raw_value), ...]
    Qaytaradi: [(nom, qiymat, sabab), ...]
    """
    cfg = cfg or load_config()
    out = []
    for tahlil_id, test_name, raw in rows:
        try:
            out += validate_result(tahlil_id, test_name, raw, cfg)
        except Exception as e:
            print(f"[OGOHLANTIRISH] Natija tekshirishda xato ({test_name}): {e}")
    return out


# ══════════════════════════════════════════════════════════════════════════
#  TASDIQLASH OYNASI
# ══════════════════════════════════════════════════════════════════════════
def format_issues(issues):
    lines = []
    for name, value, reason in issues:
        lines.append(f"• {name}\n    Kiritilgan: «{value}»\n    Sabab: {reason}")
    return "\n\n".join(lines)


def _play_sound(cfg):
    if not (cfg or {}).get("sound", True):
        return
    try:
        import critical_alert
        critical_alert.play_alert_sound()
        return
    except Exception:
        pass
    try:
        import winsound
        winsound.MessageBeep(-1)
    except Exception:
        pass


def confirm_save(parent, issues, cfg=None, title_extra=""):
    """
    Xatolik ehtimoli topilganda tasdiqlash oynasi.

    Qaytaradi:
      True  — laborant "Baribir saqlansin" ni tanladi (natija to'g'ri ekan)
      False — laborant "Tuzataman" ni tanladi (saqlash to'xtatiladi)

    Xato bo'lmasa — hech narsa ko'rsatmasdan darhol True qaytaradi.
    """
    cfg = cfg or load_config()
    if not cfg.get("enabled", True) or not issues:
        return True

    _play_sound(cfg)

    import tkinter as tk
    from tkinter import ttk

    result = {"ok": False}

    try:
        dlg = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    except Exception:
        # Tk yo'q bo'lsa (masalan konsol rejimi) — saqlashni to'xtatmaymiz
        print("[XATOLIK EHTIMOLI]\n" + format_issues(issues))
        return True

    dlg.title("⚠ NATIJADA XATOLIK EHTIMOLI" + (f" — {title_extra}" if title_extra else ""))
    dlg.configure(bg="#FFF4F4")
    try:
        dlg.transient(parent)
    except Exception:
        pass
    dlg.grab_set()
    dlg.resizable(True, True)

    n = len(issues)
    header = tk.Label(
        dlg,
        text=f"Quyidagi {n} ta natijada xatolik ehtimoli topildi",
        font=("Arial", 13, "bold"), bg="#C62828", fg="white",
        anchor="w", padx=14, pady=10
    )
    header.pack(fill=tk.X)

    sub = tk.Label(
        dlg,
        text="Natija noto'g'ri yozilgan bo'lishi mumkin (klaviatura xatosi yoki\n"
             "o'lchash chegarasidan chiqib ketgan). Iltimos, tekshirib chiqing.",
        font=("Arial", 10), bg="#FFF4F4", fg="#7F1D1D",
        anchor="w", justify=tk.LEFT, padx=14, pady=6
    )
    sub.pack(fill=tk.X, pady=(4, 0))

    # Ro'yxat (scrollable)
    body = tk.Frame(dlg, bg="#FFF4F4")
    body.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

    txt = tk.Text(body, wrap=tk.WORD, font=("Arial", 10), height=min(20, max(6, n * 4)),
                  bg="white", fg="#111111", relief=tk.SOLID, borderwidth=1)
    vsb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=vsb.set)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    txt.tag_configure("nm", font=("Arial", 10, "bold"), foreground="#B00020")
    txt.tag_configure("val", font=("Consolas", 11, "bold"), foreground="#0B3D91")
    txt.tag_configure("rs", font=("Arial", 10), foreground="#333333")

    for i, (name, value, reason) in enumerate(issues, start=1):
        txt.insert(tk.END, f"{i}. {name}\n", "nm")
        txt.insert(tk.END, "     Kiritilgan: ", "rs")
        txt.insert(tk.END, f"{value}\n", "val")
        txt.insert(tk.END, f"     Sabab: {reason}\n\n", "rs")
    txt.configure(state=tk.DISABLED)

    # Tugmalar
    btns = tk.Frame(dlg, bg="#FFF4F4")
    btns.pack(fill=tk.X, padx=12, pady=(4, 12))

    def do_fix():
        result["ok"] = False
        dlg.destroy()

    def do_force():
        result["ok"] = True
        dlg.destroy()

    fix_btn = tk.Button(btns, text="✎  Tuzataman (saqlanmasin)", command=do_fix,
                        font=("Arial", 11, "bold"), bg="#2E7D32", fg="white",
                        padx=16, pady=8, cursor="hand2", relief=tk.FLAT)
    fix_btn.pack(side=tk.LEFT)

    force_btn = tk.Button(btns, text="Natija to'g'ri — baribir saqlansin", command=do_force,
                          font=("Arial", 10), bg="#E0E0E0", fg="#333333",
                          padx=14, pady=8, cursor="hand2", relief=tk.FLAT)
    force_btn.pack(side=tk.RIGHT)

    dlg.bind("<Escape>", lambda e: do_fix())
    dlg.bind("<Return>", lambda e: do_fix())

    # Markazlashtirish
    dlg.update_idletasks()
    w = max(560, min(760, dlg.winfo_reqwidth()))
    h = max(320, min(640, dlg.winfo_reqheight()))
    try:
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        dlg.geometry(f"{w}x{h}+{max(0, px)}+{max(0, py)}")
    except Exception:
        dlg.geometry(f"{w}x{h}")

    fix_btn.focus_set()
    dlg.wait_window()
    return result["ok"]
