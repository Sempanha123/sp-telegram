from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem


class AvatarDelegate(QStyledItemDelegate):
    """Renders a rounded avatar before the cell text in an identity column.

    The delegate reads the underlying entity from ``Qt.ItemDataRole.UserRole``, draws a
    cached/generated avatar pixmap (never blocking the GUI), and requests
    async downloads for missing photos.  When ``avatarReady`` fires the owning
    table repaints only the affected rows.

    ``peer_id_attr`` / ``account_id_attr`` name entity attributes that carry the
    Telegram peer id (e.g. ``telegram_user_id`` / ``telegram_group_id``) and the
    local account id used to authorize the photo download.  Passing them lets
    the service fetch the *real* profile photo instead of only initials.
    """

    AVATAR_SIZE = 30
    GAP = 9
    H_PADDING = 8

    def __init__(self, avatar_service, kind: str, id_attr: str = "id",
                 name_attr: str = "first_name", parent=None,
                 peer_id_attr: str | None = None, account_id_attr: str | None = None):
        super().__init__(parent)
        self.avatar_service = avatar_service
        self.kind = kind
        self.id_attr = id_attr
        self.name_attr = name_attr
        self.peer_id_attr = peer_id_attr
        self.account_id_attr = account_id_attr
        self._requested: set[int] = set()
        if avatar_service is not None:
            avatar_service.avatarReady.connect(self._on_avatar_ready)

    def _entity(self, index) -> Any:
        return index.data(Qt.ItemDataRole.UserRole)

    def _entity_id(self, index) -> int:
        entity = self._entity(index)
        if entity is None:
            return 0
        if isinstance(entity, dict):
            return int(entity.get(self.id_attr) or 0)
        return int(getattr(entity, self.id_attr, 0) or 0)

    def _entity_name(self, index) -> str:
        entity = self._entity(index)
        if entity is None:
            return ""
        if isinstance(entity, dict):
            return str(entity.get(self.name_attr) or entity.get("title") or entity.get("username") or "")
        return str(getattr(entity, self.name_attr, "") or getattr(entity, "title", "") or getattr(entity, "username", "") or "")

    def _entity_peer_id(self, index) -> int | None:
        """Telegram peer id used to download the real profile photo."""
        entity = self._entity(index)
        if entity is None or not self.peer_id_attr:
            return None
        if isinstance(entity, dict):
            value = entity.get(self.peer_id_attr)
        else:
            value = getattr(entity, self.peer_id_attr, None)
        try:
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    def _entity_account_id(self, index) -> int:
        """Local account id that authorizes the photo download."""
        entity = self._entity(index)
        if entity is None or not self.account_id_attr:
            return 0
        if isinstance(entity, dict):
            value = entity.get(self.account_id_attr)
        else:
            value = getattr(entity, self.account_id_attr, 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _on_avatar_ready(self, kind: str, entity_id: int) -> None:
        if kind != self.kind:
            return
        view = self.parent()
        if view is None:
            return
        # Repaint only rows whose entity id matches the freshly downloaded photo.
        model = view.model()
        if model is None:
            return
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            if self._entity_id(idx) == entity_id:
                view.viewport().update(view.visualRect(idx))
                break

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        base = super().sizeHint(option, index)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        width = option.fontMetrics.horizontalAdvance(text) + self.AVATAR_SIZE + self.GAP + self.H_PADDING * 2
        height = max(base.height(), self.AVATAR_SIZE + 8)
        return QSize(max(base.width(), width), height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        entity_id = self._entity_id(index)
        if entity_id and self.avatar_service is not None:
            name = self._entity_name(index)
            pm = self.avatar_service.pixmap(self.kind, entity_id, name, self.AVATAR_SIZE)
            if not pm.isNull():
                rect = QRect(
                    option.rect.x() + self.H_PADDING,
                    option.rect.y() + (option.rect.height() - self.AVATAR_SIZE) // 2,
                    self.AVATAR_SIZE, self.AVATAR_SIZE,
                )
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.drawPixmap(rect, pm)
                painter.restore()
            if entity_id not in self._requested:
                self._requested.add(entity_id)
                self.avatar_service.request(
                    self.kind,
                    entity_id,
                    peer_id=self._entity_peer_id(index),
                    account_id=self._entity_account_id(index),
                )

        text_rect = option.rect.adjusted(
            self.H_PADDING + self.AVATAR_SIZE + self.GAP, 0, -self.H_PADDING, 0
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if option.state & QStyle.StateFlag.State_Selected:
            color = option.palette.color(QPalette.ColorRole.HighlightedText)
        else:
            color = option.palette.text().color()
        painter.setPen(color)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )
        painter.restore()