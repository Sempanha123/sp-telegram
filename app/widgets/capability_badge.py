from __future__ import annotations

from PySide6.QtWidgets import QLabel


class CapabilityBadge(QLabel):
    def __init__(self, capability: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.capability = capability
        self.set_enabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.setText(f"{self.capability} {'✓' if enabled else '✕'}")
        bg = "#153923" if enabled else "#3b2026"
        fg = "#6ee7a3" if enabled else "#ff9daf"
        self.setStyleSheet(f"QLabel {{background:{bg};color:{fg};border-radius:8px;padding:3px 7px;}}")
