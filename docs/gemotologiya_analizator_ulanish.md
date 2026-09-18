# Gemotologiya analizatorini ulash — universal sozlama

Dastur endi faqat Mindray BC-20S ga emas, O'zbekistonda uchraydigan barcha asosiy
gemotologiya analizatorlariga ulanadi. Kod/EXE o'zgarmaydi — **⚙ Tizim Sozlamalari →
🔵 Gemotologiya** oynasida model tanlanadi, kerak bo'lsa IP/port/COM to'g'rilanadi, Saqlash,
dastur qayta ishga tushiriladi.

| Fayl | Vazifasi |
|---|---|
| `gemo_protokol.py` | Profillar (brendlar), transport (tcp_client / tcp_server / serial), parser (HL7 ORU^R01, ASTM E1394), kod moslashuvi (LOINC / 99MRC / nomlar → kanonik) |
| `bc20s_listener.py` | Jonli qabul (nomi tarixiy). ORM→ORR / ASTM Q worklist, natija → TXT + DB + oyna |
| `hematology_window.py` | TXT fayllarni ko'rsatish (HL7 va ASTM), 3-diff + 5-diff normalar |
| `monoblok_dastur.py` | Sozlamalar oynasi, blanka (`CBC_HEMA_ROWS` 3/5-diff), import |

## Sozlama maydonlari (`analizator_config.json` → `gemotologiya`)

| Kalit | Ma'nosi |
|---|---|
| `model` | `gemo_protokol.PROFILES` kaliti (quyidagi jadval) |
| `connection_type` | `tcp_client` — dastur analizatorga ulanadi (analizator = server); `tcp_server` — analizator dasturga ulanadi; `serial` — RS-232 |
| `protocol` | `auto` (tavsiya) / `hl7` / `astm` |
| `ip`, `port` | tcp_client: analizator IP; tcp_server: tinglash IP (`0.0.0.0`) va port |
| `worklist` | analizator barcode o'qiganda bemor ismini so'rasa (ORM^O01 / ASTM Q) — bazadan javob |
| `com_port, baudrate, bytesize, parity, stopbits` | serial |

## Brendlar bo'yicha (top-10 + boshqalar)

