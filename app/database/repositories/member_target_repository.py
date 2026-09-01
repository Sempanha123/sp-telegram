from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import MemberTargetState
from app.utils.formatters import utc_now_iso

COLS = ("id","member_id","target_group_id","state","last_checked_at","last_error_code","last_error_message","created_at","updated_at","checked_by_account_id")


class MemberTargetStateRepository(BaseRepository):
    table_name = "member_target_states"
    columns = COLS

    def upsert_state(self, member_id: int, target_group_id: int, state: str, *, account_id: int | None = None,
                     error_code: str | None = None, error_message: str | None = None,
                     checked_at: str | None = None) -> MemberTargetState:
        now = checked_at or utc_now_iso()
        self.db.execute(
            """INSERT INTO member_target_states(member_id,target_group_id,state,last_checked_at,last_error_code,last_error_message,created_at,updated_at,checked_by_account_id)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(member_id,target_group_id) DO UPDATE SET state=excluded.state,last_checked_at=excluded.last_checked_at,
               last_error_code=excluded.last_error_code,last_error_message=excluded.last_error_message,updated_at=excluded.updated_at,
               checked_by_account_id=excluded.checked_by_account_id""",
            (member_id, target_group_id, state, now, error_code, error_message, now, now, account_id),
        )
        return self.get_state(member_id, target_group_id)

    def get_state(self, member_id: int, target_group_id: int) -> MemberTargetState | None:
        row = self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM member_target_states WHERE member_id=? AND target_group_id=?", (member_id, target_group_id))
        return MemberTargetState.from_row(row)

    def get_target_members(self, target_group_id: int, state: str | None = None, limit: int = 500) -> list[MemberTargetState]:
        params: list[object] = [target_group_id]
        extra = ""
        if state:
            extra = " AND state=?"
            params.append(state)
        params.append(limit)
        rows = self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM member_target_states WHERE target_group_id=?{extra} ORDER BY last_checked_at DESC LIMIT ?", tuple(params))
        return [MemberTargetState.from_row(row) for row in rows]

    def get_existing_members(self, target_group_id: int) -> list[int]:
        return [int(row["member_id"]) for row in self.db.fetch_all("SELECT member_id FROM member_target_states WHERE target_group_id=? AND state IN ('MEMBER','ALREADY_MEMBER')", (target_group_id,))]

    def get_unknown_members(self, target_group_id: int, limit: int = 500) -> list[int]:
        rows = self.db.fetch_all(
            """SELECT m.id FROM members m LEFT JOIN member_target_states s ON s.member_id=m.id AND s.target_group_id=?
               WHERE s.id IS NULL OR s.state='UNKNOWN' ORDER BY m.id LIMIT ?""",
            (target_group_id, limit),
        )
        return [int(row["id"]) for row in rows]

    def bulk_update_states(self, values: list[dict]) -> int:
        with self.db.transaction():
            for value in values:
                self.upsert_state(value["member_id"], value["target_group_id"], value["state"], account_id=value.get("checked_by_account_id"), error_code=value.get("last_error_code"), error_message=value.get("last_error_message"), checked_at=value.get("last_checked_at"))
        return len(values)


    def apply_full_snapshot(self, target_group_id: int, seen_member_ids: list[int], *, account_id: int | None = None, checked_at: str | None = None) -> dict[str, int]:
        """Apply a verified FULL target-member snapshot without loading the Member Pool.

        Seen local records become ALREADY_MEMBER.  Local records not present in a
        complete participant list become NOT_MEMBER.  This method must never be
        called for PARTIAL/HIDDEN/UNKNOWN access.
        """
        now=checked_at or utc_now_iso(); target_group_id=int(target_group_id); ids=sorted({int(x) for x in seen_member_ids})
        with self.db.transaction():
            conn=self.db.get_connection()
            conn.execute("CREATE TEMP TABLE IF NOT EXISTS sp_target_seen(member_id INTEGER PRIMARY KEY)")
            conn.execute("DELETE FROM sp_target_seen")
            if ids:conn.executemany("INSERT OR IGNORE INTO sp_target_seen(member_id) VALUES(?)",[(x,) for x in ids])
            conn.execute(
                """INSERT INTO member_target_states(member_id,target_group_id,state,last_checked_at,created_at,updated_at,checked_by_account_id)
                   SELECT s.member_id,?,'ALREADY_MEMBER',?,?,?,? FROM sp_target_seen s WHERE 1
                   ON CONFLICT(member_id,target_group_id) DO UPDATE SET state='ALREADY_MEMBER',last_checked_at=excluded.last_checked_at,updated_at=excluded.updated_at,checked_by_account_id=excluded.checked_by_account_id,last_error_code=NULL,last_error_message=NULL""",
                (target_group_id,now,now,now,account_id),
            )
            conn.execute(
                """INSERT INTO member_target_states(member_id,target_group_id,state,last_checked_at,created_at,updated_at,checked_by_account_id)
                   SELECT m.id,?,'NOT_MEMBER',?,?,?,? FROM members m WHERE NOT EXISTS(SELECT 1 FROM sp_target_seen s WHERE s.member_id=m.id)
                   ON CONFLICT(member_id,target_group_id) DO UPDATE SET state='NOT_MEMBER',last_checked_at=excluded.last_checked_at,updated_at=excluded.updated_at,checked_by_account_id=excluded.checked_by_account_id,last_error_code=NULL,last_error_message=NULL""",
                (target_group_id,now,now,now,account_id),
            )
            conn.execute("DELETE FROM sp_target_seen")
        counts=self.count_by_state(target_group_id)
        return {"already_member":int(counts.get("ALREADY_MEMBER",0)+counts.get("MEMBER",0)),"not_member":int(counts.get("NOT_MEMBER",0))}

    def list_target_member_rows(self, target_group_id: int, limit: int = 500):
        return self.db.fetch_all(
            """SELECT s.id,s.member_id,s.target_group_id,s.state,s.last_checked_at,s.last_error_code,s.last_error_message,
                      m.telegram_user_id,m.username,m.display_name,m.first_name,m.last_name,m.first_seen_at,m.last_seen_at,
                      COALESCE((SELECT GROUP_CONCAT(g.title, ', ') FROM member_sources ms JOIN groups g ON g.id=ms.group_id WHERE ms.member_id=m.id),'') sources
               FROM member_target_states s JOIN members m ON m.id=s.member_id
               WHERE s.target_group_id=? ORDER BY s.last_checked_at DESC LIMIT ?""",
            (int(target_group_id),max(1,int(limit))),
        )


    def get_member_states_for_member(self, member_id: int, limit: int = 500):
        return self.db.fetch_all(
            """SELECT s.*,g.title target_title,g.username target_username,ta.first_name account_name,ta.username account_username
               FROM member_target_states s
               JOIN groups g ON g.id=s.target_group_id
               LEFT JOIN telegram_accounts ta ON ta.id=s.checked_by_account_id
               WHERE s.member_id=? ORDER BY COALESCE(s.last_checked_at,s.updated_at) DESC LIMIT ?""",
            (int(member_id), max(1, int(limit))),
        )

    def count_by_state(self, target_group_id: int) -> dict[str, int]:
        rows = self.db.fetch_all("SELECT state,COUNT(*) count FROM member_target_states WHERE target_group_id=? GROUP BY state", (target_group_id,))
        return {str(row["state"]): int(row["count"]) for row in rows}
