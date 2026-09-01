from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import AccountRestriction
from app.utils.formatters import utc_now_iso


COLS = (
    "id", "account_id", "restriction_type", "source", "confidence", "error_code", "reason",
    "started_at", "expires_at", "is_active", "details_json", "created_at", "updated_at",
    "scope", "state", "requires_action", "last_rechecked_at", "resolution_note",
)


class RestrictionRepository(BaseRepository):
    table_name = "account_restrictions"
    columns = COLS

    def create(self, item: AccountRestriction):
        now = utc_now_iso(); data = asdict(item); data.pop("id", None)
        data["created_at"] = item.created_at or now; data["updated_at"] = now
        data.setdefault("scope", "ACCOUNT"); data.setdefault("state", "ACTIVE")
        item.id = self.insert(data)
        return AccountRestriction.from_row(self.find_by_id(item.id))

    def get_by_id(self, restriction_id: int):
        return AccountRestriction.from_row(self.find_by_id(restriction_id))

    def get_active_for_account(self, account_id: int):
        rows = self.db.fetch_all(
            f"SELECT {', '.join(COLS)} FROM account_restrictions WHERE account_id=? AND state IN ('ACTIVE','PENDING_RECHECK','MANUAL_REVIEW') ORDER BY created_at DESC",
            (account_id,),
        )
        return [AccountRestriction.from_row(r) for r in rows]

    def get_all_active(self):
        return self.get_all(state="ACTIVE")

    def get_all(self, state: str | None = None):
        where = ""; params: tuple[object, ...] = ()
        if state and state != "ALL": where = " WHERE state=?"; params = (state,)
        rows = self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM account_restrictions{where} ORDER BY created_at DESC", params)
        return [AccountRestriction.from_row(r) for r in rows]

    def resolve(self, restriction_id: int, note: str | None = None):
        return self.update_fields(restriction_id, {
            "is_active": 0, "state": "RESOLVED", "resolution_note": note,
            "last_rechecked_at": utc_now_iso(), "updated_at": utc_now_iso(),
        })

    def mark_manual_review(self, restriction_id: int):
        return self.update_fields(restriction_id, {"state": "MANUAL_REVIEW", "requires_action": 1, "updated_at": utc_now_iso()})

    def mark_pending_recheck(self, restriction_id: int):
        return self.update_fields(restriction_id, {"state": "PENDING_RECHECK", "is_active": 1, "last_rechecked_at": utc_now_iso(), "updated_at": utc_now_iso()})

    def record_recheck(self, restriction_id: int, *, resolved: bool, note: str | None = None):
        if resolved:
            return self.resolve(restriction_id, note)
        return self.update_fields(restriction_id, {"last_rechecked_at": utc_now_iso(), "updated_at": utc_now_iso(), "resolution_note": note})

    def expire_due(self, now_iso: str | None = None) -> list[int]:
        now_iso = now_iso or utc_now_iso()
        rows = self.db.fetch_all(
            "SELECT id FROM account_restrictions WHERE state='ACTIVE' AND expires_at IS NOT NULL AND expires_at <= ?",
            (now_iso,),
        )
        ids = [int(row["id"]) for row in rows]
        for restriction_id in ids:
            self.mark_pending_recheck(restriction_id)
        return ids

    def count_active(self) -> int:
        return self.count("state IN ('ACTIVE','PENDING_RECHECK','MANUAL_REVIEW')")

    def count_accounts_affected(self) -> int:
        row = self.db.fetch_one("SELECT COUNT(DISTINCT account_id) AS n FROM account_restrictions WHERE state IN ('ACTIVE','PENDING_RECHECK','MANUAL_REVIEW')")
        return int(row["n"] if row else 0)

    def delete_for_account(self, account_id: int) -> int:
        cursor = self.db.execute("DELETE FROM account_restrictions WHERE account_id = ?", (account_id,))
        return int(cursor.rowcount)
