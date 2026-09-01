from __future__ import annotations

from datetime import datetime, timedelta, timezone
from app.license.license_models import LicenseState, LicenseStatus
from app.license.plan_config import OFFLINE_GRACE_DAYS

CLOCK_SKEW_TOLERANCE_MINUTES = 5


def _dt(value:str|None):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except (TypeError,ValueError):return None

def _iso(value:datetime): return value.astimezone(timezone.utc).isoformat()

class OfflineLicensePolicy:
    def __init__(self,grace_days:int=OFFLINE_GRACE_DAYS):self.grace_days=max(0,int(grace_days))
    def on_server_unavailable(self,state:LicenseState,now:datetime|None=None)->LicenseState:
        now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);last=_dt(state.last_validated_at)
        if last and now < last-timedelta(minutes=CLOCK_SKEW_TOLERANCE_MINUTES):
            # A materially backwards local clock can incorrectly lengthen offline
            # grace. Require trusted online verification; never destroy data.
            state.status=LicenseStatus.VALIDATION_REQUIRED
            return state
        if str(state.status) in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE} and last and state.cached_license_payload:
            grace=_dt(state.offline_grace_until) or (last+timedelta(days=self.grace_days));state.offline_grace_until=_iso(grace)
            state.status=LicenseStatus.OFFLINE_GRACE if now<=grace else LicenseStatus.VALIDATION_REQUIRED
        else: state.status=LicenseStatus.VALIDATION_REQUIRED
        return state
    def normalize_cached(self,state:LicenseState,now:datetime|None=None)->LicenseState:
        now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);expires=_dt(state.expires_at)
        if expires and now>expires and str(state.status) not in {LicenseStatus.SUSPENDED,LicenseStatus.DEVICE_LIMIT}:
            state.status=LicenseStatus.EXPIRED
        elif str(state.status)==LicenseStatus.OFFLINE_GRACE:
            grace=_dt(state.offline_grace_until)
            if not grace or now>grace:state.status=LicenseStatus.VALIDATION_REQUIRED
        return state
