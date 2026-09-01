"""Compatibility re-export for normalized Phase 6 Telegram message results."""
from app.telegram.models.send_result import SendResult
from app.telegram.models.schedule_result import ScheduleResult
__all__ = ["SendResult", "ScheduleResult"]
