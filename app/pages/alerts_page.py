from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QTabWidget, QWidget

from app.dialogs.alert_details_dialog import AlertDetailsDialog
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.utils.formatters import format_local_datetime


class AlertsPage(BaseTablePage):
    def __init__(self, controller, parent=None):
        self.controller = controller
        super().__init__(
            "page_alerts", "Alerts",
            BaseTableModel(self._rows(controller.alerts()), ["Severity", "Type", "Title", "Source", "First Seen", "Last Seen", "Occurrences", "Status"]),
            "tbl_alerts",
            [("btn_open_alert", "Open"), ("btn_acknowledge_alert", "Acknowledge"), ("btn_resolve_alert", "Resolve"),
             ("btn_mute_alert", "Mute"), ("btn_mark_all_alerts_read", "Mark All Read"), ("btn_clear_resolved_alerts", "Clear Resolved")],
            "le_search_alerts", [], parent,
        )
        controller.alertsChanged.connect(lambda items: self.model.replace_rows(self._rows(items)))
        self.action_buttons["btn_open_alert"].clicked.connect(self.open_alert)
        self.action_buttons["btn_acknowledge_alert"].clicked.connect(lambda: self._action("acknowledge"))
        self.action_buttons["btn_resolve_alert"].clicked.connect(lambda: self._action("resolve"))
        self.action_buttons["btn_mute_alert"].clicked.connect(lambda: self._action("mute"))
        self.action_buttons["btn_mark_all_alerts_read"].clicked.connect(controller.mark_all_read)
        self.action_buttons["btn_clear_resolved_alerts"].clicked.connect(controller.clear_resolved)
        self.table.doubleClicked.connect(lambda _i: self.open_alert())
        self.tab_alerts = QTabWidget(); self.tab_alerts.setObjectName("tab_alerts")
        for name in ["Active", "Critical", "Warnings", "Resolved", "All"]: self.tab_alerts.addTab(QWidget(), name)
        self.tab_alerts.currentChanged.connect(self._tab_changed); self.layout().insertWidget(1, self.tab_alerts)
        self.btn_mark_alert_read = QPushButton(self); self.btn_mark_alert_read.setObjectName("btn_mark_alert_read"); self.btn_mark_alert_read.hide(); self.btn_mark_alert_read.clicked.connect(lambda: self._action("acknowledge"))

    def _rows(self, items):
        rows = []
        for a in items:
            source = a.get("source_type") or ("Account" if a.get("account_id") else "Group" if a.get("group_id") else "System")
            source_id = a.get("source_id") or a.get("account_id") or a.get("group_id") or ""
            rows.append({
                "Severity": str(a.get("severity", "INFO")).title(), "Type": str(a.get("alert_type", "SYSTEM")).replace("_", " ").title(),
                "Title": a.get("title") or "—", "Source": f"{source} {source_id}".strip(),
                "First Seen": format_local_datetime(a.get("first_seen_at") or a.get("created_at")),
                "Last Seen": format_local_datetime(a.get("last_seen_at") or a.get("created_at")),
                "Occurrences": int(a.get("occurrence_count") or 1), "Status": str(a.get("status") or "OPEN").replace("_", " ").title(),
                "_id": a.get("id"),
            })
        return rows

    def _tab_changed(self, index):
        name = self.tab_alerts.tabText(index)
        if name == "Critical": self.controller.status_filter = "ACTIVE"; self.controller.severity_filter = "CRITICAL"
        elif name == "Warnings": self.controller.status_filter = "ACTIVE"; self.controller.severity_filter = "WARNING"
        elif name == "Resolved": self.controller.status_filter = "RESOLVED"; self.controller.severity_filter = None
        elif name == "Active": self.controller.status_filter = "ACTIVE"; self.controller.severity_filter = None
        else: self.controller.status_filter = None; self.controller.severity_filter = None
        self.controller.refresh()

    def _action(self, name):
        row = self.selected_row()
        if row and row.get("_id"): getattr(self.controller, name)(int(row["_id"]))

    def open_alert(self):
        row = self.selected_row()
        if not row or not row.get("_id"): return
        alert = self.controller.get_by_id(int(row["_id"]))
        if alert: AlertDetailsDialog(alert, self).exec()
