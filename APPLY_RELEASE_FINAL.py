from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys


BUNDLE_ROOT = Path(__file__).resolve().parent
PAYLOAD_ROOT = BUNDLE_ROOT / "payload"
FILES = (
    ".gitignore",
    "main.py",
    "requirements-dev.txt",
    "SPTelegram.spec",
    "app/utils/app_paths.py",
    "scripts/build_release.ps1",
    "scripts/generate_build_assets.py",
    "scripts/release_preflight.py",
    "scripts/run_phase83_windows_qa.ps1",
    "tests/test_runtime_paths.py",
    "tests/test_release_build_contract.py",
    "tests/test_telegram_worker_runtime.py",
)


def validate_project(root: Path) -> None:
    required = (
        root / "main.py",
        root / "app" / "application_context.py",
        root / "app" / "telegram" / "workers" / "telegram_worker.py",
        root / "app" / "license" / "pinned_license_config.py",
        root / "requirements.txt",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(
            "The selected folder does not look like the SP Telegram repository.\nMissing:\n- "
            + "\n- ".join(missing)
        )


def apply(root: Path) -> Path:
    validate_project(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_root = root / f".release-backup-{stamp}"

    for relative in FILES:
        source = PAYLOAD_ROOT / relative
        if not source.is_file():
            raise SystemExit(f"Bundle payload is incomplete: {source}")
        target = root / relative
        if target.exists():
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"APPLIED | {relative}")

    return backup_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply final Windows release hardening to SP Telegram")
    parser.add_argument("--project", default=".", help="Path to the local sp-telegram checkout")
    args = parser.parse_args()
    root = Path(args.project).expanduser().resolve()
    backup = apply(root)

    print("\nRelease hardening applied successfully.")
    print(f"Backup of replaced files: {backup}")
    print("\nNext commands (PowerShell):")
    print(f'  cd "{root}"')
    print("  powershell -ExecutionPolicy Bypass -File .\\scripts\\build_release.ps1")
    print("\nFor an offline build without the live license health check:")
    print("  powershell -ExecutionPolicy Bypass -File .\\scripts\\build_release.ps1 -SkipLicenseCheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
