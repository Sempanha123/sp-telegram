from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso


class TargetInviteLinkRepository(BaseRepository):
    table_name = "target_invite_links"
    columns = (
        "id", "target_group_id", "account_id", "invite_link", "name", "request_needed",
        "expires_at", "usage_limit", "status", "last_error_code", "last_error_message",
        "created_at", "revoked_at", "updated_at",
    )

    def create_link(self, target_group_id: int, account_id: int, invite_link: str, *, name: str | None = None,
                    request_needed: bool = True, expires_at: str | None = None, usage_limit: int | None = None) -> dict:
        now = utc_now_iso()
        link_id = self.insert({
            "target_group_id": int(target_group_id), "account_id": int(account_id), "invite_link": str(invite_link),
            "name": name, "request_needed": int(bool(request_needed)), "expires_at": expires_at,
            "usage_limit": usage_limit, "status": "ACTIVE", "created_at": now, "updated_at": now,
        })
        return dict(self.find_by_id(link_id))

    def get_active_for_target(self, target_group_id: int, limit: int = 100) -> list[dict]:
        rows = self.db.fetch_all(
            "SELECT * FROM target_invite_links WHERE target_group_id=? AND status='ACTIVE' "
            "ORDER BY created_at DESC LIMIT ?", (int(target_group_id), max(1, min(500, int(limit))))
        )
        return [dict(row) for row in rows]

    def mark_revoked(self, link_id: int, *, error_code: str | None = None, error_message: str | None = None) -> bool:
        now = utc_now_iso()
        return self.update_fields(int(link_id), {
            "status": "REVOKED", "revoked_at": now, "last_error_code": error_code,
            "last_error_message": error_message, "updated_at": now,
        })
