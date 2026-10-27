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

### BK-280: LIS javobi "sekin" / 1-urinishda kelmasligi (22.10.2026)

Statistika (24.09–22.10, 601 so'rov): **22% birinchi so'rovga ACK^Q03 kelmagan**, laborant 5–10 s
kutib LIS ni qayta bosgan. Bizning javob har doim <1 s da ketadi (RAW `QUERY/*_out_dsr.txt`).
Sabab analizator dasturida (CRYSTAL `Listrans`, Conductor.exe IL dan aniqlangan):
- socket **statik va bitta** (natija ham, LIS so'rovi ham 8087 dagi bitta ulanishda);
- har `sendHex` (natija yuborish, QRY, ACK^Q03) **yangi `BeginReceive` zanjiri** ochadi, eskilari yopilmaydi;
- kelgan bo'lak navbatdagi eng eski zanjirga tushadi va **o'sha `Listrans` nusxasining** hodisasiga beriladi.
  Natija yuboruvchi nusxa (`frmAll`) zanjiriga tushgan DSR LIS oynasiga (`frmSampleInput`) yetmaydi;
- dispatch faqat bo'lakda `DSC` / `QCK^Q02` / `ACK^R01` bo'lsa, oldin `Thread.Join(1000)` (1 s uxlash).
Shuning uchun natijalar to'plamidan keyingi 1-so'rov ko'pincha yo'qoladi; analizator qayta ulangach o'tadi.
Analizatorning o'zida LIS timeout/qayta urinish **yo'q** (`checktime` — kun almashishi uchun).

**Yechim (`bk280_listener`):** DSR dan keyin `dsr_resend_after` (standart 2.5 s, faqat `biobase*` modelda)
ichida ACK kelmasa QCK+DSR qayta yuboriladi, `dsr_resend_max` (3) martagacha. ACK yoki yangi QRY kelishi bilan
bekor qilinadi; ketma-ketlik `_qlock` bilan bo'linmaydi. Haqiqiy qayta ishlash ≤ ~2.2 s (o'lchangan) — ikki
marta qayta ishlanmaydi. O'chirish: `analizator_config.json → bioximiya.dsr_resend_after = 0`.
Logda: `[QAYTA YUBORISH] <barkod>: ...`.

**Tezkor ish usuli:** analizatorda bir nechta namunani belgilab (Ctrl/Shift) **bitta** "LIS" bosish mumkin —
dastur ularni ketma-ket so'raydi (`frmSampleInput` ro'yxati). Bitta DSR yo'qolsa zanjir to'xtardi; endi
qayta yuborish bilan davom etadi. ⚠ Analizator DSR dagi barkodni TEKSHIRMAYDI (ro'yxatdagi navbatdagi
namunaga yozadi): to'plamli rejimni avval 3–5 namunada sinab, ekrandagi ismlarni barkod bilan solishtiring.

