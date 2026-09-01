from __future__ import annotations
from datetime import datetime
from PySide6.QtCore import QDate,Signal
from PySide6.QtWidgets import QCalendarWidget,QHBoxLayout,QLabel,QListWidget,QPushButton,QVBoxLayout,QWidget
class ContentCalendarWidget(QWidget):
    scheduleActivated=Signal(int)
    openCampaignRequested=Signal(int)
    editScheduleRequested=Signal(int)
    def __init__(self,parent=None):
        super().__init__(parent);self._items=[];root=QHBoxLayout(self);self.calendar=QCalendarWidget();root.addWidget(self.calendar,2);side=QVBoxLayout();self.lbl_day=QLabel();self.lbl_day.setProperty("sectionTitle",True);side.addWidget(self.lbl_day);self.list_day=QListWidget();side.addWidget(self.list_day,1);self.btn_calendar_open_campaign=QPushButton('Open Campaign');self.btn_calendar_open_campaign.setObjectName('btn_calendar_open_campaign');self.btn_calendar_edit_schedule=QPushButton('Edit Schedule');self.btn_calendar_edit_schedule.setObjectName('btn_calendar_edit_schedule');side.addWidget(self.btn_calendar_open_campaign);side.addWidget(self.btn_calendar_edit_schedule);root.addLayout(side,1);self.calendar.selectionChanged.connect(self.refresh_day);self.list_day.itemDoubleClicked.connect(lambda item:self.scheduleActivated.emit(int(item.data(32))));self.btn_calendar_open_campaign.clicked.connect(lambda:self._emit_selected(self.openCampaignRequested));self.btn_calendar_edit_schedule.clicked.connect(lambda:self._emit_selected(self.editScheduleRequested));self.refresh_day()
    def selected_schedule_id(self):
        item=self.list_day.currentItem();return int(item.data(32)) if item and item.data(32) is not None else None
    def _emit_selected(self,signal):
        sid=self.selected_schedule_id()
        if sid:signal.emit(sid)
    def set_schedules(self,items):self._items=list(items);self.refresh_day()
    def refresh_day(self):
        d=self.calendar.selectedDate();self.lbl_day.setText(d.toString('d MMMM yyyy'));self.list_day.clear()
        for s in self._items:
            raw=s.next_run_at or s.run_at
            if not raw:continue
            try:dt=datetime.fromisoformat(raw.replace('Z','+00:00')).astimezone()
            except Exception:continue
            if (dt.year,dt.month,dt.day)==(d.year(),d.month(),d.day()):
                from PySide6.QtWidgets import QListWidgetItem
                item=QListWidgetItem(f"{dt:%H:%M}  {getattr(s,'campaign_name',None) or 'Campaign'}  • {s.status}");item.setData(32,s.id);self.list_day.addItem(item)
