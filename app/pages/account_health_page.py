from __future__ import annotations

from pathlib import Path

from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.utils.formatters import format_local_datetime
from app.widgets.avatar_delegate import AvatarDelegate


class AccountHealthPage(BaseTablePage):
    def __init__(self, controller, parent=None, *, avatar_service=None):
        self.controller = controller
        self.avatar_service = avatar_service
        columns = ["Account", "Username", "Connection", "Authorization", "Health", "Last Check", "Last Error", "Session", "Last Use"]
        rows = self._rows(controller.accounts())
        super().__init__(
            "page_account_health", "Account Health Center", BaseTableModel(rows, columns), "tbl_account_health",
            [("btn_health_check_all", "Health Check All"), ("btn_health_check_selected", "Check Selected"), ("btn_clear_resolved_health", "Clear Resolved"), ("btn_view_health_history", "View History")],
            None, [], parent,
        )
        controller.accountsChanged.connect(lambda items: self.model.replace_rows(self._rows(items)))
        if self.avatar_service is not None:
            self.table.setItemDelegateForColumn(
                0,
                AvatarDelegate(
                    self.avatar_service,
                    "account",
                    "_account_id",
                    "Account",
                    self.table,
                    account_id_attr="_account_id",
                    subtitle_column="Username",
                ),
            )
            self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setColumnHidden(columns.index("Username"), True)
        self.action_buttons["btn_health_check_all"].clicked.connect(controller.run_health_check_all)
        self.action_buttons["btn_health_check_selected"].clicked.connect(self._check_selected)
        # Historical placeholder actions are retained for object-name compatibility
        # but hidden instead of presenting dead production buttons.
        self.action_buttons["btn_clear_resolved_health"].setEnabled(False); self.action_buttons["btn_clear_resolved_health"].hide()
        self.action_buttons["btn_view_health_history"].setEnabled(False); self.action_buttons["btn_view_health_history"].hide()

    def _rows(self, items):
        result = []
        for a in items:
            session = "Demo" if getattr(a, "is_demo", 0) else ("Available" if a.session_path and Path(a.session_path).is_file() else "Missing")
            result.append({
                "Account": a.first_name or a.username or a.id,
                "Username": f"@{a.username}" if a.username else "—",
                "Connection": str(a.connection_status).replace("_", " ").title(),
                "Authorization": str(getattr(a, "authorization_status", "UNKNOWN")).replace("_", " ").title(),
                "Health": str(a.health_status).replace("_", " ").title(),
                "Last Check": format_local_datetime(a.last_health_check_at),
                "Last Error": a.last_error_message or "—",
                "Session": session,
                "Last Use": format_local_datetime(a.last_active_at),
                "_account_id": a.id,
            })
        return result

    def _check_selected(self):
        row = self.selected_row()
        if row:
            self.controller.run_health_check(int(row["_account_id"]))
