# -*- coding: utf-8 -*-
"""
Gemotologiya (BC-20S) natija kelishini nazorat qilish.

MUAMMO (12.09.2026): analizator bilan TCP ulanish ochiq, heartbeat kelib turadi,
lekin analizator natija yubormay qo'ygan (avtopередача o'chib qolgan). Dastur
hech qanday xato bermagan — bir kun natijalar tushmay qolgani faqat bemor
so'raganda sezilgan. Xuddi OneDrive holati kabi: "jim" nosozlik.

NAZORAT QOIDALARI (alert_config.json -> "gemotologiya" bo'limi):
  1. TARTIB   — bemorda umumiy qon tahlili bor; bioximiya (BK-280) yoki siydik
                (URIT-50) natijasi ALLAQACHON kelgan, qon natijasi esa yo'q va
                buyurtmadan `order_rule_min_age_min` (20) daqiqa o'tgan.
  2. KECHIKISH — buyurtma berilganidan `delay_alert_min` (60) daqiqa o'tdi,
                gemotologik natija hali ham yo'q.
  3. ERTALAB  — `morning_check_time` (08:20) gacha bugun birorta ham
                gemotologik natija kelmagan, vaholanki kamida
                `morning_min_age_min` (30) daqiqalik qon buyurtmasi bor.
  4. EGASIZ   — analizatordan CBC natijasi keldi va bazaga yozildi, lekin shu
                buyurtmada "Qonning umumiy tahlili" YO'Q (qabulda qo'shilmagan
                yoki namuna ID adashgan) — natija blankaga chiqmaydi.

SABABNI ANIQLASH (16.09.2026 tajribasi: signal to'g'ri chiqdi — probirka
esdan chiqqan edi, lekin xabar "analizator yubormayapti" deb yolg'on yo'l
ko'rsatdi). Endi har yetishmayotgan namuna uchun:
     - ulanish yo'q / heartbeat yo'q      → tarmoq/kabel/dastur
     - shu buyurtmadan KEYIN boshqa namunalar kelgan → analizator ishlayapti,
                                             BU NAMUNA O'TKAZILMAGAN (probirka/bemor)
     - shu buyurtmadan beri hech narsa kelmagan → analizator yubormayapti
                                             (Автопередача / Обзор → Передать)

SIGNAL TARTIBI (hamshiralar ko'nikib qolmasligi uchun):
     - popup faqat YANGI muammo paydo bo'lganda; xuddi shu muammo uchun eng
       ko'pi `max_popups_per_order` (2) marta, oralig'i `repeat_alert_min` (90)
     - "keyin topshiradi" deb belgilangan (snooze) bemor bugun signal bermaydi
     - ulanish nosozligi faqat qon KUTILAYOTGAN bemor bo'lsa signal beradi
     - qolgan vaqtda faqat tugma qizil bo'lib turadi (holat oynasida to'liq ro'yxat)
     - hisob state fayliga yoziladi — dastur qayta ochilsa ham takror popup yo'q

"Qon natijasi keldi" deb nimani hisoblaymiz:
  test_results da shu buyurtma uchun `"source": "BC-20S"` yozuvi (WBC, HGB, ...)
  YOKI test_name = "Qonning umumiy tahlili" (qo'lda / hematologiya oynasidan
  import qilingan) — ikkalasi ham yetarli.
"""

import os
import sys
import json
import time
import threading
import datetime

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(BASE_DIR, "alert_config.json")
_STATE_PATH = os.path.join(BASE_DIR, "gemo_monitor_state.json")

DEFAULT_CONFIG = {
    "enabled": True,
    # Necha daqiqada bir tekshirish
    "check_interval_min": 5,
    # Qoida 2: buyurtmadan shuncha daqiqa o'tsa-yu qon natijasi yo'q — signal
    "delay_alert_min": 60,
    # Qoida 3: shu vaqtgacha bugun birorta gemotologik natija kelmasa — signal
    "morning_check_time": "08:20",
    # Heartbeat shuncha soniyadan beri kelmagan bo'lsa — ulanish osilgan
    "heartbeat_timeout_sec": 30,
    # Qoida 3: ertalabki signal uchun eng eski qon buyurtmasi kamida shuncha daqiqalik bo'lsin
    "morning_min_age_min": 30,
    # Qoida 1 (tartib) buyurtmadan shuncha daqiqa o'tgandagina ishlaydi
    "order_rule_min_age_min": 20,
    # Bir xil muammo haqida takror popup oralig'i (daqiqa) va eng ko'p popup soni
    "repeat_alert_min": 90,
    "max_popups_per_order": 2,
    # Umumiy qon tahlilini aniqlash: order_items.tahlil_id yoki nomi (kichik harf, qism)
    "cbc_tahlil_ids": [27],
    "cbc_name_parts": ["qonning umumiy", "umumiy qon"],
    # Faqat shu soatlar oralig'ida signal beriladi (kechasi bezovta qilmaslik)
    "work_start": "07:00",
    "work_end": "19:00",
    "sound": True,
    "popup": True,
}

