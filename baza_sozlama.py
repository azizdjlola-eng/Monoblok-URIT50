# -*- coding: utf-8 -*-
r"""
Baza ulanish sozlamasi — frozen-aware (manba va EXE da bir xil ishlaydi).

Mijoz EXE da db_config.txt ni qayerdan o'qish kerakligini hal qiladi va texnik
xodim uchun sodda sozlash oynasini beradi.

Umumiy joy:  %ProgramData%\AzizMedLine\db_config.txt
  - Barcha dasturlar (registratsiya, natija) shu bitta fayldan o'qiydi.
  - EXE qayerda bo'lishidan qat'i nazar ishlaydi.

Standalone ishga tushirish (sozlash oynasi):
    python baza_sozlama.py
"""

import os
import sys

DEFAULT = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "azizmed2026",
    "database": "lab_tizim",
    "port": 3306,
}


def konfig_papka() -> str:
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    return os.path.join(pd, "AzizMedLine")


def yozish_yoli() -> str:
    """db_config.txt yoziladigan umumiy joy."""
    return os.path.join(konfig_papka(), "db_config.txt")


def oqish_yollari() -> list:
    """db_config.txt qidiriladigan joylar (ustuvorlik tartibida)."""
    yollar = [yozish_yoli()]
    if getattr(sys, "frozen", False):
        yollar.append(os.path.join(os.path.dirname(sys.executable), "db_config.txt"))
    yollar.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_config.txt"))
    return yollar


def oqish_yoli() -> str:
    """Mavjud birinchi db_config.txt yo'li (topilmasa umumiy joy)."""
    for p in oqish_yollari():
        if os.path.exists(p):
            return p
    return yozish_yoli()


def oqi() -> dict:
    cfg = dict(DEFAULT)
    yol = oqish_yoli()
    if os.path.exists(yol):
        try:
            with open(yol, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key, value = key.strip().upper(), value.strip()
                    if key in ("HOST", "DB_HOST"):
                        cfg["host"] = value
                    elif key in ("USER", "DB_USER"):
                        cfg["user"] = value
                    elif key in ("PASS", "DB_PASS", "PASSWORD"):
                        cfg["password"] = value
                    elif key in ("DB", "DB_NAME", "DATABASE"):
                        cfg["database"] = value
                    elif key in ("PORT", "DB_PORT"):
                        try:
                            cfg["port"] = int(value)
                        except ValueError:
                            pass
        except Exception as e:
            print(f"db_config o'qishda xato: {e}")
    return cfg


def saqla(cfg: dict) -> str:
    """db_config.txt ni umumiy joyga yozadi. Yo'lni qaytaradi."""
    os.makedirs(konfig_papka(), exist_ok=True)
    yol = yozish_yoli()
    matn = (
        "# AzizMedLine — baza ulanish sozlamasi\n"
        f"HOST={cfg.get('host','127.0.0.1')}\n"
        f"USER={cfg.get('user','root')}\n"
        f"PASS={cfg.get('password','')}\n"
        f"DB={cfg.get('database','lab_tizim')}\n"
        f"PORT={cfg.get('port',3306)}\n"
    )
    # SSL qatori ilgari saqlashda jim tushib qolardi (login.py uni o'qiydi).
    ssl = str(cfg.get("ssl", "") or "").strip()
    if ssl and ssl.lower() != "auto":
        matn += f"SSL={ssl}\n"
    with open(yol, "w", encoding="utf-8") as f:
        f.write(matn)
    return yol


# ── Sozlama master paroli (DB'siz — login oynasidan ulanish sozlash uchun) ──
_SOZLAMA_PAROL_DEFAULT = "azizmed2026"


def sozlama_parol() -> str:
    """
    Ulanish sozlamalarini ochish uchun DOIMIY master parol (bazaga bog'liq emas).
    %ProgramData%\\AzizMedLine\\sozlama_parol.txt bo'lsa — undan; bo'lmasa default.
    Shu tarzda DB o'lik bo'lsa ham admin sozlamani ocha oladi.
    """
    p = os.path.join(konfig_papka(), "sozlama_parol.txt")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except Exception:
            pass
    return _SOZLAMA_PAROL_DEFAULT


def sozlama_parol_saqla(yangi: str) -> str:
    """Master sozlama parolini o'zgartiradi (sozlama_parol.txt ga yozadi)."""
    os.makedirs(konfig_papka(), exist_ok=True)
    p = os.path.join(konfig_papka(), "sozlama_parol.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write((yangi or "").strip())
    return p


def ichki_tarmoqmi(host: str) -> bool:
    """Manzil klinikaning O'Z tarmog'idami (RFC 1918 / lokal nom)."""
    host = (host or "").strip().lower()
    if not host:
        return False
    try:
        import ipaddress
        manzil = ipaddress.ip_address(host)
        return bool(manzil.is_private or manzil.is_loopback or manzil.is_link_local)
    except ValueError:
        pass
    # IP emas — kompyuter nomi. Nuqtasiz nom internetda bo'lmaydi.
    if "." not in host:
        return True
    return host.endswith((".local", ".lan", ".home", ".mshome.net", ".internal"))


# ═══════════════════════════════════════════════════════════════════════════
# caching_sha2_password KESHI (MySQL 8) — "1045 Access denied" ning ildizi
# ═══════════════════════════════════════════════════════════════════════════
# NOSOZLIK: parol TO'G'RI bo'la turib dastur "1045 (28000): Access denied for
# user 'root'@'localhost' (using password: YES)" berardi. Sabab uch narsaning
# BIRIKISHIDA:
#   1. MySQL rasmiy installeri (MySQL80) `root@localhost` ni
#      `caching_sha2_password` bilan yaratadi (eski AzizMedLine MySQL'i esa
#      `mysql_native_password` ishlatardi — shuning uchun ilgari muammo yo'q edi).
#   2. Tezlik uchun TLS o'chirildi (`ssl_disabled=True`) — 13.5s → 1.2s.
#   3. caching_sha2 QOIDASI: kesh BO'SH bo'lsa to'liq autentifikatsiya kerak,
#      u esa FAQAT shifrlangan kanalda yoki server RSA kaliti bilan bo'ladi.
#      `ssl_disabled=True` ikkalasini ham yopadi → server 1045 qaytaradi.
# Kesh MySQL har qayta ishga tushganda (yoki FLUSH PRIVILEGES da) BO'SHAYDI —
# shuning uchun nosozlik "goh bor, goh yo'q" bo'lib ko'rinardi va odатda
# kompyuter qayta yoqilgandan keyin boshlanardi.
# YECHIM: bir marta TLS bilan ulansak, server keshni to'ldiradi va shundan
# keyin TEZKOR (TLS'siz) ulanish YANA ishlaydi. Ya'ni sekin yo'l uchun faqat
# BITTA ulanish to'lanadi, tezlik yutug'i saqlanadi.

_SHA2_TEKSHIRILDI = {}      # (host, port, user) -> tekshirilgan vaqt (monotonic)
_SHA2_QAYTA_URINISH = 30.0  # server o'lik bo'lsa har chaqiruvda urinmaslik uchun
_SHA2_ICHIDA = False        # isitish ulanishining o'zi qayta kirmasin


def sha2_keshini_isit(cfg: dict) -> bool:
    """TLS'siz ulanish 1045 bersa — bir marta TLS bilan ulanib, serverning
    caching_sha2 keshini to'ldiradi. Qaytaradi: isitish BAJARILDIMI.

    Xavfsiz: parol haqiqatan noto'g'ri bo'lsa TLS bilan ham 1045 keladi va
    funksiya False qaytaradi — ya'ni bu yechim noto'g'ri parolni YASHIRMAYDI.
    """
    global _SHA2_ICHIDA
    if _SHA2_ICHIDA:
        return False
    try:
        import mysql.connector
    except Exception:
        return False
    _SHA2_ICHIDA = True
    try:
        conn = mysql.connector.connect(
            host=cfg.get("host", "127.0.0.1"), user=cfg.get("user", "root"),
            password=cfg.get("password", ""), port=int(cfg.get("port", 3306) or 3306),
            connection_timeout=8, use_pure=True,
            # database ATAYIN berilmaydi — baza hali yaratilmagan bo'lsa ham
            # kesh isishi kerak (aks holda BazaUstasi ham ishlay olmasdi).
        )
        conn.close()
        return True
    except Exception:
        return False
    finally:
        _SHA2_ICHIDA = False


def _sha2_kesh_kerakmi(cfg: dict):
    """TLS'siz ulanishdan OLDIN bir martalik tekshiruv: tezkor yo'l ishlaydimi?
    Ishlamasa (1045) keshni isitib qo'yamiz. Har jarayonda bir marta."""
    if _SHA2_ICHIDA:
        return
    try:
        import mysql.connector
    except Exception:
        return
    # ⚠️ PAROL ham kalitning bir qismi (ochiq holda EMAS — xesh bilan).
    # Nega: agar biror joy AVVAL noto'g'ri parol bilan tekshirsa (masalan
    # sozlama oynasidagi "Tekshirish"), belgi qo'yilib qolar va keyingi
    # HAQIQIY ulanish sovuq keshda isitilmay 1045 bilan yiqilardi.
    import hashlib as _h
    kalit = (str(cfg.get("host", "")), str(cfg.get("port", 3306)),
             str(cfg.get("user", "")),
             _h.sha256(str(cfg.get("password", "")).encode()).hexdigest()[:16])
    import time as _t
    oxirgi = _SHA2_TEKSHIRILDI.get(kalit)
    if oxirgi is not None and (oxirgi is True or
                               (_t.monotonic() - oxirgi) < _SHA2_QAYTA_URINISH):
        return
    try:
        conn = mysql.connector.connect(
            host=cfg.get("host", "127.0.0.1"), user=cfg.get("user", "root"),
            password=cfg.get("password", ""), port=int(cfg.get("port", 3306) or 3306),
            connection_timeout=5, use_pure=True, ssl_disabled=True)
        conn.close()
        _SHA2_TEKSHIRILDI[kalit] = True      # tezkor yo'l ishlayapti
        return
    except Exception as e:
        if "1045" in str(e) or "Access denied" in str(e):
            if sha2_keshini_isit(cfg):
                _SHA2_TEKSHIRILDI[kalit] = True
                print("[DB] caching_sha2 keshi isitildi — tezkor (TLS'siz) "
                      "ulanish yana ishlaydi")
                return
            # TLS bilan ham o'tmadi → parol HAQIQATAN noto'g'ri.
            _SHA2_TEKSHIRILDI[kalit] = True
            return
        # Server o'lik / tarmoq yo'q — bu boshqa muammo. Qisqa muddat kutamiz.
        _SHA2_TEKSHIRILDI[kalit] = _t.monotonic()


def tls_kwargs(cfg: dict) -> dict:
    """MySQL ulanishida TLS kerakmi — BARCHA modullar uchun YAGONA qoida.

    NEGA YAGONA JOYDA: bu qoida 6 ta faylda (registrator, login, tv_server,
    vrach_web, sms_watcher, lims_sync_server, baza_sinxron) nusxa-ko'chirilgan
    edi va hammasida bir xil kamchilik bor edi — TLS faqat `127.0.0.1` uchun
    o'chirilardi. Bazasi boshqa kompyuterda turgan har bir ish o'rni esa har
    ulanishga ~790 ms to'lardi (shu kompyuterda o'lchandi: 2.8 ms → 788 ms).
    Bitta joyda tuzatilsa hammasi tuzalsin.

    Qoida:
      SSL=on   → TLS majburiy (hamma joyda)
      SSL=off  → TLS o'chiq (hamma joyda)
      auto     → ichki tarmoq (127.0.0.1, 192.168.x, 10.x, LABSERVER...) = o'chiq,
                 tashqi/internet manzil = TLS QOLADI
    """
    cfg = cfg or {}
    rejim = str(cfg.get("ssl", "auto") or "auto").lower()
    if rejim in ("on", "yes", "1", "true", "yoqilgan"):
        return {}
    if rejim in ("off", "no", "0", "false", "o'chiq", "ochirilgan"):
        natija = {"ssl_disabled": True}
    else:
        host = str(cfg.get("host", "") or cfg.get("HOST", "") or "").strip().lower()
        if host in ("127.0.0.1", "localhost", "::1", ""):
            natija = {"ssl_disabled": True}
        else:
            natija = {"ssl_disabled": True} if ichki_tarmoqmi(host) else {}

    # TLS o'chirilayotgan bo'lsa — caching_sha2 keshi sovuq emasligiga
    # ishonch hosil qilamiz (yuqoridagi izohga qarang). Har jarayonda BIR
    # MARTA, faqat to'liq ma'lumot bo'lganda.
    if natija.get("ssl_disabled") and cfg.get("user") and cfg.get("password"):
        try:
            _sha2_kesh_kerakmi(cfg)
        except Exception:
            pass
    return natija


def bu_kompyuter_ip() -> str:
    """
    Shu kompyuterning LAN IP manzili (boshqa kompyuter shuni terib ulanadi).
    Topilmasa '127.0.0.1'.
    """
    import socket
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))   # tashqi ulanish shart emas — faqat lokal IP ni aniqlaydi
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    return ip


