from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.license import ActivateRequest, DeactivateDeviceRequest, LicenseReferenceRequest, ValidateRequest
from ..services import LicenseService

router=APIRouter(prefix="/api/v1/license",tags=["license"])

@router.post("/activate")
def activate(request: ActivateRequest, db: Session=Depends(get_db)):
    return LicenseService(db).activate(request.license_key, request.model_dump(exclude={"license_key"}))

@router.post("/validate")
def validate(request: ValidateRequest, db: Session=Depends(get_db)):
    return LicenseService(db).validate(request.license_reference, request.model_dump(exclude={"license_reference"}))

@router.post("/refresh")
def refresh(request: ValidateRequest, db: Session=Depends(get_db)):
    return LicenseService(db).refresh(request.license_reference, request.model_dump(exclude={"license_reference"}))

@router.post("/deactivate-device")
def deactivate(request: DeactivateDeviceRequest, db: Session=Depends(get_db)):
    return LicenseService(db).deactivate_device(request.license_reference, request.server_device_id, request.device_id)

@router.post("/devices")
def devices(request: LicenseReferenceRequest, db: Session=Depends(get_db)):
    return LicenseService(db).devices(request.license_reference, request.device_id)

@router.post("/me")
def me(request: ValidateRequest, db: Session=Depends(get_db)):
    return LicenseService(db).validate(request.license_reference, request.model_dump(exclude={"license_reference"}))


# Read-only GET aliases are convenient for administrative diagnostics and match
# the public v1 contract. The desktop currently uses POST to avoid putting
# identifiers into browser/proxy URLs during normal operation.
@router.get("/devices")
def devices_get(license_reference: str = Query(...), device_id: str | None = Query(default=None), db: Session=Depends(get_db)):
    return LicenseService(db).devices(license_reference, device_id)

@router.get("/me")
def me_get(license_reference: str = Query(...), device_id: str = Query(...), device_name: str = Query(default="SP Telegram Device"), platform: str = Query(default="Unknown"), application_version: str = Query(default="unknown"), db: Session=Depends(get_db)):
    return LicenseService(db).validate(license_reference,{"device_id":device_id,"device_name":device_name,"platform":platform,"application_version":application_version})
