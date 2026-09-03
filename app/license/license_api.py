from __future__ import annotations

import urllib.parse
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.constants import APP_VERSION
from app.license.entitlement_verifier import EntitlementVerifier
from app.license.license_errors import LicenseApiError
from app.license.license_models import LicenseApiResult


class LicenseApi(ABC):
    @abstractmethod
    async def activate_license(self, license_key: str, device: dict) -> LicenseApiResult: ...

    @abstractmethod
    async def validate_license(self, license_reference: str, device: dict) -> LicenseApiResult: ...

    async def refresh_license(self, license_reference: str, device: dict) -> LicenseApiResult:
        return await self.validate_license(license_reference, device)

    @abstractmethod
    async def deactivate_device(self, license_reference: str, device_id: str) -> LicenseApiResult: ...

    @abstractmethod
    async def get_license_devices(self, license_reference: str, device_id: str | None = None) -> LicenseApiResult: ...

    async def get_payment_plans(self) -> list[dict[str, Any]]:
        return []

    async def apply_promotion(self, code: str, plan: str, device: dict) -> dict[str, Any]:
        raise LicenseApiError("Promotion codes are not supported by this license adapter.", code="PROMO_NOT_SUPPORTED")

    async def create_payment_invoice(self, plan: str, license_reference: str | None, device: dict, promotion_code: str | None = None) -> dict[str, Any]:
        raise LicenseApiError("Payment checkout is not supported by this license adapter.", code="PAYMENT_NOT_SUPPORTED")

    async def check_payment_invoice(self, invoice_id: str, claim_token: str, device: dict) -> dict[str, Any]:
        raise LicenseApiError("Payment checkout is not supported by this license adapter.", code="PAYMENT_NOT_SUPPORTED")


