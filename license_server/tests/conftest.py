"""Isolated fixtures for license-service tests.

The environment is populated before license-server modules are imported so the
suite never reads the deployment .env or connects to the configured PostgreSQL.
"""

from __future__ import annotations

import base64
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

os.environ["SP_LICENSE_DISABLE_DOTENV"] = "1"
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1:1/not-used"
os.environ["ADMIN_API_TOKEN"] = "test-admin-token-0123456789-abcdef"
os.environ["LICENSE_KEY_HASH_SECRET"] = "test-license-hash-secret-0123456789-abcdef"
os.environ["DEVICE_ID_HASH_SECRET"] = "test-device-hash-secret-0123456789-abcdef"

_TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()
_TEST_PRIVATE_BYTES = _TEST_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
_TEST_PUBLIC_BYTES = _TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
os.environ["LICENSE_SIGNING_PRIVATE_KEY_B64"] = base64.b64encode(
    _TEST_PRIVATE_BYTES
).decode("ascii")
os.environ["LICENSE_SIGNING_KEY_ID"] = "test-ed25519-key"

from license_server.app.config import settings
from license_server.app.database import get_db
from license_server.app.main import app


@pytest.fixture(scope="session")
def test_public_key_b64() -> str:
    return base64.b64encode(_TEST_PUBLIC_BYTES).decode("ascii")


class _ForbiddenSession:
    """Stand-in session that fails only if a boundary test really uses the database.

    FastAPI resolves the ``get_db`` dependency before body validation and before a
    patched service method runs, so the override must hand back an object instead
    of raising. Any attempt to query through it still fails the test loudly, and no
    PostgreSQL connection is ever opened.
    """

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise AssertionError(
            f"This API boundary test must not use the database (attempted {name!r})."
        )


@pytest.fixture
def api_client():
    def inert_database_session():
        yield _ForbiddenSession()

    app.dependency_overrides[get_db] = inert_database_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": settings.admin_api_token}
