from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle

from app.styles.tokens import LIGHT_STATUS_COLORS, STATUS_COLORS
from app.theme_state import is_light


class ModernTableDelegate(QStyledItemDelegate):
    """Paint known status values as content-sized badges without cell widgets."""

    BADGE_HEIGHT = 28
    H_PADDING = 12
    DOT_DIAMETER = 6
    DOT_SPACING = 6
    CELL_MARGIN = 8

    @staticmethod
    def _status_palette(value):
        key = str(value or "").replace("_", " ").strip().lower()
        palette = LIGHT_STATUS_COLORS if is_light() else STATUS_COLORS
        return palette.get(key)

    def _badge_width(self, metrics, text: str) -> int:
        # The dot is painted as geometry, not as part of the text.  Measuring
        # those two pieces independently keeps the right padding symmetric at
        # every Windows DPI/font scale.
        return max(52, metrics.horizontalAdvance(text) + self.DOT_DIAMETER + self.DOT_SPACING + self.H_PADDING * 2)

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        base = super().sizeHint(option, index)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not self._status_palette(text):
            return base
        width = self._badge_width(option.fontMetrics, text) + self.CELL_MARGIN * 2
        return QSize(max(base.width(), width), max(base.height(), self.BADGE_HEIGHT + 8))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        value = index.data(Qt.ItemDataRole.DisplayRole)
        palette = self._status_palette(value)
        if not palette:
            return super().paint(painter, option, index)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        bg, fg = palette
        wanted = self._badge_width(option.fontMetrics, text)
        available = max(0, option.rect.width() - self.CELL_MARGIN * 2)
        width = min(available, wanted) if available else wanted
        rect = QRect(
            option.rect.x() + self.CELL_MARGIN,
            option.rect.y() + (option.rect.height() - self.BADGE_HEIGHT) // 2,
            max(0, width),
            self.BADGE_HEIGHT,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fg))
        dot_x = rect.x() + self.H_PADDING
        painter.drawEllipse(
            QRect(
                dot_x,
                rect.y() + (rect.height() - self.DOT_DIAMETER) // 2,
                self.DOT_DIAMETER,
                self.DOT_DIAMETER,
            )
        )
        text_rect = rect.adjusted(
            self.H_PADDING + self.DOT_DIAMETER + self.DOT_SPACING,
            0,
            -self.H_PADDING,
            0,
        )
        painter.setPen(QColor(fg))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )
        painter.restore()
