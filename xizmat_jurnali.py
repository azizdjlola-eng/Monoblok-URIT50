# -*- coding: utf-8 -*-
"""
Muammolar jurnali — texnik xodim (AnyDesk orqali) uchun YAGONA doimiy joy.

    %ProgramData%\\AzizMedLine\\jurnal\\
        Registratsiya.log, TVServer.log, ...  — xatolar, qulashlar (to'liq
                                               traceback), ishga tushish/to'xtash
        holat.txt                            — bir qarashda: litsenziya, MySQL,
                                               TV/Vrach porti, disk, zaxira

Nega shu joy:
  • Dastur C:\\ ga ham, D:\\ ga ham o'rnatilishi mumkin — jurnal baribir shu yerda.
  • Dastur o'chirilsa ham qoladi (uninstaller ProgramData ga tegmaydi).
  • EXE (PyInstaller) da `__file__` vaqtinchalik _MEIPASS ga ishora qiladi —
    Registratsiyaning eski `logs\\lims.log` i dastur yopilishi bilan o'chardi.

Qoidalar:
  • Har dastur O'Z faylida. Bitta faylga bir necha jarayon yozsa Windows'da
    aylantirish (rotation) PermissionError beradi.
  • Fayl hajmi cheklangan (5 MB × 3) — yillar davomida diskni to'ldirmaydi.
  • Faqat WARNING va undan yuqori + `jurnal` loggerining INFO yozuvlari
    tushadi (oddiy INFO shovqini emas).
  • Bemor telefoni yozilmasin: telefon raqamlari avtomatik yashiriladi.
"""

import os
import re
import sys
import socket
import logging
import platform
import threading
import datetime
from logging.handlers import RotatingFileHandler

LOGGER_NOMI = "jurnal"
_FAYL_HAJM = 5 * 1024 * 1024
_FAYL_SONI = 3

_handler = None
_dastur = ""


def jurnal_papka() -> str:
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(pd, "AzizMedLine", "jurnal")


def logger() -> logging.Logger:
    lg = logging.getLogger(LOGGER_NOMI)
    lg.setLevel(logging.INFO)
    return lg


def log(matn: str, daraja: int = logging.INFO):
    """Qisqa yo'l: xizmat_jurnali.log("TV server ishga tushdi")."""
    try:
        logger().log(daraja, matn)
    except Exception:
        pass


# ───────────────────────── Telefonni yashirish ─────────────────────────
_TELEFON_RE = (
    # +998 90 123 45 67 / 998901234567 / +998(90)123-45-67
    re.compile(r"\+?998[\s\-]?\(?\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
    # 90 123 45 67 / 90-123-45-67
    re.compile(r"(?<!\d)\d{2}[\s\-]\d{3}[\s\-]\d{2}[\s\-]\d{2}(?!\d)"),
    # 901234567 (operator kodi bilan 9 xona)
    re.compile(r"(?<!\d)(?:20|33|50|55|61|62|65|66|67|69|70|71|72|73|74|75|76|77|78|79"
               r"|88|90|91|93|94|95|97|98|99)\d{7}(?!\d)"),
)


def telefonni_yashir(matn: str) -> str:
    for r in _TELEFON_RE:
        matn = r.sub("***TELEFON***", matn)
    return matn


class _Formatlovchi(logging.Formatter):
    def format(self, record):
        return telefonni_yashir(super().format(record))


class _Saralovchi(logging.Filter):
    """WARNING+ hammasi; INFO faqat `jurnal` loggeridan."""
    def filter(self, record):
        return (record.levelno >= logging.WARNING
                or record.name == LOGGER_NOMI
                or record.name.startswith(LOGGER_NOMI + "."))


# ───────────────────────── Versiya ─────────────────────────
def versiya() -> str:
    """Dastur versiyasi: bundle'dagi versiya.txt → manba → o'rnatma reyestri."""
    nomzodlar = []
    mei = getattr(sys, "_MEIPASS", None)
    if mei:
        nomzodlar.append(os.path.join(mei, "versiya.txt"))
    if getattr(sys, "frozen", False):
        nomzodlar.append(os.path.join(os.path.dirname(sys.executable), "versiya.txt"))
    nomzodlar.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "versiya.txt"))
    for p in nomzodlar:
        try:
            with open(p, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except Exception:
            pass
    # Inno Setup «DisplayVersion» (Dasturlar va imkoniyatlar ro'yxatidagi)
    try:
        import winreg
        kalit = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for kor in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, kalit, 0, winreg.KEY_READ | kor)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    nom = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    sk = winreg.OpenKey(k, nom)
                    dn = winreg.QueryValueEx(sk, "DisplayName")[0]
                    if "azizmedline" in str(dn).lower():
                        return str(winreg.QueryValueEx(sk, "DisplayVersion")[0])
                except OSError:
                    continue
    except Exception:
        pass
    return "?"


