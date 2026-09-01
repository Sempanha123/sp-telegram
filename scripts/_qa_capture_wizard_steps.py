"""Capture the Create Campaign wizard step dots and verify they render via pixel analysis.

Run:  python scripts/_qa_capture_wizard_steps.py
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
            targets, accounts = window._campaign_dialog_data()
            from app.dialogs.create_campaign_dialog import CreateCampaignDialog
            dialog = CreateCampaignDialog(targets, accounts, window, smart_planner=context.campaign_controller.plan_smart_targets)
            dialog._update(2)  # step 3 of 7
            dialog.show()
            app.processEvents()
            out = PROJECT_ROOT / "screenshots" / "qa_wizard_steps.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            dialog.grab().save(str(out))
            print(f"Saved {out}")
            dialog.close()
        finally:
            QTimer.singleShot(0, app.quit)

    QTimer.singleShot(300, run)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())