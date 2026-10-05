"""Colours, fonts, icons and the ttk theme.

Rounded corners are drawn with small anti-aliased PNG images generated at start-up
(no extra libraries) and used as nine-slice ttk image elements.
"""

import base64
import struct
import tkinter as tk
import tkinter.font as tkfont
import zlib
from tkinter import ttk

# Catppuccin Mocha inspired dark palette
COLORS = {
    "sidebar": "#11111b",
    "bg": "#181825",
    "card": "#1e1e2e",
    "card_border": "#2b2c3f",
    "raised": "#262637",
    "input": "#25263a",
    "input_border": "#3a3c55",
    "hover": "#2d2e44",
    "line": "#2b2c3f",
    "text": "#cdd6f4",
    "text_sub": "#a6adc8",
    "muted": "#7f849c",
    "accent": "#89b4fa",
    "accent_hover": "#a6c6fb",
    "accent_deep": "#5b8def",
    "on_accent": "#11111b",
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "danger": "#f38ba8",
    "mauve": "#cba6f7",
    "teal": "#94e2d5",
    "peach": "#fab387",
}
C = COLORS

STATUS_COLORS = {"Present": C["success"], "Late": C["warning"], "Absent": C["danger"]}

ICONS = {
    "home": "",
    "checklist": "",
    "people": "",
    "education": "",
    "report": "",
    "admin": "",
    "calendar": "",
    "history": "",
    "signout": "",
    "lock": "",
    "search": "",
    "add": "",
    "edit": "",
    "delete": "",
    "download": "",
    "refresh": "",
    "left": "",
    "right": "",
    "eye": "",
    "warning": "",
    "info": "",
    "check": "",
    "check_circle": "",
    "person_add": "",
    "trending": "",
    "chart": "",
    "clock": "",
    "contact": "",
    "cancel": "",
    "group": "",
}

# Filled in by setup_styles() once the available fonts are known
FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"
FONT_DISPLAY = "Segoe UI Semibold"
ICON_FONT = "Segoe MDL2 Assets"

_scale = 1.0
_images: dict[tuple, tk.PhotoImage] = {}


def px(size: float) -> int:
    """Pixels scaled for the screen's DPI (fonts scale by themselves)."""
    return round(size * _scale)


def blend(color: str, base: str, amount: float) -> str:
    """Mix `amount` of `color` into `base`."""
    a = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(base[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(x * amount + y * (1 - amount)):02x}" for x, y in zip(a, b, strict=True)
    )


def tint(color: str, amount: float = 0.16, base: str | None = None) -> str:
    return blend(color, base or C["card"], amount)


# Images