_CFG_CACHE = [None]


def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(force=False):
    """alert_config.json -> "gemotologiya" bo'limi (bo'lmasa DEFAULT_CONFIG)."""
    if _CFG_CACHE[0] is not None and not force:
        return _CFG_CACHE[0]
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                whole = json.load(f)
            cfg = _deep_merge(cfg, whole.get("gemotologiya", {}))
    except Exception as e:
        print(f"[GemoNazorat] Konfig o'qishda xato: {e}")
    _CFG_CACHE[0] = cfg
    return cfg


def _load_state():
    try:
        if os.path.exists(_STATE_PATH):
            with open(_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(state):
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _parse_hhmm(s, default=(8, 20)):
    try:
        h, m = str(s).strip().split(":")
        return int(h), int(m)
    except Exception:
        return default


# ══════════════════════════════════════════════════════════════════════════
#  ULANISH HOLATI (bc20s_listener dan)
# ══════════════════════════════════════════════════════════════════════════
def get_connection_status(cfg=None):
    """{'running','connected','last_rx','last_result','heartbeat_ok','text'}"""
    cfg = cfg or load_config()
    st = {"running": None, "connected": None, "last_rx": None,
          "last_result": None, "heartbeat_ok": None, "text": ""}
    try:
        import bc20s_listener
        s = bc20s_listener.get_status()
        st.update(s)
    except Exception as e:
        st["text"] = f"listener holati olinmadi: {e}"
        return st

    now = datetime.datetime.now()
    hb_timeout = float(cfg.get("heartbeat_timeout_sec", 30) or 30)

    # Heartbeat faqat Mindray (tcp_client) uslubida bor. tcp_server / serial analizatorlar
    # (Genrui, Dymind, Sysmex ...) faqat natija yuborganda ulanadi — "ulanish yo'q" normal holat.
    try:
        from monoblok_db_config import get_analyzer
        _ct = (get_analyzer("gemotologiya") or {}).get("connection_type", "tcp_client")
    except Exception:
        _ct = "tcp_client"
    if _ct != "tcp_client":
        if not st.get("running"):
            st["heartbeat_ok"] = False
            st["text"] = "Gemotologiya listener ISHLAMAYAPTI (oqim to'xtagan)"
        else:
            st["heartbeat_ok"] = True
            st["text"] = ("Server tinglayapti — analizator natija yuborganda ulanadi"
                          if _ct == "tcp_server" else "COM port ochiq — natija kutilmoqda")
        return st

    if not st.get("running"):
        st["heartbeat_ok"] = False
        st["text"] = "BC-20S mijozi ISHLAMAYAPTI (oqim to'xtagan)"
    elif not st.get("connected"):
        st["heartbeat_ok"] = False
        st["text"] = "Analizator bilan ULANISH YO'Q (qayta ulanishga urinmoqda)"
    elif st.get("last_rx") is None:
        st["heartbeat_ok"] = False
        st["text"] = "Ulangan, lekin analizatordan hali hech narsa kelmadi"
    else:
        age = (now - st["last_rx"]).total_seconds()
        if age > hb_timeout:
            st["heartbeat_ok"] = False
            st["text"] = f"Ulangan, lekin HEARTBEAT {int(age)} s dan beri yo'q (ulanish osilgan)"
        else:
            st["heartbeat_ok"] = True
            st["text"] = "Ulanish sog'lom (heartbeat kelyapti)"
    return st


# ══════════════════════════════════════════════════════════════════════════
#  BAZA: bugungi qon buyurtmalari va kelgan natijalar
# ══════════════════════════════════════════════════════════════════════════
def _fetch_today_cbc_orders(cfg):
    """[{id, sample_id, sana_vaqt, fish, cbc, bio, urine}] — bugungi, o'chirilmagan."""
    from monoblok_db_config import DB_CONFIG
    import mysql.connector

    ids = [int(x) for x in (cfg.get("cbc_tahlil_ids") or []) if str(x).strip().isdigit()]
    parts = [str(p).lower() for p in (cfg.get("cbc_name_parts") or []) if str(p).strip()]

    conds, params = [], []
    if ids:
        conds.append("oi.tahlil_id IN (" + ",".join(["%s"] * len(ids)) + ")")
        params.extend(ids)
    for p in parts:
        conds.append("LOWER(oi.nomi) LIKE %s")
        params.append(f"%{p}%")
    if not conds:
        return []

    conn = mysql.connector.connect(connection_timeout=10, **DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(f"""
            SELECT o.id, o.sample_id, o.sana_vaqt, b.fish
            FROM orders o
            JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.sana_vaqt >= CURDATE()
              AND o.deleted_at IS NULL
              AND EXISTS (SELECT 1 FROM order_items oi
                          WHERE oi.order_id = o.id AND ({' OR '.join(conds)}))
            ORDER BY o.sana_vaqt
        """, params)
        orders = cur.fetchall()
        for o in orders:
            o["cbc"] = o["bio"] = o["urine"] = False
        if not orders:
            return orders

        # test_results.order_id VARCHAR (kollatsiya farqi) — Python da moslaymiz
        by_id = {str(o["id"]): o for o in orders}
        keys = list(by_id.keys())
        cur.execute(f"""
            SELECT order_id, test_name, result_data FROM test_results
            WHERE order_id IN ({",".join(["%s"] * len(keys))})
        """, keys)
        for r in cur.fetchall():
            o = by_id.get(str(r["order_id"]))
            if not o:
                continue
            rd = r.get("result_data") or ""
            tn = (r.get("test_name") or "").lower()
            if '"source": "BC-20S"' in rd or any(p in tn for p in parts):
                o["cbc"] = True
            elif '"source": "BK-280"' in rd:
                o["bio"] = True
            elif '"source": "URIT-50"' in rd:
                o["urine"] = True
        return orders
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_today_cbc_results():
    """Bugun BC-20S dan kelgan natijali buyurtmalar soni (test_results bo'yicha)."""
    from monoblok_db_config import DB_CONFIG
    import mysql.connector
    conn = mysql.connector.connect(connection_timeout=10, **DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(DISTINCT order_id) FROM test_results
                       WHERE created_at >= CURDATE()
                         AND result_data LIKE '%"source": "BC-20S"%'""")
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _fetch_today_bc20s_arrivals():
    """Bugun BC-20S natijasi kelgan buyurtmalar: {order_id(str): oxirgi created_at}.
    Sabab aniqlash uchun ("shu buyurtmadan keyin boshqa namuna keldimi?")."""
    from monoblok_db_config import DB_CONFIG
    import mysql.connector
    conn = mysql.connector.connect(connection_timeout=10, **DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""SELECT order_id, MAX(created_at) FROM test_results
                       WHERE created_at >= CURDATE()
                         AND result_data LIKE '%"source": "BC-20S"%'
                       GROUP BY order_id""")
        return {str(r[0]): r[1] for r in cur.fetchall() if r[1]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _cbc_item_conds(cfg):
    ids = [int(x) for x in (cfg.get("cbc_tahlil_ids") or []) if str(x).strip().isdigit()]
    parts = [str(p).lower() for p in (cfg.get("cbc_name_parts") or []) if str(p).strip()]
    conds, params = [], []
    if ids:
        conds.append("oi.tahlil_id IN (" + ",".join(["%s"] * len(ids)) + ")")
        params.extend(ids)
    for p in parts:
        conds.append("LOWER(oi.nomi) LIKE %s")
        params.append(f"%{p}%")
    return conds, params


def _fetch_orphan_cbc_orders(cfg, arrivals):
    """Qoida 4: BC-20S natijasi bor, lekin buyurtmada umumiy qon tahlili YO'Q.
    [{id, sample_id, sana_vaqt, fish, arrived}]"""
    oids = [int(k) for k in (arrivals or {}).keys() if str(k).strip().isdigit()]
    conds, params = _cbc_item_conds(cfg)
    if not oids or not conds:
        return []
    from monoblok_db_config import DB_CONFIG
    import mysql.connector
    conn = mysql.connector.connect(connection_timeout=10, **DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(f"""
            SELECT o.id, o.sample_id, o.sana_vaqt, b.fish
            FROM orders o
            JOIN bemorlar b ON o.bemor_id = b.id
            WHERE o.id IN ({",".join(["%s"] * len(oids))})
              AND o.deleted_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM order_items oi
                              WHERE oi.order_id = o.id AND ({' OR '.join(conds)}))
            ORDER BY o.sana_vaqt
        """, oids + params)
        rows = cur.fetchall()
        for r in rows:
            r["arrived"] = arrivals.get(str(r["id"]))
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════
#  SNOOZE — "keyin topshiradi" / "tekshirildi" belgisi (bugun signal bermaydi)
# ══════════════════════════════════════════════════════════════════════════
def _today_str(now=None):
    return (now or datetime.datetime.now()).strftime("%Y-%m-%d")


def _prune_state(state, now=None):
    """Kechagi snooze/popup yozuvlarini tozalash (faqat bugungi buyurtmalar kerak)."""
    today = _today_str(now)
    for key in ("snoozed", "alerted"):
        d = state.get(key) or {}
        state[key] = {k: v for k, v in d.items()
                      if isinstance(v, dict) and v.get("date") == today}
    return state


def snooze_order(order_id, note="", now=None):
    """Bemor bugun signal bermasin (masalan: 'abetdan keyin topshiradi')."""
    now = now or datetime.datetime.now()
    state = _prune_state(_load_state(), now)
    state["snoozed"][str(order_id)] = {"date": _today_str(now), "note": note or "",
                                       "ts": now.strftime("%H:%M")}
    _save_state(state)


def unsnooze_order(order_id):
    state = _prune_state(_load_state())
    state["snoozed"].pop(str(order_id), None)
    _save_state(state)


def get_snoozed():
    return dict(_prune_state(_load_state()).get("snoozed") or {})


# ══════════════════════════════════════════════════════════════════════════
#  TEKSHIRUV
# ══════════════════════════════════════════════════════════════════════════
def _in_work_hours(cfg, now):
    sh, sm = _parse_hhmm(cfg.get("work_start", "07:00"), (7, 0))
    eh, em = _parse_hhmm(cfg.get("work_end", "19:00"), (19, 0))
    return (sh, sm) <= (now.hour, now.minute) <= (eh, em)


def _diagnose(o, conn_bad, arrivals, last_result_ts):
    """Yetishmayotgan namuna uchun ANIQ sabab va harakat matni -> (cause, action)."""
    if conn_bad:
        return ("ulanish nosoz",
                "ulanish/heartbeat yo'q — kabel va analizatorni tekshiring, "
                "kerak bo'lsa dasturni qayta oching")
    after = [t for t in arrivals.values() if t and t > o["sana_vaqt"]]
    if last_result_ts and last_result_ts > o["sana_vaqt"]:
        after.append(last_result_ts)
    if after:
        last_t = max(after).strftime("%H:%M")
        return ("namuna o'tkazilmagan",
                f"analizator ISHLAYAPTI (oxirgi natija {last_t}) — bu probirka analizatorda "
                f"o'tkazilmagan yoki boshqa ID bilan o'tkazilgan: probirkani/bemorni tekshiring")
    return ("analizator yubormayapti",
            "buyurtmadan beri analizatordan birorta natija kelmagan — Настройка → Связь → "
            "Автопередача ni tekshiring, eskilarini Обзор → Передать bilan yuboring")


def check(cfg=None, now=None, morning=True):
    """Gemotologiya natija oqimini tekshiradi.

    Qaytaradi dict:
        level    — 'ok' | 'crit'
        problems — [str]  (odam o'qiydigan, sabab + harakat bilan)
        summary  — bir qatorli xulosa
        stats    — {conn, orders, missing, missing_details, orphans, snoozed,
                    problem_ids, conn_alert, ...}
        key      — muammo to'plami kaliti
    """
    cfg = cfg or load_config()
    now = now or datetime.datetime.now()
    state = _prune_state(_load_state(), now)
    snoozed = state.get("snoozed") or {}
    problems = []
    stats = {"orders": [], "missing": [], "missing_details": [], "orphans": [],
             "snoozed": snoozed, "today_results": None, "conn": None,
             "morning_checked": False, "morning_alert": False, "conn_alert": False}

    # ── Ulanish ───────────────────────────────────────────────────────────
    conn = get_connection_status(cfg)
    stats["conn"] = conn
    conn_bad = conn.get("heartbeat_ok") is False

    # ── Buyurtmalar ───────────────────────────────────────────────────────
    try:
        orders = _fetch_today_cbc_orders(cfg)
    except Exception as e:
        orders = []
        problems.append(f"Bazadan buyurtmalarni o'qib bo'lmadi: {e}")
    stats["orders"] = orders

    try:
        arrivals = _fetch_today_bc20s_arrivals()
    except Exception:
        arrivals = {}
    last_result_ts = conn.get("last_result")

    delay_min = float(cfg.get("delay_alert_min", 60) or 60)
    order_rule_min = float(cfg.get("order_rule_min_age_min", 20) or 0)
    for o in orders:
        o["snoozed"] = str(o["id"]) in snoozed
        o["cause"] = None
        if o["cbc"]:
            continue
        age_min = (now - o["sana_vaqt"]).total_seconds() / 60.0
        o["age_min"] = int(age_min)
        reasons = []
        if (o["bio"] or o["urine"]) and age_min >= order_rule_min:
            came = " va ".join([n for n, f in (("bioximiya", o["bio"]), ("siydik", o["urine"])) if f])
            reasons.append(f"{came} natijasi keldi, qon yo'q")
        if age_min >= delay_min:
            reasons.append(f"{int(age_min)} daqiqadan beri qon natijasi yo'q")
        if not reasons:
            continue
        cause, action = _diagnose(o, conn_bad, arrivals, last_result_ts)
        o["cause"] = cause
        who = f"{o['fish']} (№{o['sample_id'] or o['id']}, {o['sana_vaqt'].strftime('%H:%M')})"
        stats["missing_details"].append({"id": o["id"], "who": who, "cause": cause,
                                         "action": action, "reasons": reasons,
                                         "snoozed": o["snoozed"]})
        if o["snoozed"]:
            continue  # keyin topshiradi — signal yo'q, ro'yxatda ⏳ bilan ko'rinadi
        stats["missing"].append(o["id"])
        problems.append(f"{who}: " + "; ".join(reasons) + f"\n      → {action}")

    # ── Qoida 4: egasiz CBC natijasi ───────────────────────────────────────
    try:
        orphans = _fetch_orphan_cbc_orders(cfg, arrivals)
    except Exception as e:
        orphans = []
        problems.append(f"Egasiz natijalarni tekshirib bo'lmadi: {e}")
    stats["orphans"] = orphans
    for r in orphans:
        r["snoozed"] = str(r["id"]) in snoozed
        if r["snoozed"]:
            continue
        who = f"{r['fish']} (№{r['sample_id'] or r['id']}, {r['sana_vaqt'].strftime('%H:%M')})"
        at = r["arrived"].strftime("%H:%M") if r.get("arrived") else "?"
        problems.append(f"{who}: analizator {at} da CBC natijasini yubordi, lekin buyurtmada "
                        f"\"Qonning umumiy tahlili\" YO'Q — natija blankaga chiqmaydi\n"
                        f"      → qabulda buyurtmaga qon tahlilini qo'shing yoki namuna ID ni tekshiring")

    # ── Ertalabki tekshiruv (kuniga bir marta) ─────────────────────────────
    if morning:
        mh, mm = _parse_hhmm(cfg.get("morning_check_time", "08:20"), (8, 20))
        today = _today_str(now)
        if (now.hour, now.minute) >= (mh, mm) and state.get("morning_done") != today:
            stats["morning_checked"] = True
            try:
                cnt = _count_today_cbc_results()
            except Exception as e:
                cnt = None
                problems.append(f"Bugungi natijalar sonini olib bo'lmadi: {e}")
            stats["today_results"] = cnt
            min_age = float(cfg.get("morning_min_age_min", 30) or 0)
            old_enough = [o for o in orders
                          if not o["snoozed"]
                          and (now - o["sana_vaqt"]).total_seconds() / 60.0 >= min_age]
            if cnt == 0 and old_enough:
                stats["morning_alert"] = True
                if conn_bad:
                    problems.append(f"Soat {mh:02d}:{mm:02d} — bugun birorta gemotologik natija yo'q "
                                    f"va ULANISH NOSOZ\n      → kabel/analizator/dasturni tekshiring")
                else:
                    problems.append(f"Soat {mh:02d}:{mm:02d} — {len(old_enough)} ta qon buyurtmasi bor, "
                                    f"analizatordan birorta natija kelmagan\n"
                                    f"      → Настройка → Связь → Автопередача ni tekshiring")
            state["morning_done"] = today
            _save_state(state)

    # ── Ulanish nosoz — faqat qon KUTILAYOTGAN bemor bo'lsa signal ────────
    # (bo'sh vaqtda analizator o'chiq bo'lishi tabiiy — bezovta qilmaymiz)
    waiting = [o for o in orders if not o["cbc"] and not o["snoozed"]]
    if conn_bad and waiting:
        stats["conn_alert"] = True
        problems.insert(0, "ULANISH: " + conn.get("text", "") +
                        f" — {len(waiting)} ta bemor qon natijasini kutmoqda")

    level = "crit" if problems else "ok"
    n_done = sum(1 for o in orders if o["cbc"])
    n_snz = sum(1 for o in orders if not o["cbc"] and o["snoozed"])
    if level == "ok":
        summary = f"Gemotologiya: {n_done}/{len(orders)} qon natijasi kelgan"
        summary += ", ulanish sog'lom" if not conn_bad else " (ulanish yo'q, kutilayotgan bemor yo'q)"
        if n_snz:
            summary += f", {n_snz} ta keyinga qoldirilgan"
    else:
        bits = []
        if stats["missing"]:
            bits.append(f"{len(stats['missing'])} ta qon natijasi kelmagan")
        n_orph = sum(1 for r in orphans if not r["snoozed"])
        if n_orph:
            bits.append(f"{n_orph} ta egasiz natija")
        if stats["conn_alert"]:
            bits.append("ULANISH NOSOZ")
        summary = "Gemotologiya: " + (", ".join(bits) or "muammo")

    # muammoli buyurtmalar (popup qarori shu ro'yxat bo'yicha)
    problem_ids = sorted(set([str(i) for i in stats["missing"]] +
                             [str(r["id"]) for r in orphans if not r["snoozed"]]))
    stats["problem_ids"] = problem_ids
    key = "{}|{}|{}".format(level, int(stats["conn_alert"]), ",".join(problem_ids))
    return {"level": level, "problems": problems, "summary": summary,
            "stats": stats, "key": key, "time": now}


def format_report(res, full=True):
    """full=True — holat oynasi (to'liq ro'yxat); full=False — popup (faqat muammo + harakat)."""
    s = res.get("stats", {})
    icon = {"ok": "[OK]", "crit": "[XATO]"}.get(res.get("level"), "")
    lines = ["{} {}".format(icon, res.get("summary", "")), ""]
    for p in res.get("problems", []):
        lines.append("  • " + p)
    if res.get("problems"):
        lines.append("")
    conn = s.get("conn") or {}
    lines.append("Ulanish: " + str(conn.get("text", "?")))
    if conn.get("last_result"):
        lines.append("Oxirgi natija: " + conn["last_result"].strftime("%d.%m.%Y %H:%M:%S"))
    if not full:
        return "\n".join(lines)
    if s.get("today_results") is not None:
        lines.append(f"Bugun analizatordan kelgan natijalar: {s['today_results']}")
    snoozed = s.get("snoozed") or {}
    orders = s.get("orders") or []
    if orders:
        lines.append("")
        lines.append("Bugungi qon buyurtmalari:")
        for o in orders:
            if o["cbc"]:
                mark = "✓ qon"
            elif o.get("snoozed"):
                note = (snoozed.get(str(o["id"])) or {}).get("note") or "keyin topshiradi"
                mark = f"⏳ {note}"
            elif o.get("cause"):
                mark = "✗ QON YO'Q — " + o["cause"]
            else:
                mark = "… kutilmoqda"
            extra = []
            if o["bio"]:
                extra.append("bio ✓")
            if o["urine"]:
                extra.append("siydik ✓")
            lines.append("   {}  {:<28} {:<36} {}".format(
                o["sana_vaqt"].strftime("%H:%M"), (o["fish"] or "")[:28],
                mark, ", ".join(extra)))
    orphans = s.get("orphans") or []
    if orphans:
        lines.append("")
        lines.append("Egasiz CBC natijalari (buyurtmada qon tahlili yo'q):")
        for r in orphans:
            mark = "⏳ belgilangan" if r.get("snoozed") else "✗ buyurtmaga qo'shing"
            lines.append("   {}  {:<28} natija {}  {}".format(
                r["sana_vaqt"].strftime("%H:%M"), (r["fish"] or "")[:28],
                r["arrived"].strftime("%H:%M") if r.get("arrived") else "?", mark))
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
#  KUZATUVCHI OQIM
# ══════════════════════════════════════════════════════════════════════════
class GemoWatcher:
    """Fon oqimida davriy tekshiradi; muammo bo'lsa on_alert, har safar on_status.
    Ikkalasi ham fon oqimidan chaqiriladi — tkinter uchun root.after() bilan o'rang.

    Popup siyosati: har muammoli buyurtma uchun birinchi marta darhol, keyin
    `repeat_alert_min` dan so'ng yana bir marta (jami `max_popups_per_order`).
    Undan keyin faqat tugma qizil turadi. Hisob state faylida — dastur qayta
    ochilsa ham takrorlanmaydi."""

    def __init__(self, on_alert=None, on_status=None, cfg=None):
        self.on_alert = on_alert
        self.on_status = on_status
        self.cfg = cfg or load_config()
        self._stop = threading.Event()
        self._thread = None
        self.last_result = None

    def start(self, first_delay_sec=120):
        if not self.cfg.get("enabled", True):
            print("[GemoNazorat] Nazorat o'chirilgan (alert_config.json)")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(first_delay_sec,), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def _loop(self, first_delay_sec):
        if self._stop.wait(first_delay_sec):
            return
        while not self._stop.is_set():
            try:
                self.check_now()
            except Exception as e:
                print(f"[GemoNazorat] Nazoratda xato: {e}")
            interval = float(self.cfg.get("check_interval_min", 5) or 5) * 60
            if self._stop.wait(max(interval, 60)):
                return

    def _should_notify(self, res, cfg, now):
        """Popup kerakmi? Faqat YANGI yoki eslatma muddati kelgan muammolar uchun.
        Har muammo (buyurtma / ulanish / ertalab) uchun alohida hisob state faylida."""
        st = res.get("stats", {})
        ids = list(st.get("problem_ids") or [])
        if st.get("conn_alert"):
            ids.append("conn")
        if st.get("morning_alert"):
            ids.append("morning")
        if not ids:
            return False

        state = _prune_state(_load_state(), now)
        alerted = state.setdefault("alerted", {})
        max_n = max(1, int(cfg.get("max_popups_per_order", 2) or 1))
        gap = float(cfg.get("repeat_alert_min", 90) or 90) * 60
        today = _today_str(now)
        due = []
        for pid in ids:
            rec = alerted.get(pid)
            if not rec:
                due.append(pid)
                continue
            if int(rec.get("count", 0)) >= max_n:
                continue
            try:
                last = datetime.datetime.fromisoformat(rec.get("last"))
            except Exception:
                last = None
            if last is None or (now - last).total_seconds() >= gap:
                due.append(pid)
        if not due:
            return False
        for pid in due:
            rec = alerted.get(pid) or {"date": today, "count": 0}
            rec["date"] = today
            rec["count"] = int(rec.get("count", 0)) + 1
            rec["last"] = now.isoformat(timespec="seconds")
            alerted[pid] = rec
        _save_state(state)
        return True

    def check_now(self, notify=True):
        cfg = load_config(force=True)
        self.cfg = cfg
        now = datetime.datetime.now()
        res = check(cfg, now=now)
        self.last_result = res
        print(f"[GemoNazorat] {res['summary']}")

        if self.on_status:
            try:
                self.on_status(res)
            except Exception as e:
                print(f"[GemoNazorat] status callback xato: {e}")

        if not notify or res["level"] != "crit":
            return res
        if not _in_work_hours(cfg, now):
            return res
        if not self._should_notify(res, cfg, now):
            return res

        if self.on_alert:
            try:
                self.on_alert(res)
            except Exception as e:
                print(f"[GemoNazorat] alert callback xato: {e}")
        return res


if __name__ == "__main__":
    print("Gemotologiya natija nazorati — qo'lda tekshiruv\n")
    r = check(morning=False)
    print(format_report(r))
