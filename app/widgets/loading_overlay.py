from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame,QLabel,QProgressBar,QVBoxLayout,QWidget

class LoadingOverlay(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName("loading_overlay"); self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        layout=QVBoxLayout(self); layout.addStretch(); card=QFrame(); card.setObjectName("loading_card"); card.setFixedWidth(280); c=QVBoxLayout(card); c.setContentsMargins(20,18,20,18)
        self.lbl_message=QLabel("Loading…"); self.lbl_message.setObjectName("lbl_loading_message"); self.lbl_message.setAlignment(Qt.AlignmentFlag.AlignCenter); c.addWidget(self.lbl_message)
        # UX-010: indeterminate progress bar acts as a visible spinner instead of
        # static text. range(0,0) makes Qt animate it continuously.
        self.progress=QProgressBar(); self.progress.setObjectName("loading_spinner"); self.progress.setRange(0,0); self.progress.setTextVisible(False); self.progress.setFixedHeight(4); c.addWidget(self.progress)
        layout.addWidget(card,0,Qt.AlignmentFlag.AlignHCenter); layout.addStretch(); self.hide()
    def start(self,message:str)->None:
        self.lbl_message.setText(message)
        if self.parentWidget(): self.setGeometry(self.parentWidget().rect())
        self.show(); self.raise_()
    def stop(self)->None:self.hide()
