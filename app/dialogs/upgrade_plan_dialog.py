from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog,QHBoxLayout,QLabel,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *
from app.license.plan_config import PLAN_CONFIG
from app.license.license_models import PlanKey
class UpgradePlanDialog(QDialog):
    viewPlansRequested=Signal()
    def __init__(self,current_plan=None,feature_name='This feature',required_plan='PRO',usage_warning=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Upgrade Plan');self.setMinimumWidth(500);root=QVBoxLayout(self);root.setContentsMargins(24,24,24,24);root.setSpacing(12);title=QLabel(f'{feature_name} requires a different plan');title.setProperty('dialogTitle',True);root.addWidget(title);req=PlanKey(str(required_plan)) if str(required_plan) in PlanKey.__members__ else PlanKey.PRO;cfg=PLAN_CONFIG[req];ultimate=PLAN_CONFIG[PlanKey.ULTIMATE];desc=QLabel(f"Current plan: {current_plan or 'No active license'}\n\nAvailable with {cfg['name']} — ${cfg['price_monthly']}/month or {ultimate['name']} — ${ultimate['price_monthly']}/month.\n\nYour existing local data will not be deleted if you change plans.");desc.setWordWrap(True);desc.setProperty('secondary',True);root.addWidget(desc)
        if usage_warning:
            warn=QLabel(usage_warning);warn.setWordWrap(True);warn.setProperty('warning',True);root.addWidget(warn)
        row=QHBoxLayout();row.addStretch();self.btn_upgrade_cancel=QPushButton('Cancel');self.btn_upgrade_cancel.setObjectName('btn_upgrade_cancel');self.btn_upgrade_view_plans=QPushButton('View Plans');self.btn_upgrade_view_plans.setObjectName('btn_upgrade_view_plans');self.btn_upgrade_view_plans.setProperty('primary',True);row.addWidget(self.btn_upgrade_cancel);row.addWidget(self.btn_upgrade_view_plans);root.addLayout(row);self.btn_upgrade_cancel.clicked.connect(self.reject);self.btn_upgrade_view_plans.clicked.connect(lambda:(self.viewPlansRequested.emit(),self.accept()))

# Add compatibility attributes for older PySide6 versions
if not hasattr(UpgradePlanDialog, 'Accepted'):
    UpgradePlanDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(UpgradePlanDialog, 'Rejected'):
    UpgradePlanDialog.Rejected = QDialog.DialogCode.Rejected
