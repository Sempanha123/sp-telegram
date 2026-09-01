from __future__ import annotations
from dataclasses import asdict
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import Schedule
from app.utils.formatters import utc_now_iso

COLS=("id","campaign_id","schedule_type","run_at","timezone","repeat_rule","next_run_at","last_run_at","is_enabled","status","occurrence_key","last_error_code","last_error_message","missed_policy","created_at","updated_at")
class ScheduleRepository(BaseRepository):
    table_name='schedules';columns=COLS
    def create(self,item:Schedule):
        now=utc_now_iso();data=asdict(item);data.pop('id',None);data={k:v for k,v in data.items() if k in COLS};data['created_at']=item.created_at or now;data['updated_at']=now;item.id=self.insert(data);return self.get_by_id(item.id)
    def update(self,item:Schedule):
        if item.id is None:raise ValueError('Schedule id is required.')
        data=asdict(item);data={k:v for k,v in data.items() if k in COLS};data['updated_at']=utc_now_iso();self.update_fields(item.id,data);return self.get_by_id(item.id)
    def get_by_id(self,id:int):return Schedule.from_row(self.find_by_id(id))
    def get_all(self):
        rows=self.db.fetch_all(f"""SELECT {', '.join('s.'+c for c in COLS)},c.name campaign_name FROM schedules s JOIN campaigns c ON c.id=s.campaign_id ORDER BY COALESCE(s.next_run_at,s.run_at) ASC""");return [Schedule.from_row(r) for r in rows]
    def get_enabled(self):return [Schedule.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM schedules WHERE is_enabled=1 AND status NOT IN ('CANCELLED','SENT','EXPIRED') ORDER BY next_run_at")]
    def get_due(self,now_iso:str):return [Schedule.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM schedules WHERE is_enabled=1 AND status IN ('PENDING','SCHEDULED','ACTIVE') AND next_run_at IS NOT NULL AND next_run_at<=? ORDER BY next_run_at",(now_iso,))]
    def pause(self,id:int):return self.update_fields(id,{'status':'PAUSED','is_enabled':0,'updated_at':utc_now_iso()})
    def resume(self,id:int):return self.update_fields(id,{'status':'SCHEDULED','is_enabled':1,'updated_at':utc_now_iso()})
    def cancel(self,id:int):return self.update_fields(id,{'is_enabled':0,'status':'CANCELLED','updated_at':utc_now_iso()})
    def update_next_run(self,id:int,value:str|None):return self.update_fields(id,{'next_run_at':value,'updated_at':utc_now_iso()})
    def update_last_run(self,id:int,value:str|None=None):return self.update_fields(id,{'last_run_at':value or utc_now_iso(),'updated_at':utc_now_iso()})
    def set_status(self,id:int,status:str,code=None,message=None):return self.update_fields(id,{'status':status,'last_error_code':code,'last_error_message':message,'updated_at':utc_now_iso()})
