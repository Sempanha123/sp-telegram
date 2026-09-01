from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.models.pagination import PaginationState


class JobController(QObject):
    jobsChanged = Signal(list)
    jobUpdated = Signal(int)
    toast_requested = Signal(str, str)

    def __init__(self, service, parent=None):
        super().__init__(parent); self.service = service; self.pagination = PaginationState(); self.current_items = []
        self.status_filter = None; self.search = ""

    def jobs(self): return self.refresh(emit=False)

    def refresh(self, emit=True):
        items, total = self.service.get_page(self.pagination.page, self.pagination.page_size, status=self.status_filter, search=self.search)
        self.pagination.total_items = total; self.current_items = items
        if emit: self.jobsChanged.emit(items)
        return items

    def set_status_filter(self, status: str | None):
        self.status_filter = None if not status or status == "ALL" else status; self.pagination.page = 1; return self.refresh()

    def set_search(self, search: str): self.search = search.strip(); self.pagination.page = 1; return self.refresh()
    def set_page(self, page: int): self.pagination.page = max(1, int(page)); return self.refresh()
    def set_page_size(self, size: int): self.pagination.page_size = int(size); self.pagination.page = 1; return self.refresh()
    def details(self, job_id: int): return self.service.get_details(job_id)

    def pause(self, job_id: int): return self._action(job_id, self.service.pause, "Job paused.")
    def resume(self, job_id: int): return self._action(job_id, self.service.resume, "Job returned to the safe queue.")
    def cancel(self, job_id: int): return self._action(job_id, self.service.cancel, "Job cancelled.")
    def retry(self, job_id: int):
        if self.service.retry(job_id):
            self.jobUpdated.emit(job_id); self.refresh(); self.toast_requested.emit("Job queued for a safe retry.", "Success"); return True
        self.toast_requested.emit("This job is not eligible for automatic retry. Restrictions, permission failures and ambiguous outgoing jobs require operator review.", "Warning"); return False

    def delete_history(self, job_id: int):
        try:
            ok = bool(self.service.delete_history(job_id))
            if ok: self.jobUpdated.emit(job_id); self.refresh(); self.toast_requested.emit("Job history deleted.", "Success")
            else: self.toast_requested.emit("Running or queued jobs cannot be deleted.", "Warning")
            return ok
        except Exception as exc:
            self.toast_requested.emit(str(exc) or "Could not delete job history.", "Error"); return False

    def export(self, path, jobs=None):
        try:
            self.service.export_rows(path, jobs or self.current_items); self.toast_requested.emit("Job results exported.", "Success"); return True
        except Exception as exc:
            self.toast_requested.emit(str(exc) or "Could not export jobs.", "Error"); return False

    def _action(self, job_id, func, success):
        try:
            ok = bool(func(job_id))
            if ok: self.jobUpdated.emit(job_id); self.refresh(); self.toast_requested.emit(success, "Success")
            else: self.toast_requested.emit("The selected job cannot perform that action in its current state.", "Warning")
            return ok
        except Exception as exc:
            self.toast_requested.emit(str(exc) or "Job action failed.", "Error"); return False
