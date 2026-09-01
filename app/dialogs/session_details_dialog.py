from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *

from app.utils.formatters import format_local_datetime


class SessionDetailsDialog(QDialog):
    revokeRequested = Signal(object)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Telegram Session Details")
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)
        form = QFormLayout()
        values = [
            ("Device", session.device_model),
            ("Platform", session.platform),
            ("System Version", session.system_version),
            ("Application", session.app_name),
            ("App Version", session.app_version),
            ("Location", session.location),
            ("Last Active", format_local_datetime(session.last_active_at)),
            ("Created At", format_local_datetime(session.created_at)),
            ("Current Session", "Yes" if session.is_current else "No"),
        ]
        for key, value in values:
            form.addRow(key, QLabel(str(value or "—")))
        root.addLayout(form)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_session_revoke = QPushButton("Revoke")
        self.btn_session_revoke.setObjectName("btn_session_revoke")
        self.btn_session_close = QPushButton("Close")
        self.btn_session_close.setObjectName("btn_session_close")
        row.addWidget(self.btn_session_revoke)
        row.addWidget(self.btn_session_close)
        root.addLayout(row)
        self.btn_session_close.clicked.connect(self.accept)
        self.btn_session_revoke.clicked.connect(lambda: self.revokeRequested.emit(self.session))

# Add compatibility attributes for older PySide6 versions
if not hasattr(SessionDetailsDialog, 'Accepted'):
    SessionDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(SessionDetailsDialog, 'Rejected'):
    SessionDetailsDialog.Rejected = QDialog.DialogCode.Rejected
