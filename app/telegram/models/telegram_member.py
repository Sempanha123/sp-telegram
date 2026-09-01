from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class TelegramMember:
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_bot: bool | None = None
    is_deleted: bool | None = None
    is_verified: bool | None = None
    is_scam: bool | None = None
    is_fake: bool | None = None
    is_premium: bool | None = None
    source_group_id: int | None = None
    source_account_id: int | None = None
    observed_at: str | None = None
