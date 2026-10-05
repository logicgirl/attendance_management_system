"""Reusable building blocks for the AttendEase screens."""

import calendar
import datetime as dt
import functools
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from client.api import ApiError, SessionExpired
from client.ui import theme
from client.ui.theme import ICONS, STATUS_COLORS, C, blend, px, tint

STATUSES = ["Present", "Late", "Absent"]
PILL_FOR_STATUS = {"Present": "Green", "Late": "Yellow", "Absent": "Red"}


def font(size: int = 10, weight: str = "") -> tuple:
    family = theme.FONT_SEMI if weight == "semibold" else theme.FONT
    return (family, size)


def icon_font(size: int = 12) -> tuple:
    return (theme.ICON_FONT, size)


# Formatting


def parse_date(text: str, field: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError(f"{field} must be a date like 2026-09-30") from None


def format_time(value: str) -> str:
    try:
        return dt.time.fromisoformat(value).strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return value


def nice_date(value: str | dt.date, with_year: bool = False) -> str:
    day = dt.date.fromisoformat(value) if isinstance(value, str) else value
    text = f"{day:%a}, {day.day} {day:%b}"
    return f"{text} {day.year}" if with_year else text


TITLES = {"dr", "mr", "mrs", "ms", "miss", "prof", "sir"}


def parse_timestamp(value: str) -> dt.datetime:
    """A server timestamp as an aware datetime (SQLite drops the zone; it is always UTC)."""
    stamp = dt.datetime.fromisoformat(value)
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.UTC)


def initials(name: str) -> str:
    words = name.replace(".", " ").split()
    parts = [w for w in words if w[0].isalpha() and w.lower() not in TITLES] or words
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


# Error handling


def safe(action: Callable) -> Callable:
    """Run a UI action and show API errors instead of crashing.

    The widget must reach the main window through `self.app`, so that an expired
    session can send the user back to the sign-in screen."""

    @functools.wraps(action)
    def wrapper(self, *args, **kwargs):
        root = self.winfo_toplevel()
        root.config(cursor="watch")
        root.update_idletasks()
        try:
            return action(self, *args, **kwargs)
        except SessionExpired as exc:
            alert(self, "Session expired", str(exc))
            self.app.logout()
        except ApiError as exc:
            alert(self, "Something went wrong", str(exc), kind="error")
        finally:
            if root.winfo_exists():
                root.config(cursor="")

    return wrapper


# Basic pieces


def card(parent, padding: int = 20) -> ttk.Frame:
    return ttk.Frame(parent, style="Card.TFrame", padding=px(padding))


def flat(parent, **kw) -> ttk.Frame:
    return ttk.Frame(parent, style="Flat.TFrame", **kw)


def card_header(parent, title: str, subtitle: str = "") -> ttk.Frame:
    """Title (and subtitle) on the left. Pack buttons into `.actions` with side="right";
    they are laid out first, so a long title can never squeeze them."""
    bar = flat(parent)
    bar.pack(fill="x", pady=(0, px(14)))
    bar.actions = flat(bar)
    bar.actions.pack(side="right", anchor="n")
    text = flat(bar)
    text.pack(side="left", fill="x", expand=True)
    bar.title = ttk.Label(text, text=title, style="CardTitle.TLabel")
    bar.title.pack(anchor="w")
    bar.subtitle = ttk.Label(text, text=subtitle, style="Muted.Card.TLabel")
    if subtitle:
        bar.subtitle.pack(anchor="w", pady=(px(2), 0))
    return bar


def button(parent, text: str, command: Callable, kind: str = "Secondary", **kw) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style=f"{kind}.TButton", **kw)


