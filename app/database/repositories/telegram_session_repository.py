from __future__ import annotations

from app.utils.formatters import utc_now_iso


class TelegramSessionRepository:
    def __init__(self, database) -> None:
        self.db = database

    def replace_for_account(self, account_id: int, sessions: list) -> None:
        now = utc_now_iso()
        with self.db.transaction():
            self.db.execute("DELETE FROM telegram_session_cache WHERE account_id = ?", (account_id,))
            rows = [(
                account_id, str(item.authorization_hash), item.device_model, item.platform,
                item.system_version, item.app_name, item.app_version, item.location,
                item.last_active_at, item.created_at, int(item.is_current), now,
            ) for item in sessions]
            if rows:
                self.db.execute_many(
                    "INSERT INTO telegram_session_cache(account_id,authorization_hash,device_model,platform,system_version,app_name,app_version,location,last_active_at,created_at,is_current,last_synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )

    def get_for_account(self, account_id: int) -> list[dict]:
        rows = self.db.fetch_all(
            "SELECT authorization_hash,device_model,platform,system_version,app_name,app_version,location,last_active_at,created_at,is_current,last_synced_at FROM telegram_session_cache WHERE account_id=? ORDER BY is_current DESC,last_active_at DESC",
            (account_id,),
        )
        return [dict(row) for row in rows]

    def remove(self, account_id: int, authorization_hash: str) -> None:
        self.db.execute("DELETE FROM telegram_session_cache WHERE account_id=? AND authorization_hash=?", (account_id, str(authorization_hash)))
