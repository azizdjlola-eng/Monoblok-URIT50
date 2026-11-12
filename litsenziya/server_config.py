# -*- coding: utf-8 -*-
"""
Online litsenziya xizmati sozlamasi.

  - VPS_URL  : mijoz HAM, uy HAM biladi (online holat tekshiriladigan manzil).
  - ADMIN_TOKEN : FAQAT uy/authority kompyuterida (`_admin_token.txt`). Mijoz EXE ga TUSHMAYDI.

VPS_URL ni rebuild qilmasdan o'zgartirish: ProgramData/AzizMedLine/vps_url.txt ga yozing.
"""

import os

# Standart VPS manzili. 2026-11-11 dan HTTPS (nginx 443 → 5679); eski Windows
# sertifikatga ishonmasa — eski HTTP porti (vps_https.tanla).
_DEFAULT_VPS_URL_HTTPS = "https://45-130-148-66.sslip.io/litsenziya-x"
_DEFAULT_VPS_URL = "http://45.130.148.66:5679"


def _standart() -> str:
    try:
        import vps_https
        return vps_https.tanla(vps_https.LITSENZIYA_HTTPS, vps_https.LITSENZIYA_HTTP)
    except Exception:
        return _DEFAULT_VPS_URL_HTTPS


def vps_url() -> str:
    # 1) ProgramData override (rebuild kerak emas)
    try:
        pd = os.environ.get("ProgramData")
        if pd:
            p = os.path.join(pd, "AzizMedLine", "vps_url.txt")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    u = f.read().strip()
                    # Eski standart HTTP manzil qo'lda yozilgan bo'lsa — bu
                    # «o'zgartirish» emas: HTTPS ga o'tkazamiz.
                    if u and u.rstrip("/") != _DEFAULT_VPS_URL:
                        return u.rstrip("/")
    except Exception:
        pass
    # 2) Standart (HTTPS, ishlamasa eski HTTP)
    return _standart().rstrip("/")


def admin_token() -> str:
    """Faqat uy kompyuterida bo'ladi (_admin_token.txt). Mijozda bo'sh qaytadi."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_admin_token.txt")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
