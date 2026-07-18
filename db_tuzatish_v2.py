"""
AzizMedLine — Baza Tuzatish Vositasi (Yaxshilangan)
Tahlillar_norma jadvalini ko'rish, tahrirlash va tuzatish
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import mysql.connector

DB_CONFIG = {
    "host": "labserver",
    "user": "lims",
    "password": "azizmed2026",
    "database": "lab_tizim",
    "port": 3306
}

# ============================================================
# TAYYOR SQL TUZATISHLAR — zarur bo'lganda bosing
# Har bir tugma bitta muammoni hal qiladi
# ============================================================
TAYYOR_SQLLAR = {
    "🔍 Barcha norma ko'rish": """SELECT id, tahlil_nomi, guruh, type,
       norma, birlik, response_options,
       COALESCE(standard_blank_path,'') as standard_blank_path
FROM tahlillar_norma
ORDER BY guruh, tahlil_nomi;""",

    "⚠️ D: disk yo'llarini ko'rish": """SELECT id, tahlil_nomi, standard_blank_path
FROM tahlillar_norma
WHERE standard_blank_path LIKE 'D:%';""",

    "🔧 D: → G: disk yo'lini almashtirish": """UPDATE tahlillar_norma
SET standard_blank_path = REPLACE(
    standard_blank_path,
    'D:/Monoblokdagi kodlar/URIT 50/Standart shablaonlar/',
    'G:/DASTUR/URIT 50/Standart shablaonlar/'
)
WHERE standard_blank_path LIKE 'D:%';""",

    "➕ RW sifilis qo'shish": """INSERT INTO tahlillar_norma
    (guruh, tahlil_nomi, norma, birlik, type, response_options)
VALUES
    ('TEST', 'RW sifilis (ekspress)', 'Manfiy (-)', '', 'positive_negative', 'Manfiy (-),Musbat (+)')
ON DUPLICATE KEY UPDATE
    norma = 'Manfiy (-)', birlik = '',
    type = 'positive_negative',
    response_options = 'Manfiy (-),Musbat (+)';""",

    "➕ Gepatit C qo'shish": """INSERT INTO tahlillar_norma
    (guruh, tahlil_nomi, norma, birlik, type, response_options)
VALUES
    ('TEST', 'Gepatit C (HCV-Ab, ekspress)', 'Manfiy (-)', '', 'positive_negative', 'Manfiy (-),Musbat (+)')
ON DUPLICATE KEY UPDATE
    norma = 'Manfiy (-)', birlik = '',
    type = 'positive_negative',
    response_options = 'Manfiy (-),Musbat (+)';""",

    "🔧 Qon guruhi type tuzatish": """UPDATE tahlillar_norma
SET type = 'blood_group',
    norma = 'Har qanday qiymat norma hisoblanadi'
WHERE tahlil_nomi LIKE '%qon guruhi%'
   OR tahlil_nomi LIKE '%Qon guruhi%';""",

    "🔧 Ginekologik type tuzatish": """UPDATE tahlillar_norma
SET type = 'ginekologik', norma = '', birlik = '', response_options = '',
    standard_blank_path = 'G:/DASTUR/URIT 50/Standart shablaonlar/GINEKOLOGIK SURTMA.docx'
WHERE tahlil_nomi = 'Ginekologik surtma';""",

    "🔧 Gepatit B response_options": """UPDATE tahlillar_norma
SET response_options = 'Manfiy (-),Musbat (+)',
    type = 'positive_negative', birlik = ''
WHERE tahlil_nomi = 'Gepatit B (HBsAg, ekspress)';""",

    "🔍 Test_results ko'rish": """SELECT order_id, test_name, test_type, status,
       LEFT(result_data, 80) as natija_qisqa
FROM test_results
ORDER BY id DESC
LIMIT 20;""",

    "🧹 Barcha test_results o'chirish": """DELETE FROM test_results
WHERE order_id IN (
    SELECT id FROM orders WHERE id > 0
);
-- EHTIYOT: Bu barcha saqlangan natijalarni o'chiradi!""",
}


def db_conn():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        messagebox.showerror("DB Xato", f"Ulanishda xato:\n{e}")
        return None


