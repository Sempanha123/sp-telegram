from __future__ import annotations


class SystemMonitor:
    def __init__(self, *, account_monitor, group_monitor, performance_monitor, worker_registry,
                 job_repository, alert_repository, database) -> None:
        self.account_monitor = account_monitor
        self.group_monitor = group_monitor
        self.performance_monitor = performance_monitor
        self.workers = worker_registry
        self.jobs = job_repository
        self.alerts = alert_repository
        self.database = database

    def snapshot(self) -> dict:
        accounts = self.account_monitor.snapshot()
        groups = self.group_monitor.snapshot()
        workers = self.workers.all()
        performance = self.performance_monitor.sample()
        db_ok = True
        try:
            row = self.database.fetch_one("SELECT 1 AS ok")
            db_ok = bool(row and row["ok"] == 1)
        except Exception:
            db_ok = False
        return {
            "database": {"state": "HEALTHY" if db_ok else "ERROR", "schema": self.database.get_schema_version()},
            "accounts": accounts,
            "groups": groups,
            "jobs": {
                "running": self.jobs.count_by_status("RUNNING"), "queued": self.jobs.count_by_status("QUEUED"),
                "paused": self.jobs.count_by_status("PAUSED"), "failed": self.jobs.count_by_status("FAILED"),
                "reconcile": self.jobs.count_by_status("RECONCILE_REQUIRED"),
            },
            "alerts": {
                "critical": self.alerts.count_open("CRITICAL"), "warning": self.alerts.count_open("WARNING"),
                "open": self.alerts.count_open(),
            },
            "workers": [vars(w).copy() for w in workers],
            "performance": performance,
        }
