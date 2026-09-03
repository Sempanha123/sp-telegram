from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from app.dialogs.smart_add_members_dialog import SmartAddMembersDialog


VISIBLE_NAV = (
    "dashboard",
    "flow_studio",
    "accounts",
    "groups",
    "members",
    "blacklist",
    "campaigns",
    "scheduler",
    "templates",
    "jobs",
    "analytics",
    "alerts",
    "operations",
    "logs",
    "license",
    "settings",
)

NAV_LABELS = {
    "flow_studio": "Add Member",
    "groups": "Groups",
    "members": "Member Pool",
    "blacklist": "Safety List",
    "operations": "System Monitor",
    "license": "Plan & License",
}


def _hide_action(page, *names: str) -> None:
    buttons = getattr(page, "action_buttons", {}) or {}
    for name in names:
        button = buttons.get(name)
        if button is not None:
            button.hide()


def _disconnect_context(widget) -> None:
    try:
        widget.customContextMenuRequested.disconnect()
    except (TypeError, RuntimeError):
        pass


def _menu_exec(menu: QMenu, table, pos) -> None:
    menu.exec(table.viewport().mapToGlobal(pos))


def _apply_sidebar(window) -> None:
    sidebar = getattr(window, "sidebar", None)
    if sidebar is None:
        return

    visible = set(VISIBLE_NAV)
    for key, button in getattr(sidebar, "_buttons", {}).items():
        button.setVisible(key in visible)

    for key, label in NAV_LABELS.items():
        if key in getattr(sidebar, "_labels", {}):
            sidebar._labels[key] = label
            sidebar._refresh_button(key)

    # Remove empty section labels after hidden technical pages disappear.
    for label in getattr(sidebar, "_section_labels", []):
        if not label.text().strip():
            label.hide()


def _member_add_selected(page) -> None:
    ids = list(page._selected_member_ids())
    if not ids:
        QMessageBox.information(page, "Add Selected to Group", "Select one or more members first.")
        return
    if len(ids) > 100:
        QMessageBox.information(
            page,
            "Add Selected to Group",
            f"You selected {len(ids):,} members.\n\n"
            "Manual selection supports up to 100 exact members per run.\n\n"
            "For larger automatic transfers, use Add Member: drag a Source Group onto a Target Group.",
        )
        return
    SmartAddMembersDialog(
        page.controller,
        ids,
        target_group_id=page._active_target_id(),
        parent=page,
    ).exec()


def _apply_members(page) -> None:
    _hide_action(
        page,
        "btn_prepare_target",
        "btn_mass_add_to_target",
        "btn_member_more",
        "btn_member_tags",
        "btn_member_eligibility",
        "btn_member_blacklist",
    )

    add_button = getattr(page, "action_buttons", {}).get("btn_invite_to_target")
    if add_button is not None:
        add_button.setText("Add Selected to Group")
        add_button.setToolTip(
            "Add the exact members you selected. "
            "For automatic Source Group → Target Group transfer, use Add Member."
        )
        try:
            add_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        add_button.clicked.connect(lambda: _member_add_selected(page))

    sync_button = getattr(page, "action_buttons", {}).get("btn_member_sync")
    if sync_button is not None:
        sync_button.setText("Sync Members")
        sync_button.setToolTip("Collect or refresh accessible members from a Source Group.")

    if hasattr(page, "btn_selection_dnc"):
        page.btn_selection_dnc.hide()
    if hasattr(page, "target_summary"):
        page.target_summary.hide()

    # Keep only normal-user filters in the default flow.
    for obj in (
        "cmb_member_status",
        "cmb_member_consent",
        "cmb_member_tag",
        "cmb_member_bot_filter",
        "cmb_member_blacklist_filter",
    ):
        combo = getattr(page, "filter_boxes", {}).get(obj)
        if combo is not None:
            host = combo.parentWidget()
            if host is not None:
                host.hide()
            else:
                combo.hide()

    for name in (
        "chk_exclude_blacklist",
        "chk_exclude_existing",
        "chk_only_with_username",
        "chk_only_eligible",
    ):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.hide()

    _disconnect_context(page.table)
    page.table.setToolTip("Select with checkboxes. Double-click a member to view details.")


def _accounts_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    page._update_action_states()
    menu = QMenu(page)
    menu.addAction(page.act_account_details)
    menu.addAction(page.act_account_refresh_profile)
    menu.addAction(page.act_account_sessions)
    menu.addSeparator()
    menu.addAction(page.act_account_login)
    menu.addAction(page.act_account_logout)
    menu.addSeparator()
    menu.addAction(page.act_account_edit)
    menu.addAction(page.act_account_disable)
    menu.addSeparator()
    menu.addAction(page.act_account_remove)
    _menu_exec(menu, page.table, pos)


def _apply_accounts(page) -> None:
    _hide_action(page, "btn_more_account_actions")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _accounts_context(page, pos))
    page.table.setToolTip(
        "Connect, Disconnect and Health Check are in the header. "
        "Right-click for details, sessions, login/logout and local account settings."
    )


