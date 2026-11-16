# -*- coding: utf-8 -*-
"""Umumiy qon tahlili (CBC) — QO'LDA kiritish oynasi sinovi (2026-11-15).

Bazaga TEGMAYDI: MonoblokApp metodlari soxta obyektga ulanadi, oyna haqiqiy
Tk'da ochiladi, qiymatlar kiritiladi, «Saqlash» bosiladi, natija JSON'i
blanka funksiyasiga (create_hematology_cbc_table_in_doc) berilib jadval o'qiladi.
Avto-hisob (# ↔ %, MCH/MCV/MCHC, PCT, P-LCC, NLR, PLR), 3-diff/5-diff, Enter sakrashi.

    python tests_cbc_qolda_sinov.py            (G:\\DASTUR\\URIT 50 dan)
    python tests_cbc_qolda_sinov.py --rasm      oyna suratini saqlaydi (CBC_RASM)
"""
import json
import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monoblok_dastur as M  # noqa: E402
import gemo_blanka as GB  # noqa: E402
from docx import Document  # noqa: E402

RASM = "--rasm" in sys.argv
RASM_YOL = os.environ.get("CBC_RASM", "cbc_qolda_oyna.png")
xato = 0


def tek(shart, nom, izoh=""):
    global xato
    print(("  OK   " if shart else "  XATO ") + nom + (f"  ({izoh})" if izoh and not shart else ""))
    if not shart:
        xato += 1


root = tk.Tk()
root.geometry("200x100+0+0")
dialoglar = []
M.messagebox.showwarning = lambda *a, **k: dialoglar.append(("ogoh", a[0], a[1] if len(a) > 1 else ""))


class Soxta:
    _cbc_qolda_oyna = M.MonoblokApp._cbc_qolda_oyna
    _cbc_son = staticmethod(M.MonoblokApp._cbc_son)

    def __init__(self):
        self.root = root
        self.current_bemor_data = {"fish": "Sinov Bemor", "yosh": 35, "jins": "Erkak", "sample_id": "260001"}
        self.test_results = {}
        self.pending = {}
        self.yangilandi = []
        self.tests_tree = ttk.Treeview(root)
        self.tests_tree.insert("", "end", values=("x",), tags=("7_q",))

    def _mark_result_pending(self, tid, v):
        self.pending[tid] = v

    def refresh_single_test_display(self, item, tid):
        self.yangilandi.append(tid)


def tugma(w, matn):
    for c in w.winfo_children():
        if isinstance(c, tk.Button) and matn in str(c.cget("text")):
            return c
        r = tugma(c, matn)
        if r:
            return r
    return None


def yoz(win, kod, v):
    e = win.cbc_katak(kod)
    e.delete(0, tk.END)
    if v:
        e.insert(0, v)
    root.update()


def ol(win, kod):
    e = win.cbc_katak(kod)
    return e.get() if e is not None else None


def yangi_oyna(rejim="5", mavjud=None):
    app = Soxta()
    win = app._cbc_qolda_oyna(7, "Umumiy qon tahlili", mavjud=mavjud)
    root.update()
    if win.cbc_rejim.get() != rejim:
        win.cbc_rejim.set(rejim)
        root.update()
    win.cbc_avto.set(True)
    root.update()
    return app, win


print("\nA) Qo'lda kiritish + avto-hisob (MCH, MCV, MCHC, Lymph#, PLR)")
app, win = yangi_oyna("5")
for kod, v in {"WBC": "11,5", "RBC": "4.6", "HGB": "95", "HCT": "41", "PLT": "250", "Lymph%": "30"}.items():
    yoz(win, kod, v)
tek(ol(win, "Lymph#") == "3.45", "Lymph# = 11.5×30/100 = 3.45", ol(win, "Lymph#"))
tek(ol(win, "MCH") == "20.7", "MCH = 95/4.6 = 20.7", ol(win, "MCH"))
tek(ol(win, "MCV") == "89.1", "MCV = 41×10/4.6 = 89.1", ol(win, "MCV"))
tek(ol(win, "MCHC") == "232", "MCHC = 95×100/41 = 232", ol(win, "MCHC"))
tek(ol(win, "PLR") == "72", "PLR = 250/3.45 = 72", ol(win, "PLR"))
tek(str(win.cbc_katak("MCH").cget("bg")).lower() == "#e3f0ff", "hisoblangan katak och ko'k",
    win.cbc_katak("MCH").cget("bg"))
