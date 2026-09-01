from __future__ import annotations
from dataclasses import dataclass, field
from app.utils.formatters import utc_now_iso

@dataclass(slots=True)
class MemberSyncOptions:
    skip_bots: bool = True
    skip_deleted: bool = True
    save_unknown: bool = True
    update_existing_profiles: bool = True
    sync_sources: bool = True
    apply_eligibility: bool = True
    page_size: int = 200
    max_records: int | None = None
    skip_blacklist: bool = True
    only_with_username: bool = False

@dataclass(slots=True)
class MemberBatchResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    excluded: int = 0
    errors: int = 0

@dataclass(slots=True)
class MemberSyncProgress:
    sync_run_id: str
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    excluded: int = 0
    bots: int = 0
    deleted: int = 0
    errors: int = 0
    availability: str = "UNKNOWN"
    current_member_id: int | None = None
    plan_limit_skipped: int = 0

@dataclass(slots=True)
class MemberSyncResult:
    sync_run_id: str
    group_id: int
    account_id: int
    availability: str = "UNKNOWN"
    status: str = "COMPLETED"
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    excluded: int = 0
    bots: int = 0
    deleted: int = 0
    errors: int = 0
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    plan_limit_skipped: int = 0
