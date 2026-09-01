from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import RLock

from app.constants import WorkerState
from app.utils.formatters import utc_now_iso


@dataclass
class WorkerRecord:
    name: str
    state: str = WorkerState.STOPPED
    started_at: str | None = None
    last_heartbeat_at: str | None = None
    tasks_processed: int = 0
    last_error: str | None = None
    restart_count: int = 0


class WorkerRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._workers: dict[str, WorkerRecord] = {}

    def register(self, name: str, state: str = WorkerState.STARTING) -> WorkerRecord:
        now = utc_now_iso()
        with self._lock:
            record = self._workers.get(name) or WorkerRecord(name=name)
            record.state = str(state)
            if record.started_at is None and str(state) in {WorkerState.STARTING, WorkerState.RUNNING, WorkerState.IDLE}:
                record.started_at = now
            record.last_heartbeat_at = now
            self._workers[name] = record
            return record

    def set_state(self, name: str, state: str, error: str | None = None) -> WorkerRecord:
        with self._lock:
            record = self._workers.get(name) or self.register(name)
            record.state = str(state)
            if error:
                record.last_error = str(error)
            record.last_heartbeat_at = utc_now_iso()
            return record

    def heartbeat(self, name: str, *, tasks_processed_increment: int = 0) -> None:
        with self._lock:
            record = self._workers.get(name) or self.register(name)
            record.last_heartbeat_at = utc_now_iso()
            record.tasks_processed += max(0, int(tasks_processed_increment))
            if record.state in {WorkerState.STARTING, WorkerState.UNRESPONSIVE}:
                record.state = WorkerState.RUNNING

    def increment_restart(self, name: str) -> int:
        with self._lock:
            record = self._workers.get(name) or self.register(name)
            record.restart_count += 1
            record.last_heartbeat_at = utc_now_iso()
            return record.restart_count

    def get(self, name: str) -> WorkerRecord | None:
        with self._lock:
            return self._workers.get(name)

    def all(self) -> list[WorkerRecord]:
        with self._lock:
            return [WorkerRecord(**asdict(item)) for item in self._workers.values()]

    def mark_stale(self, threshold_seconds: int = 60) -> list[str]:
        now = datetime.now(timezone.utc)
        stale: list[str] = []
        with self._lock:
            for name, record in self._workers.items():
                if not record.last_heartbeat_at or record.state not in {WorkerState.RUNNING, WorkerState.IDLE, WorkerState.STARTING}:
                    continue
                try:
                    stamp = datetime.fromisoformat(record.last_heartbeat_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if (now - stamp).total_seconds() > threshold_seconds:
                    record.state = WorkerState.UNRESPONSIVE
                    stale.append(name)
        return stale
