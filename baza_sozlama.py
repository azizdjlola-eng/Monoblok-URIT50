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
        )
        conn.close()
        return True, "Ulanish muvaffaqiyatli ✅"
    except Exception as e:
        return False, f"Ulanmadi: {e}"


# ──────────────────────────── GUI ────────────────────────────
def sozlama_oynasi(parent=None) -> bool:
    import tkinter as tk
    from tkinter import messagebox

    cfg = oqi()
    holat = {"saqlandi": False}

    oyna = tk.Toplevel(parent) if parent else tk.Tk()
    oyna.title("AzizMedLine — Baza Sozlamasi")
    oyna.configure(bg="#0f1422")
    oyna.geometry("440x420")
    oyna.resizable(False, False)

    tk.Label(oyna, text="🗄️ Baza ulanish sozlamasi", bg="#0f1422", fg="#e6e9f2",
             font=("Segoe UI Semibold", 14)).pack(pady=(18, 2))
    tk.Label(oyna, text=f"Saqlanadi: {yozish_yoli()}", bg="#0f1422", fg="#9aa3bd",
             font=("Segoe UI", 8)).pack()

    maydon = {}
    qatorlar = [("host", "Server IP / Host"), ("port", "Port"),
                ("user", "Foydalanuvchi"), ("password", "Parol"),
                ("database", "Baza nomi")]
    ramka = tk.Frame(oyna, bg="#0f1422")
    ramka.pack(fill="x", padx=24, pady=10)
    for i, (kalit, label) in enumerate(qatorlar):
        tk.Label(ramka, text=label, bg="#0f1422", fg="#9aa3bd",
                 font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w", pady=6)
        e = tk.Entry(ramka, font=("Consolas", 11), bg="#1a2236", fg="#e6e9f2",
                     relief="flat", width=26, show="*" if kalit == "password" else "")
        e.insert(0, str(cfg.get(kalit, "")))
        e.grid(row=i, column=1, sticky="e", pady=6, ipady=4, padx=(10, 0))
        maydon[kalit] = e
    ramka.columnconfigure(1, weight=1)

    natija_lbl = tk.Label(oyna, text="", bg="#0f1422", fg="#9aa3bd",
                          font=("Segoe UI", 9), wraplength=400, justify="center")
    natija_lbl.pack(pady=(4, 6))

    def _yig():
        c = {k: maydon[k].get().strip() for k in maydon}
        try:
            c["port"] = int(c.get("port") or 3306)
        except ValueError:
            c["port"] = 3306
        return c

    def _test():
        ok, msg = test_ulanish(_yig())
        natija_lbl.config(text=msg, fg="#7ee0a0" if ok else "#ff9a9a")

    def _saqla():
        c = _yig()
        ok, msg = test_ulanish(c)
        if not ok and not messagebox.askyesno(
                "Ulanmadi", f"{msg}\n\nBaribir saqlansinmi?"):
            return
        yol = saqla(c)
        holat["saqlandi"] = True
        messagebox.showinfo("Saqlandi", f"Sozlama saqlandi:\n{yol}")
        oyna.destroy()

    tugma = tk.Frame(oyna, bg="#0f1422")
    tugma.pack(fill="x", padx=24, pady=10)
    tk.Button(tugma, text="🔌 Tekshirish", command=_test, bg="#2a3350", fg="#e6e9f2",
              relief="flat", font=("Segoe UI", 10), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=6)
    tk.Button(tugma, text="💾 Saqlash", command=_saqla, bg="#1f8a4c", fg="white",
              relief="flat", font=("Segoe UI Semibold", 10), cursor="hand2"
              ).pack(side="left", expand=True, fill="x", padx=(4, 0), ipady=6)

    if parent:
        oyna.transient(parent)
        oyna.grab_set()
        oyna.wait_window()
    else:
        oyna.mainloop()
    return holat["saqlandi"]


if __name__ == "__main__":
    sozlama_oynasi()
