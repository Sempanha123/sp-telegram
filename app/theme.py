from __future__ import annotations

from pathlib import Path

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


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """Apply a complete, native Qt-compatible theme to the application."""
    normalized = normalize_theme(theme)
    app.setStyleSheet(load_stylesheet(normalized))
    set_current_theme(normalized)


def get_current_theme() -> str | None:
    """Get the current theme (``light`` or ``dark``)."""
    from app.theme_state import get_current_theme as _get_current_theme

    return _get_current_theme()
