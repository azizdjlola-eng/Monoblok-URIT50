# -*- coding: utf-8 -*-
"""
30 KUNLIK DEMO (egasi qarorlari, 2026-11-03/04).

  • Litsenziyasiz kompyuterda forma → «Sinovni boshlash»: darhol, internet shart emas.
  • Bir kompyuterga BIR MARTA: dastur o'chirib-o'rnatilsa ham yangi 30 kun berilmaydi —
    boshlangan sana bir nechta mustaqil joyda; topilgan ENG ERTA sana hal qiladi.
  • Klinikada hamma kompyuter BIR KUNDA tugaydi: sana umumiy bazada (`demo_holat`);
    qo'shimcha kompyuter o'sha sanani oladi.
  • Klinika sotib olgandan keyin qo'shilgan yangi kompyuter — 3 kunlik muhlat, bir marta.
  • Internet bo'lsa VPS hakam: temir ID bo'yicha birinchi sanani qaytaradi (Windows qayta
    o'rnatilsa ham). Forma ma'lumoti ham shu yerga boradi; internet yo'q bo'lsa navbatda.

MUHIM:
  • Demoda `data_key` YO'Q — baza_shifr kalitsiz shifrlamaydi, demo davridagi ma'lumot
    ochiq turadi va haqiqiy litsenziya qo'yilgach ham o'qiladi. VPS demoga data_key
    YARATMASIN: uy `_data_key_top` u kalitni bilmaydi, sotib olingach ma'lumot ochilmaydi.
  • `holat()` FAQAT lokal izlarni o'qiydi (tez): litsenziya_gate.ruxsat_bormi uni baza
    ulanishi yo'lida chaqiradi. Baza va VPS bilan tenglash — alohida (darvoza, fon oqimi).
"""
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request

try:
    import winreg
except ImportError:
    winreg = None

from cryptography.fernet import Fernet
import base64

from . import mashina_id as _mid
from . import yollar

DEMO_KUN = 30
MUHLAT_KUN = 3                # sotib olingandan keyin qo'shilgan yangi kompyuter
_REG_YOL = r"Software\AzizMedLine\Sys"     # HKCU (vaqt_himoya yonida)
_REG_YOL_LM = r"SOFTWARE\AzizMedLine\Sys"  # HKLM — installer Users ga yozish huquqini beradi
_REG_NOM = "dm"
_FAYL_NOM = ".demo_belgisi"
_NAVBAT_NOM = "demo_navbat.json"
_PROFIL_NOM = "klinika_profil.json"
_BAZA_SIR = b"AZML-DEMO-BAZA-v1"   # baza qiymatini qo'lda tahrirlashdan (HMAC)
TURLAR = ("Laboratoriya", "Klinika", "UZI kabinet", "Stomatologiya", "Boshqa")


# ═════════════════════════════════════════════════════════════════════════════
# LOKAL IZLAR
# ═════════════════════════════════════════════════════════════════════════════
def _kalit(mid: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(("DEMO-IZ::" + mid).encode()).digest())


def _shifrla(mid: str, b: int, k: int) -> str:
    return Fernet(_kalit(mid)).encrypt(json.dumps({"b": int(b), "k": int(k)}).encode()).decode()


def _och(mid: str, token: str):
    """(boshlangan, kun) yoki None. Buzilgan iz hisobga olinmaydi (vaqt_himoya kabi)."""
    try:
        d = json.loads(Fernet(_kalit(mid)).decrypt(str(token).strip().encode()).decode())
        return int(d["b"]), int(d["k"])
    except Exception:
        return None


def _fayllar() -> list:
    out = [os.path.join(yollar.umumiy_papka(), _FAYL_NOM)]
    la = os.environ.get("LOCALAPPDATA")
    if la:
        out.append(os.path.join(la, "AzizMedLine", _FAYL_NOM))
    return out


def _reglar() -> list:
    if winreg is None:
        return []
    return [(winreg.HKEY_LOCAL_MACHINE, _REG_YOL_LM), (winreg.HKEY_CURRENT_USER, _REG_YOL)]


