from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QVBoxLayout, QDateTimeEdit,
)

from app.widgets.calendar_utils import configure_calendar_popup


class CreateTargetInviteLinkDialog(QDialog):
    """Collect non-secret invite-link options for one managed target."""

    DENIED_ACCESS = {"ACCESS_DENIED", "NOT_JOINED", "UNAVAILABLE", "NO_ACCESS", "BANNED", "LEFT"}

    def __init__(self, target_name: str, parent=None, *, accounts=None, selected_account_id: int | None = None):
        super().__init__(parent)
        self.setObjectName("dlg_create_target_invite_link")
        self.setWindowTitle("Create Target Invite Link - SP Telegram")
        self.setMinimumWidth(500)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        title = QLabel("Create Target Invite Link")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        subtitle = QLabel("Create one invite link for this managed target. Join approval is recommended when direct invitations are unavailable or inappropriate.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("secondary", True)
        root.addWidget(subtitle)

        form = QFormLayout()
        self.lbl_target = QLabel(target_name)
        self._account_rows = list(accounts or [])
        self.cmb_account = QComboBox(); self.cmb_account.setObjectName("cmb_target_invite_link_account")
        if self._account_rows:
            self.cmb_account.addItem("Auto Select Valid Account", -1)
            for mapping in self._account_rows:
                aid = int(getattr(mapping, "account_id", 0) or 0)
                name = getattr(mapping, "account_name", None) or f"Account {aid}"
                username = getattr(mapping, "account_username", None)
                role = str(getattr(mapping, "role", "UNKNOWN") or "UNKNOWN").replace("_", " ").title()
                can_link = bool(getattr(mapping, "can_manage_invite_links", 0))
                label = name + (f"  •  @{username}" if username else "") + f"  •  Role: {role}  •  Link: {'Available' if can_link else 'Unavailable'}"
                self.cmb_account.addItem(label, aid)
            if selected_account_id:
                idx = self.cmb_account.findData(int(selected_account_id))
                if idx >= 0:self.cmb_account.setCurrentIndex(idx)
        else:
            self.cmb_account.addItem("No mapped authorized account", None)
        self.le_name = QLineEdit(f"Member Pool {datetime.now():%b %Y}")
        self.le_name.setObjectName("le_target_invite_link_name")
        self.le_name.setMaxLength(32)
        self.chk_approval = QCheckBox("Require Join Approval")
        self.chk_approval.setObjectName("chk_target_invite_require_approval")
        self.chk_approval.setChecked(True)
        self.chk_expiration = QCheckBox("Set expiration")
        self.chk_expiration.setObjectName("chk_target_invite_expiration")
        self.dt_expiration = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.dt_expiration.setObjectName("dt_target_invite_expiration")
        self.dt_expiration.setDisplayFormat("dd MMM yyyy h:mm AP")
        configure_calendar_popup(self.dt_expiration)
        self.dt_expiration.setEnabled(False)
        self.chk_expiration.toggled.connect(self.dt_expiration.setEnabled)
        self.spin_limit = QSpinBox()
        self.spin_limit.setObjectName("spin_target_invite_usage_limit")
        self.spin_limit.setRange(0, 100000)
        self.spin_limit.setSpecialValueText("No limit")
        self.spin_limit.setValue(0)
        form.addRow("Target", self.lbl_target)
        form.addRow("Authorized Account", self.cmb_account)
        form.addRow("Name", self.le_name)
        form.addRow("", self.chk_approval)
        form.addRow(self.chk_expiration, self.dt_expiration)
        form.addRow("Usage Limit", self.spin_limit)
        root.addLayout(form)
        self.lbl_account_status = QLabel(""); self.lbl_account_status.setWordWrap(True); self.lbl_account_status.setProperty("secondary", True); root.addWidget(self.lbl_account_status)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Link")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.cmb_account.currentIndexChanged.connect(self._update_account_state)
        self.le_name.textChanged.connect(self._update_account_state)
        self.chk_approval.toggled.connect(self._update_account_state)
        self.chk_expiration.toggled.connect(self._update_account_state)
        self.dt_expiration.dateTimeChanged.connect(self._update_account_state)
        self.spin_limit.valueChanged.connect(self._update_account_state)
        root.addWidget(self.buttons)
        self._update_account_state()

    @classmethod
    def _mapping_allowed(cls, mapping) -> bool:
        if mapping is None or not bool(getattr(mapping, "can_manage_invite_links", 0)):
            return False
        access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
        return access not in cls.DENIED_ACCESS

    def _mapping_for_account(self, account_id: int | None):
        if account_id is None:
            return None
        return next(
            (mapping for mapping in self._account_rows if int(getattr(mapping, "account_id", 0) or 0) == int(account_id)),
            None,
        )

    def selected_account_id(self):
        raw = self.cmb_account.currentData()
        if raw is None:
            return None
        if int(raw) != -1:
            mapping = self._mapping_for_account(int(raw))
            return int(raw) if self._mapping_allowed(mapping) else None
        candidates = sorted(
            self._account_rows,
            key=lambda m: (not bool(getattr(m, "is_primary", 0)), int(getattr(m, "id", 0) or 0)),
        )
        for mapping in candidates:
            if self._mapping_allowed(mapping):
                return int(getattr(mapping, "account_id"))
        return None

    def _update_account_state(self):
        account_id = self.selected_account_id()
        issue = None
        if account_id is None:
            issue = "Invite-link permission unavailable. Choose or map an authorized account that can manage invite links for this target."
        elif not self.le_name.text().strip():
            issue = "Enter a name for the invite link."
        elif self.chk_approval.isChecked() and self.spin_limit.value() > 0:
            issue = "Usage Limit cannot be combined with Require Join Approval. Clear the limit or turn approval off."
        elif self.chk_expiration.isChecked() and self.dt_expiration.dateTime() <= QDateTime.currentDateTime().addSecs(60):
            issue = "Expiration must be at least one minute in the future."
        ok = issue is None
        self.lbl_account_status.setText(
            "The selected account will be revalidated immediately before link creation and is used only for this operation."
            if ok else str(issue)
        )
        self.lbl_account_status.setProperty("warning", not ok)
        self.lbl_account_status.style().unpolish(self.lbl_account_status)
        self.lbl_account_status.style().polish(self.lbl_account_status)
        create = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if create is not None:
            create.setEnabled(ok)
            create.setToolTip("" if ok else str(issue))

    def options(self) -> dict:
        expire = self.dt_expiration.dateTime().toPython() if self.chk_expiration.isChecked() else None
        return {
            "account_id": self.selected_account_id(),
            "title": self.le_name.text().strip() or "SP Telegram",
            "request_needed": self.chk_approval.isChecked(),
            "expire_date": expire,
            "usage_limit": self.spin_limit.value() or None,
        }

# Add compatibility attributes for older PySide6 versions
if not hasattr(CreateTargetInviteLinkDialog, 'Accepted'):
    CreateTargetInviteLinkDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CreateTargetInviteLinkDialog, 'Rejected'):
    CreateTargetInviteLinkDialog.Rejected = QDialog.DialogCode.Rejected
