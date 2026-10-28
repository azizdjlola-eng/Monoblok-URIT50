# -*- coding: utf-8 -*-
"""
TAKROR BEMORLARNI BIRLASHTIRISH (2026-10-28)

Ro'yxatga oluvchilar bir odamni har xil yozadi («Hursanov Husan» 6 tashrif,
«Xursanov Xusan» 22.10 va 28.10 da yana 2 ta alohida bemor bo'lib ochilgan).
Natijada blankadagi «Oldingi natija», tarix, SMS, qarz — hammasi bo'linib
ketadi. Bu modul ularni BITTA bemorga yig'adi.

QANDAY BIRLASHADI
  • Asosiy bemor (odatda eng ko'p tashrifi bor) QOLADI, ismi ixtiyoriy
    tuzatiladi.
  • Boshqa yozuvlarning `bemor_id` ga bog'langan HAMMA satrlari (orders,
    debtors, vaucherlar, bemor_eslatma, sms, ... — ro'yxat bazadan
    information_schema orqali olinadi, yangi jadval qo'shilsa ham chetda
    qolmaydi) asosiy bemorga ko'chadi.
  • Boshqa yozuvning o'zi O'CHIRILMAYDI — ismi asosiy bemorniki qilinadi va
    u bo'sh (tashrifsiz) qoladi.

NEGA O'CHIRILMAYDI: filial sinxronida bemor o'chirilishi «qabr toshi» bo'lib
tarqaladi va qabul qiluvchi tomonda o'sha bemorning BARCHA buyurtmalarini
ham o'chiradi (lims_sync_server._ochirishni_qolla). Agar buyurtmalarning
asosiy bemorga ko'chgani u yerga hali yetib bormagan bo'lsa — natijalar
yo'qolardi. Buyurtmaning `bemor_id` o'zgarishi esa oddiy tahrir kabi
(`updated_at`) tarqaladi.

ISHONCH: har birlashtirish `bemor_birlashtirish_log` ga yoziladi — kim,
qachon, qaysi satrlar ko'chdi, eski ismlar. `bekor_qil` hammasini qaytaradi.
"""
import json
import re

LOG_JADVAL = "bemor_birlashtirish_log"

# bemor_id bo'lsa ham KO'CHIRILMAYDI
_ISTISNO = {"bemorlar", LOG_JADVAL}


