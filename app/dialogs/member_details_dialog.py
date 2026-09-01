from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPushButton, QTabWidget, QTableView, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime
from app.utils.table_preferences import TablePreferenceManager
from app.utils.member_display_formatter import MemberDisplayFormatter, MemberDisplayPreferences
from app.utils.table_layout_manager import TableLayoutManager, MEMBER_TARGET_STATUS_LAYOUT
from app.widgets.detail_header import DetailHeaderWidget


def _mask_id(value) -> str:
    raw = str(value or "")
    if not raw:
        return "—"
    if len(raw) <= 4:
        return "•" * len(raw)
    return f"{raw[:2]}{'•' * max(4, len(raw)-4)}{raw[-2:]}"


def _mask_username(value) -> str:
    raw = str(value or "").lstrip("@")
    if not raw:
        return "—"
    return "@" + (raw[:1] + "•" * max(5, len(raw)-1))


class MemberDetailsDialog(QDialog):
    """Member details with source, target-state and invitation-history visibility.

    The dialog is local-data focused.  It never performs a target invitation by
    itself; direct invitations remain in the explicit one-account invitation
    workflow on Member Pool/Prepare for Target.
    """

    def __init__(self, controller, member_id: int, parent=None, *, avatar_service=None):
        super().__init__(parent)
        self.controller = controller
        self.member_id = int(member_id)
        self.avatar_service = avatar_service
        self.settings = QSettings()
        self.table_prefs = TablePreferenceManager(self.settings, self)
        self._details = {}
        self._source_rows = []
        self.setWindowTitle("Member Details - SP Telegram")
        self.resize(860, 640)

        preview = controller.get_member_details(member_id) or {}
        pm = preview.get("member")
        pname = (
            getattr(pm, "display_name", None)
            or " ".join(x for x in [getattr(pm, "first_name", None), getattr(pm, "last_name", None)] if x)
            or getattr(pm, "username", None)
            or f"Member {member_id}"
        ) if pm else f"Member {member_id}"

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)
        self.detail_header = DetailHeaderWidget(
            pname,
            f"@{pm.username}" if pm and getattr(pm, "username", None) else "Member record",
            getattr(pm, "eligibility_status", "UNKNOWN").replace("_", " ").title() if pm else "Unknown",
            self,
            avatar_service=avatar_service,
            avatar_kind="member",
            avatar_id=member_id,
            avatar_peer_id=getattr(pm, "telegram_user_id", None) if pm else None,
            avatar_account_id=0,
        )
        root.addWidget(self.detail_header)

        self.tab_member_details = QTabWidget()
        self.tab_member_details.setObjectName("tab_member_details")
        root.addWidget(self.tab_member_details, 1)
        self._build_overview()
        self._build_sources()
        self._build_target_status()
        self._build_invitation_history()
        self._build_activity()

        actions = QHBoxLayout()
        self.btn_refresh_member_profile = QPushButton("Refresh Telegram Profile")
        self.btn_refresh_member_profile.setObjectName("btn_refresh_member_profile")
        self.btn_refresh_member_profile.setToolTip("Refresh this selected member using one explicitly selected authorized source account.")
        self.btn_member_add_tag = QPushButton("Add Tag")
        self.btn_member_add_tag.setObjectName("btn_member_add_tag")
        self.btn_member_remove_tag = QPushButton("Remove Tag")
        self.btn_member_remove_tag.setObjectName("btn_member_remove_tag")
        self.btn_member_add_blacklist = QPushButton("Blacklist")
        self.btn_member_add_blacklist.setObjectName("btn_member_add_blacklist")
        self.btn_member_remove_blacklist = QPushButton("Remove Exclusion")
        self.btn_member_remove_blacklist.setObjectName("btn_member_remove_blacklist")
        self.btn_member_close = QPushButton("Close")
        self.btn_member_close.setObjectName("btn_member_close")
        for b in (
            self.btn_refresh_member_profile, self.btn_member_add_tag, self.btn_member_remove_tag,
            self.btn_member_add_blacklist, self.btn_member_remove_blacklist,
        ):
            actions.addWidget(b)
        actions.addStretch()
        actions.addWidget(self.btn_member_close)
        root.addLayout(actions)

        self.btn_refresh_member_profile.clicked.connect(self.refresh_profile)
        self.btn_member_add_tag.clicked.connect(self.add_tag)
        self.btn_member_remove_tag.clicked.connect(self.remove_tag)
        self.btn_member_add_blacklist.clicked.connect(lambda: controller.blacklist(member_id))
        self.btn_member_remove_blacklist.clicked.connect(lambda: controller.unblacklist(member_id))
        self.btn_member_close.clicked.connect(self.accept)
        self.btn_save_member_eligibility.clicked.connect(self.save_eligibility)
        self.btn_remove_source.clicked.connect(self.remove_source_relationship)
        self.reload()

    def _build_overview(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(8)
        self.overview_labels = {}
        self.overview_row_labels = {}
        for key, title in [
            ("telegram_user_id", "Telegram ID"), ("username", "Username"), ("display_name", "Name"),
            ("is_bot", "Bot"), ("is_premium", "Premium"), ("eligibility_status", "Eligibility"),
            ("consent_status", "Consent"), ("global_excluded", "Blacklist"),
            ("do_not_contact", "Do Not Contact"), ("first_seen_at", "First Seen"),
            ("last_seen_at", "Last Seen"), ("tags", "Tags"),
        ]:
            left = QLabel(title)
            value = QLabel("—")
            value.setTextInteractionFlags(value.textInteractionFlags())
            self.overview_labels[key] = value
            self.overview_row_labels[key] = left
            form.addRow(left, value)

        self.cmb_member_eligibility_edit = QComboBox()
        self.cmb_member_eligibility_edit.setObjectName("cmb_member_eligibility_edit")
        self.cmb_member_eligibility_edit.addItems([
            "UNKNOWN", "ELIGIBLE", "EXCLUDED", "DO_NOT_CONTACT", "MANUAL_REVIEW",
            "PRIVACY_RESTRICTED", "INVALID_USER", "DELETED_ACCOUNT", "BOT",
        ])
        self.cmb_member_consent_edit = QComboBox()
        self.cmb_member_consent_edit.setObjectName("cmb_member_consent_edit")
        self.cmb_member_consent_edit.addItems(["UNKNOWN", "OPTED_IN", "APPROVED", "DECLINED", "REVOKED"])
        self.txt_member_eligibility_notes = QTextEdit()
        self.txt_member_eligibility_notes.setObjectName("txt_member_eligibility_notes")
        self.txt_member_eligibility_notes.setMaximumHeight(82)
        self.btn_save_member_eligibility = QPushButton("Save Changes")
        self.btn_save_member_eligibility.setObjectName("btn_save_member_eligibility")
        self.lbl_member_global_exclusion = QLabel("No")
        self.lbl_member_global_exclusion.setObjectName("lbl_member_global_exclusion")
        self.lbl_member_global_exclusion.hide()
        self.lbl_member_tags = QLabel("—")
        self.lbl_member_tags.setObjectName("lbl_member_tags")
        self.lbl_member_tags.hide()
        form.addRow("Set Eligibility", self.cmb_member_eligibility_edit)
        form.addRow("Set Consent", self.cmb_member_consent_edit)
        form.addRow("Notes", self.txt_member_eligibility_notes)
        form.addRow("", self.btn_save_member_eligibility)
        self.tab_member_details.addTab(page, "Overview")

    def _build_sources(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.tbl_member_sources = QTableView()
        self.tbl_member_sources.setObjectName("tbl_member_sources")
        self.source_model = BaseTableModel([], ["Source Group", "First Discovered", "Last Seen", "Last Seen By Account", "Status"])
        self.tbl_member_sources.setModel(self.source_model)
        self.tbl_member_sources.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_member_sources.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_member_sources.verticalHeader().setVisible(False); self.tbl_member_sources.verticalHeader().setDefaultSectionSize(44)
        self.table_prefs.register(self.tbl_member_sources, self.source_model.columns, default_widths={"Source Group":220,"First Discovered":175,"Last Seen":175,"Last Seen By Account":180,"Status":140})
        TableLayoutManager(self.tbl_member_sources).apply(self.tbl_member_sources, self.source_model.columns)
        lay.addWidget(self.tbl_member_sources)
        row = QHBoxLayout()
        self.btn_remove_source = QPushButton("Remove Source Relationship")
        self.btn_remove_source.setObjectName("btn_member_remove_source_relationship")
        self.btn_remove_source.setToolTip("Removes only the local Member Pool source relationship. Telegram is not changed.")
        row.addWidget(self.btn_remove_source)
        self.btn_member_open_source_group = QPushButton("Open Source Group")
        self.btn_member_open_source_group.setObjectName("btn_member_open_source_group")
        self.btn_member_open_source_group.setEnabled(False)
        self.btn_member_open_source_group.setToolTip("Not available in this release.")
        self.btn_member_open_source_group.hide()
        row.addWidget(self.btn_member_open_source_group)
        row.addStretch()
        lay.addLayout(row)
        self.tab_member_details.addTab(page, "Sources")

    def _build_target_status(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.lbl_target_help = QLabel("Target membership is stored independently for every target. UNKNOWN is never treated as NOT_MEMBER without a verified target sync/check.")
        self.lbl_target_help.setObjectName("lbl_target_help")
        self.lbl_target_help.setWordWrap(True)
        self.lbl_target_help.setProperty("secondary", True)
        lay.addWidget(self.lbl_target_help)
        self.tbl_member_target_states = QTableView()
        self.tbl_member_target_states.setObjectName("tbl_member_target_states")
        self.target_model = BaseTableModel([], ["Target", "Status", "Last Sync / Check", "Account", "Error"])
        self.tbl_member_target_states.setModel(self.target_model)
        self.tbl_member_target_states.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_member_target_states.verticalHeader().setVisible(False); self.tbl_member_target_states.verticalHeader().setDefaultSectionSize(44)
        self.table_prefs.register(self.tbl_member_target_states, self.target_model.columns, default_widths={k:v.width for k,v in MEMBER_TARGET_STATUS_LAYOUT.items()})
        TableLayoutManager(self.tbl_member_target_states).apply(self.tbl_member_target_states, self.target_model.columns, overrides=MEMBER_TARGET_STATUS_LAYOUT)
        lay.addWidget(self.tbl_member_target_states)
        self.tab_member_details.addTab(page, "Target Status")

    def _build_invitation_history(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        note = QLabel("Invitation results are local audit/history records for explicit target actions. Permanent exclusions are not automatically retried.")
        note.setWordWrap(True)
        note.setProperty("secondary", True)
        lay.addWidget(note)
        self.tbl_member_invitation_history = QTableView()
        self.tbl_member_invitation_history.setObjectName("tbl_member_invitation_history")
        self.invitation_model = BaseTableModel([], ["Target", "Account", "Action", "Result", "Date", "Error"])
        self.tbl_member_invitation_history.setModel(self.invitation_model)
        self.tbl_member_invitation_history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_member_invitation_history.verticalHeader().setVisible(False); self.tbl_member_invitation_history.verticalHeader().setDefaultSectionSize(44)
        widths={"Target":210,"Account":170,"Action":150,"Result":170,"Date":175,"Error":300}
        self.table_prefs.register(self.tbl_member_invitation_history, self.invitation_model.columns, default_widths=widths)
        TableLayoutManager(self.tbl_member_invitation_history).apply(self.tbl_member_invitation_history, self.invitation_model.columns)
        lay.addWidget(self.tbl_member_invitation_history)
        self.tab_member_details.addTab(page, "Invitation History")

    def _build_activity(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        label = QLabel("Member activity, eligibility changes, source changes and target actions are recorded through SP Telegram's existing audit/log systems.")
        label.setWordWrap(True)
        lay.addWidget(label)
        lay.addStretch()
        self.tab_member_details.addTab(page, "Activity")

    def _set_overview_visibility(self, key: str, visible: bool):
        label = self.overview_row_labels.get(key)
        value = self.overview_labels.get(key)
        if label: label.setVisible(bool(visible))
        if value: value.setVisible(bool(visible))

    def reload(self):
        data = self.controller.get_member_details(self.member_id)
        if not data:
            return
        self._details = data
        m = data["member"]
        prefs = self.table_prefs
        privacy = str(self.settings.value("ui/privacy_mode", False)).lower() in {"1", "true", "yes"}
        show_id = bool(prefs.global_value("show_telegram_id", True))
        show_username = bool(prefs.global_value("show_username", True))
        show_name = bool(prefs.global_value("show_display_name", True))
        show_first = bool(prefs.global_value("show_first_seen", True))
        show_last = bool(prefs.global_value("show_last_seen", True))
        show_bot = bool(prefs.global_value("show_bot", False))
        show_premium = bool(prefs.global_value("show_premium", False))
        self._set_overview_visibility("telegram_user_id", show_id)
        self._set_overview_visibility("username", show_username)
        self._set_overview_visibility("display_name", show_name)
        self._set_overview_visibility("first_seen_at", show_first)
        self._set_overview_visibility("last_seen_at", show_last)
        self._set_overview_visibility("is_bot", show_bot)
        self._set_overview_visibility("is_premium", show_premium)

        display_preferences = MemberDisplayPreferences.from_manager(prefs, privacy_mode=privacy)
        identity = MemberDisplayFormatter.format_identity(m, display_preferences)
        values = {
            "telegram_user_id": identity["telegram_user_id"],
            "username": identity["username"],
            "display_name": identity["display_name"],
            "is_bot": "Yes" if m.is_bot else "No",
            "is_premium": "Yes" if m.is_premium else "No",
            "eligibility_status": str(m.eligibility_status or "UNKNOWN").replace("_", " ").title(),
            "consent_status": str(m.consent_status or "UNKNOWN").replace("_", " ").title(),
            "global_excluded": "Yes" if (m.global_excluded or data.get("exclusions")) else "No",
            "do_not_contact": "Yes" if str(m.eligibility_status).upper() == "DO_NOT_CONTACT" or any(str(getattr(x, "exclusion_type", "")).upper() == "DO_NOT_CONTACT" for x in data.get("exclusions", [])) else "No",
            "first_seen_at": format_local_datetime(m.first_seen_at),
            "last_seen_at": format_local_datetime(m.last_seen_at),
            "tags": ", ".join(data.get("tags", [])) or "No tags",
        }
        header_name = identity["display_name"] if identity["display_name"] != "—" else (identity["username"] if identity["username"] != "—" else f"Member {self.member_id}")
        self.detail_header.lbl_name.setText(header_name)
        self.detail_header.lbl_subtitle.setText(identity["username"] if identity["username"] != "—" else "Member record")
        initials = "".join(part[:1].upper() for part in str(header_name).split()[:2]) or "SP"
        self.detail_header.lbl_avatar.setText(initials)
        for key, label in self.overview_labels.items():
            label.setText(str(values.get(key, "—")))
        self.lbl_member_global_exclusion.setText(values["global_excluded"])
        self.lbl_member_tags.setText(values["tags"])

        self.cmb_member_eligibility_edit.setCurrentText(m.eligibility_status)
        self.cmb_member_consent_edit.setCurrentText(m.consent_status)
        self.txt_member_eligibility_notes.setPlainText(m.notes or "")

        self._source_rows = []
        source_rows = []
        for src in data.get("sources", []):
            source_rows.append({
                "Source Group": src.group_title,
                "First Discovered": format_local_datetime(src.first_seen_at),
                "Last Seen": format_local_datetime(src.last_seen_at),
                "Last Seen By Account": src.account_name or "—",
                "Status": str(src.source_status or "UNKNOWN").replace("_", " ").title(),
            })
            self._source_rows.append(src)
        self.source_model.replace_rows(source_rows)
        self.btn_remove_source.setEnabled(bool(source_rows))
        has_refresh_account = any(getattr(src, "last_seen_by_account_id", None) for src in data.get("sources", []))
        self.btn_refresh_member_profile.setEnabled(has_refresh_account)
        self.btn_refresh_member_profile.setToolTip(
            "Refresh this profile using one explicitly selected authorized source account." if has_refresh_account
            else "No authorized account is available to refresh this profile."
        )

        target_rows = []
        for row in data.get("target_states", []):
            target_rows.append({
                "Target": row["target_title"] or f"Target {row['target_group_id']}",
                "Status": str(row["state"] or "UNKNOWN").replace("_", " ").title(),
                "Last Sync / Check": format_local_datetime(row["last_checked_at"]),
                "Account": row["account_name"] or (f"@{row['account_username']}" if row["account_username"] else "—"),
                "Error": row["last_error_message"] or row["last_error_code"] or "—",
            })
        self.target_model.replace_rows(target_rows)

        history_rows = []
        for row in data.get("invitation_history", []):
            account = row["account_name"] or (f"@{row['account_username']}" if row["account_username"] else "—")
            history_rows.append({
                "Target": row["target_title"] or f"Target {row['target_group_id']}",
                "Account": account,
                "Action": str(row["action_type"] or "").replace("_", " ").title(),
                "Result": str(row["status"] or "UNKNOWN").replace("_", " ").title(),
                "Date": format_local_datetime(row["completed_at"] or row["attempted_at"]),
                "Error": row["error_message"] or row["telegram_error_code"] or "—",
            })
        self.invitation_model.replace_rows(history_rows)

    def save_eligibility(self):
        self.controller.set_eligibility(self.member_id, self.cmb_member_eligibility_edit.currentText())
        self.controller.set_consent(self.member_id, self.cmb_member_consent_edit.currentText())
        self.controller.update_notes(self.member_id, self.txt_member_eligibility_notes.toPlainText())
        self.reload()

    def refresh_profile(self):
        sources = self._details.get("sources", [])
        options, ids = [], []
        for src in sources:
            aid = getattr(src, "last_seen_by_account_id", None)
            if aid and aid not in ids:
                ids.append(aid)
                options.append(f"{src.account_name or ('Account '+str(aid))} — ID {aid}")
        if not ids:
            return
        label, ok = QInputDialog.getItem(self, "Refresh Member Profile", "Authorized source account", options, 0, False)
        if not ok:
            return
        aid = ids[options.index(label)]
        self.btn_refresh_member_profile.setEnabled(False)
        self.btn_refresh_member_profile.setText("Refreshing Member…")
        self.controller.refresh_member_profile(self.member_id, aid, lambda _r: self._profile_refresh_done())

    def _profile_refresh_done(self):
        self.btn_refresh_member_profile.setText("Refresh Telegram Profile")
        self.reload()

    def remove_source_relationship(self):
        selected = self.tbl_member_sources.selectionModel().selectedRows() if self.tbl_member_sources.selectionModel() else []
        if not selected:
            QMessageBox.information(self, "Remove Source", "Select a source relationship first.")
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._source_rows):
            return
        src = self._source_rows[row]
        title = getattr(src, "group_title", "source")
        if QMessageBox.question(
            self, "Remove Source Relationship",
            f"Remove this member's local source relationship with {title}?\n\nTelegram and the source group are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            self.controller.remove_member_source(self.member_id, int(src.group_id), False)
            self.reload()

    def add_tag(self):
        tag, ok = QInputDialog.getText(self, "Assign Member Tag", "Tag")
        if ok and tag.strip():
            self.controller.add_tag(self.member_id, tag.strip())
            self.reload()

    def remove_tag(self):
        tags = self.controller.service.repository.get_tags(self.member_id)
        if not tags:
            return
        tag, ok = QInputDialog.getItem(self, "Remove Member Tag", "Tag", tags, 0, False)
        if ok:
            self.controller.remove_tag(self.member_id, tag)
            self.reload()

# Add compatibility attributes for older PySide6 versions
if not hasattr(MemberDetailsDialog, 'Accepted'):
    MemberDetailsDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(MemberDetailsDialog, 'Rejected'):
    MemberDetailsDialog.Rejected = QDialog.DialogCode.Rejected
