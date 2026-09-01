from __future__ import annotations

import re
from typing import Any


class SensitiveDataFilter:
    """Central redaction policy for diagnostics, audit, support bundles and exports."""

    SENSITIVE_KEYS = {
        "otp", "verification_code", "phone_code", "2fa", "2fa_password", "password",
        "api_hash", "session_secret", "session_token", "auth_code", "qr_token", "invite_hash",
        "private_invite", "access_hash", "license_key", "license key", "raw_license",
    }

    # Phone number matcher (SEC-004): optional "+" + 1-3 digit country code,
    # then at least 4 body digits (each optionally surrounded by a space or
    # dash), then a 3-4 digit tail.  The body is fully masked; only the country
    # code and the last 3-4 digits remain visible.  Handles compact, spaced and
    # dashed international formats.
    _PHONE_RE = re.compile(r"(?<!\d)(\+?\d{1,3})((?:[\s-]?\d[\s-]?){4,})(\d{3,4})(?!\d)")

    @staticmethod
    def _mask_phone(match: re.Match) -> str:
        country = match.group(1)
        body = match.group(2)
        tail = match.group(3)
        return country + re.sub(r"\d", "•", body) + tail

    def __init__(self, *, mask_phone: bool = True, mask_ip: bool = True, mask_session_path: bool = False) -> None:
        self.mask_phone = mask_phone
        self.mask_ip = mask_ip
        self.mask_session_path = mask_session_path

    def redact(self, value: Any, key: str = "") -> Any:
        lowered = key.lower()
        if any(token in lowered for token in self.SENSITIVE_KEYS):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(k): self.redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.redact(v, key) for v in value]
        if isinstance(value, str):
            return self._redact_text(value, key)
        return value

    def _redact_text(self, text: str, key: str) -> str:
        text = re.sub(r"(?i)(api[_ -]?hash\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)((?:otp|verification code|2fa password|password|session token|license key)\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)\b(?:SP|TG)-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){2,}\b", "SP-[LICENSE-REDACTED]", text)
        text = re.sub(r"tg://login\?token=[^\s]+", "tg://login?token=[REDACTED]", text)
        text = re.sub(r"https?://t\.me/(?:joinchat/|\+)[A-Za-z0-9_-]+", "https://t.me/[PRIVATE_INVITE_REDACTED]", text)
        if self.mask_phone or "phone" in key.lower():
            text = self._PHONE_RE.sub(self._mask_phone, text)
        if self.mask_ip or "ip" in key.lower():
            text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP REDACTED]", text)
        if self.mask_session_path and ("session" in key.lower() or ".session" in text.lower()):
            text = re.sub(r"(?:[A-Za-z]:)?[^\s]*[\\/]([^\\/\s]+\.session)", r"[SESSION]/\1", text)
        return text
