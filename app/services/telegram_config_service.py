from __future__ import annotations

import re


class TelegramConfigService:
    def __init__(self, credential_store) -> None:
        self.credential_store = credential_store

    def get_api_id(self) -> int | None:
        return self.credential_store.get_api_id()

    def get_api_hash(self) -> str | None:
        return self.credential_store.get_api_hash()

    def validate_config(self, api_id=None, api_hash=None) -> tuple[bool, str]:
        api_id = self.get_api_id() if api_id is None else api_id
        api_hash = self.get_api_hash() if api_hash is None else api_hash
        try:
            api_id = int(api_id)
        except (TypeError, ValueError):
            return False, "API ID must be numeric."
        value = str(api_hash or "").strip()
        if api_id <= 0:
            return False, "API ID must be greater than zero."
        if not value:
            return False, "API Hash is required."
        if not re.fullmatch(r"[0-9a-fA-F]{16,64}", value):
            return False, "API Hash format is invalid."
        return True, "Telegram API configuration format is valid."

    def has_valid_config(self) -> bool:
        try:
            return self.validate_config()[0]
        except Exception:
            return False

    def require_credentials(self) -> tuple[int, str]:
        api_id = self.get_api_id()
        api_hash = self.get_api_hash()
        valid, message = self.validate_config(api_id, api_hash)
        if not valid:
            raise ValueError(message)
        return int(api_id), str(api_hash)

    def set_credentials(self, api_id: int, api_hash: str) -> None:
        valid, message = self.validate_config(api_id, api_hash)
        if not valid:
            raise ValueError(message)
        self.credential_store.set_api_credentials(int(api_id), api_hash.strip())


    async def test_configuration_for(self, api_id, api_hash: str | None = None) -> bool:
        if api_hash is None or not str(api_hash).strip():
            api_hash = self.get_api_hash()
        valid, message = self.validate_config(api_id, api_hash)
        if not valid:
            raise ValueError(message)
        try:
            from telethon import TelegramClient, functions
            from telethon.sessions import MemorySession
        except ImportError as exc:
            raise RuntimeError("Telethon is not installed.") from exc
        client = TelegramClient(MemorySession(), int(api_id), str(api_hash))
        try:
            await client.connect()
            await client(functions.help.GetConfigRequest())
            return True
        finally:
            await client.disconnect()

    async def test_configuration(self) -> bool:
        api_id, api_hash = self.require_credentials()
        try:
            from telethon import TelegramClient, functions
            from telethon.sessions import MemorySession
        except ImportError as exc:
            raise RuntimeError("Telethon is not installed.") from exc
        client = TelegramClient(MemorySession(), api_id, api_hash)
        try:
            await client.connect()
            await client(functions.help.GetConfigRequest())
            return True
        finally:
            await client.disconnect()
