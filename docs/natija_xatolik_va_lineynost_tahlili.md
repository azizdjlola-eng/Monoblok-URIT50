# Natija kiritish xatoliklarini aniqlash — tahlillar ro'yxati va rejasi

> **Holat:** Faqat tahlil/reja hujjati. Kodga hech qanday o'zgartirish kiritilmagan.
> **Manba:** `tahlillar` jadvali (soha='lab', aktiv=1, jami 121 ta), 2026-08-11 holatiga ko'ra
> real bazadan (`192.168.0.40/lab_tizim`) o'qildi. Ko'p-komponentli shablonlar
> `monoblok_dastur.py` dagi `update_sub_norma_panel()` (7944-qator) va
> `create_unified_blank()` / Word generatsiya funksiyalaridan olindi.

## Maqsad (eslatma)

Hozir bioximiya (BK-280) va gemotologiya (BC-20S) uchun `critical_alert.py` orqali
"chegaradan chiqib ketgan / 0 / manfiy / mantiqsiz nisbat" natijalarga signal beriladi.
Xuddi shu mexanizmni **qolgan barcha tahlillarga** (qo'lda kiritiladigan, ko'p
komponentli, sifat-ko'rsatkichli) kengaytirish kerak — bu klaviatura/sichqoncha
xatosi, tugma bosilib ketishi yoki e'tiborsizlik natijasida noto'g'ri natija
saqlanib, chop etilib ketishining oldini oladi (skrinshotlardagi holat: `2.37-1`,
`1.152.01`, `00.976` kabi).

Bu hujjat 2 ta ro'yxatni beradi:
1. **Tahlillar inventari** — bir komponentli / ko'p komponentli / sifat(musbat-manfiy) turkumlarga bo'lingan.
2. **Xatolik ehtimoli katalogi** — formatga oid xato turlari (keyingi sessiyada norma
   oynasiga "Natija chegarasi (lineynost)" va "Xatolik turi" maydonlari sifatida qo'shiladi).

Har bir tahlil qatorida **"Chegara (lineynost)"** ustuni bo'sh qoldirilgan — buni
laboratoriya reagent/analizator pasportiga qarab keyingi bosqichda birga to'ldiramiz.

---

## 1-QISM. BIR KOMPONENTLI (miqdoriy, bitta raqamli natija) tahlillar

Bu tahlillarda natija — bitta o'nlik/butun son (masalan `2.37`, `115`).
Ular uchun eng sodda tekshiruv kifoya: **[min_lineynost, max_lineynost]** oralig'i +
format validatsiyasi (pastda 4-qism).

### 1.1 Bioximiya (BK-280 orqali yoki qo'lda kiritiladigan)

| ID | Tahlil nomi | Birlik (odatda) | Chegara (lineynost) |
|----|---|---|---|
| 39 | Alanin aminotransferaza (ALT) | E/l | — |
| 35 | Albumin | g/l | — |
| 56 | Alfa-amilaza | E/l | — |
| 57 | Alfa-amilaza pankreaticheskiy | E/l | — |
| 40 | Aspartat aminotransferaza (AST) | E/l | — |
| 46 | Gamma-glutamil transferaza (GGT) | E/l | — |
| 37 | Glyukoza | mmol/l | — |
| 53 | Ishqoriy fosfataza (IF) | E/l | — |
| 48 | Kaliy K | mmol/l | — |
| 47 | Kalsiy Ca | mmol/l | — |
| 41 | Kreatinin | mkmol/l | — |
| 45 | Laktatdegidrogrenaza (LDG) | E/l | — |
| 51 | Magniy Mg | mmol/l | — |
| 42 | Mochevina | mmol/l | — |
| 52 | Natriy Na | mmol/l | — |
| 50 | Siydik kislota (Mochevaya kislota) | mkmol/l | — |
| 49 | Temir Fe | mkmol/l | — |
| 54 | Timol proba | ye. | — |
| 44 | Trigliserid-TG | mmol/l | — |
| 36 | Umumiy oqsil | g/l | — |
| 43 | Umumiy xolesterin (TC) | mmol/l | — |
| 123 | LDL-Past zichlikli lipoprotein | mmol/l | — |
| 124 | HDL-Yuqori zichlikli lipoprotein | mmol/l | — |
| 128 | Xolinesteraza (CHE) | E/l | — |
| 38 | Glyukozaga tolerantlik testi | mmol/l | ⚠ ko'p nuqtali (natoshchak/1soat/2soat) — quyida eslatma |

> **Eslatma (38):** "Glyukozaga tolerantlik testi" hozircha bitta natija maydoni
> sifatida saqlanadi (nomida "natoshchak"/"soat" suffiksi bo'lishi mumkin — bu
> `critical_alert.py` da `exclude` sifatida ham qayd etilgan). Amalda bir necha
> vaqt nuqtasi bo'lgani uchun ko'p-komponentli qilib qayta ko'rib chiqish tavsiya
> etiladi (keyingi bosqich).

### 1.2 Gemostaz — koagulogramma tarkibidagi bitta komponent alohida buyurtma qilinganda

| ID | Tahlil nomi | Birlik | Chegara |
|----|---|---|---|
| 76 | ACHTV | sek | — |
| 75 | Fibrinogen | g/l | — |
| 74 | Protrombin Time (PTI, PT/MNO) | sek / % / INR | ⚠ o'zi ham 3 qiymatli (pastga qarang) |
| 77 | Trombinovoe vremya (TT) | sek | — |
| 30 | Qonning ivish vaqti QIB | daq | — |
| 29 | Eritrotsitlar cho'kish tezligi (ECHT) | mm/soat | — |

> **Eslatma (74):** "Protrombin Time (PTI, PT/MNO)" nomidan ko'rinadiki, bitta
> tahlil ichida sekund + % (Kviku) + MNO — 3 ta qiymat bo'lishi mumkin. Hozir
> tizimda bitta natija maydoni sifatida ishlatilsa, buni ham ko'p-komponentli
> ro'yxatga o'tkazish kerakligini tekshirib chiqish lozim (keyingi bosqich).

### 1.3 Revmoproba tarkibidagi bitta komponent alohida buyurtma qilinganda

| ID | Tahlil nomi | Birlik | Chegara |
|----|---|---|---|
| 61 | ASLO (Antistreptolizin-O) avtomat | ME/ml | — |
| 60 | CRP (S-reaktivniy belok) avtomat | mg/l | — |
| 59 | RF (Revmatoidniy faktor) avtomat | ME/ml | — |

### 1.4 Onkomarker / gormon / vitamin / infeksiya IFA(ИФА) — barchasi bitta raqamli natija

| ID | Tahlil nomi | Birlik (odatda) |
|----|---|---|
| 129 | Anti HBsAg (Antitelo) immunitet IFA | mME/ml |
| 99 | Askarida IgG IFA | ko'rsatkich (indeks) |
| 109 | AT-TPO IFA | ME/ml |
| 69 | CA 72-4 (oshqozon onkomarkeri) | E/ml |
| 70 | CA15-3 (ko'krak saratoni belgisi) | E/ml |
| 86 | Gepatit A (IgG, IFA) | indeks |
| 82 | Gepatit B (HBsAg, IFA) | indeks |
| 84 | Gepatit C (Anti-HCV, IFA) | indeks |
| 85 | Gepatit D (D-antitela, IFA) | indeks |
| 98 | IgE umumiy (Allergiya uchun) | ME/ml |
| 118 | Insulin IFA | mkED/ml |
| 113 | Estradiol IFA | pg/ml |
| 105 | Ferritin | ng/ml |
| 111 | FSG (FSH) IFA | mME/ml |
| 90 | Helicobakter pylori IgG IFA | indeks |
| 119 | Kortizol IFA | nmol/l |
| 110 | LG (LH) IFA | mME/ml |
| 100 | Lyambliya-antitela IFA | indeks |
| 67 | Pepsinogen I (PGI) IFA | ng/ml |
| 68 | Pepsinogen II (PGII) IFA | ng/ml |
| 114 | Progesteron IFA | nmol/l |
| 112 | Prolaktin IFA | mME/ml |
| 108 | T3 erkin IFA | pmol/l |
| 107 | T4 erkin IFA | pmol/l |
| 116 | Testesteron Erkin IFA | pg/ml |
| 115 | Testesteron IFA | nmol/l |
| 93* | TORCH test IgM va IgG | *— ko'p komponentli, 2-qismga qarang* |
| 106 | TTG (TSH) IFA | mME/l |
| 117 | Umumiy PSA IFA | ng/ml |
| 104 | Vitamin B12 | pg/ml |
| 103 | Vitamin D (25-OH) | ng/ml |
| 120 | XGCh (Homiladorlik gormoni) IFA | mME/ml |
| 66 | Troponin T | ng/ml |

**Jami 1-qism (bir komponentli, raqamli):** ~50 ta tahlil.

---

## 2-QISM. SIFAT KO'RSATKICHI (musbat/manfiy, tayyor variantlar ro'yxatidan tanlanadigan) tahlillar

Bu tahlillarda erkin matn/raqam emas, balki **belgilangan variantlar ro'yxati**
(masalan: `Manfiy`, `Musbat`, `Kuchsiz musbat`) bo'lishi kerak. Hozirgi holatda
laborant bularni ham erkin matn sifatida kiritishi mumkin — bu ham xato manbai
(imlo xatosi, bo'shliq, katta/kichik harf farqi natijada noto'g'ri chiqishi mumkin).

| ID | Tahlil nomi | Tavsiya etiladigan variantlar ro'yxati |
|----|---|---|
| 81 | Gepatit B (HBsAg, ekspress) | Manfiy / Musbat |
| 83 | Gepatit C (HCV-Ab, ekspress) | Manfiy / Musbat |
| 89 | Helicobakter pylori AB (ekspress) | Manfiy / Musbat |
| 91 | H.Pylori Test (axlatdan) | Manfiy / Musbat |
| 121 | RW sifilis (ekspress) | Manfiy / Musbat |
| 71 | Axlatdan yashirin qon testi | Manfiy / Musbat |
| 80 | Demodikozni aniqlash | Topilmadi / Topildi (+soni) |
| 79 | Qo'tir kanasi aniqlash | Topilmadi / Topildi |
| 78 | Zamburug' tekshiruvi | Topilmadi / Topildi (+turi) |
| 87 | Brutselyoz (Reaktsiya Xedelson + Rayta) | *ko'p komponentli — 2 natija* |

**Jami 2-qism (sifat/musbat-manfiy):** ~9 ta tahlil (+ Brutselyoz 2-qismga o'tadi).

---

## 3-QISM. KO'P KOMPONENTLI tahlillar (bir buyurtmada bir nechta natija maydoni)

Bu guruh eng ko'p xato bo'ladigan joy — chunki har bir sub-maydon o'zining
lineynost chegarasiga ega, va komponentlar orasida **mantiqiy nisbat qoidalari**
ham bo'lishi kerak (masalan bog'langan bilirubin umumiydan katta bo'la olmaydi —
bu qoida bioximiyada allaqachon bor).

| ID | Tahlil nomi | Komponentlar (kalitlar) | Manba (kodda) |
|----|---|---|---|
| 55 | Bilirubin | `umumiy`, `bog_langan`, `erkin` (auto = umumiy − bog_langan) | `update_sub_norma_panel` 7957 |
| 58 | REVMOPROBA to'liq (avtomat) | `rf`, `crp`, `aslo` | 7962 |
| 62 | REVMOPROBA to'liq (qo'lda) | `rf`, `crp`, `aslo` | 7971 |
| 73 | KOAGULOGRAMMA to'liq | `pt_sek`, `pt_kviku`, `pt_mno`, `tt`, `achtv`, `fibrinogen` | 7980 |
| 126 | LIPID SPEKTRI | `tc`, `hdl`, `ldl`, `tg`, `vldl`(auto), `ka`(auto) | 7992 |
| 127 | BUYRAK PANELI | `mochevina`, `kreatinin`, `siydik_kislota`, `albumin`, `bun`(auto), `gfr`(auto) | 8004 |
| 27 | Qonning umumiy tahlili (CBC) | WBC, RBC, HGB, PLT, + 15-20 ta parametr (BC-20S) | `hematology_window.py` |
| 32 | Siydikning umumiy tahlili | rang, tiniqlik, solishtirma zichlik, pH, oqsil, glyukoza, keton, bilirubin, urobilinogen, nitrit, leykotsit, eritrotsit, epiteliy va h.k. (URIT-50) | `urine_window.py` |
| 33 | Siydikning Nicheporenko tahlili | `leykot`, `eritr`, `silindirlar` | `create_nechiporenko_table_in_doc` ~1302 |
| 34 | Siydikning Zimnitskiy tahlili | 8×(`miqdori`,`solishtirma`) + `kunduzgi_diurez`,`tungi_diurez`,`jami_diurez` | `create_zimnitskiy_table_in_doc` ~1335, `show_zimnitskiy_form` ~10821 |
| 96 | Spermogramma | hajm, rang, tiniqlik, pH, konsentratsiya (mln/ml), umumiy soni, harakatchanlik (a/b/c/d, %), morfologiya (norma %), leykotsitlar, agglutinatsiya va h.k. | alohida oyna/shablon (tekshirish kerak) |
| 94 | Ginekologik surtma | flora, leykotsitlar, epiteliy, kokk/tayoqcha, Trixomonada, Gonokokk, Kandida va h.k. (har biri sifat/miqdor) | alohida shablon |
| 97 | Mujskoy mazok (Erkaklar surtmasi) | leykotsitlar, epiteliy, flora, Trixomonada, Gonokokk va h.k. | alohida shablon |
| 93 | TORCH test IgM va IgG (to'liq) | Toksoplazma/Rubella/CMV/Gerpes × (IgM, IgG) = 8 ta natija | alohida shablon |
| 87 | Brutselyoz (Xedelson + Rayta) | `xedelson`, `rayta` | — |
| 31 | Qon guruhi va rezus faktorini aniqlash | `guruh` (O/A/B/AB), `rezus` (+/−) | — |
| 28 | Qondan mazok (morfologiya) ko'rish | tavsif (erkin matn) — validatsiya turi boshqacha | — |
| 102 | Najas tahlili (Gijja uchun) | topilgan gijja turi/soni — sifat+son aralash | — |

**Jami 3-qism (ko'p komponentli):** ~17 ta tahlil (lekin ular ichida CBC, siydik,
spermogramma, surtmalar, TORCH har biri 6-20 ta sub-maydonga ega — demak
haqiqiy "nazorat qilinadigan raqam maydonlari" soni yuzlab).

> **Eslatma:** Spermogramma, Ginekologik surtma, Mujskoy mazok, TORCH, Najas
> tahlili uchun aniq JSON kalitlar ro'yxatini kodda alohida qidirib topish kerak
> (bu fayl darajasida topilmadi — ehtimol alohida dialog/shablon sifatida
> yozilgan yoki hali umumiy natija maydoniga tushirilgan). Buni keyingi
> bosqichda aniqlashtirib, jadvalga to'ldirish kerak.

---

## 4-QISM. XATOLIK EHTIMOLI KATALOGI (validatsiya qoidalari)

Bu — "keyinchalik norma kiritish oynasiga qo'shamiz" deb aytilgan tushunchaning
ro'yxati. Har bir tahlil (yoki sub-komponent) uchun quyidagi **xatolik turlaridan
tegishlilari** belgilanadi.

### 4.1 Format xatolari (klaviatura/tugma bosilib ketishi natijasida)

| # | Xato turi | Misol (skrinshotdan/hayotiy) | Aniqlash usuli |
|---|---|---|---|
| F1 | Ikkita nuqta/vergul | `1.152.01` | Regex: bitta natijada faqat 1 ta `.`/`,` bo'lishi kerak |
| F2 | Nuqta + chiziqcha aralash | `2.37-1` | Raqam formatiga mos kelmasa rad etish |
| F3 | Boshida ortiqcha 0 | `00.976` | Parse qilib qayta formatlash yoki ogohlantirish |
| F4 | Raqam o'rniga harf/belgi | `1.15a`, `--`, `??` | `float()`ga o'tmasa — xato |
| F5 | Bo'sh natija saqlash | `` (bo'sh maydon) | Majburiy maydon tekshiruvi |
| F6 | Ortiqcha probel/tab | `12 .5`, `12\t.5` | Trim + regex |
| F7 | Kutilmagan manfiy son | `-5` (fizik jihatdan manfiy bo'la olmaydigan ko'rsatkich uchun) | `zero`/`neg` qoidasi (mavjud namunaga o'xshash) |
| F8 | Butun son kutilganda kasr (yoki aksincha) | leykotsit soni `7.5` (butun bo'lishi kerak) | Tahlil turiga qarab `int`/`float` validatsiyasi |
| F9 | Bir xil raqam ko'p marta takrorlangan (tugma yopishib qolgani) | `1111111.5` | Chegaradan keskin chiqib ketishi orqali ushlanadi (lineynost) |
| F10 | Notekis o'nlik ajratkich (nuqta/vergul aralash) | `2,37.5` | Normalizatsiya qoidasi |
| F11 | Ikki marta bosilib qo'sh belgi | `..5`, `1..5` | Regex |

### 4.2 Qiymat (lineynost/chegaradan chiqish) xatolari

| # | Xato turi | Tavsif | Signal darajasi |
|---|---|---|---|
| L1 | Analizator/reaktiv o'lchay oladigan **eng past** chegaradan past | Masalan reagent lineynosti 2.0 dan boshlanadi, 0.5 kiritilgan | 🔴 Kritik |
| L2 | Analizator/reaktiv o'lchay oladigan **eng yuqori** chegaradan baland | Masalan lineynost 500 gacha, 5000 kiritilgan | 🔴 Kritik (yoki 🟡 agar "suyultirib qayta o'lchash" natija bo'lsa) |
| L3 | 0 qiymat (doim mavjud bo'lishi kerak bo'lgan ko'rsatkich uchun) | Umumiy oqsil = 0 | 🔴 Kritik |
| L4 | Fiziologik jihatdan mumkin bo'lmagan qiymat (norma emas, balki hayot bilan mos kelmaydigan) | HGB = 5 (odam tirik bo'la olmaydi) | 🔴 Kritik |
| L5 | Normadan juda keskin chetlashish (norma × ko'p marta) | Norma 2.15-2.55, natija 23.7 (o'nlik nuqta joyi noto'g'ri bo'lishi mumkin) | 🟡 Diqqat / qayta tekshirish so'ralsin |

### 4.3 Mantiqiy nisbat xatolari (ko'p komponentli tahlillar uchun)

| # | Xato turi | Misol | Qoida |
|---|---|---|---|
| R1 | Fraksiya > umumiy | Bog'langan bilirubin ≥ Umumiy bilirubin | `direct >= total` → xato (mavjud qoidaga o'xshash) |
| R2 | Erkin/hisoblanadigan qiymat manfiy chiqishi | Erkin bilirubin = Umumiy − Bog'langan < 0 | Auto-hisoblangan maydon manfiy bo'lsa — xato |
| R3 | LDL+HDL+VLDL umumiy xolesterindan oshib ketishi | Lipid spektri | Yig'indi tekshiruvi |
| R4 | Kunduzgi+tungi diurez ≠ jami diurez (Zimnitskiy) | Mavjud auto-calc bor, lekin qo'lda o'zgartirilsa tekshirish kerak | Yig'indi tekshiruvi |
| R5 | Kreatinin past + Mochevina normal/baland (nisbat buzilgan) | Reagent tugash belgisi | Nisbat qoidasi (mavjud namunaga o'xshash) |
| R6 | Foiz ko'rsatkichlar yig'indisi 100% dan oshib ketishi | Spermogramma harakatchanlik a+b+c+d, leykoformula | Yig'indi ≤ 100 tekshiruvi |

### 4.4 Sifat-ko'rsatkich (musbat/manfiy) xatolari

| # | Xato turi | Misol | Qoida |
|---|---|---|---|
| Q1 | Ro'yxatdan tashqari matn kiritilishi | `manfiy` o'rniga `manfi`, `neg`, bo'sh joy bilan `Manfiy ` | Faqat tayyor variantlar ro'yxatidan tanlash (dropdown), erkin matn taqiqlanadi |
| Q2 | Katta/kichik harf nomuvofiqligi natijada noto'g'ri filtrlanishi | `musbat` vs `Musbat` | Variantlar ro'yxati bilan case-insensitive solishtirish yoki majburiy dropdown |

---

## 5-QISM. Tahlil turiga qarab qaysi xatolik turlari tegishli (xulosa jadvali)

| Tahlil toifasi | Tegishli xato turlari |
|---|---|
| Bir komponentli, raqamli (1-qism) | F1-F11, L1-L5 |
| Sifat/musbat-manfiy (2-qism) | Q1-Q2, F5 (bo'sh qoldirish) |
| Ko'p komponentli, barcha sub-maydonlar raqamli (Bilirubin, Revmoproba, Koagulogramma, Lipid spektri, Buyrak paneli, Nicheporenko, Zimnitskiy) | F1-F11, L1-L5 **har bir sub-maydon uchun alohida** + R1-R5 (nisbat qoidalari) |
| CBC / Siydik umumiy / Spermogramma (analizatordan avtomatik keladigan, lekin qo'lda tuzatilishi mumkin) | F1-F11, L1-L5 har bir parametr uchun + R6 (foiz yig'indisi) |
| Surtma/mazok/TORCH (aralash sifat+son) | Q1-Q2 (sifat qismlar uchun) + F/L (son qismlar uchun, masalan leykotsit soni) |

---

## 6-QISM. Keyingi bosqich — norma oynasiga qo'shiladigan yangi tushunchalar

Bu sessiyada **kodga tegilmadi**. Keyingi sessiyada `TahlilKiritishOynasi` (norma
kiritish oynasi, `monoblok_dastur.py` ~3648) ga quyidagilarni qo'shish rejalashtirilmoqda:

1. **"Natija chegarasi (Lineynost)"** — har bir tahlil (va har bir sub-komponent)
   uchun `min_lineynost` / `max_lineynost` maydonlari. Bazada saqlanadi
   (`tahlillar_norma` jadvaliga yangi ustun yoki JSON ichida).
2. **"Xatolik ehtimoli turi"** — dropdown: `Raqamli (butun)` / `Raqamli (o'nlik)` /
   `Sifat (ro'yxatdan)` / `Matn (erkin)`. Shu asosda F1-F11 validatsiyalari avtomatik
   qo'llaniladi.
3. **Saqlash/Chop etish oldidan tekshiruv** — `critical_alert.py` dagi
   `confirm_save()` naqshiga o'xshab, barcha tahlil turlari uchun umumiy
   `check_generic_result()` funksiyasi (hozircha faqat reja, yozilmagan).
4. **Yuqoridagi to'ldirilmagan jadvallar** (Chegara ustunlari, Spermogramma/
   Surtma/TORCH aniq kalitlari) — laboratoriya reagent pasportlari va mavjud kod
   asosida keyingi sessiyada birga to'ldiriladi.
