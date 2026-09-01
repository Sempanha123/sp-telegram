from __future__ import annotations
import logging
from datetime import datetime,timezone
from app.services.campaign_scheduler_service import CampaignSchedulerService
from app.utils.formatters import utc_now_iso
_LOG = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self,repository,campaign_repository=None,*,campaign_service=None,telegram_schedule_service=None,target_repository=None,delivery_repository=None,group_repository=None,job_repository=None):
        self.repository=repository;self.campaign_repository=campaign_repository;self.local=CampaignSchedulerService(repository,campaign_repository) if campaign_repository else None;self.feature_gate=None;self.campaign_service=campaign_service;self.telegram_schedule_service=telegram_schedule_service;self.target_repository=target_repository;self.delivery_repository=delivery_repository;self.group_repository=group_repository;self.job_repository=job_repository
    def get_schedules(self):return self.repository.get_all()
    def save_schedule(self,data):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            stype=str(data.get("schedule_type") or "ONCE").upper();self.feature_gate.require_feature(FeatureKey.RECURRING_SCHEDULE if stype in {"REPEAT","RECURRING"} else FeatureKey.SCHEDULE_ONCE)
        return self.local.create(data) if self.local else self.repository.create(data)
    def update_schedule(self,id,data):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            current=self.repository.get_by_id(id);stype=str(data.get("schedule_type") or getattr(current,"schedule_type",None) or "ONCE").upper();self.feature_gate.require_feature(FeatureKey.RECURRING_SCHEDULE if stype in {"REPEAT","RECURRING"} else FeatureKey.SCHEDULE_ONCE)
        return self.local.update(id,data)
    def pause_schedule(self,id):return self.local.pause(id)
    def resume_schedule(self,id):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            current=self.repository.get_by_id(id);stype=str(getattr(current,"schedule_type",None) or "ONCE").upper();self.feature_gate.require_feature(FeatureKey.RECURRING_SCHEDULE if stype in {"REPEAT","RECURRING"} else FeatureKey.SCHEDULE_ONCE)
        return self.local.resume(id)
    def cancel_schedule(self,id):return self.local.cancel(id)
    def recover(self):return self.local.recover()
    async def activate_schedule(self,id,progress_callback=None):
        schedule=self.repository.get_by_id(id)
        if self.feature_gate is not None and schedule:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.RECURRING_SCHEDULE if str(schedule.schedule_type).upper() in {"REPEAT","RECURRING"} else FeatureKey.SCHEDULE_ONCE)
        if not schedule:raise ValueError('Schedule not found.')
        if not schedule.next_run_at:raise ValueError('Schedule has no next run time.')
        if schedule.schedule_type not in {'ONCE','SCHEDULE_ONCE'}:
            self.repository.set_status(id,'ACTIVE');return {'local_recurrence':True,'schedule_id':id}
        result=await self.campaign_service.schedule_native(schedule.campaign_id,schedule.next_run_at,occurrence_key=schedule.next_run_at,progress_callback=progress_callback)
        self.repository.set_status(id,'SCHEDULED' if result.status in {'SCHEDULED','PARTIAL_SUCCESS'} else 'FAILED');return result
    async def run_now(self,id,progress_callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.SCHEDULE_ONCE)
        schedule=self.repository.get_by_id(id)
        if not schedule:raise ValueError('Schedule not found.')
        # Intentionally does not change recurrence configuration.
        return await self.campaign_service.run(schedule.campaign_id,occurrence_key='manual:'+utc_now_iso(),progress_callback=progress_callback)
    async def dispatch_occurrence(self,id,progress_callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.RECURRING_SCHEDULE)
        schedule=self.repository.get_by_id(id)
        if not schedule:raise ValueError('Schedule not found.')
        occurrence=schedule.next_run_at or schedule.run_at
        if not occurrence:raise ValueError('Schedule has no due occurrence.')
        result=await self.campaign_service.run(schedule.campaign_id,occurrence_key=occurrence,scheduled_for=occurrence,progress_callback=progress_callback)
        if result.status in {'COMPLETED','PARTIAL_SUCCESS'}:self.local.complete_occurrence(id)
        elif result.status=='PAUSED':self.repository.set_status(id,'PAUSED')
        else:self.repository.set_status(id,'FAILED')
        return result
    def advance_missed(self,id):return self.local.advance_to_next_valid(id)
    async def cancel_remote(self,id):
        schedule=self.repository.get_by_id(id)
        if not schedule:return {'cancelled':0,'failed':0}
        deliveries=[d for d in self.delivery_repository.get_campaign_deliveries(schedule.campaign_id) if d.status=='SCHEDULED' and d.telegram_scheduled_message_id and (not schedule.next_run_at or d.occurrence_key==schedule.next_run_at)]
        targets={t.id:t for t in self.target_repository.get_targets(schedule.campaign_id)};cancelled=failed=0
        for d in deliveries:
            target=targets.get(d.campaign_target_id);group=self.group_repository.get_by_id(target.group_id) if target else None
            if not target or not group:failed+=1;continue
            peer=group.username or int(group.telegram_group_id)
            try:await self.telegram_schedule_service.cancel(target.account_id,peer,[int(d.telegram_scheduled_message_id)]);self.delivery_repository.update_fields(d.id,{'status':'CANCELLED','updated_at':utc_now_iso()});cancelled+=1
            except Exception:failed+=1
        return {'cancelled':cancelled,'failed':failed}
    async def sync_telegram_schedule(self,id):
        schedule=self.repository.get_by_id(id)
        if not schedule:raise ValueError('Schedule not found.')
        deliveries=[d for d in self.delivery_repository.get_campaign_deliveries(schedule.campaign_id) if d.status=='SCHEDULED' and d.telegram_scheduled_message_id]
        job=self.job_repository.create_job('SCHEDULE_SYNC',campaign_id=schedule.campaign_id,status='RUNNING',total_items=len(deliveries),metadata_json='{}') if self.job_repository else None
        try:
            targets={t.id:t for t in self.target_repository.get_targets(schedule.campaign_id)};remote_by_target={};missing=[];seen=0;processed=0
            for d in deliveries:
                target=targets.get(d.campaign_target_id);group=self.group_repository.get_by_id(target.group_id) if target else None
                if not target or not group:
                    processed+=1
                    continue
                key=(target.id,target.account_id)
                if key not in remote_by_target:
                    peer=group.username or int(group.telegram_group_id);items=await self.telegram_schedule_service.list_scheduled(target.account_id,peer);remote_by_target[key]={str(getattr(x,'id','')) for x in items};seen+=len(items)
                if str(d.telegram_scheduled_message_id) not in remote_by_target[key]:
                    future=True
                    if d.scheduled_for:
                        try:future=datetime.fromisoformat(d.scheduled_for.replace('Z','+00:00')).astimezone(timezone.utc)>datetime.now(timezone.utc)
                        except (TypeError, ValueError) as exc:_LOG.warning("Malformed scheduled delivery timestamp; reconciliation required: %s", exc)
                    state='CANCELLED_EXTERNALLY' if future else 'RECONCILE_REQUIRED';self.delivery_repository.update_fields(d.id,{'status':state,'updated_at':utc_now_iso()});missing.append(d.id)
                processed+=1
                if job:self.job_repository.update_progress(job.id,int(processed*100/max(1,len(deliveries))))
            if missing:self.repository.set_status(id,'CANCELLED_EXTERNALLY' if all(self.delivery_repository.find_by_id(x)['status']=='CANCELLED_EXTERNALLY' for x in missing) else 'ACTIVE')
            if job:self.job_repository.update_fields(job.id,{'status':'COMPLETED','progress':100,'success_count':max(0,len(deliveries)-len(missing)),'skipped_count':len(missing),'finished_at':utc_now_iso(),'updated_at':utc_now_iso()})
            return {'remote_count':seen,'missing_local_refs':len(missing),'missing_delivery_ids':missing}
        except Exception as exc:
            if job:self.job_repository.update_fields(job.id,{'status':'FAILED','failed_count':1,'last_error':str(exc)[:500],'finished_at':utc_now_iso(),'updated_at':utc_now_iso()})
            raise
