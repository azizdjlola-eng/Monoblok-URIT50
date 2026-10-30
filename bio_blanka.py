"""
Qonning bioximiyaviy tahlili — BLANKA sozlamasi (mijozga moslash).

Bioximiyada yakka tahlilning nomi/normasi/birligi katalogdan («Tahlil Qo'shish»
oynasi) olinadi. Lekin quyidagilar ilgari kodga yozilgan edi va boshqa mijozda
buziladi yoki moslab bo'lmaydi:

  • bo'lim sarlavhasi ("QONNING BIOKIMYOVIY TAHLILI");
  • yakka tahlillarning blankadagi TARTIBI va blankadagi NOMI (katalog nomi
    registratsiya/narx uchun uzun bo'lishi mumkin — blankada boshqacha);
  • panellar (Bilirubin, Lipid spektri, Buyrak paneli): sarlavha, qatorlar nomi,
    normasi, birligi, tartibi, ko'rinishi (hisoblangan qatorlar — KA, GFR ...);
  • panel A'ZOLARINING katalog ID lari (TC=43, Kreatinin=41 ...) — boshqa mijoz
    katalogida ID lar boshqa, panel natijasi yakka tahlillardan yig'ilmay qolardi.

Saqlanadi: analizator_config.json → "bio_blanka" (Tizim Sozlamalari → 🟢 Bioximiya
→ «🧾 Blanka ko'rinishi»). Yo'q bo'lsa — standart (oldingi blanka bilan bir xil).
Bo'sh nom/norma/birlik = standart (katalog / baza / kod qiymati).
"""

import json
import os

DEFAULT_SARLAVHA = "QONNING BIOKIMYOVIY TAHLILI"


def _p(kod, standart, norma="", birlik="", tahlil_id=""):
    return {"kod": kod, "standart": standart, "nom": "", "norma": "", "birlik": "",
            "standart_norma": norma, "standart_birlik": birlik,
            "tahlil_id": str(tahlil_id) if tahlil_id else "", "korsat": "auto"}


# Panel qatorlari: standart nom/norma/birlik — monoblok_dastur dagi oldingi qattiq
# qiymatlar (Lipid va Buyrak normalari baza/shablondan ustun olinadi, bu yerdagi zaxira).
DEFAULT_PANELLAR = {
    "bilirubin": {
        "nomi": "Bilirubin",
        "sarlavha": "BILIRUBIN  (umumiy, bog‘langan, erkin)",
        "qatorlar": [
            _p("umumiy", "Umumiy Bilirubin", "3,4 – 20,5", "mkmol/l"),
            _p("bog_langan", "Bog‘langan Bilirubin", "0,86 – 5,3", "mkmol/l"),
            _p("erkin", "Erkin Bilirubin", "1,7 – 17,1", "mkmol/l"),
        ],
    },
    "lipid": {
        "nomi": "Lipid spektri",
        "sarlavha": "LIPID SPEKTRI",
        "qatorlar": [
            _p("tc", "TC — Umumiy xolesterin (katalog nomi)", "Maqbul: < 5.2 ...", "mmol/L", 43),
            _p("hdl", "HDL — Yuqori zichlikli lipoprotein (katalog nomi)", "Erkak: ≥ 1.0 ...", "mmol/L", 124),
            _p("ldl", "LDL — Past zichlikli lipoprotein (katalog nomi)", "Maqbul: < 3.4 ...", "mmol/L", 123),
            _p("tg", "TG — Trigliseridlar (katalog nomi)", "Maqbul: 0.7 – 1.7 ...", "mmol/L", 44),
            _p("vldl", "VLDL-xolesterin (hisoblangan)", "0.26 – 1.04", "mmol/L"),
            _p("non_hdl", "Non-HDL xolesterin (hisoblangan)", "Maqbul: < 3.4 ...", "mmol/L"),
            _p("ka", "Aterogenlik koeffisienti (KA) (hisoblangan)", "< 3.0 xavf past ...", ""),
            _p("tc_hdl", "TC/HDL nisbati (hisoblangan)", "< 5.0", ""),
            _p("ldl_hdl", "LDL/HDL nisbati (hisoblangan)", "< 3.5", ""),
            _p("tg_hdl", "TG/HDL nisbati (hisoblangan)", "< 1.5", ""),
        ],
    },
    "buyrak": {
        "nomi": "Buyrak paneli",
        "sarlavha": "BUYRAK PANELI",
        "qatorlar": [
            _p("mochevina", "Mochevina (katalog nomi)", "2.5 – 8.3", "mmol/L", 42),
            _p("kreatinin", "Kreatinin (katalog nomi)", "Erkak: 62 – 115 ...", "mkmol/L", 41),
            _p("siydik_kislota", "Siydik kislotasi (katalog nomi)", "Erkak: 210 – 420 ...", "mkmol/L", 50),
            _p("albumin", "Albumin (katalog nomi)", "35 – 52", "g/L", 35),
            _p("bun", "Mochevina azoti (BUN) (hisoblangan)", "1.1 – 3.9", "mmol/L"),
            _p("bun_cr", "Kreatinin / Mochevina nisbati (hisoblangan)", "10 – 20", "µmol/mmol"),
            _p("umumiy_azot", "Umumiy azot miqdori (hisoblangan)", "1.2 – 4.1", "mmol/L"),
            _p("gfr", "GFR — Klubochkaviy filtrlash tezligi (CKD-EPI)", "bosqichlar ...", "ml/min/1.73m²"),
        ],
    },
}
PANEL_KALITLAR = list(DEFAULT_PANELLAR)

