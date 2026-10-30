"""
Maxsus blanka jadvallari (Nechiporenko, Spermogramma, Najas, Urologik surtma, GTT ...)
— qator nomi va normasini laboratoriyaga moslash.

Bu jadvallarning qatorlari va normalari ilgari funksiya ichida qattiq yozilgan edi.
Endi monoblok_dastur har jadval standart qatorlarini shu modulda ro'yxatga oladi
(royxat), render paytida esa moslash() sozlamadagi nom/norma/tartib/ko'rinishni
qo'llaydi. Bo'sh qiymat = standart.

Saqlanadi: bazada (markaziy_sozlama, kalit "maxsus_jadvallar"):
  {jadval: {"qatorlar": [{kod, nom, normalar: [..], korsat}]}}
"""

import json
import re

KALIT = "maxsus_jadvallar"
KORSAT = {"auto": "Doim", "yashirin": "Yashirin"}
REESTR = {}            # jadval -> {nomi, qatorlar, nom_i, kalit_i, norma_i, norma_nomlari, son_i}
_KESH = {"mtime": None, "cfg": None}


def royxat(jadval, nomi, qatorlar, nom_i=0, kalit_i=1, norma_i=(), norma_nomlari=(), son_i=None):
    """Jadvalni standart qatorlari bilan ro'yxatga olish (modul yuklanganda).
    norma_i — tuple ichidagi norma matni indekslari; son_i — {norma_i: chegara_soni_i}
    (Nechiporenko: norma matni o'zgarsa rang chegarasi ham undagi sondan olinadi)."""
    REESTR[jadval] = {"nomi": nomi, "qatorlar": list(qatorlar), "nom_i": nom_i, "kalit_i": kalit_i,
                      "norma_i": tuple(norma_i), "norma_nomlari": tuple(norma_nomlari) or
                      tuple("Norma" for _ in norma_i), "son_i": dict(son_i or {})}


def _toza(raw) -> dict:
    out = {}
    if not isinstance(raw, dict):
        return out
    for j, v in raw.items():
        if not isinstance(v, dict) or not isinstance(v.get("qatorlar"), list):
            continue
        qs = []
        for q in v["qatorlar"]:
            if not isinstance(q, dict) or not str(q.get("kod") or "").strip():
                continue
            qs.append({"kod": str(q["kod"]).strip(), "nom": str(q.get("nom") or "").strip(),
                       "normalar": [str(x or "").strip() for x in (q.get("normalar") or [])],
                       "korsat": q.get("korsat") if q.get("korsat") in KORSAT else "auto"})
        out[str(j)] = {"qatorlar": qs}
    return out


def sozlama(force=False) -> dict:
    import markaziy_sozlama as _ms
    return _ms.modul_sozlama(KALIT, _toza, _KESH, force)


def saqla(s: dict) -> bool:
    import markaziy_sozlama as _ms
    return _ms.modul_saqla(KALIT, _toza, s, _KESH)


def _son(matn):
    m = re.search(r"\d+(?:[.,]\d+)?", str(matn or ""))
    if not m:
        return None
    x = float(m.group(0).replace(",", "."))
    return int(x) if x == int(x) else x


def moslash(jadval, qatorlar, s: dict = None):
    """Koddagi standart qatorlar → sozlamaga moslangan ro'yxat (tartib, nom, norma, ko'rinish).
    Sozlama yo'q / xato bo'lsa — qatorlar o'zgarishsiz."""
    try:
        r = REESTR.get(jadval)
        cfg = (s if s is not None else sozlama()).get(jadval)
        if not r or not cfg:
            return list(qatorlar)
        ki, ni = r["kalit_i"], r["nom_i"]
        std = {q[ki]: q for q in qatorlar}
        out, bor = [], set()
        for c in cfg["qatorlar"]:
            q = std.get(c["kod"])
            if q is None:
                continue
            bor.add(c["kod"])
            if c.get("korsat") == "yashirin":
                continue
            q = list(q)
            if c.get("nom"):
                q[ni] = c["nom"]
            for j, idx in enumerate(r["norma_i"]):
                if j < len(c.get("normalar") or []) and c["normalar"][j]:
                    q[idx] = c["normalar"][j]
                    si = r["son_i"].get(idx)
                    if si is not None and _son(q[idx]) is not None:
                        q[si] = _son(q[idx])
            out.append(tuple(q))
        out += [q for q in qatorlar if q[ki] not in bor]   # sozlamadan keyin qo'shilgan standart qator
        return out
    except Exception as e:
        print(f"[OGOHLANTIRISH] maxsus_jadval.moslash({jadval}): {e}")
        return list(qatorlar)


