# -*- coding: utf-8 -*-
"""
Kritik natija ogohlantirish tizimi (Critical value / xatolik signali).

Maqsad: analizatordan kelgan natijalar ichida FIZIOLOGIK JIHATDAN MUMKIN BO'LMAGAN
(0, manfiy, juda past) yoki normadan keskin chetlashgan qiymatlarni topib, laborantni
ogohlantirish. Ko'pincha bu qon laxtalanishi, gemoliz, zardob/reagent tugashi belgisi.

Ikki manba tekshiriladi:
  • BC-20S gematologiya — WBC / RBC / HGB / PLT + HGB/RBC balansi + "ko'p ko'rsatkich past"
  • BK-280 bioximiya   — panel bo'yicha past/nol/baland + bilirubin fraksiyalari +
                          kreatinin/mochevina balansi

Signal: qizil fon (chaqiruvchi kodda) + popup + ovoz (winsound WAV / MCI mp3).
Chegaralar `alert_config.json` da — kodga tegmasdan o'zgartirsa bo'ladi.
"""

import os
import sys
import json
import threading

# ── Papka (manba yoki EXE) ────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_CONFIG_PATH = os.path.join(BASE_DIR, "alert_config.json")

# RF/CRP/ASLO juda past — reagent muammosi xabari (DEFAULT_CONFIG va alert_config.json)
_R2_XABAR = ("juda past — R2 reagent (qizdirishdan qaytarilmagan yoki tugagan) shubhasi; "
             "reagentni tekshirib QAYTA O'LCHANG yoki mas'uldan so'rang")

