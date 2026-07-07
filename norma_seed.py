# -*- coding: utf-8 -*-
"""
Norma seed — kod ichidagi hardcoded normalarni (eski TEST_NORMAS) BAZAGA ko'chiradi.

Maqsad (egasi talabi): normalar FAQAT bazadan olinsin — chunki norma o'zgaradi va
mijoz uni bazadan tahrirlashi kerak (kodda hardcoded bo'lsa iloji yo'q).

`norma_seed.json` — bir marta kod-lug'atdan ajratilgan norma ma'lumoti (84 ta).
Dastur startda `seed_normalar()` ni chaqiradi: DB da YO'Q normalarni qo'shadi
(idempotent — mavjudini o'zgartirmaydi, qiymatlar lug'atdagidek → xatti-harakat saqlanadi).
"""

import os
import sys
import json


def _json_yol() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        for c in (base, os.path.join(base, "_internal")):
            p = os.path.join(c, "norma_seed.json")
            if os.path.exists(p):
                return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "norma_seed.json")


def normalar_yukla() -> list:
    try:
        with open(_json_yol(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _db_config() -> dict:
    """db_config ni baza_sozlama orqali (yoki zaxira) o'qiydi."""
    try:
        import baza_sozlama
        return baza_sozlama.oqi()
    except Exception:
        cfg = {"host": "127.0.0.1", "user": "root", "password": "azizmed2026",
               "database": "lab_tizim", "port": 3306}
        for base in (os.path.dirname(os.path.abspath(__file__)),):
            p = os.path.join(base, "db_config.txt")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k = k.strip().upper(); v = v.strip()
                            if k in ("HOST", "DB_HOST"): cfg["host"] = v
                            elif k in ("USER", "DB_USER"): cfg["user"] = v
                            elif k in ("PASS", "DB_PASS", "PASSWORD"): cfg["password"] = v
                            elif k in ("DB", "DB_NAME", "DATABASE"): cfg["database"] = v
                            elif k in ("PORT", "DB_PORT"):
                                try: cfg["port"] = int(v)
                                except ValueError: pass
                except Exception:
                    pass
        return cfg


def seed_avto() -> int:
    """
    O'z ulanishini ochib normalarni seed qiladi (dastur startida chaqiriladi).
    Startni HECH QACHON to'smaydi (xato bo'lsa 0 qaytadi). Idempotent.
    """
    try:
        import mysql.connector
        cfg = _db_config()
        conn = mysql.connector.connect(
            host=cfg["host"], user=cfg["user"], password=cfg["password"],
            database=cfg["database"], port=int(cfg.get("port", 3306)),
            connection_timeout=5)
        try:
            return seed_normalar(conn)
        finally:
            conn.close()
    except Exception:
        return 0


def seed_normalar(conn, faqat_yoq: bool = True) -> int:
    """
    tahlillar_norma ga kod-lug'at normalarini qo'shadi.
    faqat_yoq=True → faqat DB da bo'lmagan tahlil_nomi larni qo'shadi (mavjudni buzmaydi).
    Qaytaradi: qo'shilgan qatorlar soni. Idempotent.
    """
    rows = normalar_yukla()
    if not rows:
        return 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT tahlil_nomi FROM tahlillar_norma")
        mavjud = set((r[0] or "").strip() for r in cur.fetchall())
        qoshildi = 0
        for r in rows:
            nom = (r.get("tahlil_nomi") or "").strip()
            if not nom:
                continue
            if faqat_yoq and nom in mavjud:
                continue
            cur.execute(
                "INSERT INTO tahlillar_norma "
                " (guruh, tahlil_nomi, norma, birlik, type, min_val, max_val, "
                "  min_val_m, max_val_m, min_val_f, max_val_f) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (r.get("guruh") or "", nom, r.get("norma"), r.get("birlik"),
                 r.get("type"), r.get("min_val"), r.get("max_val"),
                 r.get("min_val_m"), r.get("max_val_m"),
                 r.get("min_val_f"), r.get("max_val_f")))
            mavjud.add(nom)
            qoshildi += 1
        conn.commit()
        return qoshildi
    finally:
        cur.close()
