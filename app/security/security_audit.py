from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from app.security.session_security import SessionSecurity


@dataclass
class SecurityAuditFinding:
    severity: str
    code: str
    message: str


class SecurityAuditService:
    def __init__(self, session_security: SessionSecurity, account_repository, telegram_config_service, paths, settings_service) -> None:
        self.session_security = session_security
        self.accounts = account_repository
        self.telegram_config = telegram_config_service
        self.paths = paths
        self.settings = settings_service

    def run(self) -> dict:
        findings: list[SecurityAuditFinding] = []
        for finding in self.session_security.audit(self.accounts.get_all()):
            findings.append(SecurityAuditFinding(finding.severity, finding.code, finding.message))
        try:
            if not self.telegram_config.has_valid_config():
                findings.append(SecurityAuditFinding("WARNING", "API_CONFIG_MISSING", "Telegram API credentials are not fully configured in secure storage."))
        except Exception:
            findings.append(SecurityAuditFinding("WARNING", "SECURE_STORAGE_UNAVAILABLE", "Secure OS credential storage could not be checked."))
        if not self.paths.sessions.exists():
            findings.append(SecurityAuditFinding("CRITICAL", "SESSION_DIR_MISSING", "Telegram session directory is missing."))
        elif not self.paths.validate().get("writable"):
            findings.append(SecurityAuditFinding("CRITICAL", "DATA_NOT_WRITABLE", "One or more application data directories are not writable."))
        if bool(self.settings.get("backup_sessions", False)):
            findings.append(SecurityAuditFinding("WARNING", "SESSION_BACKUP_ENABLED", "Session backup is enabled; Telegram session files are authorization credentials and require encrypted storage."))
        counts = {"passed": max(0, 8 - len(findings)), "warnings": sum(f.severity == "WARNING" for f in findings), "critical": sum(f.severity == "CRITICAL" for f in findings)}
        return {**counts, "findings": [asdict(f) for f in findings]}
