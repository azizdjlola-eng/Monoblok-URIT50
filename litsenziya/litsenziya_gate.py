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
from . import demo

# Aloqa ma'lumotlari (faollashtirish oynasida ko'rsatiladi)
ALOQA_TELEFON = "+998 99 673 13 42"
ALOQA_TELEGRAM = "@Aziz996731342"


def tekshir() -> "lm.Natija":
    return lm.holatni_tekshir()


# ── Baza (va boshqa muhim amallar) uchun yengil, keshlangan tekshiruv ──
import time as _time
_ruxsat_cache = {"t": 0.0, "ok": False}


def ruxsat_bormi(cache_sec: float = 300.0) -> bool:
    """
    Litsenziya yaroqlimi? (keshlangan — har chaqiruvda fayl/imzo qayta o'qilmaydi).
    Baza ulanishini himoyalash uchun: litsenziyasiz BAZAGA HAM kirmasin.
    Xatolik/yaroqsiz bo'lsa — False (fail-closed).
    """
    now = _time.time()
    if _ruxsat_cache["ok"] and (now - _ruxsat_cache["t"]) < cache_sec:
        return True
    try:
        # online=False — ATAYIN. Bu tekshiruv BAZAGA ULANISH yo'lida turadi
        # (db_conn), ya'ni foydalanuvchi tugma bosgan paytda. Online qatlam esa
        # VPS ga TCP urinadi va server javob bermasa 1.2 soniya kutadi —
        # natijada dastur har 5 daqiqada bir marta qotib qolardi.
        # Masofadan blok/uzaytirish baribir HAR OCHILISHDA darvoza() da
        # (online=True bilan) tekshiriladi — himoya susaymaydi.
        ok = lm.holatni_tekshir(online=False).yaroqli
    except Exception:
        ok = False
    _ruxsat_cache["ok"] = ok
    _ruxsat_cache["t"] = now
    return ok


def baza_ruxsati_yoki_xato():
    """
    Baza ulanish nuqtalarida chaqiriladi. Faqat FROZEN (EXE) da majburlaydi
    (dev'da ishlashni to'smaydi). Yaroqsiz bo'lsa RuntimeError ko'taradi.
    """
    import sys as _sys
    if not getattr(_sys, "frozen", False):
        return  # dev — o'tkazamiz
    if not ruxsat_bormi():
        raise RuntimeError("Litsenziya yaroqsiz — bazaga kirish taqiqlangan.")


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


def darvoza_xizmat(app_nomi: str = "AzizMed xizmati", jim: bool = False) -> bool:
    """
    Fon xizmatlari (Vrach kabineti, TV server) uchun darvoza.

      • Manba (dev) rejimi — HECH QACHON to'smaydi.
      • Litsenziya yaroqli — jimgina o'tkazadi.
      • Yaroqsiz + `jim=True` (Windows avtostarti) — oyna CHIQARMAYDI, faqat
        logga yozadi. Kompyuter yoqilganda mijoz oldiga oyna otilib chiqmasin.
      • Yaroqsiz + qo'lda ishga tushirilgan — FAOLLASHTIRISH OYNASI chiqadi
        (Machine ID + .azlic tanlash), xuddi Registratsiya oynasidagidek.
        Shu tariqa litsenziyani "qayerga qo'yish" savoli yo'qoladi.
    """
    if not getattr(sys, "frozen", False):
        return True
    n = _demo_tenglab_tekshir()
    if n.yaroqli:
        return True
    if jim:
        return darvoza_server(app_nomi)
    darvoza_server(app_nomi)        # logga sabab + Machine ID yozib qo'yamiz
    return _faollashtirish_oyna(n, app_nomi)


