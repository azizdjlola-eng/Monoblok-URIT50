# -*- coding: utf-8 -*-
"""
TAHLIL NOMLARI — kirill / rus ko'rinishi (faqat EKRANDA).

Bazada (tahlillar.nomi, order_items, natijalar) nom LOTINCHA qoladi — sinxron,
hisobot, natija blankasi va qidiruv o'zgarmaydi. «Dastur yozuvi» (ui_til)
kirill yoki rus bo'lsa, Registratsiya jadvallarida tahlil nomi shu yozuvda
ko'rinadi (ui_til.tahlil_nomlarini_qosh → Treeview filtri).

Manba tartibi (birinchi topilgani):
  1) mijozning o'z tuzatishi: %ProgramData%\\AzizMedLine\\tahlil_nomlari.json
       {"Qonning umumiy tahlili": {"kirill": "...", "rus": "..."}}
     (o'zi qo'shgan xizmatlar uchun ham — build'siz);
  2) shu fayldagi QOLDA (katalog_seed nomlari);
  3) kirill — avtomatik (ui_til.kirillga + kodlar: IFA → ИФА ...);
     rus — topilmasa lotincha qoladi (harfma-harf rus qilib bo'lmaydi).
"""

import json
import os
import re

# Kirill yozuvida o'giriladigan qisqartmalar (lotin kod bo'lib qolmasin)
KOD_KIRILL = {
    "IFA": "ИФА", "ECHT": "ЭЧТ", "ALT": "АЛТ", "AST": "АСТ", "LDG": "ЛДГ", "GGT": "ГГТ",
    "ACHTV": "АЧТВ", "TTG": "ТТГ", "LG": "ЛГ", "FSG": "ФСГ", "AT-TPO": "АТ-ТПО",
    "EXOKG": "ЭХОКГ", "OPTG": "ОПТГ", "LIPID": "ЛИПИД", "IF": "ИФ", "PTI": "ПТИ",
    "MNO": "МНО", "UZI": "УЗИ", "EKG": "ЭКГ", "XGCh": "ХГЧ",
}
_KOD_RE = re.compile(r"(?<![A-Za-z\-])(" + "|".join(
    re.escape(k) for k in sorted(KOD_KIRILL, key=len, reverse=True)) + r")(?![A-Za-z\-])")

# Avtomatik kirilldan keyingi tuzatishlar (o'zlashma so'zlar)
_KIRILL_TUZAT = [
    ("Тестестерон", "Тестостерон"), ("Ҳелисобактер", "Хеликобактер"), ("пйлори", "пилори"),
    ("инъэксия", "инъекция"), ("капелнитса", "капельница"), ("Кариэс", "Кариес"),
    ("Алфа", "Альфа"), ("Албумин", "Альбумин"), ("иэв ", "иев "), ("HCV-Аб", "HCV-Ab"),
    ("Ревматоидний", "Ревматоид"), ("реактивний", "реактив"), ("Антистрептолизин-O", "Антистрептолизин-О"),
]

