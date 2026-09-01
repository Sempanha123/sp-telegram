from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class AvatarLabel(QLabel):
    """A circular avatar that loads asynchronously from the AvatarService.

    Shows a generated initials avatar immediately, then swaps in the real
    profile photo when the download completes.
    """

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self._size = size
        self._service = None
        self._kind = ""
        self._entity_id = 0
        self._name = ""
        self._peer_id = None
        self._account_id = 0
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_entity(self, service, kind: str, entity_id: int, name: str, *, peer_id=None, account_id: int = 0) -> None:
        """Point this label at an entity and start loading its avatar."""
        if self._service is not None and self._service is not service:
            try:
                self._service.avatarReady.disconnect(self._on_avatar_ready)
            except (RuntimeError, TypeError):
                pass
        self._service = service
        self._kind = kind
        self._entity_id = int(entity_id or 0)
        self._name = name or ""
        self._peer_id = peer_id
        self._account_id = account_id
        if service is not None:
            service.avatarReady.connect(self._on_avatar_ready)
        self._refresh()

    def _on_avatar_ready(self, kind: str, entity_id: int) -> None:
        if kind == self._kind and entity_id == self._entity_id:
            self._refresh()

    def _refresh(self) -> None:
        if self._service is None or self._entity_id <= 0:
            self._show_initials()
            return
        pm = self._service.pixmap(self._kind, self._entity_id, self._name, self._size)
        self.setPixmap(pm)
        if not self._service.has_cached(self._kind, self._entity_id):
            self._service.request(
                self._kind,
                self._entity_id,
                peer_id=self._peer_id,
                account_id=self._account_id,
            )

    def _show_initials(self) -> None:
        from app.services.avatar_service import _initials_pixmap

        self.setPixmap(_initials_pixmap(self._name or "SP", self._size))

    def clear_entity(self) -> None:
        if self._service is not None:
            try:
                self._service.avatarReady.disconnect(self._on_avatar_ready)
            except (RuntimeError, TypeError):
                pass
        self._service = None
        self._entity_id = 0
        self.clear()