def _groups_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    if not page.selected_item():
        return
    menu = QMenu(page)
    menu.addAction(page.actions["act_group_details"])
    menu.addAction(page.actions["act_group_refresh_permissions"])
    classification = menu.addMenu("Classification")
    classification.addAction(page.actions["act_group_mark_source"])
    classification.addAction(page.actions["act_group_mark_target"])
    classification.addAction(page.actions["act_group_mark_managed"])
    menu.addSeparator()
    menu.addAction(page.actions["act_group_open_telegram"])
    menu.addSeparator()
    menu.addAction(page.actions["act_group_remove"])
    _menu_exec(menu, page.table, pos)


def _apply_groups(page) -> None:
    _hide_action(page, "btn_more_group_actions", "btn_resolve_group")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _groups_context(page, pos))
    page.table.setToolTip(
        "Header: Add, Discover, Sync, Refresh. "
        "Right-click a group for details, permissions, Source/Target classification or remove."
    )


def _campaign_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    item = page.selected_item()
    if item is None:
        return
    status = str(getattr(item, "status", "") or "").upper()

    menu = QMenu(page)
    open_action = menu.addAction("Open Campaign")
    duplicate_action = menu.addAction("Duplicate")
    preview_action = menu.addAction("Preview")
    menu.addSeparator()
    pause_action = menu.addAction("Pause")
    resume_action = menu.addAction("Resume")
    cancel_action = menu.addAction("Cancel")
    export_action = menu.addAction("Export Results")
    menu.addSeparator()
    archive_action = menu.addAction("Unarchive" if status == "ARCHIVED" else "Archive")
    delete_action = menu.addAction("Delete Draft" if status in {"DRAFT", "CANCELLED"} else "Delete")

    pause_action.setEnabled(status == "RUNNING")
    resume_action.setEnabled(status == "PAUSED")
    cancel_action.setEnabled(status in {"SCHEDULED", "RUNNING", "PAUSED"})

    chosen = menu.exec(page.table.viewport().mapToGlobal(pos))
    if chosen is open_action:
        page._details()
    elif chosen is duplicate_action:
        page.duplicate()
    elif chosen is preview_action:
        page.preview()
    elif chosen is pause_action:
        page.pause()
    elif chosen is resume_action:
        page.resume()
    elif chosen is cancel_action:
        page.cancel()
    elif chosen is export_action:
        page._export()
    elif chosen is archive_action:
        page._unarchive() if status == "ARCHIVED" else page._archive()
    elif chosen is delete_action:
        page._delete()


def _apply_campaigns(page) -> None:
    _hide_action(page, "btn_more_campaign_actions")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _campaign_context(page, pos))
    page.table.setToolTip(
        "Header: New Campaign, Edit, Run, Refresh. "
        "Right-click for preview, duplicate, pause/resume/cancel, export, archive or delete."
    )


def _jobs_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    page._refresh_job_actions()
    menu = QMenu(page)
    added = False
    for key, label in (
        ("btn_pause_selected_job", "Pause"),
        ("btn_resume_selected_job", "Resume"),
        ("btn_retry_failed_job", "Retry"),
        ("btn_cancel_selected_job", "Cancel"),
    ):
        button = page.action_buttons[key]
        if button.isEnabled():
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, b=button: b.click())
            added = True
    if added:
        menu.addSeparator()
    export_button = page.action_buttons["btn_export_job_results"]
    export_action = menu.addAction("Export Jobs")
    export_action.setEnabled(export_button.isEnabled())
    export_action.triggered.connect(lambda _checked=False: export_button.click())
    _menu_exec(menu, page.table, pos)


def _apply_jobs(page) -> None:
    _hide_action(page, "btn_jobs_more")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _jobs_context(page, pos))
    page.table.setToolTip(
        "Double-click for job details. Header shows Details/Result; "
        "right-click for Pause, Resume, Retry, Cancel or Export."
    )


def _alerts_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    menu = QMenu(page)
    open_action = menu.addAction("Open")
    ack_action = menu.addAction("Acknowledge")
    resolve_action = menu.addAction("Resolve")
    mute_action = menu.addAction("Mute")
    chosen = menu.exec(page.table.viewport().mapToGlobal(pos))
    if chosen is open_action:
        page.open_alert()
    elif chosen is ack_action:
        page._action("acknowledge")
    elif chosen is resolve_action:
        page._action("resolve")
    elif chosen is mute_action:
        page._action("mute")


def _apply_alerts(page) -> None:
    _hide_action(page, "btn_open_alert", "btn_acknowledge_alert", "btn_resolve_alert", "btn_mute_alert")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _alerts_context(page, pos))
    page.table.setToolTip(
        "Double-click to open. Right-click to Acknowledge, Resolve or Mute. "
        "Header keeps page-wide actions only."
    )


