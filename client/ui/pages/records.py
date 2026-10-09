import datetime as dt
import os
import tkinter as tk
from tkinter import filedialog, ttk

from client.ui.pages.base import Page
from client.ui.theme import C, px
from client.ui.widgets import (
    STATUSES,
    DateEntry,
    Dialog,
    FormDialog,
    ProgressBar,
    SearchBox,
    Table,
    button,
    card,
    card_header,
    confirm,
    field_label,
    flat,
    format_time,
    nice_date,
    parse_date,
    safe,
)

ALL_COURSES, ALL_STATUSES = "All courses", "Any status"


class RecordsPage(Page):
    """Browse, correct, delete and export attendance records."""

    key = "records"
    title = "Records & Reports"
    icon = "report"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.courses: dict[str, int] = {}
        self.records: dict[str, dict] = {}

        filters = card(self, padding=18)
        filters.pack(fill="x", pady=(0, px(16)))
        row = flat(filters)
        row.pack(fill="x")

        def column(label):
            box = flat(row)
            box.pack(side="left", padx=(0, px(12)))
            field_label(box, label)
            return box

        self.search = SearchBox(column("Search"), self.refresh, "Name or student ID", width=18)
        self.search.pack()
        self.course_var = tk.StringVar(value=ALL_COURSES)
        self.course_select = ttk.Combobox(
            column("Course"), textvariable=self.course_var, state="readonly", width=14
        )
        self.course_select.pack()
        self.course_select.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.status_var = tk.StringVar(value=ALL_STATUSES)
        status = ttk.Combobox(
            column("Status"),
            textvariable=self.status_var,
            values=[ALL_STATUSES, *STATUSES],
            state="readonly",
            width=11,
        )
        status.pack()
        status.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.date_from = DateEntry(column("From"), self.refresh, "Any date")
        self.date_from.pack()
        self.date_to = DateEntry(column("To"), self.refresh, "Any date")
        self.date_to.pack()
        clear_box = flat(row)
        clear_box.pack(side="left", anchor="s")
        button(clear_box, "Clear filters", self.clear_filters, "Ghost").pack()

        results = card(self, padding=18)
        results.pack(fill="both", expand=True)
        self.header = card_header(results, "Attendance records", "")
        button(self.header.actions, "Export to Excel", self.export, "Primary").pack(side="right")
        button(self.header.actions, "Student report", self.student_report, "Secondary").pack(
            side="right", padx=(0, px(8))
        )
        if app.is_admin:
            button(self.header.actions, "Delete selected", self.delete, "Danger").pack(
                side="right", padx=(0, px(8))
            )
        ttk.Label(
            results,
            text="Double-click a record to correct it  ·  Ctrl- or Shift-click to select several",
            style="Muted.Card.TLabel",
        ).pack(side="bottom", anchor="w", pady=(px(12), 0))
        self.table = Table(
            results,
            [
                ("student_id", "Student ID", 120),
                ("name", "Full name", 200),
                ("course", "Course", 100),
                ("time", "Time", 90),
                ("term", "Term", 110),
            ],
            selectmode="extended",
            status_heading="Status",
            empty=("search", "No records match these filters."),
        )
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.edit)

    @property
    def subtitle(self) -> str:
        return "Search attendance history, fix mistakes and export reports."

    def filters(self) -> dict:
        return {
            "search": self.search.text,
            "course_id": self.courses.get(self.course_var.get()),
            "status": None if self.status_var.get() == ALL_STATUSES else self.status_var.get(),
            "date_from": parse_date(self.date_from.get(), "From"),
            "date_to": parse_date(self.date_to.get(), "To"),
        }

    def clear_filters(self):
        self.search.var.set("")
        self.course_var.set(ALL_COURSES)
        self.status_var.set(ALL_STATUSES)
        self.date_from.set("")
        self.date_to.set("")
        self.refresh()

    @safe
    def refresh(self, **_):
        self.courses = {c["code"]: c["id"] for c in self.app.api.courses(include_inactive=True)}
        self.course_select["values"] = [ALL_COURSES, *self.courses]
        try:
            filters = self.filters()
        except ValueError as exc:
            self.app.toast(str(exc), "error")
            return
        records = self.app.api.attendance(**filters)
        self.records = {str(r["id"]): r for r in records}
        self.table.clear()
        last_date = None
        for r in reversed(records):  # newest first
            if r["date"] != last_date:
                self.table.add_separator(f"sep{r['id']}", nice_date(r["date"], with_year=True), 5)
                last_date = r["date"]
            self.table.add(
                r["id"],
                (
                    r["student_id"],
                    r["student_name"],
                    r["course_code"],
                    format_time(r["time"]),
                    r["term"],
                ),
                status=r["status"],
            )
        counts = {s: sum(1 for r in records if r["status"] == s) for s in STATUSES}
        summary = "  ·  ".join(f"{n} {s.lower()}" for s, n in counts.items())
        self.header.subtitle.config(
            text=f"{len(records)} record{'s' if len(records) != 1 else ''}"
            + (f"  ·  {summary}" if records else "")
        )
        self.header.subtitle.pack(anchor="w", pady=(px(2), 0))

    def edit(self, record_id: str):
        record = self.records[record_id]

        def submit(values):
            self.app.api.update_attendance(record["id"], values["status"])
            self.refresh()
            self.app.toast("Record updated.")

        FormDialog(
            self,
            "Correct a record",
            [("status", "Status", "combo", STATUSES)],
            submit,
            initial=record,
            subtitle=(
                f"{record['student_name']} · {record['course_code']} · "
                f"{nice_date(record['date'], True)}"
            ),
        )

    @safe
    def delete(self):
        ids = [int(i) for i in self.table.selected()]
        if not ids:
            self.app.toast("Select the records to delete.", "info")
            return
        if confirm(
            self,
            f"Delete {len(ids)} record{'s' if len(ids) != 1 else ''}?",
            "This can't be undone. The deletion is recorded in the audit log.",
            "Delete",
        ):
            deleted = self.app.api.delete_attendance(ids)
            self.refresh()
            self.app.toast(f"Deleted {deleted} record{'s' if deleted != 1 else ''}.")

    @safe
    def export(self):
        try:
            filters = self.filters()
        except ValueError as exc:
            self.app.toast(str(exc), "error")
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=f"attendance_report_{dt.date.today().isoformat()}.xlsx",
            title="Save attendance report",
        )
        if not path:
            return
        content = self.app.api.export_excel(**filters)
        try:
            with open(path, "wb") as fh:
                fh.write(content)
        except OSError as exc:
            # Most often the file is still open in Excel
            self.app.toast(
                f"Couldn't save the file. Is it open in Excel? ({exc.strerror})", "error"
            )
            return
        rows = len(self.records)
        self.app.toast(f"Exported {rows} record{'s' if rows != 1 else ''} to Excel.")
        try:
            os.startfile(path)  # open it in Excel (or whatever handles .xlsx)
        except (AttributeError, OSError):
            pass  # Not Windows, or nothing installed to open it

    @safe
    def student_report(self):
        try:
            filters = self.filters()
        except ValueError as exc:
            self.app.toast(str(exc), "error")
            return
        filters.pop("status")
        stats = self.app.api.student_stats(**filters)
        scope = self.course_var.get() if self.course_var.get() != ALL_COURSES else "all courses"
        StudentReport(self, stats, scope)


