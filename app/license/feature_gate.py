from __future__ import annotations

from app.license.feature_keys import FeatureKey
from app.license.license_errors import FeatureLockedError
from app.license.license_models import LicenseStatus
from app.license.plan_config import ALWAYS_AVAILABLE_FEATURES, get_plan, required_plan_for


class FeatureGate:
    def __init__(self, license_service): self.license_service=license_service

    def has_feature(self, feature_key) -> bool:
        try: key=FeatureKey(str(feature_key))
        except ValueError: return False
        if key in ALWAYS_AVAILABLE_FEATURES: return True
        state=self.license_service.get_current_license(); status=str(state.status if state else LicenseStatus.UNLICENSED)
        if status not in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE}: return False
        claims=self.license_service.get_entitlement_claims()
        if not claims: return False
        return str(key) in {str(value) for value in (claims.get("features") or [])}

    def require_feature(self, feature_key) -> bool:
        if self.has_feature(feature_key): return True
        required=self.get_required_plan(feature_key); reason=self.get_lock_reason(feature_key)
        raise FeatureLockedError(str(feature_key),str(required) if required else None,reason)

    def get_required_plan(self, feature_key): return required_plan_for(feature_key)

    def get_lock_reason(self, feature_key) -> str:
        required=self.get_required_plan(feature_key); name=get_plan(required)['name'] if required and get_plan(required) else 'a paid plan'
        return f"This feature is available with {name} or a higher plan."
