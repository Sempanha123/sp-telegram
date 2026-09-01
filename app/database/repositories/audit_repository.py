from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import AuditEvent
from app.utils.formatters import utc_now_iso
from app.utils.helpers import json_dumps_safe


class AuditRepository(BaseRepository):
    table_name = "audit_events"
    columns = ("id", "actor", "action", "resource_type", "resource_id", "description", "before_json", "after_json", "created_at")

    def add(self, action: str, *, resource_type: str | None = None, resource_id: int | str | None = None,
            description: str | None = None, before=None, after=None, actor: str = "LOCAL_USER") -> AuditEvent:
        event_id = self.insert({
            "actor": actor, "action": action, "resource_type": resource_type,
            "resource_id": None if resource_id is None else str(resource_id), "description": description,
            "before_json": json_dumps_safe(before) if before is not None else None,
            "after_json": json_dumps_safe(after) if after is not None else None,
            "created_at": utc_now_iso(),
        })
        return AuditEvent.from_row(self.find_by_id(event_id))

    def get_page(self, page: int, page_size: int, search: str = ""):
        where = ""; params: list[object] = []
        if search.strip():
            where = " WHERE action LIKE ? OR resource_type LIKE ? OR description LIKE ?"
            like = f"%{search.strip()}%"; params.extend([like, like, like])
        total = int(self.db.fetch_one(f"SELECT COUNT(*) AS n FROM audit_events{where}", params)["n"])
        offset = (max(1, page) - 1) * page_size
        rows = self.db.fetch_all(
            f"SELECT {', '.join(self.columns)} FROM audit_events{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        )
        return [AuditEvent.from_row(r) for r in rows], total
