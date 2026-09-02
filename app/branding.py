from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap


BRAND_ROOT = Path(__file__).resolve().parents[1] / "assets" / "branding"
BRAND_LOGO_PATH = BRAND_ROOT / "sp_cambo_logo.png"
BRAND_MARK_PATH = BRAND_ROOT / "sp_cambo_mark.png"


def brand_icon() -> QIcon:
    """Return the application icon backed by the SP Cambo brand mark."""
    return QIcon(str(BRAND_MARK_PATH)) if BRAND_MARK_PATH.is_file() else QIcon()


def _scaled_pixmap(path: Path, width: int, height: int) -> QPixmap:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        QSize(width, height),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def brand_logo_pixmap(width: int = 52, height: int = 40) -> QPixmap:
    """Return the full transparent SP Cambo logo for expanded brand chrome."""
    return _scaled_pixmap(BRAND_LOGO_PATH, width, height)


def brand_mark_pixmap(width: int = 38, height: int = 30) -> QPixmap:
    """Return the compact SP mark for collapsed navigation and window chrome."""
    return _scaled_pixmap(BRAND_MARK_PATH, width, height)