def field_label(parent, text: str) -> ttk.Label:
    label = ttk.Label(parent, text=text, style="Field.Card.TLabel")
    label.pack(anchor="w", pady=(0, px(5)))
    return label


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget, self.text, self.tip, self.job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _):
        self.job = self.widget.after(450, self._show)

    def _show(self):
        if self.tip or not self.widget.winfo_exists():
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        tk.Label(
            self.tip,
            text=self.text,
            bg=C["raised"],
            fg=C["text"],
            font=font(9),
            padx=px(8),
            pady=px(4),
            highlightthickness=1,
            highlightbackground=C["input_border"],
        ).pack()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(6)
        self.tip.update_idletasks()
        self.tip.geometry(f"+{x - self.tip.winfo_width() // 2}+{y}")

    def _hide(self, _=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class IconButton(tk.Label):
    """A clickable icon, optionally with a tooltip."""

    def __init__(
        self,
        parent,
        icon: str,
        command: Callable,
        tooltip: str = "",
        bg: str | None = None,
        fg: str | None = None,
        hover_fg: str | None = None,
        size: int = 12,
    ):
        self.bg = bg or C["card"]
        self.fg, self.hover_fg = fg or C["text_sub"], hover_fg or C["text"]
        super().__init__(
            parent,
            text=ICONS[icon],
            font=icon_font(size),
            bg=self.bg,
            fg=self.fg,
            cursor="hand2",
            padx=px(6),
            pady=px(4),
        )
        self.bind(
            "<Enter>", lambda _: self.config(fg=self.hover_fg, bg=blend(C["text"], self.bg, 0.07))
        )
        self.bind("<Leave>", lambda _: self.config(fg=self.fg, bg=self.bg))
        self.bind("<Button-1>", lambda _: command())
        if tooltip:
            Tooltip(self, tooltip)


def icon_badge(parent, icon: str, color: str, bg: str | None = None, size: int = 40) -> ttk.Label:
    """An icon on a softly tinted circle."""
    image = theme.circle(px(size), tint(color, 0.16, bg or C["card"]))
    label = tk.Label(
        parent,
        image=image,
        text=ICONS[icon],
        compound="center",
        font=icon_font(round(size / 3.2)),
        fg=color,
        bg=bg or C["card"],
        bd=0,
    )
    label.image = image
    return label


def avatar(parent, name: str, bg: str, size: int = 36) -> tk.Label:
    image = theme.circle(px(size), blend(C["accent"], bg, 0.25))
    label = tk.Label(
        parent,
        image=image,
        text=initials(name),
        compound="center",
        font=font(round(size / 3.6), "semibold"),
        fg=C["accent"],
        bg=bg,
        bd=0,
    )
    label.image = image
    return label


class ProgressBar(tk.Canvas):
    """A thin rounded progress bar."""

    def __init__(self, parent, value: float = 0, color: str | None = None, bg: str | None = None):
        self.height = px(6)
        self.bg = bg or C["card"]
        super().__init__(parent, height=self.height, bg=self.bg, highlightthickness=0, bd=0)
        self.value, self.color = value, color or C["accent"]
        self.bind("<Configure>", lambda _: self.draw())

    def set(self, value: float, color: str | None = None):
        self.value = max(0.0, min(1.0, value))
        if color:
            self.color = color
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.height
        r = h / 2
        self.create_line(r, r, max(w - r, r), r, width=h, capstyle="round", fill=C["hover"])
        if self.value > 0:
            end = r + (w - 2 * r) * self.value
            self.create_line(r, r, max(end, r + 0.1), r, width=h, capstyle="round", fill=self.color)


class StatCard(ttk.Frame):
    """A headline number with an icon, a label and a caption."""

    def __init__(self, parent, icon: str, label: str, color: str):
        super().__init__(parent, style="Card.TFrame", padding=px(18))
        top = flat(self)
        top.pack(fill="x")
        icon_badge(top, icon, color).pack(side="left")
        text = flat(top)
        text.pack(side="left", padx=(px(12), 0), fill="x", expand=True)
        ttk.Label(text, text=label, style="Muted.Card.TLabel").pack(anchor="w")
        self.value = ttk.Label(text, text="—", style="Value.Card.TLabel")
        self.value.pack(anchor="w")
        self.caption = ttk.Label(self, text="", style="Muted.Card.TLabel")
        self.caption.pack(anchor="w", pady=(px(8), 0))

    def set(self, value: str, caption: str = ""):
        self.value.config(text=value)
        self.caption.config(text=caption)


# Inputs


class _Placeholder:
    """Grey hint text shown inside an empty entry."""

    def __init__(self, entry: ttk.Entry, var: tk.StringVar, text: str):
        self.label = tk.Label(entry, text=text, bg=C["input"], fg=C["muted"], font=font(10), bd=0)
        self.label.bind("<Button-1>", lambda _: entry.focus_set())
        self.var = var
        var.trace_add("write", lambda *_: self.update())
        self.update()

    def update(self):
        if self.var.get():
            self.label.place_forget()
        else:
            self.label.place(x=0, rely=0.5, anchor="w")


class _FieldBox(ttk.Frame):
    """A rounded field holding a bare entry, with a focus ring."""

    def __init__(self, parent, width: int, placeholder: str = ""):
        super().__init__(parent, style="Field.TFrame", padding=(px(10), px(7)))
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, style="Bare.TEntry", width=width)
        self.entry.bind("<FocusIn>", lambda _: self.config(style="FieldFocus.TFrame"), add="+")
        self.entry.bind("<FocusOut>", lambda _: self.config(style="Field.TFrame"), add="+")
        if placeholder:
            _Placeholder(self.entry, self.var, placeholder)

    @property
    def text(self) -> str:
        return self.var.get().strip()

    def focus_set(self):
        self.entry.focus_set()


