from __future__ import annotations

from PySide6.QtCore import QDateTime, QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from app.models.log_table_model import LogTableModel
from app.pages.base_table_page import BaseTablePage
from app.widgets.calendar_utils import configure_calendar_popup


class LogsPage(BaseTablePage):
    def __init__(self, controller, parent=None):
        self.controller = controller

        super().__init__(
            "page_logs",
            "Logs",
            LogTableModel(controller.logs()),
            "tbl_logs",
            [
                ("btn_refresh_logs", "Refresh"),
                ("btn_clear_log_view", "Clear View"),
                ("btn_export_logs", "Export"),
                ("btn_open_log_details", "Details"),
            ],
            "le_search_logs",
            [
                (
                    "cmb_log_level",
                    "Level",
                    ["Info", "Warning", "Error", "Debug", "Critical"],
                ),
                (
                    "cmb_log_category",
                    "Category",
                    [
                        "System",
                        "Account",
                        "Group",
                        "Member",
                        "Campaign",
                        "Scheduler",
                        "Job",
                        "Database",
                        "Security",
                        "Audit",
                    ],
                ),
            ],
            parent,
        )

        self.enable_database_mode(controller.pagination)

        self.searchDebounced.connect(controller.set_search)
        self.filterChanged.connect(controller.set_filter)
        self.pageChanged.connect(controller.set_page)
        self.pageSizeChanged.connect(controller.set_page_size)

        controller.logsChanged.connect(self._on_logs_changed)

        self.action_buttons["btn_refresh_logs"].clicked.connect(
            controller.refresh
        )
        self.action_buttons["btn_export_logs"].clicked.connect(self.export)
        self.action_buttons["btn_clear_log_view"].clicked.connect(
            self._clear_view
        )
        self.action_buttons["btn_open_log_details"].clicked.connect(
            self.details
        )

        self.action_buttons["btn_clear_log_view"].hide()
        self.action_buttons["btn_open_log_details"].hide()

        self.btn_logs_more = QPushButton("More")
        self.btn_logs_more.setProperty("role", "ghost")

        more_menu = QMenu(self.btn_logs_more)
        more_menu.addAction("Open Selected Details", self.details)
        more_menu.addAction("Clear Current View", self._clear_view)
        self.btn_logs_more.setMenu(more_menu)
        self.page_header.add_action(self.btn_logs_more)

        self.table.customContextMenuRequested.connect(self.context_menu)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)

        columns = list(getattr(self.model, "columns", []) or [])
        if "Message" in columns:
            message_column = columns.index("Message")
            header.setSectionResizeMode(
                message_column,
                QHeaderView.ResizeMode.Stretch,
            )

        # Top category tabs
        self.tab_logs = QTabWidget()
        self.tab_logs.setObjectName("tab_logs")

        for name in (
            "Activity",
            "Telegram",
            "Errors",
            "Audit",
            "System",
        ):
            self.tab_logs.addTab(QWidget(), name)

        self.tab_logs.currentChanged.connect(self._tab_changed)

        # Use the concrete QVBoxLayout exposed by BaseTablePage rather than
        # QWidget.layout(), whose static type is only QLayout.
        self.root_layout.insertWidget(1, self.tab_logs)

        # Quick date filters
        quick = QWidget()
        quick_layout = QHBoxLayout(quick)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(8)

        self.chk_log_date_filter = QCheckBox("Date Range")
        self.chk_log_date_filter.setObjectName("chk_log_date_filter")

        self.dt_log_from = QDateTimeEdit(
            QDateTime.currentDateTime().addDays(-7)
        )
        self.dt_log_from.setObjectName("dt_log_from")
        configure_calendar_popup(self.dt_log_from)

        self.dt_log_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_log_to.setObjectName("dt_log_to")
        configure_calendar_popup(self.dt_log_to)

        self.btn_logs_advanced_filters = QPushButton("Advanced Filters")
        self.btn_logs_advanced_filters.setCheckable(True)
        self.btn_logs_advanced_filters.setProperty("role", "ghost")

        quick_layout.addWidget(self.chk_log_date_filter)
        quick_layout.addWidget(self.dt_log_from)
        quick_layout.addWidget(QLabel("to"))
        quick_layout.addWidget(self.dt_log_to)
        quick_layout.addWidget(self.btn_logs_advanced_filters)
        quick_layout.addStretch()

        self.root_layout.insertWidget(3, quick)

        # Advanced resource filters
        self.advanced_host = QWidget()
        advanced_layout = QHBoxLayout(self.advanced_host)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)
        advanced_layout.addWidget(QLabel("Resource IDs"))

        self.le_log_account_id = QLineEdit()
        self.le_log_account_id.setObjectName("le_log_account_id")
        self.le_log_account_id.setPlaceholderText("Account")

        self.le_log_group_id = QLineEdit()
        self.le_log_group_id.setObjectName("le_log_group_id")
        self.le_log_group_id.setPlaceholderText("Group")

        self.le_log_campaign_id = QLineEdit()
        self.le_log_campaign_id.setObjectName("le_log_campaign_id")
        self.le_log_campaign_id.setPlaceholderText("Campaign")

        self.le_log_job_id = QLineEdit()
        self.le_log_job_id.setObjectName("le_log_job_id")
        self.le_log_job_id.setPlaceholderText("Job")

        for line_edit in (
            self.le_log_account_id,
            self.le_log_group_id,
            self.le_log_campaign_id,
            self.le_log_job_id,
        ):
            line_edit.setMaximumWidth(130)
            line_edit.editingFinished.connect(self._advanced_filters)
            advanced_layout.addWidget(line_edit)

        advanced_layout.addStretch()
        self.advanced_host.hide()

        self.root_layout.insertWidget(4, self.advanced_host)

        self.btn_logs_advanced_filters.toggled.connect(
            self.advanced_host.setVisible
        )

        # These signals emit values. Accepting *_args in _advanced_filters
        # keeps PySide/Pylance signal typing happy while using the widgets'
        # current values as the source of truth.
        self.chk_log_date_filter.toggled.connect(self._advanced_filters)
        self.dt_log_from.dateTimeChanged.connect(self._advanced_filters)
        self.dt_log_to.dateTimeChanged.connect(self._advanced_filters)

    def _on_logs_changed(self, items) -> None:
        self.model.replace_rows(items)
        self.update_pagination(self.controller.pagination)

    def _clear_view(self) -> None:
        self.model.replace_rows([])

    def _tab_changed(self, index: int) -> None:
        label = self.tab_logs.tabText(index)

        if label == "Audit":
            self.controller.set_filter("Category", "Audit")
        elif label == "System":
            self.controller.set_filter("Category", "System")
        elif label == "Errors":
            self.controller.set_filter("Level", "Error")
        elif label == "Telegram":
            self.controller.set_filter("Category", "Telegram")
        elif label == "Activity":
            self.controller.set_filter("Category", "All")

    @staticmethod
    def _id(text: str) -> int | None:
        value = text.strip()
        return int(value) if value.isdigit() else None

    def _advanced_filters(self, *_args) -> None:
        date_from = None
        date_to = None

        if self.chk_log_date_filter.isChecked():
            date_from = (
                self.dt_log_from
                .dateTime()
                .toUTC()
                .toString(Qt.DateFormat.ISODate)
            )
            date_to = (
                self.dt_log_to
                .dateTime()
                .toUTC()
                .toString(Qt.DateFormat.ISODate)
            )

        self.controller.set_advanced_filters(
            account_id=self._id(self.le_log_account_id.text()),
            group_id=self._id(self.le_log_group_id.text()),
            campaign_id=self._id(self.le_log_campaign_id.text()),
            job_id=self._id(self.le_log_job_id.text()),
            date_from=date_from,
            date_to=date_to,
        )

    def context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)

        details_action = menu.addAction("Open Details")
        menu.addSeparator()
        import_action = menu.addAction("Import Logs CSV")

        viewport = self.table.viewport()
        chosen = menu.exec(viewport.mapToGlobal(pos))

        if chosen is details_action:
            self.details()
        elif chosen is import_action:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import Logs",
                "",
                "CSV Files (*.csv)",
            )
            if path:
                self.controller.import_csv(path)

    def export(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            "logs.csv",
            "CSV Files (*.csv)",
        )

        if path:
            self.controller.export_csv(path)

    def details(self) -> None:
        row = self.selected_row()

        if not row:
            return

        QMessageBox.information(
            self,
            "Log Details",
            "\n".join(
                f"{key}: {value}"
                for key, value in row.items()
            ),
        )
