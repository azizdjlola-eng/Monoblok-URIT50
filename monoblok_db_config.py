import os

def load_db_config():
    cfg = {
        "host": "127.0.0.1",
        "user": "root",
        "password": "azizmed2026",
        "database": "lab_tizim",
        "port": 3306
    }
    try:
        from baza_sozlama import oqish_yoli as _db_yoli
        config_file = _db_yoli()
    except Exception:
        config_file = os.path.join(os.path.dirname(__file__), "db_config.txt")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    if key == "HOST":   cfg["host"] = value
                    elif key == "USER": cfg["user"] = value
                    elif key == "PASS": cfg["password"] = value
                    elif key == "DB":   cfg["database"] = value
                    elif key == "PORT": cfg["port"] = int(value)
        except Exception as e:
            print(f"Config yuklashda xato: {e}")
    return cfg

DB_CONFIG = load_db_config()