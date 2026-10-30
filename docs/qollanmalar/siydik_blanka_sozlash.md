# Siydik tahlili: blanka va kiritishni sozlash

Laboratoriyalarda siydik tahlili har xil qilinadi: analizator (URIT-50, Mindray UA-66, Dirui H ...) yoki analizatorsiz, test poloskani ko'z bilan o'qib. Poloska 11 yoki 14 parametrli bo'ladi, darajalari brendga qarab farq qiladi. Ko'rsatkichlar blankada ham har xil nomlanadi. Bularning hammasi dasturning o'zidan sozlanadi.

## Qayerda

**Tizim Sozlamalari** → **🟡 Siydik** → **🧾 Blanka va kiritish (nomlar, poloska, qo'lda rejim)...**

## «Umumiy» varag'i

| Sozlama | Nima qiladi |
|---|---|
| Analizator | Natija analizatordan keladi. Kelmasa, tahlilga bosilganda «qo'lda kiritish» yoki «Siydik oynasidan natijani tanlash» taklif qilinadi |
| Qo'lda — test poloska | Analizator yo'q. Tahlilga bosilganda qo'lda kiritish oynasi savolsiz ochiladi |
| Blankadagi analizator nomi | "Kimyoviy tahlil (... Analizator)" qatoridagi nom. Bo'sh = Tizim Sozlamalaridagi model nomi |
| «Kod» ustuni | LEU, KET ... ustunini chiqarish yoki olib tashlash |
| Fizik xossalar bo'limi | Miqdori / rangi / tiniqligi jadvali |
| Cho'kma mikroskopiyasi bo'limi | Mikroskopiya jadvali |

Analizator umuman yo'q bo'lsa, **Siydik** varag'idagi «Yoqilgan» belgisini ham olib tashlang.

## «Kimyoviy (poloska)» varag'i

- **Blankadagi nomi**, **Birlik**, **Norma** — blankadagi ustunlar.
- **Qo'lda variantlar** — test poloska darajalari, vergul bilan (masalan `manfiy, ± (15), +1 (70), +2 (125)`). Qo'lda kiritish oynasida ro'yxat bo'lib chiqadi; ro'yxatdan tashqari qiymat ham yozish mumkin.
- **Analizator kodlari** — analizator ko'rsatkichni boshqa nom bilan yuborsa (masalan `ASC`, `UBG`).
- **Ko'rinish**: Avto / Doim / Natija bo'lsa / Yashirin. Avto — MA, Ca, CR, ACR va siz qo'shgan qatorlar faqat natija bo'lsa chiqadi. Yashirin qator qo'lda kiritish oynasida ham ko'rinmaydi.

Qo'lda kiritilgan qiymat qachon qizil bo'ladi: norma `1.010-1.025` yoki `<20` ko'rinishida bo'lsa, son shu bilan solishtiriladi. Aks holda "manfiy" yoki "normal" — norma, boshqa har qanday qiymat qizil. MA va CR kiritilsa, ACR avtomatik hisoblanadi.

## «Mikroskopiya» varag'i

Nomi, normasi, birligi, tartibi va ko'rinishi o'zgartiriladi. Yangi qator ham qo'shish mumkin (masalan Trixomonadalar, Spermatozoidlar). **Tanlov variantlari** berilsa (`topilmadi, topildi`), kiritish oynasida ro'yxat bo'lib chiqadi. Siz qo'shgan qator blankada faqat natija yozilganda chiqadi.

## Analizator barkod yubormasa (masalan Mindray UA-66)

1. Natija analizatordan keladi va **● Siydik** oynasida turadi.
2. Bemorni oching va siydik tahliliga bosing → **«Yo'q»** (Siydik oynasini ochish).
3. Ro'yxatdan shu bemorning natijasini tanlang → **Natijani qo'shish**.

## Amallar

- Ikki marta bosish — tahrirlash, ▲/▼ — tartib, Bo'sh joy — ko'rinishni almashtirish.
- **↺ Standart** — hammasini dastlabki holatga qaytaradi.
- **👁 Namuna blanka (Word)** — saqlashdan oldin oxirgi natija bilan ko'rib chiqish.
- **💾 Saqlash** — keyingi kiritish va blankalarda qo'llanadi.

Sozlama `analizator_config.json` ning `siydik_blanka` bo'limida saqlanadi (har kompyuterda alohida). Rus tilidagi blankada faqat standart nomlar tarjima qilinadi.
