from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)

from app.dialogs.invite_members_to_target_dialog import InvitationResultsDialog
from app.widgets.add_member_live_activity import AddMemberLiveActivity

MIME_SOURCE_GROUP = "application/x-sptelegram-source-group"


def _human(value, empty="—") -> str:
    text = str(value or "").strip()
    return text.replace("_", " ").title() if text else empty


def _repolish(widget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class SourceGroupCard(QFrame):
    clicked = Signal(int)

    def __init__(self, group, stats: dict, parent=None):
        super().__init__(parent)
        self.group = group
        self.group_id = int(group.id)
        self._press_pos = QPoint()
        self.setObjectName("drag_source_group_card")
        self.setProperty("sourceCard", True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag this Source Group onto a Target Group")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        badge = QLabel("SOURCE")
        badge.setProperty("flowBadge", "source")
        top.addWidget(badge)
        top.addStretch()
        layout.addLayout(top)

        title = QLabel(str(group.title or f"Group {group.id}"))
        title.setProperty("flowCardTitle", True)
        layout.addWidget(title)

        username = f"@{group.username}" if getattr(group, "username", None) else "Private group"
        sub = QLabel(username)
        sub.setProperty("flowMuted", True)
        layout.addWidget(sub)

        stored = int((stats or {}).get("stored", 0) or 0)
        sync_status = _human((stats or {}).get("status"), "Never Synced")
        meta = QLabel(f"{stored:,} stored members  •  {sync_status}")
        meta.setProperty("flowCardMeta", True)
        layout.addWidget(meta)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.group_id)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        mime = QMimeData()
        mime.setData(MIME_SOURCE_GROUP, QByteArray(str(self.group_id).encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class TargetGroupCard(QFrame):
    sourceDropped = Signal(int, int)
    clicked = Signal(int)

    def __init__(self, group, stats: dict, parent=None):
        super().__init__(parent)
        self.group = group
        self.group_id = int(group.id)
        self.setObjectName("drop_target_group_card")
        self.setProperty("targetCard", True)
        self.setProperty("dropActive", False)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Drop a Source Group here")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        badge = QLabel("TARGET")
        badge.setProperty("flowBadge", "target")
        hint = QLabel("DROP HERE")
        hint.setProperty("dropHint", True)
        top.addWidget(badge)
        top.addStretch()
        top.addWidget(hint)
        layout.addLayout(top)

        title = QLabel(str(group.title or f"Group {group.id}"))
        title.setProperty("flowCardTitle", True)
        layout.addWidget(title)

        username = f"@{group.username}" if getattr(group, "username", None) else "Private group"
        sub = QLabel(username)
        sub.setProperty("flowMuted", True)
        layout.addWidget(sub)

        existing = int((stats or {}).get("existing", 0) or 0)
        unknown = int((stats or {}).get("unknown", 0) or 0)
        meta = QLabel(f"{existing:,} known existing  •  {unknown:,} unknown")
        meta.setProperty("flowCardMeta", True)
        layout.addWidget(meta)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.group_id)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_SOURCE_GROUP):
            event.acceptProposedAction()
            self.setProperty("dropActive", True)
            _repolish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dropActive", False)
        _repolish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dropActive", False)
        _repolish(self)
        if not event.mimeData().hasFormat(MIME_SOURCE_GROUP):
            event.ignore()
            return
        try:
            source_id = int(bytes(event.mimeData().data(MIME_SOURCE_GROUP)).decode("utf-8"))
        except (TypeError, ValueError):
            event.ignore()
            return
        event.acceptProposedAction()
        self.sourceDropped.emit(source_id, self.group_id)


class DragDropAddDialog(QDialog):
    MAX_QUICK_MEMBERS = 100
    MAX_ACCOUNTS = 5

    def __init__(self, group_controller, member_controller, *, source_group_id=None, target_group_id=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("dlg_drag_drop_add")
        self.setWindowTitle("Quick Add Members - SP Telegram")
        self.setMinimumSize(940, 660)
        self.resize(1060, 740)

        self.group_controller = group_controller
        self.member_controller = member_controller
        self.initial_source_id = int(source_group_id) if source_group_id else None
        self.initial_target_id = int(target_group_id) if target_group_id else None
        self._source_groups = {}
        self._target_groups = {}
        self._selected_source_id = None
        self._selected_target_id = None
        self._member_ids = []
        self._account_ids = []
        self._precheck = None
        self._auto_account_retry = False
        self._last_result = None
        self._running = False
        self._closed = False
        self._generation = 0
        self._connections = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(13)

        hero = QFrame()
        hero.setObjectName("quick_transfer_hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_text = QVBoxLayout()
        title = QLabel("Quick Add")
        title.setObjectName("quick_transfer_title")
        subtitle = QLabel(
            "Drag a Source Group onto a Target Group. SP Telegram handles the technical checks automatically."
        )
        subtitle.setObjectName("quick_transfer_subtitle")
        subtitle.setWordWrap(True)
        hero_text.addWidget(title)
        hero_text.addWidget(subtitle)
        hero_layout.addLayout(hero_text, 1)
        self.btn_refresh = QPushButton("Refresh Groups")
        self.btn_refresh.setObjectName("btn_quick_transfer_refresh")
        hero_layout.addWidget(self.btn_refresh)
        root.addWidget(hero)

        self.stack = QStackedWidget()
        self.stack.setObjectName("stack_quick_transfer")
        root.addWidget(self.stack, 1)
        self._build_board()
        self._build_transfer()

        footer = QHBoxLayout()
        note = QLabel("Telegram privacy, permissions and account safety limits are always respected.")
        note.setProperty("flowMuted", True)
        self.btn_close = QPushButton("Close")
        footer.addWidget(note)
        footer.addStretch()
        footer.addWidget(self.btn_close)
        root.addLayout(footer)

        self.btn_refresh.clicked.connect(self.refresh_groups)
        self.btn_close.clicked.connect(self._close_or_background_v4)
        self.btn_back.clicked.connect(self._back_to_board)
        self.btn_check.clicked.connect(self._primary_clicked)
        self.btn_results.clicked.connect(self._show_results)
        self.spin_amount.valueChanged.connect(self._amount_changed)
        self.btn_advanced.toggled.connect(self._toggle_advanced)
        self.live_activity.backgroundRequested.connect(self._background_job_v4)
        self.live_activity.jobsRequested.connect(self._open_jobs_v4)
        self.btn_background.clicked.connect(self._background_job)
        self.btn_jobs_live.clicked.connect(self._open_jobs_live)

        self._connect(self.member_controller.targetInvitationProgress, self._progress)
        self._connect(self.member_controller.targetInvitationCompleted, self._completed)
        self._connect(self.member_controller.targetInvitationFailed, self._failed)

        self.refresh_groups()
        self._register_live_dialog_v4()
        self._register_live_dialog()
        if self.initial_source_id and self.initial_target_id:
            QTimer.singleShot(0, lambda: self._dropped(self.initial_source_id, self.initial_target_id))

    def _live_manager(self):
        parent=self.parentWidget()
        while parent is not None:
            manager=getattr(parent,"_live_job_ux",None)
            if manager is not None:
                return manager
            parent=parent.parentWidget()
        return None

    def _register_live_dialog(self):
        manager=self._live_manager()
        if manager is not None:
            try:
                manager.register_dialog(self)
            except Exception:
                pass

    def _close_clicked(self):
        if self._running:
            self._background_job()
        else:
            self.reject()

    def closeEvent(self,event):
        if self._running:
            self._background_job()
            event.ignore()
            return
        super().closeEvent(event)

    def _background_job(self):
        if not self._running:
            self.showMinimized()
            return
        self.hide()
        manager=self._live_manager()
        if manager is not None:
            try:
                manager.window.toast_requested.emit(
                    "Add Members is still running. Click the running Add chip at the top to open it again.",
                    "Info",
                )
            except Exception:
                pass

    def _open_jobs_live(self):
        manager=self._live_manager()
        if manager is not None:
            manager.open_jobs()

    def _account_display_name(self,account_id:int):
        account_id=int(account_id or 0)
        if not account_id:
            return "Automatic account"
        try:
            row=list(self._account_ids).index(account_id)
        except Exception:
            row=-1
        if 0<=row<self.table_accounts.rowCount():
            try:
                item=self.table_accounts.item(row,0)
                if item and item.text().strip():
                    return item.text().strip()
            except Exception:
                pass
        return f"Account {account_id}"

    def _start_live_activity(self):
        self.live_frame.show()
        self.btn_background.setEnabled(True)
        self.live_pulse_timer.start()
        self.live_member.setText("◐  Preparing first member…")
        self.live_account.setText("Automatic accounts are starting")
        self.live_feed_events=[]
        self.live_feed.setText(
            "You can minimize this window. The job keeps running and can be reopened from the top Add chip."
        )
        self.btn_close.setText("Background")
        self._live_counts={"successful":0,"skipped":0,"failed":0}
        self._live_account_done={}

    def _update_live_activity(self,payload):
        if not self._running:
            return

        self._live_pulse_index=(self._live_pulse_index+1)%4
        self.live_pulse.setText(("◐","◓","◑","◒")[self._live_pulse_index])

        current=str(
            payload.get("current")
            or payload.get("member_name")
            or payload.get("member")
            or payload.get("username")
            or "Preparing…"
        )
        account_id=int(payload.get("account_id") or 0)
        account_name=self._account_display_name(account_id)

        successful=int(payload.get("successful",0) or 0)
        skipped=int(payload.get("skipped",0) or 0)
        failed=int(payload.get("failed",0) or 0)
        old=dict(self._live_counts)

        if successful>old.get("successful",0):
            icon,outcome="✓","Added"
        elif failed>old.get("failed",0):
            icon,outcome="×","Failed"
        elif skipped>old.get("skipped",0):
            icon,outcome="↷","Skipped"
        elif str(payload.get("status") or "").upper()=="WAITING":
            icon,outcome="⏱","Waiting"
        else:
            icon,outcome="◓","Adding"

        self._live_counts={"successful":successful,"skipped":skipped,"failed":failed}
        self.live_member.setText(f"{icon}  {outcome}: {current}")
        self.live_account.setText(f"via {account_name}")

        if current and current!="Preparing…":
            event=f"{icon} {current}  •  {account_name}"
            if not self.live_feed_events or self.live_feed_events[-1]!=event:
                self.live_feed_events.append(event)
                self.live_feed_events=self.live_feed_events[-5:]
            self.live_feed.setText("    ".join(self.live_feed_events))

        if account_id:
            try:
                row=list(self._account_ids).index(account_id)
            except Exception:
                row=-1
            if 0<=row<self.table_accounts.rowCount():
                status_item=self.table_accounts.item(row,1)
                assigned_item=self.table_accounts.item(row,2)
                if status_item is not None:
                    status_item.setText(f"{icon} {outcome} • {current}")
                if outcome in {"Added","Failed","Skipped"}:
                    self._live_account_done[account_id]=int(self._live_account_done.get(account_id,0))+1
                if assigned_item is not None:
                    text=assigned_item.text().strip()
                    planned=0
                    if "/" in text:
                        text=text.split("/")[-1]
                    try:
                        planned=int(text)
                    except Exception:
                        planned=0
                    done=int(self._live_account_done.get(account_id,0))
                    assigned_item.setText(f"{done}/{planned}" if planned else str(done))

    def _finish_live_activity(self,result=None,error_message=""):
        self.live_pulse_timer.stop()
        self.btn_background.setEnabled(False)
        self.btn_close.setText("Close")

        if error_message:
            self.live_pulse.setText("×")
            self.live_member.setText(str(error_message))
            self.live_account.setText("Open Jobs for details")
            return

        result=dict(result or {})
        successful=int(result.get("successful",0) or 0)
        skipped=int(result.get("skipped",0) or 0)
        failed=int(result.get("failed",0) or 0)
        self.live_pulse.setText("✓" if not failed else "!")
        self.live_member.setText(
            f"Complete • {successful:,} added • {skipped:,} skipped • {failed:,} failed"
        )
        self.live_account.setText("Saved in Jobs")

    def _pulse_live(self):
        if not self._running:
            return
        self._live_pulse_index=(self._live_pulse_index+1)%4
        self.live_pulse.setText(("◐","◓","◑","◒")[self._live_pulse_index])

    def _live_manager_v4(self):
        parent=self.parentWidget()
        while parent is not None:
            manager=getattr(parent,"_live_job_ux",None)
            if manager is not None:
                return manager
            parent=parent.parentWidget()
        return None

    def _register_live_dialog_v4(self):
        manager=self._live_manager_v4()
        if manager is not None:
            try:
                manager.register_dialog(self)
            except Exception:
                pass

    def _background_job_v4(self):
        if not self._running:
            self.showMinimized()
            return
        self.hide()
        manager=self._live_manager_v4()
        if manager is not None:
            try:
                manager.window.toast_requested.emit(
                    "Add Members is still running. Click the Add x/y chip in the top bar to open it again.",
                    "Info",
                )
            except Exception:
                pass

    def _open_jobs_v4(self):
        manager=self._live_manager_v4()
        if manager is not None:
            manager.open_jobs()

    def _close_or_background_v4(self):
        if self._running:
            self._background_job_v4()
        else:
            self.reject()

    def closeEvent(self,event):
        if self._running:
            self._background_job_v4()
            event.ignore()
            return
        super().closeEvent(event)

    def _live_accounts_v4(self):
        accounts=[]
        for row,account_id in enumerate(list(self._account_ids or [])):
            name=f"Account {int(account_id)}"
            assigned=0
            try:
                item=self.table_accounts.item(row,0)
                if item and item.text().strip():
                    name=item.text().strip()
            except Exception:
                pass
            try:
                item=self.table_accounts.item(row,2)
                if item:
                    assigned=int(str(item.text()).split("/")[-1])
            except Exception:
                assigned=0
            accounts.append({
                "account_id":int(account_id),
                "name":name,
                "assigned":assigned,
            })
        return accounts

    def _connect(self, signal, slot):
        try:
            signal.connect(slot)
            self._connections.append((signal, slot))
        except (TypeError, RuntimeError):
            pass

    def done(self, result):
        self._closed = True
        self._generation += 1
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections.clear()
        super().done(result)

    def _build_board(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        instruction = QLabel("1  Pick up a Source    →    2  Drop it on a Target    →    3  Add Members")
        instruction.setObjectName("quick_transfer_instruction")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instruction)

        columns = QHBoxLayout()
        columns.setSpacing(14)

        source_panel = self._panel("SOURCE GROUPS", "Drag from here")
        self.source_host = QWidget()
        self.source_layout = QVBoxLayout(self.source_host)
        self.source_layout.setContentsMargins(0, 0, 0, 0)
        self.source_layout.setSpacing(8)
        source_scroll = QScrollArea()
        source_scroll.setObjectName("scroll_quick_sources")
        source_scroll.setWidgetResizable(True)
        source_scroll.setFrameShape(QFrame.Shape.NoFrame)
        source_scroll.setWidget(self.source_host)
        source_panel.layout().addWidget(source_scroll, 1)
        columns.addWidget(source_panel, 1)

        center = QFrame()
        center.setObjectName("quick_transfer_center")
        center.setFixedWidth(120)
        center_layout = QVBoxLayout(center)
        center_layout.addStretch()
        arrow = QLabel("DRAG\n→\nDROP")
        arrow.setObjectName("quick_transfer_arrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(arrow)
        center_layout.addStretch()
        columns.addWidget(center)

        target_panel = self._panel("TARGET GROUPS", "Drop here")
        self.target_host = QWidget()
        self.target_layout = QVBoxLayout(self.target_host)
        self.target_layout.setContentsMargins(0, 0, 0, 0)
        self.target_layout.setSpacing(8)
        target_scroll = QScrollArea()
        target_scroll.setObjectName("scroll_quick_targets")
        target_scroll.setWidgetResizable(True)
        target_scroll.setFrameShape(QFrame.Shape.NoFrame)
        target_scroll.setWidget(self.target_host)
        target_panel.layout().addWidget(target_scroll, 1)
        columns.addWidget(target_panel, 1)

        layout.addLayout(columns, 1)
        self.stack.addWidget(page)

    @staticmethod
    def _panel(title_text: str, subtitle_text: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("quick_transfer_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("quick_transfer_panel_title")
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("flowMuted", True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return panel

    def _build_transfer(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        route = QFrame()
        route.setObjectName("quick_transfer_route")
        route_layout = QHBoxLayout(route)
        route_layout.setContentsMargins(16, 13, 16, 13)
        self.lbl_route_source = QLabel("Source")
        self.lbl_route_source.setObjectName("quick_route_source")
        arrow = QLabel("→")
        arrow.setObjectName("quick_route_arrow")
        self.lbl_route_target = QLabel("Target")
        self.lbl_route_target.setObjectName("quick_route_target")
        route_layout.addWidget(self.lbl_route_source, 1)
        route_layout.addWidget(arrow)
        route_layout.addWidget(self.lbl_route_target, 1)
        layout.addWidget(route)

        amount_row = QHBoxLayout()
        amount_text = QVBoxLayout()
        amount_title = QLabel("How many members?")
        amount_title.setObjectName("quick_transfer_section_title")
        amount_hint = QLabel("Quick Add handles up to 100 members per drop.")
        amount_hint.setProperty("flowMuted", True)
        amount_text.addWidget(amount_title)
        amount_text.addWidget(amount_hint)
        amount_row.addLayout(amount_text, 1)
        self.spin_amount = QSpinBox()
        self.spin_amount.setObjectName("spin_quick_transfer_amount")
        self.spin_amount.setRange(1, self.MAX_QUICK_MEMBERS)
        self.spin_amount.setValue(20)
        self.spin_amount.setMinimumWidth(130)
        self.spin_amount.setMinimumHeight(38)
        amount_row.addWidget(self.spin_amount)
        layout.addLayout(amount_row)

        metrics = QGridLayout()
        metrics.setSpacing(9)
        self.metric_found = self._metric("Found", 0)
        self.metric_ready = self._metric("Ready", 0)
        self.metric_existing = self._metric("Already There", 0)
        self.metric_attention = self._metric("Needs Attention", 0)
        metrics.addWidget(self.metric_found, 0, 0)
        metrics.addWidget(self.metric_ready, 0, 1)
        metrics.addWidget(self.metric_existing, 0, 2)
        metrics.addWidget(self.metric_attention, 0, 3)
        layout.addLayout(metrics)

        accounts_title = QLabel("Automatic Accounts")
        accounts_title.setObjectName("quick_transfer_section_title")
        layout.addWidget(accounts_title)

        self.table_accounts = QTableWidget(0, 3)
        self.table_accounts.setObjectName("tbl_quick_transfer_accounts")
        self.table_accounts.setHorizontalHeaderLabels(["Account", "Status", "Assigned"])
        self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_accounts.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_accounts.setMaximumHeight(190)
        h = self.table_accounts.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table_accounts)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_quick_transfer")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("Preparing…")
        self.lbl_status.setObjectName("quick_transfer_status")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        self.live_activity = AddMemberLiveActivity(self)
        self.live_activity.hide()
        layout.addWidget(self.live_activity)
        self.live_frame = QFrame()
        self.live_frame.setObjectName("quick_live_activity")
        self.live_frame.hide()
        live_grid = QGridLayout(self.live_frame)
        live_grid.setContentsMargins(12, 9, 12, 9)
        live_grid.setHorizontalSpacing(10)
        live_grid.setVerticalSpacing(2)

        self.live_pulse = QLabel("◐")
        self.live_pulse.setObjectName("lbl_quick_live_pulse")
        self.live_pulse.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_pulse.setFixedWidth(28)

        self.live_title = QLabel("Live add activity")
        self.live_title.setObjectName("lbl_quick_live_title")
        self.live_member = QLabel("Waiting for the first member…")
        self.live_member.setObjectName("lbl_quick_live_member")
        self.live_member.setWordWrap(True)
        self.live_account = QLabel("Automatic account")
        self.live_account.setObjectName("lbl_quick_live_account")
        self.live_feed = QLabel("")
        self.live_feed.setObjectName("lbl_quick_live_feed")
        self.live_feed.setWordWrap(True)

        self.btn_background = QPushButton("↘  Minimize to Running Jobs")
        self.btn_background.setObjectName("btn_quick_background")
        self.btn_background.setEnabled(False)
        self.btn_background.setToolTip(
            "Hide this window while the job keeps running. Click the top Add chip to open it again."
        )
        self.btn_jobs_live = QPushButton("Open Jobs")
        self.btn_jobs_live.setObjectName("btn_quick_jobs")

        live_buttons = QVBoxLayout()
        live_buttons.setSpacing(6)
        live_buttons.addWidget(self.btn_background)
        live_buttons.addWidget(self.btn_jobs_live)

        live_grid.addWidget(self.live_pulse, 0, 0, 2, 1)
        live_grid.addWidget(self.live_title, 0, 1)
        live_grid.addWidget(self.live_member, 1, 1)
        live_grid.addWidget(self.live_account, 0, 2)
        live_grid.addLayout(live_buttons, 0, 3, 2, 1)
        live_grid.addWidget(self.live_feed, 2, 1, 1, 3)
        layout.addWidget(self.live_frame)

        self._live_pulse_index = 0
        self._live_counts = {"successful":0,"skipped":0,"failed":0}
        self._live_account_done = {}
        self.live_feed_events = []
        self.live_pulse_timer = QTimer(self)
        self.live_pulse_timer.setInterval(160)
        self.live_pulse_timer.timeout.connect(self._pulse_live)

        self.btn_advanced = QToolButton()
        self.btn_advanced.setText("Advanced details")
        self.btn_advanced.setObjectName("btn_quick_transfer_advanced")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.btn_advanced, 0, Qt.AlignmentFlag.AlignLeft)

        self.txt_advanced = QPlainTextEdit()
        self.txt_advanced.setObjectName("txt_quick_transfer_advanced")
        self.txt_advanced.setReadOnly(True)
        self.txt_advanced.setMaximumHeight(115)
        self.txt_advanced.hide()
        layout.addWidget(self.txt_advanced)

        actions = QHBoxLayout()
        self.btn_back = QPushButton("← Back")
        self.btn_results = QPushButton("View Results")
        self.btn_results.setEnabled(False)
        self.btn_check = QPushButton("Check & Continue")
        self.btn_check.setObjectName("btn_quick_transfer_primary")
        self.btn_check.setProperty("primary", True)
        actions.addWidget(self.btn_back)
        actions.addWidget(self.btn_results)
        actions.addStretch()
        actions.addWidget(self.btn_check)
        layout.addLayout(actions)

        self.stack.addWidget(page)

    @staticmethod
    def _metric(title_text: str, value: int) -> QFrame:
        frame = QFrame()
        frame.setProperty("flowMetric", True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(1)
        title = QLabel(title_text)
        title.setProperty("metricCaption", True)
        number = QLabel(str(int(value)))
        number.setProperty("metricValue", True)
        frame._number = number
        layout.addWidget(title)
        layout.addWidget(number)
        return frame

    @staticmethod
    def _set_metric(frame, value: int):
        frame._number.setText(f"{max(0, int(value)):,}")

    @staticmethod
    def _item(text="—"):
        item = QTableWidgetItem(str(text))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return item

    def _clear_cards(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh_groups(self):
        sources, _ = self.group_controller.get_scoped("source", 1, 100)
        targets, _ = self.group_controller.get_scoped("target", 1, 100)
        self._source_groups = {int(g.id): g for g in sources}
        self._target_groups = {int(g.id): g for g in targets}

        self._clear_cards(self.source_layout)
        if not sources:
            empty = QLabel("No Source Groups yet.\nClassify a group as Source first.")
            empty.setProperty("flowEmpty", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.source_layout.addWidget(empty)
        for group in sources:
            card = SourceGroupCard(group, self.member_controller.source_stats(int(group.id)) or {})
            card.clicked.connect(self._select_source)
            self.source_layout.addWidget(card)
        self.source_layout.addStretch()

        self._clear_cards(self.target_layout)
        if not targets:
            empty = QLabel("No Target Groups yet.\nClassify a group as Target first.")
            empty.setProperty("flowEmpty", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.target_layout.addWidget(empty)
        for group in targets:
            card = TargetGroupCard(group, self.member_controller.target_stats(int(group.id)) or {})
            card.sourceDropped.connect(self._dropped)
            card.clicked.connect(self._target_clicked)
            if self.initial_target_id and int(group.id) == self.initial_target_id:
                card.setProperty("recommendedTarget", True)
                _repolish(card)
            self.target_layout.addWidget(card)
        self.target_layout.addStretch()

    def _select_source(self, source_id: int):
        self._selected_source_id = int(source_id)

    def _target_clicked(self, target_id: int):
        if self._selected_source_id:
            self._dropped(self._selected_source_id, int(target_id))

    def _dropped(self, source_id: int, target_id: int):
        if int(source_id) == int(target_id):
            QMessageBox.information(self, "Quick Add", "A Source Group cannot be its own Target.")
            return
        source = self._source_groups.get(int(source_id))
        target = self._target_groups.get(int(target_id))
        if not source or not target:
            return
        self._selected_source_id = int(source_id)
        self._selected_target_id = int(target_id)
        self.lbl_route_source.setText(
            f"{source.title}\n@{source.username}" if getattr(source, "username", None) else source.title
        )
        self.lbl_route_target.setText(
            f"{target.title}\n@{target.username}" if getattr(target, "username", None) else target.title
        )
        stats = self.member_controller.source_stats(int(source_id)) or {}
        stored = int(stats.get("stored", 0) or 0)
        self.spin_amount.setMaximum(max(1, min(self.MAX_QUICK_MEMBERS, stored or self.MAX_QUICK_MEMBERS)))
        self.spin_amount.setValue(max(1, min(20, stored or 20)))
        self.stack.setCurrentIndex(1)
        QTimer.singleShot(250, self._prepare)

    def _back_to_board(self):
        if self._running:
            return
        self._generation += 1
        self._precheck = None
        self._member_ids = []
        self._account_ids = []
        self.stack.setCurrentIndex(0)

    def _amount_changed(self, *_args):
        if self._running or self.stack.currentIndex() == 0:
            return
        self._generation += 1
        self._precheck = None
        self.btn_check.setText("Check & Continue")
        self.btn_check.setEnabled(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lbl_status.setText("Amount changed. Click Check & Continue.")

    def _toggle_advanced(self, checked: bool):
        self.txt_advanced.setVisible(bool(checked))
        self.btn_advanced.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def _choose_accounts(self):
        options = list(self.member_controller.mass_add_account_options(int(self._selected_target_id)) or [])
        selectable = [row for row in options if row.get("selectable")]
        selectable.sort(
            key=lambda row: (
                0 if row.get("can_invite_now") else 1,
                0 if str(row.get("health") or "").upper() == "HEALTHY" else 1,
                int(row.get("account_id", 0)),
            )
        )
        chosen = selectable[: self.MAX_ACCOUNTS]
        self._account_ids = [int(row["account_id"]) for row in chosen]
        return options, chosen

    def _render_accounts_initial(self, options, chosen):
        visible = chosen if chosen else options[:5]
        self.table_accounts.setRowCount(len(visible))
        for index, row in enumerate(visible):
            account_id = int(row.get("account_id", 0) or 0)
            name = str(row.get("name") or f"Account {account_id}")
            if row.get("username"):
                name += f"  •  @{row['username']}"
            status = "Preparing • auto join" if row.get("auto_join") else "Preparing"
            self.table_accounts.setItem(index, 0, self._item(name))
            self.table_accounts.setItem(index, 1, self._item(status))
            self.table_accounts.setItem(index, 2, self._item("—"))

    def _prepare(self):
        if self._closed or self._running or not self._selected_source_id or not self._selected_target_id:
            return

        amount = int(self.spin_amount.value())
        self._member_ids = list(
            self.member_controller.smart_transfer_member_ids(
                int(self._selected_source_id), int(self._selected_target_id), amount
            ) or []
        )
        self._set_metric(self.metric_found, len(self._member_ids))
        self._set_metric(self.metric_ready, 0)
        self._set_metric(self.metric_existing, 0)
        self._set_metric(self.metric_attention, len(self._member_ids))

        if not self._member_ids:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.lbl_status.setText(
                "No stored members are available from this Source Group. Sync its members first, then drag it again."
            )
            self.btn_check.setText("Check Again")
            self.btn_check.setEnabled(True)
            return

        options, chosen = self._choose_accounts()
        self._render_accounts_initial(options, chosen)
        if not self._account_ids:
            self.lbl_status.setText(
                "No healthy Telegram account is available for this Target Group. Open Accounts / Health Center and make an account ready."
            )
            self.btn_check.setText("Check Again")
            self.btn_check.setEnabled(True)
            return

        self._auto_account_retry = False
        self._generation += 1
        generation = self._generation
        self._precheck = None
        self.btn_check.setEnabled(False)
        self.btn_check.setText("Preparing…")
        self.progress.setRange(0, 0)
        self.lbl_status.setText(
            "Preparing accounts, joining the target when needed, checking selected members and verifying live Telegram permissions…"
        )

        token = self.member_controller.request_invitation_batch_preflight(
            int(self._selected_target_id),
            list(self._account_ids),
            list(self._member_ids),
            callback=lambda result, g=generation: self._apply_preflight(result, g),
        )
        if token is None:
            cached = self.member_controller.invitation_batch_precheck(
                int(self._selected_target_id), list(self._account_ids), list(self._member_ids)
            )
            if cached:
                self._apply_preflight(cached, generation)
            else:
                self._preflight_failed("SP Telegram could not start the readiness check.")

    @staticmethod
    def _as_dict(value):
        if isinstance(value, dict):
            return value
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return None

    def _apply_preflight(self, result, generation=None):
        if self._closed or (generation is not None and generation != self._generation):
            return
        pre = self._as_dict(result)
        if not pre:
            self._preflight_failed("The readiness check returned no usable result.")
            return

        self._precheck = pre
        counts = dict(pre.get("counts") or {})
        selected = int(counts.get("selected", len(self._member_ids)) or 0)
        policy_ready = int(counts.get("ready", 0) or 0)
        existing = int(counts.get("already_member", 0) or 0)
        usable_ids = [int(row.get("account_id")) for row in pre.get("accounts") or [] if bool(row.get("ready"))]
        if (
            not bool(pre.get("can_start", pre.get("start_allowed", False)))
            and usable_ids
            and set(usable_ids) != set(self._account_ids)
            and not self._auto_account_retry
        ):
            self._auto_account_retry = True
            self._account_ids = usable_ids
            self.lbl_status.setText("Some accounts are unavailable. Retrying automatically with the accounts that passed Telegram checks…")
            self.member_controller.request_invitation_batch_preflight(
                int(self._selected_target_id),
                list(self._account_ids),
                list(self._member_ids),
                callback=lambda result, g=self._generation: self._apply_preflight(result, g),
            )
            return
        assigned_ready = sum(int(row.get("count", 0) or 0) for row in pre.get("assignments") or [])
        ready = assigned_ready if bool(pre.get("can_start", pre.get("start_allowed", False))) else 0
        attention = max(0, selected - ready - existing)
        self._set_metric(self.metric_found, selected)
        self._set_metric(self.metric_ready, ready)
        self._set_metric(self.metric_existing, existing)
        self._set_metric(self.metric_attention, attention)

        account_rows = list(pre.get("accounts") or [])
        self.table_accounts.setRowCount(len(account_rows))
        for index, row in enumerate(account_rows):
            name = str(row.get("name") or f"Account {row.get('account_id')}")
            blockers = list(row.get("blocking_reasons") or [])
            if row.get("can_invite") and not blockers:
                status = "Ready"
            elif row.get("can_invite"):
                status = "Ready • no assignment"
            else:
                status = self._friendly_blocker(blockers[0] if blockers else "Cannot invite")
            self.table_accounts.setItem(index, 0, self._item(name))
            self.table_accounts.setItem(index, 1, self._item(status))
            self.table_accounts.setItem(index, 2, self._item(str(int(row.get("assigned_count", 0) or 0))))

        blockers = list(pre.get("blocking_reasons") or [])
        warnings = list(pre.get("warnings") or [])
        details = [f"BLOCK: {x}" for x in blockers] + [f"NOTE: {x}" for x in warnings]
        for key, label in (
            ("eligibility_not_approved", "Needs eligibility review"),
            ("consent_not_approved", "Needs approval"),
            ("unknown", "Target membership could not be verified"),
            ("blacklisted", "Blacklisted"),
            ("do_not_contact", "Do not contact"),
            ("deleted", "Deleted"),
            ("bots", "Bots"),
        ):
            value = int(counts.get(key, 0) or 0)
            if value:
                details.append(f"{label}: {value}")
        self.txt_advanced.setPlainText(chr(10).join(details) or "All checks passed.")

        self.progress.setRange(0, 100)
        self.progress.setValue(100 if ready else 0)
        can_start = bool(pre.get("can_start", pre.get("start_allowed", False)))
        if can_start and ready > 0:
            self.lbl_status.setText(
                f"Ready. {ready:,} member(s) can be added now. {existing:,} already in the target will be skipped automatically."
            )
            self.btn_check.setText(f"Add {ready:,} Members")
            self.btn_check.setEnabled(True)
        else:
            self.lbl_status.setText(self._friendly_summary(counts, blockers))
            self.btn_check.setText("Check Again")
            self.btn_check.setEnabled(True)

    @staticmethod
    def _friendly_blocker(message: str) -> str:
        text = str(message or "")
        lower = text.lower()
        if "permission to invite" in lower:
            return "Not ready • invite permission required"
        if "not mapped" in lower or "target access" in lower:
            return "Not ready • join or permission required"
        if "not authorized" in lower or "session" in lower:
            return "Login required"
        if "connection" in lower or "disconnected" in lower:
            return "Connection unavailable"
        if "restriction" in lower or "healthy" in lower:
            return "Account restricted"
        return text or "Not ready"

    @staticmethod
    def _friendly_summary(counts: dict, blockers: list[str]) -> str:
        selected = int(counts.get("selected", 0) or 0)
        policy_ready = int(counts.get("ready", 0) or 0)
        existing = int(counts.get("already_member", 0) or 0)
        approval = int(counts.get("consent_not_approved", 0) or 0)
        review = int(counts.get("eligibility_not_approved", 0) or 0)
        unknown = int(counts.get("unknown", 0) or 0)

        if blockers and policy_ready > 0:
            return (
                f"{policy_ready:,} member check(s) passed, but no Telegram account is ready "
                "to add them to this target. SP Telegram will retry account preparation on Check Again."
            )
        if approval or review:
            return (
                f"{max(approval, review):,} member(s) need approval/review in Member Pool "
                "before they can be added."
            )
        if unknown:
            return (
                f"Telegram could not verify target membership for {unknown:,} member(s). "
                "Click Check Again or open Advanced details."
            )
        if existing and existing == selected:
            return "All selected members are already in the Target Group."
        if blockers:
            return DragDropAddDialog._friendly_blocker(blockers[0])
        if policy_ready:
            return "Member checks passed. Waiting for a usable Telegram account."
        return "Nothing is ready to add yet. Open Advanced details for the exact reason."


    def _preflight_failed(self, message):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lbl_status.setText(str(message or "Readiness check failed."))
        self.btn_check.setText("Check Again")
        self.btn_check.setEnabled(True)

    def _primary_clicked(self):
        if self._running:
            return
        pre = self._precheck or {}
        counts = pre.get("counts") or {}
        ready = int(counts.get("ready", 0) or 0)
        if bool(pre.get("can_start", pre.get("start_allowed", False))) and ready > 0:
            self._start()
        else:
            self._prepare()

    def _start(self):
        pre=self._precheck or {}
        ready=int((pre.get("counts") or {}).get("ready",0) or 0)
        if ready<=0:
            self._prepare()
            return

        target=self._target_groups.get(int(self._selected_target_id))
        if QMessageBox.question(
            self,
            "Add Members",
            f"Add {ready:,} ready member(s) to {getattr(target,'title','the target')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )!=QMessageBox.StandardButton.Yes:
            return

        self._running=True
        self.btn_back.setEnabled(False)
        self.btn_check.setEnabled(False)
        self.btn_check.setText("Adding Members…")
        self.progress.setRange(0,max(1,ready))
        self.progress.setValue(0)
        self.lbl_status.setText("Adding members safely…")

        self.live_activity.start_job(self._live_accounts_v4())
        self.resize(max(self.width(),1060),max(self.height(),860))

        token=self.member_controller.start_target_invitation_batch(
            int(self._selected_target_id),
            list(self._account_ids),
            list(self._member_ids),
        )
        if token is None:
            self._running=False
            self.btn_back.setEnabled(True)
            self.btn_check.setEnabled(True)
            self.btn_check.setText("Check Again")
            self.lbl_status.setText(
                "The operation could not start. Check license and Telegram runtime status."
            )
            self.live_activity.finish(error_message=self.lbl_status.text())

    def _progress(self,payload):
        if self._closed or not self._running or not payload:
            return
        payload=dict(payload or {})
        processed=int(payload.get("processed",0) or 0)
        total=int(payload.get("total",0) or 0)
        successful=int(payload.get("successful",0) or 0)
        skipped=int(payload.get("skipped",0) or 0)
        failed=int(payload.get("failed",0) or 0)

        self.progress.setRange(0,max(1,total))
        self.progress.setValue(processed)
        self.lbl_status.setText(
            f"Adding… {processed:,}/{total:,} • {successful:,} added • "
            f"{skipped:,} skipped • {failed:,} failed"
        )
        self.live_activity.update_progress(payload)

    def _completed(self,result):
        if self._closed or not self._running:
            return
        self._running=False
        self._last_result=result or {}
        self.btn_results.setEnabled(bool(self._last_result))
        self.btn_back.setEnabled(True)

        successful=int(self._last_result.get("successful",0) or 0)
        skipped=int(self._last_result.get("skipped",0) or 0)
        failed=int(self._last_result.get("failed",0) or 0)
        self.live_activity.finish(self._last_result)

        if str(self._last_result.get("status","")).upper()=="BLOCKED":
            self.lbl_status.setText(
                self._last_result.get("message") or "The operation stopped safely."
            )
            self.btn_check.setText("Check Again")
            self.btn_check.setEnabled(True)
            return

        self.lbl_status.setText(
            f"Completed • {successful:,} added • {skipped:,} skipped • {failed:,} failed"
        )
        self.btn_check.setText("Done ✓")
        self.btn_check.setEnabled(False)

    def _failed(self,message):
        if self._closed or not self._running:
            return
        self._running=False
        self.btn_back.setEnabled(True)
        self.btn_check.setText("Check Again")
        self.btn_check.setEnabled(True)
        self.lbl_status.setText(str(message or "The operation could not continue."))
        self.live_activity.finish(error_message=self.lbl_status.text())

    def _show_results(self):
        if self._last_result:
            InvitationResultsDialog(self._last_result, self).exec()
