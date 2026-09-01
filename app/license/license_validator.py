from __future__ import annotations

from typing import Callable

from app.license.license_models import LicenseApiResult, LicenseState, LicenseStatus, PlanKey
from app.license.license_errors import LicenseApiError
from app.license.entitlement_verifier import device_binding


class LicenseValidator:
    """Validate trusted server responses and cached signed entitlements.

    Production entitlements are accepted only when an Ed25519 verifier returns
    valid claims. No runtime mock-license bypass exists in the desktop client.
    """

    def __init__(self, cached_payload_verifier: Callable[[dict], dict | None] | None = None):
        self.cached_payload_verifier = cached_payload_verifier

    def validate_response(self, result: LicenseApiResult) -> LicenseApiResult:
        if not result.ok:
            return result
        if not result.trusted:
            raise LicenseApiError("The license response could not be trusted.", code="INVALID_LICENSE_RESPONSE")
        try:
            PlanKey(str(result.plan))
            LicenseStatus(str(result.status))
        except ValueError as exc:
            raise LicenseApiError("The license service returned an invalid entitlement.", code="INVALID_LICENSE_RESPONSE") from exc
        if not result.cached_payload or self.cached_payload_verifier is None:
            raise LicenseApiError("The license response did not contain a verifiable signed entitlement.", code="INVALID_LICENSE_RESPONSE")
        claims = self.cached_payload_verifier(result.cached_payload)
        if not claims:
            raise LicenseApiError("The signed license entitlement could not be verified.", code="INVALID_LICENSE_RESPONSE")
        return result

    def cached_state_is_trusted(self, state: LicenseState) -> bool:
        payload = state.cached_license_payload if isinstance(state.cached_license_payload, dict) else None
        if not payload or self.cached_payload_verifier is None:
            return False
        try:
            claims = self.cached_payload_verifier(payload)
        except Exception:
            return False
        if not isinstance(claims, dict):
            return False
        try:
            plan = PlanKey(str(claims.get("plan")))
            status = LicenseStatus(str(claims.get("status")))
        except ValueError:
            return False
        if str(plan) != str(state.plan):
            return False
        if state.status == LicenseStatus.OFFLINE_GRACE:
            if status not in {LicenseStatus.ACTIVE, LicenseStatus.TRIAL, LicenseStatus.OFFLINE_GRACE}:
                return False
        elif status != state.status:
            return False
        if state.expires_at and claims.get("expires_at") and str(claims.get("expires_at")) != str(state.expires_at):
            return False
        if state.device_id and str(claims.get("device_id") or "") != device_binding(state.device_id):
            return False
        return True

    def entitlement_matches_device(self, payload: dict | None, device_id: str | None) -> bool:
        if not payload or not device_id or self.cached_payload_verifier is None:
            return False
        try:
            claims=self.cached_payload_verifier(payload)
        except Exception:
            return False
        return isinstance(claims,dict) and str(claims.get("device_id") or "")==device_binding(device_id)
