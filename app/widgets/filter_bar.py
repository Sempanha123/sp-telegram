from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget


class FilterBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def add(self, widget) -> None:
        self.layout.addWidget(widget)
