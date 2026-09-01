"""Security-boundary tests that use only ephemeral test material."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.license.entitlement_verifier import EntitlementVerifier, device_binding
from license_server.app.config import Settings, settings
from license_server.app.security.tokens import (
    hash_device_id,
    hash_license_key,
    normalize_license_key,
    public_device_binding,
    sign_entitlement,
)


def _settings(**overrides) -> Settings:
    # The signing key is keyed by its validation alias because that is the only
    # name Settings accepts for it, in tests and in deployment alike.
    values = {
        "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/not-used",
        "admin_api_token": "a" * 32,
        "license_key_hash_secret": "b" * 32,
        "device_id_hash_secret": "c" * 32,
        "LICENSE_SIGNING_PRIVATE_KEY_B64": base64.b64encode(
            Ed25519PrivateKey.generate().private_bytes_raw()
        ).decode("ascii"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_runtime_secret_validation_rejects_missing_weak_and_bad_keys():
    with pytest.raises(RuntimeError, match="Missing license-server secrets"):
        Settings(
            _env_file=None,
            admin_api_token="",
            license_key_hash_secret="",
            device_id_hash_secret="",
            LICENSE_SIGNING_PRIVATE_KEY_B64="",
        ).validate_runtime_secrets()

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        _settings(admin_api_token="short").validate_runtime_secrets()

    with pytest.raises(RuntimeError, match="not valid base64"):
        _settings(
            LICENSE_SIGNING_PRIVATE_KEY_B64="not-base64!"
        ).validate_runtime_secrets()

    with pytest.raises(RuntimeError, match="32-byte Ed25519"):
        _settings(
            LICENSE_SIGNING_PRIVATE_KEY_B64=base64.b64encode(b"too short").decode(
                "ascii"
            )
        ).validate_runtime_secrets()


def test_runtime_secret_validation_accepts_ephemeral_test_values():
    _settings().validate_runtime_secrets()


def test_license_normalization_and_hmac_hashes_are_deterministic():
    raw_key = "  sp-abcd--efgh-2345  "
    normalized = "SP-ABCD-EFGH-2345"
    assert normalize_license_key(raw_key) == normalized

    expected_key_hash = hmac.new(
        settings.license_key_hash_secret.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert hash_license_key(raw_key) == expected_key_hash
    assert hash_license_key(normalized) == expected_key_hash

    expected_device_hash = hmac.new(
        settings.device_id_hash_secret.encode(),
        b"desktop-device-001",
        hashlib.sha256,
    ).hexdigest()
    assert hash_device_id(" desktop-device-001 ") == expected_device_hash
    assert hash_device_id("desktop-device-001") == expected_device_hash


def test_server_signature_verifies_with_desktop_public_key(test_public_key_b64):
    claims = {
        "license_id": "license-test-001",
        "plan": "PRO",
        "status": "ACTIVE",
        "device_id": public_device_binding("desktop-device-001"),
        "features": ["CAMPAIGNS"],
        "limits": {"MAX_ACCOUNTS": 5},
        "issued_at": "2026-08-31T12:00:00+00:00",
        "expires_at": "2027-08-31T12:00:00+00:00",
        "token_version": 1,
    }

    envelope = sign_entitlement(claims)
    verifier = EntitlementVerifier(test_public_key_b64)

    assert envelope["alg"] == "Ed25519"
    assert envelope["key_id"] == "test-ed25519-key"
    assert verifier.verify(envelope) == claims
    assert device_binding(" desktop-device-001 ") == claims["device_id"]

    tampered = dict(envelope)
    tampered["signature"] = "A" + envelope["signature"][1:]
    assert verifier.verify(tampered) is None
