from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.telegram.member_normalizer import TelegramMemberNormalizer
from app.telegram.models.member_sync_result import MemberSyncOptions


class TelegramMemberSyncService:
    """Read-only participant adapter.

    It never joins groups, invites users, rotates accounts, or attempts to work
    around hidden participant lists/restrictions.  Pause is checked *before* the
    next iterator request so a paused job does not intentionally request new
    participant pages.
    """

    def __init__(self, client_manager, normalizer: TelegramMemberNormalizer, error_handler):
        self.client_manager = client_manager
        self.normalizer = normalizer
        self.error_handler = error_handler
        self._pause: dict[str, asyncio.Event] = {}
        self._cancelled: set[str] = set()

    def create_control(self, sync_run_id: str):
        event = asyncio.Event()
        event.set()
        self._pause[sync_run_id] = event
        self._cancelled.discard(sync_run_id)

    def pause(self, sync_run_id: str):
        if sync_run_id in self._pause:
            self._pause[sync_run_id].clear()

    def resume(self, sync_run_id: str):
        if sync_run_id in self._pause:
            self._pause[sync_run_id].set()

    def stop(self, sync_run_id: str):
        self._cancelled.add(sync_run_id)
        if sync_run_id in self._pause:
            self._pause[sync_run_id].set()

    def cleanup(self, sync_run_id: str):
        self._pause.pop(sync_run_id, None)
        self._cancelled.discard(sync_run_id)

    async def iter_source_members(
        self, group_id: int, account_id: int, entity, options: MemberSyncOptions, sync_run_id: str
    ) -> AsyncIterator:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            raise RuntimeError("Telegram client is unavailable for the selected account.")
        self.create_control(sync_run_id)
        count = 0
        iterator = client.iter_participants(entity).__aiter__()
        try:
            while True:
                await self._pause[sync_run_id].wait()
                if sync_run_id in self._cancelled:
                    break
                try:
                    # Pause/cancel is checked before asking the adapter for the next
                    # participant.  Telethon remains responsible for its own paging.
                    user = await iterator.__anext__()
                except StopAsyncIteration:
                    break
                member = self.normalizer.normalize(user, group_id, account_id)
                yield member
                count += 1
                if options.max_records is not None and count >= max(0, options.max_records):
                    break
        finally:
            # Caller decides final status before cleanup; completed DB batches are
            # intentionally preserved on pause/stop/failure.
            pass