class StudentReport(Dialog):
    def __init__(self, parent, stats: list[dict], scope: str):
        super().__init__(parent, "Attendance by student", width=820)
        ttk.Label(self.body, text="Attendance by student", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            self.body,
            text=f"{scope}  ·  Late counts as attended  ·  below 75% is shown in red",
            style="Muted.Card.TLabel",
        ).pack(anchor="w", pady=(px(2), px(14)))
        table = Table(
            self.body,
            [
                ("student_id", "Student ID", 120),
                ("name", "Full name", 190),
                ("total", "Sessions", 80, "e"),
                ("present", "Present", 80, "e"),
                ("late", "Late", 60, "e"),
                ("absent", "Absent", 70, "e"),
                ("rate", "Rate", 80, "e"),
            ],
            empty=("report", "No attendance in this range."),
        )
        table.tree.configure(height=12)
        table.pack(fill="both", expand=True)
        for s in stats:
            table.add(
                s["student_id"],
                (
                    s["student_id"],
                    s["name"],
                    s["total"],
                    s["present"],
                    s["late"],
                    s["absent"],
                    f"{s['attendance_rate']:.1f}%",
                ),
                tags=("danger",) if s["attendance_rate"] < 75 else (),
            )
        if stats:
            overall = sum(s["present"] + s["late"] for s in stats) / sum(s["total"] for s in stats)
            summary = flat(self.body)
            summary.pack(fill="x", pady=(px(14), 0))
            ttk.Label(
                summary,
                text=f"Overall attendance  {overall * 100:.1f}%",
                style="Strong.Card.TLabel",
            ).pack(anchor="w")
            bar = ProgressBar(summary, overall, C["success"] if overall >= 0.75 else C["danger"])
            bar.pack(fill="x", pady=(px(6), 0))
        bar = self.footer()
        button(bar, "Close", self.destroy, "Primary").pack(side="right")
        self.show()
