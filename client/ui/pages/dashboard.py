import datetime as dt
import tkinter as tk
from tkinter import ttk

from client.ui.pages.base import Page
from client.ui.theme import C, blend, px
from client.ui.widgets import (
    ProgressBar,
    StatCard,
    avatar,
    card,
    card_header,
    flat,
    font,
    icon_badge,
    nice_date,
    safe,
)

ATTENTION_THRESHOLD = 75


class RateChart(tk.Canvas):
    """Bars of the daily attendance rate, with a hover tooltip and an average line."""

    BAR = C["accent_deep"]  # validated against the card surface for marks
    BAR_HOVER = C["accent"]

    def __init__(self, parent):
        super().__init__(parent, bg=C["card"], highlightthickness=0, bd=0, height=px(150))
        self.days: list[dict] = []
        self.hover: int | None = None
        self.slots: list[tuple[float, float, dict]] = []
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _: self._set_hover(None))

    def set(self, days: list[dict]):
        # Days with no classes (weekends, holidays) are left out rather than drawn as zero
        self.days = [d for d in days if d["total"]]
        self.hover = None
        self.draw()

    def _set_hover(self, index):
        if index != self.hover:
            self.hover = index
            self.draw()

    def _motion(self, event):
        for i, (x0, x1, _) in enumerate(self.slots):
            if x0 <= event.x <= x1:
                self._set_hover(i)
                return
        self._set_hover(None)

    def draw(self):
        self.delete("all")
        self.slots = []
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        left, right, top, bottom = px(40), px(8), px(14), px(30)
        plot_h = h - top - bottom
        base = top + plot_h

        def y_for(rate: float) -> float:
            return base - plot_h * rate / 100

        # Fewer gridlines when the chart is short, so the labels never crowd
        steps = (0, 25, 50, 75, 100) if plot_h >= px(150) else (0, 50, 100)
        for rate in steps:
            y = y_for(rate)
            self.create_line(left, y, w - right, y, fill=C["line"], dash=(2, 4) if rate else ())
            self.create_text(
                left - px(8), y, text=f"{rate}%", anchor="e", fill=C["muted"], font=font(8)
            )

        if not self.days:
            self.create_text(
                (left + w) / 2,
                top + plot_h / 2,
                text="No attendance recorded in the last two weeks",
                fill=C["muted"],
                font=font(10),
            )
            return

        slot = (w - left - right) / len(self.days)
        bar_w = min(px(30), slot * 0.56)
        radius = min(px(4), bar_w / 2)
        for i, day in enumerate(self.days):
            cx = left + slot * (i + 0.5)
            x0, x1 = cx - bar_w / 2, cx + bar_w / 2
            y0 = y_for(day["attendance_rate"])
            color = self.BAR_HOVER if i == self.hover else self.BAR
            if base - y0 > radius:
                # Rounded top, square base anchored on the axis
                self.create_rectangle(x0, y0 + radius, x1, base, fill=color, outline="")
                self.create_rectangle(
                    x0 + radius, y0, x1 - radius, y0 + radius, fill=color, outline=""
                )
                for ox in (x0, x1 - 2 * radius):
                    self.create_oval(
                        ox, y0, ox + 2 * radius, y0 + 2 * radius, fill=color, outline=""
                    )
            else:
                self.create_rectangle(x0, y0, x1, base, fill=color, outline="")
            date = dt.date.fromisoformat(day["date"])
            label = f"{date:%a}"[:2] + f" {date.day}"
            self.create_text(cx, base + px(14), text=label, fill=C["muted"], font=font(8))
            self.slots.append((left + slot * i, left + slot * (i + 1), day))

        total = sum(d["total"] for d in self.days)
        attended = sum(d["present"] + d["late"] for d in self.days)
        average = attended / total * 100
        ya = y_for(average)
        self.create_line(
            left, ya, w - right, ya, fill=C["teal"], dash=(6, 4), width=max(px(1.5), 1)
        )
        # On the left, so it never collides with the latest bar's label
        self.create_text(
            left + px(6),
            ya - px(9),
            text=f"Average {average:.0f}%",
            anchor="w",
            fill=C["teal"],
            font=font(8, "semibold"),
        )
        # Label only the latest day; everything else is in the tooltip
        last = self.days[-1]
        lx = left + slot * (len(self.days) - 0.5)
        self.create_text(
            lx,
            y_for(last["attendance_rate"]) - px(10),
            text=f"{last['attendance_rate']:.0f}%",
            fill=C["text"],
            font=font(8, "semibold"),
        )
        if self.hover is not None:
            self._tooltip(*self.slots[self.hover], top, w)

    def _tooltip(self, x0, x1, day, top, width):
        lines = [
            (nice_date(day["date"]), C["text"], "semibold"),
            (f"{day['attendance_rate']:.1f}% attended", C["text"], ""),
            (
                f"{day['present']} present · {day['late']} late · {day['absent']} absent",
                C["text_sub"],
                "",
            ),
        ]
        pad, line_h = px(10), px(18)
        box_w = px(210)
        box_h = pad * 2 + line_h * len(lines)
        cx = (x0 + x1) / 2
        bx = min(max(cx - box_w / 2, px(4)), width - box_w - px(4))
        self.create_rectangle(
            bx, top, bx + box_w, top + box_h, fill=C["raised"], outline=C["input_border"]
        )
        for i, (text, color, weight) in enumerate(lines):
            self.create_text(
                bx + pad,
                top + pad + line_h * i + line_h / 2,
                text=text,
                anchor="w",
                fill=color,
                font=font(9, weight),
            )


