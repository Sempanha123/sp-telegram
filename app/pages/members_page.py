from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,QCheckBox,QDialog,QFileDialog,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QMenu,QMessageBox,
    QPushButton,QWidget,QSizePolicy,
)

from app.dialogs.smart_add_members_dialog import SmartAddMembersDialog
from app.dialogs.mass_add_to_target_dialog import MassAddToTargetDialog
from app.dialogs.member_details_dialog import MemberDetailsDialog
from app.dialogs.member_pool_cleanup_dialog import ClearEntireMemberPoolDialog
from app.dialogs.member_tag_manager_dialog import MemberTagManagerDialog
from app.dialogs.target_preparation_dialog import TargetPreparationDialog
from app.models.member_table_model import MemberTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.avatar_delegate import AvatarDelegate
from app.widgets.select_all_header import SelectAllHeader
from app.widgets.table_checkbox_delegate import TableCheckBoxDelegate


class MembersPage(BaseTablePage):
    openCollectorRequested = Signal()
    privacyModeDisableRequested = Signal()

    DEFAULT_WIDTHS={
        "Select":44,"Telegram ID":150,"Username":260,"Name":210,"Sources":210,"Eligibility":145,
        "Consent":140,"Target Status":155,"Blacklist":100,"Bot":80,"Premium":95,"First Seen":175,
        "Last Seen":175,"Tags":190,
    }

    def __init__(self,controller,group_controller=None,parent=None,*,avatar_service=None):
        self.controller=controller;self.group_controller=group_controller;self.avatar_service=avatar_service
        sources=[f"{g.id} — {g.title}" for g in controller.all_source_groups()]
        targets=[f"{g.id} — {g.title}" for g in controller.target_groups()]
        tags=controller.tags()
        actions=[
            ("btn_import_members","Import"),("btn_export_members","Export"),("btn_member_sync","Member Sync"),
            ("btn_refresh_members","Refresh"),
            ("btn_prepare_target","Prepare for Target"),("btn_invite_to_target","Add to Group"),
            ("btn_mass_add_to_target","Advanced Add Many"),
            ("btn_member_tags","Tags"),("btn_member_eligibility","Eligibility"),("btn_member_blacklist","Blacklist"),
            ("btn_member_more","More"),("btn_view_member","View Member"),("btn_add_member_tag","Add Tag"),
            ("btn_add_to_blacklist","Blacklist"),("btn_remove_from_blacklist","Remove Exclusion"),
            ("btn_mark_eligible","Mark Eligible"),("btn_mark_do_not_contact","Do Not Contact"),
        ]
        filters=[
            ("cmb_member_source","Source",sources),
            ("cmb_member_status","Eligibility",["Eligible","Unknown","Excluded","Do Not Contact","Manual Review","Bot","Deleted Account"]),
            ("cmb_member_consent","Consent",["Unknown","Opted In","Approved","Declined","Revoked"]),
            ("cmb_member_target","Target Group",targets),
            ("cmb_member_tag","Tag",tags),("cmb_member_bot_filter","Bot",["Humans","Bots"]),
            ("cmb_member_blacklist_filter","Blacklist",["Not Blacklisted","Blacklisted"]),
        ]
        super().__init__("page_members","Member Pool",MemberTableModel(controller.members()),"tbl_members",actions,"le_search_members",filters,parent)
        self.enable_database_mode(controller.pagination)

        # Replace the default header with a page-local Select All Visible checkbox.
        header=SelectAllHeader(Qt.Orientation.Horizontal,self.table);self.table.setHorizontalHeader(header);header.setSectionsMovable(True);header.setMinimumSectionSize(60)
        self.table.setItemDelegateForColumn(0, TableCheckBoxDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(44)
        if "ID" in self.model.columns:self.table.setColumnHidden(self.model.columns.index("ID"),True)
        if "Select" in self.model.columns:self.table.setColumnWidth(self.model.columns.index("Select"),44)
        if self.avatar_service is not None and "Name" in self.model.columns:
            self.table.setItemDelegateForColumn(
                self.model.columns.index("Name"),
                AvatarDelegate(self.avatar_service, "member", "id", "first_name", self.table,
                               peer_id_attr="telegram_user_id", account_id_attr="account_id"),
            )
        self._configure_member_columns()

        self.set_empty_state("No members found","Members synced from your authorized source groups will appear here.")
        self.empty_state.set_action("Open Collector", self.openCollectorRequested.emit, primary=True)
        self.searchDebounced.connect(controller.set_search);self.filterChanged.connect(controller.set_filter)
        self.pageChanged.connect(lambda p:setattr(controller.pagination,"page",p) or controller.refresh())
        self.pageSizeChanged.connect(lambda n:(setattr(controller.pagination,"page_size",n),setattr(controller.pagination,"page",1),controller.refresh()))
        controller.membersChanged.connect(self._replace)

        self._build_filter_options()
        self._build_privacy_notice()
        self._build_target_summary()
        self._build_selection_bar()
        self._build_actions()

        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.model.checkedChanged.connect(self._selection_changed)
        self.chk_exclude_blacklist.toggled.connect(controller.set_exclude_blacklist)
        self.chk_exclude_existing.toggled.connect(controller.set_exclude_existing)
        self.chk_only_with_username.toggled.connect(controller.set_only_username)
        self.chk_only_eligible.toggled.connect(controller.set_only_eligible)
        self.cmb_member_target.currentTextChanged.connect(self._target_changed)

        self.action_buttons["btn_member_sync"].clicked.connect(self.openCollectorRequested.emit)
        self.action_buttons["btn_refresh_members"].clicked.connect(self.refresh)
        self.action_buttons["btn_view_member"].clicked.connect(self.view)
        self.action_buttons["btn_add_member_tag"].clicked.connect(self.add_tag)
        self.action_buttons["btn_add_to_blacklist"].clicked.connect(lambda:self._member_action(controller.blacklist))
        self.action_buttons["btn_remove_from_blacklist"].clicked.connect(lambda:self._member_action(controller.unblacklist))
        self.action_buttons["btn_mark_eligible"].clicked.connect(lambda:self._member_action(controller.mark_eligible))
        self.action_buttons["btn_mark_do_not_contact"].clicked.connect(self.mark_dnc)
        self.action_buttons["btn_import_members"].clicked.connect(self.import_csv)
        self.action_buttons["btn_export_members"].clicked.connect(self.export_csv)
        self.action_buttons["btn_member_tags"].clicked.connect(self.bulk_add_tag)
        self.action_buttons["btn_member_eligibility"].clicked.connect(self.eligibility_menu)
        self.action_buttons["btn_member_blacklist"].clicked.connect(self.blacklist_menu)
        self.action_buttons["btn_prepare_target"].clicked.connect(self.prepare_for_target)
        self.action_buttons["btn_invite_to_target"].clicked.connect(self.invite_to_target)
        self.action_buttons["btn_mass_add_to_target"].clicked.connect(self.mass_add_to_target)
        self.action_buttons["btn_member_more"].clicked.connect(self.show_more)
        self.table.doubleClicked.connect(lambda _i:self.view());self.table.customContextMenuRequested.connect(self.context_menu)

        self._load_member_ui_preferences()
        self._target_changed()
        self._selection_changed()
        self._apply_simple_member_pool_ui()

    def _apply_simple_member_pool_ui(self):
        self._simple_member_pool_ui=True

        # Old/duplicate paths are hidden from normal users.
        for name in (
            "btn_prepare_target",
            "btn_mass_add_to_target",
            "btn_member_more",
            "btn_member_tags",
            "btn_member_eligibility",
            "btn_member_blacklist",
        ):
            button=self.action_buttons.get(name)
            if button is not None:
                button.hide()

        add_button=self.action_buttons.get("btn_invite_to_target")
        if add_button is not None:
            add_button.setText("Add Selected to Group")
            add_button.setToolTip(
                "Add the exact members you selected. "
                "For automatic Source → Target transfer, use Flow Studio."
            )

        sync_button=self.action_buttons.get("btn_member_sync")
        if sync_button is not None:
            sync_button.setText("Sync Members")
            sync_button.setToolTip("Collect or refresh Source Group members.")

        if hasattr(self,"btn_selection_dnc"):
            self.btn_selection_dnc.hide()

        # Smart Add now performs target checks itself.
        if hasattr(self,"target_summary"):
            self.target_summary.hide()

        # Default Member Pool only needs Search + Source + Target.
        for obj in (
            "cmb_member_status",
            "cmb_member_consent",
            "cmb_member_tag",
            "cmb_member_bot_filter",
            "cmb_member_blacklist_filter",
        ):
            combo=self.filter_boxes.get(obj)
            if combo is not None:
                host=combo.parentWidget()
                if host is not None:
                    host.hide()
                else:
                    combo.hide()

        for name in (
            "chk_exclude_blacklist",
            "chk_exclude_existing",
            "chk_only_with_username",
            "chk_only_eligible",
        ):
            widget=getattr(self,name,None)
            if widget is not None:
                widget.hide()

        # Remove duplicate right-click surface. Double-click still opens details.
        try:
            self.table.customContextMenuRequested.disconnect(self.context_menu)
        except (TypeError,RuntimeError):
            pass
        self.table.setToolTip("Select with checkboxes. Double-click a row to view details.")

    def _configure_member_columns(self):
        header=self.table.horizontalHeader()
        for name,width in self.DEFAULT_WIDTHS.items():
            if name not in self.model.columns:continue
            col=self.model.columns.index(name)
            header.setSectionResizeMode(col,QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col,width)
        for name,minw in {"Eligibility":110,"Consent":110,"Target Status":125,"Sources":140,"Username":130,"Name":140}.items():
            if name in self.model.columns:self.table.setColumnWidth(self.model.columns.index(name),max(minw,self.table.columnWidth(self.model.columns.index(name))))

    def _load_member_ui_preferences(self):
        p=self.table_preferences
        try:self.controller.pagination.page_size=int(p.global_value("rows_per_page",100))
        except Exception:pass
        self.model.set_display_preferences(mask_telegram_ids=bool(p.global_value("mask_telegram_ids",False)),mask_usernames=bool(p.global_value("mask_usernames",False)),mask_display_names=bool(p.global_value("mask_display_names",False)))
        density=str(p.global_value("row_density","Comfortable"));self.table.verticalHeader().setDefaultSectionSize(40 if density.lower()=="compact" else 44)

    def refresh_table_preferences(self):
        super().refresh_table_preferences();self._load_member_ui_preferences();self._target_changed(refresh=False)

    def _build_filter_options(self):
        row=QWidget();lay=QHBoxLayout(row);lay.setContentsMargins(0,0,0,0);lay.setSpacing(14)
        for obj,text in [("chk_exclude_blacklist","Exclude blacklist"),("chk_exclude_existing","Exclude existing in selected target"),("chk_only_with_username","Only with username"),("chk_only_eligible","Only eligible")]:
            c=QCheckBox(text);c.setObjectName(obj);lay.addWidget(c);setattr(self,obj,c)
        lay.addStretch();self.layout().insertWidget(2,row)

    def _build_privacy_notice(self):
        self.privacy_notice=QWidget();self.privacy_notice.setObjectName("member_privacy_notice");lay=QHBoxLayout(self.privacy_notice);lay.setContentsMargins(10,7,10,7);lay.setSpacing(10)
        self.lbl_privacy_notice=QLabel("Privacy Mode is ON — Telegram IDs, usernames and names are masked.");self.lbl_privacy_notice.setWordWrap(True);self.lbl_privacy_notice.setProperty("warning",True)
        self.btn_member_disable_privacy=QPushButton("Show Full Identity");self.btn_member_disable_privacy.setObjectName("btn_member_disable_privacy");self.btn_member_disable_privacy.setToolTip("Disable Privacy Mode. Individual Mask ID / Username / Name settings still apply.");self.btn_member_disable_privacy.clicked.connect(self.privacyModeDisableRequested)
        lay.addWidget(self.lbl_privacy_notice,1);lay.addWidget(self.btn_member_disable_privacy);self.layout().insertWidget(3,self.privacy_notice);self.privacy_notice.hide()

    def set_privacy_mode(self,enabled:bool):
        self.model.set_privacy_mode(bool(enabled))
        if hasattr(self,"privacy_notice"):self.privacy_notice.setVisible(bool(enabled))

    def _build_target_summary(self):
        self.target_summary=QWidget();self.target_summary.setObjectName("member_target_summary");lay=QHBoxLayout(self.target_summary);lay.setContentsMargins(10,7,10,7);lay.setSpacing(16)
        self.lbl_active_target=QLabel("Target: None");self.lbl_active_target.setObjectName("lbl_member_active_target")
        self.lbl_target_known=QLabel("Known Members: —");self.lbl_target_known.setObjectName("lbl_member_target_known")
        self.lbl_target_eligible=QLabel("Eligible: —");self.lbl_target_unknown=QLabel("Unknown: —");self.lbl_target_last_sync=QLabel("Last Sync: —")
        self.btn_sync_target_members=QPushButton("Sync Target Members");self.btn_sync_target_members.setObjectName("btn_sync_target_members");self.btn_sync_target_members.clicked.connect(self.sync_target_members)
        for w in (self.lbl_active_target,self.lbl_target_known,self.lbl_target_eligible,self.lbl_target_unknown,self.lbl_target_last_sync):lay.addWidget(w)
        lay.addStretch();lay.addWidget(self.btn_sync_target_members);self.layout().insertWidget(4,self.target_summary);self.target_summary.hide()

    def _build_selection_bar(self):
        self.selection_bar=QWidget();self.selection_bar.setObjectName("selection_bar");sel=QHBoxLayout(self.selection_bar);sel.setContentsMargins(10,6,10,6);sel.setSpacing(8)
        self.lbl_selection_count=QLabel("0 selected");self.lbl_selection_count.setObjectName("lbl_selection_count");sel.addWidget(self.lbl_selection_count)
        sel.addWidget(self.action_buttons["btn_invite_to_target"]);sel.addStretch()
        self.btn_selection_dnc=QPushButton("Do Not Contact");self.btn_selection_dnc.setObjectName("btn_member_selection_do_not_contact");self.btn_selection_dnc.clicked.connect(self.mark_dnc);self.btn_selection_dnc.hide()
        self.action_buttons["btn_member_tags"].hide();self.action_buttons["btn_member_eligibility"].hide();self.action_buttons["btn_member_blacklist"].hide()
        for name in ("btn_view_member","btn_add_member_tag","btn_add_to_blacklist","btn_remove_from_blacklist","btn_mark_eligible","btn_mark_do_not_contact"):
            self.action_buttons[name].hide()
        # Selection actions are contextual, not duplicated in the main page header.
        for name in ("btn_invite_to_target","btn_member_tags","btn_member_eligibility","btn_member_blacklist"):
            self.action_buttons[name].setParent(self.selection_bar)
        self.selection_bar.hide();self.layout().insertWidget(5,self.selection_bar)

    def _active_target_id(self):
        text=self.cmb_member_target.currentText()
        if not text or text=="All":return None
        raw=text.split(" — ",1)[0];return int(raw) if raw.isdigit() else None

    @staticmethod
    def _selected_group_id(combo):
        text=combo.currentText()
        if not text or text=="All":return None
        raw=text.split(" — ",1)[0];return int(raw) if raw.isdigit() else None

    @staticmethod
    def _replace_group_combo(combo,groups,current_id):
        combo.blockSignals(True);combo.clear();combo.addItem("All")
        selected=0
        for group in groups:
            combo.addItem(f"{group.id} — {group.title}")
            if current_id is not None and int(group.id)==int(current_id):selected=combo.count()-1
        combo.setCurrentIndex(selected);combo.blockSignals(False)
        return int(current_id) if selected>0 and current_id is not None else None

    def refresh_group_options(self):
        source_id=self._selected_group_id(self.cmb_member_source)
        target_id=self._selected_group_id(self.cmb_member_target)
        new_source=self._replace_group_combo(self.cmb_member_source,list(self.controller.all_source_groups()),source_id)
        new_target=self._replace_group_combo(self.cmb_member_target,list(self.controller.target_groups()),target_id)
        filters_changed=(source_id!=new_source) or (target_id!=new_target)
        self.controller.source_group_id=new_source;self.controller.target_group_id=new_target
        self._target_changed(refresh=False);self._selection_changed()
        if filters_changed:
            self.controller.pagination.page=1;self.controller.refresh()

    def refresh(self):
        if self.group_controller is not None:
            self.group_controller.refresh()
        return self.controller.refresh()

    def _target_changed(self,*_args,refresh=True):
        target_id=self._active_target_id();self.model.set_target_selected(bool(target_id));self.target_summary.setVisible(bool(target_id) and not getattr(self,"_simple_member_pool_ui",False))
        if not target_id:
            self.lbl_active_target.setText("Target: None");self.btn_sync_target_members.setEnabled(False);return
        group=next((g for g in self.controller.target_groups() if int(g.id)==int(target_id)),None);stats=self.controller.target_stats(target_id) or {}
        self.lbl_active_target.setText(f"Target: {group.title if group else target_id}")
        self.lbl_target_known.setText(f"Known Members: {int(stats.get('existing',0)):,}")
        self.lbl_target_eligible.setText(f"Eligible: {int(stats.get('eligible',0)):,}")
        self.lbl_target_unknown.setText(f"Unknown: {int(stats.get('unknown',0)):,}")
        self.lbl_target_last_sync.setText(f"Last Sync: {stats.get('last_sync') or 'Never'}")
        self.btn_sync_target_members.setEnabled(bool(self.controller.accounts_for_group(target_id)))
        if refresh:self._selection_changed()

    def _replace(self,items):
        self.model.replace_rows(items);self.model.set_target_selected(bool(self.controller.target_group_id));self.update_pagination(self.controller.pagination);self._selection_changed();self._target_changed(refresh=False)

    def _selected_member_ids(self):
        checked=set(self.model.checked_member_ids())
        for item in self.selected_items():
            if item and getattr(item,"id",None) is not None:checked.add(int(item.id))
        return sorted(checked)

    def _selection_changed(self,*_args):
        ids=self._selected_member_ids();count=len(ids);self.lbl_selection_count.setText(f"{count} selected");self.selection_bar.setVisible(count>0)
        self.action_buttons["btn_invite_to_target"].setEnabled(count>0 and bool(self.controller.target_groups()))

    def _members_by_selected_ids(self):
        ids=set(self._selected_member_ids());return [m for m in self.controller.current_items if getattr(m,"id",None) in ids]

    def _member_action(self,fn):
        item=self.selected_item()
        if item:fn(item.id)

    def view(self):
        item=self.selected_item()
        if item:MemberDetailsDialog(self.controller,item.id,self,avatar_service=self.avatar_service).exec()

    def add_tag(self):
        item=self.selected_item()
        if not item:return
        tag,ok=QInputDialog.getText(self,"Assign Member Tag","Tag")
        if ok and tag.strip():self.controller.add_tag(item.id,tag.strip())

    def bulk_add_tag(self):
        ids=self._selected_member_ids()
        if not ids:
            MemberTagManagerDialog(self.controller,None,self).exec();return
        tag,ok=QInputDialog.getText(self,"Add Tag",f"Tag for {len(ids)} selected member(s)")
        if ok and tag.strip():
            for mid in ids:self.controller.add_tag(mid,tag.strip())

    def mark_dnc(self):
        ids=self._selected_member_ids()
        if not ids:return
        if QMessageBox.question(self,"Do Not Contact",f"Mark {len(ids)} selected member(s) as Do Not Contact?")==QMessageBox.StandardButton.Yes:
            for mid in ids:self.controller.mark_do_not_contact(mid)

    def import_csv(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Members","","CSV Files (*.csv)")
        if not path:return
        result=self.controller.import_csv(path)
        if result and result.get("error_rows"):
            details="\n".join(f"Line {r['line']}: {r['error']}" for r in result["error_rows"][:20])
            QMessageBox.warning(self,"Member Import Completed With Errors",f"Inserted: {result['inserted']}\nUpdated: {result['updated']}\nUnchanged: {result['unchanged']}\nInvalid: {result['invalid']}\n\n{details}")

    def export_csv(self):
        options=["Current Filter (all matching members)","Selected Members","Current Page"]
        choice,ok=QInputDialog.getItem(self,"Export Members","Export scope",options,0,False)
        if not ok:return
        if choice.startswith("Selected") and not self._selected_member_ids():QMessageBox.information(self,"Export Members","Select one or more members first.");return
        path,_=QFileDialog.getSaveFileName(self,"Export Members","members.csv","CSV Files (*.csv)")
        if not path:return
        if choice.startswith("Selected"):
            items=[]
            for mid in self._selected_member_ids():
                m=self.controller.service.repository.get_by_id(mid)
                if m:items.append(m)
            self.controller.export_csv(path,"selected",items);return
        scope="all_filtered" if choice.startswith("Current Filter") else "current";self.controller.export_csv(path,scope,self.selected_items())

    def prepare_for_target(self):
        if not self.controller.target_groups():QMessageBox.information(self,"Prepare for Target","Save and classify a managed Target Group first.");return
        TargetPreparationDialog(self.controller,self.group_controller,target_group_id=self._active_target_id(),member_ids=self._selected_member_ids() or None,scope_mode="SOURCE_SELECTION" if self._selected_member_ids() else "FILTERED_MEMBER_POOL",parent=self).exec()

    def invite_to_target(self):
        ids=self._selected_member_ids()
        if not ids:
            QMessageBox.information(self,"Add Selected to Group","Select one or more members first.")
            return
        if len(ids)>100:
            QMessageBox.information(
                self,
                "Add Selected to Group",
                f"You selected {len(ids):,} members.\n\n"
                "Manual Add Selected supports up to 100 exact members per run. "
                "Select 100 or fewer here.\n\n"
                "For larger automatic transfers, use Flow Studio and drag a Source Group onto a Target Group.",
            )
            return
        SmartAddMembersDialog(
            self.controller,
            ids,
            target_group_id=self._active_target_id(),
            parent=self,
        ).exec()

    def mass_add_to_target(self):
        MassAddToTargetDialog(self.controller,target_group_id=self._active_target_id(),parent=self).exec()

    def sync_target_members(self):
        target_id=self._active_target_id()
        if not target_id:return
        mappings=self.controller.accounts_for_group(target_id)
        if not mappings:QMessageBox.warning(self,"Sync Target Members","No authorized account mapping is available for this target.");return
        labels=[]
        for m in mappings:
            label=f"{m.account_name or ('Account '+str(m.account_id))}"
            if m.account_username:label+=f"  •  @{m.account_username}"
            label+=f"  •  {str(m.health_status).replace('_',' ').title()}  •  {str(m.role or m.access_state).replace('_',' ').title()}";labels.append(label)
        selected,ok=QInputDialog.getItem(self,"Sync Target Members","Authorized account",labels,0,False)
        if not ok:return
        mapping=mappings[labels.index(selected)]
        if QMessageBox.question(self,"Sync Target Members","Read the accessible target participant list and update local target membership states?\n\nA complete participant list may mark absent local members as NOT_MEMBER. Partial access leaves unseen members UNKNOWN.")==QMessageBox.StandardButton.Yes:
            self.btn_sync_target_members.setEnabled(False)
            self.controller.on_sync_target(target_id,int(mapping.account_id),lambda _r:(self.btn_sync_target_members.setEnabled(True),self._target_changed(refresh=False)))

    def _build_actions(self):
        self.act_member_details=QAction("Open Details",self);self.act_member_details.setObjectName("act_member_details");self.act_member_details.triggered.connect(self.view)
        self.act_member_prepare_target=QAction("Prepare for Target",self);self.act_member_prepare_target.setObjectName("act_member_prepare_target");self.act_member_prepare_target.triggered.connect(self.prepare_for_target)
        self.act_member_invite_target=QAction("Add to Group",self);self.act_member_invite_target.setObjectName("act_member_invite_target");self.act_member_invite_target.triggered.connect(self.invite_to_target)
        self.act_member_mass_add=QAction("Advanced Add Many",self);self.act_member_mass_add.setObjectName("act_member_mass_add");self.act_member_mass_add.triggered.connect(self.mass_add_to_target)
        self.act_member_mark_eligible=QAction("Mark Eligible",self);self.act_member_mark_eligible.setObjectName("act_member_mark_eligible");self.act_member_mark_eligible.triggered.connect(lambda:self._bulk_status("eligibility","ELIGIBLE"))
        self.act_member_manual_review=QAction("Manual Review",self);self.act_member_manual_review.setObjectName("act_member_manual_review");self.act_member_manual_review.triggered.connect(lambda:self._bulk_status("eligibility","MANUAL_REVIEW"))
        self.act_member_consent_approved=QAction("Approved",self);self.act_member_consent_approved.setObjectName("act_member_consent_approved");self.act_member_consent_approved.triggered.connect(lambda:self._bulk_status("consent","APPROVED"))
        self.act_member_consent_declined=QAction("Declined",self);self.act_member_consent_declined.setObjectName("act_member_consent_declined");self.act_member_consent_declined.triggered.connect(lambda:self._bulk_status("consent","DECLINED"))
        self.act_member_consent_revoked=QAction("Revoked",self);self.act_member_consent_revoked.setObjectName("act_member_consent_revoked");self.act_member_consent_revoked.triggered.connect(lambda:self._bulk_status("consent","REVOKED"))
        self.act_member_global_blacklist=QAction("Add to Global Blacklist",self);self.act_member_global_blacklist.setObjectName("act_member_global_blacklist");self.act_member_global_blacklist.triggered.connect(self._bulk_blacklist)
        self.act_member_do_not_contact=QAction("Do Not Contact",self);self.act_member_do_not_contact.setObjectName("act_member_do_not_contact");self.act_member_do_not_contact.triggered.connect(self.mark_dnc)
        self.act_member_remove_exclusion=QAction("Remove Exclusion",self);self.act_member_remove_exclusion.setObjectName("act_member_remove_exclusion");self.act_member_remove_exclusion.triggered.connect(self._bulk_unblacklist)
        self.act_member_assign_tag=QAction("Add Tag",self);self.act_member_assign_tag.setObjectName("act_member_assign_tag");self.act_member_assign_tag.triggered.connect(self.bulk_add_tag)
        self.act_member_remove_tag=QAction("Remove Tag",self);self.act_member_remove_tag.setObjectName("act_member_remove_tag");self.act_member_remove_tag.triggered.connect(self.remove_tag)
        self.act_member_check_target=QAction("Check Selected Target",self);self.act_member_check_target.setObjectName("act_member_check_target");self.act_member_check_target.triggered.connect(self.check_target)
        self.act_member_export=QAction("Export Selected",self);self.act_member_export.setObjectName("act_member_export");self.act_member_export.triggered.connect(self.export_csv)
        self.act_member_remove_selected=QAction("Clear Selected Members",self);self.act_member_remove_selected.setObjectName("act_member_remove_selected");self.act_member_remove_selected.triggered.connect(self.clear_selected_members)
        self.act_member_clear_filtered=QAction("Clear Filtered Members",self);self.act_member_clear_filtered.setObjectName("act_member_clear_filtered");self.act_member_clear_filtered.triggered.connect(self.clear_filtered_members)
        self.act_member_clear_source=QAction("Clear Members by Source",self);self.act_member_clear_source.setObjectName("act_member_clear_source");self.act_member_clear_source.triggered.connect(self.clear_by_source)
        self.act_member_clear_orphaned=QAction("Clear Orphaned Members",self);self.act_member_clear_orphaned.setObjectName("act_member_clear_orphaned");self.act_member_clear_orphaned.triggered.connect(self.clear_orphaned)
        self.act_member_clear_all=QAction("Clear Entire Member Pool",self);self.act_member_clear_all.setObjectName("act_member_clear_all");self.act_member_clear_all.triggered.connect(self.clear_all)
        self.act_member_reset_table=QAction("Reset Table Layout",self);self.act_member_reset_table.setObjectName("act_member_reset_table");self.act_member_reset_table.triggered.connect(lambda:self.table_preferences.reset_table(self.table.objectName()))
        self.act_member_remove_source=QAction("Remove from Source",self);self.act_member_remove_source.setObjectName("act_member_remove_source");self.act_member_remove_source.triggered.connect(self.remove_selected_source)
        self.act_member_copy_username=QAction("Copy Username",self);self.act_member_copy_username.setObjectName("act_member_copy_username");self.act_member_copy_username.triggered.connect(self.copy_selected_username)
        self.act_member_copy_telegram_id=QAction("Copy Telegram ID",self);self.act_member_copy_telegram_id.setObjectName("act_member_copy_telegram_id");self.act_member_copy_telegram_id.triggered.connect(self.copy_selected_telegram_id)

    def context_menu(self,pos):
        if not self._selected_member_ids():return
        menu=QMenu(self);menu.addAction(self.act_member_details);menu.addSeparator();menu.addAction(self.act_member_prepare_target);menu.addAction(self.act_member_invite_target);menu.addAction(self.act_member_mass_add);menu.addSeparator()
        menu.addAction(self.act_member_assign_tag);e=menu.addMenu("Eligibility");e.addActions([self.act_member_mark_eligible,self.act_member_manual_review]);c=menu.addMenu("Consent");c.addActions([self.act_member_consent_approved,self.act_member_consent_declined,self.act_member_consent_revoked]);b=menu.addMenu("Exclusions");b.addActions([self.act_member_global_blacklist,self.act_member_do_not_contact,self.act_member_remove_exclusion]);menu.addSeparator();menu.addAction(self.act_member_remove_source);menu.addAction(self.act_member_remove_selected);menu.addAction(self.act_member_export);menu.addSeparator();menu.addAction(self.act_member_copy_username);menu.addAction(self.act_member_copy_telegram_id);menu.exec(self.table.viewport().mapToGlobal(pos))

    def _bulk_status(self,kind,status):
        ids=self._selected_member_ids()
        if kind=="eligibility":self.controller.set_eligibility_many(ids,status)
        else:self.controller.set_consent_many(ids,status)
    def _bulk_blacklist(self):
        for mid in self._selected_member_ids():self.controller.blacklist(mid)
    def _bulk_unblacklist(self):
        for mid in self._selected_member_ids():self.controller.unblacklist(mid)
    def _consent(self,status):self._bulk_status("consent",status)

    def remove_selected_source(self):
        item=self.selected_item()
        if not item:return
        details=self.controller.get_member_details(item.id) or {};sources=details.get("sources",[])
        if not sources:QMessageBox.information(self,"Remove from Source","This member has no saved source relationship.");return
        labels=[f"{s.group_title} • {str(s.source_status).replace('_',' ').title()}" for s in sources]
        choice,ok=QInputDialog.getItem(self,"Remove from Source","Source relationship",labels,0,False)
        if ok:
            src=sources[labels.index(choice)]
            if QMessageBox.question(self,"Remove from Source",f"Remove the local source relationship with {src.group_title}?\n\nTelegram is not changed.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.controller.remove_member_source(item.id,int(src.group_id),False)

    def copy_selected_username(self):
        item=self.selected_item()
        if item and getattr(item,"username",None):QApplication.clipboard().setText(f"@{item.username}")

    def copy_selected_telegram_id(self):
        item=self.selected_item()
        if item and getattr(item,"telegram_user_id",None):QApplication.clipboard().setText(str(item.telegram_user_id))

    def remove_tag(self):
        item=self.selected_item()
        if not item:return
        tags=self.controller.service.repository.get_tags(item.id)
        if not tags:return
        tag,ok=QInputDialog.getItem(self,"Remove Tag","Tag",tags,0,False)
        if ok:self.controller.remove_tag(item.id,tag)

    def check_target(self):
        item=self.selected_item();target=self._active_target_id()
        if not item or not target:QMessageBox.information(self,"Target Status","Select a target first, then check the selected member.");return
        mappings=self.controller.accounts_for_group(target)
        if not mappings:QMessageBox.warning(self,"Target Status","No authorized account mapping is available for this target.");return
        labels=[f"{m.account_name or ('Account '+str(m.account_id))} • {str(m.role or m.access_state).title()}" for m in mappings];choice,ok=QInputDialog.getItem(self,"Target Status","Authorized account",labels,0,False)
        if ok:self.controller.check_target(item.id,target,int(mappings[labels.index(choice)].account_id))

    def eligibility_menu(self):
        menu=QMenu(self);menu.addAction(self.act_member_mark_eligible);menu.addAction(self.act_member_manual_review);menu.exec(self.action_buttons["btn_member_eligibility"].mapToGlobal(self.action_buttons["btn_member_eligibility"].rect().bottomLeft()))
    def blacklist_menu(self):
        menu=QMenu(self);menu.addAction(self.act_member_global_blacklist);menu.addAction(self.act_member_do_not_contact);menu.addAction(self.act_member_remove_exclusion);menu.exec(self.action_buttons["btn_member_blacklist"].mapToGlobal(self.action_buttons["btn_member_blacklist"].rect().bottomLeft()))

    def clear_selected_members(self):
        ids=self._selected_member_ids()
        if ids and QMessageBox.question(self,"Clear Selected Members",f"Remove {len(ids)} members from the local Member Pool?\n\nTelegram users/groups are not changed.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:
            self.controller.cleanup_selected(ids);self.model.clear_checked()
    def clear_filtered_members(self):
        count=int(self.controller.pagination.total_items or 0)
        if count<=0:return
        filters=self.controller.current_filter_criteria();description="\n".join(f"{k.replace('_',' ').title()}: {v}" for k,v in filters.items() if v not in {None,"",False}) or "No additional filters"
        if QMessageBox.warning(self,"Clear Filtered Members",f"{count:,} members will be removed from the local Member Pool.\n\nCurrent filters:\n{description}\n\nThis cannot be undone unless data is synced/imported again.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.controller.cleanup_filtered();self.model.clear_checked()
    def clear_by_source(self):
        groups=self.controller.all_source_groups()
        if not groups:return
        labels=[g.title for g in groups];choice,ok=QInputDialog.getItem(self,"Clear Members by Source","Source Group",labels,0,False)
        if not ok:return
        group=groups[labels.index(choice)];count=self.controller.service.sources.count_by_group(group.id,active_only=False) if self.controller.service.sources else 0
        box=QMessageBox(self);box.setWindowTitle("Clear Members by Source");box.setText(f"Found {count:,} source relationship(s) for {group.title}.");box.setInformativeText("The safer default removes only the source relationship. You can optionally remove a member record when this is its only source; protected exclusion records are preserved.")
        safe=box.addButton("Remove Source Relationship Only",QMessageBox.ButtonRole.AcceptRole);both=box.addButton("Also Remove Single-Source Members",QMessageBox.ButtonRole.DestructiveRole);box.addButton("Cancel",QMessageBox.ButtonRole.RejectRole);box.exec()
        if box.clickedButton() is safe:self.controller.cleanup_by_source(group.id,False)
        elif box.clickedButton() is both:self.controller.cleanup_by_source(group.id,True)
    def clear_orphaned(self):
        count=int(self.controller.cleanup_orphan_count() or 0)
        if count and QMessageBox.question(self,"Clear Orphaned Members",f"Remove {count:,} orphaned local member record(s)?\n\nRecords with exclusions or invitation history are protected.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Yes:self.controller.cleanup_orphaned()
    def clear_all(self):
        count=int(self.controller.statistics().get("total",0));dialog=ClearEntireMemberPoolDialog(count,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.controller.cleanup_all(dialog.chk_preserve_exclusions.isChecked(),dialog.chk_preserve_audit.isChecked());self.model.clear_checked()

    def show_more(self):
        menu=QMenu(self);menu.addAction(self.act_member_details);menu.addAction(self.act_member_export);menu.addSeparator();menu.addAction(self.act_member_mass_add);menu.addAction("Manage Tags",lambda:MemberTagManagerDialog(self.controller,None,self).exec());elig=menu.addMenu("Eligibility");elig.addActions([self.act_member_mark_eligible,self.act_member_manual_review]);excl=menu.addMenu("Blacklist / Do Not Contact");excl.addActions([self.act_member_global_blacklist,self.act_member_do_not_contact,self.act_member_remove_exclusion]);menu.addSeparator();menu.addAction(self.act_member_remove_selected);menu.addAction(self.act_member_clear_filtered);menu.addAction(self.act_member_clear_source);menu.addAction(self.act_member_clear_orphaned);menu.addAction(self.act_member_clear_all);menu.exec(self.action_buttons["btn_member_more"].mapToGlobal(self.action_buttons["btn_member_more"].rect().bottomLeft()))

    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        advanced=feature_gate.has_feature(FeatureKey.ADVANCED_MEMBER_FILTERS);target=feature_gate.has_feature(FeatureKey.TARGET_MEMBER_STATUS);prep=feature_gate.has_feature(FeatureKey.TARGET_PREPARATION);direct=feature_gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE);sync=feature_gate.has_feature(FeatureKey.TARGET_MEMBER_SYNC)
        for widget in (self.cmb_member_target,self.cmb_member_tag,self.cmb_member_bot_filter):widget.setEnabled(advanced);widget.setToolTip("Available with SP Telegram Pro or SP Telegram Ultimate." if not advanced else "")
        self.chk_exclude_existing.setEnabled(target);self.chk_exclude_existing.setToolTip("Target member status is available with SP Telegram Pro or SP Telegram Ultimate." if not target else "")
        self.act_member_check_target.setEnabled(target);self.action_buttons["btn_prepare_target"].setEnabled(prep);self.act_member_prepare_target.setEnabled(prep)
        self.action_buttons["btn_invite_to_target"].setEnabled(direct and bool(self._selected_member_ids()));self.act_member_invite_target.setEnabled(direct)
        self.action_buttons["btn_mass_add_to_target"].setEnabled(direct);self.act_member_mass_add.setEnabled(direct)
        self.btn_sync_target_members.setEnabled(sync and bool(self._active_target_id()) and bool(self.controller.accounts_for_group(self._active_target_id())))
        self.action_buttons["btn_invite_to_target"].setToolTip("Direct approved-member invitation requires SP Telegram Ultimate." if not direct else "")
        self.action_buttons["btn_mass_add_to_target"].setToolTip("Mass Add to Target requires SP Telegram Ultimate." if not direct else "")
        self.btn_sync_target_members.setToolTip("Target member sync requires SP Telegram Pro or SP Telegram Ultimate." if not sync else "")
        return True
