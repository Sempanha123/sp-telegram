from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QHeaderView,
)

from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout


class JoinRequestsDialog(QDialog):
    """Operator-reviewed pending join requests for one target and one account."""

    COLUMNS = ["Name", "Username", "User ID", "Requested"]

    def __init__(self, group_controller, group_id: int, account_id: int, target_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("dlg_target_join_requests")
        self.setWindowTitle("Pending Join Requests - SP Telegram")
        self.setMinimumSize(720, 480)
        self.controller = group_controller
        self.group_id = int(group_id)
        self.account_id = int(account_id)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        title = QLabel("Pending Join Requests")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        subtitle = QLabel(f"{target_name}\nApprove or decline one selected Telegram join request. No bulk approval is performed.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("secondary", True)
        root.addWidget(subtitle)

        self.model = BaseTableModel([], self.COLUMNS, self)
        self.table = QTableView()
        self.table.setObjectName("tbl_target_join_requests")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table_layout = TableLayoutManager(self)
        self._table_layout.apply(self.table, self.COLUMNS, overrides={
            "Name": ColumnLayout(210, 150, "stretch"),
            "Username": ColumnLayout(190, 130),
            "User ID": ColumnLayout(150, 120),
            "Requested": ColumnLayout(180, 155),
        })
        root.addWidget(self.table, 1)

        self.lbl_empty = QLabel("Loading pending requests…")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setProperty("secondary", True)
        root.addWidget(self.lbl_empty)

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh"); self.btn_refresh.setObjectName("btn_refresh_join_requests")
        self.btn_approve = QPushButton("Approve"); self.btn_approve.setObjectName("btn_approve_join_request"); self.btn_approve.setProperty("role", "primary")
        self.btn_decline = QPushButton("Decline"); self.btn_decline.setObjectName("btn_decline_join_request")
        self.btn_close = QPushButton("Close"); self.btn_close.setObjectName("btn_close_join_requests")
        bar.addWidget(self.btn_refresh); bar.addStretch(); bar.addWidget(self.btn_decline); bar.addWidget(self.btn_approve); bar.addWidget(self.btn_close)
        root.addLayout(bar)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_approve.clicked.connect(lambda: self._respond(True))
        self.btn_decline.clicked.connect(lambda: self._respond(False))
        self.btn_close.clicked.connect(self.accept)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self._selection_changed()
        self.refresh()

    @staticmethod
    def _row(item):
        if isinstance(item, dict):
            uid = int(item.get("user_id") or 0)
            username = item.get("username")
            name = item.get("display_name") or item.get("first_name") or f"User {uid}"
            requested = item.get("requested_at") or item.get("date") or "—"
        else:
            uid = int(getattr(item, "user_id", 0) or 0)
            username = getattr(item, "username", None)
            first = getattr(item, "first_name", None)
            last = getattr(item, "last_name", None)
            name = " ".join(x for x in (first, last) if x).strip() or f"User {uid}"
            requested = getattr(item, "requested_at", None) or getattr(item, "date", None) or "—"
        requested_text = format_local_datetime(str(requested)) if requested not in (None, "—") else "—"
        return {"Name": name, "Username": f"@{username}" if username else "—", "User ID": uid, "Requested": requested_text, "_user_id": uid}

    def refresh(self):
        self.btn_refresh.setEnabled(False)
        self.lbl_empty.setText("Loading pending requests…")
        self.controller.list_target_join_requests(self.group_id, self.account_id, callback=self._loaded, failure_callback=self._load_failed)

    def _load_failed(self, message=None):
        self.btn_refresh.setEnabled(True)
        self.lbl_empty.setText(str(message or "Could not load pending join requests."))
        self._selection_changed()

    def _loaded(self, items):
        rows = [self._row(item) for item in (items or [])]
        self.model.replace_rows(rows)
        self.btn_refresh.setEnabled(True)
        self.lbl_empty.setText("No pending join requests." if not rows else f"{len(rows)} pending request(s).")
        self._selection_changed()

    def _selected_user_id(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes: return None
        row = self.model.row_item(indexes[0].row())
        return int(row.get("_user_id") or 0) or None

    def _selection_changed(self, *_args):
        enabled = self._selected_user_id() is not None if self.table.selectionModel() else False
        self.btn_approve.setEnabled(enabled)
        self.btn_decline.setEnabled(enabled)

    def _respond_failed(self, _message=None):
        self._selection_changed()

    def _respond(self, approved: bool):
        user_id = self._selected_user_id()
        if not user_id: return
        action = "approve" if approved else "decline"
        if QMessageBox.question(self, "Join Request", f"{action.title()} the selected join request?") != QMessageBox.StandardButton.Yes:
            return
        self.btn_approve.setEnabled(False); self.btn_decline.setEnabled(False)
        self.controller.respond_target_join_request(
            self.group_id, self.account_id, user_id, approved=approved,
            callback=lambda _result: self.refresh(),
            failure_callback=self._respond_failed,
        )

# Add compatibility attributes for older PySide6 versions
if not hasattr(JoinRequestsDialog, 'Accepted'):
    JoinRequestsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(JoinRequestsDialog, 'Rejected'):
    JoinRequestsDialog.Rejected = QDialog.DialogCode.Rejected
