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
        return {"ssl_disabled": True}
    host = str(cfg.get("host", "") or cfg.get("HOST", "") or "").strip().lower()
    if host in ("127.0.0.1", "localhost", "::1", ""):
        return {"ssl_disabled": True}
    return {"ssl_disabled": True} if ichki_tarmoqmi(host) else {}


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


_MYSQL_SERVICE = "AzizMedLineMySQL"


def _port_ochiqmi(host: str, port: int, timeout: float = 2.0) -> bool:
    """TCP port ochiq (kimdir tinglayaptimi) — MySQL tirikligini bilish uchun."""
    import socket
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _sc_holat() -> str:
    """AzizMedLineMySQL xizmati holati: 'yoq' | 'running' | 'stopped'.
    (sc query STATE 'RUNNING'/'STOPPED' — til-mustaqil kalitlar; returncode 1060=yo'q.)"""
    import subprocess
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(["sc", "query", _MYSQL_SERVICE],
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


def lokal_mysql_ishga_tushir():
    """
    Lokal AzizMedLineMySQL Windows xizmatini ishga tushirishga urinadi.
    (ok, xabar). Admin huquqi kerak bo'lishi mumkin.
    """
    import subprocess
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    holat = _sc_holat()
    if holat == "yoq":
        return False, ("MySQL xizmati bu kompyuterda o'rnatilmagan.\n"
                       "FULL o'rnatish (MySQL bilan) yoki BazaUstasi orqali bazani sozlang.")
    if holat == "running":
        return True, "MySQL allaqachon ishlayapti."
    # stopped — ishga tushiramiz
    try:
        subprocess.run(["net", "start", _MYSQL_SERVICE],
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
    return (f"⚠️ Server javob beryapti, lekin ulanmadi:\n{msg}\n\n"
            "Odatda foydalanuvchi/parol yoki ruxsat (grant) noto'g'ri.")


def test_ulanish(cfg: dict):
    """(ok, xabar) qaytaradi."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=cfg["host"], user=cfg["user"], password=cfg["password"],
            database=cfg["database"], port=int(cfg["port"]), connection_timeout=5,
            use_pure=True,   # C-extension "Failed raising error" nosozligidan saqlanish
        )
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
    oyna.geometry("620x660")
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
