from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.dialogs.about_dialog import AboutDialog
from app.dialogs.restore_backup_dialog import RestoreBackupDialog
from app.widgets.page_header import PageHeaderWidget
from app.widgets.switch import SwitchWidget
from app.widgets.horizontal_tab_bar import HorizontalWestTabBar
from app.utils.table_preferences import GLOBAL_DEFAULTS, TablePreferenceManager


class SettingsPage(QWidget):
    themeRequested = Signal(str)
    tablePreferencesChanged = Signal()
    tableAutoFitRequested = Signal()

    def __init__(self, controller, parent=None, group_controller=None):
        super().__init__(parent)
        self.setObjectName("page_settings")
        self.controller = controller
        self.group_controller = group_controller
        self.ui_settings = QSettings()
        self.table_preference_manager = TablePreferenceManager(self.ui_settings, self)
        self.tab_indices: dict[str, int] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(PageHeaderWidget("Settings", "Configure application behavior, monitoring, security and appearance."))
        # UX-012: settings search — type to jump to the matching tab.
        search_row=QHBoxLayout(); self.le_settings_search=QLineEdit(); self.le_settings_search.setObjectName("le_settings_search"); self.le_settings_search.setPlaceholderText("Search settings…"); self.le_settings_search.setClearButtonEnabled(True); self.lbl_settings_search_hint=QLabel(""); self.lbl_settings_search_hint.setProperty("muted",True); search_row.addWidget(self.le_settings_search,1); search_row.addWidget(self.lbl_settings_search_hint); root.addLayout(search_row)
        self.tab_settings = QTabWidget(); self.tab_settings.setObjectName("tab_settings"); self.tab_settings.setTabBar(HorizontalWestTabBar())
        self.tab_settings.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_settings.setDocumentMode(True)
        root.addWidget(self.tab_settings, 1)

        self._build_general()
        self._build_telegram()
        self._build_accounts()
        self._build_groups()
        self._build_members()
        self._build_campaigns()
        self._build_scheduler()
        self._build_monitoring()
        self._build_performance()
        self._build_backup()
        self._build_security()
        self._build_notifications()
        self._build_appearance()

        actions = QHBoxLayout(); actions.addStretch()
        self.btn_about = QPushButton("About"); self.btn_about.setObjectName("btn_about")
        self.btn_reset_settings = QPushButton("Reset Settings"); self.btn_reset_settings.setObjectName("btn_reset_settings")
        self.btn_save_settings = QPushButton("Save Settings"); self.btn_save_settings.setObjectName("btn_save_settings"); self.btn_save_settings.setProperty("primary", True)
        actions.addWidget(self.btn_about); actions.addWidget(self.btn_reset_settings); actions.addWidget(self.btn_save_settings)
        root.addLayout(actions)

        self.le_settings_search.textChanged.connect(self._filter_settings_tabs)
        self.btn_save_settings.clicked.connect(self.save)
        self.btn_reset_settings.clicked.connect(self.reset)
        self.btn_about.clicked.connect(self._about)
        self.btn_test_api_settings.clicked.connect(self.test_api_settings)
        self.btn_backup_now.clicked.connect(self.backup)
        self.btn_open_backup_folder.clicked.connect(self._open_backup_folder)
        self.btn_restore_backup.clicked.connect(self.restore)
        self.btn_verify_backup.clicked.connect(self.verify_backup)
        self.btn_run_security_audit.clicked.connect(self.run_security_audit)
        self.btn_set_app_lock_password.clicked.connect(self._set_app_lock_password)
        self.btn_clear_app_lock_password.clicked.connect(self._clear_app_lock_password)
        controller.telegramConfigTested.connect(self._config_tested)
        if getattr(controller, "operations_controller", None):
            controller.operations_controller.securityAuditReady.connect(self._security_audit_ready)
            controller.operations_controller.restoreCompleted.connect(lambda _r: controller.databaseRestored.emit())
        self._load()
        self._connect_live_table_preferences()

    def _connect_live_table_preferences(self):
        # Display/privacy preferences apply immediately; Save Settings still persists
        # the rest of application configuration. SwitchWidget exposes toggled.
        live_keys = {
            "show_telegram_id", "show_username", "show_display_name", "show_sources", "show_tags",
            "show_first_seen", "show_last_seen", "show_bot", "show_premium",
            "mask_telegram_ids", "mask_usernames", "mask_display_names", "mask_phone_numbers",
        }
        for key, widget in self._table_pref_widgets().items():
            if key in live_keys and hasattr(widget, "toggled"):
                widget.toggled.connect(lambda checked, k=key: self._apply_live_table_preference(k, checked))

    def _apply_live_table_preference(self, key, value):
        self.table_preference_manager.set_global_value(key, bool(value))
        self.tablePreferencesChanged.emit()

    def _tab(self, name: str):
        widget = QWidget(); form = QFormLayout(widget)
        self.tab_indices[name.lower()] = self.tab_settings.count()
        self.tab_settings.addTab(widget, name)
        return form

    def _filter_settings_tabs(self, text: str):
        query = str(text).strip().lower()
        if not query:
            self.lbl_settings_search_hint.setText("")
            return
        matches = [i for name, i in self.tab_indices.items() if query in name]
        if matches:
            self.tab_settings.setCurrentIndex(matches[0])
            self.lbl_settings_search_hint.setText(f"{len(matches)} match" + ("es" if len(matches) != 1 else ""))
        else:
            self.lbl_settings_search_hint.setText("No matching settings")

    @staticmethod
    def _spin(name: str, minimum: int, maximum: int, value: int):
        w = QSpinBox(); w.setObjectName(name); w.setRange(minimum, maximum); w.setValue(value); return w

    @staticmethod
    def _check(name: str, text: str, checked=False):
        w = SwitchWidget(text); w.setObjectName(name); w.setChecked(checked); return w

    def _build_general(self):
        f = self._tab("General")
        self.cmb_language = QComboBox(); self.cmb_language.setObjectName("cmb_language"); self.cmb_language.addItems(["English", "ខ្មែរ"])
        self.cmb_startup_page = QComboBox(); self.cmb_startup_page.setObjectName("cmb_startup_page"); self.cmb_startup_page.addItems(["Dashboard", "Operations", "Accounts", "Groups", "Campaigns"])
        self.spin_auto_refresh_seconds = self._spin("spin_auto_refresh_seconds", 5, 3600, 30)
        self.le_database_path = QLineEdit(); self.le_database_path.setObjectName("le_database_path"); self.le_database_path.setReadOnly(True)
        self.le_sessions_path = QLineEdit(); self.le_sessions_path.setObjectName("le_sessions_path"); self.le_sessions_path.setReadOnly(True)
        # Compatibility buttons remain present but paths are centrally managed and cannot be moved here.
        self.btn_browse_database = QPushButton("Managed"); self.btn_browse_database.setObjectName("btn_browse_database"); self.btn_browse_database.setEnabled(False)
        self.btn_browse_sessions = QPushButton("Managed"); self.btn_browse_sessions.setObjectName("btn_browse_sessions"); self.btn_browse_sessions.setEnabled(False)
        f.addRow("Language", self.cmb_language); f.addRow("Startup Page", self.cmb_startup_page); f.addRow("Auto Refresh (seconds)", self.spin_auto_refresh_seconds)
        f.addRow("Database", self._line_with_button(self.le_database_path, self.btn_browse_database))
        f.addRow("Telegram Sessions", self._line_with_button(self.le_sessions_path, self.btn_browse_sessions))

    def _build_telegram(self):
        f = self._tab("Telegram")
        self.le_api_id = QLineEdit(); self.le_api_id.setObjectName("le_api_id")
        self.le_api_hash = QLineEdit(); self.le_api_hash.setObjectName("le_api_hash"); self.le_api_hash.setEchoMode(QLineEdit.EchoMode.Password); self.le_api_hash.setPlaceholderText("Stored securely — enter only to replace")
        self.btn_test_api_settings = QPushButton("Test API Settings"); self.btn_test_api_settings.setObjectName("btn_test_api_settings")
        f.addRow("API ID", self.le_api_id); f.addRow("API Hash", self.le_api_hash); f.addRow("", self.btn_test_api_settings)

    def _build_accounts(self):
        f = self._tab("Accounts")
        self.chk_auto_connect_accounts = self._check("chk_auto_connect_accounts", "Automatically connect enabled accounts on startup")
        self.spin_max_account_connections = self._spin("spin_max_account_connections", 1, 20, 3)
        f.addRow("", self.chk_auto_connect_accounts); f.addRow("Maximum simultaneous account connections", self.spin_max_account_connections)

    def _build_groups(self):
        f = self._tab("Groups")
        self.chk_auto_sync_groups = self._check("chk_auto_sync_groups", "Sync group metadata automatically")
        self.spin_group_sync_interval = self._spin("spin_group_sync_interval", 5, 1440, 60)
        self.chk_sync_group_permissions = self._check("chk_sync_group_permissions", "Refresh permissions during sync", True)
        self.spin_max_group_sync = self._spin("spin_max_group_sync", 1, 20, 3)
        f.addRow("", self.chk_auto_sync_groups); f.addRow("Sync interval (minutes)", self.spin_group_sync_interval); f.addRow("", self.chk_sync_group_permissions); f.addRow("Maximum simultaneous group sync operations", self.spin_max_group_sync)

    def _build_members(self):
        f = self._tab("Members")
        self.spin_max_member_sync = self._spin("spin_max_member_sync", 1, 10, 2)
        self.spin_database_batch_size = self._spin("spin_database_batch_size", 50, 5000, 250)
        f.addRow("Maximum simultaneous member syncs", self.spin_max_member_sync)
        f.addRow("Database batch size", self.spin_database_batch_size)

        self.cmb_member_rows_per_page = QComboBox(); self.cmb_member_rows_per_page.setObjectName("cmb_member_rows_per_page"); self.cmb_member_rows_per_page.addItems(["100","250","500"])
        self.cmb_member_row_density = QComboBox(); self.cmb_member_row_density.setObjectName("cmb_member_row_density"); self.cmb_member_row_density.addItems(["Comfortable","Compact"])
        self.chk_member_auto_fit_first_open = self._check("chk_member_auto_fit_first_open", "Auto Fit Columns on First Open", False)
        self.chk_member_auto_fit_on_refresh = self._check("chk_member_auto_fit_on_refresh", "Auto Fit Columns After Each Refresh", False)
        self.chk_member_remember_widths = self._check("chk_member_remember_widths", "Remember Column Widths", True)
        self.chk_member_remember_order = self._check("chk_member_remember_order", "Remember Column Order", True)
        self.chk_member_smooth_scrolling = self._check("chk_member_smooth_scrolling", "Smooth Pixel Scrolling", True)
        self.spin_member_vertical_scroll_step = self._spin("spin_member_vertical_scroll_step", 4, 80, 16)
        self.spin_member_horizontal_scroll_step = self._spin("spin_member_horizontal_scroll_step", 4, 120, 28)
        self.btn_auto_fit_all_tables = QPushButton("Auto Fit All Tables Now"); self.btn_auto_fit_all_tables.setObjectName("btn_auto_fit_all_tables"); self.btn_auto_fit_all_tables.clicked.connect(self.tableAutoFitRequested.emit)
        f.addRow("Rows Per Page", self.cmb_member_rows_per_page); f.addRow("Row Density", self.cmb_member_row_density)
        f.addRow("", self.chk_member_auto_fit_first_open); f.addRow("", self.chk_member_auto_fit_on_refresh)
        f.addRow("", self.chk_member_remember_widths); f.addRow("", self.chk_member_remember_order)
        f.addRow("", self.chk_member_smooth_scrolling); f.addRow("Vertical Scroll Step (pixels)", self.spin_member_vertical_scroll_step); f.addRow("Horizontal Scroll Step (pixels)", self.spin_member_horizontal_scroll_step); f.addRow("", self.btn_auto_fit_all_tables)

        self.cmb_member_default_target = QComboBox(); self.cmb_member_default_target.setObjectName("cmb_member_default_target"); self.cmb_member_default_target.addItem("None", 0)
        self.refresh_group_options()
        self.cmb_member_require_eligibility = QComboBox(); self.cmb_member_require_eligibility.setObjectName("cmb_member_require_eligibility"); self.cmb_member_require_eligibility.addItems(["ELIGIBLE","UNKNOWN","MANUAL_REVIEW"])
        self.cmb_member_require_consent = QComboBox(); self.cmb_member_require_consent.setObjectName("cmb_member_require_consent"); self.cmb_member_require_consent.addItems(["APPROVED","OPTED_IN","UNKNOWN"])
        self.chk_member_default_exclude_blacklist = self._check("chk_member_default_exclude_blacklist", "Exclude Blacklist", True)
        self.chk_member_default_exclude_dnc = self._check("chk_member_default_exclude_dnc", "Exclude Do Not Contact", True)
        self.chk_member_default_exclude_existing = self._check("chk_member_default_exclude_existing", "Exclude Existing Target Members", True)
        self.chk_member_default_exclude_bots = self._check("chk_member_default_exclude_bots", "Exclude Bots", True)
        self.chk_member_remove_orphan_automatically = self._check("chk_member_remove_orphan_automatically", "Remove orphan member automatically when its last source is removed", False)
        f.addRow("Default Target", self.cmb_member_default_target); f.addRow("Require Eligibility", self.cmb_member_require_eligibility); f.addRow("Require Consent", self.cmb_member_require_consent)
        for w in (self.chk_member_default_exclude_blacklist,self.chk_member_default_exclude_dnc,self.chk_member_default_exclude_existing,self.chk_member_default_exclude_bots,self.chk_member_remove_orphan_automatically): f.addRow("", w)
        note = QLabel("Direct invitations, when licensed, always use one explicitly selected authorized account and respect consent, exclusions, target permission and Telegram restrictions. Automatic account rotation is not used."); note.setWordWrap(True); note.setProperty("muted", True); f.addRow(note)

    def _build_campaigns(self):
        f = self._tab("Campaigns")
        self.cmb_default_timezone = QComboBox(); self.cmb_default_timezone.setObjectName("cmb_default_timezone"); self.cmb_default_timezone.setEditable(True); self.cmb_default_timezone.addItems(["Asia/Phnom_Penh", "UTC", "Asia/Bangkok", "Asia/Singapore"])
        self.cmb_default_parse_mode = QComboBox(); self.cmb_default_parse_mode.setObjectName("cmb_default_parse_mode"); self.cmb_default_parse_mode.addItems(["PLAIN", "MARKDOWN", "HTML"])
        self.cmb_default_account_strategy = QComboBox(); self.cmb_default_account_strategy.setObjectName("cmb_default_account_strategy"); self.cmb_default_account_strategy.addItems(["GROUP_PRIMARY", "CUSTOM"])
        self.chk_require_campaign_preflight = self._check("chk_require_campaign_preflight", "Require campaign preflight before publish/schedule", True)
        self.spin_max_campaign_workers = self._spin("spin_max_campaign_workers", 1, 10, 2)
        f.addRow("Default Timezone", self.cmb_default_timezone); f.addRow("Default Parse Mode", self.cmb_default_parse_mode); f.addRow("Default Account Strategy", self.cmb_default_account_strategy); f.addRow("", self.chk_require_campaign_preflight); f.addRow("Maximum campaign workers", self.spin_max_campaign_workers)

    def _build_scheduler(self):
        f = self._tab("Scheduler")
        self.cmb_missed_schedule_policy = QComboBox(); self.cmb_missed_schedule_policy.setObjectName("cmb_missed_schedule_policy"); self.cmb_missed_schedule_policy.addItems(["ASK_ME", "SKIP_MISSED", "RUN_NEXT_VALID"])
        self.chk_monitor_scheduler = self._check("chk_monitor_scheduler", "Monitor scheduler health", True)
        f.addRow("Missed Schedule Policy", self.cmb_missed_schedule_policy); f.addRow("", self.chk_monitor_scheduler)

    def _build_monitoring(self):
        f = self._tab("Monitoring")
        self.chk_enable_account_monitor = self._check("chk_enable_account_monitor", "Enable Account Monitoring", True)
        self.spin_account_monitor_interval = self._spin("spin_account_monitor_interval", 1, 1440, 5)
        self.chk_enable_group_monitor = self._check("chk_enable_group_monitor", "Enable Managed Group Monitoring", False)
        self.spin_group_monitor_interval = self._spin("spin_group_monitor_interval", 5, 1440, 30)
        self.chk_group_monitor_permissions = self._check("chk_group_monitor_permissions", "Refresh permissions during group monitoring", True)
        self.chk_monitor_workers = self._check("chk_monitor_workers", "Monitor worker heartbeats", True)
        self.chk_auto_reconnect_network = self._check("chk_auto_reconnect_network", "Allow safe reconnect after temporary network failure", True)
        self.chk_auto_restart_failed_workers = self._check("chk_auto_restart_failed_workers", "Automatically restart failed technical workers when safe", True)
        self.spin_max_worker_restarts = self._spin("spin_max_worker_restarts", 0, 10, 3)
        self.spin_recovery_backoff_seconds = self._spin("spin_recovery_backoff_seconds", 1, 600, 15)
        warning = QLabel("Telegram FloodWaits, account restrictions, privacy restrictions, login requirements, and group permission failures are never bypassed by recovery."); warning.setWordWrap(True); warning.setProperty("muted", True)
        f.addRow("", self.chk_enable_account_monitor); f.addRow("Account monitor interval (minutes)", self.spin_account_monitor_interval)
        f.addRow("", self.chk_enable_group_monitor); f.addRow("Group monitor interval (minutes)", self.spin_group_monitor_interval); f.addRow("", self.chk_group_monitor_permissions); f.addRow("", self.chk_monitor_workers)
        f.addRow("", self.chk_auto_reconnect_network); f.addRow("", self.chk_auto_restart_failed_workers); f.addRow("Maximum worker restarts / window", self.spin_max_worker_restarts); f.addRow("Recovery backoff (seconds)", self.spin_recovery_backoff_seconds); f.addRow(warning)

    def _build_performance(self):
        f = self._tab("Performance")
        # Re-use the existing connection/group controls by presenting the application-wide concurrency controls here as well.
        self.spin_performance_sample_seconds = self._spin("spin_performance_sample_seconds", 5, 300, 10)
        self.spin_log_retention_days = self._spin("spin_log_retention_days", 1, 3650, 90)
        self.spin_alert_retention_days = self._spin("spin_alert_retention_days", 1, 3650, 90)
        self.spin_job_retention_days = self._spin("spin_job_retention_days", 1, 3650, 180)
        f.addRow("Performance sampling (seconds)", self.spin_performance_sample_seconds)
        f.addRow("Keep detailed logs (days)", self.spin_log_retention_days); f.addRow("Keep resolved alerts (days)", self.spin_alert_retention_days); f.addRow("Keep completed job items (days)", self.spin_job_retention_days)
        f.addRow("Account connections", QLabel("Configured under Accounts")); f.addRow("Group sync", QLabel("Configured under Groups")); f.addRow("Member sync", QLabel("Configured under Members")); f.addRow("Campaign workers", QLabel("Configured under Campaigns")); f.addRow("DB batch size", QLabel("Configured under Members"))

    def _build_backup(self):
        f = self._tab("Backup")
        self.le_backup_directory = QLineEdit(); self.le_backup_directory.setObjectName("le_backup_directory")
        self.le_backup_path = QLineEdit(); self.le_backup_path.setObjectName("le_backup_path"); self.le_backup_path.hide()
        self.btn_browse_backup_directory = QPushButton("Browse"); self.btn_browse_backup_directory.setObjectName("btn_browse_backup_directory"); self.btn_browse_backup_directory.clicked.connect(self._browse_backup_directory)
        self.btn_browse_backup = QPushButton("Browse"); self.btn_browse_backup.setObjectName("btn_browse_backup"); self.btn_browse_backup.hide(); self.btn_browse_backup.clicked.connect(self._browse_backup_directory)
        self.chk_auto_backup = self._check("chk_auto_backup", "Enable automatic backup", False)
        self.cmb_backup_frequency = QComboBox(); self.cmb_backup_frequency.setObjectName("cmb_backup_frequency"); self.cmb_backup_frequency.addItems(["OFF", "DAILY", "WEEKLY"])
        self.spin_backup_retention_count = self._spin("spin_backup_retention_count", 1, 100, 10)
        self.btn_backup_now = QPushButton("Backup Now"); self.btn_backup_now.setObjectName("btn_backup_now")
        self.btn_open_backup_folder = QPushButton("Open Backup Folder"); self.btn_open_backup_folder.setObjectName("btn_open_backup_folder")
        self.btn_restore_backup = QPushButton("Restore Backup"); self.btn_restore_backup.setObjectName("btn_restore_backup")
        self.btn_verify_backup = QPushButton("Verify Backup"); self.btn_verify_backup.setObjectName("btn_verify_backup")
        f.addRow("Backup Location", self._line_with_button(self.le_backup_directory, self.btn_browse_backup_directory)); f.addRow("", self.chk_auto_backup); f.addRow("Frequency", self.cmb_backup_frequency); f.addRow("Keep last", self.spin_backup_retention_count)
        row = QWidget(); h = QHBoxLayout(row); h.setContentsMargins(0,0,0,0)
        for b in (self.btn_backup_now, self.btn_open_backup_folder, self.btn_verify_backup, self.btn_restore_backup): h.addWidget(b)
        f.addRow(row)
        note = QLabel("Normal backups include the SQLite database and sanitized application configuration. Telegram .session authorization files are excluded by default."); note.setWordWrap(True); note.setProperty("muted", True); f.addRow(note)

    def _build_security(self):
        f = self._tab("Security")
        self.chk_enable_app_lock = self._check("chk_enable_app_lock", "Enable Application Lock", False)
        self.spin_app_lock_minutes = self._spin("spin_app_lock_minutes", 1, 240, 10)
        self.btn_set_app_lock_password = QPushButton("Set / Change Lock Password"); self.btn_set_app_lock_password.setObjectName("btn_set_app_lock_password")
        self.btn_clear_app_lock_password = QPushButton("Disable & Remove Lock Credential"); self.btn_clear_app_lock_password.setObjectName("btn_clear_app_lock_password")
        self.chk_privacy_mode = self._check("chk_privacy_mode", "Privacy Mode — mask sensitive UI fields", False)
        self.btn_run_security_audit = QPushButton("Run Security Audit"); self.btn_run_security_audit.setObjectName("btn_run_security_audit")
        self.lbl_security_audit = QLabel("Security audit not run yet."); self.lbl_security_audit.setWordWrap(True); self.lbl_security_audit.setProperty("muted", True)
        f.addRow("", self.chk_enable_app_lock); f.addRow("Lock after inactivity (minutes)", self.spin_app_lock_minutes); f.addRow(self.btn_set_app_lock_password, self.btn_clear_app_lock_password); f.addRow("", self.chk_privacy_mode); f.addRow("", self.btn_run_security_audit); f.addRow("Audit", self.lbl_security_audit)

    def _build_notifications(self):
        f = self._tab("Notifications")
        self.chk_notify_critical_alerts = self._check("chk_notify_critical_alerts", "Notify on Critical Alerts", True)
        self.chk_notify_campaign_failures = self._check("chk_notify_campaign_failures", "Notify on Campaign Failures", True)
        self.chk_notify_login_required = self._check("chk_notify_login_required", "Notify on Login Required", True)
        self.chk_notify_backup_failure = self._check("chk_notify_backup_failure", "Notify on Backup Failure", True)
        self.chk_notify_successful_jobs = self._check("chk_notify_successful_jobs", "Notify on Successful Routine Jobs", False)
        for w in (self.chk_notify_critical_alerts, self.chk_notify_campaign_failures, self.chk_notify_login_required, self.chk_notify_backup_failure, self.chk_notify_successful_jobs): f.addRow("", w)

    def _build_appearance(self):
        f = self._tab("Appearance")
        self.cmb_theme = QComboBox(); self.cmb_theme.setObjectName("cmb_theme"); self.cmb_theme.addItems(["Dark", "Light"])
        self.chk_compact_mode = self._check("chk_compact_mode", "Compact Mode")
        self.cmb_table_density = QComboBox(); self.cmb_table_density.setObjectName("cmb_table_density"); self.cmb_table_density.addItems(["Comfortable", "Compact"])
        f.addRow("Theme", self.cmb_theme); f.addRow("", self.chk_compact_mode); f.addRow("Table Density", self.cmb_table_density)
        heading=QLabel("Table Display"); heading.setProperty("sectionTitle",True); f.addRow(heading)
        self.chk_table_show_telegram_id=self._check("chk_table_show_telegram_id","Show Telegram ID",True)
        self.chk_table_show_username=self._check("chk_table_show_username","Show Username",True)
        self.chk_table_show_display_name=self._check("chk_table_show_display_name","Show Display Name",True)
        self.chk_table_show_sources=self._check("chk_table_show_sources","Show Sources",True)
        self.chk_table_show_tags=self._check("chk_table_show_tags","Show Tags",True)
        self.chk_table_show_first_seen=self._check("chk_table_show_first_seen","Show First Seen",True)
        self.chk_table_show_last_seen=self._check("chk_table_show_last_seen","Show Last Seen",True)
        self.chk_table_show_bot=self._check("chk_table_show_bot","Show Bot Status",False)
        self.chk_table_show_premium=self._check("chk_table_show_premium","Show Premium Status",False)
        for w in (self.chk_table_show_telegram_id,self.chk_table_show_username,self.chk_table_show_display_name,self.chk_table_show_sources,self.chk_table_show_tags,self.chk_table_show_first_seen,self.chk_table_show_last_seen,self.chk_table_show_bot,self.chk_table_show_premium): f.addRow("",w)
        self.chk_mask_telegram_ids=self._check("chk_mask_telegram_ids","Mask Telegram IDs",False)
        self.chk_mask_usernames=self._check("chk_mask_usernames","Mask Usernames",False)
        self.chk_mask_display_names=self._check("chk_mask_display_names","Mask Names",False)
        self.chk_mask_phone_numbers=self._check("chk_mask_phone_numbers","Mask Phone Numbers",True)
        f.addRow(QLabel("Privacy / Masking"))
        for w in (self.chk_mask_telegram_ids,self.chk_mask_usernames,self.chk_mask_display_names,self.chk_mask_phone_numbers): f.addRow("",w)
        self.btn_reset_all_table_layouts=QPushButton("Reset All Table Layouts"); self.btn_reset_all_table_layouts.setObjectName("btn_reset_all_table_layouts"); self.btn_reset_all_table_layouts.clicked.connect(self._reset_all_table_layouts); f.addRow("",self.btn_reset_all_table_layouts)
        self.cmb_theme.currentTextChanged.connect(lambda t: self.themeRequested.emit(t.lower()))

    @staticmethod
    def _line_with_button(line, button):
        host = QWidget(); h = QHBoxLayout(host); h.setContentsMargins(0, 0, 0, 0); h.addWidget(line); h.addWidget(button); return host

    def open_tab(self, name: str):
        idx = self.tab_indices.get(name.lower())
        if idx is not None: self.tab_settings.setCurrentIndex(idx)

    def _load(self):
        s = self.controller.get_all()
        language = str(s.get("language", "English"))
        if language in {"Khmer", "Khmer (UI placeholder)", "km"}: language = "ខ្មែរ"
        self.cmb_language.setCurrentText(language if language in {"English", "ខ្មែរ"} else "English")
        self.cmb_startup_page.setCurrentText(str(s.get("startup_page", "Dashboard")))
        self.spin_auto_refresh_seconds.setValue(int(s.get("auto_refresh_seconds", 30)))
        self.cmb_theme.setCurrentText(str(s.get("theme", "light")).title())
        api_id = self.controller.get_api_id(); self.le_api_id.setText(str(api_id or "")); self.le_api_hash.clear()
        self.le_database_path.setText(self.controller.active_database_path())
        self.le_sessions_path.setText(str(s.get("session_path", self.controller.project_root / "data" / "sessions")))
        self.le_backup_directory.setText(str(s.get("backup_directory", s.get("backup_path", self.controller.project_root / "backups")))); self.le_backup_path.setText(self.le_backup_directory.text())
        mappings = {
            self.chk_auto_connect_accounts: ("auto_connect_accounts", False), self.spin_max_account_connections: ("max_account_connections", 3),
            self.chk_auto_sync_groups: ("auto_sync_groups", False), self.spin_group_sync_interval: ("group_sync_interval", 60), self.chk_sync_group_permissions: ("sync_group_permissions", True), self.spin_max_group_sync: ("max_group_sync", 3),
            self.spin_max_member_sync: ("max_member_sync", 2), self.spin_database_batch_size: ("database_batch_size", 250),
            self.chk_require_campaign_preflight: ("require_campaign_preflight", True), self.spin_max_campaign_workers: ("max_campaign_workers", 2),
            self.chk_monitor_scheduler: ("monitor_scheduler", True), self.chk_enable_account_monitor: ("enable_account_monitor", True), self.spin_account_monitor_interval: ("account_monitor_interval", 5),
            self.chk_enable_group_monitor: ("enable_group_monitor", False), self.spin_group_monitor_interval: ("group_monitor_interval", 30), self.chk_group_monitor_permissions: ("group_monitor_permissions", True), self.chk_monitor_workers: ("monitor_workers", True),
            self.chk_auto_reconnect_network: ("auto_reconnect_network", True), self.chk_auto_restart_failed_workers: ("auto_restart_failed_workers", True), self.spin_max_worker_restarts: ("max_worker_restarts", 3), self.spin_recovery_backoff_seconds: ("recovery_backoff_seconds", 15),
            self.spin_performance_sample_seconds: ("performance_sample_seconds", 10), self.spin_log_retention_days: ("log_retention_days", 90), self.spin_alert_retention_days: ("alert_retention_days", 90), self.spin_job_retention_days: ("job_retention_days", 180),
            self.chk_auto_backup: ("auto_backup", False), self.spin_backup_retention_count: ("backup_retention_count", 10), self.chk_enable_app_lock: ("enable_app_lock", False), self.spin_app_lock_minutes: ("app_lock_minutes", 10), self.chk_privacy_mode: ("privacy_mode", False),
            self.chk_notify_critical_alerts: ("notify_critical_alerts", True), self.chk_notify_campaign_failures: ("notify_campaign_failures", True), self.chk_notify_login_required: ("notify_login_required", True), self.chk_notify_backup_failure: ("notify_backup_failure", True), self.chk_notify_successful_jobs: ("notify_successful_jobs", False),
        }
        for widget, (key, default) in mappings.items():
            value = s.get(key, default)
            if isinstance(widget, QCheckBox): widget.setChecked(bool(value))
            else: widget.setValue(int(value))
        self.cmb_default_timezone.setCurrentText(str(s.get("default_timezone", "Asia/Phnom_Penh")))
        self.cmb_default_parse_mode.setCurrentText(str(s.get("default_parse_mode", "PLAIN")))
        self.cmb_default_account_strategy.setCurrentText(str(s.get("default_account_strategy", "GROUP_PRIMARY")))
        self.cmb_missed_schedule_policy.setCurrentText(str(s.get("missed_schedule_policy", "ASK_ME")))
        self.cmb_backup_frequency.setCurrentText(str(s.get("backup_frequency", "OFF")))
        self._load_table_preferences()
        if self.chk_enable_app_lock.isChecked() and not self.controller.has_app_lock_password():
            self.chk_enable_app_lock.setChecked(False)
            self.lbl_security_audit.setText("Application Lock was configured but no secure verifier is available; it remains disabled.")

    def _values(self):
        return {
            "language": self.cmb_language.currentText(), "startup_page": self.cmb_startup_page.currentText(), "auto_refresh_seconds": self.spin_auto_refresh_seconds.value(), "theme": self.cmb_theme.currentText().lower(),
            "auto_connect_accounts": self.chk_auto_connect_accounts.isChecked(), "max_account_connections": self.spin_max_account_connections.value(),
            "auto_sync_groups": self.chk_auto_sync_groups.isChecked(), "group_sync_interval": self.spin_group_sync_interval.value(), "sync_group_permissions": self.chk_sync_group_permissions.isChecked(), "max_group_sync": self.spin_max_group_sync.value(),
            "max_member_sync": self.spin_max_member_sync.value(), "database_batch_size": self.spin_database_batch_size.value(),
            "default_timezone": self.cmb_default_timezone.currentText(), "default_parse_mode": self.cmb_default_parse_mode.currentText(), "default_account_strategy": self.cmb_default_account_strategy.currentText(), "missed_schedule_policy": self.cmb_missed_schedule_policy.currentText(), "require_campaign_preflight": self.chk_require_campaign_preflight.isChecked(), "max_campaign_workers": self.spin_max_campaign_workers.value(),
            "enable_account_monitor": self.chk_enable_account_monitor.isChecked(), "account_monitor_interval": self.spin_account_monitor_interval.value(), "enable_group_monitor": self.chk_enable_group_monitor.isChecked(), "group_monitor_interval": self.spin_group_monitor_interval.value(), "group_monitor_permissions": self.chk_group_monitor_permissions.isChecked(), "monitor_scheduler": self.chk_monitor_scheduler.isChecked(), "monitor_workers": self.chk_monitor_workers.isChecked(),
            "auto_reconnect_network": self.chk_auto_reconnect_network.isChecked(), "auto_restart_failed_workers": self.chk_auto_restart_failed_workers.isChecked(), "max_worker_restarts": self.spin_max_worker_restarts.value(), "recovery_backoff_seconds": self.spin_recovery_backoff_seconds.value(),
            "performance_sample_seconds": self.spin_performance_sample_seconds.value(), "log_retention_days": self.spin_log_retention_days.value(), "alert_retention_days": self.spin_alert_retention_days.value(), "job_retention_days": self.spin_job_retention_days.value(),
            "auto_backup": self.chk_auto_backup.isChecked(), "backup_frequency": self.cmb_backup_frequency.currentText(), "backup_retention_count": self.spin_backup_retention_count.value(), "backup_directory": self.le_backup_directory.text().strip(),
            "enable_app_lock": self.chk_enable_app_lock.isChecked(), "app_lock_minutes": self.spin_app_lock_minutes.value(), "privacy_mode": self.chk_privacy_mode.isChecked(),
            "notify_critical_alerts": self.chk_notify_critical_alerts.isChecked(), "notify_campaign_failures": self.chk_notify_campaign_failures.isChecked(), "notify_login_required": self.chk_notify_login_required.isChecked(), "notify_backup_failure": self.chk_notify_backup_failure.isChecked(), "notify_successful_jobs": self.chk_notify_successful_jobs.isChecked(),
            "session_path": self.le_sessions_path.text(), "database_path": self.le_database_path.text(), "backup_path": self.le_backup_directory.text().strip(),
        }

    def save(self):
        try:
            previous_language = str(self.controller.get("language", "English"))
            api_id_text = self.le_api_id.text().strip(); api_hash = self.le_api_hash.text().strip()
            if api_id_text or api_hash:
                if not api_id_text.isdigit(): raise ValueError("Telegram API ID must be numeric.")
                if not self.controller.save_telegram_credentials(int(api_id_text), api_hash): return
            if self.chk_enable_app_lock.isChecked() and not self.controller.has_app_lock_password():
                QMessageBox.warning(self, "Application Lock", "Set an Application Lock password before enabling auto-lock.")
                self.open_tab("Security"); return
            self._save_table_preferences()
            if self.controller.save(self._values()):
                self.le_api_hash.clear()
                self.tablePreferencesChanged.emit()
                selected_language = self.cmb_language.currentText()
                previous_normalized = "ខ្មែរ" if previous_language in {"Khmer", "Khmer (UI placeholder)", "km", "ខ្មែរ"} else "English"
                if selected_language != previous_normalized:
                    QMessageBox.information(self, "Language", "Language preference saved. Restart SP Telegram to apply the language to all pages and dialogs.")
        except ValueError as exc:
            QMessageBox.warning(self, "Settings", str(exc))

    def _table_pref_widgets(self):
        return {
            "show_telegram_id": self.chk_table_show_telegram_id, "show_username": self.chk_table_show_username, "show_display_name": self.chk_table_show_display_name,
            "show_sources": self.chk_table_show_sources, "show_tags": self.chk_table_show_tags, "show_first_seen": self.chk_table_show_first_seen, "show_last_seen": self.chk_table_show_last_seen,
            "show_bot": self.chk_table_show_bot, "show_premium": self.chk_table_show_premium, "mask_telegram_ids": self.chk_mask_telegram_ids, "mask_usernames": self.chk_mask_usernames, "mask_display_names": self.chk_mask_display_names, "mask_phone_numbers": self.chk_mask_phone_numbers,
            "auto_fit_first_open": self.chk_member_auto_fit_first_open, "auto_fit_on_refresh": self.chk_member_auto_fit_on_refresh, "remember_column_widths": self.chk_member_remember_widths, "remember_column_order": self.chk_member_remember_order, "smooth_scrolling": self.chk_member_smooth_scrolling,
            "exclude_blacklist": self.chk_member_default_exclude_blacklist, "exclude_do_not_contact": self.chk_member_default_exclude_dnc, "exclude_existing": self.chk_member_default_exclude_existing, "exclude_bots": self.chk_member_default_exclude_bots,
            "remove_orphan_automatically": self.chk_member_remove_orphan_automatically,
        }

    def _load_table_preferences(self):
        p=self.table_preference_manager
        for key,widget in self._table_pref_widgets().items(): widget.setChecked(bool(p.global_value(key,GLOBAL_DEFAULTS.get(key,False))))
        rows=int(p.global_value("rows_per_page",100)); idx=self.cmb_member_rows_per_page.findText(str(rows)); self.cmb_member_rows_per_page.setCurrentIndex(max(0,idx))
        density=str(p.global_value("row_density","Comfortable")); self.cmb_member_row_density.setCurrentText(density); self.cmb_table_density.setCurrentText(density)
        self.spin_member_vertical_scroll_step.setValue(int(p.global_value("vertical_scroll_step",16)))
        self.spin_member_horizontal_scroll_step.setValue(int(p.global_value("horizontal_scroll_step",28)))
        target_id=int(p.global_value("default_target_id",0) or 0); idx=self.cmb_member_default_target.findData(target_id); self.cmb_member_default_target.setCurrentIndex(max(0,idx))
        self.cmb_member_require_eligibility.setCurrentText(str(p.global_value("require_eligibility","ELIGIBLE")))
        self.cmb_member_require_consent.setCurrentText(str(p.global_value("require_consent","APPROVED")))

    def _save_table_preferences(self):
        p=self.table_preference_manager
        for key,widget in self._table_pref_widgets().items(): p.set_global_value(key,widget.isChecked())
        p.set_global_value("rows_per_page",int(self.cmb_member_rows_per_page.currentText()))
        p.set_global_value("row_density",self.cmb_member_row_density.currentText())
        p.set_global_value("vertical_scroll_step",self.spin_member_vertical_scroll_step.value())
        p.set_global_value("horizontal_scroll_step",self.spin_member_horizontal_scroll_step.value())
        p.set_global_value("default_target_id",int(self.cmb_member_default_target.currentData() or 0))
        p.set_global_value("require_eligibility",self.cmb_member_require_eligibility.currentText())
        p.set_global_value("require_consent",self.cmb_member_require_consent.currentText())

    def refresh_group_options(self):
        if not hasattr(self,"cmb_member_default_target"):
            return
        current=int(self.cmb_member_default_target.currentData() or 0)
        groups=[]
        try:
            groups=list(self.group_controller.service.get_targets()) if self.group_controller else []
        except Exception:
            groups=[]
        self.cmb_member_default_target.blockSignals(True);self.cmb_member_default_target.clear();self.cmb_member_default_target.addItem("None",0)
        for group in groups:
            username=f"  •  @{group.username}" if getattr(group,"username",None) else ""
            self.cmb_member_default_target.addItem(f"{group.title}{username}",int(group.id))
        index=self.cmb_member_default_target.findData(current);self.cmb_member_default_target.setCurrentIndex(index if index>=0 else 0);self.cmb_member_default_target.blockSignals(False)

    def _reset_all_table_layouts(self):
        if QMessageBox.question(self,"Reset Table Layouts","Reset saved visibility, widths and order for all tables?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.table_preference_manager.reset_all_tables(); self.tablePreferencesChanged.emit()

    def reset(self):
        if QMessageBox.question(self, "Reset Settings", "Reset application/business settings? UI state and secure Telegram credentials are not deleted.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.controller.reset(); self._load()

    def test_api_settings(self):
        api_id = self.le_api_id.text().strip(); api_hash = self.le_api_hash.text().strip() or None
        if not api_id.isdigit(): QMessageBox.warning(self, "Telegram", "API ID must be numeric."); return
        self.btn_test_api_settings.setEnabled(False); self.controller.test_api_settings(int(api_id), api_hash)

    def _config_tested(self, ok: bool, message: str):
        self.btn_test_api_settings.setEnabled(True)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Telegram", message)

    def _browse_backup_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Backup Location", self.le_backup_directory.text())
        if folder: self.le_backup_directory.setText(folder)

    def backup(self):
        ops = getattr(self.controller, "operations_controller", None)
        if ops:
            destination = self.le_backup_directory.text().strip() or None
            ops.run_backup(destination)
        else:
            folder = self.le_backup_directory.text().strip() or str(self.controller.project_root / "backups")
            self.controller.backup(folder)

    def restore(self):
        ops = getattr(self.controller, "operations_controller", None)
        if not ops:
            QMessageBox.warning(self, "Restore Backup", "Restore service is currently unavailable."); return
        dialog = RestoreBackupDialog(ops, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            ops.restore_backup(dialog.backup_folder)

    def verify_backup(self):
        ops = getattr(self.controller, "operations_controller", None)
        if not ops: return
        folder = QFileDialog.getExistingDirectory(self, "Select Backup to Verify", self.le_backup_directory.text())
        if folder: ops.verify_backup(folder)

    def _open_backup_folder(self):
        folder = Path(self.le_backup_directory.text().strip() or self.controller.project_root / "backups")
        folder.mkdir(parents=True, exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def run_security_audit(self):
        ops = getattr(self.controller, "operations_controller", None)
        if ops: self.lbl_security_audit.setText("Running security audit…"); ops.run_security_audit()

    def _security_audit_ready(self, result):
        self.lbl_security_audit.setText(f"Passed {result.get('passed', 0)} • Warnings {result.get('warnings', 0)} • Critical {result.get('critical', 0)}")

    def _set_app_lock_password(self):
        password, ok = QInputDialog.getText(self, "Application Lock", "New local lock password (minimum 6 characters):", QLineEdit.EchoMode.Password)
        if not ok or not password: return
        confirm, ok2 = QInputDialog.getText(self, "Application Lock", "Confirm password:", QLineEdit.EchoMode.Password)
        if not ok2 or password != confirm:
            QMessageBox.warning(self, "Application Lock", "Passwords do not match."); return
        if self.controller.set_app_lock_password(password): self.chk_enable_app_lock.setChecked(True)

    def _clear_app_lock_password(self):
        if QMessageBox.question(self, "Disable Application Lock", "Remove the local lock verifier from secure OS storage?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if self.controller.clear_app_lock_password(): self.chk_enable_app_lock.setChecked(False)

    def _about(self):
        schema = getattr(getattr(self.controller, "service", None), "database", None)
        version = schema.get_schema_version() if schema else "?"
        AboutDialog(version, self).exec()
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        auto_backup=feature_gate.has_feature(FeatureKey.AUTO_BACKUP)
        app_lock=feature_gate.has_feature(FeatureKey.APP_LOCK)
        security=feature_gate.has_feature(FeatureKey.SECURITY_AUDIT)
        account_mon=feature_gate.has_feature(FeatureKey.ACCOUNT_MONITORING)
        group_mon=feature_gate.has_feature(FeatureKey.GROUP_MONITORING)
        for w in (self.chk_auto_backup,self.cmb_backup_frequency,self.spin_backup_retention_count):
            w.setEnabled(auto_backup);w.setToolTip("Automatic Backup requires SP Telegram Ultimate. Manual Backup and Restore remain available." if not auto_backup else "")
        for w in (self.chk_enable_app_lock,self.spin_app_lock_minutes,self.btn_set_app_lock_password,self.btn_clear_app_lock_password):
            w.setEnabled(app_lock);w.setToolTip("Application Lock requires SP Telegram Pro or SP Telegram Ultimate." if not app_lock else "")
        self.btn_run_security_audit.setEnabled(security);self.btn_run_security_audit.setToolTip("Security Audit requires SP Telegram Ultimate." if not security else "")
        for w in (self.chk_enable_account_monitor,self.spin_account_monitor_interval):w.setEnabled(account_mon)
        for w in (self.chk_enable_group_monitor,self.spin_group_monitor_interval,self.chk_group_monitor_permissions):w.setEnabled(group_mon)
        # Never gate manual backup/restore or privacy mode.
        self.btn_backup_now.setEnabled(True);self.btn_restore_backup.setEnabled(True);self.chk_privacy_mode.setEnabled(True)
        return True
