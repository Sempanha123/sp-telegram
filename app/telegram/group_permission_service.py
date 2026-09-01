from __future__ import annotations
from app.telegram.models.group_permissions import GroupPermissions

class TelegramGroupPermissionService:
    def __init__(self, client_manager): self.client_manager=client_manager

    @staticmethod
    def _participant_details_hidden(error: Exception) -> bool:
        name=type(error).__name__.lower(); message=str(error or "").lower()
        return (
            "chatparticipantsforbidden" in name
            or "chatparticipantsforbidden" in message
            or (isinstance(error,AttributeError) and "participants" in message)
        )

    @staticmethod
    def _permissions_from_group(group) -> GroupPermissions:
        """Conservative fallback when Telegram hides participant details.

        Telethon may raise while resolving ``get_permissions`` even though the
        current account's own creator/admin rights are already present on the
        channel entity.  Use only those explicit rights and never enumerate the
        participant list or infer broader access.
        """
        creator=bool(getattr(group,"creator",False)); rights=getattr(group,"admin_rights",None)
        admin=creator or rights is not None; left=bool(getattr(group,"left",False)); banned=bool(getattr(group,"kicked",False))
        role="OWNER" if creator else "ADMIN" if admin else "BANNED" if banned else "LEFT" if left else "MEMBER"
        def p(name,default=False):
            if creator:return True
            value=getattr(rights,name,None) if rights is not None else None
            return bool(value) if value is not None else default
        can_view=not banned and not left
        return GroupPermissions(
            role=role,can_view=can_view,can_post=p("post_messages",False) if bool(getattr(group,"broadcast",False)) else (True if admin else None),
            can_send_media=True if admin else None,can_invite=p("invite_users",False),can_manage=admin,
            can_delete_messages=p("delete_messages",False),can_pin_messages=p("pin_messages",False),
            can_ban_users=p("ban_users",False),can_add_admins=p("add_admins",False),
            can_manage_call=p("manage_call",False),can_manage_topics=p("manage_topics",False),
            can_manage_invite_links=p("invite_users",False),can_approve_join_requests=p("ban_users",False),
            is_creator=creator,is_admin=admin,is_member=can_view,
        )

    async def get_my_permissions(self, account_id:int, group) -> GroupPermissions:
        client=await self.client_manager.get_client(account_id)
        if client is None: raise RuntimeError("Telegram client is not initialized for this account.")
        me=await client.get_me()
        try:raw=await client.get_permissions(group,me)
        except Exception as exc:
            if self._participant_details_hidden(exc):return self._permissions_from_group(group)
            raise
        if raw is None:return GroupPermissions(role="NOT_JOINED",can_view=False,is_member=False)
        creator=bool(getattr(raw,"is_creator",False)); admin=bool(getattr(raw,"is_admin",False)); banned=bool(getattr(raw,"is_banned",False)); left=bool(getattr(raw,"has_left",False))
        role="OWNER" if creator else "ADMIN" if admin else "BANNED" if banned else "LEFT" if left else "MEMBER"
        def p(name, default=None):
            value=getattr(raw,name,default); return bool(value) if value is not None else None
        if bool(getattr(group,"broadcast",False)):
            can_post = True if creator else p("post_messages", False) if admin else False
            can_media = can_post
        else:
            # Admin post_messages is not equivalent to ordinary member send rights in groups.
            # Only claim member send capability when Telethon exposes a matching value.
            can_post = True if (creator or admin) else p("send_messages", None)
            can_media = True if (creator or admin) else p("send_media", None)
        manage=creator or admin
        return GroupPermissions(
            role=role, can_view=not banned and not left, can_post=can_post, can_send_media=can_media,
            can_invite=p("invite_users",False) if not creator else True, can_manage=manage,
            can_delete_messages=p("delete_messages",False) if not creator else True,
            can_pin_messages=p("pin_messages",False) if not creator else True,
            can_ban_users=p("ban_users",False) if not creator else True,
            can_add_admins=p("add_admins",False) if not creator else True,
            can_manage_call=p("manage_call",False) if not creator else True,
            can_manage_topics=p("manage_topics",False) if not creator else True,
            can_manage_invite_links=p("invite_users",False) if not creator else True,
            can_approve_join_requests=p("ban_users",None) if not creator else True,
            is_creator=creator,is_admin=admin,is_member=not banned and not left,
        )
