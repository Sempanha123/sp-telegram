from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from app.widgets.status_badge import StatusBadge


class AccountHealthCard(QFrame):
    def __init__(self, account: str, health: str, restriction: str = "None", parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel(account))
        layout.addStretch()
        layout.addWidget(StatusBadge(health))
        label = QLabel(restriction)
        label.setProperty("muted", True)
        layout.addWidget(label)
