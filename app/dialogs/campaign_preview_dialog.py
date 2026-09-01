from __future__ import annotations
from PySide6.QtWidgets import QComboBox,QDialog,QHBoxLayout,QLabel,QPushButton,QTextEdit,QVBoxLayout
from app.dialogs.dialog_compat import *
from app.campaign.template_renderer import CampaignTemplateRenderer
class CampaignPreviewDialog(QDialog):
    def __init__(self,details,group_lookup,parent=None):
        super().__init__(parent);self.setWindowTitle('Campaign Preview');self.resize(720,620);self.details=details;self.group_lookup=group_lookup;self.renderer=CampaignTemplateRenderer();root=QVBoxLayout(self)
        self.cmb_preview_target_group=QComboBox();self.cmb_preview_target_group.setObjectName('cmb_preview_target_group');
        for t in details.get('targets',[]):self.cmb_preview_target_group.addItem(t.group_title or str(t.group_id),t.id)
        root.addWidget(self.cmb_preview_target_group);self.lbl_preview_meta=QLabel();self.lbl_preview_meta.setWordWrap(True);root.addWidget(self.lbl_preview_meta);self.txt_preview=QTextEdit();self.txt_preview.setReadOnly(True);root.addWidget(self.txt_preview,1)
        row=QHBoxLayout();self.btn_preview_previous_target=QPushButton('Previous');self.btn_preview_previous_target.setObjectName('btn_preview_previous_target');self.btn_preview_next_target=QPushButton('Next');self.btn_preview_next_target.setObjectName('btn_preview_next_target');self.btn_preview_close=QPushButton('Close');self.btn_preview_close.setObjectName('btn_preview_close');row.addWidget(self.btn_preview_previous_target);row.addWidget(self.btn_preview_next_target);row.addStretch();row.addWidget(self.btn_preview_close);root.addLayout(row)
        self.cmb_preview_target_group.currentIndexChanged.connect(self.refresh);self.btn_preview_previous_target.clicked.connect(lambda:self.cmb_preview_target_group.setCurrentIndex(max(0,self.cmb_preview_target_group.currentIndex()-1)));self.btn_preview_next_target.clicked.connect(lambda:self.cmb_preview_target_group.setCurrentIndex(min(self.cmb_preview_target_group.count()-1,self.cmb_preview_target_group.currentIndex()+1)));self.btn_preview_close.clicked.connect(self.accept);self.refresh()
    def refresh(self):
        idx=self.cmb_preview_target_group.currentIndex();targets=self.details.get('targets',[])
        if idx<0 or idx>=len(targets):return
        t=targets[idx];group=self.group_lookup(t.group_id);camp=self.details['campaign'];parts=[]
        for i,m in enumerate(self.details.get('messages',[]),1):
            text=self.renderer.render(m.body,camp,group,camp.send_at);caption=self.renderer.render(m.caption,camp,group,camp.send_at);parts.append(f"Message {i} • {m.message_type}\n{text or caption or '[Media]'}")
        self.lbl_preview_meta.setText(f"Target: {t.group_title or t.group_id}\nPosting Account: {t.account_name or t.account_id}\nSchedule: {camp.schedule_type or 'SEND_NOW'}\nStatus: local preview — no message is sent")
        self.txt_preview.setPlainText('\n\n'.join(parts))

# Add compatibility attributes for older PySide6 versions
if not hasattr(CampaignPreviewDialog, 'Accepted'):
    CampaignPreviewDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CampaignPreviewDialog, 'Rejected'):
    CampaignPreviewDialog.Rejected = QDialog.DialogCode.Rejected
