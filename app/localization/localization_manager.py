from __future__ import annotations

import json
from pathlib import Path


class LocalizationManager:
    """Small JSON-backed display localization layer.

    Internal enum/database/license keys remain unchanged; only visible widget
    labels are translated.  Language changes are applied on the next source-app
    restart to avoid fragile mid-dialog mutations.
    """

    LANGUAGE_ALIASES = {
        "english": "en", "en": "en",
        "khmer": "km", "khmer (ui placeholder)": "km", "ខ្មែរ": "km", "km": "km",
    }

    def __init__(self, language: str = "English") -> None:
        self.root = Path(__file__).resolve().parent
        self._catalogs = {code: self._load(code) for code in ("en", "km")}
        self.language = "en"
        self.set_language(language)

    def _load(self, code: str) -> dict:
        with (self.root / f"{code}.json").open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @classmethod
    def normalize_language(cls, value: str | None) -> str:
        return cls.LANGUAGE_ALIASES.get(str(value or "English").strip().lower(), "en")

    def set_language(self, language: str | None) -> None:
        self.language = self.normalize_language(language)

    @property
    def display_name(self) -> str:
        return self._catalogs[self.language].get("language_name", "English")

    def page(self, key: str) -> tuple[str, str]:
        value = self._catalogs[self.language].get("pages", {}).get(key)
        if not value:
            value = self._catalogs["en"].get("pages", {}).get(key, [key.replace("_", " ").title(), ""])
        return str(value[0]), str(value[1] if len(value) > 1 else "")

    def translate_text(self, text: str) -> str:
        if self.language == "en" or not text:
            return text
        return self._catalogs[self.language].get("text", {}).get(text, text)

    def apply_to_widget_tree(self, root) -> None:
        """Translate common Qt widget text without renaming objectNames/keys."""
        if self.language == "en" or root is None:
            return
        try:
            from PySide6.QtGui import QAction
            from PySide6.QtWidgets import (
                QAbstractButton, QComboBox, QGroupBox, QLabel, QTabWidget, QWidget,
            )
        except ImportError:
            return
        widgets = [root] if isinstance(root, QWidget) else []
        if isinstance(root, QWidget):
            widgets.extend(root.findChildren(QWidget))
        for widget in widgets:
            if isinstance(widget, (QLabel, QAbstractButton, QGroupBox)):
                try:
                    widget.setText(self.translate_text(widget.text()))
                except (AttributeError, RuntimeError):
                    pass
            try:
                placeholder = widget.placeholderText()
                if placeholder:
                    widget.setPlaceholderText(self.translate_text(placeholder))
            except (AttributeError, RuntimeError):
                pass
            try:
                tooltip = widget.toolTip()
                if tooltip:
                    widget.setToolTip(self.translate_text(tooltip))
            except (AttributeError, RuntimeError):
                pass
            if isinstance(widget, QComboBox):
                for index in range(widget.count()):
                    current = widget.itemText(index)
                    translated = self.translate_text(current)
                    if translated != current:
                        widget.setItemText(index, translated)
            if isinstance(widget, QTabWidget):
                for index in range(widget.count()):
                    current = widget.tabText(index)
                    widget.setTabText(index, self.translate_text(current))
        try:
            for action in root.findChildren(QAction):
                action.setText(self.translate_text(action.text()))
                if action.toolTip():
                    action.setToolTip(self.translate_text(action.toolTip()))
        except (AttributeError, RuntimeError):
            pass
        try:
            title = root.windowTitle()
            if title:
                root.setWindowTitle(self.translate_text(title))
        except (AttributeError, RuntimeError):
            pass
