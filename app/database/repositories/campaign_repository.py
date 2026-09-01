from __future__ import annotations
from dataclasses import asdict, replace
from typing import Any
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import Campaign
from app.utils.formatters import utc_now_iso

COLS=("id","name","description","campaign_type","status","schedule_type","send_at","timezone","repeat_rule","default_account_id","template_id","created_by","created_at","updated_at","started_at","completed_at","last_run_at","next_run_at","total_targets","success_count","failed_count","skipped_count")
class CampaignRepository(BaseRepository):
    table_name='campaigns'; columns=COLS
    def create(self,item:Campaign):
        now=utc_now_iso(); data=asdict(item); data.pop('id',None); data={k:v for k,v in data.items() if k in COLS}; data['created_at']=item.created_at or now;data['updated_at']=now;item.id=self.insert(data);return self.get_by_id(item.id)
    def update(self,item:Campaign):
        if item.id is None:raise ValueError('Campaign id is required.')
        data=asdict(item);data={k:v for k,v in data.items() if k in COLS};data['updated_at']=utc_now_iso();self.update_fields(item.id,data);return self.get_by_id(item.id)
    def get_by_id(self,id:int):return Campaign.from_row(self.find_by_id(id))
    def get_all(self):return [Campaign.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaigns ORDER BY id DESC")]
    def get_page(self,page:int,page_size:int,search:str|None=None,status:str|None=None,campaign_type:str|None=None,schedule_type:str|None=None,group_id:int|None=None,account_id:int|None=None):
        where=[];params:list[Any]=[]
        if search:where.append('(c.name LIKE ? OR c.description LIKE ?)');params.extend([f'%{search.strip()}%']*2)
        if status and status.upper()!='ALL':where.append('c.status=?');params.append(status.upper().replace(' ','_'))
        if campaign_type and campaign_type.upper()!='ALL':where.append('c.campaign_type=?');params.append(campaign_type.upper().replace(' ','_'))
        if schedule_type and schedule_type.upper()!='ALL':where.append('c.schedule_type=?');params.append(schedule_type.upper().replace(' ','_'))
        if group_id:where.append('EXISTS(SELECT 1 FROM campaign_targets x WHERE x.campaign_id=c.id AND x.group_id=?)');params.append(group_id)
        if account_id:where.append('EXISTS(SELECT 1 FROM campaign_targets x WHERE x.campaign_id=c.id AND x.account_id=?)');params.append(account_id)
        clause=' WHERE '+' AND '.join(where) if where else ''
        count=self.db.fetch_one(f'SELECT COUNT(*) count FROM campaigns c{clause}',tuple(params));off=(max(1,page)-1)*page_size
        rows=self.db.fetch_all(f"""SELECT {', '.join('c.'+x for x in COLS)},
        (SELECT COUNT(*) FROM campaign_targets t WHERE t.campaign_id=c.id) target_count,
        (SELECT COUNT(*) FROM campaign_messages m WHERE m.campaign_id=c.id) message_count,
        (SELECT COUNT(DISTINCT t.account_id) FROM campaign_targets t WHERE t.campaign_id=c.id) account_count,
        COALESCE((SELECT a.first_name FROM telegram_accounts a WHERE a.id=c.default_account_id),'Assigned') posting_account
        FROM campaigns c{clause} ORDER BY c.updated_at DESC,c.id DESC LIMIT ? OFFSET ?""",(*params,page_size,off))
        return [Campaign.from_row(r) for r in rows],int(count['count'] if count else 0)
    def search(self,query:str):return self.get_page(1,100,query)[0]
    def set_status(self,id:int,status:str):return self.update_fields(id,{'status':status,'updated_at':utc_now_iso()})
    def set_counts(self,id:int,*,total=None,success=None,failed=None,skipped=None):
        values={'updated_at':utc_now_iso()}
        if total is not None:values['total_targets']=int(total)
        if success is not None:values['success_count']=int(success)
        if failed is not None:values['failed_count']=int(failed)
        if skipped is not None:values['skipped_count']=int(skipped)
        return self.update_fields(id,values)
    def update_run_times(self,id:int,*,started_at=None,completed_at=None,last_run_at=None,next_run_at=None):
        values={'updated_at':utc_now_iso()}
        for k,v in [('started_at',started_at),('completed_at',completed_at),('last_run_at',last_run_at),('next_run_at',next_run_at)]:
            if v is not None:values[k]=v
        return self.update_fields(id,values)
    def archive(self,id:int):return self.set_status(id,'ARCHIVED')
    def unarchive(self,id:int):return self.set_status(id,'DRAFT')
    def delete_draft(self,id:int):
        row=self.get_by_id(id)
        if not row: return False
        if row.status not in {'DRAFT','CANCELLED'}: raise ValueError('Only unused drafts or cancelled campaigns can be deleted. Archive sent campaigns instead.')
        sent=self.db.fetch_one("SELECT 1 FROM campaign_deliveries WHERE campaign_id=? AND status IN ('SENT','SCHEDULED') LIMIT 1",(id,))
        if sent:raise ValueError('This campaign has delivery history and cannot be deleted. Archive it instead.')
        return super().delete(id)
    def delete(self,id:int):
        row=self.get_by_id(id)
        if not row:return False
        if row.status in {'RUNNING','SCHEDULED','PAUSED'}:self.set_status(id,'CANCELLED');return True
        # Hard delete: campaign_deliveries has ON DELETE RESTRICT, so remove
        # delivery history first (campaign_rendered_messages cascades), then the
        # campaign row (targets/messages/target_messages cascade).
        with self.db.transaction():
            self.db.execute("DELETE FROM campaign_deliveries WHERE campaign_id=?",(id,))
            return super().delete(id)
    def duplicate(self,id:int):
        src=self.get_by_id(id)
        if not src:return None
        cp=replace(src,id=None,name=f'{src.name} Copy',status='DRAFT',started_at=None,completed_at=None,last_run_at=None,next_run_at=None,total_targets=0,success_count=0,failed_count=0,skipped_count=0,created_at=None,updated_at=None)
        created=self.create(cp);now=utc_now_iso()
        with self.db.transaction():
            self.db.execute("""INSERT INTO campaign_messages(campaign_id,position,message_type,body,caption,media_path,media_name,media_size,content_hash,parse_mode,disable_link_preview,created_at,updated_at)
            SELECT ?,position,message_type,body,caption,media_path,media_name,media_size,content_hash,parse_mode,disable_link_preview,?,? FROM campaign_messages WHERE campaign_id=?""",(created.id,now,now,id))
            self.db.execute("""INSERT INTO campaign_targets(campaign_id,group_id,account_id,status,attempt_count,created_at,updated_at)
            SELECT ?,group_id,account_id,'PENDING',0,?,? FROM campaign_targets WHERE campaign_id=?""",(created.id,now,now,id))
        return self.get_by_id(created.id)
    def get_scheduled_campaigns(self):return [Campaign.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaigns WHERE status='SCHEDULED' ORDER BY next_run_at")]
    def get_active_campaigns(self):return [Campaign.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaigns WHERE status IN ('VALIDATING','READY','SCHEDULED','RUNNING','PAUSED') ORDER BY id DESC")]
    def count_active(self):return self.count("status IN ('VALIDATING','READY','SCHEDULED','RUNNING','PAUSED')")
    def count_scheduled(self):return self.count("status='SCHEDULED'")
