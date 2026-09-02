from __future__ import annotations
from PySide6.QtWidgets import QFileDialog,QInputDialog,QMessageBox,QTabBar
from app.dialogs.add_blacklist_dialog import AddBlacklistDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage

class BlacklistPage(BaseTablePage):
    def __init__(self,controller,parent=None):
        self.controller=controller;self._tab_kind=None;rows=self._rows(controller.exclusions())
        super().__init__("page_blacklist","Blacklist & Exclusions",BaseTableModel(rows,["ID","Telegram ID","Username","Name","Exclusion Type","Target","Reason","Created","Notes"]),"tbl_blacklist",[("btn_add_blacklist","Add"),("btn_edit_blacklist","Edit"),("btn_remove_blacklist","Remove"),("btn_import_blacklist","Import"),("btn_export_blacklist","Export"),("btn_clear_blacklist_filter","Clear Filter")],"le_search_blacklist",[],parent);self.enable_database_mode(controller.pagination)
        self.tabs=QTabBar();self.tabs.setObjectName("tab_blacklist_types")
        for label in ["Global","Do Not Contact","Target-Specific","Other Exclusions"]:self.tabs.addTab(label)
        self.layout().insertWidget(2,self.tabs);self.tabs.currentChanged.connect(self._tab_changed);self.searchDebounced.connect(controller.set_search);controller.exclusionsChanged.connect(self._replace);self.pageChanged.connect(lambda p:setattr(controller.pagination,"page",p) or controller.refresh());self.pageSizeChanged.connect(lambda n:(setattr(controller.pagination,"page_size",n),setattr(controller.pagination,"page",1),controller.refresh()))
        self.action_buttons["btn_add_blacklist"].clicked.connect(self.add);self.action_buttons["btn_edit_blacklist"].clicked.connect(self.edit);self.action_buttons["btn_remove_blacklist"].clicked.connect(self.remove);self.action_buttons["btn_import_blacklist"].clicked.connect(self.import_csv);self.action_buttons["btn_export_blacklist"].clicked.connect(self.export_csv);self.action_buttons["btn_clear_blacklist_filter"].clicked.connect(lambda:self.search.clear() if self.search else None)
        # Search clearing now lives beside the search field on every table page.
        self.action_buttons["btn_clear_blacklist_filter"].hide()
    def _tab_changed(self,index):self._tab_kind=["GLOBAL_BLACKLIST","DO_NOT_CONTACT","TARGET_EXCLUSION","OTHER"][index];self._replace(self.controller.current_items)
    def _filter(self,items):
        if self._tab_kind is None:self._tab_kind="GLOBAL_BLACKLIST"
        out=[]
        for r in items:
            d=dict(r);kind=d.get("exclusion_type")
            if self._tab_kind=="OTHER":
                if kind in {"GLOBAL_BLACKLIST","DO_NOT_CONTACT","TARGET_EXCLUSION"}:continue
            elif kind!=self._tab_kind:continue
            out.append(r)
        return out
    def _rows(self,items):
        out=[]
        for r in self._filter(items):
            d=dict(r);out.append({"ID":d.get("id"),"Telegram ID":d.get("telegram_user_id"),"Username":f"@{d.get('username')}" if d.get("username") else "—","Name":" ".join(x for x in [d.get("first_name"),d.get("last_name")] if x) or "—","Exclusion Type":str(d.get("exclusion_type") or "").replace("_"," ").title(),"Target":d.get("target_title") or "Global","Reason":d.get("reason") or "—","Created":d.get("created_at"),"Notes":d.get("notes") or "—"})
        return out
    def _replace(self,items):self.model.replace_rows(self._rows(items));self.update_pagination(self.controller.pagination)
    def add(self):AddBlacklistDialog(self.controller,self).exec()
    def edit(self):
        row=self.selected_row()
        if not row:return
        reason,ok=QInputDialog.getText(self,"Edit Exclusion","Reason",text="" if row.get("Reason")=="—" else str(row.get("Reason") or ""))
        if ok:self.controller.edit(int(row["ID"]),reason,None)
    def remove(self):
        row=self.selected_row()
        if row and QMessageBox.question(self,"Remove Exclusion","Remove this member exclusion?")==QMessageBox.StandardButton.Yes:self.controller.remove(int(row["ID"]))
    def import_csv(self):
        path,_=QFileDialog.getOpenFileName(self,"Import Blacklist","","CSV Files (*.csv)")
        if path:self.controller.import_csv(path)
    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Blacklist","blacklist.csv","CSV Files (*.csv)")
        if path:self.controller.export_csv(path)
