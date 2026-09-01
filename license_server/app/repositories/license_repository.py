from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import License, LicenseDevice, LicenseEvent, Plan


class LicenseRepository:
    def __init__(self, db: Session): self.db = db

    def get_plan(self, code: str) -> Plan | None:
        return self.db.scalar(select(Plan).where(Plan.code == code.upper(), Plan.is_active.is_(True)))

    def get_license(self, license_id: str) -> License | None:
        return self.db.get(License, license_id)

    def get_license_by_key_hash(self, key_hash: str) -> License | None:
        return self.db.scalar(select(License).where(License.license_key_hash == key_hash))

    def active_devices(self, license_id: str) -> list[LicenseDevice]:
        return list(self.db.scalars(select(LicenseDevice).where(LicenseDevice.license_id == license_id, LicenseDevice.is_active.is_(True)).order_by(LicenseDevice.activated_at)))

    def device_by_hash(self, license_id: str, device_hash: str) -> LicenseDevice | None:
        return self.db.scalar(select(LicenseDevice).where(LicenseDevice.license_id == license_id, LicenseDevice.device_id_hash == device_hash))

    def device_by_id(self, license_id: str, server_device_id: str) -> LicenseDevice | None:
        obj = self.db.get(LicenseDevice, server_device_id)
        return obj if obj and obj.license_id == license_id else None

    def add_event(self, license_id: str | None, event_type: str, message: str = "", metadata: dict | None = None) -> LicenseEvent:
        event = LicenseEvent(license_id=license_id, event_type=event_type, message=message or None, metadata_json=metadata or {})
        self.db.add(event); self.db.flush(); return event

    def list_events(self, license_id: str, limit: int = 100):
        stmt = select(LicenseEvent).where(LicenseEvent.license_id == license_id).order_by(LicenseEvent.created_at.desc()).limit(max(1, min(limit, 500)))
        return list(self.db.scalars(stmt))
