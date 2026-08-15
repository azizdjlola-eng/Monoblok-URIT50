# -*- coding: utf-8 -*-
"""
Bloklamaydigan bildirishnoma (toast) — Natija (monoblok) oynalari uchun.

NEGA KERAK (egasi talabi, 2026-08-15): siydik / gemotologiya / bioximiya
analizatoridan natija asosiy oynaga o'tkazilganda har safar modal oyna chiqib,
laborant sichqonchani olib borib OK bosishi kerak edi. Bu kuniga o'nlab marta
takrorlanadi va sof vaqt yo'qotish — chunki xabar hech qanday QAROR
talab qilmaydi, shunchaki "bo'ldi" deydi.

Endi registratsiya oynasidagi kabi: pastda yashil xabar chiqadi va o'zi
yo'qoladi. Ish to'xtamaydi.

⚠️ FAQAT MUVAFFAQIYAT xabarlari uchun. Xato va ogohlantirishlar MODAL
bo'lib qolishi SHART — ular ko'rilmay o'tib ketmasligi kerak. Bugungi
kunning eng qimmat xatolari aynan "jim o'tib ketgan" xatolar edi.
"""

import tkinter as tk

YASHIL = "#1b5e20"
SARIQ = "#e65100"


def toast(parent, matn: str, davomiylik_ms: int = 3500, fon: str = YASHIL):
    """Bloklamaydigan xabar. Ustiga bosilsa darhol yopiladi.

    parent — Tk oynasi (Toplevel yoki root). Bo'lmasa/xato bo'lsa jimgina
    hech narsa qilmaydi: bildirishnoma tufayli asosiy ish buzilmasin.
    """
    try:
        win = tk.Toplevel(parent)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.96)
        except Exception:
            pass

        ramka = tk.Frame(win, bg=fon, bd=0, highlightthickness=1,
                         highlightbackground="#ffffff")
        ramka.pack(fill="both", expand=True)
        tk.Label(ramka, text=matn, bg=fon, fg="white",
                 font=("Segoe UI", 11, "bold"), justify="left",
                 padx=18, pady=12, wraplength=420).pack()

        win.update_idletasks()
        # Egasi oynasining PASTKI-O'NG burchagi
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
        except Exception:
            px = py = 0
            pw, ph = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{max(0, px + pw - w - 30)}+{max(0, py + ph - h - 60)}")

        win.bind("<Button-1>", lambda _e: _yop(win))
        for bola in (ramka, *ramka.winfo_children()):
            bola.bind("<Button-1>", lambda _e: _yop(win))

        win.after(davomiylik_ms, lambda: _yop(win))
        return win
    except Exception:
        return None


def _yop(win):
    try:
        win.destroy()
    except Exception:
        pass