# MySQL xizmati har o'rnatishda bir xil nomlanmaydi:
#   "AzizMedLineMySQL" — bizning FULL o'rnatish yaratadi,
#   "MySQL80"          — rasmiy MySQL Installer yaratadi (asosiy kompyuterlarda).
# Ilgari faqat birinchi nom so'ralardi va MySQL80 li kompyuterda xizmat "yoq"
# hisoblanardi -> "🔧 Lokal MySQL'ni ishga tushirish" tugmasi noto'g'ri
# "xizmat o'rnatilmagan" deb javob berardi (2026-08-22).
_MYSQL_SERVICES = ("AzizMedLineMySQL", "MySQL80")
_MYSQL_SERVICE = _MYSQL_SERVICES[0]   # eski kod bilan moslik uchun


def _port_ochiqmi(host: str, port: int, timeout: float = 2.0) -> bool:
    """TCP port ochiq (kimdir tinglayaptimi) — MySQL tirikligini bilish uchun."""
    import socket
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _sc_bitta(nom: str) -> str:
    """Bitta xizmatning holati: 'yoq' | 'running' | 'stopped'.
    (sc query STATE 'RUNNING'/'STOPPED' — til-mustaqil kalitlar; returncode 1060=yo'q.)"""
    import subprocess
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(["sc", "query", nom],
                           capture_output=True, text=True, errors="replace",
                           creationflags=cf, timeout=10)
        if r.returncode != 0:
            return "yoq"
        up = (r.stdout or "").upper()
        if "RUNNING" in up:
            return "running"
        return "stopped"
    except Exception:
        return "yoq"


def _mysql_xizmat_top():
    """Bu kompyuterdagi MySQL xizmatining (nom, holat) juftligi.
    Ishlab turgani ustun, keyin to'xtab qolgani; hech biri yo'q bo'lsa (None, 'yoq')."""
    toxtagan = None
    for nom in _MYSQL_SERVICES:
        holat = _sc_bitta(nom)
        if holat == "running":
            return nom, "running"
        if holat == "stopped" and toxtagan is None:
            toxtagan = nom
    if toxtagan:
        return toxtagan, "stopped"
    return None, "yoq"


def _sc_holat() -> str:
    """MySQL xizmati holati: 'yoq' | 'running' | 'stopped' (nomi qaysi bo'lsa ham)."""
    return _mysql_xizmat_top()[1]


def lokal_mysql_ishga_tushir():
    """
    Lokal AzizMedLineMySQL Windows xizmatini ishga tushirishga urinadi.
    (ok, xabar). Admin huquqi kerak bo'lishi mumkin.
    """
    import subprocess
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    nom, holat = _mysql_xizmat_top()
    if holat == "yoq":
        return False, ("MySQL xizmati bu kompyuterda o'rnatilmagan.\n"
                       "FULL o'rnatish (MySQL bilan) yoki BazaUstasi orqali bazani sozlang.")
    if holat == "running":
        return True, "MySQL allaqachon ishlayapti."
    # stopped — ishga tushiramiz (xizmat nomi qaysi bo'lsa o'shani)
    try:
        subprocess.run(["net", "start", nom],
                       capture_output=True, creationflags=cf, timeout=45)
    except Exception:
        pass
    if _sc_holat() == "running":
        return True, "MySQL xizmati ishga tushdi."
    return False, ("MySQL xizmatini ishga tushirib bo'lmadi (ehtimol administrator huquqi kerak).\n"
                   "Dasturni 'Administrator sifatida ishga tushiring' yoki BazaUstasi'ni oching.")


