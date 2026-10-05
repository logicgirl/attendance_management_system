"""Pages only admins see: user accounts, academic terms and the audit log."""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import px
from client.ui.widgets import (
    FormDialog,
    SearchBox,
    Table,
    button,
    card,
    card_header,
    confirm,
    flat,
    nice_date,
    parse_date,
    parse_timestamp,
    safe,
)

ROLES = ["admin", "lecturer", "student"]


class UsersPage(Page):
    key = "users"
    title = "Users"
    icon = "contact"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.users: dict[str, dict] = {}
        body = card(self)
        body.pack(fill="both", expand=True)
        self.header = card_header(body, "User accounts", "")
        button(self.header.actions, "New user", self.new_user, "Primary").pack(side="right")
        self.search = SearchBox(self.header.actions, self.render, "Search name or email", width=22)
        self.search.pack(side="right", padx=(0, px(12)))
        actions = flat(body)
        actions.pack(side="bottom", fill="x", pady=(px(14), 0))
        ttk.Label(
            actions,
            text="Resetting a password also unlocks a locked account",
            style="Muted.Card.TLabel",
        ).pack(side="left")
        button(actions, "Edit", lambda: self.edit(self.table.selected_one()), "Secondary").pack(
            side="right"
        )
        self.table = Table(
            body,
            [
                ("name", "Full name", 200),
                ("email", "Email", 240),
                ("role", "Role", 100),
                ("student_id", "Student ID", 120),
            ],
            status_heading="Status",
            empty=("contact", "No users found."),
        )
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.edit)

    @property
    def subtitle(self) -> str:
        return "Who can sign in, and what they're allowed to do."

    @safe
    def refresh(self, **_):
        self.users = {str(u["id"]): u for u in self.app.api.users()}
        self.render()

    def render(self):
        needle = self.search.text.lower()
        now = dt.datetime.now(dt.UTC)
        self.table.clear()
        for u in self.users.values():
            if needle and needle not in u["full_name"].lower() and needle not in u["email"]:
                continue
            locked = u["locked_until"] and parse_timestamp(u["locked_until"]) > now
            if not u["is_active"]:
                status, text = None, "Deactivated"
            elif locked:
                status, text = "Late", "Locked"
            else:
                status, text = "Present", "Active"
            self.table.add(
                u["id"],
                (u["full_name"], u["email"], u["role"].title(), u["student_id"] or "—"),
                tags=() if u["is_active"] else ("muted",),
                status=status,
                status_text=text,
            )
        counts = {r: sum(1 for u in self.users.values() if u["role"] == r) for r in ROLES}
        self.header.subtitle.config(
            text=(
                " · ".join(f"{n} {role}{'s' if n != 1 else ''}" for role, n in counts.items() if n)
            )
        )
        self.header.subtitle.pack(anchor="w", pady=(px(2), 0))

    def new_user(self):
        def submit(values):
            if not (values["full_name"] and values["email"] and values["password"]):
                raise ValueError("Name, email and password are required.")
            if values["role"] == "student" and not values["student_id"]:
                raise ValueError("Student accounts need the student's ID.")
            self.app.api.create_user(
                full_name=values["full_name"],
                email=values["email"],
                password=values["password"],
                role=values["role"],
                student_id=values["student_id"] or None,
            )
            self.refresh()
            self.app.toast(f"Account created for {values['full_name']}.")

        FormDialog(
            self,
            "New user",
            [
                ("full_name", "Full name", "entry"),
                ("email", "Email", "entry"),
                ("password", "Temporary password (at least 8 characters)", "password"),
                ("role", "Role", "combo", ROLES),
                ("student_id", "Student ID (student accounts only)", "entry"),
            ],
            submit,
            initial={"role": "lecturer"},
            submit_text="Create account",
            subtitle="They can change the password after signing in.",
        )

    def edit(self, user_id: str | None):
        if user_id is None:
            self.app.toast("Select a user first.", "info")
            return
        user = self.users[user_id]

        def submit(values):
            changes = {
                "full_name": values["full_name"],
                "role": values["role"],
                "is_active": values["is_active"],
                "student_id": values["student_id"] or None,
            }
            if values["password"]:
                changes["password"] = values["password"]
            self.app.api.update_user(user["id"], **changes)
            self.refresh()
            self.app.toast("Account updated.")

        FormDialog(
            self,
            "Edit account",
            [
                ("full_name", "Full name", "entry"),
                ("role", "Role", "combo", ROLES),
                ("student_id", "Student ID (student accounts only)", "entry"),
                ("password", "New password (leave blank to keep)", "password"),
                ("is_active", "Account is active", "check"),
            ],
            submit,
            initial=user | {"password": ""},
            subtitle=user["email"],
        )


