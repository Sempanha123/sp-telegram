from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.constants import AccountHealthStatus


def json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"


def json_loads_safe(value: str | None, default: Any = None) -> Any:
    fallback = {} if default is None else default
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def ensure_app_directories(project_root: Path) -> None:
    for name in ("data", "data/sessions", "data/cache/avatars", "backups", "logs"):
        (project_root / name).mkdir(parents=True, exist_ok=True)


def can_use_account_for_action(account: dict, action: str) -> tuple[bool, str]:
    """UI safety gate; never rotates accounts to bypass restrictions."""
    health = str(account.get("health_status") or account.get("Health") or "").upper().replace(" ", "_")
    enabled = bool(account.get("is_enabled", account.get("Enabled", True)))
    if not enabled:
        return False, "Unavailable because this account is disabled."
    blocked_health = {"RESTRICTED", "COOLDOWN", "SESSION_INVALID", "LOGIN_REQUIRED"}
    capability_map = {
        "COLLECT": "can_collect",
        "INVITE": "can_invite",
        "POST": "can_post",
        "SCHEDULE": "can_schedule",
        "MANAGE": "can_manage",
    }
    if action.upper() == "CONNECT":
        return health not in {"SESSION_INVALID"}, "Unavailable because the local session is invalid."
    field = capability_map.get(action.upper())
    if health in blocked_health and action.upper() == "INVITE":
        return False, "Unavailable because this account currently has an invite restriction or cooldown."
    if field and not bool(account.get(field, account.get(field.replace("can_", "Can ").title(), False))):
        return False, f"Unavailable because this account does not currently support {action.lower()}."
    return True, ""
