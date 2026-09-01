from __future__ import annotations

import traceback


# User-facing messages keyed by the category returned by ``classify()``.
_CATEGORY_MESSAGES: dict[str, str] = {
    "Database": (
        "A database error occurred. The application will continue, but you "
        "should restart it to avoid data inconsistencies. If the problem "
        "persists, restore the most recent backup from Settings → Maintenance."
    ),
    "Telegram": (
        "A Telegram communication error occurred. Check your internet "
        "connection and verify that Telegram is not blocking this account. "
        "If the problem persists, re-login the affected account."
    ),
    "Worker": (
        "A background task failed unexpectedly. The application may need to "
        "be restarted. Check the Logs page for details."
    ),
    "Configuration": (
        "A configuration error was detected. Open Settings to review and "
        "correct the affected settings."
    ),
}

_DEFAULT_MESSAGE = (
    "The operation could not be completed. Technical details were written "
    "to the local log."
)


class ApplicationErrorHandler:
    def __init__(self, logger, alert_manager=None) -> None:
        self.logger = logger
        self.alerts = alert_manager

    def handle(self, exc: Exception, *, component: str = "UNKNOWN", context: str = "") -> str:
        category = self.classify(exc)
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        self.logger.error(
            "SYSTEM", f"Unexpected {category.lower()} error in {component}: {exc}",
            important=True, action="UNEXPECTED_ERROR",
            details={"component": component, "context": context, "traceback": detail},
        )
        if self.alerts:
            self.alerts.raise_alert(
                "ERROR", "SYSTEM_ERROR",
                "An unexpected application error occurred",
                f"Component: {component}. The detailed error was recorded in the local log.",
                dedupe_key=f"system-error:{component}:{type(exc).__name__}",
                source_type="SYSTEM", source_id=component,
            )
        return _CATEGORY_MESSAGES.get(category, _DEFAULT_MESSAGE)

    @staticmethod
    def classify(exc: Exception) -> str:
        name = type(exc).__name__.lower()
        if "database" in name or "sqlite" in name:
            return "Database"
        if "telegram" in name or "rpc" in name:
            return "Telegram"
        if "worker" in name or "thread" in name:
            return "Worker"
        if "config" in name:
            return "Configuration"
        return "Unknown"
