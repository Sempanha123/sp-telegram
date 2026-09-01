from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QMessageBox

from app.dialogs.session_details_dialog import SessionDetailsDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.utils.formatters import format_local_datetime


class SessionsPage(BaseTablePage):
    COLUMNS = ["Current", "Device", "Platform", "Application", "App Version", "Location", "Last Active", "Created", "Status"]

    def __init__(self, account_controller, parent=None):
        self.controller = account_controller
        self._sessions = []
        super().__init__(
            "page_sessions", "Sessions", BaseTableModel([], self.COLUMNS), "tbl_sessions",
            [("btn_refresh_sessions", "Refresh Sessions"), ("btn_view_session", "View"), ("btn_revoke_selected_session", "Revoke Selected")],
            None, [], parent,
        )
        self.cmb_session_account = QComboBox()
        self.cmb_session_account.setObjectName("cmb_session_account")
        self.layout().insertWidget(1, self.cmb_session_account)
        self._load_accounts(account_controller.accounts())
        account_controller.accountsChanged.connect(self._load_accounts)
        account_controller.sessionListUpdated.connect(self._sessions_updated)
        self.action_buttons["btn_refresh_sessions"].clicked.connect(self.refresh_sessions)
        self.action_buttons["btn_view_session"].clicked.connect(self.view_selected)
        self.action_buttons["btn_revoke_selected_session"].clicked.connect(self.revoke_selected)
        self.table.doubleClicked.connect(lambda _i: self.view_selected())

    def _load_accounts(self, accounts):
        current = self.cmb_session_account.currentData()
        self.cmb_session_account.blockSignals(True)
        self.cmb_session_account.clear()
        for account in accounts:
            label = account.first_name or account.username or f"Account {account.id}"
            if getattr(account, "is_demo", 0):
                label += " (Demo)"
            self.cmb_session_account.addItem(label, account.id)
        if not accounts:
            self.cmb_session_account.addItem("No Telegram accounts available", None)
        if current is not None:
            index = self.cmb_session_account.findData(current)
            if index >= 0:
                self.cmb_session_account.setCurrentIndex(index)
        self.cmb_session_account.blockSignals(False)
        has_accounts = bool(accounts)
        self.action_buttons["btn_refresh_sessions"].setEnabled(has_accounts)
        self.action_buttons["btn_view_session"].setEnabled(has_accounts and bool(self._sessions))
        self.action_buttons["btn_revoke_selected_session"].setEnabled(has_accounts and bool(self._sessions))
        if not has_accounts:
            self._sessions = []
            self.model.replace_rows([])
            self.set_empty_state("No Telegram accounts available", "Add or connect an authorized Telegram account to review Telegram sessions.")

    def select_account(self, account_id: int):
        index = self.cmb_session_account.findData(account_id)
        if index >= 0:
            self.cmb_session_account.setCurrentIndex(index)
            self.refresh_sessions()

    def refresh_sessions(self):
        account_id = self.cmb_session_account.currentData()
        if account_id is not None:
            self.controller.refresh_sessions(int(account_id))

    def _sessions_updated(self, account_id: int, sessions: list):
        if int(account_id) != int(self.cmb_session_account.currentData() or -1):
            return
        self._sessions = list(sessions)
        rows = []
        for session in sessions:
            rows.append({
                "Current": "Yes" if session.is_current else "No",
                "Device": session.device_model,
                "Platform": session.platform,
                "Application": session.app_name,
                "App Version": session.app_version,
                "Location": session.location,
                "Last Active": format_local_datetime(session.last_active_at),
                "Created": format_local_datetime(session.created_at),
                "Status": session.status,
                "_session": session,
            })
        self.model.replace_rows(rows)
        has_rows = bool(rows)
        self.action_buttons["btn_view_session"].setEnabled(has_rows)
        self.action_buttons["btn_revoke_selected_session"].setEnabled(has_rows)

    def _selected_session(self):
        row = self.selected_row()
        return row.get("_session") if row else None

    def view_selected(self):
        session = self._selected_session()
        if not session:
            return
        dialog = SessionDetailsDialog(session, self)
        dialog.revokeRequested.connect(self._confirm_revoke)
        dialog.exec()

    def revoke_selected(self):
        session = self._selected_session()
        if session:
            self._confirm_revoke(session)

    def _confirm_revoke(self, session):
        text = f"Revoke selected Telegram session?\n\nDevice: {session.device_model}\nLocation: {session.location}\nLast Active: {format_local_datetime(session.last_active_at)}"
        if session.is_current:
            text += "\n\nThis is the session used by SP Telegram. Revoking it will require logging in again."
            first = QMessageBox.warning(self, "Revoke Current Session", text, QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)
            if first != QMessageBox.StandardButton.Yes:
                return
            second = QMessageBox.warning(self, "Confirm Current Session Revocation", "Confirm again: revoke SP Telegram's current Telegram authorization?", QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)
            if second != QMessageBox.StandardButton.Yes:
                return
        elif QMessageBox.warning(self, "Revoke Telegram Session", text, QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        account_id = self.cmb_session_account.currentData()
        if account_id is None:
            return
        self.controller.revoke_session(int(account_id), session.authorization_hash)
