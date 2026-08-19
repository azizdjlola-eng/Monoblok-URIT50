# -*- coding: utf-8 -*-
"""
NATIJA TUGALLANGANMI — `results.status` uchun YAGONA haqiqat manbai.

MUAMMO (2026-08-19 da topildi)
──────────────────────────────
"Natijalar va SMS xabarnoma" oynasi natija CHIQMAGAN bemorni ham "Tayyor"
deb ko'rsatardi. 19.08.2026 da 13 ta "Tayyor" dan 11 tasida buyurtma
qilingan tahlillarning BIRORTASI ham bajarilmagan edi.

ILDIZ: gematologiya analizatori (BC-20S) HL7 orqali natija yuborganida
`bc20s_listener._save_to_db()` DARHOL `results.status='ready'` qilardi.
Ya'ni "tayyor" deganini MASHINA aytardi — laborant emas. Bemor esa
"Qonning umumiy tahlili + ALT + Bilirubin" buyurtma qilgan bo'lsa,
analizator faqat qon tahlilining xom ko'rsatkichlarini (WBC, HGB, ...)
yuborgan bo'lardi, qolgani hali ishlanmagan.

Natija: LIMS "Tayyor" deydi → TV bemorga "tayyor" deb ko'rsatadi →
lekin blanka chop etilmagan, PDF yo'q, SMS ketmaydi. Har kuni ertalab
qizil ogohlantirish "N ta natija TAYYOR, lekin PDF blanka yo'q" chiqadi.

QOIDA (shu modul)
─────────────────
`results.status='ready'` FAQAT buyurtmadagi HAMMA laboratoriya tahlili
saqlanganda qo'yiladi. Qisman to'ldirilgan (analizator xom ma'lumoti bor,
laborant hali tugatmagan) natija — `'draft'`.

    open   — hech narsa yo'q
    draft  — qisman: analizator ma'lumoti bor, laborant tugatmagan
    ready  — buyurtmadagi hamma tahlil saqlangan (haqiqiy "Tayyor")
    printed— blanka chop etilgan (bu holatga TEGILMAYDI, u yakuniy)

"Bajarildi" belgisi: `test_results.test_name` yoki `result_items.tahlil_nomi`
buyurtmadagi tahlil NOMI bilan mos kelsa. Analizator xom ko'rsatkichlari
(WBC, HGB, ALT-kod...) bu nomlarga mos kelmaydi — shuning uchun ular
o'zicha "tayyor" qila olmaydi.

TEKSHIRILDI: oxirgi 30 kunlik 1261 ta 'ready' buyurtmadan 1226 tasi (97%)
bu qoida bo'yicha ham to'liq — ya'ni qoida haqiqiy ishni "kutilmoqda"
qilib qo'ymaydi.

Ishlatish (saqlashdan keyin, commit dan OLDIN):

    from natija_tugallik import natija_holatini_yangila
    natija_holatini_yangila(cur, order_id, vaqt=now_str)

Bu modul "D:/AzizMedLine_LIMS" va "G:/DASTUR/URIT 50" papkalarida BIR XIL
turishi shart (filial_belgi.py / natija_chaqiruv.py kabi).
"""

import re

# Laboratoriya bo'lmagan sohalar — ular vrach_web / UZI orqali yuritiladi,
# laboratoriya blankasiga kirmaydi, shuning uchun natija tugalligiga
# hisobga olinmaydi.
LAB_BO_LMAGAN_SOHALAR = ("uzi", "ambulator", "muolaja", "statsionar", "korik")

_BOSHLIQ = re.compile(r"\s+")


def _norm(nom) -> str:
    """Tahlil nomini solishtirish uchun normallashtirish."""
    if not nom:
        return ""
    s = str(nom).replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    s = _BOSHLIQ.sub(" ", s).strip().lower()
    return s


def _bir_ustun(cur):
    """Kursor dictionary=True yoki oddiy bo'lishi mumkin — ikkalasini ham qo'llab-quvvatlaydi."""
    natija = []
    for row in cur.fetchall():
        if isinstance(row, dict):
            vals = list(row.values())
            natija.append(vals[0] if vals else None)
        elif isinstance(row, (tuple, list)):
            natija.append(row[0] if row else None)
        else:
            natija.append(row)
    return natija


def _qatorlar(cur):
    """Qatorlarni (tuple) ko'rinishida qaytaradi — dict kursor bo'lsa ham."""
    natija = []
    for row in cur.fetchall():
        if isinstance(row, dict):
            natija.append(tuple(row.values()))
        else:
            natija.append(tuple(row))
    return natija