KORSAT = {
    "auto": "Doim",
    "natija": "Natija bo'lsa",
    "yashirin": "Yashirin",
}

DEFAULT = {
    "sarlavha": DEFAULT_SARLAVHA,
    "tartib": False,      # True — yakka tahlillar blankada "yakka" ro'yxati tartibida
    "yakka": [],          # [{kod: "<tahlil_id>", katalog, nom}] — blankadagi tartib va nom
    "panellar": DEFAULT_PANELLAR,
}


# ─────────────────────────────────────────────────────────────────────────────
#  O'QISH / SAQLASH
# ─────────────────────────────────────────────────────────────────────────────
_KESH = {"mtime": None, "cfg": None}


def _config_path():
    try:
        import monoblok_db_config as _mc
        return _mc.CONFIG_PATH
    except Exception:
        return ""


def _toza_panel_qator(q: dict, std: dict = None) -> dict:
    std = std or {}
    tid = str(q.get("tahlil_id") or "").strip()
    return {
        "kod": str(q.get("kod") or "").strip(),
        "standart": std.get("standart", q.get("standart", "")),
        "nom": str(q.get("nom") or "").strip(),
        "norma": str(q.get("norma") or "").strip(),
        "birlik": str(q.get("birlik") or "").strip(),
        "standart_norma": std.get("standart_norma", q.get("standart_norma", "")),
        "standart_birlik": std.get("standart_birlik", q.get("standart_birlik", "")),
        "tahlil_id": tid if tid.isdigit() else "",
        "korsat": q.get("korsat") if q.get("korsat") in KORSAT else "auto",
    }


def _toza_yakka(q: dict) -> dict:
    return {"kod": str(q.get("kod") or "").strip(), "katalog": str(q.get("katalog") or "").strip(),
            "nom": str(q.get("nom") or "").strip(), "korsat": "auto"}


def _toza(raw) -> dict:
    s = json.loads(json.dumps(DEFAULT))
    if not isinstance(raw, dict):
        return s
    if isinstance(raw.get("sarlavha"), str) and raw["sarlavha"].strip():
        s["sarlavha"] = raw["sarlavha"].strip()
    s["tartib"] = bool(raw.get("tartib", False))
    if isinstance(raw.get("yakka"), list):
        s["yakka"] = [y for y in (_toza_yakka(q) for q in raw["yakka"] if isinstance(q, dict))
                      if y["kod"].isdigit()]
    rp = raw.get("panellar") if isinstance(raw.get("panellar"), dict) else {}
    for pk, pdef in DEFAULT_PANELLAR.items():
        p = rp.get(pk) if isinstance(rp.get(pk), dict) else {}
        if isinstance(p.get("sarlavha"), str) and p["sarlavha"].strip():
            s["panellar"][pk]["sarlavha"] = p["sarlavha"].strip()
        stdmap = {q["kod"]: q for q in pdef["qatorlar"]}
        if isinstance(p.get("qatorlar"), list) and p["qatorlar"]:
            qs = [_toza_panel_qator(q, stdmap.get(q.get("kod"))) for q in p["qatorlar"]
                  if isinstance(q, dict) and q.get("kod") in stdmap]
            bor = {q["kod"] for q in qs}
            qs += [dict(q) for q in pdef["qatorlar"] if q["kod"] not in bor]
            s["panellar"][pk]["qatorlar"] = qs
    return s


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
                raw = (json.load(f) or {}).get("bio_blanka")
        except Exception as e:
            print(f"[OGOHLANTIRISH] bio_blanka sozlamasi o'qilmadi: {e}")
    cfg = _toza(raw)
    _KESH.update(mtime=mt, cfg=cfg)
    return cfg


