from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


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
    """Load public desktop license configuration.

    `desktop-license.env` is intentionally a public-client configuration file:
    it may contain only the license API URL, Ed25519 public verification key,
    and development-mode flags. Environment variables override file values.
    Server private keys/admin/database secrets are never read here.
    """
    root = Path(project_root) if project_root else _project_root()
    config_file = root / "desktop-license.env"
    file_values = _read_env_file(config_file)

    def value(name: str, default: str = "") -> str:
        if name in os.environ:
            return str(os.environ.get(name) or "").strip()
        return str(file_values.get(name, default) or "").strip()

    app_env = value("SP_APP_ENV", "production").lower()
    requested_local_http = value("SP_ALLOW_LOCAL_LICENSE_HTTP", "0").lower() in _TRUE_VALUES
    allow_local_http = app_env in {"development", "dev", "test", "testing"} and requested_local_http
    return LicenseClientConfig(
        api_base_url=value("LICENSE_API_BASE_URL"),
        public_key_b64=value("SP_LICENSE_PUBLIC_KEY_B64"),
        app_env=app_env,
        allow_local_http=allow_local_http,
        source_file=config_file if config_file.is_file() else None,
    )
