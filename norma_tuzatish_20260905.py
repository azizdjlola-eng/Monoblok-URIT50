# -*- coding: utf-8 -*-
"""Audit natijasi bo'yicha tahlillar_norma tuzatishlari. Tranzaksiyada."""
import sys, os, io, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from monoblok_db_config import DB_CONFIG
import mysql.connector

DRY = '--apply' not in sys.argv
SCR = os.path.dirname(os.path.abspath(__file__)) + os.sep
c = mysql.connector.connect(**DB_CONFIG, connection_timeout=15)
c.autocommit = False
cur = c.cursor(dictionary=True)

TEGILADI = [173, 12, 43, 68, 69, 67, 70, 96, 92, 30, 36, 118, 119, 83, 41]
cur.execute("SELECT * FROM tahlillar_norma WHERE id IN (%s)" % ','.join(map(str, TEGILADI)))
zax = cur.fetchall()
p = SCR + 'norma_zaxira_%s.json' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
io.open(p, 'w', encoding='utf-8').write(json.dumps(zax, ensure_ascii=False, indent=1, default=str))
print('Zaxira:', p, '(%d qator)' % len(zax))

UPDATES = [
 (173, 'tahlil_id', 160, "Miqdoriy Troponin I normasi 159 (noaktiv) dan 160 ga ko'chirildi"),
 (12,  'norma', 'Manfiy (-)',            "Gepatit C ekspress: ikki bo'shliq"),
 (43,  'response_options', 'Demodikoz aniqlanmadi, Demodikoz aniqlandi', "imlo: aniqlanlandi -> aniqlandi"),
 (68,  'norma', '0-1.0 Manfiy (-), >1.0 Musbat (+)',   "Gepatit B IFA: 1.00-1.10 bo'shligi va 40 tomi"),
 (69,  'norma', '0-1.0 Manfiy (-), >1.0 Musbat (+)',   "Gepatit C IFA: bo'shliq va tom"),
 (67,  'norma', '0-20 Manfiy (-), >20 Musbat (+)',     "Gepatit A IgG: 20 chegarasi ikkilanishi va 200 tomi"),
 (70,  'norma', '0-1.0 Musbat (+), >1.0 Manfiy (-)',   "Gepatit D (teskari): 1.0-1.1 bo'shligi; 1.0 endi Musbat"),
 (96,  'norma', '>10.0 Musbat (+), 0-10.0 Manfiy (-)', "Anti HBsAg: ustma-ustlik; 10.0 (immunitet bor) endi Musbat"),
 (92,  'norma', '0-0.9 Manfiy (-)\n0.9-1.1 Shubhali (chegaraviy) - qayta tekshirish\n>1.1 Musbat (+)',
                "Helicobacter IFA: 999 tomi (o'lchash chegarasi 15)"),
 (30,  'norma', '12-19 yosh Erkak: 1.0-38.0, 20-39 yosh Erkak: 8.6-29.0, 40-55 yosh Erkak: 6.9-21.0, '
                '>55 yosh Erkak: 5.9-18.1, <18 yosh Ayol: 0.2-2.5, >18 yosh Ayol: 0.0-4.6',
                "Testosteron: 20-39 yosh erkak bo'limi qo'shildi"),
 (36,  'norma', '0-40 yosh Erkak: 0.0-4.0, 41-60 yosh Erkak: 0.0-5.5, 61< yosh Erkak: 0.0-7.0, Ayol: 0.0-0.45',
                "PSA: 40 yosh teshigi va ayol yosh cheklovi"),
 (118, 'norma', '207-417', "LDG alias moslashtirildi"),
 (119, 'norma', '207-417', "LDG alias (rus) moslashtirildi"),
 (83,  'norma', 'Erkak: 0.0-30.0, Ayol: 0.0-50.0, >50 yosh Ayol: 0.0-50.0', "AT-TPO alias moslashtirildi"),
 (41,  'norma', 'Erkak: 0.0-4.0, 1-trimestr: 36.0-240.0, 2-trimestr: 60.0-240.0, 3-trimestr: 156.0-722.0, '
                'Follikulyar: 0.6-4.6, Ovulyatsiya: 11.0-80.0, Lyutein: 7.5-80.0, Menopauza: 0.0-2.3, 12-17 yosh: 0.3-4.3',
                "Progesteron alias: Ovulyatsiya/Lyutein moslashtirildi"),
]

