from __future__ import annotations
from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime
CAMPAIGN_COLUMNS=['ID','Campaign','Type','Target','Accounts','Schedule','Next Run','Success','Failed','Skipped','Last Run','Status']
class CampaignTableModel(BaseTableModel):
    def __init__(self,rows,parent=None):super().__init__(rows,CAMPAIGN_COLUMNS,parent)
    def value_for_column(self,c,cname):
        return {'ID':c.id,'Campaign':c.name,'Type':str(c.campaign_type or '').replace('_',' ').title(),'Target':getattr(c,'target_count',0) or getattr(c,'total_targets',0),'Accounts':getattr(c,'account_count',0) or (1 if getattr(c,'default_account_id',None) else 0),'Schedule':str(c.schedule_type or 'SEND_NOW').replace('_',' ').title(),'Next Run':format_local_datetime(c.next_run_at or c.send_at),'Success':getattr(c,'success_count',0),'Failed':getattr(c,'failed_count',0),'Skipped':getattr(c,'skipped_count',0),'Last Run':format_local_datetime(c.last_run_at),'Status':str(c.status or '').replace('_',' ').title()}.get(cname,'')
