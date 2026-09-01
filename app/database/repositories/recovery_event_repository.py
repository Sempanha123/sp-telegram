from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import RecoveryEvent
from app.utils.formatters import utc_now_iso


class RecoveryEventRepository(BaseRepository):
    table_name = "recovery_events"
    columns = ("id", "component", "event_type", "trigger", "action", "result", "started_at", "finished_at", "error_message")

    def start(self, component: str, event_type: str, trigger: str = "", action: str = "") -> RecoveryEvent:
        event_id = self.insert({"component": component, "event_type": event_type, "trigger": trigger, "action": action, "started_at": utc_now_iso()})
        return RecoveryEvent.from_row(self.find_by_id(event_id))

    def finish(self, event_id: int, result: str, error_message: str | None = None) -> bool:
        return self.update_fields(event_id, {"result": result, "finished_at": utc_now_iso(), "error_message": error_message})

    def recent(self, limit: int = 100) -> list[RecoveryEvent]:
        rows = self.db.fetch_all(f"SELECT {', '.join(self.columns)} FROM recovery_events ORDER BY id DESC LIMIT ?", (limit,))
        return [RecoveryEvent.from_row(r) for r in rows]
