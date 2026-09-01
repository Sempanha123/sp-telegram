from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class SendResult:
    success: bool
    group_id: int
    account_id: int
    telegram_message_id: str | None = None
    sent_at: str | None = None
    scheduled: bool = False
    error_code: str | None = None
    error_message: str | None = None
    wait_seconds: int | None = None
