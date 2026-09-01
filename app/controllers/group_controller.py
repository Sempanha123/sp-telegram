from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject,Signal
from app.models.pagination import PaginationState

_LOG=logging.getLogger(__name__)

class GroupController(QObject):
    groupsChanged=Signal(list);groupCreated=Signal(object);groupResolved=Signal(object);groupUpdated=Signal(object);groupRemoved=Signal(int);groupPermissionsUpdated=Signal(int,int);groupMappingChanged=Signal(int);groupSyncStarted=Signal(int);groupSyncFinished=Signal(int);groupSyncFailed=Signal(int,str);discoveryCompleted=Signal(int,list);groupJoinUpdated=Signal(object);errorOccurred=Signal(str);toast_requested=Signal(str,str);bulkSyncProgress=Signal(int,int,int,int,str);bulkSyncFinished=Signal(int,int,bool);planLimitReached=Signal(str,object);featureLocked=Signal(str,str)
    groupAssignmentProgress=Signal(int,int,int,str);groupAssignmentFinished=Signal(int,int,int)
    def __init__(self,service,worker=None,error_handler=None,parent=None):
        super().__init__(parent);self.service=service;self.worker=worker;self.error_handler=error_handler;self.pagination=PaginationState();self.search_text="";self.type_filter=None;self.access_filter=None;self.role_filter=None;self.status_filter=None;self.classification_filter=None;self.account_filter=None;self.flag=None;self.current_items=[];self._handlers={};self._bulk=None;self._mapping_batches={};self.license_limit_service=None;self.feature_gate=None
        if worker:worker.operationCompleted.connect(self._done);worker.operationFailed.connect(self._failed);worker.finished.connect(self._on_worker_finished)
    def _require_license_feature(self,feature):
        if self.feature_gate is None:return True
        if self.feature_gate.has_feature(feature):return True
        self.featureLocked.emit(str(feature),str(self.feature_gate.get_required_plan(feature) or "STARTER"));return False
    def groups(self):return self.refresh(emit=False)
    def refresh(self,emit=True):
        try:
            items,total=self.service.get_group_page(self.pagination.page,self.pagination.page_size,self.search_text,self.type_filter,self.access_filter,self.flag,self.status_filter,self.role_filter,self.classification_filter,self.account_filter);self.pagination.total_items=total;self.pagination.clamp();self.current_items=items
            if emit:self.groupsChanged.emit(items)
            return items
        except Exception as exc:self._error(exc);return []
    def set_scope(self,flag):self.flag=flag;self.pagination.page=1;return self.refresh()
    def get_scoped(self,flag,page=1,page_size=100):
        try:return self.service.get_group_page(page,page_size,flag=flag)
        except Exception as exc:self._error(exc);return ([],0)
    def set_search(self,text):self.search_text=text;self.pagination.page=1;return self.refresh()
    def set_filter(self,column,value):
        value=None if value in {None,"All"} else value
        if column=="Type":self.type_filter=value
        elif column=="Access":self.access_filter=value
        elif column=="Role":self.role_filter=value
        elif column=="Status":self.status_filter=value
        elif column=="Classification":self.classification_filter=value.lower() if value else None
        elif column=="Account":self.account_filter=int(value) if value and str(value).isdigit() else None
        self.pagination.page=1;return self.refresh()
    def set_page(self,page):self.pagination.page=page;return self.refresh()
    def set_page_size(self,size):self.pagination.page_size=size;self.pagination.page=1;return self.refresh()
    def add(self,data):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_MANAGER):return None
        try:item=self.service.add_group(data);self.groupCreated.emit(item);self.toast_requested.emit("Local group record added. Sync it to verify Telegram metadata.","Success");self.refresh();return item
        except Exception as exc:self._error(exc);return None
    def update(self,id,data):
        try:item=self.service.update_group(id,data);self.groupUpdated.emit(item);self.toast_requested.emit("Group updated.","Success");self.refresh();return item
        except Exception as exc:self._error(exc);return None
    def removal_summary(self,id):
        try:return self.service.group_relationship_summary(id)
        except Exception as exc:self._error(exc);return None
    def remove(self,id,remove_related=False):
        try:self.service.remove_group(id,remove_related=bool(remove_related));self.groupRemoved.emit(id);self.toast_requested.emit("Group and its selected local relationships were removed from the tool." if remove_related else "Group removed from the tool.","Success");self.refresh();return True
        except Exception as exc:self._error(exc);return False
    def details(self,id):return self.service.get_group_details(id)
    def accounts_for_group(self,id):return self.service.get_accounts_for_group(id)
    def available_accounts(self):
        repo=getattr(self.service,"account_repository",None);return repo.get_enabled_accounts() if repo else []
    def resolve_group(self,account_id:int,input_value:str,callback=None):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_RESOLVER):return None
        return self._submit(self.service.resolve_group(account_id,input_value),"group_resolve",account_id,lambda r:self._resolved(r,callback))
    def _resolved(self,result,callback):self.groupResolved.emit(result);self.toast_requested.emit("Telegram group resolved.","Success");callback(result) if callback else None
    def save_resolved_group(self,resolved,flags):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_MANAGER):return None
        try:
            if flags.get("is_source") and not self._check_limit("source"):return None
            if (flags.get("is_target") or flags.get("is_managed")) and not self._check_limit("target"):return None
            item=self.service.save_resolved_group(resolved,is_source=flags.get("is_source",False),is_target=flags.get("is_target",False),is_managed=flags.get("is_managed",False));self.groupCreated.emit(item);self.toast_requested.emit("Telegram group saved.","Success");self.refresh();return item
        except Exception as exc:self._error(exc);return None
    def join_private_group(self,account_id,resolved,callback=None):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_MANAGER):return None
        return self._submit(self.service.join_private_group(account_id,resolved),"group_join",account_id,lambda r:self._joined(r,callback))
    def _joined(self,result,callback):self.groupJoinUpdated.emit(result);self.toast_requested.emit("Join request submitted." if result.join_state=="PENDING" else "Group joined.","Info" if result.join_state=="PENDING" else "Success");callback(result) if callback else None
    def discover_groups(self,account_id:int,callback=None):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_MANAGER):return None
        return self._submit(self.service.discover_groups(account_id),"group_discovery",account_id,lambda r:self._discovered(account_id,r,callback))
    def _discovered(self,account_id,items,callback):self.discoveryCompleted.emit(account_id,items);self.toast_requested.emit(f"Discovered {len(items)} accessible groups/channels.","Success");callback(items) if callback else None
    def save_discovered(self,items):
        try:r=self.service.save_discovered_groups(items);self.refresh();self.toast_requested.emit(f"Saved {len(r)} discovered groups.","Success");return r
        except Exception as exc:self._error(exc);return []
    def sync_group(self,group_id:int,account_id:int|None=None,callback=None):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_SYNC):return None
        self.groupSyncStarted.emit(group_id);aid=account_id or 0
        return self._submit(self.service.sync_group(group_id,account_id),"group_sync",aid,lambda r:self._synced(group_id,r,callback),lambda _a,m:self._sync_failed(group_id,m))
    def _synced(self,gid,item,callback):self.groupSyncFinished.emit(gid);self.groupUpdated.emit(item);self.toast_requested.emit("Group sync completed.","Success");self.refresh();callback(item) if callback else None
    def _sync_failed(self,gid,message):self.groupSyncFailed.emit(gid,message);self.toast_requested.emit(message,"Error");self.refresh()
    def refresh_permissions(self,group_id,account_id,callback=None,failure_callback=None):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.GROUP_PERMISSIONS):return None
        return self._submit(self.service.refresh_permissions(group_id,account_id),"group_permissions",account_id,lambda r:self._perms(group_id,account_id,r,callback),lambda _a,m:self._mapping_operation_failed(m,failure_callback))
    def _perms(self,gid,aid,result,callback):self.groupPermissionsUpdated.emit(gid,aid);self.toast_requested.emit("Group permissions refreshed.","Success");self.refresh();callback(result) if callback else None
    def check_account_mapping(self,group_id,account_id,callback=None,failure_callback=None):return self._submit(self.service.check_account_mapping(group_id,account_id),"group_mapping_check",account_id,lambda r:callback(r) if callback else None,lambda _a,m:self._mapping_operation_failed(m,failure_callback))
    def save_account_mapping(self,mapping):
        try:r=self.service.save_account_mapping(mapping);self._mapping(mapping.group_id,r,None);return r
        except Exception as exc:self._error(exc);return None
    def add_account_mapping(self,group_id,account_id,callback=None,failure_callback=None):return self._submit(self.service.add_account_mapping(group_id,account_id),"group_mapping",account_id,lambda r:self._mapping(group_id,r,callback),lambda _a,m:self._mapping_operation_failed(m,failure_callback))
    def _mapping(self,gid,result,callback):self.groupMappingChanged.emit(gid);self.toast_requested.emit("Account mapping added.","Success");self.refresh();callback(result) if callback else None
    def _mapping_operation_failed(self,message,callback=None):
        text=self._friendly(str(message or "Group permission verification could not be completed."));self.toast_requested.emit(text,"Warning");callback(text) if callback else None
    def is_group_assignment_verifying(self,account_id):return int(account_id) in self._mapping_batches
    def verify_account_group_mappings(self,account_id,group_ids):
        """Verify saved mappings sequentially so one account has one Telegram request at a time."""
        try:
            account_id=int(account_id);ids=list(dict.fromkeys(int(value) for value in (group_ids or []) if int(value)>0))
        except (TypeError,ValueError):
            self.toast_requested.emit("The saved group assignment list is invalid. Refresh Account Pool and try again.","Warning");return False
        if not ids:self.refresh();return True
        if self.is_group_assignment_verifying(account_id):
            self.toast_requested.emit("This account is already verifying group assignments. Wait for it to finish before editing them again.","Warning");return False
        if not self.worker:
            self.toast_requested.emit("Assignments were saved locally, but Telegram verification is unavailable. Restart the desktop app, then use Refresh Permissions.","Warning");self.refresh();return False
        self._mapping_batches[account_id]={"ids":ids,"index":0,"success":0,"failed":0,"errors":[]}
        self._verify_mapping_next(account_id);return True
    def _verify_mapping_next(self,account_id):
        batch=self._mapping_batches.get(int(account_id))
        if not batch:return
        if batch["index"]>=len(batch["ids"]):self._finish_mapping_batch(int(account_id));return
        group_id=int(batch["ids"][batch["index"]])
        try:group=self.service.repository.get_by_id(group_id);title=getattr(group,"title",None) or f"Group {group_id}"
        except Exception as exc:self._mapping_batch_failed(int(account_id),group_id,str(exc));return
        self.groupAssignmentProgress.emit(int(account_id),batch["index"]+1,len(batch["ids"]),str(title))
        coroutine=None
        try:
            self.service.mapping_repository.mark_verification_unavailable(group_id,int(account_id),"PENDING_VERIFICATION","Telegram permission verification is running.")
            coroutine=self.service.refresh_permissions(group_id,int(account_id))
            token=self.worker.submit_coroutine(coroutine,operation="group_mapping_verify",account_id=int(account_id))
            self._handlers[token]=(
                lambda result,aid=int(account_id),gid=group_id:self._mapping_batch_ok(aid,gid,result),
                lambda _worker_account,message,aid=int(account_id),gid=group_id:self._mapping_batch_failed(aid,gid,message),
            )
        except Exception as exc:
            if coroutine is not None and hasattr(coroutine,"close"):coroutine.close()
            self._mapping_batch_failed(int(account_id),group_id,str(exc))
    def _mapping_batch_ok(self,account_id,group_id,_result):
        batch=self._mapping_batches.get(int(account_id))
        if not batch:return
        batch["success"]+=1;batch["index"]+=1;self.groupMappingChanged.emit(int(group_id));self.groupPermissionsUpdated.emit(int(group_id),int(account_id));self._verify_mapping_next(int(account_id))
    def _mapping_batch_failed(self,account_id,group_id,message):
        batch=self._mapping_batches.get(int(account_id))
        if not batch:return
        friendly=self._friendly(str(message or "Telegram permission verification failed."))
        try:
            self.service.mapping_repository.mark_verification_unavailable(int(group_id),int(account_id),"VERIFY_FAILED",friendly)
        except Exception as exc:_LOG.warning("Could not store group mapping verification error: %s",exc)
        batch["failed"]+=1;batch["index"]+=1;batch["errors"].append((int(group_id),friendly));self.groupMappingChanged.emit(int(group_id));self._verify_mapping_next(int(account_id))
    def _finish_mapping_batch(self,account_id):
        batch=self._mapping_batches.pop(int(account_id),None)
        if not batch:return
        success=int(batch["success"]);failed=int(batch["failed"]);self.refresh();self.groupAssignmentFinished.emit(int(account_id),success,failed)
        if failed:
            self.toast_requested.emit(f"Assignments stayed saved locally. Verified {success}; {failed} need attention. Open All Groups → Details to review the permission error.","Warning")
        else:self.toast_requested.emit(f"Verified {success} group assignment(s) for this account.","Success")
    def remove_account_mapping(self,group_id,account_id):
        try:self.service.remove_account_mapping(group_id,account_id);self.groupMappingChanged.emit(group_id);self.toast_requested.emit("Account mapping removed.","Success");self.refresh();return True
        except Exception as exc:self._error(exc);return False
    def set_primary_account(self,group_id,account_id):
        try:r=self.service.set_primary_account(group_id,account_id);self.groupMappingChanged.emit(group_id);self.toast_requested.emit("Primary account updated.","Success");self.refresh();return r
        except Exception as exc:self._error(exc);return None
    def set_source(self,gid,value=True):return self._classify(gid,"source",value)
    def set_target(self,gid,value=True):return self._classify(gid,"target",value)
    def set_managed(self,gid,value=True):return self._classify(gid,"managed",value)
    def _classify(self,gid,kind,value):
        try:
            item=self.service.repository.get_by_id(gid)
            already=bool(getattr(item,f"is_{kind}",False)) if item else False
            if value and not already and kind in {"source","target","managed"} and not self._check_limit("source" if kind=="source" else "target"):return None
            r=getattr(self.service,f"set_{kind}")(gid,value);self.groupUpdated.emit(r);self.refresh();return r
        except Exception as exc:self._error(exc);return None

    def create_target_invite_link(self,group_id:int,account_id:int,*,request_needed:bool=True,title:str|None=None,expire_date=None,usage_limit:int|None=None,callback=None,failure_callback=None):
        """Create one managed target invite link with the explicitly selected account."""
        return self._submit(
            self.service.create_target_invite_link(group_id,account_id,request_needed=request_needed,title=title,expire_date=expire_date,usage_limit=usage_limit),
            "target_invite_link_create",account_id,
            lambda r:self._invite_link_created(r,callback),
            lambda _a,m:self._invite_admin_failed(m,failure_callback),
        )
    def active_target_invite_links(self,group_id:int):
        service=getattr(self.service,"target_invite_link_service",None)
        if service is None:return []
        try:return list(service.list_invite_links(int(group_id)) or [])
        except Exception as exc:self._error(exc);return []
    def _invite_link_created(self,result,callback):
        payload=result.to_dict() if hasattr(result,"to_dict") else (dict(result) if isinstance(result,dict) else {"success":True,"link":result})
        if not bool(payload.get("success",True)):
            message=payload.get("user_message") or payload.get("message") or "Target invite link could not be created."
            self.toast_requested.emit(str(message),"Warning")
            if callback:
                try:callback(payload)
                except Exception as exc:_LOG.exception("Invite-link failure result callback failed",exc_info=exc)
            return
        self.toast_requested.emit("Target invite link created. No member was automatically invited.","Success")
        if callback:
            try:callback(payload)
            except Exception as exc:
                _LOG.exception("Invite-link success result callback failed",exc_info=exc)
                self.toast_requested.emit("Invite link was created, but this view could not refresh. Open Target Groups and use Copy Invite Link.","Warning")
    def list_target_join_requests(self,group_id:int,account_id:int,*,limit:int=100,callback=None,failure_callback=None):
        return self._submit(
            self.service.list_target_join_requests(group_id,account_id,limit=limit),
            "target_join_requests",account_id,
            lambda r:callback(r) if callback else None,
            lambda _a,m:self._invite_admin_failed(m,failure_callback),
        )
    def respond_target_join_request(self,group_id:int,account_id:int,user_id:int,*,approved:bool,callback=None,failure_callback=None):
        action="approve" if approved else "decline"
        return self._submit(
            self.service.respond_target_join_request(group_id,account_id,user_id,approved=approved),
            f"target_join_request_{action}",account_id,
            lambda r:self._join_request_reviewed(r,approved,callback),
            lambda _a,m:self._invite_admin_failed(m,failure_callback),
        )
    def _join_request_reviewed(self,result,approved,callback):
        self.toast_requested.emit("Join request approved." if approved else "Join request declined.","Success" if approved else "Info")
        callback(result) if callback else None
    def _invite_admin_failed(self,message,callback=None):
        # Permission/network/session failures are normal operational outcomes for
        # invite administration. Keep them inline/toast instead of escalating to
        # the global Unexpected Error path.
        text=self._friendly(message or "Target invite administration could not be completed.")
        self.toast_requested.emit(text,"Warning")
        callback(text) if callback else None

    def _check_limit(self,kind):
        if self.license_limit_service is None:return True
        result=self.license_limit_service.can_add_source_group() if kind=="source" else self.license_limit_service.can_add_target_group()
        if not result.allowed:self.planLimitReached.emit("MAX_SOURCE_GROUPS" if kind=="source" else "MAX_TARGET_GROUPS",result)
        return bool(result.allowed)

    def sync_selected_groups(self,group_ids:list[int]):
        ids=list(dict.fromkeys(int(x) for x in group_ids));self._bulk={"ids":ids,"index":0,"success":0,"failed":0,"cancel":False};self._bulk_next()
    def cancel_bulk_sync(self):
        if self._bulk:self._bulk["cancel"]=True
    def _bulk_next(self):
        b=self._bulk
        if not b:return
        if b["cancel"] or b["index"]>=len(b["ids"]):self.bulkSyncFinished.emit(b["success"],b["failed"],b["cancel"]);self._bulk=None;return
        gid=b["ids"][b["index"]];group=self.service.repository.get_by_id(gid);self.bulkSyncProgress.emit(b["index"],len(b["ids"]),b["success"],b["failed"],group.title if group else str(gid))
        def ok(_):b["success"]+=1;b.__setitem__("index",b["index"]+1);self._bulk_next()
        token=self.sync_group(gid,callback=ok)
        if token:
            # replace default failure for this token so bulk continues
            self._handlers[token]=(lambda r:self._synced(gid,r,ok),lambda _a,m:self._bulk_fail(gid,m))
    def _bulk_fail(self,gid,message):
        b=self._bulk
        if not b:return
        b["failed"]+=1;b["index"]+=1;self.groupSyncFailed.emit(gid,message);self._bulk_next()
    def import_csv(self,path):
        try:r=self.service.import_csv(path);self.refresh();self.toast_requested.emit(f"Imported: {r['imported']} • Updated: {r['updated']} • Skipped: {r['skipped']} • Errors: {r['errors']}","Success" if not r["errors"] else "Warning");return r
        except Exception as exc:self._error(exc);return None
    def export_csv(self,path):
        try:self.service.export_csv(path);self.toast_requested.emit("Groups exported successfully.","Success");return True
        except Exception as exc:self._error(exc);return False
    def _submit(self,coro,operation,account_id,success,failure=None):
        if not self.worker:self._error(RuntimeError("Telegram runtime is unavailable."));return None
        try:token=self.worker.submit_coroutine(coro,operation=operation,account_id=account_id);self._handlers[token]=(success,failure);return token
        except Exception as exc:self._error(exc);return None
    def _done(self,token,result):
        h=self._handlers.pop(token,None)
        if h and h[0]:
            try:h[0](result)
            except Exception as exc:
                _LOG.exception("Group operation result callback failed",exc_info=exc)
                self.toast_requested.emit("The operation finished, but this view could not refresh. Refresh the page and review Logs.","Warning")
    def _failed(self,token,account_id,message):
        h=self._handlers.pop(token,None)
        if not h:return
        if h[1]:
            try:h[1](account_id,self._friendly(message))
            except Exception as exc:
                _LOG.exception("Group operation failure callback failed",exc_info=exc)
                self.toast_requested.emit(self._friendly(message),"Warning")
        else:self._error(RuntimeError(self._friendly(message)))
    def _friendly(self,message):
        # Worker deliberately sends only exception text. Keep raw class names out of UI.
        if "not found" in message.lower():return "Telegram username was not found. Check the username or link and try again."
        return message or "Telegram group operation could not be completed."
    def _on_worker_finished(self):
        pending=dict(self._handlers);self._handlers.clear()
        for _token,(success,failure) in pending.items():
            if failure:
                try:failure(0,'The Telegram worker stopped unexpectedly.')
                except Exception:pass
        if pending:self.toast_requested.emit('The Telegram worker stopped. Pending operations were cancelled.','Warning');self.refresh()
    def _error(self,exc):message=str(exc) or "Cannot complete the group operation.";self.errorOccurred.emit(message);self.toast_requested.emit(message,"Error")
