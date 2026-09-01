from __future__ import annotations
from dataclasses import asdict, replace
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import CampaignTemplate
from app.utils.formatters import utc_now_iso

COLS=("id","name","description","template_type","default_parse_mode","default_schedule_type","default_timezone","created_at","updated_at","last_used_at")
class TemplateRepository(BaseRepository):
    table_name="campaign_templates"; columns=COLS
    def create(self,item:CampaignTemplate,messages:list[dict]|None=None,groups:list[int]|None=None):
        now=utc_now_iso(); data=asdict(item); data.pop('id',None); data['created_at']=item.created_at or now; data['updated_at']=now
        with self.db.transaction():
            item.id=self.insert(data); self.replace_messages(item.id,messages or []); self.replace_groups(item.id,groups or [])
        return self.get_by_id(item.id)
    def update(self,item:CampaignTemplate,messages=None,groups=None):
        if item.id is None: raise ValueError('Template id is required.')
        data=asdict(item); data['updated_at']=utc_now_iso()
        with self.db.transaction():
            self.update_fields(item.id,data)
            if messages is not None:self.replace_messages(item.id,messages)
            if groups is not None:self.replace_groups(item.id,groups)
        return self.get_by_id(item.id)
    def duplicate(self,id:int):
        src=self.get_by_id(id)
        if not src:return None
        msgs=self.get_messages(id); groups=[int(r['group_id']) for r in self.db.fetch_all('SELECT group_id FROM template_groups WHERE template_id=?',(id,))]
        return self.create(replace(src,id=None,name=f'{src.name} Copy',created_at=None,updated_at=None,last_used_at=None),msgs,groups)
    def delete(self,id:int): return super().delete(id)
    def get_all(self): return [CampaignTemplate.from_row(r) for r in self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM campaign_templates ORDER BY updated_at DESC")]
    def get_by_id(self,id:int): return CampaignTemplate.from_row(self.find_by_id(id))
    def mark_used(self,id:int): return self.update_fields(id,{'last_used_at':utc_now_iso(),'updated_at':utc_now_iso()})
    def replace_messages(self,id:int,messages:list[dict]):
        now=utc_now_iso(); self.db.execute('DELETE FROM campaign_template_messages WHERE template_id=?',(id,))
        self.db.execute_many('INSERT INTO campaign_template_messages(template_id,position,message_type,body,caption,media_path,parse_mode,disable_link_preview,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',[(id,i,str(m.get('message_type') or m.get('type') or 'TEXT').upper().replace(' ','_'),m.get('body'),m.get('caption'),m.get('media_path') or m.get('media'),str(m.get('parse_mode') or 'PLAIN').upper(),int(bool(m.get('disable_link_preview'))),now,now) for i,m in enumerate(messages)]) if messages else None
    def get_messages(self,id:int): return [dict(r) for r in self.db.fetch_all('SELECT id,template_id,position,message_type,body,caption,media_path,parse_mode,disable_link_preview FROM campaign_template_messages WHERE template_id=? ORDER BY position',(id,))]
    def replace_groups(self,id:int,groups:list[int]):
        self.db.execute('DELETE FROM template_groups WHERE template_id=?',(id,)); self.db.execute_many('INSERT INTO template_groups(template_id,group_id) VALUES(?,?)',[(id,int(g)) for g in groups]) if groups else None