### To'plamli LIS da ism "surilishi" (22.10.2026, 2 holat: 202 ← 199 ismi, 205 ← 203 ismi)
Bizning DSR to'g'ri edi (log: 202 → Iskandarov Sherbek). Analizator (`Listrans.ᜀ(String)`) kalit so'zli
har bo'lak uchun nusxa maydoniga matnni yozadi, 1 s uxlaydi, keyin ishlovchini **maydondagi ENG OXIRGI
matn** bilan chaqiradi. Alohida QCK va DSR = 2 chaqiruv: QCK chaqiruvi DSR_N ni to'g'ri qayta ishlaydi →
ACK → keyingi QRY; DSR chaqiruvi esa (keyingi javobimiz hali kelmagan bo'lsa) o'sha DSR_N ni ro'yxatdagi
**keyingi namunaga** yozadi. Isbot: QRY_203 bizning DSR_202 dan 3 ms keyin kelgan (haqiqiy ishlov ≥1 s).
**Yechim:** QCK+DSR **bitta bo'lak** (`qck_dsr_combine`, biobase da standart; ≤ `combine_max_bytes`=1000,
sig'masa eski usul + logda DIQQAT) → har so'rovga bitta chaqiruv. Natija ACK'i `ack_style: byte` (0x06) —
HL7 `ACK^R01` ham kalit so'z bo'lib, xuddi shu poygani keltirib chiqarishi mumkin edi.
**Nazorat:** ACK^Q03 birinchi bo'lakdan < 0.9 s da kelsa logda `[DIQQAT!] <barkod>` — o'sha namunaning
ismi/tahlillarini analizatorda tekshiring.
Istisno (23.10.2026): shu barkodga DSR ACK kelmasdan oldin ham ketgan bo'lsa (qayta yuborish yoki LIS
qayta bosilgan), tez ACK o'sha bir xil nusxaniki — DIQQAT chiqmaydi, logda `ACK ... oldingi DSR nusxasiga
(bir xil bemor, xavfsiz)`. Vaqt shu barkodga 1-DSR dan ham o'lchanadi (`_last_dsr[2]`).

## LIS fon xizmati va ulanish nazorati (23.10.2026)

**Hodisa:** 23.10 ertalab dastur 08:26 da ochilgan, lekin bioximiya listener logga BIRORTA qator yozmagan —
port 09:25 gacha ochilmagan (BC-20S ishlagan). Analizator LIS ga ulana olmagan: CRYSTAL saqlash/LIS da qotgan.
09:25 da dastur qayta ochilgach analizator ulanib, to'plangan natijalarni ketma-ket yuborgan (natijalar YO'QOLMAYDI).

**CRYSTAL ning ulanish xulqi (IL dan):**
- O'zi QAYTA ULANMAYDI. `Listrans.open` faqat LIS oynasi yuklanganda (`frmAll` Load) va «Подключить»
  tugmasida chaqiriladi.
- Real vaqtli natija (`frmSwatchTest::ᜉ`): LIS ochiq bo'lmasa `tcpisonline=false`, `tcp_ac=false` va
  **"Lis_noserve" MessageBox** chiqaradi. Keyingi natijalar yuborilmaydi — laborant «Подключить» ni
  bosmaguncha shunday qoladi.
- «Подключить» ESKI socket'ni YOPMAYDI (`Connect` → `new Socket`).
- Loglar: listener har qayta ochilgandan keyin analizator **o'zi** emas, laborant bosganda ulanadi (1 s dan
  77 daqiqagacha). Kun davomida monoblok 2–5 marta qayta ochiladi → har safar LIS uziladi.

**Yechim:**
1. **Fon xizmati:** `pythonw bk280_listener.py --xizmat` — monoblokdan MUSTAQIL jarayon. Monoblok uni
   ochadi (`bio_xizmat.taminla`), lekin yopilganda TO'XTATMAYDI → analizator ulanishi saqlanadi.
   - Bitta nusxa: nomli mutex `Local\AzizMedLine_BioLIS_xizmat`. Port egasi: `Local\AzizMedLine_BioLIS_port`
     (Windows `SO_REUSEADDR` ikki jarayonga bitta portni berib qo'yadi — endi faqat bittasi ochadi).
   - Holat: `%ProgramData%\AzizMedLine\BK280\xizmat_holat.json` (har 2 s: listening, connected, peer,
     oxirgi natija/so'rov, natija hodisalari, kod versiyasi). Buyruq: `xizmat_buyruq.txt` ← `stop`/`restart`.
   - Ulanish sozlamasi (ip/port/model...) o'zgarsa xizmat 10 s ichida o'zi qayta ochiladi. `ack_style` va
     qayta yuborish kabi sozlamalar jonli o'qiladi.
   - EXE (PyInstaller) o'rnatmada xizmat yo'q → eski usul (dastur ichida). O'chirish: `bioximiya.xizmat_rejimi = false`.
2. **«● Bioximiya» tugmasi** (har 5 s): yashil — ulangan; to'q sariq «⚠» — analizator ulanmagan
   («Подключить» ni bosing); kulrang «✖» — LIS server ishlamayapti. Ustiga kelganda: IP, ulanish vaqti,
   oxirgi natija/so'rov. Holat o'zgarganda toast (bloklamaydi).
3. **Nazorat (watchdog):** xizmat 15 s holat yozmasa/o'lsa → qayta ochiladi (60 s da ko'pi bilan 1 marta).
   Kod yangilangan + analizator ulanmagan → yangi kod bilan qayta ochiladi (ulanish yo'q — yo'qotish yo'q).
   Listener umuman ochilmasa → kulrang + toast + har 60 s qayta urinish.
4. **Transport (`gemo_protokol`):** server bir vaqtda bitta ulanishga xizmat qiladi. Endi O'SHA IP dan yangi
   ulanish kelsa (laborant «Подключить» ni bosdi) eskisi yopilib yangisiga o'tiladi — ilgari yangisi
   backlogda qolib, analizator "ulandim" deb o'ylardi. Boshqa IP rad etiladi. Keepalive 30 s / 5 s.
5. **Log:** `_log` avval faylga yozadi, konsol — alohida oqimda (print bloklansa listener to'xtamasin).
6. Sozlamalar → Bioximiya: «Ulanishni tekshirish» xizmat holatini ko'rsatadi (portga o'zi ulanmaydi);
   «♻ LIS xizmatini qayta ishga tushirish» (analizatorda «Подключить» ni qayta bosish kerak).

**Statistika (ulanishdan beri yuborilgan natijalar soniga qarab LIS javobi qabul qilinishi):**
<5 → 89%, 5–30 → 58%, 30+ → 48% (alohida ham, bitta bo'lak ham bir xil). Sabab — natija yuboruvchi
`Listrans` nusxasining receive zanjirlari to'planib DSR ni "o'g'irlaydi". Qayta ulanish ularni tozalaydi;
qayta yuborish (2.5 s, 3 marta) yo'qotishni yumshatadi.

**Sinov (jonli portga tegmasdan):** muhit o'zgaruvchilari `BIO_DATA_DIR`, `BIO_LOG_DIR`,
`BIO_XIZMAT_SUFFIX` (mutex nomi), `BIO_XIZMAT_CFG` (test sozlama JSON, masalan 127.0.0.1:18187).
`BIO_XIZMAT_SUFFIX` bo'lsa `hl7_inbox` ga yozilmaydi.

## CRYSTAL "Input string was not in a correct format" — o'lchash to'xtaydi (24.10.2026)

**Belgisi:** o'lchash paytida CRYSTAL oynasida ⚠ "Input string was not in a correct format." chiqadi
va o'lchash to'xtaydi. CRYSTAL yoki kompyuter qayta ishga tushirilsa ham, o'sha namunaga kelganda
xato yana chiqadi. 24.10 da 11:25, 11:43 va 11:52 da chiqqan ("Тестирование: Образец27 проект ALT").

**Isbot:** CRYSTAL logi `Log\YYYYMM.log`:
`FormatException ... Convert.ToInt32(String) at CRYSTAL.sample.frmSwatchTest.ᜀ() ... Timer.OnTick`.
IL dagi `frmSwatchTest.ᜀ()` o'lchash taymeri namunani tayyorlaydi. Unda `Isdilute` (suyultirish belgisi)
True bo'lsa `DiluteSQuan`, `DiluteQuan` (va Rise/Reduce variantlari) `Convert.ToInt32(row[..].ToString())`
bilan o'qiladi. Kunlik bazada (`DataBase\YYYYMMDD.mdb`, `sampleProgram`) bu INTEGER maydonlar NULL bo'lsa,
`""` hosil bo'ladi va FormatException chiqadi.
24.10 bazasida 10:41 LIS to'plamidagi (namuna 19–24) qatorlarda Dilute* maydonlari NULL bo'lgan,
boshqa barcha qatorlarda 20/80/0/0. Nima uchun NULL yozilgani aniqlanmadi: bizning DSR tuzilishi
ertalabki to'plamlar bilan bayt-ma-bayt bir xil, demak bu CRYSTAL ichidagi holat
(10:34 da qayta ochilgan sessiya). Xato chiqishi uchun NULL maydon + suyultirish belgisi birga
bo'lishi kerak. Belgisiz NULL qatorlar (19–24) muammosiz o'lchangan.

**Yechim (laborant):** xato chiqqanda OK → sarlavhadagi namuna raqamini yozib oling → shu namunani
(yoki tahlilini) o'chirib qayta qo'shing (LIS yoki qo'lda) va suyultirish belgisini qo'ymang.
24.10 da 11:54 da 25–30 qayta qo'shilgach to'xtash takrorlanmadi. CRYSTAL yoki kompyuterni qayta
ishga tushirish YORDAM BERMAYDI, chunki buzuq qator bazada qoladi. Bizning LIS tomonda o'zgartirish
kerak emas. Biobase ga stack trace bilan xabar berish kerak.
Tekshirish: nusxa olingan kunlik `.mdb` da `SELECT ... FROM sampleProgram WHERE DiluteSQuan IS NULL`
(32-bit ODBC "Microsoft Access Driver (*.mdb)").

## To'plamli LIS da hammasi tushmasligi: sabab tahlil soni emas (27.10.2026)

**Ma'lumot (22–26.10, 245 ta DSR):** 1-urinishda ACK kelishi tahlil soniga bog'liq emas
(1 tahlil 70%, 4 tahlil 65%, 6+ tahlil 72%). 23, 24 va 26.10 da yuborilgan har bir tahlil
analizator bazasiga tushgan, 9 tahlilli bemorda ham. Hal qiluvchi omil: ulanishdan beri
analizator yuborgan xabarlar soni (<5 natija 98%, 5–30 73%, 30+ 53%).

**Mexanizm (Conductor.exe IL, `Listrans`):**
- har `sendHex` (natija, QRY, ACK^Q03) yangi `ReceiveMsg` oqimi bilan yangi `BeginReceive` ochadi,
  eskisi yopilmaydi. Har bo'lak navbatdagi ENG ESKI qabul qilgichga tushadi va o'sha nusxaga beriladi:
  natijalar `frmSwatchTest.lll`, LIS oynasi esa `frmSampleInput.ᜀ` (har oyna uchun yangi nusxa);
- qabul qilgich bo'lakdan keyin qayta osiladi (`sb.Length > 1`). Faqat "bokira" qabul qilgichga
  1 baytli bo'lak kelsa u o'ladi. Shuning uchun bizning 0x06 ACK natija qabul qilgichlarini o'ldiradi,
  lekin DSR (ko'p bayt) tushgan qabul qilgich abadiy qoladi;
- dispatch faqat bo'lakda `DSC` / `QCK^Q02` / `ACK^R01` bo'lsa bo'ladi. Shunda 1 s kutiladi, keyin
  ishlovchi nusxa maydonidagi OXIRGI matn bilan chaqiriladi.
- **Sinov stendi:** haqiqiy `Listrans` klassi lokal serverga ulanib (scratchpad `harness\lis_harness.ps1`)
  muammoni takrorladi: 5 tur × (8 natija + 5 namuna) → 1-urinishda 15/25 (60%).
  Qayta ulanishdan keyin navbat toza bo'ladi.
- Navbatni loglardan to'liq modellashtirish 72% aniqlik berdi. Bu filler bo'laklar bilan "aniq nishonga
  olish" uchun yetarli emas, shuning uchun kodga kiritilmadi.

**Haqiqiy tahlil soni chegarasi (1024 baytli bo'lak):** QCK 127 bayt, DSR ≈ 646 + 18×tahlil
(ism uzunligiga qarab ±15).
- ≤ 12 tahlil: QCK+DSR bitta bo'lakda (`combine_max_bytes` 1000), xavfsiz;
- 13–21 tahlil: QCK va DSR alohida (2 ta dispatch), to'plamli LIS da ism surilishi xavfi bor;
- ≥ 22 tahlil: DSR 1024 dan oshadi, bo'linadi va analizator uni qayta ishlay olmaydi.
22–27.10 da eng ko'pi 9 tahlil bo'lgan.
Ishlovchi (`frmSampleInput.ᜁ(String)`) `QCK^Q02` bo'lmasa ham `DSR^Q03`+`DSP` ni qayta ishlaydi.
Shuning uchun katta buyurtmani QCK siz faqat DSR bilan yuborish mumkin: bitta bo'lakda ~20 tahlilgacha.
Jonli analizatorda sinalmagan.

**Analizator tahlilni o'zi qo'shmasligi mumkin (IL):** DSR ishlovchisi har tahlil uchun
`reagentInfo` (reagentStyle=1, R2 bo'lsa 2) ni tekshiradi. Reagent diskda bo'lmasa `Not_added`,
muddati o'tgan bo'lsa `isOverdue` beriladi. Namunada shu tahlil bor bo'lsa ham qo'shilmaydi.
Bu bizning tomonda ko'rinmaydi.

**LIS qatorlarida Dilute* NULL:** LIS ishlovchisi `sampleProgram` ga suyultirish miqdorlarini yozmaydi
(`set_DiluteSQuan` yo'q). 26.10 da 177 LIS qatoridan 68 tasi NULL bo'lgan va 10:23 da FormatException
yana chiqqan. LIS orqali kelgan namunaga suyultirish belgisini qo'ymang.

**Ism surilishi (26.10, 2 holat: №50, №86):** ikkalasi ham bir barkod qayta so'ralayotgan yoki
qayta yuborish paytida keyingi namuna so'rovi kelganda bo'lgan. №50 da `[DIQQAT!]` to'g'ri chiqqan.

**Amaliy yechim:** ko'p natija kelgandan keyin to'plamli LIS dan oldin analizatorda LIS ulanishini
yangilang (LIS oynasini yopib-ochish yoki «Подключить»). Toza ulanishda 1-urinish ~98%.

**Kodda (27.10.2026):**
- Listener ulanishdan beri natijalar va 1-urinishda yo'qolgan LIS javoblarini sanaydi.
  Holat faylida `natija_ulanishdan`, `lis_yoqotish_ulanishdan`, `qayta_ulash_tavsiya` maydonlari bor.
  Tavsiya natijalar ≥ `lis_qayta_ulash_natija` (20) bo'lsa yoki yo'qotish > 0 bo'lsa beriladi.
  Shunda tugma «↻ Bioximiya» (zaytun rang) bo'ladi, har ulanishda bir marta toast chiqadi, tooltip'da sababi ko'rinadi.
- QCK+DSR 1000 baytdan oshsa (12+ tahlil) faqat DSR bitta bo'lakda yuboriladi
  (`dsr_only_if_large`, `dsr_only_max_bytes`=1024). Logda `(QCK SIZ bitta bo'lak — N bayt sig'madi)`.
  DSR 1024 dan oshsa `[OGOHLANTIRISH] ... Tahlillarni 2 namunaga bo'ling`.
  **Jonli sinov kerak:** 13+ tahlilli buyurtmada analizator ekranida ism va hamma tahlillar chiqishini
  tekshiring. Chiqmasa `bioximiya.dsr_only_if_large = false` qilib eski usulga qaytaring.

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
- `logs/bio_YYYYMMDD.log` — `<Model> [natija] — tcp_server 0.0.0.0:8087 [auto]`, `[shtrix-kod] ... :8088`;
  `[XIZMAT] ... ishga tushdi (pid N)`, `Analizator qayta ulandi (...) — eski ulanish yopildi`.
- `%ProgramData%\AzizMedLine\BK280\xizmat_holat.json` — xizmatning joriy holati (pid, listening, connected).
- Logda listener qatorlari umuman bo'lmasa — listener ochilmagan; «● Bioximiya» kulrang bo'ladi.
- `bio_nomalum_kodlar.json` — kelgan, tanilmagan kodlar (count, oxirgi vaqt).
- Sozlamalar → "Ulanishni tekshirish": port tinglanayotganini / serial port ochilishini ko'rsatadi.
- Sinov: `python bio_protokol.py` (BK/BS/ASTM parse, worklist, DSR/ORR/ASTM javoblar).

## Cheklovlar
- Yarim-avtomat analizatorlar (BA-88A, RT-9200, Chem-7 ...) — printer matni, qo'llanmaydi.
- Worklistni analizatorga **oldindan** yuborish (push) yo'q — faqat so'rovga javob (barcha brendlarda ishlaydigan usul).
