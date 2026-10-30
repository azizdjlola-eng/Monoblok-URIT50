"""
Maxsus tahlil turlarini katalog ID siga bog'lash (mijozga moslash).

Dastur maxsus tahlillarni (Umumiy qon tahlili — analizator natijasi, 5-diff jadval,
gistogramma; Umumiy siydik; Bilirubin / Lipid / Buyrak panellari; GTT ...) ilgari
faqat NOMIDAGI SO'Z bo'yicha tanirdi ("umumiy qon", "lipid spektri" ...). Boshqa mijoz
katalogida tahlil "OAK", "Общий анализ крови" kabi nomlangan bo'lsa — analizator
natijasi bemorga biriktirilmas, blankada maxsus jadval chiqmas edi (xato xabarisiz).

Endi har tur uchun katalogdagi tahlil(lar) ID si bilan bog'lanadi:
  • bog'langan tahlil — nomi qanday bo'lishidan qat'i nazar shu tur deb taniladi
    (katalog nomi ham, eski buyurtmalardagi nomi ham — katalog keyin o'zgartirilgan
    bo'lsa); boshqa turlarning so'z qidiruvi unga qo'llanmaydi;
  • bog'lanmagan tahlil — avvalgidek nom bo'yicha (o'zgarishsiz).

Saqlanadi: analizator_config.json → "tahlil_turlari": {tur: [tahlil_id, ...]}
(Tizim Sozlamalari → 🧩 Maxsus tahlillar).
"""

import json
import os
import time

# tur kaliti → (UI nomi, nima uchun kerak)
TURLAR = {
    "gemo_cbc": ("Umumiy qon tahlili",
                 "gemotologiya analizatori natijasi shu tahlilga tushadi; blankada 5-diff jadval, gistogramma"),
    "siydik_umumiy": ("Siydikning umumiy tahlili",
                      "siydik analizatori / test poloska natijasi; kimyoviy + mikroskopiya jadvali"),
    "bilirubin": ("Bilirubin (umumiy, bog'langan, erkin)", "3 qatorli bilirubin paneli"),
    "lipid": ("Lipid spektri", "lipid paneli (TC, HDL, LDL, TG + hisoblangan)"),
    "buyrak": ("Buyrak paneli", "buyrak paneli (mochevina, kreatinin ... + GFR)"),
    "gtt": ("Glyukozaga tolerantlik testi (GTT)", "GTT jadvali"),
    "hav_combo": ("Gepatit A (IgM va IgG, ekspress)", "IgM + IgG + Xulosa qatorlari"),
    "revmo_avto": ("Revmoproba to'liq (avtomat)", "RF + CRP + ASLO analizatordan, bitta jadval"),
    "revmo_qolda": ("Revmoproba (qo'lda)", "RF + CRP + ASLO qo'lda kiritiladi"),
    "qondan_mazok": ("Qondan mazok (morfologiya)", "leykoformula / morfologiya jadvali"),
}

_KESH = {"mtime": "?", "cfg": None, "xarita": {}, "vaqt": 0.0}
_YANGILASH_SEK = 300   # bazadagi nomlar shuncha sekundda bir qayta o'qiladi


def _config_path():
    try:
        import monoblok_db_config as _mc
        return _mc.CONFIG_PATH
    except Exception:
        return ""


def _toza(raw) -> dict:
    out = {k: [] for k in TURLAR}
    if isinstance(raw, dict):
        for k in TURLAR:
            ids = []
            for x in raw.get(k) or []:
                try:
                    i = int(x)
                except (TypeError, ValueError):
                    continue
                if i > 0 and i not in ids:
                    ids.append(i)
            out[k] = ids
    return out


def sozlama(force=False) -> dict:
    path = _config_path()
    try:
        mt = os.path.getmtime(path) if path and os.path.exists(path) else None
    except Exception:
        mt = None
    if not force and _KESH["cfg"] is not None and _KESH["mtime"] == mt:
        return _KESH["cfg"]
    raw = None
    if mt is not None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = (json.load(f) or {}).get("tahlil_turlari")
        except Exception as e:
            print(f"[OGOHLANTIRISH] tahlil_turlari o'qilmadi: {e}")
    cfg = _toza(raw)
    _KESH.update(mtime=mt, cfg=cfg, vaqt=0.0)     # nomlar xaritasi qayta quriladi
    return cfg


def saqla(s: dict) -> bool:
    try:
        import monoblok_db_config as _mc
        cfg = _mc.load_config()
        cfg["tahlil_turlari"] = _toza(s)
        ok = _mc.save_config(cfg)
        _KESH.update(mtime="?", cfg=None, vaqt=0.0)
        return ok
    except Exception as e:
        print(f"[XATO] tahlil_turlari saqlanmadi: {e}")
        return False