def darvoza(app_nomi: str = "AzizMedLine", parent=None) -> bool:
    """
    GUI tekshiruv. Yaroqli bo'lsa True. Aks holda faollashtirish oynasi ochiladi;
    foydalanuvchi to'g'ri .azlic tanlasa True (faollashtirildi), aks holda False.

    Dev (manba koddan `python launcher.py` bilan ishga tushirish) — litsenziya
    MAJBURLANMAYDI (ishlab chiquvchi/egasining kompyuteri to'silmaydi). Litsenziya
    faqat tarqatilgan EXE (frozen) da talab qilinadi — bu `baza_ruxsati_yoki_xato()`
    dagi mantiq bilan bir xil.
    """
    if not getattr(sys, "frozen", False):
        return True
    n = _demo_tenglab_tekshir()
    if n.yaroqli:
        return True
    return _faollashtirish_oyna(n, app_nomi, parent)


def _demo_tenglab_tekshir():
    """holatni_tekshir + demo/litsenziyasiz holatda umumiy baza bilan tenglash: klinikada
    demo ketayotgan bo'lsa yangi kompyuter O'SHA sanani oladi (hammasi bir kunda tugaydi),
    klinika sotib olgan bo'lsa — 3 kunlik muhlat. Baza 3 s da javob bermasa — o'tkaziladi."""
    n = lm.holatni_tekshir()
    if n.holat == lm.Holat.YOQ or (n.payload or {}).get("tarif") == "DEMO":
        try:
            demo.baza_bilan_tenglash(n.machine_id)
            n = lm.holatni_tekshir(online=False)
        except Exception:
            pass
    return n


def _klinika_taxmin() -> str:
    """Brend sozlamasidagi klinika nomi (bo'lsa) — formani oldindan to'ldirish uchun."""
    try:
        import masofa_agent
        return masofa_agent._klinika_nomi()
    except Exception:
        return ""


