from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TelegramOperationResult:
    """Typed outcome for expected Telegram/business operations.

    Expected validation/API failures are returned as data and should be shown
    inline/toast. Unexpected programming defects are intentionally not hidden by
    this type and may still reach the global application error handler.
    """

    success: bool
    status: str
    error_code: str | None = None
    user_message: str = ""
    technical_message: str = ""
    retry_classification: str = "NONE"
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "error_code": self.error_code,
            "user_message": self.user_message,
            "technical_message": self.technical_message,
            "retry_classification": self.retry_classification,
            **dict(self.data or {}),
        }
