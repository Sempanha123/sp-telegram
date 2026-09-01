from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


def _from_row(cls, row):
    if row is None:
        return None
    data = dict(row)
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: data.get(key) for key in allowed})


@dataclass
class TelegramAccount:
    id: int | None = None
    telegram_user_id: int | None = None
    phone: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_premium: int = 0
    session_path: str | None = None
    connection_status: str = "OFFLINE"
    health_status: str = "UNKNOWN"
    can_collect: int = 0
    can_invite: int = 0
    can_post: int = 0
    can_schedule: int = 0
    can_manage: int = 0
    restriction_type: str | None = None
    restriction_source: str | None = None
    restriction_confidence: str | None = None
    restriction_reason: str | None = None
    restriction_started_at: str | None = None
    restriction_until: str | None = None
    last_connected_at: str | None = None
    last_active_at: str | None = None
    last_health_check_at: str | None = None
    last_collect_at: str | None = None
    last_invite_attempt_at: str | None = None
    last_invite_success_at: str | None = None
    last_post_at: str | None = None
    last_schedule_at: str | None = None
    last_success_at: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_error_at: str | None = None
    notes: str | None = None
    is_enabled: int = 1
    enabled_for_operations: int = 1
    authorization_status: str = "UNKNOWN"
    is_demo: int = 0
    photo_cache_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    tags: str = ""

    @classmethod
    def from_row(cls, row):
        return _from_row(cls, row)


