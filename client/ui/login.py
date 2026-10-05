import tkinter as tk
from tkinter import ttk

from client.api import ApiClient, ApiError
from client.config import load_api_url, save_api_url
from client.ui import theme
from client.ui.theme import ICONS, C, blend, px
from client.ui.widgets import button, field_label, flat, font, icon_font

FEATURES = (
    ("checklist", "Take a full class register in seconds"),
    ("trending", "See attendance trends at a glance"),
    ("history", "Every change is recorded and auditable"),
)


class BrandPanel(tk.Canvas):
    """Left half of the sign-in screen: a soft gradient with the product pitch."""

    TOP, BOTTOM = "#1e2a4a", "#2a1f45"

    def __init__(self, parent):
        super().__init__(parent, highlightthickness=0, bd=0, bg=self.TOP)
        self.bind("<Configure>", lambda _: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        steps = 120
        for i in range(steps):
            color = blend(self.BOTTOM, self.TOP, i / (steps - 1))
            y0, y1 = h * i / steps, h * (i + 1) / steps + 1
            self.create_rectangle(0, y0, w, y1, fill=color, outline="")
        # Soft decorative glows
        for cx, cy, r, color, amount in (
            (w * 0.85, h * 0.15, w * 0.35, C["accent"], 0.10),
            (w * 0.1, h * 0.9, w * 0.4, C["mauve"], 0.10),
        ):
            for k in range(10, 0, -1):
                rr = r * k / 10
                fill = blend(
                    color, blend(self.BOTTOM, self.TOP, cy / max(h, 1)), amount * (11 - k) / 10
                )
                self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=fill, outline="")

        left = px(56)
        y = h * 0.22
        logo = theme.rounded(px(52), px(52), px(14), C["accent"])
        self.create_image(left, y, image=logo, anchor="w")
        self.create_text(
            left + px(26), y, text="", font=icon_font(22), fill=C["on_accent"], anchor="center"
        )
        self.create_text(
            left + px(68),
            y,
            text="AttendEase",
            font=(theme.FONT_DISPLAY, 20),
            fill=C["text"],
            anchor="w",
        )
        y += px(84)
        self.create_text(
            left,
            y,
            text="Attendance,\nmade effortless.",
            font=(theme.FONT_DISPLAY, 30),
            fill=C["text"],
            anchor="nw",
        )
        y += px(118)
        self.create_text(
            left,
            y,
            text=(
                "One place for registers, students and reports,\n"
                "for admins, lecturers and students."
            ),
            font=font(11),
            fill=C["text_sub"],
            anchor="nw",
        )
        y += px(78)
        for icon, text in FEATURES:
            badge = theme.circle(px(34), blend(C["accent"], self.TOP, 0.18))
            self.create_image(left, y, image=badge, anchor="w")
            self.create_text(
                left + px(17), y, text=ICONS[icon], font=icon_font(12), fill=C["accent"]
            )
            self.create_text(left + px(48), y, text=text, font=font(10), fill=C["text"], anchor="w")
            y += px(48)


class LoginFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        BrandPanel(self).place(relx=0, rely=0, relwidth=0.5, relheight=1)
        side = ttk.Frame(self)
        side.place(relx=0.5, rely=0, relwidth=0.5, relheight=1)

        box = ttk.Frame(side, style="Card.TFrame", padding=(px(36), px(34)))
        box.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(
            box, text="Welcome back", style="CardTitle.TLabel", font=(theme.FONT_DISPLAY, 20)
        ).pack(anchor="w")
        ttk.Label(box, text="Sign in with your school account.", style="Muted.Card.TLabel").pack(
            anchor="w", pady=(px(4), px(24))
        )

        self.email = tk.StringVar()
        self.password = tk.StringVar()
        field_label(box, "Email")
        email = ttk.Entry(box, textvariable=self.email, width=34)
        email.pack(fill="x", pady=(0, px(16)))
        email.focus_set()

        field_label(box, "Password")
        pw_row = flat(box)
        pw_row.pack(fill="x")
        self.password_entry = ttk.Entry(pw_row, textvariable=self.password, show="•")
        self.password_entry.pack(side="left", fill="x", expand=True)
        self.eye = tk.Label(
            pw_row,
            text=ICONS["eye"],
            font=icon_font(12),
            bg=C["card"],
            fg=C["muted"],
            cursor="hand2",
        )
        self.eye.pack(side="left", padx=(px(8), 0))
        self.eye.bind("<Button-1>", lambda _: self.toggle_password())
        for widget in (email, self.password_entry):
            widget.bind("<Return>", lambda _: self.sign_in())

        self.server = tk.StringVar(value=load_api_url())
        self.server_box = flat(box)
        field_label(self.server_box, "Server address")
        ttk.Entry(self.server_box, textvariable=self.server).pack(fill="x")
        self.server_toggle = ttk.Label(
            box, text="Server settings  ›", style="Muted.Card.TLabel", cursor="hand2"
        )
        self.server_toggle.pack(anchor="w", pady=(px(12), 0))
        self.server_toggle.bind("<Button-1>", lambda _: self.toggle_server())

        self.error = ttk.Label(box, text="", style="Error.Card.TLabel", wraplength=px(300))
        self.error.pack(anchor="w", pady=(px(10), px(4)))
        self.sign_in_button = button(box, "Sign in", self.sign_in, "Primary")
        self.sign_in_button.pack(fill="x", ipady=px(3))

    def toggle_password(self):
        hidden = self.password_entry.cget("show") == "•"
        self.password_entry.config(show="" if hidden else "•")
        self.eye.config(fg=C["accent"] if hidden else C["muted"])

    def toggle_server(self):
        if self.server_box.winfo_ismapped():
            self.server_box.pack_forget()
            self.server_toggle.config(text="Server settings  ›")
        else:
            self.server_box.pack(fill="x", pady=(px(10), 0), before=self.error)
            self.server_toggle.config(text="Server settings  ⌄")

    def sign_in(self):
        email, password = self.email.get().strip(), self.password.get()
        server = self.server.get().strip()
        if not email or not password:
            self.error.config(text="Enter your email and password.")
            return
        if not server.startswith(("http://", "https://")):
            self.error.config(text="The server address must start with http:// or https://")
            return

        self.error.config(text="")
        self.sign_in_button.config(text="Signing in…")
        self.sign_in_button.state(["disabled"])
        self.update_idletasks()
        api = ApiClient(server)
        try:
            api.login(email, password)
        except ApiError as exc:
            api.close()
            self.error.config(text=str(exc))
            self.sign_in_button.config(text="Sign in")
            self.sign_in_button.state(["!disabled"])
            return
        save_api_url(server)
        self.app.show_main(api)
