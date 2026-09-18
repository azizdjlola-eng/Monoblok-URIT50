# -*- coding: utf-8 -*-
"""
ESKI NOM — moslik uchun saqlangan.

Siydik analizatori xizmati endi `urit50_service.py` da (universal: URIT-50,
Dirui H, Mindray UA, HL7/ASTM — model Tizim Sozlamalari → Siydik dan tanlanadi).
Ikkita nusxa bir-biridan farqlanib ketmasligi uchun bu fayl faqat yo'naltiradi.
Eski to'liq nusxa: _eski/COM4_Urit50_to_Blank_fixed  cursor.py.bak
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from urit50_service import main, db_close  # noqa: E402

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Dastur to'xtatildi (Ctrl+C)")
    finally:
        db_close()
