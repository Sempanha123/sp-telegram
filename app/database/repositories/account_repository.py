from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import TelegramAccount
from app.utils.formatters import utc_now_iso


ACCOUNT_COLUMNS = (
    "id", "telegram_user_id", "phone", "username", "first_name", "last_name", "is_premium",
    "session_path", "connection_status", "health_status", "can_collect", "can_invite", "can_post",
    "can_schedule", "can_manage", "restriction_type", "restriction_source", "restriction_confidence",
    "restriction_reason", "restriction_started_at", "restriction_until", "last_connected_at", "last_active_at",
    "last_health_check_at", "last_collect_at", "last_invite_attempt_at", "last_invite_success_at", "last_post_at",
    "last_schedule_at", "last_success_at", "last_error_code", "last_error_message", "last_error_at", "notes",
    "is_enabled", "enabled_for_operations", "authorization_status", "is_demo", "created_at", "updated_at",
)


class AccountRepository(BaseRepository):
    table_name = "telegram_accounts"
    columns = ACCOUNT_COLUMNS

    def create(self, account: TelegramAccount) -> TelegramAccount:
        now = utc_now_iso()
        values = asdict(account)
        values.pop("id", None)
        values["created_at"] = account.created_at or now
        values["updated_at"] = now
        account.id = self.insert(values)
        return self.get_by_id(account.id)

    def update(self, account: TelegramAccount) -> TelegramAccount:
        if account.id is None:
            raise ValueError("Account id is required for update.")
        values = asdict(account)
        values["updated_at"] = utc_now_iso()
        self.update_fields(account.id, values)
        return self.get_by_id(account.id)

    def get_by_id(self, account_id: int) -> TelegramAccount | None:
        return TelegramAccount.from_row(self.find_by_id(account_id))

    def get_by_telegram_id(self, telegram_user_id: int) -> TelegramAccount | None:
        row = self.db.fetch_one(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts WHERE telegram_user_id = ?",
            (telegram_user_id,),
        )
        return TelegramAccount.from_row(row)

    def get_all(self) -> list[TelegramAccount]:
        rows = self.db.fetch_all(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts ORDER BY id DESC"
        )
        return [TelegramAccount.from_row(row) for row in rows]

    def get_enabled_accounts(self) -> list[TelegramAccount]:
        rows = self.db.fetch_all(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts WHERE is_enabled = 1 ORDER BY id"
        )
        return [TelegramAccount.from_row(row) for row in rows]

    def search(self, query: str) -> list[TelegramAccount]:
        term = f"%{query.strip()}%"
        rows = self.db.fetch_all(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts "
            "WHERE username LIKE ? OR phone LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
            "OR CAST(telegram_user_id AS TEXT) LIKE ? ORDER BY id DESC",
            (term, term, term, term, term),
        )
        return [TelegramAccount.from_row(row) for row in rows]

    def filter_by_health(self, status: str) -> list[TelegramAccount]:
        rows = self.db.fetch_all(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts WHERE health_status = ? ORDER BY id DESC",
            (status,),
        )
        return [TelegramAccount.from_row(row) for row in rows]

    def update_connection_status(self, account_id: int, status: str) -> bool:
        return self.update_fields(account_id, {"connection_status": status, "updated_at": utc_now_iso()})

    def update_health_status(self, account_id: int, status: str) -> bool:
        return self.update_fields(
            account_id, {"health_status": status, "last_health_check_at": utc_now_iso(), "updated_at": utc_now_iso()}
        )

    def update_capabilities(self, account_id: int, **capabilities: bool) -> bool:
        allowed = {"can_collect", "can_invite", "can_post", "can_schedule", "can_manage"}
        values = {key: int(bool(value)) for key, value in capabilities.items() if key in allowed}
        values["updated_at"] = utc_now_iso()
        return self.update_fields(account_id, values)

    def update_last_activity(self, account_id: int, field: str = "last_active_at") -> bool:
        allowed = {
            "last_active_at", "last_collect_at", "last_invite_attempt_at", "last_invite_success_at",
            "last_post_at", "last_schedule_at", "last_success_at", "last_connected_at",
        }
        if field not in allowed:
            raise ValueError("Unsupported activity field.")
        return self.update_fields(account_id, {field: utc_now_iso(), "updated_at": utc_now_iso()})

    def update_last_error(self, account_id: int, code: str | None, message: str | None) -> bool:
        return self.update_fields(
            account_id,
            {"last_error_code": code, "last_error_message": message, "last_error_at": utc_now_iso(), "updated_at": utc_now_iso()},
        )


    def update_authorization_status(self, account_id: int, status: str) -> bool:
        return self.update_fields(account_id, {"authorization_status": status, "updated_at": utc_now_iso()})

    def update_telegram_profile(self, account_id: int, profile, session_path: str | None = None) -> TelegramAccount:
        values = {
            "telegram_user_id": int(profile.telegram_user_id),
            "username": profile.username,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "phone": profile.phone,
            "is_premium": int(bool(profile.is_premium)),
            "authorization_status": "AUTHORIZED",
            "last_active_at": utc_now_iso(),
            "last_success_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        if session_path is not None:
            values["session_path"] = session_path
        self.update_fields(account_id, values)
        return self.get_by_id(account_id)

    def set_session_path(self, account_id: int, session_path: str | None) -> bool:
        return self.update_fields(account_id, {"session_path": session_path, "updated_at": utc_now_iso()})

    def count_all(self) -> int:
        return self.count()

    def count_by_health(self, status: str) -> int:
        return self.count("health_status = ?", (status,))

    def set_enabled(self, account_id: int, enabled: bool) -> bool:
        return self.update_fields(account_id, {"is_enabled": int(enabled), "updated_at": utc_now_iso()})


    def set_operations_enabled(self, account_id: int, enabled: bool) -> bool:
        """Enable/disable assignment to NEW operational jobs without removing the account."""
        return self.update_fields(account_id, {"enabled_for_operations": int(bool(enabled)), "updated_at": utc_now_iso()})

    def get_operations_enabled_accounts(self) -> list[TelegramAccount]:
        rows = self.db.fetch_all(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM telegram_accounts "
            "WHERE is_enabled=1 AND enabled_for_operations=1 ORDER BY id"
        )
        return [TelegramAccount.from_row(row) for row in rows]

    def has_related_history(self, account_id: int) -> bool:
        checks = (
            ("account_activity", "account_id"), ("account_restrictions", "account_id"),
            ("group_accounts", "account_id"), ("jobs", "account_id"), ("campaign_targets", "account_id"),
        )
        for table, column in checks:
            row = self.db.fetch_one(f"SELECT 1 AS found FROM {table} WHERE {column} = ? LIMIT 1", (account_id,))
            if row:
                return True
        return False

    def get_tags(self, account_id: int) -> list[str]:
        rows = self.db.fetch_all(
            "SELECT t.name FROM account_tags t JOIN account_tag_links l ON l.tag_id = t.id "
            "WHERE l.account_id = ? ORDER BY t.name", (account_id,)
        )
        return [str(row["name"]) for row in rows]

    def replace_tags(self, account_id: int, tags: list[str]) -> None:
        clean = sorted({tag.strip() for tag in tags if tag.strip()})
        with self.db.transaction():
            self.db.execute("DELETE FROM account_tag_links WHERE account_id = ?", (account_id,))
            for tag in clean:
                self.db.execute("INSERT OR IGNORE INTO account_tags(name, created_at) VALUES (?, ?)", (tag, utc_now_iso()))
                row = self.db.fetch_one("SELECT id FROM account_tags WHERE name = ?", (tag,))
                if row:
                    self.db.execute(
                        "INSERT OR IGNORE INTO account_tag_links(account_id, tag_id) VALUES (?, ?)",
                        (account_id, int(row["id"])),
                    )

    def get_page(self, page: int, page_size: int, search: str | None = None, health: str | None = None, status: str | None = None):
        where: list[str] = []
        params: list[Any] = []
        if search:
            term = f"%{search.strip()}%"
            where.append("(username LIKE ? OR phone LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR CAST(telegram_user_id AS TEXT) LIKE ?)")
            params.extend([term] * 5)
        if health and health.upper() != "ALL":
            where.append("health_status = ?")
            params.append(health.upper().replace(" ", "_"))
        if status and status.upper() != "ALL":
            where.append("connection_status = ?")
            params.append(status.upper().replace(" ", "_"))
        clause = " WHERE " + " AND ".join(where) if where else ""
        count_row = self.db.fetch_one(f"SELECT COUNT(*) AS count FROM telegram_accounts{clause}", tuple(params))
        offset = max(0, (max(1, page) - 1) * page_size)
        rows = self.db.fetch_all(
            f"SELECT {', '.join('a.' + c for c in ACCOUNT_COLUMNS)}, COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM account_tag_links l JOIN account_tags t ON t.id=l.tag_id WHERE l.account_id=a.id), '') AS tags FROM telegram_accounts a{clause.replace('health_status', 'a.health_status').replace('connection_status', 'a.connection_status').replace('username', 'a.username').replace('phone', 'a.phone').replace('first_name', 'a.first_name').replace('last_name', 'a.last_name').replace('telegram_user_id', 'a.telegram_user_id')} ORDER BY a.id DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        )
        return [TelegramAccount.from_row(row) for row in rows], int(count_row["count"] if count_row else 0)
    def get_pool_page(self, page: int, page_size: int, search: str | None = None, *, enabled: str | None = None, health: str | None = None, restriction: str | None = None, safety: str | None = None):
        where=[];params=[]
        if search:
            term=f"%{search.strip()}%"
            where.append("(a.username LIKE ? OR a.first_name LIKE ? OR a.last_name LIKE ? OR CAST(a.telegram_user_id AS TEXT) LIKE ?)")
            params.extend([term]*4)
        if enabled and str(enabled).upper() not in {"ALL",""}:
            where.append("a.enabled_for_operations=?")
            params.append(1 if str(enabled).upper() in {"YES","ENABLED","ON","TRUE","1"} else 0)
        if health and str(health).upper() not in {"ALL",""}:
            where.append("a.health_status=?");params.append(str(health).upper().replace(" ","_"))
        if restriction and str(restriction).upper() not in {"ALL",""}:
            if str(restriction).upper() in {"NONE","NO RESTRICTION"}:
                where.append("COALESCE(a.restriction_type,'') IN ('','NONE','NONE_KNOWN','UNKNOWN')")
            else:
                where.append("a.restriction_type=?");params.append(str(restriction).upper().replace(" ","_"))
        if safety and str(safety).upper() not in {"ALL",""}:
            where.append("COALESCE(asp.safety_state,'NORMAL')=?");params.append(str(safety).upper().replace(" ","_"))
        clause=" WHERE "+" AND ".join(where) if where else ""
        source="telegram_accounts a LEFT JOIN account_safety_profiles asp ON asp.account_id=a.id"
        count_row=self.db.fetch_one(f"SELECT COUNT(*) count FROM {source}{clause}",tuple(params))
        offset=max(0,(max(1,int(page))-1)*int(page_size))
        rows=self.db.fetch_all(f"""
            SELECT a.*,
                   COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM account_tag_links l JOIN account_tags t ON t.id=l.tag_id WHERE l.account_id=a.id),'') tags,
                   (SELECT COUNT(*) FROM group_accounts ga WHERE ga.account_id=a.id) groups_count,
                   COALESCE((SELECT MAX(COALESCE(ga.can_invite,0)) FROM group_accounts ga WHERE ga.account_id=a.id),0) mapped_can_invite,
                   COALESCE((SELECT MAX(COALESCE(ga.can_post,0)) FROM group_accounts ga WHERE ga.account_id=a.id),0) mapped_can_post,
                   COALESCE((SELECT j.job_type FROM jobs j WHERE j.account_id=a.id AND j.status IN ('RUNNING','QUEUED','PAUSED') ORDER BY j.id DESC LIMIT 1),'') current_job
            FROM {source}{clause}
            ORDER BY a.id DESC LIMIT ? OFFSET ?
        """,(*params,int(page_size),offset))
        return [dict(row) for row in rows], int(count_row["count"] if count_row else 0)

    def set_operations_enabled_many(self, account_ids: list[int], enabled: bool) -> int:
        ids=sorted({int(x) for x in account_ids if x})
        if not ids:return 0
        marks=','.join('?' for _ in ids);now=utc_now_iso()
        with self.db.transaction():
            cur=self.db.execute(f"UPDATE telegram_accounts SET enabled_for_operations=?,updated_at=? WHERE id IN ({marks})",(int(bool(enabled)),now,*ids))
        return int(cur.rowcount or 0)
