from __future__ import annotations
from PySide6.QtCore import QPoint,QUrl,Signal
from PySide6.QtGui import QAction,QDesktopServices
from PySide6.QtWidgets import QFileDialog,QMenu,QMessageBox
from app.dialogs.add_group_dialog import AddGroupDialog
from app.dialogs.bulk_group_sync_dialog import BulkGroupSyncDialog
from app.dialogs.group_details_dialog import GroupDetailsDialog
from app.dialogs.group_discovery_dialog import GroupDiscoveryDialog
from app.models.group_table_model import GroupTableModel
from app.widgets.avatar_delegate import AvatarDelegate
from app.pages.base_table_page import BaseTablePage

class GroupsPage(BaseTablePage):
    toastRequested=Signal(str,str)
    def __init__(self,controller,parent=None,*,avatar_service=None):
        self.controller=controller;controller.flag=None;self.avatar_service=avatar_service
        super().__init__("page_groups","Groups",GroupTableModel(controller.groups()),"tbl_groups",[("btn_add_group","Add Group"),("btn_discover_groups","Discover My Groups"),("btn_resolve_group","Resolve Group"),("btn_sync_groups","Sync"),("btn_refresh_groups","Refresh"),("btn_more_group_actions","More ▾")],"le_search_groups",[("cmb_group_type_filter","Type",["Basic Group","Supergroup","Channel","Gigagroup","Forum"]),("cmb_group_access_filter","Access",["Public","Private","Access Denied","Not Joined"]),("cmb_group_role_filter","Role",["Member","Admin","Owner"]),("cmb_group_status_filter","Status",["Ready","Syncing","Access Denied","Not Joined","Unavailable","Error"]),("cmb_group_classification_filter","Classification",["Managed","Source","Target"])],parent)
        self.enable_database_mode(controller.pagination);
        for column in ["Select","ID","Freshness"]:
            if column in self.model.columns:self.table.setColumnHidden(self.model.columns.index(column),True)
        if self.avatar_service is not None and "Group" in self.model.columns:
            self.table.setItemDelegateForColumn(
                self.model.columns.index("Group"),
                AvatarDelegate(self.avatar_service, "group", "id", "title", self.table,
                               peer_id_attr="telegram_group_id", account_id_attr="primary_account_id",subtitle_column="Username"),
            )
            self.table.verticalHeader().setDefaultSectionSize(44)
        if "Username" in self.model.columns:self.table.setColumnHidden(self.model.columns.index("Username"),True)
        self.searchDebounced.connect(controller.set_search);self.filterChanged.connect(controller.set_filter);self.pageChanged.connect(controller.set_page);self.pageSizeChanged.connect(controller.set_page_size);controller.groupsChanged.connect(self._replace)
        self.action_buttons["btn_add_group"].clicked.connect(self.add_group);self.action_buttons["btn_discover_groups"].clicked.connect(self.discover);self.action_buttons["btn_resolve_group"].clicked.connect(self.add_group);self.action_buttons["btn_sync_groups"].clicked.connect(self.sync_selected);self.action_buttons["btn_refresh_groups"].clicked.connect(controller.refresh);self.action_buttons["btn_more_group_actions"].clicked.connect(self.more_menu);self.table.doubleClicked.connect(lambda:self.open_details());self.table.customContextMenuRequested.connect(self.context_menu)
        self.actions={}
        for obj,text in [("act_group_details","Open Details"),("act_group_sync","Sync Group"),("act_group_refresh_permissions","Refresh Permissions"),("act_group_assign_account","Add Account Mapping"),("act_group_set_primary","Set Primary Account"),("act_group_mark_source","Mark as Source"),("act_group_mark_target","Mark as Target"),("act_group_mark_managed","Mark as Managed"),("act_group_open_telegram","Open in Telegram"),("act_group_export","Export Groups"),("act_group_remove","Remove From Tool")]:a=QAction(text,self);a.setObjectName(obj);self.actions[obj]=a
        self.actions["act_group_details"].triggered.connect(self.open_details);self.actions["act_group_sync"].triggered.connect(self.sync_selected);self.actions["act_group_refresh_permissions"].triggered.connect(self.refresh_permissions);self.actions["act_group_assign_account"].triggered.connect(self.open_details);self.actions["act_group_set_primary"].triggered.connect(self.open_details);self.actions["act_group_mark_source"].triggered.connect(lambda:self.classify("source"));self.actions["act_group_mark_target"].triggered.connect(lambda:self.classify("target"));self.actions["act_group_mark_managed"].triggered.connect(lambda:self.classify("managed"));self.actions["act_group_open_telegram"].triggered.connect(self.open_telegram);self.actions["act_group_export"].triggered.connect(self.export_csv);self.actions["act_group_remove"].triggered.connect(self.remove_selected)
    def _replace(self,items):self.model.replace_rows(items);self.update_pagination(self.controller.pagination)
    def add_group(self):AddGroupDialog(self.controller,parent=self).exec()
    def discover(self):GroupDiscoveryDialog(self.controller,self,avatar_service=self.avatar_service).exec()
    def open_details(self):
        item=self.selected_item()
        if item:GroupDetailsDialog(self.controller,item.id,self,avatar_service=self.avatar_service).exec()
    def sync_selected(self):
        items=self.selected_items()
        if not items:return
        if len(items)==1:self.controller.sync_group(items[0].id)
        else:BulkGroupSyncDialog(self.controller,[x.id for x in items],self).exec()
    def refresh_permissions(self):
        item=self.selected_item()
        if not item:return
        mappings=self.controller.accounts_for_group(item.id);primary=next((m for m in mappings if m.is_primary),mappings[0] if mappings else None)
        if primary:self.controller.refresh_permissions(item.id,primary.account_id)
        else:self.toastRequested.emit("Add an authorized account mapping first.","Info")
    def classify(self,kind):
        item=self.selected_item()
        if not item:return
        current=bool(getattr(item,f"is_{kind}"));getattr(self.controller,f"set_{kind}")(item.id,not current)
    def open_telegram(self):
        item=self.selected_item()
        if not item:return
        if item.username:QDesktopServices.openUrl(QUrl(f"https://t.me/{item.username}"))
        else:self.toastRequested.emit("No stored public link is available for this private group. Private invite tokens are not retained.","Info")
    def remove_selected(self):
        item=self.selected_item()
        if not item:return
        summary=self.controller.removal_summary(item.id)
        if summary is None:return
        labels={
            "account_mappings":"account mappings","member_sources":"member source links","target_membership_states":"target membership checks",
            "member_exclusions":"target exclusions","member_sync_runs":"member sync history","member_target_actions":"invite/check history",
            "invite_links":"saved invite links","campaign_targets":"campaign target links","campaign_deliveries":"campaign delivery records",
            "template_links":"template links","jobs":"job references (kept, detached)","alerts":"alert references (kept, detached)","logs":"log references (kept, detached)",
        }
        linked=[f"• {labels.get(key,key.replace('_',' '))}: {count}" for key,count in summary.items() if int(count)>0]
        remove_related=bool(linked)
        if linked:
            message=(f"Remove the local group record '{item.title}' and these linked local records?\n\n"+"\n".join(linked)+"\n\nTelegram membership, the Telegram group, and its Telegram members are not changed. General jobs, alerts, and logs are kept but detached from this local group.")
        else:
            message=f"Remove '{item.title}' from this tool?\n\nTelegram membership and the Telegram group are not changed."
        if QMessageBox.question(self,"Remove Group From Tool",message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:
            self.controller.remove(item.id,remove_related=remove_related)
    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Groups","groups.csv","CSV Files (*.csv)")
        if path:self.controller.export_csv(path)
    def more_menu(self):self._menu(self.action_buttons["btn_more_group_actions"].mapToGlobal(self.action_buttons["btn_more_group_actions"].rect().bottomLeft()))
    def context_menu(self,pos:QPoint):self._menu(self.table.viewport().mapToGlobal(pos))
    def _menu(self,global_pos):
        m=QMenu(self);m.addAction(self.actions["act_group_details"]);m.addSeparator();m.addAction(self.actions["act_group_sync"]);m.addAction(self.actions["act_group_refresh_permissions"]);m.addSeparator();accounts=m.addMenu("Accounts");accounts.addAction(self.actions["act_group_assign_account"]);accounts.addAction(self.actions["act_group_set_primary"]);classification=m.addMenu("Classification");classification.addAction(self.actions["act_group_mark_source"]);classification.addAction(self.actions["act_group_mark_target"]);classification.addAction(self.actions["act_group_mark_managed"]);m.addSeparator();m.addAction(self.actions["act_group_open_telegram"]);m.addAction(self.actions["act_group_export"]);m.addSeparator();m.addAction(self.actions["act_group_remove"]);m.exec(global_pos)
