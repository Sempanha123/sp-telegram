from __future__ import annotations

from typing import Any

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import LogEntry
from app.utils.formatters import utc_now_iso

COLS = (
    "id", "level", "category", "account_id", "group_id", "campaign_id", "job_id",
    "action", "message", "details_json", "created_at",
)


class LogRepository(BaseRepository):
    table_name = "logs"
    columns = COLS

    def add_log(self, level: str, category: str, message: str, action: str | None = None,
                account_id: int | None = None, group_id: int | None = None,
                campaign_id: int | None = None, job_id: int | None = None,
                details_json: str | None = None):
        rid = self.insert({
            "level": level, "category": category, "account_id": account_id, "group_id": group_id,
            "campaign_id": campaign_id, "job_id": job_id, "action": action, "message": message,
            "details_json": details_json, "created_at": utc_now_iso(),
        })
        return LogEntry.from_row(self.find_by_id(rid))

    def get_recent(self, limit: int = 200):
        return [LogEntry.from_row(r) for r in self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
        )]

    def search(self, query: str):
        term = f"%{query.strip()}%"
        rows = self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM logs WHERE message LIKE ? OR action LIKE ? OR category LIKE ? ORDER BY created_at DESC LIMIT 500",
            (term, term, term),
        )
        return [LogEntry.from_row(r) for r in rows]

    def get_page(self, page: int, page_size: int, search: str | None = None,
                 level: str | None = None, category: str | None = None, *,
                 date_from: str | None = None, date_to: str | None = None,
                 account_id: int | None = None, group_id: int | None = None,
                 campaign_id: int | None = None, job_id: int | None = None):
        where: list[str] = []; params: list[Any] = []
        if search:
            term = f"%{search.strip()}%"; where.append("(message LIKE ? OR action LIKE ? OR category LIKE ?)"); params += [term, term, term]
        if level and level.upper() != "ALL": where.append("level=?"); params.append(level.upper())
        if category and category.upper() != "ALL": where.append("category=?"); params.append(category.upper())
        if date_from: where.append("created_at>=?"); params.append(date_from)
        if date_to: where.append("created_at<=?"); params.append(date_to)
        for column, value in [("account_id", account_id), ("group_id", group_id), ("campaign_id", campaign_id), ("job_id", job_id)]:
            if value is not None: where.append(f"{column}=?"); params.append(int(value))
        clause = " WHERE " + " AND ".join(where) if where else ""
        count = self.db.fetch_one(f"SELECT COUNT(*) AS count FROM logs{clause}", tuple(params))
        off = (max(1, page) - 1) * page_size
        rows = self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM logs{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, page_size, off),
        )
        return [LogEntry.from_row(r) for r in rows], int(count["count"] if count else 0)

    def clear_old_logs(self, before_iso: str):
        return self.db.execute("DELETE FROM logs WHERE created_at < ?", (before_iso,)).rowcount
