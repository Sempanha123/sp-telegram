from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.telegram.result import AccountRuntimeState
from app.utils.formatters import utc_now_iso

_LOG = logging.getLogger(__name__)


class SessionConflictError(RuntimeError):
    pass


class TelegramClientManager(QObject):
    """Owns exactly one active Telethon client per local account/session."""

    runtimeStateChanged = Signal(int, object)

    def __init__(self, config_service, client_factory: Callable[..., Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.config_service = config_service
        self._client_factory = client_factory
        self._clients: dict[int, Any] = {}
        self._session_paths: dict[int, str] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._runtime: dict[int, AccountRuntimeState] = {}

    def _lock(self, account_id: int) -> asyncio.Lock:
        lock = self._locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[account_id] = lock
        return lock

    def runtime_state(self, account_id: int) -> AccountRuntimeState:
        return self._runtime.setdefault(account_id, AccountRuntimeState(account_id))

    def _emit_state(self, account_id: int) -> None:
        self.runtimeStateChanged.emit(account_id, self.runtime_state(account_id))

    def _build_client(self, session_path: str):
        api_id, api_hash = self.config_service.require_credentials()
        if self._client_factory:
            return self._client_factory(session_path, api_id, api_hash)
        try:
            from telethon import TelegramClient
        except ImportError as exc:  # pragma: no cover - installation issue
            raise RuntimeError("Telethon is not installed. Run: python -m pip install -r requirements.txt") from exc
        return TelegramClient(session_path, api_id, api_hash)

    async def create_client(self, account_id: int, session_path: str):
        normalized = str(Path(session_path).resolve())
        async with self._lock(account_id):
            existing = self._clients.get(account_id)
            if existing is not None:
                current = self._session_paths.get(account_id)
                if current != normalized:
                    raise SessionConflictError("This account already has a client using another session path.")
                return existing
            for other_id, other_path in self._session_paths.items():
                if other_id != account_id and other_path == normalized and other_id in self._clients:
                    raise SessionConflictError("Session Conflict: another account is already using this session file.")
            Path(normalized).parent.mkdir(parents=True, exist_ok=True)
            client = self._build_client(normalized)
            self._clients[account_id] = client
            self._session_paths[account_id] = normalized
            self.runtime_state(account_id)
            return client

    async def get_client(self, account_id: int):
        return self._clients.get(account_id)

    async def connect(self, account_id: int):
        async with self._lock(account_id):
            client = self._clients.get(account_id)
            if client is None:
                raise RuntimeError("Telegram client has not been created for this account.")
            state = self.runtime_state(account_id)
            state.connecting = True
            state.last_connect_attempt = utc_now_iso()
            self._emit_state(account_id)
            try:
                if not client.is_connected():
                    await client.connect()
                state.connected = bool(client.is_connected())
                state.authorized = bool(await client.is_user_authorized())
                state.last_runtime_error = None
                return client
            except Exception as exc:
                state.connected = False
                state.last_runtime_error = type(exc).__name__
                raise
            finally:
                state.connecting = False
                self._emit_state(account_id)

    async def disconnect(self, account_id: int):
        client = self._clients.get(account_id)
        if client is None:
            return False
        async with self._lock(account_id):
            if client.is_connected():
                await client.disconnect()
            state = self.runtime_state(account_id)
            state.connected = False
            self._emit_state(account_id)
            return True

    async def is_connected(self, account_id: int) -> bool:
        client = self._clients.get(account_id)
        return bool(client and client.is_connected())

    async def is_authorized(self, account_id: int) -> bool:
        client = self._clients.get(account_id)
        if client is None:
            return False
        authorized = bool(await client.is_user_authorized())
        self.runtime_state(account_id).authorized = authorized
        self._emit_state(account_id)
        return authorized

    async def remove_client(self, account_id: int):
        async with self._lock(account_id):
            client = self._clients.pop(account_id, None)
            self._session_paths.pop(account_id, None)
            if client is not None and client.is_connected():
                await client.disconnect()
            self._runtime.pop(account_id, None)
        # Lock cleanup deferred to disconnect_all() to avoid destroying
        # a lock while it is still held by this context manager.
        return True

    async def disconnect_all(self):
        for account_id in list(self._clients):
            try:
                await self.disconnect(account_id)
            except Exception as exc:
                _LOG.warning("Telegram client disconnect failed during shutdown for account %s: %s", account_id, exc)
        self._clients.clear()
        self._session_paths.clear()
        self._locks.clear()
        self._runtime.clear()
