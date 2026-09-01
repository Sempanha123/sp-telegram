from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    max_accounts: Mapped[int | None] = mapped_column(Integer)
    max_source_groups: Mapped[int | None] = mapped_column(Integer)
    max_target_groups: Mapped[int | None] = mapped_column(Integer)
    max_member_pool: Mapped[int | None] = mapped_column(Integer)
    max_templates: Mapped[int | None] = mapped_column(Integer)
    features_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class License(Base):
    __tablename__ = "licenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    license_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    license_key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    customer_reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan: Mapped[Plan] = relationship(lazy="joined")
    devices: Mapped[list["LicenseDevice"]] = relationship(back_populates="license", cascade="all,delete-orphan")


class LicenseDevice(Base):
    __tablename__ = "license_devices"
    __table_args__ = (UniqueConstraint("license_id", "device_id_hash", name="uq_license_device"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    license_id: Mapped[str] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(160), nullable=False)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    app_version: Mapped[str] = mapped_column(String(40), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    license: Mapped[License] = relationship(back_populates="devices")


class LicenseEvent(Base):
    __tablename__ = "license_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_id: Mapped[str | None] = mapped_column(ForeignKey("licenses.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
