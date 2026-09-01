from __future__ import annotations
import json
from datetime import datetime
from PySide6.QtCore import QDateTime,QTimer,Qt,Signal
from PySide6.QtWidgets import (
    QComboBox,QDateTimeEdit,QDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,
    QPushButton,QRadioButton,QStackedWidget,QTableView,QTextEdit,QVBoxLayout,QWidget,QCheckBox,QTimeEdit,QMessageBox,QAbstractItemView
)
from app.widgets.calendar_utils import configure_calendar_popup
from app.dialogs.message_editor_dialog import MessageEditorDialog
from app.models.base_table_model import BaseTableModel
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout

class CreateCampaignDialog(QDialog):
    draftAutosaveRequested=Signal(dict)
    saveAsTemplateRequested=Signal(dict)
    refreshPermissionsRequested=Signal(list)
    STEPS=['General','Target Groups','Posting Accounts','Content','Schedule','Preview','Preflight']
    def __init__(self,targets:list[dict],accounts:list,parent=None,campaign=None,details=None,smart_planner=None):
        super().__init__(parent);self.setWindowTitle('Create Campaign');self.resize(960,720);self._table_layout=TableLayoutManager(self);self.targets=targets;self.accounts=accounts;self.messages=[];self._campaign=campaign;self._details=details or {};self._finish_mode='finish';self.smart_planner=smart_planner;self._last_smart_plan={}
        root=QVBoxLayout(self);self.lbl_step=QLabel();self.lbl_step.setProperty('dialogTitle',True);root.addWidget(self.lbl_step)
        # UX-008: step indicator — numbered dots show progress through the wizard.
        self._step_dots=[]; step_row=QHBoxLayout(); step_row.setSpacing(6)
        for i,name in enumerate(self.STEPS):
            dot=QLabel(str(i+1)); dot.setObjectName("wizard_step_dot"); dot.setAlignment(Qt.AlignmentFlag.AlignCenter); dot.setFixedSize(24,24); dot.setProperty("state","todo"); dot.setToolTip(f"{i+1}. {name}"); self._step_dots.append(dot); step_row.addWidget(dot)
        step_row.addStretch(); root.addLayout(step_row)
        self.stack_campaign_steps=QStackedWidget();self.stack_campaign_steps.setObjectName('stack_campaign_steps');root.addWidget(self.stack_campaign_steps,1)
        self._general();self._targets();self._accounts();self._content();self._schedule();self._preview();self._preflight()
        nav=QHBoxLayout();self.lbl_autosave=QLabel('');self.lbl_autosave.setProperty('muted',True);nav.addWidget(self.lbl_autosave)
        self.btn_campaign_save_draft=QPushButton('Save Draft');self.btn_campaign_save_draft.setObjectName('btn_campaign_save_draft');nav.addWidget(self.btn_campaign_save_draft);nav.addStretch()
        self.btn_campaign_back=QPushButton('Back');self.btn_campaign_back.setObjectName('btn_campaign_back');self.btn_campaign_next=QPushButton('Next');self.btn_campaign_next.setObjectName('btn_campaign_next')
        self.btn_campaign_finish=QPushButton('Create Campaign');self.btn_campaign_finish.setObjectName('btn_campaign_finish')
        self.btn_campaign_run=QPushButton('Create & Run');self.btn_campaign_run.setObjectName('btn_campaign_run')
        self.btn_campaign_schedule=QPushButton('Create & Schedule');self.btn_campaign_schedule.setObjectName('btn_campaign_schedule')
        self.btn_campaign_cancel=QPushButton('Cancel');self.btn_campaign_cancel.setObjectName('btn_campaign_cancel')
        for b in [self.btn_campaign_back,self.btn_campaign_next,self.btn_campaign_finish,self.btn_campaign_run,self.btn_campaign_schedule,self.btn_campaign_cancel]:nav.addWidget(b)
        root.addLayout(nav);self.btn_campaign_back.clicked.connect(lambda:self._go(-1));self.btn_campaign_next.clicked.connect(self._next);self.btn_campaign_cancel.clicked.connect(self.reject);self.btn_campaign_finish.clicked.connect(lambda:self._finish('finish'));self.btn_campaign_run.clicked.connect(lambda:self._finish('run'));self.btn_campaign_schedule.clicked.connect(lambda:self._finish('schedule'));self.btn_campaign_save_draft.clicked.connect(self._save_draft);self.stack_campaign_steps.currentChanged.connect(self._update)
        self._autosave=QTimer(self);self._autosave.setSingleShot(True);self._autosave.setInterval(1200);self._autosave.timeout.connect(self._emit_autosave)
        for w in [self.le_campaign_name,self.txt_campaign_description]:w.textChanged.connect(self._changed)
        if campaign:self._load(campaign,self._details)
        self._update(0)
    def _page(self):w=QWidget();self.stack_campaign_steps.addWidget(w);return w
    def _general(self):
        w=self._page();f=QFormLayout(w);self.le_campaign_name=QLineEdit();self.le_campaign_name.setObjectName('le_campaign_name');self.txt_campaign_description=QTextEdit();self.txt_campaign_description.setObjectName('txt_campaign_description');self.cmb_campaign_type=QComboBox();self.cmb_campaign_type.setObjectName('cmb_campaign_type');self.cmb_campaign_type.addItems(['Single Post','Multiple Messages','Scheduled Post','Recurring Post']);f.addRow('Campaign Name',self.le_campaign_name);f.addRow('Description',self.txt_campaign_description);f.addRow('Campaign Type',self.cmb_campaign_type)
    def _targets(self):
        w=self._page();l=QVBoxLayout(w);rows=[]
        for t in self.targets:
            g=t['group'];m=t.get('mapping');rows.append({'Group':g.title,'Username':('@'+g.username) if g.username else 'Private','Type':str(g.group_type).replace('_',' ').title(),'Primary Account':getattr(m,'account_name',None) or (str(m.account_id) if m else '—'),'Role':getattr(m,'role','—') if m else '—','Can Post':'Yes' if m and m.can_post else 'No','Can Media':'Yes' if m and m.can_send_media else 'No','Status':'Ready' if t.get('selectable') else (t.get('reason') or 'Unavailable'),'Group ID':g.id})
        self.target_model=BaseTableModel(rows,['Group','Username','Type','Primary Account','Role','Can Post','Can Media','Status']);self.tbl_campaign_target_selection=QTableView();self.tbl_campaign_target_selection.setObjectName('tbl_campaign_target_selection');self.tbl_campaign_target_selection.setModel(self.target_model);self.tbl_campaign_target_selection.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.tbl_campaign_target_selection.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self._table_layout.apply(self.tbl_campaign_target_selection,self.target_model.columns,overrides={'Group':ColumnLayout(210,150,'stretch'),'Username':ColumnLayout(170,120),'Primary Account':ColumnLayout(180,140),'Can Media':ColumnLayout(110,95),'Status':ColumnLayout(130,100)});l.addWidget(self.tbl_campaign_target_selection,1)
        a=QHBoxLayout();self.btn_select_all_campaign_targets=QPushButton('Select All Ready');self.btn_select_all_campaign_targets.setObjectName('btn_select_all_campaign_targets');self.btn_clear_campaign_targets=QPushButton('Clear');self.btn_clear_campaign_targets.setObjectName('btn_clear_campaign_targets');self.btn_validate_campaign_targets=QPushButton('Validate Targets');self.btn_validate_campaign_targets.setObjectName('btn_validate_campaign_targets')
        # Phase-1 compatibility names.
        self.btn_select_all_targets=self.btn_select_all_campaign_targets;self.btn_clear_target_selection=self.btn_clear_campaign_targets;self.btn_validate_targets=self.btn_validate_campaign_targets
        for b in [self.btn_select_all_campaign_targets,self.btn_clear_campaign_targets,self.btn_validate_campaign_targets]:a.addWidget(b)
        a.addStretch();l.addLayout(a);self.btn_select_all_campaign_targets.clicked.connect(self.tbl_campaign_target_selection.selectAll);self.btn_clear_campaign_targets.clicked.connect(self.tbl_campaign_target_selection.clearSelection);self.btn_validate_campaign_targets.clicked.connect(self._local_target_check)
    def _accounts(self):
        w=self._page();f=QFormLayout(w);self.rb_use_group_primary_account=QRadioButton("Use each group's primary account");self.rb_use_group_primary_account.setObjectName('rb_use_group_primary_account');self.rb_use_group_primary_account.setChecked(True);self.rb_use_campaign_custom_account=QRadioButton('Use selected account where it has verified access');self.rb_use_campaign_custom_account.setObjectName('rb_use_campaign_custom_account');self.rb_use_smart_account_pool=QRadioButton('Smart fixed assignment across healthy mapped accounts');self.rb_use_smart_account_pool.setObjectName('rb_use_smart_account_pool');self.rb_use_smart_account_pool.setEnabled(callable(self.smart_planner))
        self.rb_use_assigned_account=self.rb_use_group_primary_account;self.rb_use_custom_account=self.rb_use_campaign_custom_account
        self.cmb_campaign_account=QComboBox();self.cmb_campaign_account.setObjectName('cmb_campaign_account');self.cmb_campaign_account.addItem('Select account…',None)
        for a in self.accounts:self.cmb_campaign_account.addItem(getattr(a,'first_name',None) or getattr(a,'username',None) or f'Account {a.id}',a.id)
        self.lbl_preflight=QLabel('Smart assignment balances the saved plan across healthy mapped accounts within daily post limits. The assignment is fixed when saved; a runtime restriction pauses work and never triggers fallback rotation.');self.lbl_preflight.setWordWrap(True);f.addRow(self.rb_use_group_primary_account);f.addRow(self.rb_use_campaign_custom_account);f.addRow(self.rb_use_smart_account_pool);f.addRow('Custom Account',self.cmb_campaign_account);f.addRow('Rule',self.lbl_preflight)
    def _content(self):
        w=self._page();l=QVBoxLayout(w);self.list_campaign_messages=QListWidget();self.list_campaign_messages.setObjectName('list_campaign_messages');self.lst_messages=self.list_campaign_messages;l.addWidget(self.list_campaign_messages,1);a=QHBoxLayout()
        for obj,text,fn in [('btn_add_message','Add',self._add_message),('btn_edit_message','Edit',self._edit_message),('btn_duplicate_message','Duplicate',self._duplicate_message),('btn_remove_message','Remove',self._remove_message),('btn_move_message_up','Up',lambda:self._move(-1)),('btn_move_message_down','Down',lambda:self._move(1)),('btn_preview_message','Preview',self._preview_message),('btn_attach_media','Attach Media',self._add_message)]:
            b=QPushButton(text);b.setObjectName(obj);setattr(self,obj,b);b.clicked.connect(fn);a.addWidget(b)
        a.addStretch();l.addLayout(a);self.btn_save_campaign_as_template=QPushButton('Save Campaign As Template');self.btn_save_campaign_as_template.setObjectName('btn_save_campaign_as_template');self.btn_save_campaign_as_template.setToolTip('Create a reusable local template from the current campaign content.');self.btn_save_campaign_as_template.clicked.connect(lambda:self.saveAsTemplateRequested.emit(self.data()));l.addWidget(self.btn_save_campaign_as_template)
    def _schedule(self):
        w=self._page();f=QFormLayout(w);self.rb_campaign_send_now=QRadioButton('Send Now');self.rb_campaign_send_now.setObjectName('rb_campaign_send_now');self.rb_campaign_send_now.setChecked(True);self.rb_campaign_schedule_once=QRadioButton('Schedule Once');self.rb_campaign_schedule_once.setObjectName('rb_campaign_schedule_once');self.rb_campaign_schedule_repeat=QRadioButton('Repeat');self.rb_campaign_schedule_repeat.setObjectName('rb_campaign_schedule_repeat')
        self.dt_campaign_schedule_at=QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600));self.dt_campaign_schedule_at.setObjectName('dt_campaign_schedule_at');configure_calendar_popup(self.dt_campaign_schedule_at);self.cmb_campaign_timezone=QComboBox();self.cmb_campaign_timezone.setObjectName('cmb_campaign_timezone');self.cmb_campaign_timezone.setEditable(True);self.cmb_campaign_timezone.addItems(['Asia/Phnom_Penh','UTC','Asia/Bangkok','Asia/Singapore'])
        self.cmb_campaign_repeat_type=QComboBox();self.cmb_campaign_repeat_type.setObjectName('cmb_campaign_repeat_type');self.cmb_campaign_repeat_type.addItems(['Daily','Weekly','Custom Interval']);self.time_campaign_repeat_at=QTimeEdit();self.time_campaign_repeat_at.setObjectName('time_campaign_repeat_at')
        for wdg in [self.rb_campaign_send_now,self.rb_campaign_schedule_once,self.rb_campaign_schedule_repeat]:f.addRow(wdg)
        f.addRow('First Run',self.dt_campaign_schedule_at);f.addRow('Timezone',self.cmb_campaign_timezone);f.addRow('Repeat',self.cmb_campaign_repeat_type);f.addRow('Repeat Time',self.time_campaign_repeat_at)
        days=QHBoxLayout()
        for obj,text in [('chk_repeat_monday','Mon'),('chk_repeat_tuesday','Tue'),('chk_repeat_wednesday','Wed'),('chk_repeat_thursday','Thu'),('chk_repeat_friday','Fri'),('chk_repeat_saturday','Sat'),('chk_repeat_sunday','Sun')]:c=QCheckBox(text);c.setObjectName(obj);setattr(self,obj,c);days.addWidget(c)
        f.addRow('Weekly Days',days)
    def _preview(self):
        w=self._page();l=QVBoxLayout(w);self.lbl_campaign_preview=QLabel();self.lbl_campaign_preview.setWordWrap(True);self.lbl_campaign_preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);l.addWidget(self.lbl_campaign_preview);l.addStretch()
    def _preflight(self):
        w=self._page();l=QVBoxLayout(w);self.lbl_preflight_summary=QLabel();self.lbl_preflight_summary.setWordWrap(True);l.addWidget(self.lbl_preflight_summary);self.preflight_model=BaseTableModel([],['Group','Account','Post','Media','Health','Result','Reason']);self.tbl_campaign_preflight=QTableView();self.tbl_campaign_preflight.setObjectName('tbl_campaign_preflight');self.tbl_campaign_preflight.setModel(self.preflight_model);self._table_layout.apply(self.tbl_campaign_preflight,self.preflight_model.columns,overrides={'Group':ColumnLayout(200,150,'stretch'),'Account':ColumnLayout(170,130),'Result':ColumnLayout(140,110),'Reason':ColumnLayout(260,170,'stretch')});l.addWidget(self.tbl_campaign_preflight,1);a=QHBoxLayout()
        for obj,text in [('btn_preflight_refresh','Refresh'),('btn_preflight_refresh_permissions','Refresh Permissions'),('btn_preflight_back','Back'),('btn_preflight_continue','Continue'),('btn_preflight_cancel','Cancel')]:b=QPushButton(text);b.setObjectName(obj);setattr(self,obj,b);a.addWidget(b)
        a.addStretch();l.addLayout(a);self.btn_preflight_refresh.clicked.connect(self._build_local_preflight);self.btn_preflight_back.clicked.connect(lambda:self._go(-1));self.btn_preflight_continue.clicked.connect(self._finish);self.btn_preflight_cancel.clicked.connect(self.reject);self.btn_preflight_refresh_permissions.setToolTip('Refresh the selected account/group permission mappings through the existing Telegram group service.');self.btn_preflight_refresh_permissions.clicked.connect(lambda:self.refreshPermissionsRequested.emit(self._chosen_targets()))
    def _selected_target_indexes(self):return sorted({i.row() for i in self.tbl_campaign_target_selection.selectionModel().selectedRows()})
    def _chosen_targets(self):
        selected=self._selected_target_indexes();out=[];custom=self.cmb_campaign_account.currentData() if self.rb_use_campaign_custom_account.isChecked() else None
        if self.rb_use_smart_account_pool.isChecked():
            group_ids=[int(self.targets[idx]['group_id']) for idx in selected]
            self._last_smart_plan=self.smart_planner(group_ids,messages_per_target=max(1,len(self.messages))) if callable(self.smart_planner) else {'assignments':[],'blockers':['Smart account planning is unavailable.'],'account_plan':[]}
            return list(self._last_smart_plan.get('assignments') or [])
        for idx in selected:
            t=self.targets[idx];account_id=t.get('account_id')
            if custom:
                mapping=next((m for m in t.get('mappings',[]) if int(m.account_id)==int(custom)),None)
                account_id=custom if mapping and mapping.can_post else None
            if account_id:out.append({'group_id':t['group_id'],'account_id':int(account_id)})
        return out
    def _local_target_check(self):
        selected=self._selected_target_indexes();bad=[]
        if not selected:bad.append('Select at least one managed target group.')
        if self.rb_use_campaign_custom_account.isChecked() and not self.cmb_campaign_account.currentData():bad.append('Select a custom posting account.')
        chosen=self._chosen_targets()
        if self.rb_use_smart_account_pool.isChecked():bad.extend(self._last_smart_plan.get('blockers') or [])
        if len(chosen)!=len(selected):bad.append('One or more selected targets do not have verified posting permission for the selected account strategy.')
        QMessageBox.information(self,'Target Validation','Targets are locally valid.' if not bad else '\n'.join(bad));return not bad
    def _add_message(self):
        d=MessageEditorDialog(self)
        if d.exec():self.messages.append(d.data());self._refresh_messages();self._changed()
    def _edit_message(self):
        row=self.list_campaign_messages.currentRow()
        if row<0:return
        d=MessageEditorDialog(self,self.messages[row])
        if d.exec():self.messages[row]=d.data();self._refresh_messages();self._changed()
    def _duplicate_message(self):
        row=self.list_campaign_messages.currentRow()
        if row>=0:self.messages.insert(row+1,dict(self.messages[row]));self._refresh_messages();self.list_campaign_messages.setCurrentRow(row+1);self._changed()
    def _remove_message(self):
        row=self.list_campaign_messages.currentRow()
        if row>=0:self.messages.pop(row);self._refresh_messages();self._changed()
    def _move(self,delta):
        row=self.list_campaign_messages.currentRow();new=row+delta
        if row<0 or new<0 or new>=len(self.messages):return
        self.messages[row],self.messages[new]=self.messages[new],self.messages[row];self._refresh_messages();self.list_campaign_messages.setCurrentRow(new);self._changed()
    def _preview_message(self):
        row=self.list_campaign_messages.currentRow()
        if row<0:return
        m=self.messages[row];QMessageBox.information(self,'Message Preview',(m.get('body') or m.get('caption') or '[Media]')[:4000])
    def _refresh_messages(self):
        self.list_campaign_messages.clear()
        for i,m in enumerate(self.messages,1):self.list_campaign_messages.addItem(f"{i}. {m.get('type') or m.get('message_type','Text')}" )
    def _repeat_rule(self):
        if not self.rb_campaign_schedule_repeat.isChecked():return None
        days=[]
        for n,obj in enumerate(['chk_repeat_monday','chk_repeat_tuesday','chk_repeat_wednesday','chk_repeat_thursday','chk_repeat_friday','chk_repeat_saturday','chk_repeat_sunday']):
            if getattr(self,obj).isChecked():days.append(n)
        freq={'Daily':'DAILY','Weekly':'WEEKLY','Custom Interval':'INTERVAL'}[self.cmb_campaign_repeat_type.currentText()]
        return json.dumps({'frequency':freq,'interval':1,'weekdays':days,'time':self.time_campaign_repeat_at.time().toString('HH:mm')})
    def _schedule_type(self):
        if self.rb_campaign_send_now.isChecked():return 'SEND_NOW'
        return 'REPEAT' if self.rb_campaign_schedule_repeat.isChecked() else 'ONCE'
    def _update_preview(self):
        d=self.data();self.lbl_campaign_preview.setText(f"<b>{d['name'] or 'Untitled'}</b><br>Type: {d['campaign_type'].replace('_',' ').title()}<br>Targets: {len(d['targets'])}<br>Messages: {len(d['messages'])}<br>Schedule: {d['schedule_type'].replace('_',' ').title()}<br>Timezone: {d['timezone']}<br><br>This is a local preview. Telegram publishing occurs only after saved-campaign preflight and confirmation.")
    def _build_local_preflight(self):
        selected=self._selected_target_indexes();rows=[];blocked=0;chosen=self._chosen_targets()
        for idx in selected:
            t=self.targets[idx];g=t['group'];account_id=next((x['account_id'] for x in chosen if x['group_id']==g.id),None);mapping=next((m for m in t.get('mappings',[]) if account_id and int(m.account_id)==int(account_id)),None);post=bool(mapping and mapping.can_post);media_ok=bool(mapping and mapping.can_send_media) if any((m.get('message_type') or m.get('type','')).upper()!='TEXT' for m in self.messages) else True;ready=bool(account_id and post and media_ok);blocked+=int(not ready);account=next((a for a in self.accounts if account_id and int(a.id)==int(account_id)),None);account_name=getattr(account,'first_name',None) or getattr(account,'username',None) or str(account_id or '—');rows.append({'Group':g.title,'Account':account_name,'Post':'Yes' if post else 'No','Media':'Yes' if media_ok else 'No','Health':'Safety checked','Result':'Ready' if ready else 'Blocked','Reason':'' if ready else 'Verified mapping, health, or daily safety capacity is missing.'})
        smart_note=' Fixed smart assignments will not rotate after a runtime failure.' if self.rb_use_smart_account_pool.isChecked() else ''
        self.preflight_model.replace_rows(rows);self.lbl_preflight_summary.setText(f"Targets: {len(rows)} • Ready: {len(rows)-blocked} • Blocked: {blocked}\nA live account-health, daily-limit and permission preflight runs again immediately before actual send/schedule.{smart_note}");self.btn_preflight_continue.setEnabled(bool(rows) and blocked==0 and bool(self.messages) and bool(self.le_campaign_name.text().strip()))
    def _next(self):
        idx=self.stack_campaign_steps.currentIndex()
        if idx==0 and not self.le_campaign_name.text().strip():QMessageBox.warning(self,'Campaign','Campaign name is required.');return
        if idx==1 and not self._local_target_check():return
        if idx==3 and not self.messages:QMessageBox.warning(self,'Campaign','Add at least one campaign message.');return
        self._go(1)
    def _go(self,delta):self.stack_campaign_steps.setCurrentIndex(max(0,min(self.stack_campaign_steps.count()-1,self.stack_campaign_steps.currentIndex()+delta)))
    def _update(self,index):
        self.lbl_step.setText(f'{index+1}. {self.STEPS[index]}');self.btn_campaign_back.setEnabled(index>0);self.btn_campaign_next.setVisible(index<6);self.btn_campaign_finish.setVisible(index==6);self.btn_campaign_run.setVisible(index==6);self.btn_campaign_schedule.setVisible(index==6)
        for i,dot in enumerate(self._step_dots):
            state="current" if i==index else ("done" if i<index else "todo")
            dot.setProperty("state",state); dot.style().unpolish(dot); dot.style().polish(dot)
        if index==5:self._update_preview()
        if index==6:self._build_local_preflight()
    def _validate(self):
        """Return a list of specific, actionable validation errors."""
        errors=[]
        if not self.le_campaign_name.text().strip():errors.append('Campaign name is required.')
        selected=self._selected_target_indexes()
        if not selected:errors.append('Target is required — select at least one managed target group.')
        if selected:
            chosen=self._chosen_targets()
            if self.rb_use_smart_account_pool.isChecked():
                blockers=self._last_smart_plan.get('blockers') or []
                if blockers:errors.append('Account is required — '+blockers[0])
            elif len(chosen)!=len(selected):
                errors.append('Account is required — no posting account has verified permission for every selected target.')
        if not self.messages:errors.append('Content is required — add at least one campaign message.')
        if self.rb_campaign_schedule_repeat.isChecked() and not self._repeat_rule():
            errors.append('Schedule is invalid — select at least one repeat day or interval.')
        return errors
    def _finish(self,mode):
        errors=self._validate()
        if errors:
            QMessageBox.warning(self,'Campaign','\n'.join(errors));return
        self._finish_mode=mode;self.accept()
    def _save_draft(self):self._finish_mode='draft';self.accept()
    def _changed(self,*_):self._autosave.start()
    def _emit_autosave(self):self.lbl_autosave.setText('Draft changes pending…');self.draftAutosaveRequested.emit(self.data())
    def _load(self,campaign,details):
        self.le_campaign_name.setText(campaign.name or '');self.txt_campaign_description.setPlainText(campaign.description or '');label=str(campaign.campaign_type or 'SINGLE_POST').replace('_',' ').title().replace('Multi Message','Multiple Messages');idx=self.cmb_campaign_type.findText(label);self.cmb_campaign_type.setCurrentIndex(max(0,idx));self.messages=[]
        for m in details.get('messages',[]) or []:self.messages.append({'message_type':m.message_type,'type':m.message_type.replace('_',' ').title(),'body':m.body,'caption':m.caption,'media_path':m.media_path,'parse_mode':m.parse_mode,'disable_link_preview':bool(m.disable_link_preview)})
        self._refresh_messages();ids={t.group_id:t for t in details.get('targets',[]) or []}
        for row,t in enumerate(self.targets):
            if t['group_id'] in ids:self.tbl_campaign_target_selection.selectRow(row)
        if campaign.schedule_type=='ONCE':self.rb_campaign_schedule_once.setChecked(True)
        elif campaign.schedule_type in {'REPEAT','DAILY','WEEKLY'}:self.rb_campaign_schedule_repeat.setChecked(True)
        else:self.rb_campaign_send_now.setChecked(True)
        if campaign.send_at:
            dt=QDateTime.fromString(campaign.send_at,Qt.DateFormat.ISODate)
            if dt.isValid():self.dt_campaign_schedule_at.setDateTime(dt)
        if campaign.timezone:self.cmb_campaign_timezone.setCurrentText(campaign.timezone)
    def data(self):
        label=self.cmb_campaign_type.currentText();ctype={'Single Post':'SINGLE_POST','Multiple Messages':'MULTI_MESSAGE','Scheduled Post':'SCHEDULED_POST','Recurring Post':'RECURRING_POST'}[label];dt=self.dt_campaign_schedule_at.dateTime().toPython().astimezone().isoformat()
        strategy='SMART_FIXED' if self.rb_use_smart_account_pool.isChecked() else ('CUSTOM' if self.rb_use_campaign_custom_account.isChecked() else 'GROUP_PRIMARY')
        # Status reflects the user's explicit final action. DRAFT is created
        # ONLY when the user chooses "Save Draft". "Create Campaign" produces a
        # READY campaign; "Create & Schedule" produces a SCHEDULED campaign.
        if self._finish_mode=='draft':status='DRAFT'
        elif self._finish_mode=='schedule':status='SCHEDULED'
        else:status='READY'
        return {'name':self.le_campaign_name.text().strip(),'description':self.txt_campaign_description.toPlainText(),'campaign_type':ctype,'type':ctype,'status':status,'targets':self._chosen_targets(),'messages':self.messages,'default_account_id':self.cmb_campaign_account.currentData() if self.rb_use_campaign_custom_account.isChecked() else None,'account_strategy':strategy,'schedule_type':self._schedule_type(),'send_at':None if self.rb_campaign_send_now.isChecked() else dt,'timezone':self.cmb_campaign_timezone.currentText().strip() or 'UTC','repeat_rule':self._repeat_rule(),'finish_mode':self._finish_mode}

# Add compatibility attributes for older PySide6 versions
if not hasattr(CreateCampaignDialog, 'Accepted'):
    CreateCampaignDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CreateCampaignDialog, 'Rejected'):
    CreateCampaignDialog.Rejected = QDialog.DialogCode.Rejected
