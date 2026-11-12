# -*- coding: utf-8 -*-
"""VPS xizmatlariga HTTPS (2026-11-11).

VPS'da 45-130-148-66.sslip.io uchun Let's Encrypt sertifikati bor (nginx 443,
vps_https_yollar.sh). Xizmatlar shu domen ostida prefiks bilan:

    /lims/          → filial sinxroni (eski http://45.130.148.66:8770)
    /litsenziya-x/  → litsenziya xizmati (eski http://45.130.148.66:5679)
    /masofa/        → masofaviy yordam relay (eski http://45.130.148.66:5680)

Eski Windows'da (yangilanmagan) Let's Encrypt ildiz sertifikati bo'lmasligi
mumkin — shunda HTTPS ulanmaydi. tanla() bir marta TLS bilan ulanib ko'radi
va natijani eslab qoladi: ishlasa HTTPS, bo'lmasa eski HTTP manzil.
"""
import socket
import ssl
import time

DOMEN = "45-130-148-66.sslip.io"
ASOS = f"https://{DOMEN}"
ESKI_IP = "45.130.148.66"

LIMS_HTTPS = ASOS + "/lims"
LIMS_HTTP = f"http://{ESKI_IP}:8770"
LITSENZIYA_HTTPS = ASOS + "/litsenziya-x"
LITSENZIYA_HTTP = f"http://{ESKI_IP}:5679"
MASOFA_HTTPS = ASOS + "/masofa"
MASOFA_HTTP = f"http://{ESKI_IP}:5680"

_KESH_OK = 600          # ishladi — 10 daqiqa eslaymiz
_KESH_YOQ = 60          # ishlamadi — 1 daqiqadan keyin qayta sinaymiz
_kesh = {"natija": None, "vaqt": 0.0}


def https_ishlaydimi(timeout: float = 1.5) -> bool:
    """VPS bilan TLS (sertifikat tekshiruvi bilan) ulanadimi. Natija eslab qolinadi."""
    hozir = time.time()
    n = _kesh["natija"]
    if n is not None and hozir - _kesh["vaqt"] < (_KESH_OK if n else _KESH_YOQ):
        return n
    natija = False
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((DOMEN, 443), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=DOMEN):
                natija = True
    except ssl.SSLError:
        natija = False          # sertifikat ishonchsiz (eski Windows) — HTTP zaxira
    except Exception:
        # Internet yo'q / DNS — qaysi manzil bo'lishi farqsiz; HTTPS qaytadi va
        # 1 daqiqa eslanadi (har chaqiruvda 1,5 s kutmaslik uchun).
        _kesh.update(natija=True, vaqt=hozir - (_KESH_OK - _KESH_YOQ))
        return True
    _kesh.update(natija=natija, vaqt=hozir)
    return natija


def tanla(https_url: str, http_url: str) -> str:
    return https_url if https_ishlaydimi() else http_url
