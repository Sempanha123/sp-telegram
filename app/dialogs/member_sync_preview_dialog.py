from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout
from app.dialogs.dialog_compat import *


class MemberSyncPreviewDialog(QDialog):
    """Read-only confirmation for an authorized member synchronization."""

    def __init__(self, *, source: str, account: str, access: str, existing_pool: int,
                 plan: str, limit: int | None, remaining: int | None, options: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("dlg_member_sync_preview")
        self.setWindowTitle("Member Sync Preview - SP Telegram")
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        title = QLabel("Member Sync Preview")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        subtitle = QLabel("Review the authorized source, account and local plan capacity before starting.")
        subtitle.setWordWrap(True)
        subtitle.setProperty("secondary", True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(9)
        form.addRow("Source", QLabel(source))
        form.addRow("Account", QLabel(account))
        form.addRow("Participant Access", QLabel(access))
        form.addRow("Existing Pool", QLabel(f"{existing_pool:,}"))
        form.addRow("Plan", QLabel(plan.title()))
        capacity = "Unlimited" if limit is None else f"{max(0, int(remaining or 0)):,} remaining of {int(limit):,}"
        form.addRow("Capacity", QLabel(capacity))
        root.addLayout(form)

        opts = QLabel("\n".join(f"✓ {text}" for text in options) or "No optional filters enabled")
        opts.setWordWrap(True)
        opts.setProperty("secondary", True)
        root.addWidget(opts)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Member Sync")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

# Add compatibility attributes for older PySide6 versions
if not hasattr(MemberSyncPreviewDialog, 'Accepted'):
    MemberSyncPreviewDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(MemberSyncPreviewDialog, 'Rejected'):
    MemberSyncPreviewDialog.Rejected = QDialog.DialogCode.Rejected
