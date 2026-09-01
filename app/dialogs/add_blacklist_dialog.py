from __future__ import annotations
from PySide6.QtWidgets import QComboBox,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QTextEdit,QVBoxLayout
from app.dialogs.dialog_compat import *

class AddBlacklistDialog(QDialog):
    def __init__(self,controller,parent=None,telegram_user_id:int|None=None):
        super().__init__(parent);self.controller=controller;self.setWindowTitle("Add Member Exclusion");self.resize(520,360);root=QVBoxLayout(self);form=QFormLayout()
        self.le_blacklist_member=QLineEdit(str(telegram_user_id or ""));self.le_blacklist_member.setObjectName("le_blacklist_member");self.cmb_blacklist_type=QComboBox();self.cmb_blacklist_type.setObjectName("cmb_blacklist_type");self.cmb_blacklist_type.addItems(["GLOBAL_BLACKLIST","DO_NOT_CONTACT","TARGET_EXCLUSION","PRIVACY_RESTRICTED","INVALID_USER","DELETED_ACCOUNT","BOT","MANUAL_EXCLUSION"]);self.cmb_blacklist_target=QComboBox();self.cmb_blacklist_target.setObjectName("cmb_blacklist_target");self.cmb_blacklist_target.addItem("None",None)
        for g in controller.service.targets():self.cmb_blacklist_target.addItem(g.title,g.id)
        self.le_blacklist_reason=QLineEdit();self.le_blacklist_reason.setObjectName("le_blacklist_reason");self.txt_blacklist_notes=QTextEdit();self.txt_blacklist_notes.setObjectName("txt_blacklist_notes");form.addRow("Telegram User ID",self.le_blacklist_member);form.addRow("Exclusion Type",self.cmb_blacklist_type);form.addRow("Target",self.cmb_blacklist_target);form.addRow("Reason",self.le_blacklist_reason);form.addRow("Notes",self.txt_blacklist_notes);root.addLayout(form)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);self.btn_blacklist_save=box.button(QDialogButtonBox.StandardButton.Save);self.btn_blacklist_save.setObjectName("btn_blacklist_save");self.btn_blacklist_cancel=box.button(QDialogButtonBox.StandardButton.Cancel);self.btn_blacklist_cancel.setObjectName("btn_blacklist_cancel");root.addWidget(box);box.accepted.connect(self.save);box.rejected.connect(self.reject);self.cmb_blacklist_type.currentTextChanged.connect(self._state);self._state()
    def _state(self):self.cmb_blacklist_target.setEnabled(self.cmb_blacklist_type.currentText()=="TARGET_EXCLUSION")
    def save(self):
        try:tg=int(self.le_blacklist_member.text().strip())
        except ValueError:self.le_blacklist_member.setFocus();return
        kind=self.cmb_blacklist_type.currentText();target=self.cmb_blacklist_target.currentData() if kind=="TARGET_EXCLUSION" else None
        if kind=="TARGET_EXCLUSION" and not target:return
        if self.controller.add_by_telegram_id(tg,self.le_blacklist_reason.text().strip() or None,kind,target,self.txt_blacklist_notes.toPlainText().strip() or None):self.accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(AddBlacklistDialog, 'Accepted'):
    AddBlacklistDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AddBlacklistDialog, 'Rejected'):
    AddBlacklistDialog.Rejected = QDialog.DialogCode.Rejected
