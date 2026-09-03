from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

MIME_SOURCE_GROUP = "application/x-sptelegram-add-member-source"


def _repolish(widget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class SourceCard(QFrame):
    clicked = Signal(int)

    def __init__(self, group, stored_members: int = 0, parent=None):
        super().__init__(parent)
        self.group_id = int(getattr(group, "id", 0) or 0)
        self._press_pos = QPoint()
        self._dragging = False

        self.setObjectName("add_member_source_card")
        self.setProperty("selectedSource", False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("Drag this Source Group to a Target Group on the right.")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel(str(getattr(group, "title", "") or f"Group {self.group_id}"))
        title.setObjectName("lbl_add_member_group_title")
        top.addWidget(title, 1)
        badge = QLabel("SOURCE")
        badge.setObjectName("lbl_add_member_source_badge")
        top.addWidget(badge)
        root.addLayout(top)

        username = str(getattr(group, "username", "") or "").strip()
        sub = QLabel(f"@{username}" if username else "Private group")
        sub.setObjectName("lbl_add_member_group_username")
        root.addWidget(sub)

        stored = max(0, int(stored_members or 0))
        telegram_count = int(getattr(group, "member_count", 0) or 0)
        meta = QLabel(
            f"{stored:,} stored members   •   Telegram: {telegram_count:,}"
            if stored
            else f"No stored members yet   •   Telegram: {telegram_count:,}"
        )
        meta.setObjectName("lbl_add_member_group_meta")
        root.addWidget(meta)

    def set_selected(self, selected: bool):
        self.setProperty("selectedSource", bool(selected))
        _repolish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        self._dragging = True
        mime = QMimeData()
        mime.setData(MIME_SOURCE_GROUP, QByteArray(str(self.group_id).encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._dragging
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self.group_id)
        self._dragging = False
        super().mouseReleaseEvent(event)


class TargetCard(QFrame):
    clicked = Signal(int)
    sourceDropped = Signal(int, int)

    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.group_id = int(getattr(group, "id", 0) or 0)

        self.setObjectName("add_member_target_card")
        self.setProperty("dropActive", False)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("Drop a Source Group here to add members into this group.")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel(str(getattr(group, "title", "") or f"Group {self.group_id}"))
        title.setObjectName("lbl_add_member_group_title")
        top.addWidget(title, 1)
        badge = QLabel("DROP HERE")
        badge.setObjectName("lbl_add_member_target_badge")
        top.addWidget(badge)
        root.addLayout(top)

        username = str(getattr(group, "username", "") or "").strip()
        sub = QLabel(f"@{username}" if username else "Private group")
        sub.setObjectName("lbl_add_member_group_username")
        root.addWidget(sub)

        telegram_count = int(getattr(group, "member_count", 0) or 0)
        meta = QLabel(f"Destination   •   Telegram: {telegram_count:,}")
        meta.setObjectName("lbl_add_member_group_meta")
        root.addWidget(meta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.group_id)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat(MIME_SOURCE_GROUP):
            event.ignore()
            return
        try:
            source_id = int(bytes(event.mimeData().data(MIME_SOURCE_GROUP)).decode("utf-8"))
        except Exception:
            event.ignore()
            return
        if source_id == self.group_id:
            event.ignore()
            return
        self.setProperty("dropActive", True)
        _repolish(self)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setProperty("dropActive", False)
        _repolish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dropActive", False)
        _repolish(self)
        try:
            source_id = int(bytes(event.mimeData().data(MIME_SOURCE_GROUP)).decode("utf-8"))
        except Exception:
            event.ignore()
            return
        if source_id == self.group_id:
            event.ignore()
            return
        event.acceptProposedAction()
        self.sourceDropped.emit(source_id, self.group_id)


class _Column(QFrame):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("add_member_column")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        title_label = QLabel(title)
        title_label.setObjectName("lbl_add_member_column_title")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("lbl_add_member_column_subtitle")
        subtitle_label.setWordWrap(True)
        root.addWidget(title_label)
        root.addWidget(subtitle_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.cards = QVBoxLayout(self.host)
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(7)
        self.cards.addStretch(1)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)


class AddMemberTransferBoard(QFrame):
    transferRequested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("add_member_transfer_board")
        self._groups = []
        self._stats = {}
        self._source_cards = {}
        self._selected_source_id = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QFrame()
        toolbar.setObjectName("add_member_board_bar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 9, 14, 9)

        guide = QLabel("1  Choose Source  →  2  Drag Left to Right  →  3  Drop on Target")
        guide.setObjectName("lbl_add_member_board_title")
        toolbar_layout.addWidget(guide, 1)

        self.search = QLineEdit()
        self.search.setObjectName("le_add_member_group_search")
        self.search.setPlaceholderText("Search groups…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(250)
        self.search.textChanged.connect(self._render)
        toolbar_layout.addWidget(self.search)
        root.addWidget(toolbar)

        self.selection = QLabel(
            "Source = where members come from. Target = where members will be added."
        )
        self.selection.setObjectName("lbl_add_member_selection")
        root.addWidget(self.selection)

        board = QHBoxLayout()
        board.setSpacing(12)

        self.source_col = _Column(
            "SOURCE GROUP",
            "Drag a group from this side. It must already have stored/synced members.",
            self,
        )
        board.addWidget(self.source_col, 1)

        arrow = QFrame()
        arrow.setObjectName("add_member_arrow_lane")
        arrow.setFixedWidth(110)
        arrow_layout = QVBoxLayout(arrow)
        arrow_layout.addStretch(1)
        arrow_label = QLabel("DRAG\n→\nDROP")
        arrow_label.setObjectName("lbl_add_member_arrow")
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_layout.addWidget(arrow_label)
        arrow_layout.addStretch(1)
        board.addWidget(arrow)

        self.target_col = _Column(
            "TARGET GROUP",
            "Drop the Source on a destination group. No permanent Source/Target setup is saved.",
            self,
        )
        board.addWidget(self.target_col, 1)

        root.addLayout(board, 1)

    @staticmethod
    def _clear(layout):
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_groups(self, groups, stats_by_id=None) -> None:
        self._groups = list(groups or [])
        self._stats = dict(stats_by_id or {})
        self._render()

    def _render(self):
        self._clear(self.source_col.cards)
        self._clear(self.target_col.cards)
        self._source_cards.clear()

        query = self.search.text().strip().lower()
        groups = []
        for group in self._groups:
            title = str(getattr(group, "title", "") or "")
            username = str(getattr(group, "username", "") or "")
            if query and query not in title.lower() and query not in username.lower():
                continue
            groups.append(group)

        for group in groups:
            gid = int(getattr(group, "id", 0) or 0)
            stored = int((self._stats.get(gid) or {}).get("stored", 0) or 0)

            source = SourceCard(group, stored, self)
            source.clicked.connect(self._source_clicked)
            source.set_selected(gid == self._selected_source_id)
            self._source_cards[gid] = source
            self.source_col.cards.insertWidget(self.source_col.cards.count() - 1, source)

            target = TargetCard(group, self)
            target.clicked.connect(self._target_clicked)
            target.sourceDropped.connect(self.transferRequested)
            self.target_col.cards.insertWidget(self.target_col.cards.count() - 1, target)

    def _source_clicked(self, group_id: int):
        group_id = int(group_id)
        if self._selected_source_id and self._selected_source_id in self._source_cards:
            self._source_cards[self._selected_source_id].set_selected(False)
        self._selected_source_id = group_id
        if group_id in self._source_cards:
            self._source_cards[group_id].set_selected(True)

        group = next(
            (g for g in self._groups if int(getattr(g, "id", 0) or 0) == group_id),
            None,
        )
        name = str(getattr(group, "title", "") or f"Group {group_id}")
        self.selection.setText(
            f"FROM: {name}  →  now click a Target on the right, or drag this Source card onto it."
        )

    def _target_clicked(self, target_id: int):
        if not self._selected_source_id:
            self.selection.setText("Choose a Source Group on the left first.")
            return
        if int(target_id) == int(self._selected_source_id):
            self.selection.setText("Source and Target must be different groups.")
            return
        source_id = self._selected_source_id
        if source_id in self._source_cards:
            self._source_cards[source_id].set_selected(False)
        self._selected_source_id = 0
        self.selection.setText("Preparing Add Members…")
        self.transferRequested.emit(int(source_id), int(target_id))
