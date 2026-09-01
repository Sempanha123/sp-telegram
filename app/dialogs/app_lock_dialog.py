from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *


class AppLockDialog(QDialog):
    def __init__(self, app_lock_service, parent=None) -> None:
        super().__init__(parent); self.service = app_lock_service; self.setWindowTitle("SP Telegram Locked"); self.setModal(True); self.resize(430, 220)
        root = QVBoxLayout(self); title = QLabel("SP Telegram is locked"); title.setProperty("dialogTitle", True); root.addWidget(title)
        info = QLabel("Enter the local application-lock password to restore access. Telegram sessions remain connected unless you explicitly disconnect them."); info.setWordWrap(True); root.addWidget(info)
        form = QFormLayout(); self.le_password = QLineEdit(); self.le_password.setEchoMode(QLineEdit.EchoMode.Password); form.addRow("Password", self.le_password); root.addLayout(form)
        self.lbl_error = QLabel(""); self.lbl_error.setProperty("tone", "danger"); root.addWidget(self.lbl_error)
        button = QPushButton("Unlock"); button.setProperty("primary", True); button.clicked.connect(self._unlock); root.addWidget(button)
        self.le_password.returnPressed.connect(self._unlock)

    def _unlock(self):
        password = self.le_password.text(); self.le_password.clear()
        try:
            if self.service.unlock(password): self.accept()
            else: self.lbl_error.setText("Incorrect application-lock password.")
        except Exception:
            self.lbl_error.setText("Secure credential storage is unavailable.")

    def reject(self):
        # Lock cannot be dismissed without successful authentication.
        pass

    def closeEvent(self, event):
        # Prevent closing via window X button - only unlock button works
        event.ignore()

# Add compatibility attributes for older PySide6 versions
if not hasattr(AppLockDialog, 'Accepted'):
    AppLockDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AppLockDialog, 'Rejected'):
    AppLockDialog.Rejected = QDialog.DialogCode.Rejected
