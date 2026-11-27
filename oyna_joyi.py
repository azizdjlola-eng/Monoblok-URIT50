# -*- coding: utf-8 -*-
"""
Oynani ekranga SIG'DIRIB, markazda ochish — noutbukda ham, katta monitorda ham.

NEGA KERAK (03.11.2026): «Xizmatlar boshqaruvi», «Tizim nazorati», «Offline
navbat» oynalari qat'iy o'lcham bilan (yoki «zoomed») ochilardi: noutbukda
pastki tugmalar vazifalar paneli ostida qolar, Offline navbat esa ekranning
chap-yuqori burchagida chiqardi. Ekran o'lchami emas, ISH MAYDONI (vazifalar
panelisiz qism) olinadi — oynaning hamma qismi doim ko'rinadi.

UMUMIY HIMOYA (28.11.2026, Sardorbek: «Blanka sozlamalari»da Saqlash ko'rinmadi):
217 ta oyna qat'iy o'lchamda (geometry("750x750")) ochiladi, 41 tasi noutbukka
sig'maydi (docs/EKRAN_MOSLASHUV_VA_YORDAM.md). Har birini alohida tuzatish
o'rniga `ornat()` dastur boshida BIR MARTA chaqiriladi: shundan keyin har bir
oyna (Tk va Toplevel) ko'ringan zahoti o'z monitorining ish maydoniga
sig'diriladi — kerak bo'lsa kichraytiriladi va ekran ichiga suriladi.

EXE'lar DPI belgisisiz: Windows masshtabi 150% bo'lsa Full HD noutbukni dastur
1280×720 deb ko'radi. Barcha hisob shu (Windows bergan) koordinatalarda.

Sinov: AZIZ_ISH_MAYDONI=1280x680 muhit o'zgaruvchisi bilan katta monitorda
ham kichik noutbuk ekrani soxtalashtiriladi (oynalar shu o'lchamga qisiladi).
"""
import os

SARLAVHA = 40     # Windows sarlavha qatori + ramka (geometry ularni hisoblamaydi)
CHET = 20         # ish maydoni chetidan bo'sh joy

_ORNATILGAN = False
_YOZILGAN = set()       # jurnalga bir marta yozilgan oyna nomlari


def _soxta_maydon():
    """AZIZ_ISH_MAYDONI="1280x680" → (0, 0, 1280, 680); yo'q bo'lsa None."""
    v = (os.environ.get("AZIZ_ISH_MAYDONI") or "").lower().strip()
    if "x" not in v:
        return None
    try:
        en, boy = (int(s) for s in v.split("x", 1))
        if en >= 400 and boy >= 300:
            return 0, 0, en, boy
    except Exception:
        pass
    return None


def ish_maydoni(win):
    """(x, y, en, bo'y) — ekranning vazifalar panelisiz qismi.
    Windows'da SPI_GETWORKAREA (Tk bilan bir xil DPI koordinatalarida),
    boshqa holatda — ekran o'lchami, pastdan vazifalar paneli uchun joy."""
    s = _soxta_maydon()
    if s:
        return s
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            if r.right - r.left > 200 and r.bottom - r.top > 200:
                return r.left, r.top, r.right - r.left, r.bottom - r.top
    except Exception:
        pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight() - 60


def monitor_maydoni(win):
    """Oyna turgan MONITORning ish maydoni (ikki monitorli kompyuterda oyna
    asosiy monitorga tortib olinmasin). Topilmasa — ish_maydoni()."""
    s = _soxta_maydon()
    if s:
        return s
    try:
        import ctypes
        from ctypes import wintypes

        class _MI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        hwnd = int(win.wm_frame(), 16)
        u = ctypes.windll.user32
        u.MonitorFromWindow.restype = ctypes.c_void_p
        hmon = u.MonitorFromWindow(ctypes.c_void_p(hwnd), 2)   # MONITOR_DEFAULTTONEAREST
        mi = _MI()
        mi.cbSize = ctypes.sizeof(_MI)
        if hmon and u.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
            r = mi.rcWork
            if r.right - r.left > 200 and r.bottom - r.top > 200:
                return r.left, r.top, r.right - r.left, r.bottom - r.top
    except Exception:
        pass
    return ish_maydoni(win)


