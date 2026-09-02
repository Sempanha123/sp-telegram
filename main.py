from __future__ import annotations

from datetime import datetime, timezone
import faulthandler
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from app.application_context import ApplicationContext
from app.branding import brand_icon
from app.constants import APP_NAME
from app.database.database import DatabaseError
from app.dialogs.dialog_compat import *
from app.main_window import MainWindow
from app.theme import apply_theme
from app.utils.helpers import ensure_app_directories
from app.utils.environment import runtime_environment_summary
from app.utils.settings_migration import migrate_legacy_qsettings


_FAULT_LOG_HANDLE = None


def _append_crash_diagnostic(path: Path, heading: str, detail: str = "") -> None:
    """Write a dependency-free fallback diagnostic even if the DB logger failed."""
    try:
        with path.open("a", encoding="utf-8") as stream:
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            stream.write(f"\n[{timestamp}] {heading}\n")
            if detail:
                stream.write(detail.rstrip() + "\n")
    except OSError:
        pass


def _install_native_crash_log(project_root: Path) -> Path:
    """Capture fatal Python/native thread traces for intermittent exits."""
    global _FAULT_LOG_HANDLE
    path = project_root / "logs" / "native-crash.log"
    try:
        _FAULT_LOG_HANDLE = path.open("a", encoding="utf-8", buffering=1)
        _FAULT_LOG_HANDLE.write(
            f"\n[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] Application session started\n"
        )
        faulthandler.enable(file=_FAULT_LOG_HANDLE, all_threads=True)
    except (OSError, RuntimeError):
        _FAULT_LOG_HANDLE = None
    return path


def _install_exception_boundary(context: ApplicationContext, crash_log_path: Path) -> None:
    """Route otherwise-unhandled UI exceptions through the application error boundary."""

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if not isinstance(exc_value, Exception):
            exc_value = RuntimeError(str(exc_value))
        _append_crash_diagnostic(
            crash_log_path,
            "Unhandled Python exception",
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )
        message = context.error_handler.handle(exc_value, component="Qt Main Thread")
        try:
            QMessageBox.critical(None, f"Unexpected Error - {APP_NAME}", message)
        except RuntimeError:
            # Qt may already be tearing widgets down; the file diagnostic above
            # must still survive that shutdown path.
            pass

    sys.excepthook = handle_exception


def main() -> int:
    project_root = Path(__file__).resolve().parent
    ensure_app_directories(project_root)
    crash_log_path = _install_native_crash_log(project_root)

    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    app.setWindowIcon(brand_icon())
    # Ending the application is an explicit MainWindow decision.  Closing a
    # transient dialog or accidentally losing the last visible child must not
    # silently terminate the event loop.
    app.setQuitOnLastWindowClosed(False)
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

    _install_exception_boundary(context, crash_log_path)
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
    exit_code = app.exec()
    if not bool(getattr(window, "_shutdown_requested", False)):
        _append_crash_diagnostic(
            crash_log_path,
            "Application event loop exited without a confirmed MainWindow close",
            f"Qt exit code: {exit_code}",
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
