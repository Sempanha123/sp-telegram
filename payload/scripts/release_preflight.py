from __future__ import annotations

import argparse
import base64
import compileall
import importlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []
WARNINGS: list[str] = []


def ok(message: str) -> None:
    print(f"PASS | {message}")


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"FAIL | {message}")


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"WARN | {message}")


def require_file(relative: str) -> Path:
    path = ROOT / relative
    if path.is_file():
        ok(f"Required file exists: {relative}")
    else:
        fail(f"Required file is missing: {relative}")
    return path


def check_imports() -> None:
    for name in ("PySide6", "telethon", "qrcode", "keyring", "cryptography", "httpx"):
        try:
            importlib.import_module(name)
            ok(f"Import: {name}")
        except Exception as exc:
            fail(f"Import failed: {name}: {exc}")


def check_runtime_paths() -> None:
    from app.utils.app_paths import AppPaths, RUNTIME_DIR_ENV, default_runtime_root

    with tempfile.TemporaryDirectory(prefix="sp-telegram-preflight-") as tmp:
        old = os.environ.get(RUNTIME_DIR_ENV)
        os.environ[RUNTIME_DIR_ENV] = tmp
        try:
            root = default_runtime_root(ROOT)
            expected = Path(tmp).resolve()
            if root == expected:
                ok("Explicit writable runtime-root override")
            else:
                fail(f"Runtime-root override mismatch: expected {expected}, got {root}")
            paths = AppPaths.from_root(root)
            paths.ensure()
            validation = paths.validate(minimum_free_bytes=1)
            if validation.get("writable"):
                ok("Runtime data/session/log/backup/export directories are writable")
            else:
                fail("Runtime directories are not writable")
        finally:
            if old is None:
                os.environ.pop(RUNTIME_DIR_ENV, None)
            else:
                os.environ[RUNTIME_DIR_ENV] = old


def check_license_trust() -> None:
    from app.license.pinned_license_config import PINNED_API_BASE_URL, PINNED_PUBLIC_KEY_B64

    parsed = urlparse(str(PINNED_API_BASE_URL or ""))
    if parsed.scheme == "https" and parsed.hostname:
        ok(f"Production license URL is HTTPS: {parsed.hostname}")
    else:
        fail("Production license API URL must be pinned to HTTPS")

    try:
        raw = base64.b64decode(str(PINNED_PUBLIC_KEY_B64 or ""), validate=True)
    except Exception as exc:
        fail(f"Pinned Ed25519 public key is not valid base64: {exc}")
        return
    if len(raw) == 32:
        ok("Pinned Ed25519 public key is 32 bytes")
    else:
        fail(f"Pinned Ed25519 public key must decode to 32 bytes; got {len(raw)}")


def check_production_flags() -> None:
    from app import constants

    expected_false = ("APP_DEMO_MODE", "TELEGRAM_TEST_MODE", "MOCK_LICENSE", "DEVELOPER_MENU")
    for name in expected_false:
        value = bool(getattr(constants, name, True))
        if value:
            fail(f"Production flag must be false: {name}")
        else:
            ok(f"Production flag disabled: {name}")


def check_build_contract() -> None:
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    if "license_server/requirements.txt" in requirements:
        fail("requirements-dev.txt still references the external license_server checkout")
    else:
        ok("Desktop dev requirements are independent from license_server")

    qa = (ROOT / "scripts" / "run_phase83_windows_qa.ps1").read_text(encoding="utf-8")
    if "license_server/tests" in qa or "compileall -q app license_server" in qa:
        fail("Windows QA script still references an embedded license_server")
    else:
        ok("Windows QA script is desktop-only")

    spec = (ROOT / "SPTelegram.spec").read_text(encoding="utf-8")
    required_spec_tokens = (
        'ROOT / "assets"',
        'ROOT / "app" / "styles"',
        'ROOT / "app" / "localization"',
        'collect_submodules("keyring.backends")',
        '"qrcode.image.pil"',
        'console=False',
    )
    for token in required_spec_tokens:
        if token in spec:
            ok(f"PyInstaller contract: {token}")
        else:
            fail(f"PyInstaller spec is missing: {token}")


def check_local_secret_files() -> None:
    dangerous = {
        "ADMIN_API_TOKEN",
        "BAKONG_API_TOKEN",
        "DATABASE_URL",
        "LICENSE_KEY_HASH_SECRET",
        "DEVICE_ID_HASH_SECRET",
        "PAYMENT_KEY_ENCRYPTION_SECRET",
        "LICENSE_SIGNING_PRIVATE_KEY_B64",
    }
    candidates = [ROOT / ".env", ROOT / ".env.local", ROOT / "desktop-license.env"]
    found = False
    for path in candidates:
        if not path.is_file():
            continue
        for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key in dangerous:
                found = True
                fail(f"Server-only secret key appears in desktop file {path.name}:{line_number}: {key}")
    if not found:
        ok("No server-only secret assignments found in local desktop env files")


def check_compile() -> None:
    success = True
    for folder in (ROOT / "app", ROOT / "scripts", ROOT / "tests"):
        success = compileall.compile_dir(folder, quiet=1, force=False) and success
    success = compileall.compile_file(ROOT / "main.py", quiet=1, force=False) and success
    if success:
        ok("Python compileall")
    else:
        fail("Python compilation failed")


def check_action_audit() -> None:
    script = ROOT / "scripts" / "audit_production_actions.py"
    if not script.is_file():
        fail("Production action audit script is missing")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    print(output.rstrip())
    if result.returncode != 0:
        fail("Production action audit did not execute successfully")
    elif "review 0" in output.lower():
        ok("Production UI action audit has zero REVIEW controls")
    else:
        fail("Production UI action audit contains controls requiring review")


def check_license_connection() -> None:
    script = ROOT / "scripts" / "test_license_connection.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)
    if result.returncode == 0:
        ok("Live production license-service connection")
    else:
        fail("Live production license-service connection failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="SP Telegram release preflight")
    parser.add_argument("--check-license", action="store_true", help="Require a live HTTPS license-server health check")
    args = parser.parse_args()

    print("== SP Telegram Release Preflight ==")
    print(f"Python: {sys.version.split()[0]} | {platform.platform()} | {platform.machine()}")
    if sys.maxsize > 2**32:
        ok("64-bit Python runtime")
    else:
        fail("Use 64-bit Python for the Windows release build")

    for relative in (
        "main.py",
        "SPTelegram.spec",
        "assets/branding/sp_cambo_logo.png",
        "assets/branding/sp_cambo_mark.png",
        "app/styles/light.qss",
        "app/styles/dark.qss",
        "app/styles/components.qss",
        "app/localization/en.json",
        "app/localization/km.json",
        "app/license/pinned_license_config.py",
        "scripts/test_license_connection.py",
    ):
        require_file(relative)

    check_imports()
    check_runtime_paths()
    check_license_trust()
    check_production_flags()
    check_build_contract()
    check_local_secret_files()
    check_compile()
    check_action_audit()
    if args.check_license:
        check_license_connection()

    generated_audit = ROOT / "PRODUCTION_ACTION_AUDIT.md"
    if generated_audit.is_file():
        try:
            generated_audit.unlink()
        except OSError:
            warn("Could not remove generated PRODUCTION_ACTION_AUDIT.md")

    print("\n== Preflight Summary ==")
    print(f"Failures: {len(FAILURES)} | Warnings: {len(WARNINGS)}")
    for item in FAILURES:
        print(f"  FAIL: {item}")
    for item in WARNINGS:
        print(f"  WARN: {item}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
