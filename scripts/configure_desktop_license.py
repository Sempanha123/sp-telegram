from __future__ import annotations

import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def public_from_server_env(path: Path) -> str:
    values = read_env(path)
    private_b64 = values.get("LICENSE_SIGNING_PRIVATE_KEY_B64", "").strip()
    if not private_b64:
        raise SystemExit(f"{path} does not contain LICENSE_SIGNING_PRIVATE_KEY_B64.")
    try:
        raw = base64.b64decode(private_b64)
        private = Ed25519PrivateKey.from_private_bytes(raw)
    except Exception as exc:
        raise SystemExit("The license-server private signing key is invalid.") from exc
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(public_raw).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the public SP Telegram desktop license client.")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Public license API base URL")
    parser.add_argument("--public-key", default="", help="Ed25519 public key (base64)")
    parser.add_argument("--server-env", default=str(ROOT / "license_server" / ".env"), help="Local server .env used only to derive its public key")
    parser.add_argument("--production", action="store_true", help="Write production mode (HTTPS required by the desktop client)")
    args = parser.parse_args()

    public_key = args.public_key.strip() or public_from_server_env(Path(args.server_env))
    is_loopback = args.url.startswith("http://127.0.0.1") or args.url.startswith("http://localhost")
    if args.production and not args.url.lower().startswith("https://"):
        raise SystemExit("Production license API URL must use HTTPS.")

    env = "production" if args.production else "development"
    allow_local = "0" if args.production else ("1" if is_loopback else "0")
    target = ROOT / "desktop-license.env"
    target.write_text(
        "# Public SP Telegram desktop license configuration. No server secrets belong here.\n"
        f"LICENSE_API_BASE_URL={args.url.rstrip('/')}\n"
        f"SP_LICENSE_PUBLIC_KEY_B64={public_key}\n"
        f"SP_APP_ENV={env}\n"
        f"SP_ALLOW_LOCAL_LICENSE_HTTP={allow_local}\n",
        encoding="utf-8",
    )
    print(f"Desktop license configuration written: {target}")
    print(f"License API: {args.url.rstrip('/')}")
    print("Device identity: automatic (no customer-entered device ID or name required).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