def _q(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def _qiymat(r, kalit, idx=0):
    return r[kalit] if isinstance(r, dict) else r[idx]


def jadval_yarat(cur):
    """Jurnal jadvali. DIQQAT: MySQL da CREATE TABLE tranzaksiyani yopadi —
    shuning uchun birlashtirish tranzaksiyasidan OLDIN chaqiriladi."""
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOG_JADVAL}(
          id INT AUTO_INCREMENT PRIMARY KEY,
          guruh VARCHAR(40) NOT NULL,
          sana DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          kim VARCHAR(128) NULL,
          asosiy_id INT NOT NULL,
          boshqa_id INT NOT NULL,
          asosiy_eski_fish VARCHAR(255) NULL,
          boshqa_eski_fish VARCHAR(255) NULL,
          yangi_fish VARCHAR(255) NULL,
          kochirilgan LONGTEXT NULL,
          bekor_qilingan DATETIME NULL,
          KEY ix_guruh (guruh), KEY ix_boshqa (boshqa_id), KEY ix_asosiy (asosiy_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


def bog_jadvallar(cur):
    """`bemor_id` ustuni bor jadvallar: [(jadval, id_ustuni_bormi), ...].
    Kodda emas, BAZADA qaraladi — yangi modul jadval qo'shsa ham chetda qolmaydi."""
    rows = _q(cur, """
        SELECT c.TABLE_NAME AS t
        FROM information_schema.COLUMNS c
        JOIN information_schema.TABLES tb
          ON tb.TABLE_SCHEMA = c.TABLE_SCHEMA AND tb.TABLE_NAME = c.TABLE_NAME
        WHERE c.TABLE_SCHEMA = DATABASE() AND c.COLUMN_NAME = 'bemor_id'
          AND tb.TABLE_TYPE = 'BASE TABLE'
    """)
    jadvallar = sorted({_qiymat(r, "t") for r in rows} - _ISTISNO)
    if not jadvallar:
        return []
    ph = ",".join(["%s"] * len(jadvallar))
    id_bor = {_qiymat(r, "t") for r in _q(cur, f"""
        SELECT TABLE_NAME AS t FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME = 'id'
          AND TABLE_NAME IN ({ph})""", jadvallar)}
    # orders birinchi — eng muhimi, xato bo'lsa darhol ko'rinsin
    jadvallar.sort(key=lambda t: (t != "orders", t))
    return [(t, t in id_bor) for t in jadvallar]


def tashrif_soni(cur, bemor_ids):
    """{bemor_id: buyurtmalar soni} (o'chirilganlarsiz)."""
    ids = [int(i) for i in bemor_ids]
    if not ids:
        return {}
    ph = ",".join(["%s"] * len(ids))
    try:
        rows = _q(cur, f"""SELECT bemor_id AS b, COUNT(*) AS n FROM orders
                           WHERE bemor_id IN ({ph}) AND deleted_at IS NULL
                           GROUP BY bemor_id""", ids)
    except Exception:
        rows = _q(cur, f"""SELECT bemor_id AS b, COUNT(*) AS n FROM orders
                           WHERE bemor_id IN ({ph}) GROUP BY bemor_id""", ids)
    out = {i: 0 for i in ids}
    for r in rows:
        out[int(_qiymat(r, "b"))] = int(_qiymat(r, "n", 1))
    return out


def asosiy_tavsiya(bemorlar, soni):
    """Asosiy bemor: eng ko'p tashrif; teng bo'lsa — eng eskisi (kichik id)."""
    return min(bemorlar, key=lambda b: (-soni.get(int(b["id"]), 0), int(b["id"])))["id"]


def birlashgan_bosh_idlar(cur):
    """Birlashtirilib bo'shab qolgan yozuvlar (bekor qilinmagan) — qidiruvda
    ko'rsatilmaydi. Jurnal jadvali yo'q bo'lsa bo'sh to'plam."""
    try:
        rows = _q(cur, f"SELECT DISTINCT boshqa_id AS b FROM {LOG_JADVAL} "
                       "WHERE bekor_qilingan IS NULL")
    except Exception:
        return set()
    return {int(_qiymat(r, "b")) for r in rows}


def _fish_tozala(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def _tranzaksiya_boshla(conn):
    if getattr(conn, "in_transaction", False):
        conn.commit()
    if hasattr(conn, "start_transaction"):
        conn.start_transaction()


def birlashtir(conn, asosiy_id, boshqa_ids, yangi_fish=None, kim=None):
    """`boshqa_ids` bemorlarning hamma bog'liq satrlarini `asosiy_id` ga
    ko'chiradi. Hammasi BITTA tranzaksiyada — xato bo'lsa hech narsa
    o'zgarmaydi. Qaytaradi: {'guruh', 'asosiy_id', 'fish', 'kochdi': {jadval: n}}."""
    asosiy_id = int(asosiy_id)
    boshqa_ids = sorted({int(i) for i in boshqa_ids} - {asosiy_id})
    if not boshqa_ids:
        raise ValueError("Birlashtirish uchun kamida 2 ta bemor kerak.")

    cur = conn.cursor(dictionary=True)
    try:
        jadval_yarat(cur)
        jadvallar = bog_jadvallar(cur)
        if not any(t == "orders" for t, _ in jadvallar):
            raise RuntimeError("orders jadvali topilmadi — birlashtirish to'xtatildi.")

        hammasi = [asosiy_id] + boshqa_ids
        ph = ",".join(["%s"] * len(hammasi))
        bemorlar = {int(r["id"]): r for r in _q(
            cur, f"SELECT id, fish FROM bemorlar WHERE id IN ({ph})", hammasi)}
        yoq = [i for i in hammasi if i not in bemorlar]
        if yoq:
            raise ValueError(f"Bemor topilmadi: ID {', '.join(map(str, yoq))}")

        asosiy_eski = bemorlar[asosiy_id]["fish"] or ""
        yangi = _fish_tozala(yangi_fish) or asosiy_eski
        guruh = _guruh_kaliti(cur)

        _tranzaksiya_boshla(conn)
        jami = {}
        for bid in boshqa_ids:
            kochirilgan = {}
            for t, id_bor in jadvallar:
                if id_bor:
                    ids = [int(_qiymat(r, "id")) for r in _q(
                        cur, f"SELECT id FROM {t} WHERE bemor_id=%s", (bid,))]
                    if not ids:
                        continue
                    cur.execute(f"UPDATE {t} SET bemor_id=%s WHERE bemor_id=%s",
                                (asosiy_id, bid))
                    kochirilgan[t] = ids
                    n = len(ids)
                else:
                    cur.execute(f"UPDATE {t} SET bemor_id=%s WHERE bemor_id=%s",
                                (asosiy_id, bid))
                    n = cur.rowcount or 0
                    if not n:
                        continue
                    kochirilgan[t] = n           # satr id si yo'q — soni yoziladi
                jami[t] = jami.get(t, 0) + n
            cur.execute("UPDATE bemorlar SET fish=%s WHERE id=%s", (yangi, bid))
            cur.execute(f"""INSERT INTO {LOG_JADVAL}
                (guruh, kim, asosiy_id, boshqa_id, asosiy_eski_fish,
                 boshqa_eski_fish, yangi_fish, kochirilgan)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (guruh, (kim or "")[:128], asosiy_id, bid, asosiy_eski,
                 bemorlar[bid]["fish"] or "", yangi,
                 json.dumps(kochirilgan, ensure_ascii=False)))
        if yangi != asosiy_eski:
            cur.execute("UPDATE bemorlar SET fish=%s WHERE id=%s", (yangi, asosiy_id))
        conn.commit()
        return {"guruh": guruh, "asosiy_id": asosiy_id, "fish": yangi,
                "boshqa_ids": boshqa_ids, "kochdi": jami}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _guruh_kaliti(cur):
    import datetime
    import uuid
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S-") + uuid.uuid4().hex[:8]


def tarix(cur, limit=30):
    """Oxirgi birlashtirishlar (guruh bo'yicha):
    [{'guruh','sana','kim','asosiy_id','yangi_fish','eski_fishlar','soni','bekor'}]."""
    try:
        rows = _q(cur, f"""SELECT guruh, sana, kim, asosiy_id, asosiy_eski_fish,
                                  boshqa_eski_fish, yangi_fish, kochirilgan,
                                  bekor_qilingan
                           FROM {LOG_JADVAL} ORDER BY id DESC LIMIT %s""", (limit * 5,))
    except Exception:
        return []
    guruhlar = {}
    for r in rows:
        g = guruhlar.setdefault(r["guruh"], {
            "guruh": r["guruh"], "sana": r["sana"], "kim": r["kim"] or "",
            "asosiy_id": r["asosiy_id"], "yangi_fish": r["yangi_fish"] or "",
            "eski_fishlar": [r["asosiy_eski_fish"] or ""], "soni": 0,
            "bekor": r["bekor_qilingan"]})
        g["eski_fishlar"].append(r["boshqa_eski_fish"] or "")
        try:
            g["soni"] += len((json.loads(r["kochirilgan"] or "{}") or {}).get("orders", []))
        except Exception:
            pass
    return list(guruhlar.values())[:limit]


def bekor_qil(conn, guruh, kim=None):
    """Birlashtirishni to'liq qaytaradi: ko'chgan satrlar eski bemorga,
    eski ismlar joyiga. Faqat id si yozilgan satrlar qaytadi (id siz jadvalda
    soni yozilgan — ular asosiy bemorda qoladi, natijada aytiladi).
    Qaytaradi: {'qaytdi': {jadval: n}, 'qaytmadi': {jadval: n}}."""
    cur = conn.cursor(dictionary=True)
    try:
        rows = _q(cur, f"""SELECT id, asosiy_id, boshqa_id, asosiy_eski_fish,
                                  boshqa_eski_fish, yangi_fish, kochirilgan
                           FROM {LOG_JADVAL}
                           WHERE guruh=%s AND bekor_qilingan IS NULL
                           ORDER BY id""", (guruh,))
        if not rows:
            raise ValueError("Bu birlashtirish topilmadi yoki allaqachon bekor qilingan.")
        _tranzaksiya_boshla(conn)
        qaytdi, qaytmadi = {}, {}
        for r in rows:
            asosiy, boshqa = int(r["asosiy_id"]), int(r["boshqa_id"])
            kochirilgan = json.loads(r["kochirilgan"] or "{}") or {}
            for t, ids in kochirilgan.items():
                if not isinstance(ids, list):
                    qaytmadi[t] = qaytmadi.get(t, 0) + int(ids or 0)
                    continue
                for i in range(0, len(ids), 500):
                    bolak = ids[i:i + 500]
                    ph = ",".join(["%s"] * len(bolak))
                    cur.execute(f"UPDATE {t} SET bemor_id=%s "
                                f"WHERE id IN ({ph}) AND bemor_id=%s",
                                (boshqa, *bolak, asosiy))
                    qaytdi[t] = qaytdi.get(t, 0) + (cur.rowcount or 0)
            cur.execute("UPDATE bemorlar SET fish=%s WHERE id=%s",
                        (r["boshqa_eski_fish"], boshqa))
            cur.execute(f"UPDATE {LOG_JADVAL} SET bekor_qilingan=NOW(), "
                        "kim=CONCAT(COALESCE(kim,''), %s) WHERE id=%s",
                        (f" | bekor: {kim or ''}"[:60], r["id"]))
        # Asosiy bemor ismi — faqat keyin hech kim o'zgartirmagan bo'lsa qaytadi
        r0 = rows[0]
        cur.execute("UPDATE bemorlar SET fish=%s WHERE id=%s AND fish=%s",
                    (r0["asosiy_eski_fish"], int(r0["asosiy_id"]), r0["yangi_fish"]))
        conn.commit()
        return {"qaytdi": qaytdi, "qaytmadi": qaytmadi}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass


def admin_parol(cur, parol):
    """Admin/boshliq parolini tekshiradi (LIMS foydalanuvchilar jadvali, LIMS
    dagi check_password bilan bir qoida: bcrypt yoki eski oddiy matn).
    To'g'ri bo'lsa foydalanuvchi loginini, aks holda None qaytaradi."""
    if not parol:
        return None
    rows = _q(cur, "SELECT login, parol FROM foydalanuvchilar "
                   "WHERE rol IN ('admin','boshliq')")
    for r in rows:
        login, saqlangan = _qiymat(r, "login"), _qiymat(r, "parol", 1)
        saqlangan = saqlangan or ""
        if saqlangan.startswith("$2"):
            try:
                import bcrypt
            except Exception:
                continue          # bcrypt yo'q — hash ni tekshirib bo'lmaydi, rad
            try:
                if bcrypt.checkpw(parol.encode("utf-8"), saqlangan.encode("utf-8")):
                    return login
            except Exception:
                continue
        elif saqlangan and parol == saqlangan:
            return login
    return None