PT_TMPL = json.dumps({"type": "multi_component", "components": [
    {"name": "PT sekundalarda",   "key": "pt_sek",   "unit": "sek", "norma": "13-15",      "readonly": False},
    {"name": "PT bo'yicha Kviku", "key": "pt_kviku", "unit": "%",   "norma": "70.0-100.0", "readonly": False},
    {"name": "MNO/INR",           "key": "pt_mno",   "unit": "INR", "norma": "0.90-1.15",  "readonly": False},
]}, ensure_ascii=False)

INSERTS = [
 (164, 'TEST', 'Troponin I', 'Manfiy (-)', '', 'numeric', 'Manfiy (-), Musbat (+)', None,
      "Ekspress Troponin I - sifat javobi (miqdoriy IFA dan alohida)"),
 (159, 'TEST', 'Troponin I test', 'Manfiy (-)', '', 'numeric', 'Manfiy (-), Musbat (+)', None,
      "Eski ekspress test (167 arxiv buyurtma) - miqdoriy norma o'rniga sifat normasi"),
 (67,  'IFA',  'Pepsinogen I (PGI) IFA',  '30-130', 'mkg/l', 'numeric', None, None, "Normasi yo'q edi"),
 (68,  'IFA',  'Pepsinogen II (PGII) IFA', '4-22',  'mkg/l', 'numeric', None, None, "Normasi yo'q edi"),
 (74,  'COAG', 'Protrombin Time (PTI, PT/MNO)', '', '', 'numeric', None, PT_TMPL, "Norma/shablon yo'q edi"),
 (87,  'TEST', 'Brutselyoz (Reaktsiya Xedelson +  Rayta)', '', '', 'numeric', None, None, "Norma qatori yo'q edi"),
 (93,  'TEST', "TORCH test IgM va IgG (to'liq)", '', '', 'numeric', None, None, "Norma qatori yo'q edi"),
 (96,  'TEST', 'Spermogramma', '', '', 'numeric', None, None, "Norma qatori yo'q edi"),
 (97,  'TEST', 'Mujskoy mazok (Erkaklar surtmasi)', '', '', 'numeric', None, None, "Norma qatori yo'q edi"),
 (28,  'GEM',  "Qondan mazok (morfologiya) ko'rish", '', '', 'numeric', None, None, "Norma qatori yo'q edi"),
]

try:
    print("\n=== UPDATE ===")
    for nid, col, val, izoh in UPDATES:
        cur.execute("SELECT %s AS v, tahlil_nomi FROM tahlillar_norma WHERE id=%%s" % col, (nid,))
        r = cur.fetchone()
        if not r:
            print("  [YO'Q] norma#%s" % nid); continue
        eski = r['v']
        if str(eski) == str(val):
            print("  [BIR XIL] #%s %s" % (nid, r['tahlil_nomi'][:34])); continue
        print("  #%s %s  (%s)" % (nid, r['tahlil_nomi'][:34], izoh))
        print("      eski : %r" % (eski,))
        print("      yangi: %r" % (val,))
        if not DRY:
            cur.execute("UPDATE tahlillar_norma SET %s=%%s WHERE id=%%s" % col, (val, nid))

    print("\n=== INSERT ===")
    for tid, gr, nomi, norma, birlik, ty, opts, tmpl, izoh in INSERTS:
        cur.execute("SELECT id FROM tahlillar_norma WHERE tahlil_id=%s", (tid,))
        if cur.fetchone():
            print("  [BOR] %s %s" % (tid, nomi[:36])); continue
        print("  + %4s %-41s guruh=%s norma=%r  (%s)" % (tid, nomi[:40], gr, norma, izoh))
        if not DRY:
            cur.execute("""INSERT INTO tahlillar_norma
                (tahlil_id, guruh, tahlil_nomi, norma, birlik, type, response_options, result_template)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (tid, gr, nomi, norma, birlik, ty, opts, tmpl))
    if DRY:
        c.rollback(); print("\n*** SINOV REJIMI - hech narsa saqlanmadi (--apply bilan ishga tushiring) ***")
    else:
        c.commit(); print("\n*** SAQLANDI ***")
except Exception as e:
    c.rollback(); print("XATO, bekor qilindi:", e); raise
finally:
    c.close()
