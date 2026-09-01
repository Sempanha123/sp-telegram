from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid

from PySide6.QtCore import QObject, Signal


class OperationsTaskRunner(QObject):
    """Small cooperative background executor for blocking local maintenance/diagnostic work."""

    taskCompleted = Signal(str, object)
    taskFailed = Signal(str, str)

    def __init__(self, max_workers: int = 2, parent=None) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max(1, min(4, int(max_workers))), thread_name_prefix="tg-ops")
        self._accepting = True

    def submit(self, func, *args, **kwargs) -> str:
        if not self._accepting:
            raise RuntimeError("Operations task runner is shutting down.")
        token = uuid.uuid4().hex
        future = self._executor.submit(func, *args, **kwargs)
        def done(fut):
            try:
                self.taskCompleted.emit(token, fut.result())
            except Exception as exc:
                self.taskFailed.emit(token, str(exc) or "Background operation failed.")
        future.add_done_callback(done)
        return token

    def shutdown(self, wait: bool = True) -> None:
        self._accepting = False
        self._executor.shutdown(wait=wait, cancel_futures=True)
