from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        def __str__(self): return str(self.value)


class PlanKey(StrEnum):
    STARTER = "STARTER"
    PRO = "PRO"
    ULTIMATE = "ULTIMATE"


class LicenseStatus(StrEnum):
    UNLICENSED = "UNLICENSED"
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    OFFLINE_GRACE = "OFFLINE_GRACE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    DEVICE_LIMIT = "DEVICE_LIMIT"
    INVALID = "INVALID"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"


class LimitState(StrEnum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    AT_LIMIT = "AT_LIMIT"
    OVER_LIMIT = "OVER_LIMIT"


@dataclass
class LicenseState:
    id: int = 1
    plan: str | None = None
    status: str = LicenseStatus.UNLICENSED
    license_key_masked: str | None = None
    license_reference: str | None = None
    expires_at: str | None = None
    activated_at: str | None = None
    last_validated_at: str | None = None
    offline_grace_until: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    server_license_id: str | None = None
    cached_license_payload: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def plan_key(self) -> PlanKey | None:
        try: return PlanKey(str(self.plan)) if self.plan else None
        except ValueError: return None


@dataclass
class LicenseDevice:
    server_device_id: str | None
    device_id: str
    device_name: str
    platform: str
    is_current: bool = False
    is_active: bool = True
    activated_at: str | None = None
    last_seen_at: str | None = None
    last_synced_at: str | None = None


@dataclass
class LimitCheckResult:
    allowed: bool
    current: int
    limit: int | None
    remaining: int | None
    reason_code: str | None = None
    message: str | None = None
    state: str = LimitState.WITHIN_LIMIT


@dataclass
class LicenseApiResult:
    ok: bool
    plan: str | None = None
    status: str | None = None
    expires_at: str | None = None
    license_reference: str | None = None
    server_license_id: str | None = None
    devices: list[dict[str, Any]] = field(default_factory=list)
    cached_payload: dict[str, Any] | None = None
    error_code: str | None = None
    message: str | None = None
    trusted: bool = False


@dataclass
class LicenseSummary:
    state: LicenseState
    plan_name: str
    price_monthly: int | None
    device_limit: int | None
    days_remaining: int | None
    usage: dict[str, dict[str, Any]]
