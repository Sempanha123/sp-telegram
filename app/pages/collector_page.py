from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from app.dialogs.member_sync_preview_dialog import MemberSyncPreviewDialog
from app.icons import IconManager
from app.telegram.models.member_sync_result import MemberSyncOptions
from app.widgets.page_header import PageHeaderWidget
from app.widgets.section_card import SectionCard


class CollectorPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._last_error = ""
        self._pending_preview_result = None
        self.setObjectName("page_collector")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(PageHeaderWidget("Member Sync", "Synchronize accessible members from authorized source groups."))

        setup = SectionCard("Authorized Source Member Sync")
        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.cmb_collector_source_group = QComboBox()
        self.cmb_collector_source_group.setObjectName("cmb_collector_source_group")
        self.cmb_collector_source_group.setMinimumHeight(36)
        self.cmb_collector_account = QComboBox()
        self.cmb_collector_account.setObjectName("cmb_collector_account")
        self.cmb_collector_account.setMinimumHeight(36)

        self.lbl_participant_access = QLabel("Unavailable")
        self.lbl_participant_access.setObjectName("lbl_participant_access")
        self.lbl_participant_access.setProperty("secondary", True)
        self.lbl_last_member_sync = QLabel("Never")
        self.lbl_last_member_sync.setObjectName("lbl_last_member_sync")
        self.lbl_last_member_sync.setProperty("secondary", True)
        self.lbl_collector_requirement = QLabel("")
        self.lbl_collector_requirement.setObjectName("lbl_collector_requirement")
        self.lbl_collector_requirement.setProperty("muted", True)
        self.lbl_collector_requirement.setWordWrap(True)

        for col, (label, widget) in enumerate((
            ("Source Group", self.cmb_collector_source_group),
            ("Account", self.cmb_collector_account),
        )):
            lab = QLabel(label)
            lab.setProperty("secondary", True)
            form.addWidget(lab, 0, col)
            form.addWidget(widget, 1, col)
        form.addWidget(QLabel("Participant Access"), 2, 0)
        form.addWidget(self.lbl_participant_access, 3, 0)
        form.addWidget(QLabel("Last Sync"), 2, 1)
        form.addWidget(self.lbl_last_member_sync, 3, 1)
        form.addWidget(self.lbl_collector_requirement, 4, 0, 1, 2)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        setup.body.addLayout(form)

        options_title = QLabel("Sync Options")
        options_title.setProperty("sectionTitle", True)
        setup.body.addWidget(options_title)
        opts = QGridLayout()
        opts.setHorizontalSpacing(18)
        opts.setVerticalSpacing(8)
        option_defs = [
            ("chk_skip_existing_database", "Skip existing profile updates", False),
            ("chk_skip_blacklist", "Skip blacklist", True),
            ("chk_skip_deleted", "Skip deleted accounts", True),
            ("chk_skip_bots", "Skip bots", True),
            ("chk_only_with_username", "Only with username", False),
            ("chk_update_existing_profiles", "Update existing profiles", True),
        ]
        for i, (obj, text, checked) in enumerate(option_defs):
            control = QCheckBox(text)
            control.setObjectName(obj)
            control.setChecked(checked)
            setattr(self, obj, control)
            opts.addWidget(control, i // 3, i % 3)
        setup.body.addLayout(opts)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.btn_preview_collection = QPushButton("Preview")
        self.btn_preview_collection.setObjectName("btn_preview_collection")
        self.btn_preview_collection.setIcon(IconManager.get("search"))
        self.btn_start_collection = QPushButton("Start Member Sync")
        self.btn_start_collection.setObjectName("btn_start_collection")
        self.btn_start_collection.setProperty("primary", True)
        self.btn_pause_collection = QPushButton("Pause")
        self.btn_pause_collection.setObjectName("btn_pause_collection")
        self.btn_resume_collection = QPushButton("Resume")
        self.btn_resume_collection.setObjectName("btn_resume_collection")
        self.btn_stop_collection = QPushButton("Stop")
        self.btn_stop_collection.setObjectName("btn_stop_collection")
        self.btn_stop_collection.setProperty("danger", True)
        self.btn_view_collection_errors = QPushButton("View Errors")
        self.btn_view_collection_errors.setObjectName("btn_view_collection_errors")
        self.btn_view_collection_errors.setProperty("role", "ghost")
        # Historical objectName retained but not exposed as a fake clickable action.
        self.btn_save_collection = QPushButton("Saved Automatically", self)
        self.btn_save_collection.setObjectName("btn_save_collection")
        self.btn_save_collection.hide()
        self.lbl_collector_autosave = QLabel("●  Auto-save enabled")
        self.lbl_collector_autosave.setObjectName("lbl_collector_autosave")
        self.lbl_collector_autosave.setProperty("muted", True)
        for button in (
            self.btn_preview_collection, self.btn_start_collection, self.btn_pause_collection,
            self.btn_resume_collection, self.btn_stop_collection,
        ):
            controls.addWidget(button)
        controls.addStretch()
        controls.addWidget(self.lbl_collector_autosave)
        controls.addWidget(self.btn_view_collection_errors)
        setup.body.addLayout(controls)
        root.addWidget(setup)

        progress_card = SectionCard("Sync Progress")
        stats = QGridLayout()
        stats.setSpacing(8)
        stat_defs = [
            ("lbl_member_processed", "Processed"), ("lbl_member_new", "New"),
            ("lbl_member_updated", "Updated"), ("lbl_member_duplicate", "Duplicates"),
            ("lbl_member_excluded", "Excluded"), ("lbl_member_errors", "Errors"),
        ]
        self._stat_labels = {}
        for col, (obj, title) in enumerate(stat_defs):
            tile = QWidget()
            tile.setProperty("metricTile", True)
            lay = QVBoxLayout(tile)
            lay.setContentsMargins(10, 7, 10, 7)
            lay.setSpacing(2)
            caption = QLabel(title)
            caption.setProperty("muted", True)
            value = QLabel("0")
            value.setObjectName(obj)
            value.setProperty("metricValue", True)
            setattr(self, obj, value)
            self._stat_labels[obj] = value
            lay.addWidget(caption)
            lay.addWidget(value)
            stats.addWidget(tile, 0, col)
        progress_card.body.addLayout(stats)

        self.progress_member_sync = QProgressBar()
        self.progress_member_sync.setObjectName("progress_member_sync")
        self.progress_collection = self.progress_member_sync
        self.progress_collection.setRange(0, 100)
        self.progress_collection.setValue(0)
        progress_card.body.addWidget(self.progress_member_sync)
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status"))
        self.lbl_sync_status = QLabel("Idle")
        self.lbl_sync_status.setObjectName("lbl_sync_status")
        self.lbl_sync_status.setProperty("secondary", True)
        status_row.addWidget(self.lbl_sync_status)
        status_row.addStretch()
        progress_card.body.addLayout(status_row)
        self._legacy_progress_collection = QProgressBar()
        self._legacy_progress_collection.setObjectName("progress_collection")
        self._legacy_progress_collection.hide()
        progress_card.body.addWidget(self._legacy_progress_collection)
        root.addWidget(progress_card)

        history = SectionCard("Recent Sync Runs")
        self.lbl_collector_history = QLabel("No member sync runs yet.")
        self.lbl_collector_history.setObjectName("lbl_collector_history")
        self.lbl_collector_history.setProperty("muted", True)
        self.lbl_collector_history.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_collector_history.setMinimumHeight(58)
        history.body.addWidget(self.lbl_collector_history)
        root.addWidget(history, 1)

        self.btn_pause_collection.setEnabled(False)
        self.btn_resume_collection.setEnabled(False)
        self.btn_stop_collection.setEnabled(False)
        self.cmb_collector_source_group.currentIndexChanged.connect(self._load_accounts)
        self.cmb_collector_account.currentIndexChanged.connect(self._account_changed)
        self.btn_preview_collection.clicked.connect(self.preview)
        self.btn_start_collection.clicked.connect(self.start)
        self.btn_pause_collection.clicked.connect(self.pause)
        self.btn_resume_collection.clicked.connect(self.resume)
        self.btn_stop_collection.clicked.connect(self.stop)
        self.btn_view_collection_errors.clicked.connect(self.show_errors)
        controller.memberSyncStarted.connect(self.started)
        controller.memberSyncProgress.connect(self.progress)
        controller.memberSyncCompleted.connect(self.completed)
        controller.memberSyncFailed.connect(self.failed)
        self._load_source_groups()

    def _group_label(self, group):
        username = f"@{group.username}" if getattr(group, "username", None) else "No username"
        group_type = str(getattr(group, "group_type", "UNKNOWN") or "UNKNOWN").replace("_", " ").title()
        stats = self.controller.source_stats(int(group.id)) if getattr(group, "id", None) else {}
        last_sync = (stats or {}).get("last_sync") or getattr(group, "last_sync_at", None) or "Never"
        return f"{group.title}  •  {username}  •  {group_type}  •  Last sync: {last_sync}"

    def _load_source_groups(self):
        current=self.cmb_collector_source_group.currentData()
        self.cmb_collector_source_group.blockSignals(True)
        self.cmb_collector_source_group.clear()
        groups = list(self.controller.source_groups())
        if groups:
            for group in groups:
                self.cmb_collector_source_group.addItem(self._group_label(group), group.id)
        else:
            self.cmb_collector_source_group.addItem("No accessible source groups available", None)
        if current is not None:
            index=self.cmb_collector_source_group.findData(current)
            if index>=0:self.cmb_collector_source_group.setCurrentIndex(index)
        self.cmb_collector_source_group.blockSignals(False)
        self._load_accounts()

    def refresh_group_options(self):
        self._load_source_groups()

    def _update_action_state(self):
        gid = self.cmb_collector_source_group.currentData()
        aid = self.cmb_collector_account.currentData()
        ready, reason = self.controller.collector_readiness(gid, aid)
        self.btn_preview_collection.setEnabled(bool(ready))
        self.btn_start_collection.setEnabled(bool(ready))
        self.lbl_collector_requirement.setText("Ready for authorized member sync." if ready else reason)
        tip = "" if ready else reason
        self.btn_preview_collection.setToolTip(tip)
        self.btn_start_collection.setToolTip(tip)

    def _load_accounts(self):
        self.cmb_collector_account.blockSignals(True)
        self.cmb_collector_account.clear()
        gid = self.cmb_collector_source_group.currentData()
        if not gid:
            self.cmb_collector_account.addItem("No authorized accounts available", None)
            self.lbl_participant_access.setText("Unavailable")
            self.lbl_last_member_sync.setText("Never")
            self.cmb_collector_account.blockSignals(False)
            self._update_action_state()
            self._refresh_history()
            return

        mappings = self.controller.collector_accounts_for_group(int(gid))
        primary_index = -1
        for mapping in mappings:
            name = mapping.account_name or f"Account {mapping.account_id}"
            username = f"@{mapping.account_username}" if mapping.account_username else "No username"
            role = str(mapping.role or "UNKNOWN").replace("_", " ").title()
            health = str(mapping.health_status or "UNKNOWN").replace("_", " ").title()
            label = f"{name}  •  {username}  •  {health}  •  {role}"
            self.cmb_collector_account.addItem(label, mapping.account_id)
            if mapping.is_primary:
                primary_index = self.cmb_collector_account.count() - 1
        if primary_index >= 0:
            self.cmb_collector_account.setCurrentIndex(primary_index)
        if not mappings:
            self.cmb_collector_account.addItem("No authorized accounts available", None)
        self.cmb_collector_account.blockSignals(False)
        self._account_changed()
        self._refresh_history()

    def _account_changed(self):
        gid = self.cmb_collector_source_group.currentData()
        aid = self.cmb_collector_account.currentData()
        mapping = None
        if gid and aid:
            mapping = next((m for m in self.controller.accounts_for_group(int(gid)) if int(m.account_id) == int(aid)), None)
        if mapping:
            self.lbl_participant_access.setText(str(mapping.member_list_availability or "UNKNOWN").replace("_", " ").title())
            self.lbl_last_member_sync.setText(mapping.last_member_sync_at or "Never")
        else:
            self.lbl_participant_access.setText("Unavailable")
            self.lbl_last_member_sync.setText("Never")
        self._update_action_state()

    def _refresh_history(self):
        gid = self.cmb_collector_source_group.currentData()
        runs = []
        try:
            if gid and getattr(self.controller.service, "sync_runs", None):
                runs = self.controller.service.sync_runs.get_recent(int(gid), 5)
        except Exception:
            runs = []
        if runs:
            self.lbl_collector_history.setText("\n".join(
                f"{r.started_at or '—'}   •   {str(r.status).replace('_', ' ').title()}   •   "
                f"{r.processed:,} processed   •   {r.inserted:,} new"
                for r in runs
            ))
            self.lbl_collector_history.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        else:
            self.lbl_collector_history.setText("No member sync runs yet.")
            self.lbl_collector_history.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _selection(self):
        gid = self.cmb_collector_source_group.currentData()
        aid = self.cmb_collector_account.currentData()
        ready, reason = self.controller.collector_readiness(gid, aid)
        if not ready:
            QMessageBox.information(self, "Member Sync", reason)
            return None
        return int(gid), int(aid)

    def _options(self):
        return MemberSyncOptions(
            skip_bots=self.chk_skip_bots.isChecked(),
            skip_deleted=self.chk_skip_deleted.isChecked(),
            skip_blacklist=self.chk_skip_blacklist.isChecked(),
            only_with_username=self.chk_only_with_username.isChecked(),
            update_existing_profiles=self.chk_update_existing_profiles.isChecked() and not self.chk_skip_existing_database.isChecked(),
            page_size=200,
        )

    def _option_labels(self):
        labels = []
        if self.chk_skip_blacklist.isChecked(): labels.append("Skip blacklist")
        if self.chk_skip_deleted.isChecked(): labels.append("Skip deleted accounts")
        if self.chk_skip_bots.isChecked(): labels.append("Skip bots")
        if self.chk_only_with_username.isChecked(): labels.append("Only members with username")
        if self.chk_skip_existing_database.isChecked(): labels.append("Do not update existing profiles")
        elif self.chk_update_existing_profiles.isChecked(): labels.append("Update existing profiles")
        return labels

    def preview(self):
        selected = self._selection()
        if not selected:
            return
        gid, aid = selected
        self.btn_preview_collection.setEnabled(False)
        self.controller.preview_sync(gid, aid, lambda result: self._preview_ready(result))

    def _preview_ready(self, result):
        self._update_action_state()
        self._pending_preview_result = result
        access = result["access"]
        self.lbl_participant_access.setText(access.availability.replace("_", " ").title())
        capacity = result.get("capacity") or {}
        mapping = result["mapping"]
        account = mapping.account_name or mapping.account_username or str(mapping.account_id)
        dialog = MemberSyncPreviewDialog(
            source=result["group"].title,
            account=account,
            access=access.availability.replace("_", " ").title(),
            existing_pool=int(capacity.get("current", 0) or 0),
            plan=str(capacity.get("plan", "UNLICENSED") or "UNLICENSED"),
            limit=capacity.get("limit"),
            remaining=capacity.get("remaining"),
            options=self._option_labels(),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start()

    def start(self):
        selected = self._selection()
        if not selected:
            return
        gid, aid = selected
        self.controller.on_start_sync(gid, aid, self._options())

    def pause(self):
        if self.controller.on_pause_sync():
            self.lbl_sync_status.setText("Pausing")
            self.btn_pause_collection.setEnabled(False)
            self.btn_resume_collection.setEnabled(True)

    def resume(self):
        if self.controller.on_resume_sync():
            self.lbl_sync_status.setText("Running")
            self.btn_pause_collection.setEnabled(True)
            self.btn_resume_collection.setEnabled(False)

    def stop(self):
        if self.controller.on_stop_sync():
            self.lbl_sync_status.setText("Stopping")
            self.btn_pause_collection.setEnabled(False)
            self.btn_resume_collection.setEnabled(False)
            self.btn_stop_collection.setEnabled(False)

    def started(self, _run_id):
        self.progress_collection.setRange(0, 0)
        self.btn_start_collection.setEnabled(False)
        self.btn_preview_collection.setEnabled(False)
        self.btn_pause_collection.setEnabled(True)
        self.btn_resume_collection.setEnabled(False)
        self.btn_stop_collection.setEnabled(True)
        self.lbl_sync_status.setText("Running")
        self._last_error = ""

    def progress(self, progress):
        values = {
            "lbl_member_processed": progress.processed,
            "lbl_member_new": progress.inserted,
            "lbl_member_updated": progress.updated,
            "lbl_member_duplicate": progress.duplicates,
            "lbl_member_excluded": progress.excluded,
            "lbl_member_errors": progress.errors,
        }
        for key, value in values.items():
            self._stat_labels[key].setText(f"{int(value):,}")

    def completed(self, result):
        self.progress(result)
        self.progress_collection.setRange(0, 100)
        self.progress_collection.setValue(100 if result.status not in {"CANCELLED", "PAUSED"} else 0)
        self._finish_buttons()
        self.lbl_participant_access.setText(result.availability.replace("_", " ").title())
        self.lbl_last_member_sync.setText(result.completed_at or "Completed")
        self.lbl_sync_status.setText(str(result.status).replace("_", " ").title())
        self._refresh_history()
        skipped = int(getattr(result, "plan_limit_skipped", 0) or 0)
        if skipped:
            QMessageBox.warning(
                self, "Member Pool Plan Limit Reached",
                f"New Members Added: {result.inserted:,}\nExisting Members Updated: {result.updated:,}\n"
                f"Additional New Members Skipped: {skipped:,}\n\n"
                "Upgrade your plan to increase Member Pool capacity. Existing member updates were preserved.",
            )

    def failed(self, message):
        self._last_error = message
        self.progress_collection.setRange(0, 100)
        self.progress_collection.setValue(0)
        self.lbl_sync_status.setText("Failed")
        self._finish_buttons()
        self._refresh_history()

    def _finish_buttons(self):
        self._update_action_state()
        self.btn_pause_collection.setEnabled(False)
        self.btn_resume_collection.setEnabled(False)
        self.btn_stop_collection.setEnabled(False)

    def show_errors(self):
        QMessageBox.information(
            self, "Member Sync Errors",
            self._last_error or "No member-sync error is currently recorded for this view.",
        )
