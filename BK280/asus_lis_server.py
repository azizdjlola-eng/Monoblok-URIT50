# -*- coding: utf-8 -*-
"""
BK-280 LIS Server - HL7 QRY^Q02 Query Handler (v2.0)
BK-280 analyzer dan kelgan barcode scan (QRY^Q02) ni qabul qiladi
va QCK^Q02 + DSR^Q03 javob bilan bemor ma'lumotlarini qaytaradi.

Protokol: HL7 v2.3.1 over MLLP (TCP/IP)
Framing: <SB>(0x0B) data <EB>(0x1C) <CR>(0x0D)

Flow:
  1. BK-280 → LIS: QRY^Q02 (barcode scan, QRD-8 = sample barcode)
  2. LIS → BK-280: QCK^Q02 (acknowledgment: OK yoki NF)
  3. LIS → BK-280: DSR^Q03 (bemor + tahlil ma'lumotlari, 29 DSP segment)
  4. BK-280 → LIS: ACK^Q03 (tasdiqlash)
"""

import socket
import os
import re
import pymysql
from datetime import datetime
from contextlib import closing
import sys
import threading
import time

# Monoblok DB config import qilish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monoblok_db_config import DB_CONFIG

SERVER_IP = "0.0.0.0"
SERVER_PORT = 8088

# MLLP framing bytes
SB = b'\x0b'  # Start Block (VT = 0x0B)
EB = b'\x1c'  # End Block (FS = 0x1C)
CR = b'\x0d'  # Carriage Return (0x0D)

ERRORS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ERRORS")
os.makedirs(ERRORS_DIR, exist_ok=True)

# Global variables for threaded server
_lis_server_socket = None
_lis_running = False
_msg_counter = 0
_msg_lock = threading.Lock()


def _next_msg_id():
    global _msg_counter
    with _msg_lock:
        _msg_counter += 1
        return str(_msg_counter)


def log_error(error_msg):
    try:
        error_file = os.path.join(ERRORS_DIR, f"lis_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{error_msg}\n")
    except:
        pass


def db():
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
        log_error(f"MySQL ulanmadi: {e}")
        raise


def mllp_wrap(hl7_text):
    """HL7 xabarni MLLP framing bilan o'rash: <SB>data<EB><CR>"""
    return SB + hl7_text.encode('ascii', errors='replace') + EB + CR


def parse_qry_message(data):
    """
    QRY^Q02 xabardan barcode (sample_id) va query meta-datani ajratish.
    QRD-8 = Who Subject Filter = barcode
    QRD-10 = What Department Data Code = rack^position
    QRD-11 = What Data Code Value Qual = dilution (Y/N)
    QRD-4 = Query ID
    Returns: dict {sample_id, query_id, rack_pos, dilution, timestamp}
    """
    try:
        text = data.decode('utf-8', errors='ignore')
        # SB ni olib tashlash
        if text.startswith('\x0b'):
            text = text[1:]
        lines = text.split('\r')

        result = {
            'sample_id': None,
            'query_id': '1',
            'rack_pos': '',
            'dilution': 'N',
            'timestamp': datetime.now().strftime("%Y%m%d%H%M%S"),
            'qrd_line': '',
            'qrf_line': '',
            'msh_control_id': '1'
        }

        for line in lines:
            line = line.strip()
            if line.startswith('MSH|'):
                fields = line.split('|')
                if len(fields) > 10:
                    result['msh_control_id'] = fields[10].strip() or '1'

            elif line.startswith('QRD|'):
                result['qrd_line'] = line
                fields = line.split('|')
                if len(fields) >= 9:
                    result['sample_id'] = fields[8].strip()  # QRD-8: barcode
                if len(fields) >= 5:
                    result['query_id'] = fields[4].strip() or '1'  # QRD-4: query ID
                if len(fields) >= 11:
                    result['rack_pos'] = fields[10].strip()  # QRD-10: rack^pos
                if len(fields) >= 12:
                    result['dilution'] = fields[11].strip() or 'N'  # QRD-11: dilution

            elif line.startswith('QRF|'):
                result['qrf_line'] = line

        # Fallback: agar QRD da barcode bo'lmasa, xabar ichidan raqam qidirish
        if not result['sample_id']:
            for line in lines:
                if line.startswith('QRD|'):
                    # QRD-8 bo'sh bo'lsa, OTH yoki boshqa joyda bo'lishi mumkin
                    pass

        return result
    except Exception as e:
        log_error(f"QRY parse xatosi: {e}")
        return None


