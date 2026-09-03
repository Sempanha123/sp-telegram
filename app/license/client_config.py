from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LicenseClientConfig:
    api_base_url: str = ""
    public_key_b64: str = ""
    app_env: str = "production"
    allow_local_http: bool = False
    source_file: Path | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_candidates(project_root: str | Path | None = None) -> list[Path]:
    """Return public-config locations in production-first order.

    PyInstaller changes `__file__` semantics because modules are unpacked into a
    temporary directory. For a frozen EXE, the operator-facing
    `desktop-license.env` next to the EXE must therefore win.
    """
    candidates: list[Path] = []
    explicit = str(os.getenv("SP_DESKTOP_LICENSE_CONFIG", "") or "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "desktop-license.env")
    if project_root is not None:
        candidates.append(Path(project_root).resolve() / "desktop-license.env")
    candidates.append(_project_root() / "desktop-license.env")
    candidates.append(Path.cwd() / "desktop-license.env")

    seen: set[str] = set()
    result: list[Path] = []
    for item in candidates:
        key = str(item.resolve()) if item.exists() else str(item.absolute())
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_license_client_config(project_root: str | Path | None = None) -> LicenseClientConfig:
    """Load *public only* desktop license settings.

    Allowed values: HTTPS API URL, Ed25519 public verification key and local
    development flags. DB credentials, Bakong token, admin token, HMAC secrets
    and the signing private key must never exist in an EXE or this file.
    """
    source_file = next((p for p in _config_candidates(project_root) if p.is_file()), None)
    file_values = _read_env_file(source_file) if source_file else {}

    def value(name: str, default: str = "") -> str:
        if name in os.environ:
            return str(os.environ.get(name) or "").strip()
        return str(file_values.get(name, default) or "").strip()

    # A production build should pin both trust anchors into the executable.
    # Public keys are not secrets, but allowing an end user to replace the
    # verification key would let a fake server mint trusted entitlements.
    try:
        from app.license.pinned_license_config import PINNED_API_BASE_URL, PINNED_PUBLIC_KEY_B64
    except ImportError:
        PINNED_API_BASE_URL = PINNED_PUBLIC_KEY_B64 = ""
    pinned_url = str(PINNED_API_BASE_URL or "").strip()
    pinned_key = str(PINNED_PUBLIC_KEY_B64 or "").strip()
    if pinned_url and pinned_key:
        return LicenseClientConfig(
            api_base_url=pinned_url,
            public_key_b64=pinned_key,
            app_env="production",
            allow_local_http=False,
            source_file=source_file,
        )

    app_env = value("SP_APP_ENV", "production").lower()
    requested_local_http = value("SP_ALLOW_LOCAL_LICENSE_HTTP", "0").lower() in _TRUE_VALUES
    allow_local_http = app_env in {"development", "dev", "test", "testing"} and requested_local_http
    return LicenseClientConfig(
        api_base_url=value("LICENSE_API_BASE_URL"),
        public_key_b64=value("SP_LICENSE_PUBLIC_KEY_B64"),
        app_env=app_env,
        allow_local_http=allow_local_http,
        source_file=source_file,
    )