def ulanish_diagnostika(cfg: dict) -> str:
    """
    Ulanish nega bo'lmayotganini aniqlaydi va aniq yo'l-yo'riq beradi
    (MySQL o'chiqmi / tarmoqmi / parolmi).
    """
    host = str(cfg.get("host", "127.0.0.1")).strip()
    try:
        port = int(cfg.get("port", 3306) or 3306)
    except Exception:
        port = 3306
    lokalmi = host in ("127.0.0.1", "localhost", "::1")

    if not _port_ochiqmi(host, port):
        if lokalmi:
            return ("⛔ MySQL server BU kompyuterda ishlamayapti (port 3306 yopiq).\n\n"
                    "Yechim: '🔧 Lokal MySQL'ni ishga tushirish' tugmasini bosing.\n"
                    "Agar yordam bermasa — BazaUstasi (FULL o'rnatish) orqali bazani sozlang.")
        return (f"⛔ '{host}:{port}' manziliga ulanib bo'lmadi (tarmoq/IP/firewall).\n\n"
                "Tekshiring:\n"
                "• IP TO'G'RI terilganmi (masalan 192.168.13.42 — 198.162 EMAS!)\n"
                "• O'sha (asosiy) kompyuter yoniqmi va bir tarmoqdami\n"
                "• Asosiy kompyuterda MySQL ishlayaptimi")

    ok, msg = test_ulanish(cfg)
    if ok:
        return "✅ Ulanish muvaffaqiyatli."
    if "1045" in msg or "Access denied" in msg:
        return (f"⚠️ Server ishlayapti, lekin PAROL qabul qilinmadi:\n{msg}\n\n"
                "Bu holatda kod caching_sha2 keshini isitishga ham urinib "
                "ko'rdi (MySQL 8 ning sovuq-kesh nosozligi) — demak sabab "
                "haqiqatan foydalanuvchi/parol yoki ruxsat (grant).\n\n"
                "Tekshiring:\n"
                "• db_config.txt dagi USER/PASS shu MySQL niki ekanmi\n"
                "• Bu kompyuterda MySQL rasmiy installer bilan qayta "
                "o'rnatilmaganmi (u root paroli BOSHQA bo'ladi)")
    return (f"⚠️ Server javob beryapti, lekin ulanmadi:\n{msg}\n\n"
            "Odatda foydalanuvchi/parol yoki ruxsat (grant) noto'g'ri.")


def test_ulanish(cfg: dict):
    """(ok, xabar) qaytaradi.

    ⚠️ `cfg[...]` EMAS, `cfg.get(...)` — chaqiruvchilarning hammasida ham
    `port` kaliti yo'q edi (masalan `login.load_db_config()`). KeyError
    tashqariga «Ulanmadi: 'port'» bo'lib chiqar va foydalanuvchi buni
    ulanish xatosi deb o'qir edi: haqiqiy sabab BUTUNLAY berkitilgan edi.

    ⚠️ TLS qoidasi dasturdagi bilan AYNAN bir xil bo'lishi shart. Ilgari bu
    yerda TLS doim yoqiq edi — natijada «Tekshirish» tugmasi ✅ deb turgan
    paytda dastur o'zi 1045 bilan yiqilardi (caching_sha2 keshi izohiga
    qarang), ya'ni tekshiruv nosozlikni KO'RSATMASDI."""
    try:
        import mysql.connector
        kw = dict(
            host=cfg.get("host", "127.0.0.1"), user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", "lab_tizim"),
            connection_timeout=5,
            use_pure=True,   # C-extension "Failed raising error" nosozligidan saqlanish
        )
        try:
            kw["port"] = int(cfg.get("port", 3306) or 3306)
        except (TypeError, ValueError):
            kw["port"] = 3306
        kw.update(tls_kwargs(cfg))
        conn = mysql.connector.connect(**kw)
        conn.close()
        return True, "Ulanish muvaffaqiyatli ✅"
    except Exception as e:
        return False, f"Ulanmadi: {e}"


# ─────────────────────── Tarmoq / IP yordamchilari ───────────────────────
def barcha_iplar() -> list:
    """Shu kompyuterning LAN IP manzillari (127.* dan tashqari).
    Boshqa kompyuter/TV/telefon shu manzilni teradi."""
    import socket
    natija = []
    try:
        asosiy = bu_kompyuter_ip()
        if asosiy and not asosiy.startswith("127."):
            natija.append(asosiy)
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in natija:
                natija.append(ip)
    except Exception:
        pass
    return natija or ["127.0.0.1"]


# ─────────────────── Serverni tarmoqdan avtomatik topish ───────────────────
# NEGA: ish o'rni (Registratsiya/Natija/Vrach) SERVER kompyuterning IP sini
# qo'lda terardi. Wi-Fi/router DHCP serverga keyingi yoqilishda boshqa IP
# berishi mumkin — shunda hamma kabinet birdan «baza topilmadi» deydi, texnik
# xodim esa yangi IP ni qayerdan bilishni bilmaydi. Endi ish o'rni o'zi
# tarmoqni (o'z /24 qismi) skanerlaydi: MySQL porti ochiq kompyuterlarni
# topadi va HAR BIRIDA haqiqatan bizning baza borligini (parol + jadval +
# bemorlar soni) tekshiradi. Bemorlar soni ko'rsatiladi — tasodifan BO'SH
# bazaga ulanib «bemorlar yo'qoldi» bo'lmasligi uchun.
SERVER_PORTLARI = (3306, 3307, 3308)   # BazaUstasi 3306 band bo'lsa keyingisini oladi


def _qidiriladigan_tarmoqlar() -> list:
    """Skanerlanadigan /24 tarmoqlar prefiksi: ['192.168.0.', ...].
    Faqat xususiy (LAN) manzillar; 169.254 (DHCP olinmagan) va 127 tashlanadi.
    Virtual adapterlar (VirtualBox/Hyper-V) ham kirishi mumkin — zarari yo'q,
    lekin ko'p bo'lib ketmasin deb 4 tagacha."""
    import ipaddress
    prefikslar = []
    for ip in barcha_iplar():
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.version != 4 or not a.is_private or a.is_loopback or a.is_link_local:
            continue
        p = ip.rsplit(".", 1)[0] + "."
        if p not in prefikslar:
            prefikslar.append(p)
    return prefikslar[:4]


def _nom_top(ip: str, kutish: float = 1.5) -> str:
    """IP → kompyuter nomi (topilmasa ''). gethostbyaddr Windows'da NetBIOS
    bilan bir necha soniya osilib qolishi mumkin — shuning uchun alohida
    daemon oqimda, cheklangan kutish bilan."""
    import socket
    import threading
    natija = {"nom": ""}

    def _ish():
        try:
            natija["nom"] = socket.gethostbyaddr(ip)[0].split(".")[0].upper()
        except Exception:
            pass

    t = threading.Thread(target=_ish, daemon=True)
    t.start()
    t.join(kutish)
    return natija["nom"]


