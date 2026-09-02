"""Offscreen lifecycle coverage for the desktop shell and shared table pages."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QObject, Signal, Qt
from PySide6.QtWidgets import QHeaderView, QPushButton, QScrollArea

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.pages.operations_page import OperationsPage
from app.styles.tokens import PAGE_PADDING, TABLE_HEADER_HEIGHT, TABLE_ROW_HEIGHT
from app.widgets.sidebar import Sidebar


class _OperationsManager:
    state = "READY"

    class _Network:
        telegram_state = "OFFLINE"

    network = _Network()
    workers = {}


class _OperationsController(QObject):
    operationsChanged = Signal(dict)
    diagnosticsReady = Signal(dict)
    securityAuditReady = Signal(dict)
    maintenanceCompleted = Signal(str, dict)

    def __init__(self):
        super().__init__()
        self.manager = _OperationsManager()
        self.calls = []

    def __getattr__(self, name):
        if name.startswith(("run_", "restart_", "checkpoint_", "optimize_", "vacuum_")) or name in {
            "pause_all",
            "resume_all",
        }:
            return lambda *args, _name=name, **kwargs: self.calls.append(_name)
        raise AttributeError(name)

    def refresh(self):
        self.calls.append("refresh")
        return {
            "database": {"state": "healthy"},
            "accounts": {"counts": {}},
            "jobs": {},
            "alerts": {},
            "workers": [],
            "performance": {},
        }


def test_geometry_tokens_match_qt_integer_apis(qapp, isolated_settings):
    assert (PAGE_PADDING, TABLE_HEADER_HEIGHT, TABLE_ROW_HEIGHT) == (20, 40, 36)

    page = BaseTablePage(
        "page_test",
        "Groups",
        BaseTableModel([], ["Name"]),
        "tbl_test",
        [("btn_test_action", "Test Action")],
        "le_test_search",
        [("cmb_test_status", "Status", ["Ready"])],
    )
    try:
        margins = page.root_layout.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            PAGE_PADDING,
            PAGE_PADDING,
            PAGE_PADDING,
            PAGE_PADDING,
        )
        assert page.table.horizontalHeader().height() == TABLE_HEADER_HEIGHT
        assert page.table.verticalHeader().defaultSectionSize() == TABLE_ROW_HEIGHT

        page.filter_boxes["cmb_test_status"].setCurrentText("Ready")
        assert page.btn_clear_filters.isVisibleTo(page)
        page.btn_clear_filters.click()
        assert page.filter_boxes["cmb_test_status"].currentText() == "All"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_collapsed_sidebar_keeps_icons_visible_without_a_scrollbar(qapp, isolated_settings):
    sidebar = Sidebar()
    try:
        sidebar.set_collapsed(True)
        sidebar.show()
        qapp.processEvents()

        margins = sidebar.root_layout.contentsMargins()
        assert sidebar.width() == sidebar.compact_width == 60
        assert (margins.left(), margins.right()) == (4, 4)
        assert sidebar.nav_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert sidebar._buttons["settings"].width() <= 44
    finally:
        sidebar.close()
        sidebar.deleteLater()
        qapp.processEvents()


def test_shared_table_filters_use_one_aligned_control_row(qapp, isolated_settings):
    page = BaseTablePage(
        "page_filter_alignment",
        "Accounts",
        BaseTableModel([{"Account": "Example"}], ["Account"]),
        "tbl_filter_alignment",
        [],
        "le_filter_alignment_search",
        [
            ("cmb_filter_health", "Health", ["Healthy"]),
            ("cmb_filter_connection", "Connection", ["Connected"]),
        ],
    )
    try:
        page.resize(1100, 700)
        page.show()
        qapp.processEvents()

        controls = [page.search, *page.filter_boxes.values(), page.btn_clear_filters, page.btn_table_tools]
        assert all(control.height() == 40 for control in controls)
        assert page.search_label.text() == "Search"
        assert all(label.height() == page.search_label.height() == 14 for label in page.filter_labels.values())

        search_top = page.search.mapTo(page, QPoint(0, 0)).y()
        assert all(
            combo.mapTo(page, QPoint(0, 0)).y() == search_top
            for combo in page.filter_boxes.values()
        )
        assert page.btn_table_tools.mapTo(page, QPoint(0, 0)).y() == search_top
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_shared_table_tools_select_clear_and_restore_columns(qapp, isolated_settings):
    page = BaseTablePage(
        "page_table_tools",
        "Groups",
        BaseTableModel([{"Name": "One", "Status": "Ready"}, {"Name": "Two", "Status": "Ready"}], ["Name", "Status"]),
        "tbl_table_tools",
        [],
        "le_table_tools_search",
        [],
    )
    try:
        page.show()
        qapp.processEvents()
        page.install_table_preferences()

        page.select_all_visible()
        assert len(page.table.selectionModel().selectedRows()) == 2
        assert page.btn_table_tools.text() == "2 Selected ▾"

        page.clear_selection()
        assert not page.table.selectionModel().selectedRows()
        assert page.btn_table_tools.text() == "Select / View ▾"

        page.table.setColumnHidden(1, True)
        page.table_preferences.show_all_user_columns(page.table.objectName())
        assert not page.table.isColumnHidden(1)
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_search_clear_is_shared_and_empty_tables_hide_table_only_controls(qapp, isolated_settings):
    page = BaseTablePage(
        "page_search_clear",
        "Accounts",
        BaseTableModel([], ["Account"]),
        "tbl_search_clear",
        [],
        "le_search_clear",
        [],
    )
    try:
        page.show()
        page.search.setText("missing")
        qapp.processEvents()
        assert page.btn_clear_filters.isVisibleTo(page)
        assert page.btn_table_tools.isHidden()

        page.btn_clear_filters.click()
        assert page.search.text() == ""
        assert page.btn_clear_filters.isHidden()
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_locked_table_page_stays_compact_at_large_window_sizes(qapp, isolated_settings):
    page = BaseTablePage(
        "page_locked_layout",
        "Campaigns",
        BaseTableModel([], ["Campaign"]),
        "tbl_locked_layout",
        [("btn_create_locked", "Create")],
        "le_locked_search",
        [("cmb_locked_status", "Status", ["Ready"])],
    )
    try:
        page.set_feature_lock(
            True,
            title="Campaigns",
            description="Upgrade to create campaigns.",
            feature_list=["Managed-group campaigns", "Media posts"],
            action_text="View Pro Plan",
        )
        page.resize(1200, 900)
        page.show()
        qapp.processEvents()

        assert page.page_header.height() <= 104
        assert page._license_lock.height() <= 320
        assert page._license_lock.geometry().top() < 180
        assert page.filter_host.isHidden()
        assert page._license_lock.btn_upgrade_feature.text() == "View Pro Plan"
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_operations_page_uses_integer_table_dimensions(qapp, isolated_settings):
    controller = _OperationsController()
    page = OperationsPage(controller)
    try:
        for table in (page.tbl_operations_workers, page.tbl_operations_queues):
            assert table.horizontalHeader().height() == TABLE_HEADER_HEIGHT
            assert table.verticalHeader().defaultSectionSize() == TABLE_ROW_HEIGHT
        page.btn_operations_refresh.click()
        assert controller.calls.count("refresh") >= 2
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_main_window_constructs_and_navigates_all_pages(
    qapp,
    isolated_settings,
    tmp_path,
):
    runtime_root = tmp_path / "runtime"
    context = ApplicationContext(runtime_root)
    window = None
    try:
        window = MainWindow(context)
        assert len(window.pages) == 22

        for key in window.pages:
            window.navigate(key)
            qapp.processEvents()
            assert window.current_key() == key
            assert window.stack_main_pages.currentWidget() is window.pages[key]

        settings = window.pages["settings"]
        first_settings_tab = settings.tab_settings.widget(0)
        assert isinstance(first_settings_tab, QScrollArea)
        assert first_settings_tab.widget().objectName() == "settings_tab_page"

        health_header = window.pages["account_health"].table.horizontalHeader()
        assert health_header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive

        assert not [
            button.objectName()
            for button in window.findChildren(QPushButton)
            if button.property("productionUnavailable")
        ]
    finally:
        if window is not None:
            window.hide()
            window.deleteLater()
            qapp.processEvents()
        context.close()


def test_shell_preserves_page_owned_action_state(
    qapp,
    isolated_settings,
    tmp_path,
):
    context = ApplicationContext(tmp_path / "runtime")
    window = None
    try:
        window = MainWindow(context)
        dashboard = window.pages["dashboard"]
        settings = window.pages["settings"]
        operations = window.pages["operations"]

        assert dashboard.btn_quick_add_account.isEnabled()
        assert dashboard.btn_quick_add_group.isEnabled()
        assert dashboard.btn_quick_create_campaign.isEnabled()
        assert settings.btn_about.isEnabled()

        expected_lock_state = context.feature_gate.has_feature("FEATURE_APP_LOCK")
        assert settings.btn_set_app_lock_password.isEnabled() is expected_lock_state
        assert operations.btn_lock_application.isEnabled() is expected_lock_state

        clear_filters = window.pages["groups"].btn_clear_filters
        assert clear_filters.isEnabled()
        assert clear_filters.property("productionUnavailable") is None
    finally:
        if window is not None:
            window.hide()
            window.deleteLater()
            qapp.processEvents()
        context.close()
