# -*- coding: utf-8 -*-
"""
Natija PDF lari qaysi bulutga sinxronlanadi — OneDrive yoki Google Drive.

Natija yetkazish zanjiri:
    PDF -> <bulut>\\Natijalar\\DD.MM.YYYY -> bulut sinxronizatsiya
        -> nargi kompyuter / bot -> bemor (SMS, keyinchalik Telegram).

Bulut Blanka Sozlamalarida tanlanadi (blanka_config.json):
    "bulut_provayder": "onedrive" | "gdrive"   (bo'sh/yo'q = onedrive)
    "gdrive_root": ""   — Google Drive ildizi qo'lda (bo'sh = avtomatik topish)
    "pdf_save_dir": ""  — PDF papkasi qo'lda (eng ustun, bulutdan qat'i nazar)

Google Drive for desktop ikki rejimda ishlaydi:
    • Stream (standart) — alohida virtual disk (masalan D:), yorlig'i "Google Drive",
      ichida "My Drive" / "Мой диск" (Windows tiliga qarab nomlanadi).
      DIQQAT: GoogleDriveFS.exe to'xtasa disk umuman YO'QOLADI.
    • Mirror — %USERPROFILE%\\My Drive (oddiy papka).
"""

import os
import sys
import json
import time
import subprocess

_NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ONEDRIVE = "onedrive"
GDRIVE = "gdrive"

PROVAYDERLAR = {
    ONEDRIVE: {"nomi": "OneDrive", "exe": "OneDrive.exe"},
    GDRIVE: {"nomi": "Google Drive", "exe": "GoogleDriveFS.exe"},
}

# Google Drive "Мой диск" papkasining turli tillardagi nomi
_GDRIVE_MY_DRIVE_NOMLARI = ("My Drive", "Мой диск", "Mening diskim", "Meine Ablage",
                            "Mon Drive", "Mi unidad", "Il mio Drive", "Diskim")


# ══════════════════════════════════════════════════════════════════════════
#  SOZLAMA (blanka_config.json)
# ══════════════════════════════════════════════════════════════════════════
def _blanka_config_yollari():
    """monoblok_dastur.CONFIG_FILE bilan bir xil tartib: EXE da ProgramData
    (yozish mumkin bo'lgan joy), koddan — skript yonida; keyin EXE ichidagi nusxa."""
    yollar = []
    try:
        import natija_papka as _np
        if _np.frozen():
            yollar.append(os.path.join(_np.sozlama_papka(), "blanka_config.json"))
            yollar.append(os.path.join(os.path.dirname(sys.executable), "blanka_config.json"))
        yollar.append(_np.ichki_fayl("blanka_config.json"))
    except Exception:
        pass
    yollar.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "blanka_config.json"))
    return yollar


def _blanka_config():
    for p in _blanka_config_yollari():
        try:
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    return d
        except Exception:
            continue
    return {}


def get_provider(cfg=None):
    """Tanlangan bulut: 'onedrive' (standart) yoki 'gdrive'."""
    cfg = cfg if cfg is not None else _blanka_config()
    p = (cfg.get("bulut_provayder") or ONEDRIVE).strip().lower()
    return p if p in PROVAYDERLAR else ONEDRIVE


def provider_nomi(provider=None):
    return PROVAYDERLAR[provider or get_provider()]["nomi"]


# ══════════════════════════════════════════════════════════════════════════
#  ILDIZ PAPKALAR
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


def _my_drive_ichida(ildiz):
    """Google Drive diski/papkasi ichidan "Мой диск" papkasini topadi."""
    for nom in _GDRIVE_MY_DRIVE_NOMLARI:
        p = os.path.join(ildiz, nom)
        if os.path.isdir(p):
            return p
    # Noma'lum til — yashirin/tizim bo'lmagan yagona papka
    try:
        nomzod = [n for n in os.listdir(ildiz)
                  if not n.startswith((".", "$")) and os.path.isdir(os.path.join(ildiz, n))]
        if len(nomzod) == 1:
            return os.path.join(ildiz, nomzod[0])
    except Exception:
        pass
    return ""


def _gdrive_disklari():
    """Yorlig'i "Google Drive" bo'lgan disklar (stream rejim)."""
    out = []
    try:
        import ctypes
        import string
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for i, harf in enumerate(string.ascii_uppercase):
            if not (mask >> i) & 1:
                continue
            ildiz = harf + ":\\"
            # Faqat mahalliy disklar — uzilgan tarmoq diskida GetVolumeInformation osilib qoladi
            if k32.GetDriveTypeW(ildiz) not in (2, 3):
                continue
            yorliq = ctypes.create_unicode_buffer(261)
            if k32.GetVolumeInformationW(ildiz, yorliq, 261, None, None, None, None, 0):
                if "google drive" in (yorliq.value or "").lower():
                    out.append(ildiz)
    except Exception as e:
        print(f"[Bulut] Disklarni ko'rishda xato: {e}")
    return out


