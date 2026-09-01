from __future__ import annotations
from urllib.parse import urlparse
import re
from app.telegram.models.resolved_group import GroupInputType, GroupType, ParsedGroupInput, ResolvedGroup, GroupAccessState, JoinState

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,}$")
_INVITE_RE = re.compile(r"^[A-Za-z0-9_-]{8,}$")

class TelegramGroupInputParser:
    """Normalize public usernames/links and private invite links without exposing invite tokens."""
    HOSTS={"t.me","www.t.me","telegram.me","www.telegram.me"}
    def parse(self, value: str) -> ParsedGroupInput:
        original=value or ""; text=original.strip()
        if not text or any(ch.isspace() for ch in text): return ParsedGroupInput(original,GroupInputType.UNKNOWN)
        if text.startswith("@"): return self._username(original,text[1:].rstrip("/"),GroupInputType.USERNAME)
        candidate=text if "://" in text else (f"https://{text}" if text.lower().startswith(("t.me/","telegram.me/","www.t.me/","www.telegram.me/")) else "")
        if candidate:
            try: parsed=urlparse(candidate)
            except ValueError: return ParsedGroupInput(original,GroupInputType.UNKNOWN)
            if parsed.netloc.lower() not in self.HOSTS: return ParsedGroupInput(original,GroupInputType.UNKNOWN)
            parts=[p for p in parsed.path.split("/") if p]
            if not parts:return ParsedGroupInput(original,GroupInputType.UNKNOWN)
            if parts[0] == "+": return ParsedGroupInput(original,GroupInputType.UNKNOWN)
            if parts[0].startswith("+"):
                invite=parts[0][1:]
                return ParsedGroupInput(original,GroupInputType.PRIVATE_INVITE,invite_hash=invite) if _INVITE_RE.fullmatch(invite) else ParsedGroupInput(original,GroupInputType.UNKNOWN)
            if parts[0]=="joinchat" and len(parts)>1:
                invite=parts[1]
                return ParsedGroupInput(original,GroupInputType.PRIVATE_INVITE,invite_hash=invite) if _INVITE_RE.fullmatch(invite) else ParsedGroupInput(original,GroupInputType.UNKNOWN)
            return self._username(original,parts[0],GroupInputType.PUBLIC_LINK)
        return self._username(original,text.rstrip("/"),GroupInputType.USERNAME)
    def _username(self, original, username, kind):
        username=username.lstrip("@").strip()
        if not _USERNAME_RE.fullmatch(username): return ParsedGroupInput(original,GroupInputType.UNKNOWN)
        return ParsedGroupInput(original,kind,username=username)

class TelegramGroupNormalizer:
    """Convert Telethon Chat/Channel/full-info objects into application DTOs."""
    @staticmethod
    def entity_type(entity) -> str:
        name=type(entity).__name__.lower()
        if "chat" in name and "channel" not in name: return GroupType.BASIC_GROUP.value
        if "channel" in name or any(hasattr(entity, x) for x in ("megagroup","broadcast","forum","gigagroup")):
            if bool(getattr(entity,"gigagroup",False)): return GroupType.GIGAGROUP.value
            if bool(getattr(entity,"forum",False)): return GroupType.FORUM_SUPERGROUP.value
            if bool(getattr(entity,"megagroup",False)): return GroupType.SUPERGROUP.value
            if bool(getattr(entity,"broadcast",False)): return GroupType.CHANNEL.value
        return GroupType.UNKNOWN.value
    @staticmethod
    def normalize(entity, *, account_id=None, permissions=None, full=None, access_state=None, join_state=None, raw_reference_type="UNKNOWN") -> ResolvedGroup:
        username=getattr(entity,"username",None)
        access_type="PUBLIC" if username else "PRIVATE"
        description=None; member_count=getattr(entity,"participants_count",None); linked=None
        if full is not None:
            full_chat=getattr(full,"full_chat",full)
            description=getattr(full_chat,"about",None)
            member_count=getattr(full_chat,"participants_count",member_count)
            linked=getattr(full_chat,"linked_chat_id",None)
        resolved=ResolvedGroup(
            telegram_group_id=int(getattr(entity,"id")), title=str(getattr(entity,"title","") or "Unknown Group"),
            username=username, type=TelegramGroupNormalizer.entity_type(entity), access_type=access_type,
            access_state=access_state or (GroupAccessState.PUBLIC_ACCESSIBLE.value if username else GroupAccessState.PRIVATE_MEMBER.value),
            member_count=int(member_count) if member_count is not None else None, description=description,
            is_verified=bool(getattr(entity,"verified",False)), is_scam=bool(getattr(entity,"scam",False)), is_fake=bool(getattr(entity,"fake",False)),
            is_forum=bool(getattr(entity,"forum",False)), is_broadcast=bool(getattr(entity,"broadcast",False)), is_megagroup=bool(getattr(entity,"megagroup",False)), is_gigagroup=bool(getattr(entity,"gigagroup",False)),
            linked_chat_id=int(linked) if linked is not None else None, account_id=account_id, permissions=permissions,
            account_role=getattr(permissions,"role","UNKNOWN") if permissions else "UNKNOWN", join_state=join_state or JoinState.NONE.value,
            raw_reference_type=raw_reference_type,
        )
        return resolved
