from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon


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
        return QIcon(str(path)) if path.exists() else QIcon()

    @classmethod
    def size(cls, compact: bool = False) -> QSize:
        return QSize(16, 16) if compact else QSize(18, 18)


def icon(name: str) -> QIcon:
    """Backward-compatible helper used by legacy modules."""
    return IconManager.get(name)
