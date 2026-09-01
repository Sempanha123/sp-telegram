from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

from app.telegram.operation_result import TelegramOperationResult


_LOG = logging.getLogger(__name__)


DENIED_ACCESS = {"ACCESS_DENIED", "NOT_JOINED", "UNAVAILABLE", "NO_ACCESS", "BANNED", "LEFT"}
BLOCKING_HEALTH = {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}


class TargetInviteLinkService:
    """One-account invite-link administration with typed operational results."""

    def __init__(self, group_repository, group_account_repository, account_repository, client_manager,
                 telegram_invite_service, repository, error_handler=None, *, session_pool=None, account_service=None, alert_service=None):
        self.groups = group_repository
        self.group_accounts = group_account_repository
        self.accounts = account_repository
        self.client_manager = client_manager
        self.telegram = telegram_invite_service
        self.repository = repository
        self.error_handler = error_handler
        self.session_pool = session_pool
        self.account_service = account_service
        self.alert_service = alert_service

    @staticmethod
    def _result(success: bool, status: str, code: str | None, message: str, *, technical: str = "", retry="NONE", **data):
        return TelegramOperationResult(success, status, code, message, technical, retry, data)

    def _local_preflight(self, group_id: int, account_id: int) -> TelegramOperationResult | None:
        group = self.groups.get_by_id(int(group_id)) if self.groups else None
        if not group or not (bool(getattr(group, "is_target", 0)) or bool(getattr(group, "is_managed", 0))):
            return self._result(False, "BLOCKED", "TARGET_UNAVAILABLE", "Select a saved managed/target group first.")
        account = self.accounts.get_by_id(int(account_id)) if self.accounts else None
        if not account:
            return self._result(False, "BLOCKED", "ACCOUNT_NOT_AUTHORIZED", "The selected Telegram account no longer exists.")
        if not bool(getattr(account, "is_enabled", 0)) or not bool(getattr(account, "enabled_for_operations", 1)):
            return self._result(False, "BLOCKED", "ACCOUNT_DISABLED", "The selected account is disabled for operations.")
        if str(getattr(account, "authorization_status", "UNKNOWN") or "UNKNOWN").upper() != "AUTHORIZED":
            return self._result(False, "BLOCKED", "ACCOUNT_NOT_AUTHORIZED", "Telegram login is required for the selected account.")
        health = str(getattr(account, "health_status", "UNKNOWN") or "UNKNOWN").upper()
        restriction = str(getattr(account, "restriction_type", "") or "").upper()
        if health in BLOCKING_HEALTH or (restriction and restriction not in {"NONE", "NONE_KNOWN", "UNKNOWN"}):
            return self._result(False, "BLOCKED", "ACCOUNT_RESTRICTED", "The selected account currently has a blocking restriction.")
        mapping = self.group_accounts.get_mapping(int(group_id), int(account_id)) if self.group_accounts else None
        if not mapping:
            return self._result(False, "BLOCKED", "TARGET_ACCESS_DENIED", "The selected account is not mapped to this target.")
        access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
        if access in DENIED_ACCESS or getattr(mapping, "can_view", None) is False:
            return self._result(False, "BLOCKED", "TARGET_ACCESS_DENIED", "The selected account does not currently have access to this target.")
        return None

    async def preflight(self, group_id: int, account_id: int) -> TelegramOperationResult:
        local = self._local_preflight(group_id, account_id)
        if local:
            return local
        group = self.groups.get_by_id(int(group_id))
        client = await self.client_manager.get_client(int(account_id)) if self.client_manager else None
        try:
            # Invite-link creation is an explicit operator action, so lazily
            # initialize this one account when needed. Startup still never loads
            # or connects the whole account database.
            if client is None and self.session_pool is not None:
                client = await self.session_pool.ensure_client(int(account_id))
            elif client is None:
                account = self.accounts.get_by_id(int(account_id))
                session_path = str(getattr(account, "session_path", "") or "") if account else ""
                if not session_path or not Path(session_path).is_file():
                    return self._result(False, "BLOCKED", "SESSION_INVALID", "Telegram session is missing. Login to this account first.")
                client = await self.client_manager.create_client(int(account_id), session_path)
            if client is None:
                return self._result(False, "BLOCKED", "SESSION_INVALID", "Telegram session could not be loaded. Login to this account again.")
            if hasattr(client, "is_connected") and not bool(client.is_connected()):
                await self.client_manager.connect(int(account_id))
            if hasattr(client, "is_connected") and not bool(client.is_connected()):
                return self._result(False, "BLOCKED", "NETWORK_ERROR", "Telegram connection is unavailable for the selected account.", retry="OPERATOR_RETRY")
            if hasattr(client, "is_user_authorized") and not bool(await client.is_user_authorized()):
                return self._result(False, "BLOCKED", "ACCOUNT_NOT_AUTHORIZED", "Telegram login is required for the selected account.")
            reference = getattr(group, "username", None) or getattr(group, "telegram_group_id", None)
            if not reference:
                return self._result(False, "BLOCKED", "TARGET_UNAVAILABLE", "The target does not have a usable Telegram username or group ID. Sync the target and try again.")
            entity = await client.get_entity(reference)
            permission_service = getattr(self.telegram, "permission_service", None)
            permissions = None
            if permission_service is not None:
                permissions = await permission_service.get_my_permissions(int(account_id), entity)
                try:
                    self.group_accounts.update_permissions(int(group_id), int(account_id), permissions)
                except Exception as exc:
                    # A stale local cache/schema must not discard a valid live
                    # Telegram permission result for this explicit operation.
                    _LOG.warning("Could not cache invite-link permissions: %s", exc)
            mapping = self.group_accounts.get_mapping(int(group_id), int(account_id))
            can_manage = bool(getattr(permissions, "can_manage_invite_links", 0)) if permissions is not None else bool(getattr(mapping, "can_manage_invite_links", 0))
            if not can_manage:
                return self._result(False, "BLOCKED", "INVITE_LINK_PERMISSION_DENIED", "This account cannot create invite links for the selected target.")
            return self._result(True, "READY", None, "Invite-link permission is available.", group=group, mapping=mapping, entity=entity)
        except Exception as exc:
            result = self._normalize_expected(exc)
            if result is not None:
                self._apply_operational_effects(account_id, group_id, result)
                return result
            raise

    def _normalize_expected(self, exc: Exception) -> TelegramOperationResult | None:
        name = type(exc).__name__
        known = {
            "ChatAdminRequiredError": ("ADMIN_PERMISSION_REQUIRED", "Administrator permission is required to create an invite link.", "NONE"),
            "ChatWriteForbiddenError": ("INVITE_LINK_PERMISSION_DENIED", "Telegram denied invite-link management for this target.", "NONE"),
            "ChannelPrivateError": ("TARGET_ACCESS_DENIED", "The selected account cannot access this target.", "NONE"),
            "UserNotParticipantError": ("TARGET_ACCESS_DENIED", "The selected account is not a participant of this target.", "NONE"),
            "AuthKeyUnregisteredError": ("SESSION_INVALID", "The Telegram session is no longer valid.", "REAUTHENTICATE"),
            "SessionRevokedError": ("SESSION_INVALID", "The Telegram session was revoked.", "REAUTHENTICATE"),
            "UsageLimitInvalidError": ("INVITE_LINK_OPTIONS_INVALID", "The invite-link usage limit is not valid for these options.", "NONE"),
            "ExpireDateInvalidError": ("INVITE_LINK_OPTIONS_INVALID", "The invite-link expiration is not valid.", "NONE"),
        }
        if name in known:
            code, message, retry = known[name]
            return self._result(False, "FAILED", code, message, technical=str(exc), retry=retry)
        if isinstance(exc, ValueError):
            return self._result(False, "BLOCKED", "VALIDATION_ERROR", str(exc) or "Invite-link validation failed.")
        try:
            classified = self.error_handler.classify(exc) if self.error_handler else None
        except Exception:
            classified = None
        if classified:
            code = str(getattr(classified, "code", "UNKNOWN") or "UNKNOWN")
            if code == "FLOOD_WAIT":
                return self._result(False, "PAUSED", "FLOOD_WAIT", getattr(classified, "message", "Telegram requested a cooldown."), technical=str(exc), retry="AFTER_COOLDOWN", wait_seconds=getattr(classified, "wait_seconds", None))
            if code in {"PERMISSION_DENIED", "PRIVATE_ACCESS_DENIED", "NOT_JOINED"}:
                return self._result(False, "BLOCKED", "INVITE_LINK_PERMISSION_DENIED", getattr(classified, "message", "Invite-link permission is unavailable."), technical=str(exc))
            if code in {"NETWORK_ERROR", "SESSION_INVALID"}:
                return self._result(False, "FAILED", code, getattr(classified, "message", "Telegram operation failed."), technical=str(exc), retry="OPERATOR_RETRY")
        _LOG.exception("Unexpected target invite-link failure", exc_info=exc)
        return self._result(
            False,
            "FAILED",
            "INVITE_LINK_OPERATION_FAILED",
            "Telegram could not complete the invite-link operation. Refresh the account permission and try again.",
            technical=str(exc) or type(exc).__name__,
            retry="OPERATOR_RETRY",
        )

    def _apply_operational_effects(self, account_id: int, group_id: int, result: TelegramOperationResult) -> None:
        if result.error_code == "FLOOD_WAIT":
            wait = (result.data or {}).get("wait_seconds")
            if self.account_service is not None:
                try:self.account_service.record_confirmed_flood_wait(int(account_id), wait, result.user_message)
                except Exception:pass
            if self.alert_service is not None:
                try:self.alert_service.create("WARNING", "FLOOD_WAIT", "Invite-link operation paused", result.user_message, account_id=int(account_id), group_id=int(group_id))
                except Exception:pass

    async def create_invite_link(self, group_id: int, account_id: int, *, request_needed: bool = True,
                                 title: str | None = None, expire_date=None, usage_limit: int | None = None) -> TelegramOperationResult:
        pre = await self.preflight(group_id, account_id)
        if not pre.success:
            return pre
        # Telegram does not accept an approval-required link with a positive usage
        # limit on some server/client combinations. Avoid a crash by treating the
        # combination as an explicit validation result before making the request.
        if request_needed and usage_limit not in {None, 0, ""}:
            return self._result(False, "BLOCKED", "INVITE_LINK_OPTIONS_INVALID", "Usage Limit cannot be combined with Require Join Approval. Clear the usage limit or turn approval off.")
        try:
            link = await self.telegram.create_invite_link(
                int(account_id), pre.data["entity"], request_needed=bool(request_needed), title=title,
                expire_date=expire_date, usage_limit=usage_limit,
            )
            expires_at = None
            if expire_date is not None:
                if isinstance(expire_date, datetime):
                    expires_at = expire_date.isoformat()
                else:
                    expires_at = str(expire_date)
            row = None; persistence_warning = None
            if self.repository:
                try:
                    row = self.repository.create_link(
                        int(group_id), int(account_id), str(link), name=title,
                        request_needed=bool(request_needed), expires_at=expires_at,
                        usage_limit=int(usage_limit) if usage_limit not in {None, 0, ""} else None,
                    )
                except Exception as exc:
                    # Telegram already created the link. Return it to the user
                    # instead of reporting a failed operation that could lead to
                    # duplicate retries; local history can be repaired later.
                    persistence_warning = "The link works, but its local history record could not be saved."
                    _LOG.exception("Invite link created but local persistence failed", exc_info=exc)
            return self._result(True, "COMPLETED", None, "Invite link created.", link=str(link), record=row,
                                group_id=int(group_id), account_id=int(account_id), request_needed=bool(request_needed),
                                persistence_warning=persistence_warning)
        except Exception as exc:
            result = self._normalize_expected(exc)
            if result is not None:
                self._apply_operational_effects(account_id, group_id, result)
                return result
            raise

    def list_invite_links(self, group_id: int, limit: int = 100) -> list[dict[str, Any]]:
        return self.repository.get_active_for_target(int(group_id), limit) if self.repository else []

    async def revoke_invite_link(self, link_id: int, group_id: int, account_id: int) -> TelegramOperationResult:
        row = self.repository.find_by_id(int(link_id)) if self.repository else None
        if not row:
            return self._result(False, "BLOCKED", "INVITE_LINK_NOT_FOUND", "Invite link record was not found.")
        pre = await self.preflight(group_id, account_id)
        if not pre.success:
            return pre
        try:
            client = await self.client_manager.get_client(int(account_id))
            if hasattr(client, "revoke_invite_link"):
                await client.revoke_invite_link(pre.data["entity"], str(row["invite_link"]))
            else:
                from telethon.tl.functions.messages import EditExportedChatInviteRequest
                await client(EditExportedChatInviteRequest(peer=pre.data["entity"], link=str(row["invite_link"]), revoked=True))
            self.repository.mark_revoked(int(link_id))
            return self._result(True, "COMPLETED", None, "Invite link revoked.", link_id=int(link_id))
        except Exception as exc:
            result = self._normalize_expected(exc)
            if result is not None:
                return result
            raise
