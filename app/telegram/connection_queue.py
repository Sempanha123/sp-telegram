from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum


class ConnectionQueueStatus(str, Enum):
    PENDING = "PENDING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ConnectionQueueItem:
    account_id: int
    status: ConnectionQueueStatus = ConnectionQueueStatus.PENDING
    error: str | None = None


class AccountConnectionQueue:
    """Resource-stability queue, not a restriction/rate-limit rotation mechanism."""

    def __init__(self, max_concurrency: int = 3) -> None:
        self.max_concurrency = max(1, int(max_concurrency))
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    async def run(self, account_ids: list[int], operation):
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results: list[ConnectionQueueItem] = []

        async def one(account_id: int):
            item = ConnectionQueueItem(account_id)
            results.append(item)
            if self.cancelled:
                item.status = ConnectionQueueStatus.CANCELLED
                return
            async with semaphore:
                if self.cancelled:
                    item.status = ConnectionQueueStatus.CANCELLED
                    return
                item.status = ConnectionQueueStatus.CONNECTING
                try:
                    await operation(account_id)
                    item.status = ConnectionQueueStatus.CONNECTED
                except Exception as exc:
                    item.status = ConnectionQueueStatus.FAILED
                    item.error = str(exc)

        await asyncio.gather(*(one(account_id) for account_id in account_ids))
        return results
