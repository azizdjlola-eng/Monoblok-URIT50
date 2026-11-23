# -*- coding: utf-8 -*-
"""Blankada bemorga mos norma qatori qalin chiqishi (2026-11-24, v1.0.75).

monoblok_dastur.py og'ir (GUI, baza) — kerakli funksiyalar fayldan ast bilan ajratib olinadi.
    python tests_norma_qalin_sinov.py
"""
import ast
import os
import re

YOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monoblok_dastur.py")
KERAK_FN = {"_parse_age_condition", "_age_condition_matches", "select_norma_by_patient",
            "_get_norma_bold_hints", "_norma_line_is_bold", "_select_norma_range_by_hints"}
KERAK_VAR = {"_AGE_UNIT_WORD", "_GENDER_WORD_RE", "_NORMA_QATOR_AJRATGICH", "_NORMA_JINS_SOZLARI", "_NORMA_JINS_RE"}

with open(YOL, encoding="utf-8") as f:
    daraxt = ast.parse(f.read())
bolaklar = []
for n in daraxt.body:
    if isinstance(n, ast.FunctionDef) and n.name in KERAK_FN:
        bolaklar.append(n)
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in KERAK_VAR for t in n.targets):
        bolaklar.append(n)
G = {"re": re}
exec(compile(ast.Module(body=bolaklar, type_ignores=[]), YOL, "exec"), G)

ok = xato = 0


def tek(nom, shart):
    global ok, xato
    if shart:
        ok += 1
    else:
        xato += 1
        print("XATO:", nom)


def qalin(norma, jins, yosh, **kw):
    hints = G["_get_norma_bold_hints"](norma, jins, yosh, **kw)
    qismlar = [p.strip() for p in re.split(G["_NORMA_QATOR_AJRATGICH"], norma) if p.strip()]
    return [p for p in qismlar if G["_norma_line_is_bold"](p, hints, jins)]


# 1) AT-TPO: 30 yoshli ayolda «>50 yosh Ayol» QALIN EMAS (asosiy shikoyat)
TPO_ESKI = "Erkak: 0.0-30.0, Ayol: 0.0-50.0, >50 yosh Ayol: 0.0-50.0"
tek("TPO 30 ayol — faqat Ayol", qalin(TPO_ESKI, "Ayol", 30) == ["Ayol: 0.0-50.0"])
tek("TPO 60 ayol — aniqrog'i", qalin(TPO_ESKI, "Ayol", 60) == [">50 yosh Ayol: 0.0-50.0"])
tek("TPO erkak", qalin(TPO_ESKI, "Erkak", 40) == ["Erkak: 0.0-30.0"])
tek("TPO 30 ayol — strelka oralig'i Ayol", G["_select_norma_range_by_hints"](
    TPO_ESKI, G["_get_norma_bold_hints"](TPO_ESKI, "Ayol", 30), "Ayol") == "0.0-50.0")

# 2) Testosteron — yosh+jins
TS = ("12-19 yosh Erkak: 1.0-38.0, 20-39 yosh Erkak: 8.6-29.0, 40-55 yosh Erkak: 6.9-21.0, "
      ">55 yosh Erkak: 5.9-18.1, <18 yosh Ayol: 0.2-2.5, >18 yosh Ayol: 0.0-4.6")
tek("TS ayol 30", qalin(TS, "Ayol", 30) == [">18 yosh Ayol: 0.0-4.6"])
tek("TS ayol 15", qalin(TS, "Ayol", 15) == ["<18 yosh Ayol: 0.2-2.5"])
tek("TS erkak 25", qalin(TS, "Erkak", 25) == ["20-39 yosh Erkak: 8.6-29.0"])
tek("TS erkak 60", qalin(TS, "Erkak", 60) == [">55 yosh Erkak: 5.9-18.1"])

