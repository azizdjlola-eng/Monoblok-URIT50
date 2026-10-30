# Umumiy qon tahlili blankasini sozlash

Har laboratoriyada gematologik analizator har xil: 3-diff (Mid/Gran) yoki 5-diff (Neu/Mon/Eos/Bas), ba'zilari qo'shimcha ko'rsatkich (IG#, NRBC, P-LCR ...) yuboradi, ba'zilari gistogramma bermaydi. Ko'rsatkichlar blankada ham har xil nomlanadi. Shu sababli blanka ko'rinishi dasturning o'zidan, kodga tegmasdan sozlanadi.

## Qayerda

**Tizim Sozlamalari** → **🔵 Gemotologiya** → **🧾 Blanka ko'rinishi (nomlar, tartib, gistogramma)...**

## Umumiy sozlamalar

| Sozlama | Nima qiladi |
|---|---|
| Sarlavha | Blankadagi bo'lim nomi (standart: UMUMIY QON TAHLILI) |
| Analizator nomi | "Avtomatik gematologik analizator: ..." qatoridagi nom. Bo'sh = Tizim Sozlamalaridagi model nomi |
| Analizator / namuna № qatori | Shu qatorni chiqarish yoki chiqarmaslik |
| «Qisqa nom» ustuni | WBC, HGB ... ustunini chiqarish yoki olib tashlash |
| Gistogrammalar | WBC / RBC / PLT gistogrammasini blankaga qo'yish |

## Qatorlar jadvali

Har qator — blankadagi bitta ko'rsatkich.

- **Ko'rinish** — Avto / Doim / Natija bo'lsa / Yashirin.
- **Kod** — analizatordan kelgan natija kaliti (WBC, Lymph#, Mid% ...). Standart qatorda o'zgarmaydi.
- **Blankadagi nomi** — Ko'rsatkich ustunida chiqadigan matn (masalan "Monotsit + Eozinofil + Bazofil soni" o'rniga "O'rta hujayralar (MID)").
- **Qisqa nom**, **Birlik**, **Standart norma** — blankadagi tegishli ustunlar. Standart norma faqat yosh/jinsga mos norma topilmasa ishlatiladi.
- **Analizator kodlari** — analizator shu ko'rsatkichni qanday nom yoki raqam bilan yuborsa (vergul bilan, masalan `IG#, 10014`).

**Avto** rejimi: 5-diff qatorlar faqat natija bo'lsa chiqadi; Mid/Gran 5-diff natijada yashiriladi; asosiy ko'rsatkichlar doim chiqadi; qo'shimcha qatorlar (P-LCR, PDW-SD, siz qo'shganlar) faqat natija bo'lsa chiqadi.

## Amallar

- Ikki marta bosish yoki **✎ Tahrirlash** — qatorni o'zgartirish.
- **▲ Yuqoriga / ▼ Pastga** — blankadagi tartib.
- **Bo'sh joy** yoki **👁 Ko'rinish** — ko'rinish rejimini almashtirish.
- **＋ Yangi qator** — analizator yuboradigan yangi ko'rsatkich qo'shish.
- **✖ O'chirish** — siz qo'shgan qatorni o'chiradi; standart qatorni faqat yashirin qiladi.
- **↺ Standart** — hammasini dastlabki holatga qaytarish.
- **👁 Namuna blanka (Word)** — saqlamasdan oldin oxirgi natija bilan ko'rib chiqish.
- **💾 Saqlash** — keyingi yaratiladigan blankalarda qo'llanadi.

## Yangi ko'rsatkich qo'shish (misol: IG#)

1. Analizatordan natija keladi, lekin blankada yo'q — `logs\bc20s_YYYYMMDD.log` faylida "Noma'lum kodlar" qatoriga qarang (masalan `10014`).
2. **＋ Yangi qator**: Kod = `IG#`, nomi = "Yetilmagan granulotsitlar", birlik = `10⁹/L`, norma = `0 – 0.06`, Analizator kodlari = `10014`.
3. **▲/▼** bilan joyini tanlang, **💾 Saqlash**.
4. Keyingi namunadan boshlab IG# gemotologiya oynasida va blankada chiqadi (oldingi namunalarga qo'shilmaydi).

## Eslatmalar

- Rus tilidagi blankada faqat standart nomlar tarjima qilinadi; o'zgartirilgan nom o'zidek chiqadi.
- Sozlama `analizator_config.json` ning `gemo_blanka` bo'limida saqlanadi (har kompyuterda alohida).
