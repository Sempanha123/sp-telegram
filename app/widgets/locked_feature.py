from __future__ import annotations
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QPushButton,QSizePolicy,QVBoxLayout
from app.icons import IconManager
from app.widgets.plan_badge import PlanBadge
class LockedFeatureWidget(QFrame):
    upgradeRequested=Signal(str)
    def __init__(self,title='Feature Locked',description='',required_plan='PRO',feature_list=None,parent=None):
        super().__init__(parent);self.setObjectName('locked_feature_widget');self.setProperty('lockedFeature',True);self.required_plan=required_plan
        # Keep the upgrade notice compact and anchored below the page header.
        # A Maximum vertical policy is important when the licensed page body is
        # hidden because there is otherwise no expanding table to consume space.
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum);self.setMaximumHeight(320)
        root=QVBoxLayout(self);root.setContentsMargins(24,22,24,22);root.setSpacing(10);root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon=QLabel();IconManager.bind_label(icon,'lock',30);icon.setAlignment(Qt.AlignmentFlag.AlignCenter);root.addWidget(icon)
        row=QHBoxLayout();row.addStretch();name=QLabel(title);name.setProperty('lockedTitle',True);row.addWidget(name);row.addWidget(PlanBadge(required_plan));row.addStretch();root.addLayout(row)
        desc=QLabel(description);desc.setWordWrap(True);desc.setAlignment(Qt.AlignmentFlag.AlignCenter);desc.setProperty('secondary',True);desc.setMaximumWidth(520);root.addWidget(desc)
        if feature_list:
            feats=QLabel('\n'.join(f'• {x}' for x in feature_list));feats.setProperty('secondary',True);feats.setAlignment(Qt.AlignmentFlag.AlignLeft);root.addWidget(feats,0,Qt.AlignmentFlag.AlignCenter)
        self.btn_upgrade_feature=QPushButton(f'View {required_plan.title()} Plan');self.btn_upgrade_feature.setObjectName('btn_upgrade_feature');self.btn_upgrade_feature.setProperty('primary',True);self.btn_upgrade_feature.clicked.connect(lambda:self.upgradeRequested.emit(required_plan));root.addWidget(self.btn_upgrade_feature,0,Qt.AlignmentFlag.AlignCenter)
