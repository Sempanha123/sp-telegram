from __future__ import annotations

from datetime import datetime, timezone

from app.telegram.result import TelegramSessionInfo


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    return str(value)


class TelegramSessionService:
    def __init__(self, client_manager) -> None:
        self.client_manager = client_manager

    @staticmethod
    def _normalize(item) -> TelegramSessionInfo:
        country = getattr(item, "country", "") or ""
        region = getattr(item, "region", "") or ""
        location = ", ".join(part for part in (region, country) if part) or "Unknown"
        return TelegramSessionInfo(
            authorization_hash=str(getattr(item, "hash", "")),
            device_model=getattr(item, "device_model", None) or "Unknown device",
            platform=getattr(item, "platform", None) or "Unknown",
            system_version=getattr(item, "system_version", None) or "Unknown",
            app_name=getattr(item, "app_name", None) or "Telegram",
            app_version=getattr(item, "app_version", None) or "Unknown",
            location=location,
            last_active_at=_iso(getattr(item, "date_active", None)),
            created_at=_iso(getattr(item, "date_created", None)),
            is_current=bool(getattr(item, "current", False)),
        )

    async def get_sessions(self, account_id: int) -> list[TelegramSessionInfo]:
        client = await self.client_manager.get_client(account_id)
        if client is None or not client.is_connected():
            raise RuntimeError("Connect account first.")
        if not await client.is_user_authorized():
            raise RuntimeError("Account requires Telegram login.")
        if hasattr(client, "list_sessions"):
            values = await client.list_sessions()
        else:
            from telethon import functions
            result = await client(functions.account.GetAuthorizationsRequest())
            values = result.authorizations
        return [self._normalize(item) for item in values]

    async def revoke_session(self, account_id: int, authorization_hash: str) -> bool:
        client = await self.client_manager.get_client(account_id)
        if client is None or not client.is_connected():
            raise RuntimeError("Connect account first.")
        if hasattr(client, "revoke_session"):
            return bool(await client.revoke_session(int(authorization_hash)))
        from telethon import functions
        return bool(await client(functions.account.ResetAuthorizationRequest(hash=int(authorization_hash))))