| Profil | Model | Ulanish | Protokol | Analizatorda nima sozlanadi |
|---|---|---|---|---|
| `mindray_bc20s` | Mindray BC-20s / 30s / 5000 / 5150 | tcp_client | HL7 | Setup → Communication: LIS IP = kompyuter, port 5100, analizator Server rejimi (hozirgi ish holati) |
| `mindray_bc_client` | Mindray BC-3600 / 6800 / 2300 | tcp_server | HL7 | Communication: Client rejimi, IP = kompyuter, port = sozlamadagi |
| `mindray_bc3000plus` | Mindray BC-3000 Plus / 3200 | serial | HL7 | Setup → Transmission: HL7, baud 115200/9600. **BC-2800 xususiy formati qo'llanmaydi** |
| `genrui_kt` | Genrui KT-6300 / 6610 / 8000 | tcp_server | HL7 | Setup → System Setup → Communication: Comm. Protocol = HL7, LIS IP = kompyuter, Auto Communicate + Auto Fetch Info from LIS, gistogramma = Not transmitted |
| `edan_h` | Edan H30 Pro / H60 | tcp_server | HL7 | Settings → Communication → LIS: HL7, Server IP = kompyuter |
| `dymind` | Dymind DH-36 / DF-50 / DF-52 | tcp_server | HL7 | Setup → Communication: LIS IP/port |
| `zybio` | Zybio Z3 / Z50 / Z5 | tcp_server | HL7 | Setup → Communication: HL7 |
| `urit_hema` | URIT-3000Plus (RS-232) / 5160 / 5380 (TCP) | tcp_server / serial | HL7 | 3000Plus: ulanish turi = serial |
| `dirui_bcc` | Dirui BCC-3000 / 3600 | tcp_server | HL7 | LIS: HL7, Server IP = kompyuter |
| `biobase` | Biobase BK-6100 / 6190 / 6300 | tcp_server | HL7 | Settings → Communication: HL7 |
| `erba` | Erba Elite 3 / Elite 5 / H360 | tcp_server | auto | HL7 yoki ASTM — auto taniydi |
| `cyan_hemato` | Cypress Cyan Hemato / 380 | tcp_server | auto | LIS: HL7/ASTM, Server IP = kompyuter |
| `human_humacount` | Human HumaCount 30TS / 5L / 80TS | serial | ASTM | Communication: ASTM (LIS2-A2), 9600 8N1 |
| `sysmex_xp` | Sysmex XP-300 / KX-21N / XN-350 | serial | ASTM | Host Computer: ASTM E1394, serial yoki LAN |
| `diatron_abacus` | Diatron Abacus 3 / Junior / Aquila | serial | auto | ASTM yoki HL7 (Diatron serial formati qo'llanmaydi) |
| `hl7_generic` / `astm_generic` | Boshqa | — | — | Har qanday HL7 / ASTM analizator |

Ko'pchilik xitoy analizatorlari (Genrui, Dymind, Zybio, Edan, Biobase, Dirui, URIT, Cyan/Erba OEM)
Mindray andozasini takrorlaydi: HL7 v2.3.1, MLLP, OBX-3 = `LOINC^nom^LN` yoki `100xx^nom^99MRC`,
OBR-3 = sample ID, PID-7 tug'ilgan sana, 30525-0 = yosh, ORM^O01 worklist so'rovi.

## Parametrlar (3-diff va 5-diff)

Kanonik kalitlar: `WBC, NEU#, NEU%, LYM#, LYM%, MON#, MON%, EOS#, EOS%, BAS#, BAS%, MID#, MID%,
GRAN#, GRAN%, RBC, HGB, HCT, MCV, MCH, MCHC, RDW-CV, RDW-SD, PLT, MPV, PDW, PDW-SD, PCT, P-LCR, P-LCC, NLR, PLR`.

Nom variantlari avtomatik: `LYMPH#/LY#/Lymph#`, `NEUT%/NE%`, `MONO#/MO#`, `EO%`, `BASO#`, `MXD`→MID,
`GRA`→GRAN, `RDWc/RDWs`, `PDWc/PDWs`, `HB`→HGB, `PLCR`→P-LCR va h.k. (`gemo_protokol.normalize_param`).
3-diff analizator NEUT/MXD yuborsa (Sysmex XP) → NEU avtomatik GRAN ga o'tkaziladi.
Blankada 5-diff qatorlari (Neu/Mon/Eos/Bas) faqat natija bo'lsa chiqadi; 3-diff (Mid/Gran) qatorlari
5-diff natijada yashiriladi. DB nomlari: `Neu#, Neu%, Mon#, ..., Bas%` (`gemo_protokol.DB_NAME_MAP`).

Bazadagi `test_results.result_data` da `"source": "BC-20S"` tegi **barcha** gemotologiya analizatorlari
uchun saqlanadi (gemo_monitor va blanka shu teg bo'yicha qidiradi); haqiqiy model `"analyzer"` maydonida.

## Diagnostika
- `logs/bc20s_YYYYMMDD.log` — `<Model nomi> — tcp_server 0.0.0.0:5100 [hl7]` qatori ulanish rejimini ko'rsatadi.
- Noma'lum OBX kodlari: `Noma'lum kodlar (o'tkazib yuborildi): [...]` → `gemo_protokol.CODE_MAP` / `_BASE_ALIASES` ga qo'shish.
- Har natija RAW holida `BC-20s/YYYYMM/BC-20s_*.txt` (HL7 yoki ASTM) — `gemo_protokol.parse_message()` bilan sinash mumkin.
- `gemo_monitor` heartbeat qoidasi faqat `tcp_client` (Mindray) uchun; tcp_server/serial da "ulanish yo'q" normal holat.
- Sozlamalar oynasida **Ulanishni tekshirish**: tcp_client → analizatorga ulanadi; tcp_server → port tinglanayotganini; serial → port ochiladi.

## Cheklovlar
- Mindray BC-2800 / BC-3000 (eski, xususiy fiksatsiyalangan format) va Diatron xususiy serial formati — yo'q
  (parametr tartibi rasmiy hujjatsiz tasdiqlanmagan; xato natija biriktirilishi xavfi). Ular HL7/ASTM rejimiga o'tkazilsa ishlaydi.
- `hematology_window` da natijani tahrirlash/qayta yozish (PID/OBR) faqat HL7 TXT uchun.
- Gistogramma/skattergramma (ED, 15000-15200) hozircha o'tkazib yuboriladi.

## Sinov
`python gemo_protokol.py` — HL7 5-diff, ASTM (Sysmex), nom moslashuvi, xabar turlari.
