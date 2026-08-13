"""
Markaziy konfiguratsiya moduli.

Bu modul barcha dasturlar (monoblok_dastur, bc20s_listener, bk280_listener,
COM4 siydik skripti, hematology/biochemistry/urine oynalar) tomonidan
import qilinadi. Shu sababli u butun tizimning YAGONA sozlama manbasidir.

Sozlamalar `analizator_config.json` faylida saqlanadi (exe/skript yonida).
Agar fayl mavjud bo'lmasa — standart qiymatlar bilan avtomatik yaratiladi.

Shu tariqa dastur exe qilib mijozga berilganda, ulanish sozlamalari
(IP, port, COM port, baza manzili va h.k.) kodga tegmasdan, dastur
ichidagi "Tizim Sozlamalari" oynasidan o'zgartiriladi.

ESLATMA: Eski kod `from monoblok_db_config import DB_CONFIG` ko'rinishida
ishlatadi — bu backward-compatibility uchun saqlangan.
"""

import os
import sys
import json


# ---------------------------------------------------------------------------
# Config fayl joyi (exe yonida yoki skript papkasida)
# ---------------------------------------------------------------------------
def _base_dir() -> str:
    """Config fayli saqlanadigan papka (exe yoki skript yonida)."""
    if getattr(sys, "frozen", False):
        # PyInstaller bilan exe qilinganda — exe yonida
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_base_dir(), "analizator_config.json")


# ---------------------------------------------------------------------------
# STANDART SOZLAMALAR (JSON yo'q bo'lsa shu ishlatiladi)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    # MySQL baza ulanishi
    "database": {
        "host": "192.168.0.40",
        "user": "lims",
        "password": "azizmed2026",
        "database": "lab_tizim",
        "port": 3306,
    },

    # Siydik analizatori — URIT-50 (Serial / COM port)
    "siydik": {
        "enabled": True,
        "name": "URIT-50 (Siydik)",
        "connection_type": "serial",   # serial
        "com_port": "COM4",
        "baudrate": 9600,
        "bytesize": 8,                 # 5,6,7,8
        "parity": "N",                 # N=None, E=Even, O=Odd
        "stopbits": 1,                 # 1, 2
        "timeout": 1,                  # soniya
        "encoding": "utf-8",
    },

    # Gemotologiya analizatori — BC-20S (TCP CLIENT — dastur analizatorga ulanadi)
    "gemotologiya": {
        "enabled": True,
        "name": "BC-20S (Gemotologiya)",
        "connection_type": "tcp_client",   # tcp_client
        "ip": "192.168.0.2",
        "port": 5100,
        "reconnect_interval": 5,           # uzilganda qayta ulanish (sek)
        "encoding": "utf-8",
    },

    # Bioximiya analizatori — BK-280 (TCP SERVER — analizator dasturga ulanadi)
    "bioximiya": {
        "enabled": True,
        "name": "BK-280 (Bioximiya)",
        "connection_type": "tcp_server",   # tcp_server
        "ip": "0.0.0.0",                   # 0.0.0.0 = barcha tarmoq interfeyslari
        "port": 8087,                      # HL7 natijalar porti
        "lis_port": 8088,                  # LIS so'rov (barcode -> bemor) porti
        "encoding": "utf-8",
    },

    # Pechat (chop etish) sozlamalari
    "printer": {
        # Natija blankasi AVTO-pechati uchun printer nomi.
        # "" (bo'sh) = Windows'ning standart (asosiy) printeri ishlatiladi.
        # Aniq nom yozilsa (masalan "\\LABSERVER\EPSON L8050 kassa") —
        # natija blankalari doim shu printerdan chiqadi.
        "blanka_printer": "",
    },
}


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------
def _deep_merge(default: dict, loaded: dict) -> dict:
    """default ustiga loaded qiymatlarni qo'yadi (ichma-ich dict larni ham)."""
    result = {}
    for key, dval in default.items():
        if isinstance(dval, dict):
            lval = loaded.get(key, {})
            result[key] = _deep_merge(dval, lval if isinstance(lval, dict) else {})
        else:
            result[key] = loaded.get(key, dval)
    # default da yo'q, lekin loaded da bor kalitlarni ham saqlaymiz
    for key, lval in loaded.items():
        if key not in result:
            result[key] = lval
    return result


