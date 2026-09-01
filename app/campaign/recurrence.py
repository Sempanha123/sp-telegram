from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass(slots=True)
class RecurrenceRule:
    frequency: str = "ONCE"
    interval: int = 1
    weekdays: list[int] = field(default_factory=list)  # Monday=0
    time: str | None = None
    timezone: str = "UTC"
    start_at: str | None = None
    end_at: str | None = None
    max_occurrences: int | None = None

    def next_after(self, current: datetime) -> datetime | None:
        freq=self.frequency.upper()
        if freq == "ONCE": return None
        if freq == "DAILY": return current + timedelta(days=max(1,self.interval))
        if freq == "INTERVAL": return current + timedelta(minutes=max(1,self.interval))
        if freq == "WEEKLY":
            wanted=sorted(set(self.weekdays or [current.weekday()]))
            for days in range(1, 15):
                candidate=current+timedelta(days=days)
                if candidate.weekday() in wanted: return candidate
        return None
