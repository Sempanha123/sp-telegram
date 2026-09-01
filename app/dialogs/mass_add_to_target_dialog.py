from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.dialogs.invite_members_to_target_dialog import InvitationResultsDialog


def _human(value, empty="—") -> str:
    text = str(value or "").strip()
    return text.replace("_", " ").title() if text else empty


class MassAddToTargetDialog(QDialog):
    """Auto-fill a Target Group from Source Groups using parallel accounts.

    The dialog pulls members from the Source Groups the user selects to reach a
    target count, round-robins them across up to 20 accounts (respecting each
    account's daily safety limit), runs 1..4 account jobs in parallel, auto-joins
    the target group for accounts that are not members yet, and reports whether
    the target was reached (with a source-shortage recommendation when it was not).
    """

    ACCOUNT_COLUMNS = ["Use", "Authorized Account", "Health", "Safety", "Today / Limit", "Target Access", "Can Invite", "Restriction", "Assigned"]

    def __init__(self, member_controller, *, target_group_id: int | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("dlg_mass_add_to_target")
        self.setWindowTitle("Mass Add to Target - SP Telegram")
        self.setMinimumSize(980, 680); self.resize(1120, 760)
        self.controller = member_controller
        self._preview = None
        self._last_result = None
        self._closed = False
        self._controller_connections = []
        self._job_ids: list[int] = []
        self._account_row_by_id = {}
        self._account_update_guard = False
        self._running = False
        self.summary: dict[str, QLabel] = {}

        root = QVBoxLayout(self); root.setContentsMargins(18, 16, 18, 16); root.setSpacing(10)
        title = QLabel("Mass Add to Target"); title.setProperty("dialogTitle", True); root.addWidget(title)
        note = QLabel(
            "Select the Source Groups to pull members from, then set a target total. "
            "Members are taken only from the Sources you check, round-robin across up to 20 accounts "
            "(each account respects its daily safety limit), and run 1–4 account jobs in parallel. "
            "Accounts that are not members of the target yet are joined first."
        )
        note.setWordWrap(True); note.setProperty("secondary", True); root.addWidget(note)

        self.tabs = QTabWidget(); self.tabs.setObjectName("tabs_mass_add_to_target"); root.addWidget(self.tabs, 1)
        self._build_setup_tab(target_group_id)
        self._build_preview_tab()
        self._build_progress_tab()

        actions = QHBoxLayout()
        self.btn_results = QPushButton("View Results"); self.btn_results.setObjectName("btn_view_mass_add_results"); self.btn_results.setEnabled(False)
        self.btn_cancel = QPushButton("Close")
        self.btn_start = QPushButton("Start Mass Add"); self.btn_start.setObjectName("btn_start_mass_add"); self.btn_start.setProperty("primary", True); self.btn_start.setEnabled(False)
        actions.addWidget(self.btn_results); actions.addStretch(); actions.addWidget(self.btn_cancel); actions.addWidget(self.btn_start); root.addLayout(actions)

        self.cmb_target.currentIndexChanged.connect(self._target_changed)
        self.btn_preview.clicked.connect(self._run_preview)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_resume.clicked.connect(self._resume)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_results.clicked.connect(self._show_results)
        self._connect_controller(self.controller.massTargetAddProgress, self._progress)
        self._connect_controller(self.controller.massTargetAddCompleted, self._completed)
        self._connect_controller(self.controller.massTargetAddFailed, self._failed)
        self._target_changed()

    def _connect_controller(self, signal, slot):
        try:
            signal.connect(slot); self._controller_connections.append((signal, slot))
        except (TypeError, RuntimeError):
            pass

    def done(self, result):
        self._closed = True
        for signal, slot in self._controller_connections:
            try: signal.disconnect(slot)
            except (TypeError, RuntimeError): pass
        self._controller_connections.clear()
        super().done(result)

    # ------------------------------------------------------------------ UI
    def _build_setup_tab(self, target_group_id):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(10)
        form = QFormLayout(); form.setHorizontalSpacing(18); form.setVerticalSpacing(8)
        self.cmb_target = QComboBox(); self.cmb_target.setObjectName("cmb_mass_add_target")
        for group in self.controller.target_groups():
            self.cmb_target.addItem(group.title + (f"  @{group.username}" if getattr(group, "username", None) else ""), int(group.id))
        if target_group_id:
            index = self.cmb_target.findData(int(target_group_id)); self.cmb_target.setCurrentIndex(max(0, index))
        self.spin_target_count = QSpinBox(); self.spin_target_count.setObjectName("spin_mass_add_target_count")
        self.spin_target_count.setRange(1, 5000); self.spin_target_count.setValue(2000)
        self.spin_parallel = QSpinBox(); self.spin_parallel.setObjectName("spin_mass_add_parallel")
        self.spin_parallel.setRange(1, 4); self.spin_parallel.setValue(2)
        form.addRow("Target", self.cmb_target)
        form.addRow("Total", self.spin_target_count)
        form.addRow("Parallel", self.spin_parallel)
        layout.addLayout(form)

        heading = QLabel("Sources"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        hint_sources = QLabel("Check the Source Groups to pull members from. Members are collected from the checked Sources only — nothing is auto-selected.")
        hint_sources.setProperty("secondary", True); hint_sources.setWordWrap(True); layout.addWidget(hint_sources)
        self.list_sources = QListWidget(); self.list_sources.setObjectName("list_mass_add_sources")
        self.list_sources.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for group in self.controller.source_groups():
            item = QListWidgetItem(group.title + (f"  @{group.username}" if getattr(group, "username", None) else ""))
            item.setData(Qt.ItemDataRole.UserRole, int(group.id)); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked)
            self.list_sources.addItem(item)
        self.list_sources.setMinimumHeight(120)
        layout.addWidget(self.list_sources, 1)

        heading = QLabel("Accounts (up to 20)"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        hint = QLabel("Accounts that are not members of the target yet are auto-joined before adding starts.")
        hint.setProperty("secondary", True); hint.setWordWrap(True); layout.addWidget(hint)
        self.chk_skip_used = QCheckBox("Skip accounts already used to invite to this target")
        self.chk_skip_used.setObjectName("chk_mass_add_skip_used"); self.chk_skip_used.setToolTip("Hides accounts that already ran a successful invite job for this target, so the same account is not reused for the same target.")
        layout.addWidget(self.chk_skip_used)
        self.table_accounts = QTableWidget(0, len(self.ACCOUNT_COLUMNS)); self.table_accounts.setObjectName("tbl_mass_add_accounts")
        self.table_accounts.setHorizontalHeaderLabels(self.ACCOUNT_COLUMNS); self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_accounts.setAlternatingRowColors(True); self.table_accounts.setMinimumHeight(200)
        header = self.table_accounts.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_accounts, 1)
        bar = QHBoxLayout()
        self.btn_select_valid = QPushButton("Select Valid Accounts"); self.btn_select_valid.setObjectName("btn_select_mass_add_accounts")
        self.btn_clear_accounts = QPushButton("Clear Selection")
        self.lbl_account_selection = QLabel("0 selected"); self.lbl_account_selection.setProperty("secondary", True)
        bar.addWidget(self.btn_select_valid); bar.addWidget(self.btn_clear_accounts); bar.addStretch(); bar.addWidget(self.lbl_account_selection); layout.addLayout(bar)
        self.btn_preview = QPushButton("Preview Plan"); self.btn_preview.setObjectName("btn_mass_add_preview"); self.btn_preview.setProperty("primary", True)
        layout.addWidget(self.btn_preview)
        self.btn_select_valid.clicked.connect(self._select_valid_accounts)
        self.btn_clear_accounts.clicked.connect(self._clear_accounts)
        self.table_accounts.itemChanged.connect(self._account_item_changed)
        self.chk_skip_used.toggled.connect(self._skip_used_toggled)
        self.tabs.addTab(tab, "Setup")

    def _build_preview_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(10)
        heading = QLabel("Plan Preview"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        summary_box = QWidget(); grid = QGridLayout(summary_box); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8); self.summary = {}
        fields = [
            ("target", "Target"), ("candidates", "Candidates"), ("shortage", "Shortage"),
            ("capacity", "Account Capacity"), ("assigned", "Will Add"), ("accounts", "Accounts"),
        ]
        for i, (key, label) in enumerate(fields):
            cell = QWidget(); cell_layout = QVBoxLayout(cell); cell_layout.setContentsMargins(10, 7, 10, 7); cell_layout.setSpacing(2)
            lab = QLabel(label); lab.setProperty("secondary", True); num = QLabel("0"); num.setProperty("metric", True)
            cell_layout.addWidget(lab); cell_layout.addWidget(num); self.summary[key] = num; grid.addWidget(cell, i // 3, i % 3)
        layout.addWidget(summary_box)
        self.lbl_preview_status = QLabel("Select source groups and accounts, then run Preview Plan."); self.lbl_preview_status.setProperty("secondary", True); self.lbl_preview_status.setWordWrap(True); layout.addWidget(self.lbl_preview_status)
        self.lbl_warning = QPlainTextEdit(); self.lbl_warning.setObjectName("lbl_mass_add_warning"); self.lbl_warning.setReadOnly(True); self.lbl_warning.setMaximumHeight(150); self.lbl_warning.setProperty("warning", True); self.lbl_warning.hide(); layout.addWidget(self.lbl_warning)
        self.table_plan = QTableWidget(0, 6); self.table_plan.setObjectName("tbl_mass_add_plan")
        self.table_plan.setHorizontalHeaderLabels(["Account", "Health", "Safety", "Today / Limit", "Capacity", "Assigned"])
        self.table_plan.verticalHeader().setVisible(False); self.table_plan.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_plan.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table_plan.setAlternatingRowColors(True)
        header = self.table_plan.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_plan, 1)
        self.tabs.addTab(tab, "Preview")

    def _build_progress_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(12)
        heading = QLabel("Progress"); heading.setProperty("sectionTitle", True); layout.addWidget(heading)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0); layout.addWidget(self.progress)
        self.lbl_progress = QLabel("Preview the plan first."); self.lbl_progress.setProperty("secondary", True); self.lbl_progress.setWordWrap(True); layout.addWidget(self.lbl_progress)
        self.table_run = QTableWidget(0, 6); self.table_run.setObjectName("tbl_mass_add_run")
        self.table_run.setHorizontalHeaderLabels(["Account", "Status", "Processed", "Successful", "Skipped", "Failed"])
        self.table_run.verticalHeader().setVisible(False); self.table_run.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_run.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table_run.setAlternatingRowColors(True)
        header = self.table_run.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_run, 1)
        controls = QHBoxLayout()
        self.btn_pause = QPushButton("Pause"); self.btn_pause.setObjectName("btn_pause_mass_add")
        self.btn_resume = QPushButton("Resume"); self.btn_resume.setObjectName("btn_resume_mass_add")
        self.btn_stop = QPushButton("Stop"); self.btn_stop.setObjectName("btn_stop_mass_add")
        for button in (self.btn_pause, self.btn_resume, self.btn_stop): button.setEnabled(False); controls.addWidget(button)
        controls.addStretch(); layout.addLayout(controls); layout.addStretch()
        self.tabs.addTab(tab, "Progress")

    @staticmethod
    def _item(text="—"):
        item = QTableWidgetItem(str(text)); item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable); return item

    # ------------------------------------------------------------- accounts
    def _used_account_ids(self):
        target_id = self.cmb_target.currentData()
        if not target_id:
            return set()
        try:
            return set(self.controller.used_account_ids_for_target(int(target_id)) or [])
        except Exception:
            return set()

    def _target_changed(self, _index: int = -1):
        del _index
        target_id = self.cmb_target.currentData()
        mappings = list(self.controller.accounts_for_group(int(target_id)) or []) if target_id else []
        used = self._used_account_ids() if self.chk_skip_used.isChecked() else set()
        self._account_row_by_id = {}
        self._account_update_guard = True; self.table_accounts.blockSignals(True); self.table_accounts.setRowCount(len(mappings))
        for row, mapping in enumerate(mappings):
            account_id = int(mapping.account_id); self._account_row_by_id[account_id] = row
            access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper()
            accessible = access not in {"ACCESS_DENIED", "NO_ACCESS", "BANNED", "LEFT", "UNAVAILABLE"}
            already_used = account_id in used
            check = QTableWidgetItem(); check.setData(Qt.ItemDataRole.UserRole, account_id); check.setCheckState(Qt.CheckState.Unchecked)
            if already_used:
                check.setFlags(Qt.ItemFlag.ItemIsSelectable)
            else:
                check.setFlags((Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable) if accessible else Qt.ItemFlag.ItemIsSelectable)
            name = getattr(mapping, "account_name", None) or f"Account {account_id}"
            if getattr(mapping, "account_username", None): name += f"  •  @{mapping.account_username}"
            if already_used: name += "  •  already used"
            self.table_accounts.setItem(row, 0, check); self.table_accounts.setItem(row, 1, self._item(name))
            self.table_accounts.setItem(row, 2, self._item(_human(getattr(mapping, "health_status", "UNKNOWN"))))
            self.table_accounts.setItem(row, 3, self._item("—"))
            self.table_accounts.setItem(row, 4, self._item("—"))
            self.table_accounts.setItem(row, 5, self._item(_human(getattr(mapping, "role", None) or access)))
            self.table_accounts.setItem(row, 6, self._item("Yes" if bool(getattr(mapping, "can_invite", 0)) else "No"))
            self.table_accounts.setItem(row, 7, self._item(_human(getattr(mapping, "restriction_type", None), "None")))
            self.table_accounts.setItem(row, 8, self._item("—"))
        self.table_accounts.blockSignals(False); self._account_update_guard = False
        self._preview = None; self._set_account_selection_text()

    def _skip_used_toggled(self, checked):
        self._target_changed()
        if checked:
            self._show_warning("Accounts that already ran a successful invite job for this target are disabled and marked 'already used'.")
        else:
            self._show_warning()

    def _selected_account_ids(self):
        selected = []
        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def _selected_source_ids(self):
        ids = []
        for row in range(self.list_sources.count()):
            item = self.list_sources.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _set_account_selection_text(self):
        if self.table_accounts.rowCount() == 0:
            self.lbl_account_selection.setText("No mapped authorized accounts for this target"); return
        count = len(self._selected_account_ids())
        self.lbl_account_selection.setText(f"{count} selected  •  max 20")

    def _account_item_changed(self, item):
        if self._account_update_guard or not item or item.column() != 0:
            return
        selected = self._selected_account_ids()
        if len(selected) > 20:
            self._account_update_guard = True; item.setCheckState(Qt.CheckState.Unchecked); self._account_update_guard = False
            self._show_warning("Select no more than 20 accounts for a mass add.")
        self._set_account_selection_text(); self._preview = None; self.btn_start.setEnabled(False)

    def _select_valid_accounts(self):
        chosen = 0; self._account_update_guard = True; self.table_accounts.blockSignals(True)
        used = self._used_account_ids() if self.chk_skip_used.isChecked() else set()
        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0); account_id = int(item.data(Qt.ItemDataRole.UserRole)) if item and item.data(Qt.ItemDataRole.UserRole) else None
            mapping = next((m for m in (self.controller.accounts_for_group(self.cmb_target.currentData()) or []) if int(m.account_id) == account_id), None) if account_id else None
            access = str(getattr(mapping, "access_state", "UNKNOWN") or "UNKNOWN").upper() if mapping else "UNKNOWN"
            health = str(getattr(mapping, "health_status", "UNKNOWN") or "UNKNOWN").upper() if mapping else "UNKNOWN"
            valid = bool(mapping and bool(getattr(mapping, "can_invite", 0)) and access not in {"ACCESS_DENIED", "NO_ACCESS", "BANNED", "LEFT", "UNAVAILABLE"} and health not in {"COOLDOWN", "RESTRICTED", "SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"} and account_id not in used)
            checked = valid and chosen < 20
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable: item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            if checked: chosen += 1
        self.table_accounts.blockSignals(False); self._account_update_guard = False; self._set_account_selection_text(); self._preview = None; self.btn_start.setEnabled(False)
        if chosen == 0: self._show_warning("No account currently has cached invite permission and healthy target access. Refresh group permissions or choose an account for a live preview.")

    def _clear_accounts(self):
        self._account_update_guard = True; self.table_accounts.blockSignals(True)
        for row in range(self.table_accounts.rowCount()):
            item = self.table_accounts.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable: item.setCheckState(Qt.CheckState.Unchecked)
        self.table_accounts.blockSignals(False); self._account_update_guard = False; self._set_account_selection_text(); self._preview = None; self.btn_start.setEnabled(False)

    def _show_warning(self, message=None):
        text = str(message or "").strip()
        if text: self.lbl_warning.setPlainText(text); self.lbl_warning.show()
        else: self.lbl_warning.clear(); self.lbl_warning.hide()

    # --------------------------------------------------------------- preview
    def _run_preview(self):
        target_id = self.cmb_target.currentData(); source_ids = self._selected_source_ids(); account_ids = self._selected_account_ids()
        if not target_id:
            self._show_warning("Select a Target Group first."); return
        if not source_ids:
            self._show_warning("Select at least one Source Group to pull members from."); return
        if not account_ids:
            self._show_warning("Select at least one authorized account."); return
        self.btn_preview.setEnabled(False); self.btn_preview.setText("Previewing…")
        self.lbl_preview_status.setText("Checking candidate availability and per-account daily capacity…")
        result = self.controller.mass_target_add_preview(int(target_id), int(self.spin_target_count.value()), source_ids, account_ids)
        self.btn_preview.setEnabled(True); self.btn_preview.setText("Preview Plan")
        if not result:
            self._show_warning("Mass add preview could not be completed."); self.lbl_preview_status.setText("Preview unavailable"); return
        self._preview = result
        counts = result
        self.summary["target"].setText(f"{int(counts.get('target_count', 0)):,}")
        self.summary["candidates"].setText(f"{int(counts.get('candidate_count', 0)):,}")
        self.summary["shortage"].setText(f"{int(counts.get('shortage', 0)):,}")
        self.summary["capacity"].setText(f"{int(counts.get('capacity', 0)):,}")
        self.summary["assigned"].setText(f"{int(counts.get('assigned_total', 0)):,}")
        self.summary["accounts"].setText(f"{len(counts.get('accounts') or [])}")
        self.table_plan.setRowCount(0)
        for row in counts.get("accounts") or []:
            r = self.table_plan.rowCount(); self.table_plan.insertRow(r)
            self.table_plan.setItem(r, 0, self._item(row.get("name")))
            self.table_plan.setItem(r, 1, self._item(_human(row.get("health"), "Unknown")))
            self.table_plan.setItem(r, 2, self._item(_human(row.get("safety_state"), "Normal")))
            self.table_plan.setItem(r, 3, self._item(f"{int(row.get('invite_used_today', 0) or 0)}/{int(row.get('invite_daily_limit', 0) or 0)}" if row.get("smart_limits") else "Manual"))
            self.table_plan.setItem(r, 4, self._item(str(int(row.get("batch_capacity", 0) or 0))))
            self.table_plan.setItem(r, 5, self._item(str(int(row.get("assigned_count", 0) or 0))))
        blockers = list(counts.get("blocking_reasons") or []); warnings = list(counts.get("warnings") or [])
        messages = blockers + warnings
        self._show_warning("\n".join(f"• {message}" for message in messages))
        can_start = bool(counts.get("can_start", counts.get("start_allowed", False)))
        self.btn_start.setEnabled(can_start)
        if not can_start:
            self.lbl_preview_status.setText((blockers or ["No members are currently available for the selected sources and accounts."])[0])
        else:
            self.lbl_preview_status.setText(f"Plan ready: {int(counts.get('assigned_total', 0)):,} will be added across {len(counts.get('assignments') or [])} account job(s).")
        self.tabs.setCurrentIndex(1)

    # ----------------------------------------------------------------- start
    def _start(self):
        pre = self._preview or {}
        if not pre:
            self._show_warning("Run Preview Plan first."); self.tabs.setCurrentIndex(1); return
        if not bool(pre.get("can_start", pre.get("start_allowed", False))):
            self.btn_start.setEnabled(False); self._show_warning("The plan is not ready. Review the preview warnings."); self.tabs.setCurrentIndex(1); return
        target_id = int(self.cmb_target.currentData()); source_ids = self._selected_source_ids(); account_ids = self._selected_account_ids()
        target_count = int(self.spin_target_count.value()); parallel = int(self.spin_parallel.value())
        group_title = self.cmb_target.currentText()
        plan_lines = []
        for assignment in pre.get("assignments") or []:
            plan_lines.append(f"Account {int(assignment['account_id'])}: {int(assignment['count'])}")
        if QMessageBox.question(
            self, "Start Mass Add",
            f"Add up to {target_count:,} to {group_title} using {len(account_ids)} account(s) with {parallel} parallel job(s)?\n\n"
            + "\n".join(plan_lines)
            + "\n\nEach account respects its daily safety limit. Accounts not yet in the target are auto-joined first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._running = True
        self.btn_start.setEnabled(False); self.btn_preview.setEnabled(False)
        self.progress.setRange(0, max(1, target_count)); self.progress.setValue(0)
        self.lbl_progress.setText("Preparing parallel account jobs…")
        self.tabs.setCurrentIndex(2)
        self._job_ids = []
        self.table_run.setRowCount(0)
        for row in pre.get("accounts") or []:
            r = self.table_run.rowCount(); self.table_run.insertRow(r)
            self.table_run.setItem(r, 0, self._item(row.get("name")))
            self.table_run.setItem(r, 1, self._item("Queued"))
            self.table_run.setItem(r, 2, self._item("0")); self.table_run.setItem(r, 3, self._item("0"))
            self.table_run.setItem(r, 4, self._item("0")); self.table_run.setItem(r, 5, self._item("0"))
        token = self.controller.start_mass_target_add(int(target_id), target_count, source_ids, account_ids, parallel)
        if token is None:
            self._running = False
            self.btn_start.setEnabled(bool(pre.get("can_start", pre.get("start_allowed", False)))); self.btn_preview.setEnabled(True)
            self._show_warning("Mass add could not be queued. Check the Telegram runtime and try again."); self.tabs.setCurrentIndex(1); self.lbl_progress.setText("Mass add not started")

    def _pause(self):
        self.controller.pause_mass_target_add(self._job_ids); self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(True)
        self.lbl_progress.setText("Mass add paused. Completed results are preserved.")

    def _resume(self):
        self.controller.resume_mass_target_add(self._job_ids); self.btn_pause.setEnabled(True); self.btn_resume.setEnabled(False)
        self.lbl_progress.setText("Mass add resumed.")

    def _stop(self):
        self.controller.stop_mass_target_add(self._job_ids); self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False)
        self.lbl_progress.setText("Stop requested. Completed results are preserved; unfinished members will not be reassigned.")

    def _progress(self, payload):
        if self._closed or not payload: return
        if payload.get("job_id"): self.btn_pause.setEnabled(True); self.btn_stop.setEnabled(True)
        processed = int(payload.get("processed", 0) or 0); total = int(payload.get("total", 0) or 0)
        self.progress.setRange(0, max(1, total)); self.progress.setValue(processed)
        account_id = payload.get("account_id")
        if account_id is not None:
            row = self._account_row_by_id.get(int(account_id))
            if row is not None and row < self.table_run.rowCount():
                item = self.table_run.item(row, 1)
                if item is not None:
                    item.setText(_human(payload.get("status"), "Running"))
                for col, key in ((2, "processed"), (3, "successful"), (4, "skipped"), (5, "failed")):
                    cell = self.table_run.item(row, col)
                    if cell is not None:
                        cell.setText(str(int(payload.get(key, 0) or 0)))
        target_count = int(payload.get("target_count", 0) or 0); shortage = int(payload.get("shortage", 0) or 0)
        suffix = f"  •  Target {target_count:,}  •  Short {shortage:,}" if target_count else ""
        self.lbl_progress.setText(
            f"Processed {processed:,} / {total:,}  •  Successful {int(payload.get('successful', 0)):,}  •  "
            f"Skipped {int(payload.get('skipped', 0)):,}  •  Failed {int(payload.get('failed', 0)):,}  •  Current: {payload.get('current') or '—'}{suffix}"
        )

    def _completed(self, result):
        if self._closed: return
        result = result or {}; self._last_result = result; self._running = False
        self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False)
        status = str(result.get("status", "")).upper()
        if status == "BLOCKED":
            if result.get("results"):
                self.btn_results.setEnabled(True)
                self.lbl_progress.setText(f"Mass add stopped — {int(result.get('processed', 0)):,} processed and {int(result.get('unprocessed', 0)):,} left unprocessed.")
                self._show_warning(result.get("message") or "The mass add stopped. Unfinished members were not reassigned.")
                return
            self._show_warning(result.get("message") or "Mass add was blocked by preflight."); self.tabs.setCurrentIndex(1)
            self.lbl_progress.setText("Mass add not started. Review the preview and refresh permissions."); return
        self.btn_results.setEnabled(True)
        finished = bool(result.get("finished")); shortage = int(result.get("shortage", 0) or 0)
        self.lbl_progress.setText(
            f"Mass add {_human(result.get('status', 'COMPLETED'))} — {int(result.get('successful', 0)):,} successful, "
            f"{int(result.get('skipped', 0)):,} skipped, {int(result.get('failed', 0)):,} failed, {int(result.get('unprocessed', 0)):,} unprocessed. "
            f"Target {'reached' if finished else 'NOT reached'} ({shortage:,} short)."
        )
        if not finished:
            self._show_warning(f"The target total was not reached. {shortage:,} more members are needed — add more Sources or sync more members first.")
        elif status in {"PAUSED", "STOPPED", "CANCELLED"}:
            self._show_warning(result.get("message") or "The mass add stopped before reaching the target.")

    def _failed(self, message):
        if self._closed: return
        self._running = False
        self.btn_pause.setEnabled(False); self.btn_resume.setEnabled(False); self.btn_stop.setEnabled(False)
        self.btn_start.setEnabled(bool(self._preview and self._preview.get("can_start", self._preview.get("start_allowed", False)))); self.btn_preview.setEnabled(True)
        self._show_warning(message or "Mass add operation failed before the job could start.")
        self.tabs.setCurrentIndex(1); self.lbl_progress.setText("Mass add failed to start — no additional member was processed.")

    def _show_results(self):
        if self._last_result: InvitationResultsDialog(self._last_result, self).exec()
# Add compatibility attributes for older PySide6 versions
if not hasattr(MassAddToTargetDialog, 'Accepted'):
    MassAddToTargetDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(MassAddToTargetDialog, 'Rejected'):
    MassAddToTargetDialog.Rejected = QDialog.DialogCode.Rejected
