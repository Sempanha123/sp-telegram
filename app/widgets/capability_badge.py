from __future__ import annotations

from PySide6.QtWidgets import QLabel


class CapabilityBadge(QLabel):
    def __init__(self, capability: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.capability = capability
        self.setProperty("capabilityBadge", True)
        self.set_enabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.setText(f"{self.capability} {'✓' if enabled else '✕'}")
        self.setProperty("tone", "success" if enabled else "danger")
        self.style().unpolish(self); self.style().polish(self)