class SearchBox(_FieldBox):
    """Search field that calls `on_change` shortly after the user stops typing."""

    def __init__(self, parent, on_change: Callable, placeholder: str = "Search", width: int = 22):
        super().__init__(parent, width, placeholder)
        tk.Label(
            self, text=ICONS["search"], font=icon_font(10), bg=C["input"], fg=C["muted"], bd=0
        ).pack(side="left", padx=(0, px(8)))
        self.entry.pack(side="left", fill="x", expand=True)
        self._job = None
        self._on_change = on_change
        self.var.trace_add("write", self._schedule)
        self.entry.bind("<Escape>", lambda _: self.var.set(""))

    def _schedule(self, *_):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(300, self._on_change)


class DateEntry(_FieldBox):
    """A date field (YYYY-MM-DD) with a pop-up calendar."""

    def __init__(self, parent, on_change: Callable | None = None, placeholder: str = "YYYY-MM-DD"):
        super().__init__(parent, 12, placeholder)
        self.on_change = on_change
        self.entry.pack(side="left", fill="x", expand=True)
        pick = tk.Label(
            self,
            text=ICONS["calendar"],
            font=icon_font(11),
            bg=C["input"],
            fg=C["text_sub"],
            cursor="hand2",
            bd=0,
        )
        pick.pack(side="right", padx=(px(8), 0))
        pick.bind("<Button-1>", lambda _: self.open_calendar())
        pick.bind("<Enter>", lambda _: pick.config(fg=C["accent"]))
        pick.bind("<Leave>", lambda _: pick.config(fg=C["text_sub"]))
        self.entry.bind("<Return>", lambda _: self._changed())
        self._last = ""

    def get(self) -> str:
        return self.text

    def set(self, value: str, notify: bool = False):
        self.var.set(value)
        if notify:
            self._changed()

    def _changed(self):
        if self.text != self._last:
            self._last = self.text
            if self.on_change:
                self.on_change()

    def open_calendar(self):
        try:
            current = dt.date.fromisoformat(self.text)
        except ValueError:
            current = dt.date.today()
        CalendarPopup(self, current, lambda day: self.set(day.isoformat(), notify=True))


