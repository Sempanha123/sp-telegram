from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.utils.formatters import utc_now_iso


class TargetMembershipStatus(str, Enum):
    # MEMBER is retained for backward compatibility with pre-productionization
    # rows.  New known-target membership writes use ALREADY_MEMBER.
    MEMBER = "MEMBER"
    ALREADY_MEMBER = "ALREADY_MEMBER"
    NOT_MEMBER = "NOT_MEMBER"
    UNKNOWN = "UNKNOWN"
    EXCLUDED = "EXCLUDED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    DELETED = "DELETED"
    INVALID = "INVALID"
    ACCESS_DENIED = "ACCESS_DENIED"
    NOT_RESOLVABLE = "NOT_RESOLVABLE"
    ERROR = "ERROR"


@dataclass(slots=True)
class TargetMembershipResult:
    member_id: int
    target_group_id: int
    status: str = TargetMembershipStatus.UNKNOWN.value
    checked_by_account_id: int | None = None
    checked_at: str = ""
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = utc_now_iso()
