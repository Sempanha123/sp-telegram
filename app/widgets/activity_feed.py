"""Live user-facing activity feed widget.

Shows the most recent operational activity (from the local log store) with a
friendly, color-coded presentation.  It auto-refreshes on a timer so the user
never has to press Refresh.  Technical stack traces are intentionally never
shown here — that belongs in the Logs page / error reports.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.utils.formatters import format_local_datetime


class ActivityFeed(QFrame):
    """A scrollable list of recent activity entries.

    ``loader`` is a callable returning a list of objects with ``level``,
    ``category``, ``message``, ``action`` and ``created_at`` attributes
    (e.g. ``LogEntry``).  ``refresh_ms`` controls the auto-refresh interval.
    """

    LEVEL_COLORS = {
        "INFO": ("#2563EB", "#DBEAFE"),
        "SUCCESS": ("#059669", "#D1FAE5"),
        "WARNING": ("#D97706", "#FEF3C7"),
        "ERROR": ("#DC2626", "#FEE2E2"),
        "CRITICAL": ("#DC2626", "#FEE2E2"),
    }
    CATEGORY_ICONS = {
        "ACCOUNT": "👤", "GROUP": "👥", "MEMBER": "🧑", "CAMPAIGN": "📣",
        "JOB": "⚙️", "SYSTEM": "🖥️", "AUDIT": "🔒", "SCHEDULER": "⏰",
        "ALERT": "🔔", "SECURITY": "🛡️", "BACKUP": "💾", "DATABASE": "🗄️",
    }

    def __init__(self, loader, refresh_ms: int = 4000, max_items: int = 12, parent=None):
        super().__init__(parent)
        self.setObjectName("activity_feed")
        self.loader = loader
        self.max_items = max_items
        self._items: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent; border: 0;")
        self.scroll.viewport().setAutoFillBackground(False)
        self.host = QWidget()
        self.host.setStyleSheet("background: transparent; border: 0;")
        self.host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.host.setAutoFillBackground(False)
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll)

        self.lbl_empty = QLabel("No recent activity yet.")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setProperty("muted", True)
        self.lbl_empty.setMinimumHeight(80)
        root.addWidget(self.lbl_empty)

        self.timer = QTimer(self)
        self.timer.setInterval(refresh_ms)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def refresh(self) -> None:
        try:
            items = self.loader() or []
        except Exception:
            items = []
        self._items = list(items)[: self.max_items]
        self._rebuild()

    def _rebuild(self) -> None:
        # Remove all rows except the trailing stretch.
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.lbl_empty.setVisible(not self._items)
        for entry in self._items:
            self.list_layout.insertWidget(self.list_layout.count() - 1, self._row(entry))

    def _row(self, entry) -> QWidget:
        level = str(getattr(entry, "level", "INFO") or "INFO").upper()
        category = str(getattr(entry, "category", "") or "").upper()
        message = str(getattr(entry, "message", "") or "")
        action = str(getattr(entry, "action", "") or "")
        created = getattr(entry, "created_at", None)

        fg, bg = self.LEVEL_COLORS.get(level, ("#64748B", "#E2E8F0"))
        icon = self.CATEGORY_ICONS.get(category, "•")

        row = QFrame()
        row.setStyleSheet(
            f"background: {bg}; border-radius: 8px; border: 1px solid {bg};"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(8)

        dot = QLabel(icon)
        dot.setFixedWidth(22)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setStyleSheet(f"color: {fg}; font-size: 13px; background: transparent; border: 0;")
        lay.addWidget(dot)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        text = QLabel(message)
        text.setWordWrap(True)
        text.setStyleSheet("color: #1E293B; font-size: 12px; background: transparent; border: 0;")
        text_col.addWidget(text)
        meta = QLabel()
        parts = []
        if action:
            parts.append(action)
        if category:
            parts.append(category)
        if created:
            parts.append(format_local_datetime(created))
        meta.setText("  ·  ".join(parts))
        meta.setStyleSheet(f"color: {fg}; font-size: 10px; background: transparent; border: 0;")
        text_col.addWidget(meta)
        lay.addLayout(text_col, 1)
        return row

    def shutdown(self) -> None:
        self.timer.stop()