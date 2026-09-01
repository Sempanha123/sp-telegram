from __future__ import annotations
from PySide6.QtWidgets import QDialog,QFormLayout,QHBoxLayout,QLabel,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *
class LicenseDetailsDialog(QDialog):
    def __init__(self,summary,parent=None):
        super().__init__(parent);self.setWindowTitle('License Details');self.setMinimumWidth(460);root=QVBoxLayout(self);root.setContentsMargins(22,22,22,22);root.setSpacing(12);title=QLabel('License Details');title.setProperty('dialogTitle',True);root.addWidget(title);form=QFormLayout();s=summary.state
        for label,value in [('Plan',summary.plan_name),('Status',str(s.status).replace('_',' ').title()),('Price',f"${summary.price_monthly} / month" if summary.price_monthly is not None else '—'),('Expires',s.expires_at or '—'),('Last Verified',s.last_validated_at or 'Never'),('License Key',s.license_key_masked or '—'),('Device',s.device_name or '—')]:form.addRow(label,QLabel(str(value)))
        root.addLayout(form);actions=QHBoxLayout();actions.addStretch();self.btn_license_details_close=QPushButton('Close');self.btn_license_details_close.setObjectName('btn_license_details_close');self.btn_license_details_close.clicked.connect(self.accept);actions.addWidget(self.btn_license_details_close);root.addLayout(actions)

# Add compatibility attributes for older PySide6 versions
if not hasattr(LicenseDetailsDialog, 'Accepted'):
    LicenseDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(LicenseDetailsDialog, 'Rejected'):
    LicenseDetailsDialog.Rejected = QDialog.DialogCode.Rejected
