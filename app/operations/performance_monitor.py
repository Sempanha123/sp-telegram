from __future__ import annotations

import os
from pathlib import Path
import sys
import time
import shutil


class PerformanceMonitor:
    """Low-overhead process/database metrics without an external metrics dependency."""

    def __init__(self, database, job_repository=None, worker_registry=None) -> None:
        self.database = database
        self.jobs = job_repository
        self.workers = worker_registry
        self._last_wall = time.perf_counter()
        self._last_cpu = time.process_time()
        self.telegram_queue_provider = None

    def _memory_bytes(self) -> int | None:
        try:
            import resource
            value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            # Linux reports KiB; macOS reports bytes.
            return value if sys.platform == "darwin" else value * 1024
        except Exception:
            return None

    def sample(self) -> dict[str, object]:
        now_wall = time.perf_counter(); now_cpu = time.process_time()
        wall_delta = max(0.001, now_wall - self._last_wall); cpu_delta = max(0.0, now_cpu - self._last_cpu)
        cpu_percent = min(100.0 * max(1, os.cpu_count() or 1), (cpu_delta / wall_delta) * 100.0)
        self._last_wall, self._last_cpu = now_wall, now_cpu
        db = Path(self.database.db_path)
        wal = Path(str(db) + "-wal")
        workers = self.workers.all() if self.workers else []
        running = self.jobs.count_by_status("RUNNING") if self.jobs else 0
        queued = self.jobs.count_by_status("QUEUED") if self.jobs else 0
        disk = shutil.disk_usage(db.parent if db.parent.exists() else Path.cwd())
        queues = self.jobs.queue_summary() if self.jobs and hasattr(self.jobs, "queue_summary") else {}
        telegram_pending = 0
        if callable(self.telegram_queue_provider):
            try:
                telegram_pending = max(0, int(self.telegram_queue_provider()))
            except (TypeError, ValueError, RuntimeError):
                telegram_pending = 0
        queues = {"Telegram Queue": {"pending": telegram_pending, "running": 0, "oldest": None}, **queues}
        return {
            "cpu_percent": round(cpu_percent, 1),
            "memory_bytes": self._memory_bytes(),
            "database_bytes": db.stat().st_size if db.exists() else 0,
            "wal_bytes": wal.stat().st_size if wal.exists() else 0,
            "disk_free_bytes": int(disk.free),
            "running_jobs": running,
            "queue_length": queued + telegram_pending,
            "queue_breakdown": queues,
            "workers_total": len(workers),
            "workers_running": sum(str(w.state) in {"RUNNING", "IDLE"} for w in workers),
            "sampled_at": time.time(),
        }
