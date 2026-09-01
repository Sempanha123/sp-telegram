from __future__ import annotations

from app.security.sensitive_data_filter import SensitiveDataFilter


class AuditSecurity:
    def __init__(self, filter_: SensitiveDataFilter | None = None) -> None:
        self.filter = filter_ or SensitiveDataFilter(mask_phone=True, mask_ip=True, mask_session_path=True)

    def sanitize(self, value):
        return self.filter.redact(value)
