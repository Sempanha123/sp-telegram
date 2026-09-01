from __future__ import annotations

from app.license.feature_keys import FeatureKey, LimitKey
from app.license.license_models import PlanKey

F = FeatureKey
L = LimitKey

STARTER_FEATURES = frozenset({
    F.ACCOUNT_MANAGER, F.ACCOUNT_SESSIONS, F.ACCOUNT_HEALTH, F.RESTRICTIONS,
    F.GROUP_MANAGER, F.GROUP_RESOLVER, F.GROUP_PERMISSIONS, F.GROUP_SYNC,
    F.MEMBER_POOL, F.MEMBER_SYNC, F.MEMBER_TAGS, F.BLACKLIST, F.TARGET_PREPARATION, F.INVITE_LINK,
    F.CSV_IMPORT, F.CSV_EXPORT, F.DASHBOARD, F.LOGS, F.BASIC_ALERTS,
    F.MANUAL_BACKUP, F.RESTORE, F.PRIVACY_MODE,
})

PRO_ADDITIONAL = frozenset({
    F.ADVANCED_MEMBER_FILTERS, F.TARGET_MEMBER_STATUS, F.TARGET_MEMBER_SYNC,
    F.CAMPAIGNS, F.MEDIA_POSTING, F.MULTI_MESSAGE, F.TEMPLATES, F.SEND_NOW,
    F.SCHEDULE_ONCE, F.CAMPAIGN_PREVIEW, F.CAMPAIGN_PREFLIGHT,
    F.ADVANCED_JOBS, F.ACCOUNT_MONITORING, F.GROUP_MONITORING, F.SAFE_RECOVERY,
    F.ADVANCED_ALERTS, F.APP_LOCK, F.ADVANCED_DIAGNOSTICS, F.BASIC_CAMPAIGN_ANALYTICS,
})

ULTIMATE_ADDITIONAL = frozenset({
    F.RECURRING_SCHEDULE, F.CONTENT_CALENDAR, F.ADVANCED_ANALYTICS,
    F.FULL_OPERATIONS, F.AUTO_BACKUP, F.SECURITY_AUDIT, F.SUPPORT_BUNDLE, F.DIRECT_MEMBER_INVITE,
})

PLAN_CONFIG = {
    PlanKey.STARTER: {
        "name": "SP Telegram Starter", "price_monthly": 8, "badge": None, "device_limit": 1,
        "limits": {L.MAX_ACCOUNTS: 5, L.MAX_SOURCE_GROUPS: 5, L.MAX_TARGET_GROUPS: 5,
                   L.MAX_MEMBER_POOL: 10_000, L.MAX_TEMPLATES: 0, L.MAX_DEVICES: 1},
        "features": STARTER_FEATURES,
        "tagline": "For core account, group and member management.",
        "card_highlights": ("Member Sync", "Blacklist", "Manual Backup"),
    },
    PlanKey.PRO: {
        "name": "SP Telegram Pro", "price_monthly": 10, "badge": "MOST POPULAR", "device_limit": 1,
        "limits": {L.MAX_ACCOUNTS: 15, L.MAX_SOURCE_GROUPS: 20, L.MAX_TARGET_GROUPS: 20,
                   L.MAX_MEMBER_POOL: 50_000, L.MAX_TEMPLATES: 10, L.MAX_DEVICES: 1},
        "features": STARTER_FEATURES | PRO_ADDITIONAL,
        "tagline": "For campaigns and advanced management.",
        "card_highlights": ("Campaigns", "Media Posting", "Schedule Once", "Advanced Jobs"),
    },
    PlanKey.ULTIMATE: {
        "name": "SP Telegram Ultimate", "price_monthly": 12, "badge": "FULL FEATURES", "device_limit": 2,
        "limits": {L.MAX_ACCOUNTS: None, L.MAX_SOURCE_GROUPS: None, L.MAX_TARGET_GROUPS: None,
                   L.MAX_MEMBER_POOL: None, L.MAX_TEMPLATES: None, L.MAX_DEVICES: 2},
        "features": frozenset(FeatureKey),
        "tagline": "Everything unlocked.",
        "card_highlights": ("Recurring Scheduling", "Content Calendar", "Full Analytics", "Automatic Backup", "Security Audit"),
    },
}

PLAN_ORDER = (PlanKey.STARTER, PlanKey.PRO, PlanKey.ULTIMATE)
OFFLINE_GRACE_DAYS = 3
VALIDATION_INTERVAL_HOURS = 24
EXPIRY_WARNING_DAYS = (7, 3, 1)

# Data-protection/safety operations remain available even if subscription state is invalid.
ALWAYS_AVAILABLE_FEATURES = frozenset({F.MANUAL_BACKUP, F.RESTORE, F.PRIVACY_MODE, F.LOGS, F.BASIC_ALERTS})


def get_plan(plan: str | PlanKey | None):
    if plan is None: return None
    try: return PLAN_CONFIG[PlanKey(str(plan))]
    except (ValueError, KeyError): return None


def required_plan_for(feature: FeatureKey | str) -> PlanKey | None:
    try: feature = FeatureKey(str(feature))
    except ValueError: return None
    for plan in PLAN_ORDER:
        if feature in PLAN_CONFIG[plan]["features"]:
            return plan
    return None


def format_plan_limit(plan: PlanKey, limit_key: LimitKey, *, compact: bool = False) -> str:
    value = PLAN_CONFIG[plan]["limits"][limit_key]
    if value is None:
        return "Unlimited"
    if compact and value >= 1_000:
        if value % 1_000 == 0:
            return f"{value // 1_000}K"
    return f"{int(value):,}"


def plan_has_feature(plan: PlanKey, feature: FeatureKey) -> bool:
    return feature in PLAN_CONFIG[plan]["features"]
