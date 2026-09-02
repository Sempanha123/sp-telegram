from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QWidget

from app.dialogs.account_pool_group_assignment_dialog import AccountPoolGroupAssignmentDialog
from app.dialogs.account_safety_dialog import AccountSafetyDialog
from app.models.account_pool_table_model import AccountPoolTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.avatar_delegate import AvatarDelegate
from app.widgets.select_all_header import SelectAllHeader
from app.widgets.table_checkbox_delegate import TableCheckBoxDelegate


class AccountPoolPage(BaseTablePage):
    """Operational account pool.

    The page controls eligibility for *new* local operations and mappings. It
    never rotates an in-flight Telegram job after a restriction or FloodWait.
    """

    toastRequested = Signal(str, str)

    def __init__(self, controller, account_controller, group_controller, parent=None, *, avatar_service=None):
        self.controller = controller
        self.account_controller = account_controller
        self.group_controller = group_controller
        self.avatar_service = avatar_service
        actions = [
            ("btn_account_pool_enable", "Enable Selected"),
            ("btn_account_pool_disable", "Disable Selected"),
            ("btn_account_pool_health", "Health Check Selected"),
            ("btn_account_pool_permissions", "Refresh Permissions"),
            ("btn_account_pool_safety", "Safety Limits"),
            ("btn_account_pool_tags", "Assign Tags"),
            ("btn_account_pool_groups", "Assign Groups"),
            ("btn_account_pool_clear_assignment", "Clear Assignment"),
            ("btn_account_pool_export", "Export"),
            ("btn_account_pool_refresh", "Refresh"),
        ]
        super().__init__(
            "page_account_pool", "Account Pool", AccountPoolTableModel([]), "tbl_account_pool", actions,
            "le_search_account_pool",
            [
                ("cmb_account_pool_enabled", "Enabled", ["Enabled", "Disabled"]),
                ("cmb_account_pool_health", "Health", ["Healthy", "Ready", "Busy", "Warning", "Cooldown", "Restricted", "Offline", "Login Required", "Disabled", "Unknown"]),
                ("cmb_account_pool_restriction", "Restriction", ["None", "Cooldown", "Restricted", "Flood Wait", "Spam Limited", "Unknown"]),
                ("cmb_account_pool_safety", "Safety", ["Normal", "Watch", "Cooldown", "Recovering", "Restricted", "Disabled"]),
            ], parent,
        )
        self.enable_database_mode(controller.pagination)
        self.set_empty_state("No accounts in the pool", "Add and authorize Telegram accounts first. Accounts are loaded lazily and are not all connected at startup.")
        self._install_summary()
        self._install_checkbox_header()
        if self.avatar_service is not None and "Account" in self.model.columns:
            # Pool accounts are the same accounts as the Accounts page: their
            # avatar is always the account's own profile photo (get_me()).
            self.table.setItemDelegateForColumn(
                self.model.columns.index("Account"),
                AvatarDelegate(self.avatar_service, "account", "id", "account", self.table,
                               account_id_attr="id", subtitle_column="Username"),
            )
        self._configure_columns()
        if "Username" in self.model.columns:self.table.setColumnHidden(self.model.columns.index("Username"),True)
        self.searchDebounced.connect(controller.set_search)
        self.filterChanged.connect(controller.set_filter)
        self.pageChanged.connect(controller.set_page)
        self.pageSizeChanged.connect(controller.set_page_size)
        controller.rowsChanged.connect(self._replace)
        controller.summaryChanged.connect(self._update_summary)
        controller.toast_requested.connect(self.toastRequested)
        group_controller.groupAssignmentFinished.connect(lambda *_: controller.refresh())
        self.model.checkedChanged.connect(self._update_actions)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_actions())
        self.action_buttons["btn_account_pool_enable"].clicked.connect(lambda: self._set_enabled(True))
        self.action_buttons["btn_account_pool_disable"].clicked.connect(lambda: self._set_enabled(False))
        self.action_buttons["btn_account_pool_health"].clicked.connect(self._health_selected)
        self.action_buttons["btn_account_pool_permissions"].clicked.connect(self._refresh_permissions)
        self.action_buttons["btn_account_pool_safety"].clicked.connect(self._configure_safety)
        self.action_buttons["btn_account_pool_tags"].clicked.connect(self._assign_tags)
        self.action_buttons["btn_account_pool_groups"].clicked.connect(self._assign_groups)
        self.action_buttons["btn_account_pool_clear_assignment"].clicked.connect(self._clear_assignments)
        self.action_buttons["btn_account_pool_export"].clicked.connect(self._export)
        self.action_buttons["btn_account_pool_refresh"].clicked.connect(controller.refresh)
        self._update_actions()

    def _install_summary(self):
        host = QFrame(); host.setObjectName("account_pool_summary")
        grid = QGridLayout(host); grid.setContentsMargins(14, 10, 14, 10); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        self._summary_labels = {}
        specs = [
            ("total", "Total Accounts"), ("enabled", "Enabled"), ("healthy", "Healthy"), ("busy", "Busy"),
            ("offline", "Offline"), ("login_required", "Login Required"), ("restricted", "Restricted"),
            ("cooldown", "Cooldown"), ("watch", "Watch"), ("recovering", "Recovering"),
            ("daily_limited", "Daily Limited"), ("posting_available", "Posting Available"), ("invite_available", "Invite Available"),
        ]
        for index, (key, text) in enumerate(specs):
            box = QWidget(); box.setProperty("accountSummaryItem", True); layout = QHBoxLayout(box); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(5)
            label = QLabel(text); label.setProperty("accountSummaryLabel", True)
            value = QLabel("0"); value.setObjectName(f"lbl_account_pool_{key}"); value.setProperty("summaryValueSmall", True)
            value.setProperty("tone", {"healthy":"success","enabled":"primary","posting_available":"purple","invite_available":"primary","watch":"warning","cooldown":"warning","recovering":"danger","restricted":"danger","daily_limited":"danger","offline":"muted","login_required":"warning"}.get(key,"default"))
            layout.addWidget(label); layout.addWidget(value); layout.addStretch(); grid.addWidget(box, index // 7, index % 7)
            self._summary_labels[key] = value
        for column in range(7): grid.setColumnStretch(column, 1)
        self.root_layout.insertWidget(1, host)

    def _install_checkbox_header(self):
        old = self.table.horizontalHeader()
        header = SelectAllHeader(old.orientation(), self.table)
        header.setSectionsMovable(True); header.setStretchLastSection(False)
        self.table.setHorizontalHeader(header)
        self.table.setItemDelegateForColumn(0, TableCheckBoxDelegate(self.table))

    def _configure_columns(self):
        widths = {
            "Select": 44, "Account": 170, "Username": 175, "Enabled": 90, "Authorization": 145,
            "Connection": 130, "Health": 125, "Safety": 120, "Invite Today": 110,
            "Post Today": 105, "Restriction": 150, "Invite Capability": 145,
            "Post Capability": 140, "Groups": 80, "Current Job": 160, "Last Use": 170,
            "Next Available": 175, "Tags": 190,
        }
        for i, column in enumerate(self.model.columns):
            self.table.setColumnWidth(i, widths.get(column, 120))
        self.table.verticalHeader().setDefaultSectionSize(44)

    def refresh(self):
        return self.controller.refresh()

    def _replace(self, rows):
        self.model.replace_rows(list(rows or []))
        self.update_pagination(self.controller.pagination)
        self._update_actions()

    def _update_summary(self, data):
        for key, label in self._summary_labels.items():
            label.setText(f"{int((data or {}).get(key, 0) or 0):,}")

    def _checked(self):
        return self.model.checked_account_ids()

    def _selected_row_id(self):
        row = self.selected_row()
        return int(row.get("id", 0) or 0) if row else 0

    def _targets(self):
        ids = self._checked()
        if ids:
            return ids
        selected = self._selected_row_id()
        return [selected] if selected else []

    def _update_actions(self):
        ids = self._targets()
        selected = bool(ids)
        for key in (
            "btn_account_pool_enable", "btn_account_pool_disable", "btn_account_pool_health",
            "btn_account_pool_permissions", "btn_account_pool_safety", "btn_account_pool_tags", "btn_account_pool_clear_assignment",
        ):
            self.action_buttons[key].setEnabled(selected)
        self.action_buttons["btn_account_pool_groups"].setEnabled(len(ids) == 1)
        self.action_buttons["btn_account_pool_export"].setEnabled(bool(self.model.rows))

    def _set_enabled(self, enabled):
        ids = self._targets()
        if ids:
            self.controller.set_operations_enabled(ids, enabled)

    def _health_selected(self):
        ids = self._targets()
        if not ids:
            return
        for account_id in ids:
            self.account_controller.run_health_check(int(account_id))
        self.toastRequested.emit(f"Queued health check for {len(ids)} selected account(s).", "Info")

    def _refresh_permissions(self):
        ids = self._targets()
        if not ids:
            return
        requested = 0
        for account_id in ids:
            rows = self.controller.service.group_accounts.get_account_groups(int(account_id)) or []
            group_ids = [
                int(mapping.get("group_id", 0) if isinstance(mapping, dict) else getattr(mapping, "group_id", 0) or 0)
                for mapping in rows
            ]
            group_ids = [group_id for group_id in group_ids if group_id]
            if group_ids and self.group_controller.verify_account_group_mappings(int(account_id), group_ids):
                requested += len(group_ids)
        if requested:
            self.toastRequested.emit(f"Queued {requested} saved group permission refresh(es), one at a time per account.", "Info")
        else:
            self.toastRequested.emit("No saved group permissions were queued. The account may have no mappings or verification may already be running.", "Info")

    def _assign_tags(self):
        ids = self._targets()
        if not ids:
            return
        text, ok = QInputDialog.getText(self, "Assign Account Tags", "Comma-separated tags:")
        if ok:
            tags = [x.strip() for x in text.split(",") if x.strip()]
            self.controller.assign_tags(ids, tags)

    def _configure_safety(self):
        ids = self._targets()
        if not ids:
            return
        row = next((item for item in self.model.rows if int(item.get("id", 0) or 0) == int(ids[0])), None)
        snapshot = {
            "smart_mode": bool((row or {}).get("smart_mode", True)),
            "state": (row or {}).get("safety_state", "NORMAL"),
            "reason": (row or {}).get("safety_reason"),
            "invite_limit": int((row or {}).get("invite_limit", 20) or 0),
            "post_limit": int((row or {}).get("post_limit", 30) or 0),
            "invite_spacing_seconds": int((row or {}).get("invite_spacing_seconds", 60) or 0),
            "post_spacing_seconds": int((row or {}).get("post_spacing_seconds", 30) or 0),
        }
        dialog = AccountSafetyDialog(len(ids), snapshot, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.configure_safety(ids, dialog.values())

    def _assign_groups(self):
        ids = self._targets()
        if len(ids) != 1:
            return
        account_id = int(ids[0])
        if self.group_controller.is_group_assignment_verifying(account_id):
            self.toastRequested.emit("This account is still verifying group assignments. Wait for it to finish before editing them again.", "Warning")
            return
        account = self.controller.service.accounts.get_by_id(account_id)
        groups = self.group_controller.service.get_groups()
        existing = self.controller.service.group_accounts.get_account_groups(account_id) or []
        mapped_ids = {int(x.get("group_id", 0) if isinstance(x, dict) else getattr(x, "group_id", 0) or 0) for x in existing}
        name = getattr(account, "first_name", None) or getattr(account, "username", None) or f"Account {account_id}"
        dialog = AccountPoolGroupAssignmentDialog(str(name), groups, mapped_ids, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = set(dialog.selected_group_ids())
        result = self.controller.replace_group_assignments(account_id, selected)
        if result is None:
            return
        # The atomic local save prevents Clear Assignment from leaving the UI in
        # a half-updated state.  Permission checks then run sequentially so one
        # failure cannot cancel or hide the other selected mappings.
        self.group_controller.refresh()
        verify_ids = list(result.get("verify") or [])
        if verify_ids:
            self.group_controller.verify_account_group_mappings(account_id, verify_ids)
        else:
            self.toastRequested.emit("Group assignments are already verified and up to date.", "Info")

    def _clear_assignments(self):
        ids = self._targets()
        if not ids:
            return
        busy = [int(account_id) for account_id in ids if self.group_controller.is_group_assignment_verifying(int(account_id))]
        if busy:
            self.toastRequested.emit("Wait for group assignment verification to finish before clearing these mappings.", "Warning")
            return
        if QMessageBox.question(
            self, "Clear Account Assignments",
            f"Remove saved local group assignments for {len(ids)} account(s)?\n\nThis does not leave Telegram groups or change Telegram permissions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            if self.controller.clear_assignments(ids) is not None:
                self.group_controller.refresh()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Account Pool", "account_pool.csv", "CSV Files (*.csv)")
        if not path:
            return
        self.controller.service.export_csv(Path(path), list(self.model.rows))
        self.toastRequested.emit("Account Pool page exported.", "Success")
