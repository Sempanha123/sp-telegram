from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class OutgoingMessage:
    message_type: str = "TEXT"
    text: str | None = None
    caption: str | None = None
    media_path: str | None = None
    parse_mode: str = "PLAIN"
    disable_link_preview: bool = False
    content_hash: str = ""
