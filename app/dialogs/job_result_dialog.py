"""Job final result screen (AI2_PROMPT section 9).

Shows a clear summary when a member/operation job finishes:
    JOB COMPLETED WITH WARNINGS
    120 attempted / 108 verified / 5 unverified / 4 failed / 3 skipped

Actions: View Results, Retry Failed, View Unverified, Open Details,
Delete History.  API success is never counted as verified success — only
items that were actually verified are reported as verified.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from app.utils.formatters import format_local_datetime


class JobResultDialog(QDialog):
    retryRequested = Signal(int)
    deleteRequested = Signal(int)

    def __init__(self, job, items: list | None = None, parent=None):
        super().__init__(parent)
        self.job = job
        self.items = items or []
        self.setWindowTitle(f"Job #{job.id} — Result")
        self.resize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        # -- Status banner -------------------------------------------------
        job_status = str(job.status or "UNKNOWN").upper()
        failed = int(job.failed_count or 0)
        skipped = int(job.skipped_count or 0)
        if job_status == "COMPLETED" and (failed or skipped):
            headline = "JOB COMPLETED WITH WARNINGS"
            tone = "warning"
        elif job_status == "COMPLETED":
            headline = "JOB COMPLETED"
            tone = "success"
        elif job_status == "FAILED":
            headline = "JOB FAILED"
            tone = "danger"
        elif job_status == "PARTIAL_SUCCESS":
            headline = "JOB PARTIALLY COMPLETED"
            tone = "warning"
        else:
            headline = f"JOB {job_status.replace('_', ' ')}"
            tone = "muted"

        banner = QFrame()
        banner.setProperty("resultBanner", True)
        banner.setProperty("tone", tone)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(20, 18, 20, 18)
        bl.setSpacing(4)
        self.lbl_headline = QLabel(headline)
        self.lbl_headline.setProperty("resultHeadline", True)
        self.lbl_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(self.lbl_headline)
        sub = QLabel(f"{job.job_type}  ·  finished {format_local_datetime(job.finished_at)}")
        sub.setProperty("resultSub", True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(sub)
        root.addWidget(banner)

        # -- Counts grid ---------------------------------------------------
        attempted = int(job.total_items or 0)
        verified = int(job.success_count or 0)
        unverified = max(0, attempted - verified - failed - skipped)
        counts = [
            ("Attempted", attempted, "primary"),
            ("Verified", verified, "success"),
            ("Unverified", unverified, "warning"),
            ("Failed", failed, "danger"),
            ("Skipped", skipped, "muted"),
        ]
        grid = QHBoxLayout()
        grid.setSpacing(10)
        for label, value, tone in counts:
            cell = QFrame()
            cell.setProperty("resultCell", True)
            cell.setProperty("tone", tone)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(8, 12, 8, 12)
            cl.setSpacing(2)
            val = QLabel(f"{value:,}")
            val.setProperty("resultValue", True)
            val.setProperty("tone", tone)
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(val)
            lab = QLabel(label)
            lab.setProperty("resultLabel", True)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(lab)
            grid.addWidget(cell, 1)
        root.addLayout(grid)

        # -- Item preview --------------------------------------------------
        preview = QLabel()
        preview.setProperty("resultPreview", True)
        preview.setWordWrap(True)
        preview.setMinimumHeight(90)
        preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lines = []
        for item in self.items[:8]:
            status = str(item.get("status") or "—")
            marker = {"VERIFIED": "✓", "SUCCESS": "✓", "SENT": "✓", "FAILED": "✗", "SKIPPED": "⏭"}.get(status.upper(), "→")
            name = item.get("item_id") or item.get("item_type") or "—"
            lines.append(f"{marker}  {name}  ·  {status}")
        preview.setText("\n".join(lines) if lines else "No item-level results recorded for this job.")
        root.addWidget(preview, 1)

        # -- Actions -------------------------------------------------------
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_view_results = QPushButton("View Results")
        self.btn_retry_failed = QPushButton("Retry Failed")
        self.btn_view_unverified = QPushButton("View Unverified")
        self.btn_open_details = QPushButton("Open Details")
        self.btn_delete_history = QPushButton("Delete History")
        self.btn_delete_history.setProperty("danger", True)
        for b in (self.btn_view_results, self.btn_retry_failed, self.btn_view_unverified, self.btn_open_details, self.btn_delete_history):
            actions.addWidget(b)
        actions.addStretch()
        root.addLayout(actions)

        self.btn_view_results.clicked.connect(self._view_results)
        self.btn_retry_failed.clicked.connect(lambda: self.retryRequested.emit(int(job.id)))
        self.btn_view_unverified.clicked.connect(self._view_unverified)
        self.btn_delete_history.clicked.connect(lambda: self.deleteRequested.emit(int(job.id)))
        self.btn_open_details.clicked.connect(self.accept)

        # Retry only makes sense for failed/partial jobs.
        self.btn_retry_failed.setEnabled(job_status in {"FAILED", "PARTIAL_SUCCESS", "INTERRUPTED", "RECONCILE_REQUIRED"})

    def _view_results(self) -> None:
        self._show_items("Recorded Job Results", self.items)

    def _view_unverified(self) -> None:
        verified = {"VERIFIED", "SUCCESS", "SENT"}
        self._show_items(
            "Unverified Job Results",
            [
                item
                for item in self.items
                if str(item.get("status") or "").upper() not in verified
            ],
        )

    def _show_items(self, title: str, items: list[dict]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(660, 460)
        layout = QVBoxLayout(dialog)
        output = QPlainTextEdit(dialog)
        output.setReadOnly(True)
        lines = [
            "  ·  ".join(
                part
                for part in (
                    str(item.get("item_id") or item.get("item_type") or "—"),
                    str(item.get("status") or "UNKNOWN"),
                    str(item.get("error_message") or "").strip(),
                )
                if part
            )
            for item in items
        ]
        output.setPlainText("\n".join(lines) if lines else "No matching item-level results were recorded.")
        layout.addWidget(output, 1)
        close = QPushButton("Close", dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

# Add compatibility attributes for older PySide6 versions
if not hasattr(JobResultDialog, 'Accepted'):
    JobResultDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(JobResultDialog, 'Rejected'):
    JobResultDialog.Rejected = QDialog.DialogCode.Rejected
