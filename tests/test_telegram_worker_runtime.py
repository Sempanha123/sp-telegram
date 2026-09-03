from __future__ import annotations

import asyncio
import time

from app.telegram.workers.telegram_worker import TelegramWorkerThread


class _FakeClientManager:
    async def disconnect_all(self):
        await asyncio.sleep(0)


def test_telegram_worker_executes_coroutine_and_stops_cleanly(qapp):
    worker = TelegramWorkerThread(_FakeClientManager())
    completed: list[tuple[str, object]] = []
    failures: list[tuple[str, int, str]] = []
    worker.operationCompleted.connect(lambda token, result: completed.append((token, result)))
    worker.operationFailed.connect(lambda token, account_id, message: failures.append((token, account_id, message)))

    async def probe():
        await asyncio.sleep(0.01)
        return {"worker": "ok"}

    worker.start()
    token = worker.submit_coroutine(probe(), operation="qa_worker_probe", account_id=0)
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline and not completed and not failures:
            qapp.processEvents()
            time.sleep(0.01)
        assert not failures
        assert completed
        assert completed[0][0] == token
        assert completed[0][1] == {"worker": "ok"}
    finally:
        assert worker.shutdown(timeout_ms=3000)
        qapp.processEvents()
