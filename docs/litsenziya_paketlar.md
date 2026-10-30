# Litsenziya paketlari (Start / Standart / Pro) — imzolovchi uchun

Mijoz dasturi (`funksiya_paketlari.py`) litsenziya faylidagi `data` qismidan ikkita **ixtiyoriy** maydonni o'qiydi. Ularni litsenziya chiqaradigan (imzolovchi, ADMIN_TOKEN bor) dasturga va VPS dagi `/litsenziya/holat` javobiga qo'shish kerak.

```json
"data": {
  "machine_id": "...",
  "expires_at": 1798761600,
  "paket": "standart",
  "modullar": ["gemo_analizator"]
}
```

- `paket` — `"start"`, `"standart"` yoki `"pro"`.
- `modullar` — paketdan tashqari qo'shimcha modullar.
- Yoqilgan modullar = paketga kiradiganlar + `modullar`.
- **Ikkala maydon ham bo'lmasa — hamma funksiya yoqiq.** Eski litsenziyalar va bizning o'rnatmalar shunday ishlayveradi.
- Maydonlar imzolangan `data` ichida bo'lishi shart, aks holda mijoz ularni o'zi tahrirlay oladi.

## Modullar

| Kalit | Funksiya | Paket |
|---|---|---|
| `gemo_analizator` | Gemotologiya analizatori ulanishi | Pro (Standartda qo'shimcha) |
| `siydik_analizator` | Siydik analizatori ulanishi | Pro (Standartda qo'shimcha) |
| `bio_analizator` | Bioximiya analizatori, LIS, shtrix-kod | Pro (Standartda qo'shimcha) |
| `oldingi_natija` | Blankada «Oldingi natija» ustuni | Standart |
| `statistika` | Tahlillar statistikasi | Standart |
| `bulut_pdf` | Natija PDF bulutga (Telegram/SMS shu PDF dan) | Standart |
| `qc` | Sifat nazorati (QC) | Pro |
| `delta_check` | Delta-check | Pro |
| `kritik_jurnal` | Kritik xabar jurnali | Pro |
| `ifa_kuzatuv` | IFA kuzatuv oynasi | Pro |

**Hech qachon yopilmaydi** (modul emas): kritik natija signali, natija xatoligi tekshiruvi, «Sample ID / barkod ↔ ism mos emas» ogohlantirishlari.

## Misollar

- Kichik lab, analizatorsiz: `"paket": "start"`
- 1 ta gemo analizatorli lab: `"paket": "standart", "modullar": ["gemo_analizator"]`
- Katta lab: `"paket": "pro"`

## Mijozda nima bo'ladi

- Litsenziya VPS dan har ochilishda yangilanadi, ya'ni paket masofadan o'zgaradi. Kesh 10 daqiqa.
- Yopiq funksiya tugmasi turadi. Bosilganda «… paketda — bog'laning» xabari chiqadi. Ma'lumot o'chmaydi.
- Analizator moduli yopiq bo'lsa: ulanish xizmati ishga tushmaydi, natijani qo'lda kiritish ishlaydi.
- Paket holati: Tizim Sozlamalari → 🔑 Litsenziya.
