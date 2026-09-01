from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from app.models.pagination import PaginationState


class AccountController(QObject):
    accountsChanged = Signal(list)
    accountCreated = Signal(object)
    accountUpdated = Signal(object)
    accountRemoved = Signal(int)
    account_health_changed = Signal(int, str)
    errorOccurred = Signal(str)
    successOccurred = Signal(str)
    toast_requested = Signal(str, str)

    accountConnecting = Signal(int)
    accountConnected = Signal(int)
    accountDisconnected = Signal(int)
    accountAuthorizationRequired = Signal(int)
    accountProfileUpdated = Signal(int, object)
    accountHealthUpdated = Signal(int, object)
    accountOperationFailed = Signal(int, str)
    loginStateChanged = Signal(int, str)
    loginCodeRequested = Signal(int)
    loginPasswordRequired = Signal(int)
    loginCompleted = Signal(int, object)
    loginFailed = Signal(int, str)
    loginCancelled = Signal(int)
    qrLoginReady = Signal(int, object)
    qrLoginExpired = Signal(int)
    sessionListUpdated = Signal(int, list)
    sessionRevoked = Signal(int, str)
    telegramGlobalStatusChanged = Signal(str)
    bulkProgress = Signal(int, int, int, int, str)
    bulkFinished = Signal(int, int, bool)
    planLimitReached = Signal(str, object)
    featureLocked = Signal(str, str)

    def __init__(self, service, telegram_service=None, worker=None, settings_service=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.telegram_service = telegram_service
        self.worker = worker
        self.settings_service = settings_service
        self.pagination = PaginationState()
        self.search_text = ""
        self.health_filter = None
        self.status_filter = None
        self.current_items = []
        self._handlers: dict[str, tuple[Callable | None, Callable | None]] = {}
        self._bulk_state: dict | None = None
        self.job_repository = None
        self.license_limit_service = None
        self.feature_gate = None
        # Tracks the in-flight login so Cancel works even before the worker has
        # created the temporary "Pending Telegram Login" account row.
        self._pending_login_account_id = 0
        self._pending_login_active = False
        if self.worker is not None:
            self.worker.operationCompleted.connect(self._on_operation_completed)
            self.worker.operationFailed.connect(self._on_operation_failed)
            self.worker.finished.connect(self._on_worker_finished)

    def accounts(self):
        return self.refresh(emit=False)

    def refresh(self, emit=True):
        try:
            items, total = self.service.get_account_page(
                self.pagination.page, self.pagination.page_size, self.search_text,
                self.health_filter, self.status_filter,
            )
            self.pagination.total_items = total
            self.pagination.clamp()
            if self.job_repository is not None:
                active = self.job_repository.db.fetch_all("SELECT id,job_type,account_id,status FROM jobs WHERE status IN ('RUNNING','QUEUED','PAUSED','WAITING') AND account_id IS NOT NULL ORDER BY CASE status WHEN 'RUNNING' THEN 0 ELSE 1 END,id DESC")
                by_account = {}
                for row in active:
                    by_account.setdefault(int(row["account_id"]), row)
                for account in items:
                    job = by_account.get(int(account.id or 0))
                    account.current_job = f"#{job['id']} {str(job['job_type']).replace('_',' ').title()}" if job else "Idle"
                    health = str(account.health_status or "UNKNOWN").upper()
                    connection = str(account.connection_status or "OFFLINE").upper()
                    if not account.is_enabled: account.operational_status = "DISABLED"
                    elif health in {"COOLDOWN","RESTRICTED","LOGIN_REQUIRED"}: account.operational_status = health
                    elif job: account.operational_status = "BUSY"
                    elif connection == "CONNECTED": account.operational_status = "READY"
                    elif connection in {"OFFLINE","DISCONNECTED","ERROR"}: account.operational_status = "OFFLINE"
                    else: account.operational_status = "IDLE"
            self.current_items = items
            if emit:
                self.accountsChanged.emit(items)
            return items
        except Exception as exc:
            self._error(exc)
            return []

    def set_search(self, text: str):
        self.search_text = text
        self.pagination.page = 1
        return self.refresh()

    def set_filter(self, column: str, value: str):
        if column == "Health":
            self.health_filter = None if value == "All" else value
        elif column == "Connection":
            self.status_filter = None if value == "All" else value
        self.pagination.page = 1
        return self.refresh()

    def set_page(self, page: int):
        self.pagination.page = page
        return self.refresh()

    def set_page_size(self, size: int):
        self.pagination.page_size = size
        self.pagination.page = 1
        return self.refresh()


    def _require_license_feature(self, feature):
        if self.feature_gate is None:return True
        if self.feature_gate.has_feature(feature):return True
        required=self.feature_gate.get_required_plan(feature)
        self.featureLocked.emit(str(feature),str(required or "STARTER"));return False

    def account_add_readiness(self):
        from app.license.feature_keys import FeatureKey
        if self.feature_gate is not None and not self.feature_gate.has_feature(FeatureKey.ACCOUNT_MANAGER):
            required=self.feature_gate.get_required_plan(FeatureKey.ACCOUNT_MANAGER) or "STARTER"
            return False, f"Account management requires an active {required} or higher license."
        if self.license_limit_service is not None:
            result=self.license_limit_service.can_add_account()
            if not result.allowed:
                return False, result.message or "The current plan account limit has been reached."
        if self.telegram_service is None or self.worker is None:
            return False, "Telegram runtime is not available. Restart SP Telegram and try again."
        if not self.has_telegram_config():
            return False, "Telegram API configuration is required. Open Settings → Telegram."
        return True, "Ready"

    def can_add_new_account(self):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.ACCOUNT_MANAGER):return False
        if self.license_limit_service is None:return True
        result=self.license_limit_service.can_add_account()
        if not result.allowed:self.planLimitReached.emit("MAX_ACCOUNTS",result)
        return bool(result.allowed)

    # Phase 2 local CRUD remains available for notes/tags/manual records.
    def add(self, data: dict):
        try:
            if not self.can_add_new_account(): return None
            item = self.service.add_account(data)
            self.accountCreated.emit(item)
            self.toast_requested.emit("Account added successfully.", "Success")
            self.refresh()
            return item
        except Exception as exc:
            self._error(exc)
            return None

    def update(self, id: int, data: dict):
        try:
            item = self.service.update_account(id, data)
            self.accountUpdated.emit(item)
            self.toast_requested.emit("Account updated.", "Success")
            self.refresh()
            return item
        except Exception as exc:
            self._error(exc)
            return None

    def disable(self, id: int):
        try:
            self.service.disable_account(id)
            self.toast_requested.emit("Account disabled. History and authorization files were preserved.", "Warning")
            self.refresh()
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def remove(self, id: int):
        try:
            mode = self.service.remove_account(id)
            self.accountRemoved.emit(id)
            self.toast_requested.emit(
                "Account removed from the tool." if mode == "deleted" else "Account has related history, so it was disabled instead of deleted.",
                "Success" if mode == "deleted" else "Warning",
            )
            self.refresh()
            return mode
        except Exception as exc:
            self._error(exc)
            return None

    def tags(self, id: int):
        try:
            return self.service.get_tags(id)
        except Exception as exc:
            self._error(exc)
            return []

    def details(self, id: int):
        try:
            return self.service.get_account_details(id)
        except Exception as exc:
            self._error(exc)
            return None

    def restrictions(self):
        try:
            return self.service.get_restrictions()
        except Exception as exc:
            self._error(exc)
            return []

    def import_csv(self, path: str | Path):
        try:
            result = self.service.import_csv(path)
            self.refresh()
            self.toast_requested.emit(
                f"Imported: {result['imported']} • Updated: {result['updated']} • Skipped: {result['skipped']} • Errors: {result['errors']}",
                "Success" if not result["errors"] else "Warning",
            )
            return result
        except Exception as exc:
            self._error(exc)
            return None

    def export_csv(self, path: str | Path):
        try:
            self.service.export_csv(path)
            self.toast_requested.emit("Accounts exported successfully.", "Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def has_telegram_config(self) -> bool:
        return bool(self.telegram_service and self.telegram_service.config.has_valid_config())

    def _submit(self, coroutine, operation: str, account_id: int = 0, success=None, failure=None):
        if self.worker is None:
            self._error(RuntimeError("Telegram runtime is unavailable."))
            return None
        try:
            token = self.worker.submit_coroutine(coroutine, operation=operation, account_id=account_id)
            self._handlers[token] = (success, failure)
            return token
        except Exception as exc:
            self._error(exc)
            return None

    def _on_operation_completed(self, token: str, result) -> None:
        handler = self._handlers.pop(token, None)
        if not handler:
            return
        success, _failure = handler
        if success:
            success(result)

    def _on_operation_failed(self, token: str, account_id: int, message: str) -> None:
        handler = self._handlers.pop(token, None)
        if not handler:
            return
        _success, failure = handler
        if failure:
            failure(account_id, message)
        else:
            self.accountOperationFailed.emit(account_id, message)
            self.toast_requested.emit(message, "Error")
        self.refresh()

    # -------- Authentication --------
    def start_phone_login(self, phone: str, existing_account_id: int | None = None):
        from app.license.feature_keys import FeatureKey
        if existing_account_id is not None and not self._require_license_feature(FeatureKey.ACCOUNT_MANAGER):return None
        if existing_account_id is None and not self.can_add_new_account(): return None
        phone = "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")
        if not phone or len(phone.replace("+", "")) < 6:
            self.loginFailed.emit(0, "Enter a valid phone number including country code.")
            return None
        if not self.has_telegram_config():
            self.loginFailed.emit(0, "Telegram API configuration is required. Open Settings → Telegram.")
            return None
        self._pending_login_active = True
        self.loginStateChanged.emit(0, "CONNECTING")
        coroutine = self.telegram_service.start_phone_login_existing(existing_account_id, phone) if existing_account_id else self.telegram_service.start_phone_login(phone)
        return self._submit(
            coroutine, "login_phone", int(existing_account_id or 0),
            self._phone_login_started, self._login_error,
        )

    def _phone_login_started(self, result):
        self._pending_login_account_id = result.account_id
        self.loginStateChanged.emit(result.account_id, result.state.value)
        self.loginCodeRequested.emit(result.account_id)
        self.refresh()

    def resend_login_code(self, account_id: int):
        if not account_id:
            self.loginFailed.emit(0, "Login session is no longer active.")
            return None
        self.loginStateChanged.emit(account_id, "CODE_REQUESTED")
        return self._submit(
            self.telegram_service.resend_login_code(account_id), "login_resend", account_id,
            self._phone_login_started, self._login_error,
        )

    def submit_login_code(self, account_id: int, code: str):
        if not str(code).strip():
            self.loginFailed.emit(account_id, "Enter the verification code.")
            return None
        self.loginStateChanged.emit(account_id, "VERIFYING_CODE")
        return self._submit(
            self.telegram_service.submit_login_code(account_id, str(code)), "login_code", account_id,
            self._login_step_completed, self._login_error,
        )

    def submit_2fa_password(self, account_id: int, password: str):
        if not password:
            self.loginFailed.emit(account_id, "Enter your two-step verification password.")
            return None
        self.loginStateChanged.emit(account_id, "VERIFYING_PASSWORD")
        return self._submit(
            self.telegram_service.submit_2fa_password(account_id, str(password)), "login_2fa", account_id,
            self._login_step_completed, self._login_error,
        )

    def _login_step_completed(self, result):
        if result.state.value == "PASSWORD_REQUIRED":
            self.loginStateChanged.emit(result.account_id, result.state.value)
            self.loginPasswordRequired.emit(result.account_id)
            return
        if result.existing_account_id:
            self._pending_login_active = False
            self.loginFailed.emit(result.account_id, f"This Telegram account is already registered as local account ID {result.existing_account_id}.")
            self.refresh()
            return
        self._pending_login_active = False
        self.loginStateChanged.emit(result.account_id, "DONE")
        self.loginCompleted.emit(result.account_id, result.profile)
        self.accountConnected.emit(result.account_id)
        self.telegramGlobalStatusChanged.emit("Ready")
        self.toast_requested.emit("Account connected.", "Success")
        self.refresh()

    def start_qr_login(self):
        if not self.can_add_new_account(): return None
        if not self.has_telegram_config():
            self.loginFailed.emit(0, "Telegram API configuration is required. Open Settings → Telegram.")
            return None
        self._pending_login_active = True
        self.loginStateChanged.emit(0, "QR_GENERATING")
        return self._submit(self.telegram_service.start_qr_login(), "login_qr", 0, self._qr_started, self._login_error)

    def _qr_started(self, info):
        self._pending_login_account_id = info.account_id
        self.qrLoginReady.emit(info.account_id, info)
        self.loginStateChanged.emit(info.account_id, "QR_WAITING")
        self._submit(self.telegram_service.wait_qr_login(info.account_id), "login_qr_wait", info.account_id, self._qr_wait_completed, self._login_error)

    def refresh_qr_login(self, account_id: int):
        return self._submit(self.telegram_service.refresh_qr(account_id), "login_qr_refresh", account_id, lambda info: self.qrLoginReady.emit(account_id, info), self._login_error)

    def _qr_wait_completed(self, result):
        if result.state.value == "FAILED":
            self.qrLoginExpired.emit(result.account_id)
            self.loginStateChanged.emit(result.account_id, "QR_EXPIRED")
            return
        self._login_step_completed(result)

    def cancel_login(self, account_id: int):
        """Cancel an in-flight login and clean up the temporary account.

        ``account_id`` may be 0 when the worker has not yet created the pending
        account row (the CONNECTING phase).  In that case we fall back to the
        tracked pending account id, and if none exists yet we simply mark the
        login as cancelled so the row is cleaned up the moment it appears.
        """
        if not self.telegram_service:
            self.loginCancelled.emit(0)
            return None
        if not account_id:
            account_id = self._pending_login_account_id
        self._pending_login_active = False
        if not account_id:
            # No temporary account exists yet; nothing to clean up right now.
            self.loginCancelled.emit(0)
            return None
        self.loginStateChanged.emit(account_id, "CANCELLED")
        return self._submit(
            self.telegram_service.cancel_login(account_id), "login_cancel", account_id,
            lambda _r: self._login_cancelled(account_id),
            lambda _aid, _msg: self._login_cancelled(account_id),
        )

    def _login_cancelled(self, account_id: int):
        self._pending_login_account_id = 0
        self.refresh()
        self.loginCancelled.emit(account_id)

    def _login_error(self, account_id: int, message: str):
        self._pending_login_active = False
        self.loginStateChanged.emit(account_id, "FAILED")
        self.loginFailed.emit(account_id, message)
        self.toast_requested.emit(message, "Error")
        self.refresh()

    # -------- Connected account operations --------
    def connect_account(self, account_id: int):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.ACCOUNT_MANAGER):return None
        if not account_id:
            return None
        self.accountConnecting.emit(account_id)
        self.telegramGlobalStatusChanged.emit("Connecting")
        return self._submit(self.telegram_service.connect(account_id), "connect", account_id, self._connected, self._operation_error)

    def _connected(self, result):
        account_id = int(result["account_id"])
        if result.get("authorized"):
            self.accountConnected.emit(account_id)
            if result.get("profile"):
                self.accountProfileUpdated.emit(account_id, result["profile"])
            self.toast_requested.emit("Account connected.", "Success")
            self.telegramGlobalStatusChanged.emit("Ready")
        else:
            self.accountAuthorizationRequired.emit(account_id)
            self.toast_requested.emit("Account connected, but Telegram login is required.", "Warning")
            self.telegramGlobalStatusChanged.emit("Partial")
        self.refresh()

    def disconnect_account(self, account_id: int):
        if not account_id:
            return None
        return self._submit(self.telegram_service.disconnect(account_id), "disconnect", account_id, self._disconnected, self._operation_error)

    def _disconnected(self, account_id):
        self.accountDisconnected.emit(int(account_id))
        self.toast_requested.emit("Account disconnected. Telegram authorization was retained.", "Success")
        self.telegramGlobalStatusChanged.emit("Partial")
        self.refresh()

    def logout_account(self, account_id: int):
        return self._submit(self.telegram_service.logout(account_id), "logout", account_id, self._logged_out, self._operation_error)

    def _logged_out(self, account_id):
        self.accountAuthorizationRequired.emit(int(account_id))
        self.toast_requested.emit("Account logged out from Telegram.", "Warning")
        self.refresh()

    def refresh_profile(self, account_id: int):
        from app.license.feature_keys import FeatureKey
        if not self._require_license_feature(FeatureKey.ACCOUNT_MANAGER):return None
        return self._submit(self.telegram_service.refresh_profile(account_id), "profile", account_id, self._profile_updated, self._operation_error)

    def _profile_updated(self, account):
        self.accountProfileUpdated.emit(int(account.id), account)
        self.toast_requested.emit("Profile updated.", "Success")
        self.refresh()

    def run_health_check(self, account_id: int):
        if not account_id:
            return None
        return self._submit(self.telegram_service.check_health(account_id), "health", account_id, self._health_updated, self._operation_error)

    def health_check(self, account_id=None):
        if account_id:
            return self.run_health_check(account_id)
        return self.run_health_check_all()

    def _health_updated(self, result):
        self.accountHealthUpdated.emit(result.account_id, result)
        self.account_health_changed.emit(result.account_id, result.health_status)
        self.toast_requested.emit("Health check completed.", "Success" if result.health_status == "HEALTHY" else "Warning")
        self.refresh()

    def run_health_check_all(self):
        accounts = [a for a in self.service.get_accounts() if a.is_enabled and not getattr(a, "is_demo", 0)]
        if not accounts:
            self.toast_requested.emit("No non-demo enabled accounts are available for health check.", "Info")
            return None
        max_connections = int(self.settings_service.get("max_account_connections", 3)) if self.settings_service else 3
        ids = [int(a.id) for a in accounts]
        return self._submit(self.telegram_service.check_health_many(ids, max_connections), "health_all", 0, self._health_all_done, self._operation_error)

    def _health_all_done(self, results):
        success = sum(1 for r in results if not isinstance(r, dict) and getattr(r, "health_status", "") == "HEALTHY")
        failed = len(results) - success
        self.bulkProgress.emit(len(results), len(results), success, failed, "Completed")
        self.toast_requested.emit(f"Health checks completed: {success} healthy, {failed} need attention.", "Success" if not failed else "Warning")
        self.refresh()

    def refresh_sessions(self, account_id: int):
        return self._submit(self.telegram_service.get_sessions(account_id), "sessions", account_id, lambda items: self._sessions_updated(account_id, items), self._operation_error)

    def _sessions_updated(self, account_id: int, items: list):
        self.sessionListUpdated.emit(account_id, items)
        self.toast_requested.emit("Session list updated.", "Success")

    def revoke_session(self, account_id: int, authorization_hash: str):
        return self._submit(self.telegram_service.revoke_session(account_id, authorization_hash), "session_revoke", account_id, lambda ok: self._session_revoked(account_id, authorization_hash, ok), self._operation_error)

    def _session_revoked(self, account_id: int, authorization_hash: str, ok: bool):
        if ok:
            self.sessionRevoked.emit(account_id, authorization_hash)
            self.toast_requested.emit("Telegram session revoked.", "Success")
            self.refresh_sessions(account_id)

    def _operation_error(self, account_id: int, message: str):
        self.accountOperationFailed.emit(account_id, message)
        self.toast_requested.emit(message, "Error")
        self.telegramGlobalStatusChanged.emit("Partial")
        self.refresh()

    # -------- Safe bulk account management --------
    def start_bulk_connect(self, account_ids: list[int]):
        return self._start_bulk_account_operation("Connect", account_ids)

    def start_bulk_disconnect(self, account_ids: list[int]):
        return self._start_bulk_account_operation("Disconnect", account_ids)

    def start_bulk_health(self, account_ids: list[int]):
        return self._start_bulk_account_operation("Health Check", account_ids)

    def start_bulk_profile_refresh(self, account_ids: list[int]):
        return self._start_bulk_account_operation("Refresh Profile", account_ids)

    def _start_bulk_account_operation(self, operation: str, account_ids: list[int]):
        if self._bulk_state is not None:
            self.toast_requested.emit("Another account operation is already in progress.", "Warning")
            return False
        unique_ids = list(dict.fromkeys(int(value) for value in account_ids if value))
        if not unique_ids:
            self.toast_requested.emit("Select one or more accounts first.", "Info")
            return False
        self._bulk_state = {
            "operation": operation,
            "ids": unique_ids,
            "index": 0,
            "completed": 0,
            "success": 0,
            "failed": 0,
            "cancelled": False,
        }
        self.bulkProgress.emit(0, len(unique_ids), 0, 0, "Preparing…")
        self._bulk_schedule_next()
        return True

    def cancel_bulk_account_operation(self) -> None:
        if self._bulk_state is not None:
            self._bulk_state["cancelled"] = True

    def _bulk_schedule_next(self) -> None:
        state = self._bulk_state
        if state is None:
            return
        if state["cancelled"] or state["index"] >= len(state["ids"]):
            self._finish_bulk_operation()
            return

        account_id = int(state["ids"][state["index"]])
        state["index"] += 1
        account = self.service.get_by_id(account_id)
        display = (
            getattr(account, "first_name", None)
            or getattr(account, "username", None)
            or f"Account {account_id}"
        )
        self.bulkProgress.emit(
            state["completed"], len(state["ids"]), state["success"],
            state["failed"], str(display),
        )

        operation = state["operation"]
        if operation == "Connect":
            coroutine = self.telegram_service.connect(account_id)
        elif operation == "Disconnect":
            coroutine = self.telegram_service.disconnect(account_id)
        elif operation == "Health Check":
            coroutine = self.telegram_service.check_health(account_id)
        elif operation == "Refresh Profile":
            coroutine = self.telegram_service.refresh_profile(account_id)
        else:
            self._bulk_item_done(False, account_id, "Unsupported bulk operation.")
            return

        self._submit(
            coroutine, f"bulk_{operation.lower().replace(' ', '_')}", account_id,
            lambda result, aid=account_id: self._bulk_item_done(True, aid, result),
            lambda aid, message: self._bulk_item_done(False, aid, message),
        )

    def _bulk_item_done(self, success: bool, account_id: int, _result) -> None:
        state = self._bulk_state
        if state is None:
            return
        state["completed"] += 1
        if success:
            state["success"] += 1
        else:
            state["failed"] += 1
        self.bulkProgress.emit(
            state["completed"], len(state["ids"]), state["success"],
            state["failed"], f"Account {account_id}",
        )
        self.refresh()
        self._bulk_schedule_next()

    def _finish_bulk_operation(self) -> None:
        state = self._bulk_state
        if state is None:
            return
        cancelled = bool(state["cancelled"])
        success = int(state["success"])
        failed = int(state["failed"])
        total = len(state["ids"])
        self.bulkProgress.emit(state["completed"], total, success, failed, "Cancelled" if cancelled else "Completed")
        self._bulk_state = None
        self.bulkFinished.emit(success, failed, cancelled)
        if cancelled:
            self.toast_requested.emit("Bulk account operation cancelled. Completed results were kept.", "Info")
        else:
            self.toast_requested.emit(
                f"Bulk account operation completed: {success} succeeded, {failed} failed.",
                "Success" if failed == 0 else "Warning",
            )
        self.refresh()

    def startup_recovery(self):
        if not self.telegram_service:
            return
        # Remove any leftover temporary login rows from an interrupted login.
        try:
            removed = self.service.cleanup_stale_pending_accounts()
            if removed:
                self.toast_requested.emit(f"Cleaned up {removed} incomplete login{'s' if removed != 1 else ''}.", "Info")
        except Exception as exc:
            self._error(exc)
        from pathlib import Path as _Path
        for account in self.service.get_accounts():
            if getattr(account, "is_demo", 0):
                continue
            if account.session_path and not _Path(account.session_path).is_file() and account.authorization_status == "AUTHORIZED":
                self.service.mark_login_required(account.id, "Telegram session file is missing.", "SESSION_MISSING")
        self.refresh()
        if self.settings_service and bool(self.settings_service.get("auto_connect_accounts", False)):
            # Queueing is per account; no login is initiated automatically.
            enabled = [a for a in self.service.get_accounts() if a.is_enabled and a.session_path and _Path(a.session_path).is_file() and not getattr(a, "is_demo", 0)]
            if enabled:
                maximum = max(1, int(self.settings_service.get("max_account_connections", 3)))
                # Startup is deliberately bounded: never initialize/connect the entire
                # stored account database. Remaining sessions stay lazy and are opened
                # only when an operator/job explicitly needs them.
                ids = [int(a.id) for a in enabled[:maximum]]
                self.telegramGlobalStatusChanged.emit("Connecting")
                self._submit(self.telegram_service.connect_many(ids, maximum), "startup_connect", 0, self._startup_connect_done, self._operation_error)

    def _startup_connect_done(self, results):
        connected = sum(1 for result in results if isinstance(result, dict) and result.get("authorized"))
        if connected == len(results):
            self.telegramGlobalStatusChanged.emit("Ready")
        elif connected:
            self.telegramGlobalStatusChanged.emit("Partial")
        else:
            self.telegramGlobalStatusChanged.emit("Offline")
        self.refresh()

    def _on_worker_finished(self) -> None:
        """Drain pending handlers when the worker thread stops unexpectedly."""
        pending = dict(self._handlers)
        self._handlers.clear()
        for _token, (_success, failure) in pending.items():
            if failure:
                try:
                    failure(0, "The Telegram worker stopped unexpectedly.")
                except Exception:
                    pass
        if pending:
            self.toast_requested.emit(
                "The Telegram worker stopped. Pending operations were cancelled.",
                "Warning",
            )
            self.refresh()

    def _error(self, exc):
        message = str(exc) if str(exc) and "database operation" not in str(exc).lower() else "Cannot complete the account operation."
        self.errorOccurred.emit(message)
        self.toast_requested.emit(message, "Error")
