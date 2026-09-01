from __future__ import annotations

from PySide6.QtWidgets import QCheckBox,QDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *


class ClearEntireMemberPoolDialog(QDialog):
    def __init__(self,count:int,parent=None):
        super().__init__(parent);self.setObjectName("dlg_clear_member_pool");self.setWindowTitle("Clear Entire Member Pool - SP Telegram");self.setMinimumWidth(520)
        root=QVBoxLayout(self);root.setContentsMargins(20,20,20,20);root.setSpacing(12)
        title=QLabel("Clear Entire Member Pool?");title.setProperty("dialogTitle",True);root.addWidget(title)
        text=QLabel(f"Members: {int(count):,}\n\nThis removes local Member Pool records. It does NOT remove Telegram users from groups, delete Telegram accounts, or log out Telegram sessions.");text.setWordWrap(True);root.addWidget(text)
        self.chk_preserve_exclusions=QCheckBox("Preserve Global Blacklist / Do Not Contact Entries");self.chk_preserve_exclusions.setChecked(True);self.chk_preserve_exclusions.setObjectName("chk_clear_preserve_exclusions")
        self.chk_preserve_audit=QCheckBox("Preserve Audit History");self.chk_preserve_audit.setChecked(True);self.chk_preserve_audit.setObjectName("chk_clear_preserve_audit")
        root.addWidget(self.chk_preserve_exclusions);root.addWidget(self.chk_preserve_audit)
        form=QFormLayout();self.le_confirm=QLineEdit();self.le_confirm.setObjectName("le_clear_member_pool_confirm");self.le_confirm.setPlaceholderText("Type CLEAR");form.addRow("Confirmation",self.le_confirm);root.addLayout(form)
        bar=QHBoxLayout();bar.addStretch();self.btn_cancel=QPushButton("Cancel");self.btn_clear=QPushButton("Clear Member Pool");self.btn_clear.setObjectName("btn_confirm_clear_member_pool");self.btn_clear.setProperty("danger",True);self.btn_clear.setEnabled(False);bar.addWidget(self.btn_cancel);bar.addWidget(self.btn_clear);root.addLayout(bar)
        self.le_confirm.textChanged.connect(lambda text:self.btn_clear.setEnabled(text.strip()=="CLEAR"));self.btn_cancel.clicked.connect(self.reject);self.btn_clear.clicked.connect(self.accept)

# Add compatibility attributes for older PySide6 versions
if not hasattr(ClearEntireMemberPoolDialog, 'Accepted'):
    ClearEntireMemberPoolDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(ClearEntireMemberPoolDialog, 'Rejected'):
    ClearEntireMemberPoolDialog.Rejected = QDialog.DialogCode.Rejected
