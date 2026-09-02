from __future__ import annotations
from PySide6.QtWidgets import QMenu,QMessageBox,QPushButton
from app.dialogs.add_group_dialog import AddGroupDialog
from app.dialogs.group_details_dialog import GroupDetailsDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.avatar_delegate import AvatarDelegate

class SourceGroupsPage(BaseTablePage):
    COLUMNS=["Group","Username","Type","Access","Members","Primary Account","Account Role","Member Access","Stored Members","Last Member Sync","Sync Status","Last Sync","Status"]
    def __init__(self,controller,member_controller=None,parent=None,*,avatar_service=None):
        self.controller=controller;self.member_controller=member_controller;self.avatar_service=avatar_service;items,total=controller.get_scoped("source",1,100);controller.pagination.total_items=total
        actions=[("btn_add_source_group","Add Source Group"),("btn_sync_source_groups","Sync Metadata"),("btn_refresh_source_groups","Refresh"),("btn_source_group_details","Details"),("btn_remove_source_group_flag","Remove Source Flag"),("btn_sync_source_members","Sync Members"),("btn_view_source_members","View Members"),("btn_source_member_history","Sync History"),("btn_collect_selected_source","Sync Members")]
        super().__init__("page_source_groups","Source Groups",BaseTableModel(self._rows(items),self.COLUMNS),"tbl_source_groups",actions,None,[],parent);self.enable_database_mode(controller.pagination)
        if self.avatar_service is not None:
            self.table.setItemDelegateForColumn(0,AvatarDelegate(self.avatar_service,"group","_id","Group",self.table,peer_id_attr="_telegram_id",account_id_attr="_account_id",subtitle_column="Username"));self.table.verticalHeader().setDefaultSectionSize(44)
        if "Username" in self.model.columns:self.table.setColumnHidden(self.model.columns.index("Username"),True)
        self.action_buttons["btn_add_source_group"].clicked.connect(lambda:AddGroupDialog(controller,classification="source",parent=self).exec());self.action_buttons["btn_sync_source_groups"].clicked.connect(self.sync);self.action_buttons["btn_refresh_source_groups"].clicked.connect(self.refresh_from_controller);self.action_buttons["btn_source_group_details"].clicked.connect(self.details);self.action_buttons["btn_remove_source_group_flag"].clicked.connect(self.remove_flag)
        self.action_buttons["btn_sync_source_members"].clicked.connect(self.member_sync);self.action_buttons["btn_collect_selected_source"].clicked.connect(self.member_sync);self.action_buttons["btn_view_source_members"].clicked.connect(self.view_members);self.action_buttons["btn_source_member_history"].clicked.connect(self.history)
        # Keep the high-frequency actions visible and move selection-specific
        # operations into one compact menu so 1180px layouts do not clip labels.
        self.btn_source_more_actions=QPushButton("More ▾");self.btn_source_more_actions.setObjectName("btn_source_more_actions");self.btn_source_more_actions.setProperty("role","ghost");self.page_header.add_action(self.btn_source_more_actions)
        self.menu_source_more=QMenu(self.btn_source_more_actions)
        menu_actions=(("btn_sync_source_members","Sync Members",self.member_sync),("btn_view_source_members","View Members",self.view_members),("btn_source_member_history","Sync History",self.history),("btn_remove_source_group_flag","Remove Source Flag",self.remove_flag))
        for name,label,callback in menu_actions:
            self.action_buttons[name].hide();self.menu_source_more.addAction(label,callback)
        self.action_buttons["btn_collect_selected_source"].hide()
        self.btn_source_more_actions.setMenu(self.menu_source_more)
        if not member_controller:
            for name in ["btn_sync_source_members","btn_collect_selected_source","btn_view_source_members","btn_source_member_history"]:self.action_buttons[name].setEnabled(False)
    def _rows(self,items):
        out=[]
        for g in items:
            stats=self.member_controller.source_stats(g.id) if self.member_controller else {};mapping=stats.get("mapping") if stats else None
            out.append({"Group":g.title,"Username":f"@{g.username}" if g.username else "—","Type":g.group_type.replace("_"," ").title(),"Access":g.access_state.replace("_"," ").title(),"Members":g.member_count,"Primary Account":g.account_name or "—","Account Role":g.role.title(),"Member Access":(stats.get("availability") or "UNKNOWN").replace("_"," ").title() if stats else "Unknown","Stored Members":stats.get("stored",0) if stats else 0,"Last Member Sync":stats.get("last_sync") or "Never" if stats else "Never","Sync Status":(stats.get("status") or "NEVER_SYNCED").replace("_"," ").title() if stats else "Never Synced","Last Sync":g.last_sync_at or "Never","Status":g.status.replace("_"," ").title(),"_id":g.id,"_telegram_id":g.telegram_group_id,"_account_id":g.primary_account_id})
        return out
    def _id(self):r=self.selected_row();return r.get("_id") if r else None
    def sync(self):
        gid=self._id()
        if gid:self.controller.sync_group(gid)
    def details(self):
        gid=self._id()
        if gid:GroupDetailsDialog(self.controller,gid,self,avatar_service=self.avatar_service).exec()
    def remove_flag(self):
        gid=self._id()
        if gid and QMessageBox.question(self,"Source Group","Remove the Source classification? The Telegram group remains saved.")==QMessageBox.StandardButton.Yes:self.controller.set_source(gid,False);self.refresh_from_controller()
    def member_sync(self):
        gid=self._id()
        if not gid or not self.member_controller:return
        mappings=self.member_controller.accounts_for_group(gid);primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
        if not primary:QMessageBox.warning(self,"Member Sync","Map an authorized account to this Source Group first.");return
        if QMessageBox.question(self,"Sync Members",f"Start an authorized member sync using {primary.account_name or 'the primary account'}?\n\nOnly participants Telegram exposes to this account will be read. Hidden lists will not be bypassed.")==QMessageBox.StandardButton.Yes:self.member_controller.on_start_sync(gid,primary.account_id)
    def view_members(self):
        gid=self._id()
        if gid and self.member_controller:self.member_controller.set_source(gid);QMessageBox.information(self,"Source Members","The Member Pool filter has been set to this source. Open Member Pool to view the records.")
    def history(self):
        gid=self._id()
        if not gid or not self.member_controller:return
        runs=self.member_controller.service.sync_runs.get_recent(gid,20) if self.member_controller.service.sync_runs else []
        text="\n".join(f"{r.started_at} • {r.status} • {r.processed} processed • {r.inserted} new" for r in runs) or "No member sync history yet."
        QMessageBox.information(self,"Member Sync History",text)
    def refresh_from_controller(self):
        items,total=self.controller.get_scoped("source",1,self.controller.pagination.page_size);self.model.replace_rows(self._rows(items));self.controller.pagination.total_items=total;self.update_pagination(self.controller.pagination)
