from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from app.theme_state import is_light


class TableCheckBoxDelegate(QStyledItemDelegate):
    """High-contrast table checkbox with a forgiving click target.

    Selection remains a row-selection concept; the colored check box only reflects
    Qt.ItemDataRole.CheckStateRole and therefore stays visually distinct from selected rows.
    """

    # Keep the established 18px visual contract while accepting clicks across
    # the full table cell. CLICK_SIZE remains available to themes/tests that
    # use the historical centered hit-box dimensions.
    VISUAL_SIZE = 18
    CLICK_SIZE = 32
    CORNER_RADIUS = 6

    @classmethod
    def _palette(cls, *, hover: bool, enabled: bool):
        if is_light():
            if not enabled:
                return QColor("#E3E9F4"), QColor("#F6F8FD")
            border = QColor("#6366F1" if hover else "#B9C6DE")
            fill = QColor("#6366F1") if hover else QColor("#FFFFFF")
            return border, fill
        if not enabled:
            return QColor("#332A5C"), QColor("#16112A")
        border = QColor("#7E5FC9" if hover else "#52418C")
        fill = QColor("#261C47") if hover else QColor("#171129")
        return border, fill

    @classmethod
    def _check_fill(cls) -> QColor:
        return QColor("#6366F1") if is_light() else QColor("#8B5CF6")

    @classmethod
    def _rect(cls, option) -> QRect:
        size = cls.VISUAL_SIZE
        return QRect(option.rect.center().x() - size // 2, option.rect.center().y() - size // 2, size, size)

    def paint(self, painter: QPainter, option, index):
        state = index.data(Qt.ItemDataRole.CheckStateRole)
        if state is None:
            return super().paint(painter, option, index)
        rect = self._rect(option)
        enabled = bool(index.flags() & Qt.ItemFlag.ItemIsEnabled)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        checked = state == Qt.CheckState.Checked
        partial = state == Qt.CheckState.PartiallyChecked
        border, fill = self._palette(hover=hover, enabled=enabled)
        if (checked or partial) and enabled:
            fill = self._check_fill()
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(border, 1.5))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
            if checked:
                painter.setPen(QPen(QColor("#ffffff"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                painter.drawLine(x + 4, y + h // 2, x + 8, y + h - 5)
                painter.drawLine(x + 8, y + h - 5, x + w - 4, y + 4)
            elif partial:
                painter.setPen(QPen(QColor("#ffffff"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(rect.x() + 4, rect.center().y(), rect.right() - 4, rect.center().y())
        finally:
            # A delegate paint exception must never leave the view's shared painter
            # in a saved state; otherwise Qt can cascade into QBackingStore errors.
            painter.restore()

    def editorEvent(self, event, model, option, index):
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable) or not (index.flags() & Qt.ItemFlag.ItemIsEnabled):
            return False
        if event.type() == QEvent.Type.MouseButtonRelease:
            point = event.position().toPoint()
            # The complete Select cell is a forgiving hit target. The visual
            # indicator remains compact, while users no longer need pixel-perfect
            # clicks on high-DPI displays.
            if option.rect.contains(point):
                current = index.data(Qt.ItemDataRole.CheckStateRole)
                next_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                return bool(model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole))
        if event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Space, Qt.Key.Key_Select}:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            return bool(model.setData(index, Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole))
        return False
