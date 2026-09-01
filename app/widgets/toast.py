from __future__ import annotations
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from app.icons import IconManager

class ToastNotification(QFrame):
    def __init__(self,parent:QWidget|None=None):
        super().__init__(parent); self.setObjectName("toast_notification"); self.setMinimumWidth(340); self.setMaximumWidth(430)
        root=QHBoxLayout(self); root.setContentsMargins(12,11,10,11); root.setSpacing(10)
        self.lbl_icon=QLabel(); self.lbl_icon.setFixedWidth(22); root.addWidget(self.lbl_icon,0,Qt.AlignmentFlag.AlignTop)
        text=QVBoxLayout(); text.setSpacing(2); self.lbl_title=QLabel("Info"); self.lbl_title.setObjectName("lbl_toast_title"); self.lbl_description=QLabel(); self.lbl_description.setObjectName("lbl_toast_description"); self.lbl_description.setWordWrap(True); text.addWidget(self.lbl_title); text.addWidget(self.lbl_description); root.addLayout(text,1)
        self.btn_close=QPushButton("×"); self.btn_close.setProperty("role","ghost"); self.btn_close.setFixedSize(28,28); self.btn_close.clicked.connect(self.hide); root.addWidget(self.btn_close,0,Qt.AlignmentFlag.AlignTop); self.hide()
    def show_message(self,message:str,level:str="Info",timeout_ms:int=3500)->None:
        level=str(level or "Info").title(); icon_name={"Success":"check","Warning":"warning","Error":"warning"}.get(level,"info"); IconManager.bind_label(self.lbl_icon,icon_name,20); self.lbl_title.setText(level); self.lbl_description.setText(message)
        if self.parentWidget(): self.adjustSize(); p=self.parentWidget().rect(); self.move(max(16,p.width()-self.width()-20),max(74,p.height()-self.height()-42))
        self.show(); self.raise_(); QTimer.singleShot(timeout_ms,self.hide)