def buyurtma_tugallik(cur, order_id):
    """(tugallandi: bool, yetishmayotgan: list[str], jami: int) qaytaradi.

    tugallandi=True — buyurtmadagi HAMMA laboratoriya tahlili saqlangan.
    """
    # 1) Buyurtmadagi tahlillar (soha `tahlillar` katalogidan olinadi, chunki
    #    order_items.soha ko'p hollarda NULL)
    cur.execute("""
        SELECT oi.nomi, COALESCE(t.soha, oi.soha)
        FROM order_items oi
        LEFT JOIN tahlillar t ON t.id = oi.tahlil_id
        WHERE oi.order_id = %s
    """, (order_id,))
    buyurtma = []
    for nomi, soha in _qatorlar(cur):
        if not nomi or not str(nomi).strip():
            continue
        if soha and str(soha).strip().lower() in LAB_BO_LMAGAN_SOHALAR:
            continue                      # UZI / vrach qabuli — blankaga kirmaydi
        buyurtma.append(str(nomi).strip())

    # 2) Bajarilgan tahlil nomlari
    cur.execute("""
        SELECT test_name FROM test_results
        WHERE order_id = %s AND result_data IS NOT NULL AND TRIM(result_data) <> ''
    """, (str(order_id),))
    bajarilgan = {_norm(n) for n in _bir_ustun(cur) if n}

    cur.execute("""
        SELECT ri.tahlil_nomi
        FROM result_items ri
        JOIN results r ON r.id = ri.result_id
        WHERE r.order_id = %s AND ri.qiymat IS NOT NULL AND TRIM(ri.qiymat) <> ''
    """, (order_id,))
    bajarilgan |= {_norm(n) for n in _bir_ustun(cur) if n}

    if not buyurtma:
        # Buyurtma satrlari yo'q (eski/nomukammal yozuv) — eski xatti-harakat:
        # birorta qiymat bo'lsa tayyor deb hisoblaymiz.
        return (bool(bajarilgan), [], 0)

    yetishmaydi = [n for n in buyurtma if _norm(n) not in bajarilgan]
    return (not yetishmaydi, yetishmaydi, len(buyurtma))


def natija_holatini_yangila(cur, order_id, vaqt=None, result_id=None):
    """`results.status` ni HISOBLAB yozadi va yakuniy holatni qaytaradi.

    • 'printed' — tegilmaydi (blanka chop etilgan = yakuniy).
    • Hamma tahlil bajarilgan  → 'ready'
    • Qisman / hech narsa yo'q → 'draft' (qiymat bo'lsa) yoki 'open'
    • Holat o'zgarmasa — YOZILMAYDI (sinxron aks-sadosining oldi olinadi).
    • Bitta buyurtmada bir nechta `results` satri bo'lsa (dublikat) —
      HAMMASI bir xil holatga keltiriladi, chunki o'quvchilar
      `MAX(status IN ('ready','printed'))` bilan o'qiydi va bitta eskirgan
      dublikat butun buyurtmani yolg'on "Tayyor" qilib qo'yishi mumkin.

    Chaqiruvchi commit() qiladi. Kursor dictionary=True bo'lsa ham ishlaydi.
    """
    cur.execute("SELECT id, status FROM results WHERE order_id = %s ORDER BY id",
                (order_id,))
    satrlar = [(q[0], (q[1] or "open").strip().lower()) for q in _qatorlar(cur)]

    if any(h == "printed" for _, h in satrlar):
        return "printed"                  # blanka chop etilgan — yakuniy holat

    tugallandi, yetishmaydi, jami = buyurtma_tugallik(cur, order_id)
    if tugallandi:
        yangi = "ready"
    else:
        # Biror qiymat bormi? Bo'lsa "qisman" (draft), bo'lmasa "open".
        cur.execute("""
            SELECT COUNT(*) FROM result_items ri
            JOIN results r ON r.id = ri.result_id
            WHERE r.order_id = %s AND ri.qiymat IS NOT NULL AND TRIM(ri.qiymat) <> ''
        """, (order_id,))
        bor = _bir_ustun(cur)
        yangi = "draft" if (bor and int(bor[0] or 0) > 0) else "open"

    if not satrlar:
        if vaqt:
            cur.execute("""INSERT INTO results (order_id, status, created_at, updated_at)
                           VALUES (%s, %s, %s, %s)""", (order_id, yangi, vaqt, vaqt))
        else:
            cur.execute("INSERT INTO results (order_id, status) VALUES (%s, %s)",
                        (order_id, yangi))
        return yangi

    for rid, joriy in satrlar:
        if joriy == yangi:
            continue                      # o'zgarish yo'q — updated_at ga tegmaymiz
        if vaqt:
            cur.execute("UPDATE results SET status=%s, updated_at=%s WHERE id=%s",
                        (yangi, vaqt, rid))
        else:
            cur.execute("UPDATE results SET status=%s WHERE id=%s", (yangi, rid))
    return yangi
