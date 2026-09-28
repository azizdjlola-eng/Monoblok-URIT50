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
