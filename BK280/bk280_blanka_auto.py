# -*- coding: utf-8 -*-
"""
BK-280 Avtomatik Blanka Yaratish
results jadvalidan yangi natijalarni tekshiradi va PDF blanka yaratadi
"""

import os
import sys
import time
import pymysql
from datetime import datetime
from contextlib import closing

# Monoblok DB config import qilish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monoblok_db_config import DB_CONFIG

# PDF yaratish uchun reportlab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️ reportlab topilmadi. PDF yaratish uchun: pip install reportlab")

BASE_DIR = r"G:\DASTUR\URIT 50\BLANKS"
ERRORS_DIR = r"G:\DASTUR\URIT 50\BC-280\ERRORS"
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)

def log_error(error_msg):
    """Xatolarni ERRORS papkasiga saqlash"""
    try:
        error_file = os.path.join(ERRORS_DIR, f"blanka_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{error_msg}\n")
    except:
        pass

def db():
    """Remote MySQL ulanishi (ASUS server 192.168.0.10)"""
    try:
        config = {
            "host": DB_CONFIG["host"],
            "user": DB_CONFIG["user"],
            "password": DB_CONFIG["password"],
            "database": DB_CONFIG["database"],
            "port": DB_CONFIG["port"],
            "charset": "utf8mb4",
            "connect_timeout": 5
        }
        return pymysql.connect(**config)
    except Exception as e:
        error_msg = f"MySQL ulanmadi: {e}"
        log_error(error_msg)
        raise

def ensure_blanka_column():
    """blanka_yaratildi ustunini tekshirish va yaratish"""
    try:
        with closing(db()) as conn:
            with closing(conn.cursor()) as c:
                c.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s 
                    AND TABLE_NAME = 'results' 
                    AND COLUMN_NAME = 'blanka_yaratildi'
                """, (DB_CONFIG['database'],))
                exists = c.fetchone()[0] > 0
                
                if not exists:
                    c.execute("ALTER TABLE results ADD COLUMN blanka_yaratildi TINYINT(1) DEFAULT 0")
                    conn.commit()
                    print("✅ blanka_yaratildi ustuni qo'shildi")
    except Exception as e:
        error_msg = f"blanka_yaratildi ustunini yaratishda xato: {e}"
        print(f"⚠️ {error_msg}")
        log_error(error_msg)

def check_new_results():
    """Yangi natijalarni tekshirish (oxirgi 30 soniyada)"""
    try:
        ensure_blanka_column()
        
        with closing(db()) as conn:
            with closing(conn.cursor(pymysql.cursors.DictCursor)) as c:
                query = """
                    SELECT r.id, r.order_id, r.created_at
                    FROM results r
                    WHERE r.created_at > DATE_SUB(NOW(), INTERVAL 30 SECOND)
                    AND (r.blanka_yaratildi IS NULL OR r.blanka_yaratildi = 0)
                    AND EXISTS (
                        SELECT 1 FROM result_items ri 
                        WHERE ri.result_id = r.id 
                        AND ri.qiymat IS NOT NULL 
                        AND ri.qiymat != ''
                    )
                    ORDER BY r.created_at ASC
                    LIMIT 10
                """
                c.execute(query)
                return c.fetchall()
    except Exception as e:
        error_msg = f"Yangi natijalarni olishda xato: {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        return []

def get_patient_data(order_id):
    """Bemor ma'lumotlarini olish"""
    try:
        with closing(db()) as conn:
            with closing(conn.cursor(pymysql.cursors.DictCursor)) as c:
                query = """
                    SELECT 
                        b.ism, 
                        b.familiya, 
                        b.yosh, 
                        b.jins, 
                        o.sample_id, 
                        o.created_at,
                        b.tugilgan_sana,
                        b.telefon,
                        b.shifokor
                    FROM orders o
                    JOIN bemorlar b ON o.bemor_id = b.id
                    WHERE o.id = %s
                    LIMIT 1
                """
                c.execute(query, (order_id,))
                return c.fetchone()
    except Exception as e:
        error_msg = f"Bemor ma'lumotlarini olishda xato: {e}"
        log_error(error_msg)
        return None

def get_result_items(result_id):
    """Tahlil natijalarini olish"""
    try:
        with closing(db()) as conn:
            with closing(conn.cursor(pymysql.cursors.DictCursor)) as c:
                query = """
                    SELECT tahlil_nomi, qiymat, birlik, norma, flag
                    FROM result_items
                    WHERE result_id = %s
                    ORDER BY id
                """
                c.execute(query, (result_id,))
                return c.fetchall()
    except Exception as e:
        error_msg = f"Result items olishda xato: {e}"
        log_error(error_msg)
        return []

