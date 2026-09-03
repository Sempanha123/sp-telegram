from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urlparse

from app.license.pinned_license_config import PINNED_API_BASE_URL, PINNED_PUBLIC_KEY_B64


ROOT = Path(__file__).resolve().parents[1]


def test_production_license_trust_is_pinned():
    parsed = urlparse(PINNED_API_BASE_URL)
    assert parsed.scheme == "https"
    assert parsed.hostname
    assert len(base64.b64decode(PINNED_PUBLIC_KEY_B64, validate=True)) == 32


def test_dev_requirements_do_not_depend_on_license_server_checkout():
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "license_server/requirements.txt" not in text
    assert "pyinstaller" in text.lower()


def test_windows_qa_is_desktop_only():
    text = (ROOT / "scripts" / "run_phase83_windows_qa.ps1").read_text(encoding="utf-8")
    assert "license_server/tests" not in text
    assert "compileall -q app license_server" not in text


def test_pyinstaller_spec_bundles_required_resources():
    text = (ROOT / "SPTelegram.spec").read_text(encoding="utf-8")
    for token in (
        'ROOT / "assets"',
        'ROOT / "app" / "styles"',
        'ROOT / "app" / "localization"',
        'collect_submodules("keyring.backends")',
        '"qrcode.image.pil"',
        "console=False",
    ):
        assert token in text
