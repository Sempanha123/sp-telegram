from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QHeaderView, QTableView


@dataclass(frozen=True)
class ColumnLayout:
    width: int = 120
    minimum: int = 70
    mode: str = "interactive"  # interactive | contents | stretch | fixed
    maximum: int = 520


MEMBER_POOL_LAYOUT = {
    "Select": ColumnLayout(44, 44, "fixed", 44),
    "Telegram ID": ColumnLayout(150, 120),
    "Username": ColumnLayout(190, 130),
    "Name": ColumnLayout(210, 150),
    "Sources": ColumnLayout(210, 150),
    "Eligibility": ColumnLayout(145, 110),
    "Consent": ColumnLayout(140, 110),
    "Target Status": ColumnLayout(155, 125),
    "Blacklist": ColumnLayout(100, 90, "contents"),
    "Bot": ColumnLayout(80, 70, "contents"),
    "Premium": ColumnLayout(95, 80, "contents"),
    "First Seen": ColumnLayout(175, 150),
    "Last Seen": ColumnLayout(175, 150),
    "Tags": ColumnLayout(190, 130),
    "More": ColumnLayout(60, 60, "fixed", 60),
    "Actions": ColumnLayout(60, 60, "fixed", 60),
}

HEALTH_CENTER_LAYOUT = {
    "Account": ColumnLayout(180, 150),
    "Connection": ColumnLayout(145, 130),
    "Authorization": ColumnLayout(160, 140),
    "Health": ColumnLayout(145, 120),
    "Last Check": ColumnLayout(180, 150),
    "Last Error": ColumnLayout(300, 180, "stretch"),
    "Session": ColumnLayout(130, 110),
    "Last Use": ColumnLayout(180, 150),
}

MEMBER_TARGET_STATUS_LAYOUT = {
    "Target": ColumnLayout(220, 160, "stretch"),
    "Status": ColumnLayout(150, 125),
    "Last Sync / Check": ColumnLayout(190, 170),
    "Account": ColumnLayout(170, 140),
    "Error": ColumnLayout(300, 180, "stretch"),
}


