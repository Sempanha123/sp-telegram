from __future__ import annotations
import re
from datetime import datetime

_ALLOWED = {"group_name", "group_username", "campaign_name", "date", "time"}
_TOKEN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

class CampaignTemplateRenderer:
    def validate(self, text: str | None) -> list[str]:
        if not text:
            return []
        unknown = sorted({m.group(1) for m in _TOKEN.finditer(text) if m.group(1) not in _ALLOWED})
        return [f"Unknown template variable: {{{name}}}." for name in unknown]

    def render(self, template_text: str | None, campaign, group, scheduled_datetime=None) -> str:
        text = template_text or ""
        errors = self.validate(text)
        if errors:
            raise ValueError(errors[0])
        dt = scheduled_datetime or datetime.now().astimezone()
        if isinstance(dt, str):
            try: dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except ValueError: dt = datetime.now().astimezone()
        values = {
            "group_name": getattr(group, "title", None) or (group.get("title") if isinstance(group, dict) else "") or "",
            "group_username": getattr(group, "username", None) or (group.get("username") if isinstance(group, dict) else "") or "",
            "campaign_name": getattr(campaign, "name", None) or (campaign.get("name") if isinstance(campaign, dict) else "") or "",
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M"),
        }
        return _TOKEN.sub(lambda m: str(values[m.group(1)]), text)
