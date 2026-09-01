from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QHeaderView, QMenu, QMessageBox

from app.dialogs.account_details_dialog import AccountDetailsDialog
from app.dialogs.bulk_account_progress_dialog import BulkAccountProgressDialog
from app.dialogs.add_account_dialog import AddAccountDialog
from app.models.account_table_model import AccountTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.avatar_delegate import AvatarDelegate


class AccountsPage(BaseTablePage):
    toastRequested = Signal(str, str)
    openSettingsRequested = Signal()
    sessionsRequested = Signal(int)

    def __init__(self, controller, parent=None, *, avatar_service=None):
        self.controller = controller
        self.avatar_service = avatar_service
        actions = [
            ("btn_add_account", "Add Account"),
            ("btn_account_connect", "Connect"),
            ("btn_account_disconnect", "Disconnect"),
            ("btn_health_check_selected", "Health Check"),
            ("btn_refresh_accounts", "Refresh"),
            ("btn_account_details", "Details"),
            ("btn_account_edit", "Edit Notes"),
            ("btn_account_disable", "Disable"),
            ("btn_account_remove", "Remove"),
            ("btn_export_accounts", "Export"),
            ("btn_import_session", "Import Session"),
            ("btn_more_account_actions", "More"),
        ]
        super().__init__(
            "page_accounts", "Accounts", AccountTableModel(controller.accounts()), "tbl_accounts",
            actions, "le_search_accounts",
            [
                ("cmb_account_health_filter", "Health", ["Healthy", "Idle", "Warning", "Cooldown", "Restricted", "Offline", "Login Required", "Session Invalid", "Disabled"]),
                ("cmb_account_status_filter", "Connection", ["Connecting", "Connected", "Disconnected", "Error", "Offline"]),
                ("cmb_account_tag_filter", "Tags", ["primary", "backup", "content", "archive"]),
            ], parent,
        )
        self.enable_database_mode(controller.pagination)
        # Technical identity/session columns remain in the model and details/export,
        # but the default operations view prioritizes day-to-day status.
        for column in ["Select","ID","Telegram ID","Phone","Premium","Authorization","Session","Last Active","Last Connected","Last Health Check","Last Error","Tags"]:
            if column in self.model.columns: self.table.setColumnHidden(self.model.columns.index(column), True)
        self.searchDebounced.connect(controller.set_search)
        self.filterChanged.connect(controller.set_filter)
        self.pageChanged.connect(controller.set_page)
        self.pageSizeChanged.connect(controller.set_page_size)
        controller.accountsChanged.connect(self._replace)
        self.action_buttons["btn_add_account"].clicked.connect(self.on_add_account_clicked)
        self.action_buttons["btn_account_connect"].clicked.connect(self.connect_selected)
        self.action_buttons["btn_account_disconnect"].clicked.connect(self.disconnect_selected)
        self.action_buttons["btn_refresh_accounts"].clicked.connect(self.on_refresh_accounts_clicked)
        self.action_buttons["btn_health_check_selected"].clicked.connect(self.on_health_check_selected_clicked)
        self.action_buttons["btn_account_details"].clicked.connect(self.open_details)
        self.action_buttons["btn_account_edit"].clicked.connect(self.edit_selected)
        self.action_buttons["btn_account_disable"].clicked.connect(self.disable_selected)
        self.action_buttons["btn_account_remove"].clicked.connect(self.remove_selected)
        self.action_buttons["btn_export_accounts"].clicked.connect(self.export_csv)
        self.action_buttons["btn_more_account_actions"].clicked.connect(self.more_actions)
        self.action_buttons["btn_import_session"].clicked.connect(lambda: self.toastRequested.emit("Direct session import remains disabled. Use Login / Re-login so authorization is verified safely.", "Info"))
        self.table.doubleClicked.connect(self.on_account_double_clicked)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_action_states())
        self._make_actions()
        self._configure_account_columns()
        if self.avatar_service is not None and "Account" in self.model.columns:
            self.table.setItemDelegateForColumn(
                self.model.columns.index("Account"),
                # An account's avatar is always its own profile photo, so no
                # peer_id is passed → profile_service uses get_me() (avoids the
                # "Could not find the input entity" failure for uncached ids).
                AvatarDelegate(self.avatar_service, "account", "id", "first_name", self.table,
                               account_id_attr="id"),
            )
        # Keep the main toolbar focused on frequent operations. Less-common local
        # actions remain available through More and the existing context menu.
        for name in ("btn_account_details","btn_account_edit","btn_account_disable","btn_account_remove","btn_export_accounts","btn_import_session"):
            self.action_buttons[name].hide()
        self._update_action_states()


    def _configure_account_columns(self):
        """Give status-bearing account columns enough room for full badges."""
        header = self.table.horizontalHeader()
        widths = {
            "Account": 150,
            "Username": 170,
            "Operational Status": 160,
            "Current Job": 150,
            "Connection": 160,
            "Health": 160,
            "Last Active": 170,
        }
        for name, width in widths.items():
            if name not in self.model.columns:
                continue
            column = self.model.columns.index(name)
            if name == "Account":
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(column, width)
        header.setMinimumSectionSize(60)
        self.table.verticalHeader().setDefaultSectionSize(44)

    def _replace(self, items):
        self.model.replace_rows(items)
        self.update_pagination(self.controller.pagination)
        self._update_action_states()

    def _make_actions(self):
        specs = [
            ("act_account_details", "Open Details"),
            ("act_account_connect", "Connect"),
            ("act_account_disconnect", "Disconnect"),
            ("act_account_refresh_profile", "Refresh Profile"),
            ("act_account_health_check", "Health Check"),
            ("act_account_sessions", "Sessions"),
            ("act_account_login", "Login / Re-login"),
            ("act_account_logout", "Logout from Telegram"),
            ("act_account_restrictions", "View Restrictions"),
            ("act_account_assign_tag", "Assign Tag"),
            ("act_account_edit", "Edit Notes"),
            ("act_account_disable", "Enable / Disable"),
            ("act_account_remove", "Remove From Tool"),
        ]
        for name, text in specs:
            action = QAction(text, self)
            action.setObjectName(name)
            setattr(self, name, action)
        self.act_account_details.triggered.connect(self.open_details)
        self.act_account_connect.triggered.connect(self.connect_selected)
        self.act_account_disconnect.triggered.connect(self.disconnect_selected)
        self.act_account_refresh_profile.triggered.connect(self.refresh_profile_selected)
        self.act_account_health_check.triggered.connect(self.on_health_check_selected_clicked)
        self.act_account_sessions.triggered.connect(self.open_sessions)
        self.act_account_login.triggered.connect(self.login_selected)
        self.act_account_logout.triggered.connect(self.logout_selected)
        self.act_account_restrictions.triggered.connect(lambda: self.toastRequested.emit("Open Restrictions from the Accounts sidebar section to review recorded restrictions.", "Info"))
        self.act_account_assign_tag.triggered.connect(self.edit_selected)
        self.act_account_edit.triggered.connect(self.edit_selected)
        self.act_account_disable.triggered.connect(self.disable_selected)
        self.act_account_remove.triggered.connect(self.remove_selected)

    def _context_menu(self, pos: QPoint):
        self._update_action_states()
        menu = QMenu(self)
        menu.setObjectName("menu_account_context")
        menu.addAction(self.act_account_details)
        menu.addSeparator()
        menu.addAction(self.act_account_connect)
        menu.addAction(self.act_account_disconnect)
        menu.addAction(self.act_account_refresh_profile)
        menu.addAction(self.act_account_health_check)
        menu.addSeparator()
        menu.addAction(self.act_account_sessions)
        menu.addAction(self.act_account_login)
        menu.addAction(self.act_account_logout)
        menu.addSeparator()
        menu.addAction(self.act_account_assign_tag)
        menu.addAction(self.act_account_edit)
        menu.addAction(self.act_account_disable)
        menu.addSeparator()
        menu.addAction(self.act_account_remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _update_action_states(self):
        item = self.selected_item()
        exists = item is not None
        connected = exists and str(item.connection_status).upper() == "CONNECTED"
        authorized = exists and str(getattr(item, "authorization_status", "")).upper() == "AUTHORIZED"
        demo = exists and bool(getattr(item, "is_demo", 0))
        for name in ["btn_account_details", "btn_account_edit", "btn_account_disable", "btn_account_remove", "btn_health_check_selected"]:
            self.action_buttons[name].setEnabled(exists)
        self.action_buttons["btn_account_connect"].setEnabled(exists and not connected and not demo)
        self.action_buttons["btn_account_disconnect"].setEnabled(exists and connected and not demo)
        if hasattr(self, "act_account_connect"):
            self.act_account_connect.setEnabled(exists and not connected and not demo)
            self.act_account_disconnect.setEnabled(exists and connected and not demo)
            self.act_account_refresh_profile.setEnabled(exists and connected and authorized and not demo)
            self.act_account_sessions.setEnabled(exists and connected and authorized and not demo)
            self.act_account_logout.setEnabled(exists and authorized and not demo)
            self.act_account_login.setEnabled(exists and not demo)

    def on_add_account_clicked(self):
        ready, message = self.controller.account_add_readiness()
        if not ready:
            if not self.controller.has_telegram_config():
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Information)
                box.setWindowTitle("Telegram Configuration Required")
                box.setText("Telegram API configuration is required.")
                box.setInformativeText("Open Settings → Telegram to configure your API ID and API Hash securely.")
                open_button = box.addButton("Open Settings", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is open_button:
                    self.openSettingsRequested.emit()
            else:
                QMessageBox.information(self, "Add Account", message)
            return
        dialog = AddAccountDialog(parent=self, controller=self.controller)
        dialog.exec()

    def login_selected(self):
        item = self.selected_item()
        if not item:
            return
        if not self.controller.has_telegram_config():
            self.on_add_account_clicked()
            return
        dialog = AddAccountDialog(parent=self, controller=self.controller, existing_login_account=item)
        dialog.exec()

    def connect_selected(self):
        item = self.selected_item()
        if item:
            self.controller.connect_account(item.id)

    def disconnect_selected(self):
        item = self.selected_item()
        if item:
            self.controller.disconnect_account(item.id)

    def refresh_profile_selected(self):
        item = self.selected_item()
        if item:
            self.controller.refresh_profile(item.id)

    def on_refresh_accounts_clicked(self):
        self.controller.refresh()

    def on_health_check_selected_clicked(self):
        item = self.selected_item()
        if item:
            self.controller.run_health_check(item.id)

    def on_account_double_clicked(self, index):
        self.open_details()

    def open_details(self):
        item = self.selected_item()
        if item:
            dialog = AccountDetailsDialog(item, self.controller, self, avatar_service=self.avatar_service)
            dialog.viewSessionsRequested.connect(self.sessionsRequested)
            dialog.exec()

    def open_sessions(self):
        item = self.selected_item()
        if item:
            self.sessionsRequested.emit(item.id)

    def logout_selected(self):
        item = self.selected_item()
        if not item:
            return
        name = item.first_name or item.username or f"Account {item.id}"
        if QMessageBox.warning(
            self, "Logout from Telegram",
            f"Logout {name} from Telegram?\n\nThis removes this application's Telegram authorization for the account. Disconnect does not do this.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            self.controller.logout_account(item.id)

    def edit_selected(self):
        item = self.selected_item()
        if not item:
            return
        dialog = AddAccountDialog(item, self.controller.tags(item.id), self, controller=self.controller)
        if dialog.exec():
            self.controller.update(item.id, dialog.data())

    def disable_selected(self):
        item = self.selected_item()
        if item and QMessageBox.question(self, "Disable Account", f"Disable {item.first_name or item.username or item.id}?\n\nHistory and Telegram session path will be preserved.") == QMessageBox.StandardButton.Yes:
            self.controller.disable(item.id)

    def remove_selected(self):
        item = self.selected_item()
        if not item:
            return
        name = item.first_name or item.username or item.id
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Remove Account")
        box.setText(f"Remove {name} from SP Telegram?")
        box.setInformativeText("This removes the local configuration only when safe. It does NOT log the Telegram account out. Use 'Logout from Telegram' separately to revoke authorization.")
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self.controller.remove(item.id)

    def more_actions(self):
        menu = QMenu(self)
        profile = menu.addAction("Refresh Profile")
        sessions = menu.addAction("View Sessions")
        health_all = menu.addAction("Health Check All")
        menu.addSeparator()
        bulk_connect = menu.addAction("Connect Selected")
        bulk_disconnect = menu.addAction("Disconnect Selected")
        bulk_health = menu.addAction("Health Check Selected")
        bulk_profiles = menu.addAction("Refresh Profiles Selected")
        menu.addSeparator()
        import_csv = menu.addAction("Import Accounts CSV")
        export_csv = menu.addAction("Export Accounts CSV")
        menu.addSeparator()
        details = menu.addAction("Open Details")
        edit_notes = menu.addAction("Edit Notes")
        toggle_enabled = menu.addAction("Enable / Disable")
        remove_local = menu.addAction("Remove From Tool")
        chosen = menu.exec(self.action_buttons["btn_more_account_actions"].mapToGlobal(self.action_buttons["btn_more_account_actions"].rect().bottomLeft()))
        if chosen is profile:
            self.refresh_profile_selected()
        elif chosen is sessions:
            self.open_sessions()
        elif chosen is health_all:
            self.controller.run_health_check_all()
        elif chosen is bulk_connect:
            self._start_bulk("Connect", self.controller.start_bulk_connect)
        elif chosen is bulk_disconnect:
            self._start_bulk("Disconnect", self.controller.start_bulk_disconnect)
        elif chosen is bulk_health:
            self._start_bulk("Health Check", self.controller.start_bulk_health)
        elif chosen is bulk_profiles:
            self._start_bulk("Refresh Profile", self.controller.start_bulk_profile_refresh)
        elif chosen is import_csv:
            path, _ = QFileDialog.getOpenFileName(self, "Import Accounts", "", "CSV Files (*.csv)")
            if path:
                self.controller.import_csv(path)
        elif chosen is export_csv:
            self.export_csv()
        elif chosen is details:
            self.open_details()
        elif chosen is edit_notes:
            self.edit_selected()
        elif chosen is toggle_enabled:
            self.disable_selected()
        elif chosen is remove_local:
            self.remove_selected()

    def _start_bulk(self, operation_name, starter):
        items = [item for item in self.selected_items() if not getattr(item, "is_demo", 0)]
        ids = [int(item.id) for item in items if getattr(item, "id", None)]
        if not ids:
            self.toastRequested.emit("Select one or more non-demo accounts first.", "Info")
            return
        dialog = BulkAccountProgressDialog(self.controller, operation_name, len(ids), self)
        if starter(ids):
            # Non-modal so normal Qt signal delivery remains visible throughout the operation.
            dialog.show()
            self._bulk_dialog = dialog

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Accounts", "accounts.csv", "CSV Files (*.csv)")
        if path:
            self.controller.export_csv(path)
