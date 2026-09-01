from __future__ import annotations

from app.security.secure_storage import KeyringSecureStorage, SecureStorage


class CredentialStore:
    API_ID_KEY = "telegram_api_id"
    API_HASH_KEY = "telegram_api_hash"

    def __init__(self, storage: SecureStorage | None = None) -> None:
        self.storage = storage or KeyringSecureStorage()

    def get_api_id(self) -> int | None:
        value = self.storage.get_secret(self.API_ID_KEY)
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def get_api_hash(self) -> str | None:
        value = self.storage.get_secret(self.API_HASH_KEY)
        return value.strip() if value else None

    def set_api_credentials(self, api_id: int, api_hash: str) -> None:
        self.storage.set_secret(self.API_ID_KEY, str(int(api_id)))
        self.storage.set_secret(self.API_HASH_KEY, api_hash.strip())

    def clear_api_credentials(self) -> None:
        self.storage.delete_secret(self.API_ID_KEY)
        self.storage.delete_secret(self.API_HASH_KEY)
