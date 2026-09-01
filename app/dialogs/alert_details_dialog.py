from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout
from app.dialogs.dialog_compat import *

from app.utils.formatters import format_local_datetime


class AlertDetailsDialog(QDialog):
    def __init__(self, alert: dict, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Alert Details"); self.resize(560, 480)
        root = QVBoxLayout(self); form = QFormLayout(); root.addLayout(form)
        values = [
            ("Title", alert.get("title") or "—"), ("Severity", alert.get("severity") or "—"),
            ("Source", f"{alert.get('source_type') or 'System'} {alert.get('source_id') or ''}".strip()),
            ("First Seen", format_local_datetime(alert.get("first_seen_at") or alert.get("created_at"))),
            ("Last Seen", format_local_datetime(alert.get("last_seen_at") or alert.get("created_at"))),
            ("Occurrences", alert.get("occurrence_count") or 1), ("Status", alert.get("status") or "OPEN"),
            ("Description", alert.get("message") or "—"), ("Suggested Action", (alert.get("action_type") or "No explicit action").replace("_", " ").title()),
            ("Related Account", alert.get("account_id") or "—"), ("Related Group", alert.get("group_id") or "—"),
            ("Related Campaign", alert.get("campaign_id") or "—"), ("Related Job", alert.get("job_id") or "—"),
        ]
        for label, value in values:
            widget = QLabel(str(value)); widget.setWordWrap(True); widget.setTextInteractionFlags(widget.textInteractionFlags()); form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

# Add compatibility attributes for older PySide6 versions
if not hasattr(AlertDetailsDialog, 'Accepted'):
    AlertDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AlertDetailsDialog, 'Rejected'):
    AlertDetailsDialog.Rejected = QDialog.DialogCode.Rejected