def _umumiy_db():
    """
    LIMS ning UMUMIY baza sozlamasi (%ProgramData%\\AzizMedLine\\db_config.txt).
    Uni "Baza Sozlamasi" oynasi yozadi va Registratsiya, Vrach kabineti, TV
    server ham SHU fayldan o'qiydi.

    Faqat BIRINCHI ishga tushishda (analizator_config.json hali yo'q paytda)
    ishlatiladi — yangi kompyuterda texnik xodim bazani bir joyda sozlasa,
    Natija oynasi ham o'sha bazaga ulanadi. Mavjud o'rnatmalarda esa
    analizator_config.json o'zgarishsiz qoladi (bu yerdagi sozlama ustun).
    """
    try:
        import baza_sozlama as _bs
        c = _bs.oqi()
        if isinstance(c, dict) and c.get("host"):
            return {"host": c["host"], "user": c.get("user", "root"),
                    "password": c.get("password", ""),
                    "database": c.get("database", "lab_tizim"),
                    "port": int(c.get("port", 3306) or 3306)}
    except Exception as e:
        print(f"[ma'lumot] umumiy db_config o'qilmadi: {e}")
    return None


def load_config() -> dict:
    """analizator_config.json ni o'qiydi. Yo'q bo'lsa — yaratadi."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # chuqur nusxa
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg = _deep_merge(DEFAULT_CONFIG, loaded)
        except Exception as e:
            print(f"[OGOHLANTIRISH] analizator_config.json yuklashda xato: {e}")
    else:
        # Birinchi marta — umumiy LIMS sozlamasidan baza ulanishini olamiz
        # (bo'lmasa standart qiymatlar), so'ng faylni yaratamiz.
        umumiy = _umumiy_db()
        if umumiy:
            cfg["database"] = umumiy
            print(f"[baza] Umumiy sozlamadan olindi: {umumiy['host']}:{umumiy['port']}")
        save_config(cfg)
    return cfg


def save_config(cfg: dict) -> bool:
    """Sozlamalarni analizator_config.json ga yozadi."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        # Joriy jarayondagi DB_CONFIG ni ham yangilaymiz (in-place — barcha
        # `from ... import DB_CONFIG` qilganlar shu obyektga bog'langan).
        # DB_CONFIG modul oxirida aniqlanadi; ilk import paytida hali yo'q.
        db = cfg.get("database", {})
        if isinstance(db, dict) and db and "DB_CONFIG" in globals():
            DB_CONFIG.clear()
            DB_CONFIG.update({
                "host": db.get("host", DEFAULT_CONFIG["database"]["host"]),
                "user": db.get("user", DEFAULT_CONFIG["database"]["user"]),
                "password": db.get("password", DEFAULT_CONFIG["database"]["password"]),
                "database": db.get("database", DEFAULT_CONFIG["database"]["database"]),
                "port": int(db.get("port", DEFAULT_CONFIG["database"]["port"])),
                # C-extension (_mysql_connector.pyd) "Failed raising error" beradi —
                # barcha mysql.connector consumer'lari pure-Python ishlatsin.
                "use_pure": True,
            })
        return True
    except Exception as e:
        print(f"[XATO] analizator_config.json saqlashda xato: {e}")
        return False


def get_analyzer(name: str) -> dict:
    """Bitta analizator sozlamasini qaytaradi (siydik / gemotologiya / bioximiya)."""
    return load_config().get(name, json.loads(json.dumps(DEFAULT_CONFIG.get(name, {}))))


# ---------------------------------------------------------------------------
# Modul yuklanganda — config o'qiladi
# ---------------------------------------------------------------------------
CONFIG = load_config()

# Backward-compatible: eski kodlar `from monoblok_db_config import DB_CONFIG`
# ko'rinishida ishlatadi. Bu dict — yagona obyekt sifatida saqlanadi.
_db = CONFIG.get("database", DEFAULT_CONFIG["database"])
DB_CONFIG = {
    "host": _db.get("host", "192.168.0.40"),
    "user": _db.get("user", "lims"),
    "password": _db.get("password", "azizmed2026"),
    "database": _db.get("database", "lab_tizim"),
    "port": int(_db.get("port", 3306)),
    # C-extension (_mysql_connector.pyd) "Failed raising error" beradi — barcha
    # mysql.connector consumer'lari (analizator listenerlar ham) pure-Python ishlatsin.
    # pymysql modullari (bk280, asus_lis_server) o'z config'ini aniq kalitlar bilan
    # quradi, shuning uchun bu kalitni olmaydi — ular buzilmaydi.
    "use_pure": True,
}
