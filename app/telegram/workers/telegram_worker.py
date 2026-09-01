from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import Future

from PySide6.QtCore import QThread, Signal

_LOG = logging.getLogger(__name__)


class TelegramWorkerThread(QThread):
    """Dedicated, long-lived asyncio loop for all Telethon clients."""

    operationCompleted = Signal(str, object)
    operationFailed = Signal(str, int, str)
    loopReady = Signal()
    heartbeat = Signal()

    accountConnecting = Signal(int)
    accountConnected = Signal(int)
    accountDisconnected = Signal(int)
    accountAuthorizationRequired = Signal(int)
    accountProfileUpdated = Signal(int, object)
    accountHealthUpdated = Signal(int, object)
    accountOperationFailed = Signal(int, str)
    loginStateChanged = Signal(int, str)
    loginCompleted = Signal(int)
    loginFailed = Signal(int, str)
    sessionListUpdated = Signal(int, list)

    def __init__(self, client_manager, parent=None) -> None:
        super().__init__(parent)
        self.client_manager = client_manager
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._accepting = True
        self._pending: list[tuple[str, object, int]] = []
        self._pending_lock = threading.Lock()

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self.loopReady.emit()
        with self._pending_lock:
            pending = list(self._pending)
            self._pending.clear()
        for token, coroutine, account_id in pending:
            self._schedule(token, coroutine, account_id)
        self._loop.create_task(self._heartbeat_loop())
        try:
            self._loop.run_forever()
        finally:
            pending_tasks = asyncio.all_tasks(self._loop)
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                self._loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
            self._loop.close()
            self._loop = None
            self._ready.clear()


    async def _heartbeat_loop(self) -> None:
        while self._accepting:
            self.heartbeat.emit()
            await asyncio.sleep(15)

    @property
    def pending_count(self) -> int:
        with self._pending_lock:
            return len(self._pending)

    def restart_safely(self) -> bool:
        """Restart the same QThread object after a technical failure/clean stop."""
        if self.isRunning():
            return False
        self._accepting = True
        self.start()
        return True

    def submit_coroutine(self, coroutine, *, operation: str, account_id: int = 0) -> str:
        if not self._accepting:
            try:
                coroutine.close()
            except Exception as exc:
                _LOG.debug("Could not close rejected coroutine cleanly: %s", exc)
            raise RuntimeError("Telegram worker is shutting down.")
        token = f"{operation}:{account_id}:{uuid.uuid4().hex}"
        # Capture ``_loop`` under the same lock that guards ``_pending`` so we
        # never race with ``run()`` clearing ``_loop`` during shutdown.
        with self._pending_lock:
            loop = self._loop
        if not self._ready.is_set() or loop is None:
            with self._pending_lock:
                self._pending.append((token, coroutine, account_id))
            return token
        self._schedule_on(loop, token, coroutine, account_id)
        return token

    def _schedule(self, token: str, coroutine, account_id: int) -> None:
        loop = self._loop
        if loop is None:
            return
        self._schedule_on(loop, token, coroutine, account_id)

    def _schedule_on(self, loop: asyncio.AbstractEventLoop, token: str, coroutine, account_id: int) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except RuntimeError:
            # Loop closed between our check and this call — queue for retry.
            with self._pending_lock:
                self._pending.append((token, coroutine, account_id))
            return
        future.add_done_callback(lambda f, t=token, a=account_id: self._done(t, a, f))

    def _done(self, token: str, account_id: int, future: Future) -> None:
        try:
            result = future.result()
            self.operationCompleted.emit(token, result)
        except Exception as exc:
            self.operationFailed.emit(token, account_id, str(exc) or type(exc).__name__)

    def shutdown(self, cleanup_coroutine=None, timeout_ms: int = 5000) -> bool:
        """Cooperatively stop the asyncio runtime and wait for QThread exit.

        The method is idempotent and never uses ``QThread.terminate()``.  It
        returns whether the thread is fully stopped so application shutdown can
        keep a strong reference until destruction is safe.
        """
        self._accepting = False
        if not self.isRunning():
            if cleanup_coroutine is not None:
                try:
                    cleanup_coroutine.close()
                except Exception as close_exc:
                    _LOG.debug("Could not close unused Telegram cleanup coroutine: %s", close_exc)
            return True

        if self._loop is not None and self._ready.is_set():
            try:
                coroutine = cleanup_coroutine or self.client_manager.disconnect_all()
                future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
                future.result(timeout=max(1.0, timeout_ms / 1000.0 - 0.75))
            except Exception as exc:
                _LOG.warning("Telegram cleanup did not complete before shutdown: %s", exc)
                if cleanup_coroutine is not None:
                    try:
                        cleanup_coroutine.close()
                    except Exception as close_exc:
                        _LOG.debug("Could not close Telegram cleanup coroutine: %s", close_exc)
            finally:
                try:
                    if self._loop is not None:
                        self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception as stop_exc:
                    _LOG.warning("Could not signal Telegram event loop to stop: %s", stop_exc)
        else:
            if cleanup_coroutine is not None:
                try:
                    cleanup_coroutine.close()
                except Exception as close_exc:
                    _LOG.debug("Could not close pending cleanup coroutine: %s", close_exc)
            with self._pending_lock:
                pending = list(self._pending)
                self._pending.clear()
            for _token, coroutine, _account_id in pending:
                try:
                    coroutine.close()
                except Exception as close_exc:
                    _LOG.debug("Could not close pending Telegram coroutine: %s", close_exc)

        # ``quit`` is harmless here even though run() owns an asyncio loop; the
        # explicit loop.stop above is what exits run_forever().
        self.requestInterruption()
        self.quit()
        stopped = self.wait(timeout_ms)
        if not stopped and self._loop is not None:
            _LOG.warning("Telegram worker exceeded shutdown timeout; requesting event-loop stop again.")
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception as stop_exc:
                _LOG.warning("Second Telegram loop-stop request failed: %s", stop_exc)
            # After run_forever() receives loop.stop this should be short.  A
            # final cooperative wait avoids destroying a still-running QThread.
            stopped = self.wait(max(1000, timeout_ms))
        if not stopped:
            _LOG.error("Telegram worker is still running after timed cooperative shutdown; waiting for the already-requested loop stop to finish.")
            # Do not let a live QThread be garbage-collected.  No forceful
            # terminate() is used; this is a final cooperative join after the
            # asyncio loop has already received loop.stop().
            self.wait()
            stopped = not self.isRunning()
        return bool(stopped)
