from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.utils.helpers import json_dumps_safe


SENSITIVE_TOKENS = (
    "otp", "code", "phone_code", "2fa", "api_hash", "password", "session_secret",
    "auth_code", "qr_token", "login_token", "session_token", "license_key", "license key",
)


def redact_sensitive_data(value: Any, key: str = "") -> Any:
    """Best-effort defense-in-depth redaction before file/database logging."""
    if any(token in key.lower() for token in SENSITIVE_TOKENS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact_sensitive_data(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_sensitive_data(v, key) for v in value]
    if isinstance(value, str):
        text = value
        text = re.sub(r"(?i)(api[_ -]?hash\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)((?:otp|verification code|2fa password|password|license key)\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)\b(?:SP|TG)-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){2,}\b", "SP-[LICENSE-REDACTED]", text)
        text = re.sub(r"tg://login\?token=[^\s]+", "tg://login?token=[REDACTED]", text)
        text = re.sub(r"https?://t\.me/(?:joinchat/|\+)[A-Za-z0-9_-]+", "https://t.me/[PRIVATE_INVITE_REDACTED]", text)
        text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP REDACTED]", text)
        return text
    return value


class AppLogger:
    def __init__(self, log_dir: str | Path, log_repository=None) -> None:
        folder = Path(log_dir)
        folder.mkdir(parents=True, exist_ok=True)
        self.repository = log_repository
        self.logger = logging.getLogger("tg_control_center")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = RotatingFileHandler(folder / "app.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self.logger.addHandler(handler)

    def log(self, level: str, category: str, message: str, *, action: str | None = None, important: bool = False, details: dict[str, Any] | None = None, account_id: int | None = None, group_id: int | None = None, campaign_id: int | None = None, job_id: int | None = None) -> None:
        safe_message = str(redact_sensitive_data(message))
        safe_details = redact_sensitive_data(details or {})
        numeric = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(numeric, "%s | %s | %s", category.upper(), action or "-", safe_message)
        if important and self.repository is not None:
            try:
                self.repository.add_log(level.upper(), category.upper(), safe_message, action=action, account_id=account_id, group_id=group_id, campaign_id=campaign_id, job_id=job_id, details_json=json_dumps_safe(safe_details))
            except Exception:
                self.logger.exception("DATABASE | LOG_WRITE | Failed to persist an important log event")

    def info(self, category: str, message: str, **kwargs) -> None:
        self.log("INFO", category, message, **kwargs)

    def warning(self, category: str, message: str, **kwargs) -> None:
        self.log("WARNING", category, message, **kwargs)

    def error(self, category: str, message: str, **kwargs) -> None:
        self.log("ERROR", category, message, **kwargs)

    def close(self) -> None:
        """Release file handlers so disposable runtimes can clean up safely."""
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            try:
                handler.flush()
            finally:
                handler.close()
