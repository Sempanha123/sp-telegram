from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class DeviceInput(BaseModel):
    device_id: str = Field(min_length=8, max_length=256)
    device_name: str = Field(default="SP Telegram Device", max_length=160)
    platform: str = Field(default="Unknown", max_length=80)
    application_version: str = Field(default="unknown", max_length=40)


class ActivateRequest(DeviceInput):
    license_key: str = Field(min_length=8, max_length=160)


class ValidateRequest(DeviceInput):
    license_reference: str = Field(min_length=8, max_length=64)


class DeactivateDeviceRequest(BaseModel):
    license_reference: str
    server_device_id: str | None = None
    device_id: str | None = None


class LicenseReferenceRequest(BaseModel):
    license_reference: str
    device_id: str | None = None


class AdminCreateLicenseRequest(BaseModel):
    plan: str
    expires_at: datetime
    customer_reference: str | None = None
    notes: str | None = None


class AdminChangePlanRequest(BaseModel):
    plan: str


class AdminExtendRequest(BaseModel):
    expires_at: datetime


class AdminStatusRequest(BaseModel):
    status: str
    reason: str | None = None