class TermsPage(Page):
    key = "terms"
    title = "Academic Terms"
    icon = "calendar"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.terms: dict[str, dict] = {}
        body = card(self)
        body.pack(fill="both", expand=True)
        header = card_header(body, "Terms", "Attendance is tagged with the term its date falls in")
        button(header.actions, "New term", self.new_term, "Primary").pack(side="right")
        actions = flat(body)
        actions.pack(side="bottom", fill="x", pady=(px(14), 0))
        button(actions, "Delete", self.delete, "Danger").pack(side="right")
        button(actions, "Edit", lambda: self.edit(self.table.selected_one()), "Secondary").pack(
            side="right", padx=(0, px(8))
        )
        self.table = Table(
            body,
            [
                ("name", "Name", 180),
                ("start", "Starts", 200),
                ("end", "Ends", 200),
                ("length", "Length", 120),
            ],
            status_heading="Status",
            empty=(
                "calendar",
                "No terms yet. Records use the default term name until you add one.",
            ),
        )
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self.edit)

    @property
    def subtitle(self) -> str:
        return "Set the dates of each term so reports can be filtered by term."

    @safe
    def refresh(self, **_):
        terms = self.app.api.terms()
        self.terms = {str(t["id"]): t for t in terms}
        today = dt.date.today().isoformat()
        self.table.clear()
        for t in terms:
            if t["start_date"] <= today <= t["end_date"]:
                status, text = "Present", "Current"
            elif t["start_date"] > today:
                status, text = None, "Upcoming"
            else:
                status, text = None, "Finished"
            weeks = (
                dt.date.fromisoformat(t["end_date"]) - dt.date.fromisoformat(t["start_date"])
            ).days // 7
            self.table.add(
                t["id"],
                (
                    t["name"],
                    nice_date(t["start_date"], True),
                    nice_date(t["end_date"], True),
                    f"{weeks} weeks",
                ),
                tags=() if status else ("muted",),
                status=status,
                status_text=text,
            )

    def _form(self, title, submit, initial=None):
        FormDialog(
            self,
            title,
            [
                ("name", "Name (e.g. 2026-Term1)", "entry"),
                ("start_date", "Starts", "date"),
                ("end_date", "Ends", "date"),
            ],
            submit,
            initial=initial,
        )

    def new_term(self):
        def submit(values):
            start = parse_date(values["start_date"], "Start date")
            end = parse_date(values["end_date"], "End date")
            if not (values["name"] and start and end):
                raise ValueError("All fields are required.")
            self.app.api.create_term(values["name"], start, end)
            self.refresh()
            self.app.toast(f"Term {values['name']} added.")

        self._form("New term", submit)

    def edit(self, term_id: str | None):
        if term_id is None:
            self.app.toast("Select a term first.", "info")
            return
        term = self.terms[term_id]

        def submit(values):
            self.app.api.update_term(
                term["id"],
                name=values["name"],
                start_date=parse_date(values["start_date"], "Start date"),
                end_date=parse_date(values["end_date"], "End date"),
            )
            self.refresh()
            self.app.toast("Term updated.")

        self._form(f"Edit {term['name']}", submit, initial=term)

    @safe
    def delete(self):
        term_id = self.table.selected_one()
        if term_id is None:
            self.app.toast("Select a term first.", "info")
            return
        name = self.terms[term_id]["name"]
        if confirm(
            self,
            f"Delete {name}?",
            "Records already tagged with this term keep the name.",
            "Delete",
        ):
            self.app.api.delete_term(int(term_id))
            self.refresh()
            self.app.toast(f"Term {name} deleted.")


ACTION_LABELS = {
    "attendance.register": "Saved a register",
    "attendance.create": "Marked attendance",
    "attendance.update": "Corrected a record",
    "attendance.delete": "Deleted a record",
    "student.create": "Registered a student",
    "student.update": "Edited a student",
    "student.deactivate": "Removed a student",
    "course.create": "Created a course",
    "course.update": "Edited a course",
    "course.deactivate": "Deactivated a course",
    "course.enroll": "Enrolled students",
    "course.unenroll": "Unenrolled a student",
    "term.create": "Added a term",
    "term.update": "Edited a term",
    "term.delete": "Deleted a term",
    "user.create": "Created an account",
    "user.update": "Edited an account",
    "user.change_password": "Changed own password",
    "user.locked": "Account locked",
}


def describe(details: dict | None) -> str:
    if not details:
        return ""
    parts = []
    for key, value in details.items():
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = ", ".join(map(str, value[:4])) + (
                f" +{len(value) - 4}" if len(value) > 4 else ""
            )
        parts.append(f"{key.replace('_', ' ')}: {value}")
    return "  ·  ".join(parts)


class AuditPage(Page):
    key = "audit"
    title = "Audit Log"
    icon = "history"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        body = card(self)
        body.pack(fill="both", expand=True)
        header = card_header(body, "Recent changes", "Newest first · the last 500 changes")
        button(header.actions, "Refresh", self.refresh, "Secondary").pack(side="right")
        self.kind_var = tk.StringVar(value="Everything")
        kind = ttk.Combobox(
            header.actions,
            textvariable=self.kind_var,
            values=["Everything", "attendance", "course", "student", "term", "user"],
            state="readonly",
            width=12,
        )
        kind.pack(side="right", padx=(0, px(8)))
        kind.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.table = Table(
            body,
            [
                ("when", "When", 150),
                ("who", "By", 200),
                ("action", "What", 180),
                ("item", "Item", 110),
                ("details", "Details", 380),
            ],
            empty=("history", "No changes recorded yet."),
        )
        self.table.pack(fill="both", expand=True)

    @property
    def subtitle(self) -> str:
        return "Every change, who made it and when."

    @safe
    def refresh(self, **_):
        kind = "" if self.kind_var.get() == "Everything" else self.kind_var.get()
        self.table.clear()
        today = dt.date.today()
        for log in self.app.api.audit_logs(kind):
            when = parse_timestamp(log["created_at"]).astimezone()
            stamp = when.strftime("%I:%M %p").lstrip("0")
            day = "Today" if when.date() == today else nice_date(when.date())
            self.table.add(
                log["id"],
                (
                    f"{day}, {stamp}",
                    log["user_email"] or "System",
                    ACTION_LABELS.get(log["action"], log["action"]),
                    f"{log['entity_type']} {log['entity_id'] or ''}".strip(),
                    describe(log["details"]),
                ),
            )
