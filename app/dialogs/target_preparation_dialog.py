from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from app.dialogs.create_target_invite_link_dialog import CreateTargetInviteLinkDialog
from app.dialogs.invite_members_to_target_dialog import InviteMembersToTargetDialog
from app.models.base_table_model import BaseTableModel
from app.utils.table_preferences import TablePreferenceManager
from app.utils.member_display_formatter import MemberDisplayFormatter, MemberDisplayPreferences
from app.utils.table_layout_manager import TableLayoutManager
from app.widgets.select_all_header import SelectAllHeader
from app.widgets.table_checkbox_delegate import TableCheckBoxDelegate


class TargetPreparationModel(BaseTableModel):
    checkedChanged = Signal()

    def __init__(self, rows, columns, parent=None):
        super().__init__(rows, columns, parent)
        self.checked_ids: set[int] = set()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if index.isValid() and self.columns[index.column()] == "Select":
            if role == Qt.ItemDataRole.CheckStateRole:
                mid = int(self.rows[index.row()].get("_member_id", 0) or 0)
                return Qt.CheckState.Checked if mid in self.checked_ids else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.DisplayRole:
                return ""
        return super().data(index, role)

    def flags(self, index: QModelIndex):
        flags = super().flags(index)
        if index.isValid() and self.columns[index.column()] == "Select":
            return flags | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        return flags

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole):
        if index.isValid() and self.columns[index.column()] == "Select" and role == Qt.ItemDataRole.CheckStateRole:
            mid = int(self.rows[index.row()].get("_member_id", 0) or 0)
            if not mid:
                return False
            if value == Qt.CheckState.Checked:
                self.checked_ids.add(mid)
            else:
                self.checked_ids.discard(mid)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.checkedChanged.emit()
            return True
        return False

    def replace_rows(self, rows):
        visible = {int(row.get("_member_id", 0) or 0) for row in rows}
        self.checked_ids.intersection_update(visible)
        super().replace_rows(rows)
        self.checkedChanged.emit()

    def checked_member_ids(self) -> list[int]:
        return sorted(self.checked_ids)

    def set_all_visible_checked(self, checked: bool) -> None:
        visible = {int(row.get("_member_id", 0) or 0) for row in self.rows if row.get("_member_id")}
        if checked:
            self.checked_ids.update(visible)
        else:
            self.checked_ids.difference_update(visible)
        if self.rowCount():
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount()-1, 0), [Qt.ItemDataRole.CheckStateRole])
        self.checkedChanged.emit()

    def visible_check_state(self):
        ids = {int(row.get("_member_id", 0) or 0) for row in self.rows if row.get("_member_id")}
        if not ids or not (ids & self.checked_ids):
            return Qt.CheckState.Unchecked
        return Qt.CheckState.Checked if ids.issubset(self.checked_ids) else Qt.CheckState.PartiallyChecked


