from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from app.styles.tokens import LIGHT_STATUS_COLORS, STATUS_COLORS
from app.theme_state import is_light


class StatusBadge(QLabel):
    """Compact status pill whose geometry is derived from its content.

    Qt layouts should never have to guess a fixed badge width.  The size hint
    explicitly includes the status dot, inter-item spacing and horizontal
    padding so longer values such as ``Login Required`` and ``Disconnected``
    cannot be clipped at normal/high-DPI Windows scales.
    """

    H_PADDING = 11
    V_PADDING = 5
    DOT_DIAMETER = 6
    DOT_SPACING = 6
    MIN_HEIGHT = 28
    MIN_WIDTH = 52

    def __init__(self, state: str = "Idle", parent=None):
        super().__init__(parent)
        self._display = ""
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        display = str(state or "Unknown").replace("_", " ").title()
        self._display = display
        key = display.lower()
        # Badges are painted inline rather than via QSS, so they must resolve the
        # palette for the active theme themselves.  Without this the dark palette
        # leaked into the soft-light UI as muddy dark-on-light pills.
        if is_light():
            bg, fg = LIGHT_STATUS_COLORS.get(key, ("#EEF2F7", "#64748B"))
        else:
            bg, fg = STATUS_COLORS.get(key, ("#1C263A", "#9AA7C0"))
        self.setText(f"●  {display}")
        self.setStyleSheet(
            "QLabel{"
            f"background:{bg};color:{fg};border-radius:8px;"
            "padding:4px 10px;font-weight:600;"
            "}"
        )
        self.updateGeometry()

    def _content_size(self) -> QSize:
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._display or "Unknown")
        text_height = metrics.height()
        dot_width = max(self.DOT_DIAMETER, metrics.horizontalAdvance("●"))
        width = text_width + dot_width + self.DOT_SPACING + (self.H_PADDING * 2)
        height = max(self.MIN_HEIGHT, text_height + (self.V_PADDING * 2))
        return QSize(max(self.MIN_WIDTH, width), height)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return self._content_size()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return self._content_size()
