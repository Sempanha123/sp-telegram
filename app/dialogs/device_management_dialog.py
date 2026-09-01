from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout
from app.dialogs.dialog_compat import *
class DeviceManagementDialog(QDialog):
    deactivateRequested=Signal(str)
    def __init__(self,devices=None,parent=None):
        super().__init__(parent);self.setWindowTitle('License Devices');self.resize(680,380);root=QVBoxLayout(self);root.setContentsMargins(22,22,22,22);root.setSpacing(12);title=QLabel('Activated Devices');title.setProperty('dialogTitle',True);root.addWidget(title);self.tbl_license_devices=QTableWidget(0,5);self.tbl_license_devices.setObjectName('tbl_license_devices');self.tbl_license_devices.setHorizontalHeaderLabels(['Device','Platform','Current','Last Active','Status']);self.tbl_license_devices.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);root.addWidget(self.tbl_license_devices,1);row=QHBoxLayout();self.btn_deactivate_device=QPushButton('Deactivate');self.btn_deactivate_device.setObjectName('btn_deactivate_device');self.btn_deactivate_device.setProperty('danger',True);self.btn_license_devices_close=QPushButton('Close');self.btn_license_devices_close.setObjectName('btn_license_devices_close');row.addWidget(self.btn_deactivate_device);row.addStretch();row.addWidget(self.btn_license_devices_close);root.addLayout(row);self.btn_deactivate_device.clicked.connect(self._deactivate);self.btn_license_devices_close.clicked.connect(self.accept);self.set_devices(devices or [])
    def set_devices(self,devices):
        self._devices=list(devices);self.tbl_license_devices.setRowCount(len(self._devices))
        for r,d in enumerate(self._devices):
            vals=[d.device_name,d.platform,'Yes' if d.is_current else 'No',d.last_seen_at or '—','Active' if d.is_active else 'Inactive']
            for c,v in enumerate(vals):self.tbl_license_devices.setItem(r,c,QTableWidgetItem(str(v)))
        self.tbl_license_devices.horizontalHeader().setStretchLastSection(True)
    def _deactivate(self):
        row=self.tbl_license_devices.currentRow()
        if row<0:return
        d=self._devices[row]
        warning=f"Deactivate Device?\n\n{d.device_name}\n\nThis device will need to activate the license again before licensed features can be used. Telegram account sessions are separate and will not be deleted or logged out."
        if QMessageBox.question(self,'Deactivate Device',warning,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.deactivateRequested.emit(d.device_id);self.accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(DeviceManagementDialog, 'Accepted'):
    DeviceManagementDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(DeviceManagementDialog, 'Rejected'):
    DeviceManagementDialog.Rejected = QDialog.DialogCode.Rejected
