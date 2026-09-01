from __future__ import annotations

from PySide6.QtCore import QDateTime, QPoint, Qt
from PySide6.QtWidgets import QCheckBox,QDateTimeEdit,QFileDialog,QHeaderView,QHBoxLayout,QLabel,QLineEdit,QMenu,QMessageBox,QPushButton,QTabWidget,QVBoxLayout,QWidget
from app.widgets.calendar_utils import configure_calendar_popup

from app.models.log_table_model import LogTableModel
from app.pages.base_table_page import BaseTablePage


class LogsPage(BaseTablePage):
    def __init__(self,controller,parent=None):
        self.controller=controller
        super().__init__("page_logs","Logs",LogTableModel(controller.logs()),"tbl_logs",[("btn_refresh_logs","Refresh"),("btn_clear_log_view","Clear View"),("btn_export_logs","Export"),("btn_open_log_details","Details")],"le_search_logs",[("cmb_log_level","Level",["Info","Warning","Error","Debug","Critical"]),("cmb_log_category","Category",["System","Account","Group","Member","Campaign","Scheduler","Job","Database","Security","Audit"])],parent)
        self.enable_database_mode(controller.pagination); self.searchDebounced.connect(controller.set_search); self.filterChanged.connect(controller.set_filter); self.pageChanged.connect(controller.set_page); self.pageSizeChanged.connect(controller.set_page_size); controller.logsChanged.connect(lambda items:(self.model.replace_rows(items),self.update_pagination(controller.pagination)))
        self.action_buttons["btn_refresh_logs"].clicked.connect(controller.refresh); self.action_buttons["btn_export_logs"].clicked.connect(self.export); self.action_buttons["btn_clear_log_view"].clicked.connect(lambda:self.model.replace_rows([])); self.action_buttons["btn_open_log_details"].clicked.connect(self.details)
        self.action_buttons["btn_clear_log_view"].hide(); self.action_buttons["btn_open_log_details"].hide(); self.btn_logs_more=QPushButton("More"); self.btn_logs_more.setProperty("role","ghost"); more=QMenu(self.btn_logs_more); more.addAction("Open Selected Details",self.details); more.addAction("Clear Current View",lambda:self.model.replace_rows([])); self.btn_logs_more.setMenu(more); self.page_header.add_action(self.btn_logs_more)
        self.table.customContextMenuRequested.connect(self.context_menu); self.table.horizontalHeader().setStretchLastSection(False); self.table.horizontalHeader().setSectionResizeMode(self.model.columns.index("Message"),QHeaderView.ResizeMode.Stretch)

        self.tab_logs=QTabWidget(); self.tab_logs.setObjectName("tab_logs"); [self.tab_logs.addTab(QWidget(),name) for name in ["Activity","Telegram","Errors","Audit","System"]]; self.tab_logs.currentChanged.connect(self._tab_changed); self.layout().insertWidget(1,self.tab_logs)

        quick=QWidget(); q=QHBoxLayout(quick); q.setContentsMargins(0,0,0,0); q.setSpacing(8)
        self.chk_log_date_filter=QCheckBox("Date Range"); self.chk_log_date_filter.setObjectName("chk_log_date_filter")
        self.dt_log_from=QDateTimeEdit(QDateTime.currentDateTime().addDays(-7)); self.dt_log_from.setObjectName("dt_log_from"); configure_calendar_popup(self.dt_log_from)
        self.dt_log_to=QDateTimeEdit(QDateTime.currentDateTime()); self.dt_log_to.setObjectName("dt_log_to"); configure_calendar_popup(self.dt_log_to)
        self.btn_logs_advanced_filters=QPushButton("Advanced Filters"); self.btn_logs_advanced_filters.setCheckable(True); self.btn_logs_advanced_filters.setProperty("role","ghost")
        q.addWidget(self.chk_log_date_filter); q.addWidget(self.dt_log_from); q.addWidget(QLabel("to")); q.addWidget(self.dt_log_to); q.addWidget(self.btn_logs_advanced_filters); q.addStretch(); self.layout().insertWidget(3,quick)
        self.advanced_host=QWidget(); a=QHBoxLayout(self.advanced_host); a.setContentsMargins(0,0,0,0); a.setSpacing(8); a.addWidget(QLabel("Resource IDs"))
        self.le_log_account_id=QLineEdit(); self.le_log_account_id.setObjectName("le_log_account_id"); self.le_log_account_id.setPlaceholderText("Account")
        self.le_log_group_id=QLineEdit(); self.le_log_group_id.setObjectName("le_log_group_id"); self.le_log_group_id.setPlaceholderText("Group")
        self.le_log_campaign_id=QLineEdit(); self.le_log_campaign_id.setObjectName("le_log_campaign_id"); self.le_log_campaign_id.setPlaceholderText("Campaign")
        self.le_log_job_id=QLineEdit(); self.le_log_job_id.setObjectName("le_log_job_id"); self.le_log_job_id.setPlaceholderText("Job")
        for w in (self.le_log_account_id,self.le_log_group_id,self.le_log_campaign_id,self.le_log_job_id): w.setMaximumWidth(130); w.editingFinished.connect(self._advanced_filters); a.addWidget(w)
        a.addStretch(); self.advanced_host.hide(); self.layout().insertWidget(4,self.advanced_host); self.btn_logs_advanced_filters.toggled.connect(self.advanced_host.setVisible)
        self.chk_log_date_filter.toggled.connect(self._advanced_filters); self.dt_log_from.dateTimeChanged.connect(self._advanced_filters); self.dt_log_to.dateTimeChanged.connect(self._advanced_filters)

    def _tab_changed(self,index:int):
        label=self.tab_logs.tabText(index)
        if label=="Audit":self.controller.set_filter("Category","Audit")
        elif label=="System":self.controller.set_filter("Category","System")
        elif label=="Errors":self.controller.set_filter("Level","Error")
        elif label=="Activity":self.controller.set_filter("Category","All")
    @staticmethod
    def _id(text): text=text.strip(); return int(text) if text.isdigit() else None
    def _advanced_filters(self):
        date_from=date_to=None
        if self.chk_log_date_filter.isChecked(): date_from=self.dt_log_from.dateTime().toUTC().toString(Qt.DateFormat.ISODate); date_to=self.dt_log_to.dateTime().toUTC().toString(Qt.DateFormat.ISODate)
        self.controller.set_advanced_filters(account_id=self._id(self.le_log_account_id.text()),group_id=self._id(self.le_log_group_id.text()),campaign_id=self._id(self.le_log_campaign_id.text()),job_id=self._id(self.le_log_job_id.text()),date_from=date_from,date_to=date_to)
    def context_menu(self,pos:QPoint):
        menu=QMenu(self); details=menu.addAction("Open Details"); menu.addSeparator(); imp=menu.addAction("Import Logs CSV"); chosen=menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is details:self.details()
        elif chosen is imp:
            path,_=QFileDialog.getOpenFileName(self,"Import Logs","","CSV Files (*.csv)")
            if path:self.controller.import_csv(path)
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Logs","logs.csv","CSV Files (*.csv)")
        if path:self.controller.export_csv(path)
    def details(self):
        row=self.selected_row()
        if row:QMessageBox.information(self,"Log Details","\n".join(f"{k}: {v}" for k,v in row.items()))
