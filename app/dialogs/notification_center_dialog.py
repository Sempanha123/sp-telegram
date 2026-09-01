from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *


class NotificationCenterDialog(QDialog):
    openAlertsRequested = Signal()
    def __init__(self, alerts: list[dict], parent=None):
        super().__init__(parent); self.setWindowTitle("Notification Center"); self.resize(520, 480); root = QVBoxLayout(self)
        root.addWidget(QLabel("Latest alerts")); self.list_alerts = QListWidget(); root.addWidget(self.list_alerts, 1)
        for alert in alerts[:30]:
            severity = str(alert.get("severity", "INFO")).title(); title = alert.get("title") or "Alert"; count = int(alert.get("occurrence_count") or 1)
            suffix = f" ×{count}" if count > 1 else ""
            QListWidgetItem(f"{severity} • {title}{suffix}", self.list_alerts)
        button = QPushButton("Open Alert Center"); button.clicked.connect(lambda: (self.openAlertsRequested.emit(), self.accept())); root.addWidget(button)

# Add compatibility attributes for older PySide6 versions
if not hasattr(NotificationCenterDialog, 'Accepted'):
    NotificationCenterDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(NotificationCenterDialog, 'Rejected'):
    NotificationCenterDialog.Rejected = QDialog.DialogCode.Rejected