def _norm(nom) -> str:
    return " ".join(str(nom or "").lower().split())


def _db():
    import mysql.connector
    from monoblok_db_config import DB_CONFIG
    return mysql.connector.connect(**DB_CONFIG)


def _xarita() -> dict:
    """{normallashgan tahlil nomi: tur} — bog'langan ID larning katalog va buyurtma nomlari."""
    cfg = sozlama()
    ids = {i: k for k, lst in cfg.items() for i in lst}
    if not ids:
        _KESH["xarita"] = {}
        return {}
    if _KESH["vaqt"] and time.time() - _KESH["vaqt"] < _YANGILASH_SEK:
        return _KESH["xarita"]
    m = {}
    try:
        conn = _db()
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT id, nomi FROM tahlillar WHERE id IN ({ph})", tuple(ids))
        rows = list(cur.fetchall())
        cur.execute(f"SELECT DISTINCT tahlil_id, nomi FROM order_items WHERE tahlil_id IN ({ph})",
                    tuple(ids))
        rows += list(cur.fetchall())
        conn.close()
        for tid, nom in rows:
            if nom and int(tid) in ids:
                m.setdefault(_norm(nom), ids[int(tid)])
    except Exception as e:
        print(f"[OGOHLANTIRISH] tahlil_turlari: bazadan nomlar olinmadi: {e}")
        m = _KESH["xarita"]        # eski xarita bilan ishlashda davom etamiz
    _KESH.update(xarita=m, vaqt=time.time())
    return m


def turi(test_name):
    """Tahlil sozlamada qaysi turga bog'langan — tur kaliti yoki None (bog'lanmagan)."""
    if not test_name:
        return None
    try:
        return _xarita().get(_norm(test_name))
    except Exception:
        return None


def tekshir(kalit: str, test_name, eski_qoida) -> bool:
    """Detektor uchun: bog'langan bo'lsa — faqat shu bog'lanish hal qiladi;
    bog'lanmagan bo'lsa — eski nom-qoida (eski_qoida(test_name) -> bool)."""
    t = turi(test_name)
    if t is not None:
        return t == kalit
    return bool(eski_qoida(test_name))


