from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import CampaignDelivery
from app.utils.formatters import utc_now_iso

COLS=("id","campaign_id","campaign_target_id","campaign_message_id","occurrence_key","content_hash","telegram_message_id","telegram_scheduled_message_id","status","scheduled_for","sent_at","created_at","updated_at")

class DeliveryRepository(BaseRepository):
    table_name="campaign_deliveries"; columns=COLS
    def create_delivery(self, campaign_id:int, target_id:int, message_id:int, occurrence_key:str, content_hash:str, scheduled_for:str|None=None):
        now=utc_now_iso()
        self.db.execute("""INSERT INTO campaign_deliveries(campaign_id,campaign_target_id,campaign_message_id,occurrence_key,content_hash,status,scheduled_for,created_at,updated_at)
        VALUES(?,?,?,?,?,'PENDING',?,?,?) ON CONFLICT(campaign_target_id,campaign_message_id,occurrence_key) DO NOTHING""",(campaign_id,target_id,message_id,occurrence_key,content_hash,scheduled_for,now,now))
        return self.get_occurrence(target_id,message_id,occurrence_key)
    def get_occurrence(self,target_id:int,message_id:int,occurrence_key:str):
        return CampaignDelivery.from_row(self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM campaign_deliveries WHERE campaign_target_id=? AND campaign_message_id=? AND occurrence_key=?",(target_id,message_id,occurrence_key)))
    def exists_occurrence(self,target_id:int,message_id:int,occurrence_key:str,statuses=("SENT","SCHEDULED","SKIPPED")):
        marks=','.join('?' for _ in statuses); row=self.db.fetch_one(f"SELECT 1 ok FROM campaign_deliveries WHERE campaign_target_id=? AND campaign_message_id=? AND occurrence_key=? AND status IN ({marks}) LIMIT 1",(target_id,message_id,occurrence_key,*statuses)); return row is not None
    def _mark(self,id:int,status:str,**extra): extra.update(status=status,updated_at=utc_now_iso()); return self.update_fields(id,extra)
    def mark_sending(self,id:int): return self._mark(id,"SENDING")
    def mark_sent(self,id:int,message_id:str,sent_at:str|None=None): return self._mark(id,"SENT",telegram_message_id=str(message_id),sent_at=sent_at or utc_now_iso())
    def mark_scheduled(self,id:int,message_id:str,scheduled_for:str|None=None): return self._mark(id,"SCHEDULED",telegram_scheduled_message_id=str(message_id),scheduled_for=scheduled_for)
    def mark_failed(self,id:int): return self._mark(id,"FAILED")
    def mark_skipped(self,id:int): return self._mark(id,"SKIPPED")
    def mark_reconcile_required(self,id:int): return self._mark(id,"RECONCILE_REQUIRED")
    def get_campaign_deliveries(self,campaign_id:int): return [CampaignDelivery.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaign_deliveries WHERE campaign_id=? ORDER BY id",(campaign_id,))]
    def get_target_history(self,target_id:int): return [CampaignDelivery.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaign_deliveries WHERE campaign_target_id=? ORDER BY id DESC",(target_id,))]