def joylash(win, en, boy, min_en=None, min_boy=None):
    """Oynani en×boy o'lchamda (ish maydoniga sig'masa — kichraytirib) ekran
    markaziga qo'yadi. min_en/min_boy — foydalanuvchi bundan kichraytira olmaydi
    (ular ham ish maydonidan oshmaydi). Haqiqiy (en, bo'y) qaytaradi."""
    x0, y0, W, H = ish_maydoni(win)
    ww = max(200, min(int(en), W - 2 * CHET))
    wh = max(150, min(int(boy), H - SARLAVHA - CHET))
    x = x0 + (W - ww) // 2
    y = y0 + max(0, (H - wh - SARLAVHA) // 2)
    win.geometry(f"{ww}x{wh}+{x}+{y}")
    if min_en or min_boy:
        win.minsize(min(int(min_en or 200), ww), min(int(min_boy or 150), wh))
    return ww, wh


def kichik_bolsa_yoy(win, en, boy):
    """Ekran en×boy oynaga sig'masa — oynani butun ekranga yoyadi (zoomed).
    Katta monitorda hech narsa o'zgarmaydi. True — yoyildi."""
    try:
        _x, _y, W, H = ish_maydoni(win)
        if en > W or boy + SARLAVHA > H:
            win.state("zoomed")
            return True
    except Exception:
        pass
    return False


# ───────────────────────── umumiy himoya ─────────────────────────
def _masshtab():
    """Windows masshtabi (100/125/150...) — jurnal uchun; bilinmasa 0."""
    try:
        import ctypes
        return int(ctypes.windll.shcore.GetScaleFactorForDevice(0))
    except Exception:
        return 0


def _jurnalga(win, w, h, nw, nh, W, H):
    try:
        nom = str(win.title() or win.winfo_class())
    except Exception:
        nom = "?"
    if nom in _YOZILGAN:
        return
    _YOZILGAN.add(nom)
    try:
        import xizmat_jurnali
        m = _masshtab()
        xizmat_jurnali.log(f"[EKRAN] Oyna ekranga sig'madi va qisildi: «{nom}» {w}x{h} → "
                           f"{nw}x{nh}; ish maydoni {W}x{H}"
                           + (f", masshtab {m}%" if m else ""))
    except Exception:
        pass


def sigdir(win):
    """Oynani o'z monitorining ish maydoniga sig'diradi: kattaligi oshsa —
    kichraytiradi, chetdan chiqqan bo'lsa — ichkariga suradi. Hech qachon xato
    otmaydi. True — oyna o'zgartirildi."""
    try:
        if not win.winfo_exists() or not win.winfo_ismapped():
            return False
        if win.state() in ("zoomed", "iconic", "withdrawn"):
            return False
        if win.overrideredirect():
            return False            # maslahat (tooltip), ochiluvchi ro'yxat, splash
        try:
            if win.attributes("-fullscreen"):
                return False        # TV / kiosk to'liq ekran
        except Exception:
            pass
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        if w <= 1 or h <= 1:
            return False
        fx, fy = win.winfo_x(), win.winfo_y()
        ust = win.winfo_rooty() - fy          # sarlavha qatori
        yon = win.winfo_rootx() - fx          # yon ramka
        if not 0 < ust < 100:
            ust = 32
        if not 0 <= yon < 20:
            yon = 8
        x0, y0, W, H = monitor_maydoni(win)
        maxw = max(200, W - 2 * yon)
        maxh = max(150, H - ust - yon)
        nw, nh = min(w, maxw), min(h, maxh)
        try:
            mw, mh = win.minsize()
            if mw > nw or mh > nh:
                win.minsize(min(mw, nw), min(mh, nh))
        except Exception:
            pass
        nx = min(max(fx, x0), x0 + W - (nw + 2 * yon))
        ny = min(max(fy, y0), y0 + H - (nh + ust + yon))
        if (nw, nh, nx, ny) == (w, h, fx, fy):
            return False
        win.geometry(f"{nw}x{nh}+{nx}+{ny}")
        if (nw, nh) != (w, h):
            _jurnalga(win, w, h, nw, nh, W, H)
        return True
    except Exception:
        return False


def _bogla(interp):
    """Bitta Tcl interpretatori (har bir tk.Tk()) uchun Map bog'lamasi."""
    def _map(e):
        try:
            w = e.widget
            if isinstance(w, str):
                w = interp.nametowidget(w)
            w.after(30, lambda: sigdir(w))
        except Exception:
            pass
    try:
        if getattr(interp, "_oyna_joyi_boglandi", False):
            return
        interp.bind_class("Toplevel", "<Map>", _map, add="+")
        interp.bind_class(interp.winfo_class(), "<Map>", _map, add="+")
        interp._oyna_joyi_boglandi = True
    except Exception:
        pass


def ornat(root=None):
    """Dastur boshida chaqiriladi (qayta chaqirish zararsiz): shu jarayondagi
    HAR BIR oyna ko'ringanda ekranga sig'diriladi. Keyin yaratiladigan tk.Tk()
    lar ham (masalan, login oynasi, keyin asosiy oyna) qamraladi."""
    global _ORNATILGAN
    try:
        import tkinter as tk
        if not _ORNATILGAN:
            asl_init = tk.Tk.__init__

            def _init(self, *a, **k):
                asl_init(self, *a, **k)
                _bogla(self)
            tk.Tk.__init__ = _init
            _ORNATILGAN = True
        if root is None:
            root = getattr(tk, "_default_root", None)
        if root is not None:
            _bogla(root)
            try:
                root.after(50, lambda: sigdir(root))
            except Exception:
                pass
    except Exception:
        pass


# ───────────────────── aylanadigan (scroll) ramka ─────────────────────
def aylanma_ramka(ota, bg=None):
    """(tashqi, ichki) qaytaradi. Mazmun `ichki` ga joylanadi, `tashqi` ni
    chaqiruvchi o'zi pack/grid qiladi. Mazmun sig'sa — aylantirgich ko'rinmaydi
    va oyna oldingidek ko'rinadi; sig'masa — o'ng tomonda aylantirgich chiqadi,
    sichqoncha g'ildiragi ishlaydi."""
    import tkinter as tk
    from tkinter import ttk

    if bg is not None:
        tashqi = tk.Frame(ota, bg=bg)
        cv = tk.Canvas(tashqi, highlightthickness=0, borderwidth=0, bg=bg)
        ichki = tk.Frame(cv, bg=bg)
    else:
        tashqi = ttk.Frame(ota)
        cv = tk.Canvas(tashqi, highlightthickness=0, borderwidth=0)
        ichki = ttk.Frame(cv)
    sb = ttk.Scrollbar(tashqi, orient="vertical", command=cv.yview)
    oyna = cv.create_window((0, 0), window=ichki, anchor="nw")
    cv.configure(yscrollcommand=sb.set)
    cv.pack(side="left", fill="both", expand=True)

    def _yangila(_e=None):
        try:
            rw, rh = ichki.winfo_reqwidth(), ichki.winfo_reqheight()
            if int(cv.cget("width")) != rw or int(cv.cget("height")) != rh:
                cv.configure(width=rw, height=rh)     # tabiiy o'lcham = mazmun o'lchami
            ch = cv.winfo_height()
            # Katta ekranda mazmun oldingidek butun balandlikni egallaydi
            # (expand=True bo'lgan ro'yxat/jadvallar cho'ziladi), kichikda — aylanadi
            bal = max(rh, ch) if ch > 1 else rh
            cv.itemconfigure(oyna, height=bal)
            cv.configure(scrollregion=(0, 0, rw, bal))
            kerak = ch > 1 and rh > ch + 2
            if kerak and not sb.winfo_ismapped():
                sb.pack(side="right", fill="y", before=cv)
            elif not kerak and sb.winfo_ismapped():
                sb.pack_forget()
                cv.yview_moveto(0)
        except Exception:
            pass

    def _cv_olcham(e):
        try:
            cv.itemconfigure(oyna, width=e.width)
        except Exception:
            pass
        _yangila()

    ichki.bind("<Configure>", _yangila, add="+")
    cv.bind("<Configure>", _cv_olcham, add="+")

    def _gildirak(e):
        try:
            if not sb.winfo_ismapped() or not cv.winfo_exists():
                return
            w = e.widget
            if isinstance(w, str):
                w = cv.nametowidget(w)
            if w.winfo_class() in ("Text", "Listbox", "Treeview", "TCombobox", "Scale", "TScale"):
                return          # o'zi aylanadigan maydon
            if w.winfo_class() == "Canvas" and w is not cv:
                return          # ichkaridagi o'z aylantirgichli ro'yxat
            # faqat shu ramka ichidagi sichqoncha
            x, y = cv.winfo_pointerxy()
            if not (cv.winfo_rootx() <= x < cv.winfo_rootx() + cv.winfo_width()
                    and cv.winfo_rooty() <= y < cv.winfo_rooty() + cv.winfo_height()):
                return
            cv.yview_scroll(int(-1 * (e.delta / 120)) or (-1 if e.delta > 0 else 1), "units")
        except Exception:
            pass

    try:
        ota.winfo_toplevel().bind("<MouseWheel>", _gildirak, add="+")
    except Exception:
        pass
    tashqi.ichki = ichki
    tashqi.canvas = cv
    return tashqi, ichki
