from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication

from app.styles.tokens import (
    BASE_BACKGROUND, BASE_SURFACE, BASE_ELEVATED, BASE_PANEL, BASE_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DISABLED,
    ACCENT_PRIMARY, ACCENT_SECONDARY, ACCENT_SUCCESS, ACCENT_WARNING, ACCENT_DANGER, ACCENT_INFO,
    BORDER_PRIMARY, BORDER_SECONDARY,
    SHADOW_SMALL, SHADOW_MEDIUM,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL,
    FONT_FAMILY, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL,
    FONT_WEIGHT_REGULAR, FONT_WEIGHT_MEDIUM, FONT_WEIGHT_SEMIBOLD, FONT_WEIGHT_BOLD,
    SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED,
    LIGHT_BASE_BACKGROUND, LIGHT_BASE_SURFACE, LIGHT_BASE_ELEVATED, LIGHT_BASE_PANEL, LIGHT_BASE_CARD,
    LIGHT_TEXT_PRIMARY, LIGHT_TEXT_SECONDARY, LIGHT_TEXT_MUTED, LIGHT_TEXT_DISABLED,
    LIGHT_ACCENT_PRIMARY, LIGHT_ACCENT_SECONDARY, LIGHT_ACCENT_SUCCESS, LIGHT_ACCENT_WARNING, LIGHT_ACCENT_DANGER, LIGHT_ACCENT_INFO,
    LIGHT_BORDER_PRIMARY, LIGHT_BORDER_SECONDARY,
    STATUS_OK, STATUS_WARNING, STATUS_ERROR, STATUS_MUTED,
    LIGHT_STATUS_OK, LIGHT_STATUS_WARNING, LIGHT_STATUS_ERROR, LIGHT_STATUS_MUTED
)
from app.theme_state import set_current_theme, get_current_theme, is_light


def _styles_dir() -> Path:
    return Path(__file__).with_name("styles")


def theme_path(theme: str = "light") -> Path:
    return _styles_dir() / ("light.qss" if str(theme).lower() == "light" else "dark.qss")


def _component_qss(theme: str) -> str:
    text = (_styles_dir() / "components.qss").read_text(encoding="utf-8")
    if str(theme).lower() != "light":
        return text

    # Map dark theme tokens to light theme tokens
    mapping = {
        BASE_BACKGROUND: LIGHT_BASE_BACKGROUND,
        BASE_SURFACE: LIGHT_BASE_SURFACE,
        BASE_ELEVATED: LIGHT_BASE_ELEVATED,
        BASE_PANEL: LIGHT_BASE_PANEL,
        BASE_CARD: LIGHT_BASE_CARD,
        TEXT_PRIMARY: LIGHT_TEXT_PRIMARY,
        TEXT_SECONDARY: LIGHT_TEXT_SECONDARY,
        TEXT_MUTED: LIGHT_TEXT_MUTED,
        TEXT_DISABLED: LIGHT_TEXT_DISABLED,
        ACCENT_PRIMARY: LIGHT_ACCENT_PRIMARY,
        ACCENT_SECONDARY: LIGHT_ACCENT_SECONDARY,
        ACCENT_SUCCESS: LIGHT_ACCENT_SUCCESS,
        ACCENT_WARNING: LIGHT_ACCENT_WARNING,
        ACCENT_DANGER: LIGHT_ACCENT_DANGER,
        ACCENT_INFO: LIGHT_ACCENT_INFO,
        BORDER_PRIMARY: LIGHT_BORDER_PRIMARY,
        BORDER_SECONDARY: LIGHT_BORDER_SECONDARY,
        STATUS_OK: LIGHT_STATUS_OK,
        STATUS_WARNING: LIGHT_STATUS_WARNING,
        STATUS_ERROR: LIGHT_STATUS_ERROR,
        STATUS_MUTED: LIGHT_STATUS_MUTED,
    }

    for old, new in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(old, new)
    return text


def _generate_base_qss(theme: str = "dark") -> str:
    """Generate the base QSS stylesheet using design tokens"""
    if theme.lower() == "light":
        return _generate_light_base_qss()
    else:
        return _generate_dark_base_qss()