def query_patient_by_sample(sample_id):
    """Sample ID (barcode) orqali bemor va buyurtma qilingan tahlillarni topish"""
    if not sample_id or not sample_id.strip():
        return None

    try:
        with closing(db()) as conn:
            with closing(conn.cursor(pymysql.cursors.DictCursor)) as c:
                query = """
                    SELECT
                        b.id as bemor_id,
                        b.ism,
                        b.familiya,
                        COALESCE(b.fish, CONCAT(COALESCE(b.familiya,''), ' ', COALESCE(b.ism,''))) as fish,
                        b.yosh,
                        b.jins,
                        b.tugilgan_sana,
                        b.telefon,
                        b.shifokor,
                        o.id as order_id,
                        o.sample_id,
                        o.created_at,
                        o.sana_vaqt
                    FROM orders o
                    JOIN bemorlar b ON o.bemor_id = b.id
                    WHERE o.sample_id = %s
                    ORDER BY o.id DESC
                    LIMIT 1
                """
                c.execute(query, (sample_id.strip(),))
                patient = c.fetchone()

                if not patient:
                    return None

                # Buyurtma qilingan BIO guruh tahlillari (BK-280 faqat biokimyo)
                query_tests = """
                    SELECT t.id as test_id, t.kod, t.nomi, t.birlik,
                           tn.norma_min, tn.norma_max, tn.norma_text,
                           t.sample as guruh
                    FROM order_items oi
                    JOIN tahlillar t ON oi.tahlil_id = t.id
                    LEFT JOIN tahlillar_norma tn ON tn.tahlil_id = t.id
                    WHERE oi.order_id = %s
                    ORDER BY oi.id
                """
                c.execute(query_tests, (patient['order_id'],))
                tests = c.fetchall()

                return {"patient": patient, "tests": tests}
    except Exception as e:
        log_error(f"Bemor qidirishda xato: {e}")
        return None