def _reg_oqi(ildiz, yol):
    try:
        k = winreg.OpenKey(ildiz, yol)
        try:
            return winreg.QueryValueEx(k, _REG_NOM)[0]
        finally:
            winreg.CloseKey(k)
    except Exception:
        return None


def _reg_yoz(ildiz, yol, qiymat) -> bool:
    try:
        k = winreg.CreateKey(ildiz, yol)
        try:
            winreg.SetValueEx(k, _REG_NOM, 0, winreg.REG_SZ, qiymat)
        finally:
            winreg.CloseKey(k)
        return True
    except Exception:
        return False


def _izlar_xom(mid: str) -> list:
    out = []
    for f in _fayllar():
        try:
            with open(f, encoding="utf-8") as fh:
                v = _och(mid, fh.read())
            if v:
                out.append(v)
        except Exception:
            pass
    for ildiz, yol in _reglar():
        t = _reg_oqi(ildiz, yol)
        if t:
            v = _och(mid, t)
            if v:
                out.append(v)
    return out


def izlar_oqi(mid: str = None):
    """(boshlangan, kun) — eng erta boshlangan iz. Iz yo'q bo'lsa None.
    Muhlat (3 kun) va demo (30 kun) ikkalasi bo'lsa — ENG ERTA TUGAYDIGANI emas, eng
    erta boshlangani va uning kuni: bir kompyuterga ikkinchi imkoniyat berilmaydi."""
    mid = mid or _mid.mashina_id()
    iz = _izlar_xom(mid)
    return min(iz, key=lambda x: x[0]) if iz else None


def izlar_yoz(boshlangan: int, kun: int, mid: str = None) -> int:
    """Barcha joyga yozadi. Qaytaradi: nechta joyga yozildi. Hech qachon istisno otmaydi."""
    mid = mid or _mid.mashina_id()
    tok = _shifrla(mid, boshlangan, kun)
    n = 0
    for f in _fayllar():
        try:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(f, 0x80)   # NORMAL (yashirinni ochib yozish)
            except Exception:
                pass
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(tok)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(f, 0x2)    # HIDDEN
            except Exception:
                pass
            n += 1
        except Exception:
            pass
    for ildiz, yol in _reglar():
        if _reg_yoz(ildiz, yol, tok):
            n += 1
    return n


def holat(ishonchli_hozir: int = None, mid: str = None):
    """Demo holati (FAQAT lokal izlar — tez). Iz yo'q bo'lsa None."""
    iz = izlar_oqi(mid)
    if not iz:
        return None
    b, k = iz
    now = int(ishonchli_hozir or time.time())
    tugash = b + k * 86400
    return {"boshlangan": b, "kun": k, "tugash": tugash, "tugagan": now > tugash,
            "qolgan_sek": max(0, tugash - now), "muhlat": k == MUHLAT_KUN}


# ═════════════════════════════════════════════════════════════════════════════
# UMUMIY BAZA — klinikada hamma kompyuter bir kunda tugashi uchun
# ═════════════════════════════════════════════════════════════════════════════
def _imzo(b: int, k: int) -> str:
    return hmac.new(_BAZA_SIR, f"{int(b)}|{int(k)}".encode(), hashlib.sha256).hexdigest()


