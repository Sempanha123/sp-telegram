from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class NetworkMonitor(QObject):
    """Signal-driven connectivity state; does not aggressively ping Telegram."""

    stateChanged = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.state = "UNKNOWN"
        self.telegram_state = "UNKNOWN"

    def set_state(self, state: str) -> None:
        state = str(state).upper()
        if state not in {"ONLINE", "OFFLINE", "PARTIAL", "UNKNOWN"}:
            state = "UNKNOWN"
        if state != self.state:
            self.state = state
            self.stateChanged.emit(state)

    def report_success(self, *, telegram: bool = False) -> None:
        self.set_state("ONLINE")
        if telegram: self.telegram_state = "READY"

    def report_failure(self, error_code: str | None = None, *, telegram: bool = False) -> None:
        code = str(error_code or "").upper()
        if code in {"NETWORK_ERROR", "NETWORK_TIMEOUT", "CONNECTION_LOST"}:
            self.set_state("OFFLINE")
        else:
            self.set_state("PARTIAL")
        if telegram: self.telegram_state = "OFFLINE" if self.state == "OFFLINE" else "PARTIAL"
