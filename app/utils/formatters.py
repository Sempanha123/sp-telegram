from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_local_datetime(value: str | None, empty: str = "—") -> str:
    if not value:
        return empty
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%d %b %Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def mask_phone(phone: str | None) -> str:
    if not phone:
        return "—"
    value = str(phone).strip()
    if len(value) <= 5:
        return "•" * len(value)
    return f"{value[:4]}•••{value[-3:]}"


def metadata_freshness(value: str | None, stale_after_minutes: int = 60) -> str:
    if not value:
        return "Never Synced"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
        return "Fresh" if age.total_seconds() <= stale_after_minutes * 60 else "Stale"
    except (TypeError, ValueError):
        return "Stale"