class HttpLicenseApi(LicenseApi):
    """Production HTTPS adapter for licensing, promotions and KHQR checkout."""

    def __init__(self, base_url: str, verifier: EntitlementVerifier | None = None, *, connect_timeout: float = 5.0, read_timeout: float = 12.0, allow_local_http: bool = False):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.verifier = verifier or EntitlementVerifier()
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(self.connect_timeout, float(read_timeout))
        self.allow_local_http = bool(allow_local_http)

    def _validate_base_url(self) -> None:
        if not self.base_url:
            raise LicenseApiError("License service URL is not configured.", code="SERVER_UNAVAILABLE")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme == "https":
            return
        local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if local and self.allow_local_http:
            return
        raise LicenseApiError("Production license verification requires HTTPS.", code="INVALID_LICENSE_RESPONSE")

    async def _request(self, path: str, payload: dict[str, Any] | None = None, *, method: str = "POST") -> dict[str, Any]:
        self._validate_base_url()
        parsed = urllib.parse.urlparse(self.base_url)
        is_local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        timeout = httpx.Timeout(timeout=self.read_timeout, connect=self.connect_timeout, read=self.read_timeout, write=self.read_timeout, pool=self.connect_timeout)
        headers = {"Accept": "application/json", "User-Agent": f"SP-Telegram/{APP_VERSION}"}
        if method.upper() != "GET":
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=False, trust_env=not is_local) as client:
                response = await client.get(self.base_url + path) if method.upper() == "GET" else await client.post(self.base_url + path, json=payload or {})
        except httpx.TimeoutException as exc:
            raise LicenseApiError("The license service request timed out.", code="SERVER_UNAVAILABLE") from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise LicenseApiError("The license service is temporarily unavailable.", code="NETWORK_UNAVAILABLE") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LicenseApiError("The license service returned an invalid response.", code="INVALID_LICENSE_RESPONSE") from exc
        if not isinstance(data, dict):
            raise LicenseApiError("The license service returned an invalid response.", code="INVALID_LICENSE_RESPONSE")
        if response.status_code >= 400:
            detail = data.get("detail", data)
            if not isinstance(detail, dict):
                detail = {}
            return {
                "ok": False,
                "error_code": detail.get("error_code") or detail.get("code") or data.get("error_code") or "UNKNOWN",
                "message": detail.get("message") or data.get("message") or "Could not complete the request.",
            }
        return data

    def _signed_result(self, data: dict[str, Any]) -> LicenseApiResult:
        if not data.get("ok", False):
            return LicenseApiResult(False, error_code=data.get("error_code") or "UNKNOWN", message=data.get("message") or "Could not verify license.")
        envelope = data.get("signed_entitlement")
        claims = self.verifier.verify(envelope) if isinstance(envelope, dict) else None
        if not claims:
            raise LicenseApiError("The signed license entitlement could not be verified.", code="INVALID_LICENSE_RESPONSE")
        for key in ("plan", "status", "expires_at"):
            if data.get(key) is not None and str(data.get(key)) != str(claims.get(key)):
                raise LicenseApiError("The license response does not match its signed entitlement.", code="INVALID_LICENSE_RESPONSE")
        return LicenseApiResult(
            True,
            plan=str(claims["plan"]),
            status=str(claims["status"]),
            expires_at=str(claims["expires_at"]),
            license_reference=str(data.get("license_reference") or claims["license_id"]),
            server_license_id=str(data.get("server_license_id") or claims["license_id"]),
            devices=list(data.get("devices") or []),
            cached_payload=envelope,
            trusted=True,
        )

    @staticmethod
    def _device_payload(device: dict) -> dict:
        return {
            "device_id": str(device.get("device_id") or ""),
            "device_name": str(device.get("device_name") or "SP Telegram Device"),
            "platform": str(device.get("platform") or "Unknown"),
            "application_version": str(device.get("application_version") or APP_VERSION),
        }

    async def activate_license(self, license_key: str, device: dict) -> LicenseApiResult:
        return self._signed_result(await self._request("/api/v1/license/activate", {"license_key": license_key, **self._device_payload(device)}))

    async def validate_license(self, license_reference: str, device: dict) -> LicenseApiResult:
        return self._signed_result(await self._request("/api/v1/license/validate", {"license_reference": license_reference, **self._device_payload(device)}))

    async def refresh_license(self, license_reference: str, device: dict) -> LicenseApiResult:
        return self._signed_result(await self._request("/api/v1/license/refresh", {"license_reference": license_reference, **self._device_payload(device)}))

    async def deactivate_device(self, license_reference: str, device_id: str) -> LicenseApiResult:
        payload = {"license_reference": license_reference}
        if str(device_id).startswith("server:"):
            payload["server_device_id"] = str(device_id).split(":", 1)[1]
        else:
            payload["device_id"] = device_id
        data = await self._request("/api/v1/license/deactivate-device", payload)
        return LicenseApiResult(bool(data.get("ok")), devices=list(data.get("devices") or []), error_code=data.get("error_code"), message=data.get("message"), trusted=True)

    async def get_license_devices(self, license_reference: str, device_id: str | None = None) -> LicenseApiResult:
        data = await self._request("/api/v1/license/devices", {"license_reference": license_reference, "device_id": device_id})
        return LicenseApiResult(bool(data.get("ok")), devices=list(data.get("devices") or []), error_code=data.get("error_code"), message=data.get("message"), trusted=True)

    async def get_payment_plans(self) -> list[dict[str, Any]]:
        data = await self._request("/api/v1/payments/plans", method="GET")
        if not data.get("ok", False):
            raise LicenseApiError(data.get("message") or "Could not load plan pricing.", code=data.get("error_code") or "SERVER_UNAVAILABLE")
        return list(data.get("plans") or [])

    async def apply_promotion(self, code: str, plan: str, device: dict) -> dict[str, Any]:
        data = await self._request("/api/v1/promotions/apply", {"code": str(code).strip(), "plan": str(plan).upper(), **self._device_payload(device)})
        if not data.get("ok", False):
            raise LicenseApiError(data.get("message") or "Promotion could not be applied.", code=data.get("error_code") or "PROMO_INVALID")
        return data

    async def create_payment_invoice(self, plan: str, license_reference: str | None, device: dict, promotion_code: str | None = None) -> dict[str, Any]:
        payload = {"plan": str(plan), "license_reference": license_reference, **self._device_payload(device)}
        if promotion_code:
            payload["promotion_code"] = str(promotion_code).strip()
        data = await self._request("/api/v1/payments/invoices", payload)
        if not data.get("ok", False):
            raise LicenseApiError(data.get("message") or "Could not create payment invoice.", code=data.get("error_code") or "PAYMENT_ERROR")
        if not data.get("invoice_id") or not data.get("claim_token") or not data.get("khqr_payload"):
            raise LicenseApiError("The payment service returned an incomplete invoice.", code="INVALID_LICENSE_RESPONSE")
        return data

    async def check_payment_invoice(self, invoice_id: str, claim_token: str, device: dict) -> dict[str, Any]:
        data = await self._request(
            f"/api/v1/payments/invoices/{urllib.parse.quote(str(invoice_id), safe='')}/check",
            {"claim_token": claim_token, **self._device_payload(device)},
        )
        if not data.get("ok", False):
            raise LicenseApiError(data.get("message") or "Could not check payment.", code=data.get("error_code") or "PAYMENT_ERROR")
        return data


def create_license_api() -> LicenseApi:
    from app.license.client_config import load_license_client_config
    config = load_license_client_config()
    return HttpLicenseApi(config.api_base_url, EntitlementVerifier(config.public_key_b64), allow_local_http=config.allow_local_http)
