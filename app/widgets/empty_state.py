from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QPushButton,QVBoxLayout
from app.icons import IconManager

class EmptyState(QFrame):
    def __init__(self,title:str,description:str,action:str="",parent=None,icon_name:str="info"):
        super().__init__(parent); self.setObjectName("empty_state"); self.setMaximumHeight(250); self.setMinimumHeight(150)
        layout=QVBoxLayout(self); layout.setContentsMargins(24,22,24,22); layout.setSpacing(7); layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon=QLabel(); self.lbl_icon.setObjectName("lbl_empty_icon"); IconManager.bind_label(self.lbl_icon,icon_name,24); self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title=QLabel(title); self.lbl_title.setObjectName("lbl_empty_title"); self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_description=QLabel(description); self.lbl_description.setObjectName("lbl_empty_description"); self.lbl_description.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_description.setWordWrap(True); self.lbl_description.setMaximumWidth(480)
        layout.addWidget(self.lbl_icon); layout.addWidget(self.lbl_title); layout.addWidget(self.lbl_description)
        row=QHBoxLayout(); row.addStretch(); self.btn_action=QPushButton(action) if action else None; self.btn_secondary=None
        if self.btn_action: self.btn_action.setProperty("primary",True); row.addWidget(self.btn_action)
        row.addStretch(); layout.addLayout(row); self._button_row=row
    def set_action(self,text:str,callback=None,primary=True):
        if self.btn_action is None: self.btn_action=QPushButton(); self._button_row.insertWidget(1,self.btn_action)
        self.btn_action.setText(text); self.btn_action.setProperty("primary",primary); self.btn_action.show()
        if callback:self.btn_action.clicked.connect(callback)
    def set_secondary_action(self,text:str,callback=None):
        if self.btn_secondary is None: self.btn_secondary=QPushButton(); self.btn_secondary.setProperty("role","ghost"); self._button_row.insertWidget(2,self.btn_secondary)
        self.btn_secondary.setText(text); self.btn_secondary.show()
        if callback:self.btn_secondary.clicked.connect(callback)
