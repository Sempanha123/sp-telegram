from __future__ import annotations

from PySide6.QtWidgets import QListWidget


class ActivityTimeline(QListWidget):
    def set_events(self, events: list[str]) -> None:
        self.clear()
        self.addItems(events)
