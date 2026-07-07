# -*- coding: utf-8 -*-
"""
Online litsenziya xizmati sozlamasi.

  - VPS_URL  : mijoz HAM, uy HAM biladi (online holat tekshiriladigan manzil).
  - ADMIN_TOKEN : FAQAT uy/authority kompyuterida (`_admin_token.txt`). Mijoz EXE ga TUSHMAYDI.

VPS_URL ni rebuild qilmasdan o'zgartirish: ProgramData/AzizMedLine/vps_url.txt ga yozing.
"""

import os

# Standart VPS manzili (alohida port — litsenziya xizmati)
_DEFAULT_VPS_URL = "http://45.130.148.66:5679"


def vps_url() -> str:
    # 1) ProgramData override (rebuild kerak emas)
    try:
        pd = os.environ.get("ProgramData")
        if pd:
            p = os.path.join(pd, "AzizMedLine", "vps_url.txt")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    u = f.read().strip()
                    if u:
                        return u.rstrip("/")
    except Exception:
        pass
    # 2) Standart
    return _DEFAULT_VPS_URL.rstrip("/")


def admin_token() -> str:
    """Faqat uy kompyuterida bo'ladi (_admin_token.txt). Mijozda bo'sh qaytadi."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_admin_token.txt")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
