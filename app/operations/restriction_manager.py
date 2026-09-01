from __future__ import annotations

from datetime import datetime, timezone


class RestrictionManager:
    def __init__(self, repository, account_repository, alert_manager=None, logger=None) -> None:
        self.repository = repository
        self.accounts = account_repository
        self.alerts = alert_manager
        self.logger = logger

    def refresh_expiries(self) -> list[int]:
        pending = self.repository.expire_due()
        for restriction_id in pending:
            item = self.repository.get_by_id(restriction_id)
            if item and self.alerts:
                self.alerts.raise_alert(
                    "INFO", "RESTRICTION_RECHECK", "Restriction wait elapsed; recheck required",
                    "The known wait duration has elapsed. SP Telegram will not assume the Telegram restriction is gone until a safe recheck succeeds.",
                    dedupe_key=f"restriction-recheck:{restriction_id}", source_type="RESTRICTION", source_id=restriction_id,
                    account_id=item.account_id, requires_action=True, action_type="RECHECK_RESTRICTION",
                )
        return pending

    def mark_manual_resolved(self, restriction_id: int, note: str = "Manually resolved by local operator") -> bool:
        result = self.repository.resolve(restriction_id, note)
        if result and self.logger:
            self.logger.info("SECURITY", f"Restriction #{restriction_id} manually marked resolved.", important=True, action="RESTRICTION_MANUAL_RESOLVE")
        return bool(result)

    @staticmethod
    def remaining_seconds(item, now: datetime | None = None) -> int | None:
        if not getattr(item, "expires_at", None): return None
        try:
            expiry = datetime.fromisoformat(str(item.expires_at).replace("Z", "+00:00"))
            now = now or datetime.now(timezone.utc)
            return max(0, int((expiry - now).total_seconds()))
        except ValueError:
            return None
