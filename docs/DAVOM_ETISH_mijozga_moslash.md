# Uyda davom etish — mijozga moslash va funksiya paketlari

**Holat (30.10.2026, ish kompyuteri):** hammasi GitHub'da, oxirgi commit `5687534` (`main`).
ASUS diskidagi (Z: = `\\192.168.0.40\g\DASTUR\URIT 50`) nusxa ham shu commitda.

## Uyda birinchi qilinadigan ish

```
cd "<uydagi repo papkasi>"
git pull origin main
```

## Bugun qilingan ishlar (hammasi sinovdan o'tgan)

| Commit | Nima |
|---|---|
| 5effd3d, d4755f1, ab3ba71 | Gemo / siydik / bioximiya blankasi sozlanadi; siydik test poloska (qo'lda) rejimi |
| 5f783b2 | `tahlil_turlari.py` — maxsus tahlillar (Umumiy qon, siydik, panellar ...) katalog ID ga bog'lanadi («OAK» ham taniladi) |
| 82e0a7c | `markaziy_sozlama.py` — blanka sozlamalari **bazada** (`lims_sozlamalar` jadvali), hamma kompyuterda bir xil |
| 74f4dcc | `gemo_normalar.py` — gemotologiya normalari (yosh × jins) |
| d488bdc | `maxsus_jadval.py` — 10 ta maxsus jadval normasi; koagulogramma/bilirubin katalog sub-normasidan |
| 70762ab | `chegara_sozlama.py` — kritik qiymat / delta-check / signal chegaralari oynasi (ID mos emas → ⚠) |
| 48a513c | Blanka: imzo rasmi, «Tasdiqladi» qatori, izoh (imzo — laborant vrachniki) |
| 3c890bb | `ornatish_ustasi.py` — yangi laboratoriya uchun 11 qadamli tekshiruv |
| 9fe81f5 | `blanka_kirill.py` — o'zbek kirill blankasi |
| 5687534 | `funksiya_paketlari.py` — Start / Standart / Pro (mijoz tomoni) |

Qo'llanmalar: `docs/qollanmalar/*.md` (OneDrive\AzizMedLine_Qollanmalar da .docx/.pdf).

## UYDA QILINADIGAN ASOSIY ISH — litsenziya chiqaruvchi dastur

Mijoz dasturi tayyor, lekin paket **imzolangan** litsenziya ichida bo'lishi kerak.

1. Litsenziya chiqaradigan (imzolovchi, ADMIN_TOKEN bor) dasturga ikki maydon qo'shish: `"paket"` (`start` / `standart` / `pro`) va `"modullar"` (qo'shimcha modullar ro'yxati). Ikkalasi `data` ichida, imzodan OLDIN.
2. UI da paket tanlovi (3 ta) va qo'shimcha modullar belgilari. Modullar ro'yxati va aniq format: **`docs/litsenziya_paketlar.md`**.
3. VPS dagi `/litsenziya/holat` javobi ham shu maydonlarni qaytarishi kerak, shunda paket masofadan o'zgaradi.
4. Sinov: bitta kompyuterga `"paket": "standart", "modullar": ["gemo_analizator"]` litsenziya chiqarib, mijoz dasturida Tizim Sozlamalari → 🔑 Litsenziya varag'ini tekshirish. U yerda «Paket: Standart» va ✓/— ro'yxati chiqishi kerak.
5. Ikkala maydon bo'lmasa hamma funksiya yoqiq qoladi — eski litsenziyalarni qayta chiqarish SHART EMAS.

**Tasdiqlash kerak:** yopiq funksiya xabaridagi telefon `funksiya_paketlari.ALOQA` da (+998 99 673 13 42 — klinika raqami). Boshqa raqam kerak bo'lsa, o'zgartiring.

## Ishda dasturni qayta ochib tekshirish (jonli UI da bosib ko'rilmagan)

- Tizim Sozlamalari: 🧩 Maxsus tahlillar (3 tugma), Siydik/Gemotologiya/Bioximiya → «🧾 Blanka ...», pastda «🧭 O'rnatish ustasi», 🔑 Litsenziya → paket holati.
- Blanka Sozlamalari: imzo rasmi, tasdiq qatori, izoh, 🌐 Blanka tili → Kirill.
- Biror bemorga blanka yaratib, avvalgisi bilan bir xil chiqishini ko'rish.
- Ish kompyuterida ustadagi litsenziya qatori «boshqa kompyuter uchun berilgan» deydi — bu shu PC ning haqiqiy holati, kod xatosi emas.

## Eslatmalar

- `lims_sozlamalar` jadvali ish bazasida (192.168.0.40) yaratildi. Uydagi baza boshqa (127.0.0.1) — u yerda sozlamalar alohida, birinchi o'qishda mahalliy `analizator_config.json` dan ko'chiriladi.
- Claude uchun: xotira `Claude_Memory\G--DASTUR-URIT-50\memory` (Google Drive va OneDrive). Asosiy fayl: `project_mijozga_moslash_reja.md`. Bash heredoc'da backslash buziladi — kodni Write/Edit bilan o'zgartiring.