class TableLayoutManager(QObject):
    """Central table sizing rules with persisted-layout compatibility.

    It sets sensible *defaults/minimums* and keeps columns user-resizable. It
    intentionally samples only the loaded model rows for auto-fit; no database
    scan is triggered from this UI helper.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimums: dict[int, dict[int, int]] = {}
        self._clamping: set[int] = set()

    @staticmethod
    def _mode(value: str):
        value = str(value or "interactive").lower()
        return {
            "contents": QHeaderView.ResizeMode.ResizeToContents,
            "stretch": QHeaderView.ResizeMode.Stretch,
            "fixed": QHeaderView.ResizeMode.Fixed,
        }.get(value, QHeaderView.ResizeMode.Interactive)

    @staticmethod
    def _heuristic(column: str) -> ColumnLayout:
        name = str(column)
        low = name.lower()
        if name in MEMBER_POOL_LAYOUT:
            return MEMBER_POOL_LAYOUT[name]
        if low in {"select"}:
            return ColumnLayout(44, 44, "fixed", 44)
        if low in {"more", "actions"}:
            return ColumnLayout(60, 60, "fixed", 60)
        if "telegram id" in low:
            return ColumnLayout(150, 120)
        if "username" in low:
            return ColumnLayout(180, 130)
        if low in {"name", "member", "account", "group", "target", "title"}:
            return ColumnLayout(190, 140)
        if "source" in low:
            return ColumnLayout(190, 140)
        if "eligibility" in low:
            return ColumnLayout(145, 110)
        if "consent" in low:
            return ColumnLayout(140, 110)
        if "target status" in low:
            return ColumnLayout(155, 125)
        if any(token in low for token in ("operational status", "authorization")):
            return ColumnLayout(160, 140)
        if low in {"connection"}:
            return ColumnLayout(145, 130)
        if low in {"health"}:
            return ColumnLayout(145, 120)
        if any(token in low for token in ("first seen", "last seen", "last check", "last use", "last sync", "scheduled", "created", "updated", "date", "expires")):
            return ColumnLayout(175, 145)
        if "error" in low or "message" in low or "description" in low:
            return ColumnLayout(260, 160, "stretch")
        if low in {"status", "role", "access", "type"} or low.startswith("can "):
            return ColumnLayout(130, 100, "contents")
        if low in {"bot", "premium", "blacklist", "existing"}:
            return ColumnLayout(95, 75, "contents")
        if "tag" in low:
            return ColumnLayout(180, 120)
        return ColumnLayout(135, 80)

    def layout_for(self, table: QTableView, columns: list[str], overrides: Mapping[str, ColumnLayout] | None = None) -> dict[str, ColumnLayout]:
        overrides = dict(overrides or {})
        if table.objectName() in {"tbl_members", "tbl_target_preparation"}:
            base = dict(MEMBER_POOL_LAYOUT)
        elif table.objectName() in {"tbl_health", "tbl_account_health"}:
            base = dict(HEALTH_CENTER_LAYOUT)
        elif table.objectName() == "tbl_member_target_states":
            base = dict(MEMBER_TARGET_STATUS_LAYOUT)
        else:
            base = {}
        result = {}
        for column in columns:
            result[column] = overrides.get(column) or base.get(column) or self._heuristic(column)
        return result

    def apply(self, table: QTableView, columns: list[str], *, overrides: Mapping[str, ColumnLayout] | None = None, preserve_existing: bool = False) -> dict[str, int]:
        header = table.horizontalHeader()
        layout = self.layout_for(table, columns, overrides)
        minimums: dict[int, int] = {}
        default_widths: dict[str, int] = {}
        for index, name in enumerate(columns):
            spec = layout[name]
            minimums[index] = max(24, int(spec.minimum))
            default_widths[name] = int(spec.width)
            header.setSectionResizeMode(index, self._mode(spec.mode))
            if not preserve_existing or table.columnWidth(index) < spec.minimum:
                table.setColumnWidth(index, max(spec.minimum, spec.width))
        self._minimums[id(table)] = minimums
        marker = f"_sp_layout_clamp_{id(self)}"
        if not table.property(marker):
            table.setProperty(marker, True)
            header.sectionResized.connect(lambda logical, _old, new, t=table: self._enforce_minimum(t, logical, new))
        return default_widths

    def _enforce_minimum(self, table: QTableView, logical: int, new_size: int) -> None:
        key = id(table)
        minimum = self._minimums.get(key, {}).get(int(logical))
        if not minimum or int(new_size) >= minimum or key in self._clamping:
            return
        self._clamping.add(key)
        def restore():
            try:
                table.setColumnWidth(int(logical), int(minimum))
            except RuntimeError:
                # The table view was destroyed before the deferred restore ran
                # (e.g. a dialog with a table was closed in the same event-loop
                # turn).  Nothing to restore — the C++ object is gone.
                pass
            finally:
                self._clamping.discard(key)
        QTimer.singleShot(0, restore)

    @staticmethod
    def auto_fit_loaded_rows(table: QTableView, *, sample_rows: int = 100, maximum: int = 420) -> None:
        model = table.model()
        if model is None:
            return
        fm = table.fontMetrics(); hfm = table.horizontalHeader().fontMetrics()
        rows = min(max(0, model.rowCount()), max(1, int(sample_rows)))
        for col in range(model.columnCount()):
            if table.isColumnHidden(col):
                continue
            header_text = model.headerData(col, Qt.Orientation.Horizontal) or ""
            width = hfm.horizontalAdvance(str(header_text)) + 34
            for row in range(rows):
                value = model.data(model.index(row, col))
                if value is not None:
                    width = max(width, fm.horizontalAdvance(str(value)) + 28)
            table.setColumnWidth(col, min(int(maximum), max(60, width)))
