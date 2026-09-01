from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from app.campaign.template_renderer import CampaignTemplateRenderer
from app.models.entities import Campaign
from app.utils.formatters import utc_now_iso

class CampaignService:
    """Local campaign aggregate plus authorized managed-group execution orchestration."""
    def __init__(self,repository,target_repository,message_repository,*,group_repository=None,group_account_repository=None,account_repository=None,delivery_repository=None,target_message_repository=None,rendered_repository=None,schedule_repository=None,job_repository=None,alert_repository=None,log_repository=None,preflight_service=None,campaign_sender=None,media_service=None,account_service=None):
        self.repository=repository;self.target_repository=target_repository;self.message_repository=message_repository
        self.group_repository=group_repository;self.group_account_repository=group_account_repository;self.account_repository=account_repository;self.delivery_repository=delivery_repository;self.target_message_repository=target_message_repository;self.rendered_repository=rendered_repository;self.schedule_repository=schedule_repository;self.job_repository=job_repository;self.alert_repository=alert_repository;self.log_repository=log_repository;self.preflight_service=preflight_service;self.campaign_sender=campaign_sender;self.media_service=media_service;self.account_service=account_service
        self.renderer=CampaignTemplateRenderer();self.operations_paused=False;self.feature_gate=None;self.account_safety_service=None

    def _require(self,feature):
        if self.feature_gate is not None:self.feature_gate.require_feature(feature)
    def _require_content_features(self,data):
        if self.feature_gate is None:return
        from app.license.feature_keys import FeatureKey
        self._require(FeatureKey.CAMPAIGNS)
        ctype=self._normalize_type(data.get('type') or data.get('campaign_type'))
        if ctype=='MULTI_MESSAGE':self._require(FeatureKey.MULTI_MESSAGE)
        messages=data.get('messages') or []
        if any(str(m.get('message_type') or m.get('type') or 'TEXT').upper().replace(' ','_')!='TEXT' for m in messages):self._require(FeatureKey.MEDIA_POSTING)
        stype=str(data.get('schedule_type') or 'SEND_NOW').upper()
        if stype in {'ONCE','SCHEDULE_ONCE'}:self._require(FeatureKey.SCHEDULE_ONCE)
        if stype in {'REPEAT','RECURRING','RECURRING_POST'}:self._require(FeatureKey.RECURRING_SCHEDULE)

    def get_campaigns(self):return self.repository.get_all()
    def get_page(self,page=1,page_size=50,search=None,status=None,campaign_type=None,schedule_type=None,group_id=None,account_id=None):return self.repository.get_page(page,page_size,search,status,campaign_type,schedule_type,group_id,account_id)
    def _normalize_type(self,value):
        text=str(value or 'SINGLE_POST').upper().replace(' ','_')
        return {'MULTIPLE_MESSAGES':'MULTI_MESSAGE','SINGLE_POST':'SINGLE_POST','SCHEDULED_POST':'SCHEDULED_POST','RECURRING_POST':'RECURRING_POST'}.get(text,text)
    def _resolve_targets(self,targets,default_account_id=None):
        result=[]
        for target in targets or []:
            gid=int(target.get('group_id') if isinstance(target,dict) else target);account_id=(target.get('account_id') if isinstance(target,dict) else None) or default_account_id
            group=self.group_repository.get_by_id(gid) if self.group_repository else None
            if not group or not bool(group.is_managed):raise ValueError('Campaign targets must be saved managed groups.')
            if not account_id and self.group_account_repository:
                primary=self.group_account_repository.get_primary_account(gid);account_id=primary.account_id if primary else None
            if not account_id:raise ValueError(f'No posting account is configured for {group.title}.')
            mapping=self.group_account_repository.get_mapping(gid,int(account_id)) if self.group_account_repository else None
            if not mapping or not bool(mapping.can_post):raise ValueError(f'{group.title} does not have verified posting permission for the selected account.')
            result.append((gid,int(account_id)))
        return result
    def _adopt_media(self,campaign_id,messages):
        clean=[]
        for msg in messages or []:
            row=dict(msg);path=row.get('media_path') or row.get('media')
            if path and self.media_service and Path(path).is_file():row['media_path']=self.media_service.adopt(campaign_id,path)
            clean.append(row)
        return clean
    def create(self,data:dict):
        self._require_content_features(data)
        name=(data.get('name') or '').strip()
        if not name:raise ValueError('Campaign name is required.')
        if not (data.get('messages') or []):raise ValueError('Content is required — add at least one campaign message.')
        default_account_id=data.get('default_account_id') or data.get('account_id')
        item=Campaign(name=name,description=(data.get('description') or '').strip() or None,campaign_type=self._normalize_type(data.get('type') or data.get('campaign_type')),status=str(data.get('status') or 'DRAFT').upper(),schedule_type=str(data.get('schedule_type') or 'SEND_NOW').upper(),send_at=data.get('send_at'),timezone=data.get('timezone') or 'UTC',repeat_rule=data.get('repeat_rule'),default_account_id=int(default_account_id) if default_account_id else None,created_by=data.get('created_by'))
        with self.repository.db.transaction():
            created=self.repository.create(item);messages=self._adopt_media(created.id,data.get('messages') or []);self.message_repository.replace_messages(created.id,messages)
            targets=self._resolve_targets(data.get('targets') or [],created.default_account_id);self.target_repository.replace_targets(created.id,targets)
            self.repository.set_counts(created.id,total=len(targets))
            self._log('CAMPAIGN_CREATED',f'Campaign #{created.id} created.',campaign_id=created.id)
        return self.repository.get_by_id(created.id)
    def update(self,id:int,data:dict):
        self._require_content_features(data)
        item=self.repository.get_by_id(id)
        if not item:raise ValueError('Campaign not found.')
        if item.status in {'ARCHIVED','RUNNING','COMPLETED','PARTIAL_SUCCESS'}:
            raise ValueError('This campaign is read-only because it has active or completed delivery history. Duplicate it to make changes.')
        if self.delivery_repository:
            deliveries=self.delivery_repository.get_campaign_deliveries(id)
            if any(d.status in {'SENT','SCHEDULED','RECONCILE_REQUIRED'} for d in deliveries):
                raise ValueError('This campaign has delivery history and cannot be edited safely. Duplicate it to make changes.')
        if 'name' in data:item.name=(data['name'] or '').strip()
        if not item.name:raise ValueError('Campaign name is required.')
        if 'description' in data:item.description=(data['description'] or '').strip() or None
        if 'campaign_type' in data or 'type' in data:item.campaign_type=self._normalize_type(data.get('campaign_type') or data.get('type'))
        for f in ('schedule_type','send_at','timezone','repeat_rule','default_account_id'):
            if f in data:setattr(item,f,data[f])
        with self.repository.db.transaction():
            updated=self.repository.update(item)
            if 'messages' in data:self.message_repository.replace_messages(id,self._adopt_media(id,data.get('messages') or []))
            if 'targets' in data:
                targets=self._resolve_targets(data.get('targets') or [],item.default_account_id);self.target_repository.replace_targets(id,targets);self.repository.set_counts(id,total=len(targets))
            self._log('CAMPAIGN_UPDATED',f'Campaign #{id} updated.',campaign_id=id)
        return self.repository.get_by_id(id)
    def duplicate(self,id:int):
        from app.license.feature_keys import FeatureKey
        self._require(FeatureKey.CAMPAIGNS);return self.repository.duplicate(id)
    def archive(self,id:int):self.repository.archive(id);self._log('CAMPAIGN_ARCHIVED',f'Campaign #{id} archived.',campaign_id=id);return self.repository.get_by_id(id)
    def unarchive(self,id:int):self.repository.unarchive(id);self._log('CAMPAIGN_UNARCHIVED',f'Campaign #{id} restored from archive.',campaign_id=id);return self.repository.get_by_id(id)
    def delete_draft(self,id:int):return self.repository.delete_draft(id)
    def delete(self,id:int):return self.repository.delete(id)
    def get_details(self,id:int):
        return {'campaign':self.repository.get_by_id(id),'messages':self.message_repository.get_messages(id),'targets':self.target_repository.get_targets(id),'deliveries':self.delivery_repository.get_campaign_deliveries(id) if self.delivery_repository else []}
    def get_results(self,id:int):return self.delivery_repository.get_campaign_deliveries(id) if self.delivery_repository else []
    def get_managed_targets(self):
        if not self.group_repository:return []
        groups=self.group_repository.get_managed();out=[]
        for g in groups:
            mappings=self.group_account_repository.get_group_accounts(g.id) if self.group_account_repository else []
            primary=next((m for m in mappings if m.is_primary),None)
            out.append({'group_id':g.id,'group':g,'mapping':primary,'mappings':mappings,'account_id':primary.account_id if primary else None,'selectable':bool(primary and primary.can_post),'reason':None if primary and primary.can_post else ('Primary account has no verified posting permission.' if primary else 'Managed group has no primary posting account.')})
        return out

    def plan_smart_targets(self,group_ids,*,messages_per_target=1):
        """Build fixed posting assignments from healthy verified mappings.

        The plan is deterministic and is saved with the campaign. Runtime
        failures never trigger account rotation or reassignment.
        """
        selected=[];blockers=[];projected={};account_plan={};message_count=max(1,int(messages_per_target or 1))
        for group_id in [int(value) for value in group_ids or []]:
            group=self.group_repository.get_by_id(group_id) if self.group_repository else None
            candidates=[]
            for mapping in (self.group_account_repository.get_group_accounts(group_id) if self.group_account_repository else []):
                account_id=int(mapping.account_id);account=self.account_repository.get_by_id(account_id) if self.account_repository else None
                if not account or not bool(account.is_enabled) or not bool(account.enabled_for_operations) or str(account.authorization_status).upper()!='AUTHORIZED':continue
                if str(account.health_status or 'UNKNOWN').upper() in {'COOLDOWN','RESTRICTED','SESSION_INVALID','LOGIN_REQUIRED','DISABLED'}:continue
                if not bool(mapping.can_post) or not bool(mapping.can_view):continue
                planned=projected.get(account_id,0)+message_count
                safety=self.account_safety_service.preview(account_id,'POST',requested=planned,enforce_interval=False) if self.account_safety_service else None
                if safety is not None and not safety.allowed:continue
                ratio=((safety.used_today+planned)/max(1,safety.daily_limit)) if safety is not None and safety.smart_mode else 0.0
                candidates.append((ratio,projected.get(account_id,0),account_id,account,safety))
            if not candidates:
                blockers.append(f"{getattr(group,'title',f'Group {group_id}')} has no healthy mapped posting account within its daily safety limit.");continue
            _ratio,_load,account_id,account,safety=min(candidates,key=lambda item:(item[0],item[1],item[2]))
            projected[account_id]=projected.get(account_id,0)+message_count
            selected.append({'group_id':group_id,'account_id':account_id})
            row=account_plan.setdefault(account_id,{'account_id':account_id,'account':account,'groups':0,'post_attempts':0,'safety_state':getattr(safety,'state','NORMAL'),'used_today':getattr(safety,'used_today',0),'daily_limit':getattr(safety,'daily_limit',0)})
            row['groups']+=1;row['post_attempts']+=message_count
        return {'assignments':selected,'blockers':blockers,'account_plan':list(account_plan.values()),'fixed':True,'no_runtime_fallback':True}

    async def _reserve_post(self,account_id):
        if self.account_safety_service is None:return None
        decision=self.account_safety_service.reserve(int(account_id),'POST')
        if not decision.allowed and decision.code=='MIN_INTERVAL' and decision.wait_seconds>0:
            await asyncio.sleep(decision.wait_seconds);decision=self.account_safety_service.reserve(int(account_id),'POST')
        return decision
    def build_preflight(self,id:int):
        from app.license.feature_keys import FeatureKey
        self._require(FeatureKey.CAMPAIGN_PREFLIGHT)
        details=self.get_details(id);campaign=details['campaign'];targets=details['targets'];messages=details['messages']
        accounts={t.account_id:self.account_repository.get_by_id(t.account_id) for t in targets if t.account_id};groups={t.group_id:self.group_repository.get_by_id(t.group_id) for t in targets};mappings={(t.group_id,t.account_id):self.group_account_repository.get_mapping(t.group_id,t.account_id) for t in targets if t.account_id}
        result=self.preflight_service.build(campaign,targets,messages,accounts,groups,mappings);self.repository.set_status(id,'READY' if result.blocked_targets==0 and not result.errors else 'VALIDATING');self._log('CAMPAIGN_VALIDATED',f'Campaign #{id} preflight: {result.ready_targets} ready, {result.blocked_targets} blocked.',campaign_id=id);return result
    async def run(self,id:int,*,occurrence_key:str|None=None,scheduled_for:str|None=None,progress_callback=None):
        from app.license.feature_keys import FeatureKey
        self._require(FeatureKey.CAMPAIGNS);self._require(FeatureKey.SEND_NOW)
        if self.operations_paused:raise RuntimeError('Operations are paused.')
        campaign=self.repository.get_by_id(id)
        if not campaign:raise ValueError('Campaign not found.')
        preflight=self.build_preflight(id)
        if preflight.blocked_targets or preflight.errors:raise ValueError('Campaign preflight has blocked targets. Resolve them before publishing.')
        targets=self.target_repository.get_targets(id);messages=self.message_repository.get_messages(id)
        now=utc_now_iso();occurrence_key=occurrence_key or campaign.last_run_at or now
        if campaign.status!='PAUSED':self.repository.update_run_times(id,started_at=now,last_run_at=occurrence_key)
        self.repository.set_status(id,'RUNNING');job=self.job_repository.create_job('CAMPAIGN_SEND',campaign_id=id,status='RUNNING',total_items=max(1,len(targets)*len(messages)),metadata_json=json.dumps({'occurrence_key':occurrence_key})) if self.job_repository else None
        success_targets=failed_targets=skipped_targets=0;processed_messages=0;cooldown_pause=False
        self._log('CAMPAIGN_STARTED',f'Campaign #{id} started.',campaign_id=id)
        for ti,target in enumerate(targets):
            current=self.repository.get_by_id(id)
            if self.operations_paused or current.status=='PAUSED':
                self.target_repository.update_status(target.id,'PAUSED');break
            if current.status=='CANCELLED':self.target_repository.update_status(target.id,'CANCELLED');continue
            group=self.group_repository.get_by_id(target.group_id);account=self.account_repository.get_by_id(target.account_id);mapping=self.group_account_repository.get_mapping(target.group_id,target.account_id)
            if progress_callback:progress_callback({'event':'target_started','campaign_id':id,'group_id':target.group_id,'target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':getattr(group,'title','—')})
            if not group or not account or not mapping or not bool(group.is_managed) or not bool(mapping.can_view) or not bool(mapping.can_post) or not bool(account.is_enabled) or not bool(account.enabled_for_operations) or str(account.authorization_status).upper()!='AUTHORIZED' or account.health_status in {'COOLDOWN','RESTRICTED','SESSION_INVALID','LOGIN_REQUIRED','DISABLED'}:
                self.target_repository.record_error(target.id,'POST_PERMISSION_DENIED','Posting permission/account health is not currently valid.');failed_targets+=1
                if progress_callback:progress_callback({'event':'target_failed','campaign_id':id,'group_id':target.group_id,'error':'Posting permission/account health is not currently valid.','target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':getattr(group,'title','—')})
                continue
            target_failed=False;target_sent=False;target_skipped=True
            self.target_repository.update_status(target.id,'SENDING');self.target_repository.increment_attempt(target.id)
            for msg in messages:
                delivery=self.delivery_repository.create_delivery(id,target.id,msg.id,occurrence_key,msg.content_hash or '',scheduled_for)
                if delivery.status in {'SENT','SCHEDULED','SKIPPED'}:processed_messages+=1;continue
                if delivery.status in {'SENDING','RECONCILE_REQUIRED'}:
                    self.delivery_repository.mark_reconcile_required(delivery.id);target_failed=True;self.target_repository.record_error(target.id,'RECONCILE_REQUIRED','A previous send may have reached Telegram and requires review.','PAUSED');break
                rendered_text=self.renderer.render(msg.body,campaign,group,scheduled_for or occurrence_key);rendered_caption=self.renderer.render(msg.caption,campaign,group,scheduled_for or occurrence_key)
                send_msg={'message_type':msg.message_type,'body':rendered_text,'caption':rendered_caption,'media_path':msg.media_path,'parse_mode':msg.parse_mode,'disable_link_preview':bool(msg.disable_link_preview),'content_hash':msg.content_hash}
                safety=await self._reserve_post(target.account_id)
                if safety is not None and not safety.allowed:
                    self.target_repository.record_error(target.id,safety.code,safety.message,'PAUSED');target_failed=True;cooldown_pause=True
                    if progress_callback:progress_callback({'event':'target_failed','campaign_id':id,'group_id':target.group_id,'error':safety.message,'target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':group.title,'success':success_targets,'failed':failed_targets,'skipped':skipped_targets})
                    break
                self.delivery_repository.mark_sending(delivery.id);self.target_message_repository.upsert(target.id,msg.id,status='SENDING')
                result=await self.campaign_sender.send(target.account_id,group,send_msg)
                processed_messages+=1
                if result.success:
                    try:
                        self.delivery_repository.mark_sent(delivery.id,result.telegram_message_id or '',result.sent_at);self.rendered_repository.save_snapshot(delivery.id,rendered_text,rendered_caption,msg.media_path);self.target_message_repository.upsert(target.id,msg.id,status='SENT',telegram_message_id=result.telegram_message_id,sent_at=result.sent_at);target_sent=True;target_skipped=False
                        if self.account_safety_service:self.account_safety_service.record_success(target.account_id,'POST')
                    except Exception:
                        self.delivery_repository.mark_reconcile_required(delivery.id);self.target_message_repository.upsert(target.id,msg.id,status='RECONCILE_REQUIRED',telegram_message_id=result.telegram_message_id);target_failed=True;break
                else:
                    self.delivery_repository.mark_failed(delivery.id);self.target_message_repository.upsert(target.id,msg.id,status='FAILED',error_code=result.error_code,error_message=result.error_message);self.target_repository.record_error(target.id,result.error_code,result.error_message);target_failed=True
                    if self.account_safety_service and str(result.error_code or '').upper() in {'FLOOD_WAIT','PEER_FLOOD','SPAM_LIMITED','ACCOUNT_RESTRICTED','USER_RESTRICTED'}:
                        self.account_safety_service.record_failure(target.account_id,'POST',result.error_code,result.error_message,wait_seconds=getattr(result,'wait_seconds',None))
                    if result.error_code=='FLOOD_WAIT':
                        self._flood_wait(target.account_id,id,target.group_id,result.error_message);self.target_repository.update_status(target.id,'PAUSED');cooldown_pause=True
                    if progress_callback:progress_callback({'event':'target_failed','campaign_id':id,'group_id':target.group_id,'error':result.error_message or result.error_code or 'Target failed.','target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':group.title,'success':success_targets,'failed':failed_targets+1,'skipped':skipped_targets})
                    break
                if progress_callback:progress_callback({'campaign_id':id,'target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':group.title,'success':success_targets,'failed':failed_targets,'skipped':skipped_targets})
            if target_failed:failed_targets+=1
            elif target_sent:self.target_repository.set_telegram_message_id(target.id,next((d.telegram_message_id for d in reversed(self.delivery_repository.get_target_history(target.id)) if d.telegram_message_id),''));success_targets+=1
            elif target_skipped:self.target_repository.update_status(target.id,'SKIPPED');skipped_targets+=1
            if progress_callback and not target_failed:progress_callback({'event':'target_completed','campaign_id':id,'group_id':target.group_id,'target_index':ti+1,'target_total':len(targets),'message_index':processed_messages,'message_total':len(targets)*len(messages),'current_target':group.title,'success':success_targets,'failed':failed_targets,'skipped':skipped_targets})
            if job:
                self.job_repository.update_progress(job.id,int(processed_messages*100/max(1,len(targets)*len(messages))))
            if cooldown_pause:
                self.repository.set_status(id,'PAUSED');break
        current=self.repository.get_by_id(id)
        if current.status=='PAUSED':final='PAUSED'
        elif current.status=='CANCELLED':final='CANCELLED'
        elif success_targets and failed_targets:final='PARTIAL_SUCCESS'
        elif failed_targets and not success_targets:final='FAILED'
        else:final='COMPLETED'
        done=utc_now_iso();self.repository.set_counts(id,total=len(targets),success=success_targets,failed=failed_targets,skipped=skipped_targets);self.repository.update_run_times(id,completed_at=done if final not in {'PAUSED'} else None,last_run_at=occurrence_key);self.repository.set_status(id,final)
        if job:
            self.job_repository.update_fields(job.id,{'status':'COMPLETED' if final in {'COMPLETED','PARTIAL_SUCCESS'} else final,'success_count':success_targets,'failed_count':failed_targets,'skipped_count':skipped_targets,'progress':100 if final not in {'PAUSED'} else self.job_repository.get_by_id(job.id).progress,'finished_at':done if final not in {'PAUSED'} else None,'updated_at':done})
        if final in {'FAILED','PARTIAL_SUCCESS'} and self.alert_repository:self.alert_repository.create_alert('WARNING' if final=='PARTIAL_SUCCESS' else 'CRITICAL','CAMPAIGN_FAILURE',f'Campaign #{id} {final.replace("_"," ").lower()}.',campaign_id=id,job_id=job.id if job else None)
        self._log('CAMPAIGN_PAUSED' if final=='PAUSED' else ('CAMPAIGN_COMPLETED' if final in {'COMPLETED','PARTIAL_SUCCESS'} else 'CAMPAIGN_FAILED'),f'Campaign #{id} finished with status {final}.',campaign_id=id)
        return self.repository.get_by_id(id)
    async def schedule_native(self,id:int,scheduled_for:str,*,occurrence_key:str|None=None,progress_callback=None):
        from app.license.feature_keys import FeatureKey
        self._require(FeatureKey.SCHEDULE_ONCE)
        if self.operations_paused: raise RuntimeError('Operations are paused.')
        campaign=self.repository.get_by_id(id)
        if not campaign: raise ValueError('Campaign not found.')
        preflight=self.build_preflight(id)
        if preflight.blocked_targets or preflight.errors: raise ValueError('Campaign preflight has blocked targets. Resolve them before scheduling.')
        try: schedule_dt=datetime.fromisoformat(scheduled_for.replace('Z','+00:00'))
        except ValueError as exc: raise ValueError('Scheduled date/time is invalid.') from exc
        if schedule_dt.tzinfo is None: schedule_dt=schedule_dt.replace(tzinfo=timezone.utc)
        if schedule_dt.astimezone(timezone.utc)<=datetime.now(timezone.utc): raise ValueError('Scheduled time must be in the future.')
        targets=self.target_repository.get_targets(id);messages=self.message_repository.get_messages(id);occurrence_key=occurrence_key or schedule_dt.astimezone(timezone.utc).isoformat()
        job=self.job_repository.create_job('CAMPAIGN_SCHEDULE',campaign_id=id,status='RUNNING',total_items=max(1,len(targets)*len(messages)),metadata_json=json.dumps({'occurrence_key':occurrence_key,'scheduled_for':occurrence_key})) if self.job_repository else None
        success=failed=skipped=processed=0;cooldown_pause=False
        for target in targets:
            group=self.group_repository.get_by_id(target.group_id);account=self.account_repository.get_by_id(target.account_id);mapping=self.group_account_repository.get_mapping(target.group_id,target.account_id)
            if not group or not account or not mapping or not bool(group.is_managed) or not bool(mapping.can_view) or not bool(mapping.can_post) or not bool(account.is_enabled) or not bool(account.enabled_for_operations) or str(account.authorization_status).upper()!='AUTHORIZED' or account.health_status in {'COOLDOWN','RESTRICTED','SESSION_INVALID','LOGIN_REQUIRED','DISABLED'}:
                self.target_repository.record_error(target.id,'POST_PERMISSION_DENIED','Posting permission/account health is not currently valid.');failed+=1;continue
            target_failed=False;target_scheduled=False;target_only_skips=True
            for msg in messages:
                delivery=self.delivery_repository.create_delivery(id,target.id,msg.id,occurrence_key,msg.content_hash or '',occurrence_key)
                if delivery.status in {'SCHEDULED','SENT','SKIPPED'}:processed+=1;continue
                rendered_text=self.renderer.render(msg.body,campaign,group,occurrence_key);rendered_caption=self.renderer.render(msg.caption,campaign,group,occurrence_key)
                send_msg={'message_type':msg.message_type,'body':rendered_text,'caption':rendered_caption,'media_path':msg.media_path,'parse_mode':msg.parse_mode,'disable_link_preview':bool(msg.disable_link_preview),'content_hash':msg.content_hash}
                safety=await self._reserve_post(target.account_id)
                if safety is not None and not safety.allowed:
                    self.target_repository.record_error(target.id,safety.code,safety.message,'PAUSED');target_failed=True;cooldown_pause=True;break
                self.delivery_repository.mark_sending(delivery.id);self.target_message_repository.upsert(target.id,msg.id,status='SENDING',scheduled_at=occurrence_key)
                result=await self.campaign_sender.send(target.account_id,group,send_msg,schedule_at=schedule_dt)
                processed+=1
                if result.success:
                    self.delivery_repository.mark_scheduled(delivery.id,result.telegram_message_id or '',occurrence_key);self.rendered_repository.save_snapshot(delivery.id,rendered_text,rendered_caption,msg.media_path);self.target_message_repository.upsert(target.id,msg.id,status='SCHEDULED',telegram_scheduled_message_id=result.telegram_message_id,scheduled_at=occurrence_key);target_scheduled=True;target_only_skips=False
                    if self.account_safety_service:self.account_safety_service.record_success(target.account_id,'POST')
                else:
                    self.delivery_repository.mark_failed(delivery.id);self.target_message_repository.upsert(target.id,msg.id,status='FAILED',error_code=result.error_code,error_message=result.error_message);self.target_repository.record_error(target.id,result.error_code,result.error_message);target_failed=True
                    if self.account_safety_service and str(result.error_code or '').upper() in {'FLOOD_WAIT','PEER_FLOOD','SPAM_LIMITED','ACCOUNT_RESTRICTED','USER_RESTRICTED'}:
                        self.account_safety_service.record_failure(target.account_id,'POST',result.error_code,result.error_message,wait_seconds=getattr(result,'wait_seconds',None))
                    if result.error_code=='FLOOD_WAIT':
                        self._flood_wait(target.account_id,id,target.group_id,result.error_message);self.target_repository.update_status(target.id,'PAUSED');cooldown_pause=True
                    break
                if progress_callback: progress_callback({'campaign_id':id,'message_index':processed,'message_total':len(targets)*len(messages),'current_target':group.title,'success':success,'failed':failed,'skipped':skipped})
            if target_failed: failed+=1
            elif target_scheduled:
                remote=next((d.telegram_scheduled_message_id for d in reversed(self.delivery_repository.get_target_history(target.id)) if d.telegram_scheduled_message_id),None);self.target_repository.set_scheduled_message_id(target.id,remote or '',occurrence_key);success+=1
            elif target_only_skips:self.target_repository.update_status(target.id,'SKIPPED');skipped+=1
            if cooldown_pause:break
        final='PAUSED' if cooldown_pause else ('SCHEDULED' if success and not failed else ('PARTIAL_SUCCESS' if success and failed else 'FAILED'))
        self.repository.set_counts(id,total=len(targets),success=success,failed=failed,skipped=skipped);self.repository.update_fields(id,{'status':final,'send_at':occurrence_key,'next_run_at':occurrence_key,'updated_at':utc_now_iso()})
        if job:self.job_repository.update_fields(job.id,{'status':'PAUSED' if cooldown_pause else ('COMPLETED' if success else 'FAILED'),'success_count':success,'failed_count':failed,'skipped_count':skipped,'progress':100,'finished_at':utc_now_iso(),'updated_at':utc_now_iso()})
        self._log('SCHEDULE_CREATED',f'Campaign #{id} scheduled for {occurrence_key}.',campaign_id=id)
        return self.repository.get_by_id(id)

    def pause(self,id:int):self.repository.set_status(id,'PAUSED');self._log('CAMPAIGN_PAUSED',f'Campaign #{id} paused.',campaign_id=id);return True
    async def resume(self,id:int,progress_callback=None):
        campaign=self.repository.get_by_id(id)
        if not campaign:raise ValueError('Campaign not found.')
        self.repository.set_status(id,'RUNNING');self._log('CAMPAIGN_RESUMED',f'Campaign #{id} resumed.',campaign_id=id);return await self.run(id,occurrence_key=campaign.last_run_at,progress_callback=progress_callback)
    def cancel(self,id:int):self.repository.set_status(id,'CANCELLED');self.db_update_remaining(id,'CANCELLED');self._log('CAMPAIGN_CANCELLED',f'Campaign #{id} cancelled.',campaign_id=id);return True
    def db_update_remaining(self,id,status):self.repository.db.execute("UPDATE campaign_targets SET status=?,updated_at=? WHERE campaign_id=? AND status NOT IN ('SENT','FAILED','SKIPPED')",(status,utc_now_iso(),id))
    def set_operations_paused(self,paused:bool):self.operations_paused=bool(paused)
    def _flood_wait(self,account_id,campaign_id,group_id,message):
        if self.account_repository:self.account_repository.update_health_status(account_id,'COOLDOWN')
        if self.alert_repository:self.alert_repository.create_alert('WARNING','FLOOD_WAIT','Telegram requested a cooldown.',message or 'Outgoing campaign operation paused.',account_id=account_id,group_id=group_id,campaign_id=campaign_id)
    def _log(self,action,message,**refs):
        if self.log_repository:self.log_repository.add_log('INFO','CAMPAIGN',message,action=action,account_id=refs.get('account_id'),group_id=refs.get('group_id'))
