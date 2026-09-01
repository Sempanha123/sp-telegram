from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import string
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..config import settings

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def normalize_license_key(value: str) -> str:
    return "-".join(part for part in (value or "").strip().upper().split("-") if part)


def generate_license_key() -> str:
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(5)]
    return "SP-" + "-".join(groups)


def _hmac_hex(secret: str, value: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_license_key(key: str) -> str:
    return _hmac_hex(settings.license_key_hash_secret, normalize_license_key(key))


def hash_device_id(device_id: str) -> str:
    return _hmac_hex(settings.device_id_hash_secret, device_id.strip())

def public_device_binding(device_id: str) -> str:
    return hashlib.sha256(str(device_id or "").strip().encode("utf-8")).hexdigest()


def mask_key(key: str) -> str:
    clean = normalize_license_key(key)
    tail = clean[-4:] if len(clean) >= 4 else ""
    return f"SP-••••-••••-••••-••••-{tail}" if tail else "SP-••••"


def prefix_for_key(key: str) -> str:
    clean = normalize_license_key(key)
    return clean[:7] + "…" if len(clean) > 7 else clean


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_entitlement(claims: dict[str, Any]) -> dict[str, Any]:
    settings.validate_runtime_secrets()
    private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(settings.signing_private_key_b64))
    payload = canonical_json(claims)
    signature = private.sign(payload)
    return {
        "alg": "Ed25519",
        "key_id": settings.signing_key_id,
        "payload": _b64url(payload),
        "signature": _b64url(signature),
    }
