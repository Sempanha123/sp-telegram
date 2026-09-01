from __future__ import annotations
from PySide6.QtCore import QObject,Signal
from app.models.pagination import PaginationState


class LogController(QObject):
    logsChanged=Signal(list); toast_requested=Signal(str,str); errorOccurred=Signal(str)
    def __init__(self,service,parent=None):
        super().__init__(parent); self.service=service; self.pagination=PaginationState(page_size=100); self.search_text=""; self.level=None; self.category=None; self.filters={}; self.current_items=[]
    def logs(self):return self.refresh(emit=False)
    def refresh(self,emit=True):
        try:
            items,total=self.service.get_page(self.pagination.page,self.pagination.page_size,self.search_text,self.level,self.category,**self.filters); self.pagination.total_items=total; self.current_items=items; self.logsChanged.emit(items) if emit else None; return items
        except Exception as exc:self._error(exc); return []
    def set_search(self,text):self.search_text=text;self.pagination.page=1;return self.refresh()
    def set_filter(self,column,value):
        if column=="Level": self.level=None if value=="All" else value
        elif column=="Category": self.category=None if value=="All" else value
        self.pagination.page=1;return self.refresh()
    def set_advanced_filters(self, **filters):
        self.filters={k:v for k,v in filters.items() if v not in (None,"")}; self.pagination.page=1; return self.refresh()
    def set_page(self,page):self.pagination.page=max(1,int(page));return self.refresh()
    def set_page_size(self,size):self.pagination.page_size=int(size);self.pagination.page=1;return self.refresh()
    def import_csv(self,path):
        try:r=self.service.import_csv(path);self.refresh();self.toast_requested.emit(f"Imported: {r['imported']} • Skipped: {r['skipped']} • Errors: {r['errors']}","Success" if not r["errors"] else "Warning");return r
        except Exception as exc:self._error(exc);return None
    def export_csv(self,path):
        try:
            self.service.export_filtered_csv(
                path, search=self.search_text, level=self.level, category=self.category, **self.filters
            )
            self.toast_requested.emit("Filtered logs exported successfully with sensitive values redacted.","Success")
            return True
        except Exception as exc:
            self._error(exc)
            return False
    def _error(self,exc):message=str(exc) or "Cannot complete the log database operation.";self.errorOccurred.emit(message);self.toast_requested.emit(message,"Error")
