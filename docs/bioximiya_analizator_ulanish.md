# Bioximiya (avtomat) analizatorini ulash — universal sozlama + shtrix-kod

**⚙ Tizim Sozlamalari → 🟢 Bioximiya**: model tanlanadi → ulanish turi/port/protokol avtomatik,
kerak bo'lsa to'g'rilanadi → Saqlash → dastur qayta ishga tushiriladi. EXE qayta build qilinmaydi.

| Fayl | Vazifasi |
|---|---|
| `bio_protokol.py` | Profillar, HL7/ASTM parser, **kanonik kodlar** (BK-280 LIS raqamlari), kod xaritasi, worklist (QCK/DSR, ORR, ASTM H/P/O/L) |
| `bk280_listener.py` | Universal listener (nomi tarixiy): natija → RAW + hl7_inbox + callback; shtrix-kod so'rovi → javob. Natija va so'rov portlari (ikkita bo'lsa ikkalasi) |
| `biochemistry_window.py` | RAW ko'rish/import — parser `bio_protokol` |
| `gemo_protokol.Transport` | tcp_server / tcp_client / serial, MLLP/ASTM freymlar (umumiy) |
| `bio_kod_xarita.json` | Analizator kodi → kanonik kod (model bo'yicha); `bio_nomalum_kodlar.json` — kelgan, bog'lanmagan kodlar |

## Sozlama (`analizator_config.json → bioximiya`)

| Kalit | Ma'nosi |
|---|---|
| `model` | `bio_protokol.PROFILES` kaliti |
| `connection_type` | `tcp_server` (analizator bizga ulanadi — ko'pchilik), `tcp_client`, `serial` |
| `protocol` | `auto` / `hl7` / `astm` |
| `port` | natija porti; `lis_port` — shtrix-kod so'rovi porti (0 = natija porti bilan bir xil) |
| `ack_style` | natijaga javob: `byte` (0x06 — BK-280), `hl7` (ACK^R01), `both` |

## Brendlar

| Profil | Model | Ulanish | Protokol | So'rov (shtrix-kod) | Analizatorda |
|---|---|---|---|---|---|
| `biobase_bk` | Biobase BK-200/280/400/600 | tcp_server 8087 + 8088 | HL7 | QRY^Q02 → QCK + DSR^Q03 | LIS IP = kompyuter, natija 8087, so'rov 8088 |
| `mindray_bs` | Mindray BS-120/200/240/360E/430 | tcp_server 5100 | HL7 | QRY/DSR | Setup → LIS: HL7, Server IP/port, Bidirectional, auto query by barcode |
| `zybio_exc`, `dirui_cs`, `genrui_gs`, `rayto_chemray` | Zybio EXC, Dirui CS, Genrui/Dymind, Rayto Chemray | tcp_server 5100 | HL7 (Rayto: auto) | QRY/DSR | LIS: HL7, Server IP/port = kompyuter |
| `urit_chem` | URIT-8021A/8030/8210 | tcp_server 5100 | HL7 | ORM^O01 → ORR^O02 (QRY ham) | LIS: HL7 |
| `erba_xl`, `human_humastar`, `biosystems`, `roche_cobas` | Erba XL, HumaStar, BioSystems A15/BA, Cobas c111 | tcp_server 5100 / serial | ASTM | Q → H/P/O/L | Host: ASTM E1394 |
| `hl7_generic` / `astm_generic` | boshqalar | — | — | — | — |

## Shtrix-kod (worklist) qanday ishlaydi va nima uchun ilgari ishlamagan

1. Laborant analizatorda namuna shtrix-kodini skanerlaydi → analizator LIS ga so'rov yuboradi
   (QRY^Q02 / ORM^O01 / ASTM Q, ichida barcode).
2. Dastur `orders.sample_id` (yoki bemor `natija_kodi`/`kod_yollanma`) bo'yicha buyurtmani topadi.
   **`orders.id` bo'yicha qidirmaydi** — analizator namuna raqami 22 ni 22-buyurtmaga xato biriktirmaslik uchun.
3. Buyurtma tahlillari → **analizator kanal kodlari**: `tahlillar.id` → kanonik LIS kod (`CANONICAL_TESTS`)
   → kod xaritasi (`bio_kod_xarita.json`). Panellar ochiladi: Bilirubin(55) → 320+321,
   REVMOPROBA(58) → 305/245/322, LIPID(126) → 254/308/277/289, BUYRAK(127) → 313/323/233/310.
4. Javob: bemor ismi + tug'ilgan sana + jins + tahlillar ro'yxati → analizator ekranida paydo bo'ladi.

Ilgari `BK280/asus_lis_server.py` DSR da `tahlillar.kod` (deyarli hammasi NULL) yoki `tahlillar.id` (35, 37 ...)
yuborardi — BK-280 bu raqamlarni bilmaydi (uning kodlari 272, 236 ...) va panellar ochilmasdi. Endi to'g'ri kodlar ketadi.
**Tekshirish:** analizatorda barcode skanerlang → ism va tahlillar chiqishi kerak; `logs/bio_YYYYMMDD.log` da
`◄ QRY^Q02 (shtrix-kod): 2609...` va `-> DSR^Q03: <ism> | tahlillar: [...]` qatorlari.

## Kod xaritasi (Tahlil kodlari oynasi)

Bioximiya tabida **🧬 Tahlil kodlari** tugmasi. Jadval: analizator kodi | nomi | LIMS tahlili.
- Biobase BK-280: xarita shart emas (kodlar kanonik bilan bir xil).
- Mindray BS / Zybio / Dirui: analizatordagi **kanal raqami** (masalan 3 = GLU) → LIMS tahlili. Natija kelganda
  tanilmagan kodlar sariq "noma'lum" qatorlarda chiqadi → LIMS tahlilini tanlang → Saqlash.
- "Avtomatik taxmin" — nom bo'yicha (GLU, ALT, UREA, TBIL, CHOL, HDL-C ...) `guess_canonical` bilan.
- Xarita ikki tomonlama: natija import (analizator kod → kanonik) va worklist (kanonik → analizator kod).

## Natija oqimi

Listener natijani bazaga **yozmaydi** (eski `parse_and_save_hl7` DB yozuvi 6-argument xatosi tufayli hech qachon ishlamagan
va `orders.id` fallback bilan xavfli edi). RAW fayl → `biochemistry_window` → laborant tasdiqlab import → F2.
Kanonik kodlar (272, 236 ...) hamma joyda bir xil, shuning uchun `on_biochemistry_import` (320/321 bilirubin,
305/245/322 revmo, 313/323/310 buyrak, 254/308 lipid) boshqa brend natijalari uchun ham ishlaydi.

## Diagnostika
- `logs/bio_YYYYMMDD.log` — `<Model> [natija] — tcp_server 0.0.0.0:8087 [auto]`, `[shtrix-kod] ... :8088`.
- `bio_nomalum_kodlar.json` — kelgan, tanilmagan kodlar (count, oxirgi vaqt).
- Sozlamalar → "Ulanishni tekshirish": port tinglanayotganini / serial port ochilishini ko'rsatadi.
- Sinov: `python bio_protokol.py` (BK/BS/ASTM parse, worklist, DSR/ORR/ASTM javoblar).

## Cheklovlar
- Yarim-avtomat analizatorlar (BA-88A, RT-9200, Chem-7 ...) — printer matni, qo'llanmaydi.
- Worklistni analizatorga **oldindan** yuborish (push) yo'q — faqat so'rovga javob (barcha brendlarda ishlaydigan usul).
