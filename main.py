from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from app.application_context import ApplicationContext
from app.constants import APP_NAME
from app.database.database import DatabaseError
from app.dialogs.dialog_compat import *
from app.main_window import MainWindow
from app.theme import apply_theme
from app.utils.helpers import ensure_app_directories
from app.utils.environment import runtime_environment_summary
from app.utils.settings_migration import migrate_legacy_qsettings


def _install_exception_boundary(context: ApplicationContext) -> None:
    """Route otherwise-unhandled UI exceptions through the application error boundary."""

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if not isinstance(exc_value, Exception):
            exc_value = RuntimeError(str(exc_value))
        message = context.error_handler.handle(exc_value, component="Qt Main Thread")
        QMessageBox.critical(None, f"Unexpected Error - {APP_NAME}", message)

    sys.excepthook = handle_exception


def main() -> int:
    project_root = Path(__file__).resolve().parent
    ensure_app_directories(project_root)

    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    migrate_legacy_qsettings()
    app.setApplicationDisplayName(APP_NAME)
    app.setStyle("Fusion")
    # Apply the persisted theme before constructing widgets. Creating the full
    # window in light mode and changing it afterwards left cached icons and
    # custom-painted controls with the wrong palette.
    apply_theme(app, str(QSettings().value("ui/theme", "light")))

    try:
        context = ApplicationContext(project_root)
    except DatabaseError as exc:
        QMessageBox.critical(
            None,
            "Database Error",
            f"{APP_NAME} cannot open the database.\n\n"
            f"{exc}\n\n"
            "Check that the data folder is writable and that the database is not locked by another application. "
            "No Telegram operations were started.",
        )
        return 1

    if os.getenv("SP_APP_ENV", "production").strip().lower() in {"development", "dev", "test", "testing"}:
        env = runtime_environment_summary()
        context.logger.info(
            "SYSTEM",
            f"Development runtime Python: {env['python_executable']} | version={env['python_version']} | venv={env['virtual_environment']}",
            action="DEVELOPMENT_ENVIRONMENT",
        )

    _install_exception_boundary(context)
    # MainWindow construction may fail before closeEvent() exists.  Keep the
    # context strongly owned here and guarantee worker/database cleanup on that
    # path so no running QThread can be destroyed during exception unwinding.
    try:
        window = MainWindow(context)
    except Exception as exc:
        message = context.error_handler.handle(exc, component="MainWindow startup")
        context.close()
        QMessageBox.critical(None, f"Unexpected Error - {APP_NAME}", message)
        return 1

    app.aboutToQuit.connect(context.close)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
