from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class OperationsController(QObject):
    operationsChanged = Signal(dict)
    diagnosticsReady = Signal(object)
    securityAuditReady = Signal(object)
    maintenanceCompleted = Signal(str, object)
    backupCompleted = Signal(object)
    restoreCompleted = Signal(object)
    errorOccurred = Signal(str)
    toast_requested = Signal(str, str)
    featureLocked = Signal(str, str)

    def __init__(self, manager, diagnostics, maintenance, backup_service, security_audit,
                 task_runner, app_lock_service=None, audit_repository=None, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.diagnostics = diagnostics
        self.maintenance = maintenance
        self.backups = backup_service
        self.security_audit = security_audit
        self.runner = task_runner
        self.app_lock = app_lock_service
        self.audit = audit_repository
        self._tasks: dict[str, tuple[str, object, int | None]] = {}
        self.feature_gate = None
        self.runner.taskCompleted.connect(self._task_completed)
        self.runner.taskFailed.connect(self._task_failed)


    def _require(self, feature) -> bool:
        if self.feature_gate is None:return True
        if self.feature_gate.has_feature(feature):return True
        self.featureLocked.emit(str(feature), str(self.feature_gate.get_required_plan(feature) or "ULTIMATE"));return False

    def refresh(self) -> dict:
        try:
            data = self.manager.refresh(); self.operationsChanged.emit(data); return data
        except Exception as exc:
            self._error(exc); return {}

    def pause_all(self) -> None:
        self.manager.pause_all(); self.toast_requested.emit("All new outgoing/network write operations are paused. Monitoring and local database reads remain available.", "Warning"); self.refresh()

    def resume_all(self) -> None:
        previous = str(self.manager.state)
        self.manager.resume_all()
        if str(self.manager.state) == "DEGRADED" and self.manager.system_monitor.jobs.count_by_status("RECONCILE_REQUIRED"):
            self.toast_requested.emit("Operations remain degraded because one or more outgoing jobs require reconciliation before resuming safely.", "Warning")
        else:
            self.toast_requested.emit("Safe operations resumed.", "Success")
        self.refresh()

    def restart_failed_workers(self) -> dict[str, bool]:
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SAFE_RECOVERY):return {}
        results = self.manager.restart_failed_workers(automatic=False)
        success = sum(1 for value in results.values() if value)
        failed = len(results) - success
        self.toast_requested.emit(f"Worker restart review completed: {success} restarted, {failed} not restarted.", "Info" if failed else "Success")
        self.refresh(); return results

    def restart_worker(self, worker_name: str) -> bool:
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SAFE_RECOVERY):return False
        if not worker_name:
            return False
        result = self.manager.recovery.restart_worker(worker_name, automatic=False)
        self.refresh()
        if result:
            self.toast_requested.emit(f"{worker_name} restarted safely.", "Success")
        else:
            self.toast_requested.emit(f"{worker_name} could not be restarted safely.", "Warning")
        return bool(result)

    def run_diagnostics(self) -> str:
        return self._submit("diagnostics", self.diagnostics.collect)

    def run_security_audit(self) -> str:
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SECURITY_AUDIT):return ""
        return self._submit("security_audit", self.security_audit.run)

    def run_integrity_check(self) -> str:
        return self._submit("integrity", self.maintenance.integrity_check)

    def checkpoint_database(self) -> str:
        return self._submit("checkpoint", self.maintenance.checkpoint_wal, "PASSIVE")

    def optimize_database(self) -> str:
        return self._submit("optimize", self.maintenance.optimize)

    def vacuum_database(self) -> str:
        return self._submit("vacuum", self.maintenance.vacuum)

    def run_database_maintenance(self) -> str:
        return self._submit("maintenance", self.maintenance.run_retention, self.manager.settings)

    def open_critical_alerts(self):
        return self.manager.system_monitor.alerts.get_all(status="ACTIVE", severity="CRITICAL")

    def run_backup(self, destination=None) -> str:
        return self._submit("backup", self.backups.create_backup, destination)

    def verify_backup(self, folder) -> str:
        return self._submit("verify_backup", self.backups.verify_backup, folder)

    def restore_backup(self, folder) -> str:
        self.manager.enter_maintenance()
        return self._submit("restore", self.backups.restore_backup, folder)

    def export_diagnostics(self, path) -> str:
        return self._submit("export_diagnostics", self.diagnostics.export, path)

    def create_support_bundle(self, path) -> str:
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.SUPPORT_BUNDLE):return ""
        return self._submit("support_bundle", self.diagnostics.create_support_bundle, path)

    def database_stats(self) -> dict:
        return self.maintenance.database_stats()

    def lock_application(self) -> None:
        from app.license.feature_keys import FeatureKey
        if not self._require(FeatureKey.APP_LOCK):return
        if self.app_lock:
            self.app_lock.lock()

    def _submit(self, kind: str, func, *args) -> str:
        try:
            job_types = {
                "diagnostics": "SYSTEM_DIAGNOSTIC", "security_audit": "SYSTEM_DIAGNOSTIC",
                "backup": "DATABASE_BACKUP", "restore": "DATABASE_MAINTENANCE",
                "integrity": "DATABASE_MAINTENANCE", "checkpoint": "DATABASE_MAINTENANCE",
                "optimize": "DATABASE_MAINTENANCE", "vacuum": "DATABASE_MAINTENANCE", "maintenance": "DATABASE_MAINTENANCE",
            }
            job_id = None
            job_type = job_types.get(kind)
            if job_type:
                job = self.manager.system_monitor.jobs.create_job(job_type, status="RUNNING", resource_type="SYSTEM", resource_id=kind)
                job_id = job.id
            token = self.runner.submit(func, *args); self._tasks[token] = (kind, args, job_id); return token
        except Exception as exc:
            self._error(exc); return ""

    def _task_completed(self, token: str, result) -> None:
        info = self._tasks.pop(token, None)
        if not info: return
        kind, _args, job_id = info
        if job_id:
            self.manager.system_monitor.jobs.update_progress(job_id, 100)
            self.manager.system_monitor.jobs.update_status(job_id, "COMPLETED")
        if kind == "diagnostics": self.diagnosticsReady.emit(result)
        elif kind == "security_audit": self.securityAuditReady.emit(result)
        elif kind == "backup":
            self.backups.enforce_retention(int(self.backups.settings.get("backup_retention_count", 10)))
            self.backupCompleted.emit(result); self.toast_requested.emit("Backup completed successfully. Telegram session files were excluded.", "Success")
        elif kind == "restore":
            self.manager.leave_maintenance(); self.restoreCompleted.emit(result); self.toast_requested.emit("Backup restored successfully after safety backup and validation.", "Success")
        else:
            self.maintenanceCompleted.emit(kind, result)
            messages = {"integrity": "Database integrity check completed.", "checkpoint": "WAL checkpoint completed.", "optimize": "Database optimization completed.", "vacuum": "Database vacuum completed.", "verify_backup": "Backup verification completed.", "export_diagnostics": "Diagnostics exported.", "support_bundle": "Sanitized support bundle created."}
            self.toast_requested.emit(messages.get(kind, f"{kind.replace('_',' ').title()} completed."), "Success")
        self.refresh()

    def _task_failed(self, token: str, message: str) -> None:
        info = self._tasks.pop(token, None)
        kind = info[0] if info else "operation"
        job_id = info[2] if info and len(info) > 2 else None
        if job_id:
            self.manager.system_monitor.jobs.update_status(job_id, "FAILED", error=message, retry_classification="USER_ACTION_REQUIRED")
        if kind == "restore": self.manager.leave_maintenance()
        self.errorOccurred.emit(message); self.toast_requested.emit(message, "Error")

    def _error(self, exc: Exception) -> None:
        message = str(exc) or "The operations task could not be completed."
        self.errorOccurred.emit(message); self.toast_requested.emit(message, "Error")
