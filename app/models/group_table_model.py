from __future__ import annotations
from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime,metadata_freshness
GROUP_COLUMNS=["Select","ID","Group","Username","Type","Access","Members","Primary Account","Role","Post","Invite","Manage","Source","Target","Managed","Last Sync","Freshness","Status"]
class GroupTableModel(BaseTableModel):
    def __init__(self,rows,parent=None):super().__init__(rows,GROUP_COLUMNS,parent); self.privacy_mode=False
    def set_privacy_mode(self,enabled:bool): self.privacy_mode=bool(enabled); self.layoutChanged.emit()
    def value_for_column(self,g,c):
        def cap(v): return "—" if v is None else bool(v)
        return {"Select":"","ID":"••••••" if self.privacy_mode and g.telegram_group_id else (g.telegram_group_id or "—"),"Group":g.title,"Username":"@••••••" if self.privacy_mode and g.username else (f"@{g.username}" if g.username else "—"),"Type":g.group_type.replace("_"," ").title(),"Access":(g.access_state if g.access_state not in {None,"UNKNOWN"} else g.access_type).replace("_"," ").title(),"Members":g.member_count,"Primary Account":getattr(g,"account_name","") or "—","Role":getattr(g,"role","UNKNOWN").replace("_"," ").title(),"Post":cap(getattr(g,"can_post",None)),"Invite":cap(getattr(g,"can_invite",None)),"Manage":cap(getattr(g,"can_manage",None)),"Source":bool(g.is_source),"Target":bool(g.is_target),"Managed":bool(g.is_managed),"Last Sync":format_local_datetime(g.last_sync_at),"Freshness":metadata_freshness(g.last_sync_at),"Status":g.status.replace("_"," ").title()}.get(c,"")
