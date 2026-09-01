from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from app.license.license_api import LicenseApi
from app.license.license_errors import LicenseApiError
from app.license.license_models import LicenseDevice, LicenseState, LicenseStatus, LicenseSummary
from app.license.license_validator import LicenseValidator
from app.license.offline_license import OfflineLicensePolicy
from app.license.plan_config import VALIDATION_INTERVAL_HOURS, EXPIRY_WARNING_DAYS, get_plan
from app.utils.formatters import utc_now_iso

class LicenseService:
    def __init__(self,repository,api:LicenseApi,device_manager,validator=None,offline_policy=None,usage_service=None,audit_service=None,alert_manager=None):
        self.repository=repository;self.api=api;self.device_manager=device_manager
        if validator is None:
            verifier=getattr(getattr(api,"verifier",None),"verify",None)
            validator=LicenseValidator(cached_payload_verifier=verifier)
        self.validator=validator;self.offline=offline_policy or OfflineLicensePolicy();self.usage_service=usage_service;self.audit=audit_service;self.alerts=alert_manager;self._state=None
    def initialize(self):
        existing=self.repository.get_state();state=self.offline.normalize_cached(existing or LicenseState())
        if existing and str(state.status) in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE} and not self.validator.cached_state_is_trusted(state):
            old_status=state.status;state.status=LicenseStatus.VALIDATION_REQUIRED
            self.repository.add_history("VALIDATION_FAILED",state.plan,state.plan,old_status,state.status,"Cached license requires trusted online/signature verification.")
        self._state=self.repository.save_state(state)
        return self._state
    @staticmethod
    def mask_license_key(key:str)->str:
        clean=''.join(ch for ch in (key or '').strip().upper() if not ch.isspace());tail=clean[-4:] if len(clean)>=4 else clean
        prefix='SP-' if clean.startswith('SP-') else ''
        return f"{prefix}••••-••••-••••-••••-{tail}" if tail else "••••"
    @staticmethod
    def _reference_from_key(key:str)->str:return hashlib.sha256(key.strip().upper().encode('utf-8')).hexdigest()[:24]
    def get_entitlement_claims(self):
        state=self.get_current_license()
        payload=state.cached_license_payload if isinstance(state.cached_license_payload,dict) else None
        if not payload or self.validator.cached_payload_verifier is None:
            return None
        try:
            claims=self.validator.cached_payload_verifier(payload)
        except Exception:
            return None
        return claims if isinstance(claims,dict) else None

    def get_current_license(self):
        if self._state is None:self.initialize()
        return self._state
    def get_current_plan(self):
        state=self.get_current_license();return get_plan(state.plan)
    def get_status(self):return str(self.get_current_license().status)
    def has_valid_license(self):return self.get_status() in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE}
    def needs_online_validation(self,now=None):
        state=self.get_current_license()
        if not state.license_reference:return False
        if str(state.status) in {LicenseStatus.EXPIRED,LicenseStatus.SUSPENDED,LicenseStatus.DEVICE_LIMIT,LicenseStatus.INVALID}:return False
        if not state.last_validated_at:return True
        now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        try:last=datetime.fromisoformat(str(state.last_validated_at).replace("Z","+00:00")).astimezone(timezone.utc)
        except (TypeError,ValueError):return True
        return (now-last).total_seconds()>=VALIDATION_INTERVAL_HOURS*3600
    async def activate(self,license_key:str,device_name:str|None=None):
        clean=(license_key or '').strip()
        if len(clean)<8:raise LicenseApiError("Enter a valid license key.",code="INVALID_LICENSE_KEY")
        device=self.device_manager.metadata(device_name);old=self.get_current_license();result=self.validator.validate_response(await self.api.activate_license(clean,device))
        if not result.ok:
            code=result.error_code or "UNKNOWN"
            status_map={
                "DEVICE_LIMIT_REACHED":LicenseStatus.DEVICE_LIMIT,
                "LICENSE_EXPIRED":LicenseStatus.EXPIRED,
                "LICENSE_SUSPENDED":LicenseStatus.SUSPENDED,
                "INVALID_LICENSE_KEY":LicenseStatus.INVALID,
                "VALIDATION_REQUIRED":LicenseStatus.VALIDATION_REQUIRED,
            }
            next_status=status_map.get(code, old.status if old else LicenseStatus.UNLICENSED)
            failed=LicenseState(plan=old.plan if old else None,status=next_status,device_id=device['device_id'],device_name=device['device_name'])
            self._state=self.repository.save_state(failed)
            self.repository.add_history("VALIDATION_FAILED",getattr(old,"plan",None),failed.plan,getattr(old,"status",None),failed.status,code)
            if self.audit:self.audit.record("LICENSE_VALIDATION_FAILED",resource_type="LICENSE",resource_id="local",description=f"License activation failed: {code}.",before={"plan":getattr(old,"plan",None),"status":getattr(old,"status",None)},after={"plan":failed.plan,"status":failed.status})
            self._raise_state_alerts(failed)
            raise LicenseApiError(result.message or "Could not activate this license.",code=code)
        state=self._state_from_result(result,device,masked_key=self.mask_license_key(clean),fallback_reference=self._reference_from_key(clean))
        self._commit(old,state,"ACTIVATED","License activated.");self._save_devices(result.devices,device['device_id']);return state
    async def refresh(self):
        old=self.get_current_license();device=self.device_manager.metadata(old.device_name)
        if not old.license_reference:raise LicenseApiError("Activate a license before refreshing it.",code="VALIDATION_REQUIRED")
        try:
            result=self.validator.validate_response(await self.api.refresh_license(old.license_reference,device))
            if not result.ok:
                code=result.error_code or "UNKNOWN"
                status_map={
                    "DEVICE_LIMIT_REACHED":LicenseStatus.DEVICE_LIMIT,
                    "LICENSE_EXPIRED":LicenseStatus.EXPIRED,
                    "LICENSE_SUSPENDED":LicenseStatus.SUSPENDED,
                    "INVALID_LICENSE_KEY":LicenseStatus.INVALID,
                    "VALIDATION_REQUIRED":LicenseStatus.VALIDATION_REQUIRED,
                }
                if code in status_map:
                    new=LicenseState(**{**old.__dict__,"status":status_map[code],"updated_at":utc_now_iso()})
                    self._commit(old,new,"VALIDATION_FAILED",code)
                raise LicenseApiError(result.message or "Could not verify license.",code=code)
            state=self._state_from_result(result,device,masked_key=old.license_key_masked,fallback_reference=old.license_reference)
            self._commit(old,state,"REFRESHED","License refreshed.");self._save_devices(result.devices,device['device_id']);return state
        except LicenseApiError as exc:
            if exc.code in {"NETWORK_UNAVAILABLE","SERVER_UNAVAILABLE"}:
                state=self.offline.on_server_unavailable(old);self._commit(old,state,"OFFLINE_GRACE_STARTED" if str(state.status)==LicenseStatus.OFFLINE_GRACE else "VALIDATION_FAILED","Online license verification is unavailable.");return state
            self.repository.add_history("VALIDATION_FAILED",old.plan,old.plan,old.status,old.status,exc.code);raise
    def validate_cached_license(self):
        old=self.get_current_license();new=self.offline.normalize_cached(old);self._state=self.repository.save_state(new);return self._state
    async def get_devices(self):
        state=self.get_current_license()
        if not state.license_reference:return self.repository.get_devices()
        result=await self.api.get_license_devices(state.license_reference,state.device_id)
        if result.ok:self._save_devices(result.devices,state.device_id)
        return self.repository.get_devices()
    async def deactivate_device(self,device_id:str):
        state=self.get_current_license()
        if not state.license_reference:return False
        result=await self.api.deactivate_device(state.license_reference,device_id)
        if not result.ok:raise LicenseApiError(result.message or "Could not deactivate device.",code=result.error_code or "UNKNOWN")
        cached=next((d for d in self.repository.get_devices() if d.device_id==device_id),None)
        current=bool((state.device_id and device_id==state.device_id) or (cached and cached.is_current))
        self.repository.add_history("DEVICE_DEACTIVATED",state.plan,state.plan,state.status,LicenseStatus.VALIDATION_REQUIRED if current else state.status,"License device deactivated.")
        if self.audit:self.audit.record("LICENSE_DEVICE_DEACTIVATED",resource_type="LICENSE_DEVICE",resource_id=self.device_manager.mask_device_id(device_id),description="License device deactivated.")
        if current:
            state.status=LicenseStatus.VALIDATION_REQUIRED;self._state=self.repository.save_state(state)
        await self.get_devices()
        return True
    async def deactivate_current_device(self):
        state=self.get_current_license();return await self.deactivate_device(state.device_id) if state.device_id else False
    def get_license_summary(self):
        state=self.get_current_license();plan=get_plan(state.plan);usage={};claims=self.get_entitlement_claims() or {};signed_limits=claims.get("limits") or {}
        if self.usage_service and plan:
            from app.license.feature_keys import LimitKey
            for key in LimitKey:
                current=self.usage_service.get_usage(key);raw=signed_limits.get(str(key));limit=None if str(key) in signed_limits and raw is None else (int(raw) if raw is not None else 0);usage[str(key)]={"current":current,"limit":limit,"remaining":None if limit is None else max(0,limit-current)}
        days=None
        if state.expires_at:
            try:days=max(0,(datetime.fromisoformat(state.expires_at.replace('Z','+00:00')).astimezone(timezone.utc)-datetime.now(timezone.utc)).days)
            except (TypeError,ValueError):pass
        device_limit=signed_limits.get("MAX_DEVICES") if claims else None
        return LicenseSummary(state,plan['name'] if plan else 'No Active License',plan['price_monthly'] if plan else None,device_limit,days,usage)
    def _state_from_result(self,result,device,masked_key=None,fallback_reference=None):
        if not self.validator.entitlement_matches_device(result.cached_payload,device.get('device_id')):
            raise LicenseApiError("The license entitlement does not match this device.",code="INVALID_LICENSE_RESPONSE")
        now=utc_now_iso();return LicenseState(plan=str(result.plan),status=str(result.status),license_key_masked=masked_key,license_reference=result.license_reference or fallback_reference,expires_at=result.expires_at,activated_at=(self._state.activated_at if self._state else None) or now,last_validated_at=now,offline_grace_until=None,device_id=device['device_id'],device_name=device['device_name'],server_license_id=result.server_license_id,cached_license_payload=result.cached_payload)
    def _commit(self,old,new,event,message):
        old_plan=getattr(old,"plan",None);old_status=getattr(old,"status",None)
        self._state=self.repository.save_state(new);self.repository.add_history(event,old_plan,new.plan,old_status,new.status,message)
        if old_plan and new.plan and str(old_plan)!=str(new.plan):
            self.repository.add_history("PLAN_CHANGED",old_plan,new.plan,old_status,new.status,"Trusted license plan changed.")
        transition_event={LicenseStatus.EXPIRED:"EXPIRED",LicenseStatus.SUSPENDED:"SUSPENDED",LicenseStatus.OFFLINE_GRACE:"OFFLINE_GRACE_STARTED",LicenseStatus.VALIDATION_REQUIRED:"VALIDATION_FAILED"}.get(str(new.status))
        if transition_event and str(old_status)!=str(new.status) and transition_event!=event:
            self.repository.add_history(transition_event,old_plan,new.plan,old_status,new.status,f"License status changed to {new.status}.")
        if self.audit:
            before={"plan":old_plan,"status":old_status};after={"plan":new.plan,"status":new.status}
            self.audit.record(f"LICENSE_{event}",resource_type="LICENSE",resource_id=new.server_license_id or "local",description=message,before=before,after=after)
            if old_plan and new.plan and str(old_plan)!=str(new.plan):self.audit.record("LICENSE_PLAN_CHANGED",resource_type="LICENSE",resource_id=new.server_license_id or "local",description="Trusted license plan changed.",before=before,after=after)
        self._raise_state_alerts(new)
        return self._state
    def _raise_state_alerts(self,state):
        if not self.alerts:return
        status=str(state.status)
        if status==LicenseStatus.EXPIRED:self.alerts.raise_alert("WARNING","LICENSE_EXPIRED","License expired","Your local data is preserved. Renew or refresh the license to restore licensed creation/outgoing features.",dedupe_key="license:expired",source_type="LICENSE",requires_action=True,action_type="OPEN_LICENSE")
        elif status==LicenseStatus.VALIDATION_REQUIRED:self.alerts.raise_alert("WARNING","LICENSE_VALIDATION","Online license verification required","Connect to the internet and refresh the license. Existing data remains available.",dedupe_key="license:validation-required",source_type="LICENSE",requires_action=True,action_type="OPEN_LICENSE")
        elif status==LicenseStatus.DEVICE_LIMIT:self.alerts.raise_alert("WARNING","LICENSE_DEVICE_LIMIT","License device limit reached","Manage an existing license device before activating this computer.",dedupe_key="license:device-limit",source_type="LICENSE",requires_action=True,action_type="MANAGE_LICENSE_DEVICES")
        elif status==LicenseStatus.SUSPENDED:self.alerts.raise_alert("CRITICAL","LICENSE_SUSPENDED","License suspended","This license currently requires review. Your local data remains preserved.",dedupe_key="license:suspended",source_type="LICENSE",requires_action=True,action_type="OPEN_LICENSE")
        if state.expires_at and status in {LicenseStatus.ACTIVE,LicenseStatus.TRIAL,LicenseStatus.OFFLINE_GRACE}:
            try:
                days=max(0,(datetime.fromisoformat(str(state.expires_at).replace("Z","+00:00")).astimezone(timezone.utc)-datetime.now(timezone.utc)).days)
                if days in EXPIRY_WARNING_DAYS:self.alerts.raise_alert("WARNING","LICENSE_EXPIRING",f"License expires in {days} day{'s' if days!=1 else ''}","Open License to review subscription status.",dedupe_key=f"license:expiring:{days}",source_type="LICENSE",requires_action=True,action_type="OPEN_LICENSE")
            except (TypeError,ValueError):pass
    def _save_devices(self,raw,current_device_id):
        devices=[]
        for d in raw or []:
            identifier=('server:'+str(d.get('server_device_id'))) if d.get('server_device_id') else str(d.get('device_id') or '')
            if not identifier:continue
            is_current=bool(d.get('is_current')) or bool(current_device_id and d.get('device_id')==current_device_id)
            devices.append(LicenseDevice(d.get('server_device_id'),identifier,d.get('device_name') or 'Device',d.get('platform') or 'Unknown',is_current,bool(d.get('is_active',True)),d.get('activated_at'),d.get('last_seen_at'),utc_now_iso()))
        self.repository.replace_devices(devices)
