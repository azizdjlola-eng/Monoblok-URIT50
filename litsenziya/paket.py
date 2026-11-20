# -*- coding: utf-8 -*-
"""
KATALOG PAKETI — demo'da namunaviy, pullik litsenziyada to'liq (v1.0.73, `docs/HIMOYA_v1073_REJA.md` 4).

Mijoz buildida EXE yonida ochiq `katalog_seed.json`/`norma_seed.json` YO'Q. O'rniga:
  • demo_paket.json   — eng ko'p ishlatiladigan ~35 xizmat va ularning normalari (demo uchun yetarli);
  • toliq_paket.azp   — to'liq katalog + normalar, AES-256-GCM bilan shifrlangan.

Kalit faqat AzizMedLine VPS'ida (`/paket/kalit`) — pullik, bloklanmagan, muddati o'tmagan litsenziya va
egalik isboti bilan beriladi. Olingan kalit shu kompyuterda DPAPI (LOCAL_MACHINE) bilan saqlanadi — fayl
boshqa kompyuterga ko'chirilsa ochilmaydi. Bizning o'z buildimiz (bizniki/filial) ochiq seed bilan
ishlaydi — bu modul faqat ochiq seed bo'lmaganda ishlatiladi (`norma_seed`).

Format (.azp): {"v":1, "kid":"k1", "n":"<b64 nonce>", "ct":"<b64>"}; ochiq matn —
{"katalog":[...], "normalar":[...], "versiya":"..."}; AAD = b"AZML-PAKET-v1|" + kid.
"""
import base64
import hashlib
import json
import os
import sys
import time

DEMO_NOM = "demo_paket.json"
TOLIQ_NOM = "toliq_paket.azp"
AAD_BOSH = b"AZML-PAKET-v1|"
_kesh = {}


def _fayl_yoli(nom: str) -> str:
    """EXE yonida yoki _internal ichida (PyInstaller datas); kodda — loyiha ildizi/build/mijoz."""
    nomzod = []
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        nomzod += [os.path.join(base, nom), os.path.join(base, "_internal", nom)]
        mp = getattr(sys, "_MEIPASS", None)
        if mp:
            nomzod.append(os.path.join(mp, nom))
        # Qo'riqchi (Sozlama\BazaSozlamasi.exe) — paket Registratsiya ichida turadi
        ildiz = os.path.dirname(base)
        for komp in ("Registratsiya", "Natija"):
            nomzod += [os.path.join(ildiz, komp, "_internal", nom), os.path.join(ildiz, komp, nom)]
    nomzod.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), nom))
    for p in nomzod:
        if os.path.isfile(p):
            return p
    return ""


def demo_bormi() -> bool:
    return bool(_fayl_yoli(DEMO_NOM))


def demo_yukla() -> dict:
    p = _fayl_yoli(DEMO_NOM)
    if not p:
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# ── shifrlash (build va mijoz uchun bir xil) ──
def shifrla(ochiq: dict, kalit: bytes, kid: str) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    n = os.urandom(12)
    ct = AESGCM(kalit).encrypt(n, json.dumps(ochiq, ensure_ascii=False).encode("utf-8"),
                               AAD_BOSH + kid.encode("ascii"))
    return {"v": 1, "kid": kid, "n": base64.b64encode(n).decode("ascii"),
            "ct": base64.b64encode(ct).decode("ascii")}


def och(paket: dict, kalit: bytes) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    n = base64.b64decode(paket["n"])
    ct = base64.b64decode(paket["ct"])
    ochiq = AESGCM(kalit).decrypt(n, ct, AAD_BOSH + str(paket["kid"]).encode("ascii"))
    return json.loads(ochiq.decode("utf-8"))


def _toliq_paket() -> dict:
    p = _fayl_yoli(TOLIQ_NOM)
    if not p:
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("kid") else {}
    except Exception:
        return {}


# ── kalit keshi (DPAPI LOCAL_MACHINE: shu kompyuterda istalgan foydalanuvchi ochadi, boshqa PC — yo'q) ──
def _kesh_yoli(kid: str) -> str:
    try:
        from . import yollar
        pd = yollar.umumiy_papka()
    except Exception:
        pd = os.path.join(os.environ.get("ProgramData") or r"C:\ProgramData", "AzizMedLine")
    return os.path.join(pd, "himoya", f"pk_{kid}.bin")


