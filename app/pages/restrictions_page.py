from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton

from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.stat_card import StatCard


class RestrictionsPage(BaseTablePage):
    def __init__(self, controller, parent=None):
        self.controller = controller
        cols = ["Account", "Type", "Scope", "Source", "Confidence", "Started", "Expires", "Remaining", "Status", "Last Error"]
        super().__init__(
            "page_restrictions", "Restriction Center", BaseTableModel([], cols), "tbl_restrictions",
            [
                ("btn_refresh_restrictions", "Refresh"),
                ("btn_view_restriction", "View"),
                ("btn_recheck_restriction", "Recheck"),
                ("btn_mark_manual_resolved", "Mark Resolved"),
                ("btn_export_restrictions", "Export"),
            ],
            None,
            [
                ("cmb_restriction_type", "Type", ["Flood Wait", "Invite Restricted", "Posting Restricted", "Session Invalid", "Authentication Required", "Unknown Restriction"]),
                ("cmb_restriction_source", "Source", ["Telegram Confirmed", "Tool Detected", "Manual", "Unknown"]),
                ("cmb_restriction_status", "Status", ["Active", "Pending Recheck", "Manual Review", "Expired", "Resolved"]),
            ], parent,
        )
        cards = QHBoxLayout()
        self.card_active_restrictions = StatCard("Active Restrictions", 0, "card_active_restrictions")
        self.card_expired_today = StatCard("Expired Today", 0, "card_expired_today")
        self.card_accounts_affected = StatCard("Accounts Affected", 0, "card_accounts_affected")
        self.card_action_required = StatCard("User Action Required", 0, "card_restriction_action_required")
        for card in (self.card_active_restrictions, self.card_expired_today, self.card_accounts_affected, self.card_action_required): cards.addWidget(card)
        self.layout().insertLayout(1, cards)
        self.action_buttons["btn_refresh_restrictions"].clicked.connect(controller.refresh)
        self.action_buttons["btn_view_restriction"].clicked.connect(self._view)
        self.action_buttons["btn_recheck_restriction"].clicked.connect(self._recheck)
        self.action_buttons["btn_mark_manual_resolved"].clicked.connect(self._resolve)
        self.action_buttons["btn_export_restrictions"].clicked.connect(self._export)
        controller.restrictionsChanged.connect(self._set_items)
        self._items = []
        self._timer = QTimer(self); self._timer.setInterval(1000); self._timer.timeout.connect(self._refresh_countdowns); self._timer.start()
        self._set_items(controller.restrictions())

    @staticmethod
    def _remaining(expires_at: str | None, state: str) -> str:
        if not expires_at or str(state).upper() not in {"ACTIVE", "PENDING_RECHECK"}: return "—"
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")); now = datetime.now(timezone.utc)
            seconds = max(0, int((expiry - now).total_seconds()))
            h, rem = divmod(seconds, 3600); m, s = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if seconds else "Pending recheck"
        except Exception: return "—"

    def _rows(self, items):
        return [
            {
                "_id": r.id,
                "Account": r.account_id,
                "Type": str(r.restriction_type or "UNKNOWN").replace("_", " ").title(),
                "Scope": str(getattr(r, "scope", "UNKNOWN") or "UNKNOWN").replace("_", " ").title(),
                "Source": str(r.source or "UNKNOWN").replace("_", " ").title(),
                "Confidence": r.confidence or "—",
                "Started": r.started_at or "—",
                "Expires": r.expires_at or "—",
                "Remaining": self._remaining(r.expires_at, getattr(r, "state", "ACTIVE")),
                "Status": str(getattr(r, "state", "ACTIVE") or "ACTIVE").replace("_", " ").title(),
                "Last Error": r.reason or r.error_code or "—",
            }
            for r in items
        ]

    def _refresh_countdowns(self):
        # Countdown display is local UI state; do not re-query SQLite every
        # second merely to decrement a timer.
        if self._items:
            self.model.replace_rows(self._rows(self._items))

    def _set_items(self, items, update_cards=True):
        items = list(items or []); self._items = items; self.model.replace_rows(self._rows(items))
        if not update_cards: return
        active = [r for r in items if str(getattr(r, "state", "ACTIVE")).upper() in {"ACTIVE", "PENDING_RECHECK", "MANUAL_REVIEW"}]
        self.card_active_restrictions.set_value(len(active))
        today = datetime.now(timezone.utc).date(); expired_today = 0
        for r in items:
            try:
                if r.expires_at and datetime.fromisoformat(r.expires_at.replace("Z", "+00:00")).date() == today: expired_today += 1
            except (ValueError, TypeError, AttributeError):
                continue
        self.card_expired_today.set_value(expired_today)
        self.card_accounts_affected.set_value(len({r.account_id for r in active if r.account_id}))
        self.card_action_required.set_value(sum(bool(getattr(r, "requires_action", False)) or str(getattr(r, "state", "")).upper() == "MANUAL_REVIEW" for r in active))

    def _selected_id(self):
        row = self.selected_row(); return int(row.get("_id")) if row and row.get("_id") else None

    def _view(self):
        rid = self._selected_id()
        if not rid: return
        r = self.controller.get_by_id(rid)
        QMessageBox.information(self, "Restriction Details", f"Account: {r.account_id}\nType: {r.restriction_type}\nScope: {r.scope}\nState: {r.state}\nSource: {r.source}\nStarted: {r.started_at}\nExpires: {r.expires_at or 'Unknown'}\nReason: {r.reason or '—'}\n\nHistory is retained even after resolution.")

    def _recheck(self):
        rid = self._selected_id()
        if rid: self.controller.recheck(rid)

    def _resolve(self):
        rid = self._selected_id()
        if not rid: return
        if QMessageBox.question(self, "Manual Resolution", "Mark this restriction manually resolved?\n\nThis keeps the full history and does not claim Telegram independently confirmed the resolution.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.controller.manual_resolve(rid)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Restrictions", "restrictions.csv", "CSV Files (*.csv)")
        if path: self.controller.export(path)
