from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso

class CampaignTargetMessageRepository(BaseRepository):
    table_name="campaign_target_messages"
    columns=("id","campaign_target_id","campaign_message_id","telegram_message_id","telegram_scheduled_message_id","status","scheduled_at","sent_at","error_code","error_message","created_at","updated_at")
    def upsert(self,target_id:int,message_id:int,*,status:str="PENDING",telegram_message_id=None,telegram_scheduled_message_id=None,scheduled_at=None,sent_at=None,error_code=None,error_message=None):
        now=utc_now_iso(); self.db.execute("""INSERT INTO campaign_target_messages(campaign_target_id,campaign_message_id,telegram_message_id,telegram_scheduled_message_id,status,scheduled_at,sent_at,error_code,error_message,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(campaign_target_id,campaign_message_id) DO UPDATE SET telegram_message_id=excluded.telegram_message_id,telegram_scheduled_message_id=excluded.telegram_scheduled_message_id,status=excluded.status,scheduled_at=excluded.scheduled_at,sent_at=excluded.sent_at,error_code=excluded.error_code,error_message=excluded.error_message,updated_at=excluded.updated_at""",(target_id,message_id,telegram_message_id,telegram_scheduled_message_id,status,scheduled_at,sent_at,error_code,error_message,now,now))
    def get_for_target(self,target_id:int): return [dict(r) for r in self.db.fetch_all("SELECT * FROM campaign_target_messages WHERE campaign_target_id=? ORDER BY campaign_message_id",(target_id,))]
