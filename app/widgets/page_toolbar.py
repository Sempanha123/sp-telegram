from __future__ import annotations
from PySide6.QtWidgets import QFrame, QHBoxLayout

class PageToolbarWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("page_toolbar")
        self.layout = QHBoxLayout(self); self.layout.setContentsMargins(0,0,0,0); self.layout.setSpacing(8)
    def add(self, widget, stretch=0): self.layout.addWidget(widget, stretch)
    def add_stretch(self): self.layout.addStretch()
