from __future__ import annotations

from PySide6.QtCore import QObject


class LoginWorker(QObject):
    """Semantic login facade; execution is owned by TelegramWorkerThread."""

    def __init__(self, worker_thread, auth_service, parent=None) -> None:
        super().__init__(parent)
        self.worker_thread = worker_thread
        self.auth_service = auth_service

    def submit(self, coroutine, operation: str, account_id: int = 0) -> str:
        return self.worker_thread.submit_coroutine(coroutine, operation=operation, account_id=account_id)