def build_qck_response(query_meta, data_found):
    """
    QCK^Q02 — QRY ga dastlabki javob.
    data_found=True → QAK|SR|OK, data_found=False → QAK|SR|NF
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    ctrl_id = query_meta.get('msh_control_id', '1')

    msh = f"MSH|^~\\&|LIS||BIOBASE|BK-280|{ts}||QCK^Q02|{ctrl_id}|P|2.3.1|||||ASCII|||"
    msa = f"MSA|AA|{ctrl_id}|Message accepted|||0|"
    err = "ERR|0|"
    qak_status = "OK" if data_found else "NF"
    qak = f"QAK|SR|{qak_status}|"

    msg = "\r".join([msh, msa, err, qak]) + "\r"
    return mllp_wrap(msg)


def build_dsr_response(query_meta, data, is_last=True):
    """
    DSR^Q03 — bemor/tahlil ma'lumotlarini BK-280 ga yuborish.
    29 ta DSP segment + har bir tahlil uchun qo'shimcha DSP.

    DSP[1]=Admission Number, [2]=Bed Number, [3]=Patient Name,
    [4]=Date of Birth (YYYYMMDDHHMMSS), [5]=Sex (M/F/O),
    [6]=Blood Type, [7]=Race, [8]=Address, [9]=County Code,
    [10]=Home Phone, [11]=Business Phone, [12]=Language,
    [13]=Marital Status, [14]=Religion, [15]=Patient Account (outpatient/inpatient),
    [16]=SSN, [17]=Driver License (own/insurance), [18]=Ethnic Group,
    [19]=Birth Place, [20]=Nationality, [21]=Bar Code,
    [22]=Sample ID (int), [23]=Sample Time (YYYYMMDDHHMMSS),
    [24]=Is Emergency (Y/N), [25]=Collection Volume,
    [26]=Sample Type (serum/plasma/urine), [27]=Fetch Doctor,
    [28]=Fetch Department, [29+]=Test ID^Test Name^Unit^Normal Range
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    ctrl_id = query_meta.get('msh_control_id', '1')
    query_id = query_meta.get('query_id', '1')

    msh = f"MSH|^~\\&|LIS||BIOBASE|BK-280|{ts}||DSR^Q03|{ctrl_id}|P|2.3.1|||||ASCII|||"
    msa = f"MSA|AA|{ctrl_id}|Message accepted|||0|"
    err = "ERR|0|"
    qak = "QAK|SR|OK|"

    # QRD va QRF — BK-280 yuborgan qiymatlarni qaytarish
    qrd_line = query_meta.get('qrd_line', '')
    qrf_line = query_meta.get('qrf_line', '')
    if not qrd_line:
        barcode = query_meta.get('sample_id', '')
        qrd_line = f"QRD|{ts}|R|D|{query_id}|||RD|{barcode}|OTH|||T|"
    if not qrf_line:
        qrf_line = f"QRF|BK-280|{ts[:8]}000000|{ts}|||RCT|COR|ALL|"

    patient = data['patient']
    tests = data['tests']

    # Bemor ma'lumotlari
    fish = patient.get('fish', '') or f"{patient.get('familiya', '')} {patient.get('ism', '')}"
    fish = fish.strip()

    # Tug'ilgan sana
    birth_date = ''
    tug_sana = patient.get('tugilgan_sana', '')
    if tug_sana:
        try:
            if hasattr(tug_sana, 'strftime'):
                birth_date = tug_sana.strftime('%Y%m%d') + '000000'
            elif isinstance(tug_sana, str):
                clean = tug_sana.replace('-', '').replace('/', '').replace('.', '')[:8]
                birth_date = clean + '000000'
        except:
            pass

    # Jins
    jins = patient.get('jins', '') or ''
    if 'erkak' in jins.lower() or jins.upper() == 'M':
        gender = 'M'
    elif 'ayol' in jins.lower() or jins.upper() == 'F':
        gender = 'F'
    else:
        gender = 'O'

    telefon = patient.get('telefon', '') or ''
    shifokor = patient.get('shifokor', '') or ''
    barcode = str(patient.get('sample_id', ''))

    # Sample ID (order_id)
    order_id = str(patient.get('order_id', ''))

    # Sample time
    sample_time = ''
    created = patient.get('sana_vaqt') or patient.get('created_at')
    if created:
        try:
            if hasattr(created, 'strftime'):
                sample_time = created.strftime('%Y%m%d%H%M%S')
            elif isinstance(created, str):
                sample_time = created.replace('-', '').replace(':', '').replace(' ', '').replace('T', '')[:14]
        except:
            pass

    # 29 DSP segmentlar — BK-280 standart tartibda
    dsp_data = [
        '',              # 1: Admission Number
        '',              # 2: Bed Number
        fish,            # 3: Patient Name
        birth_date,      # 4: Date of Birth
        gender,          # 5: Sex
        '',              # 6: Blood Type
        '',              # 7: Race
        '',              # 8: Patient Address
        '',              # 9: County Code
        telefon,         # 10: Home Phone Number
        '',              # 11: Business Phone Number
        '',              # 12: Primary Language
        '',              # 13: Marital Status
        '',              # 14: Religion
        '',              # 15: Patient Account Number
        '',              # 16: Social Security Number
        '',              # 17: Driver License Number
        '',              # 18: Ethnic Group
        '',              # 19: Birth Place
        '',              # 20: Nationality
        barcode,         # 21: Bar Code
        order_id,        # 22: Sample ID (int)
        sample_time,     # 23: Sample Time
        'N',             # 24: Is Emergency
        '',              # 25: Collection Volume
        'serum',         # 26: Sample Type
        shifokor,        # 27: Fetch Doctor
        '',              # 28: Fetch Department
    ]

    # DSP segmentlarni yaratish
    segments = [msh, msa, err, qak, qrd_line, qrf_line]

    for i, value in enumerate(dsp_data, start=1):
        segments.append(f"DSP|{i}||{value}|||")

    # Tahlillar — har biri alohida DSP (29 dan keyin)
    dsp_idx = len(dsp_data) + 1
    for test in tests:
        test_id = str(test.get('kod', '') or test.get('test_id', ''))
        test_name = test.get('nomi', '') or ''
        unit = test.get('birlik', '') or ''
        # Normal range
        norma = ''
        nmin = test.get('norma_min')
        nmax = test.get('norma_max')
        ntext = test.get('norma_text', '') or ''
        if nmin is not None and nmax is not None:
            norma = f"{nmin}-{nmax}"
        elif ntext:
            norma = ntext

        # Format: TestID^TestName^Unit^NormalRange
        test_info = f"{test_id}^{test_name}^{unit}^{norma}"
        segments.append(f"DSP|{dsp_idx}||{test_info}|||")
        dsp_idx += 1

    # DSC — continuation pointer (bo'sh = oxirgi/yagona namuna)
    dsc_value = '' if is_last else str(ctrl_id)
    segments.append(f"DSC|{dsc_value}|")

    msg = "\r".join(segments) + "\r"
    return mllp_wrap(msg)


