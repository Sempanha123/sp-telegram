from __future__ import annotations

from app.license.feature_keys import LimitKey
from app.license.license_models import LicenseStatus, LimitCheckResult, LimitState
from app.license.plan_config import get_plan

class PlanUsageService:
    def __init__(self,accounts,groups,members,templates,license_repository):self.accounts=accounts;self.groups=groups;self.members=members;self.templates=templates;self.licenses=license_repository
    def get_account_usage(self):return int(self.accounts.count_all())
    def get_source_group_usage(self):return int(self.groups.count("is_source=1"))
    def get_target_group_usage(self):return int(self.groups.count("is_target=1 OR is_managed=1"))
    def get_member_usage(self):return int(self.members.count_all())
    def get_template_usage(self):return int(self.templates.count())
    def get_device_usage(self):return int(self.licenses.active_device_count())
    def get_usage(self,key):
        key=LimitKey(str(key));return {LimitKey.MAX_ACCOUNTS:self.get_account_usage,LimitKey.MAX_SOURCE_GROUPS:self.get_source_group_usage,LimitKey.MAX_TARGET_GROUPS:self.get_target_group_usage,LimitKey.MAX_MEMBER_POOL:self.get_member_usage,LimitKey.MAX_TEMPLATES:self.get_template_usage,LimitKey.MAX_DEVICES:self.get_device_usage}[key]()

class LicenseLimitService:
    def __init__(self,license_service,usage_service):self.license_service=license_service;self.usage_service=usage_service
    def get_limit(self,key):
        state=self.license_service.get_current_license();claims=self.license_service.get_entitlement_claims()
        if not claims:return 0
        raw=(claims.get("limits") or {}).get(str(LimitKey(str(key))))
        return None if raw is None and str(LimitKey(str(key))) in (claims.get("limits") or {}) else (int(raw) if raw is not None else 0)
    def get_usage(self,key):return self.usage_service.get_usage(key)
    def get_remaining(self,key):
        limit=self.get_limit(key);current=self.get_usage(key);return None if limit is None else max(0,int(limit)-current)
    def check(self,key,count=1)->LimitCheckResult:
        key=LimitKey(str(key));current=self.get_usage(key);limit=self.get_limit(key);state=self.license_service.get_current_license();valid=bool(state and str(state.status) in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE})
        if not valid:return LimitCheckResult(False,current,limit,0,"LICENSE_REQUIRED","An active license is required before creating new licensed resources.",LimitState.OVER_LIMIT)
        if limit is None:return LimitCheckResult(True,current,None,None,state=LimitState.WITHIN_LIMIT)
        remaining=max(0,limit-current);allowed=int(count)<=remaining;level=LimitState.OVER_LIMIT if current>limit else LimitState.AT_LIMIT if current==limit else LimitState.WITHIN_LIMIT
        msg=None if allowed else f"Your current plan limit is {limit:,}. Current usage is {current:,}."
        return LimitCheckResult(allowed,current,limit,remaining,None if allowed else "PLAN_LIMIT_REACHED",msg,level)
    def can_add_account(self):return self.check(LimitKey.MAX_ACCOUNTS)
    def can_add_source_group(self):return self.check(LimitKey.MAX_SOURCE_GROUPS)
    def can_add_target_group(self):return self.check(LimitKey.MAX_TARGET_GROUPS)
    def can_add_member_records(self,count=1):return self.check(LimitKey.MAX_MEMBER_POOL,count)
    def can_create_template(self):return self.check(LimitKey.MAX_TEMPLATES)
    def can_activate_device(self):return self.check(LimitKey.MAX_DEVICES)
