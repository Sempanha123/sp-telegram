from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout
from app.dialogs.dialog_compat import *

from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime
from app.utils.table_preferences import TablePreferenceManager
from app.utils.member_display_formatter import MemberDisplayFormatter, MemberDisplayPreferences
from app.utils.table_layout_manager import TableLayoutManager


class TargetMembersDialog(QDialog):
    COLUMNS = ["Member", "Username", "Telegram ID", "Status", "Joined / First Seen", "Source", "Last Sync"]
    WIDTHS = {"Member": 210, "Username": 190, "Telegram ID": 150, "Status": 155,
              "Joined / First Seen": 175, "Source": 210, "Last Sync": 175}

    def __init__(self, member_controller, target_group_id: int, target_title: str, parent=None):
        super().__init__(parent)
        self.controller = member_controller
        self.target_group_id = int(target_group_id)
        self.setWindowTitle(f"Target Members - {target_title} - SP Telegram")
        self.resize(1050, 650)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)
        title = QLabel(f"{target_title} — Target Members")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        note = QLabel("Statuses come from verified target-member synchronization or explicit target checks. UNKNOWN is kept distinct from NOT_MEMBER.")
        note.setWordWrap(True); note.setProperty("secondary", True); root.addWidget(note)
        self.table = QTableView(); self.table.setObjectName("tbl_target_members")
        self.model = BaseTableModel([], self.COLUMNS, self); self.table.setModel(self.model)
        prefs_settings=QSettings();privacy=str(prefs_settings.value("ui/privacy_mode",False)).lower() in {"1","true","yes"}
        self.model.set_privacy_mode(privacy)
        self.model.set_display_preferences(mask_telegram_ids=bool(TablePreferenceManager(prefs_settings).global_value("mask_telegram_ids",False)),mask_usernames=bool(TablePreferenceManager(prefs_settings).global_value("mask_usernames",False)),mask_display_names=bool(TablePreferenceManager(prefs_settings).global_value("mask_display_names",False)))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(42)
        root.addWidget(self.table, 1)
        self.prefs = TablePreferenceManager(QSettings(), self)
        self.prefs.register(self.table, self.COLUMNS, default_widths=self.WIDTHS)
        self.layout_manager=TableLayoutManager(self);self.layout_manager.apply(self.table,self.COLUMNS)
        bar = QHBoxLayout(); self.btn_refresh = QPushButton("Refresh"); self.btn_refresh.setObjectName("btn_refresh_target_members"); self.btn_close = QPushButton("Close")
        bar.addWidget(self.btn_refresh); bar.addStretch(); bar.addWidget(self.btn_close); root.addLayout(bar)
        self.btn_refresh.clicked.connect(self.reload); self.btn_close.clicked.connect(self.accept)
        self.reload()

    def reload(self):
        rows=[]
        display=MemberDisplayPreferences.from_manager(self.prefs)
        for row in self.controller.target_member_rows(self.target_group_id, 1000) or []:
            ident=MemberDisplayFormatter.format_identity(dict(row),display)
            rows.append({
                "Member": ident["display_name"] if ident["display_name"] != "—" else (ident["username"] if ident["username"] != "—" else f"Member {row['member_id']}"),
                "Username": ident["username"],
                "Telegram ID": ident["telegram_user_id"],
                "Status": str(row["state"] or "UNKNOWN").replace("_", " ").title(),
                "Joined / First Seen": format_local_datetime(row["first_seen_at"]),
                "Source": row["sources"] or "—",
                "Last Sync": format_local_datetime(row["last_checked_at"]),
            })
        self.model.replace_rows(rows)

# Add compatibility attributes for older PySide6 versions
if not hasattr(TargetMembersDialog, 'Accepted'):
    TargetMembersDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(TargetMembersDialog, 'Rejected'):
    TargetMembersDialog.Rejected = QDialog.DialogCode.Rejected
