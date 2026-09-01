from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.theme import apply_theme, build_palette, load_stylesheet


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
    assert "QLabel[statusBadge=\"true\"]" in stylesheet
    assert "QWidget[accountSummaryItem=\"true\"]" in stylesheet
    assert stylesheet.count("{") == stylesheet.count("}")
    assert not UNSUPPORTED_QSS.search(stylesheet)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_apply_theme_installs_the_full_stylesheet(qapp, theme: str) -> None:
    apply_theme(qapp, theme)

    assert qapp.styleSheet() == load_stylesheet(theme)


@pytest.mark.parametrize(
    ("theme", "text", "surface"),
    [("light", "#172033", "#ffffff"), ("dark", "#f5f7ff", "#11182b")],
)
def test_native_palette_matches_theme(theme: str, text: str, surface: str) -> None:
    from PySide6.QtGui import QPalette

    palette = build_palette(theme)
    assert palette.color(QPalette.ColorRole.Text).name() == text
    assert palette.color(QPalette.ColorRole.Base).name() == surface


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


def test_status_badge_uses_theme_driven_properties(qapp) -> None:
    from app.widgets.status_badge import StatusBadge

    badge = StatusBadge("Healthy")
    assert badge.property("statusBadge") is True
    assert badge.property("tone") == "success"
    assert badge.styleSheet() == ""

    badge.set_state("Running")
    assert badge.property("tone") == "info"


def test_svg_icons_follow_the_application_palette(qapp) -> None:
    from app.icons import IconManager

    def average_lightness(pixmap) -> float:
        image = pixmap.toImage()
        values = [
            image.pixelColor(x, y).lightness()
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() > 16
        ]
        return sum(values) / len(values)

    apply_theme(qapp, "light")
    icon = IconManager.get("dashboard")
    light_value = average_lightness(icon.pixmap(20, 20))
    apply_theme(qapp, "dark")
    dark_value = average_lightness(icon.pixmap(20, 20))

    assert dark_value > light_value + 80
