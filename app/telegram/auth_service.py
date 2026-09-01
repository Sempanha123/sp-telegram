from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.telegram.result import LoginContext, LoginState, QRLoginInfo, QRLoginState


class TelegramAuthService:
    def __init__(self, client_manager, error_handler) -> None:
        self.client_manager = client_manager
        self.error_handler = error_handler
        self._contexts: dict[int, LoginContext] = {}
        self._qr_logins: dict[int, object] = {}

    def context(self, account_id: int) -> LoginContext | None:
        return self._contexts.get(account_id)

    def active_login_account_ids(self) -> list[int]:
        return list(self._contexts)

    async def begin(self, account_id: int, phone: str | None, session_path: str, temporary_account: bool = True) -> LoginContext:
        context = LoginContext(account_id, phone, session_path, LoginState.CONNECTING, temporary_account=temporary_account)
        self._contexts[account_id] = context
        state = self.client_manager.runtime_state(account_id)
        state.login_in_progress = True
        await self.client_manager.create_client(account_id, session_path)
        await self.client_manager.connect(account_id)
        return context

    async def request_login_code(self, account_id: int, phone: str):
        context = self._contexts[account_id]
        context.state = LoginState.CODE_REQUESTED
        client = await self.client_manager.get_client(account_id)
        result = await client.send_code_request(phone)
        context.phone = phone
        context.phone_code_hash = getattr(result, "phone_code_hash", None)
        context.state = LoginState.WAITING_CODE
        return context

    async def sign_in_with_code(self, account_id: int, phone: str, code: str):
        context = self._contexts[account_id]
        context.state = LoginState.VERIFYING_CODE
        client = await self.client_manager.get_client(account_id)
        try:
            user = await client.sign_in(phone=phone, code=code, phone_code_hash=context.phone_code_hash)
        except Exception as exc:
            classified = self.error_handler.classify(exc)
            if classified.code == "PASSWORD_REQUIRED":
                context.state = LoginState.PASSWORD_REQUIRED
                return None, context
            context.state = LoginState.FAILED
            raise
        context.state = LoginState.AUTHORIZED
        return user, context

    async def sign_in_with_password(self, account_id: int, password: str):
        context = self._contexts[account_id]
        context.state = LoginState.VERIFYING_PASSWORD
        client = await self.client_manager.get_client(account_id)
        user = await client.sign_in(password=password)
        context.state = LoginState.AUTHORIZED
        return user, context

    async def start_qr_login(self, account_id: int, session_path: str) -> QRLoginInfo:
        context = await self.begin(account_id, None, session_path)
        context.state = LoginState.CONNECTING
        client = await self.client_manager.get_client(account_id)
        qr = await client.qr_login()
        self._qr_logins[account_id] = qr
        expires = qr.expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return QRLoginInfo(account_id, qr.url, expires.astimezone(timezone.utc).isoformat(), QRLoginState.QR_WAITING)

    async def refresh_qr_login(self, account_id: int) -> QRLoginInfo:
        qr = self._qr_logins.get(account_id)
        if qr is None:
            raise RuntimeError("QR login is not active.")
        result = await qr.recreate()
        if result is not None:
            qr = result
            self._qr_logins[account_id] = qr
        expires = qr.expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return QRLoginInfo(account_id, qr.url, expires.astimezone(timezone.utc).isoformat(), QRLoginState.QR_WAITING)

    async def wait_for_qr_login(self, account_id: int):
        qr = self._qr_logins.get(account_id)
        if qr is None:
            raise RuntimeError("QR login is not active.")
        if getattr(qr, "expires", None):
            expires = qr.expires
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            timeout = max(1.0, (expires - datetime.now(timezone.utc)).total_seconds())
        else:
            timeout = 60.0
        try:
            user = await qr.wait(timeout=timeout)
            self._contexts[account_id].state = LoginState.AUTHORIZED
            return user
        except asyncio.TimeoutError:
            return None

    async def cancel_login(self, account_id: int):
        context = self._contexts.get(account_id)
        if context:
            context.state = LoginState.CANCELLED
        self._qr_logins.pop(account_id, None)
        state = self.client_manager.runtime_state(account_id)
        state.login_in_progress = False
        await self.client_manager.remove_client(account_id)
        self._contexts.pop(account_id, None)
        return True

    async def logout(self, account_id: int):
        client = await self.client_manager.get_client(account_id)
        if client is None:
            return False
        result = await client.log_out()
        await self.client_manager.remove_client(account_id)
        return bool(result)

    def finish(self, account_id: int) -> None:
        context = self._contexts.get(account_id)
        if context:
            context.state = LoginState.DONE
        state = self.client_manager.runtime_state(account_id)
        state.login_in_progress = False
        state.authorized = True
        self._qr_logins.pop(account_id, None)
        self._contexts.pop(account_id, None)
