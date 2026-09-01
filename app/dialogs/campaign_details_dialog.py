from __future__ import annotations
from PySide6.QtWidgets import QDialog,QFormLayout,QLabel,QPushButton,QTabWidget,QTableView,QTextEdit,QVBoxLayout,QWidget
from app.dialogs.dialog_compat import *
from app.models.base_table_model import BaseTableModel
from app.utils.table_layout_manager import TableLayoutManager, ColumnLayout
from app.utils.formatters import format_local_datetime
class CampaignDetailsDialog(QDialog):
    def __init__(self,details,parent=None):
        super().__init__(parent);self._table_layout=TableLayoutManager(self);self.setWindowTitle('Campaign Details');self.resize(900,680);root=QVBoxLayout(self);tabs=QTabWidget();root.addWidget(tabs,1);c=details['campaign']
        overview=QWidget();f=QFormLayout(overview)
        for label,value in [('Name',c.name),('Type',c.campaign_type),('Status',c.status),('Targets',len(details.get('targets',[]))),('Messages',len(details.get('messages',[]))),('Created',format_local_datetime(c.created_at)),('Next Run',format_local_datetime(c.next_run_at or c.send_at)),('Last Run',format_local_datetime(c.last_run_at)),('Success',c.success_count),('Failed',c.failed_count),('Skipped',c.skipped_count)]:f.addRow(label,QLabel(str(value if value not in {None,''} else '—')))
        tabs.addTab(overview,'Overview')
        content=QWidget();cl=QVBoxLayout(content);txt=QTextEdit();txt.setReadOnly(True);txt.setPlainText('\n\n'.join(f"#{i+1} {m.message_type}\n{m.body or m.caption or '[Media]'}" for i,m in enumerate(details.get('messages',[]))));cl.addWidget(txt);self.btn_campaign_content_preview=QPushButton('Preview');self.btn_campaign_content_preview.setObjectName('btn_campaign_content_preview');cl.addWidget(self.btn_campaign_content_preview);tabs.addTab(content,'Content')
        tr=QWidget();tl=QVBoxLayout(tr);rows=[{'Group':t.group_title or t.group_id,'Account':t.account_name or t.account_id,'Scheduled':t.scheduled_at or '—','Sent':t.sent_at or '—','Message ID':t.telegram_message_id or t.telegram_scheduled_message_id or '—','Result':t.status,'Error':t.last_error_message or '—'} for t in details.get('targets',[])];table=QTableView();table.setModel(BaseTableModel(rows,['Group','Account','Scheduled','Sent','Message ID','Result','Error']));self._table_layout.apply(table,['Group','Account','Scheduled','Sent','Message ID','Result','Error'],overrides={'Group':ColumnLayout(190,140,'stretch'),'Scheduled':ColumnLayout(175,145),'Sent':ColumnLayout(175,145),'Error':ColumnLayout(280,170,'stretch')});tl.addWidget(table);tabs.addTab(tr,'Targets')
        sched=QWidget();sf=QFormLayout(sched);sf.addRow('Type',QLabel(str(c.schedule_type or 'SEND_NOW')));sf.addRow('Send/Next',QLabel(format_local_datetime(c.next_run_at or c.send_at)));sf.addRow('Timezone',QLabel(str(c.timezone or 'UTC')));sf.addRow('Repeat Rule',QLabel(str(c.repeat_rule or '—')));tabs.addTab(sched,'Schedule')
        results=QWidget();rl=QVBoxLayout(results);dr=[{'Status':d.status,'Target ID':d.campaign_target_id,'Message ID':d.campaign_message_id,'Telegram ID':d.telegram_message_id or d.telegram_scheduled_message_id or '—','Scheduled':d.scheduled_for or '—','Sent':d.sent_at or '—'} for d in details.get('deliveries',[])];dt=QTableView();dt.setModel(BaseTableModel(dr,['Status','Target ID','Message ID','Telegram ID','Scheduled','Sent']));self._table_layout.apply(dt,['Status','Target ID','Message ID','Telegram ID','Scheduled','Sent']);rl.addWidget(dt);tabs.addTab(results,'Results')
        for name in ['Activity','Errors']:
            w=QWidget();l=QVBoxLayout(w);l.addWidget(QLabel('Campaign audit entries are available in Logs and Jobs.'));l.addStretch();tabs.addTab(w,name)
        b=QPushButton('Close');b.clicked.connect(self.accept);root.addWidget(b)

# Add compatibility attributes for older PySide6 versions
if not hasattr(CampaignDetailsDialog, 'Accepted'):
    CampaignDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CampaignDetailsDialog, 'Rejected'):
    CampaignDetailsDialog.Rejected = QDialog.DialogCode.Rejected
