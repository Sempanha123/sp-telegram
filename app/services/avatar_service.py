from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from app.theme_state import is_light

_LOG = logging.getLogger(__name__)

# Pastel palette used for generated initials avatars (light theme friendly).
_AVATAR_COLORS = [
    ("#3B82F6", "#DBEAFE"),
    ("#8B5CF6", "#EDE9FE"),
    ("#10B981", "#D1FAE5"),
    ("#F59E0B", "#FEF3C7"),
    ("#EF4444", "#FEE2E2"),
    ("#06B6D4", "#CFFAFE"),
    ("#EC4899", "#FCE7F3"),
    ("#6366F1", "#E0E7FF"),
]

# Dark-theme friendly variants: light foreground on a dark tinted background so
# generated initials stay readable against the dark table surface.
_AVATAR_COLORS_DARK = [
    ("#93C5FD", "#1E3A5F"),
    ("#C4B5FD", "#3B2A63"),
    ("#6EE7B7", "#14532D"),
    ("#FCD34D", "#78350F"),
    ("#FCA5A5", "#7F1D1D"),
    ("#67E8F9", "#164E63"),
    ("#F9A8D4", "#831843"),
    ("#A5B4FC", "#312E81"),
]


class AvatarService(QObject):
    """Downloads, caches and serves entity avatars (accounts, groups, members).

    Photos are cached under ``data/cache/avatars/`` as ``<kind>_<entity_id>.jpg``.
    When a photo is not available yet, a colored initials pixmap is generated so
    the UI always has something friendly to show. Downloads run on the Telegram
    worker thread; ``avatarReady`` is emitted when a photo lands on disk.
    """

    avatarReady = Signal(str, int)  # kind, entity_id

    # Failed downloads are retried periodically (and immediately when the
    # authorizing account connects) so real photos appear once the account is
    # connected/authorized, instead of showing initials forever.
    RETRY_INTERVAL_MS = 10000

    def __init__(self, worker, profile_service, cache_dir, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.profile_service = profile_service
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # token -> (kind, entity_id, peer_id, account_id)
        self._pending: dict[str, tuple[str, int, int | None, int]] = {}
        # (kind, entity_id) -> (peer_id, account_id) awaiting retry
        self._failed: dict[tuple[str, int], tuple[int | None, int]] = {}
        self._pixmap_cache: dict[tuple[str, int, int, bool], QPixmap] = {}
        if self.worker is not None:
            self.worker.operationCompleted.connect(self._on_operation_completed)
            self.worker.operationFailed.connect(self._on_operation_failed)
            self.worker.accountConnected.connect(self.retry_for_account)
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(self.RETRY_INTERVAL_MS)
        self._retry_timer.timeout.connect(self._retry_failed)
        self._retry_timer.start()

    # -- path helpers -----------------------------------------------------
    def path_for(self, kind: str, entity_id: int) -> Path:
        return self.cache_dir / f"{kind}_{int(entity_id)}.jpg"

    def has_cached(self, kind: str, entity_id: int) -> bool:
        return self.path_for(kind, entity_id).is_file()

    # -- async download ---------------------------------------------------
    def request(self, kind: str, entity_id: int, *, peer_id: int | None = None, account_id: int = 0) -> None:
        """Request an avatar download for an entity. No-op when already cached/pending."""
        if entity_id is None or int(entity_id) <= 0:
            return
        entity_id = int(entity_id)
        if self.has_cached(kind, entity_id):
            return
        if any(eid == entity_id and k == kind for k, eid, _p, _a in self._pending.values()):
            return
        if self.worker is None:
            return
        dest = self.path_for(kind, entity_id)
        try:
            token = self.worker.submit_coroutine(
                self.profile_service.download_profile_photo(account_id, peer_id, str(dest)),
                operation=f"avatar:{kind}",
                account_id=account_id,
            )
        except RuntimeError as exc:
            _LOG.debug("Avatar request rejected for %s %s: %s", kind, entity_id, exc)
            return
        self._pending[token] = (kind, entity_id, peer_id, account_id)
        _LOG.debug("Avatar download requested for %s %s (account=%s peer=%s)", kind, entity_id, account_id, peer_id)

    def _on_operation_completed(self, token: str, result) -> None:
        entry = self._pending.pop(token, None)
        if entry is None:
            return
        kind, entity_id, _peer_id, _account_id = entry
        self._failed.pop((kind, entity_id), None)
        # Drop every cached pixmap for this entity so the freshly downloaded
        # photo replaces the generated initials on the next repaint.
        for key in [k for k in self._pixmap_cache if k[0] == kind and k[1] == entity_id]:
            del self._pixmap_cache[key]
        _LOG.info("Avatar downloaded for %s %s", kind, entity_id)
        self.avatarReady.emit(kind, entity_id)

    def _on_operation_failed(self, token: str, account_id: int, message: str) -> None:
        entry = self._pending.pop(token, None)
        if entry is None:
            return
        kind, entity_id, peer_id, _account_id = entry
        _LOG.warning("Avatar download failed for %s %s: %s", kind, entity_id, message)
        self._failed[(kind, entity_id)] = (peer_id, account_id or _account_id)

    def retry_for_account(self, account_id: int) -> None:
        """Retry failed downloads that need this account right away."""
        for (kind, entity_id), (peer_id, acct) in list(self._failed.items()):
            if acct == account_id:
                self._failed.pop((kind, entity_id), None)
                self.request(kind, entity_id, peer_id=peer_id, account_id=account_id)

    def _retry_failed(self) -> None:
        if self.worker is None:
            return
        for (kind, entity_id), (peer_id, account_id) in list(self._failed.items()):
            self._failed.pop((kind, entity_id), None)
            self.request(kind, entity_id, peer_id=peer_id, account_id=account_id)

    # -- pixmap generation ------------------------------------------------
    def pixmap(self, kind: str, entity_id: int, name: str, size: int = 40) -> QPixmap:
        """Return a rounded avatar pixmap: cached photo, or generated initials.

        The cache key includes the active theme so generated initials are
        re-rendered with the correct palette when the theme changes.
        """
        entity_id = int(entity_id or 0)
        key = (kind, entity_id, size, is_light())
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        path = self.path_for(kind, entity_id)
        if path.is_file():
            pm = QPixmap(str(path))
            if not pm.isNull():
                pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                pm = _round_pixmap(pm)
                self._pixmap_cache[key] = pm
                return pm
        pm = _initials_pixmap(name, size)
        self._pixmap_cache[key] = pm
        return pm


def _round_pixmap(source: QPixmap) -> QPixmap:
    size = min(source.width(), source.height())
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor("#FFFFFF"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setClipPath(_ellipse_path(size))
    painter.drawPixmap(0, 0, source)
    painter.end()
    return out


def _ellipse_path(size: int):
    from PySide6.QtGui import QPainterPath

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    return path


def _initials_pixmap(name: str, size: int) -> QPixmap:
    initials = "".join(part[:1].upper() for part in str(name or "SP").split()[:2]) or "SP"
    palette = _AVATAR_COLORS if is_light() else _AVATAR_COLORS_DARK
    idx = sum(ord(ch) for ch in str(name or "SP")) % len(palette)
    fg, bg = palette[idx]
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawEllipse(0, 0, size, size)
    font = QFont()
    font.setPixelSize(max(10, int(size * 0.42)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(fg))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pm