class CalendarPopup(tk.Toplevel):
    """Month calendar under a date field. Only one is open at a time; it closes on a pick,
    Escape, a click anywhere else, the window moving, or the app losing focus."""

    current: "CalendarPopup | None" = None

    def __init__(self, anchor: tk.Widget, selected: dt.date, on_pick: Callable[[dt.date], None]):
        CalendarPopup.close_open()
        super().__init__(anchor)
        CalendarPopup.current = self
        self.anchor = anchor
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=C["input_border"])
        self.selected, self.on_pick = selected, on_pick
        self.month = selected.replace(day=1)
        self.body = tk.Frame(self, bg=C["raised"], padx=px(12), pady=px(10))
        self.body.pack(padx=1, pady=1)
        self.render()
        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + px(4)
        self.geometry(f"+{x}+{y}")
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<FocusOut>", self._focus_out)
        self._watch(anchor.winfo_toplevel())
        self.focus_force()

    @staticmethod
    def _watch(window: tk.Misc) -> None:
        # Clicks anywhere in a window also reach the window's own bindings, so one
        # binding per window is enough to notice clicks outside the calendar
        if getattr(window, "_calendar_watch", False):
            return
        window.bind("<Button-1>", CalendarPopup._outside_click, add="+")
        window.bind("<Configure>", CalendarPopup._window_moved, add="+")
        window._calendar_watch = True

    @classmethod
    def close_open(cls) -> None:
        popup, cls.current = cls.current, None
        if popup is not None and popup.winfo_exists():
            popup.destroy()

    @classmethod
    def _outside_click(cls, event) -> None:
        popup = cls.current
        # A click on the date field itself (e.g. its calendar icon) is what opened it
        if popup is not None and not str(event.widget).startswith(str(popup.anchor)):
            cls.close_open()

    @classmethod
    def _window_moved(cls, event) -> None:
        widget = event.widget
        if isinstance(widget, tk.Misc) and widget is widget.winfo_toplevel():
            cls.close_open()

    def destroy(self) -> None:
        if CalendarPopup.current is self:
            CalendarPopup.current = None
        super().destroy()

    def _focus_out(self, _):
        # Fires when the user switches to another program
        self.after(100, lambda: self.winfo_exists() and self.focus_get() is None and self.destroy())

    def shift(self, months: int):
        index = self.month.year * 12 + self.month.month - 1 + months
        self.month = dt.date(index // 12, index % 12 + 1, 1)
        self.render()

    def render(self):
        for child in self.body.winfo_children():
            child.destroy()
        bg = C["raised"]
        head = tk.Frame(self.body, bg=bg)
        head.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, px(6)))
        IconButton(head, "left", lambda: self.shift(-1), bg=bg, size=10).pack(side="left")
        tk.Label(
            head, text=f"{self.month:%B %Y}", bg=bg, fg=C["text"], font=font(10, "semibold")
        ).pack(side="left", expand=True)
        IconButton(head, "right", lambda: self.shift(1), bg=bg, size=10).pack(side="right")
        for col, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(self.body, text=name, bg=bg, fg=C["muted"], font=font(8, "semibold")).grid(
                row=1, column=col, pady=(0, px(2))
            )
        today = dt.date.today()
        weeks = calendar.Calendar().monthdatescalendar(self.month.year, self.month.month)
        for row, week in enumerate(weeks, start=2):
            for col, day in enumerate(week):
                selected = day == self.selected
                fg = C["text"] if day.month == self.month.month else C["muted"]
                if day == today and not selected:
                    fg = C["accent"]
                cell_bg = C["accent"] if selected else bg
                cell = tk.Label(
                    self.body,
                    text=str(day.day),
                    width=3,
                    bg=cell_bg,
                    fg=C["on_accent"] if selected else fg,
                    font=font(9, "semibold" if selected or day == today else ""),
                    cursor="hand2",
                    pady=px(3),
                )
                cell.grid(row=row, column=col, padx=1, pady=1)
                cell.bind("<Button-1>", lambda _, d=day: self.pick(d))
                if not selected:
                    cell.bind("<Enter>", lambda _, c=cell: c.config(bg=C["hover"]))
                    cell.bind("<Leave>", lambda _, c=cell: c.config(bg=bg))
        foot = tk.Label(
            self.body, text="Today", bg=bg, fg=C["accent"], font=font(9, "semibold"), cursor="hand2"
        )
        foot.grid(row=len(weeks) + 2, column=0, columnspan=7, pady=(px(6), 0))
        foot.bind("<Button-1>", lambda _: self.pick(today))

    def pick(self, day: dt.date):
        self.destroy()
        self.on_pick(day)


# Tables


