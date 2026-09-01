from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.icons import IconManager
from app.widgets.icon_button import IconButton


class TopBar(QFrame):
    pauseToggled = Signal(bool)
    searchRequested = Signal(str)
    notificationsRequested = Signal()
    themeRequested = Signal()
    licenseRequested = Signal()

    COMPACT_WIDTH = 1040
    FULL_SEARCH_PLACEHOLDER = "Search accounts, groups, members, campaigns…"

    PAGE_SUBTITLES = {
        "Dashboard": "Overview of accounts, groups, members, campaigns and system health.",
        "Operations": "Monitor runtime health, workers, queues, recovery and maintenance.",
        "Accounts": "Manage authorized Telegram accounts and local operational state.",
        "Health Center": "Review account connectivity, authorization and local health checks.",
        "Restrictions": "Track known restrictions and required operator actions.",
        "Sessions": "Review authorized Telegram sessions for connected accounts.",
        "All Groups": "Manage saved Telegram groups, mappings and permissions.",
        "Source Groups": "Authorized source groups available to member synchronization.",
        "Target Groups": "Managed target groups and known membership state.",
        "Member Pool": "Manage member records, eligibility, tags and exclusions.",
        "Collector": "Synchronize accessible members from authorized source groups.",
        "Blacklist": "Manage global, target-specific and Do Not Contact exclusions.",
        "Campaigns": "Create and manage authorized managed-group campaigns.",
        "Scheduler": "Manage local and Telegram-native scheduled group posts.",
        "Templates": "Reusable campaign content and schedule defaults.",
        "Jobs": "Track persistent operational jobs and recovery state.",
        "Analytics": "Review local operational and campaign metrics.",
        "Alerts": "Review incidents, warnings and operator-action items.",
        "Logs": "Monitor application, Telegram, error and audit activity.",
        "License": "Manage your SP Telegram subscription and activated devices.",
        "Settings": "Configure application behavior, monitoring, security and appearance.",
    }

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("topbar"); self._paused = False; self._compact = False
        self._network_status = "Unknown"; self._telegram_status = "Configuration Required"; self._database_connected = True
        layout = QHBoxLayout(self); layout.setContentsMargins(20, 9, 18, 9); layout.setSpacing(12)
        title_host=QWidget(); title_layout=QVBoxLayout(title_host); title_layout.setContentsMargins(0,0,0,0); title_layout.setSpacing(0)
        self._title_host = title_host
        self.lbl_page_title = QLabel("Dashboard"); self.lbl_page_title.setObjectName("lbl_page_title")
        self.lbl_page_subtitle = QLabel(self.PAGE_SUBTITLES["Dashboard"]); self.lbl_page_subtitle.setObjectName("lbl_page_subtitle")
        title_layout.addWidget(self.lbl_page_title); title_layout.addWidget(self.lbl_page_subtitle); layout.addWidget(title_host)
        layout.addStretch(1)

        search_frame=QFrame(); search_frame.setObjectName("global_search_frame"); self._search_frame = search_frame; search_layout=QHBoxLayout(search_frame); search_layout.setContentsMargins(9,0,7,0); search_layout.setSpacing(6)
        search_icon=QLabel(); search_icon.setPixmap(IconManager.get("search").pixmap(16,16)); search_layout.addWidget(search_icon)
        self.le_global_search = QLineEdit(); self.le_global_search.setObjectName("le_global_search"); self.le_global_search.setPlaceholderText(self.FULL_SEARCH_PLACEHOLDER); self.le_global_search.setMinimumWidth(240); self.le_global_search.returnPressed.connect(lambda:self.searchRequested.emit(self.le_global_search.text()))
        self.lbl_search_shortcut=QLabel("Ctrl K"); self.lbl_search_shortcut.setObjectName("lbl_search_shortcut")
        search_layout.addWidget(self.le_global_search,1); search_layout.addWidget(self.lbl_search_shortcut); layout.addWidget(search_frame,2)
        self.btn_global_search = QPushButton("Search", self); self.btn_global_search.setObjectName("btn_global_search"); self.btn_global_search.hide(); self.btn_global_search.clicked.connect(lambda:self.searchRequested.emit(self.le_global_search.text()))

        self.lbl_internet_status = QLabel("NET  ●"); self.lbl_internet_status.setObjectName("lbl_internet_status"); self.lbl_internet_status.setProperty("statusChip", True)
        self.lbl_telegram_global_status = QLabel("TG  ●"); self.lbl_telegram_global_status.setObjectName("lbl_telegram_global_status"); self.lbl_telegram_global_status.setProperty("statusChip", True); self.lbl_connection=self.lbl_telegram_global_status
        self.lbl_database = QLabel("DB  ●"); self.lbl_database.setObjectName("lbl_database_status"); self.lbl_database.setProperty("statusChip", True)
        for chip in (self.lbl_internet_status,self.lbl_telegram_global_status,self.lbl_database): layout.addWidget(chip)

        self.btn_license_status = QPushButton("License"); self.btn_license_status.setObjectName("btn_license_status"); self.btn_license_status.setToolTip("License\nNo active license"); self.btn_license_status.clicked.connect(self.licenseRequested); layout.addWidget(self.btn_license_status)

        self.btn_notifications = IconButton("notification","Notifications",self); self.btn_notifications.setObjectName("btn_notifications"); self.btn_notifications.clicked.connect(self.notificationsRequested)
        self.btn_toggle_theme = IconButton("theme","Toggle theme",self); self.btn_toggle_theme.setObjectName("btn_toggle_theme"); self.btn_toggle_theme.clicked.connect(self.themeRequested)
        self.btn_emergency_pause = QPushButton("●  Running"); self.btn_emergency_pause.setObjectName("btn_emergency_pause"); self.btn_emergency_pause.setToolTip("Pause outgoing operations"); self.btn_emergency_pause.clicked.connect(self._toggle_pause)
        layout.addWidget(self.btn_notifications); layout.addWidget(self.btn_toggle_theme); layout.addWidget(self.btn_emergency_pause)
        self.lbl_status = QLabel("Ready"); self.lbl_status.setProperty("muted", True); self.lbl_status.hide()
        self.set_network_status("Unknown"); self.set_telegram_status("Configuration Required"); self.set_database_connected(True)

    def set_page(self, title: str, subtitle: str | None = None):
        self.lbl_page_title.setText(title); self.lbl_page_subtitle.setText(subtitle if subtitle is not None else self.PAGE_SUBTITLES.get(title,"")); self.lbl_page_subtitle.setVisible(not self._compact and bool(self.lbl_page_subtitle.text()))

    def resizeEvent(self, event):  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self.set_compact(event.size().width() < self.COMPACT_WIDTH)

    def set_compact(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        self.lbl_page_subtitle.setVisible(not compact and bool(self.lbl_page_subtitle.text()))
        self.lbl_search_shortcut.setVisible(not compact)
        self.le_global_search.setMinimumWidth(160 if compact else 240)
        self.le_global_search.setPlaceholderText("Search…" if compact else self.FULL_SEARCH_PLACEHOLDER)
        self._render_status_text()

    def _render_status_text(self) -> None:
        network = self._network_status
        telegram = self._telegram_status
        database = "Connected" if self._database_connected else "Error"
        self.lbl_internet_status.setText("NET  ●" if self._compact else f"NET  ●  {network}")
        self.lbl_telegram_global_status.setText("TG  ●" if self._compact else f"TG  ●  {telegram}")
        self.lbl_database.setText("DB  ●" if self._compact else f"DB  ●  {database}")

    @staticmethod
    def _chip_state(widget, state: str, tooltip: str):
        widget.setProperty("state", state); widget.setToolTip(tooltip); widget.style().unpolish(widget); widget.style().polish(widget)

    def set_database_connected(self, connected: bool):
        self._database_connected = bool(connected)
        self._render_status_text(); self._chip_state(self.lbl_database,"ok" if connected else "error", "Database\nConnected" if connected else "Database\nError")

    def set_network_status(self, status: str):
        normalized=str(status or "Unknown").title(); state={"Online":"ok","Offline":"error","Partial":"warning"}.get(normalized,"muted")
        self._network_status = normalized; self._render_status_text(); self._chip_state(self.lbl_internet_status,state,f"Internet\n{normalized}")

    def set_telegram_status(self, status: str):
        normalized = str(status or "Unknown")
        state={"Ready":"ok","Connecting":"warning","Partial":"warning","Offline":"muted","No Accounts":"muted","Configuration Required":"warning"}.get(normalized,"muted")
        self._telegram_status = normalized; self._render_status_text(); self._chip_state(self.lbl_telegram_global_status,state,f"Telegram\n{normalized}")


    def set_license_status(self, plan: str | None, status: str, expires_at: str | None = None):
        plan_text=str(plan or "LICENSE").upper(); status_text=str(status or "UNLICENSED").replace("_"," ").title(); self.btn_license_status.setText(plan_text if plan_text in {"STARTER","PRO","ULTIMATE"} else "LICENSE")
        state="ok" if str(status) in {"ACTIVE","TRIAL"} else "warning" if str(status) in {"OFFLINE_GRACE","DEVICE_LIMIT","VALIDATION_REQUIRED"} else "error" if str(status) in {"EXPIRED","SUSPENDED","INVALID"} else "muted"
        display={"STARTER":"SP Telegram Starter","PRO":"SP Telegram Pro","ULTIMATE":"SP Telegram Ultimate"}.get(plan_text,"SP Telegram License")
        detail=f"{display}\n{status_text}" + (f"\nActive until {expires_at}" if expires_at and str(status) in {"ACTIVE","TRIAL","OFFLINE_GRACE"} else "")
        self.btn_license_status.setProperty("state",state); self.btn_license_status.setToolTip(detail); self.btn_license_status.style().unpolish(self.btn_license_status); self.btn_license_status.style().polish(self.btn_license_status)

    def set_notification_count(self, count: int):
        count=max(0,int(count or 0)); self.btn_notifications.setText(str(count) if count else ""); self.btn_notifications.setToolTip(f"Notifications — {count} open" if count else "Notifications")

    def set_paused(self, paused: bool, *, emit=False):
        self._paused=bool(paused); self.btn_emergency_pause.setText("●  Paused" if self._paused else "●  Running"); self.btn_emergency_pause.setProperty("paused",self._paused); self.btn_emergency_pause.setToolTip("Resume operations" if self._paused else "Pause outgoing operations")
        self.btn_emergency_pause.style().unpolish(self.btn_emergency_pause); self.btn_emergency_pause.style().polish(self.btn_emergency_pause)
        self.lbl_status.setText("Operations paused" if self._paused else "Ready")
        if emit:self.pauseToggled.emit(self._paused)

    def _toggle_pause(self): self.set_paused(not self._paused,emit=True)
