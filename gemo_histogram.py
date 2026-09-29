# -*- coding: utf-8 -*-
"""
Gemotologiya gistogrammalari (WBC / RBC / PLT) — Tk Canvas ga chizish.

Ma'lumot manbai: gemo_protokol.parse_hl7_oru → patient["histograms"]
    {"WBC": {"data": [128 int 0..255], "lines": [kanal (0..255)], "flags": ["R1"]}, ...}

X o'qi kalibrlash (Mindray BC-20S, 26.09.2026 da tekshirilgan):
    128 nuqta = butun o'q; ajratuvchi chiziqlar 256-kanal shkalasida (nuqta = kanal / 2).
    RBC: MCV / o'rtacha-indeks bo'yicha 15 namunada barqaror ≈ 314 fL;
    WBC ≈ 400 fL, PLT ≈ 42 fL — analizator ekranidagi o'q belgilariga mos.
Y o'qi: 0..255 qat'iy (analizator ham normallashtirmaydi — past PLT past ko'rinadi).
"""

HIST_ORDER = ("WBC", "RBC", "PLT")

HIST_STYLE = {
    #        o'q uzunligi (fL), belgilar,                  bo'yoq
    "WBC": {"fl": 400.0, "ticks": (0, 100, 200, 300), "fill": "#c9d6ea", "line": "#e8eef8"},
    "RBC": {"fl": 314.0, "ticks": (0, 100, 200, 300), "fill": "#e01818", "line": "#ff5050"},
    "PLT": {"fl": 42.0,  "ticks": (0, 10, 20, 30, 40), "fill": "#6ee01a", "line": "#9cff50"},
}

BG = "#000000"
AXIS = "#d0d0d0"
SEP = "#e0e0e0"


def has_histograms(patient: dict) -> bool:
    h = (patient or {}).get("histograms") or {}
    return any((h.get(k) or {}).get("data") for k in HIST_ORDER)