def build_ack_r01(msh_control_id, ack_code="AA", text_msg="Message accepted", error_code="0"):
    """ACK^R01 — ORU^R01 ga javob"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    msh = f"MSH|^~\\&|LIS||BIOBASE|BK-280|{ts}||ACK^R01|{msh_control_id}|P|2.3.1||||0||ASCII|||"
    msa = f"MSA|{ack_code}|{msh_control_id}|{text_msg}|||{error_code}|"
    msg = "\r".join([msh, msa]) + "\r"
    return mllp_wrap(msg)


def handle_client(conn, addr):
    """Bitta klient ulanishini qayta ishlash"""
    print(f"[BK-280 LIS] Ulanish: {addr}")
    try:
        conn.settimeout(10)
        full_data = b""

        # Ma'lumot to'plash (MLLP framing: SB...EB CR)
        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                full_data += chunk
                # MLLP end marker
                if EB + CR in full_data:
                    break
            except socket.timeout:
                break

        if not full_data:
            return

        # MLLP framing ni tozalash
        msg_data = full_data
        if msg_data.startswith(SB):
            msg_data = msg_data[1:]
        if EB + CR in msg_data:
            msg_data = msg_data.split(EB + CR)[0]

        text = msg_data.decode('utf-8', errors='ignore')
        print(f"[BK-280 LIS] Qabul qilindi ({len(msg_data)} bytes)")

        # Xabar turini aniqlash
        msg_type = ''
        msh_control_id = '1'
        for line in text.split('\r'):
            if line.startswith('MSH|'):
                fields = line.split('|')
                if len(fields) > 9:
                    msg_type = fields[9].strip()  # MSH-9: Message Type
                if len(fields) > 10:
                    msh_control_id = fields[10].strip() or '1'
                break

        print(f"[BK-280 LIS] Xabar turi: {msg_type}")

        # ═══════════════════════════════════════════════
        # QRY^Q02 — Barcode scan so'rovi
        # ═══════════════════════════════════════════════
        if msg_type == 'QRY^Q02':
            query_meta = parse_qry_message(msg_data)
            if not query_meta or not query_meta.get('sample_id'):
                print("[BK-280 LIS] Sample ID topilmadi QRY xabardan")
                # NF javob
                qck = build_qck_response({'msh_control_id': msh_control_id}, False)
                conn.sendall(qck)
                return

            sample_id = query_meta['sample_id']
            print(f"[BK-280 LIS] Barcode qidirilmoqda: {sample_id}")

            # Bazadan bemor qidirish
            data = query_patient_by_sample(sample_id)

            if not data:
                print(f"[BK-280 LIS] Bemor topilmadi: {sample_id}")
                qck = build_qck_response(query_meta, False)
                conn.sendall(qck)
                return

            patient = data['patient']
            fish = patient.get('fish', '') or ''
            print(f"[BK-280 LIS] Bemor topildi: {fish}")
            print(f"[BK-280 LIS] Tahlillar soni: {len(data['tests'])}")

            # 1-qadam: QCK^Q02 yuborish (acknowledgment)
            qck = build_qck_response(query_meta, True)
            conn.sendall(qck)
            print(f"[BK-280 LIS] QCK^Q02 yuborildi (OK)")

            # Kichik pauza (analyzer javobni qayta ishlashi uchun)
            time.sleep(0.1)

            # 2-qadam: DSR^Q03 yuborish (bemor ma'lumotlari)
            dsr = build_dsr_response(query_meta, data, is_last=True)
            conn.sendall(dsr)
            print(f"[BK-280 LIS] DSR^Q03 yuborildi ({len(dsr)} bytes)")

            # 3-qadam: ACK^Q03 ni kutish (ixtiyoriy)
            try:
                conn.settimeout(5)
                ack_data = conn.recv(4096)
                if ack_data:
                    print(f"[BK-280 LIS] ACK qabul qilindi ({len(ack_data)} bytes)")
            except socket.timeout:
                print("[BK-280 LIS] ACK kutilmadi (timeout) — bu normal")

        # ═══════════════════════════════════════════════
        # ORU^R01 — Natija yuborish (bu bk280_listener.py da ishlanadi)
        # ═══════════════════════════════════════════════
        elif msg_type == 'ORU^R01':
            print("[BK-280 LIS] ORU^R01 qabul qilindi — ACK qaytarilmoqda")
            ack = build_ack_r01(msh_control_id)
            conn.sendall(ack)

        # ═══════════════════════════════════════════════
        # ACK^Q03 — DSR javobiga tasdiqlash
        # ═══════════════════════════════════════════════
        elif msg_type == 'ACK^Q03':
            print(f"[BK-280 LIS] ACK^Q03 qabul qilindi")

        else:
            print(f"[BK-280 LIS] Noma'lum xabar turi: {msg_type}")
            # Umumiy ACK qaytarish
            ack = build_ack_r01(msh_control_id, "AR", "Unsupported message type", "200")
            conn.sendall(ack)

    except socket.timeout:
        print("[BK-280 LIS] Timeout")
    except Exception as e:
        log_error(f"Klient xatosi: {e}")
        print(f"[BK-280 LIS] Xato: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except:
            pass


# ═══════════════════════════════════════════════════════
# Thread-safe server (monoblok_dastur.py dan chaqirish uchun)
# ═══════════════════════════════════════════════════════

def start_lis_server(host=None, port=None):
    """
    BK-280 LIS Query Server ni thread da ishga tushirish.
    Returns: Thread object yoki None
    """
    global _lis_server_socket, _lis_running

    if _lis_running:
        print("[OGOHLANTIRISH] BK-280 LIS server allaqachon ishlamoqda")
        return None

    server_host = host or SERVER_IP
    server_port = port or SERVER_PORT

    def server_thread():
        global _lis_server_socket, _lis_running

        try:
            _lis_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _lis_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _lis_server_socket.bind((server_host, server_port))
            _lis_server_socket.listen(5)
            _lis_running = True

            print(f"[OK] BK-280 LIS Server ishga tushdi: {server_host}:{server_port}")
            print(f"     QRY^Q02 barcode so'rovlarini kutmoqda...")

            while _lis_running:
                try:
                    _lis_server_socket.settimeout(1.0)
                    conn, addr = _lis_server_socket.accept()
                    # Har bir ulanishni alohida thread da ishlash
                    t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except socket.timeout:
                    continue
                except OSError:
                    if _lis_running:
                        raise
                    break

        except Exception as e:
            print(f"[XATO] BK-280 LIS server: {e}")
            log_error(f"LIS server thread xatosi: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _lis_running = False
            if _lis_server_socket:
                try:
                    _lis_server_socket.close()
                except:
                    pass
                _lis_server_socket = None
            print("[INFO] BK-280 LIS server to'xtatildi")

    thread = threading.Thread(target=server_thread, daemon=True)
    thread.start()
    return thread


def stop_lis_server():
    """BK-280 LIS server ni to'xtatish"""
    global _lis_server_socket, _lis_running

    _lis_running = False
    if _lis_server_socket:
        try:
            _lis_server_socket.close()
        except:
            pass
        _lis_server_socket = None


# ═══════════════════════════════════════════════════════
# Standalone ishga tushirish (test uchun)
# ═══════════════════════════════════════════════════════

def main():
    """Standalone test server"""
    print("=" * 60)
    print(f"BK-280 LIS Server (HL7 QRY^Q02 Handler) v2.0")
    print(f"Port: {SERVER_IP}:{SERVER_PORT}")
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    thread = start_lis_server()
    if thread:
        try:
            thread.join()
        except KeyboardInterrupt:
            print("\nTo'xtatilmoqda...")
            stop_lis_server()


if __name__ == "__main__":
    main()
