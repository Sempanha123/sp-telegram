from __future__ import annotations
import hashlib
from pathlib import Path
from app.telegram.models.outgoing_message import OutgoingMessage

def build_message_fingerprint(message_type:str,text:str|None,caption:str|None,media_path:str|None,parse_mode:str='PLAIN') -> str:
    media_name=Path(media_path).name if media_path else ''
    payload='\x1f'.join([message_type or '',text or '',caption or '',media_name,parse_mode or 'PLAIN'])
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

class TelegramMessageNormalizer:
    def normalize(self,message) -> OutgoingMessage:
        get=lambda n,d=None: message.get(n,d) if isinstance(message,dict) else getattr(message,n,d)
        mtype=str(get('message_type',get('type','TEXT')) or 'TEXT').upper().replace(' ','_').replace('+','WITH')
        text=get('body',get('text'))
        caption=get('caption');media=get('media_path',get('media'));parse=str(get('parse_mode','PLAIN') or 'PLAIN').upper()
        return OutgoingMessage(mtype,text,caption,media,parse,bool(get('disable_link_preview',False)),get('content_hash') or build_message_fingerprint(mtype,text,caption,media,parse))
