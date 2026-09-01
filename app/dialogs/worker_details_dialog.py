from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout
from app.dialogs.dialog_compat import *

from app.utils.formatters import format_local_datetime


class WorkerDetailsDialog(QDialog):
    def __init__(self, worker, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Worker Details"); self.resize(460, 340)
        root = QVBoxLayout(self); form = QFormLayout(); root.addLayout(form)
        values = [
            ("Name", worker.name), ("State", worker.state), ("Started At", format_local_datetime(worker.started_at)),
            ("Last Heartbeat", format_local_datetime(worker.last_heartbeat_at)), ("Tasks Processed", str(worker.tasks_processed)),
            ("Last Error", worker.last_error or "—"), ("Restart Count", str(worker.restart_count)),
        ]
        for label, value in values:
            widget = QLabel(str(value)); widget.setWordWrap(True); form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

# Add compatibility attributes for older PySide6 versions
if not hasattr(WorkerDetailsDialog, 'Accepted'):
    WorkerDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(WorkerDetailsDialog, 'Rejected'):
    WorkerDetailsDialog.Rejected = QDialog.DialogCode.Rejected
