from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox
from app.dialogs.template_editor_dialog import TemplateEditorDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
class TemplatesPage(BaseTablePage):
    useRequested=Signal(object);toastRequested=Signal(str,str)
    def __init__(self,controller,parent=None):
        self.controller=controller;super().__init__('page_templates','Templates',BaseTableModel([],['ID','Template','Type','Default Schedule','Last Used','Updated']),'tbl_templates',[('btn_create_template','Create Template'),('btn_edit_template','Edit'),('btn_duplicate_template','Duplicate'),('btn_use_template','Use'),('btn_delete_template','Delete')],'le_search_templates',[],parent);controller.templatesChanged.connect(self._replace);self._replace(controller.refresh());self.action_buttons['btn_create_template'].clicked.connect(self.create);self.action_buttons['btn_edit_template'].clicked.connect(self.edit);self.action_buttons['btn_duplicate_template'].clicked.connect(self.duplicate);self.action_buttons['btn_use_template'].clicked.connect(self.use);self.action_buttons['btn_delete_template'].clicked.connect(self.delete)
    def _replace(self,items):self._items=list(items);self.model.replace_rows([{'ID':t.id,'Template':t.name,'Type':str(t.template_type).replace('_',' ').title(),'Default Schedule':t.default_schedule_type or '—','Last Used':t.last_used_at or '—','Updated':t.updated_at or '—'} for t in items])
    def _selected_template(self):
        row=self.selected_row();return next((t for t in self._items if row and t.id==row.get('ID')),None)
    def create(self):
        d=TemplateEditorDialog(self)
        if d.exec():data,msgs=d.data();self.controller.create(data,msgs)
    def edit(self):
        t=self._selected_template()
        if not t:return
        details=self.controller.details(t.id);d=TemplateEditorDialog(self,t,details['messages'])
        if d.exec():data,msgs=d.data();self.controller.update(t.id,data,msgs)
    def duplicate(self):
        t=self._selected_template()
        if t:self.controller.duplicate(t.id)
    def use(self):
        t=self._selected_template()
        if t:self.useRequested.emit(self.controller.details(t.id))
    def delete(self):
        t=self._selected_template()
        if t and QMessageBox.question(self,'Delete Template',f"Delete template '{t.name}'?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.delete(t.id)
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        locked=not feature_gate.has_feature(FeatureKey.TEMPLATES)
        self.set_feature_lock(locked, feature_key=FeatureKey.TEMPLATES, title="Campaign Templates", description="Reusable campaign templates are available with SP Telegram Pro or SP Telegram Ultimate. Existing templates remain visible as local history.", required_plan="PRO", feature_list=["Reusable campaign content", "Up to 10 templates on SP Telegram Pro", "Unlimited templates on SP Telegram Ultimate"], preserve_read_only=True)
        return not locked

