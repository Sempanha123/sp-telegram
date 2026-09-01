from __future__ import annotations

from PySide6.QtCore import QObject


class SessionWorker(QObject):
    def __init__(self, worker_thread, session_service, parent=None) -> None:
        super().__init__(parent)
        self.worker_thread = worker_thread
        self.session_service = session_service

    def refresh(self, account_id: int) -> str:
        return self.worker_thread.submit_coroutine(self.session_service.get_sessions(account_id), operation="sessions", account_id=account_id)
