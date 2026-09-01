from __future__ import annotations

import base64
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://sptelegram:sptelegram@127.0.0.1:5432/sptelegram_license"
    admin_api_token: str = ""
    license_key_hash_secret: str = ""
    device_id_hash_secret: str = ""
    signing_private_key_b64: str = Field(default="", validation_alias="LICENSE_SIGNING_PRIVATE_KEY_B64")
    signing_key_id: str = Field(default="sp-license-v1", validation_alias="LICENSE_SIGNING_KEY_ID")
    public_base_url: str = "https://license.example.invalid"
    allow_local_http: bool = False
    offline_grace_days: int = 3

    model_config = SettingsConfigDict(
        # Tests and packaged environments can disable dotenv loading explicitly;
        # production keeps the existing license_server/.env default.
        env_file=None if os.getenv("SP_LICENSE_DISABLE_DOTENV") == "1" else str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def validate_runtime_secrets(self) -> None:
        missing = [
            name
            for name, value in (
                ("ADMIN_API_TOKEN", self.admin_api_token),
                ("LICENSE_KEY_HASH_SECRET", self.license_key_hash_secret),
                ("DEVICE_ID_HASH_SECRET", self.device_id_hash_secret),
                ("LICENSE_SIGNING_PRIVATE_KEY_B64", self.signing_private_key_b64),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("Missing license-server secrets: " + ", ".join(missing))
        weak = [
            name
            for name, value in (
                ("ADMIN_API_TOKEN", self.admin_api_token),
                ("LICENSE_KEY_HASH_SECRET", self.license_key_hash_secret),
                ("DEVICE_ID_HASH_SECRET", self.device_id_hash_secret),
            )
            if len(value) < 32
        ]
        if weak:
            raise RuntimeError("License-server secrets must be at least 32 characters: " + ", ".join(weak))
        try:
            raw = base64.b64decode(self.signing_private_key_b64)
        except Exception as exc:
            raise RuntimeError("LICENSE_SIGNING_PRIVATE_KEY_B64 is not valid base64.") from exc
        if len(raw) != 32:
            raise RuntimeError("LICENSE_SIGNING_PRIVATE_KEY_B64 must decode to a 32-byte Ed25519 private key.")


settings = Settings()