@dataclass
class AccountRestriction:
    id: int | None = None
    account_id: int | None = None
    restriction_type: str = "UNKNOWN"
    source: str = "UNKNOWN"
    confidence: str | None = None
    error_code: str | None = None
    reason: str | None = None
    started_at: str | None = None
    expires_at: str | None = None
    is_active: int = 1
    details_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    scope: str = "ACCOUNT"
    state: str = "ACTIVE"
    requires_action: int = 0
    last_rechecked_at: str | None = None
    resolution_note: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class AccountActivity:
    id: int | None = None
    account_id: int | None = None
    action_type: str = ""
    status: str | None = None
    target_type: str | None = None
    target_id: int | None = None
    message: str | None = None
    metadata_json: str | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class TelegramGroup:
    id: int | None = None
    telegram_group_id: int | None = None
    title: str = ""
    username: str | None = None
    group_type: str = "UNKNOWN"
    access_type: str = "UNKNOWN"
    access_state: str = "UNKNOWN"
    member_count: int = 0
    description: str | None = None
    is_verified: int = 0
    is_scam: int = 0
    is_fake: int = 0
    is_forum: int = 0
    is_broadcast: int = 0
    is_megagroup: int = 0
    is_gigagroup: int = 0
    linked_chat_id: int | None = None
    photo_cache_path: str | None = None
    is_source: int = 0
    is_target: int = 0
    is_managed: int = 0
    status: str = "UNKNOWN"
    last_sync_at: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_error_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Joined display fields populated by repository queries.
    role: str = "UNKNOWN"
    account_name: str = ""
    primary_account_id: int | None = None
    mapping_access_state: str = "UNKNOWN"
    can_post: int | None = None
    can_invite: int | None = None
    can_manage: int | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class GroupAccount:
    id: int | None = None
    group_id: int | None = None
    account_id: int | None = None
    role: str = "UNKNOWN"
    access_state: str = "UNKNOWN"
    can_view: int | None = None
    can_post: int | None = None
    can_send_media: int | None = None
    can_invite: int | None = None
    can_manage: int | None = None
    can_delete_messages: int | None = None
    can_pin_messages: int | None = None
    can_ban_users: int | None = None
    can_add_admins: int | None = None
    can_manage_call: int | None = None
    can_manage_topics: int | None = None
    can_manage_invite_links: int | None = None
    can_approve_join_requests: int | None = None
    is_primary: int = 0
    joined_at: str | None = None
    last_access_check_at: str | None = None
    last_permission_check_at: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    member_list_availability: str = "UNKNOWN"
    member_list_checked_at: str | None = None
    last_member_sync_at: str | None = None
    member_sync_status: str = "NEVER_SYNCED"
    stored_member_count: int = 0
    last_member_new: int = 0
    last_member_updated: int = 0
    last_member_excluded: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    account_name: str = ""
    account_username: str | None = None
    connection_status: str = "OFFLINE"
    health_status: str = "UNKNOWN"

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class Member:
    id: int | None = None
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    is_deleted: int = 0
    is_bot: int = 0
    is_verified: int = 0
    is_scam: int = 0
    is_fake: int = 0
    is_premium: int = 0
    eligibility_status: str = "UNKNOWN"
    consent_status: str = "UNKNOWN"
    global_excluded: int = 0
    notes: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    profile_updated_at: str | None = None
    photo_cache_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sources: str = ""
    tags: str = ""
    is_blacklisted: int = 0
    existing_target_state: str = "UNKNOWN"
    # Joined display field: local account that last saw this member, used to
    # authorize real profile-photo downloads in the UI.
    account_id: int | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class MemberSource:
    id: int | None = None
    member_id: int | None = None
    group_id: int | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    first_seen_by_account_id: int | None = None
    last_seen_by_account_id: int | None = None
    source_status: str = "ACTIVE"
    created_at: str | None = None
    updated_at: str | None = None
    last_seen_sync_run_id: str | None = None
    group_title: str = ""
    account_name: str = ""

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class MemberExclusion:
    id: int | None = None
    member_id: int | None = None
    exclusion_type: str = "GLOBAL_BLACKLIST"
    target_group_id: int | None = None
    reason: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class MemberTargetState:
    id: int | None = None
    member_id: int | None = None
    target_group_id: int | None = None
    state: str = "UNKNOWN"
    checked_by_account_id: int | None = None
    last_checked_at: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class AccountMemberState:
    id: int | None = None
    account_id: int | None = None
    member_id: int | None = None
    state: str = "UNKNOWN"
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_checked_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class MemberSyncRun:
    id: int | None = None
    sync_run_id: str = ""
    job_id: int | None = None
    group_id: int | None = None
    account_id: int | None = None
    availability: str = "UNKNOWN"
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    excluded: int = 0
    errors: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    status: str = "QUEUED"
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class Campaign:
    id: int | None = None
    name: str = ""
    description: str | None = None
    campaign_type: str | None = None
    status: str = "DRAFT"
    schedule_type: str | None = None
    send_at: str | None = None
    timezone: str | None = None
    repeat_rule: str | None = None
    default_account_id: int | None = None
    template_id: int | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_run_at: str | None = None
    next_run_at: str | None = None
    total_targets: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    target_count: int = 0
    message_count: int = 0
    account_count: int = 0
    posting_account: str = "Assigned"

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class CampaignTarget:
    id: int | None = None
    campaign_id: int | None = None
    group_id: int | None = None
    account_id: int | None = None
    status: str = "PENDING"
    telegram_message_id: str | None = None
    telegram_scheduled_message_id: str | None = None
    scheduled_message_id: str | None = None
    scheduled_at: str | None = None
    sent_at: str | None = None
    attempt_count: int = 0
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    group_title: str | None = None
    group_username: str | None = None
    account_name: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class CampaignMessage:
    id: int | None = None
    campaign_id: int | None = None
    position: int = 0
    message_type: str = "TEXT"
    body: str | None = None
    caption: str | None = None
    media_path: str | None = None
    media_name: str | None = None
    media_size: int | None = None
    content_hash: str | None = None
    parse_mode: str = "PLAIN"
    disable_link_preview: int = 0
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class Schedule:
    id: int | None = None
    campaign_id: int | None = None
    schedule_type: str = "ONCE"
    run_at: str | None = None
    timezone: str | None = None
    repeat_rule: str | None = None
    next_run_at: str | None = None
    last_run_at: str | None = None
    is_enabled: int = 1
    status: str | None = None
    occurrence_key: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    missed_policy: str = "ASK_ME"
    created_at: str | None = None
    updated_at: str | None = None
    campaign_name: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class CampaignDelivery:
    id: int | None = None
    campaign_id: int | None = None
    campaign_target_id: int | None = None
    campaign_message_id: int | None = None
    occurrence_key: str = ""
    content_hash: str = ""
    telegram_message_id: str | None = None
    telegram_scheduled_message_id: str | None = None
    status: str = "PENDING"
    scheduled_for: str | None = None
    sent_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class CampaignTemplate:
    id: int | None = None
    name: str = ""
    description: str | None = None
    template_type: str = "TEXT"
    default_parse_mode: str = "PLAIN"
    default_schedule_type: str | None = None
    default_timezone: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    last_used_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class Job:
    id: int | None = None
    job_type: str = ""
    status: str = "QUEUED"
    account_id: int | None = None
    group_id: int | None = None
    campaign_id: int | None = None
    progress: int = 0
    total_items: int = 0
    success_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    metadata_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    retry_classification: str = "UNKNOWN"
    interrupted_at: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class JobItem:
    id: int | None = None
    job_id: int | None = None
    item_type: str | None = None
    item_id: int | None = None
    status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class Alert:
    id: int | None = None
    severity: str = "INFO"
    alert_type: str = "SYSTEM"
    title: str = ""
    message: str | None = None
    account_id: int | None = None
    group_id: int | None = None
    campaign_id: int | None = None
    job_id: int | None = None
    is_read: int = 0
    is_resolved: int = 0
    created_at: str | None = None
    resolved_at: str | None = None
    dedupe_key: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    occurrence_count: int = 1
    requires_action: int = 0
    action_type: str | None = None
    status: str = "OPEN"

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class LogEntry:
    id: int | None = None
    level: str = "INFO"
    category: str = "SYSTEM"
    account_id: int | None = None
    group_id: int | None = None
    campaign_id: int | None = None
    job_id: int | None = None
    action: str | None = None
    message: str = ""
    details_json: str | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class TelegramSessionCache:
    id: int | None = None
    account_id: int | None = None
    authorization_hash: str = ""
    device_model: str | None = None
    platform: str | None = None
    system_version: str | None = None
    app_name: str | None = None
    app_version: str | None = None
    location: str | None = None
    last_active_at: str | None = None
    created_at: str | None = None
    is_current: int = 0
    last_synced_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class JobAttempt:
    id: int | None = None
    job_id: int | None = None
    attempt_number: int = 1
    started_at: str | None = None
    finished_at: str | None = None
    status: str = "RUNNING"
    error_code: str | None = None
    error_message: str | None = None
    retry_classification: str = "UNKNOWN"
    created_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class RecoveryEvent:
    id: int | None = None
    component: str = "SYSTEM"
    event_type: str = "UNKNOWN"
    trigger: str | None = None
    action: str | None = None
    result: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)


@dataclass
class AuditEvent:
    id: int | None = None
    actor: str = "LOCAL_USER"
    action: str = ""
    resource_type: str | None = None
    resource_id: str | None = None
    description: str | None = None
    before_json: str | None = None
    after_json: str | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row): return _from_row(cls, row)
