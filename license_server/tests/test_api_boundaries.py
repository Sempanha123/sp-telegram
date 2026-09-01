"""FastAPI contract tests that do not use the production database."""

from __future__ import annotations

from unittest.mock import patch

from license_server.app.services import LicenseDomainError


VALID_ACTIVATION = {
    "license_key": "SP-ABCD-EFGH-2345",
    "device_id": "desktop-device-001",
    "device_name": "QA Desktop",
    "platform": "Windows",
    "application_version": "1.0.0",
}


def test_health_succeeds_with_valid_test_runtime_secrets(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "sp-telegram-license"}


def test_admin_routes_reject_missing_and_incorrect_tokens_before_database(api_client):
    payload = {"plan": "PRO", "expires_at": "2027-08-31T12:00:00Z"}

    missing = api_client.post("/api/v1/admin/licenses", json=payload)
    incorrect = api_client.post(
        "/api/v1/admin/licenses",
        json=payload,
        headers={"X-Admin-Token": "incorrect-test-token"},
    )

    for response in (missing, incorrect):
        assert response.status_code == 401
        assert response.json()["detail"] == {
            "code": "ADMIN_AUTH_REQUIRED",
            "message": "Administrator authentication failed.",
        }


def test_valid_admin_token_crosses_auth_boundary_without_real_database(
    api_client, admin_headers
):
    payload = {"plan": "PRO", "expires_at": "2027-08-31T12:00:00Z"}

    with patch(
        "license_server.app.routes.admin.LicenseService.create_license"
    ) as create_license:
        plan = type("Plan", (), {"code": "PRO"})()
        license_row = type(
            "License",
            (),
            {
                "id": "license-test-001",
                "plan": plan,
                "expires_at": "2027-08-31T12:00:00+00:00",
            },
        )()
        create_license.return_value = (
            license_row,
            "SP-ABCD-EFGH-JKLM-2345-ZYXW",
        )
        response = api_client.post(
            "/api/v1/admin/licenses", json=payload, headers=admin_headers
        )

    assert response.status_code == 200
    assert response.json()["license_id"] == "license-test-001"
    assert response.json()["plan"] == "PRO"
    create_license.assert_called_once()


def test_request_validation_returns_422_before_database(api_client):
    invalid = dict(VALID_ACTIVATION)
    invalid["device_id"] = "short"

    response = api_client.post("/api/v1/license/activate", json=invalid)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(error["loc"][-1] == "device_id" for error in detail)


def test_license_domain_error_uses_stable_json_contract(api_client):
    with patch(
        "license_server.app.routes.license.LicenseService.activate",
        side_effect=LicenseDomainError(
            "INVALID_LICENSE_KEY",
            "This license key is not valid.",
            status_code=404,
        ),
    ):
        response = api_client.post(
            "/api/v1/license/activate", json=VALID_ACTIVATION
        )

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error_code": "INVALID_LICENSE_KEY",
        "message": "This license key is not valid.",
    }
