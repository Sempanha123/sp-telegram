"""Lightweight, dependency-free chart widgets for the Analytics page.

All charts are painted with QPainter so they render crisply at any DPI and
need no external plotting library.  They are intentionally simple: horizontal
bar charts, donut charts and a small trend (area) chart.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.theme_state import is_light

# Product palette (foreground, soft background) pairs used across charts.
CHART_PALETTE = [
    ("#2563EB", "#DBEAFE"),  # blue
    ("#7C3AED", "#EDE9FE"),  # purple
    ("#059669", "#D1FAE5"),  # green
    ("#D97706", "#FEF3C7"),  # amber
    ("#DC2626", "#FEE2E2"),  # red
    ("#0D9488", "#CFFAFE"),  # teal
    ("#DB2777", "#FCE7F3"),  # pink
    ("#4F46E5", "#E0E7FF"),  # indigo
    ("#0891B2", "#CFFAFE"),  # cyan
    ("#65A30D", "#ECFCCB"),  # lime
]


def _ui_palette() -> dict[str, str]:
    if is_light():
        return {
            "text": "#172033",
            "secondary": "#56627A",
            "muted": "#8491A9",
            "surface": "#FFFFFF",
            "track": "#EEF2F8",
            "grid": "#E5EAF2",
        }
    return {
        "text": "#F5F7FF",
        "secondary": "#B7C1D9",
        "muted": "#7F8BA6",
        "surface": "#11182B",
        "track": "#1C2740",
        "grid": "#283651",
    }

STATUS_COLORS = {
    "HEALTHY": ("#059669", "#D1FAE5"),
    "CONNECTED": ("#059669", "#D1FAE5"),
    "COMPLETED": ("#059669", "#D1FAE5"),
    "SUCCESS": ("#059669", "#D1FAE5"),
    "SENT": ("#059669", "#D1FAE5"),
    "ELIGIBLE": ("#059669", "#D1FAE5"),
    "APPROVED": ("#059669", "#D1FAE5"),
    "READY": ("#2563EB", "#DBEAFE"),
    "RUNNING": ("#2563EB", "#DBEAFE"),
    "ACTIVE": ("#2563EB", "#DBEAFE"),
    "SCHEDULED": ("#7C3AED", "#EDE9FE"),
    "PENDING": ("#7C3AED", "#EDE9FE"),
    "QUEUED": ("#7C3AED", "#EDE9FE"),
    "UNKNOWN": ("#64748B", "#E2E8F0"),
    "WARNING": ("#D97706", "#FEF3C7"),
    "PARTIAL_SUCCESS": ("#D97706", "#FEF3C7"),
    "PAUSED": ("#D97706", "#FEF3C7"),
    "COOLDOWN": ("#D97706", "#FEF3C7"),
    "FAILED": ("#DC2626", "#FEE2E2"),
    "ERROR": ("#DC2626", "#FEE2E2"),
    "CANCELLED": ("#DC2626", "#FEE2E2"),
    "INTERRUPTED": ("#DC2626", "#FEE2E2"),
    "RECONCILE_REQUIRED": ("#DC2626", "#FEE2E2"),
    "LOGIN_REQUIRED": ("#D97706", "#FEF3C7"),
    "EXCLUDED": ("#64748B", "#E2E8F0"),
    "BOT": ("#DB2777", "#FCE7F3"),
    "DELETED": ("#DC2626", "#FEE2E2"),
    "PUBLIC": ("#059669", "#D1FAE5"),
    "PRIVATE": ("#7C3AED", "#EDE9FE"),
    "CHANNEL": ("#2563EB", "#DBEAFE"),
    "SUPERGROUP": ("#7C3AED", "#EDE9FE"),
    "GROUP": ("#0D9488", "#CFFAFE"),
    "MEMBER_SYNC": ("#2563EB", "#DBEAFE"),
    "GROUP_SYNC": ("#7C3AED", "#EDE9FE"),
    "GROUP_DISCOVERY": ("#0D9488", "#CFFAFE"),
    "TARGET_MEMBER_INVITE": ("#DB2777", "#FCE7F3"),
    "TARGET_MEMBER_SYNC": ("#059669", "#D1FAE5"),
    "DATABASE_BACKUP": ("#D97706", "#FEF3C7"),
    "DATABASE_MAINTENANCE": ("#4F46E5", "#E0E7FF"),
    "SYSTEM_DIAGNOSTIC": ("#0891B2", "#CFFAFE"),
    "INFO": ("#2563EB", "#DBEAFE"),
    "HEALTH_CHECK": ("#059669", "#D1FAE5"),
    "DISABLED": ("#64748B", "#E2E8F0"),
    "QR_LOGIN_STARTED": ("#7C3AED", "#EDE9FE"),
    "LOGIN_SUCCESS": ("#059669", "#D1FAE5"),
    "SESSION_REFRESHED": ("#0D9488", "#CFFAFE"),
    "PROFILE_REFRESHED": ("#4F46E5", "#E0E7FF"),
}


def _palette_for(label: str, index: int = 0) -> tuple[str, str]:
    key = str(label).upper().replace(" ", "_")
    if key in STATUS_COLORS:
        return STATUS_COLORS[key]
    return CHART_PALETTE[index % len(CHART_PALETTE)]


class BarChartWidget(QFrame):
    """Horizontal bar chart with value labels and a legend.

    ``data`` is a list of ``(label, value)`` tuples.  Bars are drawn with a
    soft gradient and rounded ends; the largest value gets a highlight.
    """

    def __init__(self, data: list[tuple[str, float | int]], title: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("chartCard", True)
        self._data = list(data)
        self._title = title
        self._bar_h = 26
        self._gap = 10
        self._pad = 16
        self._label_w = 150
        self._value_w = 56
        self.setMinimumHeight(120)

    def set_data(self, data: list[tuple[str, float | int]]) -> None:
        self._data = list(data)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ui = _ui_palette()
        w = self.width()
        h = self.height()

        if self._title:
            painter.setPen(QColor(ui["text"]))
            font = QFont()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(self._pad, 8, w - self._pad * 2, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)
            top = 34
        else:
            top = 12

        if not self._data:
            painter.setPen(QColor(ui["muted"]))
            font = QFont()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(self._pad, top, w - self._pad * 2, h - top - self._pad), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return

        max_val = max(v for _, v in self._data) or 1
        chart_w = w - self._pad * 2 - self._label_w - self._value_w - 8
        y = top
        for i, (label, value) in enumerate(self._data):
            fg, bg = _palette_for(label, i)
            bar_w = max(6, int(chart_w * (value / max_val)))
            # label
            painter.setPen(QColor(ui["secondary"]))
            font = QFont()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                QRectF(self._pad, y, self._label_w - 8, self._bar_h),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(label),
            )
            # bar background track
            track = QRectF(self._pad + self._label_w, y, chart_w, self._bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ui["track"]))
            painter.drawRoundedRect(track, self._bar_h / 2, self._bar_h / 2)
            # bar
            bar = QRectF(self._pad + self._label_w, y, bar_w, self._bar_h)
            grad = QLinearGradient(bar.topLeft(), bar.topRight())
            grad.setColorAt(0, QColor(fg))
            grad.setColorAt(1, QColor(fg).lighter(115))
            painter.setBrush(grad)
            painter.drawRoundedRect(bar, self._bar_h / 2, self._bar_h / 2)
            # value
            painter.setPen(QColor(ui["text"]))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(self._pad + self._label_w + chart_w + 8, y, self._value_w, self._bar_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{value:,}",
            )
            y += self._bar_h + self._gap
        painter.end()


class DonutChartWidget(QFrame):
    """Donut chart with a centered total and a side legend."""

    def __init__(self, data: list[tuple[str, float | int]], title: str = "", total_label: str = "Total", parent=None):
        super().__init__(parent)
        self.setProperty("chartCard", True)
        self._data = list(data)
        self._title = title
        self._total_label = total_label
        self.setMinimumHeight(150)

    def set_data(self, data: list[tuple[str, float | int]]) -> None:
        self._data = list(data)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ui = _ui_palette()
        w = self.width()
        h = self.height()

        if self._title:
            painter.setPen(QColor(ui["text"]))
            font = QFont()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(16, 8, w - 32, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)
            top = 34
        else:
            top = 12

        if not self._data:
            painter.setPen(QColor(ui["muted"]))
            font = QFont()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(16, top, w - 32, h - top - 16), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return

        total = sum(v for _, v in self._data) or 1
        legend_w = 190
        chart_area = w - 32 - legend_w
        diameter = min(chart_area - 20, h - top - 24, 170)
        cx = 16 + diameter / 2 + 10
        cy = top + (h - top - 16) / 2
        rect = QRectF(cx - diameter / 2, cy - diameter / 2, diameter, diameter)

        start = 90.0
        for i, (label, value) in enumerate(self._data):
            fg, bg = _palette_for(label, i)
            span = -360.0 * (value / total)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fg))
            painter.drawPie(rect, int(start * 16), int(span * 16))
            start += span

        # center hole
        hole = QRectF(rect.center().x() - diameter * 0.42, rect.center().y() - diameter * 0.42, diameter * 0.84, diameter * 0.84)
        painter.setBrush(QColor(ui["surface"]))
        painter.drawEllipse(hole)
        painter.setPen(QColor(ui["text"]))
        font = QFont()
        font.setPixelSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(hole.adjusted(0, -10, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{total:,}")
        font.setPixelSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(ui["muted"]))
        painter.drawText(hole.adjusted(0, 14, 0, 0), Qt.AlignmentFlag.AlignCenter, self._total_label)

        # legend
        lx = 16 + chart_area + 8
        ly = top
        for i, (label, value) in enumerate(self._data):
            fg, bg = _palette_for(label, i)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fg))
            painter.drawEllipse(QRectF(lx, ly + 4, 10, 10))
            painter.setPen(QColor(ui["secondary"]))
            font = QFont()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(lx + 16, ly, legend_w - 16, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(label))
            painter.setPen(QColor(ui["text"]))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(lx + 16, ly + 18, legend_w - 16, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{value:,}  ({value * 100 / total:.0f}%)")
            ly += 40
        painter.end()


class TrendChartWidget(QFrame):
    """Simple area/line trend chart for time-series data.

    ``data`` is a list of ``(label, value)`` tuples ordered by time.
    """

    def __init__(self, data: list[tuple[str, float | int]], title: str = "", color: str = "#2563EB", parent=None):
        super().__init__(parent)
        self.setProperty("chartCard", True)
        self._data = list(data)
        self._title = title
        self._color = color
        self.setMinimumHeight(150)

    def set_data(self, data: list[tuple[str, float | int]], color: str | None = None) -> None:
        self._data = list(data)
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ui = _ui_palette()
        w = self.width()
        h = self.height()

        if self._title:
            painter.setPen(QColor(ui["text"]))
            font = QFont()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(16, 8, w - 32, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)
            top = 34
        else:
            top = 12

        if not self._data:
            painter.setPen(QColor(ui["muted"]))
            font = QFont()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(16, top, w - 32, h - top - 16), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return

        pad_l, pad_r, pad_t, pad_b = 40, 12, 8, 22
        plot_w = w - pad_l - pad_r
        plot_h = h - top - pad_t - pad_b
        max_val = max(v for _, v in self._data) or 1

        # grid lines
        painter.setPen(QPen(QColor(ui["grid"]), 1))
        for i in range(5):
            gy = top + pad_t + plot_h * i / 4
            painter.drawLine(pad_l, int(gy), w - pad_r, int(gy))

        # area + line
        n = len(self._data)
        points = []
        for i, (_, value) in enumerate(self._data):
            x = pad_l + plot_w * i / max(1, n - 1)
            y = top + pad_t + plot_h * (1 - value / max_val)
            points.append((x, y))

        path = QPainterPath()
        if points:
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            path.lineTo(points[-1][0], top + pad_t + plot_h)
            path.lineTo(points[0][0], top + pad_t + plot_h)
            path.closeSubpath()
            grad = QLinearGradient(0, top + pad_t, 0, top + pad_t + plot_h)
            base = QColor(self._color)
            grad.setColorAt(0, QColor(base.red(), base.green(), base.blue(), 90))
            grad.setColorAt(1, QColor(base.red(), base.green(), base.blue(), 12))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawPath(path)

            # line
            pen = QPen(QColor(self._color), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(1, len(points)):
                painter.drawLine(int(points[i - 1][0]), int(points[i - 1][1]), int(points[i][0]), int(points[i][1]))

            # dots
            painter.setBrush(QColor(ui["surface"]))
            for x, y in points:
                painter.setPen(QPen(QColor(self._color), 2))
                painter.drawEllipse(QRectF(x - 3, y - 3, 6, 6))

        # y labels
        painter.setPen(QColor(ui["muted"]))
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        for i in range(5):
            val = max_val * (1 - i / 4)
            gy = top + pad_t + plot_h * i / 4
            painter.drawText(QRectF(0, gy - 8, pad_l - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{val:.0f}")

        # x labels
        step = max(1, n // 6)
        for i in range(0, n, step):
            x = pad_l + plot_w * i / max(1, n - 1)
            label = str(self._data[i][0])
            painter.drawText(QRectF(x - 30, top + pad_t + plot_h + 4, 60, 16), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
