from __future__ import annotations
import uuid
from PySide6.QtCore import QObject,Signal
from app.models.pagination import PaginationState
from app.telegram.models.member_sync_result import MemberSyncOptions

class MemberController(QObject):
    membersChanged=Signal(list);memberUpdated=Signal(int);member_selected=Signal(int);errorOccurred=Signal(str);toast_requested=Signal(str,str)
    memberSyncStarted=Signal(str);memberSyncProgress=Signal(object);memberSyncCompleted=Signal(object);memberSyncFailed=Signal(str)
    memberEligibilityChanged=Signal(int);memberEligibilityBatchChanged=Signal(list);memberBlacklistChanged=Signal(int);targetMembershipUpdated=Signal(int,int);memberStatsChanged=Signal();planLimitReached=Signal(str,object);featureLocked=Signal(str,str)
    targetSyncProgress=Signal(object);targetSyncCompleted=Signal(object)
    targetInvitationProgress=Signal(object);targetInvitationCompleted=Signal(object);targetInvitationStarted=Signal(int)
    targetInvitationFailed=Signal(str)
    targetInvitationPreflightReady=Signal(object);targetInvitationPreflightFailed=Signal(str)
    massTargetAddProgress=Signal(object);massTargetAddCompleted=Signal(object);massTargetAddFailed=Signal(str)
    memberCleanupCompleted=Signal(object)
    def __init__(self,service,blacklist_service,worker=None,parent=None):
        super().__init__(parent);self.service=service;self.blacklist_service=blacklist_service;self.worker=worker;self.pagination=PaginationState();self.search_text="";self.eligibility=None;self.consent=None;self.source_group_id=None;self.target_group_id=None;self.tag=None;self.bot_filter=None;self.blacklist_filter=None;self.exclude_blacklist=False;self.exclude_existing=False;self.only_username=False;self.only_eligible=False;self.current_items=[];self._handlers={};self.active_sync_id=None;self.active_invitation_job_id=None;self.feature_gate=None
        if worker:worker.operationCompleted.connect(self._done);worker.operationFailed.connect(self._failed);worker.finished.connect(self._on_worker_finished)
    def members(self):return self.refresh(emit=False)
    def source_groups(self):return self.service.get_accessible_source_groups()
    def all_source_groups(self):return self.service.groups.get_sources() if self.service.groups else []
    def target_groups(self):return self.service.groups.get_targets() if self.service.groups else []
    def tags(self):return self.service.list_tags()
    def create_tag(self,name):r=self.service.create_tag(name);self.toast_requested.emit("Member tag created.","Success");return r
    def rename_tag(self,old,new):r=self.service.rename_tag(old,new);self.toast_requested.emit("Member tag renamed.","Success");self.refresh();return r
    def delete_tag(self,name):r=self.service.delete_tag(name);self.toast_requested.emit("Member tag deleted.","Success");self.refresh();return r
    def accounts_for_group(self,group_id):return self.service.group_accounts.get_group_accounts(group_id) if self.service.group_accounts else []
    def collector_accounts_for_group(self,group_id):return self.service.get_eligible_group_accounts(group_id)
    def collector_readiness(self,group_id,account_id):return self.service.collector_readiness(group_id,account_id)
    def target_preparation(self,target_group_id:int,**filters):
        try:return self.service.target_preparation(target_group_id,**filters)
        except Exception as exc:self._error(exc);return None
    def export_target_preparation(self,path,target_group_id:int,**filters):
        try:
            count=self.service.export_target_preparation(path,target_group_id,**filters);self.toast_requested.emit(f"Exported {count} prepared member record(s).","Success");return count
        except Exception as exc:self._error(exc);return 0
    def source_stats(self,group_id):return self.service.source_stats(group_id)
    def target_stats(self,group_id):return self.service.target_stats(group_id)
    def target_member_rows(self,group_id,limit=500):return self.service.target_member_rows(group_id,limit)
    def invitation_history(self,member_id,limit=200):return self.service.invitation_history(member_id,limit)
    def auto_select_account_for_target(self,target_group_id,permission="invite"):
        try:return self.service.auto_select_account_for_target(int(target_group_id),str(permission))
        except Exception as exc:self.toast_requested.emit(str(exc),"Warning");return {"allowed":False,"account_id":None,"reason":str(exc)}

    def invitation_precheck(self,target_group_id,account_id,member_ids):
        try:return self.service.invitation_precheck(target_group_id,account_id,list(member_ids))
        except Exception as exc:
            # Compatibility path only. Normal invitation validation is represented
            # as preflight data, not as an application exception.
            self._error(exc);return None
    def invitation_batch_precheck(self,target_group_id,account_ids,member_ids):
        try:return self.service.invitation_batch_precheck(target_group_id,list(account_ids),list(member_ids))
        except Exception as exc:
            self._error(exc);return None
    def request_invitation_preflight(self,target_group_id,account_id,member_ids,callback=None):
        def done(result):
            self.targetInvitationPreflightReady.emit(result)
            if callback:callback(result)
        def failed(_account_id,message):
            self.targetInvitationPreflightFailed.emit(message)
            self.toast_requested.emit(message or "Invitation preflight could not be completed.","Warning")
        return self._submit(self.service.invitation_preflight(int(target_group_id),int(account_id),list(member_ids)),"target_invitation_preflight",int(account_id),done,failed)
    def request_invitation_batch_preflight(self,target_group_id,account_ids,member_ids,callback=None):
        ids=[int(x) for x in account_ids]
        def done(result):
            self.targetInvitationPreflightReady.emit(result)
            if callback:callback(result)
        def failed(_account_id,message):
            self.targetInvitationPreflightFailed.emit(message)
            self.toast_requested.emit(message or "Invitation batch preflight could not be completed.","Warning")
        return self._submit(self.service.invitation_batch_preflight(int(target_group_id),ids,list(member_ids)),"target_invitation_batch_preflight",ids[0] if ids else 0,done,failed)
    def current_filter_criteria(self):
        return dict(search=self.search_text,eligibility=self.eligibility,consent=self.consent,source_group_id=self.source_group_id,target_group_id=self.target_group_id,tag=self.tag,bot_filter=self.bot_filter,blacklist_filter=self.blacklist_filter,exclude_blacklist=self.exclude_blacklist,exclude_existing=self.exclude_existing,only_username=self.only_username,only_eligible=self.only_eligible)
    def cleanup_selected(self,member_ids):
        try:
            result=self.service.cleanup_selected(member_ids);self.refresh();self.memberStatsChanged.emit();self.memberCleanupCompleted.emit(result);self.toast_requested.emit(f"Removed {getattr(result,'removed_members',0)} member(s) from the local Member Pool.","Success");return result
        except Exception as exc:self._error(exc);return None
    def cleanup_filtered(self):
        try:
            result=self.service.cleanup_filtered(**self.current_filter_criteria());self.refresh();self.memberStatsChanged.emit();self.memberCleanupCompleted.emit(result);self.toast_requested.emit(f"Removed {getattr(result,'removed_members',0)} filtered member(s).","Success");return result
        except Exception as exc:self._error(exc);return None
    def cleanup_by_source(self,group_id,remove_member_if_only_source=False):
        try:
            result=self.service.cleanup_by_source(group_id,remove_member_if_only_source);self.refresh();self.memberStatsChanged.emit();self.memberCleanupCompleted.emit(result);return result
        except Exception as exc:self._error(exc);return None
    def cleanup_orphaned(self):
        try:
            result=self.service.cleanup_orphaned();self.refresh();self.memberStatsChanged.emit();self.memberCleanupCompleted.emit(result);return result
        except Exception as exc:self._error(exc);return None
    def cleanup_all(self,preserve_global_exclusions=True,preserve_audit_history=True):
        try:
            result=self.service.cleanup_all(preserve_global_exclusions=preserve_global_exclusions,preserve_audit_history=preserve_audit_history);self.refresh();self.memberStatsChanged.emit();self.memberCleanupCompleted.emit(result);return result
        except Exception as exc:self._error(exc);return None
    def cleanup_orphan_count(self):return self.service.cleanup_orphan_count()
    def refresh(self,emit=True):
        try:
            items,total=self.service.get_member_page(self.pagination.page,self.pagination.page_size,self.search_text,self.eligibility,self.consent,None,self.only_username,source_group_id=self.source_group_id,target_group_id=self.target_group_id,tag=self.tag,bot_filter=self.bot_filter,blacklist_filter=self.blacklist_filter,exclude_blacklist=self.exclude_blacklist,exclude_existing=self.exclude_existing,only_eligible=self.only_eligible)
            self.pagination.total_items=total;self.pagination.clamp();self.current_items=items
            if emit:self.membersChanged.emit(items)
            return items
        except Exception as exc:self._error(exc);return []
    def set_search(self,text):self.search_text=text;self.pagination.page=1;return self.refresh()
    def set_filter(self,column,value):
        val=None if value in {None,"All",""} else value
        if column=="Eligibility":self.eligibility=val
        elif column=="Consent":self.consent=val
        elif column=="Source":
            raw=str(val).split(" — ",1)[0] if val else "";self.source_group_id=int(raw) if raw.isdigit() else None
        elif column in {"Target","Target Group"}:
            raw=str(val).split(" — ",1)[0] if val else "";self.target_group_id=int(raw) if raw.isdigit() else None
        elif column=="Tag":self.tag=val
        elif column=="Bot":self.bot_filter=val
        elif column=="Blacklist":self.blacklist_filter=val
        self.pagination.page=1;return self.refresh()
    def set_source(self,group_id):self.source_group_id=int(group_id) if group_id else None;self.pagination.page=1;return self.refresh()
    def set_target(self,group_id):self.target_group_id=int(group_id) if group_id else None;self.pagination.page=1;return self.refresh()
    def set_exclude_blacklist(self,checked):self.exclude_blacklist=bool(checked);self.pagination.page=1;return self.refresh()
    def set_exclude_existing(self,checked):self.exclude_existing=bool(checked);self.pagination.page=1;return self.refresh()
    def set_only_username(self,checked):self.only_username=checked;self.pagination.page=1;return self.refresh()
    def set_only_eligible(self,checked):self.only_eligible=checked;self.pagination.page=1;return self.refresh()
    def set_eligibility(self,id,status):return self._update(id,lambda:self.service.set_eligibility(id,status),"Member eligibility updated.",self.memberEligibilityChanged)
    def update_notes(self,id,notes):return self._update(id,lambda:self.service.update_notes(id,notes),"Member notes updated.",self.memberUpdated)
    def mark_eligible(self,id):return self._update(id,lambda:self.service.set_eligibility(id,"ELIGIBLE"),"Member marked eligible.",self.memberEligibilityChanged)
    def mark_manual_review(self,id):return self._update(id,lambda:self.service.set_eligibility(id,"MANUAL_REVIEW"),"Member marked for manual review.",self.memberEligibilityChanged)
    def set_consent(self,id,status):return self._update(id,lambda:self.service.set_consent(id,status),"Consent updated.",self.memberEligibilityChanged)
    def set_eligibility_many(self,ids,status):return self._status_update_many(ids,lambda values:self.service.set_eligibility_many(values,status),"Member eligibility updated.")
    def set_consent_many(self,ids,status):return self._status_update_many(ids,lambda values:self.service.set_consent_many(values,status),"Member consent updated.")
    def mark_do_not_contact(self,id):return self._update(id,lambda:self.service.mark_do_not_contact(id,"Set from Member Pool"),"Member marked Do Not Contact.",self.memberBlacklistChanged)
    def add_tag(self,id,tag):return self._update(id,lambda:self.service.assign_tag(id,tag),"Member tag added.",self.memberUpdated)
    def remove_tag(self,id,tag):return self._update(id,lambda:self.service.remove_tag(id,tag),"Member tag removed.",self.memberUpdated)
    def blacklist(self,id):return self._update(id,lambda:self.service.add_blacklist(id,"Added from Member Pool"),"Member added to blacklist.",self.memberBlacklistChanged)
    def unblacklist(self,id):return self._update(id,lambda:self.service.remove_blacklist(id),"Member removed from global exclusions.",self.memberBlacklistChanged)
    def get_member_details(self,id):return self.service.get_member_details(id)
    def remove_member_source(self,member_id,group_id,remove_orphan=False):
        try:
            result=self.service.remove_member_source(member_id,group_id,remove_orphan=remove_orphan);self.refresh();self.memberUpdated.emit(int(member_id));return result
        except Exception as exc:self._error(exc);return None
    def evaluate(self,id,target_id=None):return self.service.evaluate_member(id,target_id)
    def preview_sync(self,group_id,account_id,callback=None):return self._submit(self.service.preview_source(group_id,account_id),"member_preview",account_id,lambda r:callback(r) if callback else None)
    def on_start_sync(self,group_id,account_id,options:MemberSyncOptions|None=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.MEMBER_SYNC):self.featureLocked.emit(str(FeatureKey.MEMBER_SYNC),str(self.feature_gate.get_required_plan(FeatureKey.MEMBER_SYNC) or "STARTER"));return None
        if self.active_sync_id:return None
        run_id=uuid.uuid4().hex;self.active_sync_id=run_id;self.memberSyncStarted.emit(run_id)
        coro=self.service.sync_source_members(group_id,account_id,options or MemberSyncOptions(),sync_run_id=run_id,progress_callback=self.memberSyncProgress.emit)
        return self._submit(coro,"member_sync",account_id,self._sync_done,self._sync_fail)
    def on_pause_sync(self):
        if self.active_sync_id:return self._submit(self.service.pause_sync(self.active_sync_id),"member_sync_pause",0,lambda _:self.toast_requested.emit("Member sync paused.","Info"))
    def on_resume_sync(self):
        if self.active_sync_id:return self._submit(self.service.resume_sync(self.active_sync_id),"member_sync_resume",0,lambda _:self.toast_requested.emit("Member sync resumed.","Info"))
    def on_stop_sync(self):
        if self.active_sync_id:return self._submit(self.service.stop_sync(self.active_sync_id),"member_sync_stop",0,lambda _:self.toast_requested.emit("Member sync stop requested.","Warning"))
    start_sync=on_start_sync;pause_sync=on_pause_sync;resume_sync=on_resume_sync;stop_sync=on_stop_sync
    def _sync_done(self,result):
        self.active_sync_id=None;self.memberSyncCompleted.emit(result)
        skipped=int(getattr(result,"plan_limit_skipped",0) or 0);suffix=f" • {skipped} additional new member(s) skipped by plan capacity" if skipped else ""
        self.toast_requested.emit(f"Member sync finished: {result.inserted} new, {result.updated} updated{suffix}.","Warning" if skipped else ("Success" if result.status=="COMPLETED" else "Info"));self.refresh();self.memberStatsChanged.emit()
    def _sync_fail(self,_account_id,message):self.active_sync_id=None;self.memberSyncFailed.emit(message);self.toast_requested.emit(message,"Error");self.refresh()
    def refresh_member_profile(self,member_id,account_id,callback=None):
        return self._submit(self.service.refresh_member_profile(member_id,account_id),"member_profile_refresh",account_id,lambda r:self._profile_refreshed(r,callback))
    def _profile_refreshed(self,result,callback):
        self.memberUpdated.emit(result.id);self.refresh();self.toast_requested.emit("Member profile updated.","Success");callback(result) if callback else None
    def check_target(self,member_id,target_group_id,account_id,callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.TARGET_MEMBER_STATUS):self.featureLocked.emit(str(FeatureKey.TARGET_MEMBER_STATUS),str(self.feature_gate.get_required_plan(FeatureKey.TARGET_MEMBER_STATUS) or "PRO"));return None
        return self._submit(self.service.check_target_membership(member_id,target_group_id,account_id),"target_member_check",account_id,lambda r:self._target_checked(r,callback))
    def _target_checked(self,result,callback):self.targetMembershipUpdated.emit(result.member_id,result.target_group_id);self.refresh();callback(result) if callback else None
    def on_sync_target(self,target_group_id,account_id,callback=None):return self._submit(self.service.sync_target_member_states(target_group_id,account_id,progress_callback=self.targetSyncProgress.emit),"target_member_sync",account_id,lambda r:self._target_sync_done(r,callback))
    def _target_sync_done(self,result,callback):self.targetSyncCompleted.emit(result);self.toast_requested.emit(f"Target member status synced: {result['already_member']} existing local members found.","Success");self.refresh();callback(result) if callback else None
    def start_target_invitation(self,target_group_id,account_id,member_ids,callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):self.featureLocked.emit(str(FeatureKey.DIRECT_MEMBER_INVITE),str(self.feature_gate.get_required_plan(FeatureKey.DIRECT_MEMBER_INVITE) or "ULTIMATE"));return None
        def progress(payload):
            jid=(payload or {}).get("job_id")
            if jid and self.active_invitation_job_id!=jid:self.active_invitation_job_id=int(jid);self.targetInvitationStarted.emit(int(jid))
            self.targetInvitationProgress.emit(payload)
        return self._submit(self.service.invite_members_to_target(target_group_id,account_id,list(member_ids),progress_callback=progress),"target_member_invite",account_id,lambda r:self._invite_done(r,callback),self._invite_fail)
    def start_target_invitation_batch(self,target_group_id,account_ids,member_ids,callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):self.featureLocked.emit(str(FeatureKey.DIRECT_MEMBER_INVITE),str(self.feature_gate.get_required_plan(FeatureKey.DIRECT_MEMBER_INVITE) or "ULTIMATE"));return None
        ids=[int(x) for x in account_ids]
        def progress(payload):
            jid=(payload or {}).get("job_id")
            if jid and self.active_invitation_job_id!=jid:self.active_invitation_job_id=int(jid);self.targetInvitationStarted.emit(int(jid))
            self.targetInvitationProgress.emit(payload)
        return self._submit(self.service.invite_members_to_target_batch(target_group_id,ids,list(member_ids),progress_callback=progress),"target_member_invite_batch",ids[0] if ids else 0,lambda r:self._invite_done(r,callback),self._invite_fail)
    def _invite_done(self,result,callback=None):
        self.active_invitation_job_id=None;self.targetInvitationCompleted.emit(result);self.refresh();self.memberStatsChanged.emit()
        if str(result.get("status",""))=="BLOCKED":
            self.toast_requested.emit(result.get("message") or "Invitation was blocked by preflight.","Warning")
        else:
            self.toast_requested.emit(f"Invitation job finished: {result.get('successful',0)} successful, {result.get('skipped',0)} skipped, {result.get('failed',0)} failed.","Success" if not result.get('failed') else "Warning")
        callback(result) if callback else None
    def _invite_fail(self,_account_id,message):
        # Operational Telegram failures should normally be normalized inside the
        # invitation service. This is reserved for an unexpected worker failure,
        # but it still remains an inline/toast failure rather than a global crash.
        self.active_invitation_job_id=None
        text=message or "Invitation operation failed."
        self.targetInvitationFailed.emit(text)
        self.toast_requested.emit(text,"Error")
    def pause_target_invitation(self):
        if self.active_invitation_job_id:return self._submit(self.service.pause_target_invitation(self.active_invitation_job_id),"target_invite_pause",0,lambda _r:self.toast_requested.emit("Invitation job paused.","Info"))
    def resume_target_invitation(self):
        if self.active_invitation_job_id:return self._submit(self.service.resume_target_invitation(self.active_invitation_job_id),"target_invite_resume",0,lambda _r:self.toast_requested.emit("Invitation job resumed.","Info"))
    def stop_target_invitation(self):
        if self.active_invitation_job_id:return self._submit(self.service.stop_target_invitation(self.active_invitation_job_id),"target_invite_stop",0,lambda _r:self.toast_requested.emit("Invitation job stop requested.","Warning"))
    def mass_target_add_preview(self,target_group_id,target_count,source_group_ids,account_ids):
        try:return self.service.mass_target_add_preview(int(target_group_id),int(target_count),list(source_group_ids),list(account_ids))
        except Exception as exc:self._error(exc);return None
    def used_account_ids_for_target(self,target_group_id):
        try:return self.service.used_account_ids_for_target(int(target_group_id))
        except Exception as exc:self._error(exc);return set()
    def start_mass_target_add(self,target_group_id,target_count,source_group_ids,account_ids,parallel_jobs=1,callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):self.featureLocked.emit(str(FeatureKey.DIRECT_MEMBER_INVITE),str(self.feature_gate.get_required_plan(FeatureKey.DIRECT_MEMBER_INVITE) or "ULTIMATE"));return None
        ids=[int(x) for x in account_ids]
        def progress(payload):self.massTargetAddProgress.emit(payload)
        return self._submit(self.service.mass_add_members_to_target(int(target_group_id),int(target_count),list(source_group_ids),ids,int(parallel_jobs),progress_callback=progress),"mass_target_add",ids[0] if ids else 0,lambda r:self._mass_add_done(r,callback),self._mass_add_fail)
    def _mass_add_done(self,result,callback=None):
        self.massTargetAddCompleted.emit(result);self.refresh();self.memberStatsChanged.emit()
        if str(result.get("status",""))=="BLOCKED":
            self.toast_requested.emit(result.get("message") or "Mass add was blocked by preflight.","Warning")
        else:
            self.toast_requested.emit(f"Mass add finished: {result.get('successful',0)} successful, {result.get('skipped',0)} skipped, {result.get('failed',0)} failed. Target {'reached' if result.get('finished') else 'not reached'} ({result.get('shortage',0)} short).","Success" if result.get('finished') else "Warning")
        callback(result) if callback else None
    def _mass_add_fail(self,_account_id,message):
        self.massTargetAddFailed.emit(message);self.toast_requested.emit(message,"Error")
    def pause_mass_target_add(self,job_ids):
        ids=[int(x) for x in (job_ids or [])]
        if ids:return self._submit(self.service.pause_mass_target_add(ids),"mass_target_add_pause",0,lambda _r:self.toast_requested.emit("Mass add paused.","Info"))
    def resume_mass_target_add(self,job_ids):
        ids=[int(x) for x in (job_ids or [])]
        if ids:return self._submit(self.service.resume_mass_target_add(ids),"mass_target_add_resume",0,lambda _r:self.toast_requested.emit("Mass add resumed.","Info"))
    def stop_mass_target_add(self,job_ids):
        ids=[int(x) for x in (job_ids or [])]
        if ids:return self._submit(self.service.stop_mass_target_add(ids),"mass_target_add_stop",0,lambda _r:self.toast_requested.emit("Mass add stop requested.","Warning"))
    def import_csv(self,path):
        try:r=self.service.import_csv(path);self.refresh();self.toast_requested.emit(f"Inserted: {r['inserted']} • Updated: {r['updated']} • Unchanged: {r['unchanged']} • Invalid: {r['invalid']}","Success" if not r['errors'] else "Warning");self.memberStatsChanged.emit();return r
        except Exception as exc:self._error(exc);return None
    on_import=import_csv
    def export_csv(self,path,scope="current",selected=None):
        try:
            if scope=="selected":items=list(selected or [])
            elif scope=="all_filtered":items=self._iter_all_filtered()
            else:items=self.current_items
            self.service.export_csv(path,items);self.toast_requested.emit("Members exported successfully.","Success");return True
        except Exception as exc:self._error(exc);return False
    def _iter_all_filtered(self):
        page=1
        while True:
            items,total=self.service.get_member_page(page,500,self.search_text,self.eligibility,self.consent,None,self.only_username,source_group_id=self.source_group_id,target_group_id=self.target_group_id,tag=self.tag,bot_filter=self.bot_filter,blacklist_filter=self.blacklist_filter,exclude_blacklist=self.exclude_blacklist,exclude_existing=self.exclude_existing,only_eligible=self.only_eligible)
            if not items:break
            for item in items:yield item
            if page*500>=total:break
            page+=1
    on_export=export_csv
    def statistics(self):return self.service.statistics()
    def _update(self,id,fn,message,signal):
        try:result=fn();self.refresh();signal.emit(id);self.memberStatsChanged.emit();self.toast_requested.emit(message,"Success");return result
        except Exception as exc:self._error(exc);return None
    def _status_update_many(self,ids,fn,message):
        values=sorted({int(value) for value in ids if int(value)>0})
        if not values:return 0
        try:
            updated=int(fn(values) or 0);self.refresh();self.memberEligibilityBatchChanged.emit(values);self.memberStatsChanged.emit()
            self.toast_requested.emit(f"{message} {updated:,} record(s).","Success");return updated
        except Exception as exc:self._error(exc);return 0
    def _submit(self,coro,operation,account_id,success,failure=None):
        if not self.worker:self._error(RuntimeError("Telegram runtime is unavailable."));return None
        try:token=self.worker.submit_coroutine(coro,operation=operation,account_id=account_id);self._handlers[token]=(success,failure);return token
        except Exception as exc:self._error(exc);return None
    def _done(self,token,result):
        h=self._handlers.pop(token,None)
        if h and h[0]:h[0](result)
    def _failed(self,token,account_id,message):
        h=self._handlers.pop(token,None)
        if not h:return
        if h[1]:h[1](account_id,message)
        else:self._error(RuntimeError(message))
    def _error(self,exc):message=str(exc) or "Cannot complete the member operation.";self.errorOccurred.emit(message);self.toast_requested.emit(message,"Error")

    def _on_worker_finished(self) -> None:
        """Drain pending handlers when the worker thread stops unexpectedly."""
        pending = dict(self._handlers)
        self._handlers.clear()
        for _token, (_success, failure) in pending.items():
            if failure:
                try:
                    failure(0, "The Telegram worker stopped unexpectedly.")
                except Exception:
                    pass
        if pending:
            self.toast_requested.emit(
                "The Telegram worker stopped. Pending member operations were cancelled.",
                "Warning",
            )
            self.refresh()
