from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from app.dialogs.invite_members_to_target_dialog import InvitationResultsDialog


def _human(value, empty="—") -> str:
    text = str(value or "").strip()
    return text.replace("_", " ").title() if text else empty


class SmartAddMembersDialog(QDialog):
    """Simple user-facing Add Members flow.

    Technical account preparation, public-target auto-join, target membership
    verification, permission refresh, safety checks and fixed assignment remain
    backend responsibilities.
    """

    MAX_ACCOUNTS = 5

    def __init__(
        self,
        member_controller,
        member_ids: list[int],
        *,
        target_group_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("dlg_smart_add_members")
        self.setWindowTitle("Add Members - SP Telegram")
        self.setMinimumSize(820, 610)
        self.resize(900, 680)

        self.controller = member_controller
        self.member_ids = sorted({int(x) for x in member_ids if int(x) > 0})
        self._precheck = None
        self._auto_account_retry = False
        self._last_result = None
        self._account_ids: list[int] = []
        self._closed = False
        self._generation = 0
        self._connections = []
        self._running = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("smart_add_hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(5)

        title = QLabel("Add Members")
        title.setObjectName("smart_add_title")
        subtitle = QLabel(
            "Choose the group. SP Telegram automatically prepares healthy accounts, "
            "joins the public target when needed, verifies selected members, checks "
            "Telegram permissions and applies safety limits."
        )
        subtitle.setObjectName("smart_add_subtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        root.addWidget(hero)

        stage = QHBoxLayout()
        stage.setSpacing(8)
        self.stage_target = self._stage("1", "Target")
        self.stage_prepare = self._stage("2", "Prepare")
        self.stage_add = self._stage("3", "Add")
        for widget in (self.stage_target, self.stage_prepare, self.stage_add):
            stage.addWidget(widget, 1)
        root.addLayout(stage)

        target_card = QFrame()
        target_card.setObjectName("smart_add_target_card")
        target_layout = QVBoxLayout(target_card)
        target_layout.setContentsMargins(16, 14, 16, 14)
        target_layout.setSpacing(7)

        row = QHBoxLayout()
        labels = QVBoxLayout()
        cap = QLabel("TARGET GROUP")
        cap.setObjectName("smart_add_caption")
        self.lbl_target_hint = QLabel("Members will be added to this group.")
        self.lbl_target_hint.setObjectName("smart_add_muted")
        labels.addWidget(cap)
        labels.addWidget(self.lbl_target_hint)
        row.addLayout(labels, 1)

        self.cmb_target = QComboBox()
        self.cmb_target.setObjectName("cmb_smart_add_target")
        self.cmb_target.setMinimumWidth(360)
        self.cmb_target.setMinimumHeight(40)
        for group in self.controller.target_groups():
            label = group.title
            if getattr(group, "username", None):
                label += f"  @{group.username}"
            self.cmb_target.addItem(label, int(group.id))
        if target_group_id:
            index = self.cmb_target.findData(int(target_group_id))
            if index >= 0:
                self.cmb_target.setCurrentIndex(index)
        row.addWidget(self.cmb_target)
        target_layout.addLayout(row)
        root.addWidget(target_card)

        summary = QGridLayout()
        summary.setSpacing(10)
        self.metric_selected = self._metric("Selected", len(self.member_ids))
        self.metric_ready = self._metric("Ready", 0)
        self.metric_existing = self._metric("Already in Group", 0)
        self.metric_not_ready = self._metric("Needs Attention", len(self.member_ids))
        summary.addWidget(self.metric_selected, 0, 0)
        summary.addWidget(self.metric_ready, 0, 1)
        summary.addWidget(self.metric_existing, 0, 2)
        summary.addWidget(self.metric_not_ready, 0, 3)
        root.addLayout(summary)

        account_header = QHBoxLayout()
        account_text = QVBoxLayout()
        account_title = QLabel("Accounts")
        account_title.setObjectName("smart_add_section_title")
        self.lbl_account_summary = QLabel("SP Telegram will choose the best accounts automatically.")
        self.lbl_account_summary.setObjectName("smart_add_muted")
        account_text.addWidget(account_title)
        account_text.addWidget(self.lbl_account_summary)
        account_header.addLayout(account_text)
        account_header.addStretch()
        root.addLayout(account_header)

        self.table_accounts = QTableWidget(0, 3)
        self.table_accounts.setObjectName("tbl_smart_add_accounts")
        self.table_accounts.setHorizontalHeaderLabels(["Account", "Status", "Assigned"])
        self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_accounts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_accounts.setAlternatingRowColors(True)
        self.table_accounts.setMinimumHeight(150)
        self.table_accounts.setMaximumHeight(230)
        header = self.table_accounts.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table_accounts)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress_smart_add")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.lbl_status = QLabel("Preparing your selection…")
        self.lbl_status.setObjectName("smart_add_status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        self.btn_advanced = QToolButton()
        self.btn_advanced.setObjectName("btn_smart_add_advanced")
        self.btn_advanced.setText("Advanced details")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setArrowType(Qt.ArrowType.RightArrow)
        root.addWidget(self.btn_advanced, 0, Qt.AlignmentFlag.AlignLeft)

        self.advanced = QPlainTextEdit()
        self.advanced.setObjectName("smart_add_advanced")
        self.advanced.setReadOnly(True)
        self.advanced.setMaximumHeight(130)
        self.advanced.hide()
        root.addWidget(self.advanced)

        actions = QHBoxLayout()
        self.btn_results = QPushButton("View Results")
        self.btn_results.setObjectName("btn_smart_add_results")
        self.btn_results.setEnabled(False)
        self.btn_close = QPushButton("Close")
        self.btn_primary = QPushButton("Check & Continue")
        self.btn_primary.setObjectName("btn_smart_add_primary")
        self.btn_primary.setProperty("primary", True)
        actions.addWidget(self.btn_results)
        actions.addStretch()
        actions.addWidget(self.btn_close)
        actions.addWidget(self.btn_primary)
        root.addLayout(actions)

        self.cmb_target.currentIndexChanged.connect(self._target_changed)
        self.btn_advanced.toggled.connect(self._toggle_advanced)
        self.btn_close.clicked.connect(self.reject)
        self.btn_primary.clicked.connect(self._primary_clicked)
        self.btn_results.clicked.connect(self._show_results)

        self._connect(self.controller.targetInvitationProgress, self._on_progress)
        self._connect(self.controller.targetInvitationCompleted, self._on_completed)
        self._connect(self.controller.targetInvitationFailed, self._on_failed)

        self._target_changed()
        QTimer.singleShot(300, self._prepare)

    @staticmethod
    def _stage(number: str, text: str) -> QFrame:
        frame = QFrame()
        frame.setProperty("smartStage", True)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(7)
        badge = QLabel(number)
        badge.setProperty("stageBadge", True)
        label = QLabel(text)
        label.setProperty("stageText", True)
        layout.addWidget(badge)
        layout.addWidget(label)
        layout.addStretch()
        return frame

    @staticmethod
    def _metric(title: str, value: int) -> QFrame:
        frame = QFrame()
        frame.setProperty("smartMetric", True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(2)
        caption = QLabel(title)
        caption.setProperty("metricCaption", True)
        number = QLabel(str(int(value)))
        number.setProperty("metricValue", True)
        frame._value_label = number
        layout.addWidget(caption)
        layout.addWidget(number)
        return frame

    @staticmethod
    def _set_metric(frame: QFrame, value: int) -> None:
        frame._value_label.setText(f"{max(0, int(value)):,}")

    @staticmethod
    def _item(text="—") -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return item

    def _connect(self, signal, slot):
        try:
            signal.connect(slot)
            self._connections.append((signal, slot))
        except (TypeError, RuntimeError):
            pass

    def done(self, result):
        self._closed = True
        self._generation += 1
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections.clear()
        super().done(result)

    def _toggle_advanced(self, checked: bool):
        self.advanced.setVisible(bool(checked))
        self.btn_advanced.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def _target_changed(self, *_args):
        self._precheck = None
        self._last_result = None
        self.btn_results.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.btn_primary.setText("Check & Continue")
        self.btn_primary.setEnabled(True)
        self._load_accounts()

    def _load_accounts(self):
        target_id = self.cmb_target.currentData()
        options = (
            list(self.controller.mass_add_account_options(int(target_id)) or [])
            if target_id
            else []
        )
        # Prefer accounts already able to invite, then healthy public-target auto-join.
        selectable = [row for row in options if row.get("selectable")]
        selectable.sort(
            key=lambda row: (
                0 if row.get("can_invite_now") else 1,
                0 if row.get("health") == "HEALTHY" else 1,
                int(row.get("account_id", 0)),
            )
        )
        chosen = selectable[: self.MAX_ACCOUNTS]
        self._account_ids = [int(row["account_id"]) for row in chosen]

        self.table_accounts.setRowCount(len(options))
        chosen_ids = set(self._account_ids)
        for index, option in enumerate(options):
            account_id = int(option["account_id"])
            name = str(option.get("name") or f"Account {account_id}")
            if option.get("username"):
                name += f"  •  @{option['username']}"

            if account_id in chosen_ids:
                if option.get("auto_join"):
                    status = "Preparing • will join target"
                elif option.get("can_invite_now"):
                    status = "Preparing • permission cached"
                else:
                    status = "Preparing"
            else:
                status = self._friendly_option_status(option)

            self.table_accounts.setItem(index, 0, self._item(name))
            self.table_accounts.setItem(index, 1, self._item(status))
            self.table_accounts.setItem(index, 2, self._item("—"))

        if self._account_ids:
            self.lbl_account_summary.setText(
                f"{len(self._account_ids)} account(s) selected automatically. "
                "No manual account setup is required."
            )
        else:
            self.lbl_account_summary.setText(
                "No healthy account is currently available for this target."
            )

    @staticmethod
    def _friendly_option_status(option: dict) -> str:
        health = str(option.get("health") or "").upper()
        restriction = str(option.get("restriction") or "").upper()
        if restriction not in {"", "NONE", "NONE_KNOWN", "UNKNOWN"}:
            return "Unavailable • account restricted"
        if health in {"COOLDOWN", "RESTRICTED"}:
            return "Unavailable • waiting / restricted"
        if health in {"SESSION_INVALID", "LOGIN_REQUIRED", "DISABLED"}:
            return "Unavailable • login required"
        if option.get("auto_join"):
            return "Available • auto join"
        if option.get("can_invite_now"):
            return "Available"
        return "Unavailable • cannot invite"

    def _set_checking(self):
        self._running = False
        self._precheck = None
        self.btn_primary.setEnabled(False)
        self.btn_primary.setText("Preparing…")
        self.progress.setRange(0, 0)
        self.lbl_status.setText(
            "Preparing accounts and checking the selected members. "
            "This can take a moment because Telegram is being checked live."
        )

    def _prepare(self):
        if self._closed:
            return
        target_id = self.cmb_target.currentData()
        if not target_id:
            self.lbl_status.setText("Choose a target group first.")
            return
        if not self.member_ids:
            self.lbl_status.setText("Select one or more Member Pool records first.")
            return

        self._load_accounts()
        if not self._account_ids:
            self.lbl_status.setText(
                "No healthy account can prepare this target. Open Accounts / Health Center "
                "and make at least one Telegram account ready."
            )
            self.btn_primary.setText("Check Again")
            self.btn_primary.setEnabled(True)
            return

        self._auto_account_retry = False
        self._generation += 1
        generation = self._generation
        self._set_checking()

        token = self.controller.request_invitation_batch_preflight(
            int(target_id),
            list(self._account_ids),
            list(self.member_ids),
            callback=lambda result, g=generation: self._apply_preflight(result, g),
        )
        if token is None:
            cached = self.controller.invitation_batch_precheck(
                int(target_id), list(self._account_ids), list(self.member_ids)
            )
            if cached:
                self._apply_preflight(cached, generation)
            else:
                self._preflight_failed(
                    "SP Telegram could not start the readiness check."
                )

    @staticmethod
    def _as_dict(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return None

    def _apply_preflight(self, result, generation=None):
        if self._closed:
            return
        if generation is not None and generation != self._generation:
            return
        pre = self._as_dict(result)
        if not pre:
            self._preflight_failed("The readiness check returned no usable result.")
            return

        self._precheck = pre
        counts = dict(pre.get("counts") or {})
        selected = int(counts.get("selected", len(self.member_ids)) or 0)
        policy_ready = int(counts.get("ready", 0) or 0)
        existing = int(counts.get("already_member", 0) or 0)
        usable_ids = [int(row.get("account_id")) for row in pre.get("accounts") or [] if bool(row.get("ready"))]
        if (
            not bool(pre.get("can_start", pre.get("start_allowed", False)))
            and usable_ids
            and set(usable_ids) != set(self._account_ids)
            and not self._auto_account_retry
        ):
            self._auto_account_retry = True
            self._account_ids = usable_ids
            self.lbl_status.setText("One or more accounts could not be used. Retrying automatically with the ready accounts…")
            self.controller.request_invitation_batch_preflight(
                int(self.cmb_target.currentData()),
                list(self._account_ids),
                list(self.member_ids),
                callback=lambda result, g=self._generation: self._apply_preflight(result, g),
            )
            return
        assigned_ready = sum(int(row.get("count", 0) or 0) for row in pre.get("assignments") or [])
        ready = assigned_ready if bool(pre.get("can_start", pre.get("start_allowed", False))) else 0
        not_ready = max(0, selected - ready - existing)

        self._set_metric(self.metric_selected, selected)
        self._set_metric(self.metric_ready, ready)
        self._set_metric(self.metric_existing, existing)
        self._set_metric(self.metric_not_ready, not_ready)

        account_rows = {
            int(row.get("account_id", 0)): row
            for row in pre.get("accounts") or []
        }
        for row_index in range(self.table_accounts.rowCount()):
            name_item = self.table_accounts.item(row_index, 0)
            # Match by display order using current automatic ids first; fall back by name.
            if row_index < len(self._account_ids):
                account_id = self._account_ids[row_index]
            else:
                account_id = None
            account = account_rows.get(account_id) if account_id else None
            if account:
                assigned = int(account.get("assigned_count", 0) or 0)
                if account.get("can_invite") and not account.get("blocking_reasons"):
                    status = "Ready"
                elif account.get("can_invite"):
                    status = "Ready • no assignment"
                else:
                    blockers = list(account.get("blocking_reasons") or [])
                    status = self._friendly_blocker(blockers[0] if blockers else "Cannot invite")
                self.table_accounts.item(row_index, 1).setText(status)
                self.table_accounts.item(row_index, 2).setText(str(assigned))
                if name_item:
                    name_item.setToolTip(chr(10).join(account.get("blocking_reasons") or []))

        blockers = list(pre.get("blocking_reasons") or [])
        warnings = list(pre.get("warnings") or [])
        advanced = []
        advanced.extend(f"BLOCK: {text}" for text in blockers)
        advanced.extend(f"NOTE: {text}" for text in warnings)
        for key, label in (
            ("eligibility_not_approved", "Eligibility not approved"),
            ("consent_not_approved", "Consent not approved"),
            ("unknown", "Target membership still unknown"),
            ("blacklisted", "Blacklisted"),
            ("do_not_contact", "Do not contact"),
            ("deleted", "Deleted"),
            ("bots", "Bots"),
        ):
            value = int(counts.get(key, 0) or 0)
            if value:
                advanced.append(f"{label}: {value}")
        self.advanced.setPlainText(chr(10).join(advanced) or "All checks passed.")

        self.progress.setRange(0, 100)
        self.progress.setValue(100 if ready else 0)

        can_start = bool(pre.get("can_start", pre.get("start_allowed", False)))
        if can_start and ready > 0:
            self.lbl_status.setText(
                f"Ready. SP Telegram can add {ready:,} selected member(s) now. "
                f"{existing:,} already in the group will be skipped automatically."
            )
            self.btn_primary.setText(f"Add {ready:,} Members")
            self.btn_primary.setEnabled(True)
        else:
            self.lbl_status.setText(self._friendly_summary(counts, blockers))
            self.btn_primary.setText("Check Again")
            self.btn_primary.setEnabled(True)

    @staticmethod
    def _friendly_blocker(message: str) -> str:
        text = str(message or "")
        lower = text.lower()
        if "permission to invite" in lower:
            return "Not ready • invite permission required"
        if "not mapped" in lower or "target access" in lower:
            return "Not ready • join or permission required"
        if "not authorized" in lower or "session" in lower:
            return "Login required"
        if "disconnected" in lower or "connection" in lower:
            return "Connection unavailable"
        if "restriction" in lower or "healthy" in lower:
            return "Account restricted"
        return text or "Not ready"

    @staticmethod
    def _friendly_summary(counts: dict, blockers: list[str]) -> str:
        selected = int(counts.get("selected", 0) or 0)
        policy_ready = int(counts.get("ready", 0) or 0)
        existing = int(counts.get("already_member", 0) or 0)
        consent = int(counts.get("consent_not_approved", 0) or 0)
        eligibility = int(counts.get("eligibility_not_approved", 0) or 0)
        unknown = int(counts.get("unknown", 0) or 0)

        if blockers and policy_ready > 0:
            return (
                f"{policy_ready:,} selected member check(s) passed, but no Telegram account "
                "is ready to add them to this target. Click Check Again after account preparation."
            )
        if consent or eligibility:
            return f"{max(consent, eligibility):,} member(s) need approval/review in Member Pool."
        if unknown:
            return (
                f"{unknown:,} member(s) could not have target membership verified. "
                "Use Check Again or open Advanced details."
            )
        if existing == selected and selected:
            return "All selected members are already in this group."
        if blockers:
            return SmartAddMembersDialog._friendly_blocker(blockers[0])
        if policy_ready:
            return "Member checks passed. Waiting for a usable Telegram account."
        return "Nothing is ready to add yet. Open Advanced details for the exact reason."


    def _preflight_failed(self, message):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.lbl_status.setText(str(message or "Readiness check failed."))
        self.btn_primary.setText("Check Again")
        self.btn_primary.setEnabled(True)

    def _primary_clicked(self):
        if self._running:
            return
        pre = self._precheck or {}
        counts = pre.get("counts") or {}
        ready = int(counts.get("ready", 0) or 0)
        if bool(pre.get("can_start", pre.get("start_allowed", False))) and ready > 0:
            self._start()
        else:
            self._prepare()

    def _start(self):
        pre = self._precheck or {}
        counts = pre.get("counts") or {}
        ready = int(counts.get("ready", 0) or 0)
        if ready <= 0:
            self._prepare()
            return

        if QMessageBox.question(
            self,
            "Add Members",
            f"Add {ready:,} ready member(s) to {self.cmb_target.currentText()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        ) != QMessageBox.StandardButton.Yes:
            return

        self._running = True
        self.btn_primary.setEnabled(False)
        self.btn_primary.setText("Adding Members…")
        self.btn_close.setEnabled(False)
        self.progress.setRange(0, max(1, ready))
        self.progress.setValue(0)
        self.lbl_status.setText(
            "Adding members. SP Telegram will stop safely if Telegram returns a restriction."
        )
        token = self.controller.start_target_invitation_batch(
            int(self.cmb_target.currentData()),
            list(self._account_ids),
            list(self.member_ids),
        )
        if token is None:
            self._running = False
            self.btn_close.setEnabled(True)
            self.btn_primary.setEnabled(True)
            self.btn_primary.setText("Check Again")
            self.lbl_status.setText(
                "The job could not start. Check the license, Telegram runtime and account health."
            )

    def _on_progress(self, payload):
        if self._closed or not self._running or not payload:
            return
        processed = int(payload.get("processed", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        successful = int(payload.get("successful", 0) or 0)
        skipped = int(payload.get("skipped", 0) or 0)
        failed = int(payload.get("failed", 0) or 0)
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(processed)
        self.lbl_status.setText(
            f"Adding members… {processed:,}/{total:,} processed • "
            f"{successful:,} added • {skipped:,} skipped • {failed:,} failed"
        )

    def _on_completed(self, result):
        if self._closed or not self._running:
            return
        self._running = False
        self._last_result = result or {}
        self.btn_results.setEnabled(bool(self._last_result))
        self.btn_close.setEnabled(True)
        self.btn_close.setText("Done")
        self.btn_primary.setEnabled(False)

        successful = int(self._last_result.get("successful", 0) or 0)
        skipped = int(self._last_result.get("skipped", 0) or 0)
        failed = int(self._last_result.get("failed", 0) or 0)
        processed = int(self._last_result.get("processed", 0) or 0)
        total = int(self._last_result.get("selected", processed) or processed)
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(processed)

        if str(self._last_result.get("status", "")).upper() == "BLOCKED":
            self.lbl_status.setText(
                self._last_result.get("message")
                or "The operation stopped safely before more members were processed."
            )
            self.btn_primary.setText("Check Again")
            self.btn_primary.setEnabled(True)
            return

        self.lbl_status.setText(
            f"Completed • {successful:,} added • {skipped:,} skipped • {failed:,} failed."
        )
        self.btn_primary.setText("Completed")

    def _on_failed(self, message):
        if self._closed or not self._running:
            return
        self._running = False
        self.btn_close.setEnabled(True)
        self.btn_primary.setText("Check Again")
        self.btn_primary.setEnabled(True)
        self.lbl_status.setText(str(message or "The add-members job could not continue."))

    def _show_results(self):
        if self._last_result:
            InvitationResultsDialog(self._last_result, self).exec()