# (kirill yoki None = avtomatik, rus)
QOLDA = {
    "Qonning umumiy tahlili": (None, "Общий анализ крови"),
    "Qondan mazok (morfologiya) ko'rish": (None, "Мазок крови (морфология)"),
    "Eritrotsitlar cho'kish tezligi (ECHT)": (None, "Скорость оседания эритроцитов (СОЭ)"),
    "Qonning ivish vaqti  QIB": ("Қоннинг ивиш вақти (ҚИВ)", "Время свёртывания крови"),
    "Qon guruhi va rezus faktorini aniqlash": (None, "Группа крови и резус-фактор"),
    "Siydikning umumiy tahlili": (None, "Общий анализ мочи"),
    "Siydikning Nicheporenko tahlili": (None, "Анализ мочи по Нечипоренко"),
    "Siydikning Zimnitskiy tahlili": (None, "Анализ мочи по Зимницкому"),
    "Albumin": ("Альбумин", "Альбумин"),
    "Umumiy oqsil": (None, "Общий белок"),
    "Glyukoza": (None, "Глюкоза"),
    "Glyukozaga tolerantlik testi": (None, "Глюкозотолерантный тест"),
    "Alanin aminotransferaza (ALT)": (None, "Аланинаминотрансфераза (АЛТ)"),
    "Aspartat aminotransferaza (AST)": (None, "Аспартатаминотрансфераза (АСТ)"),
    "Kreatinin": (None, "Креатинин"),
    "Mochevina": (None, "Мочевина"),
    "Umumiy xolesterin (TC)": (None, "Общий холестерин"),
    "Trigliserid-TG": ("Триглицеридлар (TG)", "Триглицериды"),
    "Laktatdegidrogrenaza (LDG)": ("Лактатдегидрогеназа (ЛДГ)", "Лактатдегидрогеназа (ЛДГ)"),
    "Gamma-glutamil transferaza (GGT)": (None, "Гамма-глутамилтрансфераза (ГГТ)"),
    "Kalsiy Ca": ("Кальций Ca", "Кальций (Ca)"),
    "Kaliy K": ("Калий K", "Калий (K)"),
    "Temir  Fe": ("Темир Fe", "Железо (Fe)"),
    "Siydik kislota (Mochevaya kislota)": (None, "Мочевая кислота"),
    "Magniy Mg": ("Магний Mg", "Магний (Mg)"),
    "Natriy Na": ("Натрий Na", "Натрий (Na)"),
    "Ishqoriy fosfataza (IF)": (None, "Щелочная фосфатаза (ЩФ)"),
    "Timol proba": (None, "Тимоловая проба"),
    "Bilirubin": (None, "Билирубин"),
    "Alfa-amilaza": (None, "Альфа-амилаза"),
    "Alfa-amilaza pankreaticheskiy": ("Альфа-амилаза панкреатик", "Альфа-амилаза панкреатическая"),
    "REVMOPROBA to'liq (avtomat)": ("Ревмопроба тўлиқ (автомат)", "Ревмопробы полные (автомат)"),
    "RF (Revmatoidniy faktor) avtomat": (None, "Ревматоидный фактор (РФ), автомат"),
    "CRP (S-reaktivniy belok) avtomat": ("CRP (С-реактив оқсил) автомат", "С-реактивный белок (СРБ), автомат"),
    "ASLO (Antistreptolizin-O) avtomat": (None, "Антистрептолизин-О (АСЛО), автомат"),
    "REVMOPROBA to'liq (qo'lda)": ("Ревмопроба тўлиқ (қўлда)", "Ревмопробы полные (ручной метод)"),
    "Troponin T": (None, "Тропонин T"),
    "Troponin I": (None, "Тропонин I"),
    "Troponin I test": (None, "Тропонин I (тест)"),
    "Troponin I miqdoriy  ИФА": ("Тропонин I миқдорий ИФА", "Тропонин I количественный ИФА"),
    "Troponin I miqdoriy IFA": (None, "Тропонин I количественный ИФА"),
    "Pepsinogen I (PGI) IFA": (None, "Пепсиноген I (PGI) ИФА"),
    "Pepsinogen II (PGII) IFA": (None, "Пепсиноген II (PGII) ИФА"),
    "CA 72-4 (oshqozon onkomarkeri)  ИФА": ("CA 72-4 (ошқозон онкомаркери) ИФА", "CA 72-4 (онкомаркер желудка) ИФА"),
    "CA 72-4 (oshqozon onkomarkeri) IFA": (None, "CA 72-4 (онкомаркер желудка) ИФА"),
    "CA15-3 (ko'krak saratoni belgisi) ИФА": (None, "CA 15-3 (онкомаркер молочной железы) ИФА"),
    "CA15-3 (ko'krak saratoni belgisi) IFA": (None, "CA 15-3 (онкомаркер молочной железы) ИФА"),
    "Axlatdan yashirin qon testi": (None, "Анализ кала на скрытую кровь"),
    "KOAGULOGRAMMA to'liq": ("Коагулограмма тўлиқ", "Коагулограмма полная"),
    "Protrombin Time (PTI, PT/MNO)": ("Протромбин вақти (ПТИ, PT/МНО)", "Протромбиновое время (ПТИ, ПВ/МНО)"),
    "Fibrinogen": (None, "Фибриноген"),
    "ACHTV": (None, "АЧТВ"),
    "Trombinovoe vremya (TT)": ("Тромбин вақти (TT)", "Тромбиновое время (ТВ)"),
    "Zamburug' tekshiruvi": (None, "Исследование на грибок"),
    "Qo'tir kanasi aniqlash": (None, "Исследование на чесоточного клеща"),
    "Demodikozni aniqlash": (None, "Исследование на демодекоз"),
    "Gepatit B (HBsAg, ekspress)": (None, "Гепатит B (HBsAg, экспресс)"),
    "Gepatit B (HBsAg, IFA)": (None, "Гепатит B (HBsAg, ИФА)"),
    "Gepatit C (HCV-Ab, ekspress)": (None, "Гепатит C (HCV-Ab, экспресс)"),
    "Gepatit C (Anti-HCV, IFA)": (None, "Гепатит C (Anti-HCV, ИФА)"),
    "Gepatit D (D-antitela, IFA)": (None, "Гепатит D (антитела, ИФА)"),
    "Gepatit A (IgG, IFA)": (None, "Гепатит A (IgG, ИФА)"),
    "Gepatit A (IgM va IgG, ekspress)": (None, "Гепатит A (IgM и IgG, экспресс)"),
    "Gepatit A (IgM, ekspress)": (None, "Гепатит A (IgM, экспресс)"),
    "Brutselyoz (Reaktsiya Xedelson +  Rayta)": ("Бруцеллёз (Хеддельсон ва Райт реакцияси)",
                                                 "Бруцеллёз (реакция Хеддельсона и Райта)"),
    "Helicobakter pylori AB (ekspress)": ("Хеликобактер пилори, антитела (экспресс)",
                                          "Хеликобактер пилори, антитела (экспресс)"),
    "Helicobakter pylori IgG IFA": (None, "Хеликобактер пилори IgG ИФА"),
    "H.Pylori Test (axlatdan)": ("H. pylori тест (ахлатдан)", "H. pylori тест (кал)"),
    "TORCH test IgM va IgG (to'liq)": (None, "TORCH-инфекции IgM и IgG (полный)"),
    "Ginekologik surtma": (None, "Гинекологический мазок"),
    "Spermogramma": (None, "Спермограмма"),
    "Mujskoy mazok (Erkaklar surtmasi)": ("Эркаклар суртмаси (мужской мазок)", "Мужской мазок"),
    "IgE umumiy (Allergiya uchun) IFA": (None, "IgE общий (аллергия) ИФА"),
    "Askarida IgG IFA": (None, "Аскариды IgG ИФА"),
    "Lyambliya-antitela IFA": (None, "Лямблии, антитела ИФА"),
    "Najas tahlili (Gijja uchun)": (None, "Анализ кала на яйца глист"),
    "Vitamin D (25-OH) IFA": (None, "Витамин D (25-OH) ИФА"),
    "Vitamin B12 IFA": (None, "Витамин B12 ИФА"),
    "Ferritin IFA": (None, "Ферритин ИФА"),
    "TTG (TSH) IFA": (None, "ТТГ (TSH) ИФА"),
    "T4 erkin IFA": (None, "Т4 свободный ИФА"),
    "T3 erkin IFA": (None, "Т3 свободный ИФА"),
    "AT-TPO IFA": (None, "АТ-ТПО ИФА"),
    "LG (LH) IFA": (None, "ЛГ (LH) ИФА"),
    "FSG (FSH) IFA": (None, "ФСГ (FSH) ИФА"),
    "Prolaktin IFA": (None, "Пролактин ИФА"),
    "Estradiol IFA": (None, "Эстрадиол ИФА"),
    "Progesteron IFA": (None, "Прогестерон ИФА"),
    "Testesteron IFA": (None, "Тестостерон ИФА"),
    "Testesteron Erkin IFA": ("Тестостерон эркин ИФА", "Тестостерон свободный ИФА"),
    "Umumiy PSA IFA": (None, "ПСА общий ИФА"),
    "Insulin IFA": (None, "Инсулин ИФА"),
    "Kortizol IFA": (None, "Кортизол ИФА"),
    "XGCh (Homiladorlik gormoni) IFA": (None, "ХГЧ (гормон беременности) ИФА"),
    "Anti HBsAg (Antitelo) immunitet  IFA": ("Анти-HBsAg (антитело) иммунитет ИФА",
                                             "Анти-HBsAg (антитела, иммунитет) ИФА"),
    "RW sifilis (ekspress)": (None, "RW сифилис (экспресс)"),
    "LDL-Past zichlikli lipoprotein": ("LDL — паст зичликли липопротеин", "ЛПНП — липопротеины низкой плотности"),
    "HDL-Yuqori zichlikli lipoprotein": ("HDL — юқори зичликли липопротеин", "ЛПВП — липопротеины высокой плотности"),
    "LIPID SPEKTRI": ("Липид спектри", "Липидный спектр"),
    "BUYRAK PANELI": ("Буйрак панели", "Почечная панель"),
    "Xolinesteraza (CHE)": ("Холинэстераза (CHE)", "Холинэстераза (ХЭ)"),
    "Terapevt qabuli": (None, "Приём терапевта"),
    "Kardiolog qabuli": (None, "Приём кардиолога"),
    "Nevrolog qabuli": (None, "Приём невролога"),
    "Ginekolog qabuli": (None, "Приём гинеколога"),
    "Endokrinolog qabuli": (None, "Приём эндокринолога"),
    "Qorin bo'shlig'i UZI": (None, "УЗИ брюшной полости"),
    "Buyrak UZI": (None, "УЗИ почек"),
    "Qalqonsimon bez UZI": (None, "УЗИ щитовидной железы"),
    "Kichik tos a'zolari UZI": (None, "УЗИ органов малого таза"),
    "EXOKG (yurak UZI)": (None, "ЭхоКГ (УЗИ сердца)"),
    "Vena ichiga in'eksiya": (None, "Внутривенная инъекция"),
    "Mushak ichiga ukol": (None, "Внутримышечная инъекция"),
    "Tomchi (kapelnitsa)": (None, "Капельница"),
    "Fizioterapiya seansi": (None, "Сеанс физиотерапии"),
    "Massaj seansi": (None, "Сеанс массажа"),
    "Statsionar yotoq (1 kun)": (None, "Койка в стационаре (1 день)"),
    "Palata lyuks (1 kun)": (None, "Палата люкс (1 день)"),
    "Kunduzgi statsionar (1 kun)": (None, "Дневной стационар (1 день)"),
    "Jigar va o't pufagi UZI": (None, "УЗИ печени и желчного пузыря"),
    "Oshqozon osti bezi UZI": (None, "УЗИ поджелудочной железы"),
    "Taloq UZI": (None, "УЗИ селезёнки"),
    "Siydik pufagi va prostata UZI": (None, "УЗИ мочевого пузыря и простаты"),
    "Sut bezlari UZI": (None, "УЗИ молочных желёз"),
    "Bo'yin limfa tugunlari UZI": (None, "УЗИ лимфоузлов шеи"),
    "Homiladorlik UZI": (None, "УЗИ при беременности"),
    "UZI (umumiy)": (None, "УЗИ (общее)"),
    "Homila UZI (skrining)": (None, "УЗИ плода (скрининг)"),
    "Prostata UZI": (None, "УЗИ простаты"),
    "Qon tomirlari doppleri": (None, "Допплерография сосудов"),
    "Bo'g'imlar UZI": (None, "УЗИ суставов"),
    "EKG (12 tarmoqli, tavsif bilan)": (None, "ЭКГ (12 отведений, с описанием)"),
    "Stomatolog ko'rigi va konsultatsiya": (None, "Осмотр и консультация стоматолога"),
    "Tish rentgeni (prisel)": ("Тиш рентгени (прицел)", "Прицельный снимок зуба"),
    "Ortopantomogramma (OPTG)": (None, "Ортопантомограмма (ОПТГ)"),
    "Anesteziya (og'riqsizlantirish)": (None, "Анестезия (обезболивание)"),
    "Karies davolash + plomba (fotopolimer)": (None, "Лечение кариеса + пломба (фотополимер)"),
    "Vaqtinchalik plomba": (None, "Временная пломба"),
    "Kanal davolash (1 kanal)": (None, "Лечение канала (1 канал)"),
    "Tish olish (oddiy)": (None, "Удаление зуба (простое)"),
    "Tish olish (murakkab)": (None, "Удаление зуба (сложное)"),
    "Sut tishini olish": (None, "Удаление молочного зуба"),
    "Fissura germetizatsiyasi (silant)": (None, "Герметизация фиссур (силант)"),
    "Professional gigiyena (tish tozalash)": (None, "Профессиональная гигиена (чистка зубов)"),
    "Tish oqartirish": (None, "Отбеливание зубов"),
    "Metallokeramik toj": (None, "Металлокерамическая коронка"),
    "Sirkoniy toj": (None, "Циркониевая коронка"),
    "Implant o'rnatish": (None, "Установка импланта"),
    "Breket tizimi (bir jag')": (None, "Брекет-система (одна челюсть)"),
}

