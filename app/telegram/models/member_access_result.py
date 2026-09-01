from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.utils.formatters import utc_now_iso

class MemberListAvailability(str, Enum):
    FULL="FULL"; PARTIAL="PARTIAL"; HIDDEN="HIDDEN"; UNAVAILABLE="UNAVAILABLE"; ACCESS_DENIED="ACCESS_DENIED"; UNKNOWN="UNKNOWN"

@dataclass(slots=True)
class MemberAccessResult:
    group_id: int
    account_id: int
    availability: str = MemberListAvailability.UNKNOWN.value
    estimated_total: int | None = None
    message: str = ""
    checked_at: str = ""
    error_code: str | None = None
    def __post_init__(self):
        if not self.checked_at:self.checked_at=utc_now_iso()
