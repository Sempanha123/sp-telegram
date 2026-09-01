from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class ScheduleResult:
    success: bool
    group_id: int
    account_id: int
    telegram_scheduled_message_id: str | None = None
    scheduled_for: str | None = None
    status: str = "SCHEDULED"
    error_code: str | None = None
    error_message: str | None = None