class TargetPreparationDialog(QDialog):
    """Database-first preparation workflow for one managed target.

    The table loads a bounded page of prepared candidates. Counts remain SQL
    aggregate queries.  Direct invitation, when licensed, is delegated to the
    explicit one-account invitation dialog; there is no account rotation.
    """

    COLUMNS = ["Select", "Name", "Username", "Sources", "Eligibility", "Consent", "Target Status", "Tags"]
    WIDTHS = {"Select": 44, "Name": 210, "Username": 190, "Sources": 210, "Eligibility": 145,
              "Consent": 140, "Target Status": 155, "Tags": 190}

    def __init__(self, member_controller, group_controller=None, target_group_id: int | None = None, *, member_ids: list[int] | None = None, scope_mode: str = "FILTERED_MEMBER_POOL", parent=None):
        super().__init__(parent)
        self.setObjectName("dlg_target_preparation")
        self.setWindowTitle("Prepare Members for Target - SP Telegram")
        self.setMinimumSize(980, 690)
        self.member_controller = member_controller
        self.group_controller = group_controller
        self.settings = QSettings()
        self.table_prefs = TablePreferenceManager(self.settings, self)
        self._current = None
        self._last_invite_link = None
        self.input_member_ids = sorted({int(x) for x in (member_ids or []) if int(x) > 0})
        self.scope_mode = "SOURCE_SELECTION" if self.input_member_ids and str(scope_mode).upper() == "SOURCE_SELECTION" else "FILTERED_MEMBER_POOL"

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        title = QLabel("Prepare Members for Target")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        subtitle = QLabel("Filter and review local Member Pool records before a managed invite-link/join-request workflow or an explicit approved-member invitation.")
        subtitle.setProperty("secondary", True)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        self.lbl_prepare_scope = QLabel(
            f"Scope: {len(self.input_member_ids):,} selected Member Pool record(s)" if self.scope_mode == "SOURCE_SELECTION"
            else "Scope: Current Member Pool filters"
        )
        self.lbl_prepare_scope.setObjectName("lbl_prepare_scope"); self.lbl_prepare_scope.setProperty("secondary", True); root.addWidget(self.lbl_prepare_scope)

        self._build_target_card(root)
        self._build_filters(root)
        self._build_summary(root)

        self.model = TargetPreparationModel([], self.COLUMNS, self)
        self.table = QTableView()
        self.table.setObjectName("tbl_target_preparation")
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        header = SelectAllHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(header)
        self.table.setItemDelegateForColumn(0, TableCheckBoxDelegate(self.table))
        header.setSectionsMovable(True)
        header.setMinimumSectionSize(60)
        for name, width in self.WIDTHS.items():
            col = self.COLUMNS.index(name)
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)
        root.addWidget(self.table, 1)
        self.table_prefs.register(self.table, self.COLUMNS, default_widths=self.WIDTHS)
        self.layout_manager = TableLayoutManager(self); self.layout_manager.apply(self.table, self.COLUMNS)

        self.lbl_prepare_selected = QLabel("0 selected")
        self.lbl_prepare_selected.setObjectName("lbl_prepare_selected")
        self.lbl_prepare_selected.setProperty("secondary", True)
        root.addWidget(self.lbl_prepare_selected)
        self.model.checkedChanged.connect(self._selection_changed)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)

        note = QLabel("UNKNOWN target status remains UNKNOWN until a full target-member sync or an explicit permitted membership check confirms otherwise.")
        note.setProperty("secondary", True)
        note.setWordWrap(True)
        root.addWidget(note)

        actions = QHBoxLayout()
        self.btn_export = QPushButton("Export Eligible")
        self.btn_export.setObjectName("btn_export_target_eligible")
        self.btn_invite_link = QPushButton("Create Invite Link")
        self.btn_invite_link.setObjectName("btn_create_target_invite_link")
        self.btn_invite_selected = QPushButton("Invite Selected")
        self.btn_invite_selected.setObjectName("btn_invite_selected_target")
        self.btn_invite_selected.setProperty("role", "primary")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("btn_refresh_target_preparation")
        self.btn_refresh.setProperty("primary", True)
        self.btn_refresh.setEnabled(False)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("btn_close_target_preparation")
        actions.addWidget(self.btn_export)
        actions.addWidget(self.btn_invite_link)
        actions.addWidget(self.btn_invite_selected)
        actions.addStretch()
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_close)
        root.addLayout(actions)

        self.btn_export.clicked.connect(self._export)
        self.btn_invite_link.clicked.connect(self._create_invite_link)
        self.btn_invite_selected.clicked.connect(self._invite_selected)
        self.btn_refresh.clicked.connect(self._refresh)
        self.btn_close.clicked.connect(self.accept)

        self._load_defaults()
        self._load_options(target_group_id)
        self._refresh()

    def _build_target_card(self, root):
        card = QWidget()
        card.setObjectName("card_target_preparation_target")
        layout = QFormLayout(card)
        layout.setHorizontalSpacing(24)
        layout.setVerticalSpacing(7)
        
        # Target group selection - multi-select list
        self.list_targets = QListWidget()
        self.list_targets.setObjectName("list_prepare_targets")
        self.list_targets.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_targets.setMinimumHeight(100)
        self.list_targets.setMaximumHeight(150)
        
        self.lbl_target_username = QLabel("—")
        self.lbl_primary_account = QLabel("—")
        self.lbl_target_access = QLabel("—")
        self.lbl_invite_permission = QLabel("—")
        self.lbl_join_workflow = QLabel("Join Request Required")
        self.lbl_known_members = QLabel("0")
        self.lbl_last_member_sync = QLabel("Never")
        
        layout.addRow("Target Groups (check to select)", self.list_targets)
        layout.addRow("Username", self.lbl_target_username)
        layout.addRow("Primary Account", self.lbl_primary_account)
        layout.addRow("Access", self.lbl_target_access)
        layout.addRow("Invite Permission", self.lbl_invite_permission)
        layout.addRow("Join Workflow", self.lbl_join_workflow)
        layout.addRow("Current Known Members", self.lbl_known_members)
        layout.addRow("Last Member Sync", self.lbl_last_member_sync)
        root.addWidget(card)

    def _build_filters(self, root):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.cmb_source = QComboBox(); self.cmb_source.setObjectName("cmb_prepare_member_source")
        self.cmb_eligibility = QComboBox(); self.cmb_eligibility.setObjectName("cmb_prepare_eligibility")
        self.cmb_consent = QComboBox(); self.cmb_consent.setObjectName("cmb_prepare_consent")
        self.cmb_tags = QComboBox(); self.cmb_tags.setObjectName("cmb_prepare_tags")
        self.le_username = QLineEdit(); self.le_username.setObjectName("le_prepare_username"); self.le_username.setPlaceholderText("Username contains…")
        controls = [("Member Source", self.cmb_source), ("Eligibility", self.cmb_eligibility),
                    ("Consent", self.cmb_consent), ("Tags", self.cmb_tags), ("Username", self.le_username)]
        for index, (label, control) in enumerate(controls):
            col = index % 3; row = (index // 3) * 2
            grid.addWidget(QLabel(label), row, col); grid.addWidget(control, row+1, col)
        self.chk_existing = QCheckBox("Exclude Existing"); self.chk_existing.setObjectName("chk_prepare_exclude_existing")
        self.chk_blacklist = QCheckBox("Exclude Blacklist"); self.chk_blacklist.setObjectName("chk_prepare_exclude_blacklist")
        self.chk_dnc = QCheckBox("Exclude Do Not Contact"); self.chk_dnc.setObjectName("chk_prepare_exclude_dnc")
        self.chk_deleted = QCheckBox("Exclude Deleted"); self.chk_deleted.setObjectName("chk_prepare_exclude_deleted")
        self.chk_bots = QCheckBox("Exclude Bots"); self.chk_bots.setObjectName("chk_prepare_exclude_bots")
        checks = QHBoxLayout()
        for chk in (self.chk_existing, self.chk_blacklist, self.chk_dnc, self.chk_deleted, self.chk_bots): checks.addWidget(chk)
        checks.addStretch(); grid.addLayout(checks, 4, 0, 1, 3)
        root.addWidget(box)

    def _build_summary(self, root):
        box = QWidget(); grid = QGridLayout(box); grid.setContentsMargins(0, 0, 0, 0)
        self.summary_labels = {}
        for index, (key, title) in enumerate([
            ("input_selection", "Input Selection"), ("eligible", "Eligible After Filters"), ("ready", "Ready to Invite"),
            ("selected", "Dialog Selected"), ("existing", "Already Member"), ("blacklist", "Blacklist"),
            ("do_not_contact", "Do Not Contact"), ("consent_not_approved", "Consent Not Approved"),
            ("unknown", "Unknown Target"), ("deleted", "Deleted"), ("bots", "Bots"),
        ]):
            host=QWidget(); v=QVBoxLayout(host); v.setContentsMargins(8,6,8,6); v.setSpacing(2)
            label=QLabel(title); label.setProperty("secondary", True)
            value=QLabel("0"); value.setProperty("metric", True)
            v.addWidget(label); v.addWidget(value); grid.addWidget(host, index // 6, index % 6); self.summary_labels[key]=value
        root.addWidget(box)

    def _load_defaults(self):
        p = self.table_prefs
        self._default_eligibility = str(p.global_value("require_eligibility", "ELIGIBLE")).replace("_", " ").title()
        self._default_consent = str(p.global_value("require_consent", "APPROVED")).replace("_", " ").title()
        self._default_checks = {
            "existing": bool(p.global_value("exclude_existing", True)),
            "blacklist": bool(p.global_value("exclude_blacklist", True)),
            "dnc": bool(p.global_value("exclude_do_not_contact", True)),
            "bots": bool(p.global_value("exclude_bots", True)),
        }

    def _load_options(self, target_group_id):
        self.list_targets.blockSignals(True)
        self.list_targets.clear()
        targets = self.member_controller.target_groups()
        default_target = int(self.table_prefs.global_value("default_target_id", 0) or 0)
        wanted = int(target_group_id or default_target or 0)
        for group in targets:
            label = group.title + (f"  @{group.username}" if group.username else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(group.id))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if wanted and int(group.id) == wanted else Qt.CheckState.Unchecked)
            self.list_targets.addItem(item)
        self.list_targets.blockSignals(False)

        for group in self.member_controller.all_source_groups():
            self.cmb_source.addItem(group.title + (f"  @{group.username}" if group.username else ""), int(group.id))
        self.cmb_eligibility.addItems(["Eligible", "All", "Unknown", "Manual Review", "Excluded", "Do Not Contact"])
        self.cmb_consent.addItems(["Approved", "All", "Opted In", "Unknown", "Declined", "Revoked"])
        if self._default_eligibility in [self.cmb_eligibility.itemText(i) for i in range(self.cmb_eligibility.count())]: self.cmb_eligibility.setCurrentText(self._default_eligibility)
        if self._default_consent in [self.cmb_consent.itemText(i) for i in range(self.cmb_consent.count())]: self.cmb_consent.setCurrentText(self._default_consent)
        self.cmb_tags.addItem("All"); self.cmb_tags.addItems(self.member_controller.tags())
        self.chk_existing.setChecked(self._default_checks["existing"])
        self.chk_blacklist.setChecked(self._default_checks["blacklist"])
        self.chk_dnc.setChecked(self._default_checks["dnc"])
        self.chk_deleted.setChecked(True)
        self.chk_bots.setChecked(self._default_checks["bots"])

        self.list_targets.itemChanged.connect(self._mark_filters_changed)
        for combo in (self.cmb_source, self.cmb_eligibility, self.cmb_consent, self.cmb_tags): combo.currentIndexChanged.connect(self._mark_filters_changed)
        self.le_username.textChanged.connect(self._mark_filters_changed)
        for chk in (self.chk_existing, self.chk_blacklist, self.chk_dnc, self.chk_deleted, self.chk_bots): chk.toggled.connect(self._mark_filters_changed)

    def _mark_filters_changed(self, *_args):
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Refresh (Filters Changed)")

    def _selected_ids(self) -> list[int]:
        ids = set(self.model.checked_member_ids())
        selection = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        for idx in selection:
            row = self.model.row_dict(idx.row()); mid = int(row.get("_member_id", 0) or 0)
            if mid: ids.add(mid)
        return sorted(ids)

    def _selection_changed(self, *_args):
        count = len(self._selected_ids())
        self.lbl_prepare_selected.setText(f"{count:,} selected")
        self.summary_labels["selected"].setText(f"{count:,}")
        self._update_invite_button()

    def _filters(self):
        target_ids = []
        for row in range(self.list_targets.count()):
            item = self.list_targets.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                target_ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return {
            "target_group_ids": target_ids,
            "source_group_id": self.cmb_source.currentData(), "eligibility": self.cmb_eligibility.currentText(),
            "consent": self.cmb_consent.currentText(), "tag": self.cmb_tags.currentText(),
            "username_search": self.le_username.text().strip() or None,
            "exclude_existing": self.chk_existing.isChecked(), "exclude_blacklist": self.chk_blacklist.isChecked(),
            "exclude_do_not_contact": self.chk_dnc.isChecked(), "exclude_deleted": self.chk_deleted.isChecked(),
            "exclude_bots": self.chk_bots.isChecked(),
            "member_ids": list(self.input_member_ids) if self.scope_mode == "SOURCE_SELECTION" else None,
        }

    def _member_row(self, member):
        display = MemberDisplayPreferences.from_manager(self.table_prefs)
        return {
            "Select": "", "Name": MemberDisplayFormatter.format_name(member, display),
            "Username": MemberDisplayFormatter.format_username(member, display),
            "Sources": getattr(member, "sources", "") or "—",
            "Eligibility": (member.eligibility_status or "UNKNOWN").replace("_", " ").title(),
            "Consent": (member.consent_status or "UNKNOWN").replace("_", " ").title(),
            "Target Status": (getattr(member, "existing_target_state", "UNKNOWN") or "UNKNOWN").replace("_", " ").title(),
            "Tags": getattr(member, "tags", "") or "—", "_member_id": member.id,
        }

    def _refresh(self):
        target_ids = []
        for row in range(self.list_targets.count()):
            item = self.list_targets.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                target_ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        
        if not target_ids:
            self._current = None
            self.model.replace_rows([])
            self.btn_export.setEnabled(False)
            self.btn_invite_link.setEnabled(False)
            self._update_invite_button()
            self.lbl_target_username.setText("—")
            self.lbl_primary_account.setText("—")
            self.lbl_target_access.setText("—")
            self.lbl_invite_permission.setText("—")
            self.lbl_join_workflow.setText("Join Request Required")
            self.lbl_known_members.setText("0")
            self.lbl_last_member_sync.setText("Never")
            for key, label in self.summary_labels.items():
                if key != "selected":
                    label.setText("0")
            if hasattr(self, "btn_refresh"):
                self.btn_refresh.setEnabled(False)
                self.btn_refresh.setText("Refresh")
            return
        
        # Use the first selected target group for preview
        target_id = target_ids[0]
        current = self.member_controller.target_preparation(int(target_id), **self._filters())
        if not current: return
        self._current = current
        group = current["group"]
        mapping = current.get("mapping")
        summary = current.get("summary") or {}
        self.lbl_target_username.setText(f"@{group.username}" if group.username else "Private / no username")
        self.lbl_primary_account.setText(mapping.account_name if mapping else "No primary authorized account")
        self.lbl_target_access.setText((mapping.role or mapping.access_state).replace("_", " ").title() if mapping else "Unavailable")
        invite_ok = bool(mapping and (mapping.can_manage_invite_links or mapping.can_invite))
        self.lbl_invite_permission.setText("Available" if invite_ok else "Unavailable")
        self.lbl_join_workflow.setText("Join Request Required" if invite_ok else "Unavailable")
        stats = self.member_controller.target_stats(int(target_id))
        self.lbl_known_members.setText(f"{int(stats.get('existing', 0)):,}")
        self.lbl_last_member_sync.setText((mapping.last_member_sync_at if mapping and mapping.last_member_sync_at else "Never"))
        for key, label in self.summary_labels.items():
            if key != "selected":
                if key == "input_selection":
                    value = len(self.input_member_ids) if self.scope_mode == "SOURCE_SELECTION" else int(summary.get("total", 0))
                else:
                    value = int(summary.get(key, 0))
                label.setText(f"{value:,}")
        rows = [self._member_row(member) for member in current.get("members", [])]
        self.model.replace_rows(rows)
        if self.scope_mode == "SOURCE_SELECTION":
            # Preserve the original Member Pool selection semantics while only
            # checking rows that are verified ready for direct invitation.
            ready_ids = {int(m.id) for m in current.get("members", []) if str(getattr(m, "existing_target_state", "UNKNOWN")).upper() == "NOT_MEMBER" and str(getattr(m, "eligibility_status", "UNKNOWN")).upper() == "ELIGIBLE" and str(getattr(m, "consent_status", "UNKNOWN")).upper() == "APPROVED"}
            self.model.checked_ids = ready_ids
            if self.model.rowCount(): self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(self.model.rowCount() - 1, 0), [Qt.ItemDataRole.CheckStateRole])
        self.btn_export.setEnabled(True)
        self.btn_invite_link.setEnabled(bool(self.group_controller and invite_ok))
        self.btn_invite_link.setToolTip("" if self.btn_invite_link.isEnabled() else "A mapped authorized target account with invite-link permission is required.")
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("Refresh")
        self._selection_changed()

    def _update_invite_button(self):
        selected = bool(self._selected_ids()) if hasattr(self, "model") else False
        direct_allowed = False
        gate = getattr(self.member_controller, "feature_gate", None)
        if gate is not None:
            try:
                from app.license.feature_keys import FeatureKey
                direct_allowed = bool(gate.has_feature(FeatureKey.DIRECT_MEMBER_INVITE))
            except Exception:
                direct_allowed = False
        mapping = self._current.get("mapping") if self._current else None
        allowed = selected and direct_allowed and bool(mapping and mapping.can_invite)
        self.btn_invite_selected.setEnabled(allowed)
        if not direct_allowed:
            self.btn_invite_selected.setToolTip("Direct approved-member invitation requires SP Telegram Ultimate.")
        elif not mapping or not mapping.can_invite:
            self.btn_invite_selected.setToolTip("A target account with invite permission is required.")
        elif not selected:
            self.btn_invite_selected.setToolTip("Select one or more prepared members first.")
        else:
            self.btn_invite_selected.setToolTip("")

    def _export(self):
        target_ids = []
        for row in range(self.list_targets.count()):
            item = self.list_targets.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                target_ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        if not target_ids:
            return
        target_id = target_ids[0]
        path, _ = QFileDialog.getSaveFileName(self, "Export Eligible Members", "target_eligible.csv", "CSV Files (*.csv)")
        if path:
            self.member_controller.export_target_preparation(path, int(target_id), **self._filters())

    def _create_invite_link(self):
        if not self._current or not self.group_controller:
            return
        group = self._current["group"]
        mapping = self._current.get("mapping")
        if not mapping:
            QMessageBox.warning(self, "Create Invite Link", "No primary authorized account is available for this target.")
            return
        mappings = list(self.group_controller.accounts_for_group(int(group.id)) or [])
        dialog = CreateTargetInviteLinkDialog(group.title, self, accounts=mappings, selected_account_id=int(mapping.account_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        options = dialog.options()
        account_id = options.pop("account_id", None)
        if not account_id:
            QMessageBox.warning(self, "Create Invite Link", "No authorized account with invite-link permission is available for this target.")
            return
        self.btn_invite_link.setEnabled(False)
        self.btn_invite_link.setText("Creating…")
        self.group_controller.create_target_invite_link(
            int(group.id), int(account_id), callback=self._invite_link_created, failure_callback=self._invite_link_failed, **options,
        )

    def _invite_link_failed(self,_message=None):
        self.btn_invite_link.setText("Create Invite Link");self.btn_invite_link.setEnabled(True)
        if _message:
            QMessageBox.warning(self,"Create Invite Link",str(_message))

    def _invite_link_created(self,result):
        self.btn_invite_link.setText("Create Invite Link");self.btn_invite_link.setEnabled(True)
        payload=result or {}
        if not bool(payload.get("success",True)):
            self._invite_link_failed(payload.get("user_message") or payload.get("message") or "Invite link could not be created.");return
        link=str(payload.get("link") or "")
        if not link:
            self._invite_link_failed("Telegram did not return an invite link.");return
        self._last_invite_link=link;QApplication.clipboard().setText(link)
        box=QMessageBox(self);box.setWindowTitle("Invite Link Created");box.setText("Invite link created and copied to the clipboard.")
        note="Use Join Requests to review applicants when approval is required. No member was automatically invited."
        if payload.get("persistence_warning"):note+=f"\n\n{payload['persistence_warning']}"
        box.setInformativeText(note)
        box.exec()

    def _invite_selected(self):
        ids = self._selected_ids()
        target_ids = []
        for row in range(self.list_targets.count()):
            item = self.list_targets.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                target_ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        if not ids or not target_ids:
            return
        InviteMembersToTargetDialog(self.member_controller, ids, target_group_id=int(target_ids[0]), group_controller=self.group_controller, parent=self).exec()
        self._refresh()

# Add compatibility attributes for older PySide6 versions
if not hasattr(TargetPreparationDialog, 'Accepted'):
    TargetPreparationDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(TargetPreparationDialog, 'Rejected'):
    TargetPreparationDialog.Rejected = QDialog.DialogCode.Rejected
