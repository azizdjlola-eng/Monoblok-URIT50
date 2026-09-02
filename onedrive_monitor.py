# -*- coding: utf-8 -*-
"""
OneDrive sinxronizatsiya nazorati (natija PDF lari haqiqatan bulutga chiqyaptimi?).

MUAMMO: Natija yetkazish zanjiri —
    PDF yaratiladi -> OneDrive\\Natijalar\\DD.MM.YYYY -> OneDrive sinxronizatsiya
    -> nargi kompyuter fayllarni ko'radi -> bemorga SMS.
Zanjirning eng zaif bo'g'ini OneDrive.exe: u crash bo'lsa yoki "Вход" da
osilib qolsa HECH QANDAY xato chiqmaydi. Dastur normal ishlayveradi, PDF lar
yaratilaveradi, lekin internetga chiqmaydi va SMS ketmaydi. Bu bir necha bor
soatlab sezilmay qolgan.

YECHIM: fayl bulutga chiqqanini QANDAY bilamiz?
    OneDrive yuklab bo'lgan faylni "placeholder" ga aylantiradi va unga
    FILE_ATTRIBUTE_REPARSE_POINT (0x400) atributini qo'yadi.
    Yangi yaratilgan, hali yuklanmagan faylda bu atribut YO'Q.
    Demak: fayl yaratilganiga N daqiqa bo'ldi-yu, hali ham reparse yo'q
    -> u bulutga CHIQMAGAN.

Nazorat 3 bosqich:
    1. OneDrive.exe jarayoni umuman bormi?
    2. Natijalar papkasi umuman OneDrive ichidami?
    3. Bugungi/kechagi fayllar orasida "osilib qolgan" bormi?

Chegaralar `alert_config.json` -> "onedrive" bo'limida (kodga tegmasdan).
"""

import os
import sys
import json
import time
import threading
import datetime
import subprocess

# ── Papka (manba yoki EXE) ────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(BASE_DIR, "alert_config.json")
_BLANKA_CFG_PATH = os.path.join(BASE_DIR, "blanka_config.json")
_STATE_PATH = os.path.join(BASE_DIR, "onedrive_monitor_state.json")

FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

_NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

DEFAULT_CONFIG = {
    "enabled": True,
    # Necha daqiqada bir tekshirish
    "check_interval_min": 10,
    # Fayl shuncha daqiqadan beri sinxronlanmagan bo'lsa — DIQQAT
    "pending_warn_min": 20,
    # Shuncha daqiqadan beri sinxronlanmagan bo'lsa — XATO (ovoz + popup)
    "pending_crit_min": 45,
    # Bir xil muammo haqida takror ogohlantirish oralig'i (daqiqa)
    "repeat_alert_min": 30,
    # Ogohlantirish uchun oxirgi necha kunlik papka tekshiriladi
    "check_days": 3,
    # Hisobot uchun necha kunlik papka ko'riladi
    "report_days": 14,
    # OneDrive.exe o'chiq bo'lsa avtomatik qayta ishga tushirish
    "auto_restart": True,
    # Ovoz / popup (alert_config dagi umumiy sound_file ishlatiladi)
    "sound": True,
    "popup": True,
    # Faqat DIQQAT darajasida ham popup chiqsinmi? (False = faqat rang o'zgaradi,
    # popup faqat haqiqiy XATO da chiqadi — bekorga chalg'itmaslik uchun)
    "alert_on_warn": False,
}

_CFG_CACHE = [None]


def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(force=False):
    """alert_config.json -> "onedrive" bo'limi (bo'lmasa DEFAULT_CONFIG)."""
    if _CFG_CACHE[0] is not None and not force:
        return _CFG_CACHE[0]
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                whole = json.load(f)
            cfg = _deep_merge(cfg, whole.get("onedrive", {}))
    except Exception as e:
        print(f"[OneDrive] Konfig o'qishda xato: {e}")
    _CFG_CACHE[0] = cfg
    return cfg


# ── Holat fayli (placeholder ko'rilganmi va h.k.) ─────────────────────────
def _load_state():
    try:
        if os.path.exists(_STATE_PATH):
            with open(_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(state):
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════
#  YO'LLAR
# ══════════════════════════════════════════════════════════════════════════
def get_onedrive_root():
    """OneDrive ildiz papkasi (env -> registry -> home)."""
    root = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if root and os.path.isdir(root):
        return root
    try:
        ps = ("(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\OneDrive' "
              "-Name UserFolder -ErrorAction SilentlyContinue).UserFolder")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=10,
                           creationflags=_NO_WIN)
        path = (r.stdout or "").strip()
        if path and os.path.isdir(path):
            return path
    except Exception:
        pass
    cand = os.path.join(os.path.expanduser("~"), "OneDrive")
    return cand if os.path.isdir(cand) else ""


