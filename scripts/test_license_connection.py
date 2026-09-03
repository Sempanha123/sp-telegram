from __future__ import annotations

import asyncio
import sys

import httpx

from app.license.client_config import load_license_client_config
from app.license.entitlement_verifier import EntitlementVerifier


async def main():
    cfg = load_license_client_config()
    print("Config source:", cfg.source_file or "pinned build/environment")
    print("API:", cfg.api_base_url or "<missing>")
    print("Mode:", cfg.app_env)
    if not cfg.api_base_url:
        raise SystemExit("LICENSE_API_BASE_URL is missing.")
    # Construct verifier so malformed public keys fail before the EXE is shipped.
    EntitlementVerifier(cfg.public_key_b64)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        r = await client.get(cfg.api_base_url.rstrip('/') + '/health')
        print("Health:", r.status_code, r.text)
        if r.status_code != 200:
            raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
