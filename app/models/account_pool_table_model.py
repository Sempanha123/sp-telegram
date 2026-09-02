from __future__ import annotations

from PySide6.QtCore import Qt, Signal

from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime


ACCOUNT_POOL_COLUMNS = [
    "Select", "Account", "Username", "Enabled", "Authorization", "Connection", "Health",
    "Safety", "Invite Today", "Post Today", "Restriction", "Invite Capability",
    "Post Capability", "Groups", "Current Job", "Next Available", "Last Use", "Tags",
]


class AccountPoolTableModel(BaseTableModel):
    """Database-page model for operational account management.

    Checkbox state stores stable account ids and only the current visible page is
    affected by the header checkbox. No Telegram network action is performed by
    this model.
    """

    checkedChanged = Signal()

    def __init__(self, rows=None, parent=None):
        super().__init__(rows or [], ACCOUNT_POOL_COLUMNS, parent)
        self.checked_ids: set[int] = set()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and self.columns[index.column()] == "Select":
            row = self.rows[index.row()]
            account_id = int(row.get("id", 0) if isinstance(row, dict) else getattr(row, "id", 0) or 0)
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if account_id in self.checked_ids else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.DisplayRole:
                return ""
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignCenter)
        return super().data(index, role)

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and self.columns[index.column()] == "Select":
            return flags | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and self.columns[index.column()] == "Select" and role == Qt.ItemDataRole.CheckStateRole:
            row = self.rows[index.row()]
            account_id = int(row.get("id", 0) if isinstance(row, dict) else getattr(row, "id", 0) or 0)
            if account_id:
                if value == Qt.CheckState.Checked:
                    self.checked_ids.add(account_id)
                else:
                    self.checked_ids.discard(account_id)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                self.checkedChanged.emit()
                return True
        return False

    def set_all_visible_checked(self, checked: bool):
        ids = {
            int(row.get("id", 0) if isinstance(row, dict) else getattr(row, "id", 0) or 0)
            for row in self.rows
        }
        ids.discard(0)
        if checked:
            self.checked_ids.update(ids)
        else:
            self.checked_ids.difference_update(ids)
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, 0), [Qt.ItemDataRole.CheckStateRole])
        self.checkedChanged.emit()

    def visible_check_state(self):
        ids = {
            int(row.get("id", 0) if isinstance(row, dict) else getattr(row, "id", 0) or 0)
            for row in self.rows
        }
        ids.discard(0)
        selected = ids & self.checked_ids
        if not selected:
            return Qt.CheckState.Unchecked
        if ids and ids.issubset(self.checked_ids):
            return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked

    def checked_account_ids(self):
        return sorted(self.checked_ids)

    def clear_checked(self):
        self.checked_ids.clear()
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, 0), [Qt.ItemDataRole.CheckStateRole])
        self.checkedChanged.emit()

    def value_for_column(self, row, column):
        if not isinstance(row, dict):
            return super().value_for_column(row, column)
        mapping = {
            "Select": "",
            "Account": row.get("account") or f"Account {row.get('id', '')}",
            "Username": f"@{str(row.get('username') or '').lstrip('@')}" if row.get("username") else "—",
            "Enabled": "Yes" if int(row.get("enabled") or 0) else "No",
            "Authorization": str(row.get("authorization") or "UNKNOWN").replace("_", " ").title(),
            "Connection": str(row.get("connection") or "OFFLINE").replace("_", " ").title(),
            "Health": str(row.get("health") or "UNKNOWN").replace("_", " ").title(),
            "Safety": str(row.get("safety_state") or "NORMAL").replace("_", " ").title(),
            "Invite Today": f"{int(row.get('invite_used') or 0)}/{int(row.get('invite_limit') or 0)}" if row.get("smart_mode") else "Manual",
            "Post Today": f"{int(row.get('post_used') or 0)}/{int(row.get('post_limit') or 0)}" if row.get("smart_mode") else "Manual",
            "Restriction": str(row.get("restriction") or "NONE").replace("_", " ").title(),
            "Invite Capability": "Available" if int(row.get("invite_capability") or 0) else "Unavailable",
            "Post Capability": "Available" if int(row.get("post_capability") or 0) else "Unavailable",
            "Groups": row.get("groups") or 0,
            "Current Job": row.get("current_job") or "—",
            "Last Use": format_local_datetime(row.get("last_use")),
            "Next Available": format_local_datetime(row.get("safety_next") or row.get("cooldown_until")),
            "Tags": row.get("tags") or "—",
        }
        return mapping.get(column, row.get(column, ""))
