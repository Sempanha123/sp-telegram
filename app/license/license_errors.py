from __future__ import annotations

class LicenseError(RuntimeError):
    code = "UNKNOWN"
    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message); self.code = code or self.code

class FeatureLockedError(LicenseError):
    code = "FEATURE_LOCKED"
    def __init__(self, feature: str, required_plan: str | None, message: str):
        super().__init__(message, code=self.code); self.feature=feature; self.required_plan=required_plan

class LicenseLimitError(LicenseError):
    code = "PLAN_LIMIT_REACHED"

class LicenseApiError(LicenseError):
    pass
