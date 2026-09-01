from __future__ import annotations


class AlertManager:
    def __init__(self, repository, logger=None) -> None:
        self.repository = repository
        self.logger = logger

    def raise_alert(self, severity: str, alert_type: str, title: str, message: str = "", *, dedupe_key: str | None = None,
                    source_type: str | None = None, source_id=None, requires_action: bool = False, action_type: str | None = None, **refs):
        alert_id = self.repository.create_alert(
            severity, alert_type, title, message, dedupe_key=dedupe_key, source_type=source_type,
            source_id=source_id, requires_action=requires_action, action_type=action_type, **refs,
        )
        if self.logger:
            level = "ERROR" if severity.upper() in {"ERROR", "CRITICAL"} else "WARNING" if severity.upper() == "WARNING" else "INFO"
            self.logger.log(level, "SYSTEM", title, action="ALERT", important=severity.upper() in {"ERROR", "CRITICAL"})
        return alert_id

    def acknowledge(self, alert_id: int): return self.repository.acknowledge(alert_id)
    def resolve(self, alert_id: int): return self.repository.resolve(alert_id)
    def mute(self, alert_id: int): return self.repository.mute(alert_id)
    def active(self): return self.repository.get_all(status="OPEN") + self.repository.get_all(status="ACKNOWLEDGED")