def generate_pdf_blank(patient, items, order_id):
    """PDF blanka yaratish"""
    if not PDF_AVAILABLE:
        print("⚠️ reportlab o'rnatilmagan - PDF yaratib bo'lmaydi")
        return None
    
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        pdf_dir = os.path.join(BASE_DIR, date_str)
        os.makedirs(pdf_dir, exist_ok=True)
        
        filename = f"sample_{order_id}_{datetime.now().strftime('%H%M%S')}.pdf"
        filepath = os.path.join(pdf_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        
        # Header - Aziz MedLine
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(colors.green)
        c.drawString(50, height - 50, "Aziz MedLine")
        
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.black)
        c.drawString(50, height - 70, "xususiy laboratoriyasi")
        
        # Manzil va telefon
        c.setFont("Helvetica", 9)
        c.drawString(50, height - 90, "Manzil: SURXONDARYO VILOYATI, SHEROBOD TUMANI, QO'RG'ON MFY")
        c.drawString(50, height - 105, "TEL.: (998) 99-673-13-42")
        
        # Chiziq
        c.line(50, height - 115, width - 50, height - 115)
        
        # Bemor ma'lumotlari
        y = height - 140
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "BEMOR MA'LUMOTLARI:")
        
        y -= 25
        c.setFont("Helvetica", 11)
        fish = f"{patient.get('ism', '')} {patient.get('familiya', '')}".strip()
        c.drawString(50, y, f"F.I.SH: {fish}")
        
        y -= 20
        c.drawString(50, y, f"Yoshi: {patient.get('yosh', '')} yosh")
        
        y -= 20
        jins = patient.get('jins', '')
        c.drawString(50, y, f"Jinsi: {jins}")
        
        y -= 20
        sample_id = patient.get('sample_id', '')
        c.drawString(50, y, f"Sample ID: {sample_id}")
        
        y -= 20
        created_at = patient.get('created_at', '')
        if created_at:
            if isinstance(created_at, str):
                date_str = created_at[:10] if len(created_at) >= 10 else created_at
            else:
                date_str = str(created_at)[:10]
            c.drawString(50, y, f"Sana: {date_str}")
        
        # Tahlil natijalari jadvali
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "TAHLIL NATIJALARI:")
        
        # Jadval sarlavhasi
        y -= 25
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Tahlil nomi")
        c.drawString(250, y, "Qiymat")
        c.drawString(350, y, "Birlik")
        c.drawString(450, y, "Norma")
        
        # Jadval ma'lumotlari
        c.setFont("Helvetica", 10)
        y -= 20
        for item in items:
            if y < 100:  # Sahifa tugasa, yangi sahifa
                c.showPage()
                y = height - 50
            
            tahlil_nomi = item.get('tahlil_nomi', '')
            qiymat = str(item.get('qiymat', ''))
            birlik = item.get('birlik', '') or '-'
            norma = item.get('norma', '') or '-'
            flag = item.get('flag', '')
            
            # Flag belgisi
            flag_mark = ""
            flag_color = colors.black
            if flag == 'H':
                flag_mark = " ↑ YUQORI"
                flag_color = colors.red
            elif flag == 'L':
                flag_mark = " ↓ PAST"
                flag_color = colors.red
            elif flag == 'N':
                flag_mark = " (NORMAL)"
                flag_color = colors.green
            
            c.setFillColor(colors.black)
            c.drawString(50, y, tahlil_nomi[:30])  # Uzun nomlar uchun kesish
            
            # Qiymat va flag
            c.setFillColor(flag_color)
            c.drawString(250, y, qiymat + flag_mark)
            
            c.setFillColor(colors.black)
            c.drawString(350, y, birlik[:15])
            c.drawString(450, y, norma[:20])
            
            y -= 20
        
        # Footer
        y = 50
        c.setFont("Helvetica", 9)
        test_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        c.drawString(50, y, f"Test vaqti: {test_time}")
        
        y -= 20
        c.drawString(50, y, "Laborant vrach: __________")
        c.drawString(400, y, "Murodov A.X")
        
        c.save()
        return filepath
        
    except Exception as e:
        error_msg = f"PDF yaratishda xato: {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        import traceback
        traceback.print_exc()
        return None

def mark_as_generated(result_id):
    """Natijani blanka yaratildi deb belgilash"""
    try:
        ensure_blanka_column()
        
        with closing(db()) as conn:
            with closing(conn.cursor()) as c:
                c.execute("UPDATE results SET blanka_yaratildi=1 WHERE id=%s", (result_id,))
                conn.commit()
                return True
    except Exception as e:
        error_msg = f"Blanka belgisini yangilashda xato: {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        return False

