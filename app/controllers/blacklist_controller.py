from __future__ import annotations
from PySide6.QtCore import QObject,Signal
from app.models.pagination import PaginationState
class BlacklistController(QObject):
    exclusionsChanged=Signal(list);toast_requested=Signal(str,str)
    def __init__(self,service,parent=None):super().__init__(parent);self.service=service;self.pagination=PaginationState();self.search_text="";self.current_items=[]
    def exclusions(self):return self.refresh(emit=False)
    def refresh(self,emit=True):
        try:items,total=self.service.get_page(self.pagination.page,self.pagination.page_size,self.search_text);self.pagination.total_items=total;self.current_items=items;self.exclusionsChanged.emit(items) if emit else None;return items
        except Exception as exc:self.toast_requested.emit(str(exc) or "Cannot load blacklist.","Error");return []
    def set_search(self,text):self.search_text=text;self.pagination.page=1;return self.refresh()
    def add_by_telegram_id(self,telegram_user_id,reason=None,kind="GLOBAL_BLACKLIST",target_group_id=None,notes=None):
        try:
            member=self.service.member_repository.get_by_telegram_id(int(telegram_user_id)) if self.service.member_repository else None
            if not member:raise ValueError("Member not found in the local member pool.")
            item=self.service.add_target(member.id,int(target_group_id),reason,notes) if kind=="TARGET_EXCLUSION" else self.service.add_global(member.id,reason,kind,notes);self.toast_requested.emit("Member exclusion saved.","Success");self.refresh();return item
        except Exception as exc:self.toast_requested.emit(str(exc) or "Cannot add exclusion.","Error");return None
    def edit(self,id,reason=None,notes=None):
        try:r=self.service.edit(id,reason,notes);self.toast_requested.emit("Exclusion updated.","Success");self.refresh();return r
        except Exception as exc:self.toast_requested.emit(str(exc),"Error");return None
    def remove(self,id):
        try:self.service.remove(id);self.toast_requested.emit("Exclusion removed.","Success");self.refresh();return True
        except Exception as exc:self.toast_requested.emit(str(exc),"Error");return False
    def import_csv(self,path):
        try:r=self.service.import_csv(path);self.refresh();self.toast_requested.emit(f"Imported: {r['imported']} • Skipped: {r['skipped']} • Errors: {r['errors']}","Success" if not r['errors'] else "Warning");return r
        except Exception as exc:self.toast_requested.emit(str(exc),"Error");return None
    def export_csv(self,path):
        try:self.service.export_csv(path,self.current_items);self.toast_requested.emit("Blacklist exported successfully.","Success");return True
        except Exception as exc:self.toast_requested.emit(str(exc),"Error");return False
