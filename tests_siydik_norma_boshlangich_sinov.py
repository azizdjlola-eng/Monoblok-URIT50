# -*- coding: utf-8 -*-
"""Siydik qo'lda kiritish oynasi NORMA bilan to'ldirilib ochilishi (2026-11-24).

Hamshira faqat o'zgargan ko'rsatkichni tuzatadi; hammasi toza bo'lsa tegmasdan saqlaydi.
    python tests_siydik_norma_boshlangich_sinov.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import siydik_blanka as sb  # noqa: E402

ok = xato = 0


def tek(nom, shart):
    global ok, xato
    if shart:
        ok += 1
    else:
        xato += 1
        print("XATO:", nom)


S = sb._toza(None)          # standart sozlama (bazaga murojaatsiz)
N = sb.qolda_norma_qiymatlari(S)
Q = {q["kod"]: q for q in S["kimyoviy"]}

# 1) Egasi rasmidagi qatorlar — hammasi to'ldirilgan
kutilgan = {"LEU": "manfiy", "KET": "manfiy", "NIT": "manfiy", "URO": "normal",
            "BIL": "manfiy", "GLU": "manfiy", "PRO": "manfiy", "SG": "1.015",
            "PH": "6.0", "BLD": "manfiy", "Vc": "manfiy", "MA": "10", "Ca": "2.5", "CR": "8.8"}
for k, v in kutilgan.items():
    tek(f"{k} = {v} (bor: {N.get(k)!r})", N.get(k) == v)
tek("ACR qo'lda kiritilmaydi (hisoblanadi)", "ACR" not in N)
tek("qatorlar soni = qo'lda qatorlar", set(N) == {q["kod"] for q in sb.qolda_qatorlar(S)})

# 2) Hech biri blankada qizil (patologik) chiqmaydi
for k, v in N.items():
    tek(f"{k}={v} normada", not sb.patologikmi(Q[k], v))

# 3) MA/CR nisbati (ACR) — A1 norma (0-3.3)
acr = float(N["MA"]) / float(N["CR"])
tek(f"ACR {acr:.1f} A1 normada", acr <= 3.3)

# 4) Variantdagi qiymatlar ro'yxatda bor (Combobox'da tanlangan ko'rinadi)
for k in ("SG", "PH", "MA", "Ca", "CR", "LEU", "URO"):
    tek(f"{k} variantlar ichida", N[k] in Q[k]["variantlar"])

# 5) Mijoz normani o'zgartirsa — patologik qiymat qo'yilmaydi, normadagisi tanlanadi
S2 = copy.deepcopy(S)
for q in S2["kimyoviy"]:
    if q["kod"] == "PH":
        q["norma"] = "6.5-7.5"
N2 = sb.qolda_norma_qiymatlari(S2)
tek(f"pH norma 6.5-7.5 → {N2.get('PH')}", N2.get("PH") == "6.5")

# 6) Normasi va variantlari yo'q yangi qator — bo'sh qoladi
S3 = copy.deepcopy(S)
S3["kimyoviy"].append({"kod": "XYZ", "nom": "Yangi", "qisqa": "XYZ", "birlik": "", "norma": "",
                       "korsat": "auto", "variantlar": [], "kodlar": []})
tek("variantsiz qator bo'sh", "XYZ" not in sb.qolda_norma_qiymatlari(S3))
S3["kimyoviy"][-1]["variantlar"] = ["musbat", "manfiy"]
tek("variantlardan normadagisi (manfiy)", sb.qolda_norma_qiymatlari(S3).get("XYZ") == "manfiy")

# 7) Yashirin qator to'ldirilmaydi
S4 = copy.deepcopy(S)
for q in S4["kimyoviy"]:
    if q["kod"] == "Vc":
        q["korsat"] = "yashirin"
tek("yashirin Vc yo'q", "Vc" not in sb.qolda_norma_qiymatlari(S4))

# 8) Oyna kodi: faqat yangi kiritishda to'ldiradi, saqlangan qiymat ustun
YOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monoblok_dastur.py")
with open(YOL, encoding="utf-8") as f:
    kod = f.read()
tek("oyna norma bilan to'ldiradi", "_sb.qolda_norma_qiymatlari(_ss) if _norma_toldir" in kod)
tek("saqlangan qiymat ustun",
    "_sb.qiymat(all_analytes, code) or _norma_qiy.get(code, '')" in kod)
tek("faqat kimyoviy bo'sh bo'lsa",
    "_norma_toldir = not any(_sb.qiymat(all_analytes, _q[\"kod\"]) for _q in _qolda_q)" in kod)

print(f"{ok}/{ok + xato} o'tdi")
sys.exit(1 if xato else 0)
