from __future__ import annotations

import asyncio
from pathlib import Path

from app.telegram.connection_queue import AccountConnectionQueue
from app.telegram.result import LoginResult, LoginState, QRLoginState
from app.telegram.telegram_errors import LoginPersistenceError


class TelegramAccountService:
    """Coordinates Telethon results with the existing persistent AccountService."""

    def __init__(
        self,
        account_service,
        auth_service,
        profile_service,
        session_service,
        health_service,
        client_manager,
        error_handler,
        session_repository,
        alert_service,
        logger,
        telegram_config_service,
        session_dir: str | Path,
        resource_locks=None,
    ) -> None:
        self.account_service = account_service
        self.auth_service = auth_service
        self.profile_service = profile_service
        self.session_service = session_service
        self.health_service = health_service
        self.client_manager = client_manager
        self.error_handler = error_handler
        self.session_repository = session_repository
        self.alert_service = alert_service
        self.logger = logger
        self.config = telegram_config_service
        self.session_dir = Path(session_dir).resolve()
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.resource_locks = resource_locks
        self.feature_gate = None

    def _require_account_feature(self) -> None:
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.ACCOUNT_MANAGER)

    def validate_session_directory(self) -> tuple[bool, str]:
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            probe = self.session_dir / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, "Session directory is writable."
        except Exception:
            return False, "Telegram session directory is not writable."

    def _session_path(self, account_id: int) -> str:
        return str((self.session_dir / f"account_{account_id}.session").resolve())

    @staticmethod
    def _delete_session_files(session_path: str | None) -> None:
        if not session_path:
            return
        base = Path(session_path)
        for candidate in [base, Path(str(base) + "-journal"), Path(str(base) + "-wal"), Path(str(base) + "-shm")]:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass

    def _alert(self, severity: str, alert_type: str, title: str, message: str, account_id: int) -> None:
        try:
            self.alert_service.create(severity, alert_type, title, message, account_id=account_id)
        except Exception as exc:
            if self.logger:
                self.logger.warning("ACCOUNT", f"Could not persist account alert for account #{account_id}: {exc}", action="ACCOUNT_ALERT", account_id=account_id)

    def _record_failure(self, account_id: int, exc: Exception, action: str) -> None:
        result = self.error_handler.classify(exc)
        self.account_service.record_error(account_id, result.code, result.message)
        self.logger.error("ACCOUNT", f"Account ID {account_id} {action} failed: {result.code}.", action=action, account_id=account_id, important=True)
        if result.code == "FLOOD_WAIT":
            self.account_service.record_confirmed_flood_wait(account_id, result.wait_seconds, result.message)
            self._alert("WARNING", "FLOOD_WAIT", "Telegram cooldown recorded", result.message, account_id)
        elif result.requires_login:
            self.account_service.mark_login_required(account_id, result.message, result.code)
            self._alert("WARNING", "LOGIN_REQUIRED", "Telegram login required", result.message, account_id)

    async def start_phone_login(self, phone: str) -> LoginResult:
        self._require_account_feature()
        self.config.require_credentials()
        account = self.account_service.create_login_pending_account(phone)
        session_path = self._session_path(account.id)
        self.account_service.set_session_path(account.id, session_path)
        try:
            self.account_service.record_activity(account.id, "LOGIN_STARTED", "STARTED", "Phone login started.")
            await self.auth_service.begin(account.id, phone, session_path)
            context = await self.auth_service.request_login_code(account.id, phone)
            return LoginResult(account.id, context.state, message="Verification code sent.")
        except Exception as exc:
            self._record_failure(account.id, exc, "LOGIN_STARTED")
            await self.auth_service.cancel_login(account.id)
            self.account_service.cleanup_login_pending_account(account.id)
            self._delete_session_files(session_path)
            raise RuntimeError(self.error_handler.classify(exc).message) from exc


    async def start_phone_login_existing(self, account_id: int, phone: str) -> LoginResult:
        self._require_account_feature()
        self.config.require_credentials()
        account = self.account_service.get_by_id(account_id)
        if not account:
            raise RuntimeError("Account not found.")
        if account.is_demo:
            raise RuntimeError("Demo accounts cannot be attached to Telegram sessions.")
        session_path = account.session_path or self._session_path(account_id)
        self.account_service.set_session_path(account_id, session_path)
        try:
            self.account_service.record_activity(account_id, "LOGIN_STARTED", "STARTED", "Re-login started for existing local account.")
            await self.auth_service.begin(account_id, phone, session_path, temporary_account=False)
            context = await self.auth_service.request_login_code(account_id, phone)
            return LoginResult(account_id, context.state, message="Verification code sent.")
        except Exception as exc:
            self._record_failure(account_id, exc, "LOGIN_STARTED")
            await self.auth_service.cancel_login(account_id)
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def resend_login_code(self, account_id: int) -> LoginResult:
        context = self.auth_service.context(account_id)
        if context is None or not context.phone:
            raise RuntimeError("Login session is no longer active.")
        try:
            updated = await self.auth_service.request_login_code(account_id, context.phone)
            self.account_service.record_activity(account_id, "LOGIN_CODE_RESENT", "SUCCESS", "A new Telegram verification code was requested.")
            return LoginResult(account_id, updated.state, message="Verification code sent.")
        except Exception as exc:
            result = self.error_handler.classify(exc)
            self.account_service.record_error(account_id, result.code, result.message)
            raise RuntimeError(result.message) from exc

    async def submit_login_code(self, account_id: int, code: str) -> LoginResult:
        context = self.auth_service.context(account_id)
        if context is None or not context.phone:
            raise RuntimeError("Login session is no longer active.")
        try:
            user, context = await self.auth_service.sign_in_with_code(account_id, context.phone, code)
            if context.state == LoginState.PASSWORD_REQUIRED:
                return LoginResult(account_id, LoginState.PASSWORD_REQUIRED, message="Two-step verification password required.")
            return await self._complete_login(account_id, user)
        except LoginPersistenceError:
            raise
        except Exception as exc:
            result = self.error_handler.classify(exc)
            self.account_service.record_error(account_id, result.code, result.message)
            self.account_service.record_activity(account_id, "LOGIN_FAILED", "FAILED", result.message, {"code": result.code})
            if result.code == "FLOOD_WAIT":
                self.account_service.record_confirmed_flood_wait(account_id, result.wait_seconds, result.message)
            raise RuntimeError(result.message) from exc

    async def submit_2fa_password(self, account_id: int, password: str) -> LoginResult:
        try:
            user, _context = await self.auth_service.sign_in_with_password(account_id, password)
            return await self._complete_login(account_id, user)
        except LoginPersistenceError:
            raise
        except Exception as exc:
            result = self.error_handler.classify(exc)
            self.account_service.record_error(account_id, result.code, result.message)
            self.account_service.record_activity(account_id, "LOGIN_FAILED", "FAILED", result.message, {"code": result.code})
            raise RuntimeError(result.message) from exc

    async def start_qr_login(self):
        self._require_account_feature()
        self.config.require_credentials()
        account = self.account_service.create_login_pending_account(None)
        session_path = self._session_path(account.id)
        self.account_service.set_session_path(account.id, session_path)
        try:
            self.account_service.record_activity(account.id, "QR_LOGIN_STARTED", "STARTED", "QR login started.")
            return await self.auth_service.start_qr_login(account.id, session_path)
        except Exception as exc:
            self._record_failure(account.id, exc, "QR_LOGIN_STARTED")
            await self.auth_service.cancel_login(account.id)
            self.account_service.cleanup_login_pending_account(account.id)
            self._delete_session_files(session_path)
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def refresh_qr(self, account_id: int):
        return await self.auth_service.refresh_qr_login(account_id)

    async def wait_qr_login(self, account_id: int) -> LoginResult:
        try:
            user = await self.auth_service.wait_for_qr_login(account_id)
            if user is None:
                return LoginResult(account_id, LoginState.FAILED, message="QR code expired.")
            return await self._complete_login(account_id, user)
        except LoginPersistenceError:
            raise
        except Exception as exc:
            result = self.error_handler.classify(exc)
            if result.code == "PASSWORD_REQUIRED":
                context = self.auth_service.context(account_id)
                if context:
                    context.state = LoginState.PASSWORD_REQUIRED
                return LoginResult(account_id, LoginState.PASSWORD_REQUIRED, message=result.message)
            self.account_service.record_error(account_id, result.code, result.message)
            raise RuntimeError(result.message) from exc

    async def _complete_login(self, account_id: int, user) -> LoginResult:
        profile = self.profile_service.normalize(user)
        context = self.auth_service.context(account_id)
        session_path = context.session_path if context else self._session_path(account_id)
        try:
            account = self.account_service.finalize_authenticated_account(account_id, profile, session_path)
        except ValueError as exc:
            temporary = bool(context.temporary_account) if context else False
            if str(exc).startswith("DUPLICATE_TELEGRAM_ACCOUNT:"):
                existing_id = int(str(exc).split(":", 1)[1])
                await self.auth_service.cancel_login(account_id)
                if temporary:
                    self.account_service.cleanup_login_pending_account(account_id)
                    self._delete_session_files(session_path)
                return LoginResult(account_id, LoginState.FAILED, profile=profile, existing_account_id=existing_id, message="This Telegram account is already registered.")
            if str(exc) == "IDENTITY_MISMATCH":
                await self.auth_service.cancel_login(account_id)
                if temporary:
                    self.account_service.cleanup_login_pending_account(account_id)
                    self._delete_session_files(session_path)
                raise RuntimeError("The logged-in Telegram account does not match this local record.") from exc
            raise
        except Exception as exc:
            # Telegram authorization already succeeded. Preserve the local session
            # rather than silently logging the user out; after the database issue
            # is fixed, Connect can recover the verified identity from Telegram.
            context = self.auth_service.context(account_id)
            if context:
                context.state = LoginState.FAILED
            self.logger.error(
                "DATABASE", f"Account ID {account_id} authenticated but local persistence failed.",
                action="LOGIN_PERSISTENCE", account_id=account_id, important=True,
            )
            raise LoginPersistenceError(
                "Telegram login succeeded but local account data could not be saved. "
                "The local authorization session was preserved; fix the database issue and use Connect to recover the account."
            ) from exc
        self.auth_service.finish(account_id)
        self.logger.info("ACCOUNT", f"Account ID {account.id} authenticated successfully.", action="LOGIN_SUCCESS", account_id=account.id, important=True)
        return LoginResult(account.id, LoginState.DONE, profile=profile, message="Account connected.")

    async def cancel_login(self, account_id: int) -> bool:
        context = self.auth_service.context(account_id)
        session_path = context.session_path if context else None
        temporary = bool(context.temporary_account) if context else False
        await self.auth_service.cancel_login(account_id)
        if temporary:
            self.account_service.cleanup_login_pending_account(account_id)
            self._delete_session_files(session_path)
        return True

    async def shutdown(self) -> None:
        # Cancel login contexts before the worker loop closes. Temporary login
        # rows/session files are cleaned; established account sessions remain.
        for account_id in self.auth_service.active_login_account_ids():
            try:
                await self.cancel_login(account_id)
            except Exception as exc:
                if self.logger:
                    self.logger.warning("ACCOUNT", f"Pending login cleanup failed for account #{account_id}: {exc}", action="LOGIN_CLEANUP", account_id=account_id)
        await self.client_manager.disconnect_all()

    async def connect(self, account_id: int):
        self._require_account_feature()
        account = self.account_service.get_by_id(account_id)
        if not account:
            raise RuntimeError("Account not found.")
        if account.is_demo:
            raise RuntimeError("Demo accounts never connect to Telegram.")
        if not account.session_path or not Path(account.session_path).is_file():
            self.account_service.mark_login_required(account_id, "Telegram session file is missing.", "SESSION_MISSING")
            self._alert("WARNING", "SESSION_MISSING", f"{account.first_name or account.username or 'Account'} requires login", "Telegram session file is missing.", account_id)
            raise RuntimeError("Session file is missing. Login to this account again.")
        try:
            await self.client_manager.create_client(account_id, account.session_path)
            await self.client_manager.connect(account_id)
            authorized = await self.client_manager.is_authorized(account_id)
            if not authorized:
                self.account_service.set_connection_state(account_id, "CONNECTED", authorized=False)
                self.account_service.mark_login_required(account_id, "Telegram session is no longer authorized.", "SESSION_UNAUTHORIZED")
                self._alert("WARNING", "LOGIN_REQUIRED", "Account requires login", "Telegram authorization is no longer valid.", account_id)
                return {"account_id": account_id, "authorized": False}
            self.account_service.set_connection_state(account_id, "CONNECTED", authorized=True, health_status="HEALTHY")
            profile = await self.profile_service.refresh_profile(account_id)
            self.account_service.sync_telegram_profile(account_id, profile)
            self.account_service.record_activity(account_id, "CONNECTED", "SUCCESS", "Account connected to Telegram.")
            return {"account_id": account_id, "authorized": True, "profile": profile}
        except Exception as exc:
            self._record_failure(account_id, exc, "CONNECT")
            self.account_service.set_connection_state(account_id, "ERROR")
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def connect_many(self, account_ids: list[int], max_concurrency: int = 3):
        semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))
        results = []
        async def one(account_id: int):
            async with semaphore:
                try:
                    results.append(await self.connect(account_id))
                except Exception as exc:
                    results.append({"account_id": account_id, "authorized": False, "error": str(exc)})
        await asyncio.gather(*(one(account_id) for account_id in account_ids))
        return results

    async def disconnect(self, account_id: int):
        try:
            await self.client_manager.disconnect(account_id)
            self.account_service.set_connection_state(account_id, "DISCONNECTED")
            self.account_service.record_activity(account_id, "DISCONNECTED", "SUCCESS", "Telegram network connection closed; authorization retained.")
            return account_id
        except Exception as exc:
            self._record_failure(account_id, exc, "DISCONNECT")
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def logout(self, account_id: int):
        account = self.account_service.get_by_id(account_id)
        if not account:
            raise RuntimeError("Account not found.")
        from contextlib import nullcontext
        lock = self.resource_locks.hold("ACCOUNT", account_id, "LOGOUT", "Account Logout") if self.resource_locks else nullcontext()
        try:
            with lock:
                client = await self.client_manager.get_client(account_id)
                if client is None and account.session_path and Path(account.session_path).is_file():
                    await self.client_manager.create_client(account_id, account.session_path)
                    await self.client_manager.connect(account_id)
                await self.auth_service.logout(account_id)
                self.account_service.mark_logged_out(account_id)
                self.account_service.record_activity(account_id, "LOGGED_OUT", "SUCCESS", "Telegram authorization was revoked for this application.")
                self._alert("INFO", "ACCOUNT_LOGGED_OUT", "Account logged out", "Telegram authorization was removed from SP Telegram.", account_id)
                return account_id
        except Exception as exc:
            self._record_failure(account_id, exc, "LOGOUT")
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def refresh_profile(self, account_id: int):
        self._require_account_feature()
        try:
            if not await self.client_manager.is_connected(account_id):
                await self.connect(account_id)
            if not await self.client_manager.is_authorized(account_id):
                raise RuntimeError("Account requires Telegram login.")
            profile = await self.profile_service.refresh_profile(account_id)
            account = self.account_service.sync_telegram_profile(account_id, profile)
            return account
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc) == "Account requires Telegram login.":
                self.account_service.mark_login_required(account_id, str(exc))
                raise
            self._record_failure(account_id, exc, "PROFILE_REFRESH")
            raise RuntimeError(self.error_handler.classify(exc).message) from exc

    async def check_health(self, account_id: int):
        account = self.account_service.get_by_id(account_id)
        if not account:
            raise RuntimeError("Account not found.")
        result = await self.health_service.check(account)
        self.account_service.set_health_result(result)
        if result.error_code == "SESSION_MISSING":
            self._alert("WARNING", "SESSION_MISSING", "Telegram session missing", result.error_message or "Session missing.", account_id)
        elif result.health_status in {"LOGIN_REQUIRED", "SESSION_INVALID"}:
            self._alert("WARNING", "LOGIN_REQUIRED", "Account requires login", result.error_message or "Login required.", account_id)
        return result

    async def check_health_many(self, account_ids: list[int], max_concurrency: int = 3):
        queue = AccountConnectionQueue(max_concurrency)
        results = []
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        async def one(account_id):
            async with semaphore:
                try:
                    results.append(await self.check_health(account_id))
                except Exception as exc:
                    results.append({"account_id": account_id, "error": str(exc)})
        await asyncio.gather(*(one(i) for i in account_ids))
        return results

    async def get_sessions(self, account_id: int):
        if not await self.client_manager.is_connected(account_id):
            await self.connect(account_id)
        sessions = await self.session_service.get_sessions(account_id)
        self.session_repository.replace_for_account(account_id, sessions)
        self.account_service.record_activity(account_id, "SESSION_REFRESHED", "SUCCESS", "Telegram session list refreshed.")
        return sessions

    async def revoke_session(self, account_id: int, authorization_hash: str):
        cached = self.session_repository.get_for_account(account_id)
        is_current = any(str(row.get("authorization_hash")) == str(authorization_hash) and bool(row.get("is_current")) for row in cached)
        ok = await self.session_service.revoke_session(account_id, authorization_hash)
        if ok:
            self.session_repository.remove(account_id, authorization_hash)
            self.account_service.record_activity(account_id, "SESSION_REVOKED", "SUCCESS", "A Telegram authorization session was revoked.")
            if is_current:
                await self.client_manager.remove_client(account_id)
                self.account_service.mark_login_required(account_id, "The current SP Telegram Telegram session was revoked.", "SESSION_REVOKED")
                self.account_service.set_connection_state(account_id, "DISCONNECTED", authorized=False)
                self._alert("WARNING", "LOGIN_REQUIRED", "Current Telegram session revoked", "This account requires login again.", account_id)
        return ok
