
from __future__ import annotations
from PySide6.QtCore import Signal,Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog,QMenu,QMessageBox
from app.models.campaign_table_model import CampaignTableModel
from app.dialogs.campaign_progress_dialog import CampaignProgressDialog
from app.pages.base_table_page import BaseTablePage

class CampaignsPage(BaseTablePage):
    createRequested=Signal();editRequested=Signal(object);previewRequested=Signal(object);detailsRequested=Signal(object);toastRequested=Signal(str,str)
    def __init__(self,controller,parent=None):
        self.controller=controller
        actions=[('btn_create_campaign','New Campaign'),('btn_edit_campaign','Edit'),('btn_duplicate_campaign','Duplicate'),('btn_preview_campaign','Preview'),('btn_run_campaign','Run'),('btn_pause_campaign','Pause'),('btn_resume_campaign','Resume'),('btn_cancel_campaign','Cancel'),('btn_refresh_campaigns','Refresh'),('btn_export_campaign_results','Export Results'),('btn_more_campaign_actions','More ▾')]
        managed=controller.managed_targets();group_values=[f"{t['group_id']}: {t['group'].title}" for t in managed];account_ids={}
        for t in managed:
            for m in t.get('mappings',[]):
                if getattr(m,'account_id',None):account_ids[int(m.account_id)]=getattr(m,'account_name',None) or f"Account {m.account_id}"
        filters=[('cmb_campaign_status_filter','Status',['Draft','Validating','Ready','Scheduled','Running','Paused','Partial Success','Completed','Failed','Cancelled','Archived']),('cmb_campaign_type_filter','Type',['Single Post','Multiple Messages','Scheduled Post','Recurring Post']),('cmb_campaign_schedule_filter','Schedule',['Send Now','Once','Repeat']),('cmb_campaign_group_filter','Group',group_values),('cmb_campaign_account_filter','Account',[f"{k}: {v}" for k,v in sorted(account_ids.items())])]
        super().__init__('page_campaigns','Campaigns',CampaignTableModel(controller.campaigns()),'tbl_campaigns',actions,'le_search_campaigns',filters,parent)
        self.enable_database_mode(controller.pagination);self.searchDebounced.connect(controller.set_search);self.filterChanged.connect(controller.set_filter);self.pageChanged.connect(lambda p:(setattr(controller.pagination,'page',p),controller.refresh()));self.pageSizeChanged.connect(lambda n:(setattr(controller.pagination,'page_size',n),setattr(controller.pagination,'page',1),controller.refresh()));controller.campaignsChanged.connect(self._replace)
        self.action_buttons['btn_create_campaign'].clicked.connect(self.createRequested);self.action_buttons['btn_edit_campaign'].clicked.connect(self.edit);self.action_buttons['btn_duplicate_campaign'].clicked.connect(self.duplicate);self.action_buttons['btn_preview_campaign'].clicked.connect(self.preview);self.action_buttons['btn_run_campaign'].clicked.connect(self.run);self.action_buttons['btn_pause_campaign'].clicked.connect(self.pause);self.action_buttons['btn_resume_campaign'].clicked.connect(self.resume);self.action_buttons['btn_cancel_campaign'].clicked.connect(self.cancel);self.action_buttons['btn_refresh_campaigns'].clicked.connect(controller.refresh);self.action_buttons['btn_export_campaign_results'].clicked.connect(self._export);self.action_buttons['btn_more_campaign_actions'].clicked.connect(self._show_more)
        self.progress_dialog=CampaignProgressDialog(self);controller.campaignStarted.connect(self._campaign_started);controller.campaignProgress.connect(self.progress_dialog.update_progress);controller.campaignCompleted.connect(self._campaign_finished);controller.campaignFailed.connect(lambda _id,_msg:self._campaign_finished(_id))
        self.table.doubleClicked.connect(lambda _idx:self._details());self.table.customContextMenuRequested.connect(self._context)
        for name in ('btn_duplicate_campaign','btn_preview_campaign','btn_pause_campaign','btn_resume_campaign','btn_cancel_campaign','btn_export_campaign_results'):
            self.action_buttons[name].hide()
        self.set_empty_state('No campaigns found','Create a campaign to publish or schedule content to managed groups and channels.')
    def refresh_group_options(self):
        managed=self.controller.managed_targets();group_values=[f"{t['group_id']}: {t['group'].title}" for t in managed];account_ids={}
        for target in managed:
            for mapping in target.get('mappings',[]):
                if getattr(mapping,'account_id',None):account_ids[int(mapping.account_id)]=getattr(mapping,'account_name',None) or f"Account {mapping.account_id}"
        changed=False
        for name,values,attr in (
            ('cmb_campaign_group_filter',group_values,'group_filter'),
            ('cmb_campaign_account_filter',[f"{key}: {value}" for key,value in sorted(account_ids.items())],'account_filter'),
        ):
            combo=getattr(self,name);current=getattr(self.controller,attr,None);combo.blockSignals(True);combo.clear();combo.addItem('All')
            for value in values:combo.addItem(value)
            index=0
            if current is not None:
                prefix=f"{int(current)}:"
                index=next((i for i in range(1,combo.count()) if combo.itemText(i).startswith(prefix)),0)
            combo.setCurrentIndex(index);combo.blockSignals(False)
            if current is not None and index==0:setattr(self.controller,attr,None);changed=True
        if changed:self.controller.pagination.page=1;self.controller.refresh()
    def _replace(self,items):self.model.replace_rows(items);self.update_pagination(self.controller.pagination)
    def _campaign_started(self,campaign_id):
        self.progress_dialog.reset_for_campaign(campaign_id);self.progress_dialog.show();self.progress_dialog.raise_()
    def _campaign_finished(self,campaign_id):
        self.progress_dialog.progress_campaign.setValue(100);self.progress_dialog.lbl_campaign_current_target.setText('Finished')
    def duplicate(self):
        item=self.selected_item()
        if item:self.controller.duplicate(item.id)
    def edit(self):
        item=self.selected_item()
        if item:self.editRequested.emit(item)
    def preview(self):
        item=self.selected_item()
        if item:self.previewRequested.emit(item)
    def _details(self):
        item=self.selected_item()
        if item:self.detailsRequested.emit(item)
    def run(self):
        item=self.selected_item()
        if not item:return
        pre=self.controller.validate_campaign(item.id)
        if not pre:return
        if pre.blocked_targets or pre.errors:
            QMessageBox.warning(self,'Campaign Preflight',f'Campaign is blocked.\n\nReady: {pre.ready_targets}\nBlocked: {pre.blocked_targets}\n\n'+('\n'.join(pre.errors[:6]) or 'Resolve target/account configuration.'));return
        details=self.controller.details(item.id);messages=len(details.get('messages',[]));targets=len(details.get('targets',[]));accounts=len({t.account_id for t in details.get('targets',[]) if t.account_id})
        if QMessageBox.question(self,'Publish Campaign',f"Publish campaign?\n\nCampaign: {item.name}\nTargets: {targets} managed group(s)\nMessages: {messages}\nPosting accounts: {accounts}\n\nAlready confirmed deliveries will not be sent again.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.run_campaign(item.id)
    def pause(self):
        item=self.selected_item()
        if item:self.controller.pause_campaign(item.id)
    def resume(self):
        item=self.selected_item()
        if item and QMessageBox.question(self,'Resume Campaign','Resume pending campaign work? Confirmed deliveries will be skipped.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.resume_campaign(item.id)
    def cancel(self):
        item=self.selected_item()
        if item and QMessageBox.question(self,'Cancel Campaign','Cancel remaining campaign work? Already published messages will remain.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.cancel_campaign(item.id)
    def _export(self):
        item=self.selected_item()
        if not item:return
        path,_=QFileDialog.getSaveFileName(self,'Export Campaign Results',f'campaign_{item.id}_results.csv','CSV files (*.csv)')
        if path:self.controller.export_results(item.id,path)
    def _archive(self):
        item=self.selected_item()
        if item:self.controller.archive(item.id)
    def _unarchive(self):
        item=self.selected_item()
        if item:self.controller.unarchive(item.id)
    def _delete(self):
        item=self.selected_item()
        if not item:return
        status=str(item.status or '').upper()
        if status in {'RUNNING','SCHEDULED','PAUSED'}:
            QMessageBox.information(self,'Delete Campaign','Cancel the campaign first, then delete it.')
            return
        if status in {'DRAFT','CANCELLED'}:
            message=f"Delete '{item.name}'? This cannot be undone."
        else:
            message=f"Delete '{item.name}'? Its delivery history will be permanently removed. This cannot be undone."
        if QMessageBox.question(self,'Delete Campaign',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.delete(item.id)
    def _action(self,menu,text,obj,slot):a=QAction(text,self);a.setObjectName(obj);a.triggered.connect(slot);menu.addAction(a);return a
    def _menu(self):
        item=self.selected_item();status=str(getattr(item,'status','') or '').upper()
        m=QMenu(self);self.act_campaign_details=self._action(m,'Open Campaign','act_campaign_details',self._details);m.addSeparator();self.act_campaign_edit=self._action(m,'Edit','act_campaign_edit',self.edit);self.act_campaign_duplicate=self._action(m,'Duplicate','act_campaign_duplicate',self.duplicate);self.act_campaign_preview=self._action(m,'Preview','act_campaign_preview',self.preview);m.addSeparator();self.act_campaign_run=self._action(m,'Run Now','act_campaign_run',self.run);self.act_campaign_pause=self._action(m,'Pause','act_campaign_pause',self.pause);self.act_campaign_resume=self._action(m,'Resume','act_campaign_resume',self.resume);self.act_campaign_cancel=self._action(m,'Cancel','act_campaign_cancel',self.cancel);m.addSeparator();self.act_campaign_results=self._action(m,'Export Results','act_campaign_results',self._export);m.addSeparator()
        if status=='ARCHIVED':self.act_campaign_unarchive=self._action(m,'Unarchive','act_campaign_unarchive',self._unarchive)
        else:self.act_campaign_archive=self._action(m,'Archive','act_campaign_archive',self._archive)
        delete_label='Delete Draft' if status in {'DRAFT','CANCELLED'} else 'Delete'
        self.act_campaign_delete=self._action(m,delete_label,'act_campaign_delete',self._delete)
        selected=item is not None
        for action in (self.act_campaign_details,self.act_campaign_edit,self.act_campaign_duplicate,self.act_campaign_preview,self.act_campaign_results,self.act_campaign_delete):action.setEnabled(selected)
        self.act_campaign_run.setEnabled(selected and status not in {'RUNNING','ARCHIVED'})
        self.act_campaign_pause.setEnabled(selected and status=='RUNNING')
        self.act_campaign_resume.setEnabled(selected and status=='PAUSED')
        self.act_campaign_cancel.setEnabled(selected and status in {'SCHEDULED','RUNNING','PAUSED'})
        archive=getattr(self,'act_campaign_unarchive',None) if status=='ARCHIVED' else getattr(self,'act_campaign_archive',None)
        if archive is not None:archive.setEnabled(selected)
        return m
    def _show_more(self):self._menu().exec(self.action_buttons['btn_more_campaign_actions'].mapToGlobal(self.action_buttons['btn_more_campaign_actions'].rect().bottomLeft()))
    def _context(self,pos):
        if self.table.indexAt(pos).isValid():self._menu().exec(self.table.viewport().mapToGlobal(pos))
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        locked=not feature_gate.has_feature(FeatureKey.CAMPAIGNS)
        self.set_feature_lock(
            locked,
            feature_key=FeatureKey.CAMPAIGNS,
            title="Campaigns",
            description="Available with SP Telegram Pro or Ultimate. Publish text, photos, videos and documents to managed groups you are authorized to manage.",
            required_plan="PRO",
            feature_list=["Managed-group campaigns", "Media posts", "Multi-message campaigns", "Schedule Once"],
            action_text="View Pro Plan",
            preserve_read_only=False,
        )
        create=self.action_buttons.get('btn_create_campaign')
        if create:
            create.setText('New Campaign  •  PRO' if locked else 'New Campaign')
            create.setToolTip('Campaign publishing requires SP Telegram Pro or Ultimate.' if locked else '')
        refresh=self.action_buttons.get('btn_refresh_campaigns')
        if refresh:
            refresh.setEnabled(True)
        return not locked
