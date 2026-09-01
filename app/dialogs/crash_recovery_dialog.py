from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QTextEdit
from app.dialogs.dialog_compat import *

from app.utils.formatters import format_local_datetime


class CrashRecoveryDialog(QDialog):
    """Modal dialog shown when SP Telegram recovers from an unclean shutdown."""

    def __init__(self, report: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SP Telegram — Crash Recovery")
        self.setModal(True)
        self.resize(600, 480)

        root = QVBoxLayout(self)

        # Header
        header = QLabel(
            "<b>SP Telegram recovered from an interrupted session.</b><br/>"
            "Some background jobs may have been interrupted and need your review."
        )
        header.setWordWrap(True)
        root.addWidget(header)

        # Details form
        form = QFormLayout()
        root.addLayout(form)

        interrupted = report.get("interrupted", 0)
        reconcile = report.get("reconcile_required", 0)
        total = interrupted + reconcile

        values = [
            ("Total Affected Jobs", str(total)),
            ("Interrupted (auto-restart attempted)", str(interrupted)),
            ("Require Manual Review", str(reconcile)),
        ]

        for label, value in values:
            widget = QLabel(value)
            widget.setTextInteractionFlags(widget.textInteractionFlags())
            form.addRow(label, widget)

        # Explanation
        explanation = QTextEdit()
        explanation.setReadOnly(True)
        explanation.setMaximumHeight(150)
        explanation.setPlainText(
            "What happened:\n"
            "The application was closed unexpectedly (crash, force-quit, or system shutdown)\n"
            "while background jobs were running. SP Telegram automatically attempts to\n"
            "recover interrupted jobs, but some may be in an uncertain state.\n\n"
            "What you should do:\n"
            "1. Open the Jobs page to see the affected jobs.\n"
            f"2. Jobs marked 'RECONCILE_REQUIRED' ({reconcile}) need manual review — "
            "check if their operations actually completed on Telegram.\n"
            f"3. Jobs marked 'INTERRUPTED' ({interrupted}) were auto-restarted — verify "
            "their progress and results.\n"
            "4. Use the 'Retry' action on any job that failed or is incomplete.\n"
            "5. Once reviewed, you can safely continue normal operations."
        )
        root.addWidget(explanation)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        root.addWidget(buttons)
# Add compatibility attributes for older PySide6 versions
if not hasattr(CrashRecoveryDialog, 'Accepted'):
    CrashRecoveryDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CrashRecoveryDialog, 'Rejected'):
    CrashRecoveryDialog.Rejected = QDialog.DialogCode.Rejected
