from __future__ import annotations
import hashlib
from pathlib import Path
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import CampaignMessage
from app.utils.formatters import utc_now_iso

COLS=("id","campaign_id","position","message_type","body","caption","media_path","media_name","media_size","content_hash","parse_mode","disable_link_preview","created_at","updated_at")
def _hash(message_type,body,caption,media_path,parse_mode):
    raw='\x1f'.join(str(x or '') for x in (message_type,body,caption,Path(media_path).name if media_path else '',parse_mode));return hashlib.sha256(raw.encode()).hexdigest()
class CampaignMessageRepository(BaseRepository):
    table_name='campaign_messages';columns=COLS
    def _payload(self,campaign_id:int,pos:int,msg:dict):
        media=msg.get('media_path') or msg.get('media'); mtype=str(msg.get('message_type') or msg.get('type') or 'TEXT').upper().replace(' ','_').replace('+','WITH'); body=msg.get('body') or msg.get('text');caption=msg.get('caption');parse=str(msg.get('parse_mode') or 'PLAIN').upper(); h=msg.get('content_hash') or _hash(mtype,body,caption,media,parse)
        size=Path(media).stat().st_size if media and Path(media).is_file() else None
        return (campaign_id,pos,mtype,body,caption,media,Path(media).name if media else None,size,h,parse,int(bool(msg.get('disable_link_preview'))))
    def replace_messages(self,campaign_id:int,messages:list[dict]):
        now=utc_now_iso()
        with self.db.transaction():
            self.db.execute('DELETE FROM campaign_messages WHERE campaign_id=?',(campaign_id,))
            rows=[(*self._payload(campaign_id,i,msg),now,now) for i,msg in enumerate(messages)]
            if rows:self.db.execute_many('INSERT INTO campaign_messages(campaign_id,position,message_type,body,caption,media_path,media_name,media_size,content_hash,parse_mode,disable_link_preview,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
        return self.get_messages(campaign_id)
    def get_messages(self,campaign_id:int):return [CampaignMessage.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaign_messages WHERE campaign_id=? ORDER BY position,id",(campaign_id,))]
    def get_for_campaign(self,campaign_id:int):return self.get_messages(campaign_id)
    def create(self,campaign_id:int,msg:dict):
        row=self.db.fetch_one('SELECT COALESCE(MAX(position),-1)+1 p FROM campaign_messages WHERE campaign_id=?',(campaign_id,));pos=int(row['p']);now=utc_now_iso();payload=self._payload(campaign_id,pos,msg);cur=self.db.execute('INSERT INTO campaign_messages(campaign_id,position,message_type,body,caption,media_path,media_name,media_size,content_hash,parse_mode,disable_link_preview,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(*payload,now,now));return CampaignMessage.from_row(self.find_by_id(cur.lastrowid))
    def update(self,id:int,msg:dict):
        current=CampaignMessage.from_row(self.find_by_id(id));
        if not current:raise ValueError('Campaign message not found.')
        payload=self._payload(int(current.campaign_id),int(current.position),msg);keys=('campaign_id','position','message_type','body','caption','media_path','media_name','media_size','content_hash','parse_mode','disable_link_preview');self.update_fields(id,{**dict(zip(keys,payload)),'updated_at':utc_now_iso()});return CampaignMessage.from_row(self.find_by_id(id))
    def delete(self,id:int):
        row=CampaignMessage.from_row(self.find_by_id(id));ok=super().delete(id)
        if ok and row:self._normalize(int(row.campaign_id))
        return ok
    def duplicate(self,id:int):
        row=CampaignMessage.from_row(self.find_by_id(id));
        if not row:return None
        data={k:getattr(row,k) for k in ('message_type','body','caption','media_path','parse_mode','disable_link_preview')};return self.create(int(row.campaign_id),data)
    def reorder(self,campaign_id:int,ordered_ids:list[int]):
        with self.db.transaction():
            for pos,id in enumerate(ordered_ids):self.db.execute('UPDATE campaign_messages SET position=?,updated_at=? WHERE id=? AND campaign_id=?',(pos,utc_now_iso(),id,campaign_id))
        return self.get_messages(campaign_id)
    def _normalize(self,campaign_id:int):self.reorder(campaign_id,[int(r['id']) for r in self.db.fetch_all('SELECT id FROM campaign_messages WHERE campaign_id=? ORDER BY position,id',(campaign_id,))])
    def set_content_hash(self,id:int,value:str):return self.update_fields(id,{'content_hash':value,'updated_at':utc_now_iso()})
