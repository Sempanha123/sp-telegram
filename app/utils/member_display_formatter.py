from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_PLACEHOLDER_NAMES = {"", "hidden", "unavailable", "unknown", "—", "-"}


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MemberDisplayPreferences:
    show_telegram_id: bool = True
    show_username: bool = True
    show_display_name: bool = True
    mask_telegram_ids: bool = False
    mask_usernames: bool = False
    mask_display_names: bool = False
    privacy_mode: bool = False

    @classmethod
    def from_manager(cls, manager, *, privacy_mode: bool | None = None):
        settings = getattr(manager, "settings", None)
        if privacy_mode is None:
            raw = settings.value("ui/privacy_mode", False) if settings is not None else False
            privacy_mode = _bool(raw, False)
        return cls(
            show_telegram_id=bool(manager.global_value("show_telegram_id", True)),
            show_username=bool(manager.global_value("show_username", True)),
            show_display_name=bool(manager.global_value("show_display_name", True)),
            mask_telegram_ids=bool(manager.global_value("mask_telegram_ids", False)),
            mask_usernames=bool(manager.global_value("mask_usernames", False)),
            mask_display_names=bool(manager.global_value("mask_display_names", False)),
            privacy_mode=bool(privacy_mode),
        )


class MemberDisplayFormatter:
    """Canonical presentation-only member identity formatting.

    Raw database values are never changed. Visibility, normal masking and the
    global Privacy Mode override are deliberately separate concerns.
    """

    @staticmethod
    def _raw(member: Any, name: str, default=None):
        if isinstance(member, dict):
            return member.get(name, default)
        return getattr(member, name, default)

    @classmethod
    def raw_display_name(cls, member: Any) -> str | None:
        # Prefer first/last name when available. This also avoids propagating a
        # historical presentation placeholder such as "Hidden" that may exist in
        # display_name while real first/last fields are still known.
        parts = [str(cls._raw(member, "first_name", "") or "").strip(), str(cls._raw(member, "last_name", "") or "").strip()]
        joined = " ".join(x for x in parts if x).strip()
        if joined:
            return joined
        display = str(cls._raw(member, "display_name", "") or "").strip()
        if display.lower() not in _PLACEHOLDER_NAMES:
            return display
        return None

    @staticmethod
    def mask_telegram_id(value: Any) -> str:
        raw = str(value or "")
        if not raw:
            return "—"
        if len(raw) <= 4:
            return "•" * len(raw)
        return f"{raw[:2]}{'•' * max(4, len(raw) - 4)}{raw[-2:]}"

    @staticmethod
    def mask_username(value: Any) -> str:
        raw = str(value or "").strip().lstrip("@")
        if not raw:
            return "—"
        return "@" + raw[:1] + ("•" * max(5, len(raw) - 1))

    @staticmethod
    def mask_name(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        masked = []
        for part in text.split():
            if not part:
                continue
            masked.append(part[:1] + ("•" * max(2, len(part) - 1)))
        return " ".join(masked) or "—"

    @classmethod
    def format_telegram_id(cls, member: Any, preferences: MemberDisplayPreferences, *, unavailable: str = "—") -> str:
        value = cls._raw(member, "telegram_user_id")
        if value in (None, ""):
            return unavailable
        if preferences.privacy_mode or preferences.mask_telegram_ids:
            return cls.mask_telegram_id(value)
        return str(value)

    @classmethod
    def format_username(cls, member: Any, preferences: MemberDisplayPreferences, *, unavailable: str = "—") -> str:
        value = str(cls._raw(member, "username", "") or "").strip().lstrip("@")
        if not value:
            return unavailable
        if preferences.privacy_mode or preferences.mask_usernames:
            return cls.mask_username(value)
        return f"@{value}"

    @classmethod
    def format_name(cls, member: Any, preferences: MemberDisplayPreferences, *, unavailable: str = "—") -> str:
        value = cls.raw_display_name(member)
        if not value:
            return unavailable
        if preferences.privacy_mode or preferences.mask_display_names:
            return cls.mask_name(value)
        return value

    @classmethod
    def format_identity(cls, member: Any, preferences: MemberDisplayPreferences) -> dict[str, str]:
        return {
            "telegram_user_id": cls.format_telegram_id(member, preferences),
            "username": cls.format_username(member, preferences),
            "display_name": cls.format_name(member, preferences),
        }
