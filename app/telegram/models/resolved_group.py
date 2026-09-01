from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from app.telegram.models.group_permissions import GroupPermissions

class GroupInputType(str, Enum):
    USERNAME="USERNAME"; PUBLIC_LINK="PUBLIC_LINK"; PRIVATE_INVITE="PRIVATE_INVITE"; UNKNOWN="UNKNOWN"
class GroupType(str, Enum):
    BASIC_GROUP="BASIC_GROUP"; SUPERGROUP="SUPERGROUP"; CHANNEL="CHANNEL"; GIGAGROUP="GIGAGROUP"; FORUM_SUPERGROUP="FORUM_SUPERGROUP"; UNKNOWN="UNKNOWN"
class GroupRole(str, Enum):
    OWNER="OWNER"; ADMIN="ADMIN"; MEMBER="MEMBER"; LEFT="LEFT"; BANNED="BANNED"; NOT_JOINED="NOT_JOINED"; UNKNOWN="UNKNOWN"
class GroupAccessState(str, Enum):
    PUBLIC_ACCESSIBLE="PUBLIC_ACCESSIBLE"; PRIVATE_MEMBER="PRIVATE_MEMBER"; PRIVATE_INVITE_AVAILABLE="PRIVATE_INVITE_AVAILABLE"; JOIN_REQUEST_REQUIRED="JOIN_REQUEST_REQUIRED"; JOIN_REQUEST_PENDING="JOIN_REQUEST_PENDING"; NOT_JOINED="NOT_JOINED"; ACCESS_DENIED="ACCESS_DENIED"; UNAVAILABLE="UNAVAILABLE"; UNKNOWN="UNKNOWN"
class JoinState(str, Enum):
    NONE="NONE"; AVAILABLE="AVAILABLE"; REQUEST_REQUIRED="REQUEST_REQUIRED"; PENDING="PENDING"; ALREADY_JOINED="ALREADY_JOINED"; EXPIRED="EXPIRED"; INVALID="INVALID"

@dataclass(frozen=True)
class ParsedGroupInput:
    original: str
    input_type: GroupInputType
    username: str | None = None
    invite_hash: str | None = None

@dataclass
class ResolvedGroup:
    telegram_group_id: int
    title: str
    username: str | None = None
    type: str = GroupType.UNKNOWN.value
    access_type: str = "UNKNOWN"
    access_state: str = GroupAccessState.UNKNOWN.value
    member_count: int | None = None
    description: str | None = None
    is_verified: bool = False
    is_scam: bool = False
    is_fake: bool = False
    is_forum: bool = False
    is_broadcast: bool = False
    is_megagroup: bool = False
    is_gigagroup: bool = False
    linked_chat_id: int | None = None
    account_id: int | None = None
    account_role: str = GroupRole.UNKNOWN.value
    permissions: GroupPermissions = field(default_factory=GroupPermissions)
    join_state: str = JoinState.NONE.value
    raw_reference_type: str = GroupInputType.UNKNOWN.value
    invite_hash: str | None = field(default=None, repr=False)
    already_saved: bool = False
