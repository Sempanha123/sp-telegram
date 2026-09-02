from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QSettings, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QTableView,
    QVBoxLayout, QWidget,
)

from app.constants import APP_NAME, DEFAULT_WINDOW_SIZE, MIN_WINDOW_SIZE, OperationalState
from app.dialogs.create_campaign_dialog import CreateCampaignDialog
from app.dialogs.campaign_preview_dialog import CampaignPreviewDialog
from app.dialogs.campaign_details_dialog import CampaignDetailsDialog
from app.dialogs.save_campaign_template_dialog import SaveCampaignAsTemplateDialog
from app.dialogs.notification_center_dialog import NotificationCenterDialog
from app.dialogs.app_lock_dialog import AppLockDialog
from app.dialogs.upgrade_plan_dialog import UpgradePlanDialog
from app.widgets.command_palette import CommandPaletteDialog
from app.pages.account_health_page import AccountHealthPage
from app.pages.account_pool_page import AccountPoolPage
from app.pages.accounts_page import AccountsPage
from app.pages.alerts_page import AlertsPage
from app.pages.analytics_page import AnalyticsPage
from app.pages.blacklist_page import BlacklistPage
from app.pages.campaigns_page import CampaignsPage
from app.pages.collector_page import CollectorPage
from app.pages.dashboard_page import DashboardPage
from app.pages.groups_page import GroupsPage
from app.pages.jobs_page import JobsPage
from app.pages.logs_page import LogsPage
from app.pages.license_page import LicensePage
from app.pages.operations_page import OperationsPage
from app.pages.members_page import MembersPage
from app.pages.restrictions_page import RestrictionsPage
from app.pages.scheduler_page import SchedulerPage
from app.pages.sessions_page import SessionsPage
from app.pages.settings_page import SettingsPage
from app.pages.source_groups_page import SourceGroupsPage
from app.pages.target_groups_page import TargetGroupsPage
from app.pages.templates_page import TemplatesPage
from app.theme import apply_theme, normalize_theme
from app.license.feature_keys import FeatureKey, LimitKey
from app.license.license_models import PlanKey
from app.license.plan_config import PLAN_CONFIG, PLAN_ORDER
from app.localization import LocalizationManager
from app.widgets.sidebar import Sidebar
from app.widgets.toast import ToastNotification
from app.widgets.topbar import TopBar
from app.utils.table_preferences import TablePreferenceManager


