import datetime as dt
import tkinter as tk
from tkinter import ttk

from client.api import ApiClient
from client.ui import theme
from client.ui.pages.admin import AuditPage, TermsPage, UsersPage
from client.ui.pages.courses import CoursesPage
from client.ui.pages.dashboard import DashboardPage
from client.ui.pages.my_attendance import MyAttendancePage
from client.ui.pages.records import RecordsPage
from client.ui.pages.register import RegisterPage
from client.ui.pages.students import StudentsPage
from client.ui.theme import ICONS, C, blend, px
from client.ui.widgets import (
    CalendarPopup,
    FormDialog,
    IconButton,
    Toast,
    avatar,
    font,
    icon_font,
)

PAGES_BY_ROLE = {
    "admin": [
        DashboardPage,
        RegisterPage,
        StudentsPage,
        CoursesPage,
        RecordsPage,
        UsersPage,
        TermsPage,
        AuditPage,
    ],
    "lecturer": [DashboardPage, RegisterPage, StudentsPage, CoursesPage, RecordsPage],
    "student": [MyAttendancePage],
}
ADMIN_SECTION_STARTS = "users"


class NavItem(tk.Frame):
    """A sidebar entry: icon and label, with hover and selected states."""

    def __init__(self, parent, icon: str, text: str, command, shortcut: str = ""):
        super().__init__(parent, bg=C["sidebar"], cursor="hand2")
        self.selected = False
        self.bar = tk.Frame(self, width=px(3), bg=C["sidebar"])
        self.bar.pack(side="left", fill="y")
        self.icon = tk.Label(
            self, text=ICONS[icon], font=icon_font(13), bg=C["sidebar"], fg=C["muted"]
        )
        self.icon.pack(side="left", padx=(px(16), px(12)), pady=px(9))
        self.label = tk.Label(
            self, text=text, font=font(10), bg=C["sidebar"], fg=C["text_sub"], anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True)
        self.hint = tk.Label(self, text=shortcut, font=font(8), bg=C["sidebar"], fg=C["sidebar"])
        self.hint.pack(side="right", padx=(0, px(14)))
        for widget in (self, self.icon, self.label, self.hint):
            widget.bind("<Button-1>", lambda _: command())
            widget.bind("<Enter>", lambda _: self._paint(hover=True))
            widget.bind("<Leave>", lambda _: self._paint(hover=False))

    def select(self, selected: bool):
        self.selected = selected
        self._paint(False)

    def _paint(self, hover: bool):
        if self.selected:
            bg, fg, icon_fg, bar = (
                blend(C["accent"], C["sidebar"], 0.12),
                C["text"],
                C["accent"],
                C["accent"],
            )
        elif hover:
            bg, fg, icon_fg, bar = C["hover"], C["text"], C["text_sub"], C["hover"]
        else:
            bg, fg, icon_fg, bar = C["sidebar"], C["text_sub"], C["muted"], C["sidebar"]
        for widget in (self, self.icon, self.label, self.hint):
            widget.config(bg=bg)
        self.label.config(fg=fg, font=font(10, "semibold" if self.selected else ""))
        self.icon.config(fg=icon_fg)
        self.hint.config(fg=C["muted"] if hover or self.selected else bg)
        self.bar.config(bg=bar)


