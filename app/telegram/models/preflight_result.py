from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(slots=True)
class TargetPreflightResult:
    group_id: int
    account_id: int | None
    ready: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    capabilities: dict[str, bool | None] = field(default_factory=dict)

@dataclass(slots=True)
class CampaignPreflightResult:
    campaign_id: int | None
    total_targets: int
    ready_targets: int
    warning_targets: int
    blocked_targets: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    targets: list[TargetPreflightResult] = field(default_factory=list)
