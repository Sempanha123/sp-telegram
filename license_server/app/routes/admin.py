from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..repositories import LicenseRepository
from ..schemas.license import AdminChangePlanRequest, AdminCreateLicenseRequest, AdminExtendRequest, AdminStatusRequest
from ..security.admin import require_admin
from ..services import LicenseDomainError, LicenseService

router=APIRouter(prefix="/api/v1/admin",tags=["admin"],dependencies=[Depends(require_admin)])

@router.post("/licenses")
def create_license(request: AdminCreateLicenseRequest, db: Session=Depends(get_db)):
    lic,key=LicenseService(db).create_license(request.plan,request.expires_at,request.customer_reference,request.notes)
    return {"license_id":lic.id,"license_key":key,"masked_key":f"{key[:3]}••••••••{key[-4:]}","plan":lic.plan.code,"expires_at":lic.expires_at}

@router.post("/licenses/{license_id}/plan")
def change_plan(license_id:str, request:AdminChangePlanRequest, db:Session=Depends(get_db)):
    service=LicenseService(db);lic=service.repo.get_license(license_id)
    if not lic:raise HTTPException(404,"License not found")
    lic=service.set_plan(lic,request.plan);return {"ok":True,"license_id":lic.id,"plan":lic.plan.code}

@router.post("/licenses/{license_id}/extend")
def extend(license_id:str, request:AdminExtendRequest, db:Session=Depends(get_db)):
    service=LicenseService(db);lic=service.repo.get_license(license_id)
    if not lic:raise HTTPException(404,"License not found")
    service.set_expiry(lic,request.expires_at);return {"ok":True,"expires_at":lic.expires_at}

@router.post("/licenses/{license_id}/status")
def status(license_id:str, request:AdminStatusRequest, db:Session=Depends(get_db)):
    service=LicenseService(db);lic=service.repo.get_license(license_id)
    if not lic:raise HTTPException(404,"License not found")
    service.set_status(lic,request.status,request.reason);return {"ok":True,"status":lic.status}

@router.get("/licenses/{license_id}/devices")
def devices(license_id:str, db:Session=Depends(get_db)):
    return LicenseService(db).devices(license_id)

@router.post("/licenses/{license_id}/devices/{device_id}/deactivate")
def deactivate_device(license_id:str,device_id:str,db:Session=Depends(get_db)):
    return LicenseService(db).deactivate_device(license_id,device_id,None)

@router.get("/licenses/{license_id}/events")
def events(license_id:str,db:Session=Depends(get_db)):
    repo=LicenseRepository(db);return [{"event_type":e.event_type,"message":e.message,"metadata":e.metadata_json,"created_at":e.created_at} for e in repo.list_events(license_id)]
