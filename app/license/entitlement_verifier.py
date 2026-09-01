from __future__ import annotations

import base64
import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


# Public verification material is intentionally not a secret. Replace this
# deployment placeholder before Phase 8.4, or provide SP_LICENSE_PUBLIC_KEY_B64.
BUNDLED_LICENSE_PUBLIC_KEY_B64 = ""




def device_binding(device_id: str) -> str:
    """Public one-way binding used inside signed entitlement claims."""
    return hashlib.sha256(str(device_id or "").strip().encode("utf-8")).hexdigest()


def _decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _public_key_bytes(value: str) -> bytes:
    try:
        raw = base64.b64decode(value)
    except Exception as exc:
        raise ValueError("License public verification key is invalid.") from exc
    if len(raw) != 32:
        raise ValueError("License public verification key must decode to 32 Ed25519 bytes.")
    return raw


class EntitlementVerifier:
    """Verify server-signed Ed25519 entitlement envelopes.

    The desktop never signs entitlements and never contains a server private key.
    """

    def __init__(self, public_key_b64: str | None = None):
        self.public_key_b64 = (public_key_b64 or os.getenv("SP_LICENSE_PUBLIC_KEY_B64") or BUNDLED_LICENSE_PUBLIC_KEY_B64).strip()

    @property
    def configured(self) -> bool:
        return bool(self.public_key_b64)

    def verify(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        if not self.configured or not isinstance(envelope, dict):
            return None
        if envelope.get("alg") != "Ed25519":
            return None
        payload_text = envelope.get("payload")
        signature_text = envelope.get("signature")
        if not isinstance(payload_text, str) or not isinstance(signature_text, str):
            return None
        try:
            payload = _decode_b64url(payload_text)
            signature = _decode_b64url(signature_text)
            key = Ed25519PublicKey.from_public_bytes(_public_key_bytes(self.public_key_b64))
            key.verify(signature, payload)
            claims = json.loads(payload.decode("utf-8"))
        except (InvalidSignature, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(claims, dict):
            return None
        required = {"license_id", "plan", "status", "device_id", "features", "limits", "issued_at", "expires_at", "token_version"}
        if not required.issubset(claims):
            return None
        try:
            issued = datetime.fromisoformat(str(claims["issued_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            expires = datetime.fromisoformat(str(claims["expires_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
        # Expired/suspended entitlements are still valid signed statements from
        # the server. Expiry is an authorization state, not a signature error.
        # Consumers decide whether the signed status permits an operation.
        _ = issued, expires
        return claims
