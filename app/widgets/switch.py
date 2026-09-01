from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QCheckBox


class SwitchWidget(QCheckBox):
    """QCheckBox-compatible, lightweight painted switch.

    It preserves every existing checked/toggled API and objectName contract used
    by Settings while replacing the native checkbox indicator visually.
    """
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setProperty("switch", True)
        self.setMinimumHeight(28)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(base.width() + 28, max(28, base.height()))

    def paintEvent(self, event) -> None:
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track_w, track_h = 36.0, 20.0
        y = (self.height() - track_h) / 2.0
        track = QRectF(1.0, y, track_w, track_h)
        if not self.isEnabled(): track_color = QColor("#253044")
        elif self.isChecked(): track_color = QColor("#4C8DFF")
        else: track_color = QColor("#344056")
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(track_color); painter.drawRoundedRect(track, 10, 10)
        knob = 16.0; x = track.right() - knob - 2 if self.isChecked() else track.left() + 2
        painter.setBrush(QColor("#F2F5F9")); painter.drawEllipse(QRectF(x, y + 2, knob, knob))
        text_rect = self.rect().adjusted(47, 0, 0, 0)
        painter.setPen(self.palette().color(QPalette.ColorRole.Text) if self.isEnabled() else self.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.hasFocus():
            painter.setPen(QColor("#4C8DFF")); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRoundedRect(track.adjusted(-1,-1,1,1),11,11)
