from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class PageHeaderWidget(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("page_header")
        # A page header is content, not a canvas.  When a table/feature body is
        # hidden Qt otherwise gives this frame the unused vertical space and
        # separates its title, subtitle and actions by hundreds of pixels.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setMaximumHeight(104)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_title = QLabel(title)
        self.lbl_title.setProperty("pageTitle", True)
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setProperty("pageSubtitle", True)
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setVisible(bool(subtitle))
        text.addWidget(self.lbl_title)
        text.addWidget(self.lbl_subtitle)
        root.addLayout(text, 1)
        self.action_host = QWidget()
        self.action_layout = QHBoxLayout(self.action_host)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(8)
        self.action_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        root.addWidget(self.action_host, 0, Qt.AlignmentFlag.AlignTop)

    def add_action(self, widget) -> None:
        self.action_layout.addWidget(widget)

    def set_subtitle(self, text: str) -> None:
        self.lbl_subtitle.setText(text)
        self.lbl_subtitle.setVisible(bool(text))
