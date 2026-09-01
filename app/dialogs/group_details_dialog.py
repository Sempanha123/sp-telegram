from __future__ import annotations
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox,QDialog,QFormLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTabWidget,QTableView,QVBoxLayout,QWidget,QAbstractItemView
from app.dialogs.dialog_compat import *
from app.models.base_table_model import BaseTableModel
from app.dialogs.group_account_mapping_dialog import GroupAccountMappingDialog
from app.widgets.detail_header import DetailHeaderWidget
from app.utils.formatters import format_local_datetime
from app.utils.table_preferences import TablePreferenceManager
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout

class GroupDetailsDialog(QDialog):
    ACCOUNT_COLS=["Account","Role","Health","Post","Invite","Create Link","Approve Join","Primary","Last Verified","Status"]
    TARGET_MEMBER_COLS=["Member","Username","Telegram ID","Status","Joined / First Seen","Source","Last Sync"]
    TARGET_MEMBER_WIDTHS={"Member":190,"Username":170,"Telegram ID":140,"Status":150,"Joined / First Seen":165,"Source":190,"Last Sync":165}
    def __init__(self,controller,group_id:int,parent=None,member_controller=None,avatar_service=None):
        super().__init__(parent);self.controller=controller;self.member_controller=member_controller;self.avatar_service=avatar_service;self._table_layout=TableLayoutManager(self);self.group_id=group_id
        try:
            self.details=controller.details(group_id) or {}
        except Exception:
            self.details={}
        self.group=self.details.get("group")
        if self.group is None:
            # Invalid / deleted / no-longer-accessible group reference. Defer
            # the explanation until exec() so no queued modal callback can
            # outlive this already-rejected dialog.
            self.reject()
            return
        self.setWindowTitle(f"Group Details — {self.group.title}");self.resize(950,680);root=QVBoxLayout(self);root.setContentsMargins(20,20,20,16);root.setSpacing(12);root.addWidget(DetailHeaderWidget(self.group.title, f"@{self.group.username}" if self.group.username else "Telegram group", self.group.status.replace("_"," ").title(), self));self.tabs=QTabWidget();root.addWidget(self.tabs,1);self._overview();self._permissions();self._accounts();self._telegram_info();
        if self.group and self.group.is_target and self.member_controller:self._target_members()
        self._activity();self._errors();actions=QHBoxLayout();actions.addStretch();self.btn_refresh_group=QPushButton("Sync Group");self.btn_refresh_group.setObjectName("btn_refresh_group");self.btn_group_close=QPushButton("Close");self.btn_group_close.setObjectName("btn_group_close");actions.addWidget(self.btn_refresh_group);actions.addWidget(self.btn_group_close);root.addLayout(actions);self.btn_group_close.clicked.connect(self.accept);self.btn_refresh_group.clicked.connect(lambda:self.controller.sync_group(self.group_id,callback=lambda _:self.reload()))
    def exec(self):
        if self.group is None:
            QMessageBox.warning(
                self.parentWidget() or self,
                "Group Not Found",
                "This group no longer exists in the local database. It may have "
                "been removed, or its local record is no longer accessible.\n\n"
                "Refresh the group list and try again.",
            )
            return QDialog.DialogCode.Rejected
        return super().exec()

    def _tab_form(self,title):w=QWidget();f=QFormLayout(w);self.tabs.addTab(w,title);return f
    def _overview(self):
        f=self._tab_form("Overview");g=self.group
        for label,val in [("Name",g.title),("Telegram ID",g.telegram_group_id),("Username",f"@{g.username}" if g.username else "—"),("Type",g.group_type.replace("_"," ").title()),("Access",g.access_state.replace("_"," ").title()),("Status",g.status.replace("_"," ").title()),("Member Count",g.member_count),("Description",g.description or "—"),("Forum","Yes" if g.is_forum else "No"),("Broadcast","Yes" if g.is_broadcast else "No"),("Verified","Yes" if g.is_verified else "No"),("Source","Yes" if g.is_source else "No"),("Target","Yes" if g.is_target else "No"),("Managed","Yes" if g.is_managed else "No"),("Primary Account",g.account_name or "—"),("Last Sync",g.last_sync_at or "Never")]:f.addRow(label,QLabel(str(val)))
    def _permissions(self):
        w=QWidget();root=QVBoxLayout(w);top=QHBoxLayout();self.cmb_group_permission_account=QComboBox();self.cmb_group_permission_account.setObjectName("cmb_group_permission_account");self.btn_refresh_group_permissions=QPushButton("Refresh Permissions");self.btn_refresh_group_permissions.setObjectName("btn_refresh_group_permissions");top.addWidget(QLabel("Account"));top.addWidget(self.cmb_group_permission_account);top.addWidget(self.btn_refresh_group_permissions);root.addLayout(top);self.permission_form=QFormLayout();self.permission_labels={}
        for key,label in [("can_view","View"),("can_post","Post"),("can_send_media","Send Media"),("can_invite","Invite"),("can_manage","Manage"),("can_delete_messages","Delete Messages"),("can_pin_messages","Pin Messages"),("can_ban_users","Ban Users"),("can_add_admins","Add Admins"),("can_manage_call","Manage Calls"),("can_manage_topics","Manage Topics"),("can_manage_invite_links","Manage Invite Links"),("can_approve_join_requests","Approve Join Requests")]:q=QLabel("—");self.permission_labels[key]=q;self.permission_form.addRow(label,q)
        root.addLayout(self.permission_form);self.tabs.addTab(w,"Permissions");self.cmb_group_permission_account.currentIndexChanged.connect(self._show_permissions);self.btn_refresh_group_permissions.clicked.connect(self._refresh_permissions)
    def _accounts(self):
        w=QWidget();root=QVBoxLayout(w);self.accounts_model=BaseTableModel([],self.ACCOUNT_COLS);self.tbl_group_accounts=QTableView();self.tbl_group_accounts.setModel(self.accounts_model);self.tbl_group_accounts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self._table_layout.apply(self.tbl_group_accounts,self.ACCOUNT_COLS);root.addWidget(self.tbl_group_accounts,1);actions=QHBoxLayout();self.btn_group_add_account_mapping=QPushButton("Add Account Mapping");self.btn_group_add_account_mapping.setObjectName("btn_group_add_account_mapping");self.btn_group_refresh_account_mapping=QPushButton("Refresh Mapping");self.btn_group_refresh_account_mapping.setObjectName("btn_group_refresh_account_mapping");self.btn_group_remove_account_mapping=QPushButton("Remove Mapping");self.btn_group_remove_account_mapping.setObjectName("btn_group_remove_account_mapping");self.btn_group_set_primary_account=QPushButton("Set Primary");self.btn_group_set_primary_account.setObjectName("btn_group_set_primary_account");[actions.addWidget(x) for x in [self.btn_group_add_account_mapping,self.btn_group_refresh_account_mapping,self.btn_group_remove_account_mapping,self.btn_group_set_primary_account]];actions.addStretch();root.addLayout(actions);self.tabs.addTab(w,"Accounts");self.btn_group_add_account_mapping.clicked.connect(self._add_mapping);self.btn_group_refresh_account_mapping.clicked.connect(self.reload);self.btn_group_remove_account_mapping.clicked.connect(self._remove_mapping);self.btn_group_set_primary_account.clicked.connect(self._set_primary);self._load_accounts()
    def _telegram_info(self):
        f=self._tab_form("Telegram Info");g=self.group
        for label,val in [("Telegram Entity ID",g.telegram_group_id),("Username",g.username or "—"),("Entity Type",g.group_type),("Megagroup",bool(g.is_megagroup)),("Broadcast",bool(g.is_broadcast)),("Forum",bool(g.is_forum)),("Gigagroup",bool(g.is_gigagroup)),("Linked Discussion",g.linked_chat_id or "—"),("Verified",bool(g.is_verified)),("Scam Flag",bool(g.is_scam)),("Fake Flag",bool(g.is_fake))]:f.addRow(label,QLabel(str(val)))
    def _target_members(self):
        w=QWidget();root=QVBoxLayout(w);root.setContentsMargins(8,8,8,8);root.setSpacing(8)
        note=QLabel("Statuses come from verified target-member synchronization or explicit target checks. UNKNOWN remains distinct from NOT MEMBER.");note.setWordWrap(True);note.setProperty("secondary",True);root.addWidget(note)
        self.target_members_model=BaseTableModel([],self.TARGET_MEMBER_COLS,self)
        settings=QSettings();prefs=TablePreferenceManager(settings,self)
        privacy=str(settings.value("ui/privacy_mode",False)).lower() in {"1","true","yes"}
        self.target_members_model.set_privacy_mode(privacy)
        self.target_members_model.set_display_preferences(mask_telegram_ids=bool(prefs.global_value("mask_telegram_ids",False)),mask_usernames=bool(prefs.global_value("mask_usernames",False)))
        self.tbl_group_target_members=QTableView();self.tbl_group_target_members.setObjectName("tbl_target_members");self.tbl_group_target_members.setModel(self.target_members_model);self.tbl_group_target_members.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.tbl_group_target_members.verticalHeader().setVisible(False);self.tbl_group_target_members.verticalHeader().setDefaultSectionSize(42);self._table_layout.apply(self.tbl_group_target_members,self.TARGET_MEMBER_COLS,overrides={k:ColumnLayout(v,max(80,v-30)) for k,v in self.TARGET_MEMBER_WIDTHS.items()});root.addWidget(self.tbl_group_target_members,1)
        self.target_member_prefs=prefs;prefs.register(self.tbl_group_target_members,self.TARGET_MEMBER_COLS,default_widths=self.TARGET_MEMBER_WIDTHS)
        bar=QHBoxLayout();self.btn_refresh_group_target_members=QPushButton("Refresh");self.btn_refresh_group_target_members.setObjectName("btn_refresh_group_target_members");bar.addWidget(self.btn_refresh_group_target_members);bar.addStretch();root.addLayout(bar);self.btn_refresh_group_target_members.clicked.connect(self._load_target_members)
        self.tabs.addTab(w,"Members");self._load_target_members()
    def _load_target_members(self):
        if not getattr(self,"member_controller",None) or not hasattr(self,"target_members_model"):return
        rows=[]
        for row in self.member_controller.target_member_rows(self.group_id,1000) or []:
            rows.append({"Member":row["display_name"] or (f"@{row['username']}" if row["username"] else f"Member {row['member_id']}"),"Username":f"@{row['username']}" if row["username"] else "—","Telegram ID":row["telegram_user_id"],"Status":str(row["state"] or "UNKNOWN").replace("_"," ").title(),"Joined / First Seen":format_local_datetime(row["first_seen_at"]),"Source":row["sources"] or "—","Last Sync":format_local_datetime(row["last_checked_at"])})
        self.target_members_model.replace_rows(rows)
    def _activity(self):
        self.activity_model=BaseTableModel(self.details.get("logs",[]),["created_at","action","message"]);tbl=QTableView();tbl.setModel(self.activity_model);self.tabs.addTab(tbl,"Activity")
    def _errors(self):
        f=self._tab_form("Errors");g=self.group;f.addRow("Code",QLabel(g.last_error_code or "—"));f.addRow("Message",QLabel(g.last_error_message or "—"));f.addRow("At",QLabel(g.last_error_at or "—"))
    def _load_accounts(self):
        mappings=self.controller.accounts_for_group(self.group_id);self._mappings=mappings;self.cmb_group_permission_account.blockSignals(True);self.cmb_group_permission_account.clear();rows=[]
        for m in mappings:
            self.cmb_group_permission_account.addItem(m.account_name,m.account_id);rows.append({"Account":m.account_name,"Role":m.role.title(),"Health":str(getattr(m,"health_status","UNKNOWN") or "UNKNOWN").replace("_"," ").title(),"Post":self._cap(m.can_post),"Invite":self._cap(m.can_invite),"Create Link":self._cap(m.can_manage_invite_links),"Approve Join":self._cap(getattr(m,"can_approve_join_requests",None)),"Primary":"Yes" if m.is_primary else "No","Last Verified":m.last_permission_check_at or "Never","Status":m.last_error_code or "Ready"})
        self.cmb_group_permission_account.blockSignals(False);self.accounts_model.replace_rows(rows);self._show_permissions()
    def _show_permissions(self):
        aid=self.cmb_group_permission_account.currentData();m=next((x for x in getattr(self,"_mappings",[]) if x.account_id==aid),None)
        for key,label in self.permission_labels.items():label.setText(self._cap(getattr(m,key,None)) if m else "—")
    @staticmethod
    def _cap(v):return "Unknown" if v is None else "✅" if bool(v) else "❌"
    def _refresh_permissions(self):
        aid=self.cmb_group_permission_account.currentData()
        if aid:self.controller.refresh_permissions(self.group_id,int(aid),lambda _:self.reload())
    def _selected_mapping(self):
        rows=self.tbl_group_accounts.selectionModel().selectedRows()
        if not rows:return None
        return self._mappings[rows[0].row()]
    def _add_mapping(self):
        d=GroupAccountMappingDialog(self.controller,self.group,self)
        if d.exec():self.reload()
    def _remove_mapping(self):
        m=self._selected_mapping()
        if m and QMessageBox.question(self,"Remove Mapping",f"Remove {m.account_name} from this local group mapping?")==QMessageBox.StandardButton.Yes:self.controller.remove_account_mapping(self.group_id,m.account_id);self.reload()
    def _set_primary(self):
        m=self._selected_mapping()
        if m:self.controller.set_primary_account(self.group_id,m.account_id);self.reload()
    def reload(self):
        self.details=self.controller.details(self.group_id) or self.details;self.group=self.details.get("group",self.group);self._load_accounts();self._load_target_members()

# Add compatibility attributes for older PySide6 versions
if not hasattr(GroupDetailsDialog, 'Accepted'):
    GroupDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(GroupDetailsDialog, 'Rejected'):
    GroupDetailsDialog.Rejected = QDialog.DialogCode.Rejected
