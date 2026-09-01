from __future__ import annotations

import re

_GROUP_RE = re.compile(r"^(?:https?://)?(?:t\.me/)?@?([A-Za-z0-9_]{4,})$")


def normalize_group_reference(value: str) -> str | None:
    value = value.strip().rstrip("/")
    match = _GROUP_RE.match(value)
    if not match:
        return None
    return "@" + match.group(1)
