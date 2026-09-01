from __future__ import annotations

import hmac
from fastapi import Header, HTTPException

from ..config import settings


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not settings.admin_api_token or not hmac.compare_digest(x_admin_token, settings.admin_api_token):
        raise HTTPException(status_code=401, detail={"code": "ADMIN_AUTH_REQUIRED", "message": "Administrator authentication failed."})
