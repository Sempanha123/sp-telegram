from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import CampaignTarget
from app.utils.formatters import utc_now_iso

COLS=("id","campaign_id","group_id","account_id","status","telegram_message_id","telegram_scheduled_message_id","scheduled_message_id","scheduled_at","sent_at","attempt_count","last_error_code","last_error_message","created_at","updated_at")
class CampaignTargetRepository(BaseRepository):
    table_name='campaign_targets';columns=COLS
    def create_targets(self,campaign_id:int,targets:list[tuple[int,int|None]]):return self.replace_targets(campaign_id,targets)
    def replace_targets(self,campaign_id:int,targets:list[tuple[int,int|None]]):
        now=utc_now_iso()
        with self.db.transaction():
            self.db.execute('DELETE FROM campaign_targets WHERE campaign_id=?',(campaign_id,))
            self.db.execute_many("INSERT INTO campaign_targets(campaign_id,group_id,account_id,status,attempt_count,created_at,updated_at) VALUES(?,?,?,'PENDING',0,?,?)",[(campaign_id,int(g),int(a) if a else None,now,now) for g,a in targets]) if targets else None
        return self.get_targets(campaign_id)
    def get_targets(self,campaign_id:int):
        rows=self.db.fetch_all(f"""SELECT {', '.join('ct.'+c for c in COLS)},g.title group_title,g.username group_username,COALESCE(a.first_name,a.username,CAST(a.id AS TEXT)) account_name
        FROM campaign_targets ct JOIN groups g ON g.id=ct.group_id LEFT JOIN telegram_accounts a ON a.id=ct.account_id WHERE ct.campaign_id=? ORDER BY ct.id""",(campaign_id,));return [CampaignTarget.from_row(r) for r in rows]
    def get_by_id(self,id:int):return CampaignTarget.from_row(self.find_by_id(id))
    def update_status(self,id:int,status:str):return self.update_fields(id,{'status':status,'updated_at':utc_now_iso()})
    def set_telegram_message_id(self,id:int,message_id:str,sent_at:str|None=None):return self.update_fields(id,{'telegram_message_id':str(message_id),'sent_at':sent_at or utc_now_iso(),'status':'SENT','updated_at':utc_now_iso()})
    def set_scheduled_message_id(self,id:int,message_id:str,scheduled_at:str|None=None):return self.update_fields(id,{'telegram_scheduled_message_id':str(message_id),'scheduled_at':scheduled_at,'status':'SCHEDULED','updated_at':utc_now_iso()})
    def record_error(self,id:int,code:str|None,message:str|None,status='FAILED'):return self.update_fields(id,{'last_error_code':code,'last_error_message':message,'status':status,'updated_at':utc_now_iso()})
    def increment_attempt(self,id:int):return self.db.execute('UPDATE campaign_targets SET attempt_count=attempt_count+1,updated_at=? WHERE id=?',(utc_now_iso(),id)).rowcount>0
    def count_by_status(self,campaign_id:int,status:str):return self.count('campaign_id=? AND status=?',(campaign_id,status))
    def count_for_campaign(self,campaign_id:int):return self.count('campaign_id=?',(campaign_id,))
