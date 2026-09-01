from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import License, LicenseDevice
from ..repositories import LicenseRepository
from ..security.tokens import generate_license_key, hash_device_id, hash_license_key, prefix_for_key, public_device_binding, sign_entitlement


def utcnow(): return datetime.now(timezone.utc)

def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def iso(value):
    value=_utc(value)
    return value.isoformat() if value else None


class LicenseDomainError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message); self.code=code; self.status_code=status_code


class LicenseService:
    def __init__(self, db: Session): self.db=db; self.repo=LicenseRepository(db)

    def _effective_status(self, lic: License) -> str:
        now=utcnow()
        if lic.revoked_at or lic.status == "REVOKED": return "INVALID"
        if lic.suspended_at or lic.status == "SUSPENDED": return "SUSPENDED"
        if _utc(lic.expires_at) <= now: return "EXPIRED"
        return "ACTIVE"

    def _limits(self, plan) -> dict:
        return {
            "MAX_ACCOUNTS": plan.max_accounts,
            "MAX_SOURCE_GROUPS": plan.max_source_groups,
            "MAX_TARGET_GROUPS": plan.max_target_groups,
            "MAX_MEMBER_POOL": plan.max_member_pool,
            "MAX_TEMPLATES": plan.max_templates,
            "MAX_DEVICES": plan.device_limit,
        }

    def _device_view(self, d: LicenseDevice, current_hash: str | None = None) -> dict:
        return {
            "server_device_id": d.id,
            "device_id": d.device_id_hash,
            "device_name": d.device_name,
            "platform": d.platform,
            "is_current": bool(current_hash and d.device_id_hash == current_hash),
            "is_active": d.is_active,
            "activated_at": iso(d.activated_at),
            "last_seen_at": iso(d.last_seen_at),
        }

    def _response(self, lic: License, device_hash: str, entitlement_device_id: str) -> dict:
        status=self._effective_status(lic); plan=lic.plan
        if status == "INVALID": raise LicenseDomainError("INVALID_LICENSE_KEY", "This license is not active.", status_code=403)
        claims={
            "license_id": lic.id,
            "plan": plan.code,
            "status": status,
            "device_id": entitlement_device_id,
            "features": list(plan.features_json or []),
            "limits": self._limits(plan),
            "issued_at": iso(utcnow()),
            "expires_at": iso(lic.expires_at),
            "offline_grace_until": iso(min(_utc(lic.expires_at), utcnow()+timedelta(days=settings.offline_grace_days))),
            "token_version": 1,
        }
        return {
            "ok": True,
            "plan": plan.code,
            "status": status,
            "expires_at": iso(lic.expires_at),
            "license_reference": lic.id,
            "server_license_id": lic.id,
            "devices": [self._device_view(d, device_hash) for d in self.repo.active_devices(lic.id)],
            "signed_entitlement": sign_entitlement(claims),
        }

    def activate(self, license_key: str, device: dict) -> dict:
        key_hash=hash_license_key(license_key); lic=self.repo.get_license_by_key_hash(key_hash)
        if lic is None:
            self.repo.add_event(None,"VALIDATION_FAILED","Invalid activation key."); self.db.commit()
            raise LicenseDomainError("INVALID_LICENSE_KEY","This license key is not valid.",status_code=404)
        device_hash=hash_device_id(device["device_id"]); status=self._effective_status(lic)
        if status != "ACTIVE": return self._response(lic,device_hash,public_device_binding(device["device_id"]))
        row=self.repo.device_by_hash(lic.id,device_hash)
        if row is None or not row.is_active:
            active=self.repo.active_devices(lic.id)
            if len(active) >= int(lic.plan.device_limit):
                self.repo.add_event(lic.id,"VALIDATION_FAILED","Device limit reached.",{"device_limit":lic.plan.device_limit}); self.db.commit()
                raise LicenseDomainError("DEVICE_LIMIT_REACHED",f"{lic.plan.name} supports {lic.plan.device_limit} activated device{'s' if lic.plan.device_limit != 1 else ''}.",status_code=409)
            if row is None:
                row=LicenseDevice(license_id=lic.id,device_id_hash=device_hash,device_name=device["device_name"],platform=device["platform"],app_version=device["application_version"])
                self.db.add(row)
            else:
                row.is_active=True; row.deactivated_at=None; row.activated_at=utcnow()
            self.repo.add_event(lic.id,"DEVICE_ACTIVATED","License device activated.",{"server_device_id":row.id})
        row.device_name=device["device_name"]; row.platform=device["platform"]; row.app_version=device["application_version"]; row.last_seen_at=utcnow()
        self.repo.add_event(lic.id,"ACTIVATED","License activated on a device."); self.db.commit(); self.db.refresh(lic)
        return self._response(lic,device_hash,public_device_binding(device["device_id"]))

    def validate(self, license_reference: str, device: dict) -> dict:
        lic=self.repo.get_license(license_reference)
        if lic is None: raise LicenseDomainError("INVALID_LICENSE_KEY","License reference was not found.",status_code=404)
        device_hash=hash_device_id(device["device_id"]); row=self.repo.device_by_hash(lic.id,device_hash)
        if row is None or not row.is_active:
            raise LicenseDomainError("VALIDATION_REQUIRED","This device is not active for the license.",status_code=403)
        row.device_name=device["device_name"]; row.platform=device["platform"]; row.app_version=device["application_version"]; row.last_seen_at=utcnow()
        self.repo.add_event(lic.id,"VALIDATED","License validated."); self.db.commit(); return self._response(lic,device_hash,public_device_binding(device["device_id"]))

    def refresh(self, license_reference: str, device: dict) -> dict:
        response=self.validate(license_reference,device)
        lic=self.repo.get_license(license_reference)
        if lic is not None:
            self.repo.add_event(lic.id,"REFRESHED","License entitlement refreshed.")
            self.db.commit()
        return response

    def devices(self, license_reference: str, current_device_id: str | None = None) -> dict:
        lic=self.repo.get_license(license_reference)
        if lic is None: raise LicenseDomainError("INVALID_LICENSE_KEY","License reference was not found.",status_code=404)
        current_hash=hash_device_id(current_device_id) if current_device_id else None
        return {"ok":True,"devices":[self._device_view(d,current_hash) for d in self.repo.active_devices(lic.id)]}

    def deactivate_device(self, license_reference: str, server_device_id: str | None, device_id: str | None) -> dict:
        lic=self.repo.get_license(license_reference)
        if lic is None: raise LicenseDomainError("INVALID_LICENSE_KEY","License reference was not found.",status_code=404)
        row=self.repo.device_by_id(lic.id,server_device_id) if server_device_id else self.repo.device_by_hash(lic.id,hash_device_id(device_id or ""))
        if row is None: raise LicenseDomainError("DEVICE_NOT_FOUND","License device was not found.",status_code=404)
        row.is_active=False; row.deactivated_at=utcnow(); self.repo.add_event(lic.id,"DEVICE_DEACTIVATED","License device deactivated.",{"server_device_id":row.id}); self.db.commit()
        return {"ok":True,"devices":[self._device_view(d) for d in self.repo.active_devices(lic.id)]}

    def create_license(self, plan_code: str, expires_at: datetime, customer_reference: str | None = None, notes: str | None = None):
        plan=self.repo.get_plan(plan_code)
        if plan is None: raise LicenseDomainError("PLAN_NOT_FOUND","Unknown or inactive plan.",status_code=404)
        raw=generate_license_key(); lic=License(license_key_hash=hash_license_key(raw),license_key_prefix=prefix_for_key(raw),plan_id=plan.id,status="ACTIVE",starts_at=utcnow(),expires_at=_utc(expires_at),customer_reference=customer_reference,notes=notes)
        self.db.add(lic); self.db.flush(); self.repo.add_event(lic.id,"LICENSE_CREATED","License created.",{"plan":plan.code}); self.db.commit(); self.db.refresh(lic)
        return lic,raw

    def set_plan(self, lic: License, plan_code: str):
        plan=self.repo.get_plan(plan_code)
        if plan is None: raise LicenseDomainError("PLAN_NOT_FOUND","Unknown or inactive plan.",status_code=404)
        old=lic.plan.code; lic.plan_id=plan.id; self.repo.add_event(lic.id,"PLAN_CHANGED","License plan changed.",{"old_plan":old,"new_plan":plan.code}); self.db.commit(); self.db.refresh(lic); return lic

    def set_expiry(self, lic: License, expires_at: datetime):
        lic.expires_at=_utc(expires_at); self.repo.add_event(lic.id,"EXTENDED","License expiration updated."); self.db.commit(); return lic

    def set_status(self, lic: License, status: str, reason: str | None = None):
        status=status.upper()
        if status not in {"ACTIVE","SUSPENDED","REVOKED"}: raise LicenseDomainError("INVALID_STATUS","Unsupported administrative status.")
        lic.status=status; lic.suspended_at=utcnow() if status=="SUSPENDED" else None; lic.revoked_at=utcnow() if status=="REVOKED" else None
        event={"ACTIVE":"UNSUSPENDED","SUSPENDED":"SUSPENDED","REVOKED":"REVOKED"}[status]; self.repo.add_event(lic.id,event,reason or event.title()); self.db.commit(); return lic
