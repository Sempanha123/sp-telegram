from __future__ import annotations

from abc import ABC, abstractmethod


class SecureStorageError(RuntimeError):
    """Raised when the operating-system credential store is unavailable."""


class SecureStorage(ABC):
    @abstractmethod
    def get_secret(self, key: str) -> str | None: ...

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None: ...

    @abstractmethod
    def delete_secret(self, key: str) -> None: ...


class KeyringSecureStorage(SecureStorage):
    """OS-backed credential storage through Python keyring.

    On Windows this normally resolves to Windows Credential Manager. Secrets are
    never placed in SQLite or QSettings. A legacy service namespace is read only
    as a compatibility bridge after the SP Telegram product rename; values found
    there are copied to the current namespace on first access.
    """

    CURRENT_SERVICE_NAME = "SP Telegram"
    LEGACY_SERVICE_NAMES = ("TG Control Center Premium",)

    def __init__(self, service_name: str = CURRENT_SERVICE_NAME) -> None:
        self.service_name = service_name

    @staticmethod
    def _keyring():
        try:
            import keyring
            return keyring
        except Exception as exc:  # pragma: no cover - environment dependent
            raise SecureStorageError(
                "Secure OS credential storage is unavailable. Install the project requirements and try again."
            ) from exc

    def get_secret(self, key: str) -> str | None:
        try:
            keyring = self._keyring()
            value = keyring.get_password(self.service_name, key)
            if value or self.service_name != self.CURRENT_SERVICE_NAME:
                return value
            # Preserve credentials created by pre-rename releases. Do not delete
            # the legacy copy automatically; migration must never risk data loss.
            for legacy_name in self.LEGACY_SERVICE_NAMES:
                value = keyring.get_password(legacy_name, key)
                if value:
                    keyring.set_password(self.CURRENT_SERVICE_NAME, key, value)
                    return value
            return None
        except SecureStorageError:
            raise
        except Exception as exc:
            raise SecureStorageError("Could not read credentials from secure OS storage.") from exc

    def set_secret(self, key: str, value: str) -> None:
        try:
            self._keyring().set_password(self.service_name, key, value)
        except SecureStorageError:
            raise
        except Exception as exc:
            raise SecureStorageError("Could not save credentials to secure OS storage.") from exc

    def delete_secret(self, key: str) -> None:
        try:
            keyring = self._keyring()
            names = [self.service_name]
            if self.service_name == self.CURRENT_SERVICE_NAME:
                names.extend(self.LEGACY_SERVICE_NAMES)
            for name in dict.fromkeys(names):
                try:
                    keyring.delete_password(name, key)
                except keyring.errors.PasswordDeleteError:
                    pass
        except SecureStorageError:
            raise
        except Exception as exc:
            raise SecureStorageError("Could not remove credentials from secure OS storage.") from exc