def sorov_oynasi(parent, natija):
    """«📨 Litsenziya so'rash»: klinika, telefon, Telegram → VPS → egasiga Telegram xabari.
    Internet bo'lmasa — so'rov matni nusxalanadi (Telegram'da qo'lda yuborish uchun)."""
    import tkinter as tk
    from tkinter import messagebox
    w = tk.Toplevel(parent)
    w.title("📨 Litsenziya so'rash")
    w.configure(bg="#0f1422")
    w.resizable(False, False)
    tk.Label(w, text="Litsenziya so'rovi", bg="#0f1422", fg="#e6e9f2",
             font=("Segoe UI Semibold", 13)).pack(pady=(14, 2))
    tk.Label(w, text="Ma'lumot AzizMedLine'ga yuboriladi, siz bilan bog'lanishadi.", bg="#0f1422",
             fg="#9aa3bd", font=("Segoe UI", 9)).pack()
    f = tk.Frame(w, bg="#0f1422")
    f.pack(padx=22, pady=10)
    maydon = {}
    for i, (k, nom, std) in enumerate((("klinika", "Klinika / laboratoriya nomi *", _klinika_taxmin()),
                                       ("telefon", "Telefon raqami *", ""),
                                       ("telegram", "Telegram (raqam yoki @nom)", ""),
                                       ("izoh", "Izoh (nechta kompyuter, muddat...)", ""))):
        tk.Label(f, text=nom, bg="#0f1422", fg="#cfd6ea", font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w", pady=3)
        v = tk.StringVar(value=std)
        tk.Entry(f, textvariable=v, width=34, font=("Segoe UI", 10)).grid(row=i, column=1, padx=(8, 0), pady=3)
        maydon[k] = v
    v_roz = tk.BooleanVar(value=False)
    tk.Checkbutton(w, text="Ma'lumotlarim AzizMedLine'ga yuborilishiga roziman", variable=v_roz,
                   bg="#0f1422", fg="#cfd6ea", selectcolor="#1a2236", activebackground="#0f1422",
                   font=("Segoe UI", 9)).pack(anchor="w", padx=22)

    def _matn():
        return (f"Litsenziya so'rovi\nKlinika: {maydon['klinika'].get()}\nTelefon: {maydon['telefon'].get()}\n"
                f"Telegram: {maydon['telegram'].get()}\nKompyuter ID: {natija.machine_id}\n"
                f"Holat: {natija.xabar}\nIzoh: {maydon['izoh'].get()}")

    def _yubor():
        if not maydon["klinika"].get().strip() or not maydon["telefon"].get().strip():
            messagebox.showwarning("To'ldiring", "Klinika nomi va telefon raqami kerak.", parent=w)
            return
        if not v_roz.get():
            messagebox.showwarning("Rozilik", "Yuborish uchun rozilik belgisini qo'ying.", parent=w)
            return
        ok, xabar = lm.sorov_yubor(maydon["klinika"].get().strip(), maydon["telefon"].get().strip(),
                                   maydon["telegram"].get().strip(), maydon["izoh"].get().strip(), natija.xabar)
        if ok:
            messagebox.showinfo("Yuborildi", xabar, parent=w)
            w.destroy()
            return
        try:
            w.clipboard_clear()
            w.clipboard_append(_matn())
        except Exception:
            pass
        messagebox.showwarning("Yuborilmadi", f"{xabar}\n\nSo'rov matni NUSXALANDI — uni Telegram'da "
                               f"{ALOQA_TELEGRAM} ga yuboring (Ctrl+V)\nyoki qo'ng'iroq qiling: {ALOQA_TELEFON}",
                               parent=w)
    tk.Button(w, text="📨 Yuborish", command=_yubor, bg="#1f8a4c", fg="white", relief="flat",
              font=("Segoe UI Semibold", 11), cursor="hand2").pack(fill="x", padx=22, pady=(8, 14), ipady=6)
    w.transient(parent)
    w.grab_set()
    return w


def demo_oynasi(parent) -> bool:
    """«🎁 30 kunlik sinov» formasi. Forma ma'lumoti klinika profiliga (chek, TV, Vrach) va
    internet bo'lganda AzizMedLine'ga boradi. True — demo boshlandi va hali yaroqli."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    natija = {"ok": False}
    w = tk.Toplevel(parent)
    w.title("🎁 30 kunlik sinovni boshlash")
    w.configure(bg="#0f1422")
    w.resizable(False, False)
    tk.Label(w, text=f"{demo.DEMO_KUN} kunlik bepul sinov", bg="#0f1422", fg="#e6e9f2",
             font=("Segoe UI Semibold", 14)).pack(pady=(14, 2))
    tk.Label(w, text="Barcha imkoniyatlar ochiq. Bu ma'lumotlar chek, blanka va TV'da ham ishlatiladi.",
             bg="#0f1422", fg="#9aa3bd", font=("Segoe UI", 9)).pack(padx=20)
    f = tk.Frame(w, bg="#0f1422")
    f.pack(padx=22, pady=10)
    maydon = {}
    qatorlar = (("nomi", "Klinika / laboratoriya nomi *"), ("turi", "Turi *"), ("telefon", "Telefon raqami *"),
                ("telegram", "Telegram (raqam yoki @nom)"), ("manzil", "Manzil (viloyat, tuman, ko'cha) *"),
                ("masul", "Mas'ul shaxs"))
    for i, (k, nom) in enumerate(qatorlar):
        tk.Label(f, text=nom, bg="#0f1422", fg="#cfd6ea", font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w", pady=3)
        v = tk.StringVar()
        if k == "turi":
            v.set(demo.TURLAR[0])
            ttk.Combobox(f, textvariable=v, values=demo.TURLAR, state="readonly", width=32).grid(
                row=i, column=1, padx=(8, 0), pady=3)
        else:
            tk.Entry(f, textvariable=v, width=35, font=("Segoe UI", 10)).grid(row=i, column=1, padx=(8, 0), pady=3)
        maydon[k] = v
    v_roz = tk.BooleanVar(value=False)
    tk.Checkbutton(w, text="Ma'lumotlarim AzizMedLine'ga yuborilishiga roziman (internet bo'lganda)",
                   variable=v_roz, bg="#0f1422", fg="#cfd6ea", selectcolor="#1a2236", activebackground="#0f1422",
                   font=("Segoe UI", 9)).pack(anchor="w", padx=22)

    def _boshla():
        forma = {k: v.get().strip() for k, v in maydon.items()}
        if not forma["nomi"] or not forma["telefon"] or not forma["manzil"]:
            messagebox.showwarning("To'ldiring", "Klinika nomi, telefon va manzil kerak.", parent=w)
            return
        if not v_roz.get():
            messagebox.showwarning("Rozilik", "Boshlash uchun rozilik belgisini qo'ying.", parent=w)
            return
        d = demo.boshlat(forma)
        if d and not d["tugagan"]:
            natija["ok"] = True
            messagebox.showinfo("Tayyor", f"Sinov boshlandi: {max(1, d['qolgan_sek'] // 86400)} kun.\n"
                                "Dastur ochiladi.", parent=w)
            w.destroy()
        else:
            messagebox.showerror("Sinov tugagan", "Bu kompyuterda sinov muddati ILGARI ishlatilgan.\n"
                                 f"Litsenziya uchun: {ALOQA_TELEFON}  {ALOQA_TELEGRAM}", parent=w)
            w.destroy()
    tk.Button(w, text="🎁 Sinovni boshlash", command=_boshla, bg="#1f8a4c", fg="white", relief="flat",
              font=("Segoe UI Semibold", 11), cursor="hand2").pack(fill="x", padx=22, pady=(8, 14), ipady=6)
    w.transient(parent)
    w.grab_set()
    w.wait_window()
    return natija["ok"]


def _zaxira_ol(parent):
    """Demo/litsenziya tugagach ham mijoz o'z ma'lumotini saqlab qola oladi (egasi qarori)."""
    import threading
    from tkinter import messagebox
    try:
        import baza_zaxira
    except Exception:
        messagebox.showwarning("Zaxira", "Zaxira moduli bu dasturda yo'q — Registratsiya orqali oling.", parent=parent)
        return
    natija = {}

    def _ish():
        try:
            natija.update(baza_zaxira.eksport(sabab="litsenziya tugagan") or {})
        except Exception as e:
            natija.update({"ok": False, "xabar": str(e)})
    t = threading.Thread(target=_ish, daemon=True)
    t.start()

    def _kut():
        if t.is_alive():
            parent.after(500, _kut)
        elif natija.get("ok"):
            messagebox.showinfo("💾 Zaxira olindi", f"{natija.get('fayl', '')}\n\nFaylni saqlab qo'ying.", parent=parent)
        else:
            messagebox.showerror("Zaxira olinmadi", str(natija.get("xabar") or "noma'lum xato"), parent=parent)
    _kut()


def demo_kuzat(root):
    """Oyna ochilgach chaqiriladi (Registratsiya, Natija). Demo: sarlavhada «N kun qoldi»,
    oxirgi 3 kunda HAR SOATDA ogohlantirish. Pullik litsenziya: bazaga belgi (keyin qo'shilgan
    kompyuter 3 kunlik muhlat olsin). Faqat EXE da; xato dasturga ta'sir qilmaydi."""
    if not getattr(sys, "frozen", False):
        return
    import threading
    import time as _t
    holat = {"oxirgi_xabar": 0.0, "fon": False, "belgi": False, "tugadi": False}

    def _xabar(matn, sarlavha):
        import tkinter as tk
        w = tk.Toplevel(root)
        w.title(sarlavha)
        w.configure(bg="#fff3e0")
        w.resizable(False, False)
        tk.Label(w, text=matn, bg="#fff3e0", fg="#b71c1c", font=("Segoe UI Semibold", 11), justify="left",
                 wraplength=460).pack(padx=18, pady=(14, 6))
        tk.Label(w, text=f"{ALOQA_TELEFON}   {ALOQA_TELEGRAM}", bg="#fff3e0", fg="#333",
                 font=("Segoe UI", 10)).pack()
        r = tk.Frame(w, bg="#fff3e0")
        r.pack(pady=12)
        tk.Button(r, text="📨 Litsenziya so'rash", bg="#1f8a4c", fg="white", font=("Segoe UI Semibold", 10),
                  command=lambda: sorov_oynasi(w, lm.holatni_tekshir(online=False))).pack(side="left", padx=6)
        tk.Button(r, text="Yopish", command=w.destroy).pack(side="left", padx=6)
        w.attributes("-topmost", True)
        w.after(1500, lambda: w.attributes("-topmost", False))

    def _tick():
        try:
            n = lm.holatni_tekshir(online=False)
            p = n.payload or {}
            if p.get("tarif") == "DEMO":
                if not holat["fon"]:
                    holat["fon"] = True
                    demo.fon_ishga_tushir()
                sek = max(0, int(p.get("expires_at", 0)) - int(_t.time()))
                kun = sek // 86400 + (1 if sek % 86400 else 0)
                sarlavha = root.title().split("  —  DEMO")[0]
                root.title(f"{sarlavha}  —  DEMO: {kun} kun qoldi" if n.yaroqli else f"{sarlavha}  —  DEMO TUGAGAN")
                if not n.yaroqli and not holat["tugadi"]:
                    holat["tugadi"] = True
                    _xabar("Sinov muddati tugadi. Dastur keyingi ochilishda ishlamaydi — ma'lumotlaringiz "
                           "saqlanadi. Litsenziya oling.", "Sinov muddati tugadi")
                elif n.yaroqli and sek <= 3 * 86400 and _t.time() - holat["oxirgi_xabar"] >= 3600:
                    holat["oxirgi_xabar"] = _t.time()
                    _xabar(f"Sinov muddati tugashiga {kun} kun qoldi!\nTugagach dastur ishlamaydi. "
                           "Ma'lumotlar saqlanadi — litsenziya oling.", "⚠ Sinov tugayapti")
            elif n.yaroqli and not holat["belgi"]:
                holat["belgi"] = True
                threading.Thread(target=demo.pullik_belgila, daemon=True, name="pullik_belgi").start()
        except Exception:
            pass
        try:
            root.after(60_000, _tick)
        except Exception:
            pass
    root.after(5000, _tick)


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
    en, bo = 520, 610
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

    # Birinchi marta (izi yo'q kompyuter) — eng avval BEPUL sinov: kompyuterni yaxshi
    # bilmaydigan odam birinchi tugmani bosadi
    sinov_mumkin = natija.holat == lm.Holat.YOQ and demo.boshlash_mumkinmi(natija.machine_id)
    if sinov_mumkin:
        lbl("👋", font=("Segoe UI", 30)).pack(pady=(16, 2))
        lbl("Xush kelibsiz!", font=("Segoe UI Semibold", 15)).pack()
        lbl(f"Dasturni {demo.DEMO_KUN} kun bepul sinab ko'ring yoki litsenziya o'rnating.", fg="#9fe0b8",
            font=("Segoe UI", 10), wraplength=460).pack(pady=(4, 8))

        def _demo_bosh():
            if demo_oynasi(oyna):
                holat["ok"] = True
                oyna.destroy()
        tk.Button(oyna, text=f"🎁 {demo.DEMO_KUN} kunlik BEPUL sinovni boshlash", command=_demo_bosh, bg="#0e9f6e",
                  fg="white", relief="flat", font=("Segoe UI Semibold", 12), cursor="hand2"
                  ).pack(fill="x", padx=26, pady=(0, 8), ipady=10)
    else:
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
    tk.Button(oyna, text="📨 Litsenziya so'rash (internet orqali)",
              command=lambda: sorov_oynasi(oyna, natija), bg="#8a5a1f", fg="white", relief="flat",
              font=("Segoe UI Semibold", 10), cursor="hand2").pack(fill="x", padx=26, pady=4, ipady=7)
    if natija.holat == lm.Holat.MUDDATI_TUGAGAN:
        # Ish to'xtaydi, lekin mijoz o'z ma'lumotini saqlab qola oladi (egasi qarori)
        tk.Button(oyna, text="💾 Zaxira olish (ma'lumotlarim)", command=lambda: _zaxira_ol(oyna), bg="#2a3350",
                  fg="#e6e9f2", relief="flat", font=("Segoe UI Semibold", 10), cursor="hand2"
                  ).pack(fill="x", padx=26, pady=4, ipady=7)

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
