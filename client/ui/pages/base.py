from tkinter import ttk


class Page(ttk.Frame):
    """One screen in the main window. The shell shows `title` and `subtitle` above it."""

    key = ""
    title = ""
    icon = "home"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

    @property
    def subtitle(self) -> str:
        return ""

    def refresh(self, **options) -> None:
        """Called each time the page is shown; options come from Shell.show_page()."""
