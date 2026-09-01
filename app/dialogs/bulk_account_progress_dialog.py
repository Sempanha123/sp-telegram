from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class BulkAccountProgressDialog(QDialog):
    """Progress UI for safe account-management operations only.

    This dialog is intentionally limited to connect/disconnect/health/profile
    operations. It is not used for message sending, invitations, or account
    rotation after Telegram restrictions.
    """

    def __init__(self, controller, operation_name: str, total: int, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Processing Accounts")
        self.setModal(False)
        self.setMinimumWidth(430)
        self._finished = False

        root = QVBoxLayout(self)
        title = QLabel(f"{operation_name} Accounts")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)

        self.progress_bulk_accounts = QProgressBar()
        self.progress_bulk_accounts.setObjectName("progress_bulk_accounts")
        self.progress_bulk_accounts.setRange(0, max(1, total))
        root.addWidget(self.progress_bulk_accounts)

        self.lbl_bulk_current_account = QLabel("Preparing…")
        self.lbl_bulk_current_account.setObjectName("lbl_bulk_current_account")
        root.addWidget(self.lbl_bulk_current_account)

        stats = QHBoxLayout()
        self.lbl_bulk_success = QLabel("Success: 0")
        self.lbl_bulk_success.setObjectName("lbl_bulk_success")
        self.lbl_bulk_failed = QLabel("Failed: 0")
        self.lbl_bulk_failed.setObjectName("lbl_bulk_failed")
        stats.addWidget(self.lbl_bulk_success)
        stats.addWidget(self.lbl_bulk_failed)
        stats.addStretch()
        root.addLayout(stats)

        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_cancel_bulk_account_operation = QPushButton("Cancel")
        self.btn_cancel_bulk_account_operation.setObjectName("btn_cancel_bulk_account_operation")
        self.btn_cancel_bulk_account_operation.clicked.connect(self._cancel)
        actions.addWidget(self.btn_cancel_bulk_account_operation)
        root.addLayout(actions)

        controller.bulkProgress.connect(self._on_progress)
        controller.bulkFinished.connect(self._on_finished)

    def _on_progress(self, completed: int, total: int, success: int, failed: int, current: str) -> None:
        self.progress_bulk_accounts.setMaximum(max(1, total))
        self.progress_bulk_accounts.setValue(completed)
        self.lbl_bulk_success.setText(f"Success: {success}")
        self.lbl_bulk_failed.setText(f"Failed: {failed}")
        self.lbl_bulk_current_account.setText(current or "Processing…")

    def _on_finished(self, success: int, failed: int, cancelled: bool) -> None:
        self._finished = True
        self.btn_cancel_bulk_account_operation.setText("Close")
        self.lbl_bulk_current_account.setText("Cancelled" if cancelled else "Completed")

    def _cancel(self) -> None:
        if self._finished:
            self.close()
            return
        self.controller.cancel_bulk_account_operation()
        self.btn_cancel_bulk_account_operation.setEnabled(False)
        self.lbl_bulk_current_account.setText("Cancelling after the current safe operation…")

    def closeEvent(self, event) -> None:
        if not self._finished:
            # Closing the progress window has the same safe cancellation semantics:
            # no new account operation is scheduled; the current one may finish.
            self.controller.cancel_bulk_account_operation()
        super().closeEvent(event)

# Add compatibility attributes for older PySide6 versions
if not hasattr(BulkAccountProgressDialog, 'Accepted'):
    BulkAccountProgressDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(BulkAccountProgressDialog, 'Rejected'):
    BulkAccountProgressDialog.Rejected = QDialog.DialogCode.Rejected