# ── Standart sozlama (alert_config.json bo'lmasa shu ishlatiladi) ─────────
DEFAULT_CONFIG = {
    "enabled": True,
    "popup": True,
    "sound": True,
    # WAV -> winsound (doimo ishlaydi), mp3/boshqa -> Windows MCI.
    # Nisbiy yo'l loyiha papkasiga nisbatan.
    "sound_file": "signals/alarm_clock.wav",

    "hematology": {
        # Faqat sodda kam/ko'p chegaralari — chegaradan chiqsa signal beradi.
        # (HGB/RBC nisbati va "ko'p ko'rsatkich past" qoidalari olib tashlangan —
        #  ular normal natijalarga ham yolg'on signal berardi.)
        "WBC": {"low": 4.0,  "high": 20.0},
        "RBC": {"low": 2.5,  "high": 6.0},
        "HGB": {"low": 80.0, "high": 160.0},
        "PLT": {"low": 100.0, "high": 600.0},
    },

    "biochemistry": {
        # Har bir tahlil: nomdan (kichik harf) topiladi.
        #   match   — shu so'zlardan BIRORTASI nomda bo'lsa mos keladi
        #   exclude — bulardan biri nomda bo'lsa TASHLAB ketiladi
        #   low     — shundan past -> 🔴 xatolik shubhasi
        #   high    — shundan baland -> 🟡 diqqat
        #   zero    — 0 bo'lsa xatolik (oqsil/glyukoza/kreatinin kabi doimo mavjud moddalar)
        #   neg     — faqat manfiy bo'lsa xatolik (fermentlar/bilirubin — past normal)
        "tests": [
            {"key": "umumiy_oqsil",     "match": ["umumiy oqsil"],                    "low": 40,  "high": 100,  "zero": True},
            {"key": "albumin",          "match": ["albumin"], "exclude": ["mikroalbumin"], "low": 20, "high": 60, "zero": True},
            {"key": "glyukoza",         "match": ["glyukoza"], "exclude": ["tolerantlik", "soat", "natoshchak", "o'tgach"], "low": 2.0, "high": 25, "zero": True},
            {"key": "kreatinin",        "match": ["kreatinin"], "exclude": ["nisbat", "mochevina", "/"], "low": 40, "high": 500, "zero": True},
            {"key": "mochevina",        "match": ["mochevina"], "exclude": ["azot", "nisbat", "kislota", "/"], "low": 0.5, "high": 30, "zero": True},
            {"key": "siydik_kislota",   "match": ["siydik kislota", "mochevaya kislota"], "low": 60, "high": 900, "zero": True},
            # Kalsiy ko'p "o'ynaydi" — egasi talabi (2026-09-29): >2.7 qizil, <1.8 ko'k signal
            {"key": "kalsiy",           "match": ["kalsiy"],                           "low": 1.8, "high": 2.7,  "zero": True,
             "high_level": "critical",
             "low_msg": "past — gipokalsiemiya yoki namuna xatosi, qayta tekshiring"},
            # CRP 0–1, RF 0–2, ASLO 0–10 (chegara ham) — egasi talabi (2026-09-29):
            # R2 reagent qizdirishdan qaytarilmay qolsa yoki tugasa analizator 0 ga
            # yaqin "natija" beradi. 'critical' — hamshira uni haqiqiy deb yubormasin:
            # ro'yxatda signal + importda "Tekshiraman (saqlanmasin)" oynasi.
            {"key": "crp",              "match": ["s-reaktiv", "crp", "crb", "srb"],
             "exclude": ["revmoproba"], "low": 1, "low_inclusive": True, "neg": True,
             "low_level": "critical", "low_msg": _R2_XABAR},
            {"key": "rf",               "match": ["revmatoid", "r faktor"],
             "exclude": ["revmoproba"], "low": 2, "low_inclusive": True, "neg": True,
             "low_level": "critical", "low_msg": _R2_XABAR},
            {"key": "aslo",             "match": ["antistreptolizin", "aslo"],
             "exclude": ["revmoproba"], "low": 10, "low_inclusive": True, "neg": True,
             "low_level": "critical", "low_msg": _R2_XABAR},
            {"key": "kaliy",            "match": ["kaliy"],                            "low": 2.0, "high": 7.0,  "zero": True},
            {"key": "natriy",           "match": ["natriy"],                           "low": 110, "high": 170,  "zero": True},
            {"key": "magniy",           "match": ["magniy"],                           "low": 0.5, "high": 5.0,  "zero": True},
            {"key": "temir",            "match": ["temir", " fe"],                     "high": 70,  "neg": True},
            {"key": "alt",              "match": ["alanin aminotransferaza", "(alt)"], "high": 400, "neg": True},
            {"key": "ast",              "match": ["aspartat aminotransferaza", "(ast)"], "high": 400, "neg": True},
            {"key": "ldg",              "match": ["laktatdegidrog", "(ldg)"],          "low": 50,  "high": 2000},
            {"key": "ggt",              "match": ["gamma-glutamil", "(ggt)"],          "high": 600, "neg": True},
            {"key": "alp",              "match": ["ishqoriy fosfataza"],               "high": 1000, "neg": True},
            {"key": "amilaza",          "match": ["amilaza"],                          "high": 600, "neg": True},
            {"key": "timol",            "match": ["timol"],                            "high": 10,  "neg": True},
            {"key": "xolesterin",       "match": ["umumiy xolesterin"],                "high": 12,  "zero": True},
            {"key": "trigliserid",      "match": ["trigliserid"],                      "high": 15,  "zero": True},
            {"key": "umumiy_bilirubin", "match": ["umumiy bilirubin"],                 "high": 200, "zero": True},
            {"key": "boglangan_bil",    "match": ["langan bilirubin"],                 "high": 100, "neg": True},
        ],
        "rules": {
            # Bog'langan (direkt) bilirubin >= Umumiy bilirubin -> mumkin emas (EDTA/sentrifuga/reagent)
            "bilirubin_direct_ge_total": True,
            # Bog'langan > Umumiy ning shu ulushi (lekin teng emas) -> 🟡 shubhali
            "bilirubin_direct_ratio_warn": 0.9,
            # Kreatinin shundan past -> 🔴 reagent kam shubhasi
            "kreatinin_low": 40,
            # Mochevina normal/baland bo'lib Kreatinin/Mochevina nisbati shundan past bo'lsa
            # -> kreatinin reagenti tugagan (norma 10-20 µmol/mmol)
            "kre_urea_ratio_min": 8,
        },
    },
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
    """alert_config.json ni o'qish (bo'lmasa standartni yozib qo'yadi)."""
    if _CFG_CACHE[0] is not None and not force:
        return _CFG_CACHE[0]
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # chuqur nusxa
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _deep_merge(cfg, json.load(f))
        else:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    _CFG_CACHE[0] = cfg
    return cfg


# ══════════════════════════════════════════════════════════════════════════
#  Yordamchi
# ══════════════════════════════════════════════════════════════════════════
def _to_float(val):
    """'↑ 7.3', '13,2', '5.0' -> float. Bo'lmasa None."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for ch in ("↑", "↓", " ", "\t"):
        s = s.replace(ch, "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _norm_name(name):
    s = str(name or "").lower()
    for ch in ("'", "‘", "’", "`", "ʻ"):
        s = s.replace(ch, "")
    return s


# ══════════════════════════════════════════════════════════════════════════
#  GEMATOLOGIYA (BC-20S)
# ══════════════════════════════════════════════════════════════════════════
def check_hematology(values, cfg=None):
    """
    values: {'WBC': '7.1', 'RBC': '4.9', 'HGB': '137', 'PLT': '247', ...}
    Qaytaradi: (alerts, offending_keys)
      alerts        — [{'level': 'critical', 'msg': str}, ...]
      offending_keys — {'RBC', 'HGB', ...}  (qizil qilish uchun)

    Faqat sodda kam/ko'p tekshiruvi: qiymat [low, high] oralig'idan chiqsa (yoki 0/manfiy)
    signal beriladi. Boshqa hech qanday qoida (nisbat va h.k.) yo'q.
    """
    cfg = cfg or load_config()
    h = cfg.get("hematology", {})
    alerts = []
    offending = set()

    for key in ("WBC", "RBC", "HGB", "PLT"):
        conf = h.get(key)
        if not conf:
            continue
        val = _to_float(values.get(key))
        if val is None:
            continue
        lo = conf.get("low")
        hi = conf.get("high")
        if val <= 0:
            alerts.append({"level": "critical", "msg": f"{key} = {val:g} — nol/manfiy (o'lchov xatosi)"})
            offending.add(key)
        elif lo is not None and val < lo:
            alerts.append({"level": "critical", "msg": f"{key} = {val:g} — past ({lo:g} dan past)"})
            offending.add(key)
        elif hi is not None and val > hi:
            alerts.append({"level": "critical", "msg": f"{key} = {val:g} — baland ({hi:g} dan baland)"})
            offending.add(key)

    return alerts, offending


# ══════════════════════════════════════════════════════════════════════════
#  BIOXIMIYA (BK-280)
# ══════════════════════════════════════════════════════════════════════════
def check_biochemistry(rows, cfg=None):
    """
    rows: iterable of (name, value) — nom va natija (matn bo'lishi mumkin)
    Qaytaradi: (alerts, offending_names)
      alerts          — [{'level': ..., 'msg': ...}, ...]
      offending_names — {nom, ...}  (aynan berilgan nom bilan qizil qilish uchun)
    """
    alerts, offending, _dirs = check_biochemistry_detail(rows, cfg)
    return alerts, offending


def check_biochemistry_detail(rows, cfg=None):
    """check_biochemistry + yo'nalish: (alerts, offending_names, {nom: 'high'|'low'}).

    'low' — past chiqqan (ko'k signal), 'high' — baland yoki mantiqiy xato (qizil).
    Qoidada ixtiyoriy: "high_level"/"low_level" ('warn'|'critical'), "low_msg"/"high_msg".
    """
    cfg = cfg or load_config()
    b = cfg.get("biochemistry", {})
    tests_cfg = b.get("tests", [])
    rules = b.get("rules", {})

    alerts = []
    offending = set()
    dirs = {}

    # Nomlarni saqlab qolgan holda ro'yxat
    parsed = []
    for name, value in rows:
        parsed.append((name, _norm_name(name), _to_float(value)))

    # ── Har bir tahlil bo'yicha past/nol/baland ────────────────────────────
    for name, nnorm, val in parsed:
        if val is None:
            continue
        for rule in tests_cfg:
            match = rule.get("match", [])
            excl = rule.get("exclude", [])
            if not any(m in nnorm for m in match):
                continue
            if any(e in nnorm for e in excl):
                continue
            low = rule.get("low")
            high = rule.get("high")
            if rule.get("zero") and val == 0:
                alerts.append({"level": "critical", "msg": f"{name} = 0 — o'lchov/reagent xatosi shubhasi"})
                offending.add(name)
                dirs[name] = "high"
            elif (rule.get("zero") or rule.get("neg")) and val < 0:
                alerts.append({"level": "critical", "msg": f"{name} = {val:g} — manfiy (xato)"})
                offending.add(name)
                dirs[name] = "high"
            elif low is not None and (val < low or (rule.get("low_inclusive") and val <= low)):
                sabab = rule.get("low_msg") or "juda past, reagent/zardob shubhasi"
                oraliq = (f"0–{low:g} oralig'ida" if rule.get("low_inclusive")
                          else f"{low:g} dan past")
                alerts.append({"level": rule.get("low_level", "critical"),
                               "msg": f"{name} = {val:g} — {sabab} ({oraliq})"})
                offending.add(name)
                dirs[name] = "low"
            elif high is not None and val > high:
                sabab = rule.get("high_msg") or "baland"
                alerts.append({"level": rule.get("high_level", "warn"),
                               "msg": f"{name} = {val:g} — {sabab} ({high:g} dan baland)"})
                offending.add(name)
                dirs[name] = "high"
            break  # birinchi mos qoida yetarli

    # ── Bilirubin fraksiyalari ─────────────────────────────────────────────
    total_bil = None
    direct_bil = None
    total_name = direct_name = None
    for name, nnorm, val in parsed:
        if "bilirubin" not in nnorm or val is None:
            continue
        if "umumiy" in nnorm:
            total_bil, total_name = val, name
        elif "langan" in nnorm or "bog" in nnorm or "direkt" in nnorm or "direct" in nnorm:
            direct_bil, direct_name = val, name

    if total_bil is not None and direct_bil is not None and total_bil > 0:
        if rules.get("bilirubin_direct_ge_total") and direct_bil >= total_bil:
            alerts.append({"level": "critical",
                           "msg": f"Bog'langan bilirubin ({direct_bil:g}) ≥ Umumiy ({total_bil:g}) — mumkin emas (EDTA/sentrifuga/reagent xatosi)"})
            if direct_name:
                offending.add(direct_name)
            if total_name:
                offending.add(total_name)
        else:
            warn_ratio = rules.get("bilirubin_direct_ratio_warn")
            if warn_ratio and direct_bil > total_bil * warn_ratio:
                alerts.append({"level": "warn",
                               "msg": f"Bog'langan bilirubin ({direct_bil:g}) umumiyning {direct_bil / total_bil * 100:.0f}% i — shubhali yuqori ulush"})
                if direct_name:
                    offending.add(direct_name)

    # ── Kreatinin / Mochevina balansi ──────────────────────────────────────
    kre = kre_name = urea = None
    for name, nnorm, val in parsed:
        if val is None:
            continue
        if "kreatinin" in nnorm and "nisbat" not in nnorm and "/" not in nnorm:
            kre, kre_name = val, name
        elif "mochevina" in nnorm and "azot" not in nnorm and "nisbat" not in nnorm and "/" not in nnorm:
            urea = val

    kre_low = rules.get("kreatinin_low")
    ratio_min = rules.get("kre_urea_ratio_min")
    if kre is not None and urea is not None and urea > 2.5 and kre > 0 and ratio_min:
        ratio = kre / urea
        if ratio < ratio_min:
            alerts.append({"level": "critical",
                           "msg": f"Kreatinin/Mochevina = {ratio:.1f} (norma 10-20) — mochevina baland, kreatinin past: kreatinin reagenti kam shubhasi"})
            if kre_name:
                offending.add(kre_name)

    for n in offending:
        dirs.setdefault(n, "high")     # bilirubin/kreatinin mantiqiy xatolari — qizil
    return alerts, offending, dirs


# ══════════════════════════════════════════════════════════════════════════
#  OVOZ
# ══════════════════════════════════════════════════════════════════════════
def _resolve_sound_path(cfg):
    path = (cfg or load_config()).get("sound_file", "")
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return path if os.path.exists(path) else None


def play_alert_sound(cfg=None):
    """WAV -> winsound, mp3/boshqa -> Windows MCI. Non-bloklovchi."""
    cfg = cfg or load_config()
    if not cfg.get("sound", True):
        return
    path = _resolve_sound_path(cfg)

    def _play():
        try:
            if path and path.lower().endswith(".wav"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif path:
                import ctypes
                w = ctypes.windll.winmm
                w.mciSendStringW("close azalarm", None, 0, 0)
                w.mciSendStringW(f'open "{path}" alias azalarm', None, 0, 0)
                w.mciSendStringW("play azalarm", None, 0, 0)
            else:
                import winsound
                winsound.MessageBeep(-1)
        except Exception:
            try:
                import winsound
                winsound.MessageBeep(-1)
            except Exception:
                pass

    threading.Thread(target=_play, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════
#  KO'RSATISH
# ══════════════════════════════════════════════════════════════════════════
def format_alerts(alerts):
    lines = []
    for a in alerts:
        mark = "[XATO] " if a.get("level") == "critical" else "[DIQQAT] "
        lines.append(f"{mark}{a.get('msg', '')}")
    return "\n".join(lines)


def has_critical(alerts):
    return any(a.get("level") == "critical" for a in alerts)


def notify(parent, patient_name, alerts, cfg=None, play=True):
    """Ovoz + popup ogohlantirish (askamas, faqat xabar)."""
    cfg = cfg or load_config()
    if not cfg.get("enabled", True) or not alerts:
        return
    if play:
        play_alert_sound(cfg)
    if not cfg.get("popup", True):
        return
    from tkinter import messagebox
    title = "⚠ KRITIK NATIJA — TEKSHIRING"
    body = f"Bemor: {patient_name}\n\n{format_alerts(alerts)}\n\n" \
           "Iltimos, natijani va namunani tekshiring."
    try:
        messagebox.showwarning(title, body, parent=parent)
    except Exception:
        messagebox.showwarning(title, body)


def kursor_tugmaga(widget):
    """Sichqoncha kursorini XAVFSIZ tugma markaziga olib borish.

    Egasi talabi (2026-09-29): ogohlantirish oynasida sichqoncha va Enter
    "bizning foydamizga" — ya'ni xavfsiz tugmada tursin (Windows'ning
    "tugmaga avtomatik o'tish" kabi). Shoshilgan hamshira boshqa tugmani
    tasodifan bosib qo'ymasin. Xato bo'lsa jim o'tadi.
    """
    try:
        widget.update_idletasks()
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() // 2
        import ctypes
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    except Exception:
        pass


def confirm_save(parent, patient_name, alerts, cfg=None):
    """Saqlash/import oldidan tasdiqlash. True = davom etsin.

    Standart (Enter/Esc/yopish, kursor) — "Tekshiraman (saqlanmasin)".
    """
    cfg = cfg or load_config()
    if not cfg.get("enabled", True) or not has_critical(alerts):
        return True
    play_alert_sound(cfg)
    try:
        import tkinter as tk
        res = {"ok": False}
        dlg = tk.Toplevel(parent)
        dlg.title("⚠ KRITIK NATIJA")
        dlg.configure(bg="#FFF4F4")
        try:
            dlg.transient(parent)
        except Exception:
            pass
        tk.Label(dlg, text=f"⚠ KRITIK NATIJA — {patient_name}", bg="#C62828", fg="white",
                 font=("Arial", 13, "bold"), padx=14, pady=10, anchor="w"
                 ).pack(fill=tk.X)
        tk.Label(dlg, text=format_alerts(alerts), bg="#FFF4F4", fg="#7F1D1D",
                 font=("Arial", 11, "bold"), justify=tk.LEFT, wraplength=620,
                 padx=16, pady=10).pack(anchor="w")
        tk.Label(dlg, text="Bu natijalarda xatolik shubhasi bor. Namunani/natijani tekshiring.",
                 bg="#FFF4F4", font=("Arial", 10), padx=16).pack(anchor="w")
        bf = tk.Frame(dlg, bg="#FFF4F4")
        bf.pack(fill=tk.X, padx=14, pady=12)

        def _yoq(e=None):
            res["ok"] = False
            dlg.destroy()

        def _ha():
            res["ok"] = True
            dlg.destroy()
        safe = tk.Button(bf, text="✎  Tekshiraman (saqlanmasin)", command=_yoq,
                         bg="#2E7D32", fg="white", font=("Arial", 11, "bold"),
                         padx=14, pady=6, cursor="hand2")
        safe.pack(side=tk.LEFT)
        tk.Button(bf, text="Natija to'g'ri — baribir saqlansin", command=_ha,
                  bg="#E0E0E0", font=("Arial", 9), padx=10, pady=4).pack(side=tk.RIGHT)
        dlg.bind("<Return>", _yoq)
        dlg.bind("<Escape>", _yoq)
        dlg.protocol("WM_DELETE_WINDOW", _yoq)
        dlg.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - dlg.winfo_reqwidth()) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_reqheight()) // 3
            dlg.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass
        dlg.grab_set()
        safe.focus_set()
        dlg.after(80, lambda: kursor_tugmaga(safe))
        dlg.wait_window()
        return res["ok"]
    except Exception:
        pass
    from tkinter import messagebox
    body = f"Bemor: {patient_name}\n\n{format_alerts(alerts)}\n\n" \
           "Bu natijalarda xatolik shubhasi bor.\nBaribir saqlansinmi?"
    try:
        return messagebox.askyesno("⚠ KRITIK NATIJA", body, parent=parent, icon="warning",
                                   default="no")
    except Exception:
        return messagebox.askyesno("⚠ KRITIK NATIJA", body)
