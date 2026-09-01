from __future__ import annotations
from datetime import datetime
from app.telegram.models.outgoing_message import OutgoingMessage
from app.telegram.models.send_result import SendResult
from app.utils.formatters import utc_now_iso

class TelegramMessagingService:
    """Authorized group/channel posting only. No user/Member Pool recipient API exists here."""
    def __init__(self,client_manager,error_handler):self.client_manager=client_manager;self.error_handler=error_handler
    async def _client(self,account_id:int):
        client=await self.client_manager.get_client(account_id)
        if client is None:raise RuntimeError('Posting account is not connected.')
        if not client.is_connected():await self.client_manager.connect(account_id)
        if not await client.is_user_authorized():raise RuntimeError('Posting account requires Telegram login.')
        return client
    async def send_text(self,account_id:int,peer,text:str,*,parse_mode=None,disable_link_preview=False,schedule=None):
        client=await self._client(account_id);return await client.send_message(peer,text,parse_mode=parse_mode,link_preview=not disable_link_preview,schedule=schedule)
    async def send_photo(self,account_id:int,peer,path:str,*,caption=None,parse_mode=None,schedule=None):
        client=await self._client(account_id);return await client.send_file(peer,path,caption=caption,parse_mode=parse_mode,schedule=schedule)
    async def send_video(self,account_id:int,peer,path:str,*,caption=None,parse_mode=None,schedule=None):return await self.send_photo(account_id,peer,path,caption=caption,parse_mode=parse_mode,schedule=schedule)
    async def send_document(self,account_id:int,peer,path:str,*,caption=None,parse_mode=None,schedule=None):
        client=await self._client(account_id);return await client.send_file(peer,path,caption=caption,parse_mode=parse_mode,force_document=True,schedule=schedule)
    async def send_message(self,account_id:int,group_id:int,peer,message:OutgoingMessage,*,schedule_at:datetime|None=None)->SendResult:
        parse=None if message.parse_mode=='PLAIN' else message.parse_mode.lower()
        try:
            if message.message_type=='TEXT':result=await self.send_text(account_id,peer,message.text or '',parse_mode=parse,disable_link_preview=message.disable_link_preview,schedule=schedule_at)
            elif message.message_type=='DOCUMENT':result=await self.send_document(account_id,peer,message.media_path or '',caption=message.caption,parse_mode=parse,schedule=schedule_at)
            elif message.message_type in {'PHOTO','VIDEO','MEDIA_WITH_CAPTION','MEDIAWITH_CAPTION'}:result=await self.send_photo(account_id,peer,message.media_path or '',caption=message.caption,parse_mode=parse,schedule=schedule_at)
            else:raise ValueError('Unsupported campaign message type.')
            mid=str(getattr(result,'id','')) or None
            return SendResult(True,group_id,account_id,mid,utc_now_iso() if schedule_at is None else None,schedule_at is not None)
        except Exception as exc:
            err=self.error_handler.classify(exc);return SendResult(False,group_id,account_id,error_code=err.code,error_message=err.message,wait_seconds=err.wait_seconds)
    async def edit_message(self,account_id:int,peer,message_id:int,text:str):
        client=await self._client(account_id);return await client.edit_message(peer,message_id,text)
    async def delete_message(self,account_id:int,peer,message_id:int):
        client=await self._client(account_id);return await client.delete_messages(peer,[message_id])
