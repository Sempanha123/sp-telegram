from __future__ import annotations
from PySide6.QtWidgets import QComboBox,QDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QPushButton,QTextEdit,QVBoxLayout,QMessageBox
from app.dialogs.dialog_compat import *
from app.dialogs.message_editor_dialog import MessageEditorDialog
class TemplateEditorDialog(QDialog):
    def __init__(self,parent=None,template=None,messages=None):
        super().__init__(parent);self.setWindowTitle('Campaign Template');self.resize(720,600);self.messages=[dict(m) if isinstance(m,dict) else {'message_type':m.message_type,'body':m.body,'caption':m.caption,'media_path':m.media_path,'parse_mode':m.parse_mode,'disable_link_preview':bool(m.disable_link_preview)} for m in (messages or [])];root=QVBoxLayout(self);f=QFormLayout();self.le_template_name=QLineEdit();self.txt_template_description=QTextEdit();self.txt_template_description.setMaximumHeight(90);self.cmb_template_type=QComboBox();self.cmb_template_type.addItems(['Text','Photo','Video','Document','Multi Message']);self.cmb_template_parse=QComboBox();self.cmb_template_parse.addItems(['PLAIN','MARKDOWN','HTML']);self.cmb_template_timezone=QComboBox();self.cmb_template_timezone.setEditable(True);self.cmb_template_timezone.addItems(['Asia/Phnom_Penh','UTC']);f.addRow('Name',self.le_template_name);f.addRow('Description',self.txt_template_description);f.addRow('Type',self.cmb_template_type);f.addRow('Parse Mode',self.cmb_template_parse);f.addRow('Default Timezone',self.cmb_template_timezone);root.addLayout(f);self.lst_template_messages=QListWidget();root.addWidget(self.lst_template_messages,1);row=QHBoxLayout();self.btn_template_add_message=QPushButton('Add Message');self.btn_template_edit_message=QPushButton('Edit Message');self.btn_template_remove_message=QPushButton('Remove Message');row.addWidget(self.btn_template_add_message);row.addWidget(self.btn_template_edit_message);row.addWidget(self.btn_template_remove_message);row.addStretch();root.addLayout(row);buttons=QHBoxLayout();buttons.addStretch();cancel=QPushButton('Cancel');save=QPushButton('Save Template');save.setProperty('primary',True);buttons.addWidget(cancel);buttons.addWidget(save);root.addLayout(buttons);cancel.clicked.connect(self.reject);save.clicked.connect(self._save);self.btn_template_add_message.clicked.connect(self._add);self.btn_template_edit_message.clicked.connect(self._edit);self.btn_template_remove_message.clicked.connect(self._remove)
        if template:self.le_template_name.setText(template.name or '');self.txt_template_description.setPlainText(template.description or '');self.cmb_template_type.setCurrentText(str(template.template_type or 'TEXT').replace('_',' ').title());self.cmb_template_parse.setCurrentText(template.default_parse_mode or 'PLAIN');self.cmb_template_timezone.setCurrentText(template.default_timezone or 'Asia/Phnom_Penh')
        self._refresh()
    def _refresh(self):self.lst_template_messages.clear();[self.lst_template_messages.addItem(f"{i+1}. {str(m.get('message_type') or m.get('type') or 'TEXT').replace('_',' ').title()}") for i,m in enumerate(self.messages)]
    def _add(self):
        d=MessageEditorDialog(self)
        if d.exec():self.messages.append(d.data());self._refresh()
    def _edit(self):
        r=self.lst_template_messages.currentRow()
        if r<0:return
        d=MessageEditorDialog(self,self.messages[r])
        if d.exec():self.messages[r]=d.data();self._refresh()
    def _remove(self):
        r=self.lst_template_messages.currentRow()
        if r>=0:self.messages.pop(r);self._refresh()
    def _save(self):
        if not self.le_template_name.text().strip():QMessageBox.warning(self,'Template','Template name is required.');return
        if not self.messages:QMessageBox.warning(self,'Template','Add at least one message.');return
        self.accept()
    def data(self):return {'name':self.le_template_name.text().strip(),'description':self.txt_template_description.toPlainText(),'template_type':self.cmb_template_type.currentText().upper().replace(' ','_'),'default_parse_mode':self.cmb_template_parse.currentText(),'default_timezone':self.cmb_template_timezone.currentText()},self.messages

# Add compatibility attributes for older PySide6 versions
if not hasattr(TemplateEditorDialog, 'Accepted'):
    TemplateEditorDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(TemplateEditorDialog, 'Rejected'):
    TemplateEditorDialog.Rejected = QDialog.DialogCode.Rejected
