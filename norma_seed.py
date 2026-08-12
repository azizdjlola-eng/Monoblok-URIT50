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
import csv
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
            connection_timeout=5, use_pure=True)
        try:
            _ensure_norma_table(conn)     # tahlillar_norma KAFOLATLI mavjud bo'lsin
            n1 = seed_normalar(conn)      # tahlillar_norma (normalar)
            n2 = seed_katalog(conn)       # tahlillar (xizmat katalogi + narxlar)
            n3 = seed_mkb10(conn)         # mkb10 (XKT-10 tashxis lug'ati)
            return n1 + n2 + n3
        finally:
            conn.close()
    except Exception:
        return 0


def _ensure_norma_table(conn):
    """tahlillar_norma jadvalini yaratadi (agar yo'q bo'lsa). Natija (monoblok) oynasi
    SHU jadvalni so'raydi — registrator ochilmagan fresh installда yo'q bo'lsa
    "1146 doesn't exist" beradi. seed_avto ni ikkala ilova ham startда chaqirgani uchun
    bu yerда kafolatlaymiz (qaysi oyna avval ochilsa ham)."""
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tahlillar_norma (
              id INT AUTO_INCREMENT PRIMARY KEY,
              guruh VARCHAR(50) NOT NULL, tahlil_nomi VARCHAR(255) NOT NULL,
              norma TEXT, birlik VARCHAR(50), yosh VARCHAR(100), jins VARCHAR(50),
              fazasikli VARCHAR(100), trimestr1 VARCHAR(100), trimestr2 VARCHAR(100),
              trimestr3 VARCHAR(100), type VARCHAR(50) DEFAULT 'numeric',
              min_val DECIMAL(10,2), max_val DECIMAL(10,2),
              min_val_m DECIMAL(10,2), max_val_m DECIMAL(10,2),
              min_val_f DECIMAL(10,2), max_val_f DECIMAL(10,2),
              result_template TEXT, standard_blank_path VARCHAR(500),
              is_calculated BOOLEAN DEFAULT FALSE, formula TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              UNIQUE KEY unique_tahlil (guruh, tahlil_nomi)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit(); cur.close()
    except Exception:
        pass


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


# ─────────────────── KATALOG (tahlillar / xizmatlar + narxlar) ───────────────
# `katalog_seed.json` — build vaqtida ENG OXIRGI bazadan eksport qilinadi
# (build/katalog_export.py). Yangi kompyuter to'liq xizmat ro'yxati bilan
# o'rnatiladi (ilgari faqat ~30 ta hardcoded default bor edi).

def _katalog_json_yol() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        for c in (base, os.path.join(base, "_internal")):
            p = os.path.join(c, "katalog_seed.json")
            if os.path.exists(p):
                return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "katalog_seed.json")


def katalog_yukla() -> list:
    try:
        with open(_katalog_json_yol(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def seed_katalog(conn, faqat_yoq: bool = True) -> int:
    """tahlillar (xizmat katalogi) ni seed qiladi — DB da YO'Q nomlarni qo'shadi.
    Idempotent; mavjud tahlil narxini BUZMAYDI (faqat yangi nomlar)."""
    rows = katalog_yukla()
    if not rows:
        return 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT nomi FROM tahlillar")
        mavjud = set((r[0] or "").strip() for r in cur.fetchall())
        qoshildi = 0
        for r in rows:
            nom = (r.get("nomi") or "").strip()
            if not nom or (faqat_yoq and nom in mavjud):
                continue
            # id — MASHINALARARO BIR XIL katalog ID (Natija oynasi natijani tahlil_id
            # bo'yicha bog'laydi). Seed'da id bo'lsa AYNAN o'sha id bilan qo'shamiz →
            # har o'rnatishda ALT=39 va h.k. Agar id band bo'lsa (kam ehtimol) id'siz.
            _sid = r.get("id")
            try:
                if _sid is not None:
                    cur.execute(
                        "INSERT INTO tahlillar(id, nomi, narxi, sample, turi, soha, aktiv) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (int(_sid), nom, int(r.get("narxi") or 0), r.get("sample"),
                         r.get("turi"), r.get("soha"), 1 if r.get("aktiv", 1) else 0))
                else:
                    raise ValueError("id yo'q")
            except Exception:
                try:
                    cur.execute(
                        "INSERT INTO tahlillar(nomi, narxi, sample, turi, soha, aktiv) "
                        "VALUES(%s,%s,%s,%s,%s,%s)",
                        (nom, int(r.get("narxi") or 0), r.get("sample"), r.get("turi"),
                         r.get("soha"), 1 if r.get("aktiv", 1) else 0))
                except Exception:
                    cur.execute("INSERT INTO tahlillar(nomi, narxi) VALUES(%s,%s)",
                                (nom, int(r.get("narxi") or 0)))
            mavjud.add(nom)
            qoshildi += 1
        conn.commit()
        return qoshildi
    finally:
        cur.close()


# ─────────────── MKB-10 (XKT-10/ICD-10) tashxis kodlari lug'ati ──────────────
# `mkb10_seed.csv` — milliy XKT-10 lug'ati (15900+ qator: kod, nomi_uz, nomi_ru,
# daraja). Vrach kabineti (diagnoz) va UZI protokoli (klinik tashxis) SHU
# jadvaldan qidiradi (vrach_web/app.py: /api/mkb10). Foydalanuvchi TAHRIRLAMAYDI
# va har kompyuterda bir xil bo'lishi shart — shuning uchun sinxron orqali EMAS,
# faqat shu LOKAL fayldan (bir marta, jadval bo'sh bo'lsa) to'ldiriladi.

def _mkb10_csv_yol() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        for c in (base, os.path.join(base, "_internal")):
            p = os.path.join(c, "mkb10_seed.csv")
            if os.path.exists(p):
                return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "mkb10_seed.csv")


