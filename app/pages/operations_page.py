from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QPushButton,QTableView,QVBoxLayout,QWidget

from app.dialogs.diagnostics_dialog import DiagnosticsDialog
from app.dialogs.worker_details_dialog import WorkerDetailsDialog
from app.icons import IconManager
from app.models.base_table_model import BaseTableModel
from app.styles.tokens import TABLE_HEADER_HEIGHT,TABLE_ROW_HEIGHT
from app.widgets.loading_overlay import LoadingOverlay
from app.widgets.page_header import PageHeaderWidget
from app.widgets.section_card import SectionCard
from app.widgets.stat_card import StatCard
from app.widgets.summary_card import SummaryCard
from app.widgets.table_delegate import ModernTableDelegate
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout


class OperationsPage(QWidget):
    criticalAlertsRequested=Signal(); privacyModeRequested=Signal(); lockRequested=Signal()
    def __init__(self,controller,parent=None)->None:
        super().__init__(parent); self.setObjectName("page_operations"); self.controller=controller; self._table_layout=TableLayoutManager(self)
        root=QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(14)
        header=PageHeaderWidget("Operations Center","Monitor runtime health, workers, queues, recovery and maintenance.")
        for obj,text,slot in [("btn_operations_refresh","Refresh",controller.refresh),("btn_operations_pause_all","Pause All",controller.pause_all),("btn_operations_resume_all","Resume Safe",controller.resume_all),("btn_operations_run_diagnostics","Diagnostics",controller.run_diagnostics),("btn_operations_restart_workers","Restart Failed",controller.restart_failed_workers),("btn_operations_view_critical_alerts","Critical Alerts",lambda:self.criticalAlertsRequested.emit())]:
            b=QPushButton(text); b.setObjectName(obj); b.clicked.connect(slot); setattr(self,obj,b); header.add_action(b)
            if "refresh" in obj:b.setIcon(IconManager.get("refresh"))
            if "critical" in obj:b.setProperty("danger",True)
        root.addWidget(header)

        summaries=QGridLayout(); summaries.setSpacing(12)
        self.summary_system=SummaryCard("System","Starting","card_operations_summary_system"); self.summary_accounts=SummaryCard("Accounts",0,"card_operations_summary_accounts"); self.summary_jobs=SummaryCard("Jobs",0,"card_operations_summary_jobs"); self.summary_alerts=SummaryCard("Alerts",0,"card_operations_summary_alerts"); self.summary_workers=SummaryCard("Workers",0,"card_operations_summary_workers")
        for i,c in enumerate((self.summary_system,self.summary_accounts,self.summary_jobs,self.summary_alerts,self.summary_workers)): summaries.addWidget(c,0,i)
        root.addLayout(summaries)

        self.lbl_operational_state=QLabel("Starting"); self.lbl_telegram_state=QLabel("Unknown"); self.lbl_database_state=QLabel("Unknown"); self.lbl_workers_state=QLabel("—"); self.lbl_scheduler_state=QLabel("Running")
        self.cards={}; self._legacy_cards=[]
        for title,key in [("Healthy Accounts","account_ready"),("Account Warnings","account_warning"),("Cooldown","account_cooldown"),("Login Required","account_login"),("Running Jobs","jobs_running"),("Queued Jobs","jobs_queued"),("Paused Jobs","jobs_paused"),("Failed Jobs","jobs_failed"),("Critical Alerts","alerts_critical"),("Warnings","alerts_warning"),("Needs Reconcile","jobs_reconcile")]:
            c=StatCard(title,0,f"card_operations_{key}",self); c.hide(); self.cards[key]=c; self._legacy_cards.append(c)

        lower=QHBoxLayout(); lower.setSpacing(12)
        workers=SectionCard("Worker Status"); workers.setMinimumHeight(300); self.worker_model=BaseTableModel([], ["Name","State","Started","Last Heartbeat","Tasks","Last Error","Restarts"])
        self.tbl_operations_workers=QTableView(); self.tbl_operations_workers.setObjectName("tbl_operations_workers"); self.tbl_operations_workers.setModel(self.worker_model)
        self._modern_table(self.tbl_operations_workers, {
            "Name": ColumnLayout(180,150), "State": ColumnLayout(120,105,"contents"),
            "Started": ColumnLayout(190,165), "Last Heartbeat": ColumnLayout(190,165),
            "Tasks": ColumnLayout(90,80,"contents"), "Last Error": ColumnLayout(320,200,"stretch"),
            "Restarts": ColumnLayout(95,85,"contents"),
        })
        self.tbl_operations_workers.setMinimumHeight(220); self.tbl_operations_workers.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.tbl_operations_workers.horizontalHeader().setStretchLastSection(False); workers.body.addWidget(self.tbl_operations_workers,1)
        wr=QHBoxLayout(); self.btn_worker_details=QPushButton("Worker Details"); self.btn_worker_details.setObjectName("btn_worker_details"); self.btn_restart_failed_worker=QPushButton("Restart Failed Worker"); self.btn_restart_failed_worker.setObjectName("btn_restart_failed_worker"); wr.addWidget(self.btn_worker_details); wr.addWidget(self.btn_restart_failed_worker); wr.addStretch(); workers.body.addLayout(wr); self.btn_worker_details.clicked.connect(self._worker_details); self.btn_restart_failed_worker.clicked.connect(self._restart_selected_worker); lower.addWidget(workers,3)
        performance=SectionCard("Performance"); performance.setMinimumWidth(300); self._perf_labels={}
        for key in ["CPU","Memory","Database","WAL","Active Jobs","Queue","Workers"]:
            row=QHBoxLayout(); lab=QLabel(key); lab.setProperty("secondary",True); value=QLabel("—"); value.setProperty("emphasis",True); self._perf_labels[key]=value; row.addWidget(lab); row.addStretch(); row.addWidget(value); performance.body.addLayout(row)
        lower.addWidget(performance,1); root.addLayout(lower,1)

        queue=SectionCard("Queues"); self.queue_model=BaseTableModel([], ["Queue","Pending","Running","Oldest Item"]); self.tbl_operations_queues=QTableView(); self.tbl_operations_queues.setObjectName("tbl_operations_queues"); self.tbl_operations_queues.setModel(self.queue_model)
        self._modern_table(self.tbl_operations_queues, {
            "Queue": ColumnLayout(240,180), "Pending": ColumnLayout(130,110,"contents"),
            "Running": ColumnLayout(130,110,"contents"), "Oldest Item": ColumnLayout(360,220,"stretch"),
        })
        self.tbl_operations_queues.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection); self.tbl_operations_queues.setMinimumHeight(150); self.tbl_operations_queues.setMaximumHeight(240); queue.body.addWidget(self.tbl_operations_queues); root.addWidget(queue)

        tools=QHBoxLayout(); db=SectionCard("Database Maintenance"); dbrow=QHBoxLayout()
        for obj,text,slot in [("btn_database_integrity_check","Integrity Check",controller.run_integrity_check),("btn_database_checkpoint","WAL Checkpoint",controller.checkpoint_database),("btn_database_optimize","Optimize",controller.optimize_database),("btn_database_vacuum","Vacuum",self._vacuum),("btn_database_backup","Backup",controller.run_backup)]:
            b=QPushButton(text); b.setObjectName(obj); b.clicked.connect(slot); dbrow.addWidget(b); setattr(self,obj,b)
        dbrow.addStretch(); db.body.addLayout(dbrow); tools.addWidget(db,1)
        sec=SectionCard("Security & Diagnostics"); secrow=QHBoxLayout(); self.btn_run_security_audit=QPushButton("Security Audit"); self.btn_run_security_audit.setObjectName("btn_run_security_audit"); self.btn_run_security_audit.clicked.connect(controller.run_security_audit); self.btn_run_diagnostics=QPushButton("Diagnostics"); self.btn_run_diagnostics.setObjectName("btn_run_diagnostics"); self.btn_run_diagnostics.clicked.connect(controller.run_diagnostics); self.btn_privacy_mode=QPushButton("Privacy Mode"); self.btn_privacy_mode.setObjectName("btn_privacy_mode"); self.btn_privacy_mode.clicked.connect(self.privacyModeRequested); self.btn_lock_application=QPushButton("Lock Application"); self.btn_lock_application.setObjectName("btn_lock_application"); self.btn_lock_application.clicked.connect(self.lockRequested)
        for b in (self.btn_run_security_audit,self.btn_run_diagnostics,self.btn_privacy_mode,self.btn_lock_application):secrow.addWidget(b)
        secrow.addStretch(); sec.body.addLayout(secrow); tools.addWidget(sec,1); root.addLayout(tools)
        self.loading_overlay=LoadingOverlay(self); self.loading_overlay.hide(); root.addWidget(self.loading_overlay)
        self.btn_run_security_audit.clicked.connect(lambda:(self.loading_overlay.start("Running security audit…"), controller.run_security_audit()))
        self.btn_run_diagnostics.clicked.connect(lambda:(self.loading_overlay.start("Running diagnostics…"), controller.run_diagnostics()))
        controller.operationsChanged.connect(self.set_snapshot); controller.diagnosticsReady.connect(self._diagnostics_ready); controller.securityAuditReady.connect(self._security_ready); controller.maintenanceCompleted.connect(self._maintenance_done); self.set_snapshot(controller.refresh())

    def _modern_table(self, table, overrides=None):
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setShowGrid(False); table.setAlternatingRowColors(False); table.verticalHeader().setVisible(False); table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT); table.horizontalHeader().setFixedHeight(TABLE_HEADER_HEIGHT); table.setItemDelegate(ModernTableDelegate(table))
        model=table.model(); columns=list(getattr(model,"columns",[]) or [])
        if columns:self._table_layout.apply(table,columns,overrides=overrides or {})

    def set_snapshot(self,data:dict)->None:
        if not data:return
        state=str(self.controller.manager.state).replace("_"," ").title(); self.lbl_operational_state.setText(f"● {state}"); dbstate=data.get("database",{}).get("state","Unknown").title(); tg=self.controller.manager.network.telegram_state.title(); self.lbl_database_state.setText(f"● {dbstate}"); self.lbl_telegram_state.setText(f"● {tg}")
        workers=data.get("workers",[]); running=sum(str(w.get("state")) in {"RUNNING","IDLE"} for w in workers); self.lbl_workers_state.setText(f"● {running} / {len(workers)} Running")
        ac=data.get("accounts",{}).get("counts",{}); jobs=data.get("jobs",{}); alerts=data.get("alerts",{}); values={"account_ready":ac.get("READY",0),"account_warning":ac.get("WARNING",0),"account_cooldown":ac.get("COOLDOWN",0),"account_login":ac.get("LOGIN_REQUIRED",0),"jobs_running":jobs.get("running",0),"jobs_queued":jobs.get("queued",0),"jobs_paused":jobs.get("paused",0),"jobs_failed":jobs.get("failed",0),"jobs_reconcile":jobs.get("reconcile",0),"alerts_critical":alerts.get("critical",0),"alerts_warning":alerts.get("warning",0)}
        for key,value in values.items():self.cards[key].set_value(value)
        self.summary_system.set_value(state); self.summary_system.set_metrics([("Telegram",tg,"success" if tg.lower()=="ready" else "warning"),("Database",dbstate,"success" if dbstate.lower()=="healthy" else "warning"),("Scheduler","Running","success")])
        self.summary_accounts.set_value(int(values["account_ready"])); self.summary_accounts.set_metrics([("Ready",int(values["account_ready"]),"success"),("Warning",int(values["account_warning"]),"warning"),("Cooldown",int(values["account_cooldown"]),"warning"),("Login Required",int(values["account_login"]),"danger")])
        self.summary_jobs.set_value(int(values["jobs_running"])); self.summary_jobs.set_metrics([("Running",int(values["jobs_running"]),"success"),("Queued",int(values["jobs_queued"]),"primary"),("Failed",int(values["jobs_failed"]),"danger"),("Needs Review",int(values["jobs_reconcile"]),"warning")])
        self.summary_alerts.set_value(int(values["alerts_critical"])+int(values["alerts_warning"])); self.summary_alerts.set_metrics([("Critical",int(values["alerts_critical"]),"danger"),("Warnings",int(values["alerts_warning"]),"warning")])
        self.summary_workers.set_value(running); self.summary_workers.set_metrics([("Running",running,"success"),("Total",len(workers),"muted")])
        self.worker_model.replace_rows([{"Name":w.get("name"),"State":str(w.get("state","")).replace("_"," ").title(),"Started":w.get("started_at") or "—","Last Heartbeat":w.get("last_heartbeat_at") or "—","Tasks":w.get("tasks_processed",0),"Last Error":w.get("last_error") or "—","Restarts":w.get("restart_count",0)} for w in workers])
        p=data.get("performance",{}); self._perf_labels["CPU"].setText(f"{p.get('cpu_percent',0):.1f}%"); self._perf_labels["Memory"].setText(self._bytes(p.get("memory_bytes"))); self._perf_labels["Database"].setText(self._bytes(p.get("database_bytes"))); self._perf_labels["WAL"].setText(self._bytes(p.get("wal_bytes"))); self._perf_labels["Active Jobs"].setText(str(p.get("running_jobs",0))); self._perf_labels["Queue"].setText(str(p.get("queue_length",0))); self._perf_labels["Workers"].setText(f"{p.get('workers_running',0)} / {p.get('workers_total',0)}")
        queues=p.get("queue_breakdown",{}) or {}; self.queue_model.replace_rows([{"Queue":n,"Pending":i.get("pending",0),"Running":i.get("running",0),"Oldest Item":i.get("oldest") or "—"} for n,i in queues.items()])
    @staticmethod
    def _bytes(value):
        if value is None:return "Unavailable"
        value=float(value)
        for unit in ["B","KB","MB","GB"]:
            if value<1024 or unit=="GB":return f"{value:.1f} {unit}"
            value/=1024
    def _selected_worker_name(self):
        indexes=self.tbl_operations_workers.selectionModel().selectedRows(); return self.worker_model.row_dict(indexes[0].row()).get("Name") if indexes else None
    def _worker_details(self):
        name=self._selected_worker_name(); record=self.controller.manager.workers.get(name) if name else None
        if record:WorkerDetailsDialog(record,self).exec()
    def _restart_selected_worker(self):
        name=self._selected_worker_name()
        if not name:QMessageBox.information(self,"Restart Worker","Select a failed or unresponsive worker first.");return
        self.controller.restart_worker(name)
    def _vacuum(self):
        if QMessageBox.question(self,"Vacuum Database","Vacuum can take time and temporarily blocks database mutations. Pause operations and run Vacuum now?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.manager.pause_all();self.controller.vacuum_database()
    def _diagnostics_ready(self,report):
        self.loading_overlay.stop()
        dialog=DiagnosticsDialog(self.controller.diagnostics.to_text(report),self);dialog.exportRequested.connect(self.controller.export_diagnostics);dialog.exec()
    def _security_ready(self,result):
        self.loading_overlay.stop()
        QMessageBox.information(self,"Security Audit",f"Passed: {result.get('passed',0)}\nWarnings: {result.get('warnings',0)}\nCritical: {result.get('critical',0)}")
    def _maintenance_done(self,kind,result):
        if kind=="integrity":QMessageBox.information(self,"Database Integrity","Database integrity check passed." if result.get("ok") else f"Database integrity issue: {result.get('result')}")
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        safe_recovery=feature_gate.has_feature(FeatureKey.SAFE_RECOVERY)
        app_lock=feature_gate.has_feature(FeatureKey.APP_LOCK)
        security_audit=feature_gate.has_feature(FeatureKey.SECURITY_AUDIT)
        full_ops=feature_gate.has_feature(FeatureKey.FULL_OPERATIONS)
        for b in (self.btn_operations_restart_workers,self.btn_restart_failed_worker):
            b.setEnabled(safe_recovery);b.setToolTip("Safe technical recovery requires SP Telegram Pro or SP Telegram Ultimate." if not safe_recovery else "")
        self.btn_lock_application.setEnabled(app_lock);self.btn_lock_application.setToolTip("Application Lock requires SP Telegram Pro or SP Telegram Ultimate." if not app_lock else "")
        self.btn_run_security_audit.setEnabled(security_audit);self.btn_run_security_audit.setToolTip("Security Audit requires SP Telegram Ultimate." if not security_audit else "")
        # Safety-critical pause/resume, logs, diagnostics, database backup and integrity remain available on every plan.
        if not full_ops:
            self.btn_database_optimize.setToolTip("Core database maintenance remains available. Full Operations features require SP Telegram Ultimate.")
        return True
