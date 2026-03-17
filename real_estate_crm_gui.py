import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import date
import webbrowser
import urllib.parse


DB_NAME = "real_estate_crm.db"


class RealEstateCRM:
    def __init__(self, root):
        self.root = root
        self.root.title("مكتب العقارات - CRM كامل مع واتساب والتفاصيل")
        self.root.geometry("1400x800")
        
        self.request_types = ["شراء", "بيع", "إيجار", "تأجير"]
        self.status_types = ["قيد التنفيذ", "تم"]
        self.property_types = [
            "أرض سكنية", "أرض تجارية", "أرض زراعية", "أرض صناعية",
            "شقة", "دور", "رووف", "فيلا", "فيلا وشقق",
            "عمارة سكنية", "عمارة تجارية", "محل"
        ]
        self.sort_col = None
        self.sort_desc = False
        
        self.init_db()
        self.create_widgets()
        self.refresh_list()
        self.tree.bind("<Button-1>", self.on_whatsapp_click)

    def init_db(self):
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                request_type TEXT,
                property_type TEXT,
                request TEXT NOT NULL,
                price REAL,
                date_added TEXT NOT NULL,
                notes TEXT,
                status TEXT
            )
        """)
        # إضافة الأعمدة إذا لم تكن موجودة
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN request_type TEXT")
        except:
            pass
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN status TEXT")
        except:
            pass
        try:
            cur.execute("ALTER TABLE clients ADD COLUMN property_type TEXT")
        except:
            pass
        conn.commit()
        conn.close()

    def create_widgets(self):
        # شريط أدوات
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=10, pady=5)
        self.create_search_frame()
        ttk.Button(toolbar, text="🔄 تحديث",
                   command=self.refresh_list).pack(side="left", padx=5)
        
        # نموذج الإدخال
        form_frame = ttk.LabelFrame(self.root, text="عميل / تعديل", padding=10)
        form_frame.pack(fill="x", padx=10, pady=5)

        self.vars = {}
        fields = [("الاسم:", "name_var", 14), ("الهاتف:", "phone_var", 14),
                  ("نوع الطلب:", "request_type_var", None),
                  ("نوع العقار:", "property_type_var", None),
                  ("الطلب:", "request_var", 14),
                  ("السعر:", "price_var", 12), ("الحالة:", "status_var", None),
                  ("ملاحظات:", "notes_var", 30)]

        row = 0
        for label, var_name, width in fields:
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            
            if var_name == "request_type_var":
                var = tk.StringVar(value="")
                combo = ttk.Combobox(form_frame, textvariable=var, values=self.request_types,
                                     state="readonly", width=12)
                self.request_type_combo = combo
            elif var_name == "property_type_var":
                var = tk.StringVar(value="")
                combo = ttk.Combobox(form_frame, textvariable=var, values=self.property_types,
                                     state="readonly", width=14)
                self.property_type_combo = combo
            elif var_name == "status_var":
                var = tk.StringVar(value="")
                combo = ttk.Combobox(form_frame, textvariable=var, values=self.status_types,
                                     state="readonly", width=12)
                self.status_combo = combo
            else:
                var = tk.StringVar()
                ttk.Entry(form_frame, textvariable=var, width=width or 20
                          ).grid(row=row, column=1, columnspan=3, sticky="ew", pady=2)
            
            if var_name in ["request_type_var", "property_type_var", "status_var"]:
                combo.grid(row=row, column=1, sticky="w", pady=2)
            setattr(self, var_name, var)
            self.vars[var_name] = var
            row += 1

        form_frame.grid_columnconfigure(1, weight=1)

        btn_row = row
        ttk.Button(form_frame, text="➕ إضافة", command=self.add_client, width=10).grid(row=btn_row, column=0, pady=10)
        ttk.Button(form_frame, text="✏️ تحديث", command=self.update_client, width=10).grid(row=btn_row, column=1, pady=10)
        ttk.Button(form_frame, text="🗑️ حذف", command=self.delete_client, width=10).grid(row=btn_row, column=2, pady=10)
        ttk.Button(form_frame, text="🧹 مسح", command=self.clear_inputs, width=10).grid(row=btn_row, column=3, pady=10)

        # إطار رسالة واتساب الموحدة
        wa_frame = ttk.LabelFrame(self.root, text="💬 رسالة واتساب موحدة", padding=10)
        wa_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(wa_frame, text="نص الرسالة:").grid(row=0, column=0, sticky="nw")

        # صندوق نص متعدد الأسطر للرسالة
        self.whatsapp_text = tk.Text(wa_frame, height=3, width=60)
        self.whatsapp_text.grid(row=0, column=1, sticky="ew", padx=5)

        wa_frame.grid_columnconfigure(1, weight=1)

        # زر إرسال للصفوف المحددة
        ttk.Button(
            wa_frame,
            text="💬 إرسال للصفوف المحددة",
            command=self.whatsapp_to_selected
        ).grid(row=0, column=2, padx=10, sticky="n")

        # ✅ الجدول - إنشاء Treeview أولاً
        list_frame = ttk.LabelFrame(self.root, text="العملاء (💬=واتساب | انقر للترتيب)", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("ID", "الاسم", "الهاتف", "نوع الطلب", "نوع العقار", "الطلب", "السعر", "التاريخ", "الحالة", "واتساب")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=22,
            selectmode="extended"  # ✅ يسمح بتحديد عدة صفوف
        )

        # عرض الأعمدة
        self.tree.column("#0", width=0, stretch=False)
        self.tree.column("ID", width=55)
        self.tree.column("الاسم", width=110)
        self.tree.column("الهاتف", width=125)
        self.tree.column("نوع الطلب", width=75)
        self.tree.column("نوع العقار", width=110)
        self.tree.column("الطلب", width=130)
        self.tree.column("السعر", width=75)
        self.tree.column("التاريخ", width=90)
        self.tree.column("الحالة", width=90, anchor="center")
        self.tree.column("واتساب", width=75, anchor="center")

        # ✅ إعداد الألوان بعد إنشاء self.tree
        self.setup_tree_tags()

        # رؤوس الترتيب
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))

        # scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ربط الأحداث
        self.tree.bind("<Button-1>", self.on_whatsapp_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def setup_tree_tags(self):
        """✅ إعداد ألوان الحالات للصفوف"""
        # تم - أخضر
        self.tree.tag_configure("status-completed", background="#d4edda", foreground="#155724")
        # قيد التنفيذ - أصفر
        self.tree.tag_configure("status-pending", background="#fff3cd", foreground="#856404")
        # حالة فارغة - افتراضي
        self.tree.tag_configure("status-empty", background="white", foreground="black")

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if selected:
            values = self.tree.item(selected[0])['values']
            self.name_var.set(values[1])
            self.phone_var.set(values[2])
            self.request_type_var.set(values[3])
            self.property_type_var.set(values[4])
            self.request_var.set(values[5])
            self.price_var.set(str(values[6]) if values[6] else "")
            self.status_var.set(values[8])
            self.notes_var.set("")

    def on_whatsapp_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        column = self.tree.identify_column(event.x)

        # واتساب (العمود #10)
        if column == "#10":
            values = self.tree.item(item)['values']
            phone = values[2]
            # استخدام نفس الدالة مع رسالة فارغة
            self.open_whatsapp_with_message(phone, "")
            return

        # ملء النموذج
        values = self.tree.item(item)['values']
        self.name_var.set(values[1])
        self.phone_var.set(values[2])
        self.request_type_var.set(values[3])
        self.property_type_var.set(values[4])
        self.request_var.set(values[5])
        self.price_var.set(str(values[6]) if values[6] else "")
        self.status_var.set(values[8])

    def sort_column(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False
        self.refresh_list()

    def get_sort_sql(self):
        if not self.sort_col:
            return "ORDER BY id DESC"

        order = "DESC" if self.sort_desc else "ASC"
        col_map = {
            "ID": "id", "الاسم": "name", "الهاتف": "phone",
            "نوع الطلب": "request_type", "نوع العقار": "property_type",
            "الطلب": "request", "السعر": "price",
            "التاريخ": "date_added", "الحالة": "status"
        }
        db_col = col_map.get(self.sort_col, "id")

        if db_col == "price":
            return f"ORDER BY {db_col} IS NULL, {db_col} {order}"
        elif db_col == "date_added":
            return f"ORDER BY {db_col} {order}"
        else:
            return f"ORDER BY {db_col} {order}"

    def add_client(self):
        self.save_client('add')

    def update_client(self):
        self.save_client('update')

    def save_client(self, mode):
        if not self.phone_var.get():
            return messagebox.showerror("خطأ", "الهاتف مطلوب")

        phone = self.phone_var.get().strip()
        name = self.name_var.get().strip()
        request_type = self.request_type_var.get()
        property_type = self.property_type_var.get()
        request = self.request_var.get().strip()
        price = float(self.price_var.get()) if self.price_var.get().strip() else None
        status = self.status_var.get()
        notes = self.notes_var.get().strip()

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        try:
            if mode == 'add':
                cur.execute("""
                    INSERT INTO clients (name, phone, request_type, property_type, request, price, date_added, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, phone, request_type, property_type, request, price, date.today().isoformat(), notes, status))
            else:
                client_id = self.tree.item(self.tree.selection()[0])['values'][0]
                cur.execute("""
                    UPDATE clients SET name=?, request_type=?, property_type=?, request=?, price=?, notes=?, status=?
                    WHERE id=?
                """, (name, request_type, property_type, request, price, notes, status, client_id))
            conn.commit()
            messagebox.showinfo("نجح", f"تم {mode}")
            self.clear_inputs()
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("خطأ", str(e))
        finally:
            conn.close()

    def delete_client(self):
        if not self.tree.selection():
            return messagebox.showerror("خطأ", "اختر عميلاً")
        if messagebox.askyesno("تأكيد", "حذف العميل؟"):
            client_id = self.tree.item(self.tree.selection()[0])['values'][0]
            conn = sqlite3.connect(DB_NAME)
            conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
            conn.commit()
            conn.close()
            self.clear_inputs()
            self.refresh_list()

    def clear_inputs(self):
        self.name_var.set("")
        self.phone_var.set("")
        self.request_type_var.set("")
        self.property_type_var.set("")
        self.request_var.set("")
        self.price_var.set("")
        self.status_var.set("")
        self.notes_var.set("")

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        sql = f"SELECT id, name, phone, request_type, property_type, request, price, date_added, status FROM clients {self.get_sort_sql()}"
        cur.execute(sql)

        for row in cur.fetchall():
            property_display = row[4] or ""
            status_display = row[8] or ""
            price_display = f"{row[6]:,.0f}" if row[6] else ""
            
            # ✅ تحديد tag حسب الحالة
            status_tag = "status-empty"
            if status_display == "تم":
                status_tag = "status-completed"
            elif status_display == "قيد التنفيذ":
                status_tag = "status-pending"
            
            self.tree.insert("", "end", values=(
                row[0], row[1], row[2], row[3], property_display,
                row[5], price_display, row[7], status_display, "💬"
            ), tags=(status_tag,))
        conn.close()

    def open_whatsapp_with_message(self, phone, message):
        phone_clean = ''.join(c for c in str(phone) if c.isdigit())
        if phone_clean.startswith('0'):
            phone_intl = '966' + phone_clean[1:]
        elif phone_clean.startswith('966'):
            phone_intl = phone_clean
        else:
            phone_intl = '966' + phone_clean

        text_param = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{phone_intl}?text={text_param}"
        webbrowser.open_new_tab(whatsapp_url)
        print(f"✅ واتساب (مع رسالة): {phone_intl}")

    def create_search_frame(self):
        search_frame = ttk.LabelFrame(self.root, text="🔍 البحث السريع", padding=10)
        search_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(search_frame, text="الاسم:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.search_name_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_name_var, width=15).grid(row=0, column=1, padx=5)

        ttk.Label(search_frame, text="الهاتف:").grid(row=0, column=2, sticky="w", padx=(10, 5))
        self.search_phone_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_phone_var, width=15).grid(row=0, column=3, padx=5)

        ttk.Label(search_frame, text="نوع الطلب:").grid(row=0, column=4, sticky="w", padx=(10, 5))
        self.search_request_var = tk.StringVar()
        ttk.Combobox(search_frame, textvariable=self.search_request_var, values=[""] + self.request_types,
                     state="readonly", width=10).grid(row=0, column=5, padx=5)

        ttk.Label(search_frame, text="نوع العقار:").grid(row=0, column=6, sticky="w", padx=(10, 5))
        self.search_property_var = tk.StringVar()
        ttk.Combobox(search_frame, textvariable=self.search_property_var, values=[""] + self.property_types,
                     state="readonly", width=12).grid(row=0, column=7, padx=5)

        ttk.Label(search_frame, text="الحالة:").grid(row=0, column=8, sticky="w", padx=(10, 5))
        self.search_status_var = tk.StringVar()
        ttk.Combobox(search_frame, textvariable=self.search_status_var, values=[""] + self.status_types,
                     state="readonly", width=10).grid(row=0, column=9, padx=5)

        ttk.Button(search_frame, text="🔍 بحث", command=self.search_clients, width=8).grid(row=0, column=10, padx=10)
        ttk.Button(search_frame, text="🧹 كل العملاء", command=self.refresh_list, width=12).grid(row=0, column=11, padx=5)

    def search_clients(self):
        """البحث في العملاء حسب الحقول المملوءة"""
        self.refresh_list()  # إعادة تحميل كامل أولاً

        # فلترة النتائج حسب الحقول المملوءة فقط
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']

            name_match = not self.search_name_var.get() or self.search_name_var.get().lower() in values[1].lower()
            phone_match = not self.search_phone_var.get() or self.search_phone_var.get() in values[2]
            request_match = not self.search_request_var.get() or self.search_request_var.get() == values[3]
            property_match = not self.search_property_var.get() or self.search_property_var.get() == values[4]
            status_match = not self.search_status_var.get() or self.search_status_var.get() == values[8]

            if not (name_match and phone_match and request_match and property_match and status_match):
                self.tree.detach(item)

    def clear_search(self):
        """مسح حقول البحث"""
        self.search_name_var.set("")
        self.search_phone_var.set("")
        self.search_request_var.set("")
        self.search_property_var.set("")
        self.search_status_var.set("")
        self.refresh_list()

    def whatsapp_to_selected(self):
        """إرسال نص الرسالة في الصندوق إلى كل العملاء المحددين في الجدول"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showerror("خطأ", "اختر عميلًا واحدًا على الأقل من الجدول")
            return

        msg = self.whatsapp_text.get("1.0", "end").strip()
        if not msg:
            messagebox.showerror("خطأ", "اكتب نص الرسالة أولاً")
            return

        for item in selected_items:
            values = self.tree.item(item)["values"]
            phone = values[2]
            self.open_whatsapp_with_message(phone, msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = RealEstateCRM(root)
    root.mainloop()