tek(str(win.cbc_katak("HGB").cget("bg")).lower() == "white", "qo'lda katak oq")
if RASM:
    try:
        from PIL import ImageGrab
        win.lift(); win.attributes("-topmost", True); root.update(); win.after(400); root.update()
        x, y = win.winfo_rootx(), win.winfo_rooty()
        ImageGrab.grab(bbox=(x, y, x + win.winfo_width(), y + win.winfo_height())).save(RASM_YOL)
        print("  surat:", RASM_YOL)
    except Exception as e:
        print("  surat olinmadi:", e)
tugma(win, "Saqlash").invoke()
root.update()
d = json.loads(app.test_results.get(7, "{}"))
tek(d.get("type") == "hematology_cbc" and d.get("source") == "Qo'lda", "type=hematology_cbc, source=Qo'lda", str(d)[:120])
tek(d.get("WBC") == "11.5", "vergul nuqtaga: WBC=11.5", d.get("WBC"))
tek(d.get("Lymph#") == "3.45" and d.get("MCV") == "89.1", "hisoblanganlar JSON'da")
tek(d.get("sid") == "260001" and d.get("patient_age") == "35", "sid va yosh yozildi")
tek(7 in app.pending and app.yangilandi == [7], "saqlanmagan deb belgilandi + jadval qatori yangilandi")
tek("RDW-CV" not in d and "NLR" not in d, "kiritilmagan/hisoblanmaydigan ko'rsatkich JSON'da yo'q")

print("\nB) Blanka jadvali shu JSON'dan")
doc = Document()
M.create_hematology_cbc_table_in_doc(doc, app.test_results[7], {"yosh": 35, "jins": "Erkak", "sample_id": "260001"})
qator = {}
for t in doc.tables:
    for r in t.rows:
        cells = [c.text.strip() for c in r.cells]
        if len(cells) >= 3:
            qator[cells[1]] = cells
tek("WBC" in qator and qator["WBC"][2].startswith("11.5"), "blankada WBC 11.5", str(qator.get("WBC")))
tek("↑" in qator.get("WBC", ["", "", ""])[2], "WBC normadan yuqori — ↑", str(qator.get("WBC")))
tek("↓" in qator.get("HGB", ["", "", ""])[2], "HGB 95 — ↓", str(qator.get("HGB")))
tek(qator.get("MCV", ["", "", ""])[2].startswith("89.1"), "blankada hisoblangan MCV 89.1", str(qator.get("MCV")))
tek(qator.get("RDW-CV", ["", "", "-"])[2] in ("-", ""), "kiritilmagan RDW-CV blankada «-»", str(qator.get("RDW-CV")))

print("\nC) Noto'g'ri qiymat saqlanmaydi")
app2, win2 = yangi_oyna("5")
yoz(win2, "WBC", "abc")
yoz(win2, "HGB", "-5")
tek(str(win2.cbc_katak("WBC").cget("bg")).lower() == "#ffd6d6", "noto'g'ri maydon qizil", win2.cbc_katak("WBC").cget("bg"))
tugma(win2, "Saqlash").invoke()
root.update()
tek(not app2.test_results and dialoglar and "WBC" in dialoglar[-1][2] and "HGB" in dialoglar[-1][2],
    "saqlanmadi, ogohlantirishda WBC va HGB", str(dialoglar[-1:]))
win2.destroy()

print("\nD) Bo'sh oynani saqlash")
app3, win3 = yangi_oyna("5")
tugma(win3, "Saqlash").invoke()
root.update()
tek(not app3.test_results and "kiritilmadi" in dialoglar[-1][2], "bo'sh — saqlanmadi")
win3.destroy()

print("\nE) Analizator natijasini qo'lda tuzatish (gistogramma saqlanadi)")
app4 = Soxta()
analizator = {"type": "hematology_cbc", "source": "BC-20S", "sid": "777", "WBC": "6.0", "HGB": "140",
              "MCV": "88", "histograms": {"WBC": [1, 2, 3]}}
