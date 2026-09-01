from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import MemberSyncRun
from app.utils.formatters import utc_now_iso

COLS=("id","sync_run_id","job_id","group_id","account_id","availability","processed","inserted","updated","unchanged","duplicates","excluded","errors","started_at","completed_at","status","error_code","error_message")
class MemberSyncRunRepository(BaseRepository):
    table_name="member_sync_runs"; columns=COLS
    def create_run(self,sync_run_id:str,group_id:int,account_id:int,*,job_id=None,availability="UNKNOWN"):
        now=utc_now_iso(); rid=self.insert({"sync_run_id":sync_run_id,"job_id":job_id,"group_id":group_id,"account_id":account_id,"availability":availability,"started_at":now,"status":"VALIDATING"});return MemberSyncRun.from_row(self.find_by_id(rid))
    def update_run(self,run_id:int,**values): self.update_fields(run_id,values); return MemberSyncRun.from_row(self.find_by_id(run_id))
    def finish(self,run_id:int,status:str,**counts): return self.update_run(run_id,status=status,completed_at=utc_now_iso(),**counts)
    def get_recent(self,group_id:int|None=None,limit:int=50):
        where=" WHERE group_id=?" if group_id else "";params=(group_id,limit) if group_id else (limit,);rows=self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM member_sync_runs{where} ORDER BY started_at DESC LIMIT ?",params);return [MemberSyncRun.from_row(r) for r in rows]
