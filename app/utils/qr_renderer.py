from __future__ import annotations

from io import BytesIO

from PySide6.QtGui import QPixmap


def render_qr_pixmap(uri: str, size: int = 260) -> QPixmap:
    """Render a Telegram login URI in memory; the QR image is never written to disk."""
    import qrcode

    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap.scaled(size, size)
