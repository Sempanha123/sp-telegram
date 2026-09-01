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
    assert "QPushButton:focus" in stylesheet
    assert "QTableView:focus" in stylesheet
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


def test_topbar_compact_mode_preserves_full_status_in_tooltips(qapp) -> None:
    from app.widgets.topbar import TopBar

    topbar = TopBar()
    topbar.set_network_status("Online")
    topbar.set_telegram_status("Ready")
    topbar.set_database_connected(False)

    topbar.set_compact(True)
    assert topbar.lbl_page_subtitle.isHidden()
    assert topbar.lbl_search_shortcut.isHidden()
    assert topbar.lbl_internet_status.text() == "NET  ●"
    assert topbar.lbl_telegram_global_status.text() == "TG  ●"
    assert topbar.lbl_database.text() == "DB  ●"
    assert topbar.lbl_internet_status.toolTip() == "Internet\nOnline"
    assert topbar.lbl_database.toolTip() == "Database\nError"

    topbar.set_compact(False)
    assert "Online" in topbar.lbl_internet_status.text()
    assert "Ready" in topbar.lbl_telegram_global_status.text()
    assert "Error" in topbar.lbl_database.text()


def test_dashboard_attention_banner_routes_to_the_relevant_page(qapp) -> None:
    from PySide6.QtCore import QObject, Signal

    from app.pages.dashboard_page import DashboardPage

    class StubController(QObject):
        summaryChanged = Signal(dict)

        @staticmethod
        def summary():
            return {}

        def refresh(self):
            data = self.summary()
            self.summaryChanged.emit(data)
            return data

    page = DashboardPage(StubController())
    requested: list[str] = []
    page.quickAction.connect(requested.append)

    page.set_summary({"accounts": {"total": 1, "restricted": 1}, "alerts": {"critical": 0}})
    assert page.banner.property("state") == "attention"
    assert not page.btn_review_attention.isHidden()
    page.btn_review_attention.click()
    assert requested == ["account_health"]

    page.set_summary({"alerts": {"critical": 2}})
    page.btn_review_attention.click()
    assert requested[-1] == "alerts"

    page.set_summary({})
    assert page.banner.property("state") == "ok"
    assert page.btn_review_attention.isHidden()