def _lims_bazasini_tekshir(cfg: dict) -> dict:
    """Ochiq port — bizning bazami? {'holat': 'ok'|'parol'|'baza_yoq'|'xato',
    'bemorlar': int|None, 'xabar': str}."""
    try:
        import mysql.connector
    except Exception as e:
        return {"holat": "xato", "bemorlar": None, "xabar": str(e)}
    try:
        kw = dict(host=cfg["host"], port=int(cfg["port"]),
                  user=cfg.get("user", "root"), password=cfg.get("password", ""),
                  database=cfg.get("database", "lab_tizim"),
                  connection_timeout=5, use_pure=True)
        kw.update(tls_kwargs(cfg))
        conn = mysql.connector.connect(**kw)
    except Exception as e:
        s = str(e)
        # 1044 = foydalanuvchi to'g'ri, lekin bu bazaga ruxsati yo'q (yoki baza
        # yo'q) — matnida ham «Access denied» bor, shuning uchun 1045 dan OLDIN.
        if "1049" in s or "Unknown database" in s or "1044" in s:
            return {"holat": "baza_yoq", "bemorlar": None,
                    "xabar": f"MySQL bor, lekin «{cfg.get('database', 'lab_tizim')}» bazasi yo'q"}
        if "1045" in s or "Access denied" in s:
            return {"holat": "parol", "bemorlar": None,
                    "xabar": "MySQL bor, lekin parol mos emas (boshqa dastur bazasi)"}
        return {"holat": "xato", "bemorlar": None, "xabar": s[:160]}
    try:
        cur = conn.cursor()
        cur.execute("SHOW TABLES LIKE 'foydalanuvchilar'")
        if not cur.fetchall():
            return {"holat": "baza_yoq", "bemorlar": None,
                    "xabar": "Baza bor, lekin LIMS jadvallari yo'q (BazaUstasi tugallanmagan?)"}
        bemorlar = None
        try:
            cur.execute("SELECT COUNT(*) FROM bemorlar")
            bemorlar = int(cur.fetchone()[0])
        except Exception:
            pass
        cur.close()
        return {"holat": "ok", "bemorlar": bemorlar, "xabar": "LIMS bazasi"}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def server_qidir(cfg: dict, jarayon=None, toxtat=None, port_kutish: float = 0.5) -> list:
    """Lokal tarmoqdan LIMS bazasi turgan kompyuter(lar)ni topadi.

    cfg      — foydalanuvchi/parol/baza nomi shu yerdan olinadi (host/port emas).
    jarayon  — ixtiyoriy callback(bajarildi, jami). ⚠️ ISHCHI oqimdan chaqiriladi —
               tkinter'ga to'g'ridan-to'g'ri tegmasin (holat lug'atiga yozsin).
    toxtat   — ixtiyoriy threading.Event: o'rnatilsa skanerlash to'xtaydi.

    Qaytaradi: [{'host','port','nomi','holat','bemorlar','xabar','shu_kompyuter'}],
    yaroqlilari (holat='ok') birinchi, bemorlar soni bo'yicha kamayish tartibida.
    Bitta /24 tarmoq ~2-3 soniya.
    """
    import socket
    from concurrent.futures import ThreadPoolExecutor, as_completed

    oz_iplar = set(barcha_iplar())
    nishonlar = [(f"{p}{i}", port) for p in _qidiriladigan_tarmoqlar()
                 for i in range(1, 255) for port in SERVER_PORTLARI]
    jami = len(nishonlar)

    def _ochiqmi(nishon):
        if toxtat is not None and toxtat.is_set():
            return None
        try:
            s = socket.create_connection(nishon, timeout=port_kutish)
            s.close()
            return nishon
        except Exception:
            return None

    ochiqlar = []
    bajarildi = 0
    if jami:
        with ThreadPoolExecutor(max_workers=200) as ex:
            for f in as_completed([ex.submit(_ochiqmi, n) for n in nishonlar]):
                bajarildi += 1
                r = f.result()
                if r:
                    ochiqlar.append(r)
                if jarayon and (bajarildi % 50 == 0 or bajarildi == jami):
                    try:
                        jarayon(bajarildi, jami)
                    except Exception:
                        pass

    topilgan = []
    # Tekshiruv KETMA-KET: sha2 keshini isitish (tls_kwargs) global bayroq
    # ishlatadi — parallel chaqirilsa bir-biriga xalaqit beradi.
    for host, port in sorted(ochiqlar):
        if toxtat is not None and toxtat.is_set():
            break
        c = dict(cfg)
        c["host"], c["port"] = host, port
        t = _lims_bazasini_tekshir(c)
        t.update(host=host, port=port, shu_kompyuter=host in oz_iplar,
                 nomi=_nom_top(host) if t["holat"] == "ok" else "")
        topilgan.append(t)
    topilgan.sort(key=lambda d: (d["holat"] != "ok", -(d["bemorlar"] or 0), d["host"]))
    return topilgan


def qayta_qidirish_kerakmi(cfg: dict) -> bool:
    """Login ulanmaganda: «server IP si o'zgargan bo'lishi mumkin» holatimi?
    Faqat host LAN IP raqami bo'lsa va o'sha manzilda port umuman yopiq
    bo'lsa True. (Parol xatosi yoki 127.0.0.1 — IP almashuvi emas.)"""
    import ipaddress
    host = str(cfg.get("host", "") or "").strip()
    try:
        a = ipaddress.ip_address(host)
    except ValueError:
        return False
    if a.version != 4 or a.is_loopback or not a.is_private:
        return False
    try:
        port = int(cfg.get("port", 3306) or 3306)
    except (TypeError, ValueError):
        port = 3306
    return not _port_ochiqmi(host, port)


def server_qidir_oynasi(parent, cfg: dict):
    """«🔍 Serverni avtomatik topish» oynasi (modal). Tarmoqni skanerlaydi,
    topilgan bazalarni ro'yxatda ko'rsatadi. Foydalanuvchi tanlasa — host/port
    almashtirilgan cfg NUSXASINI qaytaradi (SAQLAMAYDI — saqlash chaqiruvchida).
    Bekor qilinsa None."""
    import threading
    import tkinter as tk
    from tkinter import ttk

    cfg = dict(cfg or {})
    natija = {"cfg": None}
    holat = {"bajarildi": 0, "jami": 1, "tayyor": False, "royxat": [], "xato": ""}
    toxtat = threading.Event()

    oyna = tk.Toplevel(parent)
    oyna.title("Serverni tarmoqdan topish")
    oyna.geometry("640x400")
    oyna.resizable(True, True)
    try:
        oyna.transient(parent.winfo_toplevel())
        oyna.grab_set()
    except Exception:
        pass

    tarmoqlar = ", ".join(p + "x" for p in _qidiriladigan_tarmoqlar()) or "—"
    sarlavha = ttk.Label(oyna, text=f"Tarmoq qidirilmoqda ({tarmoqlar}) ...",
                         font=("Segoe UI", 10, "bold"))
    sarlavha.pack(anchor="w", padx=12, pady=(12, 4))
    pb = ttk.Progressbar(oyna, mode="determinate", maximum=100)
    pb.pack(fill="x", padx=12)

    ustunlar = ("manzil", "nomi", "bemorlar", "holat")
    jadval = ttk.Treeview(oyna, columns=ustunlar, show="headings", height=8,
                          selectmode="browse")
    for k, sarl, en in (("manzil", "Manzil", 150), ("nomi", "Kompyuter nomi", 140),
                        ("bemorlar", "Bemorlar", 80), ("holat", "Holat", 240)):
        jadval.heading(k, text=sarl)
        jadval.column(k, width=en, anchor="w")
    jadval.pack(fill="both", expand=True, padx=12, pady=8)

    izoh = ttk.Label(oyna, text="", foreground="#555", wraplength=600, justify="left")
    izoh.pack(fill="x", padx=12)

    tugmalar = ttk.Frame(oyna)
    tugmalar.pack(fill="x", padx=12, pady=10)

    def _tanla(_e=None):
        sel = jadval.selection()
        if not sel:
            return
        d = holat["royxat"][int(sel[0])]
        if d["holat"] != "ok":
            izoh.config(text="Bu manzilda LIMS bazasi yo'q — ✅ belgili qatorni tanlang.",
                        foreground="#c0392b")
            return
        c = dict(cfg)
        # Server SHU kompyuterning o'zi bo'lsa — 127.0.0.1 (IP o'zgarsa ham ishlaydi)
        c["host"] = "127.0.0.1" if d["shu_kompyuter"] else d["host"]
        c["port"] = d["port"]
        natija["cfg"] = c
        _yop()

    def _yop():
        toxtat.set()
        try:
            oyna.grab_release()
        except Exception:
            pass
        oyna.destroy()

    def _boshla():
        toxtat.clear()
        holat.update(bajarildi=0, jami=1, tayyor=False, royxat=[], xato="")
        jadval.delete(*jadval.get_children())
        sarlavha.config(text=f"Tarmoq qidirilmoqda ({tarmoqlar}) ...")
        izoh.config(text="Odatda 3-5 soniya.", foreground="#555")
        b_qayta.config(state="disabled")

        def _jarayon(b, j):
            holat["bajarildi"], holat["jami"] = b, j

        def _ish():
            try:
                holat["royxat"] = server_qidir(cfg, jarayon=_jarayon, toxtat=toxtat)
            except Exception as e:
                holat["xato"] = str(e)
            holat["tayyor"] = True

        threading.Thread(target=_ish, daemon=True).start()
        oyna.after(150, _tik)

    def _tik():
        if not oyna.winfo_exists():
            return
        pb["value"] = 100.0 * holat["bajarildi"] / max(holat["jami"], 1)
        if not holat["tayyor"]:
            oyna.after(150, _tik)
            return
        pb["value"] = 100
        b_qayta.config(state="normal")
        royxat = holat["royxat"]
        for i, d in enumerate(royxat):
            belgi = "✅ " if d["holat"] == "ok" else "⚠️ "
            manzil = f"{d['host']}:{d['port']}"
            if d["shu_kompyuter"]:
                manzil += " (shu)"
            jadval.insert("", "end", iid=str(i), values=(
                manzil, d.get("nomi", ""),
                "" if d["bemorlar"] is None else d["bemorlar"],
                belgi + d["xabar"]))
        yaroqli = [i for i, d in enumerate(royxat) if d["holat"] == "ok"]
        if holat["xato"]:
            sarlavha.config(text="Qidiruvda xato")
            izoh.config(text=holat["xato"], foreground="#c0392b")
        elif yaroqli:
            sarlavha.config(text=f"Topildi: {len(yaroqli)} ta LIMS bazasi")
            jadval.selection_set(str(yaroqli[0]))
            izoh.config(foreground="#1f8a4c", text=(
                "Bemorlar soni ENG KO'P bo'lgani odatda haqiqiy server. "
                "Tanlang va «Shu serverga ulanish» ni bosing (yoki ikki marta bosing).\n"
                "⚠️ Faqat HAQIQIY SERVER kompyuterni tanlang. Server o'chiq bo'lsa — "
                "avval uni yoqing: boshqa kompyuterdagi eski/sinov bazasi tanlansa "
                "ma'lumot ikkiga bo'linib ketadi."))
        else:
            sarlavha.config(text="LIMS bazasi topilmadi")
            izoh.config(foreground="#c0392b", text=(
                "Tekshiring:  • SERVER kompyuter yoniqmi, BazaUstasi tugallanganmi\n"
                "• Ikkala kompyuter BITTA routerga ulanganmi (mehmon Wi-Fi emas)\n"
                "• Serverda «Boshqa kompyuterlarga ruxsat» bosilganmi; "
                "antivirus fayrvoli 3306-portni yopmayaptimi\n"
                "• Router «AP isolation / mijozlarni ajratish» yoqilmaganmi"))

    b_tanla = ttk.Button(tugmalar, text="✅ Shu serverga ulanish", command=_tanla)
    b_tanla.pack(side="right", padx=4)
    ttk.Button(tugmalar, text="Bekor", command=_yop).pack(side="right", padx=4)
    b_qayta = ttk.Button(tugmalar, text="🔄 Qayta qidirish", command=_boshla)
    b_qayta.pack(side="left", padx=4)
    jadval.bind("<Double-1>", _tanla)
    oyna.protocol("WM_DELETE_WINDOW", _yop)

    _boshla()
    oyna.wait_window()
    return natija["cfg"]


