from __future__ import annotations


class AlertService:
    def __init__(self, repository): self.repository = repository
    def create(self, *args, **kwargs): return self.repository.create_alert(*args, **kwargs)
    def get_all(self, **filters): return self.repository.get_all(**filters)
    def get_by_id(self, alert_id: int): return self.repository.get_by_id(alert_id)
    def mark_all_read(self): return self.repository.mark_all_read()
    def clear_resolved(self): return self.repository.clear_resolved()
    def mark_read(self, alert_id: int): return self.repository.mark_read(alert_id)
    def acknowledge(self, alert_id: int): return self.repository.acknowledge(alert_id)
    def resolve(self, alert_id: int): return self.repository.resolve(alert_id)
    def mute(self, alert_id: int): return self.repository.mute(alert_id)
    def count_open(self, severity=None): return self.repository.count_open(severity)