class Table(ttk.Frame):
    """A table with an optional status column (coloured dot) and an empty state.

    Columns are (key, heading, width) or (key, heading, width, anchor)."""

    def __init__(
        self,
        parent,
        columns: list[tuple],
        selectmode: str = "browse",
        status_heading: str | None = None,
        empty: tuple[str, str] = ("info", "Nothing here yet"),
    ):
        super().__init__(parent, style="Flat.TFrame")
        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(
            self,
            columns=keys,
            show="tree headings" if status_heading else "headings",
            selectmode=selectmode,
        )
        if status_heading:
            self.tree.heading("#0", text=status_heading.upper(), anchor="w")
            self.tree.column("#0", width=px(130), minwidth=px(110), stretch=False, anchor="w")
        for key, heading, width, *anchor in columns:
            side = anchor[0] if anchor else "w"
            self.tree.heading(key, text=heading.upper(), anchor=side)
            self.tree.column(key, width=px(width), minwidth=px(50), anchor=side)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y", padx=(px(6), 0))

        self.tree.tag_configure("odd", background=blend(C["text"], C["card"], 0.025))
        self.tree.tag_configure("muted", foreground=C["muted"])
        self.tree.tag_configure("danger", foreground=C["danger"])
        self.tree.tag_configure("unsaved", font=(theme.FONT_SEMI, 10), foreground=C["accent"])
        self.tree.tag_configure(
            "separator", background=C["raised"], foreground=C["text_sub"], font=font(9, "semibold")
        )
        self.dots = {s: theme.circle(px(10), color) for s, color in STATUS_COLORS.items()}
        self.dots[None] = theme.rounded(px(10), px(10), px(5), None, C["muted"], max(px(1.5), 1))

        self.empty = flat(self)
        self.empty_icon = icon_badge(self.empty, empty[0], C["muted"], size=48)
        self.empty_icon.pack()
        self.empty_text = ttk.Label(self.empty, text=empty[1], style="Sub.Card.TLabel")
        self.empty_text.pack(pady=(px(10), 0))
        self.count = 0
        self._show_empty()

    def _show_empty(self):
        self.empty.place(relx=0.5, rely=0.55, anchor="center")

    def set_empty(self, text: str, icon: str | None = None):
        self.empty_text.config(text=text)
        if icon:
            self.empty_icon.config(text=ICONS[icon])

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.count = 0
        self._show_empty()

    def add(self, iid, values, tags=(), status: str | None = "", status_text: str | None = None):
        """status="" means no status column; None draws an empty ring."""
        options = {"values": values, "tags": (*tags, "odd") if self.count % 2 else tags}
        if status != "":
            options["image"] = self.dots[status]
            options["text"] = f"  {status_text if status_text is not None else status or '—'}"
        self.tree.insert("", "end", iid=str(iid), **options)
        self.count += 1
        self.empty.place_forget()

    def add_separator(self, iid, text: str, columns: int):
        self.tree.insert(
            "", "end", iid=str(iid), text=f"  {text}", values=[""] * columns, tags=("separator",)
        )

    def selected(self) -> list[str]:
        return [i for i in self.tree.selection() if not i.startswith("sep")]

    def selected_one(self) -> str | None:
        items = self.selected()
        return items[0] if items else None

    def on_double_click(self, callback: Callable[[str], None]) -> None:
        def handler(event):
            if self.tree.identify_region(event.x, event.y) in ("cell", "tree") and (
                item := self.selected_one()
            ):
                callback(item)

        self.tree.bind("<Double-1>", handler)


# Dialogs and notifications


