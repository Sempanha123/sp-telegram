from __future__ import annotations
from PySide6.QtWidgets import QComboBox,QDialog,QFormLayout,QLabel,QPushButton,QVBoxLayout,QDialogButtonBox
from app.dialogs.dialog_compat import *
class GroupAccountMappingDialog(QDialog):
    def __init__(self,controller,group,parent=None):
        super().__init__(parent);self.controller=controller;self.group=group;self.result=None;self.setWindowTitle("Add Account To Group");root=QVBoxLayout(self);f=QFormLayout();f.addRow("Group",QLabel(group.title));self.cmb_account=QComboBox()
        accounts=list(controller.available_accounts())
        for a in accounts:self.cmb_account.addItem(f"{a.first_name or a.username or 'Account'} @{a.username or '—'}",a.id)
        if not accounts:self.cmb_account.addItem("No accounts available",None)
        self.lbl_access=QLabel("Not checked");self.lbl_role=QLabel("—");self.lbl_post=QLabel("—");self.lbl_invite=QLabel("—");self.btn_check=QPushButton("Check Access");f.addRow("Account",self.cmb_account);f.addRow("",self.btn_check);f.addRow("Access",self.lbl_access);f.addRow("Role",self.lbl_role);f.addRow("Can Post",self.lbl_post);f.addRow("Can Invite",self.lbl_invite);root.addLayout(f);box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);self.btn_save=box.button(QDialogButtonBox.StandardButton.Save);self.btn_save.setText("Save Mapping");self.btn_save.setEnabled(False);root.addWidget(box);self.btn_check.clicked.connect(self.check);self.btn_save.clicked.connect(self.save);box.rejected.connect(self.reject);self.btn_check.setEnabled(bool(accounts));self.btn_check.setToolTip("Add or connect an authorized Telegram account first." if not accounts else "")
    def check(self):
        aid=self.cmb_account.currentData()
        if aid is None:return
        self.btn_check.setEnabled(False);self.controller.check_account_mapping(self.group.id,int(aid),self._checked,self._check_failed)
    def _checked(self,m):self.result=m;self.btn_check.setEnabled(True);self.btn_save.setEnabled(True);self.lbl_access.setText(m.access_state.replace("_"," ").title());self.lbl_role.setText(m.role.title());self.lbl_post.setText("Unknown" if m.can_post is None else "Yes" if m.can_post else "No");self.lbl_invite.setText("Unknown" if m.can_invite is None else "Yes" if m.can_invite else "No")
    def _check_failed(self,message):self.result=None;self.btn_check.setEnabled(True);self.btn_save.setEnabled(False);self.lbl_access.setText("Check failed — see notification");self.lbl_access.setToolTip(str(message or ""));self.lbl_role.setText("—");self.lbl_post.setText("—");self.lbl_invite.setText("—")
    def save(self):
        if self.result and self.controller.save_account_mapping(self.result):self.accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(GroupAccountMappingDialog, 'Accepted'):
    GroupAccountMappingDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(GroupAccountMappingDialog, 'Rejected'):
    GroupAccountMappingDialog.Rejected = QDialog.DialogCode.Rejected
