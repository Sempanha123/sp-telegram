from __future__ import annotations
import csv
from pathlib import Path
from app.database.database import DatabaseError
from app.models.entities import GroupAccount,TelegramGroup
from app.utils.formatters import utc_now_iso

READ_ACTIONS={"RESOLVE","DISCOVER","SYNC","VIEW","CHECK_PERMISSIONS"}

def can_use_account_for_group_action(account,group_mapping,action:str)->tuple[bool,str]:
    action=action.upper()
    if account is None:return False,"Choose an authorized Telegram account."
    if not bool(account.is_enabled):return False,"This account is disabled."
    if bool(getattr(account,"is_demo",0)):return False,"Demo accounts cannot perform Telegram network operations."
    if str(getattr(account,"authorization_status","UNKNOWN"))!="AUTHORIZED":return False,"This account requires Telegram login."
    if str(getattr(account,"health_status","UNKNOWN")) in {"SESSION_INVALID","LOGIN_REQUIRED","DISABLED"}:return False,"This account is not currently available for Telegram group operations."
    if group_mapping and action=="VIEW" and getattr(group_mapping,"can_view",None) is not None and not bool(getattr(group_mapping,"can_view",None)):return False,"This account cannot currently view the selected group."
    return True,""

class GroupService:
    """Application group orchestration. UI never receives raw Telethon objects."""
    def __init__(self,repository,mapping_repository,*,account_repository=None,telegram_group_service=None,client_manager=None,alert_service=None,logger=None,job_repository=None,error_handler=None):
        self.repository=repository;self.mapping_repository=mapping_repository;self.account_repository=account_repository;self.telegram=telegram_group_service;self.client_manager=client_manager;self.alerts=alert_service;self.logger=logger;self.jobs=job_repository;self.error_handler=error_handler;self.license_limit_service=None;self.feature_gate=None

    def _license_feature(self,feature):
        if self.feature_gate is not None:self.feature_gate.require_feature(feature)

    def _license_limit(self,kind,group_id=None):
        if self.license_limit_service is None:return
        item=self.repository.get_by_id(group_id) if group_id else None
        already=bool(getattr(item,'is_source',False)) if kind=='source' and item else bool((getattr(item,'is_target',False) or getattr(item,'is_managed',False)) if item else False)
        if already:return
        result=self.license_limit_service.can_add_source_group() if kind=='source' else self.license_limit_service.can_add_target_group()
        if not result.allowed:raise RuntimeError(result.message or 'Group plan limit reached.')

    def get_groups(self):return self.repository.get_all()
    def get_sources(self):return self.repository.get_sources()
    def get_targets(self):return self.repository.get_targets()
    def get_managed(self):return self.repository.get_managed()
    def get_group_page(self,page=1,page_size=100,search=None,group_type=None,access=None,flag=None,status=None,role=None,classification=None,account_id=None):return self.repository.get_page(page,page_size,search,group_type,access,flag,status,role,classification,account_id)
    def get_accounts_for_group(self,group_id:int):return self.mapping_repository.get_group_accounts(group_id)
    def get_account_groups(self,account_id:int):return self.mapping_repository.get_account_groups(account_id)
    def _account(self,account_id:int):
        if not self.account_repository:raise RuntimeError("Account repository is not configured.")
        account=self.account_repository.get_by_id(account_id);ok,message=can_use_account_for_group_action(account,None,"VIEW")
        if not ok:raise ValueError(message)
        return account
    async def _ensure_connected(self,account_id:int):
        account=self._account(account_id)
        if not self.telegram or not self.client_manager:raise RuntimeError("Telegram group services are not configured.")
        if not await self.client_manager.is_connected(account_id):
            if not account.session_path or not Path(account.session_path).exists():raise ValueError("Telegram session is missing. Login to this account first.")
            await self.client_manager.create_client(account_id,account.session_path)
            await self.client_manager.connect(account_id)
        if not await self.client_manager.is_authorized(account_id):raise ValueError("This account requires Telegram login.")
        return account
    async def resolve_group(self,account_id:int,input_value:str):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_RESOLVER)
        await self._ensure_connected(account_id)
        self._log("GROUP_RESOLVE_STARTED","Telegram group resolve started.",account_id=account_id)
        try:
            result=await self.telegram.resolve_group(account_id,input_value)
            if result.telegram_group_id:
                result.already_saved=self.repository.get_by_telegram_id(result.telegram_group_id) is not None
            self._log("GROUP_RESOLVED",f"Group resolved: {result.title}.",account_id=account_id)
            return result
        except Exception as exc:
            self._log("GROUP_RESOLVE_FAILED","Telegram group resolution failed.",account_id=account_id,level="WARNING")
            raise ValueError(self._friendly_error(exc)) from exc
    async def discover_groups(self,account_id:int):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_MANAGER)
        await self._ensure_connected(account_id);job=self._job("GROUP_DISCOVERY",account_id=account_id,status="RUNNING")
        try:
            results=await self.telegram.discover_groups(account_id)
            for item in results:item.already_saved=self.repository.get_by_telegram_id(item.telegram_group_id) is not None
            self._finish_job(job,True,total=len(results));return results
        except Exception as exc:self._finish_job(job,False,error=self._friendly_error(exc));raise ValueError(self._friendly_error(exc)) from exc
    async def join_private_group(self,account_id:int,resolved):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_MANAGER)
        await self._ensure_connected(account_id);self._log("PRIVATE_JOIN_STARTED","Private group join explicitly requested.",account_id=account_id)
        try:
            result=await self.telegram.join_private_group(account_id,resolved)
        except Exception as exc:
            raise ValueError(self._friendly_error(exc)) from exc
        action="PRIVATE_JOIN_REQUESTED" if result.join_state=="PENDING" else "PRIVATE_JOIN_SUCCESS";self._log(action,"Private group join state updated.",account_id=account_id)
        return result
    async def _prepare_target_invite_admin(self,group_id:int,account_id:int):
        await self._ensure_connected(account_id)
        group=self.repository.get_by_id(group_id)
        if not group or not (bool(getattr(group,"is_target",0)) or bool(getattr(group,"is_managed",0))):
            raise ValueError("Select a saved managed/target group first.")
        mapping=self.mapping_repository.get_mapping(group_id,account_id)
        if not mapping:
            raise ValueError("The selected account is not mapped to this target group.")
        if str(getattr(mapping,"access_state","UNKNOWN")).upper() in {"ACCESS_DENIED","NOT_JOINED","UNAVAILABLE"}:
            raise ValueError("The selected account does not currently have access to this target group.")
        if not bool(getattr(mapping,"can_manage_invite_links",0) or getattr(mapping,"can_approve_join_requests",0)):
            raise ValueError("The selected account does not have permission to manage invite links or join requests for this target group.")
        client=await self.client_manager.get_client(account_id)
        reference=group.username or group.telegram_group_id
        entity=await client.get_entity(reference)
        return group,mapping,entity

    async def create_target_invite_link(self,group_id:int,account_id:int,*,request_needed:bool=True,title:str|None=None,expire_date=None,usage_limit:int|None=None):
        if self.target_invite_link_service is not None:
            result=await self.target_invite_link_service.create_invite_link(
                group_id,account_id,request_needed=request_needed,title=title,expire_date=expire_date,usage_limit=usage_limit
            )
            if result.success:
                self._log("TARGET_INVITE_LINK_CREATED",f"Invite link created for target group ID {group_id}.",account_id=account_id,group_id=group_id)
            return result
        group,mapping,entity=await self._prepare_target_invite_admin(group_id,account_id)
        link=await self.telegram.create_invite_link(account_id,entity,request_needed=request_needed,title=title,expire_date=expire_date,usage_limit=usage_limit)
        self._log("TARGET_INVITE_LINK_CREATED",f"Invite link created for target group ID {group_id}.",account_id=account_id,group_id=group_id)
        return {"success":True,"status":"COMPLETED","group_id":group_id,"account_id":account_id,"link":link,"request_needed":bool(request_needed),"title":title,"usage_limit":usage_limit}

    async def list_target_join_requests(self,group_id:int,account_id:int,*,limit:int=100):
        _group,_mapping,entity=await self._prepare_target_invite_admin(group_id,account_id)
        return await self.telegram.list_join_requests(account_id,entity,limit=limit)

    async def respond_target_join_request(self,group_id:int,account_id:int,user_id:int,*,approved:bool):
        _group,_mapping,entity=await self._prepare_target_invite_admin(group_id,account_id)
        result=await self.telegram.respond_join_request(account_id,entity,user_id,approved)
        self._log("TARGET_JOIN_REQUEST_APPROVED" if approved else "TARGET_JOIN_REQUEST_DECLINED",f"Join request reviewed for target group ID {group_id}.",account_id=account_id,group_id=group_id)
        return bool(result)

    def save_resolved_group(self,resolved,*,is_source=False,is_target=False,is_managed=False,set_primary=True):
        if int(resolved.telegram_group_id or 0)<=0:raise ValueError("Join the private group or wait for approval before saving it as a Telegram-backed group.")
        existing_group=self.repository.get_by_telegram_id(int(resolved.telegram_group_id))
        if is_source and not (existing_group and existing_group.is_source):self._license_limit("source")
        if (is_target or is_managed) and not (existing_group and (existing_group.is_target or existing_group.is_managed)):self._license_limit("target")
        source_flag=bool(existing_group.is_source) or bool(is_source) if existing_group else bool(is_source)
        target_flag=bool(existing_group.is_target) or bool(is_target) if existing_group else bool(is_target)
        managed_flag=bool(existing_group.is_managed) or bool(is_managed) if existing_group else bool(is_managed)
        with self.repository.db.transaction():
            group=self.repository.upsert_resolved_group(resolved,is_source=source_flag,is_target=target_flag,is_managed=managed_flag)
            mapping=GroupAccount(group_id=group.id,account_id=resolved.account_id,role=resolved.account_role,access_state=resolved.access_state,is_primary=0)
            self._apply_permissions(mapping,resolved.permissions)
            current=self.mapping_repository.get_mapping(group.id,resolved.account_id)
            if current:mapping.id=current.id;mapping.is_primary=current.is_primary
            elif set_primary and not self.mapping_repository.get_primary_account(group.id):mapping.is_primary=1
            self.mapping_repository.upsert_mapping(mapping)
        self._log("GROUP_ADDED" if not current else "GROUP_UPDATED",f"Group saved: {group.title}.",account_id=resolved.account_id,group_id=group.id)
        return self.repository.get_by_id(group.id)
    def save_discovered_groups(self,items,*,is_managed=False):
        saved=[]
        for item in items:saved.append(self.save_resolved_group(item,is_managed=is_managed))
        return saved
    def add_group(self,data:dict):
        telegram_id=data.get("telegram_group_id")
        try:telegram_id=int(telegram_id) if telegram_id not in (None,"") else None
        except (TypeError,ValueError) as exc:raise ValueError("Telegram Group ID must be a number.") from exc
        item=TelegramGroup(telegram_group_id=telegram_id,title=(data.get("title") or data.get("Group Name") or "").strip(),username=(data.get("username") or data.get("Username") or "").strip().lstrip("@") or None,group_type=str(data.get("group_type") or data.get("Type") or "UNKNOWN").upper(),access_type=str(data.get("access_type") or data.get("Access") or "UNKNOWN").upper(),access_state=str(data.get("access_state") or "UNKNOWN").upper(),member_count=max(0,int(data.get("member_count") or data.get("Members") or 0)),description=(data.get("description") or "").strip() or None,is_source=int(bool(data.get("is_source",False))),is_target=int(bool(data.get("is_target",False))),is_managed=int(bool(data.get("is_managed",False))),status=str(data.get("status") or "UNSYNCED").upper())
        if not item.title:raise ValueError("Group title is required.")
        if item.is_source:self._license_limit("source")
        if item.is_target or item.is_managed:self._license_limit("target")
        try:return self.repository.create(item)
        except DatabaseError as exc:
            if exc.kind=="unique":raise ValueError("This Telegram Group ID already exists.") from exc
            raise
    def update_group(self,group_id:int,data:dict):
        item=self.repository.get_by_id(group_id)
        if not item:raise ValueError("Group not found.")
        for field in ("title","username","description"):
            if field in data:setattr(item,field,(data.get(field) or "").strip() or None)
        if not item.title:raise ValueError("Group title is required.")
        if data.get("is_source") and not item.is_source:self._license_limit("source",group_id)
        if (data.get("is_target") and not item.is_target) or (data.get("is_managed") and not item.is_managed):self._license_limit("target",group_id)
        for field in ("is_source","is_target","is_managed"):
            if field in data:setattr(item,field,int(bool(data[field])))
        return self.repository.update(item)
    async def sync_group(self,group_id:int,account_id:int|None=None):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_SYNC)
        group=self.repository.get_by_id(group_id)
        if not group:raise ValueError("Group not found.")
        mapping=self.mapping_repository.get_mapping(group_id,account_id) if account_id else self.mapping_repository.get_primary_account(group_id)
        if not mapping:raise ValueError("No account mapping is available for this group.")
        account_id=int(mapping.account_id);await self._ensure_connected(account_id);job=self._job("GROUP_SYNC",account_id=account_id,group_id=group_id,status="RUNNING")
        self.repository.update_sync_status(group_id,"SYNCING");self._log("GROUP_SYNC_STARTED",f"Sync started for {group.title}.",account_id=account_id,group_id=group_id)
        reference=group.username or group.telegram_group_id
        try:
            resolved=await self.telegram.sync_group(account_id,reference)
            self._persist_sync(group,mapping,resolved);self._finish_job(job,True,total=1);self._log("GROUP_SYNC_SUCCESS",f"Group synced: {resolved.title}.",account_id=account_id,group_id=group_id)
            return self.repository.get_by_id(group_id)
        except Exception as exc:
            code=self._code(exc);self.repository.update_sync_status(group_id,"ACCESS_DENIED" if code in {"PRIVATE_ACCESS_DENIED","NOT_JOINED"} else "UNAVAILABLE" if code=="GROUP_UNAVAILABLE" else "ERROR",code,str(exc));self.mapping_repository.update_last_error(group_id,account_id,code,str(exc));self._finish_job(job,False,error=str(exc));self._log("GROUP_SYNC_FAILED",f"Group sync failed for {group.title}.",account_id=account_id,group_id=group_id,level="WARNING")
            if code in {"PRIVATE_ACCESS_DENIED","NOT_JOINED","GROUP_UNAVAILABLE"}:self._alert("WARNING","GROUP_ACCESS",f"Group access issue: {group.title}",str(exc),account_id=account_id,group_id=group_id)
            raise ValueError(self._friendly_error(exc)) from exc
    def _persist_sync(self,old,mapping,resolved):
        changes=[]
        if old.username!=resolved.username:changes.append(("username",old.username,resolved.username))
        if old.title!=resolved.title:changes.append(("title",old.title,resolved.title))
        old_role=mapping.role;old_post=mapping.can_post;old_invite=mapping.can_invite
        with self.repository.db.transaction():
            self.repository.upsert_resolved_group(resolved,is_source=bool(old.is_source),is_target=bool(old.is_target),is_managed=bool(old.is_managed))
            mapping.role=resolved.account_role;mapping.access_state=resolved.access_state;self._apply_permissions(mapping,resolved.permissions);self.mapping_repository.upsert_mapping(mapping)
        for field,before,after in changes:
            self._log("GROUP_UPDATED",f"Group {field} changed: {before or '—'} → {after or '—'}",account_id=mapping.account_id,group_id=old.id)
            if field=="username":self._alert("INFO","GROUP_USERNAME_CHANGED",f"Group username changed: {resolved.title}","Group username metadata changed during sync.",group_id=old.id)
        if old_role!=mapping.role:
            self._log("GROUP_ROLE_CHANGED",f"Account role changed: {old_role} → {mapping.role}",account_id=mapping.account_id,group_id=old.id)
            if old_role in {"OWNER","ADMIN"} and mapping.role not in {"OWNER","ADMIN"}:self._alert("WARNING","GROUP_ROLE",f"Admin role removed: {resolved.title}","A mapped account no longer has its previous admin role.",account_id=mapping.account_id,group_id=old.id)
        for label,before,after in (("Posting",old_post,mapping.can_post),("Invite",old_invite,mapping.can_invite)):
            if before is not None and bool(before) and after is not None and not bool(after):self._alert("WARNING","GROUP_PERMISSION",f"{label} permission removed: {resolved.title}",f"{label} permission changed for the mapped account.",account_id=mapping.account_id,group_id=old.id)
    async def refresh_permissions(self,group_id:int,account_id:int):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_PERMISSIONS)
        group=self.repository.get_by_id(group_id);mapping=self.mapping_repository.get_mapping(group_id,account_id)
        if not group or not mapping:raise ValueError("Group/account mapping not found.")
        reference=group.username or group.telegram_group_id
        if not reference:raise ValueError("This saved group has no Telegram username or group ID. Resolve or sync the group before checking permissions.")
        await self._ensure_connected(account_id);client=await self.client_manager.get_client(account_id);entity=await client.get_entity(reference);perms=await self.telegram.refresh_permissions(account_id,entity);old_role=mapping.role
        self.mapping_repository.update_permissions(group_id,account_id,perms);self.mapping_repository.update_access_state(group_id,account_id,"PUBLIC_ACCESSIBLE" if group.username else "PRIVATE_MEMBER")
        self.mapping_repository.update_last_error(group_id,account_id,None,None)
        self._log("GROUP_PERMISSION_CHANGED","Group permissions refreshed.",account_id=account_id,group_id=group_id)
        if old_role!=perms.role:self._log("GROUP_ROLE_CHANGED",f"Account role changed: {old_role} → {perms.role}",account_id=account_id,group_id=group_id)
        return self.mapping_repository.get_mapping(group_id,account_id)
    async def check_account_mapping(self,group_id:int,account_id:int):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_PERMISSIONS)
        group=self.repository.get_by_id(group_id)
        if not group:raise ValueError("The saved group no longer exists. Refresh All Groups and try again.")
        reference=group.username or group.telegram_group_id
        if not reference:raise ValueError("This saved group has no Telegram username or group ID. Resolve or sync the group before assigning it.")
        await self._ensure_connected(account_id)
        client=await self.client_manager.get_client(account_id)
        try:entity=await client.get_entity(reference);perms=await self.telegram.refresh_permissions(account_id,entity)
        except Exception as exc:raise ValueError(self._friendly_error(exc)) from exc
        mapping=GroupAccount(group_id=group_id,account_id=account_id,role=perms.role,access_state="PUBLIC_ACCESSIBLE" if group.username else "PRIVATE_MEMBER");self._apply_permissions(mapping,perms)
        existing=self.mapping_repository.get_mapping(group_id,account_id)
        if existing:mapping.id=existing.id;mapping.is_primary=existing.is_primary
        elif not self.mapping_repository.get_primary_account(group_id):mapping.is_primary=1
        return mapping
    def save_account_mapping(self,mapping):
        result=self.mapping_repository.upsert_mapping(mapping);group=self.repository.get_by_id(mapping.group_id);self._log("GROUP_MAPPING_ADDED",f"Account mapping added to {group.title if group else 'group'}.",account_id=mapping.account_id,group_id=mapping.group_id);return result
    async def add_account_mapping(self,group_id:int,account_id:int):
        from app.license.feature_keys import FeatureKey
        self._license_feature(FeatureKey.GROUP_MANAGER)
        return self.save_account_mapping(await self.check_account_mapping(group_id,account_id))
    def remove_account_mapping(self,group_id:int,account_id:int):
        result=self.mapping_repository.remove_mapping(group_id,account_id);self._log("GROUP_MAPPING_REMOVED","Group account mapping removed.",account_id=account_id,group_id=group_id);return result
    def set_primary_account(self,group_id:int,account_id:int):
        result=self.mapping_repository.set_primary_account(group_id,account_id);self._log("GROUP_PRIMARY_ACCOUNT_CHANGED","Primary group account changed.",account_id=account_id,group_id=group_id);return result
    def set_source(self,group_id:int,value:bool):
        if value:
            from app.license.feature_keys import FeatureKey
            self._license_feature(FeatureKey.GROUP_MANAGER);self._license_limit("source",group_id)
        self.repository.set_source(group_id,value);return self.repository.get_by_id(group_id)
    def set_target(self,group_id:int,value:bool):
        if value:
            from app.license.feature_keys import FeatureKey
            self._license_feature(FeatureKey.GROUP_MANAGER);self._license_limit("target",group_id)
        self.repository.set_target(group_id,value);return self.repository.get_by_id(group_id)
    def set_managed(self,group_id:int,value:bool):
        if value:
            from app.license.feature_keys import FeatureKey
            self._license_feature(FeatureKey.GROUP_MANAGER);self._license_limit("target",group_id)
        self.repository.set_managed(group_id,value);return self.repository.get_by_id(group_id)
    def get_group_details(self,group_id:int):return {"group":self.repository.get_by_id(group_id),"accounts":self.mapping_repository.get_group_accounts(group_id),"logs":self._group_logs(group_id)}

    def group_relationship_summary(self,group_id:int):
        if not self.repository.get_by_id(group_id):raise ValueError("Group not found.")
        db=self.repository.db
        def count(sql,params=(group_id,)):
            row=db.fetch_one(sql,params);return int(row["count"] if row else 0)
        return {
            "account_mappings":count("SELECT COUNT(*) count FROM group_accounts WHERE group_id=?"),
            "member_sources":count("SELECT COUNT(*) count FROM member_sources WHERE group_id=?"),
            "target_membership_states":count("SELECT COUNT(*) count FROM member_target_states WHERE target_group_id=?"),
            "member_exclusions":count("SELECT COUNT(*) count FROM member_exclusions WHERE target_group_id=?"),
            "member_sync_runs":count("SELECT COUNT(*) count FROM member_sync_runs WHERE group_id=?"),
            "member_target_actions":count("SELECT COUNT(*) count FROM member_target_actions WHERE target_group_id=?"),
            "invite_links":count("SELECT COUNT(*) count FROM target_invite_links WHERE target_group_id=?"),
            "campaign_targets":count("SELECT COUNT(*) count FROM campaign_targets WHERE group_id=?"),
            "campaign_deliveries":count("SELECT COUNT(*) count FROM campaign_deliveries d JOIN campaign_targets t ON t.id=d.campaign_target_id WHERE t.group_id=?"),
            "template_links":count("SELECT COUNT(*) count FROM template_groups WHERE group_id=?"),
            "jobs":count("SELECT COUNT(*) count FROM jobs WHERE group_id=?"),
            "alerts":count("SELECT COUNT(*) count FROM alerts WHERE group_id=?"),
            "logs":count("SELECT COUNT(*) count FROM logs WHERE group_id=?"),
        }

    def remove_group(self,group_id:int,remove_related:bool=False):
        if not self.repository.get_by_id(group_id):raise ValueError("Group not found.")
        if remove_related:
            summary=self.group_relationship_summary(group_id);db=self.repository.db
            with db.transaction():
                # Campaign delivery rows reference campaign targets with RESTRICT,
                # so their local snapshots must be removed first.
                db.execute("DELETE FROM campaign_rendered_messages WHERE delivery_id IN (SELECT d.id FROM campaign_deliveries d JOIN campaign_targets t ON t.id=d.campaign_target_id WHERE t.group_id=?)",(group_id,))
                db.execute("DELETE FROM campaign_deliveries WHERE campaign_target_id IN (SELECT id FROM campaign_targets WHERE group_id=?)",(group_id,))
                db.execute("DELETE FROM campaign_target_messages WHERE campaign_target_id IN (SELECT id FROM campaign_targets WHERE group_id=?)",(group_id,))
                db.execute("DELETE FROM campaign_targets WHERE group_id=?",(group_id,))
                for table,column in (
                    ("member_target_actions","target_group_id"),("member_sync_runs","group_id"),
                    ("member_target_states","target_group_id"),("member_exclusions","target_group_id"),
                    ("member_sources","group_id"),("template_groups","group_id"),
                    ("target_invite_links","target_group_id"),("group_accounts","group_id"),
                ):
                    db.execute(f"DELETE FROM {table} WHERE {column}=?",(group_id,))
                # Keep general audit/job rows, but detach their foreign-key link so
                # the historical text remains available after the local group is gone.
                for table in ("jobs","alerts","logs"):
                    db.execute(f"UPDATE {table} SET group_id=NULL WHERE group_id=?",(group_id,))
                removed=self.repository.delete(group_id)
            return {"removed":bool(removed),"relationships":summary}
        try:return self.repository.delete(group_id)
        except DatabaseError as exc:
            if exc.kind=="foreign_key":raise ValueError("This group has linked local records. Use Remove From Tool again and confirm removal of the listed local relationships.") from exc
            raise
    def import_csv(self,path:str|Path):
        imported=updated=skipped=errors=0;error_rows=[]
        with Path(path).open("r",encoding="utf-8-sig",newline="") as handle:
            for line,row in enumerate(csv.DictReader(handle),2):
                try:
                    raw=(row.get("telegram_group_id") or "").strip();tid=int(raw) if raw else None;existing=self.repository.get_by_telegram_id(tid) if tid else None
                    data={"telegram_group_id":tid,"title":row.get("title") or "","username":row.get("username") or "","group_type":row.get("group_type") or row.get("type") or "UNKNOWN","access_type":row.get("access_type") or row.get("access") or "UNKNOWN","member_count":int(row.get("member_count") or row.get("members") or 0),"is_source":str(row.get("is_source") or row.get("source") or "0").lower() in {"1","true","yes"},"is_target":str(row.get("is_target") or row.get("target") or "0").lower() in {"1","true","yes"},"is_managed":str(row.get("is_managed") or row.get("managed") or "0").lower() in {"1","true","yes"},"status":"UNSYNCED"}
                    if existing:self.update_group(existing.id,data);self.repository.update_sync_status(existing.id,"UNSYNCED");updated+=1
                    else:self.add_group(data);imported+=1
                except ValueError as exc:skipped+=1;error_rows.append({"line":line,"error":str(exc)})
                except Exception as exc:errors+=1;error_rows.append({"line":line,"error":str(exc)})
        return {"imported":imported,"updated":updated,"skipped":skipped,"errors":errors,"error_rows":error_rows}
    def export_csv(self,path:str|Path):
        with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
            w=csv.writer(handle);w.writerow(["telegram_group_id","title","username","type","access","members","source","target","managed","primary_account","status","last_sync"])
            for g in self.get_groups():w.writerow([g.telegram_group_id or "",g.title,g.username or "",g.group_type,g.access_type,g.member_count,g.is_source,g.is_target,g.is_managed,g.account_name or "",g.status,g.last_sync_at or ""])
        return Path(path)
    @staticmethod
    def _apply_permissions(mapping,perms):
        if not perms:return
        for f in ("role","can_view","can_post","can_send_media","can_invite","can_manage","can_delete_messages","can_pin_messages","can_ban_users","can_add_admins","can_manage_call","can_manage_topics","can_manage_invite_links"):
            v=getattr(perms,f,None);setattr(mapping,f,int(v) if isinstance(v,bool) else v)
        mapping.last_permission_check_at=getattr(perms,"checked_at",None);mapping.last_access_check_at=utc_now_iso()
    def _friendly_error(self, exc):
        if self.error_handler:
            try:
                result=self.error_handler.classify(exc)
                if result and result.message and result.code != "UNKNOWN":return result.message
            except Exception as classify_exc:
                if self.logger:self.logger.warning("GROUP", f"Telegram error classification failed: {classify_exc}", action="GROUP_ERROR_CLASSIFY")
        code=self._code(exc)
        return {
            "INVALID_USERNAME":"Invalid Telegram group reference.",
            "USERNAME_NOT_FOUND":"Telegram username was not found. Check the username or link and try again.",
            "INVALID_INVITE":"This Telegram invite link is invalid.",
            "INVITE_EXPIRED":"This Telegram invite link is no longer valid.",
            "PRIVATE_ACCESS_DENIED":"This account does not currently have access to the selected private group.",
            "NOT_JOINED":"This account is not currently a member of the selected group.",
            "JOIN_REQUEST_PENDING":"Join request submitted. Waiting for administrator approval.",
            "GROUP_UNAVAILABLE":"The Telegram group is unavailable to this account.",
            "FLOOD_WAIT":"Telegram requested a cooldown. The group operation was stopped and was not moved to another account.",
            "NETWORK_ERROR":"Telegram is currently unreachable from this computer.",
        }.get(code,"Telegram group operation could not be completed.")
    def _code(self,exc):
        name=type(exc).__name__
        return {"UsernameNotOccupiedError":"USERNAME_NOT_FOUND","InviteHashExpiredError":"INVITE_EXPIRED","InviteHashInvalidError":"INVALID_INVITE","ChannelPrivateError":"PRIVATE_ACCESS_DENIED","UserNotParticipantError":"NOT_JOINED","ChannelInvalidError":"GROUP_UNAVAILABLE","ChatIdInvalidError":"GROUP_UNAVAILABLE","InviteRequestSentError":"JOIN_REQUEST_PENDING","FloodWaitError":"FLOOD_WAIT"}.get(name,"NETWORK_ERROR" if isinstance(exc,(OSError,ConnectionError,TimeoutError)) else "UNKNOWN")
    def _log(self,action,message,*,account_id=None,group_id=None,level="INFO"):
        if self.logger:self.logger.log(level,"GROUP",message,action=action,important=True,account_id=account_id,group_id=group_id)
    def _alert(self,severity,kind,title,message,**refs):
        if self.alerts:self.alerts.create(severity,kind,title,message,**refs)
    def _job(self,kind,**values):return self.jobs.create_job(kind,**values) if self.jobs else None
    def _finish_job(self,job,success,total=0,error=None):
        if not job:return
        if total:self.jobs.update_fields(job.id,{"total_items":total,"progress":100,"success_count":total if success else 0,"failed_count":0 if success else 1,"status":"COMPLETED" if success else "FAILED","finished_at":utc_now_iso(),"last_error":error,"updated_at":utc_now_iso()})
        else:self.jobs.update_fields(job.id,{"progress":100,"success_count":1 if success else 0,"failed_count":0 if success else 1,"status":"COMPLETED" if success else "FAILED","finished_at":utc_now_iso(),"last_error":error,"updated_at":utc_now_iso()})
    def _group_logs(self,group_id:int):
        if not self.logger or not self.logger.repository:return []
        return [dict(r) for r in self.repository.db.fetch_all("SELECT id,level,action,message,created_at FROM logs WHERE group_id=? ORDER BY created_at DESC LIMIT 100",(group_id,))]
