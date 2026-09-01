from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHeaderView

from app.theme_state import is_light


class SelectAllHeader(QHeaderView):
    """Tri-state, high-contrast checkbox for the currently visible page only.

    The Select column header paints only a centered checkbox: no header text and
    no per-theme mismatched background, so the column reads as a control rather
    than a labelled data column.
    """
    VISUAL_SIZE = 18
    CORNER_RADIUS = 6

    @classmethod
    def _section_palette(cls):
        if is_light():
            return QColor("#F8FAFD"), QColor("#DDE3EE"), QColor("#B8C2D4"), QColor("#5B5CE2")
        return QColor("#141D32"), QColor("#2B3855"), QColor("#405171"), QColor("#6D7CFF")

    def _source(self):
        model = self.model()
        source = getattr(model, "sourceModel", lambda: None)() if model else None
        return source if source is not None else model

    def _paint_checkbox(self, painter: QPainter, rect: QRect) -> None:
        source = self._source()
        if source is None or not hasattr(source, "visible_check_state"):
            return
        size = self.VISUAL_SIZE
        box = QRect(rect.center().x() - size // 2, rect.center().y() - size // 2, size, size)
        state = source.visible_check_state()
        checked, partial = state == Qt.CheckState.Checked, state == Qt.CheckState.PartiallyChecked
        _, _, border, active = self._section_palette()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(active if (checked or partial) else border, 1.5))
        painter.setBrush(active if (checked or partial) else QColor(0, 0, 0, 0))
        painter.drawRoundedRect(box, self.CORNER_RADIUS, self.CORNER_RADIUS)
        if checked:
            painter.setPen(QPen(QColor("#ffffff"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            x, y, w, h = box.x(), box.y(), box.width(), box.height()
            painter.drawLine(x + 4, y + h // 2, x + 8, y + h - 5)
            painter.drawLine(x + 8, y + h - 5, x + w - 4, y + 4)
        elif partial:
            painter.setPen(QPen(QColor("#ffffff"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(box.x() + 4, box.center().y(), box.right() - 4, box.center().y())

    def paintSection(self, painter: QPainter, rect, logicalIndex):  # noqa: N802
        if logicalIndex != 0:
            super().paintSection(painter, rect, logicalIndex)
            return
        # Skip super() for the Select column: it would paint the column label
        # ("Select") over the checkbox. Replicate only the flat header surface
        # and its bottom border so the cell matches neighbouring sections.
        background, border, _, _ = self._section_palette()
        painter.save()
        painter.fillRect(rect, background)
        painter.setPen(QPen(border, 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        self._paint_checkbox(painter, rect)
        painter.restore()

    def mousePressEvent(self, event):  # noqa: N802
        logical = self.logicalIndexAt(event.position().toPoint())
        if logical == 0:
            rect = self.sectionViewportPosition(0)
            section = QRect(rect, 0, self.sectionSize(0), self.height())
            if section.contains(event.position().toPoint()):
                source = self._source()
                if source is not None and hasattr(source, "set_all_visible_checked"):
                    source.set_all_visible_checked(source.visible_check_state() != Qt.CheckState.Checked)
                    self.viewport().update()
                    return
        super().mousePressEvent(event)
