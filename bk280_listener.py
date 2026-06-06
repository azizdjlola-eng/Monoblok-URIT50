# -*- coding: utf-8 -*-
"""
BK-280 HL7 Listener
BK-280 analyzer dan kelgan HL7 xabarlarni qabul qiladi, parse qiladi va LIMS bazasiga saqlaydi.
"""

import socket
import os
import re
import pymysql
from datetime import datetime
from contextlib import closing
import sys
import io
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Monoblok DB config import qilish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monoblok_db_config import DB_CONFIG

SERVER_IP = "0.0.0.0"
try:
    from analizator_config import oqi as _acfg
    SERVER_PORT = int(_acfg().get("bk280_port", 8087))
except Exception:
    SERVER_PORT = 8087

# Frozen-aware yozish papkasi (mijozda G: bo'lmasligi mumkin)
_BK_DATA = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "AzizMedLine", "BK280")
BASE_DIR = os.path.join(_BK_DATA, "RAW_LOGS")
ERRORS_DIR = os.path.join(_BK_DATA, "ERRORS")
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)

ACK = b'\x06'   # BK-280 kutadigan tasdiqlash bayti

def log_error(error_msg):
    """Xatolarni ERRORS papkasiga saqlash"""
    try:
        error_file = os.path.join(ERRORS_DIR, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{error_msg}\n")
    except:
        pass

def db():
    """Remote MySQL ulanishi (ASUS server 192.168.0.10)"""
    try:
        # pymysql uchun config tayyorlash
        config = {
            "host": DB_CONFIG["host"],
            "user": DB_CONFIG["user"],
            "password": DB_CONFIG["password"],
            "database": DB_CONFIG["database"],
            "port": DB_CONFIG["port"],
            "charset": "utf8mb4",
            "connect_timeout": 5  # 5 soniya timeout
        }
        return pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        error_msg = f"MySQL ulanmadi (192.168.0.10): {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Database ulanish xatosi: {e}"
        print(f"❌ {error_msg}")
        log_error(error_msg)
        raise

def get_order_by_sample_id(sample_id):
    """Sample ID orqali order topish"""
    if not sample_id or not sample_id.strip():
        return None
    with closing(db()) as conn:
        with closing(conn.cursor()) as c:
            # Avval sample_id orqali qidirish
            c.execute("SELECT id FROM orders WHERE sample_id=%s LIMIT 1", (sample_id.strip(),))
            row = c.fetchone()
            if row:
                return row[0]
            # Agar topilmasa, id sifatida tekshirish (agar sample_id son bo'lsa)
            try:
                order_id_int = int(sample_id.strip())
                c.execute("SELECT id FROM orders WHERE id=%s LIMIT 1", (order_id_int,))
                row = c.fetchone()
                if row:
                    return row[0]
            except ValueError:
                pass
    return None

def open_result(order_id):
    """Result yaratish yoki mavjudini qaytarish"""
    with closing(db()) as conn:
        with closing(conn.cursor()) as c:
            c.execute("INSERT IGNORE INTO results(order_id,status) VALUES(%s,'open')", (order_id,))
            conn.commit()
            c.execute("SELECT id FROM results WHERE order_id=%s", (order_id,))
            row = c.fetchone()
            return row[0] if row else None

def upsert_result_item(result_id, test_name, value_text, unit=None, ref_text=None):
    """Result item yaratish yoki yangilash"""
    with closing(db()) as conn:
        with closing(conn.cursor()) as c:
            # Agar allaqachon mavjud bo'lsa, yangilash
            c.execute("SELECT id FROM result_items WHERE result_id=%s AND tahlil_nomi=%s", 
                     (result_id, test_name))
            existing = c.fetchone()
            if existing:
                c.execute("""UPDATE result_items 
                           SET qiymat=%s, birlik=%s, norma=%s
                           WHERE id=%s""", 
                         (value_text, unit, ref_text, existing[0]))
            else:
                c.execute("""INSERT INTO result_items(result_id, tahlil_nomi, qiymat, birlik, norma)
                           VALUES(%s,%s,%s,%s,%s)""", 
                         (result_id, test_name, value_text, unit, ref_text))
            conn.commit()

def save_raw(raw):
    """Raw HL7 xabarni oylik papkaga saqlash: BASE_DIR/YYYYMM/bk280_raw_YYYYMMDD_HHMMSS.txt"""
    dt = datetime.now()
    month_folder = os.path.join(BASE_DIR, dt.strftime("%Y%m"))
    os.makedirs(month_folder, exist_ok=True)
    fname = dt.strftime("bk280_raw_%Y%m%d_%H%M%S.txt")
    path = os.path.join(month_folder, fname)
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(raw)
    print(f"📄 RAW saqlandi: {path}")

def parse_and_save_hl7(raw_msg):
    """
    HL7 xabarni parse qilish va bazaga saqlash.
    BK-280 format:
    - OBR-3: Sample ID (asosiy)
    - PID-5: Patient Name (FamilyName^GivenName)
    - OBX: Test natijalari (OBX-3: kod^nom, OBX-5: qiymat, OBX-6: unit, OBX-7: ref range)
    """
    try:
        # 1) Raw xabarni logga saqlash
        save_raw(raw_msg)
        
        # 2) HL7 xabarni log jadvaliga saqlash
        con = db()
        try:
            with con.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS hl7_inbox(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT NOW()
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
                cur.execute("INSERT INTO hl7_inbox(raw_text, created_at) VALUES(%s, NOW())", (raw_msg,))
                con.commit()
        except Exception as e:
            print(f"⚠️ HL7 log saqlashda xato: {e}")
        finally:
            con.close()
        
        # 3) Sample ID ni topish (OBR-3)
        # Format: OBR|18||18|BIOBASE^BK-280|...
        # OBR-1: sequence, OBR-2: placer order (bo'sh bo'lishi mumkin), OBR-3: filler order (sample_id)
        sample_id = None
        
        # Variant 1: OBR segmentini to'liq parse qilish
        obr_match = re.search(r"OBR\|([^|]+)\|([^|]*)\|([^|]+)\|", raw_msg)
        if obr_match:
            # OBR-3 = filler order number (sample_id)
            sample_id = obr_match.group(3).strip()
        
        # Variant 2: Agar OBR-3 bo'sh bo'lsa, OBR-2 ni tekshirish
        if not sample_id or not sample_id:
            obr_match2 = re.search(r"OBR\|[^|]+\|([^|]+)\|", raw_msg)
            if obr_match2:
                sample_id = obr_match2.group(1).strip()
        
        if not sample_id:
            print("⚠️ Sample ID topilmadi (OBR-2 va OBR-3 bo'sh)")
            print(f"   OBR segment: {raw_msg[raw_msg.find('OBR'):raw_msg.find('OBR')+100] if 'OBR' in raw_msg else 'topilmadi'}")
            return False
        
        print(f"📋 Sample ID: {sample_id}")
        
        # 4) Order topish
        order_id = get_order_by_sample_id(sample_id)
        if not order_id:
            print(f"⚠️ Sample ID {sample_id} uchun order topilmadi")
            return False
        
        print(f"✅ Order topildi: order_id={order_id}")
        
        # 5) Result yaratish
        result_id = open_result(order_id)
        if not result_id:
            print(f"⚠️ Result yaratib bo'lmadi order_id={order_id}")
            return False
        
        # 6) OBX segmentlardan test natijalarini olish
        # Format: OBX|0|NM|272|GLUKOZA|16.66|mmol/L|3.89~6.1|H|...
        pattern = r"OBX\|\d+\|NM\|(\d+)\|(.*?)\|([\d\.]+)\|([^\|]*)\|([^\|]*)\|([^\|]*)"
        matches = re.findall(pattern, raw_msg)
        
        saved_count = 0
        for kod, nom, qiymat, unit, ref_range, flag in matches:
            test_name = nom.strip() if nom.strip() else kod.strip()
            value_text = qiymat.strip()
            unit_text = unit.strip() if unit.strip() else None
            ref_text = ref_range.strip() if ref_range.strip() else None
            flag_text = flag.strip() if flag.strip() else None  # N=Normal, H=High, L=Low
            
            # Agar qiymat '*' bo'lsa, saqlashdan o'tkazamiz
            if value_text and value_text != '*':
                upsert_result_item(result_id, test_name, value_text, unit_text, ref_text, flag_text)
                saved_count += 1
                flag_mark = f" [{flag_text}]" if flag_text else ""
                print(f"  ✓ {test_name}: {value_text} {unit_text or ''}{flag_mark}")
        
        print(f"✅ Sample ID {sample_id} uchun {saved_count} ta natija saqlandi (order_id={order_id}, result_id={result_id})")
        
        # Avtomatik blanka yaratish (agar natijalar bo'lsa)
        if saved_count > 0:
            try:
                from bk280_blanka_auto import save_blanka_to_file
                blanka_path = save_blanka_to_file(order_id)
                if blanka_path:
                    print(f"✅ Blanka avtomatik yaratildi: {blanka_path}")
            except Exception as e:
                print(f"⚠️ Blanka yaratishda xato (e'tiborsiz): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ HL7 parse va saqlash xatosi: {e}")
        import traceback
        traceback.print_exc()
        return False

# Global variable for server socket (to stop listener)
_bk280_server_socket = None
_bk280_running = False

def start_bk280_listener(host=None, port=None, order_update_callback=None):
    """
    BK-280 HL7 Listener ni thread da ishga tushirish
    Returns: Thread object yoki None
    """
    global _bk280_server_socket, _bk280_running
    
    if _bk280_running:
        print("[OGOHLANTIRISH] BK-280 listener allaqachon ishlamoqda")
        return None
    
    server_host = host or SERVER_IP
    server_port = port or SERVER_PORT
    
    def listener_thread():
        global _bk280_server_socket, _bk280_running
        
        try:
            _bk280_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _bk280_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _bk280_server_socket.bind((server_host, server_port))
            _bk280_server_socket.listen(5)
            _bk280_running = True

            print("=" * 60)
            print(f"🔵 BK-280 HL7 Listener")
            print(f"📍 Port: {server_host}:{server_port}")
            print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print(f"✅ Server ishga tushdi. Xabarlarni kutmoqda...\n")

            while _bk280_running:
                try:
                    _bk280_server_socket.settimeout(1.0)  # 1 soniya timeout (tekshirish uchun)
                    conn, addr = _bk280_server_socket.accept()
                    print(f"\n🔵 Ulandi: {addr}")

                    # Analyzer ulanishni ochiq ushlab turadi → biz ham ushlab turamiz
                    full_data = b""

                    while _bk280_running:
                        try:
                            chunk = conn.recv(4096)

                            if not chunk:
                                print("⚠ Ulanish yopildi (bo'sh paket).")
                                break

                            full_data += chunk

                            # Paket oxiri \x1c\x0d (FS+CR) bilan tugaydi
                            if b"\x1c\x0d" in full_data:
                                # ACK qaytariladi
                                conn.sendall(ACK)
                                print("🔶 BK-280 ga ACK yuborildi.")

                                # Matnni decode qilish
                                text = full_data.decode("utf-8", errors="ignore")
                                print("📥 HL7 xabar qabul qilindi:")
                                print(text[:200], " ..." if len(text) > 200 else "")
                                
                                # Parse qilish va bazaga saqlash
                                success = parse_and_save_hl7(text)
                                
                                # Callback chaqirish (agar order_id topilsa)
                                if success and order_update_callback:
                                    try:
                                        # Sample ID ni topish va order_id ni olish
                                        obr_match = re.search(r"OBR\|([^|]+)\|([^|]*)\|([^|]+)\|", text)
                                        if obr_match:
                                            sample_id = obr_match.group(3).strip()
                                            if sample_id:
                                                order_id = get_order_by_sample_id(sample_id)
                                                if order_id:
                                                    order_update_callback(order_id)
                                    except Exception as e:
                                        print(f"⚠️ Callback chaqirishda xato: {e}")
                                
                                full_data = b""  # Yana xabar bo'lsa qayta yig'ish uchun bo'shatiladi

                        except socket.timeout:
                            continue  # Timeout - tekshirish uchun, davom etamiz
                        except ConnectionResetError:
                            print("❌ BK-280 ulanishni uzdi (10054).")
                            break
                        except Exception as e:
                            print(f"❌ Xato: {e}")
                            import traceback
                            traceback.print_exc()
                            break

                    conn.close()
                    print("🔁 Keyingi ulanishni kutamiz...\n")
                    
                except socket.timeout:
                    continue  # Timeout - tekshirish uchun, davom etamiz
                except OSError as e:
                    if _bk280_running:
                        print(f"❌ Socket xatosi: {e}")
                    break
                except Exception as e:
                    if _bk280_running:
                        print(f"❌ Xato: {e}")
                        import traceback
                        traceback.print_exc()
                    break
            
        except Exception as e:
            print(f"❌ BK-280 listener thread xatosi: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _bk280_running = False
            if _bk280_server_socket:
                try:
                    _bk280_server_socket.close()
                except:
                    pass
                _bk280_server_socket = None
            print("🔴 BK-280 listener to'xtatildi")
    
    thread = threading.Thread(target=listener_thread, daemon=True)
    thread.start()
    return thread

def stop_bk280_listener():
    """BK-280 listener ni to'xtatish"""
    global _bk280_server_socket, _bk280_running
    
    _bk280_running = False
    if _bk280_server_socket:
        try:
            _bk280_server_socket.close()
        except:
            pass
        _bk280_server_socket = None

def main():
    """Standalone ishga tushirish (test uchun)"""
    import threading
    thread = start_bk280_listener()
    if thread:
        try:
            thread.join()
        except KeyboardInterrupt:
            print("\n\n⚠️ To'xtatilmoqda...")
            stop_bk280_listener()


if __name__ == "__main__":
    import threading
    main()