def _baza():
    """To'g'ridan-to'g'ri ulanish (litsenziya darvozasidan O'TMAYDI — darvozaning o'zi
    shu yerdan chaqiriladi). 3 s: server o'chiq bo'lsa start uzoq kutmasin."""
    try:
        import baza_sozlama
        import mysql.connector
        cfg = baza_sozlama.oqi()
        kw = dict(host=cfg.get("host", "127.0.0.1"), user=cfg.get("user", "root"),
                  password=cfg.get("password", ""), database=cfg.get("database", "lab_tizim"),
                  port=int(cfg.get("port", 3306) or 3306), connection_timeout=3, use_pure=True)
        try:
            kw.update(baza_sozlama.tls_kwargs(cfg))
        except Exception:
            pass
        c = mysql.connector.connect(**kw)
        cur = c.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS demo_holat (
                         kalit VARCHAR(32) PRIMARY KEY, qiymat VARCHAR(255),
                         yangilangan DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)""")
        cur.close()
        return c
    except Exception:
        return None


def _baza_oqi(c, kalit):
    """(boshlangan, kun) yoki None. HMAC mos kelmasa — hisobga olinmaydi."""
    try:
        cur = c.cursor()
        cur.execute("SELECT qiymat FROM demo_holat WHERE kalit=%s", (kalit,))
        r = cur.fetchone()
        cur.close()
        if not r or not r[0]:
            return None
        d = json.loads(r[0])
        if hmac.compare_digest(str(d.get("h", "")), _imzo(d["b"], d["k"])):
            return int(d["b"]), int(d["k"])
    except Exception:
        pass
    return None


def _baza_yoz(c, kalit, b: int, k: int):
    try:
        cur = c.cursor()
        q = json.dumps({"b": int(b), "k": int(k), "h": _imzo(b, k)})
        cur.execute("INSERT INTO demo_holat (kalit, qiymat) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE qiymat=VALUES(qiymat)", (kalit, q))
        c.commit()
        cur.close()
    except Exception:
        pass


def baza_bilan_tenglash(mid: str = None, conn=None) -> str:
    """Lokal izlar ↔ umumiy baza. Qaytaradi: nima bo'ldi (sinov/jurnal uchun):
      'baza_yoq' | 'tenglashdi' | 'bazadan_oldi' | 'muhlat' | 'bazaga_yozdi' | 'iz_yoq'."""
    mid = mid or _mid.mashina_id()
    c = conn or _baza()
    if c is None:
        return "baza_yoq"
    try:
        umumiy = _baza_oqi(c, "boshlangan")
        pullik = _baza_oqi(c, "pullik")
        iz = izlar_oqi(mid)
        if iz is None:
            if pullik:                       # klinika sotib olgan — yangi kompyuterga muhlat
                izlar_yoz(int(time.time()), MUHLAT_KUN, mid)
                return "muhlat"
            if umumiy:                       # klinikada demo ketyapti — o'sha sana
                izlar_yoz(umumiy[0], DEMO_KUN, mid)
                return "bazadan_oldi"
            return "iz_yoq"
        b, k = iz
        if k != DEMO_KUN:                    # muhlat — klinika sanasiga aralashmaydi
            return "tenglashdi"
        if umumiy is None or b < umumiy[0]:
            _baza_yoz(c, "boshlangan", b, DEMO_KUN)
            return "bazaga_yozdi"
        if umumiy[0] < b:
            izlar_yoz(umumiy[0], DEMO_KUN, mid)
            return "bazadan_oldi"
        return "tenglashdi"
    finally:
        if conn is None:
            try:
                c.close()
            except Exception:
                pass


def pullik_belgila(conn=None) -> bool:
    """Shu klinikada pullik litsenziya bor — keyin qo'shilgan kompyuter muhlat oladi."""
    c = conn or _baza()
    if c is None:
        return False
    try:
        if _baza_oqi(c, "pullik") is None:
            _baza_yoz(c, "pullik", int(time.time()), 0)
        return True
    finally:
        if conn is None:
            try:
                c.close()
            except Exception:
                pass


# ═════════════════════════════════════════════════════════════════════════════
# VPS — hakam va forma ma'lumoti
# ═════════════════════════════════════════════════════════════════════════════
def _navbat_yoli() -> str:
    return os.path.join(yollar.umumiy_papka(), _NAVBAT_NOM)