def mkb10_yukla() -> list:
    yol = _mkb10_csv_yol()
    if not os.path.exists(yol):
        return []
    try:
        with open(yol, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def seed_mkb10(conn) -> int:
    """mkb10 jadvalini `mkb10_seed.csv` (to'liq milliy XKT-10 lug'ati) dan
    to'ldiradi. Jadval ustunlari: kod, nomi (o'zbekcha — ILGARIDAN mavjud,
    ba'zilari qo'lda kiritilgan), nomi_ru, daraja.

    Qo'lda kiritilgan/tahrirlangan qatorlar SAQLANADI — `nomi` ustuniga
    tegilmaydi, faqat YO'Q kodlar qo'shiladi va bo'sh nomi_ru/daraja
    to'ldiriladi. `COUNT(*) >= CSV qatorlar soni` bo'lsa qimmat solishtiruv
    butunlay o'tkazib yuboriladi (arzon tez-yo'l — keyingi startlarda)."""
    cur = conn.cursor()
    try:
        rows = mkb10_yukla()
        if not rows:
            return 0
        try:
            cur.execute("SELECT COUNT(*) FROM mkb10")
            (mavjud_soni,) = cur.fetchone()
        except Exception:
            return 0          # jadval hali yo'q (eski ensure_schema) — keyingi startda
        if mavjud_soni and int(mavjud_soni) >= len(rows):
            return 0          # allaqachon to'liq (yoki qo'lda ko'proq qo'shilgan)

        cur.execute("SELECT kod, nomi_ru, daraja FROM mkb10")
        mavjud = {k: (ru, dj) for k, ru, dj in cur.fetchall()}

        yangi, toldirish = [], []
        for r in rows:
            kod = (r.get("kod") or "").strip()
            nomi_uz = (r.get("nomi_uz") or "").strip()
            if not kod or not nomi_uz:
                continue
            nomi_ru = (r.get("nomi_ru") or "").strip()
            try:
                daraja = int(r.get("daraja") or 4)
            except (TypeError, ValueError):
                daraja = 4
            if kod not in mavjud:
                yangi.append((kod, nomi_uz, nomi_ru, daraja))
            else:
                eski_ru, eski_dj = mavjud[kod]
                if not eski_ru and nomi_ru:
                    toldirish.append((nomi_ru, daraja, kod))

        BATCH = 1000
        for i in range(0, len(yangi), BATCH):
            cur.executemany(
                "INSERT IGNORE INTO mkb10 (kod, nomi, nomi_ru, daraja) "
                "VALUES (%s,%s,%s,%s)", yangi[i:i + BATCH])
        for i in range(0, len(toldirish), BATCH):
            cur.executemany(
                "UPDATE mkb10 SET nomi_ru=%s, daraja=%s WHERE kod=%s",
                toldirish[i:i + BATCH])
        conn.commit()
        return len(yangi)
    finally:
        cur.close()
