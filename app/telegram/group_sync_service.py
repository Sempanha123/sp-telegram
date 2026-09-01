from __future__ import annotations
import logging
_LOG = logging.getLogger(__name__)
from app.telegram.group_normalizer import TelegramGroupNormalizer
from app.telegram.models.resolved_group import GroupAccessState

class TelegramGroupSyncService:
    def __init__(self,client_manager,permission_service): self.client_manager=client_manager;self.permission_service=permission_service
    async def sync(self,account_id:int,telegram_reference):
        client=await self.client_manager.get_client(account_id)
        entity=await client.get_entity(telegram_reference)
        full=None
        try:
            if hasattr(client, "get_group_full"):
                full=await client.get_group_full(entity)
            else:
                from telethon.tl import functions, types
                if isinstance(entity, types.Channel): full=await client(functions.channels.GetFullChannelRequest(entity))
                elif isinstance(entity, types.Chat): full=await client(functions.messages.GetFullChatRequest(entity.id))
        except Exception as exc:_LOG.debug("Optional Telegram group metadata lookup failed: %s", exc)
        perms=await self.permission_service.get_my_permissions(account_id,entity)
        return TelegramGroupNormalizer.normalize(entity,account_id=account_id,permissions=perms,full=full,access_state=GroupAccessState.PUBLIC_ACCESSIBLE.value if getattr(entity,"username",None) else GroupAccessState.PRIVATE_MEMBER.value,raw_reference_type="SYNC")