def _dpapi(b: bytes, shifr: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    kirish = BLOB(len(b), ctypes.cast(ctypes.create_string_buffer(b, len(b)), ctypes.POINTER(ctypes.c_char)))
    chiqish = BLOB()
    entropiya_b = b"AZML-PAKET-KESH"
    ent = BLOB(len(entropiya_b), ctypes.cast(ctypes.create_string_buffer(entropiya_b, len(entropiya_b)),
                                            ctypes.POINTER(ctypes.c_char)))
    crypt = ctypes.windll.crypt32
    fn = crypt.CryptProtectData if shifr else crypt.CryptUnprotectData
    # 0x4 = CRYPTPROTECT_LOCAL_MACHINE, 0x1 = UI_FORBIDDEN
    ok = fn(ctypes.byref(kirish), None, ctypes.byref(ent), None, None, 0x5 if shifr else 0x1,
            ctypes.byref(chiqish))
    if not ok:
        raise OSError("DPAPI xato")
    try:
        return ctypes.string_at(chiqish.pbData, chiqish.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(chiqish.pbData)


def _kesh_oqi(kid: str) -> bytes:
    try:
        with open(_kesh_yoli(kid), "rb") as f:
            k = _dpapi(f.read(), False)
        return k if len(k) == 32 else b""
    except Exception:
        return b""


def _kesh_yoz(kid: str, kalit: bytes) -> bool:
    try:
        p = _kesh_yoli(kid)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(_dpapi(kalit, True))
        return True
    except Exception:
        return False


def _egalik() -> str:
    """litsenziya_manager._online_tekshir bilan bir xil isbot: qo'ldagi .azlic imzosining sha256 i."""
    from . import litsenziya_manager as lm
    fayl = lm.faylni_top()
    if not fayl:
        return ""
    with open(fayl, "r", encoding="utf-8") as f:
        return hashlib.sha256(str(json.load(f).get("imzo", "")).strip().lower().encode("ascii")).hexdigest()


def pullikmi() -> bool:
    try:
        from . import litsenziya_manager as lm
        n = lm.holatni_tekshir(online=False)
        return bool(n.yaroqli and str((n.payload or {}).get("tarif") or "").upper() != "DEMO")
    except Exception:
        return False


def kalit_ol(timeout: float = 6) -> bytes:
    """To'liq paket kaliti: keshdan, bo'lmasa (pullik litsenziyada) VPS'dan. b"" — yo'q."""
    pk = _toliq_paket()
    if not pk:
        return b""
    kid = str(pk["kid"])
    k = _kesh_oqi(kid)
    if k:
        return k
    if not pullikmi():
        return b""
    # 1) Pullik litsenziya faylining o'zida (2026-11-21 dan beriladigan litsenziyalar) — internetsiz
    try:
        from . import litsenziya_manager as lm
        with open(lm.faylni_top(), "r", encoding="utf-8") as f:
            lp = json.load(f)
        payload, holat = lm._blobni_tekshir(lp, lm._mid.mashina_id())
        hx = ((payload or {}).get("pk") or {}).get(kid) if holat == "ok" else ""
        if hx and len(hx) == 64:
            k = bytes.fromhex(hx)
            och(pk, k)
            _kesh_yoz(kid, k)
            return k
    except Exception:
        pass
    # 2) VPS'dan (eski litsenziya; VPS'ga push qilingan bo'lishi kerak) — 6 soatda bir urinish
    urinish = _kesh_yoli(kid) + ".urinish"
    try:
        if time.time() - os.path.getmtime(urinish) < 6 * 3600:
            return b""
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(urinish), exist_ok=True)
        with open(urinish, "w") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass
    try:
        import urllib.parse
        import urllib.request
        from . import server_config
        from . import mashina_id
        q = urllib.parse.urlencode({"mid": mashina_id.mashina_id(), "egalik": _egalik(), "kid": kid})
        with urllib.request.urlopen(server_config.vps_url().rstrip("/") + "/paket/kalit?" + q, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8") or "{}")
        hx = (j.get("kalitlar") or {}).get(kid) if j.get("ok") else ""
        if not hx or len(hx) != 64:
            return b""
        k = bytes.fromhex(hx)
        och(pk, k)                                  # kalit to'g'riligini tekshirish
        _kesh_yoz(kid, k)
        return k
    except Exception:
        return b""


def toliq_yukla() -> dict:
    """To'liq paket (ochilgan) yoki {} — kalit faqat keshdan (startni internetga bog'lamaslik uchun)."""
    if "toliq" in _kesh:
        return _kesh["toliq"]
    pk = _toliq_paket()
    d = {}
    if pk:
        k = _kesh_oqi(str(pk["kid"]))
        if k:
            try:
                d = och(pk, k)
            except Exception:
                d = {}
    if d:
        _kesh["toliq"] = d
    return d


def katalog_va_normalar():
    """(katalog, normalar, manba) — mijoz buildi uchun. manba: 'toliq' | 'demo' | ''."""
    d = toliq_yukla()
    if d:
        return d.get("katalog") or [], d.get("normalar") or [], "toliq"
    d = demo_yukla()
    if d:
        return d.get("katalog") or [], d.get("normalar") or [], "demo"
    return [], [], ""


def kerak_bolsa_toliqqa_otkaz(log=lambda m: None) -> bool:
    """Fon (himoya oqimi, Qo'riqchi): pullik litsenziya bor-u to'liq paket hali ochilmagan bo'lsa —
    kalitni VPS'dan oladi va bazaga to'liq katalogni qo'shadi (mavjud tahlil/narxlar buzilmaydi).
    True — hozir ochildi."""
    pk = _toliq_paket()
    if not pk or _kesh_oqi(str(pk["kid"])):
        return False
    if not kalit_ol():
        return False
    _kesh.pop("toliq", None)
    try:
        import norma_seed
        n = norma_seed.seed_avto()
        log(f"paket: to'liq katalog ochildi, bazaga {n} ta yozuv qo'shildi")
    except Exception as e:
        log(f"paket: kalit olindi, seed keyingi ochilishda ({e})")
    try:
        import himoya_hodisa
        himoya_hodisa.qayd("holat", "To'liq katalog ochildi (pullik litsenziya)", {"paket": pk.get("kid")},
                           daraja=0, takror_sek=0)
    except Exception:
        pass
    return True
