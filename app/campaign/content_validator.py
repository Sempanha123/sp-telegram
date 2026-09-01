from __future__ import annotations
from pathlib import Path

class CampaignContentValidator:
    MEDIA_TYPES = {"PHOTO", "VIDEO", "DOCUMENT", "MEDIA_WITH_CAPTION", "MEDIA_+_CAPTION", "MEDIA"}
    def validate_message(self, message) -> list[str]:
        mtype = str(getattr(message, "message_type", None) or (message.get("message_type") if isinstance(message, dict) else None) or (message.get("type") if isinstance(message, dict) else "TEXT")).upper().replace(" ", "_")
        body = getattr(message, "body", None) if not isinstance(message, dict) else message.get("body")
        caption = getattr(message, "caption", None) if not isinstance(message, dict) else message.get("caption")
        media = getattr(message, "media_path", None) if not isinstance(message, dict) else (message.get("media_path") or message.get("media"))
        errors=[]
        if mtype == "TEXT" and not (body or "").strip(): errors.append("Text message cannot be empty.")
        if mtype in self.MEDIA_TYPES:
            if not media: errors.append("Media file is required.")
            elif not Path(media).is_file(): errors.append("Media file is missing or unreadable.")
        if not (body or caption or media): errors.append("Message content is empty.")
        return errors
