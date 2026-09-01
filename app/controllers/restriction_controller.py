from __future__ import annotations

import csv
from PySide6.QtCore import QObject, Signal


class RestrictionController(QObject):
    restrictionsChanged = Signal(list)
    toast_requested = Signal(str, str)

    def __init__(self, repository, manager, account_controller=None, parent=None) -> None:
        super().__init__(parent); self.repository = repository; self.manager = manager; self.account_controller = account_controller
        self._pending: dict[int, int] = {}
        if account_controller is not None:
            account_controller.accountHealthUpdated.connect(self._health_result)

    def restrictions(self): return self.refresh(emit=False)
    def refresh(self, emit=True):
        self.manager.refresh_expiries(); items = self.repository.get_all()
        if emit: self.restrictionsChanged.emit(items)
        return items
    def get_by_id(self, restriction_id: int): return self.repository.get_by_id(restriction_id)

    def recheck(self, restriction_id: int):
        item = self.repository.get_by_id(restriction_id)
        if not item or not item.account_id: return False
        if not self.account_controller:
            self.toast_requested.emit("Account health controller is unavailable.", "Error"); return False
        self.repository.mark_pending_recheck(restriction_id); self._pending[int(item.account_id)] = restriction_id
        self.account_controller.run_health_check(int(item.account_id)); self.toast_requested.emit("Restriction recheck queued. The restriction will remain pending until a safe check succeeds.", "Info"); self.refresh(); return True

    def _health_result(self, account_id: int, result) -> None:
        restriction_id = self._pending.pop(int(account_id), None)
        if not restriction_id: return
        item = self.repository.get_by_id(restriction_id)
        healthy = str(getattr(result, "health_status", "")) == "HEALTHY"
        if item and healthy and str(item.restriction_type).upper() == "FLOOD_WAIT":
            self.repository.record_recheck(restriction_id, resolved=True, note="Known wait elapsed and basic account health recheck succeeded.")
            self.toast_requested.emit("Flood-wait restriction marked resolved after recheck.", "Success")
        elif item and healthy and str(item.scope).upper() in {"ACCOUNT", "SESSION"}:
            self.repository.record_recheck(restriction_id, resolved=True, note="Account/session health recheck succeeded.")
            self.toast_requested.emit("Restriction marked resolved after safe recheck.", "Success")
        else:
            self.repository.mark_manual_review(restriction_id)
            self.toast_requested.emit("The health check did not safely prove this capability restriction is gone. Manual review is required.", "Warning")
        self.refresh()

    def manual_resolve(self, restriction_id: int):
        ok = self.manager.mark_manual_resolved(restriction_id); self.refresh(); return ok

    def export(self, path: str):
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle); writer.writerow(["account", "type", "scope", "source", "confidence", "started", "expires", "state", "error", "reason"])
            for r in self.repository.get_all():
                writer.writerow([r.account_id, r.restriction_type, r.scope, r.source, r.confidence, r.started_at, r.expires_at, r.state, r.error_code, r.reason])
        self.toast_requested.emit("Restriction history exported.", "Success")
