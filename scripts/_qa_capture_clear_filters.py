"""Capture the Accounts page with an active filter to verify clear-filters UI.

Run:  python scripts/_qa_capture_clear_filters.py
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
            window.navigate("accounts", "Accounts")
            app.processEvents()
            page = window.pages["accounts"]
            page._on_filter("Health", "Healthy")
            app.processEvents()
            out = PROJECT_ROOT / "screenshots" / "qa_clear_filters.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(out))
            print(f"Saved {out}")
            print("clear button visible:", page.btn_clear_filters.isVisible())
        finally:
            QTimer.singleShot(0, app.quit)

    QTimer.singleShot(300, run)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())