def saqla(s: dict) -> bool:
    try:
        import monoblok_db_config as _mc
        cfg = _mc.load_config()
        cfg["bio_blanka"] = _toza(s)
        ok = _mc.save_config(cfg)
        _KESH.update(mtime=None, cfg=None)
        return ok
    except Exception as e:
        print(f"[XATO] bio_blanka saqlanmadi: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  BLANKA UCHUN YORDAMCHILAR
# ─────────────────────────────────────────────────────────────────────────────
def sarlavha(s: dict = None) -> str:
    return (s or sozlama()).get("sarlavha") or DEFAULT_SARLAVHA


def yakka_nomi(tahlil_id, katalog_nomi: str, s: dict = None) -> str:
    """Blankada chiqadigan yakka tahlil nomi (sozlamada berilmagan bo'lsa — katalog nomi)."""
    if tahlil_id is None:
        return katalog_nomi
    for y in (s or sozlama())["yakka"]:
        if y["kod"] == str(tahlil_id):
            return y["nom"] or katalog_nomi
    return katalog_nomi


def yakka_tartiblash(tests: list, s: dict = None) -> list:
    """Yakka tahlillarni sozlamadagi tartibda (ro'yxatda yo'qlari — oxirida, asl tartibda)."""
    s = s or sozlama()
    tartib = {y["kod"]: i for i, y in enumerate(s["yakka"])} if s.get("tartib") else {}
    if not tartib:
        return list(tests)
    n = len(tartib)
    return [t for _i, t in sorted(enumerate(tests),
                                  key=lambda it: (tartib.get(str(it[1].get("tahlil_id")), n), it[0]))]


def panel_sarlavha(panel: str, s: dict = None) -> str:
    return (s or sozlama())["panellar"][panel]["sarlavha"]


def panel_azolari(panel: str, s: dict = None) -> dict:
    """{a'zo tahlil_id (int): panel kaliti} — panel natijasini yakka tahlillardan yig'ish uchun."""
    out = {}
    for q in (s or sozlama())["panellar"][panel]["qatorlar"]:
        if q.get("tahlil_id"):
            out[int(q["tahlil_id"])] = q["kod"]
    return out


def panel_qatorlari(panel: str, rows: list, vals: dict, s: dict = None):
    """Koddagi standart qatorlar [(nom, kalit, norma, birlik)] → sozlamaga moslangan ro'yxat
    (tartib, nom/norma/birlik almashtirish, ko'rinish). Qaytaradi: (qatorlar, norma_ozgargan_kalitlar)."""
    std = {r[1]: r for r in rows}
    out, user_norma = [], set()
    for q in (s or sozlama())["panellar"][panel]["qatorlar"]:
        r = std.get(q["kod"])
        if r is None or q.get("korsat") == "yashirin":
            continue
        val = vals.get(q["kod"], "") if isinstance(vals, dict) else ""
        if q.get("korsat") == "natija" and (val is None or str(val).strip() == ""):
            continue
        if q.get("norma"):
            user_norma.add(q["kod"])
        out.append((q.get("nom") or r[0], r[1], q.get("norma") or r[2], q.get("birlik") or r[3]))
    return out, user_norma


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI (Tizim Sozlamalari → 🟢 Bioximiya → «🧾 Blanka ko'rinishi»)
# ─────────────────────────────────────────────────────────────────────────────
def katalog_bio_tahlillar() -> list:
    """Katalogdagi bioximiya tahlillari [(tahlil_id, nomi)] — bazadan."""
    try:
        import mysql.connector
        from monoblok_db_config import DB_CONFIG
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""SELECT DISTINCT t.id, t.nomi FROM tahlillar_norma n
                       JOIN tahlillar t ON t.id = n.tahlil_id
                       WHERE n.guruh = 'BIO' ORDER BY t.nomi""")
        rows = [(int(r[0]), str(r[1] or "")) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[OGOHLANTIRISH] bioximiya katalogi o'qilmadi: {e}")
        return []


def ochish_oyna(parent, namuna_fn=None, saqlangach_fn=None):
    """saqlangach_fn() — saqlangandan keyin (panel a'zolari ID larini jonli yangilash uchun)."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    from blanka_qator_ui import QatorJadvali

    s = json.loads(json.dumps(sozlama(force=True)))

    # Yakka: katalogdagi barcha BIO tahlillar — saqlangan tartibda, yangilari oxirida
    katalog = katalog_bio_tahlillar()
    kat_nomi = {str(i): n for i, n in katalog}
    yakka = [dict(y, katalog=kat_nomi.get(y["kod"], y.get("katalog") or "(katalogda yo'q)"))
             for y in s["yakka"]]
    bor = {y["kod"] for y in yakka}
    yakka += [_toza_yakka({"kod": str(i), "katalog": n}) for i, n in katalog if str(i) not in bor]
    yakka_std = [_toza_yakka({"kod": str(i), "katalog": n}) for i, n in katalog]

    win = tk.Toplevel(parent)
    win.title("🧾 Bioximiya — blanka ko'rinishi")
    win.geometry("1120x700")
    win.minsize(900, 560)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

    # ── Yakka tahlillar ───────────────────────────────────────────────
    t1 = ttk.Frame(nb, padding=6)
    nb.add(t1, text="  Yakka tahlillar  ")
    top = ttk.Frame(t1)
    top.pack(fill=tk.X, pady=(0, 6))
    v_sarl = tk.StringVar(value=s["sarlavha"])
    ttk.Label(top, text="Bo'lim sarlavhasi:").pack(side=tk.LEFT)
    ttk.Entry(top, textvariable=v_sarl, width=44).pack(side=tk.LEFT, padx=6)
    v_tartib = tk.BooleanVar(value=s.get("tartib", False))
    ttk.Checkbutton(top, text="Blankada shu tartibda chiqarish (o'chiq = buyurtmadagi tartib)",
                    variable=v_tartib).pack(side=tk.LEFT, padx=(16, 0))
    if not katalog:
        ttk.Label(t1, foreground="#c62828", text="Bazaga ulanib bo'lmadi — katalog ro'yxati yuklanmadi.").pack(anchor="w")
    jad_y = QatorJadvali(
        t1, yakka, yakka_std,
        [("kod", "ID", 50, False), ("katalog", "Katalogdagi nomi", 330, False),
         ("nom", "Blankadagi nomi (bo'sh = katalog nomi)", 330, False)],
        {"auto": "—"}, _toza_yakka, faqat_oqish=("katalog",), yangi_qator=False,
        yordam=("• Blankadagi nomi — faqat blankada chiqadigan nom (registratsiya va narxlar "
                "katalog nomi bilan qoladi). Bo'sh = katalog nomi.\n"
                "• Tartib (▲/▼) — buyurtmadagi tahlillar blankada shu tartibda chiqadi.\n"
                "• Norma va birlik — «Tahlil Qo'shish» oynasida (katalog) o'zgartiriladi."))

    # ── Panellar ──────────────────────────────────────────────────────
    panel_jad, panel_sarl = {}, {}
    for pk in PANEL_KALITLAR:
        p = s["panellar"][pk]
        tp = ttk.Frame(nb, padding=6)
        nb.add(tp, text=f"  {DEFAULT_PANELLAR[pk]['nomi']}  ")
        f = ttk.Frame(tp)
        f.pack(fill=tk.X, pady=(0, 6))
        v = tk.StringVar(value=p["sarlavha"])
        ttk.Label(f, text="Panel sarlavhasi:").pack(side=tk.LEFT)
        ttk.Entry(f, textvariable=v, width=44).pack(side=tk.LEFT, padx=6)
        panel_sarl[pk] = v
        panel_jad[pk] = QatorJadvali(
            tp, p["qatorlar"], DEFAULT_PANELLAR[pk]["qatorlar"],
            [("kod", "Kalit", 80, False), ("standart", "Standart nomi", 250, False),
             ("nom", "Blankadagi nomi", 200, False), ("norma", "Norma (bo'sh = standart)", 150, False),
             ("birlik", "Birlik", 70, False), ("tahlil_id", "A'zo tahlil ID", 90, False)],
            KORSAT, lambda q, _pk=pk: _toza_panel_qator(
                q, {x["kod"]: x for x in DEFAULT_PANELLAR[_pk]["qatorlar"]}.get(q.get("kod"))),
            faqat_oqish=("standart",), yangi_qator=False,
            yordam=("• Blankadagi nomi / Norma / Birlik — bo'sh qoldirilsa standart (katalog nomi, "
                    "bazadagi yoki koddagi norma) ishlatiladi. Norma bir necha qatorli bo'lishi "
                    "mumkin emas — kerak bo'lsa «Erkak: 62-115; Ayol: 53-97» deb yozing.\n"
                    "• A'zo tahlil ID — panel natijasi shu katalog tahlilining yakka natijasidan "
                    "olinadi (masalan TC = Xolesterin tahlili ID si). ID «Yakka tahlillar» "
                    "varag'ida ko'rinadi. Hisoblangan qatorlarda bo'sh.\n"
                    "• Ko'rinish: Doim / Natija bo'lsa / Yashirin (masalan GFR yoki KA kerak bo'lmasa)."))

    def _yig():
        return {"sarlavha": v_sarl.get().strip() or DEFAULT_SARLAVHA,
                "tartib": bool(v_tartib.get()),
                "yakka": [{"kod": y["kod"], "katalog": y["katalog"], "nom": y["nom"]} for y in jad_y.qatorlar],
                "panellar": {pk: {"sarlavha": panel_sarl[pk].get().strip() or DEFAULT_PANELLAR[pk]["sarlavha"],
                                  "qatorlar": panel_jad[pk].qatorlar} for pk in PANEL_KALITLAR}}

    def _standart():
        if not messagebox.askyesno("Standart", "Barcha nomlar, tartib va panellar standart holatga "
                                   "qaytarilsinmi?", parent=win):
            return
        jad_y.standartga()
        v_sarl.set(DEFAULT_SARLAVHA)
        v_tartib.set(False)
        for pk in PANEL_KALITLAR:
            panel_jad[pk].standartga()
            panel_sarl[pk].set(DEFAULT_PANELLAR[pk]["sarlavha"])

    def _namuna():
        try:
            namuna_fn(_toza(_yig()))
        except Exception as e:
            messagebox.showerror("Namuna", f"Namuna blanka yaratilmadi:\n{e}", parent=win)

    def _saqla():
        if saqla(_yig()):
            if saqlangach_fn:
                try:
                    saqlangach_fn()
                except Exception as e:
                    print(f"[OGOHLANTIRISH] bio_blanka saqlangach: {e}")
            messagebox.showinfo("Saqlandi", "[OK] Bioximiya blanka sozlamasi saqlandi.\n"
                                "Keyingi yaratiladigan blankalarda qo'llanadi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Sozlamani saqlab bo'lmadi!", parent=win)

    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1080, text=(
        "Ikki marta bosing — tahrirlash; ▲/▼ — tartib; Bo'sh joy — ko'rinish (panellarda). "
        "Rus tilidagi blankada faqat standart nomlar tarjima qilinadi."
    )).pack(fill=tk.X, padx=10, pady=(2, 2))

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="↺ Standart", command=_standart).pack(side=tk.RIGHT, padx=4)
    if namuna_fn is not None:
        ttk.Button(bot, text="👁 Namuna blanka (Word)", command=_namuna).pack(side=tk.LEFT, padx=4)

    win.bind("<Escape>", lambda e: win.destroy())
    return win
