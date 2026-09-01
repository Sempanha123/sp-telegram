from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.operations.resource_locks import ResourceLockManager
from app.utils.formatters import utc_now_iso


class DatabaseMaintenanceService:
    def __init__(self, database, *, log_repository=None, alert_repository=None, job_repository=None,
                 resource_locks: ResourceLockManager | None = None) -> None:
        self.database = database
        self.logs = log_repository
        self.alerts = alert_repository
        self.jobs = job_repository
        self.locks = resource_locks
        self.last_integrity_check: str | None = None
        self.last_integrity_result: str | None = None

    def integrity_check(self) -> dict:
        row = self.database.fetch_one("PRAGMA integrity_check")
        result = str(row[0] if row else "unknown")
        self.last_integrity_check = utc_now_iso(); self.last_integrity_result = result
        return {"ok": result.lower() == "ok", "result": result, "checked_at": self.last_integrity_check}

    def checkpoint_wal(self, mode: str = "PASSIVE") -> dict:
        mode = mode.upper() if mode.upper() in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"} else "PASSIVE"
        row = self.database.fetch_one(f"PRAGMA wal_checkpoint({mode})")
        values = list(row) if row else [0, 0, 0]
        return {"busy": int(values[0]), "log_frames": int(values[1]), "checkpointed_frames": int(values[2])}

    def analyze(self) -> bool:
        self.database.execute("ANALYZE")
        return True

    def vacuum(self) -> bool:
        lock_ctx = self.locks.hold("DATABASE_MAINTENANCE", "database", "DATABASE_MAINTENANCE") if self.locks else None
        if lock_ctx:
            with lock_ctx:
                self.database.execute("VACUUM")
        else:
            self.database.execute("VACUUM")
        return True

    def cleanup_old_logs(self, days: int) -> int:
        if not self.logs: return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
        return int(self.logs.clear_old_logs(cutoff))

    def cleanup_old_resolved_alerts(self, days: int) -> int:
        if not self.alerts: return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
        return int(self.alerts.cleanup_resolved_before(cutoff))

    def cleanup_old_completed_jobs(self, days: int) -> int:
        if not self.jobs: return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
        cursor = self.database.execute(
            "DELETE FROM job_items WHERE job_id IN (SELECT id FROM jobs WHERE status IN ('COMPLETED','CANCELLED','STOPPED') AND COALESCE(finished_at,updated_at) < ?)",
            (cutoff,),
        )
        return int(cursor.rowcount)

    def cleanup_temp_files(self, temp_dir: str | Path, *, older_than_days: int = 7) -> int:
        folder = Path(temp_dir)
        if not folder.exists(): return 0
        cutoff = datetime.now(timezone.utc).timestamp() - max(1, int(older_than_days)) * 86400
        removed = 0
        for item in folder.iterdir():
            if not item.is_file(): continue
            try:
                if item.stat().st_mtime < cutoff:
                    item.unlink(); removed += 1
            except OSError:
                continue
        return removed

    def run_retention(self, settings) -> dict:
        log_days = int(settings.get("log_retention_days", 90))
        alert_days = int(settings.get("alert_retention_days", 90))
        job_days = int(settings.get("job_retention_days", 180))
        return {
            "logs_removed": self.cleanup_old_logs(log_days),
            "alerts_removed": self.cleanup_old_resolved_alerts(alert_days),
            "job_items_removed": self.cleanup_old_completed_jobs(job_days),
        }

    def database_stats(self) -> dict:
        db = Path(self.database.db_path); wal = Path(str(db) + "-wal")
        page_count = self.database.fetch_one("PRAGMA page_count")
        page_size = self.database.fetch_one("PRAGMA page_size")
        return {
            "path": str(db), "size_bytes": db.stat().st_size if db.exists() else 0,
            "wal_bytes": wal.stat().st_size if wal.exists() else 0,
            "page_count": int(page_count[0] if page_count else 0),
            "page_size": int(page_size[0] if page_size else 0),
            "schema_version": self.database.get_schema_version(),
            "last_integrity_check": self.last_integrity_check,
            "last_integrity_result": self.last_integrity_result,
        }

    def optimize(self) -> dict:
        integrity = self.integrity_check()
        checkpoint = self.checkpoint_wal("PASSIVE")
        self.analyze()
        return {"integrity": integrity, "checkpoint": checkpoint}
