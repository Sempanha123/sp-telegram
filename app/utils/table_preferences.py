from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QObject, QSettings, Signal, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHeaderView, QMenu, QTableView


GLOBAL_COLUMN_KEYS = {
    "Telegram ID": "show_telegram_id",
    "Username": "show_username",
    "Name": "show_display_name",
    "Display Name": "show_display_name",
    "Member": "show_display_name",
    "Sources": "show_sources",
    "Source": "show_sources",
    "Tags": "show_tags",
    "First Seen": "show_first_seen",
    "Joined / First Seen": "show_first_seen",
    "Last Seen": "show_last_seen",
    "Bot": "show_bot",
    "Premium": "show_premium",
}

GLOBAL_DEFAULTS = {
    "show_telegram_id": True,
    "show_username": True,
    "show_display_name": True,
    "show_sources": True,
    "show_tags": True,
    "show_first_seen": True,
    "show_last_seen": True,
    "show_bot": False,
    "show_premium": False,
    "mask_telegram_ids": False,
    "mask_usernames": False,
    "mask_display_names": False,
    "mask_phone_numbers": True,
    "rows_per_page": 100,
    "row_density": "Comfortable",
    "auto_fit_first_open": False,
    "auto_fit_on_refresh": False,
    "remember_column_widths": True,
    "remember_column_order": True,
    "smooth_scrolling": True,
    "vertical_scroll_step": 16,
    "horizontal_scroll_step": 28,
    "default_target_id": 0,
    "require_eligibility": "ELIGIBLE",
    "require_consent": "APPROVED",
    "exclude_blacklist": True,
    "exclude_do_not_contact": True,
    "exclude_existing": True,
    "exclude_bots": True,
    "remove_orphan_automatically": False,
}


