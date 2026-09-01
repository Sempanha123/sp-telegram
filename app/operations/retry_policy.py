from __future__ import annotations

from app.constants import RetryClassification


class RetryPolicy:
    """Classifies retry safety. Restrictions and permissions never auto-retry."""

    SAFE_CODES = {"NETWORK_ERROR", "NETWORK_TIMEOUT", "CONNECTION_LOST", "SERVER_ERROR", "WORKER_FAILED"}
    WAIT_CODES = {"DATABASE_LOCKED", "TEMPORARY_DB_LOCK", "TELEGRAM_SERVER_TEMPORARY"}
    USER_CODES = {"LOGIN_REQUIRED", "SESSION_INVALID", "CONFIGURATION_REQUIRED"}
    NO_RETRY_CODES = {
        "FLOOD_WAIT", "RATE_LIMIT", "ACCOUNT_RESTRICTED", "POST_PERMISSION_DENIED",
        "INVITE_RESTRICTED", "GROUP_ACCESS_DENIED", "PRIVACY_RESTRICTED", "DO_NOT_CONTACT",
        "PERMISSION_DENIED", "AUTH_KEY_INVALID",
    }

    @classmethod
    def classify(cls, error_code: str | None, message: str | None = None) -> RetryClassification:
        code = str(error_code or "").upper()
        text = str(message or "").lower()
        if code in cls.NO_RETRY_CODES or "flood" in text or "permission denied" in text or "restricted" in text:
            return RetryClassification.DO_NOT_RETRY
        if code in cls.USER_CODES or "login required" in text or "session invalid" in text:
            return RetryClassification.USER_ACTION_REQUIRED
        if code in cls.WAIT_CODES or "database is locked" in text:
            return RetryClassification.WAIT_AND_RETRY
        if code in cls.SAFE_CODES or "timeout" in text or "network" in text or "temporar" in text:
            return RetryClassification.SAFE_RETRY
        return RetryClassification.UNKNOWN
