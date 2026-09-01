from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class GroupOperationResult:
    ok: bool
    value: Any = None
    error_code: str | None = None
    message: str = ""
