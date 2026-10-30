# Bioximiya blankasini sozlash

Bioximiyada har bir yakka tahlilning nomi, normasi va birligi katalogdan olinadi va **«Tahlil Qo'shish»** oynasida o'zgartiriladi. Blankaning qolgan qismi — bo'lim sarlavhasi, tahlillar tartibi, blankadagi nomlar va panellar (Bilirubin, Lipid spektri, Buyrak paneli) — shu oynadan sozlanadi.

## Qayerda

**Tizim Sozlamalari** → **🟢 Bioximiya** → **🧾 Blanka ko'rinishi (nomlar, tartib, panellar)...**

## «Yakka tahlillar» varag'i

- **Bo'lim sarlavhasi** — standart: QONNING BIOKIMYOVIY TAHLILI.
- Ro'yxatda katalogdagi barcha bioximiya tahlillari turadi (ID, katalog nomi).
- **Blankadagi nomi** — faqat blankada chiqadigan nom. Masalan katalogda "Alanin aminotransferaza (ALT)", blankada "ALT". Bo'sh = katalog nomi. Registratsiya va narxlar katalog nomi bilan qoladi.
- **Blankada shu tartibda chiqarish** belgisi yoqilsa, buyurtmadagi tahlillar blankada ▲/▼ bilan berilgan tartibda chiqadi. O'chiq bo'lsa — buyurtmadagi tartib.

## Panellar (Bilirubin, Lipid spektri, Buyrak paneli)

Har panel o'z varag'ida:

| Ustun | Ma'nosi |
|---|---|
| Panel sarlavhasi | Blankadagi panel nomi (masalan LIPID SPEKTRI → LIPIDOGRAMMA) |
| Blankadagi nomi | Bo'sh = standart (a'zolar uchun katalog nomi) |
| Norma | Bo'sh = bazadagi yoki standart norma. Yozilsa — shu ishlatiladi |
| Birlik | Bo'sh = standart |
| A'zo tahlil ID | Panel natijasi qaysi katalog tahlilining yakka natijasidan olinadi |
| Ko'rinish | Doim / Natija bo'lsa / Yashirin (masalan KA, GFR, nisbatlar kerak bo'lmasa) |

**A'zo tahlil ID — yangi o'rnatishda albatta tekshiring.** Standart ID lar (Xolesterin = 43, Trigliseridlar = 44, LDL = 123, HDL = 124, Mochevina = 42, Kreatinin = 41, Albumin = 35, Siydik kislota = 50) faqat Aziz Medline katalogiga mos. Boshqa laboratoriyada katalog ID lari boshqacha bo'ladi. Kerakli ID ni «Yakka tahlillar» varag'idan topib, panelning tegishli qatoriga yozing. Aks holda panel yakka tahlillardan yig'ilmaydi va bitta tahlil blankada ikki marta chiqishi mumkin.

## Amallar

- Ikki marta bosish — tahrirlash; ▲/▼ — tartib; Bo'sh joy — ko'rinish (panellarda).
- **↺ Standart** — hammasini dastlabki holatga qaytaradi.
- **👁 Namuna blanka (Word)** — saqlashdan oldin katalogdagi bir nechta tahlil va uchala panel bilan ko'rib chiqish (raqamlar namunaviy).
- **💾 Saqlash** — keyingi blankalarda qo'llanadi. A'zo ID lari darhol kuchga kiradi.

Sozlama `analizator_config.json` ning `bio_blanka` bo'limida saqlanadi (har kompyuterda alohida). Rus tilidagi blankada faqat standart nomlar tarjima qilinadi.
