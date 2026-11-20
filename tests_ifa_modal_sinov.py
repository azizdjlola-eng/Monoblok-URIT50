"""Monoblok: modal (grab) oyna ochiq turganda IFA ogohlantirishi kechiktiriladimi.

2026-11-20: siydik natijasini yozayotganda (modal oyna, grab_set) yangi IFA kelsa, IFA oynasi
ustiga chiqib «Ko'rdim» ham, ortdagi siydik oynasi ham bosilmay dastur qotardi.
Ishga tushirish:  py -3 tests_ifa_modal_sinov.py
"""
import os, sys, tempfile
sys.stdout.reconfigure(encoding="utf-8")
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ["ProgramData"] = tempfile.mkdtemp()
import tkinter as tk
import monoblok_dastur as M

M._pkt.yoqilganmi = lambda k: True
cls = next(v for v in vars(M).values() if isinstance(v, type) and hasattr(v, "open_immuno_window"))
app = cls.__new__(cls)
app.root = tk.Tk()
app.root.geometry("300x200+-3000+0")

ochildi = []
asl = cls.open_immuno_window
natija = []


def tekshir(nom, shart):
    natija.append(shart)
    print(("[OK]  " if shart else "[XATO]") + " " + nom)


# 1) modal siydik oynasi
popup = tk.Toplevel(app.root)
popup.geometry("200x100+-3000+300")
popup.transient(app.root)
app.root.update()
popup.grab_set()
app.root.update()
tekshir("grab siydik oynasida", app._boshqa_modal_oyna())

# open_immuno_window ning o'zini chaqiramiz (haqiqiy yo'l) — oyna yaratilmasligi kerak
app.open_immuno_window(banner="🔔 YANGI IFA: Vitamin D")
tekshir("modal paytida IFA oynasi YARATILMADI", getattr(app, "_immuno_win", None) is None)
tekshir("banner kutishda", app._imm_kutilgan_banner == "🔔 YANGI IFA: Vitamin D")
app.open_immuno_window(banner="🔔 YANGI IFA: TTG")
tekshir("ikkinchi IFA ham qo'shildi", "TTG" in app._imm_kutilgan_banner and "Vitamin" in app._imm_kutilgan_banner)

# Endi ochilishni yozib olamiz (to'liq oyna bazaga ulanadi — sinovda kerak emas)
cls.open_immuno_window = lambda self, banner=None: ochildi.append(banner)


def keyin():
    tekshir("modal ochiq — hali ochilmadi", ochildi == [])
    popup.grab_release()
    popup.destroy()
    app.root.after(2500, yakun)


def yakun():
    tekshir("modal yopilgach IFA ochildi (1 marta)", len(ochildi) == 1)
    tekshir("ikkala IFA bannerda", bool(ochildi) and "TTG" in ochildi[0] and "Vitamin" in ochildi[0])
    tekshir("grab yo'q — kutish tugadi", not app._boshqa_modal_oyna() and not app._imm_kutish_faol)
    app.root.destroy()


app.root.after(2000, keyin)
app.root.mainloop()
print(f"JAMI: {sum(natija)}/{len(natija)}")
sys.exit(0 if natija and all(natija) else 1)
