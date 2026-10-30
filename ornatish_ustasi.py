"""
Yangi mijozga o'rnatish ustasi — tekshiruv ro'yxati.

Dasturni yangi laboratoriyaga o'rnatganda nimalarni sozlash kerakligi bir oynada:
har qadam avtomatik tekshiriladi (✓ tayyor / ⚠ e'tibor bering / ℹ ma'lumot) va
tegishli sozlash oynasini ochadigan tugma bor. Qadamlarni monoblok_dastur beradi
(tekshiruv va ochish funksiyalari), bu modul faqat oyna.

«✔ O'rnatish tugadi» — bazaga belgi yoziladi (markaziy_sozlama "ornatish_tugadi");
mijoz buildida usta shu belgi bo'lmaguncha dastur ochilganda o'zi chiqadi.
"""

import datetime
import socket
import threading

BELGI = {True: "✓", False: "⚠", None: "ℹ"}
RANG = {True: "#1b5e20", False: "#c62828", None: "#1565C0"}


def tugadimi() -> bool:
    try:
        import markaziy_sozlama as _ms
        return bool(_ms.ol("ornatish_tugadi"))
    except Exception:
        return True      # baza ishlamasa — ustani majburan chiqarmaymiz


def tugadi_belgila() -> bool:
    import markaziy_sozlama as _ms
    return _ms.yoz("ornatish_tugadi", {"sana": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "kompyuter": socket.gethostname()})


def ochish_oyna(parent, qadamlar):
    """qadamlar: [{"nomi", "izoh", "tekshir": fn() -> (True|False|None, matn), "ochish": fn | None,
                  "tugma": "Ochish..."}]"""
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(parent)
    win.title("🧭 O'rnatish ustasi — yangi laboratoriya")
    win.geometry("980x700")
    win.minsize(820, 560)
    win.transient(parent)

    tk.Label(win, text="Yangi laboratoriyaga o'rnatish — tekshiruv ro'yxati", bg="#1a3a5c", fg="white",
             font=("Arial", 13, "bold"), anchor="w", padx=12, pady=8).pack(fill=tk.X)
    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=940, text=(
        "Yuqoridan pastga qarab o'ting. ⚠ — albatta qarang; ✓ — tayyor; ℹ — ma'lumot. "
        "Har qadamdagi tugma tegishli sozlash oynasini ochadi; sozlab bo'lgach "
        "«↻ Qayta tekshirish» ni bosing. Hammasi tayyor bo'lsa — «✔ O'rnatish tugadi».")
              ).pack(fill=tk.X, padx=12, pady=(8, 4))

    outer = ttk.Frame(win)
    outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    canvas = tk.Canvas(outer, highlightthickness=0)
    sb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.LEFT, fill=tk.Y)
    win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
                    if win.winfo_exists() else None)

    holat_lbl = []
    for i, q in enumerate(qadamlar, 1):
        fr = ttk.Frame(inner, padding=(6, 6))
        fr.pack(fill=tk.X, anchor="w")
        top = ttk.Frame(fr)
        top.pack(fill=tk.X)
        b = tk.Label(top, text="…", font=("Arial", 14, "bold"), width=2, fg="#888")
        b.pack(side=tk.LEFT)
        tk.Label(top, text=f"{i}. {q['nomi']}", font=("Arial", 11, "bold"), anchor="w").pack(side=tk.LEFT)
        if q.get("ochish"):
            ttk.Button(top, text=q.get("tugma") or "Ochish...",
                       command=lambda f=q["ochish"]: _och(f)).pack(side=tk.RIGHT)
        if q.get("izoh"):
            ttk.Label(fr, text=q["izoh"], foreground="#555", wraplength=880, justify=tk.LEFT
                      ).pack(anchor="w", padx=(30, 0))
        h = tk.Label(fr, text="tekshirilmoqda...", fg="#888", wraplength=880, justify=tk.LEFT, anchor="w")
        h.pack(anchor="w", padx=(30, 0), pady=(2, 0))
        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=6)
        holat_lbl.append((b, h))

    def _och(f):
        try:
            f()
        except Exception as e:
            messagebox.showerror("O'rnatish ustasi", f"Oyna ochilmadi:\n{e}", parent=win)

    def _tekshir():
        """Tekshiruvlar fon oqimida (baza so'rovlari oynani qotirmasin), natija — UI da."""
        for b, h in holat_lbl:
            b.config(text="…", fg="#888")
            h.config(text="tekshirilmoqda...", fg="#888")

        def ish():
            natijalar = []
            for q in qadamlar:
                try:
                    natijalar.append(q["tekshir"]() if q.get("tekshir") else (None, ""))
                except Exception as e:
                    natijalar.append((False, f"Tekshirishda xato: {e}"))

            def ko_rsat():
                if not win.winfo_exists():
                    return
                for (b, h), (ok, matn) in zip(holat_lbl, natijalar):
                    b.config(text=BELGI[ok], fg=RANG[ok])
                    h.config(text=matn or "", fg=RANG[ok] if ok is False else "#333")
            win.after(0, ko_rsat)
        threading.Thread(target=ish, daemon=True).start()

    def _tugadi():
        if not messagebox.askyesno("O'rnatish ustasi", "O'rnatish tugadi deb belgilansinmi?\n"
                                   "(Usta endi o'zi chiqmaydi — Tizim Sozlamalaridan ochsa bo'ladi.)",
                                   parent=win):
            return
        if tugadi_belgila():
            messagebox.showinfo("O'rnatish ustasi", "Belgilandi.", parent=win)
            win.destroy()
        else:
            messagebox.showwarning("O'rnatish ustasi", "Bazaga yozib bo'lmadi (mahalliy saqlandi).", parent=win)

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="✔ O'rnatish tugadi", command=_tugadi, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=14, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Yopish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="↻ Qayta tekshirish", command=_tekshir).pack(side=tk.LEFT, padx=4)
    win.bind("<Escape>", lambda e: win.destroy())
    _tekshir()
    return win