def _template_context(page, pos) -> None:
    if not page.table.indexAt(pos).isValid():
        return
    menu = QMenu(page)
    edit_action = menu.addAction("Edit")
    duplicate_action = menu.addAction("Duplicate")
    menu.addSeparator()
    delete_action = menu.addAction("Delete")
    chosen = menu.exec(page.table.viewport().mapToGlobal(pos))
    if chosen is edit_action:
        page.edit()
    elif chosen is duplicate_action:
        page.duplicate()
    elif chosen is delete_action:
        page.delete()


def _apply_templates(page) -> None:
    _hide_action(page, "btn_edit_template", "btn_duplicate_template", "btn_delete_template")
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _template_context(page, pos))
    try:
        page.table.doubleClicked.disconnect()
    except (TypeError, RuntimeError):
        pass
    page.table.doubleClicked.connect(lambda _i: page.edit())
    page.table.setToolTip("Create/Use are in the header. Double-click to edit; right-click to duplicate or delete.")


def _schedule_context(page, pos) -> None:
    index = page.tbl_schedules.indexAt(pos)
    if not index.isValid():
        return
    page.tbl_schedules.selectRow(index.row())
    row = page.schedule_model.row_dict(index.row())
    status = str(row.get("Status") or "").upper()

    menu = QMenu(page)
    edit_action = menu.addAction("Edit")
    run_action = menu.addAction("Run Now")
    sync_action = menu.addAction("Sync Telegram")
    menu.addSeparator()
    pause_action = menu.addAction("Pause")
    resume_action = menu.addAction("Resume")
    cancel_action = menu.addAction("Cancel")

    pause_action.setEnabled(status in {"ACTIVE", "SCHEDULED"})
    resume_action.setEnabled(status == "PAUSED")
    cancel_action.setEnabled(status not in {"SENT", "CANCELLED", "CANCELLED EXTERNALLY", "EXPIRED"})

    chosen = menu.exec(page.tbl_schedules.viewport().mapToGlobal(pos))
    if chosen is edit_action:
        page.edit()
    elif chosen is run_action:
        page.run_now()
    elif chosen is sync_action:
        page._selected_call(page.controller.sync_telegram)
    elif chosen is pause_action:
        page._selected_call(page.controller.pause)
    elif chosen is resume_action:
        page._selected_call(page.controller.resume)
    elif chosen is cancel_action:
        page.cancel()


def _apply_scheduler(page) -> None:
    for name in (
        "btn_edit_schedule",
        "btn_pause_schedule",
        "btn_resume_schedule",
        "btn_cancel_schedule",
        "btn_run_schedule_now",
        "btn_sync_scheduled_posts",
    ):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.hide()

    page.tbl_schedules.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    _disconnect_context(page.tbl_schedules)
    page.tbl_schedules.customContextMenuRequested.connect(lambda pos: _schedule_context(page, pos))
    page.tbl_schedules.setToolTip(
        "Header: calendar view, + Schedule, Refresh. "
        "Double-click or right-click a schedule for selected-row actions."
    )


def _logs_context(page, pos) -> None:
    menu = QMenu(page)
    details_action = menu.addAction("Open Details")
    import_action = menu.addAction("Import Logs CSV")
    menu.addSeparator()
    clear_action = menu.addAction("Clear Current View")
    chosen = menu.exec(page.table.viewport().mapToGlobal(pos))
    if chosen is details_action:
        page.details()
    elif chosen is import_action:
        path, _ = QFileDialog.getOpenFileName(page, "Import Logs", "", "CSV Files (*.csv)")
        if path:
            page.controller.import_csv(path)
    elif chosen is clear_action:
        page._clear_view()


def _apply_logs(page) -> None:
    button = getattr(page, "btn_logs_more", None)
    if button is not None:
        button.hide()
    _disconnect_context(page.table)
    page.table.customContextMenuRequested.connect(lambda pos: _logs_context(page, pos))
    page.table.setToolTip("Header: Refresh and Export. Right-click for Details, Import or Clear Current View.")


def _apply_operations(page) -> None:
    duplicate = getattr(page, "btn_operations_run_diagnostics", None)
    if duplicate is not None:
        duplicate.hide()


def _apply_target_groups(page) -> None:
    _hide_action(page, "btn_mass_add_to_target")
    more = getattr(page, "btn_target_more_actions", None)
    if more is not None:
        more.hide()
    advanced = getattr(page, "act_advanced_mass_add", None)
    if advanced is not None:
        advanced.setVisible(False)


def apply_product_ux(window) -> None:
    """Apply one clear action surface per page without removing backend capabilities."""
    _apply_sidebar(window)

    pages = getattr(window, "pages", {})
    handlers = (
        ("members", _apply_members),
        ("accounts", _apply_accounts),
        ("groups", _apply_groups),
        ("campaigns", _apply_campaigns),
        ("jobs", _apply_jobs),
        ("alerts", _apply_alerts),
        ("templates", _apply_templates),
        ("scheduler", _apply_scheduler),
        ("logs", _apply_logs),
        ("operations", _apply_operations),
        ("target_groups", _apply_target_groups),
    )
    for key, handler in handlers:
        page = pages.get(key)
        if page is None:
            continue
        try:
            handler(page)
        except Exception:
            # UX cleanup must never prevent the application from opening.
            continue