# ─────────────────────────────────────────────────────────────────────────────
#  SOZLASH OYNASI
# ─────────────────────────────────────────────────────────────────────────────
def _jadval_qatorlari(jadval, s):
    """UI uchun: [{kod, standart, nom, norma0.., korsat}] (sozlama tartibida)."""
    r = REESTR[jadval]
    ki, ni = r["kalit_i"], r["nom_i"]
    cfg = {c["kod"]: c for c in (s.get(jadval) or {}).get("qatorlar", [])}
    tartib = [c["kod"] for c in (s.get(jadval) or {}).get("qatorlar", [])]
    std = {q[ki]: q for q in r["qatorlar"]}
    kodlar = [k for k in tartib if k in std] + [q[ki] for q in r["qatorlar"] if q[ki] not in tartib]
    out = []
    for k in kodlar:
        q, c = std[k], cfg.get(k, {})
        d = {"kod": k, "standart": str(q[ni]).replace("\n", " "), "nom": c.get("nom", ""),
             "korsat": c.get("korsat", "auto")}
        for j, idx in enumerate(r["norma_i"]):
            norm = (c.get("normalar") or [])
            d[f"norma{j}"] = norm[j] if j < len(norm) else ""
            d[f"std{j}"] = str(q[idx])
        out.append(d)
    return out


def ochish_oyna(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from blanka_qator_ui import QatorJadvali

    if not REESTR:
        messagebox.showinfo("Maxsus jadvallar", "Ro'yxatga olingan jadval yo'q.", parent=parent)
        return None
    s = json.loads(json.dumps(sozlama(force=True)))

    win = tk.Toplevel(parent)
    win.title("📋 Maxsus jadvallar — nomlar va normalar")
    win.geometry("1120x640")
    win.minsize(900, 500)
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass
    ttk.Label(win, foreground="#555", justify=tk.LEFT, wraplength=1080, text=(
        "Har varaqda bitta jadval. «Blankadagi nomi» va «Norma» bo'sh bo'lsa — standart (qavsdagi). "
        "Ikki marta bosing — tahrirlash; ▲/▼ — tartib; Bo'sh joy — yashirish. Nechiporenkoda "
        "norma matnidagi son (masalan «4000 gacha») rang chegarasi ham bo'ladi.")).pack(fill=tk.X, padx=10, pady=(8, 4))
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    jadvallar = {}
    for j, r in REESTR.items():
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text=f"  {r['nomi']}  ")
        qs = _jadval_qatorlari(j, s)
        std_qs = _jadval_qatorlari(j, {})
        maydon = [("kod", "Kalit", 90, False), ("standart", "Standart nomi", 260, False),
                  ("nom", "Blankadagi nomi", 240, False)]
        for k, nn in enumerate(r["norma_nomlari"]):
            maydon.append((f"norma{k}", f"{nn} (bo'sh = standart)", 170, False))

        def _toza_q(q, _qs=std_qs):
            base = next((x for x in _qs if x["kod"] == q.get("kod")), {})
            d = dict(base)
            d.update({k: (str(v).strip() if isinstance(v, str) else v) for k, v in q.items()
                      if k in ("nom", "korsat") or k.startswith("norma")})
            d["korsat"] = d.get("korsat") if d.get("korsat") in KORSAT else "auto"
            return d

        yordam = "Standart normalar: " + "; ".join(
            f"{q['standart'][:30]} = " + " / ".join(q.get(f"std{k}", "") for k in range(len(r["norma_i"])))
            for q in std_qs[:6]) if r["norma_i"] else ""
        jadvallar[j] = QatorJadvali(f, qs, std_qs, maydon, KORSAT, _toza_q,
                                    faqat_oqish=("standart",), yangi_qator=False, yordam=yordam)

    def _yig():
        out = {}
        for j, jad in jadvallar.items():
            n = len(REESTR[j]["norma_i"])
            out[j] = {"qatorlar": [{"kod": q["kod"], "nom": q.get("nom", ""), "korsat": q.get("korsat", "auto"),
                                    "normalar": [q.get(f"norma{k}", "") for k in range(n)]}
                                   for q in jad.qatorlar]}
        return out

    def _saqla():
        if saqla(_yig()):
            messagebox.showinfo("Saqlandi", "[OK] Maxsus jadvallar sozlamasi saqlandi.", parent=win)
            win.destroy()
        else:
            messagebox.showerror("Xato", "Saqlab bo'lmadi!", parent=win)

    def _standart():
        if messagebox.askyesno("Standart", "Barcha jadvallar standartga qaytarilsinmi?", parent=win):
            for jad in jadvallar.values():
                jad.standartga()

    bot = ttk.Frame(win)
    bot.pack(fill=tk.X, padx=8, pady=8)
    tk.Button(bot, text="💾 Saqlash", command=_saqla, bg="#2E7D32", fg="white",
              font=("Arial", 10, "bold"), padx=16, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="Bekor qilish", command=win.destroy).pack(side=tk.RIGHT, padx=4)
    ttk.Button(bot, text="↺ Standart", command=_standart).pack(side=tk.RIGHT, padx=4)
    win.bind("<Escape>", lambda e: win.destroy())
    return win