def _png(width: int, height: int, rgba: bytearray) -> bytes:
    stride = width * 4
    raw = b"".join(b"\x00" + bytes(rgba[y * stride : (y + 1) * stride]) for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def _inside(x: float, y: float, w: float, h: float, r: float) -> bool:
    if x < 0 or y < 0 or x > w or y > h:
        return False
    cx = min(max(x, r), w - r)
    cy = min(max(y, r), h - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def rounded(
    w: int, h: int, r: int, fill: str | None, border: str | None = None, bw: int = 1
) -> tk.PhotoImage:
    """Anti-aliased rounded rectangle. fill=None draws only the border."""
    key = ("rr", w, h, r, fill, border, bw)
    if key in _images:
        return _images[key]
    ss = 4
    offsets = [(i + 0.5) / ss for i in range(ss)]
    fill_rgb = _rgb(fill) if fill else None
    border_rgb = _rgb(border) if border else None
    inset = bw if border else 0
    rgba = bytearray(w * h * 4)
    solid_fill = bytes((*fill_rgb, 255)) if fill_rgb else bytes(4)
    solid_border = bytes((*border_rgb, 255)) if border_rgb else solid_fill
    for y in range(h):
        in_corner_rows = y < r + 1 or y >= h - r - 1
        for x in range(w):
            i = (y * w + x) * 4
            if not (in_corner_rows and (x < r + 1 or x >= w - r - 1)):
                # Straight edges and the middle need no anti-aliasing
                on_edge = inset and (x < inset or y < inset or x >= w - inset or y >= h - inset)
                rgba[i : i + 4] = solid_border if on_edge else solid_fill
                continue
            outer = inner = 0
            for oy in offsets:
                for ox in offsets:
                    sx, sy = x + ox, y + oy
                    if _inside(sx, sy, w, h, r):
                        outer += 1
                        if not inset or _inside(
                            sx - inset, sy - inset, w - 2 * inset, h - 2 * inset, max(r - inset, 0)
                        ):
                            inner += 1
            if not outer:
                continue
            ring = outer - inner
            if fill_rgb is None:
                color, alpha = border_rgb, ring / (ss * ss)
            else:
                t = ring / outer if border_rgb else 0.0
                color = tuple(
                    round(f * (1 - t) + b * t)
                    for f, b in zip(fill_rgb, border_rgb or fill_rgb, strict=True)
                )
                alpha = outer / (ss * ss)
            rgba[i : i + 4] = bytes((*color, round(alpha * 255)))
    image = tk.PhotoImage(data=base64.b64encode(_png(w, h, rgba)))
    _images[key] = image
    return image


def circle(diameter: int, fill: str) -> tk.PhotoImage:
    return rounded(diameter, diameter, diameter // 2, fill)


def nine_slice(r: int, fill: str | None, border: str | None = None, bw: int = 1):
    """A square image for ttk to stretch, with border = r + 1 on each side.

    Tk tiles the middle rather than scaling it, so the middle is kept wide;
    a tiny middle makes large widgets very slow to draw."""
    size = 2 * (r + 1) + 48
    return rounded(size, size, r, fill, border, bw)


# Styles


def _pick_font(families: set[str], *names: str) -> str:
    return next((n for n in names if n in families), names[-1])


def _image_element(style: ttk.Style, name: str, normal, *states, border, **kw) -> None:
    # width/height 0: the image must not force a minimum size; padding 0: the
    # widget's own padding decides the spacing
    options = {"padding": 0, "width": 0, "height": 0} | kw
    style.element_create(name, "image", normal, *states, border=border, sticky="nsew", **options)


def _segment_distance(x, y, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def _pad_right(image: tk.PhotoImage, gap: int) -> tk.PhotoImage:
    """The same image with transparent space on its right (for label spacing)."""
    key = ("pad", str(image), gap)
    if key not in _images:
        padded = tk.PhotoImage(width=image.width() + gap, height=image.height())
        padded.tk.call(padded, "copy", image, "-to", 0, 0)
        _images[key] = padded
    return _images[key]


def checkbox(size: int, checked: bool, hover: bool = False) -> tk.PhotoImage:
    """A rounded checkbox, ticked or empty."""
    key = ("check", size, checked, hover)
    if key in _images:
        return _images[key]
    r = max(size // 4, 2)
    if not checked:
        border = C["accent"] if hover else C["input_border"]
        image = rounded(size, size, r, C["input"], border, max(px(1.5), 1))
        _images[key] = image
        return image
    ss = 4
    fill = _rgb(C["accent_hover"] if hover else C["accent"])
    tick = _rgb(C["on_accent"])
    stroke = size / 9
    points = [(size * 0.27, size * 0.52), (size * 0.44, size * 0.68), (size * 0.74, size * 0.34)]
    rgba = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            box = mark = 0
            for oy in range(ss):
                for ox in range(ss):
                    sx, sy = x + (ox + 0.5) / ss, y + (oy + 0.5) / ss
                    if _inside(sx, sy, size, size, r):
                        box += 1
                        d = min(
                            _segment_distance(sx, sy, *points[0], *points[1]),
                            _segment_distance(sx, sy, *points[1], *points[2]),
                        )
                        if d <= stroke:
                            mark += 1
            if box:
                t = mark / box
                color = tuple(round(f * (1 - t) + k * t) for f, k in zip(fill, tick, strict=True))
                i = (y * size + x) * 4
                rgba[i : i + 4] = bytes((*color, round(box / (ss * ss) * 255)))
    image = tk.PhotoImage(data=base64.b64encode(_png(size, size, rgba)))
    _images[key] = image
    return image


def _wrap(element: str, inner: str) -> list:
    """A layout whose background is `element`, holding the widget's padding and label."""
    return [
        (
            element,
            {
                "sticky": "nsew",
                "children": [
                    (
                        f"{inner}.padding",
                        {"sticky": "nsew", "children": [(f"{inner}.label", {"sticky": "nsew"})]},
                    )
                ],
            },
        )
    ]


def setup_styles(root: tk.Tk) -> None:
    global _scale, FONT, FONT_SEMI, FONT_DISPLAY, ICON_FONT
    _scale = max(root.winfo_fpixels("1i") / 96, 1.0)
    families = set(tkfont.families(root))
    FONT = _pick_font(families, "Segoe UI Variable Text", "Segoe UI")
    FONT_SEMI = _pick_font(families, "Segoe UI Variable Text Semibold", "Segoe UI Semibold")
    FONT_DISPLAY = _pick_font(families, "Segoe UI Variable Display Semibold", "Segoe UI Semibold")
    ICON_FONT = _pick_font(families, "Segoe Fluent Icons", "Segoe MDL2 Assets")

    root.configure(bg=C["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=C["bg"], foreground=C["text"], font=(FONT, 10))

    # Surfaces
    style.configure("TFrame", background=C["bg"])
    style.configure("Sidebar.TFrame", background=C["sidebar"])
    style.configure("Flat.TFrame", background=C["card"])
    card_r = px(12)
    _image_element(
        style, "Card.bg", nine_slice(card_r, C["card"], C["card_border"]), border=card_r + 1
    )
    style.layout("Card.TFrame", [("Card.bg", {"sticky": "nsew"})])
    style.configure("Card.TFrame", background=C["bg"])
    raised_r = px(10)
    _image_element(
        style, "Raised.bg", nine_slice(raised_r, C["raised"], C["line"]), border=raised_r + 1
    )
    style.layout("Raised.TFrame", [("Raised.bg", {"sticky": "nsew"})])
    style.configure("Raised.TFrame", background=C["card"])

    # Text
    for name, bg, fg, font in (
        ("TLabel", C["bg"], C["text"], (FONT, 10)),
        ("PageTitle.TLabel", C["bg"], C["text"], (FONT_DISPLAY, 20)),
        ("PageSub.TLabel", C["bg"], C["muted"], (FONT, 10)),
        ("Clock.TLabel", C["bg"], C["text_sub"], (FONT, 10)),
        ("Card.TLabel", C["card"], C["text"], (FONT, 10)),
        ("Strong.Card.TLabel", C["card"], C["text"], (FONT_SEMI, 10)),
        ("CardTitle.TLabel", C["card"], C["text"], (FONT_SEMI, 12)),
        ("Muted.Card.TLabel", C["card"], C["muted"], (FONT, 9)),
        ("Sub.Card.TLabel", C["card"], C["text_sub"], (FONT, 10)),
        ("Field.Card.TLabel", C["card"], C["text_sub"], (FONT_SEMI, 9)),
        ("Error.Card.TLabel", C["card"], C["danger"], (FONT, 9)),
        ("Value.Card.TLabel", C["card"], C["text"], (FONT_DISPLAY, 22)),
        ("Raised.TLabel", C["raised"], C["text"], (FONT, 10)),
        ("Muted.Raised.TLabel", C["raised"], C["muted"], (FONT, 9)),
        ("Strong.Raised.TLabel", C["raised"], C["text"], (FONT_SEMI, 10)),
    ):
        style.configure(name, background=bg, foreground=fg, font=font)

    # Pills: small rounded labels that size to their text
    pill_r = px(9)
    for name, color in (
        ("Green", C["success"]),
        ("Yellow", C["warning"]),
        ("Red", C["danger"]),
        ("Blue", C["accent"]),
        ("Grey", C["muted"]),
    ):
        _image_element(
            style, f"Pill{name}.bg", nine_slice(pill_r, tint(color, 0.16)), border=pill_r + 1
        )
        style.layout(f"{name}.Pill.TLabel", _wrap(f"Pill{name}.bg", "Label"))
        style.configure(
            f"{name}.Pill.TLabel",
            background=C["card"],
            foreground=color,
            font=(FONT_SEMI, 9),
            padding=(px(10), px(3)),
        )

    # Buttons (all buttons sit on cards)
    btn_r = px(8)
    button_kinds = {
        "Primary": (
            C["accent"],
            C["accent_hover"],
            blend(C["accent"], C["card"], 0.8),
            C["on_accent"],
        ),
        "Secondary": (C["raised"], C["hover"], C["input"], C["text"]),
        "Ghost": (C["card"], C["hover"], C["raised"], C["text_sub"]),
        "Success": (
            tint(C["success"]),
            tint(C["success"], 0.26),
            tint(C["success"], 0.34),
            C["success"],
        ),
        "Warning": (
            tint(C["warning"]),
            tint(C["warning"], 0.26),
            tint(C["warning"], 0.34),
            C["warning"],
        ),
        "Danger": (
            tint(C["danger"]),
            tint(C["danger"], 0.26),
            tint(C["danger"], 0.34),
            C["danger"],
        ),
    }
    for kind, (normal, hover, pressed, fg) in button_kinds.items():
        element = f"{kind}.btn"
        _image_element(
            style,
            element,
            nine_slice(btn_r, normal, C["line"] if kind == "Secondary" else None),
            ("disabled", nine_slice(btn_r, C["raised"])),
            ("pressed", nine_slice(btn_r, pressed)),
            ("active", nine_slice(btn_r, hover)),
            border=btn_r + 1,
        )
        name = f"{kind}.TButton"
        style.layout(name, _wrap(element, "Button"))
        style.configure(
            name,
            background=C["card"],
            foreground=fg,
            font=(FONT_SEMI, 10),
            padding=(px(14), px(7)),
            anchor="center",
        )
        style.map(name, foreground=[("disabled", C["muted"])])

    # Inputs
    field_r = px(8)
    field = nine_slice(field_r, C["input"], C["input_border"])
    field_focus = nine_slice(field_r, C["input"], C["accent"], bw=max(px(1.5), 1))
    field_disabled = nine_slice(field_r, C["raised"], C["line"])
    _image_element(
        style,
        "Rounded.field",
        field,
        ("focus", field_focus),
        ("disabled", field_disabled),
        border=field_r + 1,
        padding=(px(10), px(7)),
    )
    style.layout(
        "TEntry",
        [
            (
                "Rounded.field",
                {"sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]},
            )
        ],
    )
    entry_colors = {
        "foreground": C["text"],
        "fieldbackground": C["input"],
        "insertcolor": C["text"],
        "selectbackground": blend(C["accent"], C["input"], 0.45),
        "selectforeground": C["text"],
    }
    style.configure("TEntry", background=C["card"], **entry_colors)
    # An entry without its own field, used inside composites (search box, date picker)
    style.layout("Bare.TEntry", [("Entry.textarea", {"sticky": "nsew"})])
    style.configure("Bare.TEntry", background=C["input"], **entry_colors)
    _image_element(style, "Field.bg", field, border=field_r + 1)
    style.layout("Field.TFrame", [("Field.bg", {"sticky": "nsew"})])
    style.configure("Field.TFrame", background=C["card"])
    _image_element(style, "FieldFocus.bg", field_focus, border=field_r + 1)
    style.layout("FieldFocus.TFrame", [("FieldFocus.bg", {"sticky": "nsew"})])
    style.configure("FieldFocus.TFrame", background=C["card"])

    style.layout(
        "TCombobox",
        [
            (
                "Rounded.field",
                {
                    "sticky": "nsew",
                    "children": [
                        ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
                        ("Combobox.textarea", {"sticky": "nsew"}),
                    ],
                },
            )
        ],
    )
    style.configure(
        "TCombobox",
        background=C["input"],
        foreground=C["text"],
        fieldbackground=C["input"],
        arrowcolor=C["text_sub"],
        arrowsize=px(11),
        bordercolor=C["input"],
        lightcolor=C["input"],
        darkcolor=C["input"],
        selectbackground=C["input"],
        selectforeground=C["text"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", C["input"])],
        background=[("active", C["input"]), ("readonly", C["input"])],
        arrowcolor=[("active", C["accent"])],
        selectbackground=[("readonly", C["input"])],
        selectforeground=[("readonly", C["text"])],
    )
    root.option_add("*TCombobox*Listbox.background", C["raised"])
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", blend(C["accent"], C["raised"], 0.3))
    root.option_add("*TCombobox*Listbox.selectForeground", C["text"])
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    box, gap = px(18), px(9)
    style.element_create(
        "Rounded.indicator",
        "image",
        _pad_right(checkbox(box, False), gap),
        ("selected active", _pad_right(checkbox(box, True, hover=True), gap)),
        ("selected", _pad_right(checkbox(box, True), gap)),
        ("active", _pad_right(checkbox(box, False, hover=True), gap)),
        sticky="",
    )
    style.layout(
        "TCheckbutton",
        [
            (
                "Checkbutton.padding",
                {
                    "sticky": "nsew",
                    "children": [
                        ("Rounded.indicator", {"side": "left", "sticky": ""}),
                        ("Checkbutton.label", {"side": "left", "sticky": "nsew"}),
                    ],
                },
            )
        ],
    )
    style.configure("TCheckbutton", background=C["card"], foreground=C["text_sub"], font=(FONT, 10))
    style.map(
        "TCheckbutton", background=[("active", C["card"])], foreground=[("active", C["text"])]
    )

    # Tables
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nsew"})])
    # Rows without the expand/collapse indicator, so the first column lines up
    style.layout(
        "Treeview.Item",
        [
            (
                "Treeitem.padding",
                {
                    "sticky": "nsew",
                    "children": [
                        ("Treeitem.image", {"side": "left", "sticky": ""}),
                        ("Treeitem.text", {"side": "left", "sticky": "w"}),
                    ],
                },
            )
        ],
    )
    style.configure(
        "Treeview",
        background=C["card"],
        fieldbackground=C["card"],
        foreground=C["text"],
        rowheight=px(36),
        font=(FONT, 10),
        borderwidth=0,
        indent=0,
        padding=(px(4), 0),
    )
    style.map(
        "Treeview",
        background=[("selected", blend(C["accent"], C["card"], 0.2))],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background=C["card"],
        foreground=C["muted"],
        font=(FONT_SEMI, 9),
        relief="flat",
        borderwidth=0,
        bordercolor=C["card"],
        lightcolor=C["card"],
        darkcolor=C["card"],
        padding=(px(8), px(8)),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", C["card"])],
        foreground=[("active", C["text"])],
    )

    # Slim rounded scrollbars
    thumb_w = px(8)
    thumb = rounded(thumb_w, thumb_w * 3, thumb_w // 2, C["input_border"])
    thumb_hover = rounded(thumb_w, thumb_w * 3, thumb_w // 2, C["muted"])
    _image_element(
        style,
        "Slim.Vertical.Scrollbar.thumb",
        thumb,
        ("active", thumb_hover),
        ("pressed", thumb_hover),
        border=(0, thumb_w // 2 + 1),
        width=thumb_w,
        height=thumb_w * 3,
    )
    style.layout(
        "Vertical.TScrollbar",
        [
            (
                "Vertical.Scrollbar.trough",
                {
                    "sticky": "ns",
                    "children": [
                        ("Slim.Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nsew"})
                    ],
                },
            )
        ],
    )
    style.configure(
        "Vertical.TScrollbar",
        troughcolor=C["card"],
        background=C["card"],
        bordercolor=C["card"],
        lightcolor=C["card"],
        darkcolor=C["card"],
        gripcount=0,
        arrowsize=thumb_w,
    )


def style_window(window: tk.Misc) -> None:
    """Dark title bar on Windows 10/11 so the window chrome matches the app."""
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), 4)
        # Windows 11 also lets us colour the caption itself (COLORREF is 0x00BBGGRR)
        r, g, b = _rgb(C["sidebar"])
        caption = ctypes.c_int(b << 16 | g << 8 | r)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)
    except (AttributeError, OSError):
        pass  # Not Windows, or a version without these settings
