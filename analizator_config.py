# -*- coding: utf-8 -*-
"""
Analizator sozlamalari — frozen-aware (manba va EXE da bir xil).

Sozlamalar `%ProgramData%\\AzizMedLine\\analizator.json` da saqlanadi — barcha
nusxalar (registratsiya/natija) bir joydan o'qiydi, EXE qayerda bo'lishidan qat'i nazar.

Mijozda analizatorlar farq qilishi mumkin (IP, port, COM) → shu yerdan sozlanadi.
"""

import os
import json

DEFAULT = {
    # BC-20S (gemotologiya, Mindray) — TCP
    "bc20s_yoq": True,
    "bc20s_ip": "192.168.0.2",
    "bc20s_port": 5100,
    # BK-280 (bioximiya) — LIS server (port orqali txt qabul qiladi)
    "bk280_yoq": True,
    "bk280_port": 8087,
    # URIT-50 (siydik) — COM port (serial)
    "urit_yoq": True,
    "urit_com": "COM4",
    "urit_strip": 14,
}


def konfig_papka() -> str:
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    return os.path.join(pd, "AzizMedLine")


def _yol() -> str:
    return os.path.join(konfig_papka(), "analizator.json")


def oqi() -> dict:
    cfg = dict(DEFAULT)
    try:
        with open(_yol(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    return cfg


def saqla(yangi: dict) -> str:
    os.makedirs(konfig_papka(), exist_ok=True)
    cfg = oqi()
    cfg.update(yangi or {})
    with open(_yol(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return _yol()


def get(key, default=None):
    return oqi().get(key, DEFAULT.get(key, default))
