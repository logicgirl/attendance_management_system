import datetime as dt
import tkinter as tk
from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import px
from client.ui.widgets import (
    STATUSES,
    DateEntry,
    SearchBox,
    Table,
    button,
    card,
    confirm,
    field_label,
    flat,
    nice_date,
    safe,
)


def course_label(course: dict) -> str:
    return f"{course['code']}  ·  {course['title']}"


class RegisterPage(Page):
    """Take attendance for a whole class at once."""

    key = "register"
    title = "Take Attendance"
    icon = "checklist"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.courses: dict[str, dict] = {}
        self.loaded: tuple[int, str] | None = None
        self.loaded_label = ""
        self.saved: dict[str, str | None] = {}
        self.statuses: dict[str, str | None] = {}
        self.students: dict[str, tuple[str, str]] = {}

        top = card(self, padding=18)
        top.pack(fill="x", pady=(0, px(16)))
        controls = flat(top)
        controls.pack(fill="x")

        course_box = flat(controls)
        course_box.pack(side="left")
        field_label(course_box, "Course")
        self.course_var = tk.StringVar()
        self.course_select = ttk.Combobox(
            course_box, textvariable=self.course_var, state="readonly", width=40
        )
        self.course_select.pack()
        self.course_select.bind("<<ComboboxSelected>>", lambda _: self.load())

        date_box = flat(controls)
        date_box.pack(side="left", padx=(px(14), 0))
        field_label(date_box, "Date")
        date_row = flat(date_box)
        date_row.pack()
        self.date = DateEntry(date_row, on_change=self.load)
        self.date.set(dt.date.today().isoformat())
        self.date.pack(side="left")
        button(date_row, "Today", self.set_today, "Ghost").pack(side="left", padx=(px(6), 0))

        self.pills = flat(controls)
        self.pills.pack(side="right", anchor="s")
        self.pill = {}
        for name, style in (
            ("Present", "Green"),
            ("Late", "Yellow"),
            ("Absent", "Red"),
            ("Unmarked", "Grey"),
        ):
            label = ttk.Label(self.pills, text=f"{name} 0", style=f"{style}.Pill.TLabel")
            label.pack(side="left", padx=(px(6), 0))
            self.pill[name] = label

        body = card(self, padding=18)
        body.pack(fill="both", expand=True)
        toolbar = flat(body)
        toolbar.pack(fill="x", pady=(0, px(12)))
        ttk.Label(toolbar, text="Mark selected", style="Field.Card.TLabel").pack(
            side="left", padx=(0, px(10))
        )
        for status, kind, key in (
            ("Present", "Success", "P"),
            ("Late", "Warning", "L"),
            ("Absent", "Danger", "A"),
        ):
            button(toolbar, f"{status}  ({key})", lambda s=status: self.set_selected(s), kind).pack(
                side="left", padx=(0, px(6))
            )
        button(toolbar, "Mark the rest present", self.fill_present, "Ghost").pack(
            side="left", padx=(px(4), 0)
        )
        self.search = SearchBox(toolbar, self.render, "Find a student", width=18)
        self.search.pack(side="right")

        footer = flat(body)
        footer.pack(side="bottom", fill="x", pady=(px(14), 0))
        self.progress = ttk.Label(footer, text="", style="Sub.Card.TLabel")
        self.progress.pack(side="left")
        self.save_button = button(footer, "Save register", self.save, "Primary")
        self.save_button.pack(side="right")
        self.discard_button = button(footer, "Discard changes", self.discard, "Ghost")
        self.discard_button.pack(side="right", padx=(0, px(8)))

        self.table = Table(
            body,
            [
                ("student_id", "Student ID", 140),
                ("name", "Full name", 260),
                ("department", "Department", 220),
            ],
            selectmode="extended",
            status_heading="Status",
            empty=("checklist", "Choose a course to see its class list"),
        )
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.cycle)
        tree = self.table.tree
        for key, value in (("p", "Present"), ("l", "Late"), ("a", "Absent")):
            tree.bind(f"<KeyPress-{key}>", lambda _, v=value: self.set_selected(v))
        tree.bind("<Control-a>", lambda _: tree.selection_set(tree.get_children()) or "break")
        self.winfo_toplevel().bind("<Control-s>", self._shortcut_save)

    def _shortcut_save(self, _event):
        if self.winfo_exists() and self.winfo_ismapped():
            self.save()

    @property
    def subtitle(self) -> str:
        if self.loaded is None:
            return "Pick a course and a day, set each student's status, then save."
        code = self.loaded_label.split("·")[0].strip()
        return f"{code} on {nice_date(self.loaded[1], with_year=True)}"

    @safe
    def refresh(self, course_id: int | None = None, **_):
        courses = self.app.api.courses()
        self.courses = {course_label(c): c for c in courses}
        self.course_select["values"] = list(self.courses)
        if course_id is not None:
            label = next((k for k, c in self.courses.items() if c["id"] == course_id), None)
            if label and (self.loaded is None or self.loaded[0] != course_id):
                self.course_var.set(label)
                self.load()
                return
        if self.course_var.get() not in self.courses:
            self.course_var.set(next(iter(self.courses), ""))
        if not courses:
            self.table.set_empty(
                "You have no courses yet. An admin can create one and assign you.", "education"
            )
        elif self.loaded is None:
            self.load()

    def set_today(self):
        self.date.set(dt.date.today().isoformat(), notify=True)

    def has_unsaved(self) -> bool:
        return any(self.statuses[s] != self.saved.get(s) for s in self.statuses)

    @safe
    def load(self):
        course = self.courses.get(self.course_var.get())
        if course is None:
            return
        try:
            day = dt.date.fromisoformat(self.date.get())
        except ValueError:
            self.app.toast("Enter the date as YYYY-MM-DD.", "error")
            return
        if day > dt.date.today():
            self.app.toast("You can't take attendance for a future date.", "error")
            if self.loaded:
                self.date.set(self.loaded[1])
            return
        if self.has_unsaved() and not confirm(
            self,
            "Discard unsaved changes?",
            "You've changed this register without saving.",
            "Discard",
        ):
            self.course_var.set(self.loaded_label)
            self.date.set(self.loaded[1])
            return

        rows = self.app.api.register(course["id"], day.isoformat())
        self.loaded = (course["id"], day.isoformat())
        self.loaded_label = self.course_var.get()
        self.saved = {r["student_id"]: r["status"] for r in rows}
        self.statuses = dict(self.saved)
        self.students = {r["student_id"]: (r["name"], r["department"]) for r in rows}
        self.table.set_empty(
            "No students are enrolled in this course yet. Add them under Courses.", "people"
        )
        self.render()
        self.app.update_header()

    def render(self):
        selection = self.table.tree.selection()
        needle = self.search.text.lower()
        self.table.clear()
        for student_id, (name, department) in self.students.items():
            if needle and needle not in name.lower() and needle not in student_id.lower():
                continue
            status = self.statuses.get(student_id)
            changed = status != self.saved.get(student_id)
            text = (status or "Not marked") + ("  •" if changed else "")
            self.table.add(
                student_id,
                (student_id, name, department),
                tags=("unsaved",) if changed else () if status else ("muted",),
                status=status,
                status_text=text,
            )
        keep = [i for i in selection if self.table.tree.exists(i)]
        if keep:
            self.table.tree.selection_set(keep)

        counts = {s: sum(1 for v in self.statuses.values() if v == s) for s in STATUSES}
        unmarked = sum(1 for v in self.statuses.values() if v is None)
        for name, n in (*counts.items(), ("Unmarked", unmarked)):
            self.pill[name].config(text=f"{name}  {n}")
        unsaved = sum(self.statuses[s] != self.saved.get(s) for s in self.statuses)
        marked = len(self.statuses) - unmarked
        text = f"{marked} of {len(self.statuses)} students marked"
        if unsaved:
            text += f"   ·   {unsaved} unsaved change{'s' if unsaved != 1 else ''}"
        self.progress.config(text=text if self.statuses else "")
        state = ["!disabled"] if unsaved else ["disabled"]
        self.save_button.state(state)
        self.discard_button.state(state)

    def set_selected(self, status: str):
        selected = self.table.selected()
        if not selected:
            self.app.toast("Select one or more students first.", "info")
            return
        for student_id in selected:
            self.statuses[student_id] = status
        self.render()

    def cycle(self, student_id: str):
        current = self.statuses.get(student_id)
        order = [*STATUSES, None] if self.saved.get(student_id) is None else STATUSES
        self.statuses[student_id] = order[(order.index(current) + 1) % len(order)]
        self.render()

    def fill_present(self):
        for student_id, status in self.statuses.items():
            if status is None:
                self.statuses[student_id] = "Present"
        self.render()

    def discard(self):
        self.statuses = dict(self.saved)
        self.render()

    @safe
    def save(self):
        if self.loaded is None:
            return
        changes = {
            s: v for s, v in self.statuses.items() if v is not None and v != self.saved.get(s)
        }
        if not changes:
            return
        course_id, day = self.loaded
        self.app.api.save_register(course_id, day, changes)
        self.saved.update(changes)
        self.render()
        self.app.toast(
            f"Register saved for {len(changes)} student{'s' if len(changes) != 1 else ''}."
        )
