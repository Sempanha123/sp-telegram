from __future__ import annotations
from dataclasses import asdict
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import AccountActivity
from app.utils.formatters import utc_now_iso

COLS=("id","account_id","action_type","status","target_type","target_id","message","metadata_json","created_at")
class AccountActivityRepository(BaseRepository):
    table_name="account_activity"; columns=COLS
    def create(self,item:AccountActivity):
        data=asdict(item); data.pop("id",None); data["created_at"]=item.created_at or utc_now_iso(); item.id=self.insert(data); return AccountActivity.from_row(self.find_by_id(item.id))
    def get_recent(self,account_id:int,limit:int=100):
        rows=self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM account_activity WHERE account_id=? ORDER BY created_at DESC LIMIT ?",(account_id,limit)); return [AccountActivity.from_row(r) for r in rows]

    def delete_for_account(self, account_id: int) -> int:
        cursor = self.db.execute("DELETE FROM account_activity WHERE account_id = ?", (account_id,))
        return int(cursor.rowcount)
