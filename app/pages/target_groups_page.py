from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication,QDialog,QMenu,QMessageBox,QPushButton
from app.dialogs.add_group_dialog import AddGroupDialog
from app.dialogs.group_details_dialog import GroupDetailsDialog
from app.dialogs.create_target_invite_link_dialog import CreateTargetInviteLinkDialog
from app.dialogs.mass_add_to_target_dialog import MassAddToTargetDialog
from app.dialogs.target_members_dialog import TargetMembersDialog
from app.dialogs.join_requests_dialog import JoinRequestsDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage

class TargetGroupsPage(BaseTablePage):
    campaignRequested=Signal(int)
    COLUMNS=["Target","Username","Members","Primary Account","Role","Can Post","Can Invite","Can Manage","Known Existing Members","Unknown Status","Last Member Check","Last Sync","Status"]
    def __init__(self,controller,member_controller=None,parent=None,*,avatar_service=None):
        self.controller=controller;self.member_controller=member_controller;self.avatar_service=avatar_service;items,total=controller.get_scoped("target",1,100);controller.pagination.total_items=total
        super().__init__("page_target_groups","Target Groups",BaseTableModel(self._rows(items),self.COLUMNS),"tbl_target_groups",[("btn_add_target_group","Add Target Group"),("btn_sync_target_groups","Sync Metadata"),("btn_assign_target_account","Assign Account"),("btn_target_group_details","Details"),("btn_remove_target_group_flag","Remove Target Flag"),("btn_sync_target_members","Sync Existing Status"),("btn_view_target_members","View Target Members"),("btn_create_target_invite_link","Create Invite Link"),("btn_copy_target_invite_link","Copy Invite Link"),("btn_view_join_requests","Join Requests"),("btn_create_target_campaign","Create Campaign"),("btn_manage_invite_links","Invite Links"),("btn_mass_add_to_target","Mass Add to Target")],None,[],parent);self.enable_database_mode(controller.pagination)
        self.action_buttons["btn_add_target_group"].clicked.connect(lambda:AddGroupDialog(controller,classification="target",parent=self).exec());self.action_buttons["btn_sync_target_groups"].clicked.connect(self.sync);self.action_buttons["btn_assign_target_account"].clicked.connect(self.details);self.action_buttons["btn_target_group_details"].clicked.connect(self.details);self.action_buttons["btn_remove_target_group_flag"].clicked.connect(self.remove_flag);self.action_buttons["btn_sync_target_members"].clicked.connect(self.sync_members);self.action_buttons["btn_view_target_members"].clicked.connect(self.view_members);self.action_buttons["btn_create_target_invite_link"].clicked.connect(self.create_invite_link);self.action_buttons["btn_copy_target_invite_link"].clicked.connect(self.copy_invite_link);self.action_buttons["btn_view_join_requests"].clicked.connect(self.view_join_requests);self.action_buttons["btn_create_target_campaign"].clicked.connect(self.create_campaign);self.action_buttons["btn_mass_add_to_target"].clicked.connect(self.mass_add_to_target)
        # Historical objectName stays hidden for compatibility.  The production
        # actions below manage invite links/join requests only; they never perform
        # automatic member invitations or account rotation.
        self.action_buttons["btn_manage_invite_links"].setEnabled(False);self.action_buttons["btn_manage_invite_links"].hide()
        self._invite_links={}
        self.action_buttons["btn_copy_target_invite_link"].setEnabled(False)
        self.btn_target_more_actions=QPushButton("More ▾");self.btn_target_more_actions.setObjectName("btn_target_more_actions");self.btn_target_more_actions.setProperty("role","ghost");self.page_header.add_action(self.btn_target_more_actions)
        self.menu_target_more=QMenu(self.btn_target_more_actions)
        menu_actions=(("btn_assign_target_account","Assign Account",self.details),("btn_sync_target_members","Sync Existing Status",self.sync_members),("btn_view_target_members","View Target Members",self.view_members),("btn_copy_target_invite_link","Copy Invite Link",self.copy_invite_link),("btn_view_join_requests","Join Requests",self.view_join_requests),("btn_remove_target_group_flag","Remove Target Flag",self.remove_flag))
        for name,label,callback in menu_actions:
            self.action_buttons[name].hide();self.menu_target_more.addAction(label,callback)
        self.btn_target_more_actions.setMenu(self.menu_target_more)
        if not member_controller:
            self.action_buttons["btn_sync_target_members"].setEnabled(False);self.action_buttons["btn_view_target_members"].setEnabled(False)
    def _rows(self,items):
        out=[]
        for g in items:
            stats=self.member_controller.target_stats(g.id) if self.member_controller else {};mapping=stats.get("mapping") if stats else None;last=mapping.member_list_checked_at if mapping else None
            out.append({"Target":g.title,"Username":f"@{g.username}" if g.username else "—","Members":g.member_count,"Primary Account":g.account_name or "—","Role":g.role.title(),"Can Post":"—" if g.can_post is None else bool(g.can_post),"Can Invite":"—" if g.can_invite is None else bool(g.can_invite),"Can Manage":"—" if g.can_manage is None else bool(g.can_manage),"Known Existing Members":stats.get("existing",0) if stats else 0,"Unknown Status":stats.get("unknown",0) if stats else 0,"Last Member Check":last or "Never","Last Sync":g.last_sync_at or "Never","Status":g.status.replace("_"," ").title(),"_id":g.id})
        return out
    def _id(self):r=self.selected_row();return r.get("_id") if r else None
    def sync(self):
        gid=self._id()
        if gid:self.controller.sync_group(gid)
    def details(self):
        gid=self._id()
        if gid:GroupDetailsDialog(self.controller,gid,self,member_controller=self.member_controller,avatar_service=self.avatar_service).exec()
    def remove_flag(self):
        gid=self._id()
        if gid and QMessageBox.question(self,"Target Group","Remove the Target classification? The Telegram group remains saved.")==QMessageBox.StandardButton.Yes:self.controller.set_target(gid,False);self.refresh_from_controller()
    def create_campaign(self):
        gid=self._id()
        if gid:self.campaignRequested.emit(int(gid))
    def _primary_mapping(self,gid):
        mappings=self.controller.accounts_for_group(gid) or []
        return next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
    def _require_invite_admin(self,gid):
        mapping=self._primary_mapping(gid)
        if not mapping:
            QMessageBox.warning(self,"Target Invite Link","Map an authorized account to this target first.");return None
        if str(mapping.access_state or "UNKNOWN").upper() in {"ACCESS_DENIED","NOT_JOINED","UNAVAILABLE"}:
            QMessageBox.warning(self,"Target Invite Link","The primary account does not currently have access to this target.");return None
        if not bool(mapping.can_manage_invite_links):
            QMessageBox.warning(self,"Target Invite Link","The primary account does not have invite-link permission for this target.");return None
        return mapping
    def create_invite_link(self):
        gid=self._id()
        if not gid:return
        mappings=[m for m in (self.controller.accounts_for_group(gid) or []) if str(getattr(m,"access_state","UNKNOWN") or "UNKNOWN").upper() not in {"ACCESS_DENIED","NOT_JOINED","UNAVAILABLE","NO_ACCESS","BANNED","LEFT"}]
        if not mappings:
            QMessageBox.warning(self,"Target Invite Link","Map an authorized account with target access first.");return
        permitted=[m for m in mappings if bool(getattr(m,"can_manage_invite_links",0))]
        preferred=permitted or mappings
        primary=next((m for m in preferred if bool(getattr(m,"is_primary",0))),preferred[0])
        group=self.controller.service.repository.get_by_id(gid)
        dialog=CreateTargetInviteLinkDialog(group.title if group else "Target Group",self,accounts=mappings,selected_account_id=int(primary.account_id))
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        options=dialog.options();account_id=options.pop("account_id",None)
        if not account_id:
            QMessageBox.warning(self,"Target Invite Link","No authorized account with invite-link permission is available.");return
        button=self.action_buttons["btn_create_target_invite_link"];button.setEnabled(False);button.setText("Creating…")
        token=self.controller.create_target_invite_link(gid,int(account_id),callback=lambda r:self._invite_created(gid,r),failure_callback=self._invite_failed,**options)
        if token is None:
            self._invite_failed("Invite-link creation could not be queued. Check the Telegram runtime and try again.")
    def _invite_failed(self,message=None):
        button=self.action_buttons["btn_create_target_invite_link"];button.setEnabled(True);button.setText("Create Invite Link")
        if message:
            QMessageBox.warning(self,"Target Invite Link",str(message))
    def _invite_created(self,gid,result):
        button=self.action_buttons["btn_create_target_invite_link"];button.setEnabled(True);button.setText("Create Invite Link")
        payload=result or {}
        if not bool(payload.get("success",True)):
            QMessageBox.warning(self,"Target Invite Link",str(payload.get("user_message") or payload.get("message") or "Invite link could not be created."));return
        link=str(payload.get("link") or "")
        if not link:
            QMessageBox.warning(self,"Target Invite Link","Telegram did not return an invite link.");return
        self._invite_links[int(gid)]=link
        self.action_buttons["btn_copy_target_invite_link"].setEnabled(True)
        QApplication.clipboard().setText(link)
        QMessageBox.information(self,"Target Invite Link","A join-request invite link was created and copied to the clipboard.\n\nNo member was automatically invited.")
    def copy_invite_link(self):
        gid=self._id();link=self._invite_links.get(int(gid)) if gid else None
        if gid and not link:
            rows=self.controller.active_target_invite_links(int(gid))
            link=str((rows[0] if rows else {}).get("invite_link") or "")
            if link:self._invite_links[int(gid)]=link
        if not link:
            QMessageBox.information(self,"Target Invite Link","Create an invite link for this target first.");return
        QApplication.clipboard().setText(link);self.controller.toast_requested.emit("Invite link copied to clipboard.","Success")
    def view_join_requests(self):
        gid=self._id()
        if not gid:return
        mapping=self._require_invite_admin(gid)
        if not mapping:return
        group=self.controller.service.repository.get_by_id(gid)
        JoinRequestsDialog(self.controller,gid,int(mapping.account_id),group.title if group else "Target Group",self).exec()
    def sync_members(self):
        gid=self._id()
        if not gid or not self.member_controller:return
        mappings=self.member_controller.accounts_for_group(gid);primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
        if not primary:QMessageBox.warning(self,"Target Member Status","Map an authorized account to this target first.");return
        if QMessageBox.question(self,"Target Member Status","Read the accessible target participant list to mark known local members as ALREADY MEMBER?\n\nThis does not invite or add anyone.")==QMessageBox.StandardButton.Yes:self.member_controller.on_sync_target(gid,primary.account_id,lambda _r:self.refresh_from_controller())
    def view_members(self):
        gid=self._id()
        if gid and self.member_controller:
            group=self.controller.service.repository.get_by_id(gid)
            TargetMembersDialog(self.member_controller,int(gid),group.title if group else "Target Group",self).exec()
    def mass_add_to_target(self):
        gid=self._id()
        if not gid or not self.member_controller:return
        MassAddToTargetDialog(self.member_controller,target_group_id=int(gid),parent=self).exec()
    def refresh_from_controller(self):
        items,total=self.controller.get_scoped("target",1,self.controller.pagination.page_size);self.model.replace_rows(self._rows(items));self.controller.pagination.total_items=total;self.update_pagination(self.controller.pagination)

    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        invite=feature_gate.has_feature(FeatureKey.INVITE_LINK)
        sync=feature_gate.has_feature(FeatureKey.TARGET_MEMBER_SYNC)
        direct=feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE)
        self.action_buttons["btn_create_target_invite_link"].setEnabled(invite)
        self.action_buttons["btn_create_target_invite_link"].setToolTip("Basic managed invite-link workflow is not available on the current plan." if not invite else "")
        self.action_buttons["btn_sync_target_members"].setEnabled(sync and bool(self.member_controller))
        self.action_buttons["btn_sync_target_members"].setToolTip("Target member sync requires SP Telegram Pro or SP Telegram Ultimate." if not sync else "")
        self.action_buttons["btn_mass_add_to_target"].setEnabled(direct and bool(self.member_controller))
        self.action_buttons["btn_mass_add_to_target"].setToolTip("Mass Add to Target requires SP Telegram Ultimate." if not direct else "")
        return True
