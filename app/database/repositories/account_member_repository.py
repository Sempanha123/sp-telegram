from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.models.entities import AccountMemberState
from app.utils.formatters import utc_now_iso

COLS=("id","account_id","member_id","state","last_error_code","last_error_message","last_checked_at","created_at","updated_at")

class AccountMemberStateRepository(BaseRepository):
    table_name="account_member_states"; columns=COLS
    def upsert_state(self,account_id:int,member_id:int,state:str,*,error_code=None,error_message=None):
        now=utc_now_iso(); self.db.execute("""INSERT INTO account_member_states(account_id,member_id,state,last_error_code,last_error_message,last_checked_at,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(account_id,member_id) DO UPDATE SET state=excluded.state,last_error_code=excluded.last_error_code,last_error_message=excluded.last_error_message,last_checked_at=excluded.last_checked_at,updated_at=excluded.updated_at""",(account_id,member_id,state,error_code,error_message,now,now,now));
        return AccountMemberState.from_row(self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM account_member_states WHERE account_id=? AND member_id=?",(account_id,member_id)))
