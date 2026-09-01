from __future__ import annotations
from app.telegram.group_normalizer import TelegramGroupInputParser,TelegramGroupNormalizer
from app.telegram.models.group_permissions import GroupPermissions
from app.telegram.models.resolved_group import GroupAccessState,GroupInputType,JoinState

class TelegramGroupResolver:
    def __init__(self,client_manager,permission_service): self.client_manager=client_manager;self.permission_service=permission_service;self.parser=TelegramGroupInputParser()
    async def resolve(self,account_id:int,input_value:str):
        parsed=self.parser.parse(input_value)
        if parsed.input_type==GroupInputType.UNKNOWN: raise ValueError("Invalid Telegram group reference. Enter a public @username, Telegram group link, or valid private invite link.")
        client=await self.client_manager.get_client(account_id)
        if client is None: raise RuntimeError("Telegram client is not initialized for this account.")
        if parsed.input_type==GroupInputType.PRIVATE_INVITE:return await self._resolve_invite(client,account_id,parsed)
        entity=await client.get_entity(parsed.username)
        if not hasattr(entity,"title"): raise ValueError("The Telegram reference is not a group or channel.")
        full=await self._full(client,entity)
        try: perms=await self.permission_service.get_my_permissions(account_id,entity)
        except Exception: perms=GroupPermissions(role="NOT_JOINED",can_view=True,is_member=False)
        return TelegramGroupNormalizer.normalize(entity,account_id=account_id,permissions=perms,full=full,raw_reference_type=parsed.input_type.value)
    async def _resolve_invite(self,client,account_id,parsed):
        if hasattr(client, "check_chat_invite"):
            info=await client.check_chat_invite(parsed.invite_hash)
        else:
            from telethon.tl.functions.messages import CheckChatInviteRequest
            info=await client(CheckChatInviteRequest(parsed.invite_hash))
        entity=getattr(info,"chat",None)
        already=entity is not None
        if entity is None:
            title=getattr(info,"title","Private Telegram Group"); count=getattr(info,"participants_count",None)
            from app.telegram.models.resolved_group import ResolvedGroup
            request_needed=bool(getattr(info,"request_needed",False))
            return ResolvedGroup(telegram_group_id=0,title=title,type="UNKNOWN",access_type="PRIVATE",access_state=GroupAccessState.JOIN_REQUEST_REQUIRED.value if request_needed else GroupAccessState.PRIVATE_INVITE_AVAILABLE.value,member_count=count,account_id=account_id,account_role="NOT_JOINED",permissions=GroupPermissions(role="NOT_JOINED",can_view=False,is_member=False),join_state=JoinState.REQUEST_REQUIRED.value if request_needed else JoinState.AVAILABLE.value,raw_reference_type=parsed.input_type.value,invite_hash=parsed.invite_hash)
        full=await self._full(client,entity)
        try: perms=await self.permission_service.get_my_permissions(account_id,entity)
        except Exception: perms=GroupPermissions(role="MEMBER",can_view=True,is_member=True)
        result=TelegramGroupNormalizer.normalize(entity,account_id=account_id,permissions=perms,full=full,access_state=GroupAccessState.PRIVATE_MEMBER.value,join_state=JoinState.ALREADY_JOINED.value,raw_reference_type=parsed.input_type.value)
        result.invite_hash=parsed.invite_hash; return result
    async def _full(self,client,entity):
        try:
            if hasattr(client, "get_group_full"):
                return await client.get_group_full(entity)
            from telethon.tl import functions, types
            if isinstance(entity, types.Channel):
                return await client(functions.channels.GetFullChannelRequest(entity))
            if isinstance(entity, types.Chat):
                return await client(functions.messages.GetFullChatRequest(entity.id))
        except Exception:
            return None
        return None
