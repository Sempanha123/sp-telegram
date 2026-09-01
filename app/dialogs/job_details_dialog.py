from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QFormLayout
from app.dialogs.dialog_compat import *

from app.utils.formatters import format_local_datetime
from app.utils.helpers import json_loads_safe


class JobDetailsDialog(QDialog):
    def __init__(self, details: dict, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Job Details"); self.resize(780, 560)
        root = QVBoxLayout(self); tabs = QTabWidget(); root.addWidget(tabs, 1)
        job = details.get("job")
        overview = QWidget(); form = QFormLayout(overview)
        if job:
            for label, value in [
                ("Job ID", job.id), ("Type", job.job_type), ("Status", job.status), ("Progress", f"{job.progress}%"),
                ("Account", job.account_id or "—"), ("Group", job.group_id or "—"), ("Campaign", job.campaign_id or "—"),
                ("Started", format_local_datetime(job.started_at)), ("Finished", format_local_datetime(job.finished_at)),
                ("Retry Classification", getattr(job, "retry_classification", "UNKNOWN")), ("Last Error", job.last_error or "—"),
            ]:
                label_widget = QLabel(str(value)); label_widget.setWordWrap(True); form.addRow(label, label_widget)
        tabs.addTab(overview, "Overview")
        attempts = QTableWidget(0, 5); attempts.setHorizontalHeaderLabels(["Attempt", "Started", "Finished", "Status", "Retry"])
        for item in details.get("attempts", []):
            row = attempts.rowCount(); attempts.insertRow(row)
            for col, value in enumerate([item.attempt_number, format_local_datetime(item.started_at), format_local_datetime(item.finished_at), item.status, item.retry_classification]): attempts.setItem(row, col, QTableWidgetItem(str(value)))
        tabs.addTab(attempts, "Attempts")
        items = QTableWidget(0, 5); items.setHorizontalHeaderLabels(["Type", "Item", "Status", "Error", "Started"])
        for item in details.get("items", []):
            row = items.rowCount(); items.insertRow(row)
            for col, value in enumerate([item.get("item_type"), item.get("item_id"), item.get("status"), item.get("error_message") or "—", format_local_datetime(item.get("started_at"))]): items.setItem(row, col, QTableWidgetItem(str(value)))
        tabs.addTab(items, "Items")
        timeline = QPlainTextEdit(); timeline.setReadOnly(True)
        timeline.setPlainText("\n".join(f"{format_local_datetime(i.get('created_at'))}  {i.get('status') or ''}  {i.get('item_type') or ''}" for i in details.get("items", [])) or "No item timeline has been recorded for this job.")
        tabs.addTab(timeline, "Timeline")
        errors = QPlainTextEdit(); errors.setReadOnly(True); errors.setPlainText(job.last_error if job and job.last_error else "No job-level error recorded."); tabs.addTab(errors, "Errors")
        metadata = QPlainTextEdit(); metadata.setReadOnly(True); metadata.setPlainText(str(json_loads_safe(job.metadata_json, {}) if job else {})); tabs.addTab(metadata, "Metadata")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

# Add compatibility attributes for older PySide6 versions
if not hasattr(JobDetailsDialog, 'Accepted'):
    JobDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(JobDetailsDialog, 'Rejected'):
    JobDetailsDialog.Rejected = QDialog.DialogCode.Rejected