class Shell(ttk.Frame):
    """The signed-in window: sidebar navigation, page header and the current page."""

    def __init__(self, parent, app, api: ApiClient):
        super().__init__(parent)
        self.app = app
        self.api = api
        self.user = api.user
        self.is_admin = self.user["role"] == "admin"
        self.toaster = Toast(self.winfo_toplevel())
        self.pages: dict[str, ttk.Frame] = {}
        self.nav: dict[str, NavItem] = {}
        self.current: str | None = None

        self._build_sidebar()
        main = ttk.Frame(self)
        main.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(main, padding=(px(32), px(26), px(32), px(18)))
        header.pack(fill="x")
        right = ttk.Frame(header)
        right.pack(side="right", anchor="n")
        self.clock = ttk.Label(right, text="", style="Clock.TLabel")
        self.clock.pack(anchor="e")
        self.date_label = ttk.Label(right, text="", style="PageSub.TLabel")
        self.date_label.pack(anchor="e")
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="x", expand=True)
        self.title_label = ttk.Label(titles, text="", style="PageTitle.TLabel")
        self.title_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(titles, text="", style="PageSub.TLabel")
        self.subtitle_label.pack(anchor="w", pady=(px(2), 0))

        self.content = ttk.Frame(main, padding=(px(32), 0, px(32), px(28)))
        self.content.pack(fill="both", expand=True)
        for page_class in PAGES_BY_ROLE[self.user["role"]]:
            self.pages[page_class.key] = page_class(self.content, self)

        root = self.winfo_toplevel()
        for i, key in enumerate(self.pages, start=1):
            if i <= 9:
                root.bind(f"<Control-Key-{i}>", lambda _, k=key: self.show_page(k))
        self.tick()
        self.show_page(next(iter(self.pages)))

    def _build_sidebar(self):
        side = tk.Frame(self, bg=C["sidebar"], width=px(240))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=C["sidebar"])
        brand.pack(fill="x", padx=px(20), pady=(px(26), px(26)))
        logo_image = theme.rounded(px(36), px(36), px(10), C["accent"])
        logo = tk.Label(
            brand,
            image=logo_image,
            text="",
            compound="center",
            font=icon_font(15),
            fg=C["on_accent"],
            bg=C["sidebar"],
        )
        logo.image = logo_image
        logo.pack(side="left")
        names = tk.Frame(brand, bg=C["sidebar"])
        names.pack(side="left", padx=(px(12), 0))
        tk.Label(
            names, text="AttendEase", font=(theme.FONT_DISPLAY, 14), fg=C["text"], bg=C["sidebar"]
        ).pack(anchor="w")
        tk.Label(
            names, text="Attendance made easy", font=font(8), fg=C["muted"], bg=C["sidebar"]
        ).pack(anchor="w")

        def section(text):
            tk.Label(
                side, text=text, font=font(8, "semibold"), fg=C["muted"], bg=C["sidebar"]
            ).pack(anchor="w", padx=px(22), pady=(px(10), px(6)))

        section("MENU")
        for i, page_class in enumerate(PAGES_BY_ROLE[self.user["role"]], start=1):
            if page_class.key == ADMIN_SECTION_STARTS:
                section("ADMINISTRATION")
            item = NavItem(
                side,
                page_class.icon,
                page_class.title,
                lambda k=page_class.key: self.show_page(k),
                shortcut=f"Ctrl+{i}" if i <= 9 else "",
            )
            item.pack(fill="x", padx=(0, px(12)))
            self.nav[page_class.key] = item

        account = tk.Frame(side, bg=C["sidebar"])
        account.pack(side="bottom", fill="x", padx=px(16), pady=px(18))
        tk.Frame(side, height=1, bg=C["line"]).pack(side="bottom", fill="x", padx=px(16))
        avatar(account, self.user["full_name"], C["sidebar"]).pack(side="left")
        who = tk.Frame(account, bg=C["sidebar"])
        who.pack(side="left", padx=(px(10), 0), fill="x", expand=True)
        name = self.user["full_name"]
        tk.Label(
            who,
            text=name if len(name) <= 18 else name[:17] + "…",
            font=font(10, "semibold"),
            fg=C["text"],
            bg=C["sidebar"],
        ).pack(anchor="w")
        tk.Label(
            who, text=self.user["role"].title(), font=font(8), fg=C["muted"], bg=C["sidebar"]
        ).pack(anchor="w")
        IconButton(
            account, "signout", self.logout, "Sign out", bg=C["sidebar"], hover_fg=C["danger"]
        ).pack(side="right")
        IconButton(account, "lock", self.change_password, "Change password", bg=C["sidebar"]).pack(
            side="right"
        )

    def show_page(self, key: str, **options):
        if key not in self.pages:
            return
        CalendarPopup.close_open()
        if self.current:
            self.pages[self.current].pack_forget()
            self.nav[self.current].select(False)
        self.current = key
        page = self.pages[key]
        self.nav[key].select(True)
        page.pack(fill="both", expand=True)
        self.update_header()
        page.refresh(**options)
        self.update_header()

    def update_header(self):
        page = self.pages[self.current]
        self.title_label.config(text=page.title)
        self.subtitle_label.config(text=page.subtitle)

    def tick(self):
        if not self.winfo_exists():
            return
        now = dt.datetime.now()
        self.clock.config(text=now.strftime("%I:%M %p").lstrip("0"))
        self.date_label.config(text=f"{now:%A}, {now.day} {now:%B %Y}")
        self.after(1000 * (60 - now.second), self.tick)

    def toast(self, message: str, kind: str = "success"):
        self.toaster.show(message, kind)

    def change_password(self):
        def submit(values):
            if values["new"] != values["confirm"]:
                raise ValueError("The new passwords do not match.")
            if len(values["new"]) < 8:
                raise ValueError("The new password must be at least 8 characters.")
            self.api.change_password(values["current"], values["new"])
            self.toast("Your password has been changed.")

        FormDialog(
            self,
            "Change password",
            [
                ("current", "Current password", "password"),
                ("new", "New password", "password"),
                ("confirm", "Confirm new password", "password"),
            ],
            submit,
            submit_text="Change password",
            subtitle="Use at least 8 characters.",
        )

    def logout(self):
        for i in range(1, 10):
            self.winfo_toplevel().unbind(f"<Control-Key-{i}>")
        self.toaster._close()
        self.app.logout()
