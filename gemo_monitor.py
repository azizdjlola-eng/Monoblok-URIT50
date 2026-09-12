# -*- coding: utf-8 -*-
"""
Gemotologiya (BC-20S) natija kelishini nazorat qilish.

MUAMMO (12.09.2026): analizator bilan TCP ulanish ochiq, heartbeat kelib turadi,
lekin analizator natija yubormay qo'ygan (avtopередача o'chib qolgan). Dastur
hech qanday xato bermagan — bir kun natijalar tushmay qolgani faqat bemor
so'raganda sezilgan. Xuddi OneDrive holati kabi: "jim" nosozlik.

NAZORAT QOIDALARI (alert_config.json -> "gemotologiya" bo'limi):
  1. TARTIB   — bemorda umumiy qon tahlili bor; bioximiya (BK-280) yoki siydik
                (URIT-50) natijasi ALLAQACHON kelgan, qon natijasi esa yo'q.
                Qon odatda birinchi bo'lib chiqadi — tartib buzilishi = signal.
  2. KECHIKISH — buyurtma berilganidan `delay_alert_min` (60) daqiqa o'tdi,
                gemotologik natija hali ham yo'q.
  3. ERTALAB  — `morning_check_time` (08:20) gacha bugun birorta ham
                gemotologik natija kelmagan (qon buyurtmasi bo'lsa yoki
                ulanish nosoz bo'lsa).
  Har signal oldidan ULANISH holati tekshiriladi (TCP ulangan? heartbeat
  kelyaptimi?) va xabarda aniq sabab ko'rsatiladi:
     - "ulanish yo'q"            → tarmoq/kabel/analizator o'chiq
     - "heartbeat yo'q"          → ulanish osilib qolgan (dasturni qayta ishga tushiring)
     - "ulanish sog'lom, natija yo'q" → analizator yubormayapti (avtопередача /
                                        Обзор → Передать)

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
    # Bir xil muammo haqida takror ogohlantirish oralig'i (daqiqa)
    "repeat_alert_min": 30,
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


# ══════════════════════════════════════════════════════════════════════════
#  TEKSHIRUV
# ══════════════════════════════════════════════════════════════════════════
def _in_work_hours(cfg, now):
    sh, sm = _parse_hhmm(cfg.get("work_start", "07:00"), (7, 0))
    eh, em = _parse_hhmm(cfg.get("work_end", "19:00"), (19, 0))
    t = (now.hour, now.minute)
    return (sh, sm) <= t <= (eh, em)


def check(cfg=None, now=None, morning=True):
    """Gemotologiya natija oqimini tekshiradi.

    Qaytaradi dict:
        level    — 'ok' | 'crit'
        problems — [str]
        summary  — bir qatorli xulosa
        stats    — {conn, orders, missing, today_results, ...}
        key      — takror-ogohlantirishni cheklash uchun kalit
    """
    cfg = cfg or load_config()
    now = now or datetime.datetime.now()
    state = _load_state()
    problems = []
    stats = {"orders": [], "missing": [], "today_results": None, "conn": None,
             "morning_checked": False}

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

    delay_min = float(cfg.get("delay_alert_min", 60) or 60)
    for o in orders:
        if o["cbc"]:
            continue
        age_min = (now - o["sana_vaqt"]).total_seconds() / 60.0
        who = f"{o['fish']} (№{o['sample_id'] or o['id']}, {o['sana_vaqt'].strftime('%H:%M')})"
        reasons = []
        if o["bio"] or o["urine"]:
            came = " va ".join([n for n, f in (("bioximiya", o["bio"]), ("siydik", o["urine"])) if f])
            reasons.append(f"{came} natijasi keldi, QON YO'Q")
        if age_min >= delay_min:
            reasons.append(f"{int(age_min)} daqiqadan beri qon natijasi yo'q")
        if reasons:
            stats["missing"].append(o["id"])
            problems.append(f"{who}: " + "; ".join(reasons))

    # ── Ertalabki tekshiruv (kuniga bir marta) ─────────────────────────────
    if morning:
        mh, mm = _parse_hhmm(cfg.get("morning_check_time", "08:20"), (8, 20))
        today = now.strftime("%Y-%m-%d")
        if (now.hour, now.minute) >= (mh, mm) and state.get("morning_done") != today:
            stats["morning_checked"] = True
            try:
                cnt = _count_today_cbc_results()
            except Exception as e:
                cnt = None
                problems.append(f"Bugungi natijalar sonini olib bo'lmadi: {e}")
            stats["today_results"] = cnt
            if cnt == 0:
                if conn_bad:
                    problems.append(f"Soat {mh:02d}:{mm:02d} — bugun birorta gemotologik natija yo'q "
                                    f"va ULANISH NOSOZ")
                elif orders:
                    problems.append(f"Soat {mh:02d}:{mm:02d} — {len(orders)} ta qon buyurtmasi bor, "
                                    f"analizatordan birorta natija kelmagan")
            state["morning_done"] = today
            _save_state(state)

    # ── Ulanish nosoz bo'lsa — o'zi alohida muammo ─────────────────────────
    if conn_bad:
        problems.insert(0, "ULANISH: " + conn.get("text", ""))

    # ── Sabab (natija yo'q + ulanish sog'lom = analizator yubormayapti) ────
    if problems and not conn_bad and (stats["missing"] or stats["morning_checked"]):
        problems.append("Ulanish sog'lom — demak ANALIZATOR natija yubormayapti: "
                        "Настройка → Связь → Автопередача ni tekshiring; "
                        "eskilarini Обзор → Передать bilan yuboring.")

    level = "crit" if problems else "ok"
    if level == "ok":
        n_done = sum(1 for o in orders if o["cbc"])
        summary = f"Gemotologiya: {n_done}/{len(orders)} qon natijasi kelgan, ulanish sog'lom"
    else:
        summary = f"Gemotologiya: {len(stats['missing'])} ta qon natijasi kelmagan" + \
                  (" — ULANISH NOSOZ" if conn_bad else "")

    key = "{}|{}|{}".format(level, int(conn_bad), ",".join(str(i) for i in stats["missing"]))
    return {"level": level, "problems": problems, "summary": summary,
            "stats": stats, "key": key, "time": now}


def format_report(res):
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
    if s.get("today_results") is not None:
        lines.append(f"Bugun analizatordan kelgan natijalar: {s['today_results']}")
    orders = s.get("orders") or []
    if orders:
        lines.append("")
        lines.append("Bugungi qon buyurtmalari:")
        for o in orders:
            mark = "✓ qon" if o["cbc"] else "✗ QON YO'Q"
            extra = []
            if o["bio"]:
                extra.append("bio ✓")
            if o["urine"]:
                extra.append("siydik ✓")
            lines.append("   {}  {:<28} {:<12} {}".format(
                o["sana_vaqt"].strftime("%H:%M"), (o["fish"] or "")[:28],
                mark, ", ".join(extra)))
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
#  KUZATUVCHI OQIM
# ══════════════════════════════════════════════════════════════════════════
class GemoWatcher:
    """Fon oqimida davriy tekshiradi; muammo bo'lsa on_alert, har safar on_status.
    Ikkalasi ham fon oqimidan chaqiriladi — tkinter uchun root.after() bilan o'rang."""

    def __init__(self, on_alert=None, on_status=None, cfg=None):
        self.on_alert = on_alert
        self.on_status = on_status
        self.cfg = cfg or load_config()
        self._stop = threading.Event()
        self._thread = None
        self._last_alert_key = None
        self._last_alert_ts = 0.0
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

        gap = float(cfg.get("repeat_alert_min", 30) or 30) * 60
        ts = time.time()
        if res["key"] == self._last_alert_key and (ts - self._last_alert_ts) < gap:
            return res
        self._last_alert_key = res["key"]
        self._last_alert_ts = ts

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
