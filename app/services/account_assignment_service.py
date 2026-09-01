from __future__ import annotations

from dataclasses import dataclass


BLOCKING_HEALTH = {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}
DENIED_ACCESS = {"ACCESS_DENIED", "NOT_JOINED", "UNAVAILABLE", "NO_ACCESS", "BANNED", "LEFT"}


@dataclass(frozen=True)
class AccountAssignmentDecision:
    account_id: int | None
    allowed: bool
    reason: str
    account: object | None = None
    mapping: object | None = None


class AccountAssignmentService:
    """Choose one valid account before a job starts.

    This service intentionally has no retry/rotation API. Once a job has an
    account_id, later restrictions pause/stop that job for operator review.
    """

    PERMISSIONS = {
        "invite": "can_invite",
        "post": "can_post",
        "invite_link": "can_manage_invite_links",
        "approve_join": "can_approve_join_requests",
        "view": "can_view",
    }

    def __init__(self, account_repository, group_account_repository, job_repository=None):
        self.accounts = account_repository
        self.group_accounts = group_account_repository
        self.jobs = job_repository

    def _validate(self, group_id: int, account_id: int, permission: str) -> AccountAssignmentDecision:
        account = self.accounts.get_by_id(int(account_id))
        if not account:
            return AccountAssignmentDecision(None, False, "Account does not exist.")
        if not bool(getattr(account, "is_enabled", 0)):
            return AccountAssignmentDecision(int(account_id), False, "Account is disabled.", account=account)
        if not bool(getattr(account, "enabled_for_operations", 1)):
            return AccountAssignmentDecision(int(account_id), False, "Account is disabled for new operations.", account=account)
        if str(getattr(account, "authorization_status", "UNKNOWN") or "UNKNOWN").upper() != "AUTHORIZED":
            return AccountAssignmentDecision(int(account_id), False, "Account login is required.", account=account)
        if str(getattr(account, "connection_status", "OFFLINE") or "OFFLINE").upper() != "CONNECTED":
            return AccountAssignmentDecision(int(account_id), False, "Account is disconnected.", account=account)
        health = str(getattr(account, "health_status", "UNKNOWN") or "UNKNOWN").upper()
        if health in BLOCKING_HEALTH:
            return AccountAssignmentDecision(int(account_id), False, f"Account health is {health.replace('_',' ').title()}.", account=account)
        restriction = str(getattr(account, "restriction_type", "") or "").upper()
        if restriction and restriction not in {"NONE", "NONE_KNOWN", "UNKNOWN"}:
            return AccountAssignmentDecision(int(account_id), False, f"Account restriction: {restriction.replace('_',' ').title()}.", account=account)
        if self.jobs is not None:
            row = self.jobs.db.fetch_one(
                "SELECT id,job_type FROM jobs WHERE account_id=? AND status IN ('RUNNING','QUEUED','PAUSED') ORDER BY id DESC LIMIT 1",
                (int(account_id),),
            )
            if row:
                return AccountAssignmentDecision(int(account_id), False, f"Account is already assigned to active job #{int(row['id'])} ({row['job_type']}).", account=account)
        mapping = self.group_accounts.get_mapping(int(group_id), int(account_id))
        if not mapping:
            return AccountAssignmentDecision(int(account_id), False, "Account is not mapped to the selected group.", account=account)
        access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
        if access in DENIED_ACCESS or getattr(mapping, "can_view", None) is False:
            return AccountAssignmentDecision(int(account_id), False, "Account does not currently have group access.", account=account, mapping=mapping)
        field = self.PERMISSIONS.get(str(permission), str(permission))
        if not bool(getattr(mapping, field, 0)):
            return AccountAssignmentDecision(int(account_id), False, f"Required permission {field.replace('can_','').replace('_',' ')} is unavailable.", account=account, mapping=mapping)
        return AccountAssignmentDecision(int(account_id), True, "Healthy, connected, mapped and permission verified.", account=account, mapping=mapping)

    def validate_manual(self, group_id: int, account_id: int, permission: str) -> AccountAssignmentDecision:
        return self._validate(group_id, account_id, permission)

    def auto_select(self, group_id: int, permission: str) -> AccountAssignmentDecision:
        mappings = list(self.group_accounts.get_group_accounts(int(group_id)) or [])
        mappings.sort(key=lambda m: (not bool(getattr(m, "is_primary", 0)), int(getattr(m, "id", 0) or 0)))
        reasons: list[str] = []
        for mapping in mappings:
            decision = self._validate(int(group_id), int(mapping.account_id), permission)
            if decision.allowed:
                return decision
            reasons.append(decision.reason)
        return AccountAssignmentDecision(None, False, reasons[0] if reasons else "No valid authorized account is available for this group.")
