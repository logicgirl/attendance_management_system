"""AttendEase desktop client.

Talks to the AttendEase API (see backend/). Run with: python attendease_client.py
"""

import tkinter as tk

from client.api import ApiClient
from client.ui.login import LoginFrame
from client.ui.main_window import Shell
from client.ui.theme import px, setup_styles, style_window


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.api: ApiClient | None = None
        self.screen: tk.Widget | None = None
        root.title("AttendEase")
        setup_styles(root)
        # Fit the window to the screen, whatever the display scaling, and centre it
        width = min(px(1320), int(root.winfo_screenwidth() * 0.94))
        height = min(px(840), int(root.winfo_screenheight() * 0.88))
        x = (root.winfo_screenwidth() - width) // 2
        y = max((root.winfo_screenheight() - height) // 2 - px(20), 0)
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.minsize(min(px(1100), width), min(px(680), height))
        style_window(root)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show_login()

    def _swap(self, screen: tk.Widget) -> None:
        if self.screen is not None:
            self.screen.destroy()
        self.screen = screen
        screen.pack(fill="both", expand=True)

    def show_login(self) -> None:
        self._swap(LoginFrame(self.root, self))

    def show_main(self, api: ApiClient) -> None:
        self.api = api
        self._swap(Shell(self.root, self, api))

    def logout(self) -> None:
        if self.api is not None:
            self.api.close()
            self.api = None
        self.show_login()

    def quit(self) -> None:
        if self.api is not None:
            self.api.close()
        self.root.destroy()


def enable_sharp_text() -> None:
    """Render at the screen's real resolution instead of letting Windows blur-stretch it."""
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # Not Windows, or an old Windows version


def main() -> None:
    enable_sharp_text()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
