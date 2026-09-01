from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class TelegramService(QObject):
    accountUpdated = Signal(dict)
    accountError = Signal(int, str)
    groupResolved = Signal(dict)
    operationStarted = Signal(str)
    operationProgress = Signal(str, int)
    operationFinished = Signal(str)

    def _mock_operation(self, name: str) -> None:
        self.operationStarted.emit(name)
        QTimer.singleShot(150, lambda: self.operationProgress.emit(name, 50))
        QTimer.singleShot(350, lambda: self.operationFinished.emit(name))

    def connect_account(self, account_id: int) -> None: self._mock_operation(f"connect:{account_id}")
    def disconnect_account(self, account_id: int) -> None: self._mock_operation(f"disconnect:{account_id}")
    def check_account_health(self, account_id: int | None = None) -> None: self._mock_operation(f"health:{account_id or 'all'}")
    def resolve_group(self, reference: str) -> dict:
        result = {"Group Name": reference.lstrip("@").replace("_", " ").title(), "Username": reference, "Type":"Supergroup", "Access":"Public", "Role":"Admin", "Members":1234, "Can Post":True, "Can Invite":True, "Can Manage":True}
        QTimer.singleShot(150, lambda: self.groupResolved.emit(result)); return result
    def sync_group(self, reference: str) -> None: self._mock_operation(f"sync:{reference}")
    def collect_members(self, group: str) -> None: self._mock_operation(f"collect:{group}")
    def create_campaign(self, data: dict) -> None: self._mock_operation("create_campaign")
    def schedule_campaign(self, data: dict) -> None: self._mock_operation("schedule_campaign")
    def cancel_schedule(self, schedule_id: str) -> None: self._mock_operation(f"cancel_schedule:{schedule_id}")
