from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from app.campaign.recurrence import RecurrenceRule
from app.models.entities import Schedule
from app.utils.formatters import utc_now_iso

class CampaignSchedulerService:
    def __init__(self,repository,campaign_repository):self.repository=repository;self.campaign_repository=campaign_repository
    def create(self,data):
        cid=int(data.get('campaign_id') or 0)
        if not cid or not self.campaign_repository.get_by_id(cid):raise ValueError('Select a campaign before creating a schedule.')
        run=data.get('run_at') or data.get('next_run_at');stype=str(data.get('schedule_type') or 'ONCE').upper();repeat=data.get('repeat_rule')
        item=Schedule(campaign_id=cid,schedule_type=stype,run_at=run,timezone=data.get('timezone') or 'UTC',repeat_rule=repeat,next_run_at=data.get('next_run_at') or run,status='SCHEDULED',missed_policy=data.get('missed_policy') or 'ASK_ME')
        created=self.repository.create(item);self.campaign_repository.update_fields(cid,{'status':'SCHEDULED','schedule_type':stype,'send_at':run,'timezone':item.timezone,'repeat_rule':repeat,'next_run_at':created.next_run_at,'updated_at':utc_now_iso()});return created
    def update(self,id,data):
        item=self.repository.get_by_id(id)
        if not item:raise ValueError('Schedule not found.')
        for f in ('schedule_type','run_at','timezone','repeat_rule','next_run_at','status','missed_policy'):
            if f in data:setattr(item,f,data[f])
        return self.repository.update(item)
    def pause(self,id):return self.repository.pause(id)
    def resume(self,id):return self.repository.resume(id)
    def cancel(self,id):return self.repository.cancel(id)
    def due(self):return self.repository.get_due(utc_now_iso())
    def recover(self):return {'enabled':self.repository.get_enabled(),'due':self.due()}
    def next_occurrence(self,schedule,from_iso=None):
        base=datetime.fromisoformat((from_iso or schedule.next_run_at or schedule.run_at).replace('Z','+00:00'))
        if schedule.schedule_type in {'ONCE','SEND_NOW'}:return None
        try:data=json.loads(schedule.repeat_rule) if schedule.repeat_rule and schedule.repeat_rule.strip().startswith('{') else {}
        except Exception:data={}
        rule=RecurrenceRule(str(data.get('frequency') or schedule.schedule_type or 'DAILY').upper(),int(data.get('interval') or 1),list(data.get('weekdays') or []),data.get('time'),schedule.timezone or 'UTC')
        nxt=rule.next_after(base);return nxt.astimezone(timezone.utc).isoformat() if nxt else None
    def advance_to_next_valid(self,id,now_iso=None):
        item=self.repository.get_by_id(id)
        if not item:return None
        now=datetime.fromisoformat((now_iso or utc_now_iso()).replace('Z','+00:00')).astimezone(timezone.utc);cutoff=now+timedelta(seconds=1)
        current=item.next_run_at or item.run_at
        for _ in range(500):
            if not current:break
            cur=datetime.fromisoformat(current.replace('Z','+00:00')).astimezone(timezone.utc)
            if cur>cutoff:break
            nxt=self.next_occurrence(item,current)
            if not nxt:current=None;break
            current=nxt
        self.repository.update_next_run(id,current)
        self.repository.set_status(id,'ACTIVE' if current else 'EXPIRED')
        if not current:self.repository.update_fields(id,{'is_enabled':0})
        return self.repository.get_by_id(id)
    def complete_occurrence(self,id):
        item=self.repository.get_by_id(id);now=utc_now_iso();self.repository.update_last_run(id,now);nxt=self.next_occurrence(item)
        if nxt:self.repository.update_next_run(id,nxt);self.repository.set_status(id,'SCHEDULED')
        else:self.repository.update_next_run(id,None);self.repository.set_status(id,'SENT');self.repository.update_fields(id,{'is_enabled':0})
        return self.repository.get_by_id(id)
