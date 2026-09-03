from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget


class GroupLibraryCard(QFrame):
    clicked = Signal(int)

    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.group_id = int(getattr(group, "id", 0) or 0)
        self.setObjectName("group_library_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(84)
        self.setToolTip("Click to open group information, permissions, accounts and settings.")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(4)

        title = QLabel(str(getattr(group, "title", "") or f"Group {self.group_id}"))
        title.setObjectName("lbl_group_library_title")
        root.addWidget(title)

        username = str(getattr(group, "username", "") or "").strip()
        sub = QLabel(f"@{username}" if username else "Private group")
        sub.setObjectName("lbl_group_library_username")
        root.addWidget(sub)

        count = int(getattr(group, "member_count", 0) or 0)
        status = str(getattr(group, "status", "UNKNOWN") or "UNKNOWN").replace("_", " ").title()
        meta = QLabel(f"{count:,} Telegram members   •   {status}")
        meta.setObjectName("lbl_group_library_meta")
        root.addWidget(meta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.group_id)
        super().mouseReleaseEvent(event)


class GroupBoardWidget(QFrame):
    groupClicked = Signal(int)
    roleDropped = Signal(int, str)  # compatibility only; never emitted

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("group_library_board")
        self._groups = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        bar = QFrame()
        bar.setObjectName("group_library_bar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(14, 10, 14, 10)

        copy = QVBoxLayout()
        title = QLabel("Your Groups")
        title.setObjectName("lbl_group_library_heading")
        hint = QLabel(
            "Groups is your library and settings area. Click a group to open information, permissions and accounts. "
            "Use Add Member when you want to move members between groups."
        )
        hint.setObjectName("lbl_group_library_hint")
        hint.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(hint)
        bar_layout.addLayout(copy, 1)

        self.search = QLineEdit()
        self.search.setObjectName("le_group_library_search")
        self.search.setPlaceholderText("Search groups…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(250)
        self.search.textChanged.connect(self._render)
        bar_layout.addWidget(self.search)
        root.addWidget(bar)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll_group_library")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        host = QWidget()
        self.cards_layout = QVBoxLayout(host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, 1)

    def set_groups(self, groups):
        self._groups = list(groups or [])
        self._render()

    def _render(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        query = self.search.text().strip().lower()
        visible = []
        for group in self._groups:
            title = str(getattr(group, "title", "") or "")
            username = str(getattr(group, "username", "") or "")
            if query and query not in title.lower() and query not in username.lower():
                continue
            visible.append(group)

        if not visible:
            empty = QLabel("No groups found.")
            empty.setObjectName("lbl_group_library_empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(120)
            self.cards_layout.insertWidget(0, empty)
            return

        for group in visible:
            card = GroupLibraryCard(group, self)
            card.clicked.connect(self.groupClicked)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
