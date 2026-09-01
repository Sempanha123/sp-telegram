from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.theme import apply_theme, load_stylesheet


STYLES_DIR = Path(__file__).resolve().parents[1] / "app" / "styles"
UNSUPPORTED_QSS = re.compile(
    r"\b(?:transition|transform|box-shadow|text-shadow|letter-spacing|text-transform)\s*:"
    r"|:focus-within\b"
    r"|\b[xy][12]="
)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_is_complete_and_qt_compatible(theme: str) -> None:
    stylesheet = load_stylesheet(theme)

    assert "QFrame#sidebar" in stylesheet
    assert "QFrame#topbar" in stylesheet
    assert "QPushButton[primary=\"true\"]" in stylesheet
    assert "QTableView" in stylesheet
    assert stylesheet.count("{") == stylesheet.count("}")
    assert not UNSUPPORTED_QSS.search(stylesheet)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_apply_theme_installs_the_full_stylesheet(qapp, theme: str) -> None:
    apply_theme(qapp, theme)

    assert qapp.styleSheet() == load_stylesheet(theme)


def test_theme_files_are_not_accidentally_empty() -> None:
    assert (STYLES_DIR / "light.qss").stat().st_size > 10_000
    assert (STYLES_DIR / "dark.qss").stat().st_size > 2_000
    assert (STYLES_DIR / "components.qss").stat().st_size > 10_000
