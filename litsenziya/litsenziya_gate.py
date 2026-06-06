# -*- coding: utf-8 -*-
"""
Litsenziya DARVOZASI — dastur ishga tushishida chaqiriladi.

Foydalanish (desktop ilovalar — login.py, launcher.py, monoblok, registrator):
    from litsenziya import litsenziya_gate
    if not litsenziya_gate.darvoza("AzizMedLine"):
        sys.exit(0)   # litsenziya yo'q/yaroqsiz → dastur ochilmaydi

Foydalanish (server jarayonlari — sam_nazorat --server-only, tv_server):
    from litsenziya import litsenziya_gate
    if not litsenziya_gate.darvoza_server("AzizMed Server"):
        sys.exit(1)
"""

import os
import sys

from . import litsenziya_manager as lm

# Aloqa ma'lumotlari (faollashtirish oynasida ko'rsatiladi)
ALOQA_TELEFON = "+998 90 000 00 00"
ALOQA_TELEGRAM = "@azizmedline_support"


def tekshir() -> "lm.Natija":
    return lm.holatni_tekshir()


def darvoza_server(app_nomi: str = "AzizMed Server") -> bool:
    """Konsol (GUI'siz) tekshiruv — server jarayonlari uchun."""
    n = lm.holatni_tekshir()
    if n.yaroqli:
        print(f"[litsenziya] OK — {n.xabar}")
        return True
    print("=" * 60)
    print(f"[litsenziya] BLOK — {app_nomi}")
    print(f"  Sabab      : {n.xabar}")
    print(f"  Machine ID : {n.machine_id}")
    print(f"  Aloqa      : {ALOQA_TELEFON}  |  {ALOQA_TELEGRAM}")
    print("=" * 60)
    return False


def darvoza(app_nomi: str = "AzizMedLine", parent=None) -> bool:
    """
    GUI tekshiruv. Yaroqli bo'lsa True. Aks holda faollashtirish oynasi ochiladi;
    foydalanuvchi to'g'ri .azlic tanlasa True (faollashtirildi), aks holda False.
    """
    n = lm.holatni_tekshir()
    if n.yaroqli:
        return True
    return _faollashtirish_oyna(n, app_nomi, parent)


def _faollashtirish_oyna(natija, app_nomi, parent=None) -> bool:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        # Tkinter yo'q — konsolga tushamiz
        return darvoza_server(app_nomi)

    holat = {"ok": False}

    oyna = tk.Toplevel(parent) if parent else tk.Tk()
    oyna.title(f"{app_nomi} — Litsenziya kerak")
    oyna.configure(bg="#0f1422")
    en, bo = 520, 460
    oyna.geometry(f"{en}x{bo}")
    oyna.resizable(False, False)
    try:
        oyna.eval('tk::PlaceWindow . center')
    except Exception:
        pass

    def lbl(txt, **kw):
        d = dict(bg="#0f1422", fg="#e6e9f2", font=("Segoe UI", 10))
        d.update(kw)
        return tk.Label(oyna, text=txt, **d)

    lbl("🔒", font=("Segoe UI", 34)).pack(pady=(22, 4))
    lbl("Dastur faollashtirilmagan", font=("Segoe UI Semibold", 15)).pack()
    lbl(natija.xabar, fg="#ff9a9a", font=("Segoe UI", 10), wraplength=460).pack(pady=(6, 14))

    ramka = tk.Frame(oyna, bg="#1a2236")
    ramka.pack(fill="x", padx=26, pady=4)
    tk.Label(ramka, text="Ushbu kompyuter ID raqami:", bg="#1a2236", fg="#9aa3bd",
             font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 0))
    id_var = tk.StringVar(value=natija.machine_id)
    id_box = tk.Entry(ramka, textvariable=id_var, font=("Consolas", 13), justify="center",
                      bg="#0f1422", fg="#7ee0a0", relief="flat", readonlybackground="#0f1422")
    id_box.configure(state="readonly")
    id_box.pack(fill="x", padx=12, pady=(2, 10), ipady=6)

    def nusxa():
        oyna.clipboard_clear()
        oyna.clipboard_append(natija.machine_id)
        messagebox.showinfo("Nusxalandi", "Machine ID nusxalandi.\nShu ID ni administratorga yuboring.")

    tk.Button(oyna, text="📋 ID ni nusxalash", command=nusxa, bg="#2b5cff", fg="white",
              relief="flat", font=("Segoe UI Semibold", 10), cursor="hand2"
              ).pack(fill="x", padx=26, pady=(8, 4), ipady=7)

    def fayl_tanla():
        yol = filedialog.askopenfilename(
            title="Litsenziya faylini tanlang",
            filetypes=[("Litsenziya", "*.azlic"), ("Barcha fayllar", "*.*")],
        )
        if not yol:
            return
        natija2 = lm.faollashtir(yol)
        if natija2.yaroqli:
            messagebox.showinfo("Tayyor", f"Litsenziya faollashtirildi!\n{natija2.xabar}")
            holat["ok"] = True
            oyna.destroy()
        else:
            messagebox.showerror("Xato", natija2.xabar)

    tk.Button(oyna, text="📂 Litsenziya faylini tanlash (.azlic)", command=fayl_tanla,
              bg="#1f8a4c", fg="white", relief="flat", font=("Segoe UI Semibold", 10),
              cursor="hand2").pack(fill="x", padx=26, pady=4, ipady=7)

    def qayta():
        natija2 = lm.holatni_tekshir()
        if natija2.yaroqli:
            holat["ok"] = True
            oyna.destroy()
        else:
            messagebox.showwarning("Hali yaroqsiz", natija2.xabar)

    pastki = tk.Frame(oyna, bg="#0f1422")
    pastki.pack(fill="x", padx=26, pady=(8, 4))
    tk.Button(pastki, text="↻ Qayta urinish", command=qayta, bg="#2a3350", fg="#e6e9f2",
              relief="flat", font=("Segoe UI", 10), cursor="hand2").pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)
    tk.Button(pastki, text="✖ Yopish", command=oyna.destroy, bg="#5a2330", fg="#ffd0d0",
              relief="flat", font=("Segoe UI", 10), cursor="hand2").pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=5)

    tk.Label(oyna, text=f"Administrator bilan bog'laning:\n{ALOQA_TELEFON}   {ALOQA_TELEGRAM}",
             bg="#0f1422", fg="#9aa3bd", font=("Segoe UI", 9), justify="center").pack(pady=(12, 0))

    oyna.protocol("WM_DELETE_WINDOW", oyna.destroy)
    if parent:
        oyna.transient(parent)
        oyna.grab_set()
        oyna.wait_window()
    else:
        oyna.mainloop()
    return holat["ok"]


if __name__ == "__main__":
    n = lm.holatni_tekshir()
    print("Holat:", n.holat.value, "—", n.xabar)
    print("Machine ID:", n.machine_id)
    if not n.yaroqli:
        darvoza("AzizMedLine (sinov)")