class DBTuzatish:
    def __init__(self, root):
        self.root = root
        self.root.title("AzizMedLine — Baza Tuzatish Vositasi v2")
        self.root.geometry("1400x800")
        self.root.configure(bg="#f0f4f8")
        self.build_ui()
        self.yuklash()

    def build_ui(self):
        # Sarlavha
        tk.Label(self.root, text="🔧 Tahlillar Norma Bazasini Boshqarish",
                 font=("Arial", 15, "bold"), bg="#1a3c5e", fg="white",
                 pady=12).pack(fill="x")

        main = tk.Frame(self.root, bg="#f0f4f8")
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # === CHAP PANEL ===
        left = tk.Frame(main, bg="#f0f4f8", width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        # Qidiruv
        tk.Label(left, text="Qidirish:", font=("Arial", 10, "bold"),
                 bg="#f0f4f8").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self.yuklash())
        tk.Entry(left, textvariable=self.search_var, font=("Arial", 11)).pack(fill="x", pady=(0,5))

        # Asosiy tugmalar
        for text, cmd, color in [
            ("🔄 Yangilash", self.yuklash, "#17a2b8"),
            ("➕ Yangi yozuv", self.yangi_qoshish, "#28a745"),
            ("🗑 O'chirish", self.ochirish, "#dc3545"),
        ]:
            tk.Button(left, text=text, command=cmd, bg=color, fg="white",
                      font=("Arial", 10, "bold"), relief="flat",
                      pady=5).pack(fill="x", pady=2)

        # Ajratgich
        tk.Label(left, text="━" * 28, bg="#f0f4f8", fg="#ccc").pack(pady=4)

        # Tayyor SQL tugmalar sarlavhasi
        tk.Label(left, text="⚡ Tayyor SQL Tuzatishlar:",
                 font=("Arial", 9, "bold"), bg="#f0f4f8", fg="#555").pack(anchor="w")

        # Tayyor SQL tugmalar (scrollable)
        sql_btn_canvas = tk.Canvas(left, bg="#f0f4f8", height=200, highlightthickness=0)
        sql_btn_scroll = ttk.Scrollbar(left, orient="vertical",
                                        command=sql_btn_canvas.yview)
        sql_btn_frame = tk.Frame(sql_btn_canvas, bg="#f0f4f8")
        sql_btn_frame.bind("<Configure>",
            lambda e: sql_btn_canvas.configure(
                scrollregion=sql_btn_canvas.bbox("all")))
        sql_btn_canvas.create_window((0, 0), window=sql_btn_frame, anchor="nw")
        sql_btn_canvas.configure(yscrollcommand=sql_btn_scroll.set)
        sql_btn_canvas.pack(side="left", fill="both", expand=True)
        sql_btn_scroll.pack(side="right", fill="y")

        for btn_text, sql in TAYYOR_SQLLAR.items():
            color = "#6f42c1" if "ko'rish" in btn_text else \
                    "#e83e8c" if "o'chirish" in btn_text.lower() else \
                    "#fd7e14" if "almashtirish" in btn_text or "disk" in btn_text else \
                    "#20c997"
            tk.Button(sql_btn_frame, text=btn_text,
                      command=lambda s=sql, t=btn_text: self.tayyor_sql_qo_y(s, t),
                      bg=color, fg="white", font=("Arial", 9),
                      relief="flat", pady=3,
                      anchor="w", wraplength=230).pack(fill="x", pady=1)

        # SQL panel
        tk.Label(left, text="SQL buyruq (ehtiyot bilan!):",
                 font=("Arial", 9, "bold"), bg="#f0f4f8", fg="#888").pack(anchor="w", pady=(8,0))
        self.sql_text = scrolledtext.ScrolledText(left, height=7, font=("Courier", 9), wrap="word")
        self.sql_text.pack(fill="x")

        tk.Button(left, text="▶ SQL Bajar", command=self.sql_bajar,
                  bg="#6f42c1", fg="white", font=("Arial", 11, "bold"),
                  relief="flat", pady=6).pack(fill="x", pady=3)

        self.sql_result = scrolledtext.ScrolledText(left, height=6, font=("Courier", 8),
                                                     wrap="word", state="disabled",
                                                     bg="#1e1e1e", fg="#00ff00")
        self.sql_result.pack(fill="x")

        # === O'NG PANEL ===
        right = tk.Frame(main, bg="#f0f4f8")
        right.pack(side="left", fill="both", expand=True)

        # Jadval
        cols = ["tahlil_nomi", "guruh", "type", "norma", "birlik",
                "response_options", "standard_blank_path"]
        col_labels = ["Tahlil nomi", "Guruh", "Type",
                      "Norma", "Birlik", "Javob variantlari", "Standart blanka yo'li"]
        col_widths = [180, 60, 120, 130, 80, 170, 200]

        tree_frame = tk.Frame(right, bg="#f0f4f8")
        tree_frame.pack(fill="both", expand=True)

        sy = ttk.Scrollbar(tree_frame, orient="vertical")
        sx = ttk.Scrollbar(tree_frame, orient="horizontal")
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")

        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9), rowheight=22)
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   yscrollcommand=sy.set, xscrollcommand=sx.set)
        for col, label, width in zip(cols, col_labels, col_widths):
            self.tree.heading(col, text=label,
                              command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=width, minwidth=40)

        self.tree.tag_configure("toq", background="#e8f4f8")
        self.tree.tag_configure("xato_yo'l", background="#ffe4e4")
        self.tree.pack(fill="both", expand=True)
        sy.config(command=self.tree.yview)
        sx.config(command=self.tree.xview)
        self.tree.bind("<Double-1>", self.tahrirlash)
        self.tree.bind("<Return>", self.tahrirlash)

        # Tahrirlash paneli
        edit_lf = tk.LabelFrame(right,
            text="  ✏️ Tanlangan yozuvni tahrirlash  (Double-click yoki Enter)",
            font=("Arial", 9, "bold"), bg="#f0f4f8", pady=6, padx=10)
        edit_lf.pack(fill="x", pady=(6,0))

        fields = [
            ("tahlil_nomi",      "Tahlil nomi:",                               0, 0, 45),
            ("guruh",            "Guruh (GEM/BIO/TEST/COAG/...):",              0, 2, 18),
            ("type",             "Type (positive_negative / express / blood_group / ginekologik / numeric):", 1, 0, 35),
            ("norma",            "Norma (masalan: Manfiy (-), yoki 25-36.9):",  1, 2, 35),
            ("birlik",           "Birlik (Ед/л, g/l, ...):",                    2, 0, 20),
            ("response_options", "Javob variantlari (vergul bilan: Manfiy (-),Musbat (+)):", 2, 2, 45),
            ("standard_blank_path", "Standart blanka fayl yo'li (G:/DASTUR/...):", 3, 0, 70),
        ]
        self.edit_vars = {}
        for key, label, row, col_start, width in fields:
            tk.Label(edit_lf, text=label, font=("Arial", 8),
                     bg="#f0f4f8", anchor="w").grid(
                row=row, column=col_start, sticky="w", padx=(5,2), pady=2)
            var = tk.StringVar()
            self.edit_vars[key] = var
            colspan = 1
            tk.Entry(edit_lf, textvariable=var, font=("Arial", 9),
                     width=width).grid(row=row, column=col_start+1,
                                       sticky="ew", padx=(0,10), pady=2,
                                       columnspan=colspan)

        edit_lf.columnconfigure(1, weight=1)
        edit_lf.columnconfigure(3, weight=1)

        btn_row = tk.Frame(edit_lf, bg="#f0f4f8")
        btn_row.grid(row=4, column=0, columnspan=4, pady=6)

        for text, cmd, color in [
            ("💾 Saqlash (UPDATE)", self.saqlash,     "#007bff"),
            ("🆕 Yangi (INSERT)",   self.insert_yangi, "#28a745"),
            ("🧹 Tozalash",         self.tozalash,     "#6c757d"),
        ]:
            tk.Button(btn_row, text=text, command=cmd, bg=color, fg="white",
                      font=("Arial", 10, "bold"), relief="flat",
                      padx=18, pady=5).pack(side="left", padx=4)

        # Status bar
        self.status_var = tk.StringVar(value="Tayyor")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Arial", 9), bg="#343a40", fg="#adb5bd",
                 anchor="w", padx=10, pady=3).pack(fill="x", side="bottom")

    # ── Yordamchi: sort ──────────────────────────────────────
    def sort_by(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort()
        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)

    # ── Yuklash ──────────────────────────────────────────────
    def yuklash(self):
        search = self.search_var.get().strip()
        conn = db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor(dictionary=True)
            sql = """SELECT tahlil_nomi, guruh, type, norma, birlik,
                            COALESCE(response_options,'') as response_options,
                            COALESCE(standard_blank_path,'') as standard_blank_path
                     FROM tahlillar_norma"""
            params = []
            if search:
                sql += " WHERE tahlil_nomi LIKE %s"
                params.append(f"%{search}%")
            sql += " ORDER BY guruh, tahlil_nomi"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            for item in self.tree.get_children():
                self.tree.delete(item)
            for i, row in enumerate(rows):
                tag = "xato_yo'l" if (row['standard_blank_path'] or '').startswith('D:') \
                      else ("toq" if i % 2 == 0 else "")
                self.tree.insert("", "end", tags=(tag,), values=(
                    row['tahlil_nomi'], row['guruh'], row['type'],
                    row['norma'], row['birlik'],
                    row['response_options'], row['standard_blank_path']
                ))
            self.status_var.set(f"✅ {len(rows)} ta yozuv. "
                                f"Qizil = D: disk yo'li (tuzatish kerak)")
            cursor.close()
        except Exception as e:
            messagebox.showerror("Xato", str(e))
        finally:
            conn.close()

    # ── Double-click → tahrirlash ─────────────────────────────
    def tahrirlash(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        keys = ["tahlil_nomi","guruh","type","norma","birlik",
                "response_options","standard_blank_path"]
        for key, val in zip(keys, vals):
            self.edit_vars[key].set(str(val) if val else "")
        self.status_var.set(f"Tahrirlash: {vals[0]}")

    # ── Saqlash (UPDATE) ─────────────────────────────────────
    def saqlash(self):
        nom = self.edit_vars["tahlil_nomi"].get().strip()
        if not nom:
            messagebox.showwarning("Diqqat", "Tahlil nomi bo'sh!")
            return
        conn = db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tahlillar_norma WHERE tahlil_nomi=%s", (nom,))
            if not cursor.fetchone():
                if messagebox.askyesno("Topilmadi", f"'{nom}' bazada yo'q.\nYangi qo'shamizmi?"):
                    self.insert_yangi()
                return
            cursor.execute("""
                UPDATE tahlillar_norma SET
                    guruh=%s, type=%s, norma=%s, birlik=%s,
                    response_options=%s, standard_blank_path=%s
                WHERE tahlil_nomi=%s
            """, (
                self.edit_vars["guruh"].get().strip(),
                self.edit_vars["type"].get().strip(),
                self.edit_vars["norma"].get().strip(),
                self.edit_vars["birlik"].get().strip(),
                self.edit_vars["response_options"].get().strip(),
                self.edit_vars["standard_blank_path"].get().strip(),
                nom
            ))
            conn.commit()
            messagebox.showinfo("✅", f"'{nom}' yangilandi!")
            self.status_var.set(f"[OK] '{nom}' saqlandi")
            cursor.close()
            self.yuklash()
        except Exception as e:
            messagebox.showerror("Xato", str(e))
        finally:
            conn.close()

    # ── Yangi qo'shish (INSERT) ──────────────────────────────
    def insert_yangi(self):
        nom = self.edit_vars["tahlil_nomi"].get().strip()
        if not nom:
            messagebox.showwarning("Diqqat", "Tahlil nomini kiriting!")
            return
        conn = db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tahlillar_norma
                    (guruh, tahlil_nomi, norma, birlik,
                     type, response_options, standard_blank_path)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    guruh=VALUES(guruh), type=VALUES(type),
                    norma=VALUES(norma), birlik=VALUES(birlik),
                    response_options=VALUES(response_options),
                    standard_blank_path=VALUES(standard_blank_path)
            """, (
                self.edit_vars["guruh"].get().strip(),
                nom,
                self.edit_vars["norma"].get().strip(),
                self.edit_vars["birlik"].get().strip(),
                self.edit_vars["type"].get().strip(),
                self.edit_vars["response_options"].get().strip(),
                self.edit_vars["standard_blank_path"].get().strip(),
            ))
            conn.commit()
            messagebox.showinfo("✅", f"'{nom}' qo'shildi/yangilandi!")
            self.status_var.set(f"[OK] '{nom}' kiritildi")
            cursor.close()
            self.yuklash()
        except Exception as e:
            messagebox.showerror("Xato", str(e))
        finally:
            conn.close()

    # ── Yangi yozuv uchun bo'sh forma ───────────────────────
    def yangi_qoshish(self):
        self.tozalash()
        self.edit_vars["guruh"].set("TEST")
        self.edit_vars["type"].set("positive_negative")
        self.edit_vars["response_options"].set("Manfiy (-),Musbat (+)")
        self.status_var.set("Yangi yozuv — maydonlarni to'ldiring → 'Yangi (INSERT)' bosing")

    # ── O'chirish ────────────────────────────────────────────
    def ochirish(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Diqqat", "Avval tahlilni tanlang")
            return
        nom = self.tree.item(sel[0])['values'][0]
        if not messagebox.askyesno("O'chirish",
                f"'{nom}' ni o'chiramizmi?\n⚠️ Bu amalni qaytarib bo'lmaydi!"):
            return
        conn = db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tahlillar_norma WHERE tahlil_nomi=%s", (nom,))
            conn.commit()
            messagebox.showinfo("✅", f"'{nom}' o'chirildi")
            cursor.close()
            self.yuklash()
        except Exception as e:
            messagebox.showerror("Xato", str(e))
        finally:
            conn.close()

    # ── Tozalash ─────────────────────────────────────────────
    def tozalash(self):
        for var in self.edit_vars.values():
            var.set("")

    # ── Tayyor SQL ni SQL panelga joylashtirish ──────────────
    def tayyor_sql_qo_y(self, sql, nom):
        self.sql_text.delete("1.0", "end")
        self.sql_text.insert("1.0", sql)
        self.status_var.set(f"SQL yuklandi: {nom} — 'SQL Bajar' tugmasini bosing")

    # ── SQL Bajar ────────────────────────────────────────────
    def sql_bajar(self):
        sql = self.sql_text.get("1.0", "end").strip()
        if not sql:
            return
        # Xavfli amallar uchun ogohlantirish
        if any(w in sql.upper() for w in ["DELETE", "DROP", "TRUNCATE"]):
            if not messagebox.askyesno("⚠️ Xavfli amal",
                    "Bu SQL ma'lumotlarni O'CHIRADI!\nDavom ettirasizmi?"):
                return
        conn = db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            # Bir nechta SQL bo'lsa har birini alohida bajar
            statements = [s.strip() for s in sql.split(';') if s.strip()
                          and not s.strip().startswith('--')]
            output_lines = []
            for stmt in statements:
                if not stmt:
                    continue
                cursor.execute(stmt)
                if stmt.strip().upper().startswith("SELECT"):
                    rows = cursor.fetchall()
                    cols = [d[0] for d in cursor.description]
                    output_lines.append("  ".join(f"{c[:15]:<15}" for c in cols))
                    output_lines.append("─" * 80)
                    for row in rows:
                        output_lines.append("  ".join(f"{str(v)[:15]:<15}" for v in row))
                    output_lines.append(f"\n→ {len(rows)} ta natija")
                else:
                    conn.commit()
                    output_lines.append(f"✅ Bajarildi. Ta'sir: {cursor.rowcount} qator")

            result_text = "\n".join(output_lines)
            self.sql_result.config(state="normal")
            self.sql_result.delete("1.0", "end")
            self.sql_result.insert("1.0", result_text)
            self.sql_result.config(state="disabled")
            self.status_var.set(f"✅ SQL bajarildi ({len(statements)} ta buyruq)")
            cursor.close()
            self.yuklash()
        except Exception as e:
            self.sql_result.config(state="normal")
            self.sql_result.delete("1.0", "end")
            self.sql_result.insert("1.0", f"❌ XATO:\n{e}")
            self.sql_result.config(state="disabled")
            self.status_var.set(f"❌ SQL xatosi: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = DBTuzatish(root)
    root.mainloop()
