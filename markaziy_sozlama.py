"""
Laboratoriya bo'yicha UMUMIY sozlamalar — bazada (hamma kompyuterda bir xil).

Muammo: blanka sozlamalari (gemo_blanka, siydik_blanka, bio_blanka, tahlil_turlari)
analizator_config.json da — HAR KOMPYUTERDA ALOHIDA saqlanardi. Laboratoriyada
2-3 kompyuter bo'lsa, birida o'zgartirilgan blanka boshqasida eski ko'rinishda chiqardi.

Endi bu sozlamalar bazadagi `lims_sozlamalar` jadvalida (kalit → JSON):
  • o'qish — bazadan (60 s kesh); baza ishlamasa — mahalliy nusxa (analizator_config.json
    dagi o'sha kalit); dastur qotib qolmasin deb xatodan keyin 2 daqiqa bazaga urinilmaydi;
  • yozish — bazaga VA mahalliy nusxaga (oflayn zaxira);
  • bazada hali yo'q, mahalliyda bor bo'lsa — birinchi o'qishda bazaga ko'chiriladi
    (mavjud o'rnatmalar sozlamasi yo'qolmaydi).

Ulanish sozlamalari (IP, COM port, papkalar) bu yerda EMAS — ular kompyuterga xos.
"""

import json
import threading
import time

JADVAL = "lims_sozlamalar"
KESH_SEK = 60          # bazadan qayta o'qish oralig'i
XATO_KUTISH_SEK = 120  # baza ishlamasa — shuncha vaqt faqat mahalliy nusxa

_lock = threading.RLock()
_kesh = {}             # kalit -> (vaqt, json_satr)  ("" = sozlama yo'q)
_holat = {"xato_vaqt": 0.0, "jadval": False}


def _db():
    import mysql.connector
    from monoblok_db_config import DB_CONFIG
    return mysql.connector.connect(**DB_CONFIG)


def _jadval_yarat(cur):
    if _holat["jadval"]:
        return
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {JADVAL} (
                        kalit VARCHAR(64) NOT NULL PRIMARY KEY,
                        qiymat LONGTEXT,
                        kompyuter VARCHAR(64),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) DEFAULT CHARSET=utf8mb4""")
    _holat["jadval"] = True


def _mahalliy_js(kalit) -> str:
    try:
        import monoblok_db_config as _mc
        with open(_mc.CONFIG_PATH, "r", encoding="utf-8") as f:
            v = (json.load(f) or {}).get(kalit)
        return json.dumps(v, ensure_ascii=False) if v is not None else ""
    except Exception:
        return ""


def _mahalliy_yoz(kalit, qiymat) -> bool:
    try:
        import monoblok_db_config as _mc
        cfg = _mc.load_config()
        cfg[kalit] = qiymat
        return bool(_mc.save_config(cfg))
    except Exception as e:
        print(f"[OGOHLANTIRISH] {kalit} mahalliy nusxaga yozilmadi: {e}")
        return False


def _bazaga_yoz(cur, kalit, js):
    import socket
    cur.execute(f"""INSERT INTO {JADVAL} (kalit, qiymat, kompyuter) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE qiymat = VALUES(qiymat), kompyuter = VALUES(kompyuter)""",
                (kalit, js, socket.gethostname()[:64]))


def _js(kalit) -> str:
    """Sozlamaning JSON satri (kesh bilan). "" — sozlama yo'q."""
    with _lock:
        now = time.time()
        k = _kesh.get(kalit)
        if k and now - k[0] < KESH_SEK:
            return k[1]
        if now - _holat["xato_vaqt"] < XATO_KUTISH_SEK:
            js = k[1] if k else _mahalliy_js(kalit)
            _kesh[kalit] = (now, js)
            return js
        try:
            conn = _db()
            try:
                cur = conn.cursor()
                _jadval_yarat(cur)
                cur.execute(f"SELECT qiymat FROM {JADVAL} WHERE kalit = %s", (kalit,))
                r = cur.fetchone()
                js = (r[0] or "") if r else ""
                if not r:
                    # Bazada yo'q — mahalliy sozlama bor bo'lsa bazaga ko'chiramiz
                    loc = _mahalliy_js(kalit)
                    if loc:
                        _bazaga_yoz(cur, kalit, loc)
                        conn.commit()
                        js = loc
                        print(f"[markaziy_sozlama] {kalit}: mahalliy sozlama bazaga ko'chirildi")
            finally:
                conn.close()
        except Exception as e:
            _holat["xato_vaqt"] = now
            print(f"[OGOHLANTIRISH] markaziy_sozlama: baza o'qilmadi ({kalit}) — mahalliy nusxa: {e}")
            js = k[1] if k else _mahalliy_js(kalit)
        _kesh[kalit] = (now, js)
        return js


def ol(kalit):
    """Sozlama qiymati (dict/list) yoki None."""
    js = _js(kalit)
    try:
        return json.loads(js) if js else None
    except Exception:
        return None


def versiya(kalit) -> str:
    """Arzon o'zgarish belgisi — modul o'z _toza() natijasini faqat o'zgarganda qayta quradi."""
    return _js(kalit)


def yoz(kalit, qiymat) -> bool:
    """Bazaga va mahalliy nusxaga yozish. Baza ishlamasa — mahalliy saqlanadi va
    keyingi muvaffaqiyatli saqlashda bazaga ham tushadi."""
    js = json.dumps(qiymat, ensure_ascii=False)
    mahalliy_ok = _mahalliy_yoz(kalit, qiymat)
    with _lock:
        try:
            conn = _db()
            try:
                cur = conn.cursor()
                _jadval_yarat(cur)
                _bazaga_yoz(cur, kalit, js)
                conn.commit()
            finally:
                conn.close()
            _kesh[kalit] = (time.time(), js)
            _holat["xato_vaqt"] = 0.0
            return True
        except Exception as e:
            print(f"[OGOHLANTIRISH] markaziy_sozlama: bazaga yozilmadi ({kalit}): {e}")
            _kesh[kalit] = (time.time(), js)
            return mahalliy_ok


def modul_sozlama(kalit, toza_fn, kesh: dict, force=False, **tozala):
    """Modullar (gemo_blanka ...) uchun: toza_fn(raw) natijasi, faqat sozlama o'zgarganda
    qayta quriladi. kesh — modulning {"mtime", "cfg"} lug'ati; tozala — o'zgarganda
    kesh ga qo'shimcha yoziladigan qiymatlar (masalan xarita_cfg=None)."""
    if force:
        yangilash(kalit)
    v = versiya(kalit)
    if kesh.get("cfg") is not None and kesh.get("mtime") == v:
        return kesh["cfg"]
    try:
        raw = json.loads(v) if v else None
    except Exception as e:
        print(f"[OGOHLANTIRISH] {kalit} sozlamasi buzilgan — standart ishlatiladi: {e}")
        raw = None
    cfg = toza_fn(raw)
    kesh.update(mtime=v, cfg=cfg, **tozala)
    return cfg


def modul_saqla(kalit, toza_fn, s, kesh: dict, **tozala) -> bool:
    try:
        ok = yoz(kalit, toza_fn(s))
    except Exception as e:
        print(f"[XATO] {kalit} saqlanmadi: {e}")
        ok = False
    kesh.update(mtime=None, cfg=None, **tozala)
    return ok


def yangilash(kalit=None):
    """Keshni tozalash (keyingi o'qish bazadan)."""
    with _lock:
        if kalit:
            _kesh.pop(kalit, None)
        else:
            _kesh.clear()