def get_gdrive_root(cfg=None):
    """Google Drive "Мой диск" papkasi (qo'lda -> stream disk -> mirror papka)."""
    cfg = cfg if cfg is not None else _blanka_config()
    qolda = (cfg.get("gdrive_root") or "").strip()
    if qolda and os.path.isdir(qolda):
        return qolda
    for disk in _gdrive_disklari():
        p = _my_drive_ichida(disk)
        if p:
            return p
    home = os.path.expanduser("~")
    for nom in _GDRIVE_MY_DRIVE_NOMLARI:
        for p in (os.path.join(home, nom), os.path.join(home, "Google Drive", nom)):
            if os.path.isdir(p):
                return p
    return ""


def get_cloud_root(provider=None, cfg=None):
    cfg = cfg if cfg is not None else _blanka_config()
    provider = provider or get_provider(cfg)
    return get_gdrive_root(cfg) if provider == GDRIVE else get_onedrive_root()


def get_natijalar_root(cfg=None):
    """Natija PDF lari ildizi: pdf_save_dir (qo'lda) > <bulut>\\Natijalar.
    Bulut topilmasa '' qaytaradi."""
    cfg = cfg if cfg is not None else _blanka_config()
    qolda = (cfg.get("pdf_save_dir") or "").strip()
    if qolda:
        return qolda
    root = get_cloud_root(cfg=cfg)
    return os.path.join(root, "Natijalar") if root else ""


def is_inside_cloud(path, provider=None):
    """Papka tanlangan bulut ichidami? (bo'lmasa sinxronizatsiya yo'q)"""
    root = get_cloud_root(provider)
    if not root or not path:
        return False
    try:
        a = os.path.normcase(os.path.abspath(path))
        b = os.path.normcase(os.path.abspath(root))
        return a == b or a.startswith(b.rstrip(os.sep) + os.sep)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════
#  JARAYON (OneDrive.exe / GoogleDriveFS.exe)
# ══════════════════════════════════════════════════════════════════════════
def is_client_running(provider=None):
    exe = PROVAYDERLAR[provider or get_provider()]["exe"]
    try:
        r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                           capture_output=True, text=True, timeout=20,
                           creationflags=_NO_WIN)
        return exe.lower() in (r.stdout or "").lower()
    except Exception as e:
        print(f"[Bulut] Jarayonni tekshirishda xato: {e}")
        return True  # tekshira olmadik — yolg'on signal bermaymiz


def _client_buyruq(provider):
    """Klientni ishga tushirish buyrug'i (ro'yxat) yoki None."""
    if provider == GDRIVE:
        baza = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                            "Google", "Drive File Stream")
        launch = os.path.join(baza, "launch.bat")
        if os.path.isfile(launch):
            return ["cmd", "/c", launch]
        # Versiyali papkalardan eng yangisi: ...\Drive File Stream\132.0.0.0\GoogleDriveFS.exe
        try:
            def _v(n):
                try:
                    return tuple(int(x) for x in n.split("."))
                except ValueError:
                    return ()
            for v in sorted(os.listdir(baza), key=_v, reverse=True):
                exe = os.path.join(baza, v, "GoogleDriveFS.exe")
                if os.path.isfile(exe):
                    return [exe]
        except Exception:
            pass
        return None
    for p in [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "OneDrive", "OneDrive.exe"),
        r"C:\Program Files\Microsoft OneDrive\OneDrive.exe",
        r"C:\Program Files (x86)\Microsoft OneDrive\OneDrive.exe",
    ]:
        if p and os.path.isfile(p):
            return [p, "/background"]
    return None


def restart_client(provider=None):
    """Bulut klientini qayta ishga tushirish. Qaytaradi: (True/False, xabar)"""
    provider = provider or get_provider()
    info = PROVAYDERLAR[provider]
    cmd = _client_buyruq(provider)
    if not cmd:
        return False, f"{info['exe']} topilmadi"
    try:
        if is_client_running(provider):
            subprocess.run(["taskkill", "/IM", info["exe"], "/F"],
                           capture_output=True, timeout=25, creationflags=_NO_WIN)
            time.sleep(2)
        subprocess.Popen(cmd, creationflags=_NO_WIN)
        return True, f"{info['nomi']} qayta ishga tushirildi"
    except Exception as e:
        return False, f"Qayta ishga tushirishda xato: {e}"


if __name__ == "__main__":
    cfg = _blanka_config()
    print("Tanlangan bulut :", provider_nomi(get_provider(cfg)))
    print("OneDrive ildizi :", get_onedrive_root() or "(topilmadi)")
    print("Google Drive    :", get_gdrive_root(cfg) or "(topilmadi)")
    print("Natijalar papka :", get_natijalar_root(cfg) or "(topilmadi)")
    for p in PROVAYDERLAR:
        print(f"{PROVAYDERLAR[p]['exe']:<18}:", "ishlayapti" if is_client_running(p) else "ISHLAMAYAPTI")