def draw_histogram(canvas, kind: str, hist: dict):
    """Bitta gistogrammani canvas ga (uning joriy o'lchamida) chizadi. hist=None → bo'sh panel."""
    canvas.delete("all")
    w = max(int(canvas.winfo_width()), 60)
    h = max(int(canvas.winfo_height()), 60)
    st = HIST_STYLE[kind]

    ml, mr, mt, mb = 12, 22, 20, 20          # chegaralar: chap, o'ng, yuqori, past
    x0, x1 = ml, w - mr
    y0, y1 = mt, h - mb                      # y1 = asos chizig'i
    pw, ph = x1 - x0, y1 - y0

    canvas.create_text(w // 2, 3, text=kind, fill="#ffffff", anchor="n", font=("Arial", 9, "bold"))

    data = (hist or {}).get("data") or []
    if not data:
        canvas.create_text(w // 2, h // 2, text="gistogramma yo'q", fill="#777777", font=("Arial", 8))
        return

    n = len(data)

    def px(idx):                             # nuqta indeksi → x
        return x0 + pw * idx / n

    def py(v):
        return y1 - ph * min(max(v, 0), 255) / 255.0

    # Egri chiziq (to'ldirilgan)
    pts = [x0, y1]
    for i, v in enumerate(data):
        pts += [px(i + 0.5), py(v)]
    pts += [x1, y1]
    canvas.create_polygon(pts, fill=st["fill"], outline="")
    canvas.create_line(pts[2:-2], fill=st["line"], width=1)

    # Ajratuvchi chiziqlar (256-kanal → 128 nuqta)
    for ch in (hist.get("lines") or []):
        x = px(ch / 2.0)
        if x0 <= x <= x1:
            canvas.create_line(x, mt - 4, x, y1, fill=SEP, dash=(3, 3))

    # O'qlar
    canvas.create_line(x0, y1, x1, y1, fill=AXIS)
    canvas.create_line(x0, y1, x0, mt - 4, fill=AXIS)
    for t in st["ticks"]:
        x = x0 + pw * t / st["fl"]
        canvas.create_line(x, y1, x, y1 + 3, fill=AXIS)
        canvas.create_text(x, y1 + 3, text=str(t), fill=AXIS, anchor="n", font=("Arial", 7))
    canvas.create_text(w - 3, y1 - 2, text="fL", fill=AXIS, anchor="se", font=("Arial", 7, "italic"))

    # WBC hudud belgilari (R1..R4)
    flags = hist.get("flags") or []
    if flags:
        canvas.create_text(w - 4, mt, text=" ".join(sorted(set(flags))), fill="#ff4040",
                           anchor="ne", font=("Arial", 8, "bold"))


# ══════════════════════════════════════════════════════════════════════
#  GISTOGRAMMA IZOHI — laborant uchun (FAQAT oynada; blankaga chiqmaydi)
# ══════════════════════════════════════════════════════════════════════
# Egasi talabi (2026-09-29): gistogramma faqat chiroyli rasm bo'lmasin —
# oynada bemor tanlanganda "nimaga e'tibor berish kerak" deb yozib chiqsin.
# Manbalar: (1) analizatorning IS belgilari (gemo_protokol → patient["is_flags"]),
# (2) WBC R1..R4, (3) egri shakli, (4) ko'rsatkichlar (MCV, RDW, PLT ...).
# Matn — laboratoriya amaliy qadami (surtma / qayta o'lchash); tashxis emas.
# Darajalar: "!" — harakat kerak (qizil), "i" — ma'lumot (kulrang), "ok" — yashil.

# Analizator IS belgilari (BC-20S kodlari; 6300 namunada uchraganlari) → (panel, daraja, matn).
# Faqat soni yuqori/past (Leucocytosis, Anemia ...) belgilar qo'shilmaydi — ular
# jadvalda ↑/↓ bilan allaqachon ko'rinib turadi (shovqin bo'lmasin).
IS_IZOH = {
    "12045": ("WBC", "!", "Bir nechta hududda ogohlantirish (Rm) — formula ishonchsiz, surtma shart"),
    "12050": ("PLT", "!", "PLT/RBC chegarasi xira — mayda eritrotsit yoki bo'laklar PLT kanaliga "
                          "tushgan; PLT yolg'on baland bo'lishi mumkin, surtmada tasdiqlang"),
    "12016": ("PLT", "!", "Trombotsit taqsimoti g'ayrioddiy — PLT ishonchsiz, surtmada tasdiqlang"),
    "12052": ("PLT", "!", "Yirik trombotsit / trombotsit to'dasi — PLT yolg'on PAST bo'lishi mumkin; "
                          "laxta yo'qligini tekshiring, surtma"),
    "12051": ("PLT", "i", "Mayda zarrachalar ko'p (mikrotrombotsit yoki eritrotsit bo'laklari)"),
    "12013": ("RBC", "!", "Analizator: eritrotsit taqsimoti g'ayrioddiy — surtmada shaklini ko'ring"),
    "15199-3": ("RBC", "i", "Analizator: mikrotsitlar bor"),
    "15198-5": ("RBC", "i", "Analizator: makrotsitlar bor"),
    "12015": ("RBC", "!", "HGB ga xalaqit (lipemiya / juda yuqori WBC) — HGB, MCH, MCHC ishonchsiz "
                          "bo'lishi mumkin"),
}

REGION_IZOH = {
    "R1": "R1 — limfotsitdan chapda signal: trombotsit to'dasi, yadroli eritrotsit yoki "
          "parchalanmagan eritrotsit. WBC/LYM noto'g'ri bo'lishi mumkin — surtma",
    "R2": "R2 — LYM/MID chegarasi: atipik limfotsit, blast yoki plazmotsit ehtimoli. "
          "LYM%/MID% ishonchsiz — surtma ko'ring",
    "R3": "R3 — MID/GRAN chegarasi: yosh granulotsitlar yoki eozinofiliya ehtimoli. "
          "GRAN%/MID% ishonchsiz — surtma ko'ring",
    "R4": "R4 — o'ng chetda signal: neytrofillar juda ko'p yoki yirik hujayralar — surtma",
}


def _f(v):
    try:
        s = str(v).strip().lstrip("↑↓ ").replace(",", ".")
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def _smooth(data, k=2):
    n = len(data)
    return [sum(data[max(0, i - k):min(n, i + k + 1)]) / (min(n, i + k + 1) - max(0, i - k))
            for i in range(n)]


def _cho_qqilar(data, min_frac=0.25, min_gap=8):
    """Silliqlangan egri cho'qqilari (indeks) — balandligi max ning min_frac qismidan katta."""
    s = _smooth(data)
    mx = max(s) if s else 0
    if mx <= 0:
        return [], s
    pk = [i for i in range(1, len(s) - 1)
          if s[i] >= s[i - 1] and s[i] > s[i + 1] and s[i] >= mx * min_frac]
    out = []
    for i in pk:                              # bir-biriga juda yaqinlarini birlashtirish
        if out and i - out[-1] < min_gap:
            if s[i] > s[out[-1]]:
                out[-1] = i
        else:
            out.append(i)
    return out, s


def histogram_izoh(values: dict, histograms: dict, is_flags=None) -> dict:
    """Har bir gistogramma uchun izoh: {"WBC": [(daraja, matn), ...], "RBC": [...], "PLT": [...]}.

    values — {'WBC': '7.0', 'MCV': '57.5', ...} (edit qilingan qiymatlar bilan)
    """
    v = {k: _f(x) for k, x in (values or {}).items()}
    h = histograms or {}
    out = {"WBC": [], "RBC": [], "PLT": []}

    # 1) Analizator IS belgilari (MCV bo'yicha o'zimiz yozadiganlari takrorlanmaydi)
    _mcv = v.get("MCV")
    takror = set()
    if _mcv is not None and _mcv < 80:
        takror.add("15199-3")
    if _mcv is not None and _mcv > 100:
        takror.add("15198-5")
    for fl in (is_flags or []):
        kod = str(fl.get("code", ""))
        e = None if kod in takror else IS_IZOH.get(kod)
        if e:
            panel, lvl, txt = e
            if (lvl, txt) not in out[panel]:
                out[panel].append((lvl, txt))

    # 2) WBC: R1..R4 + juda kam hujayra
    for rf in sorted(set((h.get("WBC") or {}).get("flags") or [])):
        if rf in REGION_IZOH:
            out["WBC"].append(("!", REGION_IZOH[rf]))
    wbc = v.get("WBC")
    if wbc is not None and wbc < 1.0:
        out["WBC"].append(("!", f"WBC juda past ({wbc:g}) — gistogramma kam hujayradan tuzilgan, "
                                "formula (%) ishonchsiz; qayta o'lchang, formulani qo'lda hisoblang"))

    # 3) RBC: MCV bo'yicha siljish, RDW, ikki cho'qqi, Mentzer indeksi
    mcv, rbc, mch, rdw = v.get("MCV"), v.get("RBC"), v.get("MCH"), v.get("RDW-CV")
    if mcv is not None and mcv < 80:
        t = f"Egri CHAPGA siljigan — mikrotsitoz (MCV {mcv:g})"
        if mch is not None and mch < 27:
            t += ", gipoxromiya (MCH past)"
        out["RBC"].append(("!", t))
        if rbc:
            mi = mcv / rbc
            if mi > 13:
                izoh = "temir tanqisligiga ko'proq mos"
            else:
                izoh = "talasemiya tashuvchiligini istisno qilish kerak"
            out["RBC"].append(("i", f"Mentzer indeksi MCV/RBC = {mi:.1f} — {izoh} "
                                    f"(chegara 13). Xulosa — vrachniki"))
    elif mcv is not None and mcv > 100:
        out["RBC"].append(("!", f"Egri O'NGGA siljigan — makrotsitoz (MCV {mcv:g}); "
                                "B12/folat, jigar — vrach baholaydi"))
    if rdw is not None and rdw > 16:
        out["RBC"].append(("i", f"Egri keng — eritrotsitlar o'lchami har xil, anizotsitoz (RDW-CV {rdw:g})"))
    rd = (h.get("RBC") or {}).get("data") or []
    if rd:
        pk, s = _cho_qqilar(rd)
        if len(pk) >= 2:
            a, b = pk[0], pk[1]
            vodiy = min(s[a:b + 1])
            if vodiy <= 0.7 * min(s[a], s[b]):
                out["RBC"].append(("!", "IKKI cho'qqi — ikki xil eritrotsit populyatsiyasi (qon quyilgan, "
                                        "davolash boshlangan, aralash anemiya); surtma ko'ring"))

    # 4) PLT: o'ng chetda ko'tarilish, past/yuqori PLT
    plt = v.get("PLT")
    pdata = (h.get("PLT") or {}).get("data") or []
    if len(pdata) >= 110:
        s = _smooth(pdata)
        peak = max(s[3:60]) if max(s[3:60]) > 0 else 0
        o_rta = sum(s[76:90]) / 14.0           # ~25–29 fL
        chet = max(s[95:])                     # ~31 fL — o'q oxirigacha (ba'zan 36 fL da uziladi)
        # Me'yorda egri o'ngga qarab nolga tushadi; bu yerda oxiri o'rtadagidan
        # kamida 3 barobar baland va cho'qqining 20% idan ko'p bo'lsa — ko'tarilish
        if peak > 0 and chet >= 0.20 * peak and chet >= 3 * max(o_rta, 1.0):
            t = ("O'ng chetda KO'TARILISH (30–40 fL) — mayda eritrotsitlar/bo'laklar yoki yirik "
                 "trombotsitlar PLT kanaliga tushgan; PLT soni ishonchsiz — surtmada tasdiqlang")
            if mcv is not None and mcv < 75:
                t += f" (MCV {mcv:g} — mayda eritrotsitlar ehtimoli katta)"
            out["PLT"].append(("!", t))
    if plt is not None and plt < 100:
        out["PLT"].append(("!", f"PLT past ({plt:g}) — avval probirkada laxta / trombotsit to'dasi "
                                "yo'qligini tekshiring (EDTA psevdotrombotsitopeniya); surtmada tasdiqlang"))
    elif plt is not None and plt > 400 and mcv is not None and mcv < 75:
        out["PLT"].append(("i", f"PLT yuqori ({plt:g}) + mayda eritrotsitlar — ular PLT ga qo'shilib "
                                "sonni oshirgan bo'lishi mumkin"))

    for k in out:
        if not out[k] and (h.get(k) or {}).get("data"):
            out[k].append(("ok", "Odatiy shakl — alohida belgi yo'q"))
    return out


# ══════════════════════════════════════════════════════════════════════
#  SAQLASH (CBC JSON ichida ixcham shakl) — {"WBC": {"b64": "...", "lines": [...], "flags": [...]}}
# ══════════════════════════════════════════════════════════════════════
def pack_histograms(h: dict) -> dict:
    """patient["histograms"] → JSON uchun ixcham (Base64) shakl. Bo'sh bo'lsa {}."""
    import base64
    out = {}
    for k in HIST_ORDER:
        e = (h or {}).get(k) or {}
        data = e.get("data")
        if not data:
            continue
        item = {"b64": base64.b64encode(bytes(max(0, min(255, int(v))) for v in data)).decode("ascii")}
        if e.get("lines"):
            item["lines"] = [int(x) for x in e["lines"]]
        if e.get("flags"):
            item["flags"] = list(e["flags"])
        out[k] = item
    return out


def unpack_histograms(x) -> dict:
    """pack_histograms natijasi (yoki to'liq shakl) → {"WBC": {"data": [...], "lines": [...], "flags": [...]}}."""
    import base64
    out = {}
    if not isinstance(x, dict):
        return out
    for k in HIST_ORDER:
        e = x.get(k)
        if not isinstance(e, dict):
            continue
        data = e.get("data")
        if not data and e.get("b64"):
            try:
                data = list(base64.b64decode(e["b64"]))
            except Exception:
                data = None
        if data:
            out[k] = {"data": list(data), "lines": list(e.get("lines") or []), "flags": list(e.get("flags") or [])}
    return out


# ══════════════════════════════════════════════════════════════════════
#  BLANKA UCHUN RASM (oq fon, rangli qalin chiziq — siyoh tejaladi)
# ══════════════════════════════════════════════════════════════════════
PRINT_STYLE = {
    #        chiziq rangi,  juda och to'ldirish,  nomi (blankada)
    "WBC": {"color": (31, 90, 190),  "tint": (236, 242, 252), "title": "Leykotsitlar"},
    "RBC": {"color": (205, 30, 30),  "tint": (252, 236, 236), "title": "Eritrotsitlar"},
    "PLT": {"color": (35, 145, 45),  "tint": (234, 247, 234), "title": "Trombotsitlar"},
}


def _font(size, bold=False):
    from PIL import ImageFont
    names = ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf") if bold else \
            ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf")
    for n in names:
        for p in (n, r"C:\Windows\Fonts\%s" % n):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_print_png(histograms: dict, out, width_px: int = 1800, height_px: int = 250):
    """3 ta gistogrammani bitta oq fonli PNG ga chizadi (blanka uchun).
    out — fayl yo'li yoki BytesIO. Qaytaradi: True (chizildi) / False (ma'lumot yo'q)."""
    from PIL import Image, ImageDraw
    kinds = [k for k in HIST_ORDER if ((histograms or {}).get(k) or {}).get("data")]
    if not kinds:
        return False

    S = 2                                        # 2x chizib, keyin kichraytiramiz → silliq chiziq
    W, H = width_px * S, height_px * S
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Ixcham tartib: 1800x250 px = blankada 18 x 2.5 sm (10 px ≈ 1 mm; 26 px ≈ 7.4 pt).
    # Balandlik o'zgarsa yozuvlar ham mutanosib kattalashadi (k).
    k = max(0.8, min(2.0, height_px / 250.0))
    def z(v):
        return int(round(v * k)) * S
    gap = 12 * S
    n = len(HIST_ORDER)
    pw_total = (W - gap * (n - 1)) // n
    f_title = _font(z(26), bold=True)
    f_sub = _font(z(21))
    f_tick = _font(z(20))
    f_flag = _font(z(22), bold=True)
    grey, frame, sep = (70, 70, 70), (175, 175, 175), (120, 120, 120)

    for pi, kind in enumerate(HIST_ORDER):
        px0 = pi * (pw_total + gap)
        px1 = px0 + pw_total - 1
        d.rounded_rectangle([px0 + S, S, px1 - S, H - S], radius=8 * S, outline=frame, width=2 * S)

        st, ps = HIST_STYLE[kind], PRINT_STYLE[kind]
        hist = (histograms or {}).get(kind) or {}
        data = hist.get("data") or []

        # Sarlavha: "WBC" (rangli) + " — Leykotsitlar"
        tx, ty = px0 + 12 * S, z(3)
        d.text((tx, ty), kind, font=f_title, fill=ps["color"])
        tw = d.textlength(kind, font=f_title)
        d.text((tx + tw + 8 * S, ty + z(4)), "— " + ps["title"], font=f_sub, fill=grey)
        flags = sorted(set(hist.get("flags") or []))
        if flags:
            ft = " ".join(flags)
            d.text((px1 - 12 * S - d.textlength(ft, font=f_flag), ty + z(2)), ft, font=f_flag, fill=(210, 0, 0))

        # Chizma maydoni
        x0, x1 = px0 + 18 * S, px1 - z(30)
        y0, y1 = z(34), H - z(25)
        pw, ph = x1 - x0, y1 - y0

        if not data:
            msg = "ma'lumot yo'q"
            d.text(((x0 + x1) / 2 - d.textlength(msg, font=f_sub) / 2, (y0 + y1) / 2), msg, font=f_sub, fill=frame)
        else:
            m = len(data)
            pts = [(x0 + pw * (i + 0.5) / m, y1 - ph * min(max(v, 0), 255) / 255.0) for i, v in enumerate(data)]
            d.polygon([(x0, y1)] + pts + [(x1, y1)], fill=ps["tint"])
            # Ajratuvchi chiziqlar (shtrix)
            for ch in (hist.get("lines") or []):
                x = x0 + pw * (ch / 2.0) / m
                if x0 <= x <= x1:
                    yy = y0
                    while yy < y1:
                        d.line([(x, yy), (x, min(yy + 7 * S, y1))], fill=sep, width=2 * S)
                        yy += 12 * S
            d.line(pts, fill=ps["color"], width=4 * S, joint="curve")

        # O'qlar
        d.line([(x0, y1), (x1 + 6 * S, y1)], fill=grey, width=2 * S)
        d.line([(x0, y1), (x0, y0 - 4 * S)], fill=grey, width=2 * S)
        for t in st["ticks"]:
            x = x0 + pw * t / st["fl"]
            d.line([(x, y1), (x, y1 + 4 * S)], fill=grey, width=2 * S)
            s = str(t)
            d.text((x - d.textlength(s, font=f_tick) / 2, y1 + 4 * S), s, font=f_tick, fill=grey)
        d.text((x1 + 6 * S, y1 - z(24)), "fL", font=f_tick, fill=grey)

    img = img.resize((width_px, height_px), Image.LANCZOS)
    # Ixcham PNG (PDF hajmi uchun): palitraga o'tkazish
    img = img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    img.save(out, format="PNG", optimize=True)
    return True
