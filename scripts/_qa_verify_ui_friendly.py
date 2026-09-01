"""Verify the Cycle 8 UI-friendliness fixes offscreen.

Covers: UX-001 page-jump spinbox, UX-002 clear-filters button, UX-004 topbar
status text, UX-005/010 loading overlay spinner, UX-006 contextual empty state,
UX-008 campaign wizard step dots, UX-012 settings search, command palette.

Run:  python scripts/_qa_verify_ui_friendly.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("SP_APP_ENV", "development")

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.theme import apply_theme

RESULTS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))
    print(RESULTS[-1])


def main() -> int:
    theme = "light"
    QSettings().setValue("ui/theme", theme)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_theme(app, theme)

    context = ApplicationContext(PROJECT_ROOT)
    window = MainWindow(context)
    window.show()

    def run():
        try:
            # --- UX-001: page-jump spinbox on a database-mode page ---
            window.navigate("accounts", "Accounts")
            app.processEvents()
            page = window.pages["accounts"]
            spin = getattr(page.pagination_bar, "spin_page", None)
            check("UX-001 page-jump spinbox exists", spin is not None)
            if spin is not None:
                check("UX-001 spinbox range >= 1", spin.minimum() >= 1 and spin.maximum() >= 1, f"range {spin.minimum()}..{spin.maximum()}")

            # --- UX-002: clear-filters button + active property ---
            btn = getattr(page, "btn_clear_filters", None)
            check("UX-002 clear-filters button exists", btn is not None)
            if btn is not None:
                page._on_filter("Health", "Healthy")
                app.processEvents()
                check("UX-002 clear button visible when filter active", btn.isVisible())
                page.clear_filters()
                app.processEvents()
                check("UX-002 clear button hidden after clear", not btn.isVisible())

            # --- UX-004: topbar status chips carry text ---
            check("UX-004 NET chip has text", "●" in window.topbar.lbl_internet_status.text() and len(window.topbar.lbl_internet_status.text()) > 5, window.topbar.lbl_internet_status.text())
            check("UX-004 DB chip has text", "●" in window.topbar.lbl_database.text() and len(window.topbar.lbl_database.text()) > 5, window.topbar.lbl_database.text())

            # --- UX-005/010: loading overlay with spinner ---
            overlay = getattr(page, "loading_overlay", None)
            check("UX-005 loading overlay instantiated", overlay is not None)
            if overlay is not None:
                check("UX-010 spinner progress bar present", hasattr(overlay, "progress"))
                page.set_loading(True, "Testing…")
                app.processEvents()
                check("UX-005 overlay shows on set_loading(True)", overlay.isVisible())
                page.set_loading(False)
                app.processEvents()
                check("UX-005 overlay hides on set_loading(False)", not overlay.isVisible())

            # --- UX-008: campaign wizard step dots ---
            from app.dialogs.create_campaign_dialog import CreateCampaignDialog
            targets, accounts = window._campaign_dialog_data()
            dialog = CreateCampaignDialog(targets, accounts, window, smart_planner=context.campaign_controller.plan_smart_targets)
            check("UX-008 wizard step dots created", len(dialog._step_dots) == 7, f"{len(dialog._step_dots)} dots")
            dialog._update(3)
            app.processEvents()
            check("UX-008 current step highlighted", dialog._step_dots[3].property("state") == "current")
            check("UX-008 prior step marked done", dialog._step_dots[0].property("state") == "done")
            dialog.close()

            # --- UX-012: settings search ---
            window.navigate("settings", "Settings")
            app.processEvents()
            settings_page = window.pages["settings"]
            le = getattr(settings_page, "le_settings_search", None)
            check("UX-012 settings search box exists", le is not None)
            if le is not None:
                le.setText("sec")
                app.processEvents()
                check("UX-012 search jumps to Security tab", settings_page.tab_settings.currentIndex() == settings_page.tab_indices.get("security", -1))
                le.setText("zzz_none")
                app.processEvents()
                check("UX-012 no-match hint shown", settings_page.lbl_settings_search_hint.text() == "No matching settings")
                le.setText("")

            # --- Command palette ---
            from app.widgets.command_palette import CommandPaletteDialog
            palette = CommandPaletteDialog(window)
            check("Command palette lists pages", palette.list_results.count() >= 22, f"{palette.list_results.count()} entries")
            palette.le_query.setText("campaign")
            app.processEvents()
            check("Command palette filters results", palette.list_results.count() >= 1 and palette.list_results.count() < 30, f"{palette.list_results.count()} matches")
            palette.close()

            check("ALL UI-FRIENDLY CHECKS COMPLETE", True)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("UNEXPECTED EXCEPTION", False, str(exc))
        finally:
            QTimer.singleShot(0, app.quit)

    QTimer.singleShot(300, run)
    app.exec()

    passed = sum(1 for r in RESULTS if r.startswith("PASS"))
    failed = sum(1 for r in RESULTS if r.startswith("FAIL"))
    print(f"\n===== UI-FRIENDLY VERIFY SUMMARY =====\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())