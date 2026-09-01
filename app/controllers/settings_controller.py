from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class SettingsController(QObject):
    settingsChanged = Signal()
    databaseRestored = Signal()
    telegramConfigChanged = Signal(bool)
    telegramConfigTested = Signal(bool, str)
    appLockChanged = Signal(bool)
    privacyModeChanged = Signal(bool)
    errorOccurred = Signal(str)
    toast_requested = Signal(str, str)

    def __init__(self, service, project_root, telegram_config_service=None, worker=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.project_root = Path(project_root)
        self.telegram_config = telegram_config_service
        self.worker = worker
        self.operations_controller = None
        self.app_lock_service = None
        self.audit_service = None
        self._test_tokens: set[str] = set()
        if worker is not None:
            worker.operationCompleted.connect(self._worker_completed)
            worker.operationFailed.connect(self._worker_failed)

    def get_all(self):
        return self.service.get_all()

    def get(self, key, default=None):
        return self.service.get(key, default)

    def active_database_path(self):
        return str(self.service.database.db_path)

    def get_api_id(self):
        try:
            return self.telegram_config.get_api_id() if self.telegram_config else None
        except Exception:
            return None

    def has_api_hash(self):
        try:
            return bool(self.telegram_config and self.telegram_config.get_api_hash())
        except Exception:
            return False

    def save_telegram_credentials(self, api_id, api_hash: str | None):
        try:
            if not self.telegram_config:
                raise RuntimeError("Telegram configuration service is unavailable.")
            existing_hash = self.telegram_config.get_api_hash()
            hash_value = (api_hash or "").strip() or existing_hash
            self.telegram_config.set_credentials(int(api_id), str(hash_value or ""))
            self.telegramConfigChanged.emit(True)
            self.toast_requested.emit("Telegram API credentials saved securely.", "Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def test_api_settings(self, api_id, api_hash: str | None):
        if not self.worker or not self.telegram_config:
            self._error(RuntimeError("Telegram runtime is unavailable."))
            return None
        try:
            coroutine = self.telegram_config.test_configuration_for(api_id, api_hash)
            token = self.worker.submit_coroutine(coroutine, operation="test_api_config", account_id=0)
            self._test_tokens.add(token)
            self.toast_requested.emit("Testing Telegram configuration…", "Info")
            return token
        except Exception as exc:
            self._error(exc)
            return None

    def _worker_completed(self, token: str, result):
        if token not in self._test_tokens:
            return
        self._test_tokens.discard(token)
        self.telegramConfigTested.emit(True, "Telegram configuration is valid and Telegram is reachable.")
        self.toast_requested.emit("Telegram configuration test succeeded.", "Success")

    def _worker_failed(self, token: str, account_id: int, message: str):
        if token not in self._test_tokens:
            return
        self._test_tokens.discard(token)
        self.telegramConfigTested.emit(False, message)
        self.toast_requested.emit(message, "Error")

    def save(self, values):
        try:
            before = self.service.get_all()
            self.service.save(values)
            if self.app_lock_service:
                self.app_lock_service.configure(
                    bool(values.get("enable_app_lock", before.get("enable_app_lock", False))),
                    int(values.get("app_lock_minutes", before.get("app_lock_minutes", 10))),
                )
            if "privacy_mode" in values:
                self.privacyModeChanged.emit(bool(values["privacy_mode"]))
            if self.audit_service:
                # AuditSecurity removes anything credential-shaped before persistence.
                self.audit_service.record(
                    "SETTINGS_CHANGED",
                    resource_type="SETTINGS",
                    resource_id="application",
                    description="Application operational settings changed.",
                    before=before,
                    after=self.service.get_all(),
                )
            self.settingsChanged.emit()
            self.toast_requested.emit("Settings saved.", "Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def reset(self):
        try:
            self.service.reset()
            if self.audit_service:
                self.audit_service.record(
                    "SETTINGS_RESET", resource_type="SETTINGS", resource_id="application",
                    description="Application settings were reset to defaults on next startup."
                )
            self.settingsChanged.emit()
            self.toast_requested.emit("Application settings reset.", "Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def set_app_lock_password(self, password: str) -> bool:
        try:
            if not self.app_lock_service:
                raise RuntimeError("Application Lock service is unavailable.")
            self.app_lock_service.set_password(password)
            self.appLockChanged.emit(True)
            self.toast_requested.emit("Application Lock credential saved securely.", "Success")
            return True
        except Exception as exc:
            self._error(exc); return False

    def clear_app_lock_password(self) -> bool:
        try:
            if not self.app_lock_service:
                raise RuntimeError("Application Lock service is unavailable.")
            self.app_lock_service.clear_password()
            self.service.save({"enable_app_lock": False})
            self.appLockChanged.emit(False)
            self.toast_requested.emit("Application Lock disabled and its verifier removed from secure storage.", "Success")
            return True
        except Exception as exc:
            self._error(exc); return False

    def has_app_lock_password(self) -> bool:
        try:
            return bool(self.app_lock_service and self.app_lock_service.has_password())
        except Exception:
            return False

    # Legacy single-database backup API remains for Phase 2 compatibility. Phase 7 UI
    # routes backup/restore through OperationsController to get manifest validation.
    def backup(self, path):
        try:
            if self.operations_controller:
                return self.operations_controller.run_backup(path)
            result = self.service.backup(path)
            self.toast_requested.emit("Database backup completed successfully. Telegram session files were not included.", "Success")
            return result
        except Exception as exc:
            self._error(exc); return None

    def restore(self, path):
        try:
            if self.operations_controller:
                return self.operations_controller.restore_backup(path)
            result = self.service.restore(path, self.project_root / "backups")
            self.databaseRestored.emit()
            self.toast_requested.emit("Database restored successfully. Telegram session files were not modified.", "Success")
            return result
        except Exception as exc:
            self._error(exc); return None

    def _error(self, exc):
        message = str(exc) or "Cannot complete the settings operation."
        self.errorOccurred.emit(message)
        self.toast_requested.emit(message, "Error")
