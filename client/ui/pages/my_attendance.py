from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import C, px
from client.ui.widgets import (
    ProgressBar,
    StatCard,
    Table,
    card,
    card_header,
    flat,
    format_time,
    nice_date,
    safe,
)


class MyAttendancePage(Page):
    """What a student sees: their own attendance."""

    key = "mine"
    title = "My Attendance"
    icon = "checklist"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")
        self.rowconfigure(1, weight=1)
        self.kpi_rate = StatCard(self, "trending", "Attendance rate", C["accent"])
        self.kpi_present = StatCard(self, "check_circle", "Present", C["success"])
        self.kpi_late = StatCard(self, "clock", "Late", C["warning"])
        self.kpi_absent = StatCard(self, "cancel", "Absent", C["danger"])
        for col, kpi in enumerate(
            (self.kpi_rate, self.kpi_present, self.kpi_late, self.kpi_absent)
        ):
            kpi.grid(
                row=0,
                column=col,
                sticky="nsew",
                padx=(0 if col == 0 else px(8), 0 if col == 3 else px(8)),
            )

        self.by_course = card(self)
        self.by_course.grid(row=1, column=0, sticky="nsew", pady=(px(16), 0), padx=(0, px(8)))
        card_header(self.by_course, "By course", "Late counts as attended")
        self.course_list = flat(self.by_course)
        self.course_list.pack(fill="both", expand=True)

        history = card(self)
        history.grid(
            row=1, column=1, columnspan=3, sticky="nsew", pady=(px(16), 0), padx=(px(8), 0)
        )
        card_header(history, "History", "Most recent first")
        self.table = Table(
            history,
            [
                ("date", "Date", 150),
                ("course", "Course", 110),
                ("time", "Time", 100),
                ("term", "Term", 110),
            ],
            status_heading="Status",
            empty=("checklist", "No attendance has been recorded for you yet."),
        )
        self.table.pack(fill="both", expand=True)

    @property
    def subtitle(self) -> str:
        return f"Hi {self.app.user['full_name'].split()[0]}, here's your attendance record."

    @safe
    def refresh(self, **_):
        records = self.app.api.my_attendance()
        total = len(records)
        counts = {
            s: sum(1 for r in records if r["status"] == s) for s in ("Present", "Late", "Absent")
        }
        attended = counts["Present"] + counts["Late"]
        rate = attended / total * 100 if total else None
        self.kpi_rate.set(
            f"{rate:.0f}%" if rate is not None else "—", f"{attended} of {total} sessions attended"
        )
        self.kpi_present.set(str(counts["Present"]), "On time")
        self.kpi_late.set(str(counts["Late"]), "Arrived late")
        self.kpi_absent.set(str(counts["Absent"]), "Missed")

        self.table.clear()
        for r in reversed(records):
            self.table.add(
                r["id"],
                (nice_date(r["date"], True), r["course_code"], format_time(r["time"]), r["term"]),
                status=r["status"],
            )

        for child in self.course_list.winfo_children():
            child.destroy()
        courses: dict[str, list[dict]] = {}
        for r in records:
            courses.setdefault(r["course_code"], []).append(r)
        if not courses:
            ttk.Label(
                self.course_list, text="Nothing recorded yet.", style="Muted.Card.TLabel"
            ).pack(anchor="w")
        for code, rows in sorted(courses.items()):
            went = sum(1 for r in rows if r["status"] != "Absent")
            course_rate = went / len(rows)
            row = flat(self.course_list)
            row.pack(fill="x", pady=(0, px(14)))
            line = flat(row)
            line.pack(fill="x")
            ttk.Label(line, text=code, style="Strong.Card.TLabel").pack(side="left")
            value = ttk.Label(line, text=f"{course_rate * 100:.0f}%", style="Strong.Card.TLabel")
            value.configure(foreground=C["success"] if course_rate >= 0.75 else C["danger"])
            value.pack(side="right")
            ttk.Label(row, text=f"{went} of {len(rows)} sessions", style="Muted.Card.TLabel").pack(
                anchor="w"
            )
            ProgressBar(
                row, course_rate, C["success"] if course_rate >= 0.75 else C["danger"]
            ).pack(fill="x", pady=(px(5), 0))
