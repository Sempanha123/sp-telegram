from __future__ import annotations
import json
from PySide6.QtCore import QDateTime,Signal,QSettings
from PySide6.QtWidgets import QCheckBox,QComboBox,QDateTimeEdit,QHBoxLayout,QLabel,QMessageBox,QPushButton,QRadioButton,QTableView,QVBoxLayout,QWidget
from app.widgets.calendar_utils import configure_calendar_popup
from app.models.base_table_model import BaseTableModel
from app.widgets.content_calendar import ContentCalendarWidget
from app.widgets.page_header import PageHeaderWidget
from app.widgets.locked_feature import LockedFeatureWidget
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout
class SchedulerPage(QWidget):
    licenseUpgradeRequested=Signal(str)
    toastRequested=Signal(str,str)
    campaignOpenRequested=Signal(int)
    def __init__(self,controller,campaign_controller,parent=None):
        super().__init__(parent);self.setObjectName('page_scheduler');self.controller=controller;self.campaign_controller=campaign_controller;self.settings=QSettings();root=QVBoxLayout(self);self.root_layout=root;self._license_lock=None;root.setContentsMargins(24,24,24,24);root.setSpacing(14);root.addWidget(PageHeaderWidget('Scheduler','Plan, review and reconcile authorized managed-group content schedules.'));head=QHBoxLayout();head.addStretch()
        for obj,text in [('btn_scheduler_day','Day'),('btn_scheduler_week','Week'),('btn_scheduler_month','Month'),('btn_scheduler_list','List'),('btn_schedule_new_post','+ Schedule'),('btn_edit_schedule','Edit'),('btn_pause_schedule','Pause'),('btn_resume_schedule','Resume'),('btn_cancel_schedule','Cancel'),('btn_run_schedule_now','Run Now'),('btn_sync_scheduled_posts','Sync Telegram'),('btn_refresh_schedule','Refresh')]:b=QPushButton(text);b.setObjectName(obj);setattr(self,obj,b);head.addWidget(b)
        root.addLayout(head)
        calendar_filters=QHBoxLayout();self.cmb_calendar_group_filter=QComboBox();self.cmb_calendar_group_filter.setObjectName('cmb_calendar_group_filter');self.cmb_calendar_account_filter=QComboBox();self.cmb_calendar_account_filter.setObjectName('cmb_calendar_account_filter');self.cmb_calendar_status_filter=QComboBox();self.cmb_calendar_status_filter.setObjectName('cmb_calendar_status_filter');self.cmb_calendar_status_filter.addItems(['All Status','SCHEDULED','ACTIVE','PAUSED','SENT','CANCELLED','CANCELLED_EXTERNALLY','FAILED','EXPIRED']);calendar_filters.addWidget(QLabel('Calendar:'));calendar_filters.addWidget(self.cmb_calendar_group_filter);calendar_filters.addWidget(self.cmb_calendar_account_filter);calendar_filters.addWidget(self.cmb_calendar_status_filter);calendar_filters.addStretch();root.addLayout(calendar_filters)
        self.calendar_widget=ContentCalendarWidget();root.addWidget(self.calendar_widget,2)
        form=QHBoxLayout();self.cmb_schedule_campaign=QComboBox();self.cmb_schedule_campaign.setObjectName('cmb_schedule_campaign');form.addWidget(self.cmb_schedule_campaign,2);self.rb_send_now=QRadioButton('Send Now');self.rb_send_now.setObjectName('rb_send_now');self.rb_schedule_once=QRadioButton('Once');self.rb_schedule_once.setObjectName('rb_schedule_once');self.rb_schedule_once.setChecked(True);self.rb_schedule_repeat=QRadioButton('Repeat');self.rb_schedule_repeat.setObjectName('rb_schedule_repeat');form.addWidget(self.rb_send_now);form.addWidget(self.rb_schedule_once);form.addWidget(self.rb_schedule_repeat);self.dt_schedule_at=QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600));self.dt_schedule_at.setObjectName('dt_schedule_at');configure_calendar_popup(self.dt_schedule_at);form.addWidget(self.dt_schedule_at);self.cmb_repeat_type=QComboBox();self.cmb_repeat_type.setObjectName('cmb_repeat_type');self.cmb_repeat_type.addItems(['Daily','Weekly','Custom Interval']);form.addWidget(self.cmb_repeat_type);root.addLayout(form)
        days=QHBoxLayout()
        for obj,txt in [('chk_repeat_monday','Mon'),('chk_repeat_tuesday','Tue'),('chk_repeat_wednesday','Wed'),('chk_repeat_thursday','Thu'),('chk_repeat_friday','Fri'),('chk_repeat_saturday','Sat'),('chk_repeat_sunday','Sun')]:c=QCheckBox(txt);c.setObjectName(obj);setattr(self,obj,c);days.addWidget(c)
        days.addStretch();root.addLayout(days)
        self.schedule_model=BaseTableModel([],['ID','Campaign','Target Count','Next Run','Repeat','Timezone','Last Run','Status']);self.tbl_schedules=QTableView();self.tbl_schedules.setObjectName('tbl_schedules');self.tbl_schedules.setModel(self.schedule_model);self.tbl_schedules.verticalHeader().setDefaultSectionSize(44);self.tbl_schedules.verticalHeader().setVisible(False);self._table_layout=TableLayoutManager(self);self._table_layout.apply(self.tbl_schedules,self.schedule_model.columns,overrides={'ID':ColumnLayout(70,60),'Campaign':ColumnLayout(220,160,'stretch'),'Target Count':ColumnLayout(120,100),'Next Run':ColumnLayout(180,150),'Repeat':ColumnLayout(150,120),'Timezone':ColumnLayout(150,120),'Last Run':ColumnLayout(180,150),'Status':ColumnLayout(140,110)});root.addWidget(self.tbl_schedules,2)
        controller.schedulesChanged.connect(self._replace);campaign_controller.campaignsChanged.connect(lambda _:self._load_campaigns());self._load_campaigns();self._load_calendar_filters();self._replace(controller.schedules());self.cmb_calendar_group_filter.currentIndexChanged.connect(self._apply_calendar_filters);self.cmb_calendar_account_filter.currentIndexChanged.connect(self._apply_calendar_filters);self.cmb_calendar_status_filter.currentIndexChanged.connect(self._apply_calendar_filters)
        self.btn_schedule_new_post.clicked.connect(self.save);self.btn_refresh_schedule.clicked.connect(controller.refresh);self.btn_edit_schedule.clicked.connect(self.edit);self.btn_pause_schedule.clicked.connect(lambda:self._selected_call(controller.pause));self.btn_resume_schedule.clicked.connect(lambda:self._selected_call(controller.resume));self.btn_cancel_schedule.clicked.connect(self.cancel);self.btn_run_schedule_now.clicked.connect(self.run_now);self.btn_sync_scheduled_posts.clicked.connect(lambda:self._selected_call(controller.sync_telegram));self.btn_scheduler_list.clicked.connect(lambda:self._set_view('list'));self.btn_scheduler_month.clicked.connect(lambda:self._set_view('month'));self.btn_scheduler_week.clicked.connect(lambda:self._set_view('week'));self.btn_scheduler_day.clicked.connect(lambda:self._set_view('day'));self.calendar_widget.scheduleActivated.connect(self._select_schedule);self.calendar_widget.openCampaignRequested.connect(self._calendar_activate);self.calendar_widget.editScheduleRequested.connect(self._calendar_edit);self._set_view(str(self.settings.value('scheduler/view','month')))
    def _load_calendar_filters(self):
        current_group=self.cmb_calendar_group_filter.currentData();current_account=self.cmb_calendar_account_filter.currentData();self.cmb_calendar_group_filter.blockSignals(True);self.cmb_calendar_account_filter.blockSignals(True);self.cmb_calendar_group_filter.clear();self.cmb_calendar_group_filter.addItem('All Groups',None);self.cmb_calendar_account_filter.clear();self.cmb_calendar_account_filter.addItem('All Accounts',None);seen={}
        for t in self.campaign_controller.managed_targets():
            self.cmb_calendar_group_filter.addItem(t['group'].title,t['group_id'])
            for m in t.get('mappings',[]):
                if getattr(m,'account_id',None):seen[int(m.account_id)]=getattr(m,'account_name',None) or f'Account {m.account_id}'
        for aid,name in sorted(seen.items()):self.cmb_calendar_account_filter.addItem(name,aid)
        group_index=self.cmb_calendar_group_filter.findData(current_group);account_index=self.cmb_calendar_account_filter.findData(current_account);self.cmb_calendar_group_filter.setCurrentIndex(group_index if group_index>=0 else 0);self.cmb_calendar_account_filter.setCurrentIndex(account_index if account_index>=0 else 0);self.cmb_calendar_group_filter.blockSignals(False);self.cmb_calendar_account_filter.blockSignals(False);self._apply_calendar_filters()
    def refresh_group_options(self):self._load_calendar_filters()
    def _apply_calendar_filters(self):
        gid=self.cmb_calendar_group_filter.currentData();aid=self.cmb_calendar_account_filter.currentData();status=self.cmb_calendar_status_filter.currentText();filtered=[]
        for sch in getattr(self,'_items',[]):
            if status!='All Status' and str(sch.status)!=status:continue
            if gid or aid:
                details=self.campaign_controller.details(sch.campaign_id);targets=details.get('targets',[]) if details else []
                if gid and not any(int(t.group_id)==int(gid) for t in targets):continue
                if aid and not any(t.account_id and int(t.account_id)==int(aid) for t in targets):continue
            filtered.append(sch)
        self.calendar_widget.set_schedules(filtered)
    def _set_view(self,name):
        name=name if name in {'day','week','month','list'} else 'month';self.settings.setValue('scheduler/view',name);self.calendar_widget.setVisible(name!='list');self.tbl_schedules.setVisible(name in {'list','month','week'});self.calendar_widget.calendar.setGridVisible(name in {'week','month'})
        if name=='list':self.tbl_schedules.setFocus()
    def _calendar_activate(self,sid):
        self._select_schedule(sid);item=next((x for x in getattr(self,'_items',[]) if int(x.id)==int(sid)),None)
        if item:self.campaignOpenRequested.emit(int(item.campaign_id))
    def _calendar_edit(self,sid):
        self._select_schedule(sid);self.edit()
    def _load_campaigns(self):
        current=self.cmb_schedule_campaign.currentData();self.cmb_schedule_campaign.clear()
        campaigns=list(self.campaign_controller.all_campaigns())
        for c in campaigns:self.cmb_schedule_campaign.addItem(c.name,c.id)
        if not campaigns:self.cmb_schedule_campaign.addItem('No campaigns available',None)
        if current is not None:
            idx=self.cmb_schedule_campaign.findData(current)
            if idx>=0:self.cmb_schedule_campaign.setCurrentIndex(idx)
    def _replace(self,items):
        self._items=list(items);rows=[]
        for s in items:
            camp=self.campaign_controller.service.repository.get_by_id(s.campaign_id);rows.append({'ID':s.id,'Campaign':getattr(s,'campaign_name',None) or (camp.name if camp else s.campaign_id),'Target Count':getattr(camp,'total_targets',0) if camp else 0,'Next Run':s.next_run_at or s.run_at or '—','Repeat':s.repeat_rule or s.schedule_type,'Timezone':s.timezone or 'UTC','Last Run':s.last_run_at or '—','Status':s.status or '—'})
        self.schedule_model.replace_rows(rows);self._apply_calendar_filters()
    def _data(self):
        weekdays=[i for i,obj in enumerate(['chk_repeat_monday','chk_repeat_tuesday','chk_repeat_wednesday','chk_repeat_thursday','chk_repeat_friday','chk_repeat_saturday','chk_repeat_sunday']) if getattr(self,obj).isChecked()];repeat=None
        if self.rb_schedule_repeat.isChecked():repeat=json.dumps({'frequency':{'Daily':'DAILY','Weekly':'WEEKLY','Custom Interval':'INTERVAL'}[self.cmb_repeat_type.currentText()],'interval':1,'weekdays':weekdays})
        stype='SEND_NOW' if self.rb_send_now.isChecked() else ('REPEAT' if self.rb_schedule_repeat.isChecked() else 'ONCE');dt=self.dt_schedule_at.dateTime().toPython().astimezone().isoformat();return {'campaign_id':self.cmb_schedule_campaign.currentData(),'schedule_type':stype,'run_at':dt,'next_run_at':dt,'repeat_rule':repeat,'timezone':'Asia/Phnom_Penh','missed_policy':'ASK_ME'}
    def save(self):
        if self.cmb_schedule_campaign.currentData() is None:
            QMessageBox.information(self,'Scheduler','Create a campaign before creating or running a schedule.');return
        if self.rb_send_now.isChecked():
            cid=self.cmb_schedule_campaign.currentData()
            if cid and QMessageBox.question(self,'Run Campaign Now','Run this campaign now? This does not create or alter a recurring schedule.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.campaign_controller.run_campaign(cid)
            return
        if QMessageBox.question(self,'Schedule Campaign',f"Schedule campaign for {self.dt_schedule_at.dateTime().toString()}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.save_schedule(self._data(),activate_remote=True)
    def _selected_id(self):
        rows=self.tbl_schedules.selectionModel().selectedRows();return int(self.schedule_model.row_dict(rows[0].row())['ID']) if rows else None
    def _selected_call(self,fn):
        sid=self._selected_id();return fn(sid) if sid else None
    def edit(self):
        sid=self._selected_id()
        if sid:self.controller.update(sid,self._data())
    def cancel(self):
        sid=self._selected_id()
        if sid and QMessageBox.question(self,'Cancel Schedule','Cancel this schedule? Future runs will stop; already published messages remain.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.cancel(sid,True)
    def run_now(self):
        sid=self._selected_id()
        if sid and QMessageBox.question(self,'Run Schedule Now','Run an additional occurrence now? The recurrence rule will not be changed.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.run_now(sid)
    def _select_schedule(self,sid):
        for r in range(self.schedule_model.rowCount()):
            if int(self.schedule_model.row_dict(r)['ID'])==sid:self.tbl_schedules.selectRow(r);break
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        schedule_once=feature_gate.has_feature(FeatureKey.SCHEDULE_ONCE)
        recurring=feature_gate.has_feature(FeatureKey.RECURRING_SCHEDULE)
        calendar=feature_gate.has_feature(FeatureKey.CONTENT_CALENDAR)
        if not schedule_once:
            if self._license_lock is None:
                self._license_lock=LockedFeatureWidget("Scheduler","Scheduling is available with SP Telegram Pro or SP Telegram Ultimate.","PRO",["Schedule Once","Campaign scheduling","SP Telegram Ultimate adds recurring schedules and Content Calendar"],self)
                self._license_lock.upgradeRequested.connect(self.licenseUpgradeRequested);self.root_layout.insertWidget(1,self._license_lock)
            self._license_lock.show()
        elif self._license_lock is not None:
            self._license_lock.hide()
        # Keep local history/list view visible, but gate creation/outgoing schedule controls.
        for widget in (self.btn_schedule_new_post,self.btn_edit_schedule,self.btn_resume_schedule,self.btn_run_schedule_now,self.btn_sync_scheduled_posts,self.cmb_schedule_campaign,self.rb_send_now,self.rb_schedule_once,self.dt_schedule_at):
            widget.setEnabled(schedule_once)
        # Stopping/pausing future publication is a safety action and remains
        # available even after downgrade/expiry. Resume remains licensed.
        self.btn_pause_schedule.setEnabled(True);self.btn_cancel_schedule.setEnabled(True)
        for widget in (self.rb_schedule_repeat,self.cmb_repeat_type,self.chk_repeat_monday,self.chk_repeat_tuesday,self.chk_repeat_wednesday,self.chk_repeat_thursday,self.chk_repeat_friday,self.chk_repeat_saturday,self.chk_repeat_sunday):
            widget.setEnabled(recurring)
            widget.setToolTip("Recurring scheduling requires SP Telegram Ultimate." if not recurring else "")
        for widget in (self.btn_scheduler_day,self.btn_scheduler_week,self.btn_scheduler_month,self.cmb_calendar_group_filter,self.cmb_calendar_account_filter,self.cmb_calendar_status_filter):
            widget.setEnabled(calendar)
            widget.setToolTip("Content Calendar requires SP Telegram Ultimate." if not calendar else "")
        if not calendar:self._set_view('list')
        return schedule_once