def save_to_pdf_documents(order_id, filepath):
    """pdf_documents jadvaliga saqlash"""
    try:
        with closing(db()) as conn:
            with closing(conn.cursor()) as c:
                # Jadval mavjudligini tekshirish va yaratish
                c.execute("""
                    CREATE TABLE IF NOT EXISTS pdf_documents (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        order_id INT NOT NULL,
                        fayl_nomi VARCHAR(255) NOT NULL,
                        fayl_turi VARCHAR(50) DEFAULT 'blanka',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_order_id (order_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                
                query = """
                    INSERT INTO pdf_documents (order_id, fayl_nomi, fayl_turi, created_at)
                    VALUES (%s, %s, 'blanka', NOW())
                """
                c.execute(query, (order_id, os.path.basename(filepath)))
                conn.commit()
                return True
    except Exception as e:
        error_msg = f"pdf_documents ga saqlashda xato: {e}"
        print(f"⚠️ {error_msg}")
        log_error(error_msg)
        return False

def save_blanka_to_file(order_id):
    """
    Blanka yaratish funksiyasi (bk280_listener.py dan chaqiriladi)
    Returns: saqlangan fayl yo'li yoki None
    """
    try:
        # Bemor ma'lumotlarini olish
        patient = get_patient_data(order_id)
        if not patient:
            print(f"⚠️ Order ID {order_id} uchun bemor topilmadi")
            return None
        
        # Result ID ni topish
        with closing(db()) as conn:
            with closing(conn.cursor()) as c:
                c.execute("SELECT id FROM results WHERE order_id=%s ORDER BY id DESC LIMIT 1", (order_id,))
                row = c.fetchone()
                if not row:
                    print(f"⚠️ Order ID {order_id} uchun result topilmadi")
                    return None
                result_id = row[0]
        
        # Tahlil natijalarini olish
        items = get_result_items(result_id)
        if not items:
            print(f"⚠️ Result ID {result_id} uchun natijalar topilmadi")
            return None
        
        # PDF yaratish
        pdf_path = generate_pdf_blank(patient, items, order_id)
        if pdf_path:
            save_to_pdf_documents(order_id, pdf_path)
            mark_as_generated(result_id)
        
        return pdf_path
    except Exception as e:
        error_msg = f"save_blanka_to_file xatosi (order_id={order_id}): {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        return None

def process_new_results():
    """Yangi natijalarni qayta ishlash"""
    new_results = check_new_results()
    
    if not new_results:
        return 0
    
    processed = 0
    for result in new_results:
        result_id = result['id']
        order_id = result['order_id']
        
        print(f"\n📋 Yangi natija topildi: result_id={result_id}, order_id={order_id}")
        
        # 1. Bemor ma'lumotlarini olish
        patient = get_patient_data(order_id)
        if not patient:
            print(f"❌ Order ID {order_id} uchun bemor topilmadi")
            continue
        
        # 2. Tahlil natijalarini olish
        items = get_result_items(result_id)
        if not items:
            print(f"❌ Result ID {result_id} uchun natijalar topilmadi")
            continue
        
        # 3. PDF yaratish
        pdf_path = generate_pdf_blank(patient, items, order_id)
        if not pdf_path:
            print(f"⚠️ PDF yaratilmadi order_id={order_id}")
            continue
        
        print(f"📄 PDF yaratildi: {pdf_path}")
        
        # 4. Bazaga saqlash
        save_to_pdf_documents(order_id, pdf_path)
        
        # 5. Belgilash
        if mark_as_generated(result_id):
            print(f"✅ Blanka muvaffaqiyatli yaratildi va belgilandi!")
            processed += 1
        else:
            print(f"⚠️ Blanka yaratildi, lekin belgilashda xato")
    
    return processed

def main():
    """Asosiy loop - har 5 soniyada tekshirish"""
    print("=" * 60)
    print("🔄 BK-280 Avtomatik Blanka Yaratish")
    print(f"📍 Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"📁 Blankalar saqlash: {BASE_DIR}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if not PDF_AVAILABLE:
        print("⚠️ reportlab o'rnatilmagan!")
        print("   PDF yaratish uchun: pip install reportlab")
        return
    
    print("✅ Server ishga tushdi. Yangi natijalarni tekshiryapman...\n")
    
    while True:
        try:
            processed = process_new_results()
            if processed > 0:
                print(f"\n✅ {processed} ta natija qayta ishlandi")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Dastur to'xtatildi (Ctrl+C)")
            break
        except Exception as e:
            error_msg = f"Asosiy tsiklda xato: {e}"
            print(f"❌ {error_msg}")
            log_error(error_msg)
            import traceback
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()