def _int_setting(manager, name: str, default: int) -> int:
    """Coerce a QSettings-backed preference to an int, falling back to default."""
    value = manager.global_value(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class MainWindow(QMainWindow):
    account_selected = Signal(int)
    account_health_changed = Signal(int, str)
    group_selected = Signal(int)
    member_selected = Signal(int)
    campaign_selected = Signal(int)
    campaign_created = Signal(dict)
    campaign_updated = Signal(dict)
    schedule_changed = Signal()
    job_status_changed = Signal(int, str)
    alert_created = Signal(dict)
    toast_requested = Signal(str, str)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.settings = QSettings()
        self._table_preferences = TablePreferenceManager(self.settings, self)
        self.setWindowTitle(APP_NAME)
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self.pages = {}
        self._page_keys = []
        self._operations_paused = False
        self._privacy_mode = bool(context.settings_service.get("privacy_mode", False))
        self._shutdown_requested = False
        self._lock_dialog_open = False
        self._lock_paused_operations = False
        self.localization = LocalizationManager(context.settings_service.get("language", "English"))
        self._build_ui()
        self._connect_signals()
        self._refresh_table_preferences()
        self._install_shortcuts()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._localize_focus_window)
        self._restore_state()
        self._apply_localization()
        self.refresh_all()
        # Runs after the event loop can process worker signals. It never initiates login.
        QTimer.singleShot(0, self.context.account_controller.startup_recovery)
        if bool(self.context.settings_service.get("auto_sync_groups", False)):
            QTimer.singleShot(3000, self._startup_group_sync)
        self._campaign_scheduler_timer = QTimer(self); self._campaign_scheduler_timer.setInterval(30000); self._campaign_scheduler_timer.timeout.connect(self._scheduler_tick); self._campaign_scheduler_timer.start(); QTimer.singleShot(4000, self._scheduler_tick)
        self._operations_timer = QTimer(self); self._operations_timer.setInterval(max(1000, int(self.context.settings_service.get("performance_sample_seconds", 10)) * 1000)); self._operations_timer.timeout.connect(self._operations_tick); self._operations_timer.start()
        self._account_monitor_timer = QTimer(self); self._account_monitor_timer.setInterval(max(60000, int(self.context.settings_service.get("account_monitor_interval", 5)) * 60000)); self._account_monitor_timer.timeout.connect(self._account_monitor_tick); self._account_monitor_timer.start()
        self._group_monitor_timer = QTimer(self); self._group_monitor_timer.setInterval(max(300000, int(self.context.settings_service.get("group_monitor_interval", 30)) * 60000)); self._group_monitor_timer.timeout.connect(self._group_monitor_tick); self._group_monitor_timer.start()
        self._auto_lock_timer = QTimer(self); self._auto_lock_timer.setInterval(15000); self._auto_lock_timer.timeout.connect(self._auto_lock_tick); self._auto_lock_timer.start()
        self._backup_timer = QTimer(self); self._backup_timer.setInterval(3600000); self._backup_timer.timeout.connect(self._auto_backup_tick); self._backup_timer.start(); QTimer.singleShot(10000, self._auto_backup_tick)
        self._maintenance_timer = QTimer(self); self._maintenance_timer.setInterval(24 * 3600000); self._maintenance_timer.timeout.connect(self._retention_tick); self._maintenance_timer.start()
        self._license_validation_timer = QTimer(self); self._license_validation_timer.setInterval(6 * 3600000); self._license_validation_timer.timeout.connect(self.context.license_controller.refresh_if_due); self._license_validation_timer.start(); QTimer.singleShot(5000, self.context.license_controller.refresh_if_due)
        # Track inactivity only on real QWidget/QObject instances.  An
        # application-wide event filter can receive internal layout items on
        # some PySide6/Qt paths, which are not QObject-compatible watched
        # objects.  Installing on the window tree keeps the same activity
        # semantics without exposing QObject.eventFilter() to QWidgetItem.
        self._install_activity_filters()
        self.set_privacy_mode(self._privacy_mode, persist=False)
        self._apply_license_ui()
        if not bool(getattr(self.context, "previous_shutdown_clean", True)):
            report = getattr(self.context, "startup_recovery_report", {"interrupted": 0, "reconcile_required": 0})
            if report.get("interrupted", 0) or report.get("reconcile_required", 0):
                QTimer.singleShot(0, lambda: self._show_crash_recovery_dialog(report))

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central_root")
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = Sidebar()
        shell.addWidget(self.sidebar)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.topbar = TopBar()
        layout.addWidget(self.topbar)
        self.stack_main_pages = QStackedWidget()
        self.stack_main_pages.setObjectName("stack_main_pages")
        layout.addWidget(self.stack_main_pages, 1)
        shell.addWidget(content, 1)
        self.toast = ToastNotification(content)

        c = self.context
        self._add_page("dashboard", DashboardPage(c.dashboard_controller, activity_loader=lambda: c.log_repository.get_recent(10)))
        self._add_page("operations", OperationsPage(c.operations_controller))
        self._add_page("accounts", AccountsPage(c.account_controller, avatar_service=c.avatar_service))
        self._add_page("account_pool", AccountPoolPage(c.account_pool_controller, c.account_controller, c.group_controller, avatar_service=c.avatar_service))
        self._add_page("account_health", AccountHealthPage(c.account_controller, avatar_service=c.avatar_service))
        self._add_page("restrictions", RestrictionsPage(c.restriction_controller, avatar_service=c.avatar_service))
        self._add_page("sessions", SessionsPage(c.account_controller))
        self._add_page("groups", GroupsPage(c.group_controller, avatar_service=c.avatar_service))
        self._add_page("source_groups", SourceGroupsPage(c.group_controller, c.member_controller, avatar_service=c.avatar_service))
        self._add_page("target_groups", TargetGroupsPage(c.group_controller, c.member_controller, avatar_service=c.avatar_service))
        self._add_page("members", MembersPage(c.member_controller, c.group_controller, avatar_service=c.avatar_service))
        self._add_page("collector", CollectorPage(c.member_controller))
        self._add_page("blacklist", BlacklistPage(c.blacklist_controller))
        self._add_page("campaigns", CampaignsPage(c.campaign_controller))
        self._add_page("scheduler", SchedulerPage(c.scheduler_controller, c.campaign_controller))
        self._add_page("templates", TemplatesPage(c.template_controller))
        self._add_page("jobs", JobsPage(c.job_controller))
        self._add_page("analytics", AnalyticsPage(c))
        self._add_page("alerts", AlertsPage(c.alert_controller))
        self._add_page("logs", LogsPage(c.log_controller))
        self._add_page("license", LicensePage(c.license_controller))
        self._add_page("settings", SettingsPage(c.settings_controller, group_controller=c.group_controller))

        self.topbar.set_database_connected(True)
        self._refresh_telegram_topbar()
        ls=c.license_service.get_current_license();self.topbar.set_license_status(ls.plan, str(ls.status), ls.expires_at)
        self._update_statusbar()

    def _add_page(self, key, page):
        self.pages[key] = page
        self._page_keys.append(key)
        self.stack_main_pages.addWidget(page)

    def _connect_signals(self):
        self.sidebar.pageRequested.connect(self.navigate)
        self.sidebar.collapsedChanged.connect(lambda value: self.settings.setValue("window/sidebar_collapsed", value))
        self.topbar.pauseToggled.connect(self.on_operations_pause_toggled)
        self.topbar.searchRequested.connect(self.on_global_search)
        self.topbar.commandPaletteRequested.connect(self._open_command_palette)
        self.topbar.notificationsRequested.connect(self.open_notification_center)
        self.topbar.themeRequested.connect(self.on_toggle_theme)
        self.topbar.licenseRequested.connect(lambda: self.navigate("license", "License"))
        self.toast_requested.connect(self.toast.show_message)

        controllers = [
            self.context.account_controller, self.context.account_pool_controller, self.context.group_controller,
            self.context.member_controller, self.context.blacklist_controller,
            self.context.campaign_controller, self.context.scheduler_controller,
            self.context.job_controller, self.context.log_controller,
            self.context.alert_controller, self.context.settings_controller, self.context.template_controller,
            self.context.operations_controller, self.context.restriction_controller, self.context.license_controller,
        ]
        for controller in controllers:
            if hasattr(controller, "toast_requested"):
                controller.toast_requested.connect(self.toast_requested)

        self.pages["dashboard"].quickAction.connect(self.on_dashboard_quick_action)
        self.pages["members"].openCollectorRequested.connect(lambda: self.navigate("collector", "Collector"))
        campaigns = self.pages["campaigns"]
        campaigns.createRequested.connect(self.on_create_campaign_clicked)
        campaigns.editRequested.connect(self.on_edit_campaign)
        campaigns.previewRequested.connect(self.on_preview_campaign)
        campaigns.detailsRequested.connect(self.on_campaign_details)
        campaigns.toastRequested.connect(self.toast_requested)
        self.pages["scheduler"].toastRequested.connect(self.toast_requested)
        self.pages["templates"].toastRequested.connect(self.toast_requested)
        self.pages["templates"].useRequested.connect(self.on_use_template)
        self.pages["target_groups"].campaignRequested.connect(self.on_create_campaign_for_group)
        self.pages["scheduler"].campaignOpenRequested.connect(self.on_scheduler_campaign_open)
        self.context.scheduler_controller.missedOccurrenceNeedsDecision.connect(lambda sid:self.toast_requested.emit(f"Schedule #{sid} was missed while the application was offline. Open Scheduler to Run Now, Skip, or edit it.","Warning"))
        self.pages["accounts"].toastRequested.connect(self.toast_requested)
        self.pages["account_pool"].toastRequested.connect(self.toast_requested)
        self.pages["accounts"].openSettingsRequested.connect(self.open_telegram_settings)
        self.pages["accounts"].sessionsRequested.connect(self.open_sessions_for_account)
        self.pages["groups"].toastRequested.connect(self.toast_requested)
        self.pages["settings"].themeRequested.connect(self.set_theme)
        self.pages["settings"].tablePreferencesChanged.connect(self._refresh_table_preferences)
        self.pages["settings"].tableAutoFitRequested.connect(self._auto_fit_all_tables)
        self.pages["license"].toastRequested.connect(self.toast_requested)
        for page_key in ("campaigns","scheduler","templates","analytics"):
            page=self.pages.get(page_key);signal=getattr(page,"licenseUpgradeRequested",None)
            if signal:signal.connect(lambda _plan:self.navigate("license","License"))
        self.pages["operations"].criticalAlertsRequested.connect(lambda: self.navigate("alerts", "Alerts"))
        self.pages["operations"].privacyModeRequested.connect(self.toggle_privacy_mode)
        self.pages["members"].privacyModeDisableRequested.connect(lambda: self.set_privacy_mode(False))
        self.pages["operations"].lockRequested.connect(self.lock_application)
        self.context.settings_controller.databaseRestored.connect(self.refresh_all)
        self.context.settings_controller.telegramConfigChanged.connect(
            lambda _valid: self._refresh_telegram_topbar()
        )
        self.context.account_controller.telegramGlobalStatusChanged.connect(self._telegram_runtime_state)
        self.context.account_controller.account_health_changed.connect(self.account_health_changed)
        self.context.account_controller.accountsChanged.connect(lambda *_: self._refresh_telegram_topbar())
        self.context.account_controller.accountsChanged.connect(lambda *_: self.pages["analytics"].refresh_filter_options())
        self.context.group_controller.groupsChanged.connect(self._refresh_group_dependents)
        self.context.campaign_controller.campaignsChanged.connect(lambda *_: self.pages["analytics"].refresh_filter_options())
        self.context.alert_controller.alertCountChanged.connect(self.topbar.set_notification_count)
        self.context.alert_controller.alertCountChanged.connect(lambda count: self.sidebar.set_badge("alerts", count))
        self.context.operations_manager.networkStateChanged.connect(self.topbar.set_network_status)
        self.context.operations_manager.operationsPaused.connect(lambda: self.topbar.set_paused(True))
        self.context.operations_manager.operationsResumed.connect(lambda: self.topbar.set_paused(False))
        self.context.operations_manager.systemStateChanged.connect(lambda state: self.topbar.lbl_status.setText(str(state).replace("_", " ").title()))
        self.context.settings_controller.privacyModeChanged.connect(lambda enabled: self.set_privacy_mode(enabled, persist=False))
        self.context.job_controller.jobsChanged.connect(lambda *_: self.sidebar.set_badge("jobs", self.context.job_repository.count_by_status("RUNNING") + self.context.job_repository.count_by_status("QUEUED") + self.context.job_repository.count_by_status("RECONCILE_REQUIRED")))
        self.context.job_controller.jobsChanged.connect(lambda *_: self._update_statusbar())

        # One entitlement event drives the shell refresh.  The controller also
        # emits feature/usage signals for specialized listeners, but connecting
        # all three here would repaint the entire shell three times per refresh.
        self.context.license_controller.licenseChanged.connect(lambda *_: self._apply_license_ui())
        for owner in (self.context.account_controller,self.context.group_controller,self.context.member_controller,self.context.campaign_controller,self.context.scheduler_controller,self.context.template_controller,self.context.operations_controller):
            signal=getattr(owner,"featureLocked",None)
            if signal:signal.connect(self._show_feature_upgrade)
        for owner in (self.context.account_controller,self.context.group_controller,self.context.template_controller):
            signal=getattr(owner,"planLimitReached",None)
            if signal:signal.connect(self._show_limit_upgrade)

        for signal_owner in [
            self.context.account_controller, self.context.account_pool_controller, self.context.group_controller,
            self.context.member_controller, self.context.campaign_controller,
            self.context.scheduler_controller, self.context.job_controller,
        ]:
            for name in ["accountsChanged", "groupsChanged", "membersChanged", "campaignsChanged", "schedule_changed", "jobsChanged"]:
                signal = getattr(signal_owner, name, None)
                if signal:
                    try:
                        signal.connect(self._on_data_changed)
                    except TypeError:
                        pass

        # Telegram actions can create alerts/log records asynchronously.
        for signal_name in ["accountConnected", "accountDisconnected", "accountAuthorizationRequired", "accountHealthUpdated", "accountOperationFailed"]:
            signal = getattr(self.context.account_controller, signal_name, None)
            if signal:
                signal.connect(lambda *args: self.context.alert_controller.refresh())
    def _install_shortcuts(self):
        for sequence, slot in [
            ("Ctrl+N", self.on_new_shortcut), ("Ctrl+F", self.on_find_shortcut),
            ("Ctrl+R", self.on_refresh_shortcut), ("F5", self.on_refresh_shortcut),
            ("Ctrl+S", self.on_save_shortcut), ("Ctrl+K", self._open_command_palette),
        ]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(slot)

    def navigate(self, key, title=None):
        if key not in self.pages:
            return
        self.stack_main_pages.setCurrentWidget(self.pages[key])
        self.sidebar.set_current(key)
        localized_title, localized_subtitle = self.localization.page(key)
        self.topbar.set_page(localized_title, localized_subtitle)
        self.settings.setValue("window/last_page", key)
        if key == "dashboard":
            self.pages[key].refresh()
        elif key == "operations":
            self.context.operations_controller.refresh()
        elif key == "account_pool":
            self.context.account_pool_controller.refresh()
        elif key in {"source_groups", "target_groups"}:
            self.pages[key].refresh_from_controller()
        elif key == "members":
            self.pages[key].refresh_group_options()
        elif key == "collector":
            self.pages[key].refresh_group_options()
        elif key == "settings":
            self.pages[key].refresh_group_options()
        elif key == "alerts":
            self.context.alert_controller.refresh()
        elif key == "license":
            self.pages[key].refresh()


    def _apply_localization(self) -> None:
        self.sidebar.apply_localization(self.localization)
        from app.widgets.page_header import PageHeaderWidget
        for key, page in self.pages.items():
            title, subtitle = self.localization.page(key)
            header = page.findChild(PageHeaderWidget)
            if header is not None:
                header.lbl_title.setText(title)
                header.set_subtitle(subtitle)
        self.localization.apply_to_widget_tree(self)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _localize_focus_window(self, _old, current) -> None:
        if current is None or self.localization.language == "en":
            return
        try:
            self.localization.apply_to_widget_tree(current.window())
            # Update the theme state with the current theme
            from app.theme_state import set_current_theme
            set_current_theme(str(self.settings.value("ui/theme", "light")))
        except (RuntimeError, AttributeError):
            return


    def _apply_license_ui(self):
        state = self.context.license_service.get_current_license()
        self.topbar.set_license_status(state.plan, str(state.status), state.expires_at)
        for key in ("campaigns", "scheduler", "templates", "analytics", "operations", "members", "settings"):
            page = self.pages.get(key)
            if page and hasattr(page, "apply_license_features"):
                page.apply_license_features(self.context.feature_gate, self.context.license_limit_service)
        if self.pages.get("license"):
            self.pages["license"].refresh()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _show_crash_recovery_dialog(self, report: dict) -> None:
        from app.dialogs.crash_recovery_dialog import CrashRecoveryDialog
        dialog = CrashRecoveryDialog(report, self)
        dialog.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _show_feature_upgrade(self, feature, required):
        required = str(required or self.context.feature_gate.get_required_plan(feature) or "PRO")
        state = self.context.license_service.get_current_license()
        current = PLAN_CONFIG.get(PlanKey(str(state.plan)), {}).get("name") if state.plan in {p.value for p in PlanKey} else "No active license"
        dialog = UpgradePlanDialog(current, str(feature).replace("FEATURE_", "").replace("_", " ").title(), required, parent=self)
        dialog.viewPlansRequested.connect(lambda: self.navigate("license", "License"))
        dialog.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _show_limit_upgrade(self, limit_key, result):
        try:
            key = LimitKey(str(limit_key))
        except ValueError:
            key = LimitKey.MAX_ACCOUNTS
        state = self.context.license_service.get_current_license()
        current_plan = state.plan_key
        required = PlanKey.STARTER
        for plan in PLAN_ORDER:
            cfg = PLAN_CONFIG[plan]
            limit = cfg["limits"][key]
            if (limit is None or int(limit) > int(result.current)) and plan != current_plan:
                required = plan
                break
        label = {
            LimitKey.MAX_ACCOUNTS: "Account Limit Reached",
            LimitKey.MAX_SOURCE_GROUPS: "Source Group Limit Reached",
            LimitKey.MAX_TARGET_GROUPS: "Managed / Target Group Limit Reached",
            LimitKey.MAX_MEMBER_POOL: "Member Pool Plan Limit Reached",
            LimitKey.MAX_TEMPLATES: "Template Limit Reached",
            LimitKey.MAX_DEVICES: "Device Limit Reached"
        }[key]
        warning = f"Current Usage: {result.current:,} / {'Unlimited' if result.limit is None else f'{result.limit:,}'}\n\nExisting data will not be deleted. New additions remain blocked until usage is within plan limits or the license is upgraded."
        current = PLAN_CONFIG[current_plan]["name"] if current_plan in PLAN_CONFIG else "No active license"
        d = UpgradePlanDialog(current, label, required.value, warning, self)
        d.viewPlansRequested.connect(lambda: self.navigate("license", "License"))
        d.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _focus_global_search(self):
        self.topbar.le_global_search.setFocus()
        self.topbar.le_global_search.selectAll()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _open_command_palette(self):
        dialog = CommandPaletteDialog(self)
        dialog.pageSelected.connect(self.navigate)
        dialog.actionSelected.connect(self._run_palette_action)
        dialog.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _run_palette_action(self, action: str):
        if action == "toggle_theme":
            self.on_toggle_theme()
        elif action == "toggle_pause":
            self.topbar._toggle_pause()
        elif action == "create_campaign":
            self.on_create_campaign_clicked()
        elif action == "add_account":
            page = self.pages.get("accounts")
            if page is not None:
                button = page.findChild(QPushButton, "btn_add_account")
                if button is not None:
                    button.click()
        elif action == "add_group":
            page = self.pages.get("groups")
            if page is not None:
                button = page.findChild(QPushButton, "btn_add_group")
                if button is not None:
                    button.click()
        elif action == "run_diagnostics":
            self.context.operations_controller.run_diagnostics()
        elif action == "security_audit":
            self.context.operations_controller.run_security_audit()
        elif action == "backup":
            page = self.pages.get("settings")
            if page is not None:
                self.navigate("settings", "Settings")
                button = page.findChild(QPushButton, "btn_backup_now")
                if button is not None:
                    button.click()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _update_statusbar(self):
        running = self.context.job_repository.count_by_status("RUNNING") if getattr(self.context, "job_repository", None) else 0
        self.statusBar().showMessage(f"● Database Ready     {running} Running Job{'s' if running != 1 else ''}     SP Telegram")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _operations_tick(self):
        # Logical workers are timer/service loops owned by the Qt application,
        # so their heartbeat is emitted from the timer that actually drives them.
        for name in ("Monitor Worker", "Job Worker", "Notification Worker", "Database Maintenance Worker"):
            self.context.worker_registry.heartbeat(name)
        self.context.operations_controller.refresh()
        self.context.alert_controller.refresh()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _account_monitor_tick(self):
        if not self.context.feature_gate.has_feature(FeatureKey.ACCOUNT_MONITORING):
            return
        if self._operations_paused or not bool(self.context.settings_service.get("enable_account_monitor", True)):
            return
        if not self.context.operations_manager.can_start_network_operation():
            return
        self.context.account_controller.run_health_check_all()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _group_monitor_tick(self):
        if not self.context.feature_gate.has_feature(FeatureKey.GROUP_MONITORING):
            return
        if self._operations_paused or not bool(self.context.settings_service.get("enable_group_monitor", False)):
            return
        if not self.context.operations_manager.can_start_network_operation():
            return
        ids = [g.id for g in self.context.group_repository.get_managed() if g.id]
        if ids:
            self.context.group_controller.sync_selected_groups(ids)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _auto_backup_tick(self):
        if not self.context.feature_gate.has_feature(FeatureKey.AUTO_BACKUP):
            return
        if not bool(self.context.settings_service.get("auto_backup", False)):
            return
        frequency = str(self.context.settings_service.get("backup_frequency", "OFF")).upper()
        if frequency not in {"DAILY", "WEEKLY"}:
            return
        latest = self.context.backup_repository.latest()
        interval = 86400 if frequency == "DAILY" else 7 * 86400
        if latest and latest.get("created_at"):
            try:
                from datetime import datetime, timezone
                stamp = datetime.fromisoformat(str(latest["created_at"]).replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - stamp).total_seconds() < interval:
                    return
            except (TypeError, ValueError) as exc:
                self.context.logger.warning("SYSTEM", f"Could not parse last backup timestamp: {exc}", action="BACKUP_TIMESTAMP")
        if self.context.operations_manager.state in {"PAUSED", "MAINTENANCE", "SHUTTING_DOWN"}:
            return
        destination = self.context.settings_service.get("backup_directory", None)
        self.context.operations_controller.run_backup(destination)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _retention_tick(self):
        if self.context.operations_manager.state not in {"READY", "DEGRADED"}:
            return
        self.context.operations_controller.run_database_maintenance()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _auto_lock_tick(self):
        # Do not interrupt a blocking modal/file chooser with the app-lock
        # dialog.  The next timer tick will re-evaluate after the modal closes.
        if QApplication.activeModalWidget() is not None:
            return
        service = self.context.app_lock_service
        if service.should_auto_lock():
            self.lock_application()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _install_activity_filters(self) -> None:
        """Install app-lock activity filters only on QObject-backed widgets."""
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Defensive guard for binding edge cases.  Normal Qt event filtering
        # only supplies QObject instances; never forward a QLayoutItem/
        # QWidgetItem to QObject.eventFilter().
        if not isinstance(watched, QObject):
            return False
        # A watched widget may have been destroyed while still installed as a
        # filter target (e.g. a dialog table closed mid-event).  Accessing its
        # C++ object raises RuntimeError and floods the log with recursive
        # "Error calling Python override" messages — bail out instead.
        try:
            import shiboken6
            if not shiboken6.isValid(watched):
                return False
        except Exception:
            pass

        event_type = event.type()
        if event_type in {QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel}:
            try:
                self.context.app_lock_service.touch()
            except (RuntimeError, AttributeError) as exc:
                self.context.logger.warning(
                    "SYSTEM", f"App-lock activity tracking failed: {exc}", action="APP_LOCK_ACTIVITY"
                )
        elif event_type == QEvent.Type.ChildAdded:
            # Dialog/page controls created after MainWindow construction are
            # filtered only when they are actual QWidget/QObject instances.
            child = getattr(event, "child", lambda: None)()
            if isinstance(child, QWidget):
                child.installEventFilter(self)
                for nested in child.findChildren(QWidget):
                    nested.installEventFilter(self)

        return super().eventFilter(watched, event)

    def lock_application(self):
        service = self.context.app_lock_service
        # App Lock is a Pro+ configuration feature, but if it was already
        # enabled before expiry/downgrade it continues protecting the local UI.
        # Licensing must never weaken an existing security control.
        if not self.context.feature_gate.has_feature(FeatureKey.APP_LOCK) and not service.state.enabled:
            self._show_feature_upgrade(str(FeatureKey.APP_LOCK), str(self.context.feature_gate.get_required_plan(FeatureKey.APP_LOCK) or "PRO"))
            return
        if not service.state.enabled:
            self.toast_requested.emit("Application Lock is disabled. Configure it under Settings → Security first.", "Info")
            return
        if self._lock_dialog_open:
            return
        # Preserve an operator-initiated/global pause. Unlocking must never
        # resume operations that were already paused before the lock screen.
        self._lock_paused_operations = self.context.operations_manager.state != OperationalState.PAUSED
        service.lock()
        self._lock_dialog_open = True
        if self._lock_paused_operations:
            self.context.operations_controller.pause_all()
        dialog = AppLockDialog(service, self)
        dialog.exec()
        self._lock_dialog_open = False
        if not service.state.locked and self._lock_paused_operations:
            self.context.operations_controller.resume_all()
        self._lock_paused_operations = False
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _refresh_telegram_topbar(self):
        accounts = list(self.context.account_controller.accounts())
        if not self.context.account_controller.has_telegram_config():
            self.topbar.set_telegram_status("Configuration Required")
        elif not accounts:
            self.topbar.set_telegram_status("No Accounts")
        elif any(str(getattr(a, "connection_status", "")).upper() == "CONNECTED" for a in accounts):
            self.topbar.set_telegram_status("Ready")
        else:
            self.topbar.set_telegram_status("Offline")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _refresh_table_preferences(self):
        for page in self.pages.values():
            refresh = getattr(page, "refresh_table_preferences", None)
            if refresh:
                try:
                    refresh()
                except Exception as exc:
                    logging.getLogger(__name__).warning("Could not refresh table preferences: %s", exc)
        manager = self._table_preferences
        smooth = bool(manager.global_value("smooth_scrolling", True))
        mode = QAbstractItemView.ScrollMode.ScrollPerPixel if smooth else QAbstractItemView.ScrollMode.ScrollPerItem
        vertical = max(1, min(120, _int_setting(manager, "vertical_scroll_step", 16)))
        horizontal = max(1, min(160, _int_setting(manager, "horizontal_scroll_step", 28)))
        for table in self.findChildren(QTableView):
            table.setVerticalScrollMode(mode)
            table.setHorizontalScrollMode(mode)
            table.verticalScrollBar().setSingleStep(vertical)
            table.horizontalScrollBar().setSingleStep(horizontal)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _auto_fit_all_tables(self):
        fitted = 0
        for page in self.pages.values():
            auto_fit = getattr(page, "auto_fit_columns", None)
            if auto_fit:
                try:
                    auto_fit()
                    fitted += 1
                except Exception as exc:
                    logging.getLogger(__name__).warning("Could not auto-fit table columns: %s", exc)
        self.toast_requested.emit(f"Auto-fitted {fitted} table(s).", "Success")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _refresh_group_dependents(self, *_args):
        refreshers = (
            ("source_groups", "refresh_from_controller"), ("target_groups", "refresh_from_controller"),
            ("members", "refresh_group_options"), ("collector", "refresh_group_options"),
            ("campaigns", "refresh_group_options"), ("scheduler", "refresh_group_options"),
            ("analytics", "refresh_filter_options"), ("settings", "refresh_group_options"),
        )
        for page_key, method_name in refreshers:
            page = self.pages.get(page_key)
            method = getattr(page, method_name, None) if page else None
            if method:
                try:
                    method()
                except Exception as exc:
                    self.context.logger.warning("GROUP", f"Could not refresh {page_key} group options: {exc}", action="GROUP_REFERENCE_REFRESH")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def set_privacy_mode(self, enabled: bool, persist: bool = True):
        self._privacy_mode = bool(enabled)
        # Keep transient dialogs/models in sync with the current privacy state,
        # not only the state written during main-window shutdown.
        self.settings.setValue("ui/privacy_mode", self._privacy_mode)
        if persist:
            self.context.settings_service.save({"privacy_mode": self._privacy_mode})
        for key in ("accounts", "groups", "members", "blacklist"):
            page = self.pages.get(key)
            model = getattr(page, "model", None)
            if page and hasattr(page, "set_privacy_mode"):
                page.set_privacy_mode(self._privacy_mode)
            elif model and hasattr(model, "set_privacy_mode"):
                model.set_privacy_mode(self._privacy_mode)
        ops = self.pages.get("operations")
        if ops:
            ops.btn_privacy_mode.setText("Disable Privacy Mode" if self._privacy_mode else "Privacy Mode")
            ops.btn_privacy_mode.setToolTip(
                "Privacy Mode is masking Telegram IDs, usernames, names and other sensitive fields. Disable it to show full values, subject to the individual Mask settings."
                if self._privacy_mode else
                "Temporarily mask sensitive identity fields across SP Telegram."
            )
        self.toast_requested.emit("Privacy Mode enabled." if self._privacy_mode else "Privacy Mode disabled.", "Info") if persist else None
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def toggle_privacy_mode(self):
        self.set_privacy_mode(not self._privacy_mode)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def open_notification_center(self):
        items = self.context.alert_controller.alerts()
        rows = [vars(item).copy() if hasattr(item, "__dict__") else dict(item) for item in items]
        dialog = NotificationCenterDialog(rows, self)
        dialog.openAlertsRequested.connect(lambda: self.navigate("alerts", "Alerts"))
        dialog.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _telegram_runtime_state(self, status: str):
        self.topbar.set_telegram_status(status)
        if status == "Ready":
            self.context.network_monitor.report_success(telegram=True)
        elif status == "Partial":
            self.context.network_monitor.report_failure("UNKNOWN", telegram=True)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _scheduler_tick(self):
        self.context.worker_registry.heartbeat("Scheduler Worker")
        if not self._operations_paused and self.context.operations_manager.can_start_network_operation():
            self.context.scheduler_controller.process_due()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _startup_group_sync(self):
        groups = [g.id for g in self.context.group_controller.groups() if g.id and g.status != "UNAVAILABLE"]
        if groups:
            self.context.group_controller.sync_selected_groups(groups)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def open_telegram_settings(self):
        self.navigate("settings", "Settings")
        self.pages["settings"].open_tab("Telegram")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def open_sessions_for_account(self, account_id: int):
        self.navigate("sessions", "Sessions")
        self.pages["sessions"].select_account(account_id)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_dashboard_quick_action(self, key):
        self.navigate(key)
        mapping = {
            "accounts": "btn_add_account", "groups": "btn_add_group",
            "campaigns": "btn_create_campaign", "scheduler": "btn_schedule_new_post",
        }
        name = mapping.get(key)
        if name:
            button = self.pages[key].findChild(QPushButton, name)
            if button:
                button.click()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _campaign_dialog_data(self):
        # Service returns managed groups plus the exact verified account mappings.
        targets = self.context.campaign_controller.managed_targets()
        accounts = [a for a in self.context.account_controller.accounts() if a.id and a.is_enabled]
        return targets, accounts
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _schedule_campaign(self, item, data):
        """Persist a schedule for a campaign (explicit Create & Schedule action)."""
        when = data.get("send_at")
        self.context.scheduler_controller.save_schedule({
            "campaign_id": item.id, "schedule_type": data.get("schedule_type"),
            "run_at": when, "next_run_at": when, "repeat_rule": data.get("repeat_rule"),
            "timezone": data.get("timezone") or "UTC",
            "missed_policy": self.context.settings_service.get("missed_schedule_policy", "ASK_ME"),
        }, activate_remote=True)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _save_campaign_dialog(self, dialog, existing_id=None):
        data = dialog.data()
        finish_mode = data.get("finish_mode") or "finish"
        item = (self.context.campaign_controller.update(existing_id, data) if existing_id else self.context.campaign_controller.create(data))
        if not item:
            return None
        if existing_id:
            self.campaign_updated.emit(data)
        else:
            self.campaign_created.emit(data)
        # Explicit final actions from the wizard.
        if finish_mode == "run":
            self.context.campaign_controller.run_campaign(item.id)
        elif finish_mode == "schedule":
            self._schedule_campaign(item, data)
        elif finish_mode == "finish" and data.get("schedule_type") in {"ONCE", "REPEAT"}:
            # "Create Campaign" with a scheduled type: confirm before scheduling.
            when = data.get("send_at")
            if QMessageBox.question(
                self, "Schedule Campaign",
                f"Schedule '{item.name}'?\n\nFirst run: {when or 'Not set'}\nTimezone: {data.get('timezone') or 'UTC'}\nRepeat: {data.get('repeat_rule') or 'Once'}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self._schedule_campaign(item, data)
        return item
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_create_campaign_for_group(self, group_id: int):
        if not self.context.feature_gate.has_feature(FeatureKey.CAMPAIGNS):
            self._show_feature_upgrade(str(FeatureKey.CAMPAIGNS), str(self.context.feature_gate.get_required_plan(FeatureKey.CAMPAIGNS) or "PRO"))
            return
        targets, accounts = self._campaign_dialog_data()
        dialog = CreateCampaignDialog(targets, accounts, self, smart_planner=self.context.campaign_controller.plan_smart_targets, avatar_service=self.context.avatar_service)
        dialog.saveAsTemplateRequested.connect(self.on_save_campaign_as_template)
        dialog.refreshPermissionsRequested.connect(self.on_campaign_refresh_permissions)
        for row, target in enumerate(targets):
            if int(target.get("group_id") or 0) == int(group_id):
                dialog.tbl_campaign_target_selection.selectRow(row)
                break
        if dialog.exec():
            self._save_campaign_dialog(dialog)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_scheduler_campaign_open(self, campaign_id: int):
        item = self.context.campaign_repository.get_by_id(campaign_id)
        if item:
            self.on_campaign_details(item)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_create_campaign_clicked(self):
        if not self.context.feature_gate.has_feature(FeatureKey.CAMPAIGNS):
            self._show_feature_upgrade(str(FeatureKey.CAMPAIGNS), str(self.context.feature_gate.get_required_plan(FeatureKey.CAMPAIGNS) or "PRO"))
            return
        targets, accounts = self._campaign_dialog_data()
        dialog = CreateCampaignDialog(targets, accounts, self, smart_planner=self.context.campaign_controller.plan_smart_targets, avatar_service=self.context.avatar_service)
        dialog.saveAsTemplateRequested.connect(self.on_save_campaign_as_template)
        dialog.refreshPermissionsRequested.connect(self.on_campaign_refresh_permissions)
        if dialog.exec():
            self._save_campaign_dialog(dialog)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_edit_campaign(self, item):
        targets, accounts = self._campaign_dialog_data()
        details = self.context.campaign_controller.details(item.id)
        dialog = CreateCampaignDialog(targets, accounts, self, campaign=item, details=details, smart_planner=self.context.campaign_controller.plan_smart_targets, avatar_service=self.context.avatar_service)
        dialog.saveAsTemplateRequested.connect(self.on_save_campaign_as_template)
        dialog.refreshPermissionsRequested.connect(self.on_campaign_refresh_permissions)
        dialog.setWindowTitle("Edit Campaign")
        if dialog.exec():
            self._save_campaign_dialog(dialog, item.id)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_preview_campaign(self, item):
        details = self.context.campaign_controller.details(item.id)
        if details and details.get("campaign"):
            CampaignPreviewDialog(details, self.context.group_repository.get_by_id, self).exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_campaign_details(self, item):
        details = self.context.campaign_controller.details(item.id)
        if details and details.get("campaign"):
            dialog = CampaignDetailsDialog(details, self)
            dialog.btn_campaign_content_preview.clicked.connect(lambda: self.on_preview_campaign(item))
            dialog.exec()
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_campaign_refresh_permissions(self, targets):
        if not targets:
            self.toast_requested.emit("Select campaign targets before refreshing permissions.", "Info")
            return
        for target in targets:
            self.context.group_controller.refresh_permissions(int(target["group_id"]), int(target["account_id"]))
        self.toast_requested.emit("Permission refresh queued for the selected campaign mappings.", "Info")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_save_campaign_as_template(self, campaign_data):
        dialog = SaveCampaignAsTemplateDialog(campaign_data.get("name", "Campaign"), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dialog.data()
        messages = campaign_data.get("messages", []) if opts["include_content"] else []
        groups = [int(t["group_id"]) for t in campaign_data.get("targets", [])] if opts["include_targets"] else []
        template_data = {
            "name": opts["name"],
            "description": campaign_data.get("description"),
            "template_type": campaign_data.get("campaign_type") or "TEXT",
            "default_parse_mode": (messages[0].get("parse_mode") if messages else "PLAIN") or "PLAIN",
            "default_schedule_type": campaign_data.get("schedule_type") if opts["include_schedule"] else None,
            "default_timezone": campaign_data.get("timezone") if opts["include_schedule"] else None,
        }
        created = self.context.template_controller.create(template_data, messages, groups)
        if created:
            self.toast_requested.emit("Campaign template saved.", "Success")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_use_template(self, details):
        targets, accounts = self._campaign_dialog_data()
        dialog = CreateCampaignDialog(targets, accounts, self, smart_planner=self.context.campaign_controller.plan_smart_targets, avatar_service=self.context.avatar_service)
        dialog.saveAsTemplateRequested.connect(self.on_save_campaign_as_template)
        dialog.refreshPermissionsRequested.connect(self.on_campaign_refresh_permissions)
        template = details.get("template")
        if template:
            dialog.le_campaign_name.setText(f"{template.name} Campaign")
            dialog.cmb_campaign_timezone.setCurrentText(template.default_timezone or "Asia/Phnom_Penh")
        dialog.messages = [dict(m) for m in details.get("messages", [])]
        dialog._refresh_messages()
        if dialog.exec():
            item = self._save_campaign_dialog(dialog)
            if item and template:
                try:
                    self.context.template_repository.mark_used(template.id)
                except Exception as exc:
                    self.context.logger.warning("CAMPAIGN", f"Could not update template last-used timestamp: {exc}", action="TEMPLATE_MARK_USED")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def _on_data_changed(self, *args):
        try:
            self.pages["dashboard"].refresh()
        except Exception as exc:
            self.context.logger.warning("SYSTEM", f"Dashboard refresh after data change failed: {exc}", action="DASHBOARD_REFRESH")
        try:
            self.context.account_pool_controller.refresh()
        except Exception as exc:
            self.context.logger.warning("ACCOUNT", f"Account Pool refresh after data change failed: {exc}", action="ACCOUNT_POOL_REFRESH")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def refresh_all(self):
        self.context.account_controller.refresh()
        self.context.account_pool_controller.refresh()
        self.context.group_controller.refresh()
        self.context.member_controller.refresh()
        self.context.blacklist_controller.refresh()
        self.context.campaign_controller.refresh()
        self.context.scheduler_controller.refresh()
        self.context.template_controller.refresh()
        self.context.job_controller.refresh()
        self.context.log_controller.refresh()
        self.context.alert_controller.refresh()
        self.context.restriction_controller.refresh()
        self.context.operations_controller.refresh()
        self.pages["dashboard"].refresh()
        self.topbar.set_database_connected(True)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_operations_pause_toggled(self, paused):
        if paused:
            self.context.operations_controller.pause_all()
        else:
            self.context.operations_controller.resume_all()
        # A failed resume can intentionally leave the application DEGRADED
        # when reconciliation is required.  Only PAUSED means globally paused.
        self._operations_paused = self.context.operations_manager.state == OperationalState.PAUSED
        self.topbar.set_paused(self._operations_paused)
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_global_search(self, text):
        text = text.strip()
        if not text:
            self.toast_requested.emit("Enter a global search term.", "Info")
            return
        for key in ["accounts", "groups", "members", "campaigns", "logs"]:
            search = getattr(self.pages[key], "search", None)
            if search:
                search.setText(text)
        self.toast_requested.emit(f"Applied '{text}' to searchable database pages.", "Info")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_toggle_theme(self):
        current = str(self.settings.value("ui/theme", "light"))
        self.set_theme("light" if current == "dark" else "dark")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def set_theme(self, theme):
        normalized = normalize_theme(theme)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, normalized)
        self.settings.setValue("ui/theme", normalized)

    def current_key(self):
        widget = self.stack_main_pages.currentWidget()
        return next((key for key, value in self.pages.items() if value is widget), "dashboard")

    def on_new_shortcut(self):
        key = self.current_key()
        mapping = {
            "accounts": "btn_add_account", "groups": "btn_add_group",
            "campaigns": "btn_create_campaign", "scheduler": "btn_schedule_new_post",
        }
        name = mapping.get(key)
        if name:
            button = self.pages[key].findChild(QPushButton, name)
            if button:
                button.click()
        else:
            self.toast_requested.emit("Ctrl+N has no local create action on this page.", "Info")
        # Update the theme state with the current theme
        from app.theme_state import set_current_theme
        set_current_theme(str(self.settings.value("ui/theme", "light")))

    def on_find_shortcut(self):
        search = getattr(self.pages[self.current_key()], "search", None)
        if search:
            search.setFocus(); search.selectAll()
        else:
            self.topbar.le_global_search.setFocus(); self.topbar.le_global_search.selectAll()

    def on_refresh_shortcut(self):
        key = self.current_key()
        buttons = {
            "accounts": "btn_refresh_accounts", "groups": "btn_refresh_groups",
            "members": "btn_refresh_members", "campaigns": "btn_refresh_campaigns",
            "scheduler": "btn_refresh_schedule", "jobs": "btn_refresh_jobs",
            "logs": "btn_refresh_logs", "sessions": "btn_refresh_sessions", "jobs": "btn_refresh_jobs", "restrictions": "btn_refresh_restrictions", "operations": "btn_operations_refresh",
        }
        name = buttons.get(key)
        if name:
            button = self.pages[key].findChild(QPushButton, name)
            if button:
                button.click()
        elif key == "dashboard":
            self.pages[key].refresh()
        elif key == "operations":
            self.context.operations_controller.refresh()
        elif key == "account_pool":
            self.context.account_pool_controller.refresh()

    def on_save_shortcut(self):
        if self.current_key() == "settings":
            self.pages["settings"].save()
        else:
            self.toast_requested.emit("No editable form is active.", "Info")

    def _restore_state(self):
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.sidebar.set_collapsed(str(self.settings.value("window/sidebar_collapsed", "false")).lower() in {"true", "1"})
        theme = str(self.settings.value("ui/theme", "light"))
        self.set_theme(theme)
        key = str(self.settings.value("window/last_page", "dashboard"))
        self.navigate(key if key in self.pages else "dashboard")

    def closeEvent(self, event):
        active = self.context.job_repository.count_by_status("RUNNING") + self.context.job_repository.count_by_status("QUEUED")
        if active:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning); box.setWindowTitle("Active Operations")
            box.setText(f"{active} operations are currently active or queued.")
            box.setInformativeText("Keep the application running for safe completion, or stop accepting new work and exit safely. Ambiguous outgoing work will be recovered as interrupted/reconcile-required on the next startup.")
            keep = box.addButton("Wait for Safe Completion", QMessageBox.ButtonRole.ActionRole)
            stop = box.addButton("Stop Safely and Exit", QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton("Cancel Exit", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() in {keep, cancel}:
                event.ignore(); return
        # QApplication does not exit merely because a transient/child window
        # disappears.  Mark only this confirmed MainWindow close as an
        # intentional shutdown; main.py uses the flag for diagnostics.
        self._shutdown_requested = True
        self.context.operations_manager.begin_shutdown()
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/sidebar_collapsed", self.sidebar.is_collapsed())
        self.settings.setValue("window/last_page", self.current_key())
        self.settings.setValue("ui/privacy_mode", self._privacy_mode)
        for page in self.pages.values():
            if hasattr(page, "save_table_state"):
                page.save_table_state()
        self.settings.sync()
        # Per-widget filters are removed automatically as the QObject tree is
        # destroyed; there is no application-wide event filter to detach.
        app = QApplication.instance()
        if isinstance(app, QApplication):
            try:
                app.focusChanged.disconnect(self._localize_focus_window)
            except (TypeError, RuntimeError):
                pass
        self.context.close()
        super().closeEvent(event)
        if event.isAccepted() and isinstance(app, QApplication):
            QTimer.singleShot(0, app.quit)
