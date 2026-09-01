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
                return QColor("#DDE3EE"), QColor("#F5F7FB")
            border = QColor("#5B5CE2" if hover else "#B8C2D4")
            fill = QColor("#5B5CE2") if hover else QColor("#FFFFFF")
            return border, fill
        if not enabled:
            return QColor("#26324A"), QColor("#0F1728")
        border = QColor("#8B9BFF" if hover else "#405171")
        fill = QColor("#1B2742") if hover else QColor("#11182B")
        return border, fill

    @classmethod
    def _check_fill(cls) -> QColor:
        return QColor("#5B5CE2") if is_light() else QColor("#6D7CFF")

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
