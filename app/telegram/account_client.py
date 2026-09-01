from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AccountClient:
    account_id: int
    session_path: str
    client: Any
