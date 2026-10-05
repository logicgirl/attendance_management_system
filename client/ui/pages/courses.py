import tkinter as tk
from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import px
from client.ui.widgets import (
    FormDialog,
    PickDialog,
    Table,
    button,
    card,
    card_header,
    confirm,
    flat,
    safe,
)

NO_LECTURER = "— Not assigned —"


class CoursesPage(Page):
    key = "courses"
    title = "Courses"
    icon = "education"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.courses: dict[str, dict] = {}
        self.lecturers: dict[str, int] = {}

        left = card(self)
        left.pack(side="left", fill="both", expand=True, padx=(0, px(16)))
        header = card_header(left, "All courses" if app.is_admin else "My courses", "")
        self.list_header = header
        if app.is_admin:
            button(header.actions, "New course", self.new_course, "Primary").pack(side="right")
        self.table = Table(
            left,
            [("code", "Code", 90), ("title", "Title", 220), ("lecturer", "Lecturer", 170)],
            empty=("education", "No courses yet."),
        )
        if app.is_admin:
            actions = flat(left)
            actions.pack(side="bottom", fill="x", pady=(px(14), 0))
            self.show_inactive = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                actions, text="Show inactive", variable=self.show_inactive, command=self.refresh
            ).pack(side="left")
            button(actions, "Deactivate", self.deactivate, "Danger").pack(side="right")
            button(actions, "Edit", self.edit_course, "Secondary").pack(
                side="right", padx=(0, px(8))
            )
            self.table.on_double_click(lambda _: self.edit_course())
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", lambda _: self.load_students())

        right = card(self)
        right.pack(side="left", fill="both", expand=True)
        self.detail = card_header(right, "Class list", "Select a course to see who's enrolled")
        button(self.detail.actions, "Enroll students", self.enroll, "Primary").pack(side="right")
        actions = flat(right)
        actions.pack(side="bottom", fill="x", pady=(px(14), 0))
        self.enrolled_count = ttk.Label(actions, text="", style="Muted.Card.TLabel")
        self.enrolled_count.pack(side="left")
        button(actions, "Remove from course", self.unenroll, "Danger").pack(side="right")
        self.students = Table(
            right,
            [
                ("student_id", "Student ID", 130),
                ("name", "Full name", 200),
                ("department", "Department", 170),
            ],
            empty=("people", "Select a course on the left."),
        )
        self.students.pack(fill="both", expand=True)

    @property
    def subtitle(self) -> str:
        if self.app.is_admin:
            return "Create courses, assign lecturers and manage who's enrolled."
        return "The courses you teach and the students in each."

    def selected_course(self) -> dict | None:
        course_id = self.table.selected_one()
        return self.courses.get(course_id) if course_id else None

    @safe
    def refresh(self, **_):
        selected = self.table.selected_one()
        include_inactive = self.app.is_admin and self.show_inactive.get()
        courses = self.app.api.courses(include_inactive)
        self.courses = {str(c["id"]): c for c in courses}
        self.table.clear()
        if not self.app.is_admin:
            self.table.set_empty("You aren't assigned to any courses yet.", "education")
        for c in courses:
            self.table.add(
                c["id"],
                (c["code"], c["title"], c["lecturer_name"] or "—"),
                tags=() if c["is_active"] else ("muted",),
            )
        active = sum(1 for c in courses if c["is_active"])
        self.list_header.subtitle.config(text=f"{active} active course{'s' if active != 1 else ''}")
        self.list_header.subtitle.pack(anchor="w", pady=(px(2), 0))
        if selected in self.courses:
            self.table.tree.selection_set(selected)
        elif courses:
            self.table.tree.selection_set(str(courses[0]["id"]))
        else:
            self.students.clear()

    @safe
    def load_students(self):
        course = self.selected_course()
        self.students.clear()
        if course is None:
            return
        students = self.app.api.course_students(course["id"])
        self.detail.title.config(text=f"{course['code']} class list")
        lecturer = course["lecturer_name"] or "no lecturer assigned"
        self.detail.subtitle.config(text=f"{course['title']} · {lecturer}")
        self.students.set_empty("Nobody is enrolled yet. Use “Enroll students”.", "person_add")
        for s in students:
            self.students.add(s["student_id"], (s["student_id"], s["name"], s["department"]))
        self.enrolled_count.config(text=f"{len(students)} enrolled")

    def _load_lecturers(self) -> list[str]:
        self.lecturers = {
            f"{u['full_name']}  ({u['email']})": u["id"]
            for u in self.app.api.users()
            if u["role"] in ("lecturer", "admin") and u["is_active"]
        }
        return [NO_LECTURER, *self.lecturers]

    @safe
    def new_course(self):
        options = self._load_lecturers()

        def submit(values):
            if not all(values[k] for k in ("code", "title", "department")):
                raise ValueError("Code, title and department are required.")
            course = self.app.api.create_course(
                code=values["code"],
                title=values["title"],
                department=values["department"],
                lecturer_id=self.lecturers.get(values["lecturer"]),
            )
            self.refresh()
            self.table.tree.selection_set(str(course["id"]))
            self.app.toast(f"{course['code']} created. Now enroll its students.")

        FormDialog(
            self,
            "New course",
            [
                ("code", "Course code", "entry"),
                ("title", "Title", "entry"),
                ("department", "Department", "entry"),
                ("lecturer", "Lecturer", "combo", options),
            ],
            submit,
            initial={"lecturer": NO_LECTURER},
            submit_text="Create course",
            subtitle="For example CSC101 · Introduction to Programming",
        )

    @safe
    def edit_course(self):
        course = self.selected_course()
        if course is None:
            self.app.toast("Select a course first.", "info")
            return
        options = self._load_lecturers()
        current = next(
            (label for label, uid in self.lecturers.items() if uid == course["lecturer_id"]),
            NO_LECTURER,
        )

        def submit(values):
            self.app.api.update_course(
                course["id"],
                title=values["title"],
                department=values["department"],
                lecturer_id=self.lecturers.get(values["lecturer"]),
                is_active=values["is_active"],
            )
            self.refresh()
            self.load_students()
            self.app.toast(f"{course['code']} updated.")

        FormDialog(
            self,
            f"Edit {course['code']}",
            [
                ("title", "Title", "entry"),
                ("department", "Department", "entry"),
                ("lecturer", "Lecturer", "combo", options),
                ("is_active", "Course is active", "check"),
            ],
            submit,
            initial=course | {"lecturer": current},
        )

    @safe
    def deactivate(self):
        course = self.selected_course()
        if course and confirm(
            self,
            f"Deactivate {course['code']}?",
            "It will no longer appear in registers. Its attendance history is kept.",
            "Deactivate",
        ):
            self.app.api.deactivate_course(course["id"])
            self.refresh()
            self.app.toast(f"{course['code']} deactivated.")

    @safe
    def enroll(self):
        course = self.selected_course()
        if course is None:
            self.app.toast("Select a course first.", "info")
            return
        enrolled = set(self.students.tree.get_children())
        candidates = [
            (s["student_id"], f"{s['name']}   ·   {s['student_id']}   ·   {s['department']}")
            for s in self.app.api.students()
            if s["student_id"] not in enrolled
        ]
        if not candidates:
            self.app.toast("Every active student is already enrolled.", "info")
            return

        def submit(student_ids):
            self.app.api.enroll(course["id"], student_ids)
            self.load_students()
            self.app.toast(
                f"Enrolled {len(student_ids)} student{'s' if len(student_ids) != 1 else ''} "
                f"in {course['code']}."
            )

        PickDialog(self, f"Enroll students in {course['code']}", candidates, submit, "Enroll")

    @safe
    def unenroll(self):
        course = self.selected_course()
        student_id = self.students.selected_one()
        if course is None or student_id is None:
            self.app.toast("Select an enrolled student first.", "info")
            return
        if confirm(
            self,
            f"Remove {student_id} from {course['code']}?",
            "They'll leave this course's register. Their past attendance is kept.",
            "Remove",
        ):
            self.app.api.unenroll(course["id"], student_id)
            self.load_students()
            self.app.toast("Student removed from the course.")
