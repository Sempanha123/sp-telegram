from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *


class ActivateLicenseDialog(QDialog):
    def __init__(self, device_summary: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Activate License")
        self.setMinimumWidth(440)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(12)

        title = QLabel("Activate SP Telegram")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        desc = QLabel("Enter the license key provided by the trusted license service. The full key is never written to logs or displayed after activation.")
        desc.setWordWrap(True)
        desc.setProperty("secondary", True)
        root.addWidget(desc)

        form = QFormLayout()
        self.le_license_key = QLineEdit()
        self.le_license_key.setObjectName("le_license_key")
        self.le_license_key.setPlaceholderText("SP-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.le_license_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("License Key", self.le_license_key)

        info = device_summary or {}
        name = str(info.get("device_name") or "This Device")
        platform_text = str(info.get("platform") or "")
        masked = str(info.get("masked_device_id") or "")
        device_text = name
        if platform_text:
            device_text += f"  •  {platform_text}"
        if masked:
            device_text += f"  •  {masked}"
        self.lbl_license_device = QLabel(device_text)
        self.lbl_license_device.setObjectName("lbl_license_device")
        self.lbl_license_device.setProperty("secondary", True)
        self.lbl_license_device.setWordWrap(True)
        form.addRow("This Device", self.lbl_license_device)
        root.addLayout(form)

        note = QLabel("Device identity is generated automatically and bound to this installation. Customers never enter or edit a device ID.")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        root.addWidget(note)

        box = QDialogButtonBox()
        self.btn_activate_license_confirm = QPushButton("Activate")
        self.btn_activate_license_confirm.setObjectName("btn_activate_license_confirm")
        self.btn_activate_license_confirm.setProperty("primary", True)
        self.btn_activate_license_cancel = QPushButton("Cancel")
        self.btn_activate_license_cancel.setObjectName("btn_activate_license_cancel")
        box.addButton(self.btn_activate_license_cancel, QDialogButtonBox.ButtonRole.RejectRole)
        box.addButton(self.btn_activate_license_confirm, QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_activate_license_confirm.clicked.connect(self.accept)
        self.btn_activate_license_cancel.clicked.connect(self.reject)
        root.addWidget(box)

    def data(self):
        # Backward-compatible shape: callers still receive (key, device_name),
        # but the name is intentionally None so DeviceManager auto-detects it.
        return self.le_license_key.text().strip(), None

    def accept(self):
        if len(self.le_license_key.text().strip()) < 8:
            self.le_license_key.setFocus()
            return
        super().accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(ActivateLicenseDialog, 'Accepted'):
    ActivateLicenseDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(ActivateLicenseDialog, 'Rejected'):
    ActivateLicenseDialog.Rejected = QDialog.DialogCode.Rejected
