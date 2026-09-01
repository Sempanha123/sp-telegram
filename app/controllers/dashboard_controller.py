from __future__ import annotations
from PySide6.QtCore import QObject,Signal
class DashboardController(QObject):
    summaryChanged=Signal(dict)
    def __init__(self,service,parent=None):super().__init__(parent); self.service=service
    def summary(self): return self.service.get_dashboard_summary()
    def refresh(self):data=self.summary(); self.summaryChanged.emit(data); return data
