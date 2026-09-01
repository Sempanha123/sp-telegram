from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import threading
from typing import Iterator


@dataclass(frozen=True)
class ResourceLock:
    resource_type: str
    resource_id: str
    operation: str
    owner: str


class ResourceConflictError(RuntimeError):
    pass


class ResourceLockManager:
    """Coordinates conflicting write operations without over-locking reads."""

    WRITE_OPERATIONS = {
        "LOGOUT", "CAMPAIGN_SEND", "MEMBER_SYNC", "GROUP_WRITE", "RESTORE",
        "DATABASE_MAINTENANCE", "ACCOUNT_MUTATION", "SCHEDULE_WRITE",
    }

    def __init__(self) -> None:
        self._guard = threading.RLock()
        self._locks: dict[tuple[str, str], ResourceLock] = {}

    def acquire(self, resource_type: str, resource_id: int | str, operation: str, owner: str = "LOCAL") -> ResourceLock:
        key = (str(resource_type).upper(), str(resource_id))
        operation = str(operation).upper()
        with self._guard:
            current = self._locks.get(key)
            if current and operation in self.WRITE_OPERATIONS:
                raise ResourceConflictError(
                    f"{key[0].title()} {key[1]} is currently used by {current.operation.replace('_', ' ').title()}."
                )
            lock = ResourceLock(key[0], key[1], operation, owner)
            if operation in self.WRITE_OPERATIONS:
                self._locks[key] = lock
            return lock

    def release(self, lock: ResourceLock) -> None:
        key = (lock.resource_type, lock.resource_id)
        with self._guard:
            if self._locks.get(key) == lock:
                self._locks.pop(key, None)

    def current(self, resource_type: str, resource_id: int | str) -> ResourceLock | None:
        with self._guard:
            return self._locks.get((str(resource_type).upper(), str(resource_id)))

    def has_active_writes(self) -> bool:
        with self._guard:
            return bool(self._locks)

    @contextmanager
    def hold(self, resource_type: str, resource_id: int | str, operation: str, owner: str = "LOCAL") -> Iterator[ResourceLock]:
        lock = self.acquire(resource_type, resource_id, operation, owner)
        try:
            yield lock
        finally:
            self.release(lock)
