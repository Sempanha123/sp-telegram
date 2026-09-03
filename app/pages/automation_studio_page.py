from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.dialogs.drag_drop_add_dialog import DragDropAddDialog, SourceGroupCard, TargetGroupCard


class AutomationStudioPage(QWidget):
    navigateRequested = Signal(str, str)

    def __init__(self, group_controller, member_controller, parent=None):
        super().__init__(parent)
        self.setObjectName("page_automation_studio")
        self.group_controller = group_controller
        self.member_controller = member_controller
        self._sources = {}
        self._targets = {}
        self._selected_source_id = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("studio_hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 15, 18, 15)

        copy = QVBoxLayout()
        title = QLabel("Flow Studio")
        title.setObjectName("studio_title")
        subtitle = QLabel(
            "Drag a Source Group onto a Target Group. SP Telegram automatically chooses members and handles accounts, "
            "joins, permissions, member checks and safety automatically."
        )
        subtitle.setObjectName("studio_subtitle")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        hero_layout.addLayout(copy, 1)

        self.btn_refresh = QPushButton("Refresh")
        hero_layout.addWidget(self.btn_refresh)
        root.addWidget(hero)

        actions = QHBoxLayout()
        self.btn_accounts = QPushButton("Accounts")
        self.btn_members = QPushButton("Member Pool")
        self.btn_groups = QPushButton("Group Manager")
        for button in (self.btn_accounts, self.btn_members, self.btn_groups):
            button.setProperty("role", "ghost")
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

        helper = QLabel("DRAG SOURCE  →  DROP ON TARGET")
        helper.setObjectName("studio_instruction")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(helper)

        board = QHBoxLayout()
        board.setSpacing(14)

        source_panel = self._panel("SOURCE GROUPS", "Where members come from")
        self.source_host = QWidget()
        self.source_layout = QVBoxLayout(self.source_host)
        self.source_layout.setContentsMargins(0, 0, 0, 0)
        self.source_layout.setSpacing(9)
        source_scroll = QScrollArea()
        source_scroll.setWidgetResizable(True)
        source_scroll.setFrameShape(QFrame.Shape.NoFrame)
        source_scroll.setWidget(self.source_host)
        source_panel.layout().addWidget(source_scroll, 1)
        board.addWidget(source_panel, 1)

        center = QFrame()
        center.setObjectName("studio_center_lane")
        center.setFixedWidth(130)
        center_layout = QVBoxLayout(center)
        center_layout.addStretch()
        arrow = QLabel("DRAG\n→\nDROP")
        arrow.setObjectName("studio_route_arrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(arrow)
        center_layout.addStretch()
        board.addWidget(center)

        target_panel = self._panel("TARGET GROUPS", "Where members should go")
        self.target_host = QWidget()
        self.target_layout = QVBoxLayout(self.target_host)
        self.target_layout.setContentsMargins(0, 0, 0, 0)
        self.target_layout.setSpacing(9)
        target_scroll = QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setFrameShape(QFrame.Shape.NoFrame)
        target_scroll.setWidget(self.target_host)
        target_panel.layout().addWidget(target_scroll, 1)
        board.addWidget(target_panel, 1)

        root.addLayout(board, 1)

        self.lbl_status = QLabel("Tip: click Source, then Target if you do not want to drag.")
        self.lbl_status.setObjectName("studio_status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_accounts.clicked.connect(lambda: self.navigateRequested.emit("accounts", "Accounts"))
        self.btn_members.clicked.connect(lambda: self.navigateRequested.emit("members", "Member Pool"))
        self.btn_groups.clicked.connect(lambda: self.navigateRequested.emit("groups", "All Groups"))

        self.refresh()

    @staticmethod
    def _panel(title_text: str, subtitle_text: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("studio_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)
        title = QLabel(title_text)
        title.setObjectName("studio_panel_title")
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("studioMuted", True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return panel

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self):
        sources, _ = self.group_controller.get_scoped("source", 1, 100)
        targets, _ = self.group_controller.get_scoped("target", 1, 100)
        self._sources = {int(g.id): g for g in sources}
        self._targets = {int(g.id): g for g in targets}
        self._selected_source_id = None

        self._clear_layout(self.source_layout)
        if not sources:
            empty = QLabel("No Source Groups yet.\nOpen Group Manager and mark a group as Source.")
            empty.setProperty("studioEmpty", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.source_layout.addWidget(empty)
        for group in sources:
            card = SourceGroupCard(group, self.member_controller.source_stats(int(group.id)) or {})
            card.clicked.connect(self._source_clicked)
            self.source_layout.addWidget(card)
        self.source_layout.addStretch()

        self._clear_layout(self.target_layout)
        if not targets:
            empty = QLabel("No Target Groups yet.\nOpen Group Manager and mark a group as Target.")
            empty.setProperty("studioEmpty", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.target_layout.addWidget(empty)
        for group in targets:
            card = TargetGroupCard(group, self.member_controller.target_stats(int(group.id)) or {})
            card.sourceDropped.connect(self._open_flow)
            card.clicked.connect(self._target_clicked)
            self.target_layout.addWidget(card)
        self.target_layout.addStretch()

        self.lbl_status.setText(
            f"{len(sources)} Source Group(s) • {len(targets)} Target Group(s) • Drag Source → Target to begin."
        )

    def _source_clicked(self, source_id: int):
        self._selected_source_id = int(source_id)
        source = self._sources.get(int(source_id))
        if source:
            self.lbl_status.setText(f"Selected {source.title}. Now click a Target Group or drag it there.")

    def _target_clicked(self, target_id: int):
        if not self._selected_source_id:
            target = self._targets.get(int(target_id))
            if target:
                self.lbl_status.setText(f"{target.title} is a Target. Select a Source Group first.")
            return
        self._open_flow(self._selected_source_id, int(target_id))

    def _open_flow(self, source_id: int, target_id: int):
        if int(source_id) == int(target_id):
            self.lbl_status.setText("A group cannot be both Source and Target in the same transfer.")
            return
        dialog = DragDropAddDialog(
            self.group_controller,
            self.member_controller,
            source_group_id=int(source_id),
            target_group_id=int(target_id),
            parent=self,
        )
        dialog.exec()
        self.refresh()
