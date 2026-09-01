from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.services.invitation_eligibility_policy import (
    InvitationEligibilityPolicy, ELIGIBILITY_NOT_APPROVED, CONSENT_NOT_APPROVED,
    BLACKLISTED, DO_NOT_CONTACT, DELETED, BOT, ALREADY_MEMBER, TARGET_STATUS_UNKNOWN,
)


BLOCKING_HEALTH = {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}
DENIED_ACCESS = {"ACCESS_DENIED", "NOT_JOINED", "UNAVAILABLE", "NO_ACCESS"}


@dataclass
class InvitationPreflightResult:
    account_exists: bool = False
    account_authorized: bool = False
    account_connected: bool = False
    account_health: str = "UNKNOWN"
    target_access: str = "UNKNOWN"
    target_role: str = "UNKNOWN"
    can_invite: bool = False
    can_manage_invite_links: bool = False
    target_access_valid: bool = False
    restriction_allows_operation: bool = True
    safety_allows_invite: bool = True
    smart_limits_enabled: bool = False
    safety_state: str = "NORMAL"
    invite_daily_limit: int = 0
    invite_used_today: int = 0
    invite_remaining_today: int = 0
    safety_next_available_at: str | None = None
    preflight_complete: bool = False
    restriction_status: str | None = None
    selected_count: int = 0
    eligible_count: int = 0
    ready_count: int = 0
    already_member_count: int = 0
    blacklist_count: int = 0
    do_not_contact_count: int = 0
    eligibility_not_approved_count: int = 0
    consent_not_approved_count: int = 0
    unknown_target_count: int = 0
    deleted_count: int = 0
    bot_count: int = 0
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    group: Any = None
    mapping: Any = None
    account: Any = None
    permission_refreshed: bool = False

    @property
    def can_start(self) -> bool:
        return (
            self.preflight_complete
            and self.account_exists
            and self.account_authorized
            and self.account_connected
            and self.target_access_valid
            and self.can_invite
            and self.restriction_allows_operation
            and self.safety_allows_invite
            and self.ready_count > 0
            and not self.blocking_reasons
        )

    @property
    def start_allowed(self) -> bool:
        # Backwards-compatible alias used by existing controller/page contracts.
        return self.can_start

    @property
    def counts(self) -> dict[str, int]:
        return {
            "selected": self.selected_count,
            "eligible": self.eligible_count,
            "already_member": self.already_member_count,
            "blacklisted": self.blacklist_count,
            "do_not_contact": self.do_not_contact_count,
            "eligibility_not_approved": self.eligibility_not_approved_count,
            "consent_not_approved": self.consent_not_approved_count,
            "unknown": self.unknown_target_count,
            "ready": self.ready_count,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["counts"] = self.counts
        data["can_start"] = self.can_start
        data["start_allowed"] = self.can_start
        # Keep domain objects for current callers; asdict() would recursively turn
        # dataclasses into dicts and break established controller/dialog contracts.
        data["group"] = self.group
        data["mapping"] = self.mapping
        data["account"] = self.account
        data["items"] = self.items
        return data


class InvitationPreflightService:
    """Central invitation-readiness evaluator.

    Local policy checks are deterministic and never raise for ordinary
    validation failures. The asynchronous path optionally refreshes current
    Telegram group permissions and runtime connection state before a write.
    """

    def __init__(
        self,
        member_repository,
        exclusion_repository,
        target_repository,
        group_repository,
        group_account_repository,
        account_repository,
        *,
        group_service=None,
        client_manager=None,
        account_safety_service=None,
    ):
        self.members = member_repository
        self.exclusions = exclusion_repository
        self.targets = target_repository
        self.groups = group_repository
        self.group_accounts = group_account_repository
        self.accounts = account_repository
        self.group_service = group_service
        self.client_manager = client_manager
        self.account_safety_service = account_safety_service
        self.eligibility_policy = InvitationEligibilityPolicy()

    @staticmethod
    def _append_unique(values: list[str], message: str) -> None:
        if message and message not in values:
            values.append(message)

    @staticmethod
    def _safe_runtime_message(error: Exception, fallback: str) -> str:
        name=type(error).__name__.lower(); message=str(error or "").lower()
        if "chatparticipantsforbidden" in name or "chatparticipantsforbidden" in message or (isinstance(error,AttributeError) and "participants" in message):
            return "Telegram hides participant details for this group. Current account rights could not be fully refreshed."
        return str(error or "").strip() or fallback

    def evaluate_cached(self, target_group_id: int, account_id: int, member_ids: list[int]) -> InvitationPreflightResult:
        result = InvitationPreflightResult(preflight_complete=True)
        result.group = self.groups.get_by_id(int(target_group_id)) if self.groups else None
        result.mapping = self.group_accounts.get_mapping(int(target_group_id), int(account_id)) if self.group_accounts else None
        result.account = self.accounts.get_by_id(int(account_id)) if self.accounts else None
        account = result.account; mapping = result.mapping; group = result.group

        result.account_exists = bool(account)
        result.account_health = str(getattr(account, "health_status", "UNKNOWN") or "UNKNOWN").upper() if account else "UNKNOWN"
        result.account_authorized = bool(
            account
            and bool(getattr(account, "is_enabled", 0))
            and str(getattr(account, "authorization_status", "UNKNOWN") or "UNKNOWN").upper() == "AUTHORIZED"
            and bool(str(getattr(account, "session_path", "") or ""))
        )
        result.account_connected = bool(account and str(getattr(account, "connection_status", "OFFLINE") or "OFFLINE").upper() == "CONNECTED")
        result.restriction_status = str(getattr(account, "restriction_type", "") or "").upper() or None if account else None

        if not group or not (bool(getattr(group, "is_target", 0)) or bool(getattr(group, "is_managed", 0))):
            self._append_unique(result.blocking_reasons, "Select a saved Target Group first.")
        if not mapping:
            result.target_access = "NO_ACCESS"
            result.target_role = "UNKNOWN"
            result.target_access_valid = False
            self._append_unique(result.blocking_reasons, "The selected account is not mapped to this target group.")
        else:
            result.target_access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
            raw_role = str(getattr(mapping, "role", "UNKNOWN") or "UNKNOWN").upper()
            result.can_invite = bool(getattr(mapping, "can_invite", 0))
            result.target_access_valid = bool(
                result.target_access not in DENIED_ACCESS
                and getattr(mapping, "can_view", None) is not False
                and raw_role not in {"BANNED", "LEFT", "NOT_JOINED", "NO_ACCESS"}
            )
            if raw_role == "MEMBER":
                result.target_role = "MEMBER_WITH_INVITE_PERMISSION" if result.can_invite else "MEMBER_WITHOUT_INVITE_PERMISSION"
            elif raw_role in {"OWNER", "ADMIN"}:
                result.target_role = raw_role
            elif not result.target_access_valid:
                result.target_role = "NO_ACCESS"
            else:
                result.target_role = raw_role
            result.can_manage_invite_links = bool(getattr(mapping, "can_manage_invite_links", 0))
            if not result.target_access_valid:
                self._append_unique(result.blocking_reasons, "The selected account does not currently have target access.")
            if not result.can_invite:
                self._append_unique(result.blocking_reasons, "This account does not currently have permission to invite users to the selected target.")

        if not result.account_exists:
            self._append_unique(result.blocking_reasons, "The selected Telegram account no longer exists.")
        elif not result.account_authorized:
            self._append_unique(result.blocking_reasons, "The selected account is not authorized for Telegram operations.")
        if result.account_health in BLOCKING_HEALTH:
            self._append_unique(result.blocking_reasons, "The selected account is not currently healthy enough for direct invitations.")
            result.restriction_allows_operation = False
        if result.restriction_status and result.restriction_status not in {"NONE", "NONE_KNOWN", "UNKNOWN"}:
            result.restriction_allows_operation = False
            self._append_unique(result.blocking_reasons, f"Account restriction: {result.restriction_status.replace('_', ' ').title()}.")

        if result.account_exists and self.account_safety_service is not None:
            decision = self.account_safety_service.preview(int(account_id), "INVITE", requested=1, enforce_interval=False)
            result.safety_allows_invite = bool(decision.allowed)
            result.smart_limits_enabled = bool(decision.smart_mode)
            result.safety_state = str(decision.state or "NORMAL")
            result.invite_daily_limit = int(decision.daily_limit)
            result.invite_used_today = int(decision.used_today)
            result.invite_remaining_today = int(decision.remaining_today)
            result.safety_next_available_at = decision.next_available_at
            if not decision.allowed:
                self._append_unique(result.blocking_reasons, decision.message)

        for member_id in sorted({int(x) for x in member_ids}):
            member = self.members.get_by_id(member_id)
            if not member:
                continue
            result.selected_count += 1
            state = self.targets.get_state(member_id, int(target_group_id)) if self.targets else None
            target_state = str(getattr(state, "state", "UNKNOWN") or "UNKNOWN").upper()
            blacklisted = bool(self.exclusions and self.exclusions.is_global_blacklisted(member_id))
            dnc = bool(self.exclusions and self.exclusions.is_do_not_contact(member_id))
            policy = self.eligibility_policy.evaluate(member, target_state, blacklisted=blacklisted, do_not_contact=dnc)
            reasons = list(policy.reasons)
            reason = reasons[0] if reasons else None
            if policy.allowed:
                result.eligible_count += 1
                result.ready_count += 1
            else:
                if ELIGIBILITY_NOT_APPROVED in reasons: result.eligibility_not_approved_count += 1
                if CONSENT_NOT_APPROVED in reasons: result.consent_not_approved_count += 1
                if BLACKLISTED in reasons: result.blacklist_count += 1
                if DO_NOT_CONTACT in reasons: result.do_not_contact_count += 1
                if DELETED in reasons: result.deleted_count += 1
                if BOT in reasons: result.bot_count += 1
                if ALREADY_MEMBER in reasons: result.already_member_count += 1
                if TARGET_STATUS_UNKNOWN in reasons: result.unknown_target_count += 1
            result.items.append({
                "member": member, "target_state": target_state, "reason": reason,
                "reasons": reasons, "allowed": policy.allowed,
            })

        if result.selected_count == 0:
            self._append_unique(result.blocking_reasons, "No valid selected Member Pool records are available.")
        elif result.ready_count == 0:
            self._append_unique(result.blocking_reasons, "No selected member currently passes the direct-invitation eligibility policy.")
        if not result.account_connected:
            self._append_unique(result.warnings, "Telegram runtime connection has not yet been confirmed for this account.")
        return result

    async def refresh(self, target_group_id: int, account_id: int, member_ids: list[int]) -> InvitationPreflightResult:
        # Start from local state so ordinary data problems become inline blockers.
        result = self.evaluate_cached(target_group_id, account_id, member_ids)
        if not result.group or not result.account or not result.mapping:
            return result

        # Current permission data is authoritative before a write. Any failure is
        # represented as a normal operational blocker rather than a programming error.
        if self.group_service is not None:
            try:
                await self.group_service.refresh_permissions(int(target_group_id), int(account_id))
                result.permission_refreshed = True
            except Exception as exc:
                self._append_unique(result.blocking_reasons, self._safe_runtime_message(exc,"Target permission refresh failed."))

        # Re-evaluate after the permission repository was refreshed.
        refreshed = self.evaluate_cached(target_group_id, account_id, member_ids)
        refreshed.permission_refreshed = result.permission_refreshed
        for message in result.blocking_reasons:
            if not result.permission_refreshed and message not in refreshed.blocking_reasons:
                self._append_unique(refreshed.blocking_reasons, message)

        if self.client_manager is not None and refreshed.account:
            try:
                client = await self.client_manager.get_client(int(account_id))
                if client is not None:
                    connected = bool(client.is_connected()) if hasattr(client, "is_connected") else True
                    refreshed.account_connected = connected
                    if connected and hasattr(client, "is_user_authorized"):
                        refreshed.account_authorized = bool(await client.is_user_authorized())
            except Exception as exc:
                refreshed.account_connected = False
                self._append_unique(refreshed.blocking_reasons, self._safe_runtime_message(exc,"Telegram connection check failed."))

        # Session-path existence is useful for stale rows but must not override a
        # currently connected/authorized client.
        path = str(getattr(refreshed.account, "session_path", "") or "") if refreshed.account else ""
        if path and not Path(path).is_file() and not refreshed.account_connected:
            refreshed.account_authorized = False
            self._append_unique(refreshed.blocking_reasons, "The selected account session file is unavailable.")

        # Reconcile cached blockers with the authoritative runtime result. A stale
        # database connection/auth status must not keep Start disabled after a live
        # client check succeeds.
        if refreshed.account_connected:
            refreshed.warnings = [x for x in refreshed.warnings if "connection" not in x.lower()]
            refreshed.blocking_reasons = [x for x in refreshed.blocking_reasons if "disconnected" not in x.lower()]
        else:
            self._append_unique(refreshed.blocking_reasons, "The selected Telegram account is disconnected.")
        if refreshed.account_authorized:
            refreshed.blocking_reasons = [
                x for x in refreshed.blocking_reasons
                if "not authorized" not in x.lower() and "session file is unavailable" not in x.lower()
            ]
        else:
            self._append_unique(refreshed.blocking_reasons, "The selected Telegram session is not authorized.")
        return refreshed
