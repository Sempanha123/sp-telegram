from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.dialogs.drag_drop_add_dialog import DragDropAddDialog
from app.widgets.group_transfer_board import AddMemberTransferBoard


class AddMemberPage(QWidget):
    navigateRequested = Signal(str, str)

    def __init__(self, group_controller, member_controller, parent=None):
        super().__init__(parent)
        self.setObjectName("page_add_member")
        self.group_controller = group_controller
        self.member_controller = member_controller
        self._groups = {}
        self._dialogs = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("add_member_hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)

        copy = QVBoxLayout()
        title = QLabel("Add Member")
        title.setObjectName("add_member_title")
        subtitle = QLabel(
            "Choose a Source on the left, then drag it to a Target on the right. SP Telegram handles accounts, permissions, safety checks and Jobs automatically."
        )
        subtitle.setObjectName("add_member_subtitle")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        hero_layout.addLayout(copy, 1)

        self.btn_refresh = QPushButton("Refresh Groups")
        self.btn_refresh.setObjectName("btn_add_member_refresh")
        hero_layout.addWidget(self.btn_refresh)
        root.addWidget(hero)

        quick = QHBoxLayout()
        self.btn_groups = QPushButton("Groups")
        self.btn_accounts = QPushButton("Accounts")
        self.btn_member_pool = QPushButton("Member Pool")
        for button in (self.btn_groups, self.btn_accounts, self.btn_member_pool):
            button.setProperty("role", "ghost")
            quick.addWidget(button)
        quick.addStretch(1)
        root.addLayout(quick)

        self.board = AddMemberTransferBoard(self)
        self.board.transferRequested.connect(self._open_transfer)
        root.addWidget(self.board, 1)

        self.status = QLabel(
            "No permanent Source/Target setup is saved. Left means FROM; right means ADD TO for this job only."
        )
        self.status.setObjectName("lbl_add_member_page_status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_groups.clicked.connect(lambda: self.navigateRequested.emit("groups", "Groups"))
        self.btn_accounts.clicked.connect(lambda: self.navigateRequested.emit("accounts", "Accounts"))
        self.btn_member_pool.clicked.connect(lambda: self.navigateRequested.emit("members", "Member Pool"))

        for signal_name in ("groupCreated", "groupUpdated", "groupRemoved", "groupSyncFinished"):
            signal = getattr(self.group_controller, signal_name, None)
            if signal is not None:
                try:
                    signal.connect(lambda *_args: self.refresh())
                except (TypeError, RuntimeError):
                    pass

        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _all_groups(self):
        try:
            items, _total = self.group_controller.get_scoped(None, 1, 500)
            return list(items or [])
        except Exception:
            return list(getattr(self.group_controller, "current_items", []) or [])

    def refresh(self):
        groups = self._all_groups()
        self._groups = {int(getattr(g, "id", 0) or 0): g for g in groups if int(getattr(g, "id", 0) or 0)}

        stats = {}
        for gid in self._groups:
            try:
                stats[gid] = dict(self.member_controller.source_stats(gid) or {})
            except Exception:
                stats[gid] = {}

        self.board.set_groups(groups, stats)
        self.status.setText(
            f"{len(groups)} group(s) available. Drag FROM group → destination group. "
            "SP Telegram will choose accounts, check permissions, skip existing members and create Jobs automatically."
        )

    def _open_transfer(self, source_id: int, target_id: int):
        import logging

        log=logging.getLogger(__name__)
        source_id=int(source_id)
        target_id=int(target_id)

        if source_id==target_id:
            QMessageBox.information(self,"Add Member","Choose two different groups.")
            return

        source=self._groups.get(source_id)
        target=self._groups.get(target_id)
        if source is None or target is None:
            QMessageBox.warning(
                self,
                "Add Member",
                "One of the groups is no longer available. Refresh and try again.",
            )
            return

        try:
            stats=dict(self.member_controller.source_stats(source_id) or {})
            stored=int(stats.get("stored",0) or 0)
        except Exception:
            stored=0

        if stored<=0:
            QMessageBox.information(
                self,
                "Sync Members First",
                f"{getattr(source,'title','This group')} has no stored members yet.\n\n"
                "Open Member Pool → Sync Members, sync this group once, then return to Add Member.",
            )
            return

        source_name=str(getattr(source,"title","") or f"Group {source_id}")
        target_name=str(getattr(target,"title","") or f"Group {target_id}")
        self.status.setText(f"Preparing {source_name} → {target_name}…")

        try:
            dialog=DragDropAddDialog(
                self.group_controller,
                self.member_controller,
                target_group_id=None,
                parent=self,
            )
            dialog._source_groups=dict(self._groups)
            dialog._target_groups=dict(self._groups)
            dialog._dropped(source_id,target_id)
            dialog.setWindowTitle("Add Members - SP Telegram")
            dialog.setModal(False)
            dialog.setWindowModality(Qt.WindowModality.NonModal)

            self._dialogs.append(dialog)

            def cleanup(*_args):
                try:
                    if dialog in self._dialogs:
                        self._dialogs.remove(dialog)
                except Exception:
                    pass
                self.refresh()

            dialog.finished.connect(cleanup)
            dialog.destroyed.connect(lambda *_: cleanup())
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

            self.status.setText(
                f"Ready: {source_name} → {target_name}. "
                "You can keep using SP Telegram while Add Members runs."
            )
        except Exception as exc:
            log.exception("Add Member dialog preparation failed")
            QMessageBox.critical(
                self,
                "Add Member",
                "Could not prepare Add Members.\n\n"
                f"{exc}\n\n"
                "The full traceback was written to the local log.",
            )
            self.status.setText(
                "Add Member could not be prepared. Open Logs for the technical reason."
            )