# ─────────────────── Xizmatlar (Vrach kabineti / TV server) ───────────────────
VRACH_PORT = 8090
TV_PORT = 8765

# Vrach kabineti config.json standart qiymatlari (vrach_web/app.py bilan bir xil)
VRACH_DEFAULT = {
    "port": VRACH_PORT,
    "host_bind": "127.0.0.1",
    "tv_server_url": f"http://127.0.0.1:{TV_PORT}",
    "tv_ids": ["ALL"],
    "xona": "kabinet",
}


def xizmat_papka(nom: str) -> str:
    """%ProgramData%\\AzizMedLine\\<nom> — EXE rejimida xizmatlar shu yerda ishlaydi."""
    yol = os.path.join(konfig_papka(), nom)
    try:
        os.makedirs(yol, exist_ok=True)
    except Exception:
        pass
    return yol


def vrach_config_yol() -> str:
    """Vrach kabineti config.json yo'li.
    EXE: %ProgramData%\\AzizMedLine\\VrachKabineti\\config.json  (app.py shu yerdan o'qiydi)
    Dev: vrach_web\\config.json"""
    if getattr(sys, "frozen", False):
        return os.path.join(xizmat_papka("VrachKabineti"), "config.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vrach_web", "config.json")


def vrach_config_oqi() -> dict:
    import json
    cfg = dict(VRACH_DEFAULT)
    yol = vrach_config_yol()
    try:
        if os.path.exists(yol):
            with open(yol, "r", encoding="utf-8") as f:
                mavjud = json.load(f)
            if isinstance(mavjud, dict):
                cfg.update(mavjud)
    except Exception as e:
        print(f"vrach config.json o'qilmadi: {e}")
    return cfg


def vrach_config_saqla(yangilar: dict) -> str:
    """config.json dagi FAQAT berilgan kalitlarni yangilaydi — qolgan sozlamalar
    (blanka ranglari, vrach_id, Word papkasi...) saqlanib qoladi."""
    import json
    yol = vrach_config_yol()
    mavjud = {}
    try:
        if os.path.exists(yol):
            with open(yol, "r", encoding="utf-8") as f:
                o = json.load(f)
            if isinstance(o, dict):
                mavjud = o
    except Exception:
        mavjud = {}
    mavjud.update(yangilar)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(mavjud, f, ensure_ascii=False, indent=2)
    return yol


_XIZMAT_EXE = {"VrachKabineti": "VrachKabineti.exe", "TVServer": "AzizMedTVServer.exe"}


def xizmat_exe(nom: str) -> str:
    """O'rnatmadagi xizmat EXE yo'li ('VrachKabineti' | 'TVServer').
    Sozlama EXE  ...\\AzizMedLine\\Sozlama\\  da turadi — qo'shni papkani qaraymiz."""
    if not getattr(sys, "frozen", False):
        return ""
    ildiz = os.path.dirname(os.path.dirname(sys.executable))     # ...\AzizMedLine
    yol = os.path.join(ildiz, nom, _XIZMAT_EXE.get(nom, ""))
    return yol if os.path.exists(yol) else ""


def xizmat_ishga_tushir(nom: str):
    """Xizmatni ishga tushiradi. (ok, xabar)."""
    exe = xizmat_exe(nom)
    if not exe:
        return False, ("Bu kompyuterda o'rnatilmagan.\n"
                       "O'rnatuvchini qayta ishga tushirib, kerakli komponentni belgilang.")
    import subprocess
    try:
        subprocess.Popen([exe], cwd=os.path.dirname(exe))
        return True, "Ishga tushirildi — bir necha soniyadan keyin tayyor bo'ladi."
    except Exception as e:
        return False, f"Ishga tushmadi: {e}"


def xizmat_ishlayaptimi(port: int, host: str = "127.0.0.1") -> bool:
    return _port_ochiqmi(host, port, timeout=0.6)


def tv_admin_url_saqla(url: str) -> str:
    """TV admin yorlig'i ochadigan manzil (TV_ADMIN.vbs shu fayldan o'qiydi)."""
    os.makedirs(konfig_papka(), exist_ok=True)
    yol = os.path.join(konfig_papka(), "tv_admin_url.txt")
    with open(yol, "w", encoding="utf-8") as f:
        f.write((url or "").strip())
    return yol


# ─────────────────── LAN ruxsati (boshqa kompyuterlar ulanishi) ───────────────────
def lan_ruxsat(cfg: dict):
    """
    Bu kompyuterni SERVER qilib ochadi (boshqa kabinetlardagi Vrach kabineti,
    Registratsiya va Natija oynalari shu bazaga ulanishi uchun):
      1) Windows fayrvolida MySQL portini ochadi
      2) MySQL'da root@'%' foydalanuvchisini yaratadi/yangilaydi
    Administrator huquqi kerak. (ok, xabar) qaytaradi.
    """
    import subprocess
    qadamlar = []
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        port = int(cfg.get("port", 3306) or 3306)
    except Exception:
        port = 3306

    # 1) Fayrvol
    try:
        subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule",
                        f"name=AzizMedLine MySQL ({port})", "dir=in", "action=allow",
                        "protocol=TCP", f"localport={port}"],
                       capture_output=True, creationflags=cf, timeout=20)
        qadamlar.append(f"✅ Fayrvol: {port}-port ochildi")
    except Exception as e:
        qadamlar.append(f"⚠️ Fayrvol ochilmadi ({e}) — administrator huquqi kerak")

    # 2) root@'%' grant
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host="127.0.0.1", port=port, user=cfg.get("user", "root"),
            password=cfg.get("password", ""), connection_timeout=6, use_pure=True)
        cur = conn.cursor()
        parol = cfg.get("password", "")
        cur.execute("CREATE USER IF NOT EXISTS 'root'@'%' "
                    "IDENTIFIED WITH mysql_native_password BY %s", (parol,))
        cur.execute("ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY %s", (parol,))
        cur.execute("GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION")
        cur.execute("FLUSH PRIVILEGES")
        cur.close()
        conn.close()
        qadamlar.append("✅ Baza: boshqa kompyuterlarga ruxsat berildi")
    except Exception as e:
        qadamlar.append(f"⛔ Bazaga ruxsat berilmadi: {e}")
        return False, "\n".join(qadamlar)

    iplar = ", ".join(barcha_iplar())
    qadamlar.append(f"\nBoshqa kompyuterlar shu IP ni tersin:  {iplar}")
    return True, "\n".join(qadamlar)


