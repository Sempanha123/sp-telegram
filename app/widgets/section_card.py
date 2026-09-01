from __future__ import annotations
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from app.icons import IconManager

class SectionCard(QFrame):
    def __init__(self, title: str, action_text: str = "", parent=None):
        super().__init__(parent); self.setProperty("sectionCard", True)
        root=QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(10)
        header=QHBoxLayout(); self.lbl_title=QLabel(title); self.lbl_title.setProperty("sectionTitle",True)
        header.addWidget(self.lbl_title); header.addStretch(); self.btn_action=None
        if action_text:
            self.btn_action=QPushButton(action_text); self.btn_action.setProperty("role","ghost"); self.btn_action.setIcon(IconManager.get("arrow_right")); header.addWidget(self.btn_action)
        root.addLayout(header); self.body=QVBoxLayout(); self.body.setSpacing(6); root.addLayout(self.body,1)
