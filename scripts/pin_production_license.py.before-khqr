from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "license" / "pinned_license_config.py"

ap = argparse.ArgumentParser(description="Pin the production license API URL and Ed25519 public key into the desktop build.")
ap.add_argument("--api-url", required=True)
ap.add_argument("--public-key", required=True)
args = ap.parse_args()
url = args.api_url.strip().rstrip("/")
key = args.public_key.strip()
if not url.startswith("https://"):
    raise SystemExit("Production API URL must start with https://")
if len(key) < 40:
    raise SystemExit("Public key appears invalid/too short.")
TARGET.write_text(
    '"""Generated production license trust anchors. Public values, not secrets."""\n'
    f'PINNED_API_BASE_URL = {url!r}\n'
    f'PINNED_PUBLIC_KEY_B64 = {key!r}\n',
    encoding="utf-8",
)
print(f"Pinned production license trust config: {TARGET}")
