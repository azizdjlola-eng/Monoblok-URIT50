# -*- coding: utf-8 -*-
"""
AzizMedLine LIMS — Litsenziya tizimi (Ed25519 asimmetrik imzo)

Arxitektura:
  - Uy/authority kompyuteri  : MAXFIY kalit (imzolaydi) → litsenziya_generator, litsenziya_admin
  - Mijoz EXE (filial/klient) : OCHIQ kalit (faqat tekshiradi) → litsenziya_manager, litsenziya_gate

Himoya tamoyillari:
  1. Hardware fingerprint (mashina_id) — protsessor + anakart + Windows GUID asosida.
     Boshqa kompyuterga o'tkazsa machine_id o'zgaradi → ishlamaydi (barmoq izidek).
  2. Ed25519 imzo — ochiq kalit bilan faqat TEKSHIRISH mumkin, soxta litsenziya yasab bo'lmaydi.
  3. Offline ishlaydi — fayl ichida muddat (expires_at) bor, internet shart emas.
  4. Anti-rollback — tizim vaqtini orqaga qaytarib muddatni cho'zib bo'lmaydi (vaqt_himoya).
"""

from . import mashina_id
from . import litsenziya_manager
from . import litsenziya_gate

__all__ = ["mashina_id", "litsenziya_manager", "litsenziya_gate"]