def get_natijalar_root():
    """Natija PDF lari saqlanadigan ildiz papka.
    Blanka sozlamasidagi pdf_save_dir ustun (monoblok_dastur bilan bir xil mantiq).
    """
    try:
        if os.path.exists(_BLANKA_CFG_PATH):
            with open(_BLANKA_CFG_PATH, "r", encoding="utf-8") as f:
                custom = (json.load(f).get("pdf_save_dir", "") or "").strip()
            if custom:
                return custom
    except Exception:
        pass
    root = get_onedrive_root()
    if root:
        return os.path.join(root, "Natijalar")
    return ""


def is_inside_onedrive(path):
    """Natijalar papkasi umuman OneDrive ichidami? (bo'lmasa sinxronizatsiya yo'q)"""
    od = get_onedrive_root()
    if not od or not path:
        return False
    try:
        a = os.path.normcase(os.path.abspath(path))
        b = os.path.normcase(os.path.abspath(od))
        return a == b or a.startswith(b + os.sep)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════
#  JARAYON
# ══════════════════════════════════════════════════════════════════════════
def is_onedrive_running():
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OneDrive.exe", "/NH"],
                           capture_output=True, text=True, timeout=20,
                           creationflags=_NO_WIN)
        return "OneDrive.exe" in (r.stdout or "")
    except Exception as e:
        print(f"[OneDrive] Jarayonni tekshirishda xato: {e}")
        return True  # tekshira olmadik — yolg'on signal bermaymiz


def _onedrive_exe():
    for p in [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "OneDrive", "OneDrive.exe"),
        r"C:\Program Files\Microsoft OneDrive\OneDrive.exe",
        r"C:\Program Files (x86)\Microsoft OneDrive\OneDrive.exe",
    ]:
        if p and os.path.isfile(p):
            return p
    return None


def restart_onedrive():
    """OneDrive.exe ni qayta ishga tushirish. Qaytaradi: (True/False, xabar)"""
    exe = _onedrive_exe()
    if not exe:
        return False, "OneDrive.exe topilmadi"
    try:
        if is_onedrive_running():
            subprocess.run(["taskkill", "/IM", "OneDrive.exe", "/F"],
                           capture_output=True, timeout=25, creationflags=_NO_WIN)
            time.sleep(2)
        subprocess.Popen([exe, "/background"], creationflags=_NO_WIN)
        return True, "OneDrive qayta ishga tushirildi"
    except Exception as e:
        return False, f"Qayta ishga tushirishda xato: {e}"


# ══════════════════════════════════════════════════════════════════════════
#  PAPKA SKANERI
# ══════════════════════════════════════════════════════════════════════════
class _ExposePlaceholders:
    """Joriy OQIM uchun OneDrive placeholder larini "ochiq" rejimga o'tkazadi.

    Windows sukut bo'yicha har bir jarayonga placeholder larni ODDIY FAYL qilib
    ko'rsatadi (PHCM_DISGUISE_PLACEHOLDER) — eski dasturlar buzilmasligi uchun.
    Shu sababli GetFileAttributesW ham, os.scandir ham 0x20 (Archive) qaytaradi va
    sinxronlangan faylni sinxronlanmagandan ajratib bo'lmaydi.
    RtlSetThreadPlaceholderCompatibilityMode(2) — FAQAT shu oqim uchun — haqiqiy
    atributlarni ochadi (0x420 = Archive|ReparsePoint). Chiqishda oldingi rejim
    tiklanadi, ya'ni dasturning boshqa qismlariga ta'sir qilmaydi.
    """

    PHCM_EXPOSE = 2

    def __init__(self):
        self._prev = None
        self._fn = None

    def __enter__(self):
        try:
            import ctypes
            nt = ctypes.WinDLL("ntdll")
            fn = nt.RtlSetThreadPlaceholderCompatibilityMode
            fn.argtypes = [ctypes.c_char]
            fn.restype = ctypes.c_char
            self._prev = fn(ctypes.c_char(bytes([self.PHCM_EXPOSE])))
            self._fn = fn
        except Exception as e:
            print(f"[OneDrive] Placeholder rejimini o'zgartirib bo'lmadi: {e}")
        return self

    def __exit__(self, *exc):
        try:
            if self._fn is not None and self._prev is not None:
                self._fn(self._prev)
        except Exception:
            pass
        return False


