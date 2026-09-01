from __future__ import annotations
from dataclasses import dataclass
from app.utils.formatters import utc_now_iso

@dataclass
class GroupPermissions:
    role: str = "UNKNOWN"
    can_view: bool | None = None
    can_post: bool | None = None
    can_send_media: bool | None = None
    can_invite: bool | None = None
    can_manage: bool | None = None
    can_delete_messages: bool | None = None
    can_pin_messages: bool | None = None
    can_ban_users: bool | None = None
    can_add_admins: bool | None = None
    can_manage_call: bool | None = None
    can_manage_topics: bool | None = None
    can_manage_invite_links: bool | None = None
    can_approve_join_requests: bool | None = None
    is_creator: bool = False
    is_admin: bool = False
    is_member: bool = False
    checked_at: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = utc_now_iso()
