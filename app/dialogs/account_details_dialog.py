from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.utils.formatters import format_local_datetime, mask_phone
from app.widgets.capability_badge import CapabilityBadge
from app.widgets.status_badge import StatusBadge
from app.widgets.detail_header import DetailHeaderWidget


class AccountDetailsDialog(QDialog):
    viewSessionsRequested = Signal(int)

    def __init__(self, account, controller, parent=None, *, avatar_service=None):
        super().__init__(parent)
        self.account = account
        self.controller = controller
        self.setWindowTitle(f"Account Details — {account.first_name or account.username or account.id}")
        self.resize(760, 590)
        root = QVBoxLayout(self); root.setContentsMargins(20,20,20,16); root.setSpacing(12)
        display_name = " ".join(x for x in [account.first_name, account.last_name] if x) or account.username or f"Account {account.id}"
        root.addWidget(DetailHeaderWidget(
            display_name,
            f"@{account.username}" if account.username else "Authorized account",
            account.health_status.replace("_", " ").title(),
            self,
            avatar_service=avatar_service,
            avatar_kind="account",
            avatar_id=account.id,
            avatar_peer_id=account.telegram_user_id,
            avatar_account_id=account.id,
        ))
        self.tab_account_details = QTabWidget()
        self.tab_account_details.setObjectName("tab_account_details")
        root.addWidget(self.tab_account_details, 1)
        self._overview()
        self._health()
        self._capabilities()
        self._restrictions()
        self._activity()
        self._sessions()
        self._groups()
        self._statistics()
        buttons = QHBoxLayout()
        specs = [
            ("btn_account_connect", "Connect"),
            ("btn_account_disconnect", "Disconnect"),
            ("btn_account_logout", "Logout from Telegram"),
            ("btn_account_run_health_check", "Health Check"),
            ("btn_refresh_account_profile", "Refresh Profile"),
            ("btn_account_view_sessions", "View Sessions"),
            ("btn_account_save", "Save"),
            ("btn_account_close", "Close"),
        ]
        for obj, text in specs:
            button = QPushButton(text)
            button.setObjectName(obj)
            setattr(self, obj, button)
            buttons.addWidget(button)
        buttons.addStretch()
        root.addLayout(buttons)
        self.btn_account_close.clicked.connect(self.accept)
        self.btn_account_save.clicked.connect(lambda: self.accept())
        self.btn_account_connect.clicked.connect(lambda: controller.connect_account(account.id))
        self.btn_account_disconnect.clicked.connect(lambda: controller.disconnect_account(account.id))
        self.btn_account_run_health_check.clicked.connect(lambda: controller.run_health_check(account.id))
        self.btn_refresh_account_profile.clicked.connect(lambda: controller.refresh_profile(account.id))
        self.btn_account_view_sessions.clicked.connect(lambda: self.viewSessionsRequested.emit(account.id))
        self.btn_account_logout.clicked.connect(self._logout)
        controller.accountsChanged.connect(self._refresh_reference)
        self.update_account_action_states(account)

    def _new_form(self, title):
        widget = QWidget()
        form = QFormLayout(widget)
        self.tab_account_details.addTab(widget, title)
        return form

    def _overview(self):
        f = self._new_form("Overview")
        rows = [
            ("Telegram ID", self.account.telegram_user_id or "—"),
            ("Username", f"@{self.account.username}" if self.account.username else "—"),
            ("Name", " ".join(x for x in [self.account.first_name, self.account.last_name] if x) or "—"),
            ("Phone", mask_phone(self.account.phone)),
            ("Premium", "Yes" if self.account.is_premium else "No"),
            ("Connection", self.account.connection_status.replace("_", " ").title()),
            ("Authorization", self.account.authorization_status.replace("_", " ").title()),
            ("Last Active", format_local_datetime(self.account.last_active_at)),
            ("Last Connected", format_local_datetime(self.account.last_connected_at)),
        ]
        for key, value in rows:
            f.addRow(key, QLabel(str(value)))

    def _health(self):
        f = self._new_form("Health")
        f.addRow("Health State", StatusBadge(self.account.health_status.replace("_", " ").title()))
        for key, value in [
            ("Last Health Check", format_local_datetime(self.account.last_health_check_at)),
            ("Last Error", self.account.last_error_message or "—"),
            ("Restriction", (self.account.restriction_type or "None").replace("_", " ").title()),
            ("Restriction Until", format_local_datetime(self.account.restriction_until)),
            ("Session", "Available" if self.account.session_path and Path(self.account.session_path).is_file() else "Missing / not configured"),
        ]:
            f.addRow(key, QLabel(str(value)))

    def _capabilities(self):
        f = self._new_form("Capabilities")
        for label, allowed in [
            ("Collect Members", bool(self.account.can_collect)),
            ("Invite Members", bool(self.account.can_invite)),
            ("Send Group Posts", bool(self.account.can_post)),
            ("Schedule Posts", bool(self.account.can_schedule)),
            ("Manage Groups", bool(self.account.can_manage)),
        ]:
            badge = CapabilityBadge(label, allowed)
            badge.setToolTip("Capability is only shown when locally verified. Successful login alone does not grant it.")
            f.addRow(label, badge)

    def _restrictions(self):
        f = self._new_form("Restrictions")
        details = self.controller.details(self.account.id) or {}
        restrictions = self.controller.restrictions()
        own = [r for r in restrictions if r.account_id == self.account.id]
        f.addRow("Active restrictions", QLabel(str(len(own))))
        f.addRow("Current", QLabel((self.account.restriction_type or "None").replace("_", " ").title()))

    def _activity(self):
        f = self._new_form("Activity")
        details = self.controller.details(self.account.id) or {}
        activity = details.get("activity", [])
        if not activity:
            f.addRow("Recent", QLabel("No recorded activity yet."))
            return
        for item in activity[:8]:
            f.addRow(format_local_datetime(item.created_at), QLabel(f"{item.action_type}: {item.message or ''}"))

    def _sessions(self):
        f = self._new_form("Sessions")
        f.addRow("Session file", QLabel("Configured" if self.account.session_path else "Not configured"))
        f.addRow("Authorization", QLabel(self.account.authorization_status.replace("_", " ").title()))
        f.addRow("Note", QLabel("Open Session Manager to fetch Telegram-authorized devices."))

    def _groups(self):
        f = self._new_form("Groups")
        group_controller = getattr(self.controller, "group_controller", None)
        mappings = group_controller.service.get_account_groups(self.account.id) if group_controller else []
        if not mappings:
            f.addRow("Mapped groups", QLabel("No Telegram group mappings yet."))
            return
        owner = sum(1 for m in mappings if str(m.get("role")) == "OWNER")
        admin = sum(1 for m in mappings if str(m.get("role")) == "ADMIN")
        member = sum(1 for m in mappings if str(m.get("role")) == "MEMBER")
        managed = sum(1 for m in mappings if bool(m.get("is_managed")))
        f.addRow("Groups Accessible", QLabel(str(len(mappings))))
        f.addRow("Owner", QLabel(str(owner)))
        f.addRow("Admin", QLabel(str(admin)))
        f.addRow("Member", QLabel(str(member)))
        f.addRow("Managed Groups", QLabel(str(managed)))
        for m in mappings[:12]:
            title = str(m.get("group_title") or m.get("group_id"))
            role = str(m.get("role") or "UNKNOWN").title()
            caps = f"Post: {'Yes' if m.get('can_post') else 'No'} • Invite: {'Yes' if m.get('can_invite') else 'No'} • Manage: {'Yes' if m.get('can_manage') else 'No'}"
            f.addRow(title, QLabel(f"{role} • {caps}"))

    def _statistics(self):
        f = self._new_form("Statistics")
        f.addRow("Last success", QLabel(format_local_datetime(self.account.last_success_at)))
        f.addRow("Last connection", QLabel(format_local_datetime(self.account.last_connected_at)))
        f.addRow("Last health check", QLabel(format_local_datetime(self.account.last_health_check_at)))

    def update_account_action_states(self, account):
        connected = str(account.connection_status).upper() == "CONNECTED"
        authorized = str(account.authorization_status).upper() == "AUTHORIZED"
        demo = bool(getattr(account, "is_demo", 0))
        self.btn_account_connect.setEnabled(not connected and not demo)
        self.btn_account_disconnect.setEnabled(connected and not demo)
        self.btn_account_logout.setEnabled(authorized and not demo)
        self.btn_refresh_account_profile.setEnabled(connected and authorized and not demo)
        self.btn_account_view_sessions.setEnabled(connected and authorized and not demo)
        self.btn_account_run_health_check.setEnabled(not demo)

    def _refresh_reference(self, accounts):
        for account in accounts:
            if account.id == self.account.id:
                self.account = account
                self.update_account_action_states(account)
                return

    def _logout(self):
        name = self.account.first_name or self.account.username or f"Account {self.account.id}"
        if QMessageBox.warning(
            self,
            "Logout from Telegram",
            f"Logout {name} from Telegram?\n\nThis removes this application's Telegram authorization and will require logging in again.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            self.controller.logout_account(self.account.id)

# Add compatibility attributes for older PySide6 versions
if not hasattr(AccountDetailsDialog, 'Accepted'):
    AccountDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AccountDetailsDialog, 'Rejected'):
    AccountDetailsDialog.Rejected = QDialog.DialogCode.Rejected
