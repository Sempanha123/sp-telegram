from __future__ import annotations

from PySide6.QtCore import QDate, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QDateEdit,
    QDateTimeEdit,
    QHeaderView,
    QToolButton,
)


CALENDAR_MINIMUM_SIZE = QSize(420, 320)
DATE_EDITOR_MINIMUM_WIDTH = 210
DATE_EDITOR_MINIMUM_HEIGHT = 38
DAY_ROW_MINIMUM_HEIGHT = 36


class PolishedCalendarWidget(QCalendarWidget):
    """DPI-friendly calendar with full-cell selection and a distinct today ring."""

    SELECTED = QColor("#4C8DFF")
    SELECTED_TEXT = QColor("#FFFFFF")
    TODAY_BORDER = QColor("#6AA0FF")

    def paintCell(self, painter: QPainter, rect, date: QDate) -> None:  # noqa: N802
        # Let Qt render normal/disabled/outside-month/weekend typography first.
        if date != self.selectedDate():
            super().paintCell(painter, rect, date)
            if date == QDate.currentDate():
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(self.TODAY_BORDER, 1.5))
                painter.drawRoundedRect(QRectF(rect).adjusted(3.5, 3.5, -3.5, -3.5), 7, 7)
                painter.restore()
            return

        # Selected date owns almost the complete cell instead of just a text fragment.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.SELECTED)
        selected_rect = QRectF(rect).adjusted(2.5, 2.5, -2.5, -2.5)
        painter.drawRoundedRect(selected_rect, 7, 7)
        painter.setPen(self.SELECTED_TEXT)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), str(date.day()))
        painter.restore()


def _install_polished_calendar(editor: QDateEdit | QDateTimeEdit) -> PolishedCalendarWidget:
    existing = editor.calendarWidget()
    if isinstance(existing, PolishedCalendarWidget):
        return existing
    calendar = PolishedCalendarWidget(editor)
    editor.setCalendarWidget(calendar)
    return calendar


def configure_calendar_popup(editor: QDateEdit | QDateTimeEdit) -> QCalendarWidget:
    """Apply one DPI-friendly calendar policy to every date/date-time editor."""
    editor.setCalendarPopup(True)
    editor.setMinimumWidth(DATE_EDITOR_MINIMUM_WIDTH)
    editor.setMinimumHeight(DATE_EDITOR_MINIMUM_HEIGHT)

    calendar = _install_polished_calendar(editor)
    calendar.setMinimumSize(CALENDAR_MINIMUM_SIZE)
    calendar.setGridVisible(False)
    calendar.setNavigationBarVisible(True)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)

    # Use a subtle weekend tint rather than Qt's default aggressive red.
    weekend = QTextCharFormat()
    weekend.setForeground(QColor("#AAB6C8"))
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend)
    calendar.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend)

    view = calendar.findChild(QAbstractItemView, "qt_calendar_calendarview")
    if view is not None:
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setMinimumHeight(DAY_ROW_MINIMUM_HEIGHT * 7)
        vertical = getattr(view, "verticalHeader", lambda: None)()
        if vertical is not None:
            vertical.setMinimumSectionSize(DAY_ROW_MINIMUM_HEIGHT)
            vertical.setDefaultSectionSize(DAY_ROW_MINIMUM_HEIGHT)
        horizontal = getattr(view, "horizontalHeader", lambda: None)()
        if horizontal is not None:
            horizontal.setMinimumSectionSize(44)
            horizontal.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    for object_name in ("qt_calendar_prevmonth", "qt_calendar_nextmonth"):
        button = calendar.findChild(QToolButton, object_name)
        if button is not None:
            button.setMinimumSize(36, 30)
    month_button = calendar.findChild(QToolButton, "qt_calendar_monthbutton")
    year_button = calendar.findChild(QToolButton, "qt_calendar_yearbutton")
    for button in (month_button, year_button):
        if button is not None:
            button.setMinimumWidth(88)

    calendar.setStyleSheet(
        "QCalendarWidget QWidget#qt_calendar_navigationbar { min-height: 40px; }"
        "QCalendarWidget QToolButton { min-height: 30px; padding: 4px 10px; font-weight: 600; }"
        "QCalendarWidget QToolButton#qt_calendar_prevmonth,"
        "QCalendarWidget QToolButton#qt_calendar_nextmonth { min-width: 36px; }"
        "QCalendarWidget QAbstractItemView { outline: 0; selection-background-color: transparent; selection-color: #FFFFFF; }"
        "QCalendarWidget QAbstractItemView::item { min-height: 36px; padding: 5px; }"
        "QCalendarWidget QAbstractItemView::item:hover { background: #1B2432; border-radius: 6px; }"
    )
    return calendar