def _list_raw(path):
    """Papkani FindFirstFileW orqali o'qiydi — (nom, atributlar, o'zgargan_vaqt).

    os.scandir ishlatilmaydi: CPython reparse bitini o'zi tozalab yuboradi
    (reparse tag symlink/junction emasligi uchun), ya'ni sinxronizatsiya
    belgisi yo'qoladi. FindFirstFileW xom atributlarni beradi.
    """
    import ctypes
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD),
                    ("dwHighDateTime", wintypes.DWORD)]

    class _WIN32_FIND_DATAW(ctypes.Structure):
        _fields_ = [("dwFileAttributes", wintypes.DWORD),
                    ("ftCreationTime", _FILETIME),
                    ("ftLastAccessTime", _FILETIME),
                    ("ftLastWriteTime", _FILETIME),
                    ("nFileSizeHigh", wintypes.DWORD),
                    ("nFileSizeLow", wintypes.DWORD),
                    ("dwReserved0", wintypes.DWORD),
                    ("dwReserved1", wintypes.DWORD),
                    ("cFileName", wintypes.WCHAR * 260),
                    ("cAlternateFileName", wintypes.WCHAR * 14)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.FindFirstFileW.restype = wintypes.HANDLE
    k32.FindFirstFileW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_WIN32_FIND_DATAW)]
    k32.FindNextFileW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_WIN32_FIND_DATAW)]
    k32.FindClose.argtypes = [wintypes.HANDLE]

    INVALID = wintypes.HANDLE(-1).value
    data = _WIN32_FIND_DATAW()
    h = k32.FindFirstFileW(os.path.join(path, "*"), ctypes.byref(data))
    if h == INVALID:
        return []

    def _unix(ft):
        v = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        return (v - 116444736000000000) / 10000000.0 if v else 0.0

    out = []
    try:
        while True:
            if data.cFileName not in (".", ".."):
                out.append((data.cFileName, int(data.dwFileAttributes),
                            _unix(data.ftLastWriteTime)))
            if not k32.FindNextFileW(h, ctypes.byref(data)):
                break
    finally:
        k32.FindClose(h)
    return out


def _day_folders(natijalar_root, days):
    """Natijalar ichidagi DD.MM.YYYY papkalari — eng yangisidan boshlab, `days` ta."""
    out = []
    if not natijalar_root or not os.path.isdir(natijalar_root):
        return out
    try:
        for name in os.listdir(natijalar_root):
            full = os.path.join(natijalar_root, name)
            if not os.path.isdir(full):
                continue
            try:
                d = datetime.datetime.strptime(name, "%d.%m.%Y").date()
            except ValueError:
                continue
            out.append((d, full))
    except Exception as e:
        print(f"[OneDrive] Papkalarni o'qishda xato: {e}")
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:days] if days else out


def scan_folder(path, now_ts=None):
    """Bitta kun papkasi: jami / sinxronlangan / kutayotgan fayllar."""
    now_ts = now_ts or time.time()
    total = synced = 0
    pending = []  # [(nom, yosh_daqiqa)]
    try:
        with _ExposePlaceholders():
            rows = _list_raw(path)
        for name, attrs, mtime in rows:
            if attrs & FILE_ATTRIBUTE_DIRECTORY:
                continue
            if not name.lower().endswith((".pdf", ".docx")):
                continue
            total += 1
            if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                # OneDrive faylni placeholder qilgan = bulutga yuklangan
                synced += 1
            else:
                age = (now_ts - mtime) / 60.0 if mtime else 0.0
                pending.append((name, max(age, 0.0)))
    except Exception as e:
        print(f"[OneDrive] Papka skanerida xato ({path}): {e}")
    pending.sort(key=lambda x: -x[1])
    return {"path": path, "total": total, "synced": synced, "pending": pending}


