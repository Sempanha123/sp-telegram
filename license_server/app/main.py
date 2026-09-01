from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .routes import admin_router, license_router
from .services.license_service import LicenseDomainError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail closed on deployment if any server-only signing/HMAC/admin secret is
    # absent or malformed. None of these values exist in the desktop client.
    settings.validate_runtime_secrets()
    yield


app=FastAPI(title="SP Telegram License Service",version="1.0.0",lifespan=lifespan)
app.include_router(license_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"ok":True,"service":"sp-telegram-license"}


@app.exception_handler(LicenseDomainError)
async def domain_error(_request:Request,exc:LicenseDomainError):
    return JSONResponse(status_code=exc.status_code,content={"ok":False,"error_code":exc.code,"message":str(exc)})
