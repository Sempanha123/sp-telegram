from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AlertController(QObject):
    alertsChanged = Signal(list)
    alertCountChanged = Signal(int)
    toast_requested = Signal(str, str)

    def __init__(self, service, parent=None):
        super().__init__(parent); self.service = service; self.status_filter = None; self.severity_filter = None

    def alerts(self):
        try: return self.service.get_all(status=self.status_filter, severity=self.severity_filter)
        except Exception as exc: self.toast_requested.emit(str(exc), "Error"); return []

    def refresh(self):
        items = self.alerts(); self.alertsChanged.emit(items); self.alertCountChanged.emit(self.service.count_open()); return items

    def set_status_filter(self, status: str | None):
        self.status_filter = None if not status or status == "ALL" else status; return self.refresh()

    def set_severity_filter(self, severity: str | None):
        self.severity_filter = None if not severity or severity == "ALL" else severity; return self.refresh()

    def get_by_id(self, alert_id: int): return self.service.get_by_id(alert_id)
    def mark_read(self, alert_id: int): return self.acknowledge(alert_id)
    def acknowledge(self, alert_id: int): self.service.acknowledge(alert_id); self.refresh()
    def resolve(self, alert_id: int): self.service.resolve(alert_id); self.refresh(); self.toast_requested.emit("Alert resolved.", "Success")
    def mute(self, alert_id: int): self.service.mute(alert_id); self.refresh(); self.toast_requested.emit("Alert muted.", "Info")
    def mark_all_read(self): self.service.mark_all_read(); self.refresh()
    def clear_resolved(self): self.service.clear_resolved(); self.refresh()
