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

### Mindray UA-66 — ✅ jonli sinovdan o'tgan (17.10.2026)
Boshqa klinikadan vaqtincha olingan UA-66 bilan sinaldi: natijalar dasturga tushdi
(RAW fayl + Siydik oynasi + blanka). Sinovdan keyin URIT-50 qayta ulanib, u ham avvalgidek ishladi.

**Sozlama:** model `Mindray UA-66 (RS-232)`, `serial`, protokol `text`, **COM4 (USB-serial CH340), 57600 8N1**.
Baud analizatorning o'z Setup → Communication sahifasidagi qiymat bilan bir xil bo'lishi shart
(sinalgan qurilmada 57600 edi; profil standarti ham 57600).

**Kabel:** URIT-50 ning RS232 kabeli bilan 0 bayt keldi — UA-66 ga boshqa RS232 kabel ulangandan
keyin ishladi. Ya'ni UA-66 uchun mos (o'z) kabeli kerak.

**Haqiqiy format** (STX/ETX YO'Q — blok `idle_timeout` jimlik bilan yopiladi; `\t` = TAB):
```
2026-10-17
12:25:40
004                       ← namuna raqami ("NO." belgisisiz) → NO
 LEU\t-
 URO\t3.5 umol/L
 PH \t5.5
 KET\tNeg.                 ← musbat bo'lsa faqat son: "KET\t4.0 mmol/L", "GLU\t60 mmol/L", "BIL\t35 umol/L"
 LEU\t2+                   ← ba'zilari faqat daraja
 ASC\t1.14 mmol/L          ← ASC = Vc (askorbin)
```
Namuna: `ua66_raw_004.bin` (side-session notes). Kod: bo'sh raqam qatori birinchi analitdan oldin
bo'lsa `NO` sifatida olinadi (2041 ta URIT-50 RAW fayl regressiyasi — farq 0).

**Cheklovlar (URIT-50 dan farqi):**
- **ID yuborilmaydi** → natija bemorga avtomatik bog'lanmaydi. Servisdagi skaner (`input()`)
  oynasiz servisga yetmaydi. Bog'lash: Siydik oynasi → **✏ Taxrirlash → Sample ID** (ID satri
  bo'lmagan faylga boshiga `ID:` qo'shiladi) yoki asosiy oynada **⬆ Natijani qo'shish**.
- `*` (patologiya) belgisi yo'q va qog'ozdagi daraja + son (`2+ 1.14 mmol/L`) portga bitta ustun
  bo'lib keladi → `ABNORMAL` bo'sh, blankada musbat natija qalin chiqmaydi. Doimiy ishlatilsa —
  sondan musbatni aniqlash qoidasi qo'shilishi kerak.
- 11 parametr (MA/Ca/CR/ACR yo'q).

**Diagnostika saboqlari:** "Ulanishni tekshirish" dagi `PermissionError 13` = portni servis band
qilgan (normal). RS232 da port ochilishi qurilma ulanganini bildirmaydi. 0 bayt = kabel/transmit;
noto'g'ri baud = tushunarsiz baytlar.

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
