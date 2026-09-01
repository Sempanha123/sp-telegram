from __future__ import annotations
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QLabel,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *

class ConfirmationDialog(QDialog):
    def __init__(self,title:str,message:str,parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.setMinimumWidth(430)
        layout=QVBoxLayout(self); lbl=QLabel(message); lbl.setWordWrap(True); layout.addWidget(lbl)
        box=QDialogButtonBox(); self.btn_cancel=box.addButton("Cancel",QDialogButtonBox.ButtonRole.RejectRole); self.btn_cancel.setObjectName("btn_cancel_confirmation"); self.btn_confirm=box.addButton("Confirm",QDialogButtonBox.ButtonRole.AcceptRole); self.btn_confirm.setObjectName("btn_confirm_confirmation"); self.btn_confirm.setProperty("danger",True); box.rejected.connect(self.reject); box.accepted.connect(self.accept); layout.addWidget(box)

# Add compatibility attributes for older PySide6 versions
if not hasattr(ConfirmationDialog, 'Accepted'):
    ConfirmationDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(ConfirmationDialog, 'Rejected'):
    ConfirmationDialog.Rejected = QDialog.DialogCode.Rejected