# ───────────────────────── Sozlash ─────────────────────────
def sozla(dastur: str) -> logging.Logger:
    """Dastur boshida BIR MARTA chaqiriladi (qayta chaqirish zararsiz).

    Jurnal faylini ulaydi, ushlanmagan xatolarni (asosiy oqim + ishchi
    oqimlar) to'liq traceback bilan yozdiradi va «ishga tushdi» qatorini
    qo'yadi. Hech qachon dasturni yiqitmaydi."""
    global _handler, _dastur
    lg = logger()
    if _handler is not None:
        return lg
    _dastur = dastur
    try:
        papka = jurnal_papka()
        os.makedirs(papka, exist_ok=True)
        h = RotatingFileHandler(os.path.join(papka, f"{dastur}.log"),
                                maxBytes=_FAYL_HAJM, backupCount=_FAYL_SONI,
                                encoding="utf-8", delay=True)
        h.setLevel(logging.INFO)
        h.addFilter(_Saralovchi())
        h.setFormatter(_Formatlovchi(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
        logging.getLogger().addHandler(h)
        _handler = h
    except Exception:
        return lg

    _eski_hook = sys.excepthook

    def _hook(tur, qiymat, tb):
        try:
            lg.critical("USHLANMAGAN XATO (dastur yiqildi)", exc_info=(tur, qiymat, tb))
        except Exception:
            pass
        _eski_hook(tur, qiymat, tb)
    sys.excepthook = _hook

    if hasattr(threading, "excepthook"):
        _eski_thook = threading.excepthook

        def _thook(args):
            try:
                lg.error(f"Fon oqimida xato ({getattr(args.thread, 'name', '?')})",
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            except Exception:
                pass
            _eski_thook(args)
        threading.excepthook = _thook

    try:
        exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        lg.info(f"===== {dastur} ishga tushdi | v{versiya()} | PID {os.getpid()} | "
                f"{socket.gethostname()} | {platform.platform()} | {exe}")
    except Exception:
        pass

    import atexit
    atexit.register(lambda: log(f"===== {dastur} yopildi"))
    return lg


def tk_ulash(root):
    """Tkinter tugma/after ichidagi xatolar ham jurnalga tushsin (odatda ular
    faqat konsolga chiqadi — pythonw/EXE da esa hech qayerga)."""
    _eski = getattr(root, "report_callback_exception", None)

    def _rce(tur, qiymat, tb):
        try:
            logger().error("Oyna (tkinter) ichida xato", exc_info=(tur, qiymat, tb))
        except Exception:
            pass
        if _eski:
            try:
                _eski(tur, qiymat, tb)
            except Exception:
                pass
    try:
        root.report_callback_exception = _rce
    except Exception:
        pass


# ───────────────────────── holat.txt ─────────────────────────
def _port_ochiq(host: str, port: int, kutish: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=kutish):
            return True
    except Exception:
        return False


def _xizmat_ornatilganmi(papka: str, exe: str):
    """None = aniqlab bo'lmadi (dev rejim)."""
    if not getattr(sys, "frozen", False):
        return None
    ildiz = os.path.dirname(os.path.dirname(sys.executable))
    return os.path.exists(os.path.join(ildiz, papka, exe))


def _oxirgi_xatolar(soni: int = 8) -> list:
    papka = jurnal_papka()
    qatorlar = []
    try:
        fayllar = [os.path.join(papka, f) for f in os.listdir(papka) if f.endswith(".log")]
    except Exception:
        return []
    for f in fayllar:
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                for q in fh:
                    if "[ERROR]" in q or "[CRITICAL]" in q:
                        qatorlar.append(q.rstrip())
        except Exception:
            pass
    qatorlar.sort()          # qator sana bilan boshlanadi → vaqt tartibi
    return qatorlar[-soni:]


def holat_matni(dastur: str = "") -> str:
    """holat.txt mazmuni. Har tekshiruv o'z try ichida — bittasi yiqilsa
    qolganlari baribir yoziladi."""
    q = []
    hozir = datetime.datetime.now()
    q.append("AzizMedLine — HOLAT")
    q.append("=" * 60)
    q.append(f"Yozildi:     {hozir:%Y-%m-%d %H:%M:%S}  ({dastur or _dastur or '?'} tomonidan)")
    q.append(f"Kompyuter:   {socket.gethostname()}")
    q.append(f"Windows:     {platform.platform()}")
    q.append(f"Versiya:     {versiya()}")
    if getattr(sys, "frozen", False):
        q.append(f"O'rnatilgan: {os.path.dirname(os.path.dirname(sys.executable))}")
    q.append("")

    # Litsenziya
    try:
        from litsenziya import litsenziya_manager as _lm
        n = _lm.holatni_tekshir(online=False)
        exp = (n.payload or {}).get("expires_at") if getattr(n, "payload", None) else None
        tugash = ""
        if exp:
            try:
                tugash = f", tugash {datetime.datetime.fromtimestamp(int(exp)):%Y-%m-%d}"
            except Exception:
                pass
        belgi = "✅" if n.yaroqli else "❌"
        q.append(f"{belgi} Litsenziya: {n.xabar}{tugash}")
        q.append(f"   Kompyuter ID: {n.machine_id}")
    except Exception as e:
        q.append(f"⚠️ Litsenziya: tekshirib bo'lmadi ({e})")

    # Baza
    cfg = None
    try:
        import baza_sozlama
        cfg = baza_sozlama.oqi()
        manzil = f"{cfg.get('host')}:{cfg.get('port')} / {cfg.get('database')} (user: {cfg.get('user')})"
        ok, xabar = baza_sozlama.test_ulanish(cfg)
        q.append(f"{'✅' if ok else '❌'} MySQL: {manzil}" + ("" if ok else f" — {xabar}"))
        if str(cfg.get("host", "")).lower() in ("127.0.0.1", "localhost", "::1"):
            xh = baza_sozlama._sc_holat()
            matn = {"running": "ishlayapti", "stopped": "TO'XTAGAN",
                    "yoq": "o'rnatilmagan"}.get(xh, xh)
            q.append(f"{'✅' if xh == 'running' else '❌'} MySQL xizmati: {matn}")
    except Exception as e:
        q.append(f"⚠️ MySQL: tekshirib bo'lmadi ({e})")

    # Xizmatlar (shu kompyuterda)
    for nom, papka, exe, port in (("TV server", "TVServer", "AzizMedTVServer.exe", 8765),
                                  ("Vrach kabineti", "VrachKabineti", "VrachKabineti.exe", 8090)):
        try:
            ornatilgan = _xizmat_ornatilganmi(papka, exe)
            if ornatilgan is False:
                q.append(f"➖ {nom}: shu kompyuterga o'rnatilmagan")
                continue
            if _port_ochiq("127.0.0.1", port):
                q.append(f"✅ {nom}: ishlayapti ({port}-port)")
            else:
                q.append(f"❌ {nom}: javob bermayapti ({port}-port) — ishga tushmagan yoki yiqilgan")
        except Exception as e:
            q.append(f"⚠️ {nom}: tekshirib bo'lmadi ({e})")

    # Disk
    try:
        import shutil
        disklar = []
        for d in ("C:\\", os.path.splitdrive(sys.executable)[0] + "\\"):
            if d not in disklar and os.path.exists(d):
                disklar.append(d)
        for d in disklar:
            u = shutil.disk_usage(d)
            gb = u.free / 1024 ** 3
            q.append(f"{'✅' if gb >= 2 else '❌'} Disk {d} bo'sh joy: {gb:.1f} GB")
    except Exception as e:
        q.append(f"⚠️ Disk: tekshirib bo'lmadi ({e})")

    # Zaxira
    try:
        import baza_zaxira
        q.append(baza_zaxira.holat_qatori())
    except Exception as e:
        q.append(f"⚠️ Zaxira: tekshirib bo'lmadi ({e})")

    q.append("")
    q.append("Oxirgi xatolar (barcha dasturlar):")
    xatolar = _oxirgi_xatolar()
    if xatolar:
        q.extend("  " + x for x in xatolar)
    else:
        q.append("  (yo'q)")
    q.append("")
    q.append(f"To'liq jurnal: {jurnal_papka()}")
    return telefonni_yashir("\n".join(q)) + "\n"


def holat_yoz(dastur: str = "") -> str:
    """holat.txt ni qayta yozadi (atomar). Yo'lini qaytaradi."""
    papka = jurnal_papka()
    os.makedirs(papka, exist_ok=True)
    yol = os.path.join(papka, "holat.txt")
    vaqt = yol + ".tmp"
    with open(vaqt, "w", encoding="utf-8") as f:
        f.write(holat_matni(dastur))
    os.replace(vaqt, yol)
    return yol


def holat_yoz_fonda(dastur: str = ""):
    """Startni sekinlashtirmaslik uchun — fon oqimida."""
    def _ish():
        try:
            holat_yoz(dastur)
        except Exception as e:
            log(f"holat.txt yozilmadi: {e}", logging.WARNING)
    threading.Thread(target=_ish, name="holat_txt", daemon=True).start()


if __name__ == "__main__":
    sozla("Sinov")
    print(holat_matni("Sinov"))
