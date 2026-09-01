from __future__ import annotations

from pathlib import Path

from app.telegram.result import AccountHealthResult


class TelegramAccountHealthService:
    """Basic local/session/authorization health only; no Telegram reputation scoring."""

    def __init__(self, client_manager, profile_service, error_handler) -> None:
        self.client_manager = client_manager
        self.profile_service = profile_service
        self.error_handler = error_handler

    async def check(self, account) -> AccountHealthResult:
        account_id = int(account.id)
        if not account.is_enabled:
            return AccountHealthResult(account_id, False, bool(account.session_path and Path(account.session_path).exists()), False, False, "DISABLED")
        if not account.session_path or not Path(account.session_path).is_file():
            return AccountHealthResult(account_id, False, False, False, False, "LOGIN_REQUIRED", "SESSION_MISSING", "Telegram session file is missing.")
        try:
            await self.client_manager.create_client(account_id, account.session_path)
            await self.client_manager.connect(account_id)
            authorized = await self.client_manager.is_authorized(account_id)
            if not authorized:
                return AccountHealthResult(account_id, True, True, False, False, "LOGIN_REQUIRED", "SESSION_UNAUTHORIZED", "Telegram login is required.")
            await self.profile_service.get_me(account_id)
            return AccountHealthResult(account_id, True, True, True, True, "HEALTHY")
        except Exception as exc:
            error = self.error_handler.classify(exc)
            if error.category.value == "RATE_LIMIT":
                status = "COOLDOWN"
            elif error.requires_login or error.category.value == "SESSION":
                status = "SESSION_INVALID"
            elif error.category.value == "NETWORK":
                status = "WARNING"
            else:
                status = "WARNING"
            return AccountHealthResult(account_id, False, True, False, False, status, error.code, error.message)