win4 = app4._cbc_qolda_oyna(7, "Umumiy qon tahlili", mavjud=analizator)
root.update()
tek(ol(win4, "WBC") == "6.0" and ol(win4, "MCV") == "88", "mavjud qiymatlar to'ldirilgan")
yoz(win4, "HGB", "132")
yoz(win4, "MCV", "")
tugma(win4, "Saqlash").invoke()
root.update()
d4 = json.loads(app4.test_results[7])
tek(d4["HGB"] == "132" and "MCV" not in d4, "HGB tuzatildi, o'chirilgan MCV olib tashlandi")
tek(d4.get("histograms") == {"WBC": [1, 2, 3]} and d4.get("sid") == "777", "gistogramma va sid saqlandi")
tek(d4.get("source") == "BC-20S (qo'lda tuzatilgan)", "manba: BC-20S (qo'lda tuzatilgan)", d4.get("source"))

print("\nF) 5-diff leykoformula: % YOKI # kiritiladi (teskari formula)")
app5, win5 = yangi_oyna("5")
yoz(win5, "WBC", "8")
yoz(win5, "Neu%", "60")
yoz(win5, "Lymph#", "2.4")          # soni kiritildi — % hisoblanadi
yoz(win5, "Mon%", "6")
yoz(win5, "Eos%", "3")
tek("100.0 %" not in win5.cbc_jami() and "hali hammasi" in win5.cbc_jami(), "jami: hali to'liq emas", win5.cbc_jami())
yoz(win5, "Bas%", "1")
tek(ol(win5, "Neu#") == "4.80", "Neu# = 8×60/100 = 4.80", ol(win5, "Neu#"))
tek(ol(win5, "Lymph%") == "30.0", "teskari: Lymph% = 2.4/8×100 = 30.0", ol(win5, "Lymph%"))
tek(ol(win5, "Mon#") == "0.48" and ol(win5, "Eos#") == "0.24" and ol(win5, "Bas#") == "0.08", "Mon#/Eos#/Bas#")
tek(ol(win5, "NLR") == "2.00", "NLR = 4.80/2.4 = 2.00", ol(win5, "NLR"))
tek("100.0 %" in win5.cbc_jami() and "✓" in win5.cbc_jami(), "jami 100 % ✓", win5.cbc_jami())
tek(win5.cbc_katak("Mid#") is None and win5.cbc_katak("Gran%") is None, "5-diff: Mid/Gran oynada yo'q")

print("\nG) Hisoblangan katakka o'zi yozsa — qo'lda bo'ladi, dastur tegmaydi")
yoz(win5, "Neu#", "5.5")
tek("Neu#" not in win5.cbc_avto_kodlar and ol(win5, "Neu#") == "5.5", "Neu# endi qo'lda 5.5")
tek("mos emas" in win5.cbc_jami() and "Neu" in win5.cbc_jami(), "# va % mos emas ogohlantirishi", win5.cbc_jami())
yoz(win5, "WBC", "10")
tek(ol(win5, "Neu#") == "5.5" and ol(win5, "Mon#") == "0.60", "WBC o'zgardi: qo'lda Neu# o'zgarmadi, Mon# qayta hisoblandi",
    f"{ol(win5, 'Neu#')} {ol(win5, 'Mon#')}")
yoz(win5, "Neu#", "")
tek(ol(win5, "Neu#") == "6.00", "qo'lda Neu# o'chirildi — yana hisoblandi 6.00", ol(win5, "Neu#"))

print("\nH) Avtomatik hisoblash o'chirilsa")
win5.cbc_avto.set(False)
root.update()
tek(ol(win5, "Neu#") == "" and ol(win5, "Lymph%") == "" and ol(win5, "NLR") == "", "hisoblanganlar tozalandi")
tek(ol(win5, "Neu%") == "60" and ol(win5, "Lymph#") == "2.4", "qo'lda yozilganlar qoldi")
win5.cbc_avto.set(True)
root.update()
tek(ol(win5, "Lymph%") == "24.0", "qayta yoqildi: Lymph% = 2.4/10×100 = 24.0", ol(win5, "Lymph%"))

