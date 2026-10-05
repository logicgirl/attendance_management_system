import datetime as dt
import re
import tkinter as tk
from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import C, px
from client.ui.widgets import (
    FormDialog,
    SearchBox,
    Table,
    button,
    card,
    card_header,
    confirm,
    field_label,
    flat,
    font,
    icon_badge,
    safe,
)


def department_code(department: str) -> str:
    """Same rule as the server (backend/app/services/student_ids.py), for the preview."""
    words = re.findall(r"[A-Za-z]+", department)
    if not words:
        return "STU"
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:4]).upper()


class StudentsPage(Page):
    key = "students"
    title = "Students"
    icon = "people"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.students: dict[str, dict] = {}

        form = card(self)
        form.pack(side="left", fill="y", padx=(0, px(16)))
        card_header(form, "Register a student", "Add someone to the roster")
        self.entries: dict[str, ttk.Entry] = {}
        for key, label in (("name", "Full name"), ("department", "Department / class")):
            field_label(form, label)
            entry = ttk.Entry(form, width=30)
            entry.pack(fill="x", pady=(0, px(14)))
            self.entries[key] = entry
        self.entries["department"].bind("<Return>", lambda _: self.add())
        self.entries["department"].bind("<KeyRelease>", lambda _: self._preview_id(), add="+")

        field_label(form, "Student ID")
        id_box = ttk.Frame(form, style="Raised.TFrame", padding=(px(12), px(9)))
        id_box.pack(fill="x", pady=(0, px(14)))
        self.id_preview = tk.Label(
            id_box, text="", bg=C["raised"], fg=C["text_sub"], font=font(10), anchor="w"
        )
        self.id_preview.pack(fill="x")
        self._preview_id()
        self.form_error = ttk.Label(form, text="", style="Error.Card.TLabel", wraplength=px(240))
        self.form_error.pack(anchor="w")
        button(form, "Add student", self.add, "Primary").pack(fill="x", pady=(px(4), 0))

        note = ttk.Frame(form, style="Raised.TFrame", padding=px(12))
        note.pack(side="bottom", fill="x")
        row = tk.Frame(note, bg=C["raised"])
        row.pack(fill="x")
        icon_badge(row, "info", C["accent"], bg=C["raised"], size=30).pack(side="left", anchor="n")
        tk.Label(
            row,
            text=(
                "IDs are made from the department,\nthe year and a number.\n"
                "Removed students keep their\nattendance history."
            ),
            bg=C["raised"],
            fg=C["text_sub"],
            justify="left",
            font=font(9),
        ).pack(side="left", padx=(px(10), 0))

        roster = card(self)
        roster.pack(side="left", fill="both", expand=True)
        self.header = card_header(roster, "All students", "")
        if app.is_admin:
            self.show_removed = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                self.header.actions,
                text="Show removed",
                variable=self.show_removed,
                command=self.refresh,
            ).pack(side="right", padx=(px(12), 0))
        self.search = SearchBox(
            self.header.actions, self.refresh, "Search name, ID or department", width=26
        )
        self.search.pack(side="right")

        actions = flat(roster)
        actions.pack(side="bottom", fill="x", pady=(px(14), 0))
        ttk.Label(actions, text="Double-click a student to edit", style="Muted.Card.TLabel").pack(
            side="left"
        )
        if app.is_admin:
            button(actions, "Remove from roster", self.remove, "Danger").pack(side="right")
        button(actions, "Edit", lambda: self.edit(self.table.selected_one()), "Secondary").pack(
            side="right", padx=(0, px(8))
        )

        self.table = Table(
            roster,
            [
                ("student_id", "Student ID", 110),
                ("name", "Full name", 190),
                ("department", "Department", 170),
            ],
            status_heading="Status",
            empty=("people", "No students yet. Register the first one on the left."),
        )
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.edit)

    @property
    def subtitle(self) -> str:
        return "Everyone on the roster, with their department."

    @safe
    def refresh(self, **_):
        include_removed = self.app.is_admin and self.show_removed.get()
        students = self.app.api.students(self.search.text, include_removed)
        self.students = {s["student_id"]: s for s in students}
        self.table.clear()
        if self.search.text:
            self.table.set_empty(f"No students match “{self.search.text}”.", "search")
        else:
            self.table.set_empty("No students yet. Register the first one on the left.", "people")
        for s in students:
            self.table.add(
                s["student_id"],
                (s["student_id"], s["name"], s["department"]),
                tags=() if s["is_active"] else ("muted",),
                status="Present" if s["is_active"] else None,
                status_text="Active" if s["is_active"] else "Removed",
            )
        active = sum(1 for s in students if s["is_active"])
        self.header.subtitle.config(text=f"{active} active student{'s' if active != 1 else ''}")
        self.header.subtitle.pack(anchor="w", pady=(px(2), 0))

    @safe
    def add(self):
        values = {k: e.get().strip() for k, e in self.entries.items()}
        if not all(values.values()):
            self.form_error.config(text="Enter the student's name and department.")
            return
        self.form_error.config(text="")
        student = self.app.api.create_student(**values)
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.entries["name"].focus_set()
        self._preview_id()
        self.refresh()
        self.table.tree.selection_set(student["student_id"])
        self.table.tree.see(student["student_id"])
        self.app.toast(f"{student['name']} registered with ID {student['student_id']}.")

    def _preview_id(self):
        """Show the shape of the ID the server will assign (the number is decided there)."""
        department = self.entries["department"].get()
        if not department.strip():
            self.id_preview.config(text="Assigned automatically", fg=C["muted"])
            return
        year = dt.date.today().year % 100
        self.id_preview.config(
            text=f"{department_code(department)}-{year:02d}-####  (assigned automatically)",
            fg=C["text_sub"],
        )

    def edit(self, student_id: str | None):
        if student_id is None:
            self.app.toast("Select a student first.", "info")
            return
        student = self.students[student_id]
        fields = [("name", "Full name", "entry"), ("department", "Department / class", "entry")]
        if self.app.is_admin:
            fields.append(("is_active", "Active on the roster", "check"))

        def submit(values):
            if not values["name"] or not values["department"]:
                raise ValueError("Name and department can't be blank.")
            self.app.api.update_student(student_id, **values)
            self.refresh()
            self.app.toast("Student updated.")

        FormDialog(
            self,
            "Edit student",
            fields,
            submit,
            initial=student,
            subtitle=f"Student ID {student_id}",
        )

    @safe
    def remove(self):
        student_id = self.table.selected_one()
        if student_id is None:
            self.app.toast("Select a student to remove.", "info")
            return
        name = self.students[student_id]["name"]
        if confirm(
            self,
            f"Remove {name}?",
            "They'll be taken off the roster and out of new registers. "
            "Their past attendance is kept.",
            "Remove",
        ):
            self.app.api.deactivate_student(student_id)
            self.refresh()
            self.app.toast(f"{name} removed from the roster.")