def _generate_dark_base_qss() -> str:
    """Generate the dark theme base QSS"""
    return f"""
/* ============================================================
   SP Telegram — Professional Dark Theme
   Clean, focused, and professional dark theme with restrained
   accent colors and clear visual hierarchy.
   ============================================================ */

* {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD};
    color: {TEXT_PRIMARY};
    transition: all 0.2s ease;
}}

QMainWindow, QWidget {{
    background: {BASE_BACKGROUND};
    color: {TEXT_PRIMARY};
}}

QWidget#central_root {{
    background: {BASE_BACKGROUND};
}}

/* Sidebar */
QFrame#sidebar {{
    background: {BASE_PANEL};
    border-right: 1px solid {BORDER_PRIMARY};
    border-radius: 0 {RADIUS_LG} {RADIUS_LG} 0;
}}

QFrame#topbar {{
    background: {BASE_SURFACE};
    border-bottom: 1px solid {BORDER_PRIMARY};
}}

/* Cards */
QFrame[card="true"], QFrame[sectionCard="true"], QGroupBox {{
    background: {BASE_CARD};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: {RADIUS_LG};
    transition: border-color 0.2s ease;
}}

QFrame[card="true"]:hover, QFrame[sectionCard="true"]:hover {{
    border-color: {BORDER_SECONDARY};
}}

QGroupBox {{
    margin-top: {SPACING_MD};
    padding-top: {SPACING_LG};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SPACING_MD};
    padding: 0 {SPACING_XS};
    color: {TEXT_SECONDARY};
}}

/* Text */
QLabel[muted="true"], QLabel#lbl_muted {{
    color: {TEXT_MUTED};
}}

QLabel[secondary="true"] {{
    color: {TEXT_SECONDARY};
}}

QLabel#lbl_page_title {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_LG};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#lbl_page_subtitle {{
    color: {TEXT_MUTED};
    font-size: {FONT_SIZE_SM};
}}

QLabel#lbl_stat_value {{
    font-size: {FONT_SIZE_XL};
    font-weight: {FONT_WEIGHT_BOLD};
}}

/* Status bar */
QStatusBar {{
    background: {BASE_PANEL};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER_PRIMARY};
    min-height: 24px;
}}

/* Tooltips */
QToolTip {{
    background: {BASE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_PRIMARY};
    padding: {SPACING_SM} {SPACING_MD};
    border-radius: {RADIUS_MD};
}}

/* Menus */
QMenu {{
    background: {BASE_ELEVATED};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: {RADIUS_MD};
    padding: {SPACING_XS};
}}

QMenu::item {{
    padding: {SPACING_SM} 30px {SPACING_SM} {SPACING_SM};
    border-radius: {RADIUS_SM};
}}

QMenu::item:selected {{
    background: {BASE_CARD};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER_PRIMARY};
    margin: {SPACING_XS} {SPACING_SM};
}}

/* Scrollbars */
QScrollBar:vertical {{
    width: 9px;
    background: transparent;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_PRIMARY};
    border-radius: 4px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BORDER_SECONDARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    height: 9px;
    background: transparent;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_PRIMARY};
    border-radius: 4px;
    min-width: 28px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Dialogs */
QDialog {{
    background: {BASE_BACKGROUND};
}}

QMessageBox {{
    background: {BASE_SURFACE};
}}

QSplitter::handle {{
    background: {BORDER_PRIMARY};
}}

QCalendarWidget QWidget {{
    alternate-background-color: {BASE_ELEVATED};
}}

QCalendarWidget QAbstractItemView {{
    selection-background-color: {ACCENT_PRIMARY};
    selection-color: white;
}}
"""


