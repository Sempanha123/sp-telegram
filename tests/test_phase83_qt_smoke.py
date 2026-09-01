"""Offscreen lifecycle coverage for the desktop shell and shared table pages."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.models.base_table_model import BaseTableModel
from app.pages.base_table_page import BaseTablePage
from app.pages.operations_page import OperationsPage
from app.styles.tokens import PAGE_PADDING, TABLE_HEADER_HEIGHT, TABLE_ROW_HEIGHT


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
