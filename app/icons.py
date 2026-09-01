from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel


class _PaletteSvgIconEngine(QIconEngine):
    """Render ``currentColor`` SVG icons using the active Qt palette."""

    def __init__(self, svg: str):
        super().__init__()
        self._svg = svg
        self._renderers: dict[str, QSvgRenderer] = {}

    def clone(self):
        return _PaletteSvgIconEngine(self._svg)

    @staticmethod
    def _color(mode: QIcon.Mode) -> str:
        app = QApplication.instance()
        if app is None:
            return "#718096"
        group = QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled else QPalette.ColorGroup.Active
        return app.palette().color(group, QPalette.ColorRole.Text).name()

    def _renderer(self, color: str) -> QSvgRenderer:
        renderer = self._renderers.get(color)
        if renderer is None:
            data = self._svg.replace("currentColor", color).encode("utf-8")
            renderer = QSvgRenderer(QByteArray(data))
            self._renderers[color] = renderer
        return renderer

    def paint(self, painter: QPainter, rect, mode: QIcon.Mode, state: QIcon.State) -> None:
        self._renderer(self._color(mode)).render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


class IconManager:
    """Central SVG icon provider for SP Telegram.

    Icons are intentionally lightweight monochrome SVGs so they scale cleanly
    at 100/125/150% Windows DPI without introducing a heavyweight icon pack.
    """

    _root = Path(__file__).resolve().parents[1] / "assets" / "icons"
    _aliases = {
        "account_health": "health",
        "source_groups": "source_groups",
        "target_groups": "target_groups",
        "member_pool": "members",
        "add": "plus",
        "bell": "notification",
    }

    @classmethod
    def path(cls, name: str) -> Path:
        resolved = cls._aliases.get(name, name)
        return cls._root / f"{resolved}.svg"

    @classmethod
    def get(cls, name: str) -> QIcon:
        path = cls.path(name)
        if not path.exists():
            return QIcon()
        try:
            return QIcon(_PaletteSvgIconEngine(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError):
            return QIcon(str(path))

    @classmethod
    def bind_label(cls, label: QLabel, name: str, size: int) -> None:
        """Attach a palette-aware icon pixmap that can refresh on theme change."""
        label.setProperty("themeIconName", name)
        label.setProperty("themeIconSize", int(size))
        cls.refresh_label(label)

    @classmethod
    def refresh_label(cls, label) -> None:
        name = str(label.property("themeIconName") or "")
        size = int(label.property("themeIconSize") or 18)
        if name and hasattr(label, "setPixmap"):
            label.setPixmap(cls.get(name).pixmap(size, size))

    @classmethod
    def size(cls, compact: bool = False) -> QSize:
        return QSize(16, 16) if compact else QSize(18, 18)


def icon(name: str) -> QIcon:
    """Backward-compatible helper used by legacy modules."""
    return IconManager.get(name)
