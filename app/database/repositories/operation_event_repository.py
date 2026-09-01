from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso
from app.utils.helpers import json_dumps_safe


class OperationEventRepository(BaseRepository):
    table_name = "operation_events"
    columns = ("id", "event_type", "severity", "component", "resource_type", "resource_id", "message", "metadata_json", "created_at")

    def add(self, event_type: str, message: str, *, severity: str = "INFO", component: str | None = None,
            resource_type: str | None = None, resource_id: int | str | None = None, metadata=None) -> int:
        return self.insert({
            "event_type": event_type, "severity": severity, "component": component,
            "resource_type": resource_type, "resource_id": None if resource_id is None else str(resource_id),
            "message": message, "metadata_json": json_dumps_safe(metadata or {}), "created_at": utc_now_iso(),
        })

    def recent(self, limit: int = 100):
        return [dict(r) for r in self.db.fetch_all(
            f"SELECT {', '.join(self.columns)} FROM operation_events ORDER BY id DESC LIMIT ?", (limit,)
        )]
