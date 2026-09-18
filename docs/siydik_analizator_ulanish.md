# Siydik analizatorini ulash — universal sozlama

Dastur endi faqat URIT-50 ga emas, har qanday siydik (strip) analizatoriga ulanadi.
Kod o'zgarmaydi — **⚙ Tizim Sozlamalari → 🟡 Siydik** oynasida model tanlanadi.

Modul: `siydik_protokol.py` (transport + parser), xizmat: `urit50_service.py`,
RAW ko'rish oynasi: `urine_window.py`. Uchalasi bitta kanonik lug'at bilan ishlaydi:
`NO, ID, DATE, TIME, LEU, KET, NIT, URO, BIL, PRO, GLU, SG, pH, BLD, Vc, MA, Ca, CR, ACR, ABNORMAL`.

## Sozlama maydonlari (`analizator_config.json` → `siydik`)

| Kalit | Ma'nosi |
|---|---|
| `model` | Profil kaliti (`siydik_protokol.PROFILES`): `urit50`, `dirui_h`, `dirui_hl7`, `mindray_ua66`, `mindray_ua_hl7`, `urit_hl7`, `uriscan`, `combilyzer`, `astm_generic`, `hl7_generic`, `text_generic` |
| `connection_type` | `serial` (COM), `tcp_server` (analizator bizga ulanadi), `tcp_client` (biz analizatorga ulanamiz) |
| `protocol` | `auto` (tavsiya), `text` (STX…ETX printer matni), `hl7` (ORU^R01, MLLP), `astm` (E1394/E1381) |
| `com_port, baudrate, bytesize, parity, stopbits, timeout` | serial parametrlar |
| `ip, port, reconnect_interval` | TCP parametrlar |
| `idle_timeout` | ETX yubormaydigan analizator uchun: shuncha soniya jimlikdan keyin blok yopiladi (3 s) |

Model tanlanganda profil standartlari (ulanish turi, protokol, baud, port) avtomatik to'ldiriladi.

## Analizatorlar bo'yicha ko'rsatma

### URIT-50 / URIT-30 (hozirgi)
RS-232, 9600 8N1. Analizatorda **RS232** tugmasi → STX … ETX matn bloki:
`ID:…`, `NO.000009 2000-01-01`, vaqt qatori, so'ng ` LEU -  0 CELL/uL` qatorlari, `*` = patologiya.
Manba: `Urit/RAW_LOGS` dagi 3000+ real fayl (regressiya testi 100% mos).

### Dirui H-100 / H-300 / H-50
RS-232 9600 (yoki 1200) 8N1, qo'l berish yo'q. Analizatorda: **Setup → PC Port = ON, Baud Rate = 9600**.
Format (User Manual, Appendix B "Interface for Communicating with Computer"):
```
STX CR LF
 Date:YYYY-MM-DD HH:MM
 No. xxxx
 ID：xxxxxxxxxxxx          ← faqat barcode o'quvchi ON bo'lsa (to'liq kenglikdagi "："!)
 UBG …  BIL …  KET …  CRE …  BLD …  PRO …  ALB …  NIT …  LEU …  GLU …  SG …  PH …  VC …  Ca …  A:C …  RT …
ETX
```
Kod moslashuvi: `UBG→URO`, `CRE→CR`, `ALB→MA`, `A:C→ACR`, `VC→Vc`, `PH→pH`. `RT` noma'lum → logda `EXTRA`.
Dirui SP1 = `0xAB` ajratuvchi bayt — kodirovkada buzilmasligi uchun bo'sh joyga almashtiriladi.
Qiymatlar `neg / 1+ / 2+ / trace` → URIT uslubiga (`- / +1 / +2 / +-`) normallashadi (blanka/mikroskopiya mantiqi shu shaklga moslangan).

### Dirui H-500 / H-800 / FUS-series
LIS: HL7 (TCP). Analizator **LIS sozlamasi → HL7, Server IP = kompyuter IP, Port = 5200** (yoki sozlamadagi).
Dasturda: `tcp_server`, `hl7`. OBX-3 kodlari alias jadvali orqali moslanadi, OBX-8 flag (`A/H/L`) → `ABNORMAL`.
Sample ID: OBR-3 → SPM-2 → PID-3 tartibida.

### Mindray UA-66
RS-232, 11 parametr (URO BIL KET BLD PRO NIT LEU GLU SG VC PH), printer-uslubidagi matn.
Profil: `mindray_ua66` (serial, text, 9600 8N1). Aniq bayt tartibi rasmiy hujjatdan tekshirilmagan
(manualslib bot-tekshiruvi ochilmadi) — parser qator boshidagi kodni tanib oladi, shuning uchun
qatorlar tartibi/bo'sh joylar farq qilsa ham ishlaydi. Birinchi ulashda `Urit/RAW_LOGS` dagi RAW faylni
ko'rib, `EXTRA` da noma'lum kod chiqsa `CODE_ALIASES` ga qo'shish kifoya.

### Mindray UA-600 / UA-1600 / UA-5600
HL7 (MLLP, TCP) — BC-20S kabi. Profil `mindray_ua_hl7`, `tcp_server`, port 5200.
Analizator: **Setup → Communication → LIS: protocol HL7, IP = kompyuter, Port = 5200**.

### Boshqalar (Uriscan, Combilyzer/Urilyzer/DocUReader, Sysmex, Roche, Erba …)
- Matn chiqaradigan bo'lsa → `text_generic` (yoki mos profil).
- ASTM (LIS2-A2) → `astm_generic`: ENQ→ACK, har freymga ACK, EOT da blok yopiladi. Serial ham, TCP ham.
- HL7 → `hl7_generic`.

## Diagnostika
- Xizmat konsolida: `🔧 Siydik analizatori: <model> — COM4 9600 8N1 [text]` yoki `tcp_server 0.0.0.0:5200 [hl7]`.
- Har natija RAW holida `Urit/RAW_LOGS/YYYYMM/urit_raw_*.txt` ga yoziladi (HL7/ASTM ham) — parse muammosi bo'lsa shu fayl bilan `siydik_protokol.parse_block()` ni sinash mumkin.
- Noma'lum kodlar `ℹ️ Noma'lum kodlar (blankaga kirmaydi): {...}` deb chiqadi → `CODE_ALIASES` ga qo'shiladi.
- Sozlamalar oynasida **Ulanishni tekshirish**: serial → port ochiladi; tcp_client → analizatorga ulanadi; tcp_server → port tinglanayotganini ko'rsatadi.

## Sinov
`python siydik_protokol.py` — 4 format (URIT, Dirui, HL7, ASTM) uchun namunaviy parse.
