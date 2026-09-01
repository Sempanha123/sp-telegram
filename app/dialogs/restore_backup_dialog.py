from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)


class RestoreBackupDialog(QDialog):
    """Conservative local restore wizard.

    Validation and the actual restore run outside the UI thread through
    OperationsController. This dialog only collects and confirms a backup folder.
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Restore Backup")
        self.resize(620, 420)
        self._validated: dict | None = None

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        select = QWidget(); form = QFormLayout(select)
        self.le_backup_folder = QLineEdit(); self.le_backup_folder.setReadOnly(True)
        self.btn_select_backup = QPushButton("Select Backup…")
        self.btn_select_backup.clicked.connect(self._select)
        form.addRow("Backup Folder", self.le_backup_folder)
        form.addRow("", self.btn_select_backup)
        self.tabs.addTab(select, "1. Select")

        validate = QWidget(); v = QVBoxLayout(validate)
        self.lbl_validation = QLabel("Select a backup, then validate its manifest, checksum, and SQLite database.")
        self.lbl_validation.setWordWrap(True)
        self.btn_validate_backup = QPushButton("Validate Backup")
        self.btn_validate_backup.clicked.connect(self._validate)
        v.addWidget(self.lbl_validation); v.addWidget(self.btn_validate_backup); v.addStretch()
        self.tabs.addTab(validate, "2. Validate")

        contents = QWidget(); c = QVBoxLayout(contents)
        self.lbl_contents = QLabel("No validated backup selected.")
        self.lbl_contents.setWordWrap(True)
        c.addWidget(self.lbl_contents); c.addStretch()
        self.tabs.addTab(contents, "3. Contents")

        confirm = QWidget(); x = QVBoxLayout(confirm)
        notice = QLabel(
            "Restoring pauses operations, creates a safety backup of the current database, "
            "validates the selected backup, restores it, and then re-runs migrations if needed.\n\n"
            "Telegram .session authorization files are not part of normal backups and are not replaced."
        )
        notice.setWordWrap(True); x.addWidget(notice); x.addStretch()
        self.tabs.addTab(confirm, "4. Confirm")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.btn_restore = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_restore.setText("Restore")
        self.btn_restore.setEnabled(False)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept_restore)
        root.addWidget(buttons)

        controller.maintenanceCompleted.connect(self._maintenance_result)

    @property
    def backup_folder(self) -> str:
        return self.le_backup_folder.text().strip()

    def _select(self):
        folder = QFileDialog.getExistingDirectory(self, "Select SP Telegram Backup")
        if not folder:
            return
        self.le_backup_folder.setText(folder)
        self._validated = None
        self.btn_restore.setEnabled(False)
        self.lbl_validation.setText("Backup selected. Run validation before restore.")
        self.lbl_contents.setText("Pending validation.")
        self.tabs.setCurrentIndex(1)

    def _validate(self):
        if not self.backup_folder:
            QMessageBox.warning(self, "Restore Backup", "Select a backup folder first.")
            return
        self.btn_validate_backup.setEnabled(False)
        self.lbl_validation.setText("Validating backup…")
        token = self.controller.verify_backup(self.backup_folder)
        if not token:
            self.btn_validate_backup.setEnabled(True)

    def _maintenance_result(self, kind: str, result):
        if kind != "verify_backup":
            return
        self.btn_validate_backup.setEnabled(True)
        self._validated = dict(result or {})
        valid = bool(self._validated.get("ok", False))
        if valid:
            manifest = self._validated.get("manifest") or {}
            schema = manifest.get("schema_version", "Unknown")
            created = manifest.get("created_at", "Unknown")
            files = manifest.get("files") or {}
            self.lbl_validation.setText("Backup validation passed.")
            self.lbl_contents.setText(
                f"Created: {created}\nSchema: {schema}\nFiles: {', '.join(files) if isinstance(files, dict) else 'database/settings/manifest'}\n"
                "Telegram sessions: Excluded"
            )
            self.btn_restore.setEnabled(True)
            self.tabs.setCurrentIndex(2)
        else:
            self.lbl_validation.setText("Backup validation failed. Restore is blocked.")
            self.btn_restore.setEnabled(False)

    def _accept_restore(self):
        if not self._validated or not self._validated.get("ok"):
            QMessageBox.warning(self, "Restore Backup", "Validate the backup before restoring it.")
            return
        if QMessageBox.question(
            self,
            "Confirm Restore",
            "Restore this backup?\n\nA safety backup of the current database will be created first. "
            "Active operations will be paused during restore.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(RestoreBackupDialog, 'Accepted'):
    RestoreBackupDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(RestoreBackupDialog, 'Rejected'):
    RestoreBackupDialog.Rejected = QDialog.DialogCode.Rejected
