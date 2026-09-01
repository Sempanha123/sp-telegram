from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *


class DiagnosticsDialog(QDialog):
    exportRequested = Signal(str)

    def __init__(self, report_text: str, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Diagnostics Center"); self.resize(820, 620)
        root = QVBoxLayout(self); self.txt_report = QPlainTextEdit(report_text); self.txt_report.setReadOnly(True); root.addWidget(self.txt_report, 1)
        row = QHBoxLayout(); row.addStretch()
        self.btn_copy_diagnostics = QPushButton("Copy Diagnostics"); self.btn_copy_diagnostics.setObjectName("btn_copy_diagnostics")
        self.btn_export_diagnostics = QPushButton("Export Diagnostics"); self.btn_export_diagnostics.setObjectName("btn_export_diagnostics")
        close = QPushButton("Close")
        row.addWidget(self.btn_copy_diagnostics); row.addWidget(self.btn_export_diagnostics); row.addWidget(close); root.addLayout(row)
        self.btn_copy_diagnostics.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_report.toPlainText()))
        self.btn_export_diagnostics.clicked.connect(self._export); close.clicked.connect(self.accept)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics", "diagnostics.json", "JSON (*.json);;Text (*.txt)")
        if path: self.exportRequested.emit(path)

# Add compatibility attributes for older PySide6 versions
if not hasattr(DiagnosticsDialog, 'Accepted'):
    DiagnosticsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(DiagnosticsDialog, 'Rejected'):
    DiagnosticsDialog.Rejected = QDialog.DialogCode.Rejected
