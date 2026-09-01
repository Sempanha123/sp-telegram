from __future__ import annotations
from PySide6.QtWidgets import QLineEdit
from app.icons import IconManager

class SearchBar(QLineEdit):
    def __init__(self, placeholder: str = "Search…", parent=None):
        super().__init__(parent); self.setPlaceholderText(placeholder); self.setClearButtonEnabled(True)
        self.addAction(IconManager.get("search"), QLineEdit.ActionPosition.LeadingPosition)