def _generate_light_base_qss() -> str:
    """Generate the light theme base QSS"""
    return f"""
/* ============================================================
   SP Telegram — Professional Light Theme
   Clean, focused, and professional light theme with restrained
   accent colors and clear visual hierarchy.
   ============================================================ */

* {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD};
    color: {LIGHT_TEXT_PRIMARY};
    transition: all 0.2s ease;
}}

QMainWindow, QWidget {{
    background: {LIGHT_BASE_BACKGROUND};
    color: {LIGHT_TEXT_PRIMARY};
}}

QWidget#central_root {{
    background: {LIGHT_BASE_BACKGROUND};
}}

/* Sidebar */
QFrame#sidebar {{
    background: {LIGHT_BASE_PANEL};
    border-right: 1px solid {LIGHT_BORDER_PRIMARY};
    border-radius: 0 {RADIUS_LG} {RADIUS_LG} 0;
}}

QFrame#topbar {{
    background: {LIGHT_BASE_SURFACE};
    border-bottom: 1px solid {LIGHT_BORDER_PRIMARY};
}}

/* Cards */
QFrame[card="true"], QFrame[sectionCard="true"], QGroupBox {{
    background: {LIGHT_BASE_SURFACE};
    border: 1px solid {LIGHT_BORDER_PRIMARY};
    border-radius: {RADIUS_LG};
    transition: border-color 0.2s ease;
}}

QFrame[card="true"]:hover, QFrame[sectionCard="true"]:hover {{
    border-color: {LIGHT_BORDER_SECONDARY};
}}

QGroupBox {{
    margin-top: {SPACING_MD};
    padding-top: {SPACING_LG};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SPACING_MD};
    padding: 0 {SPACING_XS};
    color: {LIGHT_TEXT_SECONDARY};
}}

/* Text */
QLabel[muted="true"], QLabel#lbl_muted {{
    color: {LIGHT_TEXT_MUTED};
}}

QLabel[secondary="true"] {{
    color: {LIGHT_TEXT_SECONDARY};
}}

QLabel#lbl_page_title {{
    color: {LIGHT_TEXT_PRIMARY};
    font-size: {FONT_SIZE_LG};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#lbl_page_subtitle {{
    color: {LIGHT_TEXT_MUTED};
    font-size: {FONT_SIZE_SM};
}}

QLabel#lbl_stat_value {{
    font-size: {FONT_SIZE_XL};
    font-weight: {FONT_WEIGHT_BOLD};
    color: {LIGHT_TEXT_PRIMARY};
}}

/* Status bar */
QStatusBar {{
    background: {LIGHT_BASE_SURFACE};
    color: {LIGHT_TEXT_MUTED};
    border-top: 1px solid {LIGHT_BORDER_PRIMARY};
    min-height: 24px;
}}

/* Tooltips */
QToolTip {{
    background: {LIGHT_BASE_ELEVATED};
    color: {LIGHT_TEXT_PRIMARY};
    border: 1px solid {LIGHT_BORDER_PRIMARY};
    padding: {SPACING_SM} {SPACING_MD};
    border-radius: {RADIUS_MD};
}}

/* Menus */
QMenu {{
    background: {LIGHT_BASE_SURFACE};
    border: 1px solid {LIGHT_BORDER_PRIMARY};
    border-radius: {RADIUS_MD};
    padding: {SPACING_XS};
}}

QMenu::item {{
    padding: {SPACING_SM} 30px {SPACING_SM} {SPACING_SM};
    border-radius: {RADIUS_SM};
}}

QMenu::item:selected {{
    background: {LIGHT_BASE_ELEVATED};
    color: {LIGHT_TEXT_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background: {LIGHT_BORDER_PRIMARY};
    margin: {SPACING_XS} {SPACING_SM};
}}

/* Scrollbars */
QScrollBar:vertical {{
    width: 9px;
    background: transparent;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {LIGHT_BORDER_PRIMARY};
    border-radius: 4px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {LIGHT_BORDER_SECONDARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    height: 9px;
    background: transparent;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {LIGHT_BORDER_PRIMARY};
    border-radius: 4px;
    min-width: 28px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Dialogs */
QDialog {{
    background: {LIGHT_BASE_SURFACE};
}}

QMessageBox {{
    background: {LIGHT_BASE_SURFACE};
}}

QSplitter::handle {{
    background: {LIGHT_BORDER_PRIMARY};
}}

QCalendarWidget QWidget {{
    alternate-background-color: {LIGHT_BASE_ELEVATED};
}}

QCalendarWidget QAbstractItemView {{
    selection-background-color: {LIGHT_ACCENT_PRIMARY};
    selection-color: white;
}}
"""


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """Apply the selected theme to the application"""
    theme = "light" if str(theme).lower() == "light" else "dark"
    set_current_theme(theme)

    # Generate and apply the base stylesheet
    base = _generate_base_qss(theme)

    if theme == "light":
        # light.qss is a complete, hand-authored stylesheet (base + components)
        app.setStyleSheet(base)
    else:
        app.setStyleSheet(base + "\n" + _component_qss(theme))


def get_current_theme() -> str | None:
    """Get the current theme ("light" or "dark")"""
    from app.theme_state import get_current_theme as _get_current_theme
    return _get_current_theme()
