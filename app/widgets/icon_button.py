from __future__ import annotations
from PySide6.QtWidgets import QPushButton
from app.icons import IconManager

class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", parent=None):
        super().__init__(parent); self.setProperty("iconButton", True); self.setProperty("role","ghost")
        self.setIcon(IconManager.get(icon_name)); self.setIconSize(IconManager.size())
        if tooltip: self.setToolTip(tooltip)
