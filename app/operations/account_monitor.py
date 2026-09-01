from __future__ import annotations

from pathlib import Path


class AccountMonitor:
    def __init__(self, account_repository, restriction_repository, alert_manager=None) -> None:
        self.accounts = account_repository
        self.restrictions = restriction_repository
        self.alerts = alert_manager

    def snapshot(self) -> dict:
        items = self.accounts.get_all()
        counts = {"READY": 0, "WARNING": 0, "COOLDOWN": 0, "LOGIN_REQUIRED": 0, "OFFLINE": 0, "DISABLED": 0}
        issues = []
        for account in items:
            if not account.is_enabled: status = "DISABLED"
            elif account.health_status == "COOLDOWN": status = "COOLDOWN"
            elif account.health_status in {"LOGIN_REQUIRED", "SESSION_INVALID"}: status = "LOGIN_REQUIRED"
            elif account.connection_status in {"OFFLINE", "DISCONNECTED", "ERROR"}: status = "OFFLINE"
            elif account.health_status in {"WARNING", "RESTRICTED"}: status = "WARNING"
            else: status = "READY"
            counts[status] = counts.get(status, 0) + 1
            if account.session_path and not Path(account.session_path).exists() and not account.is_demo:
                issues.append((account.id, "SESSION_MISSING"))
                if self.alerts:
                    self.alerts.raise_alert(
                        "WARNING", "SESSION_MISSING", f"Account {account.id} session file is missing",
                        "The local Telegram session path no longer exists. Login is required before network operations can continue.",
                        dedupe_key=f"account-session-missing:{account.id}", source_type="ACCOUNT", source_id=account.id,
                        account_id=account.id, requires_action=True, action_type="LOGIN_ACCOUNT",
                    )
        return {"total": len(items), "counts": counts, "issues": issues}
