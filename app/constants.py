from __future__ import annotations

import os

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility
    from enum import Enum

    class StrEnum(str, Enum):
        """Small compatibility shim for Python versions before 3.11."""

        def __str__(self) -> str:
            return str(self.value)


APP_NAME = "SP Telegram"
APP_SHORT_NAME = "SP"
APP_VERSION = "0.8.3-prod"
APP_CHANNEL = "production"
# Production source never enables runtime demo/test seed behavior. Automated tests
# inject their own fixtures/adapters and do not depend on these runtime flags.
APP_DEMO_MODE = False
TELEGRAM_TEST_MODE = False
MOCK_LICENSE = False
DEVELOPER_MENU = False
DEFAULT_WINDOW_SIZE = (1440, 900)
MIN_WINDOW_SIZE = (1180, 720)


class AccountConnectionStatus(StrEnum):
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    ERROR = "Error"
    OFFLINE = "Offline"  # legacy Phase 2 value

class AccountHealthStatus(StrEnum):
    HEALTHY = "Healthy"
    IDLE = "Idle"
    WARNING = "Warning"
    COOLDOWN = "Cooldown"
    RESTRICTED = "Restricted"
    OFFLINE = "Offline"
    LOGIN_REQUIRED = "Login Required"
    SESSION_INVALID = "Session Invalid"
    DISABLED = "Disabled"
    UNKNOWN = "Unknown"


class RestrictionType(StrEnum):
    NONE = "None"
    FLOOD_WAIT = "Flood Wait"
    INVITE_RESTRICTED = "Invite Restricted"
    POSTING_RESTRICTED = "Posting Restricted"
    SESSION_INVALID = "Session Invalid"
    AUTH_REQUIRED = "Authentication Required"
    UNKNOWN = "Unknown Restriction"


class CapabilityType(StrEnum):
    CONNECT = "CONNECT"
    COLLECT = "COLLECT"
    INVITE = "INVITE"
    POST = "POST"
    SCHEDULE = "SCHEDULE"
    MANAGE = "MANAGE"


class GroupType(StrEnum):
    GROUP = "Group"
    SUPERGROUP = "Supergroup"
    CHANNEL = "Channel"


class GroupRole(StrEnum):
    MEMBER = "Member"
    ADMIN = "Admin"
    OWNER = "Owner"


class MemberEligibilityStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    ALREADY_MEMBER = "ALREADY_MEMBER"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    INVALID_USER = "INVALID_USER"
    DELETED_ACCOUNT = "DELETED_ACCOUNT"
    BOT = "BOT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ConsentStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    OPTED_IN = "OPTED_IN"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    REVOKED = "REVOKED"


class MemberExclusionType(StrEnum):
    GLOBAL_BLACKLIST = "GLOBAL_BLACKLIST"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    TARGET_EXCLUSION = "TARGET_EXCLUSION"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    INVALID_USER = "INVALID_USER"
    DELETED_ACCOUNT = "DELETED_ACCOUNT"
    BOT = "BOT"
    MANUAL_EXCLUSION = "MANUAL_EXCLUSION"


class MemberListAvailability(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    HIDDEN = "HIDDEN"
    UNAVAILABLE = "UNAVAILABLE"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNKNOWN = "UNKNOWN"


class MemberTargetState(StrEnum):
    MEMBER = "MEMBER"
    NOT_MEMBER = "NOT_MEMBER"
    UNKNOWN = "UNKNOWN"
    ACCESS_DENIED = "ACCESS_DENIED"
    NOT_RESOLVABLE = "NOT_RESOLVABLE"
    ERROR = "ERROR"


class CampaignType(StrEnum):
    SINGLE_POST = "SINGLE_POST"
    MULTI_MESSAGE = "MULTI_MESSAGE"
    SCHEDULED_POST = "SCHEDULED_POST"
    RECURRING_POST = "RECURRING_POST"


class CampaignMessageType(StrEnum):
    TEXT = "TEXT"
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    MEDIA_WITH_CAPTION = "MEDIA_WITH_CAPTION"


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class CampaignTargetStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"


class ScheduleStatus(StrEnum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"
    CANCELLED_EXTERNALLY = "CANCELLED_EXTERNALLY"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class JobStatus(StrEnum):
    QUEUED = "Queued"
    VALIDATING = "Validating"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"
    STOPPED = "Stopped"
    STOPPING = "Stopping"
    PARTIAL_SUCCESS = "Partial Success"
    CANCELLED = "Cancelled"
    WAITING = "Waiting"
    INTERRUPTED = "Interrupted"
    RECONCILE_REQUIRED = "Reconcile Required"


class AlertSeverity(StrEnum):
    INFO = "Info"
    SUCCESS = "Success"
    WARNING = "Warning"
    ERROR = "Error"
    CRITICAL = "Critical"


class OperationalState(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"
    MAINTENANCE = "MAINTENANCE"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    ERROR = "ERROR"


class WorkerState(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    UNRESPONSIVE = "UNRESPONSIVE"


class RetryClassification(StrEnum):
    SAFE_RETRY = "SAFE_RETRY"
    WAIT_AND_RETRY = "WAIT_AND_RETRY"
    DO_NOT_RETRY = "DO_NOT_RETRY"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    UNKNOWN = "UNKNOWN"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    MUTED = "MUTED"


class RestrictionScope(StrEnum):
    ACCOUNT = "ACCOUNT"
    INVITE = "INVITE"
    POST = "POST"
    GROUP = "GROUP"
    SESSION = "SESSION"
    UNKNOWN = "UNKNOWN"


class RestrictionState(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PENDING_RECHECK = "PENDING_RECHECK"


NAV_ITEMS = [
    ("dashboard", "Dashboard", "btn_nav_dashboard"),
    ("flow_studio", "Add Member", "btn_nav_flow_studio"),
    ("operations", "System Monitor", "btn_nav_operations"),
    ("accounts", "Accounts", "btn_nav_accounts"),
    ("account_pool", "Account Pool", "btn_nav_account_pool"),
    ("account_health", "Health Center", "btn_nav_account_health"),
    ("restrictions", "Restrictions", "btn_nav_restrictions"),
    ("sessions", "Sessions", "btn_nav_sessions"),
    ("groups", "Groups", "btn_nav_groups"),
    ("source_groups", "Source Groups", "btn_nav_source_groups"),
    ("target_groups", "Target Groups", "btn_nav_target_groups"),
    ("members", "Member Pool", "btn_nav_members"),
    ("collector", "Collector", "btn_nav_collector"),
    ("blacklist", "Safety List", "btn_nav_blacklist"),
    ("campaigns", "Campaigns", "btn_nav_campaigns"),
    ("scheduler", "Scheduler", "btn_nav_scheduler"),
    ("templates", "Templates", "btn_nav_templates"),
    ("jobs", "Jobs", "btn_nav_jobs"),
    ("analytics", "Analytics", "btn_nav_analytics"),
    ("alerts", "Alerts", "btn_nav_alerts"),
    ("logs", "Logs", "btn_nav_logs"),
    ("license", "Plan & License", "btn_nav_license"),
    ("settings", "Settings", "btn_nav_settings"),
]
