from __future__ import annotations

from PySide6.QtCore import QObject


class HealthWorker(QObject):
    def __init__(self, worker_thread, health_service, parent=None) -> None:
        super().__init__(parent)
        self.worker_thread = worker_thread
        self.health_service = health_service

    def check(self, account) -> str:
        return self.worker_thread.submit_coroutine(self.health_service.check(account), operation="health", account_id=account.id)