# 3) Yangi yozuv (belgi oldin) — eski bilan BIR XIL qalin
IGE_E = "<1 yosh: 0.0-15.0, 1-6 yosh: 0.0-60.0, 6-10 yosh: 0.0-90.0, 10-16 yosh: 20.0-200.0, 16< yosh: 20.0-100.0"
IGE_Y = IGE_E.replace("16< yosh", ">16 yosh")
for y in (0, 3, 8, 12, 16, 17, 40):
    tek(f"IgE {y} yosh qalin bir xil",
        [p.replace("16< yosh", ">16 yosh") for p in qalin(IGE_E, "Ayol", y)] == qalin(IGE_Y, "Ayol", y))
    tek(f"IgE {y} yosh tanlov bir xil",
        G["select_norma_by_patient"](IGE_E, "Ayol", y) == G["select_norma_by_patient"](IGE_Y, "Ayol", y))
tek("IgE 40 — >16", qalin(IGE_Y, "Erkak", 40) == [">16 yosh: 20.0-100.0"])

# 4) PSA: 61 yoshli erkak — eski «61<» hech biriga tushmasdi, yangi «>60» tushadi
PSA_E = "0-40 yosh Erkak: 0.0-4.0, 41-60 yosh Erkak: 0.0-5.5, 61< yosh Erkak: 0.0-7.0, Ayol: 0.0-0.45"
PSA_Y = PSA_E.replace("61< yosh", ">60 yosh")
tek("PSA 61 eski — qalin yo'q", qalin(PSA_E, "Erkak", 61) == [])
tek("PSA 61 yangi", qalin(PSA_Y, "Erkak", 61) == [">60 yosh Erkak: 0.0-7.0"])
tek("PSA 70 yangi", qalin(PSA_Y, "Erkak", 70) == [">60 yosh Erkak: 0.0-7.0"])
tek("PSA 50", qalin(PSA_Y, "Erkak", 50) == ["41-60 yosh Erkak: 0.0-5.5"])
tek("PSA ayol", qalin(PSA_Y, "Ayol", 50) == ["Ayol: 0.0-0.45"])
tek("PSA 61 tanlov", G["select_norma_by_patient"](PSA_Y, "Erkak", 61) == "0.0-7.0")

# 5) Insulin: qandli diabet qatori hech qachon avtomatik qalin emas
INS = "<12 yosh: 0.0-10.0, >12 yosh: 2.0-24.9, Qandli diabetda (12 yoshdan katta): 25.0-100.0"
tek("Insulin 30", qalin(INS, "Ayol", 30) == [">12 yosh: 2.0-24.9"])
tek("Insulin 8", qalin(INS, "Erkak", 8) == ["<12 yosh: 0.0-10.0"])
tek("Insulin 30 tanlov", G["select_norma_by_patient"](INS, "Ayol", 30) == "2.0-24.9")

# 6) Yoshsiz qatorlar — avvalgidek
FAZA = "Erkak: 1.5-12.4, Follikulyar: 3.5-12.5, Ovulyatsiya: 4.7-21.5, Lyutein: 1.7-7.7, Menopauza: 25.8-134.8"
tek("Faza Follikulyar", qalin(FAZA, "Ayol", 30, cycle_note="5-kun") == ["Follikulyar: 3.5-12.5"])
tek("Menopauza", qalin(FAZA, "Ayol", 55, menopauza=1) == ["Menopauza: 25.8-134.8"])
tek("Jins oddiy", qalin("Erkak: 62-115, Ayol: 53-97", "Ayol", 30) == ["Ayol: 53-97"])
tek("Emizikli", "Emizikli yosh: 1-2" in qalin("Ayol: 0-1, Emizikli yosh: 1-2", "Ayol", 25, emizikli=1))
# Yosh noma'lum — yoshli qator qalin emas, jins qatori qalin
tek("Yosh yo'q", qalin(TPO_ESKI, "Ayol", None) == ["Ayol: 0.0-50.0"])

print(f"NATIJA: {ok} OK, {xato} XATO")
raise SystemExit(1 if xato else 0)
