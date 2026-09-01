from __future__ import annotations
from PySide6.QtWidgets import QFrame,QLabel,QVBoxLayout
class StatCard(QFrame):
    def __init__(self,title:str,value:str|int="0",object_name:str="",parent=None):
        super().__init__(parent)
        if object_name:self.setObjectName(object_name)
        self.setProperty("card",True); layout=QVBoxLayout(self); layout.setContentsMargins(16,13,16,13); layout.setSpacing(4)
        self.lbl_title=QLabel(title); self.lbl_title.setProperty("muted",True); self.lbl_value=QLabel(str(value)); self.lbl_value.setObjectName("lbl_stat_value"); layout.addWidget(self.lbl_title); layout.addWidget(self.lbl_value)
    def set_value(self,value): self.lbl_value.setText(f"{value:,}" if isinstance(value,int) else str(value))