print("\nI) Enter — hisoblangan va indeks kataklarni o'tkazib yuboradi")
kodlar = [k for k, _e in win5.cbc_nav]
i_neu = kodlar.index("Neu%")
win5.lift(); win5.focus_force(); root.update()
win5.cbc_otish(i_neu, +1, True)
root.update()
fk = win5.focus_get()
tek(fk is win5.cbc_katak("Lymph#"), "Neu% → Enter → Lymph# (Neu# hisoblangan, Lymph% hisoblangan — o'tkazildi)",
    str(fk))
win5.cbc_otish(i_neu, +1, False)
root.update()
tek(win5.focus_get() is win5.cbc_katak("Neu#"), "↓ — o'tkazmasdan keyingi katak (Neu#)")
i_plt = kodlar.index("PLT")
i_nlr = kodlar.index("NLR")
tek(i_nlr > i_plt, "NLR jadvalda PLT dan keyin")
win5.destroy()

print("\nJ) 3-diff leykoformula (Lymph, Mid, Gran)")
app6, win6 = yangi_oyna("3")
tek(win6.cbc_katak("Neu%") is None and win6.cbc_katak("Mid%") is not None, "3-diff: Neu/Mon/Eos/Bas yo'q, Mid/Gran bor")
for kod, v in {"WBC": "6", "Lymph%": "35", "Mid%": "8", "Gran%": "57", "PLT": "300"}.items():
    yoz(win6, kod, v)
tek(ol(win6, "Gran#") == "3.42" and ol(win6, "Mid#") == "0.48" and ol(win6, "Lymph#") == "2.10", "Gran#/Mid#/Lymph#",
    f"{ol(win6, 'Gran#')} {ol(win6, 'Mid#')} {ol(win6, 'Lymph#')}")
tek(ol(win6, "NLR") == "1.63", "NLR = Gran#/Lymph# = 1.63", ol(win6, "NLR"))
tek("100.0 %" in win6.cbc_jami(), "jami 100 %", win6.cbc_jami())
tugma(win6, "Saqlash").invoke()
root.update()
d6 = json.loads(app6.test_results[7])
tek("Neu#" not in d6 and d6.get("Gran%") == "57" and d6.get("Gran#") == "3.42", "JSON 3-diff")
doc6 = Document()
M.create_hematology_cbc_table_in_doc(doc6, app6.test_results[7], {"yosh": 35, "jins": "Erkak"})
q6 = {}
for t in doc6.tables:
    for r in t.rows:
        cells = [c.text.strip() for c in r.cells]
        if len(cells) >= 3:
            q6[cells[1]] = cells
tek("Mid#" in q6 and "Neu#" not in q6, "blankada 3-diff qatorlar, 5-diff yo'q", str(list(q6)[:12]))

print("\nK) Formulalar (gemo_blanka.avto_hisobla)")
r = GB.avto_hisobla({"HGB": 130, "RBC": 4.3}, "5", bor={"HGB", "RBC", "MCH", "CP"})
tek(r.get("MCH") == "30.2" and r.get("CP") == "0.91", "MCH 30.2, rang ko'rsatkichi 0.91", str(r))
r = GB.avto_hisobla({"PLT": 250, "MPV": 10, "P-LCR": 30}, "5")
tek(r.get("PCT") == "0.250" and r.get("P-LCC") == "75", "PCT 0.250, P-LCC 75", str(r))
r = GB.avto_hisobla({"HGB": 13.0, "RBC": 4.3}, "5", birlik={"HGB": "g/dL"})
tek(r.get("MCH") == "30.2", "HGB g/dL bo'lsa ham MCH 30.2", str(r))
r = GB.avto_hisobla({"WBC": 0, "Neu#": 1}, "5")
tek("Neu%" not in r, "WBC=0 — nolga bo'linmaydi", str(r))

root.destroy()
print("\nNATIJA:", "HAMMASI OK" if not xato else f"{xato} ta XATO")
sys.exit(1 if xato else 0)
