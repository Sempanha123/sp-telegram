from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionPoolStatus:
    active_clients: int
    maximum_active_clients: int


class TelegramSessionPool:
    """Lazy resource-stability facade over TelegramClientManager.

    Clients are initialized only for an explicit operation. The pool is a
    concurrency/resource guard, not a workload-rotation mechanism: it has no API
    that reassigns an in-flight job after Telegram restrictions.
    """

    def __init__(self, client_manager, account_repository, *, max_active_clients: int = 3):
        self.client_manager = client_manager
        self.accounts = account_repository
        self.max_active_clients = max(1, int(max_active_clients or 3))
        self._lock = asyncio.Lock()

    async def status(self) -> SessionPoolStatus:
        """Return a consistent snapshot of the pool under the pool lock.

        Acquiring ``self._lock`` prevents the count from being read mid-way
        through a concurrent ``ensure_client``/``create_client`` mutation, so
        callers never observe a stale ``active_clients`` value (BUG-016).
        """
        async with self._lock:
            clients = getattr(self.client_manager, "_clients", {})
            return SessionPoolStatus(len(clients), self.max_active_clients)

    async def ensure_client(self, account_id: int):
        account_id = int(account_id)
        existing = await self.client_manager.get_client(account_id)
        if existing is not None:
            return existing
        account = self.accounts.get_by_id(account_id)
        if not account:
            raise ValueError("Telegram account does not exist.")
        session_path = str(getattr(account, "session_path", "") or "")
        if not session_path or not Path(session_path).is_file():
            raise ValueError("Telegram session is missing. Login to this account first.")

        async with self._lock:
            # Check limit inside lock to avoid TOCTOU
            clients = getattr(self.client_manager, "_clients", {})
            if len(clients) >= self.max_active_clients:
                raise RuntimeError(
                    f"Telegram client concurrency limit reached ({self.max_active_clients}). "
                    "Disconnect an idle client or increase the operational concurrency setting."
                )
            return await self.client_manager.create_client(account_id, session_path)
