from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from app.models.pagination import PaginationState


class AccountPoolController(QObject):
    rowsChanged=Signal(list); summaryChanged=Signal(dict); toast_requested=Signal(str,str)
    def __init__(self,service,parent=None):
        super().__init__(parent);self.service=service;self.pagination=PaginationState(page_size=100);self.search='';self.enabled=None;self.health=None;self.restriction=None;self.safety=None;self.current_rows=[]
    def refresh(self):
        rows,total=self.service.get_page(self.pagination.page,self.pagination.page_size,self.search,self.enabled,self.health,self.restriction,self.safety);self.pagination.total_items=total;self.pagination.clamp();self.current_rows=rows;self.rowsChanged.emit(rows);self.summaryChanged.emit(self.service.summary());return rows
    def set_search(self,text):self.search=text;self.pagination.page=1;return self.refresh()
    def set_filter(self,name,value):
        v=None if value in {None,'All'} else value
        if name=='Enabled':self.enabled=v
        elif name=='Health':self.health=v
        elif name=='Restriction':self.restriction=v
        elif name=='Safety':self.safety=v
        self.pagination.page=1;return self.refresh()
    def set_page(self,page):self.pagination.page=int(page);return self.refresh()
    def set_page_size(self,size):self.pagination.page_size=int(size);self.pagination.page=1;return self.refresh()
    def set_operations_enabled(self,ids,enabled):
        count=self.service.set_operations_enabled(ids,enabled);self.toast_requested.emit(f"{'Enabled' if enabled else 'Disabled'} {count} account(s) for new operations.",'Success' if enabled else 'Info');self.refresh();return count
    def assign_tags(self,ids,tags):count=self.service.assign_tags(ids,tags);self.toast_requested.emit(f'Updated tags for {count} account(s).','Success');self.refresh();return count
    def replace_group_assignments(self,account_id,group_ids):
        try:
            result=self.service.replace_group_assignments(account_id,group_ids)
        except Exception as exc:
            self.toast_requested.emit(str(exc) or 'Group assignments could not be saved.','Error');return None
        self.toast_requested.emit(f"Saved {len(result['selected'])} group assignment(s) locally. Telegram permission verification will run one group at a time.",'Success')
        try:self.refresh()
        except Exception as exc:self.toast_requested.emit(f"Assignments were saved, but Account Pool could not refresh: {exc}",'Warning')
        return result
    def clear_assignments(self,ids):
        try:
            count=self.service.clear_assignments(ids)
        except Exception as exc:
            self.toast_requested.emit(str(exc) or 'Account/group assignments could not be cleared.','Error');return None
        self.toast_requested.emit(f'Removed {count} local account/group assignment(s).','Info')
        try:self.refresh()
        except Exception as exc:self.toast_requested.emit(f"Assignments were cleared, but Account Pool could not refresh: {exc}",'Warning')
        return count
    def configure_safety(self,ids,values):
        count=self.service.configure_safety(ids,values);self.toast_requested.emit(f'Updated safety limits for {count} account(s).','Success');self.refresh();return count
