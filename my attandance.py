import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import datetime
import re

class ModernAttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Attendance Management System")
        self.root.geometry("1100x720")
        self.root.minsize(920, 640)

        # Handle clean window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Dark Theme Color Palette (Catppuccin Macchiato inspired)
        self.colors = {
            "bg_dark": "#181825",
            "bg_card": "#1e1e2e",
            "bg_input": "#313244",
            "accent": "#89b4fa",
            "accent_hover": "#b4befe",
            "text": "#cdd6f4",
            "text_sub": "#a6adc8",
            "success": "#a6e3a1",
            "danger": "#f38ba8",
            "warning": "#f9e2af",
            "border": "#45475a"
        }

        self.root.configure(bg=self.colors["bg_dark"])

        # Checked state tracker & selection mode flag
        self.checked_logs = {}
        self.selection_mode_active = False

        # Initialize SQLite Database & Styles
        self.init_db()
        self.setup_styles()

        # Build UI Components
        self.create_header()
        self.create_tabs()

        # Initial Data Load
        self.refresh_student_dropdown()
        self.load_students_table()
        self.load_attendance_logs()
        self.update_analytics()

    def init_db(self):
        """Initialize SQLite DB with index optimizations and constraints."""
        self.conn = sqlite3.connect("attendance_system.db")
        self.cursor = self.conn.cursor()

        # Students Table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Migration: is_active column check
        self.cursor.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if "is_active" not in columns:
            self.cursor.execute("ALTER TABLE students ADD COLUMN is_active INTEGER DEFAULT 1")

        # Attendance Table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                day TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL,
                term TEXT DEFAULT '2026-Term1',
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # Attendance Migrations
        self.cursor.execute("PRAGMA table_info(attendance)")
        att_columns = [column[1] for column in self.cursor.fetchall()]
        if "term" not in att_columns:
            self.cursor.execute("ALTER TABLE attendance ADD COLUMN term TEXT DEFAULT '2026-Term1'")
        if "day" not in att_columns:
            self.cursor.execute("ALTER TABLE attendance ADD COLUMN day TEXT DEFAULT ''")

        # Performance Indexes
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(date)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_att_student ON attendance(student_id)")

        self.conn.commit()

    def setup_styles(self):
        """Configure TTK Dark Theme Styles."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=self.colors["bg_dark"])
        style.configure("Card.TFrame", background=self.colors["bg_card"], relief="flat")

        style.configure("TNotebook", background=self.colors["bg_dark"], borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=self.colors["bg_card"],
                        foreground=self.colors["text"],
                        padding=[18, 8],
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", self.colors["accent"])],
                  foreground=[("selected", "#11111b")])

        style.configure("TLabel", background=self.colors["bg_dark"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=self.colors["bg_card"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=self.colors["bg_dark"], foreground=self.colors["text"], font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.Card.TLabel", background=self.colors["bg_card"], foreground=self.colors["accent"], font=("Segoe UI", 11, "bold"))
        style.configure("Metric.Card.TLabel", background=self.colors["bg_card"], foreground=self.colors["warning"], font=("Segoe UI", 14, "bold"))

        # Buttons
        style.configure("Primary.TButton", background=self.colors["accent"], foreground="#11111b", font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[12, 6])
        style.map("Primary.TButton", background=[("active", self.colors["accent_hover"])])

        style.configure("Secondary.TButton", background=self.colors["bg_input"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[10, 6])
        style.configure("Success.TButton", background=self.colors["success"], foreground="#11111b", font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[14, 7])
        style.configure("Danger.TButton", background=self.colors["danger"], foreground="#11111b", font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[12, 6])

        # Form Controls
        style.configure("TEntry", fieldbackground=self.colors["bg_input"], foreground=self.colors["text"], borderwidth=1)
        style.configure("TCombobox", fieldbackground=self.colors["bg_input"], foreground=self.colors["text"], borderwidth=1)
        style.map("TCombobox", fieldbackground=[("readonly", self.colors["bg_input"])],
                               selectbackground=[("readonly", self.colors["bg_input"])],
                               selectforeground=[("readonly", self.colors["text"])])

        # Data Tables
        style.configure("Treeview",
                        background=self.colors["bg_card"],
                        foreground=self.colors["text"],
                        fieldbackground=self.colors["bg_card"],
                        rowheight=32,
                        font=("Segoe UI", 10),
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background=self.colors["bg_input"],
                        foreground=self.colors["accent"],
                        font=("Segoe UI", 10, "bold"),
                        relief="flat",
                        anchor="center")
        style.map("Treeview", background=[("selected", self.colors["border"])], foreground=[("selected", "#ffffff")])

        # Configure tags for day-based row background styling & separators
        self.logs_tree_tags_setup = True

    def create_header(self):
        """Header Banner with System Title, Real-time Clock, and Summary Analytics."""
        header_frame = ttk.Frame(self.root, padding=(25, 15, 25, 10))
        header_frame.pack(fill="x")

        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side="left")
        ttk.Label(title_frame, text="⚡ Attendance Management System", style="Header.TLabel").pack(anchor="w")
        
        # Real-time Summary Analytics
        self.lbl_analytics = ttk.Label(title_frame, text="Active Students: 0 | Today's Logs: 0 | Attendance Rate: 0%", font=("Segoe UI", 9), foreground=self.colors["text_sub"])
        self.lbl_analytics.pack(anchor="w", pady=(3, 0))

        self.time_label = ttk.Label(header_frame, text="", font=("Segoe UI", 10, "italic"), foreground=self.colors["accent"])
        self.time_label.pack(side="right", anchor="n")
        self.update_clock()

    def update_clock(self):
        now = datetime.datetime.now().strftime("%A, %b %d, %Y  |  %I:%M:%S %p")
        self.time_label.config(text=now)
        self.root.after(1000, self.update_clock)

    def update_analytics(self):
        """Recalculate summary metrics for header banner display."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        self.cursor.execute("SELECT COUNT(*) FROM students WHERE is_active = 1")
        total_students = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
        logs_today = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'Present'", (today,))
        presents_today = self.cursor.fetchone()[0]

        rate = round((presents_today / logs_today * 100), 1) if logs_today > 0 else 0.0

        self.lbl_analytics.config(
            text=f"Active Roster: {total_students} | Today Logs: {logs_today} | Daily Present Rate: {rate}%"
        )

    def create_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=25, pady=(0, 20))

        self.tab_attendance = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(self.tab_attendance, text="  Mark Attendance  ")
        self.build_attendance_tab()

        self.tab_students = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(self.tab_students, text="  Student Directory  ")
        self.build_students_tab()

        self.tab_logs = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(self.tab_logs, text="  Logs & Reports  ")
        self.build_logs_tab()

    # --- TAB 1: MARK ATTENDANCE ---
    def build_attendance_tab(self):
        container = ttk.Frame(self.tab_attendance, style="Card.TFrame", padding=30)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Log Daily Attendance", style="SubHeader.Card.TLabel").pack(anchor="w", pady=(0, 20))

        form_frame = ttk.Frame(container, style="Card.TFrame")
        form_frame.pack(fill="x", pady=10)

        ttk.Label(form_frame, text="Select Student:", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=10, padx=(0, 15))
        self.combo_students = ttk.Combobox(form_frame, state="readonly", width=42)
        self.combo_students.grid(row=0, column=1, sticky="w", pady=10)

        ttk.Label(form_frame, text="Attendance Status:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=10, padx=(0, 15))
        self.status_var = tk.StringVar(value="Present")
        
        status_frame = ttk.Frame(form_frame, style="Card.TFrame")
        status_frame.grid(row=1, column=1, sticky="w", pady=10)

        for status_option in ["Present", "Absent", "Late"]:
            rb = tk.Radiobutton(status_frame, text=status_option, value=status_option, variable=self.status_var,
                                bg=self.colors["bg_card"], fg=self.colors["text"],
                                selectcolor=self.colors["bg_input"], activebackground=self.colors["bg_card"],
                                activeforeground=self.colors["accent"], font=("Segoe UI", 10))
            rb.pack(side="left", padx=(0, 20))

        btn_submit = ttk.Button(container, text="Record Attendance", style="Primary.TButton", command=self.record_attendance)
        btn_submit.pack(anchor="w", pady=(25, 0))

    def refresh_student_dropdown(self):
        self.cursor.execute("SELECT student_id, name FROM students WHERE is_active = 1 ORDER BY name ASC")
        students = self.cursor.fetchall()
        self.student_map = {f"{s[1]} (ID: {s[0]})": s[0] for s in students}
        self.combo_students['values'] = list(self.student_map.keys())
        if self.student_map:
            self.combo_students.current(0)
        else:
            self.combo_students.set("")

    def record_attendance(self):
        selected_text = self.combo_students.get()
        if not selected_text:
            messagebox.showwarning("Warning", "Please select an active student first.")
            return

        student_id = self.student_map[selected_text]
        student_name = selected_text.split(" (ID:")[0]
        status = self.status_var.get()
        
        now = datetime.datetime.now()
        day_of_week = now.strftime("%A")
        today_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%I:%M %p")

        self.cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ?", (student_id, today_date))
        if self.cursor.fetchone():
            messagebox.showinfo("Already Logged", f"Attendance for {student_name} on {today_date} has already been recorded.")
            return

        self.cursor.execute("""
            INSERT INTO attendance (student_id, student_name, day, date, time, status, term)
            VALUES (?, ?, ?, ?, ?, ?, '2026-Term1')
        """, (student_id, student_name, day_of_week, today_date, current_time, status))
        self.conn.commit()

        messagebox.showinfo("Success", f"Recorded {student_name} as '{status}'.")
        self.load_attendance_logs()
        self.update_analytics()

    # --- TAB 2: STUDENT DIRECTORY ---
    def build_students_tab(self):
        left_panel = ttk.Frame(self.tab_students, style="Card.TFrame", padding=20)
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 15))

        ttk.Label(left_panel, text="Add / Register Student", style="SubHeader.Card.TLabel").pack(anchor="w", pady=(0, 15))

        ttk.Label(left_panel, text="Student ID:", style="Card.TLabel").pack(anchor="w", pady=(5, 2))
        self.ent_student_id = ttk.Entry(left_panel, width=28)
        self.ent_student_id.pack(anchor="w", pady=(0, 12))

        ttk.Label(left_panel, text="Full Name:", style="Card.TLabel").pack(anchor="w", pady=(5, 2))
        self.ent_student_name = ttk.Entry(left_panel, width=28)
        self.ent_student_name.pack(anchor="w", pady=(0, 12))

        ttk.Label(left_panel, text="Department / Grade:", style="Card.TLabel").pack(anchor="w", pady=(5, 2))
        self.ent_student_dept = ttk.Entry(left_panel, width=28)
        self.ent_student_dept.pack(anchor="w", pady=(0, 15))

        btn_add = ttk.Button(left_panel, text="Add Student", style="Success.TButton", command=self.add_student)
        btn_add.pack(fill="x", pady=(5, 10))

        btn_remove = ttk.Button(left_panel, text="Remove Selected", style="Danger.TButton", command=self.remove_student)
        btn_remove.pack(fill="x")

        # Dynamic Scaling Table Layout
        right_panel = ttk.Frame(self.tab_students, style="Card.TFrame", padding=20)
        right_panel.pack(side="right", fill="both", expand=True)

        header_bar = ttk.Frame(right_panel, style="Card.TFrame")
        header_bar.pack(fill="x", pady=(0, 10))
        ttk.Label(header_bar, text="Registered Students Roster", style="SubHeader.Card.TLabel").pack(side="left")
        ttk.Label(header_bar, text="(Double-click any row to edit)", font=("Segoe UI", 9, "italic"), foreground=self.colors["text_sub"]).pack(side="right")

        cols = ("id", "name", "department")
        self.student_tree = ttk.Treeview(right_panel, columns=cols, show="headings", selectmode="browse")
        
        self.student_tree.heading("id", text="Student ID", anchor="center")
        self.student_tree.heading("name", text="Full Name", anchor="center")
        self.student_tree.heading("department", text="Department", anchor="center")

        self.student_tree.column("id", width=120, anchor="center")
        self.student_tree.column("name", width=220, anchor="center")
        self.student_tree.column("department", width=180, anchor="center")

        # Double-click event binding for Student Editing
        self.student_tree.bind("<Double-1>", self.on_edit_student)
        self.student_tree.pack(fill="both", expand=True)

    def validate_student_inputs(self, s_id, s_name, s_dept):
        """Perform regex format check and sanitization."""
        if not s_id or not s_name or not s_dept:
            messagebox.showwarning("Validation Error", "All student fields are required.")
            return False
        
        if not re.match(r"^[A-Za-z0-9\-_]+$", s_id):
            messagebox.showwarning("Format Error", "Student ID can only contain letters, numbers, hyphens, and underscores.")
            return False
            
        return True

    def add_student(self):
        s_id = self.ent_student_id.get().strip()
        s_name = self.ent_student_name.get().strip().title()
        s_dept = self.ent_student_dept.get().strip().title()

        if not self.validate_student_inputs(s_id, s_name, s_dept):
            return

        try:
            self.cursor.execute("SELECT is_active FROM students WHERE student_id = ?", (s_id,))
            existing = self.cursor.fetchone()

            if existing and existing[0] == 0:
                self.cursor.execute("UPDATE students SET name = ?, department = ?, is_active = 1 WHERE student_id = ?", (s_name, s_dept, s_id))
            else:
                self.cursor.execute("INSERT INTO students (student_id, name, department, is_active) VALUES (?, ?, ?, 1)", (s_id, s_name, s_dept))
            
            self.conn.commit()
            
            self.ent_student_id.delete(0, tk.END)
            self.ent_student_name.delete(0, tk.END)
            self.ent_student_dept.delete(0, tk.END)

            self.load_students_table()
            self.refresh_student_dropdown()
            self.update_analytics()
            messagebox.showinfo("Success", f"Student '{s_name}' registered successfully.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Student ID '{s_id}' already exists.")

    def on_edit_student(self, event):
        """Popup Modal Dialog for Inline Student Editing."""
        selected = self.student_tree.selection()
        if not selected:
            return

        values = self.student_tree.item(selected[0], "values")
        s_id, current_name, current_dept = values[0], values[1], values[2]

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Edit Student Details: {s_id}")
        edit_win.geometry("360x260")
        edit_win.configure(bg=self.colors["bg_card"])
        edit_win.grab_set()

        ttk.Label(edit_win, text=f"Edit Record ({s_id})", style="SubHeader.Card.TLabel").pack(pady=12)

        ttk.Label(edit_win, text="Full Name:", style="Card.TLabel").pack(anchor="w", padx=20, pady=(5, 2))
        ent_name = ttk.Entry(edit_win, width=32)
        ent_name.insert(0, current_name)
        ent_name.pack(padx=20, pady=(0, 10))

        ttk.Label(edit_win, text="Department / Grade:", style="Card.TLabel").pack(anchor="w", padx=20, pady=(5, 2))
        ent_dept = ttk.Entry(edit_win, width=32)
        ent_dept.insert(0, current_dept)
        ent_dept.pack(padx=20, pady=(0, 15))

        def save_changes():
            new_name = ent_name.get().strip().title()
            new_dept = ent_dept.get().strip().title()
            if not new_name or not new_dept:
                messagebox.showwarning("Warning", "Fields cannot be blank.", parent=edit_win)
                return

            self.cursor.execute("UPDATE students SET name = ?, department = ? WHERE student_id = ?", (new_name, new_dept, s_id))
            self.cursor.execute("UPDATE attendance SET student_name = ? WHERE student_id = ?", (new_name, s_id))
            self.conn.commit()

            self.load_students_table()
            self.load_attendance_logs()
            self.refresh_student_dropdown()
            edit_win.destroy()
            messagebox.showinfo("Updated", "Student record updated successfully.")

        ttk.Button(edit_win, text="Save Changes", style="Success.TButton", command=save_changes).pack(pady=5)

    def remove_student(self):
        selected_item = self.student_tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a student to remove.")
            return

        item_values = self.student_tree.item(selected_item[0], "values")
        s_id, s_name = item_values[0], item_values[1]

        if messagebox.askyesno("Confirm Removal", f"Remove '{s_name}'?\n\n(Past attendance logs will be preserved permanently)."):
            self.cursor.execute("UPDATE students SET is_active = 0 WHERE student_id = ?", (s_id,))
            self.conn.commit()
            self.load_students_table()
            self.refresh_student_dropdown()
            self.update_analytics()
            messagebox.showinfo("Deactivated", f"Student '{s_name}' removed from roster.")

    def load_students_table(self):
        for row in self.student_tree.get_children():
            self.student_tree.delete(row)

        self.cursor.execute("SELECT student_id, name, department FROM students WHERE is_active = 1 ORDER BY name ASC")
        for row in self.cursor.fetchall():
            self.student_tree.insert("", "end", values=row)

    # --- TAB 3: LOGS & CSV EXPORT ---
    def build_logs_tab(self):
        container = ttk.Frame(self.tab_logs, style="Card.TFrame", padding=20)
        container.pack(fill="both", expand=True)

        filter_frame = ttk.Frame(container, style="Card.TFrame")
        filter_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(filter_frame, text="Search Logs:", style="Card.TLabel").pack(side="left", padx=(0, 10))
        self.ent_search = ttk.Entry(filter_frame, width=22)
        self.ent_search.pack(side="left", padx=(0, 10))
        self.ent_search.bind("<KeyRelease>", lambda event: self.filter_logs())

        btn_export = ttk.Button(filter_frame, text="Export CSV", style="Primary.TButton", command=self.export_to_csv)
        btn_export.pack(side="right", padx=(6, 0))

        btn_delete_log = ttk.Button(filter_frame, text="Delete Selected", style="Danger.TButton", command=self.delete_selected_log)
        btn_delete_log.pack(side="right", padx=(6, 0))

        self.btn_deselect = ttk.Button(filter_frame, text="Deselect All", style="Secondary.TButton", command=self.deselect_all_logs)
        self.btn_select_all = ttk.Button(filter_frame, text="Select All", style="Secondary.TButton", command=self.select_all_logs)

        self.btn_toggle_item = ttk.Button(filter_frame, text="Select Items", style="Secondary.TButton", command=self.toggle_selection_mode)
        self.btn_toggle_item.pack(side="right", padx=(4, 0))

        cols = ("select", "id", "student_id", "name", "day", "date", "time", "status")
        self.logs_tree = ttk.Treeview(container, columns=cols, show="headings", selectmode="browse")
        
        self.logs_tree.heading("select", text="Select", anchor="center")
        self.logs_tree.heading("id", text="Log ID", anchor="center")
        self.logs_tree.heading("student_id", text="Student ID", anchor="center")
        self.logs_tree.heading("name", text="Full Name", anchor="center")
        self.logs_tree.heading("day", text="Day", anchor="center")
        self.logs_tree.heading("date", text="Date", anchor="center")
        self.logs_tree.heading("time", text="Timestamp", anchor="center")
        self.logs_tree.heading("status", text="Status", anchor="center")

        self.logs_tree.column("select", width=0, minwidth=0, stretch=False, anchor="center")
        self.logs_tree.column("id", width=60, anchor="center")
        self.logs_tree.column("student_id", width=100, anchor="center")
        self.logs_tree.column("name", width=180, anchor="center")
        self.logs_tree.column("day", width=100, anchor="center")
        self.logs_tree.column("date", width=110, anchor="center")
        self.logs_tree.column("time", width=110, anchor="center")
        self.logs_tree.column("status", width=90, anchor="center")

        # Treeview tag styles for separator and day grouping
        self.logs_tree.tag_configure("day_group_1", background=self.colors["bg_card"])
        self.logs_tree.tag_configure("day_group_2", background="#2a2b3d")
        self.logs_tree.tag_configure("date_separator", background=self.colors["border"], foreground=self.colors["accent"])

        self.logs_tree.bind("<Button-1>", self.on_log_row_click)
        self.logs_tree.bind("<Double-1>", self.on_edit_attendance_log)
        self.logs_tree.pack(fill="both", expand=True)

    def on_edit_attendance_log(self, event):
        """Double-click modal editor for attendance records."""
        region = self.logs_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        selected = self.logs_tree.selection()
        if not selected or selected[0].startswith("sep_"):
            return  # Ignore double-clicks on separator rows

        item_id = selected[0] # SQLite ID
        values = self.logs_tree.item(item_id, "values")
        log_id, s_name, current_status = values[1], values[3], values[7]

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Modify Log Record #{log_id}")
        edit_win.geometry("320x200")
        edit_win.configure(bg=self.colors["bg_card"])
        edit_win.grab_set()

        ttk.Label(edit_win, text=f"Edit Attendance: {s_name}", style="SubHeader.Card.TLabel").pack(pady=12)

        status_var = tk.StringVar(value=current_status)
        combo = ttk.Combobox(edit_win, textvariable=status_var, values=["Present", "Absent", "Late"], state="readonly", width=20)
        combo.pack(pady=10)

        def save_log_change():
            new_status = status_var.get()
            self.cursor.execute("UPDATE attendance SET status = ? WHERE id = ?", (new_status, item_id))
            self.conn.commit()

            self.load_attendance_logs(self.ent_search.get().strip() if self.ent_search.get().strip() else None)
            self.update_analytics()
            edit_win.destroy()
            messagebox.showinfo("Updated", "Log status updated successfully.")

        ttk.Button(edit_win, text="Save Status", style="Success.TButton", command=save_log_change).pack(pady=12)

    def toggle_selection_mode(self):
        self.selection_mode_active = not self.selection_mode_active

        if self.selection_mode_active:
            self.logs_tree.column("select", width=60, minwidth=60, stretch=True, anchor="center")
            self.btn_select_all.pack(side="right", padx=(4, 0), before=self.btn_toggle_item)
            self.btn_deselect.pack(side="right", padx=(4, 0), before=self.btn_select_all)
            self.btn_toggle_item.config(text="Cancel Selection")
        else:
            self.logs_tree.column("select", width=0, minwidth=0, stretch=False, anchor="center")
            self.btn_select_all.pack_forget()
            self.btn_deselect.pack_forget()
            self.btn_toggle_item.config(text="Select Items")
            self.checked_logs.clear()

        self.load_attendance_logs(self.ent_search.get().strip() if self.ent_search.get().strip() else None)

    def on_log_row_click(self, event):
        if not self.selection_mode_active:
            return

        region = self.logs_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.logs_tree.identify_row(event.y)
            if item and not item.startswith("sep_"):
                self.checked_logs[item] = not self.checked_logs.get(item, False)
                self.update_row_checkbox(item)

    def update_row_checkbox(self, item_id):
        if item_id.startswith("sep_"):
            return
        current_values = list(self.logs_tree.item(item_id, "values"))
        is_checked = self.checked_logs.get(item_id, False)
        current_values[0] = "[✓]" if is_checked else "[  ]"
        self.logs_tree.item(item_id, values=current_values)

    def select_all_logs(self):
        for item in self.logs_tree.get_children():
            if not item.startswith("sep_"):
                self.checked_logs[item] = True
                self.update_row_checkbox(item)

    def deselect_all_logs(self):
        for item in self.logs_tree.get_children():
            if not item.startswith("sep_"):
                self.checked_logs[item] = False
                self.update_row_checkbox(item)

    def load_attendance_logs(self, query=None):
        for row in self.logs_tree.get_children():
            self.logs_tree.delete(row)

        if query:
            search_param = f"%{query}%"
            self.cursor.execute("""
                SELECT id, student_id, student_name, day, date, time, status 
                FROM attendance 
                WHERE student_name LIKE ? OR student_id LIKE ? OR date LIKE ? OR day LIKE ?
                ORDER BY date ASC, time ASC
            """, (search_param, search_param, search_param, search_param))
        else:
            self.cursor.execute("SELECT id, student_id, student_name, day, date, time, status FROM attendance ORDER BY date ASC, time ASC")

        records = self.cursor.fetchall()
        last_date = None
        group_toggle = False
        display_index = 1

        for row in records:
            db_id = str(row[0])
            student_id = row[1]
            student_name = row[2]
            day = row[3]
            date_str = row[4]
            timestamp = row[5]
            status = row[6]

            # Detect when the date changes
            if last_date is not None and date_str != last_date:
                group_toggle = not group_toggle
                # Insert a visual separator row across the table
                sep_id = f"sep_{date_str}_{db_id}"
                self.logs_tree.insert(
                    "", 
                    "end", 
                    iid=sep_id, 
                    values=("", "---", "----------------", f"─── {day} ({date_str}) ───", "----------------", "------------", "------------", "--------"), 
                    tags=("date_separator",)
                )

            last_date = date_str
            tag_name = "day_group_1" if not group_toggle else "day_group_2"

            is_checked = self.checked_logs.get(db_id, False)
            chk_symbol = "[✓]" if is_checked else "[  ]"

            display_row = (chk_symbol, display_index, student_id, student_name, day, date_str, timestamp, status)
            self.logs_tree.insert("", "end", iid=db_id, values=display_row, tags=(tag_name,))
            display_index += 1

    def filter_logs(self):
        query = self.ent_search.get().strip()
        self.load_attendance_logs(query if query else None)

    def delete_selected_log(self):
        to_delete = [db_id for db_id, is_checked in self.checked_logs.items() if is_checked and not db_id.startswith("sep_")]

        if not to_delete:
            selected_highlight = self.logs_tree.selection()
            if selected_highlight:
                to_delete = [item for item in selected_highlight if not item.startswith("sep_")]

        if not to_delete:
            messagebox.showwarning("Selection Error", "Select items to delete using the checkmarks or by clicking a row.")
            return

        count = len(to_delete)
        confirm_msg = f"Delete {count} log record(s)?" if count > 1 else "Delete the selected log?"

        if messagebox.askyesno("Confirm Deletion", confirm_msg):
            for db_id in to_delete:
                self.cursor.execute("DELETE FROM attendance WHERE id = ?", (db_id,))
                if db_id in self.checked_logs:
                    del self.checked_logs[db_id]
            
            self.conn.commit()
            self.load_attendance_logs(self.ent_search.get().strip() if self.ent_search.get().strip() else None)
            self.update_analytics()
            messagebox.showinfo("Deleted", f"Deleted {count} record(s).")

    def export_to_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                                                title="Save Attendance Report")
        if not file_path:
            return

        self.cursor.execute("SELECT student_id, student_name, day, date, time, status, term FROM attendance ORDER BY id ASC")
        records = self.cursor.fetchall()

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Log ID", "Student ID", "Full Name", "Day", "Date", "Timestamp", "Status", "Academic Term"])
                
                for idx, record in enumerate(records, start=1):
                    writer.writerow([idx] + list(record))

            messagebox.showinfo("Export Successful", f"Exported {len(records)} records to CSV.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

    def on_closing(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernAttendanceApp(root)
    root.mainloop()