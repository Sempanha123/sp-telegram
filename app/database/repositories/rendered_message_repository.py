from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso
class RenderedMessageRepository(BaseRepository):
    table_name='campaign_rendered_messages'; columns=('id','delivery_id','rendered_text','rendered_caption','media_reference','created_at')
    def save_snapshot(self,delivery_id:int,text:str|None,caption:str|None,media_reference:str|None):
        self.db.execute('INSERT INTO campaign_rendered_messages(delivery_id,rendered_text,rendered_caption,media_reference,created_at) VALUES(?,?,?,?,?) ON CONFLICT(delivery_id) DO UPDATE SET rendered_text=excluded.rendered_text,rendered_caption=excluded.rendered_caption,media_reference=excluded.media_reference',(delivery_id,text,caption,media_reference,utc_now_iso()))