def _bool(value, default=False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class TableLayoutDefaults:
    visibility: dict[str, bool]
    widths: dict[str, int]


class TablePreferenceManager(QObject):
    """Reusable QSettings-backed table-display preferences.

    Global identity preferences act as defaults.  A table can override any
    column through the header context menu.  Header order/widths are persisted
    using QHeaderView.saveState(), so this manager never touches business data.
    """

    preferencesChanged = Signal()

    def __init__(self, settings: QSettings | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings or QSettings()
        self._registered: dict[str, tuple[QTableView, list[str], TableLayoutDefaults]] = {}

    @staticmethod
    def global_key(name: str) -> str:
        return f"ui/table_display/{name}"

    def global_value(self, name: str, default=None):
        if default is None:
            default = GLOBAL_DEFAULTS.get(name)
        value = self.settings.value(self.global_key(name), default)
        if isinstance(default, bool):
            return _bool(value, default)
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return int(default)
        return value

    def set_global_value(self, name: str, value) -> None:
        self.settings.setValue(self.global_key(name), value)
        self.preferencesChanged.emit()

    def global_column_visible(self, column: str, default=True) -> bool:
        key = GLOBAL_COLUMN_KEYS.get(column)
        return bool(self.global_value(key, default)) if key else bool(default)

    @staticmethod
    def table_key(table: QTableView | str) -> str:
        name = table if isinstance(table, str) else table.objectName()
        return str(name or "table")

    def _visibility_key(self, table_key: str, column: str) -> str:
        return f"tables/{table_key}/column_visibility/{column}"

    def _header_key(self, table_key: str) -> str:
        return f"tables/{table_key}/header_state"

    def _widths_key(self, table_key: str) -> str:
        return f"tables/{table_key}/column_widths"

    def _order_key(self, table_key: str) -> str:
        return f"tables/{table_key}/column_order"

    def has_saved_layout(self, table_key: str) -> bool:
        return any(
            self.settings.contains(key)
            for key in (
                self._header_key(table_key),
                self._widths_key(table_key),
                self._order_key(table_key),
                f"tables/{table_key}/header",
            )
        )

    def column_visible(self, table_key: str, column: str, default=True) -> bool:
        global_default = self.global_column_visible(column, default)
        raw = self.settings.value(self._visibility_key(table_key, column), None)
        if raw is None:
            return global_default
        return _bool(raw, global_default)

    def set_column_visible(self, table_key: str, column: str, visible: bool) -> None:
        self.settings.setValue(self._visibility_key(table_key, column), bool(visible))
        registered = self._registered.get(table_key)
        if registered:
            table, columns, _defaults = registered
            if column in columns:
                table.setColumnHidden(columns.index(column), not bool(visible))
        self.preferencesChanged.emit()

    def register(
        self,
        table: QTableView,
        columns: Iterable[str],
        *,
        default_visibility: dict[str, bool] | None = None,
        default_widths: dict[str, int] | None = None,
    ) -> None:
        key = self.table_key(table)
        cols = list(columns)
        defaults = TableLayoutDefaults(dict(default_visibility or {}), dict(default_widths or {}))
        self._registered[key] = (table, cols, defaults)
        self.apply(table, cols, defaults=defaults)
        header = table.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(lambda pos, k=key: self.show_header_menu(k, pos))
        header.sectionResized.connect(lambda *_args, k=key: self.save_header_state(k))
        header.sectionMoved.connect(lambda *_args, k=key: self.save_header_state(k))

    def apply(self, table: QTableView, columns: list[str], *, defaults: TableLayoutDefaults | None = None) -> None:
        key = self.table_key(table)
        defaults = defaults or TableLayoutDefaults({}, {})
        for idx, column in enumerate(columns):
            visible_default = defaults.visibility.get(column, self.global_column_visible(column, True))
            table.setColumnHidden(idx, not self.column_visible(key, column, visible_default))
            width = int(defaults.widths.get(column, 0) or 0)
            if width > 0 and not self.settings.contains(self._header_key(key)) and not self.settings.contains(self._widths_key(key)):
                table.setColumnWidth(idx, width)
        state = self.settings.value(self._header_key(key))
        if state:
            # Legacy combined state is read for upgrade compatibility only.
            table.horizontalHeader().restoreState(state)
        order = self.settings.value(self._order_key(key), None)
        if order:
            try:
                logical_order=[int(x) for x in list(order)]
                header=table.horizontalHeader()
                for visual, logical in enumerate(logical_order):
                    current=header.visualIndex(logical)
                    if current>=0 and current!=visual:header.moveSection(current,visual)
            except Exception:
                pass
        widths = self.settings.value(self._widths_key(key), None)
        if widths:
            try:
                for idx,width in enumerate(list(widths)):
                    if idx < len(columns) and int(width)>0:table.setColumnWidth(idx,int(width))
            except Exception:
                pass
        # Visibility is restored explicitly after state/order/widths so current
        # global/per-table preferences remain authoritative.
        for idx, column in enumerate(columns):
            visible_default = defaults.visibility.get(column, self.global_column_visible(column, True))
            table.setColumnHidden(idx, not self.column_visible(key, column, visible_default))

    def save_header_state(self, table_key: str) -> None:
        registered = self._registered.get(table_key)
        if not registered:
            return
        table, columns, _defaults = registered
        header=table.horizontalHeader()
        remember_widths=bool(self.global_value("remember_column_widths",True))
        remember_order=bool(self.global_value("remember_column_order",True))
        if remember_widths:
            self.settings.setValue(self._widths_key(table_key),[int(table.columnWidth(i)) for i in range(len(columns))])
        else:
            self.settings.remove(self._widths_key(table_key))
        if remember_order:
            order=[int(header.logicalIndex(v)) for v in range(header.count()) if header.logicalIndex(v)>=0]
            self.settings.setValue(self._order_key(table_key),order)
        else:
            self.settings.remove(self._order_key(table_key))
        # Preserve the legacy combined key only when both dimensions are enabled.
        if remember_widths and remember_order:
            self.settings.setValue(self._header_key(table_key),header.saveState())
        else:
            self.settings.remove(self._header_key(table_key))

    def reset_table(self, table_key: str) -> None:
        prefix = f"tables/{table_key}/"
        self.settings.beginGroup(prefix.rstrip("/"))
        self.settings.remove("")
        self.settings.endGroup()
        registered = self._registered.get(table_key)
        if registered:
            table, columns, defaults = registered
            header = table.horizontalHeader()
            # Return visual order to logical order.
            for logical in range(len(columns)):
                visual = header.visualIndex(logical)
                if visual != logical:
                    header.moveSection(visual, logical)
            self.apply(table, columns, defaults=defaults)
        self.preferencesChanged.emit()

    def reset_all_tables(self) -> None:
        self.settings.beginGroup("tables")
        self.settings.remove("")
        self.settings.endGroup()
        for key in list(self._registered):
            self.reset_table(key)
        self.preferencesChanged.emit()

    def auto_fit(self, table_key: str, *, sample_rows: int = 100, max_width: int = 420) -> None:
        registered = self._registered.get(table_key)
        if not registered:
            return
        table, columns, defaults = registered
        model = table.model()
        fm = table.fontMetrics()
        header_fm = table.horizontalHeader().fontMetrics()
        row_count = min(max(0, model.rowCount()), max(1, int(sample_rows)))
        for logical, name in enumerate(columns):
            if table.isColumnHidden(logical):
                continue
            width = header_fm.horizontalAdvance(str(name)) + 34
            for row in range(row_count):
                try:
                    value = model.data(model.index(row, logical))
                except Exception:
                    value = None
                if value is not None:
                    width = max(width, fm.horizontalAdvance(str(value)) + 28)
            floor = int(defaults.widths.get(name, 60) or 60)
            table.setColumnWidth(logical, max(floor, min(int(max_width), width)))
        self.save_header_state(table_key)

    def show_header_menu(self, table_key: str, pos) -> None:
        registered = self._registered.get(table_key)
        if not registered:
            return
        table, columns, defaults = registered
        header = table.horizontalHeader()
        menu = QMenu(header)
        columns_menu = menu.addMenu("Columns")
        for column in columns:
            if column in {"Select", "ID", "More", "Actions"}:
                continue
            action = QAction(column, columns_menu)
            action.setCheckable(True)
            idx = columns.index(column)
            action.setChecked(not table.isColumnHidden(idx))
            action.toggled.connect(lambda checked, c=column: self.set_column_visible(table_key, c, checked))
            columns_menu.addAction(action)
        menu.addSeparator()
        fit = menu.addAction("Auto Fit Columns")
        fit.triggered.connect(lambda: self.auto_fit(table_key))
        reset = menu.addAction("Reset Column Layout")
        reset.triggered.connect(lambda: self.reset_table(table_key))
        menu.exec(header.mapToGlobal(pos))