# Eski ikki-yozuvli nomlar («... IFA ИФА», aktiv=0) — yangi nusxasi bilan bir xil tarjima
for _eski, _yangi in (
        ("Gepatit B (HBsAg, IFA ИФА)", "Gepatit B (HBsAg, IFA)"),
        ("Gepatit C (Anti-HCV, IFA ИФА)", "Gepatit C (Anti-HCV, IFA)"),
        ("Gepatit D (D-antitela, IFA ИФА)", "Gepatit D (D-antitela, IFA)"),
        ("Gepatit A (IgG, IFA) ИФА", "Gepatit A (IgG, IFA)"),
        ("Helicobakter pylori IgG IFA ИФА", "Helicobakter pylori IgG IFA"),
        ("IgE umumiy (Allergiya uchun) ИФА", "IgE umumiy (Allergiya uchun) IFA"),
        ("Askarida IgG IFA ИФА", "Askarida IgG IFA"),
        ("Lyambliya-antitela IFA ИФА", "Lyambliya-antitela IFA"),
        ("Vitamin D (25-OH) ИФА", "Vitamin D (25-OH) IFA"),
        ("Vitamin B12 ИФА", "Vitamin B12 IFA"),
        ("Ferritin ИФА", "Ferritin IFA"),
        ("TTG (TSH) IFA ИФА", "TTG (TSH) IFA"),
        ("T4 erkin IFA ИФА", "T4 erkin IFA"),
        ("T3 erkin IFA ИФА", "T3 erkin IFA"),
        ("AT-TPO IFA ИФА", "AT-TPO IFA"),
        ("LG (LH) IFA ИФА", "LG (LH) IFA"),
        ("FSG (FSH) IFA ИФА", "FSG (FSH) IFA"),
        ("Prolaktin IFA ИФА", "Prolaktin IFA"),
        ("Estradiol IFA ИФА", "Estradiol IFA"),
        ("Progesteron IFA ИФА", "Progesteron IFA"),
        ("Testesteron IFA ИФА", "Testesteron IFA"),
        ("Testesteron Erkin IFA ИФА", "Testesteron Erkin IFA"),
        ("Umumiy PSA IFA ИФА", "Umumiy PSA IFA"),
        ("Insulin IFA ИФА", "Insulin IFA"),
        ("Kortizol IFA ИФА", "Kortizol IFA"),
        ("XGCh (Homiladorlik gormoni) IFA ИФА", "XGCh (Homiladorlik gormoni) IFA"),
        ("Anti HBsAg (Antitelo) immunitet  IFA  ИФА", "Anti HBsAg (Antitelo) immunitet  IFA"),
):
    QOLDA.setdefault(_eski, QOLDA[_yangi])

