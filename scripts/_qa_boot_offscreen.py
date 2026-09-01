"""Boot the desktop shell offscreen without touching operator data or settings."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("SP_APP_ENV", "development")

from PySide6.QtCore import QCoreApplication, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.theme import apply_theme


def main() -> int:
    theme = sys.argv[1] if len(sys.argv) > 1 else "dark"

    with tempfile.TemporaryDirectory(prefix="sp-telegram-boot-") as tmp:
        runtime_root = Path(tmp)
        settings_root = runtime_root / "settings"
        settings_root.mkdir()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            str(settings_root),
        )
        QCoreApplication.setOrganizationName("SP Telegram QA")
        QCoreApplication.setApplicationName("SP Telegram QA")

        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        QSettings().setValue("ui/theme", theme)
        apply_theme(app, theme)

        context = None
        window = None
        try:
            context = ApplicationContext(runtime_root)
            window = MainWindow(context)
            window.show()
            QTimer.singleShot(750, app.quit)
            rc = app.exec()
            if rc != 0:
                print("STARTUP FAILED, exit code", rc, file=sys.stderr)
                return rc
            print(f"STARTUP OK, pages={len(window.pages)}, exit code={rc}")
            return 0
        except Exception as exc:
            print(f"STARTUP FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            if window is not None:
                window.hide()
                window.deleteLater()
                app.processEvents()
            if context is not None:
                context.close()


if __name__ == "__main__":
    raise SystemExit(main())
