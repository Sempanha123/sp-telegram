from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout,
    QGridLayout, QHeaderView, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QTableView, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from app.dialogs.create_target_invite_link_dialog import CreateTargetInviteLinkDialog
from app.models.base_table_model import BaseTableModel
from app.utils.member_display_formatter import MemberDisplayFormatter, MemberDisplayPreferences
from app.utils.table_layout_manager import TableLayoutManager
from app.utils.table_preferences import TablePreferenceManager
from app.widgets.add_member_live_activity import AddMemberLiveActivity


def _human(value, empty="—") -> str:
    text = str(value or "").strip()
    return text.replace("_", " ").title() if text else empty


class InvitationResultsDialog(QDialog):
    COLUMNS = ["Member", "Username", "Telegram ID", "Status", "Error"]

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result or {}
        self.setWindowTitle("Invitation Results - SP Telegram")
        self.resize(900, 540)
        root = QVBoxLayout(self); root.setContentsMargins(18, 18, 18, 18); root.setSpacing(12)
        root.addWidget(QLabel("Invitation Results"))
        summary = QLabel(
            f"Processed: {int(self.result.get('processed', self.result.get('selected', 0))):,}  •  "
            f"Successful: {int(self.result.get('successful', 0)):,}  •  "
            f"Already Member: {int(self.result.get('already_member', 0)):,}  •  "
            f"Privacy Restricted: {int(self.result.get('privacy_restricted', 0)):,}  •  "
            f"Skipped: {int(self.result.get('skipped', 0)):,}  •  Failed: {int(self.result.get('failed', 0)):,}"
        )
        summary.setProperty("secondary", True); summary.setWordWrap(True); root.addWidget(summary)

        prefs = TablePreferenceManager(QSettings(), self)
        display = MemberDisplayPreferences.from_manager(prefs)
        rows = []
        for item in self.result.get("results", []) or []:
            identity = MemberDisplayFormatter.format_identity(item, display)
            name = identity["display_name"]
            if name == "—":
                name = identity["username"] if identity["username"] != "—" else f"Member #{item.get('member_id')}"
            rows.append({
                "Member": name,
                "Username": identity["username"],
                "Telegram ID": identity["telegram_user_id"],
                "Status": _human(item.get("status")),
                "Error": item.get("message") or item.get("error_code") or "—",
            })
        self.model = BaseTableModel(rows, self.COLUMNS, self)
        self.model.set_display_preferences(
            mask_telegram_ids=display.mask_telegram_ids,
            mask_usernames=display.mask_usernames,
            mask_display_names=display.mask_display_names,
        )
        self.model.set_privacy_mode(display.privacy_mode)
        self.table = QTableView(); self.table.setObjectName("tbl_target_invitation_results"); self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(44)
        root.addWidget(self.table, 1)
        self.prefs = prefs
        self.prefs.register(self.table, self.COLUMNS, default_widths={"Member": 210, "Username": 190, "Telegram ID": 150, "Status": 175, "Error": 300})
        self.layout_manager = TableLayoutManager(self); self.layout_manager.apply(self.table, self.COLUMNS)

        bar = QHBoxLayout()
        self.btn_export = QPushButton("Export Results"); self.btn_export.setObjectName("btn_export_target_invitation_results"); self.btn_export.clicked.connect(self._export)
        btn = QPushButton("Close"); btn.clicked.connect(self.accept)
        bar.addWidget(self.btn_export); bar.addStretch(); bar.addWidget(btn); root.addLayout(bar)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Invitation Results", "invitation_results.csv", "CSV Files (*.csv)")
        if not path:
            return
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle); writer.writerow(self.COLUMNS)
            for row in self.model.rows:
                writer.writerow([row.get(c, "") for c in self.COLUMNS])


