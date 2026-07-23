"""
VPS Sync moduli — monoblok_dastur.py dan VPS serverga natija yuborish.
Bu modul lokal kompyuterda ishlaydi va natija tayyor bo'lganda
VPS dagi sync API ga HTTP POST yuboradi.
"""
import json
import logging
import threading
from datetime import datetime

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

logger = logging.getLogger("vps_sync")

# ── SOZLAMALAR ──────────────────────────────────────────────
VPS_SYNC_URL = "http://45.130.148.66:8443/api/sync_natija"
VPS_BATCH_URL = "http://45.130.148.66:8443/api/sync_batch"
VPS_API_KEY = "azizmedline_sync_2026_xavfsiz_kalit"
SYNC_TIMEOUT = 15  # sekund


def sync_natija_to_vps(sample_id, order_id, fish, telefon, elementlar,
                       yosh=None, jins=None, shifokor=None, manzil=None,
                       tugilgan_sana=None, sana=None, blocking=False):
    """
    Bitta natijani VPS ga yuborish.

    elementlar = [
        {"tahlil_nomi": "Glyukoza", "qiymat": "5.6", "birlik": "ммоль/л", "norma": "3.2-6.1", "izoh": ""},
        ...
    ]

    blocking=False: alohida threadda yuboradi (UI bloklanmaydi)
    blocking=True:  hozirgi threadda yuboradi (test uchun)
    """
    if not REQUESTS_OK:
        logger.warning("requests kutubxonasi o'rnatilmagan — sync ishlamaydi")
        return False

    payload = {
        "sample_id": str(sample_id),
        "order_id": order_id,
        "fish": fish or "Noma'lum",
        "telefon": str(telefon) if telefon else None,
        "yosh": yosh,
        "jins": jins,
        "shifokor": shifokor,
        "manzil": manzil,
        "tugilgan_sana": str(tugilgan_sana) if tugilgan_sana else None,
        "sana": sana or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elementlar": elementlar,
    }

    if blocking:
        return _do_sync(payload)
    else:
        t = threading.Thread(target=_do_sync, args=(payload,), daemon=True)
        t.start()
        return True


def _do_sync(payload):
    """HTTP POST yuborish (threadda ishlaydi)."""
    try:
        resp = requests.post(
            VPS_SYNC_URL,
            json=payload,
            headers={"X-API-Key": VPS_API_KEY, "Content-Type": "application/json"},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                "VPS sync muvaffaqiyatli: %s (%s) — tg:%s",
                payload["sample_id"], payload["fish"],
                data.get("telegram_id", "—")
            )
            return True
        else:
            logger.error("VPS sync xato: %s — %s", resp.status_code, resp.text[:200])
            return False
    except requests.ConnectionError:
        logger.error("VPS ga ulanib bo'lmadi (server o'chiqmi?): %s", VPS_SYNC_URL)
        return False
    except requests.Timeout:
        logger.error("VPS javob bermadi (%ds timeout)", SYNC_TIMEOUT)
        return False
    except Exception as e:
        logger.error("VPS sync kutilmagan xato: %s", e)
        return False


def collect_result_data(conn, order_id, sample_id):
    """
    MySQL bazadan natija ma'lumotlarini yig'ish.
    conn: mysql.connector ulanish
    Returns: dict (sync_natija_to_vps ga tayyor) yoki None
    """
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT b.fish, b.telefon, b.yosh, b.jins, b.shifokor,
                   b.manzil, b.tugilgan_sana, b.sana_vaqt,
                   o.sample_id
            FROM orders o
            JOIN bemorlar b ON b.id = o.bemor_id
            WHERE o.id = %s
        """, (order_id,))
        order_info = cursor.fetchone()
        if not order_info:
            logger.warning("Order %s topilmadi", order_id)
            return None

        cursor.execute("""
            SELECT r.id as result_id FROM results r
            WHERE r.order_id = %s AND r.status = 'ready'
        """, (order_id,))
        result_row = cursor.fetchone()
        if not result_row:
            logger.warning("Order %s uchun tayyor natija yo'q", order_id)
            return None

        result_id = result_row["result_id"]

        cursor.execute("""
            SELECT tahlil_nomi, qiymat, birlik, norma, note as izoh
            FROM result_items
            WHERE result_id = %s
        """, (result_id,))
        items = cursor.fetchall()

        if not items:
            logger.warning("Result %s uchun elementlar yo'q", result_id)
            return None

        elementlar = []
        for item in items:
            elementlar.append({
                "tahlil_nomi": item.get("tahlil_nomi", ""),
                "qiymat": item.get("qiymat", ""),
                "birlik": item.get("birlik", ""),
                "norma": item.get("norma", ""),
                "izoh": item.get("izoh", ""),
            })

        cursor.close()

        return {
            "sample_id": sample_id or order_info.get("sample_id", ""),
            "order_id": order_id,
            "fish": order_info.get("fish", ""),
            "telefon": order_info.get("telefon"),
            "yosh": order_info.get("yosh"),
            "jins": order_info.get("jins"),
            "shifokor": order_info.get("shifokor"),
            "manzil": order_info.get("manzil"),
            "tugilgan_sana": str(order_info["tugilgan_sana"]) if order_info.get("tugilgan_sana") else None,
            "sana": str(order_info["sana_vaqt"]) if order_info.get("sana_vaqt") else None,
            "elementlar": elementlar,
        }
    except Exception as e:
        logger.error("collect_result_data xato: %s", e)
        return None


def sync_from_db(conn, order_id, sample_id):
    """
    MySQL dan ma'lumot yig'ib VPS ga yuborish (bitta funksiya).
    monoblok_dastur.py dan chaqirish uchun qulay.
    """
    data = collect_result_data(conn, order_id, sample_id)
    if not data:
        return False
    return sync_natija_to_vps(
        sample_id=data["sample_id"],
        order_id=data["order_id"],
        fish=data["fish"],
        telefon=data["telefon"],
        elementlar=data["elementlar"],
        yosh=data["yosh"],
        jins=data["jins"],
        shifokor=data["shifokor"],
        manzil=data["manzil"],
        tugilgan_sana=data["tugilgan_sana"],
        sana=data["sana"],
    )