class Dialog(tk.Toplevel):
    """A modal window centred on its parent, with the app's look."""

    def __init__(self, parent, title: str, width: int = 400):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.body = flat(self, padding=px(24))
        self.body.pack(fill="both", expand=True)
        self.min_width = px(width)
        self.bind("<Escape>", lambda _: self.destroy())

    def show(self):
        self.update_idletasks()
        owner = self.master.winfo_toplevel()
        w = max(self.winfo_reqwidth(), self.min_width)
        h = self.winfo_reqheight()
        x = owner.winfo_rootx() + (owner.winfo_width() - w) // 2
        y = owner.winfo_rooty() + (owner.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        theme.style_window(self)
        self.deiconify()
        self.grab_set()
        self.focus_force()

    def footer(self) -> ttk.Frame:
        bar = flat(self.body)
        bar.pack(fill="x", pady=(px(18), 0))
        return bar


def _message_dialog(parent, title, message, kind, buttons) -> bool:
    colors = {
        "error": C["danger"],
        "danger": C["danger"],
        "info": C["accent"],
        "success": C["success"],
    }
    icons = {"error": "warning", "danger": "warning", "info": "info", "success": "check_circle"}
    dialog = Dialog(parent, title, width=380)
    row = flat(dialog.body)
    row.pack(fill="x")
    icon_badge(row, icons[kind], colors[kind], size=44).pack(side="left", anchor="n")
    text = flat(row)
    text.pack(side="left", fill="x", expand=True, padx=(px(14), 0))
    ttk.Label(text, text=title, style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(text, text=message, style="Sub.Card.TLabel", wraplength=px(280), justify="left").pack(
        anchor="w", pady=(px(4), 0)
    )
    result = {"ok": False}

    def close(ok: bool):
        result["ok"] = ok
        dialog.destroy()

    bar = dialog.footer()
    for text_, kind_, ok in reversed(buttons):
        b = button(bar, text_, lambda ok=ok: close(ok), kind_)
        b.pack(side="right", padx=(px(8), 0))
        if ok:
            b.focus_set()
    dialog.bind("<Return>", lambda _: close(True))
    dialog.show()
    dialog.wait_window()
    return result["ok"]


def alert(parent, title: str, message: str, kind: str = "info") -> None:
    _message_dialog(parent, title, message, kind, [("OK", "Primary", True)])


def confirm(parent, title: str, message: str, action: str = "Confirm", danger: bool = True) -> bool:
    return _message_dialog(
        parent,
        title,
        message,
        "danger" if danger else "info",
        [("Cancel", "Ghost", False), (action, "Danger" if danger else "Primary", True)],
    )


class FormDialog(Dialog):
    """Fields: (key, label, kind[, options]) where kind is entry, password, combo,
    check or date. `on_submit(values)` may raise ValueError or ApiError to keep the
    dialog open and show the message."""

    def __init__(
        self, parent, title, fields, on_submit, initial=None, submit_text="Save", subtitle=""
    ):
        super().__init__(parent, title, width=420)
        self.on_submit = on_submit
        self.getters: dict[str, Callable] = {}
        initial = initial or {}
        ttk.Label(self.body, text=title, style="CardTitle.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(self.body, text=subtitle, style="Muted.Card.TLabel").pack(
                anchor="w", pady=(px(2), 0)
            )
        flat(self.body, height=px(14)).pack()

        first = None
        for key, label, kind, *options in fields:
            value = initial.get(key)
            if kind == "check":
                var = tk.BooleanVar(value=True if value is None else bool(value))
                ttk.Checkbutton(self.body, text=label, variable=var).pack(
                    anchor="w", pady=(px(2), px(12))
                )
                self.getters[key] = var.get
                continue
            field_label(self.body, label)
            if kind == "date":
                widget = DateEntry(self.body)
                widget.set(value or "")
                widget.pack(fill="x", pady=(0, px(12)))
                self.getters[key] = widget.get
                first = first or widget
                continue
            var = tk.StringVar(value="" if value is None else str(value))
            if kind == "combo":
                widget = ttk.Combobox(
                    self.body, textvariable=var, values=options[0], state="readonly"
                )
            else:
                widget = ttk.Entry(
                    self.body, textvariable=var, show="•" if kind == "password" else ""
                )
            widget.pack(fill="x", pady=(0, px(12)))
            self.getters[key] = lambda var=var: var.get().strip()
            first = first or widget

        self.error = ttk.Label(self.body, text="", style="Error.Card.TLabel", wraplength=px(360))
        self.error.pack(anchor="w")
        bar = self.footer()
        button(bar, submit_text, self._submit, "Primary").pack(side="right")
        button(bar, "Cancel", self.destroy, "Ghost").pack(side="right", padx=(0, px(8)))
        self.bind("<Return>", lambda _: self._submit())
        self.show()
        if first is not None:
            first.focus_set()

    def _submit(self):
        values = {key: get() for key, get in self.getters.items()}
        try:
            self.on_submit(values)
        except (ValueError, ApiError) as exc:
            self.error.config(text=str(exc))
            return
        self.destroy()


class PickDialog(Dialog):
    """Pick several items from a searchable list. Items are (id, label)."""

    def __init__(
        self,
        parent,
        title: str,
        items: list[tuple[str, str]],
        on_submit,
        action: str = "Add selected",
    ):
        super().__init__(parent, title, width=460)
        self.items, self.on_submit = items, on_submit
        ttk.Label(self.body, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            self.body, text="Ctrl- or Shift-click to choose several", style="Muted.Card.TLabel"
        ).pack(anchor="w", pady=(px(2), px(12)))
        self.search = SearchBox(self.body, self._fill, "Search by name or ID", width=40)
        self.search.pack(fill="x", pady=(0, px(10)))
        box = ttk.Frame(self.body, style="Field.TFrame", padding=px(6))
        box.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(
            box,
            selectmode="extended",
            height=12,
            bg=C["input"],
            fg=C["text"],
            selectbackground=blend(C["accent"], C["input"], 0.35),
            selectforeground=C["text"],
            font=font(10),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda _: self._count())
        self.status = ttk.Label(self.body, text="", style="Muted.Card.TLabel")
        self.status.pack(anchor="w", pady=(px(8), 0))
        self.error = ttk.Label(self.body, text="", style="Error.Card.TLabel", wraplength=px(400))
        self.error.pack(anchor="w")
        bar = self.footer()
        button(
            bar, "Select all", lambda: (self.listbox.select_set(0, "end"), self._count()), "Ghost"
        ).pack(side="left")
        self.submit_button = button(bar, action, self._submit, "Primary")
        self.submit_button.pack(side="right")
        button(bar, "Cancel", self.destroy, "Ghost").pack(side="right", padx=(0, px(8)))
        self.visible: list[tuple[str, str]] = []
        self._fill()
        self.show()
        self.search.focus_set()

    def _fill(self):
        needle = self.search.text.lower()
        self.visible = [item for item in self.items if needle in item[1].lower()]
        self.listbox.delete(0, "end")
        for _, label in self.visible:
            self.listbox.insert("end", f"  {label}")
        self._count()

    def _count(self):
        chosen = len(self.listbox.curselection())
        self.status.config(text=f"{chosen} selected  ·  {len(self.visible)} shown")

    def _submit(self):
        chosen = [self.visible[i][0] for i in self.listbox.curselection()]
        if not chosen:
            self.error.config(text="Select at least one student.")
            return
        try:
            self.on_submit(chosen)
        except ApiError as exc:
            self.error.config(text=str(exc))
            return
        self.destroy()


class Toast:
    """Brief, non-blocking notification in the bottom-right corner."""

    KEY = "#010203"  # painted transparent so the toast can have rounded corners

    def __init__(self, root: tk.Tk):
        self.root = root
        self.window: tk.Toplevel | None = None
        self.jobs: list[str] = []
        style = ttk.Style(root)
        style.layout("Toast.TFrame", [("Raised.bg", {"sticky": "nsew"})])
        style.configure("Toast.TFrame", background=self.KEY)

    def show(self, message: str, kind: str = "success"):
        self._close()
        color = {"success": C["success"], "error": C["danger"], "info": C["accent"]}[kind]
        icon = {"success": "check_circle", "error": "warning", "info": "info"}[kind]
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=self.KEY)
        try:
            window.attributes("-transparentcolor", self.KEY)
        except tk.TclError:
            window.configure(bg=C["raised"])
        frame = ttk.Frame(window, style="Toast.TFrame", padding=(px(14), px(12)))
        frame.pack()
        tk.Label(frame, text=ICONS[icon], font=icon_font(13), fg=color, bg=C["raised"]).pack(
            side="left"
        )
        tk.Label(
            frame,
            text=message,
            font=font(10),
            fg=C["text"],
            bg=C["raised"],
            wraplength=px(320),
            justify="left",
        ).pack(side="left", padx=(px(10), px(4)))
        window.update_idletasks()
        x = self.root.winfo_rootx() + self.root.winfo_width() - window.winfo_reqwidth() - px(24)
        y = self.root.winfo_rooty() + self.root.winfo_height() - window.winfo_reqheight() - px(24)
        window.geometry(f"+{x}+{y}")
        self.window = window
        self.jobs = [self.root.after(2600, self._fade, 1.0)]

    def _fade(self, alpha: float):
        if self.window is None or not self.window.winfo_exists():
            return
        if alpha <= 0.05:
            self._close()
            return
        self.window.attributes("-alpha", alpha)
        self.jobs.append(self.root.after(30, self._fade, alpha - 0.1))

    def _close(self):
        for job in self.jobs:
            self.root.after_cancel(job)
        self.jobs = []
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
