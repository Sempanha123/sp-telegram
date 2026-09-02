from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox, QPushButton, QTabWidget, QWidget

from app.dialogs.job_details_dialog import JobDetailsDialog
from app.dialogs.job_result_dialog import JobResultDialog
from app.models.job_table_model import JobTableModel
from app.pages.base_table_page import BaseTablePage


class JobsPage(BaseTablePage):
    TAB_STATUS = {"Active": "RUNNING", "Queued": "QUEUED", "Paused": "PAUSED", "Completed": "COMPLETED", "Failed": "FAILED", "All": None}

    def __init__(self, controller, parent=None):
        self.controller = controller
        super().__init__(
            "page_jobs", "Jobs", JobTableModel(controller.jobs()), "tbl_jobs",
            [("btn_refresh_jobs", "Refresh"), ("btn_pause_selected_job", "Pause"), ("btn_resume_selected_job", "Resume"),
             ("btn_cancel_selected_job", "Cancel"), ("btn_retry_failed_job", "Retry"), ("btn_view_job_details", "Details"),
             ("btn_view_job_result", "Result"), ("btn_export_job_results", "Export"), ("btn_jobs_more", "More ▾")],
            "le_search_jobs", [], parent,
        )
        self.enable_database_mode(controller.pagination)
        self.searchDebounced.connect(controller.set_search); self.pageChanged.connect(controller.set_page); self.pageSizeChanged.connect(controller.set_page_size)
        controller.jobsChanged.connect(lambda items: (self.model.replace_rows(items), self.update_pagination(controller.pagination)))
        self.action_buttons["btn_refresh_jobs"].clicked.connect(controller.refresh)
        self.action_buttons["btn_pause_selected_job"].clicked.connect(lambda: self._selected_action("pause"))
        self.action_buttons["btn_resume_selected_job"].clicked.connect(lambda: self._selected_action("resume"))
        self.action_buttons["btn_cancel_selected_job"].clicked.connect(lambda: self._selected_action("cancel"))
        self.action_buttons["btn_retry_failed_job"].clicked.connect(lambda: self._selected_action("retry"))
        self.action_buttons["btn_view_job_details"].clicked.connect(self._details)
        self.action_buttons["btn_view_job_result"].clicked.connect(self._result)
        self.action_buttons["btn_export_job_results"].clicked.connect(self._export)
        self.action_buttons["btn_jobs_more"].clicked.connect(self._show_more)
        for key in ("btn_pause_selected_job", "btn_resume_selected_job", "btn_cancel_selected_job", "btn_retry_failed_job", "btn_export_job_results"):
            self.action_buttons[key].hide()
        self.table.doubleClicked.connect(lambda _i: self._details())
        self.table.selectionModel().selectionChanged.connect(self._refresh_job_actions)
        self.model.modelReset.connect(self._refresh_job_actions)
        self.tab_jobs = QTabWidget(); self.tab_jobs.setObjectName("tab_jobs")
        for name in self.TAB_STATUS: self.tab_jobs.addTab(QWidget(), name)
        self.tab_jobs.currentChanged.connect(self._tab_changed); self.layout().insertWidget(1, self.tab_jobs)
        # Compatibility with the Phase-1 object contract. "Cancel" is the Phase-7 user-facing action.
        self.btn_stop_selected_job = QPushButton(self); self.btn_stop_selected_job.setObjectName("btn_stop_selected_job"); self.btn_stop_selected_job.hide(); self.btn_stop_selected_job.clicked.connect(lambda: self._selected_action("cancel"))
        self._refresh_job_actions()

    def _refresh_job_actions(self, *_args):
        item = self.selected_item()
        status = str(getattr(item, "status", "") or "").upper()
        selected = item is not None
        self.action_buttons["btn_view_job_details"].setEnabled(selected)
        self.action_buttons["btn_view_job_result"].setEnabled(selected)
        self.action_buttons["btn_pause_selected_job"].setEnabled(status == "RUNNING")
        self.action_buttons["btn_resume_selected_job"].setEnabled(status == "PAUSED")
        self.action_buttons["btn_cancel_selected_job"].setEnabled(status in {"QUEUED", "RUNNING", "PAUSED"})
        self.action_buttons["btn_retry_failed_job"].setEnabled(status == "FAILED")
        self.action_buttons["btn_export_job_results"].setEnabled(bool(self.model.rows))

    def _show_more(self):
        menu = QMenu(self.action_buttons["btn_jobs_more"])
        for key in ("btn_pause_selected_job", "btn_resume_selected_job", "btn_retry_failed_job", "btn_export_job_results"):
            button = self.action_buttons[key]
            action = menu.addAction(button.text())
            action.setEnabled(button.isEnabled())
            action.triggered.connect(lambda _checked=False, b=button: b.click())
        menu.addSeparator()
        cancel = self.action_buttons["btn_cancel_selected_job"]
        action = menu.addAction(cancel.text())
        action.setEnabled(cancel.isEnabled())
        action.triggered.connect(lambda _checked=False: cancel.click())
        menu.exec(self.action_buttons["btn_jobs_more"].mapToGlobal(self.action_buttons["btn_jobs_more"].rect().bottomLeft()))

    def _tab_changed(self, index: int):
        name = self.tab_jobs.tabText(index); self.controller.set_status_filter(self.TAB_STATUS.get(name))

    def _selected_action(self, action: str):
        item = self.selected_item()
        if not item or not item.id: return
        if action == "cancel" and QMessageBox.question(self, "Cancel Job", f"Cancel job #{item.id}?\n\nCompleted work remains recorded.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        getattr(self.controller, action)(int(item.id))

    def _details(self):
        item = self.selected_item()
        if item and item.id:
            details = self.controller.details(int(item.id))
            if details: JobDetailsDialog(details, self).exec()

    def _result(self):
        item = self.selected_item()
        if not item or not item.id:
            return
        details = self.controller.details(int(item.id))
        if not details:
            return
        dialog = JobResultDialog(details.get("job"), details.get("items", []), self)
        dialog.retryRequested.connect(lambda jid: (self.controller.retry(jid), dialog.accept()))
        dialog.deleteRequested.connect(lambda jid: self._delete_history(jid))
        dialog.exec()

    def _delete_history(self, job_id: int):
        if QMessageBox.question(self, "Delete Job History", f"Delete finished history for job #{job_id}?\n\nRunning state is never touched.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if self.controller.delete_history(job_id):
            self.controller.refresh()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Job Results", "jobs.csv", "CSV Files (*.csv)")
        if path: self.controller.export(path, self.controller.current_items)
