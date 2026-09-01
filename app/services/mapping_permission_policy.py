from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable


MAX_MAPPING_PERMISSION_AGE = timedelta(minutes=15)
REFRESH_PERMISSIONS_MESSAGE = "Refresh group permissions and try again."

_INVALID_STATES = {
    "UNKNOWN", "PENDING", "PENDING_VERIFICATION", "VERIFY_FAILED",
    "UNAVAILABLE", "ACCESS_DENIED", "NOT_JOINED", "NO_ACCESS", "BANNED", "LEFT",
}


@dataclass(frozen=True)
class MappingPermissionDecision:
    allowed: bool
    code: str
    message: str


class MappingPermissionPolicy:
    """Fail-closed validity policy for cached outbound Telegram permissions."""

    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def evaluate(self, mapping, required_permissions: Iterable[str]) -> MappingPermissionDecision:
        if mapping is None:
            return self._blocked("MAPPING_MISSING", "The selected account is not mapped to this group.")

        access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
        error = str(getattr(mapping, "last_error_code", "") or "").upper()
        if access in _INVALID_STATES or error in _INVALID_STATES:
            return self._blocked("PERMISSION_NOT_VERIFIED", "Group permissions are not currently verified.")

        checked_at = self._parse_timestamp(getattr(mapping, "last_permission_check_at", None))
        if checked_at is None:
            return self._blocked("PERMISSION_TIMESTAMP_INVALID", "Group permission verification time is missing or invalid.")

        now = self._now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age = now.astimezone(timezone.utc) - checked_at
        if age < timedelta(0):
            return self._blocked("PERMISSION_TIMESTAMP_FUTURE", "Group permission verification time is in the future.")
        if age > MAX_MAPPING_PERMISSION_AGE:
            return self._blocked("PERMISSION_STALE", "Cached group permissions are older than 15 minutes.")

        for permission in required_permissions:
            if getattr(mapping, str(permission), None) is not True and getattr(mapping, str(permission), None) != 1:
                label = str(permission).removeprefix("can_").replace("_", " ")
                if label == "post":
                    label = "posting"
                return self._blocked("PERMISSION_DENIED", f"Required group {label} permission is unavailable.")
        return MappingPermissionDecision(True, "PERMISSION_VERIFIED", "Group permissions are fresh and verified.")

    @staticmethod
    def _parse_timestamp(value) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _blocked(code: str, detail: str) -> MappingPermissionDecision:
        return MappingPermissionDecision(False, code, f"{detail} {REFRESH_PERMISSIONS_MESSAGE}")