class InviteMembersToTargetDialog(QDialog):
    """Bounded explicit-account invitation batch with fixed member assignments."""

    MAX_ACCOUNTS = 5
    ACCOUNT_COLUMNS = ["Use", "Authorized Account", "Account Health", "Safety", "Today / Limit", "Target Access", "Can Invite", "Restriction", "Assigned"]

    def __init__(self, member_controller, member_ids: list[int], *, target_group_id: int | None = None,
                 group_controller=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("dlg_invite_members_to_target")
        self.setWindowTitle("Invite Members to Target - SP Telegram")
        self.setMinimumSize(900, 620); self.resize(1040, 700)
        self.controller = member_controller; self.group_controller = group_controller
        self.member_ids = sorted({int(x) for x in member_ids if int(x) > 0})
        self._precheck = None; self._last_result = None; self._preflight_generation = 0; self._last_invite_link = None
        self._closed = False; self._controller_connections = []
        self._running = False
        self._mapping_by_account = {}; self._account_option_by_id = {}; self._account_row_by_id = {}; self._account_update_guard = False

        root = QVBoxLayout(self); root.setContentsMargins(18, 16, 18, 16); root.setSpacing(10)
        title = QLabel("Invite Members to Target"); title.setProperty("dialogTitle", True); root.addWidget(title)
        self.lbl_scope = QLabel(f"Input Selection: {len(self.member_ids):,} Member Pool record(s)")
        self.lbl_scope.setProperty("secondary", True); root.addWidget(self.lbl_scope)
        note = QLabel(
            "Choose up to 5 authorized accounts. Each account receives a fixed assignment within both the 20-member batch ceiling and its remaining daily safety limit. "
            "A Telegram restriction, FloodWait or permission failure stops the batch; unfinished members are not moved to another account."
        )
        note.setWordWrap(True); note.setProperty("secondary", True); root.addWidget(note)

        self.tabs = QTabWidget(); self.tabs.setObjectName("tabs_target_invitation"); root.addWidget(self.tabs, 1)
        self._build_setup_tab(target_group_id)
        self._build_eligibility_tab()
        self._build_progress_tab()

        self.live_activity = AddMemberLiveActivity(self)
        self.live_activity.hide()
        root.addWidget(self.live_activity)

        actions = QHBoxLayout()
        self.btn_results = QPushButton("View Results"); self.btn_results.setObjectName("btn_view_target_invitation_results"); self.btn_results.setEnabled(False)
        self.btn_cancel = QPushButton("Close")
        self.btn_start = QPushButton("Start Invitation"); self.btn_start.setObjectName("btn_start_target_invitation"); self.btn_start.setProperty("primary", True); self.btn_start.setEnabled(False)
        actions.addWidget(self.btn_results); actions.addStretch(); actions.addWidget(self.btn_cancel); actions.addWidget(self.btn_start); root.addLayout(actions)

        self._preflight_timer = QTimer(self); self._preflight_timer.setSingleShot(True); self._preflight_timer.setInterval(180); self._preflight_timer.timeout.connect(self._request_preflight)
        self.cmb_target.currentIndexChanged.connect(self._target_changed); self.table_accounts.itemChanged.connect(self._account_item_changed)
        self.btn_select_valid.clicked.connect(self._select_valid_accounts); self.btn_clear_accounts.clicked.connect(self._clear_accounts)
        self.btn_refresh_permission.clicked.connect(self._request_preflight); self.btn_invite_link.clicked.connect(self._create_invite_link)
        self.btn_start.clicked.connect(self._start); self.btn_cancel.clicked.connect(self._close_or_background_v5)
        self.live_activity.backgroundRequested.connect(self._background_v5)
        self.live_activity.jobsRequested.connect(self._open_jobs_v5)
        self.btn_pause.clicked.connect(self._pause); self.btn_resume.clicked.connect(self._resume); self.btn_stop.clicked.connect(self._stop); self.btn_results.clicked.connect(self._show_results)
        self._connect_controller(self.controller.targetInvitationProgress, self._progress)
        self._connect_controller(self.controller.targetInvitationCompleted, self._completed)
        if hasattr(self.controller, "targetInvitationFailed"):
            self._connect_controller(self.controller.targetInvitationFailed, self._invitation_failed)
        if hasattr(self.controller, "targetInvitationPreflightFailed"):
            self._connect_controller(self.controller.targetInvitationPreflightFailed, self._preflight_failed)
        for signal_name in ("memberEligibilityChanged", "memberEligibilityBatchChanged", "memberBlacklistChanged", "targetMembershipUpdated"):
            signal = getattr(self.controller, signal_name, None)
            if signal is not None:
                slot = lambda *_: self._schedule_preflight()
                self._connect_controller(signal, slot)
        self._target_changed()
        self._register_live_dialog_v5()

    def _live_manager_v5(self):
        parent=self.parentWidget()
        while parent is not None:
            manager=getattr(parent,"_live_job_ux",None)
            if manager is not None:
                return manager
            parent=parent.parentWidget()
        return None

    def _register_live_dialog_v5(self):
        manager=self._live_manager_v5()
        if manager is not None:
            try:
                manager.register_dialog(self)
            except Exception:
                pass

    def _live_account_plan_v5(self):
        pre=self._precheck or {}
        result=[]
        for account in pre.get("accounts") or []:
            assigned=int(account.get("assigned_count",0) or 0)
            if assigned<=0:
                continue
            result.append({
                "account_id":int(account.get("account_id",0) or 0),
                "name":str(account.get("name") or f"Account {int(account.get('account_id',0) or 0)}"),
                "assigned":assigned,
            })
        return result

    def _background_v5(self):
        if not self._running:
            self.showMinimized()
            return
        self.hide()
        manager=self._live_manager_v5()
        if manager is not None:
            try:
                manager.window.toast_requested.emit(
                    "Add Members is still running. Click the Add x/y chip at the top to reopen it.",
                    "Info",
                )
            except Exception:
                pass

    def _open_jobs_v5(self):
        manager=self._live_manager_v5()
        if manager is not None:
            manager.open_jobs()

    def _close_or_background_v5(self):
        if self._running:
            self._background_v5()
        else:
            self.reject()

    def closeEvent(self,event):
        if self._running:
            self._background_v5()
            event.ignore()
            return
        super().closeEvent(event)

    def _connect_controller(self, signal, slot):
        try:
            signal.connect(slot); self._controller_connections.append((signal, slot))
        except (TypeError, RuntimeError):
            pass

    def done(self, result):
        self._closed = True; self._preflight_generation += 1; self._preflight_timer.stop()
        for signal, slot in self._controller_connections:
            try: signal.disconnect(slot)
            except (TypeError, RuntimeError): pass
        self._controller_connections.clear()
        super().done(result)

    def _build_setup_tab(self, target_group_id):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(10)
        form = QFormLayout(); form.setHorizontalSpacing(18); form.setVerticalSpacing(8)
        self.cmb_target = QComboBox(); self.cmb_target.setObjectName("cmb_invite_target")
        for group in self.controller.target_groups():
            self.cmb_target.addItem(group.title + (f"  @{group.username}" if getattr(group, "username", None) else ""), int(group.id))
        if target_group_id:
            index = self.cmb_target.findData(int(target_group_id)); self.cmb_target.setCurrentIndex(max(0, index))
        form.addRow("Target", self.cmb_target); layout.addLayout(form)

        heading = QLabel("Authorized Accounts"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        hint = QLabel("Select up to 5 accounts. Accounts marked Auto Join will join this public target during preflight, then live invite permission is checked automatically.")
        hint.setProperty("secondary", True); hint.setWordWrap(True); layout.addWidget(hint)
        self.table_accounts = QTableWidget(0, len(self.ACCOUNT_COLUMNS)); self.table_accounts.setObjectName("tbl_invitation_accounts")
        self.table_accounts.setHorizontalHeaderLabels(self.ACCOUNT_COLUMNS); self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_accounts.setAlternatingRowColors(True); self.table_accounts.setMinimumHeight(225)
        header = self.table_accounts.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_accounts, 1)
        bar = QHBoxLayout()
        self.btn_select_valid = QPushButton("Select Valid Accounts"); self.btn_select_valid.setObjectName("btn_choose_invitation_account")
        self.btn_clear_accounts = QPushButton("Clear Selection")
        self.lbl_account_selection = QLabel("0 selected"); self.lbl_account_selection.setProperty("secondary", True)
        bar.addWidget(self.btn_select_valid); bar.addWidget(self.btn_clear_accounts); bar.addStretch(); bar.addWidget(self.lbl_account_selection); layout.addLayout(bar)
        self.tabs.addTab(tab, "Setup")

    def _build_eligibility_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(10)
        heading = QLabel("Eligibility Summary"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        summary_box = QWidget(); grid = QGridLayout(summary_box); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8); self.summary = {}
        fields = [
            ("selected", "Input Selection"), ("eligible", "Eligible"), ("ready", "Ready to Invite"),
            ("eligibility_not_approved", "Eligibility Not Approved"), ("consent_not_approved", "Consent Not Approved"),
            ("already_member", "Already Member"), ("blacklisted", "Blacklisted"), ("do_not_contact", "Do Not Contact"),
            ("unknown", "Unknown Target"), ("deleted", "Deleted"), ("bots", "Bots"),
        ]
        for i, (key, label) in enumerate(fields):
            cell = QWidget(); cell_layout = QVBoxLayout(cell); cell_layout.setContentsMargins(10, 7, 10, 7); cell_layout.setSpacing(2)
            lab = QLabel(label); lab.setProperty("secondary", True); num = QLabel("0"); num.setProperty("metric", True)
            cell_layout.addWidget(lab); cell_layout.addWidget(num); self.summary[key] = num; grid.addWidget(cell, i // 4, i % 4)
        layout.addWidget(summary_box)
        self.lbl_preflight_status = QLabel("Select authorized accounts to run preflight."); self.lbl_preflight_status.setProperty("secondary", True); self.lbl_preflight_status.setWordWrap(True); layout.addWidget(self.lbl_preflight_status)
        self.lbl_warning = QPlainTextEdit(); self.lbl_warning.setObjectName("lbl_invitation_preflight_warning"); self.lbl_warning.setReadOnly(True); self.lbl_warning.setMaximumHeight(150); self.lbl_warning.setProperty("warning", True); self.lbl_warning.hide(); layout.addWidget(self.lbl_warning)
        layout.addStretch()
        preflight_actions = QHBoxLayout()
        self.btn_refresh_permission = QPushButton("Refresh Permissions"); self.btn_refresh_permission.setObjectName("btn_refresh_invitation_permission")
        self.btn_invite_link = QPushButton("Create Invite Link"); self.btn_invite_link.setObjectName("btn_invitation_create_invite_link"); self.btn_invite_link.setEnabled(False)
        preflight_actions.addWidget(self.btn_refresh_permission); preflight_actions.addWidget(self.btn_invite_link); preflight_actions.addStretch(); layout.addLayout(preflight_actions)
        self.tabs.addTab(tab, "Eligibility")

    def _build_progress_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(12)
        heading = QLabel("Progress"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        self.progress = QProgressBar(); self.progress.setRange(0, max(1, len(self.member_ids))); self.progress.setValue(0); layout.addWidget(self.progress)
        self.lbl_progress = QLabel("Preflight required"); self.lbl_progress.setProperty("secondary", True); self.lbl_progress.setWordWrap(True); layout.addWidget(self.lbl_progress)
        controls = QHBoxLayout()
        self.btn_pause = QPushButton("Pause"); self.btn_pause.setObjectName("btn_pause_target_invitation")
        self.btn_resume = QPushButton("Resume"); self.btn_resume.setObjectName("btn_resume_target_invitation")
        self.btn_stop = QPushButton("Stop"); self.btn_stop.setObjectName("btn_stop_target_invitation")
        for button in (self.btn_pause, self.btn_resume, self.btn_stop): button.setEnabled(False); controls.addWidget(button)
        controls.addStretch(); layout.addLayout(controls); layout.addStretch()
        self.tabs.addTab(tab, "Progress")

    @staticmethod
    def _item(text="—"):
        item = QTableWidgetItem(str(text)); item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable); return item

    def _target_changed(self, *_args):
        target_id = self.cmb_target.currentData()
        options = list(self.controller.mass_add_account_options(int(target_id)) or []) if target_id else []

        self._account_option_by_id = {int(row["account_id"]): row for row in options}
        self._mapping_by_account = {
            int(row["account_id"]): row.get("mapping")
            for row in options
            if row.get("mapping") is not None
        }
        self._account_row_by_id = {}

        self._account_update_guard = True
        self.table_accounts.blockSignals(True)
        self.table_accounts.setRowCount(len(options))

        for row, option in enumerate(options):
            account_id = int(option["account_id"])
            self._account_row_by_id[account_id] = row
            auto_join = bool(option.get("auto_join"))
            selectable = bool(option.get("selectable"))

            check = QTableWidgetItem()
            check.setData(Qt.ItemDataRole.UserRole, account_id)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setFlags(
                (Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if selectable
                else Qt.ItemFlag.ItemIsSelectable
            )

            name = str(option.get("name") or f"Account {account_id}")
            if option.get("username"):
                name += f"  •  @{option['username']}"
            if auto_join:
                name += "  •  Auto Join"

            access_text = "Auto Join → Live Check" if auto_join else _human(option.get("access"), "Unknown")
            invite_text = "After Join" if auto_join else ("Yes" if option.get("can_invite_now") else "No")

            self.table_accounts.setItem(row, 0, check)
            self.table_accounts.setItem(row, 1, self._item(name))
            self.table_accounts.setItem(row, 2, self._item(_human(option.get("health"), "Unknown")))
            self.table_accounts.setItem(row, 3, self._item("—"))
            self.table_accounts.setItem(row, 4, self._item("—"))
            self.table_accounts.setItem(row, 5, self._item(access_text))
            self.table_accounts.setItem(row, 6, self._item(invite_text))
            self.table_accounts.setItem(row, 7, self._item(_human(option.get("restriction"), "None")))
            self.table_accounts.setItem(row, 8, self._item("—"))

        self.table_accounts.blockSignals(False)
        self._account_update_guard = False
        self._precheck = None
        self.btn_start.setEnabled(False)
        self.btn_invite_link.setEnabled(False)
        self._set_account_selection_text()

        if any(bool(row.get("auto_join")) for row in options):
            self._show_warning(
                "Accounts marked Auto Join will join this public target during preflight. "
                "SP Telegram then refreshes live invite permission before Start is enabled."
            )
        else:
            self._show_warning("")


    def _selected_account_ids(self):
        selected = []
        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def _set_account_selection_text(self):
        if self.table_accounts.rowCount() == 0:
            self.lbl_account_selection.setText("No mapped authorized accounts for this target"); return
        count = len(self._selected_account_ids())
        self.lbl_account_selection.setText(f"{count} selected  •  max {self.MAX_ACCOUNTS}  •  20 ready members per account")

    def _account_item_changed(self, item):
        if self._account_update_guard or not item or item.column() != 0:
            return
        selected = self._selected_account_ids()
        if len(selected) > self.MAX_ACCOUNTS:
            self._account_update_guard = True; item.setCheckState(Qt.CheckState.Unchecked); self._account_update_guard = False
            self._show_warning(f"Select no more than {self.MAX_ACCOUNTS} accounts per invitation batch.")
        self._set_account_selection_text(); self._schedule_preflight()

    def _select_valid_accounts(self):
        chosen = 0
        self._account_update_guard = True
        self.table_accounts.blockSignals(True)

        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0)
            account_id = (
                int(item.data(Qt.ItemDataRole.UserRole))
                if item and item.data(Qt.ItemDataRole.UserRole)
                else None
            )
            option = self._account_option_by_id.get(account_id) if account_id else None
            valid = bool(option and option.get("selectable"))
            checked = valid and chosen < self.MAX_ACCOUNTS

            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            if checked:
                chosen += 1

        self.table_accounts.blockSignals(False)
        self._account_update_guard = False
        self._set_account_selection_text()
        self._schedule_preflight()

        if chosen == 0:
            self._show_warning(
                "No healthy authorized account can invite or auto-join this target. "
                "Auto Join requires a public @username."
            )


    def _clear_accounts(self):
        self._account_update_guard = True; self.table_accounts.blockSignals(True)
        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable: item.setCheckState(Qt.CheckState.Unchecked)
        self.table_accounts.blockSignals(False); self._account_update_guard = False; self._set_account_selection_text(); self._schedule_preflight()

    def _show_warning(self, message=None):
        text = str(message or "").strip()
        if text: self.lbl_warning.setPlainText(text); self.lbl_warning.show()
        else: self.lbl_warning.clear(); self.lbl_warning.hide()

    def _set_checking(self):
        self._precheck = None; self.btn_start.setEnabled(False); self.btn_invite_link.setEnabled(False)
        self.lbl_preflight_status.setText("Checking current authorization, connection, target permissions and fixed assignment capacity…")
        for row in range(self.table_accounts.rowCount()):
            self.table_accounts.item(row, 8).setText("—")
        for account_id in self._selected_account_ids():
            row = self._account_row_by_id.get(account_id)
            if row is not None: self.table_accounts.item(row, 8).setText("Checking…")

    def _schedule_preflight(self, *_args):
        if self._closed:return
        self._set_checking(); self._preflight_timer.start()

    def _request_preflight(self):
        if self._closed:return
        target_id = self.cmb_target.currentData(); account_ids = self._selected_account_ids()
        self._preflight_generation += 1; generation = self._preflight_generation
        if not target_id or not account_ids:
            self._precheck = None; self.btn_start.setEnabled(False); self.btn_invite_link.setEnabled(False)
            self.lbl_preflight_status.setText("Select 1–5 authorized accounts to run preflight.")
            self._show_warning("No authorized account is selected. Use the checkboxes in Setup or choose Select Valid Accounts.")
            return
        self._set_checking()
        token = self.controller.request_invitation_batch_preflight(
            int(target_id), account_ids, self.member_ids,
            callback=lambda result, g=generation: self._apply_preflight(result, g),
        )
        if token is None:
            cached = self.controller.invitation_batch_precheck(int(target_id), account_ids, self.member_ids)
            if cached: self._apply_preflight(cached, generation)

    @staticmethod
    def _as_dict(pre):
        if pre is None: return None
        if isinstance(pre, dict): return pre
        if hasattr(pre, "to_dict"): return pre.to_dict()
        return None

    def _apply_preflight(self, result, generation=None):
        if self._closed:return
        if generation is not None and generation != self._preflight_generation:
            return
        pre = self._as_dict(result)
        if not pre:
            self._preflight_failed("Invitation preflight did not return a usable result."); return
        self._precheck = pre; counts = dict(pre.get("counts") or {})
        for key, label in self.summary.items(): label.setText(f"{int(counts.get(key, 0) or 0):,}")
        self._account_update_guard = True; self.table_accounts.blockSignals(True)
        for account in pre.get("accounts") or []:
            row = self._account_row_by_id.get(int(account.get("account_id", 0)))
            if row is None: continue
            self.table_accounts.item(row, 2).setText(_human(account.get("health"), "Unknown"))
            self.table_accounts.item(row, 3).setText(_human(account.get("safety_state"), "Normal"))
            self.table_accounts.item(row, 4).setText(f"{int(account.get('invite_used_today', 0) or 0)}/{int(account.get('invite_daily_limit', 0) or 0)}" if account.get("smart_limits") else "Manual")
            self.table_accounts.item(row, 5).setText(_human(account.get("role"), "Unknown"))
            self.table_accounts.item(row, 6).setText("Yes" if account.get("can_invite") else "No")
            self.table_accounts.item(row, 7).setText(_human(account.get("restriction"), "None"))
            self.table_accounts.item(row, 8).setText(str(int(account.get("assigned_count", 0) or 0)))
            blockers = list(account.get("blocking_reasons") or [])
            self.table_accounts.item(row, 1).setToolTip("\n".join(blockers))
        self.table_accounts.blockSignals(False); self._account_update_guard = False
        blockers = list(pre.get("blocking_reasons") or []); warnings = list(pre.get("warnings") or [])
        messages = blockers + warnings
        if int(counts.get("ready", 0) or 0) <= 0 and int(counts.get("selected", 0) or 0) > 0:
            details = []
            for key, text in [
                ("eligibility_not_approved", "require Eligibility = Eligible"), ("consent_not_approved", "require Consent = Approved"),
                ("do_not_contact", "are Do Not Contact"), ("blacklisted", "are blacklisted"),
                ("already_member", "are already members"), ("unknown", "need a verified target-membership check"),
                ("deleted", "are deleted/deactivated"), ("bots", "are bots"),
            ]:
                count = int(counts.get(key, 0) or 0)
                if count: details.append(f"{count} selected member(s) {text}.")
            if details: messages.append(" ".join(details))
        self._show_warning("\n".join(f"• {message}" for message in messages))
        can_start = bool(pre.get("can_start", pre.get("start_allowed", False)))
        self.btn_start.setEnabled(can_start); self.btn_start.setProperty("preflightAllowed", can_start)
        self.btn_start.style().unpolish(self.btn_start); self.btn_start.style().polish(self.btn_start)
        if not can_start:
            self.btn_start.setToolTip((blockers or ["No selected members currently satisfy the invitation eligibility requirements."])[0])
        else:
            self.btn_start.setToolTip("")
        self.btn_invite_link.setEnabled(self._can_create_invite_link())
        self.btn_invite_link.setToolTip("" if self.btn_invite_link.isEnabled() else "None of the selected accounts can create an invite link for this target.")
        selected_accounts = int(pre.get("selected_account_count", 0) or 0); ready = int(counts.get("ready", 0) or 0)
        self.lbl_preflight_status.setText(f"Preflight complete: {selected_accounts} account(s), {ready} ready member(s). Assignments are fixed; no fallback account will be used.")
        self.tabs.setTabText(1, f"Eligibility ({ready})")

    def _preflight_failed(self, message):
        if self._closed:return
        self._precheck = None; self.btn_start.setEnabled(False); self.btn_invite_link.setEnabled(False)
        self._show_warning(message or "Invitation preflight could not be completed."); self.lbl_preflight_status.setText("Preflight unavailable")

    def _start(self):
        pre = self._precheck or {}; counts = pre.get("counts") or {}
        if not pre:
            self._show_warning("Invitation preflight is not available yet."); self.tabs.setCurrentIndex(1); return
        if not bool(pre.get("can_start", pre.get("start_allowed", False))) or int(counts.get("ready", 0) or 0) <= 0:
            self.btn_start.setEnabled(False); self.btn_start.setToolTip("No selected members currently satisfy the invitation eligibility requirements.")
            self._show_warning("No selected members currently satisfy the invitation eligibility requirements. Review the eligibility summary."); self.tabs.setCurrentIndex(1); return

        account_ids = self._selected_account_ids(); ready = int(counts.get("ready", 0) or 0)
        group = pre.get("group"); group_title = getattr(group, "title", None) if group is not None else self.cmb_target.currentText()
        plan_lines = []
        for account in pre.get("accounts") or []:
            if int(account.get("assigned_count", 0) or 0):
                plan_lines.append(f"{account.get('name')}: {int(account.get('assigned_count', 0))} member(s)")

        if QMessageBox.question(
            self, "Start Invitation Batch",
            f"Invite {ready} eligible member(s) to {group_title} using {len(account_ids)} selected account(s)?\n\n"
            + "\n".join(plan_lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return

        self.btn_start.setEnabled(False)
        self.lbl_progress.setText("Starting Add Members…")
        self.progress.setRange(0, max(1, ready)); self.progress.setValue(0)
        self.tabs.setCurrentIndex(2)

        self._running=True
        self.live_activity.start_job(self._live_account_plan_v5())

        token = self.controller.start_target_invitation_batch(
            int(self.cmb_target.currentData()), account_ids, self.member_ids
        )
        if token is None:
            self._running=False
            self.live_activity.finish(error_message="Add Members could not be queued.")
            self.btn_start.setEnabled(bool(pre.get("can_start", pre.get("start_allowed", False))))
            self._show_warning("Invitation could not be queued. Check plan access and Telegram runtime, then refresh permissions.")
            self.tabs.setCurrentIndex(1)
            self.lbl_progress.setText("Invitation not started")

    def _can_create_invite_link(self):
        selected = set(self._selected_account_ids())
        return bool(self.group_controller and self._precheck and any(int(row.get("account_id", 0)) in selected and row.get("can_manage_invite_links") for row in self._precheck.get("accounts") or []))

    def _create_invite_link(self):
        if not self._can_create_invite_link():
            self._show_warning("None of the selected accounts can create an invite link for this target."); return
        group = self._precheck.get("group"); selected_account_id = next((int(row["account_id"]) for row in self._precheck.get("accounts") or [] if row.get("can_manage_invite_links")), None)
        if not group or not selected_account_id: return
        mappings = list(self.controller.accounts_for_group(int(group.id)) or [])
        dialog = CreateTargetInviteLinkDialog(group.title, self, accounts=mappings, selected_account_id=selected_account_id)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        options = dialog.options(); account_id = options.pop("account_id", None)
        if not account_id:
            self._invite_link_failed("No authorized account with invite-link permission is available for this target."); return
        self.btn_invite_link.setEnabled(False); self.btn_invite_link.setText("Creating…")
        self.group_controller.create_target_invite_link(int(group.id), int(account_id), callback=self._invite_link_created, failure_callback=self._invite_link_failed, **options)

    def _invite_link_created(self, result):
        if self._closed:return
        self.btn_invite_link.setText("Create Invite Link"); payload = result or {}
        if not bool(payload.get("success", True)):
            self._invite_link_failed(payload.get("user_message") or payload.get("message") or "Invite link could not be created."); return
        self.btn_invite_link.setEnabled(self._can_create_invite_link()); link = str(payload.get("link") or "")
        if link:
            self._last_invite_link = link; QApplication.clipboard().setText(link)
            warning = str(payload.get("persistence_warning") or "").strip()
            message = "Invite link created and copied to the clipboard. Join requests can be reviewed separately when approval is required."
            if warning: message += f"\n\n{warning}"
            QMessageBox.information(self, "Invite Link Created", message)
        else: self._invite_link_failed("Telegram did not return an invite link.")

    def _invite_link_failed(self, message=None):
        if self._closed:return
        self.btn_invite_link.setText("Create Invite Link"); self.btn_invite_link.setEnabled(self._can_create_invite_link())
        self._show_warning(message or "Invite link could not be created."); self.tabs.setCurrentIndex(1)

    def _pause(self):
        self.controller.pause_target_invitation(); self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(True); self.lbl_progress.setText("Current account job paused. Completed results and fixed assignments are preserved.")

    def _resume(self):
        self.controller.resume_target_invitation(); self.btn_pause.setEnabled(True); self.btn_resume.setEnabled(False); self.lbl_progress.setText("Current account job resumed with the same explicitly selected account.")

    def _stop(self):
        self.controller.stop_target_invitation(); self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False); self.lbl_progress.setText("Stop requested. Completed results are preserved; unfinished members will not be reassigned.")

    def _progress(self, payload):
        if self._closed:return
        if not payload:return
        if payload.get("job_id"):
            self.btn_pause.setEnabled(True); self.btn_stop.setEnabled(True)

        processed = int(payload.get("processed", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        self.progress.setRange(0, max(1, total)); self.progress.setValue(processed)

        account = (
            f"Account {int(payload.get('account_index', 0))}/{int(payload.get('account_count', 0))}"
            if payload.get("account_count") else "Batch"
        )
        self.lbl_progress.setText(
            f"{account} • Processed {processed:,}/{total:,} • "
            f"Successful {int(payload.get('successful',0)):,} • "
            f"Skipped {int(payload.get('skipped',0)):,} • "
            f"Failed {int(payload.get('failed',0)):,} • "
            f"Current: {payload.get('current') or '—'}"
        )
        self.live_activity.update_progress(payload)

    def _completed(self, result):
        if self._closed:return
        result = result or {}
        self._running=False
        self._last_result = result
        self.live_activity.finish(result)

        self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False)
        status = str(result.get("status", "")).upper()

        if status == "BLOCKED":
            if result.get("results"):
                self.btn_results.setEnabled(True)
                self._progress({
                    "processed":result.get("processed",0),
                    "total":result.get("selected",0),
                    "successful":result.get("successful",0),
                    "skipped":result.get("skipped",0),
                    "failed":result.get("failed",0),
                    "current":"Stopped",
                })
                self.btn_pause.setEnabled(False); self.btn_stop.setEnabled(False)
                self._show_warning(result.get("message") or "The batch stopped safely.")
                self.lbl_progress.setText(
                    f"Batch stopped — {int(result.get('processed',0)):,} processed and "
                    f"{int(result.get('unprocessed',0)):,} left unprocessed."
                )
                return

            self._show_warning(result.get("message") or "Invitation was blocked by final preflight.")
            self.tabs.setCurrentIndex(1)
            self.lbl_progress.setText("Invitation not started. Review preflight and refresh permissions.")
            return

        self.btn_results.setEnabled(True)
        self.lbl_progress.setText(
            f"Invitation {_human(result.get('status','COMPLETED'))} — "
            f"{int(result.get('successful',0)):,} successful, "
            f"{int(result.get('skipped',0)):,} skipped, "
            f"{int(result.get('failed',0)):,} failed, "
            f"{int(result.get('unprocessed',0)):,} unprocessed."
        )
        if status in {"PAUSED","STOPPED","CANCELLED"}:
            self._show_warning(result.get("message") or "The batch stopped on the current account.")

    def _invitation_failed(self, message):
        if self._closed:return
        self._running=False
        self.live_activity.finish(error_message=message or "Invitation operation failed.")
        self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False)
        can_retry = bool(self._precheck and self._precheck.get("can_start", self._precheck.get("start_allowed", False)))
        self.btn_start.setEnabled(can_retry)
        self._show_warning(message or "Invitation operation failed before the job could start.")
        self.tabs.setCurrentIndex(1)
        self.lbl_progress.setText("Invitation failed to start — no additional member was processed.")

    def _show_results(self):
        if self._last_result: InvitationResultsDialog(self._last_result, self).exec()

# Add compatibility attributes for older PySide6 versions
if not hasattr(InvitationResultsDialog, 'Accepted'):
    InvitationResultsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(InvitationResultsDialog, 'Rejected'):
    InvitationResultsDialog.Rejected = QDialog.DialogCode.Rejected