MIJOZ_FAYL = "tahlil_nomlari.json"
_MIJOZ = None


def _kalit(nom):
    """Solishtirish kaliti: ortiqcha bo'shliq va tutuq turlari farq qilmaydi."""
    s = str(nom or "").translate(str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'"}))
    return re.sub(r"\s+", " ", s).strip()


_QOLDA_K = {_kalit(k): v for k, v in QOLDA.items()}


def mijoz_fayli():
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(pd, "AzizMedLine", MIJOZ_FAYL)


def _mijoz(qayta=False):
    global _MIJOZ
    if _MIJOZ is not None and not qayta:
        return _MIJOZ
    d = {}
    try:
        with open(mijoz_fayli(), encoding="utf-8") as f:
            for k, v in (json.load(f) or {}).items():
                if isinstance(v, dict) and not str(k).startswith("_"):
                    d[_kalit(k)] = {kk: str(vv).strip() for kk, vv in v.items()
                                   if kk in ("kirill", "rus") and str(vv or "").strip()}
    except Exception:
        d = {}
    _MIJOZ = d
    return d


def kirill_avto(nom):
    """Lotin nomdan kirill (ui_til qoidalari + tahlil kodlari)."""
    import ui_til
    s = re.sub(r"\s{2,}", " ", str(nom)).strip()
    k = ui_til.kirillga(s)
    k = _KOD_RE.sub(lambda m: KOD_KIRILL[m.group(1)], k)
    for a, b in _KIRILL_TUZAT:
        k = k.replace(a, b)
    k = re.sub(r"\bИФА( ИФА)+\b", "ИФА", k)
    return re.sub(r"\s{2,}", " ", k).strip()


def korinish(nom, rejim):
    """Tahlil nomining `rejim` ('kirill' / 'rus' / 'lotin') dagi ko'rinishi.
    Topilmasa — asl nom (rus) yoki avtomatik kirill."""
    if not isinstance(nom, str) or not nom.strip() or rejim not in ("kirill", "rus"):
        return nom
    if not re.search(r"[A-Za-z]", nom):
        return nom                      # allaqachon kirill/rus yozilgan
    k = _kalit(nom)
    m = _mijoz().get(k) or {}
    if m.get(rejim):
        return m[rejim]
    q = _QOLDA_K.get(k)
    if rejim == "rus":
        return q[1] if q and q[1] else nom
    if q and q[0]:
        return q[0]
    try:
        return kirill_avto(nom)
    except Exception:
        return nom
