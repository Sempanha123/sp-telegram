from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from app.theme_state import is_light


class BaseTableModel(QAbstractTableModel):
    def __init__(self, rows: list[Any], columns: list[str], parent=None):
        super().__init__(parent)
        self.rows = rows
        self.columns = columns
        self.privacy_mode = False
        self.mask_telegram_ids = False
        self.mask_usernames = False
        self.mask_display_names = False
        self.mask_phone_numbers = True

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    @staticmethod
    def _mask_identifier(value: Any) -> str:
        raw = str(value or "")
        if not raw:
            return "—"
        if len(raw) <= 4:
            return "•" * len(raw)
        return f"{raw[:2]}{'•' * max(4, len(raw)-4)}{raw[-2:]}"

    @staticmethod
    def _mask_username(value: Any) -> str:
        raw = str(value or "").lstrip("@")
        if not raw:
            return "—"
        return "@" + raw[:1] + ("•" * max(5, len(raw)-1))

    def set_privacy_mode(self, enabled: bool):
        self.privacy_mode = bool(enabled)
        self.layoutChanged.emit()

    def set_display_preferences(self, *, mask_telegram_ids=None, mask_usernames=None, mask_display_names=None, mask_phone_numbers=None):
        if mask_telegram_ids is not None: self.mask_telegram_ids = bool(mask_telegram_ids)
        if mask_usernames is not None: self.mask_usernames = bool(mask_usernames)
        if mask_display_names is not None: self.mask_display_names = bool(mask_display_names)
        if mask_phone_numbers is not None: self.mask_phone_numbers = bool(mask_phone_numbers)
        self.layoutChanged.emit()

    def value_for_column(self, item: Any, column: str) -> Any:
        if isinstance(item, dict):
            value = item.get(column, "")
            if column == "Telegram ID" and (self.privacy_mode or self.mask_telegram_ids):
                return self._mask_identifier(value)
            if column == "Username" and (self.privacy_mode or self.mask_usernames):
                return self._mask_username(value)
            if column in {"Name", "Display Name", "Member"} and (self.privacy_mode or self.mask_display_names):
                raw = str(value or "")
                return " ".join((part[:1] + "•" * max(2, len(part)-1)) for part in raw.split()) if raw else "—"
            if column in {"Phone", "Phone Number"} and (self.privacy_mode or self.mask_phone_numbers):
                return self._mask_identifier(value)
            return value
        attr = column.lower().replace(" ", "_").replace("/", "_")
        return getattr(item, attr, "")

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.rows[index.row()]
        key = self.columns[index.column()]
        value = self.value_for_column(item, key)
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, bool):
                return "Yes" if value else "No"
            if isinstance(value, int) and key.startswith(("Can ", "Premium", "Blacklist", "Existing")):
                return "Yes" if value else "No"
            return str(value if value not in (None, "") else "—")
        if role == Qt.ItemDataRole.ToolTipRole:
            # Tooltips expose the full *displayed* value, never the unmasked raw identity.
            return str(value if value not in (None, "") else "—")
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.ForegroundRole:
            text = str(value).replace("_", " ").title()
            colors = {
                "success": "#047857" if is_light() else "#6EE7B7",
                "warning": "#B45309" if is_light() else "#FCD34D",
                "danger": "#BE123C" if is_light() else "#FDA4AF",
                "purple": "#6D28D9" if is_light() else "#C4B5FD",
                "info": "#0369A1" if is_light() else "#7DD3FC",
            }
            if text in {"Healthy", "Connected", "Ready", "Completed", "Success", "Eligible", "Normal"}:
                return QColor(colors["success"])
            if text in {"Cooldown", "Warning", "Paused", "Validating", "Unknown", "Watch", "Daily Limited"}:
                return QColor(colors["warning"])
            if text in {"Restricted", "Failed", "Critical", "Session Invalid", "Do Not Contact", "Recovering", "Disabled", "Safety Blocked"}:
                return QColor(colors["danger"])
            if text == "Scheduled":
                return QColor(colors["purple"])
            if text == "Running":
                return QColor(colors["info"])
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(value, (int, float)):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section] if orientation == Qt.Orientation.Horizontal else str(section + 1)
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        key = self.columns[column]
        self.layoutAboutToBeChanged.emit()
        self.rows.sort(
            key=lambda item: str(self.value_for_column(item, key) or "").lower(),
            reverse=order == Qt.SortOrder.DescendingOrder,
        )
        self.layoutChanged.emit()

    def replace_rows(self, rows: list[Any]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def row_item(self, row: int) -> Any:
        return self.rows[row]

    def row_dict(self, row: int) -> dict[str, Any]:
        item = self.rows[row]
        if isinstance(item, dict):
            return dict(item)
        if is_dataclass(item):
            data = asdict(item)
        else:
            data = dict(vars(item)) if hasattr(item, "__dict__") else {"value": item}
        # Preserve legacy display-key access for existing dialogs.
        for column in self.columns:
            data[column] = self.value_for_column(item, column)
        return data
