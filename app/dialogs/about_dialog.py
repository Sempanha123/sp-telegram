from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout
from app.dialogs.dialog_compat import *
from app.constants import APP_NAME, APP_VERSION


class AboutDialog(QDialog):
    def __init__(self, schema_version: int, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle(f"About {APP_NAME}"); root = QVBoxLayout(self); form = QFormLayout(); root.addLayout(form)
        try:
            import PySide6; pyside = PySide6.__version__
        except Exception: pyside = "unknown"
        try:
            telethon_version = package_version("Telethon")
        except PackageNotFoundError:
            telethon_version = "unavailable"
        for label, value in [("Application", APP_NAME), ("Version", APP_VERSION), ("Python", sys.version.split()[0]), ("PySide6", pyside), ("Database Schema", schema_version), ("Telegram Client Library", telethon_version)]: form.addRow(label, QLabel(str(value)))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

# Add compatibility attributes for older PySide6 versions
if not hasattr(AboutDialog, 'Accepted'):
    AboutDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AboutDialog, 'Rejected'):
    AboutDialog.Rejected = QDialog.DialogCode.Rejected
