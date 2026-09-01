from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.icons import IconManager


class AccentCard(QFrame):
    """A colorful, friendly metric card with a tinted accent background.

    ``accent`` selects one of the soft pastel palettes defined in the light
    theme (primary / success / warning / danger / purple / info).
    """

    ICONS = {
        "accounts": "accounts", "groups": "groups", "members": "members",
        "campaigns": "campaigns", "jobs": "jobs", "alerts": "alerts",
        "operations": "operations", "scheduler": "scheduler", "templates": "templates",
        "health": "health", "blacklist": "blacklist", "analytics": "analytics",
    }

    def __init__(self, title: str, value: str | int = "0", accent: str = "primary",
                 icon_name: str = "", object_name: str = "", parent=None):
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self.setProperty("accentCard", True)
        self.setProperty("accent", accent)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(IconManager.get(self.ICONS.get(icon_name or title.lower(), "dashboard")).pixmap(16, 16))
        icon.setFixedSize(18, 18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setProperty("accentLabel", True)
        head.addWidget(icon)
        head.addWidget(self.lbl_title)
        head.addStretch()
        root.addLayout(head)

        self.lbl_value = QLabel(str(value))
        self.lbl_value.setProperty("accentValue", True)
        self.lbl_value.setProperty("accent", accent)
        root.addWidget(self.lbl_value)

        self.metrics_host = QWidget()
        self.metrics_host.setStyleSheet("background:transparent;border:0;")
        self.metrics = QVBoxLayout(self.metrics_host)
        self.metrics.setContentsMargins(0, 0, 0, 0)
        self.metrics.setSpacing(5)
        root.addWidget(self.metrics_host)
        self._metric_labels: dict[str, QLabel] = {}

    def set_value(self, value) -> None:
        self.lbl_value.setText(f"{value:,}" if isinstance(value, int) else str(value))

    def set_metrics(self, metrics: list[tuple[str, object, str | None]]) -> None:
        while self.metrics.count():
            item = self.metrics.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        self._metric_labels.clear()
        for label, value, tone in metrics:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            dot = QLabel("●")
            dot.setFixedWidth(10)
            dot.setProperty("tone", tone or "muted")
            text = QLabel(f"{value:,}  {label}" if isinstance(value, int) else f"{value}  {label}")
            text.setProperty("summaryMetric", True)
            row.addWidget(dot)
            row.addWidget(text, 1)
            self.metrics.addLayout(row)
            self._metric_labels[label] = text