# ─────────────────────────── Litsenziya ───────────────────────────
def litsenziya_holati(online: bool = False) -> dict:
    """Litsenziya holati — Sozlama oynasining 'Litsenziya' bo'limi uchun."""
    natija = {"ok": False, "xabar": "Litsenziya moduli topilmadi.", "machine_id": "",
              "tarif": "", "korxona": "", "tugash": "", "qolgan": None, "fayl": ""}
    try:
        from litsenziya import litsenziya_manager as lm
        n = lm.holatni_tekshir(online=online)
        p = n.payload or {}
        natija.update(ok=n.yaroqli, xabar=n.xabar, machine_id=n.machine_id,
                      tarif=p.get("tarif", ""), korxona=p.get("korxona", ""),
                      qolgan=n.qolgan_kun, fayl=lm.faylni_top() or "")
        exp = p.get("expires_at")
        if exp:
            import datetime
            natija["tugash"] = datetime.datetime.fromtimestamp(int(exp)).strftime("%d.%m.%Y")
    except Exception as e:
        natija["xabar"] = f"Litsenziya o'qilmadi: {e}"
        try:
            from litsenziya import mashina_id as _mid
            natija["machine_id"] = _mid.mashina_id()
        except Exception:
            pass
    return natija


def litsenziya_ornat(azlic_yoli: str):
    """.azlic faylni umumiy joyga o'rnatadi (barcha dastur ko'radi). (ok, xabar)."""
    try:
        from litsenziya import litsenziya_manager as lm
        n = lm.faollashtir(azlic_yoli)
        return n.yaroqli, n.xabar
    except Exception as e:
        return False, f"O'rnatib bo'lmadi: {e}"


def litsenziya_joyi() -> str:
    try:
        from litsenziya import yollar as _y
        return _y.yoziladigan_papka()
    except Exception:
        return konfig_papka()


# ──────────────────────────── GUI ────────────────────────────
# Ranglar (barcha oynalar bilan bir xil uslub)
_BG = "#0f1422"
_KARTA = "#1a2236"
_MATN = "#e6e9f2"
_KUL = "#9aa3bd"
_YASHIL = "#1f8a4c"
_QIZIL = "#ff9a9a"
_OK = "#7ee0a0"


