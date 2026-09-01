from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QStylePainter, QTabBar


class HorizontalWestTabBar(QTabBar):
    """West-side tab bar that keeps labels horizontal instead of rotating them."""

    def tabSizeHint(self, index: int) -> QSize:
        base = super().tabSizeHint(index)
        return QSize(max(158, base.height() + 70), max(40, min(44, base.width())))

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            rect = self.tabRect(index)
            option.rect = rect
            text = option.text
            option.text = ""
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            painter.save()
            color = self.palette().highlightedText().color() if index == self.currentIndex() else self.palette().text().color()
            painter.setPen(color)
            painter.drawText(rect.adjusted(14,0,-10,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            painter.restore()
