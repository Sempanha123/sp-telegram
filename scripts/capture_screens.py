"""Capture screenshots of the running SP Telegram UI for visual verification.

Usage:
    python scripts/capture_screens.py [--theme dark|light] [--out DIR]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SP_APP_ENV", "development")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.theme import apply_theme


def main() -> int:
    theme = "dark"
    out_dir = Path("screenshots")
    args = sys.argv[1:]
    if "--theme" in args:
        theme = args[args.index("--theme") + 1]
    if "--out" in args:
        out_dir = Path(args[args.index("--out") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_theme(app, theme)

    context = ApplicationContext(PROJECT_ROOT)
    window = MainWindow(context)
    window.show()

    pages = ["dashboard", "accounts", "groups", "members", "blacklist", "campaigns", "scheduler", "templates", "operations", "jobs", "analytics", "alerts", "logs", "settings"]

    def capture():
        window.navigate("dashboard", "Dashboard")
        app.processEvents()
        window.grab().save(str(out_dir / f"dashboard_{theme}.png"))

        for key in pages[1:]:
            window.navigate(key, key.replace("_", " ").title())
            app.processEvents()
            window.grab().save(str(out_dir / f"{key}_{theme}.png"))
        print(f"Saved {len(pages)} screenshots to {out_dir}")
        app.quit()

    QTimer.singleShot(2500, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())