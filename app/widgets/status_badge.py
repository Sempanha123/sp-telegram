from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from app.styles.tokens import STATUS_TONE_BY_KEY


class StatusBadge(QLabel):
    """Compact status pill whose geometry is derived from its content.

    Qt layouts should never have to guess a fixed badge width.  The size hint
    explicitly includes the status dot, inter-item spacing and horizontal
    padding so longer values such as ``Login Required`` and ``Disconnected``
    cannot be clipped at normal/high-DPI Windows scales.
    """

    H_PADDING = 12
    V_PADDING = 5
    MIN_HEIGHT = 28
    MIN_WIDTH = 52

    def __init__(self, state: str = "Idle", parent=None):
        super().__init__(parent)
        self._display = ""
        self.setProperty("statusBadge", True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        display = str(state or "Unknown").replace("_", " ").title()
        self._display = display
        key = display.lower()
        self.setText(f"●  {display}")
        self.setProperty("tone", STATUS_TONE_BY_KEY.get(key, "muted"))
        self.style().unpolish(self); self.style().polish(self)
        self.updateGeometry()

    def _content_size(self) -> QSize:
        metrics = self.fontMetrics()
        # Measure exactly what QLabel paints.  Estimating the bullet and its
        # spaces separately clipped the final character on some Windows DPI
        # settings (for example, "Connected").
        text_width = metrics.horizontalAdvance(self.text() or "●  Unknown")
        text_height = metrics.height()
        width = text_width + (self.H_PADDING * 2) + 2
        height = max(self.MIN_HEIGHT, text_height + (self.V_PADDING * 2))
        return QSize(max(self.MIN_WIDTH, width), height)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return self._content_size()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return self._content_size()
