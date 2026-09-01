from __future__ import annotations
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLabel,QVBoxLayout
from app.dialogs.dialog_compat import *

class RestrictionDetailsDialog(QDialog):
    def __init__(self,data:dict,parent=None):
        super().__init__(parent); self.setWindowTitle("Restriction Details"); root=QVBoxLayout(self); f=QFormLayout()
        for k,v in data.items(): f.addRow(str(k),QLabel(str(v)))
        root.addLayout(f); note=QLabel("Restrictions are surfaced for safety. The UI does not rotate accounts or bypass Telegram controls."); note.setWordWrap(True); note.setProperty("muted",True); root.addWidget(note); box=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept); root.addWidget(box)

# Add compatibility attributes for older PySide6 versions
if not hasattr(RestrictionDetailsDialog, 'Accepted'):
    RestrictionDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(RestrictionDetailsDialog, 'Rejected'):
    RestrictionDetailsDialog.Rejected = QDialog.DialogCode.Rejected
