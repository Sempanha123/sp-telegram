from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Plan

PLANS = {
    "STARTER": dict(name="SP Telegram Starter", price_monthly=8, device_limit=1, max_accounts=5, max_source_groups=5, max_target_groups=5, max_member_pool=10_000, max_templates=0),
    "PRO": dict(name="SP Telegram Pro", price_monthly=10, device_limit=1, max_accounts=15, max_source_groups=20, max_target_groups=20, max_member_pool=50_000, max_templates=10),
    "ULTIMATE": dict(name="SP Telegram Ultimate", price_monthly=12, device_limit=2, max_accounts=None, max_source_groups=None, max_target_groups=None, max_member_pool=None, max_templates=None),
}

# These strings mirror the desktop feature-key enum and are signed by the server.
STARTER = {
    "FEATURE_ACCOUNT_MANAGER","FEATURE_ACCOUNT_SESSIONS","FEATURE_ACCOUNT_HEALTH","FEATURE_RESTRICTIONS","FEATURE_GROUP_MANAGER","FEATURE_GROUP_RESOLVER","FEATURE_GROUP_PERMISSIONS","FEATURE_GROUP_SYNC",
    "FEATURE_MEMBER_POOL","FEATURE_MEMBER_SYNC","FEATURE_MEMBER_TAGS","FEATURE_BLACKLIST","FEATURE_TARGET_PREPARATION","FEATURE_INVITE_LINK","FEATURE_CSV_IMPORT","FEATURE_CSV_EXPORT","FEATURE_DASHBOARD","FEATURE_LOGS","FEATURE_BASIC_ALERTS","FEATURE_MANUAL_BACKUP","FEATURE_RESTORE","FEATURE_PRIVACY_MODE",
}
PRO = STARTER | {
    "FEATURE_ADVANCED_MEMBER_FILTERS","FEATURE_TARGET_MEMBER_STATUS","FEATURE_TARGET_MEMBER_SYNC","FEATURE_CAMPAIGNS","FEATURE_MEDIA_POSTING","FEATURE_MULTI_MESSAGE","FEATURE_TEMPLATES","FEATURE_SEND_NOW","FEATURE_SCHEDULE_ONCE","FEATURE_CAMPAIGN_PREVIEW","FEATURE_CAMPAIGN_PREFLIGHT",
    "FEATURE_ADVANCED_JOBS","FEATURE_ACCOUNT_MONITORING","FEATURE_GROUP_MONITORING","FEATURE_SAFE_RECOVERY","FEATURE_ADVANCED_ALERTS","FEATURE_APP_LOCK","FEATURE_ADVANCED_DIAGNOSTICS","FEATURE_BASIC_CAMPAIGN_ANALYTICS",
}
ULTIMATE = PRO | {"FEATURE_RECURRING_SCHEDULE","FEATURE_CONTENT_CALENDAR","FEATURE_ADVANCED_ANALYTICS","FEATURE_FULL_OPERATIONS","FEATURE_AUTO_BACKUP","FEATURE_SECURITY_AUDIT","FEATURE_SUPPORT_BUNDLE","FEATURE_DIRECT_MEMBER_INVITE"}
FEATURES = {"STARTER": STARTER, "PRO": PRO, "ULTIMATE": ULTIMATE}


def seed_plans(db: Session) -> None:
    for code, values in PLANS.items():
        plan = db.scalar(select(Plan).where(Plan.code == code))
        payload = {**values, "features_json": sorted(FEATURES[code]), "is_active": True}
        if plan is None:
            db.add(Plan(code=code, **payload))
        else:
            for key, value in payload.items(): setattr(plan, key, value)
    db.commit()
