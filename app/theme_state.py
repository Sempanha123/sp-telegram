from __future__ import annotations

_current_theme: str | None = None


def get_current_theme() -> str | None:
    """Get the current theme ("light" or "dark")"""
    return _current_theme


def set_current_theme(theme: str) -> None:
    """Set the current theme"""
    global _current_theme
    _current_theme = theme


def is_light() -> bool:
    """Check if the current theme is light"""
    return _current_theme == "light"