def _fod_seen(natijalar_root, state):
    """Bu kompyuterda OneDrive placeholder (Files On-Demand) ishlatiladimi?

    Bir marta ko'rilgan bo'lsa holat faylida eslab qolinadi — chunki uzoq
    uzilishda oxirgi kunlarning HAMMASI sinxronlanmagan bo'lishi mumkin va
    "placeholder yo'q ekan" deb signalni butunlay o'chirib qo'yish xavfli.
    """
    if state.get("fod_seen"):
        return True
    for _d, folder in _day_folders(natijalar_root, 45):
        if scan_folder(folder)["synced"] > 0:
            state["fod_seen"] = True
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════
#  ASOSIY TEKSHIRUV
# ══════════════════════════════════════════════════════════════════════════
def check(cfg=None, days=None):
    """OneDrive natija sinxronizatsiyasini tekshiradi.

    Qaytaradi dict:
        level    — 'ok' | 'warn' | 'crit'
        problems — [str] muammolar ro'yxati
        summary  — bir qatorli xulosa
        stats    — {natijalar_root, process, total, synced, pending, folders, ...}
    """
    cfg = cfg or load_config()
    state = _load_state()
    now_ts = time.time()

    natijalar_root = get_natijalar_root()
    stats = {"natijalar_root": natijalar_root, "process": None, "total": 0,
             "synced": 0, "pending": 0, "oldest_min": 0.0, "folders": [],
             "examples": []}
    problems = []
    level = "ok"

    if not natijalar_root or not os.path.isdir(natijalar_root):
        return {"level": "warn",
                "problems": ["Natijalar papkasi topilmadi: " + (natijalar_root or "(aniqlanmadi)")],
                "summary": "Natijalar papkasi yo'q", "stats": stats}

    in_od = is_inside_onedrive(natijalar_root)
    stats["in_onedrive"] = in_od
    if not in_od:
        # PDF lar OneDrive dan tashqariga saqlanmoqda — bulutga umuman chiqmaydi
        return {"level": "warn",
                "problems": ["Natijalar OneDrive papkasida EMAS:\n   " + natijalar_root +
                             "\n   Bu papka bulutga sinxronlanmaydi — SMS ham ketmaydi."],
                "summary": "Natijalar papkasi OneDrive dan tashqarida",
                "stats": stats}

    # 1) Jarayon
    running = is_onedrive_running()
    stats["process"] = running
    if not running:
        problems.append("OneDrive.exe ISHLAMAYAPTI — hech narsa bulutga chiqmaydi.")
        level = "crit"

    # 2) Papkalarni skanerlash
    fod = _fod_seen(natijalar_root, state)
    stats["fod"] = fod
    day_count = days or int(cfg.get("check_days", 3) or 3)
    all_pending = []
    for d, folder in _day_folders(natijalar_root, day_count):
        st = scan_folder(folder, now_ts)
        stats["total"] += st["total"]
        stats["synced"] += st["synced"]
        stats["folders"].append({"kun": d.strftime("%d.%m.%Y"), "jami": st["total"],
                                 "sinxron": st["synced"], "kutmoqda": len(st["pending"])})
        for nm, age in st["pending"]:
            all_pending.append((d, nm, age))

    stats["pending"] = len(all_pending)
    if all_pending:
        all_pending.sort(key=lambda x: -x[2])
        stats["oldest_min"] = all_pending[0][2]
        stats["examples"] = ["{}  ({} daq.)".format(nm, int(age)) for _d, nm, age in all_pending[:5]]

    if fod:
        warn_min = float(cfg.get("pending_warn_min", 20) or 20)
        crit_min = float(cfg.get("pending_crit_min", 45) or 45)
        old = [p for p in all_pending if p[2] >= warn_min]
        very_old = [p for p in all_pending if p[2] >= crit_min]
        if very_old:
            problems.append(
                "{} ta natija {} daqiqadan beri bulutga CHIQMAGAN — "
                "sinxronizatsiya to'xtagan.".format(len(very_old), int(very_old[0][2])))
            level = "crit"
        elif old:
            problems.append(
                "{} ta natija hali sinxronlanmagan (eng eskisi {} daq.) — "
                "kuzatilmoqda.".format(len(old), int(old[0][2])))
            if level != "crit":
                level = "warn"
    else:
        # Placeholder belgisi hech qachon ko'rilmagan — atribut bo'yicha hukm
        # qilib bo'lmaydi (Files On-Demand o'chiq bo'lishi mumkin).
        stats["note"] = ("Sinxronizatsiya belgisi (placeholder) topilmadi — "
                         "fayl darajasidagi tekshiruv o'chiq, faqat jarayon tekshirilmoqda.")

    _save_state(state)

    if level == "ok":
        summary = "OneDrive ishlayapti — {}/{} natija bulutda".format(stats["synced"], stats["total"])
    elif level == "warn":
        summary = "OneDrive: {} natija navbatda".format(stats["pending"])
    else:
        summary = "OneDrive SINXRONLAMAYAPTI — {} natija bulutga chiqmagan".format(stats["pending"])

    return {"level": level, "problems": problems, "summary": summary, "stats": stats}


