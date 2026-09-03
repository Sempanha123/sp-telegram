from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Write public SP Telegram license config beside a built EXE.")
parser.add_argument("--dist-dir", required=True, help="Directory that contains SP Telegram.exe")
parser.add_argument("--api-url", required=True, help="HTTPS license server URL")
parser.add_argument("--public-key", required=True, help="Ed25519 public verification key in base64")
args = parser.parse_args()

url = args.api_url.strip().rstrip("/")
if not url.startswith("https://"):
    raise SystemExit("Production API URL must use https://")
if len(args.public_key.strip()) < 40:
    raise SystemExit("Public key looks too short.")

path = Path(args.dist_dir).resolve() / "desktop-license.env"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    "# PUBLIC configuration shipped beside SP Telegram.exe\n"
    f"LICENSE_API_BASE_URL={url}\n"
    f"SP_LICENSE_PUBLIC_KEY_B64={args.public_key.strip()}\n"
    "SP_APP_ENV=production\n"
    "SP_ALLOW_LOCAL_LICENSE_HTTP=0\n",
    encoding="utf-8",
)
print(path)
