from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import MemberSource
from app.utils.formatters import utc_now_iso

COLS = (
    "id", "member_id", "group_id", "first_seen_at", "last_seen_at",
    "first_seen_by_account_id", "last_seen_by_account_id", "source_status",
    "created_at", "updated_at", "last_seen_sync_run_id",
)


class MemberSourceRepository(BaseRepository):
    table_name = "member_sources"
    columns = COLS

    def upsert_source(self, member_id: int, group_id: int, *, account_id: int | None = None,
                      seen_at: str | None = None, sync_run_id: str | None = None,
                      source_status: str = "ACTIVE") -> MemberSource:
        now = seen_at or utc_now_iso()
        self.db.execute(
            """INSERT INTO member_sources(
                member_id,group_id,first_seen_at,last_seen_at,first_seen_by_account_id,last_seen_by_account_id,
                source_status,created_at,updated_at,last_seen_sync_run_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(member_id,group_id) DO UPDATE SET
                last_seen_at=excluded.last_seen_at,
                last_seen_by_account_id=excluded.last_seen_by_account_id,
                source_status=excluded.source_status,
                updated_at=excluded.updated_at,
                last_seen_sync_run_id=excluded.last_seen_sync_run_id""",
            (member_id, group_id, now, now, account_id, account_id, source_status, now, now, sync_run_id),
        )
        row = self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM member_sources WHERE member_id=? AND group_id=?", (member_id, group_id))
        return MemberSource.from_row(row)

    def add(self, member_id: int, group_id: int):
        return self.upsert_source(member_id, group_id)

    def bulk_upsert_sources(self, rows: list[tuple[int, int, int | None, str | None, str | None]]) -> int:
        count = 0
        with self.db.transaction():
            for member_id, group_id, account_id, seen_at, sync_run_id in rows:
                self.upsert_source(member_id, group_id, account_id=account_id, seen_at=seen_at, sync_run_id=sync_run_id)
                count += 1
        return count

    def get_member_sources(self, member_id: int) -> list[MemberSource]:
        rows = self.db.fetch_all(
            f"""SELECT {', '.join('s.' + c for c in COLS)}, g.title AS group_title,
                COALESCE(a.first_name || ' ' || a.last_name, a.username, 'Account ' || a.id) AS account_name
                FROM member_sources s JOIN groups g ON g.id=s.group_id
                LEFT JOIN telegram_accounts a ON a.id=s.last_seen_by_account_id
                WHERE s.member_id=? ORDER BY s.last_seen_at DESC""",
            (member_id,),
        )
        return [MemberSource.from_row(row) for row in rows]

    def get_group_members(self, group_id: int, *, active_only: bool = False) -> list[int]:
        where = " AND source_status='ACTIVE'" if active_only else ""
        rows = self.db.fetch_all(f"SELECT member_id FROM member_sources WHERE group_id=?{where}", (group_id,))
        return [int(row["member_id"]) for row in rows]

    def mark_sync_seen(self, member_id: int, group_id: int, account_id: int, sync_run_id: str, seen_at: str | None = None):
        return self.upsert_source(member_id, group_id, account_id=account_id, seen_at=seen_at, sync_run_id=sync_run_id, source_status="ACTIVE")

    def mark_missing_after_full_sync(self, group_id: int, sync_run_id: str) -> int:
        cursor = self.db.execute(
            """UPDATE member_sources SET source_status='NO_LONGER_VISIBLE',updated_at=?
               WHERE group_id=? AND source_status='ACTIVE'
               AND COALESCE(last_seen_sync_run_id,'')<>?""",
            (utc_now_iso(), group_id, sync_run_id),
        )
        return cursor.rowcount

    def mark_source_unavailable(self, group_id: int) -> int:
        cursor = self.db.execute(
            "UPDATE member_sources SET source_status='SOURCE_UNAVAILABLE',updated_at=? WHERE group_id=? AND source_status='ACTIVE'",
            (utc_now_iso(), group_id),
        )
        return cursor.rowcount

    def count_by_group(self, group_id: int, *, active_only: bool = False) -> int:
        row = self.db.fetch_one(
            "SELECT COUNT(*) count FROM member_sources WHERE group_id=?" + (" AND source_status='ACTIVE'" if active_only else ""),
            (group_id,),
        )
        return int(row["count"] if row else 0)