def format_report(res):
    """Tekshiruv natijasini o'qiladigan matnga aylantiradi."""
    s = res.get("stats", {})
    icon = {"ok": "[OK]", "warn": "[DIQQAT]", "crit": "[XATO]"}.get(res.get("level"), "")
    lines = ["{} {}".format(icon, res.get("summary", "")), ""]
    for p in res.get("problems", []):
        lines.append("  • " + p)
    if res.get("problems"):
        lines.append("")
    lines.append("Papka: " + str(s.get("natijalar_root", "")))
    lines.append("OneDrive.exe: " + ("ishlayapti" if s.get("process") else "ISHLAMAYAPTI"))
    if s.get("folders"):
        lines.append("")
        lines.append("Kunlar bo'yicha:")
        for f in s["folders"]:
            mark = "OK" if f["kutmoqda"] == 0 else "{} kutmoqda".format(f["kutmoqda"])
            lines.append("   {}:  {}/{} bulutda   ({})".format(
                f["kun"], f["sinxron"], f["jami"], mark))
    if s.get("examples"):
        lines.append("")
        lines.append("Chiqmagan natijalar (eng eskisi):")
        for e in s["examples"]:
            lines.append("   - " + e)
    if s.get("note"):
        lines.append("")
        lines.append(s["note"])
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
#  KUZATUVCHI OQIM
# ══════════════════════════════════════════════════════════════════════════
class OneDriveWatcher:
    """Fon oqimida davriy tekshiradi va muammo topilsa callback chaqiradi.

    on_status(res)  — HAR tekshiruvdan keyin (holat ko'rsatkichini yangilash uchun)
    on_alert(res)   — faqat muammo bo'lganda va takror oralig'i o'tgan bo'lsa
    Ikkalasi ham fon oqimidan chaqiriladi — tkinter uchun root.after() bilan o'rang.
    """

    def __init__(self, on_alert=None, on_status=None, cfg=None):
        self.on_alert = on_alert
        self.on_status = on_status
        self.cfg = cfg or load_config()
        self._stop = threading.Event()
        self._thread = None
        self._last_alert_key = None
        self._last_alert_ts = 0.0
        self.last_result = None

    def start(self, first_delay_sec=60):
        if not self.cfg.get("enabled", True):
            print("[OneDrive] Nazorat o'chirilgan (alert_config.json)")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(first_delay_sec,), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def _loop(self, first_delay_sec):
        if self._stop.wait(first_delay_sec):
            return
        while not self._stop.is_set():
            try:
                self.check_now()
            except Exception as e:
                print(f"[OneDrive] Nazoratda xato: {e}")
            interval = float(self.cfg.get("check_interval_min", 10) or 10) * 60
            if self._stop.wait(max(interval, 60)):
                return

    def check_now(self, notify=True):
        cfg = load_config(force=True)
        self.cfg = cfg
        res = check(cfg)
        self.last_result = res
        print(f"[OneDrive] {res['summary']}")

        if self.on_status:
            try:
                self.on_status(res)
            except Exception as e:
                print(f"[OneDrive] status callback xato: {e}")

        if not notify or res["level"] not in ("warn", "crit"):
            return res
        if res["level"] == "warn" and not cfg.get("alert_on_warn", False):
            # Faqat ko'rsatkich rangi o'zgaradi — popup bilan chalg'itmaymiz
            return res

        # Jarayon o'lgan bo'lsa — avtomatik qayta yoqib ko'ramiz
        if cfg.get("auto_restart", True) and res["stats"].get("process") is False:
            ok, msg = restart_onedrive()
            print(f"[OneDrive] Avtomatik tiklash: {msg}")
            if ok:
                res["problems"].append("Avtomatik: " + msg +
                                       " — 2-3 daqiqadan keyin qayta tekshiriladi.")

        # Takror ogohlantirishni cheklash
        key = "{}|{}|{}".format(res["level"], res["stats"].get("process"), len(res["problems"]))
        gap = float(cfg.get("repeat_alert_min", 30) or 30) * 60
        now = time.time()
        if key == self._last_alert_key and (now - self._last_alert_ts) < gap:
            return res
        self._last_alert_key = key
        self._last_alert_ts = now

        if self.on_alert:
            try:
                self.on_alert(res)
            except Exception as e:
                print(f"[OneDrive] alert callback xato: {e}")
        return res


# ── Qo'lda test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("OneDrive natija sinxronizatsiyasini tekshirish...\n")
    r = check(days=int(load_config().get("report_days", 14)))
    print(format_report(r))
    print("\nDaraja: " + r["level"])
