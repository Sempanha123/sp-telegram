from __future__ import annotations
from datetime import datetime

class TelegramScheduleService:
    """Native Telegram scheduled-message queue reconciliation for one mapped managed group."""
    def __init__(self,client_manager,error_handler):self.client_manager=client_manager;self.error_handler=error_handler
    async def _client_peer(self,account_id:int,peer):
        client=await self.client_manager.get_client(account_id)
        if client is None:raise RuntimeError('Posting account is not connected.')
        if not client.is_connected():await self.client_manager.connect(account_id)
        return client,peer
    async def list_scheduled(self,account_id:int,peer):
        client,peer=await self._client_peer(account_id,peer)
        if hasattr(client,'get_scheduled_messages'):return await client.get_scheduled_messages(peer)
        try:
            from telethon.tl.functions.messages import GetScheduledHistoryRequest
            result=await client(GetScheduledHistoryRequest(peer=peer,hash=0));return list(getattr(result,'messages',[]) or [])
        except ImportError:return []
    async def send_now(self,account_id:int,peer,message_ids:list[int]):
        client,peer=await self._client_peer(account_id,peer)
        if hasattr(client,'send_scheduled_messages'):return await client.send_scheduled_messages(peer,message_ids)
        from telethon.tl.functions.messages import SendScheduledMessagesRequest
        return await client(SendScheduledMessagesRequest(peer=peer,id=message_ids))
    async def cancel(self,account_id:int,peer,message_ids:list[int]):
        client,peer=await self._client_peer(account_id,peer)
        if hasattr(client,'delete_scheduled_messages'):return await client.delete_scheduled_messages(peer,message_ids)
        from telethon.tl.functions.messages import DeleteScheduledMessagesRequest
        return await client(DeleteScheduledMessagesRequest(peer=peer,id=message_ids))