def _navbat_oqi() -> dict:
    try:
        with open(_navbat_yoli(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _navbat_yoz(d: dict):
    try:
        os.makedirs(os.path.dirname(_navbat_yoli()), exist_ok=True)
        tmp = _navbat_yoli() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _navbat_yoli())
    except Exception:
        pass


def _sir_yoli() -> str:
    return os.path.join(yollar.umumiy_papka(), ".lits_sir")


def sir_saqla(sir: str):
    """VPS bergan egalik belgisi: demo mijozda hali litsenziya yo'q, sotib olganda shu bilan
    isbotlaydi (paket ichida data_key bor — faqat egasiga beriladi)."""
    if not sir:
        return
    try:
        os.makedirs(os.path.dirname(_sir_yoli()), exist_ok=True)
        with open(_sir_yoli(), "w", encoding="utf-8") as f:
            f.write(str(sir).strip())
    except Exception:
        pass


def sir_oqi() -> str:
    try:
        with open(_sir_yoli(), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def vps_hakam(forma: dict = None, boshlangan: int = 0, timeout: int = 4):
    """VPS ga so'raydi/yuboradi. Javob dict yoki None (internet yo'q)."""
    from . import server_config
    import socket
    d = {"mid": _mid.mashina_id(), "temir": _mid.temir_id(), "boshlangan": int(boshlangan or 0),
         "kompyuter": socket.gethostname(), "forma": forma or {}}
    req = urllib.request.Request(server_config.vps_url() + "/demo/boshlash",
                                 data=json.dumps(d, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8") or "{}")
        if isinstance(j, dict) and j.get("sir"):
            sir_saqla(j["sir"])
        return j
    except Exception:
        return None


def vps_bilan_tenglash(timeout: int = 4) -> bool:
    """Navbatdagi formani yuboradi, VPS sanasi erta bo'lsa lokal izga oladi. True — javob keldi."""
    iz = izlar_oqi()
    if not iz:
        return False                  # demo boshlanmagan — VPS da yozuv ochilmasin
    nav = _navbat_oqi()
    j = vps_hakam(nav.get("forma") if not nav.get("yuborildi") else None, iz[0] if iz else 0, timeout)
    if not isinstance(j, dict) or not j.get("ok"):
        return False
    if nav and not nav.get("yuborildi"):
        nav["yuborildi"] = True
        _navbat_yoz(nav)
    vb = int(j.get("boshlangan") or 0)
    if vb and iz and vb < iz[0]:
        izlar_yoz(vb, iz[1])
    return True


# ═════════════════════════════════════════════════════════════════════════════
# BOSHLASH
# ═════════════════════════════════════════════════════════════════════════════
def boshlash_mumkinmi(mid: str = None) -> bool:
    return izlar_oqi(mid) is None


def boshlat(forma: dict) -> dict:
    """Formadan keyin. Avval VPS'dan so'raydi (bu temir ilgari demo olganmi — internet
    bo'lsa); javob bo'lmasa ham darhol boshlanadi. Qaytaradi: holat()."""
    now = int(time.time())
    if boshlash_mumkinmi():
        j = vps_hakam(forma, now, timeout=4)
        b = now
        yuborildi = False
        if isinstance(j, dict) and j.get("ok"):
            yuborildi = True
            b = min(now, int(j.get("boshlangan") or now))
        izlar_yoz(b, DEMO_KUN)
        _navbat_yoz({"forma": forma, "yuborildi": yuborildi, "vaqt": now})
        profil_saqla(forma)
        threading.Thread(target=baza_bilan_tenglash, daemon=True, name="demo_baza").start()
    return holat()


# ─── klinika profili: forma → chek/TV/Vrach (Registratsiya ochilganda qo'llanadi) ──
def _profil_yoli() -> str:
    return os.path.join(yollar.umumiy_papka(), _PROFIL_NOM)


def profil_saqla(forma: dict):
    try:
        os.makedirs(os.path.dirname(_profil_yoli()), exist_ok=True)
        with open(_profil_yoli(), "w", encoding="utf-8") as f:
            json.dump(dict(forma, qollandi=False), f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def profil_oqi() -> dict:
    try:
        with open(_profil_yoli(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def profil_belgila(**kv):
    d = profil_oqi()
    if d:
        d.update(kv)
        try:
            with open(_profil_yoli(), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except Exception:
            pass


def _yordamchi_fon():
    """Registratsiya ochiq turganda: baza va VPS bilan tenglash (start darrov, keyin har soat)."""
    while True:
        try:
            baza_bilan_tenglash()
            vps_bilan_tenglash(timeout=8)
        except Exception:
            pass
        time.sleep(3600)


def fon_ishga_tushir():
    t = threading.Thread(target=_yordamchi_fon, daemon=True, name="demo_tenglash")
    t.start()
    return t