class DashboardPage(Page):
    key = "dashboard"
    title = "Dashboard"
    icon = "home"

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")
        # The chart takes whatever height is left; the attention strip keeps its natural size
        self.rowconfigure(1, weight=1)

        role_word = "Active students" if app.is_admin else "My students"
        self.kpi_students = StatCard(self, "people", role_word, C["accent"])
        self.kpi_today = StatCard(self, "check_circle", "Attendance today", C["success"])
        self.kpi_registers = StatCard(self, "checklist", "Registers taken today", C["mauve"])
        self.kpi_trend = StatCard(self, "trending", "14-day attendance", C["teal"])
        for col, kpi in enumerate(
            (self.kpi_students, self.kpi_today, self.kpi_registers, self.kpi_trend)
        ):
            kpi.grid(
                row=0,
                column=col,
                sticky="nsew",
                padx=(0 if col == 0 else px(8), 0 if col == 3 else px(8)),
            )

        chart_card = card(self)
        chart_card.grid(
            row=1, column=0, columnspan=3, sticky="nsew", pady=(px(16), px(8)), padx=(0, px(8))
        )
        card_header(
            chart_card, "Attendance rate", "Daily share of students present or late, last 14 days"
        )
        self.chart = RateChart(chart_card)
        self.chart.pack(fill="both", expand=True)

        self.attention = card(self)
        self.attention.grid(
            row=2, column=0, columnspan=3, sticky="nsew", pady=(px(8), 0), padx=(0, px(8))
        )
        self.attention_header = card_header(
            self.attention,
            "Students needing attention",
            f"Below {ATTENTION_THRESHOLD}% attendance over the last 30 days",
        )
        self.attention_more = ttk.Label(
            self.attention_header.actions, text="", style="Muted.Card.TLabel"
        )
        self.attention_more.pack(side="right")
        self.attention_list = flat(self.attention)
        self.attention_list.pack(fill="both", expand=True)

        self.classes = card(self)
        self.classes.grid(
            row=1, column=3, rowspan=2, sticky="nsew", pady=(px(16), 0), padx=(px(8), 0)
        )
        self.classes_header = card_header(self.classes, "Today's classes", "")
        self.classes_list = flat(self.classes)
        self.classes_list.pack(fill="both", expand=True)

    @property
    def subtitle(self) -> str:
        hour = dt.datetime.now().hour
        greeting = (
            "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        )
        first = self.app.user["full_name"].split()[0]
        if first.endswith(".") and len(self.app.user["full_name"].split()) > 1:
            first = self.app.user["full_name"].split()[1]
        return f"{greeting}, {first}. Here's how attendance is looking."

    @safe
    def refresh(self, **_):
        api = self.app.api
        summary = api.summary()
        daily = api.daily_counts(days=14)
        courses = api.course_overview()
        since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        stats = api.student_stats(date_from=since)

        self.kpi_students.set(
            str(summary["active_students"]),
            f"Across {len(courses)} active course{'s' if len(courses) != 1 else ''}",
        )
        total_today = summary["total_records"]
        today_rate = (
            (summary["present"] + summary["late"]) / total_today * 100 if total_today else None
        )
        self.kpi_today.set(
            f"{today_rate:.0f}%" if today_rate is not None else "—",
            f"{summary['present']} present · {summary['late']} late · {summary['absent']} absent"
            if total_today
            else "No attendance taken yet today",
        )
        teaching = [c for c in courses if c["enrolled"]]
        done = sum(1 for c in teaching if c["marked"] >= c["enrolled"])
        self.kpi_registers.set(
            f"{done} / {len(teaching)}",
            "All registers complete"
            if teaching and done == len(teaching)
            else f"{len(teaching) - done} still to take",
        )
        recorded = [d for d in daily if d["total"]]
        sessions = sum(d["total"] for d in recorded)
        trend = (
            sum(d["present"] + d["late"] for d in recorded) / sessions * 100 if sessions else None
        )
        self.kpi_trend.set(
            f"{trend:.0f}%" if trend is not None else "—",
            f"{sessions} records on {len(recorded)} day{'s' if len(recorded) != 1 else ''}",
        )
        self.chart.set(daily)
        self._fill_classes(teaching)
        self._fill_attention(stats)

    def _fill_classes(self, courses: list[dict]):
        for child in self.classes_list.winfo_children():
            child.destroy()
        self.classes_header.subtitle.config(text=nice_date(dt.date.today(), with_year=True))
        self.classes_header.subtitle.pack(anchor="w", pady=(px(2), 0))
        if not courses:
            empty = flat(self.classes_list)
            empty.pack(expand=True)
            icon_badge(empty, "education", C["muted"], size=48).pack()
            ttk.Label(empty, text="No courses with students yet", style="Sub.Card.TLabel").pack(
                pady=(px(10), 0)
            )
            return
        shown = courses[:3]
        for course in shown:
            row = ttk.Frame(self.classes_list, style="Raised.TFrame", padding=(px(14), px(12)))
            row.pack(fill="x", pady=(0, px(10)))
            top = tk.Frame(row, bg=C["raised"])
            top.pack(fill="x")
            complete = course["marked"] >= course["enrolled"]
            if complete:
                state, color = "Done", C["success"]
            elif course["marked"]:
                state, color = f"{course['marked']}/{course['enrolled']}", C["warning"]
            else:
                state, color = "To do", C["muted"]
            # Packed before the names so the status always keeps its space
            open_button = tk.Label(
                top,
                text=state,
                font=font(9, "semibold"),
                fg=color,
                bg=blend(color, C["raised"], 0.14),
                padx=px(8),
                pady=px(2),
                cursor="hand2",
            )
            open_button.pack(side="right", anchor="n")
            names = tk.Frame(top, bg=C["raised"])
            names.pack(side="left", fill="x", expand=True)
            tk.Label(
                names, text=course["code"], font=font(10, "semibold"), fg=C["text"], bg=C["raised"]
            ).pack(anchor="w")
            title = course["title"] if len(course["title"]) <= 20 else course["title"][:19] + "…"
            # anchor="w" so that if space runs short the text is cut on the right only
            tk.Label(
                names, text=title, font=font(9), fg=C["muted"], bg=C["raised"], anchor="w"
            ).pack(fill="x")
            bar = ProgressBar(
                row,
                course["marked"] / course["enrolled"],
                C["success"] if complete else C["accent"],
                bg=C["raised"],
            )
            bar.pack(fill="x", pady=(px(10), 0))
            for widget in (row, top, names, open_button, *names.winfo_children()):
                widget.bind(
                    "<Button-1>",
                    lambda _, c=course: self.app.show_page("register", course_id=c["course_id"]),
                )
                widget.configure(cursor="hand2")
        if len(courses) > len(shown):
            ttk.Label(
                self.classes_list,
                text=f"+ {len(courses) - len(shown)} more courses",
                style="Muted.Card.TLabel",
            ).pack(anchor="w")
        ttk.Label(
            self.classes_list, text="Click a class to open its register", style="Muted.Card.TLabel"
        ).pack(side="bottom", anchor="w")

    def _fill_attention(self, stats: list[dict]):
        for child in self.attention_list.winfo_children():
            child.destroy()
        at_risk = sorted(
            (s for s in stats if s["total"] >= 3 and s["attendance_rate"] < ATTENTION_THRESHOLD),
            key=lambda s: s["attendance_rate"],
        )
        more = len(at_risk) - 3
        self.attention_more.config(
            text=f"+ {more} more in Records → Student report" if more > 0 else ""
        )
        if not at_risk:
            empty = flat(self.attention_list)
            empty.pack(expand=True)
            icon_badge(empty, "check_circle", C["success"], size=44).pack(side="left")
            ttk.Label(
                empty,
                text=f"Everyone is at or above {ATTENTION_THRESHOLD}%. Nice work.",
                style="Sub.Card.TLabel",
            ).pack(side="left", padx=(px(12), 0))
            return
        grid = flat(self.attention_list)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure((0, 1, 2), weight=1, uniform="att")
        for i, s in enumerate(at_risk[:3]):
            cell = flat(grid)
            cell.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else px(16), 0))
            avatar(cell, s["name"], C["card"], size=34).pack(side="left")
            text = flat(cell)
            text.pack(side="left", fill="x", expand=True, padx=(px(10), 0))
            line = flat(text)
            line.pack(fill="x")
            name = s["name"] if len(s["name"]) <= 20 else s["name"][:19] + "…"
            ttk.Label(line, text=name, style="Strong.Card.TLabel").pack(side="left")
            rate = ttk.Label(line, text=f"{s['attendance_rate']:.0f}%", style="Strong.Card.TLabel")
            rate.configure(foreground=C["danger"])
            rate.pack(side="right")
            ttk.Label(
                text,
                text=f"Absent {s['absent']} of {s['total']}",
                style="Muted.Card.TLabel",
            ).pack(anchor="w")
            ProgressBar(text, s["attendance_rate"] / 100, C["danger"]).pack(
                fill="x", pady=(px(4), 0)
            )
