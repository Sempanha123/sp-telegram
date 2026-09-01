from __future__ import annotations

SCHEMA_VERSION = 13

MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS telegram_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE,
    phone TEXT,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_premium INTEGER DEFAULT 0,
    session_path TEXT,
    connection_status TEXT DEFAULT 'OFFLINE',
    health_status TEXT DEFAULT 'UNKNOWN',
    restriction_type TEXT,
    restriction_source TEXT,
    restriction_confidence TEXT,
    restriction_reason TEXT,
    restriction_started_at TEXT,
    restriction_until TEXT,
    last_connected_at TEXT,
    last_active_at TEXT,
    last_health_check_at TEXT,
    last_collect_at TEXT,
    last_invite_attempt_at TEXT,
    last_invite_success_at TEXT,
    last_post_at TEXT,
    last_schedule_at TEXT,
    last_success_at TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    last_error_at TEXT,
    notes TEXT,
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_tag_links (
    account_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (account_id, tag_id),
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES account_tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account_restrictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    restriction_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence TEXT,
    error_code TEXT,
    reason TEXT,
    started_at TEXT,
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    details_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS account_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT,
    target_type TEXT,
    target_id INTEGER,
    message TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_group_id INTEGER UNIQUE,
    title TEXT NOT NULL,
    username TEXT,
    group_type TEXT DEFAULT 'UNKNOWN',
    access_type TEXT DEFAULT 'UNKNOWN',
    member_count INTEGER DEFAULT 0,
    description TEXT,
    is_source INTEGER DEFAULT 0,
    is_target INTEGER DEFAULT 0,
    is_managed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'UNKNOWN',
    last_sync_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    role TEXT DEFAULT 'UNKNOWN',
    can_post INTEGER DEFAULT 0,
    can_invite INTEGER DEFAULT 0,
    can_manage INTEGER DEFAULT 0,
    is_primary INTEGER DEFAULT 0,
    last_permission_check_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (group_id, account_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_deleted INTEGER DEFAULT 0,
    is_bot INTEGER DEFAULT 0,
    eligibility_status TEXT DEFAULT 'UNKNOWN',
    consent_status TEXT DEFAULT 'UNKNOWN',
    notes TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS member_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (member_id, group_id),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS member_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS member_tag_links (
    member_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (member_id, tag_id),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES member_tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member_exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    exclusion_type TEXT NOT NULL,
    target_group_id INTEGER,
    reason TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (target_group_id) REFERENCES groups(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS member_target_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    target_group_id INTEGER NOT NULL,
    state TEXT DEFAULT 'UNKNOWN',
    last_checked_at TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (member_id, target_group_id),
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (target_group_id) REFERENCES groups(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    account_id INTEGER,
    group_id INTEGER,
    campaign_id INTEGER,
    progress INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    item_type TEXT,
    item_id INTEGER,
    status TEXT,
    error_code TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT,
    account_id INTEGER,
    group_id INTEGER,
    campaign_id INTEGER,
    job_id INTEGER,
    is_read INTEGER DEFAULT 0,
    is_resolved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    category TEXT NOT NULL,
    account_id INTEGER,
    group_id INTEGER,
    action TEXT,
    message TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    value_type TEXT NOT NULL DEFAULT 'STRING',
    updated_at TEXT NOT NULL
);
"""

MIGRATION_002 = """
CREATE INDEX IF NOT EXISTS idx_accounts_username ON telegram_accounts(username);
CREATE INDEX IF NOT EXISTS idx_accounts_health ON telegram_accounts(health_status);
CREATE INDEX IF NOT EXISTS idx_accounts_enabled ON telegram_accounts(is_enabled);
CREATE INDEX IF NOT EXISTS idx_restrictions_account_active ON account_restrictions(account_id, is_active);
CREATE INDEX IF NOT EXISTS idx_activity_account_created ON account_activity(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_groups_username ON groups(username);
CREATE INDEX IF NOT EXISTS idx_groups_source ON groups(is_source);
CREATE INDEX IF NOT EXISTS idx_groups_target ON groups(is_target);
CREATE INDEX IF NOT EXISTS idx_groups_managed ON groups(is_managed);
CREATE INDEX IF NOT EXISTS idx_group_accounts_group ON group_accounts(group_id);
CREATE INDEX IF NOT EXISTS idx_group_accounts_account ON group_accounts(account_id);
CREATE INDEX IF NOT EXISTS idx_members_username ON members(username);
CREATE INDEX IF NOT EXISTS idx_members_eligibility ON members(eligibility_status);
CREATE INDEX IF NOT EXISTS idx_members_consent ON members(consent_status);
CREATE INDEX IF NOT EXISTS idx_member_sources_group ON member_sources(group_id);
CREATE INDEX IF NOT EXISTS idx_member_sources_member ON member_sources(member_id);
CREATE INDEX IF NOT EXISTS idx_exclusions_member ON member_exclusions(member_id);
CREATE INDEX IF NOT EXISTS idx_exclusions_target ON member_exclusions(target_group_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level_category ON logs(level, category);
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, is_resolved);
"""

MIGRATION_003 = """
ALTER TABLE telegram_accounts ADD COLUMN can_collect INTEGER DEFAULT 0;
ALTER TABLE telegram_accounts ADD COLUMN can_invite INTEGER DEFAULT 0;
ALTER TABLE telegram_accounts ADD COLUMN can_post INTEGER DEFAULT 0;
ALTER TABLE telegram_accounts ADD COLUMN can_schedule INTEGER DEFAULT 0;
ALTER TABLE telegram_accounts ADD COLUMN can_manage INTEGER DEFAULT 0;
"""

MIGRATION_004 = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    campaign_type TEXT,
    status TEXT DEFAULT 'DRAFT',
    schedule_type TEXT,
    send_at TEXT,
    timezone TEXT,
    repeat_rule TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    account_id INTEGER,
    status TEXT,
    scheduled_message_id TEXT,
    sent_at TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (campaign_id, group_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id) REFERENCES telegram_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS campaign_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    message_type TEXT NOT NULL,
    body TEXT,
    caption TEXT,
    media_path TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    schedule_type TEXT NOT NULL,
    run_at TEXT,
    timezone TEXT,
    repeat_rule TEXT,
    next_run_at TEXT,
    last_run_at TEXT,
    is_enabled INTEGER DEFAULT 1,
    status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_campaign_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_campaign ON campaign_targets(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_messages_campaign ON campaign_messages(campaign_id, position);
CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules(is_enabled, next_run_at);
"""


MIGRATION_005 = """
ALTER TABLE telegram_accounts ADD COLUMN authorization_status TEXT DEFAULT 'UNKNOWN';
ALTER TABLE telegram_accounts ADD COLUMN is_demo INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS telegram_session_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    authorization_hash TEXT NOT NULL,
    device_model TEXT,
    platform TEXT,
    system_version TEXT,
    app_name TEXT,
    app_version TEXT,
    location TEXT,
    last_active_at TEXT,
    created_at TEXT,
    is_current INTEGER DEFAULT 0,
    last_synced_at TEXT NOT NULL,
    UNIQUE(account_id, authorization_hash),
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_accounts_authorization ON telegram_accounts(authorization_status);
CREATE INDEX IF NOT EXISTS idx_session_cache_account ON telegram_session_cache(account_id, is_current);
"""


MIGRATION_006 = """
ALTER TABLE groups ADD COLUMN access_state TEXT DEFAULT 'UNKNOWN';
ALTER TABLE groups ADD COLUMN is_verified INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_scam INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_fake INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_forum INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_broadcast INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_megagroup INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN is_gigagroup INTEGER DEFAULT 0;
ALTER TABLE groups ADD COLUMN linked_chat_id INTEGER;
ALTER TABLE groups ADD COLUMN photo_cache_path TEXT;
ALTER TABLE groups ADD COLUMN last_error_code TEXT;
ALTER TABLE groups ADD COLUMN last_error_message TEXT;
ALTER TABLE groups ADD COLUMN last_error_at TEXT;

ALTER TABLE group_accounts ADD COLUMN access_state TEXT DEFAULT 'UNKNOWN';
ALTER TABLE group_accounts ADD COLUMN can_view INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_send_media INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_delete_messages INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_pin_messages INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_ban_users INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_add_admins INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_manage_call INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_manage_topics INTEGER;
ALTER TABLE group_accounts ADD COLUMN can_manage_invite_links INTEGER;
ALTER TABLE group_accounts ADD COLUMN joined_at TEXT;
ALTER TABLE group_accounts ADD COLUMN last_access_check_at TEXT;
ALTER TABLE group_accounts ADD COLUMN last_error_code TEXT;
ALTER TABLE group_accounts ADD COLUMN last_error_message TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_primary_one
ON group_accounts(group_id) WHERE is_primary = 1;
CREATE INDEX IF NOT EXISTS idx_groups_access_state ON groups(access_state);
CREATE INDEX IF NOT EXISTS idx_groups_status ON groups(status);
CREATE INDEX IF NOT EXISTS idx_groups_type_status ON groups(group_type, status);
CREATE INDEX IF NOT EXISTS idx_group_accounts_role ON group_accounts(role);
CREATE INDEX IF NOT EXISTS idx_group_accounts_access ON group_accounts(access_state);
"""


MIGRATION_007 = """
ALTER TABLE members ADD COLUMN display_name TEXT;
ALTER TABLE members ADD COLUMN is_verified INTEGER DEFAULT 0;
ALTER TABLE members ADD COLUMN is_scam INTEGER DEFAULT 0;
ALTER TABLE members ADD COLUMN is_fake INTEGER DEFAULT 0;
ALTER TABLE members ADD COLUMN is_premium INTEGER DEFAULT 0;
ALTER TABLE members ADD COLUMN profile_updated_at TEXT;
ALTER TABLE members ADD COLUMN global_excluded INTEGER DEFAULT 0;

ALTER TABLE member_sources ADD COLUMN first_seen_by_account_id INTEGER;
ALTER TABLE member_sources ADD COLUMN last_seen_by_account_id INTEGER;
ALTER TABLE member_sources ADD COLUMN source_status TEXT DEFAULT 'ACTIVE';
ALTER TABLE member_sources ADD COLUMN updated_at TEXT;
ALTER TABLE member_sources ADD COLUMN last_seen_sync_run_id TEXT;

ALTER TABLE member_target_states ADD COLUMN checked_by_account_id INTEGER;

ALTER TABLE group_accounts ADD COLUMN member_list_availability TEXT DEFAULT 'UNKNOWN';
ALTER TABLE group_accounts ADD COLUMN member_list_checked_at TEXT;
ALTER TABLE group_accounts ADD COLUMN last_member_sync_at TEXT;
ALTER TABLE group_accounts ADD COLUMN member_sync_status TEXT DEFAULT 'NEVER_SYNCED';
ALTER TABLE group_accounts ADD COLUMN stored_member_count INTEGER DEFAULT 0;
ALTER TABLE group_accounts ADD COLUMN last_member_new INTEGER DEFAULT 0;
ALTER TABLE group_accounts ADD COLUMN last_member_updated INTEGER DEFAULT 0;
ALTER TABLE group_accounts ADD COLUMN last_member_excluded INTEGER DEFAULT 0;

ALTER TABLE jobs ADD COLUMN metadata_json TEXT;

CREATE TABLE IF NOT EXISTS account_member_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'UNKNOWN',
    last_error_code TEXT,
    last_error_message TEXT,
    last_checked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, member_id),
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT,
    FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_run_id TEXT NOT NULL UNIQUE,
    job_id INTEGER,
    group_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    availability TEXT NOT NULL DEFAULT 'UNKNOWN',
    processed INTEGER DEFAULT 0,
    inserted INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    unchanged INTEGER DEFAULT 0,
    duplicates INTEGER DEFAULT 0,
    excluded INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    error_code TEXT,
    error_message TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE SET NULL,
    FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT
);

-- Preserve Phase 2 target-state semantics while normalizing the Phase 5 name.
UPDATE member_target_states SET state='MEMBER' WHERE state='ALREADY_MEMBER';

CREATE INDEX IF NOT EXISTS idx_members_telegram_user_id ON members(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_members_username ON members(username);
CREATE INDEX IF NOT EXISTS idx_members_eligibility ON members(eligibility_status);
CREATE INDEX IF NOT EXISTS idx_members_consent ON members(consent_status);
CREATE INDEX IF NOT EXISTS idx_members_global_excluded ON members(global_excluded);
CREATE INDEX IF NOT EXISTS idx_member_sources_group ON member_sources(group_id);
CREATE INDEX IF NOT EXISTS idx_member_sources_status ON member_sources(group_id, source_status);
CREATE INDEX IF NOT EXISTS idx_member_sources_sync_run ON member_sources(group_id, last_seen_sync_run_id);
CREATE INDEX IF NOT EXISTS idx_member_target_target ON member_target_states(target_group_id);
CREATE INDEX IF NOT EXISTS idx_member_target_state ON member_target_states(state);
CREATE INDEX IF NOT EXISTS idx_member_exclusion_member ON member_exclusions(member_id);
CREATE INDEX IF NOT EXISTS idx_account_member_account ON account_member_states(account_id, state);
CREATE INDEX IF NOT EXISTS idx_member_sync_runs_group ON member_sync_runs(group_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_sync_runs_job ON member_sync_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_group_accounts_member_access ON group_accounts(group_id, member_list_availability);
"""


MIGRATION_008 = """
ALTER TABLE campaigns ADD COLUMN default_account_id INTEGER;
ALTER TABLE campaigns ADD COLUMN template_id INTEGER;
ALTER TABLE campaigns ADD COLUMN created_by TEXT;
ALTER TABLE campaigns ADD COLUMN started_at TEXT;
ALTER TABLE campaigns ADD COLUMN completed_at TEXT;
ALTER TABLE campaigns ADD COLUMN last_run_at TEXT;
ALTER TABLE campaigns ADD COLUMN next_run_at TEXT;
ALTER TABLE campaigns ADD COLUMN total_targets INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN success_count INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN failed_count INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN skipped_count INTEGER DEFAULT 0;

ALTER TABLE campaign_targets ADD COLUMN telegram_message_id TEXT;
ALTER TABLE campaign_targets ADD COLUMN telegram_scheduled_message_id TEXT;
ALTER TABLE campaign_targets ADD COLUMN scheduled_at TEXT;
ALTER TABLE campaign_targets ADD COLUMN attempt_count INTEGER DEFAULT 0;

ALTER TABLE campaign_messages ADD COLUMN media_name TEXT;
ALTER TABLE campaign_messages ADD COLUMN media_size INTEGER;
ALTER TABLE campaign_messages ADD COLUMN parse_mode TEXT DEFAULT 'PLAIN';
ALTER TABLE campaign_messages ADD COLUMN disable_link_preview INTEGER DEFAULT 0;

ALTER TABLE schedules ADD COLUMN occurrence_key TEXT;
ALTER TABLE schedules ADD COLUMN last_error_code TEXT;
ALTER TABLE schedules ADD COLUMN last_error_message TEXT;
ALTER TABLE schedules ADD COLUMN missed_policy TEXT DEFAULT 'ASK_ME';

CREATE TABLE IF NOT EXISTS campaign_target_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_target_id INTEGER NOT NULL,
    campaign_message_id INTEGER NOT NULL,
    telegram_message_id TEXT,
    telegram_scheduled_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    scheduled_at TEXT,
    sent_at TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_target_id, campaign_message_id),
    FOREIGN KEY(campaign_target_id) REFERENCES campaign_targets(id) ON DELETE CASCADE,
    FOREIGN KEY(campaign_message_id) REFERENCES campaign_messages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS campaign_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    campaign_target_id INTEGER NOT NULL,
    campaign_message_id INTEGER NOT NULL,
    occurrence_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    telegram_message_id TEXT,
    telegram_scheduled_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    scheduled_for TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_target_id, campaign_message_id, occurrence_key),
    FOREIGN KEY(campaign_id) REFERENCES campaigns(id) ON DELETE RESTRICT,
    FOREIGN KEY(campaign_target_id) REFERENCES campaign_targets(id) ON DELETE RESTRICT,
    FOREIGN KEY(campaign_message_id) REFERENCES campaign_messages(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS campaign_rendered_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id INTEGER NOT NULL UNIQUE,
    rendered_text TEXT,
    rendered_caption TEXT,
    media_reference TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(delivery_id) REFERENCES campaign_deliveries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS campaign_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    template_type TEXT NOT NULL DEFAULT 'TEXT',
    default_parse_mode TEXT DEFAULT 'PLAIN',
    default_schedule_type TEXT,
    default_timezone TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS campaign_template_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    message_type TEXT NOT NULL,
    body TEXT,
    caption TEXT,
    media_path TEXT,
    parse_mode TEXT DEFAULT 'PLAIN',
    disable_link_preview INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(template_id) REFERENCES campaign_templates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS template_groups (
    template_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY(template_id, group_id),
    FOREIGN KEY(template_id) REFERENCES campaign_templates(id) ON DELETE CASCADE,
    FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_campaign_type_status ON campaigns(campaign_type, status);
CREATE INDEX IF NOT EXISTS idx_campaign_next_run ON campaigns(next_run_at, status);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_status ON campaign_targets(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_targets_account ON campaign_targets(account_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_target_messages_target ON campaign_target_messages(campaign_target_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_campaign ON campaign_deliveries(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_occurrence ON campaign_deliveries(occurrence_key, status);
CREATE INDEX IF NOT EXISTS idx_campaign_templates_used ON campaign_templates(last_used_at);
CREATE INDEX IF NOT EXISTS idx_schedules_status_next ON schedules(status, is_enabled, next_run_at);
"""


MIGRATION_009 = """
ALTER TABLE jobs ADD COLUMN retry_classification TEXT DEFAULT 'UNKNOWN';
ALTER TABLE jobs ADD COLUMN interrupted_at TEXT;
ALTER TABLE jobs ADD COLUMN resource_type TEXT;
ALTER TABLE jobs ADD COLUMN resource_id TEXT;

ALTER TABLE logs ADD COLUMN campaign_id INTEGER;
ALTER TABLE logs ADD COLUMN job_id INTEGER;

ALTER TABLE alerts ADD COLUMN dedupe_key TEXT;
ALTER TABLE alerts ADD COLUMN source_type TEXT;
ALTER TABLE alerts ADD COLUMN source_id TEXT;
ALTER TABLE alerts ADD COLUMN first_seen_at TEXT;
ALTER TABLE alerts ADD COLUMN last_seen_at TEXT;
ALTER TABLE alerts ADD COLUMN occurrence_count INTEGER DEFAULT 1;
ALTER TABLE alerts ADD COLUMN requires_action INTEGER DEFAULT 0;
ALTER TABLE alerts ADD COLUMN action_type TEXT;
ALTER TABLE alerts ADD COLUMN status TEXT DEFAULT 'OPEN';

UPDATE alerts
SET first_seen_at = COALESCE(first_seen_at, created_at),
    last_seen_at = COALESCE(last_seen_at, created_at),
    status = CASE
        WHEN is_resolved = 1 THEN 'RESOLVED'
        WHEN is_read = 1 THEN 'ACKNOWLEDGED'
        ELSE 'OPEN'
    END
WHERE first_seen_at IS NULL OR last_seen_at IS NULL OR status IS NULL;

ALTER TABLE account_restrictions ADD COLUMN scope TEXT DEFAULT 'ACCOUNT';
ALTER TABLE account_restrictions ADD COLUMN state TEXT DEFAULT 'ACTIVE';
ALTER TABLE account_restrictions ADD COLUMN requires_action INTEGER DEFAULT 0;
ALTER TABLE account_restrictions ADD COLUMN last_rechecked_at TEXT;
ALTER TABLE account_restrictions ADD COLUMN resolution_note TEXT;

UPDATE account_restrictions
SET state = CASE WHEN is_active = 1 THEN 'ACTIVE' ELSE 'RESOLVED' END
WHERE state IS NULL OR state = '';

CREATE TABLE IF NOT EXISTS job_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    retry_classification TEXT NOT NULL DEFAULT 'UNKNOWN',
    created_at TEXT NOT NULL,
    UNIQUE(job_id, attempt_number),
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_dependencies (
    job_id INTEGER NOT NULL,
    depends_on_job_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(job_id, depends_on_job_id),
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(depends_on_job_id) REFERENCES jobs(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS recovery_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    event_type TEXT NOT NULL,
    trigger TEXT,
    action TEXT,
    result TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT 'LOCAL_USER',
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    description TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    component TEXT,
    resource_type TEXT,
    resource_id TEXT,
    message TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    manifest_path TEXT,
    schema_version INTEGER NOT NULL,
    app_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    checksum TEXT,
    created_at TEXT NOT NULL,
    verified_at TEXT,
    restored_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_campaign_created ON logs(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_job_created ON logs(job_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_retry ON jobs(retry_classification, status);
CREATE INDEX IF NOT EXISTS idx_job_attempts_job ON job_attempts(job_id, attempt_number DESC);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_dependency ON job_dependencies(depends_on_job_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe_open ON alerts(dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('OPEN','ACKNOWLEDGED');
CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON alerts(status, severity, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_restrictions_state_expires ON account_restrictions(state, expires_at);
CREATE INDEX IF NOT EXISTS idx_recovery_events_component ON recovery_events(component, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_resource ON audit_events(resource_type, resource_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_events_created ON operation_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backup_records_created ON backup_records(created_at DESC);
"""

MIGRATION_010 = """
CREATE TABLE IF NOT EXISTS license_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    plan TEXT,
    status TEXT NOT NULL DEFAULT 'UNLICENSED',
    license_key_masked TEXT,
    license_reference TEXT,
    expires_at TEXT,
    activated_at TEXT,
    last_validated_at TEXT,
    offline_grace_until TEXT,
    device_id TEXT,
    device_name TEXT,
    server_license_id TEXT,
    cached_license_payload TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS license_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    old_plan TEXT,
    new_plan TEXT,
    old_status TEXT,
    new_status TEXT,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS license_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_device_id TEXT,
    device_id TEXT NOT NULL,
    device_name TEXT NOT NULL,
    platform TEXT,
    is_current INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    activated_at TEXT,
    last_seen_at TEXT,
    last_synced_at TEXT,
    UNIQUE(device_id)
);

CREATE INDEX IF NOT EXISTS idx_license_history_created ON license_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_license_history_event ON license_history(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_license_devices_active ON license_devices(is_active, is_current);
"""

MIGRATION_011 = """
CREATE TABLE IF NOT EXISTS member_target_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    target_group_id INTEGER NOT NULL,
    account_id INTEGER,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    telegram_error_code TEXT,
    error_message TEXT,
    attempted_at TEXT NOT NULL,
    completed_at TEXT,
    job_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY(target_group_id) REFERENCES groups(id) ON DELETE RESTRICT,
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_member_target_actions_member ON member_target_actions(member_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_target_actions_target ON member_target_actions(target_group_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_target_actions_job ON member_target_actions(job_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_target_actions_status ON member_target_actions(status, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_target_member_target ON member_target_states(member_id, target_group_id);
CREATE INDEX IF NOT EXISTS idx_member_target_target_member ON member_target_states(target_group_id, member_id);
CREATE INDEX IF NOT EXISTS idx_member_sources_member_group ON member_sources(member_id, group_id);
"""


MIGRATION_012 = """
ALTER TABLE telegram_accounts ADD COLUMN enabled_for_operations INTEGER DEFAULT 1;
ALTER TABLE group_accounts ADD COLUMN can_approve_join_requests INTEGER;

CREATE TABLE IF NOT EXISTS target_invite_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_group_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    invite_link TEXT NOT NULL,
    name TEXT,
    request_needed INTEGER DEFAULT 1,
    expires_at TEXT,
    usage_limit INTEGER,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(target_group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_accounts_telegram_user_id ON telegram_accounts(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_username_ci ON telegram_accounts(username COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_accounts_operations_enabled ON telegram_accounts(enabled_for_operations, is_enabled);
CREATE INDEX IF NOT EXISTS idx_accounts_health_status ON telegram_accounts(health_status);
CREATE INDEX IF NOT EXISTS idx_accounts_connection_status ON telegram_accounts(connection_status);
CREATE INDEX IF NOT EXISTS idx_accounts_authorization_status ON telegram_accounts(authorization_status);
CREATE INDEX IF NOT EXISTS idx_accounts_restriction_type ON telegram_accounts(restriction_type);
CREATE INDEX IF NOT EXISTS idx_group_accounts_account_group ON group_accounts(account_id, group_id);
CREATE INDEX IF NOT EXISTS idx_group_accounts_group_account ON group_accounts(group_id, account_id);
CREATE INDEX IF NOT EXISTS idx_restrictions_account_active ON account_restrictions(account_id, is_active);
CREATE INDEX IF NOT EXISTS idx_jobs_account_status ON jobs(account_id, status);
CREATE INDEX IF NOT EXISTS idx_target_invite_links_target ON target_invite_links(target_group_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_target_invite_links_account ON target_invite_links(account_id, created_at DESC);
"""


MIGRATION_013 = """
CREATE TABLE IF NOT EXISTS account_safety_profiles (
    account_id INTEGER PRIMARY KEY,
    smart_mode INTEGER NOT NULL DEFAULT 1,
    safety_state TEXT NOT NULL DEFAULT 'NORMAL',
    invite_daily_limit INTEGER NOT NULL DEFAULT 20,
    post_daily_limit INTEGER NOT NULL DEFAULT 30,
    invite_spacing_seconds INTEGER NOT NULL DEFAULT 60,
    post_spacing_seconds INTEGER NOT NULL DEFAULT 30,
    cooldown_until TEXT,
    recovery_reason TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    success_streak INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account_operation_usage (
    account_id INTEGER NOT NULL,
    operation_date TEXT NOT NULL,
    invite_attempts INTEGER NOT NULL DEFAULT 0,
    invite_successes INTEGER NOT NULL DEFAULT 0,
    post_attempts INTEGER NOT NULL DEFAULT 0,
    post_successes INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_invite_at TEXT,
    last_post_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(account_id, operation_date),
    FOREIGN KEY(account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO account_safety_profiles(
    account_id, smart_mode, safety_state, invite_daily_limit, post_daily_limit,
    invite_spacing_seconds, post_spacing_seconds, created_at, updated_at
)
SELECT id, 1, 'NORMAL', 20, 30, 60, 30, created_at, updated_at
FROM telegram_accounts;

CREATE INDEX IF NOT EXISTS idx_account_safety_state ON account_safety_profiles(safety_state, smart_mode);
CREATE INDEX IF NOT EXISTS idx_account_safety_cooldown ON account_safety_profiles(cooldown_until);
CREATE INDEX IF NOT EXISTS idx_account_usage_date ON account_operation_usage(operation_date, account_id);
"""


MIGRATION_014 = """
ALTER TABLE telegram_accounts ADD COLUMN photo_cache_path TEXT;
ALTER TABLE members ADD COLUMN photo_cache_path TEXT;
"""