def keshni_tozala():
    _KESH.update(mtime="?", cfg=None, xarita={}, vaqt=0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI
# ─────────────────────────────────────────────────────────────────────────────
def _katalog():
    """[(id, nomi, sample, aktiv)] — butun katalog."""
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id, nomi, sample, aktiv FROM tahlillar ORDER BY nomi")
    rows = [(int(r[0]), str(r[1] or ""), str(r[2] or ""), r[3]) for r in cur.fetchall()]
    conn.close()
    return rows


def ochish_oyna(parent, eski_qoidalar: dict = None):
    """eski_qoidalar — {tur: fn(test_name)->bool} (nom bo'yicha eski aniqlash) — holat
    ustunida "nom bo'yicha topilgan" tahlillarni ko'rsatish uchun."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    eski_qoidalar = eski_qoidalar or {}
    try:
        katalog = _katalog()
    except Exception as e:
        messagebox.showerror("Maxsus tahlillar", f"Bazaga ulanib bo'lmadi:\n{e}", parent=parent)
        return None
    kat = {i: (n, s, a) for i, n, s, a in katalog}
    s = json.loads(json.dumps(sozlama(force=True)))

    win = tk.Toplevel(parent)
    win.title("🧩 Maxsus tahlillar — katalogga bog'lash")
    win.geometry("1100x640")
    win.minsize(900, 500)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1060, text=(
        "Dastur quyidagi tahlillarni maxsus ishlaydi (analizator natijasi, alohida jadval, panel). "
        "Agar katalogingizdagi nom standart so'zlarga mos kelmasa (masalan «OAK», «Общий анализ крови»), "
        "tahlilni shu yerda bog'lang. Bog'langan tahlil nomi qanday bo'lmasin taniladi. "
        "«⚠ topilmadi» — katalogda bu turga mos tahlil yo'q: bor bo'lsa, albatta bog'lang."
    )).pack(fill=tk.X, padx=10, pady=(8, 4))

    body = ttk.Frame(win)
    body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    cols = ("tur", "boglangan", "nom_boyicha")
    tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
    for c, t, w in (("tur", "Tur", 260), ("boglangan", "Bog'langan tahlil(lar)", 380),
                    ("nom_boyicha", "Hozir nom bo'yicha topilganlar", 380)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor=tk.W)
    tree.tag_configure("ogoh", foreground="#c62828")
    tree.tag_configure("ok", foreground="#1b5e20")
    sb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.LEFT, fill=tk.Y)

    def _nom_boyicha(k):
        fn = eski_qoidalar.get(k)
        if not fn:
            return []
        out = []
        for i, (n, _s, a) in kat.items():
            try:
                if fn(n):
                    out.append(f"{n} [{i}]")
            except Exception:
                pass
        return out

    def _yangila(sel=None):
        tree.delete(*tree.get_children())
        for k, (nomi, izoh) in TURLAR.items():
            bog = [f"{kat.get(i, ('(katalogda yo‘q)',))[0]} [{i}]" for i in s[k]]
            nb = _nom_boyicha(k) if not bog else []
            if bog:
                tag, holat = "ok", "—"
            elif nb:
                tag, holat = "", "; ".join(nb[:3]) + (f" (+{len(nb) - 3})" if len(nb) > 3 else "")
            else:
                tag, holat = "ogoh", "⚠ topilmadi"
            tree.insert("", tk.END, iid=k, tags=(tag,),
                        values=(nomi, "; ".join(bog) or "—", holat))
        if sel:
            tree.selection_set(sel)
            tree.see(sel)

    def _tanlangan():
        sel = tree.selection()
        return sel[0] if sel else None

    def _qosh(_e=None):
        k = _tanlangan()
        if not k:
            messagebox.showinfo("Maxsus tahlillar", "Avval turni tanlang.", parent=win)
            return
        d = tk.Toplevel(win)
        d.title(f"Katalogdan tanlash — {TURLAR[k][0]}")
        d.geometry("620x520")
        d.transient(win)
        try:
            d.grab_set()
        except Exception:
            pass
        v_q = tk.StringVar()
        f = ttk.Frame(d)
        f.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(f, text="Qidiruv:").pack(side=tk.LEFT)
        e = ttk.Entry(f, textvariable=v_q, width=40)
        e.pack(side=tk.LEFT, padx=6)
        lt = ttk.Treeview(d, columns=("id", "nomi", "sample"), show="headings", selectmode="extended")
        for c, t, w in (("id", "ID", 60), ("nomi", "Katalog nomi", 400), ("sample", "Guruh", 80)):
            lt.heading(c, text=t)
            lt.column(c, width=w, anchor=tk.W if c == "nomi" else tk.CENTER)
        lt.pack(fill=tk.BOTH, expand=True, padx=8)

        def _filtr(*_a):
            q = v_q.get().strip().lower()
            lt.delete(*lt.get_children())
            for i, (n, sm, a) in kat.items():
                if q and q not in n.lower() and q != str(i):
                    continue
                lt.insert("", tk.END, iid=str(i), values=(i, n + ("" if a in (1, None, True) else "  (nofaol)"), sm))

        v_q.trace_add("write", _filtr)
        _filtr()
        e.focus_set()

        def _ok(_e=None):
            sel = [int(x) for x in lt.selection()]
            if not sel:
                return
            # bitta tahlil faqat bitta turga bog'lanadi
            for kk in s:
                if kk != k:
                    s[kk] = [i for i in s[kk] if i not in sel]
            s[k] = s[k] + [i for i in sel if i not in s[k]]
            d.destroy()
            _yangila(k)

        lt.bind("<Double-1>", _ok)
        bf = ttk.Frame(d)
        bf.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(bf, text="Bog'lash", command=_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="Bekor", command=d.destroy).pack(side=tk.RIGHT, padx=4)

    def _tozala():
        k = _tanlangan()
        if k and s[k] and messagebox.askyesno(
                "Maxsus tahlillar", f"«{TURLAR[k][0]}» bog'lanishlari olib tashlansinmi?\n"
                "(Shundan keyin nom bo'yicha aniqlanadi.)", parent=win):
            s[k] = []
            _yangila(k)

    side = ttk.Frame(body)
    side.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
    ttk.Button(side, text="＋ Katalogdan bog'lash", command=_qosh, width=22).pack(fill=tk.X, pady=2)
    ttk.Button(side, text="✖ Bog'lanishni olish", command=_tozala, width=22).pack(fill=tk.X, pady=2)
    tree.bind("<Double-1>", _qosh)

    def _saqla():
        if saqla(s):
            messagebox.showinfo("Saqlandi", "[OK] Maxsus tahlillar bog'lanishi saqlandi.\n"
                                "Darhol kuchga kiradi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Sozlamani saqlab bo'lmadi!", parent=win)

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    _yangila(next(iter(TURLAR)))
    win.bind("<Escape>", lambda e: win.destroy())
    return win
