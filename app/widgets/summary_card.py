from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.icons import IconManager


class SummaryCard(QFrame):
    ICONS = {"accounts": "accounts", "groups": "groups", "members": "members", "campaigns": "campaigns"}

    def __init__(self, title: str, value: str | int = "0", object_name: str = "", parent=None):
        super().__init__(parent)
        if object_name: self.setObjectName(object_name)
        self.setProperty("summaryCard", True)
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(9)
        head=QHBoxLayout(); head.setContentsMargins(0,0,0,0); head.setSpacing(8)
        icon=QLabel(); icon.setObjectName("lbl_summary_icon"); icon.setPixmap(IconManager.get(self.ICONS.get(title.lower(),"dashboard")).pixmap(16,16)); icon.setFixedSize(18,18); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title=QLabel(title.upper()); self.lbl_title.setProperty("summaryLabel",True)
        head.addWidget(icon); head.addWidget(self.lbl_title); head.addStretch(); root.addLayout(head)
        self.lbl_value=QLabel(str(value)); self.lbl_value.setProperty("summaryValue",True); root.addWidget(self.lbl_value)
        self.metrics_host=QWidget(); self.metrics_host.setObjectName("summary_metrics_host"); self.metrics_host.setStyleSheet("background:transparent;border:0;")
        self.metrics=QVBoxLayout(self.metrics_host); self.metrics.setContentsMargins(0,0,0,0); self.metrics.setSpacing(5); root.addWidget(self.metrics_host)
        self._metric_labels:dict[str,QLabel]={}

    def set_value(self,value): self.lbl_value.setText(f"{value:,}" if isinstance(value,int) else str(value))

    def set_metrics(self,metrics:list[tuple[str,object,str|None]]):
        while self.metrics.count():
            item=self.metrics.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            if item.layout():
                while item.layout().count():
                    child=item.layout().takeAt(0)
                    if child.widget(): child.widget().deleteLater()
        self._metric_labels.clear()
        for label,value,tone in metrics:
            row=QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)
            dot=QLabel("●"); dot.setFixedWidth(10); dot.setProperty("tone",tone or "muted")
            text=QLabel(f"{value:,}  {label}" if isinstance(value,int) else f"{value}  {label}"); text.setProperty("summaryMetric",True)
            row.addWidget(dot); row.addWidget(text,1); self.metrics.addLayout(row); self._metric_labels[label]=text
