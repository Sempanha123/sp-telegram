from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.theme_state import set_current_theme


_THEME_FILES = {
    "light": ("light.qss",),
    "dark": ("dark.qss", "components.qss"),
}


def _styles_dir() -> Path:
    return Path(__file__).with_name("styles")


def normalize_theme(theme: str | None) -> str:
    """Return one of the two supported theme names."""
    return "dark" if str(theme or "").strip().lower() == "dark" else "light"


def theme_path(theme: str = "light") -> Path:
    return _styles_dir() / _THEME_FILES[normalize_theme(theme)][0]


def load_stylesheet(theme: str = "light") -> str:
    """Load the complete Qt stylesheet for ``theme``.

    Each theme file is intentionally self-contained. The previous loader built
    a small stylesheet in Python and never loaded ``light.qss`` at all, which
    made the default theme look mostly unstyled. Keeping the source in QSS also
    makes it much easier to validate and maintain.
    """
    files = _THEME_FILES[normalize_theme(theme)]
    return "\n".join((_styles_dir() / name).read_text(encoding="utf-8") for name in files)


def build_palette(theme: str = "light") -> QPalette:
    """Build the native Qt palette used by custom-painted and popup widgets.

    QSS alone does not reliably update ``QStyleOption`` palettes on Windows.
    Delegates, tabs and native dialogs therefore need an explicit application
    palette or they can keep black text after switching to dark mode.
    """
    dark = normalize_theme(theme) == "dark"
    colors = {
        "window": "#0B1020" if dark else "#F5F7FB",
        "surface": "#11182B" if dark else "#FFFFFF",
        "alternate": "#141D32" if dark else "#F8FAFD",
        "text": "#F5F7FF" if dark else "#172033",
        "muted": "#7F8BA6" if dark else "#8491A9",
        "disabled": "#4D5870" if dark else "#AEBACD",
        "button": "#141D32" if dark else "#FFFFFF",
        "highlight": "#243253" if dark else "#DDE0F6",
        "highlighted": "#F2F5FF" if dark else "#172033",
        "link": "#67E8F9" if dark else "#2563EB",
        "visited": "#8B7CFF" if dark else "#5B5CE2",
    }
    palette = QPalette()
    role_colors = {
        QPalette.ColorRole.Window: colors["window"],
        QPalette.ColorRole.WindowText: colors["text"],
        QPalette.ColorRole.Base: colors["surface"],
        QPalette.ColorRole.AlternateBase: colors["alternate"],
        QPalette.ColorRole.ToolTipBase: colors["surface"],
        QPalette.ColorRole.ToolTipText: colors["text"],
        QPalette.ColorRole.Text: colors["text"],
        QPalette.ColorRole.Button: colors["button"],
        QPalette.ColorRole.ButtonText: colors["text"],
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: colors["highlight"],
        QPalette.ColorRole.HighlightedText: colors["highlighted"],
        QPalette.ColorRole.Link: colors["link"],
        QPalette.ColorRole.LinkVisited: colors["visited"],
        QPalette.ColorRole.PlaceholderText: colors["muted"],
    }
    for role, value in role_colors.items():
        palette.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled"]))
    return palette


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """Apply a complete, native Qt-compatible theme to the application."""
    normalized = normalize_theme(theme)
    # Theme-aware delegates consult this state while Qt applies/repaints QSS.
    # Set it first so they never render one frame with the previous palette.
    set_current_theme(normalized)
    app.setPalette(build_palette(normalized))
    app.setStyleSheet(load_stylesheet(normalized))

    # QLabel pixmaps are snapshots rather than live QIcons. Refresh the small
    # set of labels registered with IconManager after a palette change.
    from app.icons import IconManager

    for widget in app.allWidgets():
        if widget.property("themeIconName"):
            IconManager.refresh_label(widget)
        widget.update()


def get_current_theme() -> str | None:
    """Get the current theme (``light`` or ``dark``)."""
    from app.theme_state import get_current_theme as _get_current_theme

    return _get_current_theme()
