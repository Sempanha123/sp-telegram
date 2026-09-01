from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from app.constants import WorkerState
from app.operations.retry_policy import RetryPolicy


class RecoveryManager:
    """Safe technical recovery only. Telegram restrictions are never bypassed."""

    def __init__(self, worker_registry, recovery_repository=None, alert_manager=None, resource_locks=None, database=None,
                 *, max_restarts: int = 3, restart_window_minutes: int = 15) -> None:
        self.workers = worker_registry
        self.repository = recovery_repository
        self.alerts = alert_manager
        self.resource_locks = resource_locks
        self.database = database
        self.max_restarts = max(1, int(max_restarts))
        self.restart_window = timedelta(minutes=max(1, int(restart_window_minutes)))
        self._history: dict[str, deque[datetime]] = defaultdict(deque)
        self._history_lock = threading.Lock()
        self._restart_callbacks: dict[str, callable] = {}

    def register_worker_restart(self, worker_name: str, callback) -> None:
        self._restart_callbacks[worker_name] = callback

    def _within_limit(self, worker_name: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._history_lock:
            history = self._history[worker_name]
            cutoff = now - self.restart_window
            while history and history[0] < cutoff:
                history.popleft()
            return len(history) < self.max_restarts

    def restart_worker(self, worker_name: str, *, automatic: bool = False) -> bool:
        record = self.workers.get(worker_name)
        if not record or record.state not in {WorkerState.FAILED, WorkerState.UNRESPONSIVE, WorkerState.STOPPED}:
            return False
        if self.resource_locks and self.resource_locks.has_active_writes():
            return False
        if self.database and self.database.has_active_transactions():
            return False
        if automatic and not self._within_limit(worker_name):
            if self.alerts:
                self.alerts.raise_alert(
                    "CRITICAL", "WORKER_RESTART_LIMIT", f"{worker_name} auto-recovery stopped",
                    "The worker exceeded the configured automatic restart limit and requires operator review.",
                    dedupe_key=f"worker-restart-limit:{worker_name}", source_type="WORKER", source_id=worker_name,
                    requires_action=True, action_type="REVIEW_WORKER",
                )
            return False
        callback = self._restart_callbacks.get(worker_name)
        if callback is None: return False
        event = self.repository.start("WORKER", "WORKER_RESTART", worker_name, "restart") if self.repository else None
        # Count every restart attempt, including failed callbacks, so a broken worker cannot
        # enter an endless automatic restart loop.
        with self._history_lock:
            self._history[worker_name].append(datetime.now(timezone.utc))
        self.workers.increment_restart(worker_name)
        try:
            self.workers.set_state(worker_name, WorkerState.STARTING)
            restarted = callback()
            if restarted is False:
                raise RuntimeError("Worker restart callback declined the restart.")
            self.workers.set_state(worker_name, WorkerState.RUNNING)
            if event: self.repository.finish(event.id, "SUCCESS")
            return True
        except Exception as exc:
            self.workers.set_state(worker_name, WorkerState.FAILED, str(exc))
            if event: self.repository.finish(event.id, "FAILED", str(exc))
            return False

    def classify_retry(self, error_code: str | None, message: str | None = None):
        return RetryPolicy.classify(error_code, message)

    def can_auto_retry(self, error_code: str | None, message: str | None = None) -> bool:
        return str(self.classify_retry(error_code, message)) in {"SAFE_RETRY", "WAIT_AND_RETRY"}