def sozlama_oynasi(parent=None, bolim: str = "baza") -> bool:
    """
    AzizMedLine sozlama oynasi — 3 bo'lim:
      • Baza      — ulanish (BARCHA dasturga amal qiladi)
      • Litsenziya— .azlic ni bir marta o'rnatish (barcha dastur ko'radi)
      • Xizmatlar — Vrach kabineti / TV server manzillari (IP) va sozlamasi

    `bolim` — ochilishda qaysi bo'lim ko'rinsin ("baza" | "litsenziya" | "xizmatlar").
    True qaytadi — baza sozlamasi saqlangan bo'lsa.
    """
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import webbrowser

    cfg = oqi()
    holat = {"saqlandi": False}

    oyna = tk.Toplevel(parent) if parent else tk.Tk()
    oyna.title("AzizMedLine — Sozlama")
    oyna.configure(bg=_BG)
    oyna.geometry("620x710")
    oyna.resizable(False, False)

    # ── Sarlavha ──
    bosh = tk.Frame(oyna, bg=_BG)
    bosh.pack(fill="x", padx=20, pady=(14, 6))
    tk.Label(bosh, text="🛠️  AzizMedLine sozlamasi", bg=_BG, fg=_MATN,
             font=("Segoe UI Semibold", 15)).pack(side="left")
    tk.Label(bosh, text=f"Bu kompyuter: {'  '.join(barcha_iplar())}", bg=_BG, fg=_OK,
             font=("Consolas", 10)).pack(side="right")

    # ── Bo'lim tugmalari (tab) ──
    tab_ramka = tk.Frame(oyna, bg=_BG)
    tab_ramka.pack(fill="x", padx=20)
    sahifalar = {}
    tab_tugma = {}

    def _koorsat(nom):
        for k, s in sahifalar.items():
            s.pack_forget()
            tab_tugma[k].config(bg=_KARTA, fg=_KUL)
        sahifalar[nom].pack(fill="both", expand=True, padx=20, pady=(10, 0))
        tab_tugma[nom].config(bg="#2b5cff", fg="white")
        if nom == "litsenziya":
            _lic_yangila()
        elif nom == "xizmatlar":
            _xizmat_yangila()

    for nom, matn in (("baza", "🗄️  Baza"), ("litsenziya", "🔑  Litsenziya"),
                      ("xizmatlar", "🖥️  Xizmatlar (Vrach / TV)")):
        b = tk.Button(tab_ramka, text=matn, relief="flat", bg=_KARTA, fg=_KUL,
                      font=("Segoe UI Semibold", 10), cursor="hand2",
                      command=lambda n=nom: _koorsat(n))
        b.pack(side="left", padx=(0, 4), ipady=6, ipadx=10)
        tab_tugma[nom] = b
        sahifalar[nom] = tk.Frame(oyna, bg=_BG)

    # ════════════════════ 1) BAZA ════════════════════
    s1 = sahifalar["baza"]
    tk.Label(s1, text="Bu ulanish sozlamasi TO'RTTA dasturga ham amal qiladi:\n"
                      "Registratsiya  •  Natija  •  Vrach kabineti  •  TV server",
             bg=_KARTA, fg=_KUL, font=("Segoe UI", 9), justify="center"
             ).pack(fill="x", pady=(0, 8), ipady=7)
    tk.Label(s1, text=f"Saqlanadi: {yozish_yoli()}", bg=_BG, fg=_KUL,
             font=("Segoe UI", 8)).pack()

    maydon = {}
    qatorlar = [("host", "Server IP / Host"), ("port", "Port"),
                ("user", "Foydalanuvchi"), ("password", "Parol"),
                ("database", "Baza nomi")]
    ramka = tk.Frame(s1, bg=_BG)
    ramka.pack(fill="x", pady=(8, 4))
    for i, (kalit, label) in enumerate(qatorlar):
        tk.Label(ramka, text=label, bg=_BG, fg=_KUL,
                 font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w", pady=5)
        e = tk.Entry(ramka, font=("Consolas", 11), bg=_KARTA, fg=_MATN,
                     relief="flat", width=30, show="*" if kalit == "password" else "")
        e.insert(0, str(cfg.get(kalit, "")))
        e.grid(row=i, column=1, sticky="e", pady=5, ipady=4, padx=(10, 0))
        maydon[kalit] = e
    ramka.columnconfigure(1, weight=1)

    def _yig():
        c = {k: maydon[k].get().strip() for k in maydon}
        try:
            c["port"] = int(c.get("port") or 3306)
        except ValueError:
            c["port"] = 3306
        return c

    def _hostni_qoy(v):
        maydon["host"].delete(0, "end")
        maydon["host"].insert(0, v)

    rejim = tk.Frame(s1, bg=_BG)
    rejim.pack(fill="x", pady=(6, 2))
    tk.Button(rejim, text="🖥️  Baza SHU kompyuterda", relief="flat", bg=_KARTA, fg=_MATN,
              font=("Segoe UI", 9), cursor="hand2",
              command=lambda: _hostni_qoy("127.0.0.1")
              ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)
    tk.Button(rejim, text="🌐  Baza BOSHQA kompyuterda (IP)", relief="flat", bg=_KARTA,
              fg=_MATN, font=("Segoe UI", 9), cursor="hand2",
              command=lambda: (_hostni_qoy(""), maydon["host"].focus_set())
              ).pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=5)

    def _avto_top():
        c = server_qidir_oynasi(oyna, _yig())
        if not c:
            return
        _hostni_qoy(c["host"])
        maydon["port"].delete(0, "end")
        maydon["port"].insert(0, str(c["port"]))
        natija_lbl.config(text=f"Topildi: {c['host']}:{c['port']} — tekshirilmoqda...", fg=_KUL)
        oyna.update_idletasks()
        natija_lbl.config(text=ulanish_diagnostika(_yig()) +
                          "\n\n«💾 Saqlash» ni bosing.", fg=_MATN)

    tk.Button(s1, text="🔍  Serverni tarmoqdan AVTOMATIK topish (IP terish shart emas)",
              relief="flat", bg="#2b5cff", fg="white", font=("Segoe UI Semibold", 10),
              cursor="hand2", command=_avto_top
              ).pack(fill="x", pady=(4, 0), ipady=6)

    natija_lbl = tk.Label(s1, text="", bg=_BG, fg=_KUL, font=("Segoe UI", 9),
                          wraplength=560, justify="left")
    natija_lbl.pack(pady=(8, 4), fill="x")

    def _test():
        natija_lbl.config(text="Tekshirilmoqda...", fg=_KUL)
        oyna.update_idletasks()
        natija_lbl.config(text=ulanish_diagnostika(_yig()), fg=_MATN)

    def _saqla():
        c = _yig()
        ok, msg = test_ulanish(c)
        if not ok and not messagebox.askyesno("Ulanmadi", f"{msg}\n\nBaribir saqlansinmi?"):
            return
        yol = saqla(c)
        holat["saqlandi"] = True
        messagebox.showinfo("Saqlandi",
                            f"Sozlama saqlandi:\n{yol}\n\n"
                            "Registratsiya, Natija, Vrach kabineti va TV server\n"
                            "endi shu bazaga ulanadi (ular qayta ishga tushirilsin).")

    def _lokal_mysql():
        ok, msg = lokal_mysql_ishga_tushir()
        natija_lbl.config(text=msg, fg=_OK if ok else _QIZIL)

    def _lan():
        if not messagebox.askyesno(
                "Boshqa kompyuterlarga ruxsat",
                "Bu kompyuter SERVER bo'ladi:\n"
                "• fayrvolda MySQL porti ochiladi\n"
                "• bazaga tarmoqdan ulanish yoqiladi\n\n"
                "Davom etilsinmi?"):
            return
        ok, msg = lan_ruxsat(_yig())
        natija_lbl.config(text=msg, fg=_OK if ok else _QIZIL)

    tugma = tk.Frame(s1, bg=_BG)
    tugma.pack(fill="x", pady=(4, 6))
    tk.Button(tugma, text="🔌 Tekshirish", command=_test, bg="#2a3350", fg=_MATN,
              relief="flat", font=("Segoe UI", 10), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=6)
    tk.Button(tugma, text="💾 Saqlash", command=_saqla, bg=_YASHIL, fg="white",
              relief="flat", font=("Segoe UI Semibold", 10), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=6)

    qosh = tk.Frame(s1, bg=_BG)
    qosh.pack(fill="x")
    tk.Button(qosh, text="🔧 Lokal MySQL'ni ishga tushirish", command=_lokal_mysql,
              bg=_KARTA, fg=_KUL, relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)
    tk.Button(qosh, text="🔓 Boshqa kompyuterlarga ruxsat (server)", command=_lan,
              bg=_KARTA, fg=_KUL, relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=5)

    # ════════════════════ 2) LITSENZIYA ════════════════════
    s2 = sahifalar["litsenziya"]
    tk.Label(s2, text="Litsenziya BIR MARTA o'rnatiladi — o'rnatmadagi barcha dastur\n"
                      "(Registratsiya, Natija, Vrach kabineti, TV server) shu fayldan foydalanadi.",
             bg=_KARTA, fg=_KUL, font=("Segoe UI", 9), justify="center"
             ).pack(fill="x", pady=(0, 10), ipady=7)

    lic_holat = tk.Label(s2, text="Tekshirilmoqda...", bg=_BG, fg=_KUL,
                         font=("Segoe UI Semibold", 11), wraplength=560, justify="center")
    lic_holat.pack(pady=(4, 2))
    lic_izoh = tk.Label(s2, text="", bg=_BG, fg=_KUL, font=("Segoe UI", 9),
                        wraplength=560, justify="center")
    lic_izoh.pack(pady=(0, 10))

    id_ramka = tk.Frame(s2, bg=_KARTA)
    id_ramka.pack(fill="x", pady=4)
    tk.Label(id_ramka, text="Ushbu kompyuter ID raqami (litsenziya shu ID ga beriladi):",
             bg=_KARTA, fg=_KUL, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(10, 0))
    id_var = tk.StringVar(value="")
    id_box = tk.Entry(id_ramka, textvariable=id_var, font=("Consolas", 13), justify="center",
                      bg=_BG, fg=_OK, relief="flat", readonlybackground=_BG)
    id_box.configure(state="readonly")
    id_box.pack(fill="x", padx=12, pady=(2, 10), ipady=6)

    def _id_nusxa():
        oyna.clipboard_clear()
        oyna.clipboard_append(id_var.get())
        messagebox.showinfo("Nusxalandi",
                            "Machine ID nusxalandi.\nShu ID ni administratorga yuboring:\n"
                            "+998 99 673 13 42  |  @Aziz996731342")

    def _lic_yangila(online=False):
        h = litsenziya_holati(online=online)
        id_var.set(h["machine_id"])
        if h["ok"]:
            qolgan = f" • {h['qolgan']} kun qoldi" if h.get("qolgan") is not None else ""
            lic_holat.config(text=f"✅ Litsenziya faol{qolgan}", fg=_OK)
            lic_izoh.config(
                text=f"{h['korxona'] or ''}   tarif: {h['tarif'] or '—'}   "
                     f"tugash sanasi: {h['tugash'] or '—'}\nFayl: {h['fayl'] or '—'}")
        else:
            lic_holat.config(text=f"⛔ {h['xabar']}", fg=_QIZIL)
            lic_izoh.config(text=f"Litsenziya o'rnatiladigan joy: {litsenziya_joyi()}")

    def _lic_tanla():
        yol = filedialog.askopenfilename(
            title="Litsenziya faylini tanlang",
            filetypes=[("Litsenziya", "*.azlic"), ("Barcha fayllar", "*.*")])
        if not yol:
            return
        ok, msg = litsenziya_ornat(yol)
        _lic_yangila()
        if ok:
            messagebox.showinfo("Tayyor",
                                f"Litsenziya o'rnatildi!\n{msg}\n\n"
                                "Endi Registratsiya, Natija, Vrach kabineti va TV server\n"
                                "ochiladi (ishlab turganlari qayta ishga tushirilsin).")
        else:
            messagebox.showerror("Xato", msg)

    tk.Button(s2, text="📋 ID ni nusxalash", command=_id_nusxa, bg="#2b5cff", fg="white",
              relief="flat", font=("Segoe UI Semibold", 10), cursor="hand2"
              ).pack(fill="x", pady=(8, 4), ipady=7)
    tk.Button(s2, text="📂 Litsenziya faylini o'rnatish (.azlic)", command=_lic_tanla,
              bg=_YASHIL, fg="white", relief="flat", font=("Segoe UI Semibold", 10),
              cursor="hand2").pack(fill="x", pady=4, ipady=7)
    tk.Button(s2, text="↻ Holatni yangilash (onlayn tekshirish)",
              command=lambda: _lic_yangila(online=True), bg=_KARTA, fg=_KUL,
              relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(fill="x", pady=4, ipady=5)
    tk.Label(s2, text="Litsenziya olish uchun:  +998 99 673 13 42   |   @Aziz996731342",
             bg=_BG, fg=_KUL, font=("Segoe UI", 9)).pack(pady=(10, 0))

    # ════════════════════ 3) XIZMATLAR ════════════════════
    s3 = sahifalar["xizmatlar"]
    vcfg = vrach_config_oqi()
    ip_asosiy = barcha_iplar()[0]

    tk.Label(s3, text="Vrach kabineti va TV server — brauzerda ochiladigan dasturlar.\n"
                      "Boshqa kabinetdagi kompyuter/telefon/TV quyidagi manzillarni teradi.",
             bg=_KARTA, fg=_KUL, font=("Segoe UI", 9), justify="center"
             ).pack(fill="x", pady=(0, 8), ipady=7)

    # ─ Vrach kabineti ─
    # DIQQAT: LabelFrame sarlavhasida emoji ISHLATMANG — Windows Tk uni
    # kvadratcha qilib chizadi (ayniqsa 👨‍⚕️ kabi ZWJ birikmalarni).
    vk = tk.LabelFrame(s3, text="  Vrach kabineti  ", bg=_BG, fg=_MATN,
                       font=("Segoe UI Semibold", 10), bd=1, relief="groove")
    vk.pack(fill="x", pady=(2, 8), ipady=4)

    v_holat = tk.Label(vk, text="", bg=_BG, fg=_KUL, font=("Segoe UI", 9))
    v_holat.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))

    tk.Label(vk, text="Port", bg=_BG, fg=_KUL, font=("Segoe UI", 9)
             ).grid(row=1, column=0, sticky="w", padx=10, pady=3)
    v_port = tk.Entry(vk, font=("Consolas", 10), bg=_KARTA, fg=_MATN, relief="flat", width=10)
    v_port.insert(0, str(vcfg.get("port", VRACH_PORT)))
    v_port.grid(row=1, column=1, sticky="w", pady=3, ipady=3)

    v_lan = tk.BooleanVar(value=str(vcfg.get("host_bind", "127.0.0.1")) not in
                          ("127.0.0.1", "localhost"))
    tk.Checkbutton(vk, text="Tarmoqdan ham ochilsin (boshqa kompyuter/telefon)",
                   variable=v_lan, bg=_BG, fg=_KUL, selectcolor=_KARTA,
                   activebackground=_BG, activeforeground=_MATN, font=("Segoe UI", 9)
                   ).grid(row=1, column=2, sticky="w", padx=(10, 0))

    tk.Label(vk, text="TV server manzili", bg=_BG, fg=_KUL, font=("Segoe UI", 9)
             ).grid(row=2, column=0, sticky="w", padx=10, pady=3)
    v_tv = tk.Entry(vk, font=("Consolas", 10), bg=_KARTA, fg=_MATN, relief="flat", width=34)
    v_tv.insert(0, str(vcfg.get("tv_server_url", f"http://127.0.0.1:{TV_PORT}")))
    v_tv.grid(row=2, column=1, columnspan=2, sticky="we", padx=(0, 10), pady=3, ipady=3)

    tk.Label(vk, text="Xona nomi", bg=_BG, fg=_KUL, font=("Segoe UI", 9)
             ).grid(row=3, column=0, sticky="w", padx=10, pady=3)
    v_xona = tk.Entry(vk, font=("Segoe UI", 10), bg=_KARTA, fg=_MATN, relief="flat", width=34)
    v_xona.insert(0, str(vcfg.get("xona", "kabinet")))
    v_xona.grid(row=3, column=1, columnspan=2, sticky="we", padx=(0, 10), pady=3, ipady=3)

    v_manzil = tk.Label(vk, text="", bg=_BG, fg=_OK, font=("Consolas", 10))
    v_manzil.grid(row=4, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
    vk.columnconfigure(2, weight=1)

    def _vrach_port():
        try:
            return int(v_port.get().strip() or VRACH_PORT)
        except ValueError:
            return VRACH_PORT

    def _vrach_saqla():
        yol = vrach_config_saqla({
            "port": _vrach_port(),
            "host_bind": "0.0.0.0" if v_lan.get() else "127.0.0.1",
            "tv_server_url": v_tv.get().strip() or f"http://127.0.0.1:{TV_PORT}",
            "xona": v_xona.get().strip() or "kabinet",
        })
        messagebox.showinfo("Saqlandi",
                            f"Vrach kabineti sozlamasi saqlandi:\n{yol}\n\n"
                            "Vrach kabineti qayta ishga tushirilsin.")
        _xizmat_yangila()

    v_tugma = tk.Frame(vk, bg=_BG)
    v_tugma.grid(row=5, column=0, columnspan=3, sticky="we", padx=10, pady=(2, 8))
    tk.Button(v_tugma, text="💾 Saqlash", command=_vrach_saqla, bg=_YASHIL, fg="white",
              relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(0, 3), ipady=5)
    tk.Button(v_tugma, text="▶ Ishga tushirish",
              command=lambda: _xizmat_boshla("VrachKabineti"), bg=_KARTA, fg=_MATN,
              relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=3, ipady=5)
    tk.Button(v_tugma, text="🌐 Brauzerda ochish",
              command=lambda: webbrowser.open(f"http://127.0.0.1:{_vrach_port()}"),
              bg=_KARTA, fg=_MATN, relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(3, 0), ipady=5)

    # ─ TV server ─
    tvf = tk.LabelFrame(s3, text="  AzizMed TV server  ", bg=_BG, fg=_MATN,
                        font=("Segoe UI Semibold", 10), bd=1, relief="groove")
    tvf.pack(fill="x", pady=(2, 6), ipady=4)

    t_holat = tk.Label(tvf, text="", bg=_BG, fg=_KUL, font=("Segoe UI", 9))
    t_holat.pack(anchor="w", padx=10, pady=(6, 2))
    t_manzil = tk.Label(tvf, text="", bg=_BG, fg=_OK, font=("Consolas", 10), justify="left")
    t_manzil.pack(anchor="w", padx=10, pady=(0, 4))

    def _tv_admin_och():
        url = f"http://127.0.0.1:{TV_PORT}/admin"
        if not xizmat_ishlayaptimi(TV_PORT):
            ok, msg = xizmat_ishga_tushir("TVServer")
            if not ok:
                messagebox.showerror("TV server", msg)
                return
            import time
            for _ in range(20):
                time.sleep(0.7)
                oyna.update()
                if xizmat_ishlayaptimi(TV_PORT):
                    break
        webbrowser.open(url)
        _xizmat_yangila()

    t_tugma = tk.Frame(tvf, bg=_BG)
    t_tugma.pack(fill="x", padx=10, pady=(2, 8))
    tk.Button(t_tugma, text="▶ Ishga tushirish",
              command=lambda: _xizmat_boshla("TVServer"), bg=_KARTA, fg=_MATN,
              relief="flat", font=("Segoe UI", 9), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(0, 3), ipady=5)
    tk.Button(t_tugma, text="🖥️ TV admin panelini ochish", command=_tv_admin_och,
              bg=_YASHIL, fg="white", relief="flat", font=("Segoe UI Semibold", 9),
              cursor="hand2").pack(side="left", expand=True, fill="x", padx=(3, 0), ipady=5)

    def _xizmat_boshla(nom):
        ok, msg = xizmat_ishga_tushir(nom)
        (messagebox.showinfo if ok else messagebox.showerror)("Xizmat", msg)
        oyna.after(2500, _xizmat_yangila)

    def _xizmat_yangila():
        ip = barcha_iplar()[0]
        vp = _vrach_port()
        v_ish = xizmat_ishlayaptimi(vp)
        v_holat.config(text=("● Ishlab turibdi" if v_ish else "○ Ishlamayapti"),
                       fg=_OK if v_ish else _KUL)
        v_manzil.config(text=f"Shu kompyuterda:  http://127.0.0.1:{vp}\n"
                             f"Boshqa kabinetdan: http://{ip}:{vp}"
                             + ("" if v_lan.get() else "   ← 'Tarmoqdan ham ochilsin' yoqilsin"))
        t_ish = xizmat_ishlayaptimi(TV_PORT)
        t_holat.config(text=("● Ishlab turibdi" if t_ish else "○ Ishlamayapti"),
                       fg=_OK if t_ish else _KUL)
        t_manzil.config(text=f"TV admin paneli:   http://{ip}:{TV_PORT}/admin\n"
                             f"TV pristavka (APK): http://{ip}:{TV_PORT}\n"
                             f"Telefon boshqaruvi: http://{ip}:{TV_PORT}")
        try:
            tv_admin_url_saqla(f"http://127.0.0.1:{TV_PORT}/admin")
        except Exception:
            pass

    # ── Yopish ──
    tk.Button(oyna, text="✖ Yopish", command=lambda: oyna.destroy(), bg=_KARTA, fg=_KUL,
              relief="flat", font=("Segoe UI", 10), cursor="hand2"
              ).pack(side="bottom", fill="x", padx=20, pady=12, ipady=6)

    _koorsat(bolim if bolim in sahifalar else "baza")

    if parent:
        oyna.transient(parent)
        oyna.grab_set()
        oyna.wait_window()
    else:
        oyna.mainloop()
    return holat["saqlandi"]


if __name__ == "__main__":
    import sys as _s
    _b = "baza"
    if "--litsenziya" in _s.argv:
        _b = "litsenziya"
    elif "--xizmatlar" in _s.argv:
        _b = "xizmatlar"
    sozlama_oynasi(bolim=_b)
