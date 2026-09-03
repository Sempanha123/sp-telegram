from __future__ import annotations

import asyncio
import csv
import time
import uuid
from pathlib import Path
from typing import Callable

from app.models.entities import GroupAccount, Member
from app.telegram.models.member_sync_result import MemberSyncOptions, MemberSyncProgress, MemberSyncResult
from app.utils.formatters import utc_now_iso

MAX_INVITATION_BATCH_ACCOUNTS=5
MAX_INVITATION_MEMBERS_PER_ACCOUNT=20
MAX_INVITATION_BATCH_MEMBERS=100

# Mass Add to Target (auto-fill from source groups with parallel accounts).
MASS_ADD_MAX_ACCOUNTS=20
MASS_ADD_MAX_PARALLEL=4
MASS_ADD_MAX_TARGET=5000
MASS_ADD_PER_ACCOUNT_CAP=100


class MemberService:
    """Persistent member domain service plus safe read-only Telegram synchronization."""
    def __init__(self, repository, source_repository=None, exclusion_repository=None, target_repository=None,
                 account_member_repository=None, sync_repository=None, group_repository=None,
                 group_account_repository=None, account_repository=None, telegram_member_service=None,
                 eligibility_engine=None, job_repository=None, alert_service=None, logger=None,
                 error_handler=None, client_manager=None, account_service=None, target_action_repository=None, target_invitation_service=None, invitation_preflight_service=None):
        self.repository=repository;self.sources=source_repository;self.exclusions=exclusion_repository
        self.targets=target_repository;self.account_member_states=account_member_repository;self.sync_runs=sync_repository
        self.groups=group_repository;self.group_accounts=group_account_repository;self.accounts=account_repository
        self.telegram=telegram_member_service;self.eligibility=eligibility_engine;self.jobs=job_repository
        self.alerts=alert_service;self.logger=logger;self.error_handler=error_handler;self.client_manager=client_manager
        self.account_service=account_service;self.target_actions=target_action_repository;self.target_invitation=target_invitation_service;self.invitation_preflight_service=invitation_preflight_service;self.account_safety_service=None;self.cleanup_service=None;self._active_sync_jobs={};self._active_invitation_jobs={};self.license_limit_service=None;self.feature_gate=None

    def _account_collect_readiness(self, group_id:int, account_id:int) -> tuple[bool,str]:
        group=self.groups.get_by_id(group_id) if self.groups else None
        mapping=self.group_accounts.get_mapping(group_id,account_id) if self.group_accounts else None
        account=self.accounts.get_by_id(account_id) if self.accounts else None
        if not group or not bool(getattr(group,"is_source",0)):
            return False,"Select a saved Source Group first."
        if not mapping:
            return False,"The selected account is not mapped to this source group."
        if str(getattr(mapping,"access_state","UNKNOWN")).upper() in {"ACCESS_DENIED","NOT_JOINED","UNAVAILABLE"} or (getattr(mapping,"can_view",None) is not None and not bool(getattr(mapping,"can_view",None))):
            return False,"The selected account does not currently have access to this source group."
        if not account or not bool(getattr(account,"is_enabled",0)):
            return False,"The selected Telegram account is disabled or unavailable."
        if str(getattr(account,"authorization_status","UNKNOWN")).upper() != "AUTHORIZED":
            return False,"The selected account requires Telegram login."
        session_path=str(getattr(account,"session_path","") or "")
        if not session_path or not Path(session_path).is_file():
            return False,"The selected account session is missing. Login to the account again."
        health=str(getattr(account,"health_status","UNKNOWN") or "UNKNOWN").upper()
        if health in {"SESSION_INVALID","LOGIN_REQUIRED","DISABLED"}:
            return False,"The selected account is not ready for Telegram operations."
        if health in {"COOLDOWN","RESTRICTED"}:
            return False,"The selected account is currently restricted or waiting. Review Account Health before syncing."
        return True,""

    def get_accessible_source_groups(self):
        """Saved source groups with at least one locally authorized accessible mapping."""
        groups=self.groups.get_sources() if self.groups else []
        out=[]
        for group in groups:
            # Visibility is based on authorization/session/group access, not on a
            # temporary health cooldown.  A cooldown account stays visible so the
            # UI can explain why Start is disabled instead of making the source
            # disappear unexpectedly.
            if self.get_eligible_group_accounts(group.id):
                out.append(group)
        return out

    def get_eligible_group_accounts(self, group_id:int):
        mappings=self.group_accounts.get_group_accounts(group_id) if self.group_accounts else []
        out=[]
        for mapping in mappings:
            # Keep legitimate mapped accounts visible even while in cooldown so the
            # operator can see the reason Start is disabled.  Invalid/login-required
            # mappings are not offered as collector accounts.
            account=self.accounts.get_by_id(mapping.account_id) if self.accounts else None
            if not account or not bool(getattr(account,"is_enabled",0)):
                continue
            if str(getattr(account,"authorization_status","UNKNOWN")).upper()!="AUTHORIZED":
                continue
            if str(getattr(mapping,"access_state","UNKNOWN")).upper() in {"ACCESS_DENIED","NOT_JOINED","UNAVAILABLE"} or (getattr(mapping,"can_view",None) is not None and not bool(getattr(mapping,"can_view",None))):
                continue
            session_path=str(getattr(account,"session_path","") or "")
            if not session_path or not Path(session_path).is_file():
                continue
            out.append(mapping)
        return out

    def collector_readiness(self, group_id:int|None, account_id:int|None):
        if not group_id:
            return False,"Select an authorized source group first."
        if not account_id:
            return False,"Select an authorized Telegram account first."
        return self._account_collect_readiness(int(group_id),int(account_id))

    def member_pool_capacity_summary(self):
        current=self.repository.count_all()
        limit=None;remaining=None;plan="UNLICENSED"
        if self.license_limit_service is not None:
            from app.license.feature_keys import LimitKey
            limit=self.license_limit_service.get_limit(LimitKey.MAX_MEMBER_POOL)
            remaining=self.license_limit_service.get_remaining(LimitKey.MAX_MEMBER_POOL)
        if self.feature_gate is not None:
            state=self.feature_gate.license_service.get_current_license()
            plan=str(getattr(state,"plan",None) or "UNLICENSED")
        return {"current":current,"limit":limit,"remaining":remaining,"plan":plan}

    def _licensed_member_addition_capacity(self):
        """Return remaining NEW-member capacity; existing records are always updatable.

        Invalid/expired/suspended licenses get zero new-member capacity even if the
        cached plan's numerical limit would otherwise have room. Unlimited plans
        return ``None``.
        """
        if self.license_limit_service is None:
            return None
        check=self.license_limit_service.can_add_member_records(1)
        if not check.allowed:
            return 0
        return check.remaining

    def get_member_page(self,page=1,page_size=100,search=None,eligibility=None,consent=None,excluded=None,only_username=False,**filters):
        # ``exclude_blacklist`` is a first-class filter in the modern Member Pool
        # controller.  Older call sites may still use the legacy ``excluded``
        # argument.  Normalize the two here instead of forwarding both names,
        # which would raise ``got multiple values for keyword argument``.
        explicit_exclude_blacklist = filters.pop("exclude_blacklist", None)
        if explicit_exclude_blacklist is None:
            explicit_exclude_blacklist = (excluded is False) if excluded is not None else False
        return self.repository.get_filtered_page(
            page,page_size,search=search,eligibility=eligibility,consent=consent,
            exclude_blacklist=bool(explicit_exclude_blacklist),
            only_username=only_username,**filters
        )
    def get_members(self):return self.repository.search("",500)
    def get_member(self,id:int):return self.repository.get_by_id(id)
    def get_member_details(self,id:int):
        member=self.repository.get_by_id(id)
        if not member:return None
        return {
            "member":member,
            "sources":self.sources.get_member_sources(id) if self.sources else [],
            "exclusions":self.exclusions.get_member_exclusions(id) if self.exclusions else [],
            "tags":self.repository.get_tags(id),
            "target_states":self.targets.get_member_states_for_member(id) if self.targets and hasattr(self.targets,"get_member_states_for_member") else [],
            "invitation_history":self.target_actions.get_for_member(id) if self.target_actions else [],
        }
    def search_members(self,query:str):return self.repository.search(query)
    def remove_member_source(self, member_id:int, group_id:int, *, remove_orphan:bool=False):
        if not self.sources: raise RuntimeError("Member source repository is unavailable.")
        with self.repository.db.transaction():
            removed=self.repository.remove_source(int(member_id),int(group_id))
            orphan=False
            if removed:
                row=self.repository.db.fetch_one("SELECT 1 FROM member_sources WHERE member_id=? LIMIT 1",(int(member_id),))
                orphan=row is None
                protected=self.repository.db.fetch_one("SELECT 1 FROM member_exclusions WHERE member_id=? LIMIT 1",(int(member_id),)) is not None
                protected=protected or (self.target_actions is not None and self.repository.db.fetch_one("SELECT 1 FROM member_target_actions WHERE member_id=? LIMIT 1",(int(member_id),)) is not None)
                if orphan and remove_orphan and not protected:
                    self.repository.delete(int(member_id))
            self._log("MEMBER_SOURCE_CLEARED",f"Member source relationship cleared for group ID {int(group_id)}.",group_id=int(group_id))
        return {"removed":bool(removed),"orphan":bool(orphan)}
    def save_member(self,data:dict):
        existing=self.repository.get_by_telegram_id(int(data["telegram_user_id"]))
        if existing is None and self.license_limit_service is not None:
            check=self.license_limit_service.can_add_member_records(1)
            if not check.allowed:raise RuntimeError(check.message or "Member Pool plan limit reached.")
        item=Member(telegram_user_id=int(data["telegram_user_id"]),username=(data.get("username") or "").strip().lstrip("@") or None,
            first_name=(data.get("first_name") or "").strip() or None,last_name=(data.get("last_name") or "").strip() or None,
            eligibility_status=str(data.get("eligibility_status") or "UNKNOWN").upper().replace(" ","_"),consent_status=str(data.get("consent_status") or "UNKNOWN").upper().replace(" ","_"),notes=(data.get("notes") or "").strip() or None)
        return self.repository.upsert_by_telegram_id(item)
    def set_eligibility(self,id:int,status:str):return self.repository.set_eligibility(id,status.upper().replace(" ","_"))
    def set_consent(self,id:int,status:str):return self.repository.set_consent(id,status.upper().replace(" ","_"))
    def set_eligibility_many(self,ids,status:str):return self.repository.set_status_many(ids,"eligibility_status",status.upper().replace(" ","_"))
    def set_consent_many(self,ids,status:str):return self.repository.set_status_many(ids,"consent_status",status.upper().replace(" ","_"))
    def update_notes(self,id:int,notes:str|None):
        return self.repository.update_fields(id,{"notes":(notes or "").strip() or None,"updated_at":utc_now_iso()})

    async def refresh_member_profile(self,member_id:int,account_id:int):
        """Explicit single-member profile refresh using one operator-selected authorized account."""
        member=self.repository.get_by_id(member_id);account=self.accounts.get_by_id(account_id) if self.accounts else None
        if not member:raise ValueError("Member not found.")
        if not account or not account.is_enabled or account.authorization_status!="AUTHORIZED":raise ValueError("Selected account is not authorized.")
        client=await self.client_manager.get_client(account_id) if self.client_manager else None
        if client is None:
            if not account.session_path:raise ValueError("Selected account has no Telegram session.")
            client=await self.client_manager.create_client(account_id,account.session_path)
        if not client.is_connected():await self.client_manager.connect(account_id)
        if not await client.is_user_authorized():raise ValueError("Selected account requires Telegram login.")
        try:
            user=await client.get_entity(member.telegram_user_id)
            tm=self.telegram.sync.normalizer.normalize(user,0,account_id)
            if tm.telegram_user_id!=member.telegram_user_id:raise RuntimeError("Telegram returned a different member identity; the local record was not changed.")
            self.repository.update_profile(member_id,{"username":tm.username,"first_name":tm.first_name,"last_name":tm.last_name,"is_bot":tm.is_bot,"is_deleted":tm.is_deleted,"is_verified":tm.is_verified,"is_scam":tm.is_scam,"is_fake":tm.is_fake,"is_premium":tm.is_premium,"profile_updated_at":tm.observed_at,"last_seen_at":tm.observed_at})
            self._log("MEMBER_UPDATED",f"Member ID {member_id} profile refreshed.",account_id=account_id)
            return self.repository.get_by_id(member_id)
        except Exception as exc:
            result=self.error_handler.classify(exc) if self.error_handler else None
            raise RuntimeError(result.message if result else "Could not refresh this member profile.") from None
    def evaluate_member(self,id:int,target_group_id:int|None=None):return self.eligibility.evaluate(id,target_group_id)
    def assign_tag(self,id:int,tag:str):return self.repository.add_tag(id,tag)
    def add_tag(self,id:int,tag:str):return self.assign_tag(id,tag)
    def remove_tag(self,id:int,tag:str):return self.repository.remove_tag(id,tag)
    def list_tags(self):return self.repository.list_tags()
    def create_tag(self,name):return self.repository.create_tag(name)
    def rename_tag(self,old,new):return self.repository.rename_tag(old,new)
    def delete_tag(self,name):return self.repository.delete_tag(name)
    def add_blacklist(self,id:int,reason:str|None=None):
        item=self.exclusions.add_global_blacklist(id,reason) if hasattr(self.exclusions,"add_global_blacklist") else self.exclusions.add_global_exclusion(id,reason)
        self.repository.set_global_excluded(id,True);self.repository.set_eligibility(id,"EXCLUDED");self._log("MEMBER_BLACKLISTED",f"Member ID {id} added to global blacklist.");return item
    def remove_blacklist(self,id:int):
        count=self.exclusions.remove_member_global(id);self.repository.set_global_excluded(id,False);self._log("MEMBER_BLACKLIST_REMOVED",f"Member ID {id} global exclusions removed.");return count
    def mark_do_not_contact(self,id:int,reason:str|None=None):
        item=self.exclusions.add_do_not_contact(id,reason) if hasattr(self.exclusions,"add_do_not_contact") else self.exclusions.add_global_exclusion(id,reason,exclusion_type="DO_NOT_CONTACT")
        self.repository.set_global_excluded(id,True);self.repository.set_eligibility(id,"DO_NOT_CONTACT");self._log("MEMBER_EXCLUDED",f"Member ID {id} marked Do Not Contact.");return item
    def bulk_upsert_members(self,members):
        items=list(members or [])
        if self.license_limit_service is None:return self.repository.bulk_upsert(items)
        remaining=self._licensed_member_addition_capacity();prepared=[];skipped=0
        for item in items:
            telegram_id=getattr(item,"telegram_user_id",None) if not isinstance(item,dict) else item.get("telegram_user_id")
            existing=self.repository.get_by_telegram_id(int(telegram_id)) if telegram_id is not None else None
            if existing is None and remaining is not None and remaining<=0:skipped+=1;continue
            prepared.append(item)
            if existing is None and remaining is not None:remaining-=1
        result=self.repository.bulk_upsert(prepared);result["plan_limit_skipped"]=skipped;result["excluded"]=int(result.get("excluded",0))+skipped;return result

    async def preview_source(self,group_id:int,account_id:int):
        ready,message=self.collector_readiness(group_id,account_id)
        if not ready:raise ValueError(message)
        group,mapping,entity=await self._prepare_group_account(group_id,account_id,source_required=True)
        result=await self.telegram.access.check(group_id,account_id,entity)
        self.group_accounts.update_member_access(group_id,account_id,result.availability,checked_at=result.checked_at)
        return {"group":group,"mapping":self.group_accounts.get_mapping(group_id,account_id),"access":result,"capacity":self.member_pool_capacity_summary()}

    async def sync_source_members(self,group_id:int,account_id:int,options:MemberSyncOptions|None=None,*,sync_run_id:str|None=None,progress_callback:Callable|None=None)->MemberSyncResult:
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.MEMBER_SYNC)
        options=options or MemberSyncOptions();sync_run_id=sync_run_id or uuid.uuid4().hex
        started=utc_now_iso();job=self.jobs.create_job("MEMBER_SYNC",status="VALIDATING",account_id=account_id,group_id=group_id,started_at=started,metadata_json='{"phase":5}') if self.jobs else None
        if job:self._active_sync_jobs[sync_run_id]=job.id
        run=None
        try:
            group,mapping,entity=await self._prepare_group_account(group_id,account_id,source_required=True)
            access=await self.telegram.access.check(group_id,account_id,entity)
            self.group_accounts.update_member_access(group_id,account_id,access.availability,checked_at=access.checked_at)
            if access.availability in {"HIDDEN","UNAVAILABLE","ACCESS_DENIED"}:
                code=access.error_code or ("PARTICIPANT_LIST_HIDDEN" if access.availability=="HIDDEN" else "PARTICIPANT_LIST_UNAVAILABLE")
                self._alert("WARNING","MEMBER_SYNC",f"Participant list {access.availability.lower()}",access.message,account_id=account_id,group_id=group_id)
                raise MemberSyncUnavailable(code,access.message)
            if self.sync_runs:run=self.sync_runs.create_run(sync_run_id,group_id,account_id,job_id=job.id if job else None,availability=access.availability)
            if job:self.jobs.update_fields(job.id,{"status":"RUNNING","updated_at":utc_now_iso()})
            self._log("MEMBER_SYNC_STARTED",f"Member sync started for group ID {group_id}.",account_id=account_id,group_id=group_id)
            progress=MemberSyncProgress(sync_run_id,availability=access.availability);batch=[];seen:set[int]=set();last_emit=time.monotonic()
            async for tm in self.telegram.sync.iter_source_members(group_id,account_id,entity,options,sync_run_id):
                progress.processed+=1;progress.current_member_id=tm.telegram_user_id
                if tm.telegram_user_id in seen:progress.duplicates+=1;continue
                seen.add(tm.telegram_user_id)
                include,reason=self._filter(tm,options)
                if not include:
                    progress.excluded+=1
                    if reason=="BOT":progress.bots+=1
                    if reason=="DELETED_ACCOUNT":progress.deleted+=1
                    continue
                batch.append(tm)
                if len(batch)>=max(20,min(500,options.page_size)):
                    self._save_batch(batch,group_id,account_id,sync_run_id,options,progress);batch.clear()
                now=time.monotonic()
                if progress.processed%50==0 or now-last_emit>=0.35:
                    self._emit_progress(progress,progress_callback,job);last_emit=now
            if batch:self._save_batch(batch,group_id,account_id,sync_run_id,options,progress)
            cancelled=sync_run_id in self.telegram.sync._cancelled
            status="CANCELLED" if cancelled else ("PARTIAL_SUCCESS" if access.availability=="PARTIAL" else "COMPLETED")
            if status=="COMPLETED" and access.availability=="FULL":self.sources.mark_missing_after_full_sync(group_id,sync_run_id)
            stored=self.sources.count_by_group(group_id,active_only=True)
            self.group_accounts.update_member_sync_stats(group_id,account_id,status=status,stored_count=stored,new_count=progress.inserted,updated_count=progress.updated,excluded_count=progress.excluded)
            completed=utc_now_iso();result=MemberSyncResult(sync_run_id,group_id,account_id,access.availability,status,progress.processed,progress.inserted,progress.updated,progress.unchanged,progress.duplicates,progress.excluded,progress.bots,progress.deleted,progress.errors,started,completed,plan_limit_skipped=progress.plan_limit_skipped)
            if run:self.sync_runs.finish(run.id,status,processed=progress.processed,inserted=progress.inserted,updated=progress.updated,unchanged=progress.unchanged,duplicates=progress.duplicates,excluded=progress.excluded,errors=progress.errors)
            if job:self.jobs.update_fields(job.id,{"status":status,"progress":100,"total_items":progress.processed,"success_count":progress.inserted+progress.updated,"skipped_count":progress.excluded+progress.duplicates,"failed_count":progress.errors,"finished_at":completed,"updated_at":completed})
            self.telegram.sync.cleanup(sync_run_id);self._active_sync_jobs.pop(sync_run_id,None);self._log("MEMBER_SYNC_COMPLETED",f"Member sync completed: {progress.processed} processed, {progress.inserted} new, {progress.updated} updated.",account_id=account_id,group_id=group_id)
            return result
        except Exception as exc:
            self.telegram.sync.cleanup(sync_run_id);self._active_sync_jobs.pop(sync_run_id,None);code,message=self._classify(exc)
            status="PAUSED" if code=="FLOOD_WAIT" else "FAILED";now=utc_now_iso()
            if run:self.sync_runs.finish(run.id,status,error_code=code,error_message=message)
            if job:self.jobs.update_fields(job.id,{"status":status,"finished_at":now,"last_error":message,"updated_at":now})
            if code=="FLOOD_WAIT" and self.account_service:
                classified=self.error_handler.classify(exc);self.account_service.record_confirmed_flood_wait(account_id,classified.wait_seconds,message)
                self._alert("WARNING","FLOOD_WAIT","Account entered cooldown",message,account_id=account_id,group_id=group_id)
            else:self._alert("WARNING","MEMBER_SYNC","Member sync failed",message,account_id=account_id,group_id=group_id)
            self._log("MEMBER_SYNC_FAILED",f"Member sync failed: {code}.",account_id=account_id,group_id=group_id,level="ERROR")
            raise RuntimeError(message) from exc

    async def pause_sync(self,sync_run_id:str):
        self.telegram.sync.pause(sync_run_id);job_id=self._active_sync_jobs.get(sync_run_id)
        if job_id and self.jobs:self.jobs.update_status(job_id,"PAUSED")
        self._log("MEMBER_SYNC_PAUSED",f"Member sync {sync_run_id[:8]} paused.");return True
    async def resume_sync(self,sync_run_id:str):
        self.telegram.sync.resume(sync_run_id);job_id=self._active_sync_jobs.get(sync_run_id)
        if job_id and self.jobs:self.jobs.update_status(job_id,"RUNNING")
        self._log("MEMBER_SYNC_RESUMED",f"Member sync {sync_run_id[:8]} resumed.");return True
    async def stop_sync(self,sync_run_id:str):
        self.telegram.sync.stop(sync_run_id);job_id=self._active_sync_jobs.get(sync_run_id)
        if job_id and self.jobs:self.jobs.update_status(job_id,"STOPPING")
        self._log("MEMBER_SYNC_STOPPED",f"Member sync {sync_run_id[:8]} stop requested.");return True

    async def check_target_membership(self,member_id:int,target_group_id:int,account_id:int):
        member=self.repository.get_by_id(member_id)
        if not member:raise ValueError("Member not found.")
        group,mapping,entity=await self._prepare_group_account(target_group_id,account_id,target_required=True)
        result=await self.telegram.target.check_member(member_id,target_group_id,account_id,entity,member.telegram_user_id)
        self.targets.upsert_state(member_id,target_group_id,result.status,account_id=account_id,error_code=result.error_code,error_message=result.error_message,checked_at=result.checked_at)
        self._log("TARGET_MEMBER_CHECK",f"Member ID {member_id} target status checked: {result.status}.",account_id=account_id,group_id=target_group_id)
        return result

    async def sync_target_member_states(self,target_group_id:int,account_id:int,*,max_records:int|None=None,progress_callback=None):
        group,mapping,entity=await self._prepare_group_account(target_group_id,account_id,target_required=True)
        access=await self.telegram.access.check(target_group_id,account_id,entity)
        if access.availability in {"HIDDEN","UNAVAILABLE","ACCESS_DENIED"}:raise RuntimeError(access.message or "Target participant list is unavailable.")
        job=self.jobs.create_job("TARGET_MEMBER_SYNC",status="RUNNING",account_id=account_id,group_id=target_group_id,started_at=utc_now_iso()) if self.jobs else None
        checked=existing=unknown=errors=0;seen=set();opts=MemberSyncOptions(skip_bots=False,skip_deleted=False,max_records=max_records)
        run_id="target_"+uuid.uuid4().hex;self.telegram.sync.create_control(run_id)
        try:
            async for tm in self.telegram.sync.iter_source_members(target_group_id,account_id,entity,opts,run_id):
                checked+=1
                local=self.repository.get_by_telegram_id(tm.telegram_user_id)
                if local:
                    self.targets.upsert_state(local.id,target_group_id,"ALREADY_MEMBER",account_id=account_id);existing+=1;seen.add(local.id)
                else:unknown+=1
                if progress_callback and checked%50==0:progress_callback({"checked":checked,"existing":existing,"unknown":unknown,"errors":errors})
            snapshot={"already_member":existing,"not_member":0}
            if str(access.availability).upper()=="FULL":
                snapshot=self.targets.apply_full_snapshot(target_group_id,list(seen),account_id=account_id)
                existing=int(snapshot.get("already_member",existing)); unknown=0
            if self.group_accounts:
                try:self.group_accounts.update_fields(mapping.id,{"last_member_sync_at":utc_now_iso(),"member_sync_status":"COMPLETED","stored_member_count":checked})
                except Exception:pass
            if job:self.jobs.update_fields(job.id,{"status":"COMPLETED","progress":100,"total_items":checked,"success_count":existing,"skipped_count":unknown,"failed_count":errors,"finished_at":utc_now_iso(),"updated_at":utc_now_iso()})
            return {"checked":checked,"already_member":existing,"not_member":int(snapshot.get("not_member",0)),"unknown":unknown,"errors":errors,"availability":access.availability}
        finally:self.telegram.sync.cleanup(run_id)


    def auto_select_account_for_target(self, target_group_id: int, permission: str = "invite"):
        service = getattr(self, "account_assignment_service", None)
        if service is None:
            return {"allowed": False, "account_id": None, "reason": "Account assignment service is unavailable."}
        decision = service.auto_select(int(target_group_id), str(permission))
        return {
            "allowed": bool(decision.allowed), "account_id": decision.account_id, "reason": decision.reason,
            "account": decision.account, "mapping": decision.mapping,
        }

    def invitation_precheck(self,target_group_id:int,account_id:int,member_ids:list[int]):
        """Compatibility/local preflight that never raises for ordinary blockers."""
        if self.invitation_preflight_service is not None:
            return self.invitation_preflight_service.evaluate_cached(target_group_id,account_id,list(member_ids)).to_dict()
        # Fallback for narrow unit-service construction. Keep normal validation
        # failures as data so the UI can render them inline rather than surfacing
        # them as unexpected exceptions.
        from app.services.invitation_preflight_service import InvitationPreflightService
        service=InvitationPreflightService(self.repository,self.exclusions,self.targets,self.groups,self.group_accounts,self.accounts,client_manager=self.client_manager,account_safety_service=self.account_safety_service)
        return service.evaluate_cached(target_group_id,account_id,list(member_ids)).to_dict()

    async def invitation_preflight(self,target_group_id:int,account_id:int,member_ids:list[int]):
        if self.invitation_preflight_service is not None:
            return (await self.invitation_preflight_service.refresh(target_group_id,account_id,list(member_ids))).to_dict()
        from app.services.invitation_preflight_service import InvitationPreflightService
        service=InvitationPreflightService(self.repository,self.exclusions,self.targets,self.groups,self.group_accounts,self.accounts,client_manager=self.client_manager,account_safety_service=self.account_safety_service)
        return (await service.refresh(target_group_id,account_id,list(member_ids))).to_dict()

    @staticmethod
    def _explicit_ids(values):
        out=[]
        for value in values or []:
            try:item=int(value)
            except (TypeError,ValueError):continue
            if item>0 and item not in out:out.append(item)
        return out

    def _build_invitation_batch_plan(self,target_group_id:int,account_ids:list[int],member_ids:list[int],preflights:dict[int,dict]):
        account_ids=self._explicit_ids(account_ids);member_ids=sorted(set(self._explicit_ids(member_ids)))
        blockers=[];warnings=[]
        def add(values,message):
            if message and message not in values:values.append(message)
        if not account_ids:add(blockers,"Select at least one authorized account for this batch.")
        if len(account_ids)>MAX_INVITATION_BATCH_ACCOUNTS:add(blockers,f"Select no more than {MAX_INVITATION_BATCH_ACCOUNTS} accounts per invitation batch.")
        if not member_ids:add(blockers,"No valid selected Member Pool records are available.")
        if len(member_ids)>MAX_INVITATION_BATCH_MEMBERS:add(blockers,f"This batch is limited to {MAX_INVITATION_BATCH_MEMBERS} selected members.")
        first=next((preflights.get(aid) for aid in account_ids if preflights.get(aid)),None) or {}
        counts=dict(first.get("counts") or {"selected":len(member_ids),"ready":0})
        counts.setdefault("deleted",int(first.get("deleted_count",0) or 0));counts.setdefault("bots",int(first.get("bot_count",0) or 0))
        ready_ids=[]
        for item in first.get("items") or []:
            member=item.get("member") if isinstance(item,dict) else None
            if bool(item.get("allowed")) and getattr(member,"id",None):ready_ids.append(int(member.id))
        ready_ids=list(dict.fromkeys(ready_ids))
        if not ready_ids and member_ids:add(blockers,"No member is ready to add yet. A direct Add Member requires Eligibility = Eligible, Consent = Approved, and destination status = verified Not Member.")
        account_rows=[]
        for account_id in account_ids:
            pre=preflights.get(account_id) or {}
            account=getattr(pre.get("account"),"first_name",None) or getattr(pre.get("account"),"username",None) or f"Account {account_id}"
            row_blockers=list(pre.get("blocking_reasons") or [])
            row_ready=bool(pre.get("can_start",pre.get("start_allowed",False)))
            if not pre:
                row_ready=False;row_blockers=["Account preflight was not completed."]
            smart_limits=bool(pre.get("smart_limits_enabled",False))
            daily_remaining=max(0,int(pre.get("invite_remaining_today",0) or 0)) if smart_limits else MAX_INVITATION_MEMBERS_PER_ACCOUNT
            batch_capacity=min(MAX_INVITATION_MEMBERS_PER_ACCOUNT,daily_remaining)
            for message in row_blockers:add(blockers,f"{account}: {message}")
            account_rows.append({
                "account_id":account_id,"account":pre.get("account"),"mapping":pre.get("mapping"),
                "name":str(account),"authorized":bool(pre.get("account_authorized")),
                "connected":bool(pre.get("account_connected")),"health":str(pre.get("account_health") or "UNKNOWN"),
                "role":str(pre.get("target_role") or "UNKNOWN"),"can_invite":bool(pre.get("can_invite")),
                "can_manage_invite_links":bool(pre.get("can_manage_invite_links")),
                "restriction":pre.get("restriction_status"),"ready":row_ready,"blocking_reasons":row_blockers,
                "safety_state":str(pre.get("safety_state") or "NORMAL"),"smart_limits":smart_limits,
                "invite_used_today":int(pre.get("invite_used_today",0) or 0),"invite_daily_limit":int(pre.get("invite_daily_limit",0) or 0),
                "invite_remaining_today":daily_remaining,"batch_capacity":batch_capacity,
                "assigned_member_ids":[],"assigned_count":0,
            })
            for message in pre.get("warnings") or []:add(warnings,f"{account}: {message}")
        capacity=min(MAX_INVITATION_BATCH_MEMBERS,sum(row["batch_capacity"] for row in account_rows if row["ready"]))
        if len(ready_ids)>capacity:add(blockers,f"The selected accounts have capacity for {capacity} ready member(s) in this batch after daily safety limits ({MAX_INVITATION_MEMBERS_PER_ACCOUNT} maximum per account).")
        cursor=0;assigned_total=0;assignments=[]
        if len(account_ids)<=MAX_INVITATION_BATCH_ACCOUNTS and len(member_ids)<=MAX_INVITATION_BATCH_MEMBERS:
            for member_id in ready_ids:
                assigned=False
                for offset in range(len(account_rows)):
                    index=(cursor+offset)%len(account_rows) if account_rows else 0
                    row=account_rows[index] if account_rows else None
                    if row and row["ready"] and len(row["assigned_member_ids"])<row["batch_capacity"]:
                        row["assigned_member_ids"].append(member_id);cursor=(index+1)%len(account_rows);assigned_total+=1;assigned=True;break
                if not assigned:break
            for row in account_rows:
                assigned=row["assigned_member_ids"];row["assigned_count"]=len(assigned)
                if assigned:assignments.append({"account_id":row["account_id"],"member_ids":assigned,"count":len(assigned),"daily_remaining":row["invite_remaining_today"]})
        can_start=bool(assignments and assigned_total==len(ready_ids) and all(row["ready"] for row in account_rows) and not blockers)
        return {
            "target_group_id":int(target_group_id),"preflight_complete":bool(preflights),
            "explicit_account_selection":True,"account_ids":account_ids,"selected_account_count":len(account_ids),
            "limits":{"max_accounts":MAX_INVITATION_BATCH_ACCOUNTS,"max_members_per_account":MAX_INVITATION_MEMBERS_PER_ACCOUNT,"max_members":MAX_INVITATION_BATCH_MEMBERS},
            "daily_capacity":capacity,
            "counts":counts,"ready_member_ids":ready_ids,"accounts":account_rows,"assignments":assignments,
            "blocking_reasons":blockers,"warnings":warnings,"can_start":can_start,"start_allowed":can_start,
            "group":first.get("group"),"can_manage_invite_links":any(bool((preflights.get(aid) or {}).get("can_manage_invite_links")) for aid in account_ids),
        }

    def invitation_batch_precheck(self,target_group_id:int,account_ids:list[int],member_ids:list[int]):
        ids=self._explicit_ids(account_ids);members=self._explicit_ids(member_ids);preflights={}
        if len(ids)<=MAX_INVITATION_BATCH_ACCOUNTS and len(members)<=MAX_INVITATION_BATCH_MEMBERS:
            for account_id in ids:preflights[account_id]=self.invitation_precheck(target_group_id,account_id,members)
        return self._build_invitation_batch_plan(target_group_id,ids,members,preflights)

    async def _auto_verify_add_member_target_states(self,target_group_id:int,account_ids:list[int],member_ids:list[int]):
        target_group_id=int(target_group_id)
        account_ids=self._explicit_ids(account_ids)
        member_ids=self._explicit_ids(member_ids)
        summary={"requested":len(member_ids),"checked":0,"not_member":0,"already_member":0,"unknown":0,"errors":0,"account_id":None}
        if not member_ids or not account_ids or not self.targets:
            return summary
        verifier_id=None
        for account_id in account_ids:
            account=self.accounts.get_by_id(account_id) if self.accounts else None
            mapping=self.group_accounts.get_mapping(target_group_id,account_id) if self.group_accounts else None
            if not account or not mapping:
                continue
            if not bool(getattr(account,"is_enabled",0)):
                continue
            if str(getattr(account,"authorization_status","UNKNOWN") or "UNKNOWN").upper()!="AUTHORIZED":
                continue
            access=str(getattr(mapping,"access_state","UNKNOWN") or "UNKNOWN").upper()
            if access in {"ACCESS_DENIED","UNAVAILABLE","NO_ACCESS","NOT_JOINED","LEFT"}:
                continue
            verifier_id=int(account_id)
            break
        if verifier_id is None:
            return summary
        summary["account_id"]=verifier_id
        for member_id in member_ids:
            member=self.repository.get_by_id(member_id)
            if not member:
                continue
            eligibility=str(getattr(member,"eligibility_status","UNKNOWN") or "UNKNOWN").upper()
            consent=str(getattr(member,"consent_status","UNKNOWN") or "UNKNOWN").upper()
            if eligibility!="ELIGIBLE" or consent!="APPROVED":
                continue
            if bool(getattr(member,"is_deleted",0)) or bool(getattr(member,"is_bot",0)):
                continue
            if self.exclusions and (self.exclusions.is_global_blacklisted(member_id) or self.exclusions.is_do_not_contact(member_id)):
                continue
            state=self.targets.get_state(member_id,target_group_id)
            current=str(getattr(state,"state","UNKNOWN") or "UNKNOWN").upper() if state else "UNKNOWN"
            if current in {"MEMBER","ALREADY_MEMBER","JOINED"}:
                summary["already_member"]+=1
                continue
            if current=="NOT_MEMBER":
                summary["not_member"]+=1
                continue
            try:
                result=await self.check_target_membership(member_id,target_group_id,verifier_id)
                status=str(getattr(result,"status","UNKNOWN") or "UNKNOWN").upper()
                summary["checked"]+=1
                if status=="NOT_MEMBER":
                    summary["not_member"]+=1
                elif status in {"MEMBER","ALREADY_MEMBER","JOINED","INVITED"}:
                    summary["already_member"]+=1
                else:
                    summary["unknown"]+=1
            except Exception:
                summary["errors"]+=1
                summary["unknown"]+=1
        return summary

    async def invitation_batch_preflight(self,target_group_id:int,account_ids:list[int],member_ids:list[int]):
        ids=self._explicit_ids(account_ids)
        members=self._explicit_ids(member_ids)
        preflights={}
        if len(ids)<=MAX_INVITATION_BATCH_ACCOUNTS and len(members)<=MAX_INVITATION_BATCH_MEMBERS:
            await self._auto_verify_add_member_target_states(int(target_group_id),ids,members)
            for account_id in ids:
                preflights[account_id]=await self.invitation_preflight(target_group_id,account_id,members)
        plan=self._build_invitation_batch_plan(target_group_id,ids,members,preflights)
        counts=dict(plan.get("counts") or {})
        ready=int(counts.get("ready",0) or 0)
        selected=int(counts.get("selected",len(members)) or 0)
        if selected and not ready:
            reasons=[
                x for x in list(plan.get("blocking_reasons") or [])
                if "direct-invitation eligibility policy" not in str(x).lower()
                and "direct invitation eligibility policy" not in str(x).lower()
            ]
            eligibility=int(counts.get("eligibility_not_approved",0) or 0)
            consent=int(counts.get("consent_not_approved",0) or 0)
            unknown=int(counts.get("unknown",0) or 0)
            existing=int(counts.get("already_member",0) or 0)
            parts=[]
            if eligibility: parts.append(f"{eligibility} need Eligibility = Eligible")
            if consent: parts.append(f"{consent} need Consent = Approved")
            if unknown: parts.append(f"{unknown} could not be verified against the destination")
            if existing: parts.append(f"{existing} are already in the destination")
            message=("No members are ready yet: "+", ".join(parts)+".") if parts else "No members are ready for this Add Member job."
            if message not in reasons:
                reasons.insert(0,message)
            plan["blocking_reasons"]=reasons
        return plan

    def _blocked_invitation_result(pre:dict, code:str="PREFLIGHT_BLOCKED", message:str|None=None):
        reasons=list(pre.get("blocking_reasons") or [])
        return {
            "job_id":None,"status":"BLOCKED","error_code":code,
            "message":message or (reasons[0] if reasons else "Invitation preflight did not allow this operation."),
            "selected":int((pre.get("counts") or {}).get("selected",0)),"processed":0,
            "successful":0,"skipped":0,"failed":0,"results":[],"preflight":pre,
        }

    async def _confirm_invite_applied(self,member,target_group_id:int,account_id:int,entity):
        last_status="UNKNOWN"
        last_code=None
        last_message=None
        for delay in (0.35,0.8,1.5):
            await asyncio.sleep(delay)
            try:
                result=await self.telegram.target.check_member(
                    int(member.id),
                    int(target_group_id),
                    int(account_id),
                    entity,
                    int(member.telegram_user_id),
                )
                last_status=str(getattr(result,"status","UNKNOWN") or "UNKNOWN").upper()
                last_code=getattr(result,"error_code",None)
                last_message=getattr(result,"error_message",None)
                if self.targets:
                    self.targets.upsert_state(
                        int(member.id),
                        int(target_group_id),
                        last_status,
                        account_id=int(account_id),
                        error_code=last_code,
                        error_message=last_message,
                        checked_at=getattr(result,"checked_at",None),
                    )
                if last_status in {"ALREADY_MEMBER","MEMBER","JOINED"}:
                    return True,last_status,last_code,last_message
                if last_status in {"PRIVACY_RESTRICTED","ACCESS_DENIED","INVALID","ERROR"}:
                    break
            except Exception as exc:
                last_status="UNKNOWN"
                last_code=type(exc).__name__
                last_message=str(exc) or "Membership confirmation failed."
        return False,last_status,last_code,last_message

    async def invite_members_to_target(self,target_group_id:int,account_id:int,member_ids:list[int],*,progress_callback=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):
                return self._blocked_invitation_result({"counts":{"selected":len(set(member_ids))},"blocking_reasons":["Direct member invitation requires SP Telegram Ultimate."]},"LICENSE_LOCKED")
        # Final asynchronous permission/connection validation immediately before
        # the write. A stale UI preflight can therefore never authorize a write.
        pre=await self.invitation_preflight(target_group_id,account_id,member_ids)
        if not bool(pre.get("can_start", pre.get("start_allowed", False))):
            reason=(pre.get("blocking_reasons") or ["Invitation preflight blocked the operation."])[0]
            code="TARGET_PERMISSION_DENIED" if not bool(pre.get("can_invite")) else "PREFLIGHT_BLOCKED"
            return self._blocked_invitation_result(pre,code,reason)
        try:
            group,mapping,entity=await self._prepare_group_account(target_group_id,account_id,target_required=True)
        except Exception as exc:
            return self._blocked_invitation_result(pre,"TARGET_ACCESS_DENIED",str(exc) or "Target access could not be validated.")
        if not bool(getattr(mapping,"can_invite",0)):
            return self._blocked_invitation_result(pre,"TARGET_PERMISSION_DENIED","This account does not currently have permission to invite users to the selected target.")
        counts=pre.get("counts") or {};items=pre.get("items") or []
        job=self.jobs.create_job("TARGET_MEMBER_INVITE",status="RUNNING",account_id=account_id,group_id=target_group_id,total_items=int(counts.get("selected",0)),started_at=utc_now_iso()) if self.jobs else None
        key=f"invite_{job.id if job else uuid.uuid4().hex}"; self._active_invitation_jobs[str(job.id if job else key)]=key
        if progress_callback:
            progress_callback({"job_id": job.id if job else None, "status": "RUNNING", "processed": 0,
                               "total": int(counts.get("ready", 0) or 0), "successful": 0, "skipped": 0,
                               "failed": 0, "current": "—"})
        if self.target_invitation:self.target_invitation.create_control(key)
        processed=success=skipped=failed=0;results=[];safety_stop_code=None;safety_stop_message=None
        try:
            for item in items:
                if self.target_invitation and not await self.target_invitation.checkpoint(key):break
                m=item["member"];reason=item.get("reason")
                if not reason and self.account_safety_service is not None:
                    decision=self.account_safety_service.reserve(account_id,"INVITE")
                    if not decision.allowed and decision.code=="MIN_INTERVAL" and decision.wait_seconds>0:
                        if progress_callback:progress_callback({"job_id":job.id if job else None,"status":"WAITING","processed":processed,"total":int(counts.get("selected",0)),"successful":success,"skipped":skipped,"failed":failed,"current":f"Smart spacing: {decision.wait_seconds}s"})
                        await asyncio.sleep(decision.wait_seconds)
                        decision=self.account_safety_service.reserve(account_id,"INVITE")
                    if not decision.allowed:
                        safety_stop_code=decision.code;safety_stop_message=decision.message
                        if self.jobs and job:self.jobs.update_status(job.id,"PAUSED",error=decision.message)
                        if self.target_invitation:self.target_invitation.pause(key)
                        results.append({"member_id":m.id,"telegram_user_id":m.telegram_user_id,"username":m.username,"display_name":m.display_name,"first_name":m.first_name,"last_name":m.last_name,"status":"SAFETY_BLOCKED","error_code":decision.code,"message":decision.message})
                        break
                processed+=1
                action=self.target_actions.create_action(m.id,target_group_id,account_id,"DIRECT_INVITE",status="VALIDATING",job_id=job.id if job else None) if self.target_actions else None
                action_id=int(action["id"]) if action is not None else None
                if reason:
                    normalized={
                        "UNKNOWN":"SKIPPED","TARGET_STATUS_UNKNOWN":"SKIPPED","CONSENT_NOT_APPROVED":"CONSENT_NOT_APPROVED",
                        "USER_DEACTIVATED":"USER_DEACTIVATED",
                    }.get(reason,reason if reason in {"ALREADY_MEMBER","BLACKLISTED","DO_NOT_CONTACT","DELETED"} else "SKIPPED")
                    skipped+=1
                    error_code = "TARGET_STATUS_UNKNOWN" if reason == "UNKNOWN" else reason
                    if self.target_actions and action_id:self.target_actions.finish_action(action_id,normalized,error_code=error_code,error_message="Excluded by local invitation policy.")
                    results.append({"member_id":m.id,"telegram_user_id":m.telegram_user_id,"username":m.username,"display_name":m.display_name,"first_name":m.first_name,"last_name":m.last_name,"status":normalized,"error_code":error_code,"message":"Excluded by local invitation policy."})
                else:
                    if self.target_actions and action_id:self.target_actions.update_fields(action_id,{"status":"INVITING","updated_at":utc_now_iso()})
                    attempt=await self.target_invitation.invite_member(account_id,entity,m.telegram_user_id,m.username) if self.target_invitation else None
                    status=str(getattr(attempt,"status","FAILED") or "FAILED");code=getattr(attempt,"error_code",None);message=getattr(attempt,"message",None)
                    if status=="SUCCESS":
                        confirmed,verify_status,verify_code,verify_message=await self._confirm_invite_applied(
                            m,target_group_id,account_id,entity
                        )
                        if confirmed:
                            success+=1
                            status="SUCCESS"
                            code=None
                            message="Added and confirmed in the destination group."
                        else:
                            failed+=1
                            if verify_status=="NOT_MEMBER":
                                status="INVITE_NOT_CONFIRMED"
                                code="INVITE_NOT_CONFIRMED"
                                message=(
                                    "Telegram accepted the invite request, but the member was still "
                                    "not present in the destination after verification."
                                )
                                self.targets.upsert_state(
                                    m.id,target_group_id,"NOT_MEMBER",
                                    account_id=account_id,
                                    error_code=code,
                                    error_message=message,
                                )
                            else:
                                status="INVITE_UNVERIFIED"
                                code=verify_code or "INVITE_UNVERIFIED"
                                message=verify_message or (
                                    "The invite request returned without an error, but SP Telegram "
                                    "could not confirm that the member joined the destination."
                                )
                                self.targets.upsert_state(
                                    m.id,target_group_id,"UNKNOWN",
                                    account_id=account_id,
                                    error_code=code,
                                    error_message=message,
                                )
                    elif status=="ALREADY_MEMBER":
                        skipped+=1;self.targets.upsert_state(m.id,target_group_id,"ALREADY_MEMBER",account_id=account_id)
                    elif status=="PRIVACY_RESTRICTED":
                        failed+=1;self.targets.upsert_state(m.id,target_group_id,"PRIVACY_RESTRICTED",account_id=account_id,error_code=code,error_message=message)
                    elif status=="USER_DEACTIVATED":
                        skipped+=1;self.targets.upsert_state(m.id,target_group_id,"DELETED",account_id=account_id,error_code=code,error_message=message)
                    elif status=="FLOOD_WAIT":
                        failed+=1
                        if self.account_service:self.account_service.record_confirmed_flood_wait(account_id,getattr(attempt,"wait_seconds",None),message or "Telegram requested a cooldown.")
                        if self.jobs and job:self.jobs.update_status(job.id,"PAUSED",error=message or "Telegram requested a cooldown.")
                        self._alert("WARNING","FLOOD_WAIT","Target invitation paused",message or "Telegram requested a cooldown.",account_id=account_id,group_id=target_group_id)
                        if self.target_invitation:self.target_invitation.pause(key)
                    elif status=="TARGET_PERMISSION_DENIED":
                        failed+=1;status="TARGET_PERMISSION_DENIED";self.targets.upsert_state(m.id,target_group_id,"FAILED",account_id=account_id,error_code="TARGET_PERMISSION_DENIED",error_message=message)
                    else:
                        failed+=1;self.targets.upsert_state(m.id,target_group_id,"FAILED",account_id=account_id,error_code=code,error_message=message)
                    if self.account_safety_service is not None:
                        if status in {"SUCCESS","ALREADY_MEMBER"}:self.account_safety_service.record_success(account_id,"INVITE")
                        elif str(code or status).upper() in {"FLOOD_WAIT","PEER_FLOOD","SPAM_LIMITED","ACCOUNT_RESTRICTED","USER_RESTRICTED"}:
                            self.account_safety_service.record_failure(account_id,"INVITE",code or status,message,wait_seconds=getattr(attempt,"wait_seconds",None))
                    if self.target_actions and action_id:self.target_actions.finish_action(action_id,status,error_code=code,error_message=message)
                    results.append({"member_id":m.id,"telegram_user_id":m.telegram_user_id,"username":m.username,"display_name":m.display_name,"first_name":m.first_name,"last_name":m.last_name,"status":status,"error_code":code,"message":message})
                    if status in {"FLOOD_WAIT","TARGET_PERMISSION_DENIED"}:break
                if self.jobs and job:
                    pct=int(processed*100/max(1,int(counts.get("selected",0))));self.jobs.update_fields(job.id,{"progress":pct,"success_count":success,"skipped_count":skipped,"failed_count":failed,"updated_at":utc_now_iso()})
                if progress_callback:progress_callback({"job_id":job.id if job else None,"processed":processed,"total":int(counts.get("selected",0)),"successful":success,"skipped":skipped,"failed":failed,"current":m.username or m.display_name or str(m.telegram_user_id)})
            status="COMPLETED"
            if self.jobs and job:
                current=self.jobs.get_by_id(job.id)
                if current and current.status in {"STOPPED","CANCELLED"}:status=current.status
                elif current and current.status=="PAUSED":status="PAUSED"
                else:status="PARTIAL_SUCCESS" if failed else "COMPLETED"
                if status not in {"PAUSED","STOPPED","CANCELLED"}:self.jobs.update_status(job.id,status)
            status_counts={}
            for row in results:
                key=str(row.get("status") or "UNKNOWN").upper();status_counts[key]=status_counts.get(key,0)+1
            return {"job_id":job.id if job else None,"status":status,"error_code":safety_stop_code,"message":safety_stop_message,"selected":int(counts.get("selected",0)),"processed":processed,"successful":success,"skipped":skipped,"failed":failed,
                    "already_member":status_counts.get("ALREADY_MEMBER",0),"privacy_restricted":status_counts.get("PRIVACY_RESTRICTED",0),
                    "results":results,"preflight":pre}
        finally:
            if self.target_invitation:self.target_invitation.cleanup(key)
            self._active_invitation_jobs.pop(str(job.id if job else key),None)

    async def invite_members_to_target_batch(self,target_group_id:int,account_ids:list[int],member_ids:list[int],*,progress_callback=None):
        """Run fixed, explicitly selected account assignments without reassignment."""
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):
                return self._blocked_invitation_result({"counts":{"selected":len(set(member_ids))},"blocking_reasons":["Direct member invitation requires SP Telegram Ultimate."]},"LICENSE_LOCKED")
        pre=await self.invitation_batch_preflight(target_group_id,account_ids,member_ids)
        if not bool(pre.get("can_start")):
            reason=(pre.get("blocking_reasons") or ["Invitation batch preflight did not allow this operation."])[0]
            blocked=self._blocked_invitation_result(pre,"BATCH_PREFLIGHT_BLOCKED",reason);blocked["batch_preflight"]=pre;return blocked
        total=sum(int(row.get("count",0)) for row in pre.get("assignments") or [])
        aggregate={"processed":0,"successful":0,"skipped":0,"failed":0};results=[];account_results=[];job_ids=[];stop_status=None;stop_message=None
        if progress_callback:progress_callback({"job_id":None,"status":"RUNNING","processed":0,"total":total,"successful":0,"skipped":0,"failed":0,"current":"Preparing fixed account assignments"})
        for index,assignment in enumerate(pre.get("assignments") or [],start=1):
            account_id=int(assignment["account_id"]);offset=aggregate["processed"]
            def account_progress(payload,*,aid=account_id,number=index,base=offset):
                payload=payload or {};current_job=payload.get("job_id")
                if current_job and current_job not in job_ids:job_ids.append(int(current_job))
                if progress_callback:progress_callback({
                    "job_id":current_job,"status":payload.get("status","RUNNING"),"account_id":aid,"account_index":number,
                    "account_count":len(pre.get("assignments") or []),"processed":base+int(payload.get("processed",0)),"total":total,
                    "successful":aggregate["successful"]+int(payload.get("successful",0)),"skipped":aggregate["skipped"]+int(payload.get("skipped",0)),
                    "failed":aggregate["failed"]+int(payload.get("failed",0)),"current":payload.get("current") or "—",
                })
            result=await self.invite_members_to_target(target_group_id,account_id,list(assignment["member_ids"]),progress_callback=account_progress)
            account_results.append({"account_id":account_id,**result});results.extend(result.get("results") or [])
            for key in aggregate:aggregate[key]+=int(result.get(key,0) or 0)
            job_id=result.get("job_id")
            if job_id and int(job_id) not in job_ids:job_ids.append(int(job_id))
            result_status=str(result.get("status") or "UNKNOWN").upper()
            terminal_code=str(result.get("error_code") or "").upper()
            item_codes={str(item.get("status") or item.get("error_code") or "").upper() for item in result.get("results") or []}
            if result_status in {"PAUSED","STOPPED","CANCELLED","BLOCKED"} or terminal_code in {"FLOOD_WAIT","TARGET_PERMISSION_DENIED"} or item_codes.intersection({"FLOOD_WAIT","TARGET_PERMISSION_DENIED"}):
                stop_status=result_status if result_status in {"PAUSED","STOPPED","CANCELLED","BLOCKED"} else "BLOCKED"
                stop_message=result.get("message") or "The batch stopped on the current account. Unfinished members were not reassigned."
                break
        status=stop_status or ("PARTIAL_SUCCESS" if aggregate["failed"] else "COMPLETED")
        status_counts={}
        for row in results:
            key=str(row.get("status") or "UNKNOWN").upper();status_counts[key]=status_counts.get(key,0)+1
        return {
            "job_id":job_ids[-1] if job_ids else None,"job_ids":job_ids,"status":status,"message":stop_message,
            "selected":total,**aggregate,"unprocessed":max(0,total-aggregate["processed"]),"results":results,
            "already_member":status_counts.get("ALREADY_MEMBER",0),"privacy_restricted":status_counts.get("PRIVACY_RESTRICTED",0),
            "account_results":account_results,"selected_account_count":len(pre.get("account_ids") or []),"batch_preflight":pre,"preflight":pre,
        }

    # ------------------------------------------------------------------
    # Mass Add to Target — auto-fill a target group from source groups,
    # round-robin across accounts, running 1..4 account jobs in parallel.
    # ------------------------------------------------------------------
    def used_account_ids_for_target(self, target_group_id:int) -> set[int]:
        """Accounts that have already run a successful TARGET_MEMBER_INVITE job
        for this target group. Used by the Mass Add dialog to let the user skip
        accounts that already invited to the same target."""
        if not self.jobs:
            return set()
        rows = self.jobs.db.fetch_all(
            "SELECT DISTINCT account_id FROM jobs "
            "WHERE job_type='TARGET_MEMBER_INVITE' AND group_id=? AND account_id IS NOT NULL AND success_count>0",
            (int(target_group_id),),
        )
        return {int(r["account_id"]) for r in rows if r["account_id"] is not None}

    def mass_add_account_options(self, target_group_id:int):
        group = self.groups.get_by_id(int(target_group_id)) if self.groups else None
        if not group or not self.accounts:
            return []

        rows = []
        hard_access = {"BANNED", "ACCESS_DENIED", "NO_ACCESS", "UNAVAILABLE"}
        blocking_health = {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}
        harmless_restrictions = {"", "NONE", "NONE_KNOWN", "UNKNOWN"}
        public_target = bool(str(getattr(group, "username", "") or "").strip())

        for account in self.accounts.get_operations_enabled_accounts():
            account_id = int(getattr(account, "id", 0) or 0)
            if not account_id:
                continue

            mapping = self.group_accounts.get_mapping(int(target_group_id), account_id) if self.group_accounts else None
            access = str(getattr(mapping, "access_state", "NOT_JOINED") or "NOT_JOINED").upper() if mapping else "NOT_JOINED"
            health = str(getattr(account, "health_status", "UNKNOWN") or "UNKNOWN").upper()
            restriction = str(getattr(account, "restriction_type", "") or "").upper()

            authorized = bool(
                getattr(account, "is_enabled", 0)
                and getattr(account, "enabled_for_operations", 0)
                and str(getattr(account, "authorization_status", "UNKNOWN") or "UNKNOWN").upper() == "AUTHORIZED"
                and str(getattr(account, "session_path", "") or "").strip()
            )
            can_invite_now = bool(
                mapping
                and bool(getattr(mapping, "can_invite", 0))
                and access not in hard_access | {"NOT_JOINED", "LEFT"}
            )

            auto_join = bool(
                public_target
                and access not in hard_access
                and not can_invite_now
            )

            selectable = bool(
                authorized
                and health not in blocking_health
                and restriction in harmless_restrictions
                and (can_invite_now or auto_join)
            )

            name = str(
                getattr(account, "first_name", "")
                or getattr(account, "username", "")
                or f"Account {account_id}"
            )
            username = str(getattr(account, "username", "") or "").strip() or None
            rows.append({
                "account_id": account_id,
                "account": account,
                "mapping": mapping,
                "name": name,
                "username": username,
                "health": health,
                "restriction": restriction or "NONE",
                "access": access,
                "authorized": authorized,
                "connected": str(getattr(account, "connection_status", "OFFLINE") or "OFFLINE").upper() == "CONNECTED",
                "can_invite_now": can_invite_now,
                "auto_join": auto_join,
                "selectable": selectable,
            })
        return rows


    def _mass_candidates(self, target_group_id:int, source_group_ids:list[int], target_count:int):
        target_group_id=int(target_group_id)
        target_count=max(1,int(target_count or 0))
        seen: dict[int, Member] = {}
        for source_group_id in self._explicit_ids(source_group_ids):
            members=self.repository.get_target_preparation_members(
                target_group_id,
                source_group_id=int(source_group_id),
                exclude_existing=True,
                exclude_blacklist=True,
                exclude_do_not_contact=True,
                exclude_deleted=True,
                exclude_bots=True,
                limit=max(target_count*3,target_count),
            )
            for member in members:
                member_id=int(getattr(member,"id",0) or 0)
                if not member_id or member_id in seen:
                    continue
                eligibility=str(getattr(member,"eligibility_status","UNKNOWN") or "UNKNOWN").upper()
                consent=str(getattr(member,"consent_status","UNKNOWN") or "UNKNOWN").upper()
                if eligibility!="ELIGIBLE" or consent!="APPROVED":
                    continue
                if bool(getattr(member,"is_deleted",0)) or bool(getattr(member,"is_bot",0)):
                    continue
                if self.exclusions:
                    if self.exclusions.is_global_blacklisted(member_id):
                        continue
                    if self.exclusions.is_do_not_contact(member_id):
                        continue
                seen[member_id]=member
                if len(seen)>=target_count:
                    break
            if len(seen)>=target_count:
                break
        return list(seen.values())

    def smart_transfer_member_ids(self, source_group_id:int, target_group_id:int, count:int=20):
        """Return deterministic Source members for the simple drag/drop flow."""
        limit=max(1,min(int(count or 20),MAX_INVITATION_BATCH_MEMBERS))
        rows=self._mass_candidates(int(target_group_id),[int(source_group_id)],limit)
        return [int(row.id) for row in rows if getattr(row,"id",None)][:limit]

    def mass_target_add_preview(self, target_group_id:int, target_count:int, source_group_ids:list[int], account_ids:list[int]):
        """Build a safe Mass Add plan, including provisional public Auto Join accounts."""
        target_group_id = int(target_group_id)
        target_count = max(1, min(int(target_count or 0), MASS_ADD_MAX_TARGET))
        source_group_ids = self._explicit_ids(source_group_ids)
        account_ids = self._explicit_ids(account_ids)
        blockers, warnings = [], []
        def add(values, message):
            if message and message not in values:
                values.append(message)
        if not source_group_ids:
            add(blockers, "Select at least one Source Group to pull members from.")
        if not account_ids:
            add(blockers, "Select at least one authorized account.")
        if len(account_ids) > MASS_ADD_MAX_ACCOUNTS:
            add(blockers, f"Select no more than {MASS_ADD_MAX_ACCOUNTS} accounts.")

        candidates = self._mass_candidates(target_group_id, source_group_ids, target_count) if source_group_ids else []
        candidate_ids = [int(m.id) for m in candidates if m.id]
        shortage = max(0, target_count - len(candidate_ids))
        if shortage:
            add(warnings, f"Only {len(candidate_ids):,} candidate(s) are available — {shortage:,} short of the {target_count:,} target. Add/sync more Source Groups first.")

        options = {int(row["account_id"]): row for row in self.mass_add_account_options(target_group_id)}
        group = self.groups.get_by_id(target_group_id) if self.groups else None
        target_fragments = (
            "not mapped to this target group",
            "does not currently have target access",
            "does not currently have permission to invite",
        )
        account_rows = []
        for account_id in account_ids:
            option = options.get(int(account_id))
            if not option:
                add(blockers, f"Account {account_id}: disabled, unauthorized, or unavailable for operations.")
                continue
            pre = self.invitation_precheck(target_group_id, account_id, candidate_ids) if candidate_ids else {}
            name = option["name"] + (f"  •  @{option['username']}" if option.get("username") else "")
            auto_join = bool(option.get("auto_join"))
            raw_blockers = list(pre.get("blocking_reasons") or [])
            row_blockers = [
                msg for msg in raw_blockers
                if not (auto_join and any(fragment in str(msg).lower() for fragment in target_fragments))
            ]
            smart_limits = bool(pre.get("smart_limits_enabled", False))
            remaining = max(0, int(pre.get("invite_remaining_today", 0) or 0)) if smart_limits else MASS_ADD_PER_ACCOUNT_CAP
            capacity = min(MASS_ADD_PER_ACCOUNT_CAP, remaining)
            if auto_join:
                ready = bool(
                    option.get("selectable")
                    and int(pre.get("ready_count", 0) or 0) > 0
                    and bool(pre.get("restriction_allows_operation", True))
                    and bool(pre.get("safety_allows_invite", True))
                    and not row_blockers
                )
                target_name = f"@{getattr(group, 'username', '')}" if group and getattr(group, "username", None) else "the target"
                add(warnings, f"{name}: Auto Join {target_name}; invite permission will be checked live after joining.")
            else:
                ready = bool(pre.get("can_start", pre.get("start_allowed", False)))
            for msg in row_blockers:
                add(blockers, f"{name}: {msg}")
            account_rows.append({
                "account_id": account_id,
                "account": pre.get("account") or option.get("account"),
                "mapping": pre.get("mapping") or option.get("mapping"),
                "name": name,
                "authorized": bool(pre.get("account_authorized", option.get("authorized"))),
                "connected": bool(pre.get("account_connected", option.get("connected"))),
                "health": str(pre.get("account_health") or option.get("health") or "UNKNOWN"),
                "target_access": str(option.get("access") or "UNKNOWN"),
                "role": str(pre.get("target_role") or ("AUTO_JOIN" if auto_join else "UNKNOWN")),
                "can_invite": bool(pre.get("can_invite")) if not auto_join else False,
                "auto_join": auto_join,
                "restriction": pre.get("restriction_status") or option.get("restriction"),
                "ready": ready,
                "blocking_reasons": row_blockers,
                "safety_state": str(pre.get("safety_state") or "NORMAL"),
                "smart_limits": smart_limits,
                "invite_used_today": int(pre.get("invite_used_today", 0) or 0),
                "invite_daily_limit": int(pre.get("invite_daily_limit", 0) or 0),
                "invite_remaining_today": remaining,
                "batch_capacity": capacity,
                "assigned_member_ids": [],
                "assigned_count": 0,
            })
            for msg in pre.get("warnings") or []:
                add(warnings, f"{name}: {msg}")

        total_capacity = sum(row["batch_capacity"] for row in account_rows if row["ready"])
        cursor = 0
        assigned_total = 0
        for member_id in candidate_ids:
            assigned = False
            for offset in range(len(account_rows)):
                index = (cursor + offset) % len(account_rows) if account_rows else 0
                row = account_rows[index] if account_rows else None
                if row and row["ready"] and len(row["assigned_member_ids"]) < row["batch_capacity"]:
                    row["assigned_member_ids"].append(member_id)
                    cursor = (index + 1) % len(account_rows)
                    assigned_total += 1
                    assigned = True
                    break
            if not assigned:
                break
        assignments = []
        for row in account_rows:
            row["assigned_count"] = len(row["assigned_member_ids"])
            if row["assigned_count"]:
                assignments.append({
                    "account_id": row["account_id"],
                    "member_ids": row["assigned_member_ids"],
                    "count": row["assigned_count"],
                    "daily_remaining": row["invite_remaining_today"],
                    "auto_join": bool(row.get("auto_join")),
                })
        can_start = bool(assignments and not blockers)
        return {
            "target_group_id": target_group_id, "target_count": target_count,
            "source_group_ids": source_group_ids, "account_ids": account_ids,
            "candidate_count": len(candidate_ids), "candidate_ids": candidate_ids,
            "shortage": shortage, "capacity": total_capacity, "assigned_total": assigned_total,
            "accounts": account_rows, "assignments": assignments,
            "blocking_reasons": blockers, "warnings": warnings,
            "can_start": can_start, "start_allowed": can_start,
            "limits": {"max_accounts": MASS_ADD_MAX_ACCOUNTS, "max_parallel": MASS_ADD_MAX_PARALLEL, "max_target": MASS_ADD_MAX_TARGET, "per_account_cap": MASS_ADD_PER_ACCOUNT_CAP},
        }

    async def _ensure_target_joined(self, account_id:int, group, mapping, client=None) -> bool:
        username = str(getattr(group, "username", "") or "").strip()
        if not username:
            return False

        state = (
            str(getattr(mapping, "access_state", "NOT_JOINED") or "NOT_JOINED").upper()
            if mapping else "NOT_JOINED"
        )
        if state in {"BANNED", "ACCESS_DENIED", "NO_ACCESS", "UNAVAILABLE"}:
            return False

        if mapping is not None and bool(getattr(mapping, "can_invite", 0)):
            return True

        try:
            group_service = getattr(self.invitation_preflight_service, "group_service", None)
            if group_service is not None and hasattr(group_service, "_ensure_connected"):
                await group_service._ensure_connected(int(account_id))

            if client is None and self.client_manager is not None:
                client = await self.client_manager.get_client(int(account_id))
            if client is None:
                return False

            entity = await client.get_entity(username)

            try:
                from telethon.tl.functions.channels import JoinChannelRequest
                await client(JoinChannelRequest(channel=entity))
            except Exception as exc:
                name = type(exc).__name__.lower()
                message = str(exc or "").lower()
                already = (
                    "useralreadyparticipant" in name
                    or "already participant" in message
                    or "already a participant" in message
                    or "already joined" in message
                )
                if not already:
                    return False

            if self.group_accounts:
                current = self.group_accounts.get_mapping(int(group.id), int(account_id))
                if current is None:
                    current = GroupAccount(
                        group_id=int(group.id),
                        account_id=int(account_id),
                        role="MEMBER",
                        access_state="PUBLIC_ACCESSIBLE",
                        can_view=1,
                        joined_at=utc_now_iso(),
                    )
                    self.group_accounts.upsert_mapping(current)
                else:
                    try:
                        self.group_accounts.update_access_state(
                            int(group.id), int(account_id), "PUBLIC_ACCESSIBLE"
                        )
                    except Exception:
                        pass

            try:
                group_service = getattr(self.invitation_preflight_service, "group_service", None)
                if group_service is not None:
                    await group_service.refresh_permissions(int(group.id), int(account_id))
            except Exception:
                pass

            return True
        except Exception:
            return False


    async def mass_add_members_to_target(self,target_group_id:int,target_count:int,source_group_ids:list[int],account_ids:list[int],parallel_jobs:int=1,*,progress_callback=None):
        """Auto-fill a target group from source groups using parallel accounts.

        The plan is computed locally (candidates + round-robin assignments that
        respect each account's daily safety limit), accounts that are not yet
        members of the target are joined first, then the account jobs run in
        parallel (1..4 at a time). The final report includes whether the target
        count was reached and a shortage recommendation when it was not.
        """
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            if not self.feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE):
                return {"status":"BLOCKED","error_code":"LICENSE_LOCKED","message":"Direct member invitation requires SP Telegram Ultimate.","selected":0,"processed":0,"successful":0,"skipped":0,"failed":0,"results":[]}
        preview=self.mass_target_add_preview(target_group_id,target_count,source_group_ids,account_ids)
        if not bool(preview.get("can_start")):
            reason=(preview.get("blocking_reasons") or ["Mass add preflight did not allow this operation."])[0]
            return {"status":"BLOCKED","error_code":"MASS_PREFLIGHT_BLOCKED","message":reason,"selected":0,"processed":0,"successful":0,"skipped":0,"failed":0,"results":[],"preview":preview}

        initial_preview=preview
        group=self.groups.get_by_id(int(target_group_id)) if self.groups else None
        joined_accounts=set()
        for row in preview.get("accounts") or []:
            if not bool(row.get("auto_join")) or int(row.get("assigned_count",0) or 0)<=0:
                continue
            account_id=int(row["account_id"])
            mapping=self.group_accounts.get_mapping(int(target_group_id),account_id) if self.group_accounts else None
            if group is None or not await self._ensure_target_joined(account_id,group,mapping,None):
                message=f"{row.get('name') or f'Account {account_id}'} could not auto-join the public target or refresh invitation permission."
                return {"status":"BLOCKED","error_code":"TARGET_AUTO_JOIN_FAILED","message":message,"selected":0,"processed":0,"successful":0,"skipped":0,"failed":0,"results":[],"preview":preview}
            joined_accounts.add(account_id)

        # Recalculate after join using live refreshed target permissions.
        if joined_accounts:
            preview=self.mass_target_add_preview(target_group_id,target_count,source_group_ids,account_ids)
            if not bool(preview.get("can_start")):
                reason=(preview.get("blocking_reasons") or ["An account joined the target but does not have permission to invite users."])[0]
                return {"status":"BLOCKED","error_code":"TARGET_PERMISSION_DENIED","message":reason,"selected":0,"processed":0,"successful":0,"skipped":0,"failed":0,"results":[],"preview":preview,"initial_preview":initial_preview,"joined_accounts":sorted(joined_accounts)}

        assignments=preview.get("assignments") or []
        total=sum(int(row.get("count",0)) for row in assignments)
        parallel_jobs=max(1,min(int(parallel_jobs or 1),MASS_ADD_MAX_PARALLEL))
        aggregate={"processed":0,"successful":0,"skipped":0,"failed":0};results=[];account_results=[];job_ids=[];stop_status=None;stop_message=None
        if progress_callback:
            progress_callback({"status":"RUNNING","processed":0,"total":total,"successful":0,"skipped":0,"failed":0,"current":"Preparing parallel account jobs","target_count":int(target_count),"shortage":int(preview.get("shortage",0))})
        semaphore=asyncio.Semaphore(parallel_jobs)
        async def run_assignment(assignment,index):
            account_id=int(assignment["account_id"]);base=aggregate["processed"]
            def account_progress(payload,*,aid=account_id,number=index):
                payload=payload or {};current_job=payload.get("job_id")
                if current_job and current_job not in job_ids:job_ids.append(int(current_job))
                if progress_callback:
                    progress_callback({
                        "job_id":current_job,"status":payload.get("status","RUNNING"),"account_id":aid,
                        "account_index":number,"account_count":len(assignments),
                        "processed":base+int(payload.get("processed",0)),"total":total,
                        "successful":aggregate["successful"]+int(payload.get("successful",0)),
                        "skipped":aggregate["skipped"]+int(payload.get("skipped",0)),
                        "failed":aggregate["failed"]+int(payload.get("failed",0)),
                        "current":payload.get("current") or "—",
                        "target_count":int(target_count),"shortage":int(preview.get("shortage",0)),
                    })
            async with semaphore:
                return account_id,await self.invite_members_to_target(int(target_group_id),account_id,list(assignment["member_ids"]),progress_callback=account_progress)
        tasks=[asyncio.ensure_future(run_assignment(assignment,index)) for index,assignment in enumerate(assignments,start=1)]
        try:
            for future in asyncio.as_completed(tasks):
                account_id,result=await future
                account_results.append({"account_id":account_id,**result});results.extend(result.get("results") or [])
                for key in aggregate:aggregate[key]+=int(result.get(key,0) or 0)
                job_id=result.get("job_id")
                if job_id and int(job_id) not in job_ids:job_ids.append(int(job_id))
                result_status=str(result.get("status") or "UNKNOWN").upper()
                terminal_code=str(result.get("error_code") or "").upper()
                item_codes={str(item.get("status") or item.get("error_code") or "").upper() for item in result.get("results") or []}
                if result_status in {"PAUSED","STOPPED","CANCELLED","BLOCKED"} or terminal_code in {"FLOOD_WAIT","TARGET_PERMISSION_DENIED"} or item_codes.intersection({"FLOOD_WAIT","TARGET_PERMISSION_DENIED"}):
                    stop_status=result_status if result_status in {"PAUSED","STOPPED","CANCELLED","BLOCKED"} else "BLOCKED"
                    stop_message=result.get("message") or "A parallel account job stopped. Remaining assignments were not processed."
                    for task in tasks:
                        if not task.done():task.cancel()
                    break
        finally:
            await asyncio.gather(*tasks,return_exceptions=True)
        status=stop_status or ("PARTIAL_SUCCESS" if aggregate["failed"] else "COMPLETED")
        status_counts={}
        for row in results:
            key=str(row.get("status") or "UNKNOWN").upper();status_counts[key]=status_counts.get(key,0)+1
        finished=aggregate["successful"]>=int(target_count)
        return {
            "job_id":job_ids[-1] if job_ids else None,"job_ids":job_ids,"status":status,"message":stop_message,
            "selected":total,**aggregate,"unprocessed":max(0,total-aggregate["processed"]),"results":results,
            "already_member":status_counts.get("ALREADY_MEMBER",0),"privacy_restricted":status_counts.get("PRIVACY_RESTRICTED",0),
            "account_results":account_results,"selected_account_count":len(assignments),
            "target_count":int(target_count),"shortage":int(preview.get("shortage",0)),
            "finished":finished,"joined_accounts":sorted(joined_accounts),"preview":preview,
        }

    async def pause_mass_target_add(self,job_ids:list[int]):
        for job_id in job_ids:
            await self.pause_target_invitation(int(job_id))
        return True
    async def resume_mass_target_add(self,job_ids:list[int]):
        for job_id in job_ids:
            await self.resume_target_invitation(int(job_id))
        return True
    async def stop_mass_target_add(self,job_ids:list[int]):
        for job_id in job_ids:
            await self.stop_target_invitation(int(job_id))
        return True

    async def pause_target_invitation(self,job_id:int):
        key=self._active_invitation_jobs.get(str(job_id))
        if key and self.target_invitation:self.target_invitation.pause(key)
        if self.jobs:self.jobs.update_status(int(job_id),"PAUSED")
        return True
    async def resume_target_invitation(self,job_id:int):
        key=self._active_invitation_jobs.get(str(job_id))
        if key and self.target_invitation:self.target_invitation.resume(key)
        if self.jobs:self.jobs.update_status(int(job_id),"RUNNING")
        return True
    async def stop_target_invitation(self,job_id:int):
        key=self._active_invitation_jobs.get(str(job_id))
        if key and self.target_invitation:self.target_invitation.stop(key)
        if self.jobs:self.jobs.update_status(int(job_id),"STOPPED")
        return True

    def invitation_history(self,member_id:int,limit:int=200):
        return self.target_actions.get_for_member(member_id,limit) if self.target_actions else []

    def target_member_rows(self,target_group_id:int,limit:int=500):
        return self.targets.list_target_member_rows(target_group_id,limit) if self.targets else []

    def cleanup_selected(self,member_ids):return self.cleanup_service.clear_selected(member_ids) if self.cleanup_service else None
    def cleanup_filtered(self,**filters):return self.cleanup_service.clear_filtered(**filters) if self.cleanup_service else None
    def cleanup_by_source(self,group_id,remove_member_if_only_source=False):return self.cleanup_service.clear_by_source(group_id,remove_member_if_only_source=remove_member_if_only_source) if self.cleanup_service else None
    def cleanup_orphaned(self):return self.cleanup_service.clear_orphaned() if self.cleanup_service else None
    def cleanup_all(self,**options):return self.cleanup_service.clear_entire(**options) if self.cleanup_service else None
    def cleanup_orphan_count(self):return self.cleanup_service.orphan_count() if self.cleanup_service else 0

    def target_preparation(self,target_group_id:int,**filters):
        group=self.groups.get_by_id(target_group_id) if self.groups else None
        if not group or not (bool(getattr(group,"is_target",0)) or bool(getattr(group,"is_managed",0))):
            raise ValueError("Select a saved Target Group first.")
        mappings=self.group_accounts.get_group_accounts(target_group_id) if self.group_accounts else []
        primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
        members=self.repository.get_target_preparation_members(target_group_id,limit=250,**filters)
        summary=self.repository.target_preparation_summary(target_group_id,**filters)
        return {"group":group,"mapping":primary,"summary":summary,"members":members}

    def export_target_preparation(self,path:str|Path,target_group_id:int,**filters):
        # Stream bounded SQL pages instead of materializing a potentially very large
        # Member Pool in Python memory. The repository keeps all target/source/status
        # filtering in SQL and each page remains small.
        count=0
        offset=0
        batch_size=1000
        with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.writer(handle)
            writer.writerow(["telegram_user_id","username","display_name","eligibility","consent","target_status","sources","tags"])
            while True:
                members=self.repository.get_target_preparation_members(
                    target_group_id,limit=batch_size,offset=offset,**filters
                )
                if not members:
                    break
                for member in members:
                    writer.writerow([member.telegram_user_id,member.username or "",member.display_name or "",member.eligibility_status,member.consent_status,member.existing_target_state,member.sources,member.tags])
                    count+=1
                if len(members)<batch_size:
                    break
                offset+=len(members)
        self._log("TARGET_PREPARATION_EXPORT",f"Exported {count} locally prepared member records for target group ID {target_group_id}.",group_id=target_group_id)
        return count

    def import_members(self,path:str|Path):return self.import_csv(path)
    def import_csv(self,path:str|Path):
        valid=[];error_rows=[]
        with Path(path).open("r",encoding="utf-8-sig",newline="") as handle:
            for line,row in enumerate(csv.DictReader(handle),start=2):
                try:
                    tid=int(row.get("telegram_user_id") or "")
                    valid.append(Member(telegram_user_id=tid,username=(row.get("username") or "").strip().lstrip("@") or None,first_name=(row.get("first_name") or "").strip() or None,last_name=(row.get("last_name") or "").strip() or None,eligibility_status=(row.get("eligibility_status") or "UNKNOWN").upper().replace(" ","_"),consent_status=(row.get("consent_status") or "UNKNOWN").upper().replace(" ","_"),notes=(row.get("notes") or "").strip() or None))
                except Exception as exc:error_rows.append({"line":line,"error":str(exc)})
        inserted=updated=unchanged=skipped=0
        remaining=self._licensed_member_addition_capacity()
        with self.repository.db.transaction():
            for item in valid:
                existing=self.repository.get_by_telegram_id(item.telegram_user_id)
                if existing:
                    changed=False;values={}
                    for field in ("username","first_name","last_name"):
                        val=getattr(item,field)
                        if val is not None and getattr(existing,field)!=val:values[field]=val;changed=True
                    if item.eligibility_status!="UNKNOWN":values["eligibility_status"]=item.eligibility_status
                    if item.consent_status!="UNKNOWN":values["consent_status"]=item.consent_status
                    if item.notes:values["notes"]=item.notes
                    if values:self.repository.update_fields(existing.id,{**values,"updated_at":utc_now_iso()});updated+=1 if changed or values else 0
                    else:unchanged+=1
                else:
                    if remaining is not None and remaining<=0:skipped+=1;continue
                    self.repository.create(item);inserted+=1
                    if remaining is not None:remaining-=1
        result={"inserted":inserted,"updated":updated,"unchanged":unchanged,"invalid":len(error_rows),"skipped":skipped,"errors":len(error_rows),"error_rows":error_rows};self._log("MEMBER_IMPORT",f"Member CSV import completed: {inserted} inserted, {updated} updated, {skipped} skipped by plan capacity.");return result
    def export_members(self,path,items):return self.export_csv(path,items)
    def export_csv(self,path:str|Path,items):
        count=0
        with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
            w=csv.writer(handle);w.writerow(["telegram_user_id","username","first_name","last_name","eligibility","consent","sources","tags","first_seen","last_seen"])
            for m in items:
                w.writerow([m.telegram_user_id,m.username or "",m.first_name or "",m.last_name or "",m.eligibility_status,m.consent_status,m.sources,m.tags,m.first_seen_at or "",m.last_seen_at or ""]);count+=1
        self._log("MEMBER_EXPORT",f"Exported {count} member records.");return Path(path)

    def source_stats(self,group_id:int):
        mappings=self.group_accounts.get_group_accounts(group_id) if self.group_accounts else [];primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None);return {"stored":self.sources.count_by_group(group_id,active_only=True) if self.sources else 0,"mapping":primary,"availability":primary.member_list_availability if primary else "UNKNOWN","last_sync":primary.last_member_sync_at if primary else None,"status":primary.member_sync_status if primary else "NEVER_SYNCED"}
    def target_stats(self,group_id:int):
        counts=self.targets.count_by_state(group_id) if self.targets else {};mappings=self.group_accounts.get_group_accounts(group_id) if self.group_accounts else [];primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
        prepared=self.repository.target_preparation_summary(group_id,eligibility="ELIGIBLE",consent="APPROVED",exclude_existing=True,exclude_blacklist=True,exclude_do_not_contact=True,exclude_deleted=True,exclude_bots=True) if self.repository else {}
        return {"existing":counts.get("MEMBER",0)+counts.get("ALREADY_MEMBER",0)+counts.get("JOINED",0),"eligible":int(prepared.get("eligible",0)),"unknown":counts.get("UNKNOWN",0),"not_member":counts.get("NOT_MEMBER",0),"last_sync":getattr(primary,"last_member_sync_at",None) if primary else None,"mapping":primary}
    def statistics(self):
        by=self.repository.count_by_eligibility();return {"total":self.repository.count_all(),"eligible":by.get("ELIGIBLE",0),"unknown":by.get("UNKNOWN",0),"do_not_contact":by.get("DO_NOT_CONTACT",0),"blacklisted":self.exclusions.count("exclusion_type='GLOBAL_BLACKLIST' AND target_group_id IS NULL") if self.exclusions else 0,"bots":self.repository.count_bots(),"deleted":self.repository.count_deleted()}

    async def _prepare_group_account(self,group_id:int,account_id:int,*,source_required=False,target_required=False):
        group=self.groups.get_by_id(group_id) if self.groups else None
        mapping=self.group_accounts.get_mapping(group_id,account_id) if self.group_accounts else None
        account=self.accounts.get_by_id(account_id) if self.accounts else None
        if not group:
            raise ValueError("Group not found.")
        if not account or not bool(getattr(account,"is_enabled",0)):
            raise ValueError("Selected account is unavailable.")
        if str(getattr(account,"authorization_status","UNKNOWN") or "UNKNOWN").upper()!="AUTHORIZED":
            raise ValueError("Selected account requires Telegram login.")
        if not mapping:
            raise ValueError("The selected account is not mapped to this group.")
        access=str(getattr(mapping,"access_state","UNKNOWN") or "UNKNOWN").upper()
        if access in {"ACCESS_DENIED","UNAVAILABLE","NO_ACCESS"}:
            raise ValueError("Selected account does not currently have access to this group.")
        if access in {"NOT_JOINED","LEFT"}:
            raise ValueError("Selected account has not joined this group yet.")
        client=await self.client_manager.get_client(account_id) if self.client_manager else None
        if client is None:
            session_path=str(getattr(account,"session_path","") or "")
            if not session_path:
                raise ValueError("Selected account has no Telegram session.")
            client=await self.client_manager.create_client(account_id,session_path)
        if hasattr(client,"is_connected") and not client.is_connected() and self.client_manager:
            await self.client_manager.connect(account_id)
        if hasattr(client,"is_user_authorized") and not await client.is_user_authorized():
            raise ValueError("Selected account requires Telegram login.")
        username=str(getattr(group,"username","") or "").strip()
        peer=getattr(group,"telegram_id",None)
        entity=None
        last_error=None
        for ref in (username,peer):
            if ref in (None,""):
                continue
            try:
                entity=await client.get_entity(ref)
                break
            except Exception as exc:
                last_error=exc
        if entity is None:
            raise RuntimeError(str(last_error or "Could not resolve the selected Telegram group."))
        return group,mapping,entity

    def _save_batch(self,batch,group_id,account_id,sync_run_id,options,progress):
        prepared=[];telegram_by_id={};remaining=self._licensed_member_addition_capacity()
        for tm in batch:
            existing=self.repository.get_by_telegram_id(tm.telegram_user_id)
            if options.skip_blacklist and existing and self.exclusions and self.exclusions.is_global_blacklisted(existing.id):
                progress.excluded+=1;continue
            if existing is None and remaining is not None and remaining<=0:
                progress.plan_limit_skipped+=1;progress.excluded+=1;continue
            if existing and not options.update_existing_profiles:
                member=Member(telegram_user_id=existing.telegram_user_id,username=existing.username,first_name=existing.first_name,last_name=existing.last_name,display_name=existing.display_name,is_bot=existing.is_bot,is_deleted=existing.is_deleted,is_verified=existing.is_verified,is_scam=existing.is_scam,is_fake=existing.is_fake,is_premium=existing.is_premium,last_seen_at=tm.observed_at,profile_updated_at=existing.profile_updated_at)
            else:
                member=Member(telegram_user_id=tm.telegram_user_id,username=tm.username,first_name=tm.first_name,last_name=tm.last_name,is_bot=int(bool(tm.is_bot)),is_deleted=int(bool(tm.is_deleted)),is_verified=int(bool(tm.is_verified)),is_scam=int(bool(tm.is_scam)),is_fake=int(bool(tm.is_fake)),is_premium=int(bool(tm.is_premium)),last_seen_at=tm.observed_at,profile_updated_at=tm.observed_at)
            prepared.append(member);telegram_by_id[tm.telegram_user_id]=tm
            if existing is None and remaining is not None:remaining-=1
        if not prepared:return
        with self.repository.db.transaction():
            result=self.repository.bulk_upsert(prepared);progress.inserted+=result["inserted"];progress.updated+=result["updated"];progress.unchanged+=result["unchanged"];progress.duplicates+=result["duplicates"];progress.errors+=result["errors"]
            if options.sync_sources:
                for telegram_id,mid in result["member_ids"].items():
                    tm=telegram_by_id.get(telegram_id)
                    if tm:self.sources.mark_sync_seen(mid,group_id,account_id,sync_run_id,tm.observed_at)
            if options.apply_eligibility:
                for telegram_id,mid in result["member_ids"].items():
                    tm=telegram_by_id.get(telegram_id);stored=self.repository.get_by_id(mid)
                    if not tm or not stored or stored.eligibility_status!="UNKNOWN":continue
                    if tm.is_deleted:self.repository.set_eligibility(mid,"DELETED_ACCOUNT")
                    elif tm.is_bot:self.repository.set_eligibility(mid,"BOT")
    @staticmethod
    def _filter(tm,options):
        if options.skip_bots and tm.is_bot:return False,"BOT"
        if options.skip_deleted and tm.is_deleted:return False,"DELETED_ACCOUNT"
        if options.only_with_username and not tm.username:return False,"NO_USERNAME"
        return True,None
    def _emit_progress(self,progress,callback,job):
        if callback:callback(progress)
        if job:
            # Exact total can be unknown; keep progress indeterminate until completion.
            self.jobs.update_fields(job.id,{"total_items":progress.processed,"success_count":progress.inserted+progress.updated,"skipped_count":progress.excluded+progress.duplicates,"failed_count":progress.errors,"updated_at":utc_now_iso()})
    def _classify(self,exc):
        if isinstance(exc,MemberSyncUnavailable):return exc.code,str(exc)
        result=self.error_handler.classify(exc) if self.error_handler else None
        if not result:return "UNKNOWN","Member sync could not be completed."
        normalized={
            "SESSION_UNAUTHORIZED":"SESSION_INVALID",
            "SESSION_INVALID":"SESSION_INVALID",
            "PRIVATE_ACCESS_DENIED":"GROUP_ACCESS_DENIED",
            "NOT_JOINED":"GROUP_ACCESS_DENIED",
            "PERMISSION_DENIED":"GROUP_ACCESS_DENIED",
            "PARTICIPANT_LIST_HIDDEN":"PARTICIPANT_LIST_HIDDEN",
            "FLOOD_WAIT":"FLOOD_WAIT",
            "NETWORK_ERROR":"NETWORK_ERROR",
        }.get(result.code,result.code if result.code in {
            "ACCOUNT_NOT_AUTHORIZED","GROUP_ACCESS_DENIED","PARTICIPANT_LIST_HIDDEN",
            "PARTICIPANT_LIST_UNAVAILABLE","NETWORK_ERROR","FLOOD_WAIT","SESSION_INVALID"
        } else "UNKNOWN")
        return normalized,result.message
    def _alert(self,severity,kind,title,message,**refs):
        if self.alerts:
            try:self.alerts.create(severity,kind,title,message,**refs)
            except Exception as exc:
                if self.logger:self.logger.warning("MEMBER", f"Could not persist member alert: {exc}", action="MEMBER_ALERT")
    def _log(self,action,message,*,account_id=None,group_id=None,level="INFO"):
        if self.logger:self.logger.log(level,"MEMBER",message,action=action,important=True,account_id=account_id,group_id=group_id)

class MemberSyncUnavailable(RuntimeError):
    def __init__(self,code,message):super().__init__(message or code);self.code=code
