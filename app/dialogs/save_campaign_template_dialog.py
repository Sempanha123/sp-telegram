from __future__ import annotations
from PySide6.QtWidgets import QCheckBox,QDialog,QFormLayout,QHBoxLayout,QLineEdit,QMessageBox,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *

class SaveCampaignAsTemplateDialog(QDialog):
    def __init__(self, campaign_name='', parent=None):
        super().__init__(parent);self.setWindowTitle('Save Campaign As Template');root=QVBoxLayout(self);form=QFormLayout();self.le_template_name=QLineEdit((campaign_name or 'Campaign')+' Template');form.addRow('Template Name',self.le_template_name)
        self.chk_include_content=QCheckBox('Include Content');self.chk_include_content.setChecked(True);self.chk_include_targets=QCheckBox('Include Target Defaults');self.chk_include_targets.setChecked(False);self.chk_include_schedule=QCheckBox('Include Schedule Defaults');self.chk_include_schedule.setChecked(True)
        form.addRow(self.chk_include_content);form.addRow(self.chk_include_targets);form.addRow(self.chk_include_schedule);root.addLayout(form);row=QHBoxLayout();row.addStretch();cancel=QPushButton('Cancel');save=QPushButton('Save Template');save.setProperty('primary',True);row.addWidget(cancel);row.addWidget(save);root.addLayout(row);cancel.clicked.connect(self.reject);save.clicked.connect(self._save)
    def _save(self):
        if not self.le_template_name.text().strip():QMessageBox.warning(self,'Template','Template name is required.');return
        self.accept()
    def data(self):return {'name':self.le_template_name.text().strip(),'include_content':self.chk_include_content.isChecked(),'include_targets':self.chk_include_targets.isChecked(),'include_schedule':self.chk_include_schedule.isChecked()}

# Add compatibility attributes for older PySide6 versions
if not hasattr(SaveCampaignAsTemplateDialog, 'Accepted'):
    SaveCampaignAsTemplateDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(SaveCampaignAsTemplateDialog, 'Rejected'):
    SaveCampaignAsTemplateDialog.Rejected = QDialog.DialogCode.Rejected
