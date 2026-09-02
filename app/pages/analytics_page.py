from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QGridLayout,
    QHBoxLayout, QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)
from app.widgets.calendar_utils import configure_calendar_popup
from app.widgets.charts import BarChartWidget, DonutChartWidget, TrendChartWidget
from app.widgets.page_header import PageHeaderWidget
from app.widgets.locked_feature import LockedFeatureWidget


class AnalyticsPage(QWidget):
    licenseUpgradeRequested = Signal(str)
    """Local analytics backed by real database metrics and painted charts."""

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.setObjectName("page_analytics")
        root = QVBoxLayout(self)
        self.root_layout = root
        self._license_lock = None
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(PageHeaderWidget("Analytics", "Local account, group, member, campaign and job performance metrics."))

        self.filter_host = QWidget()
        self.filter_host.setObjectName("filter_bar")
        self.filter_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        filters = QHBoxLayout(self.filter_host)
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setSpacing(8)
        self.cmb_analytics_period = QComboBox()
        self.cmb_analytics_period.setObjectName("cmb_analytics_period")
        self.cmb_analytics_period.addItems(["7 days", "30 days", "90 days", "Custom"])
        self.date_analytics_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_analytics_from.setObjectName("date_analytics_from")
        configure_calendar_popup(self.date_analytics_from)
        self.date_analytics_to = QDateEdit(QDate.currentDate())
        self.date_analytics_to.setObjectName("date_analytics_to")
        configure_calendar_popup(self.date_analytics_to)
        self.cmb_analytics_campaign = QComboBox(); self.cmb_analytics_campaign.setObjectName("cmb_analytics_campaign")
        self.cmb_analytics_group = QComboBox(); self.cmb_analytics_group.setObjectName("cmb_analytics_group")
        self.cmb_analytics_account = QComboBox(); self.cmb_analytics_account.setObjectName("cmb_analytics_account")
        self.btn_refresh_analytics = QPushButton("Refresh"); self.btn_refresh_analytics.setObjectName("btn_refresh_analytics")
        self.btn_export_analytics = QPushButton("Export"); self.btn_export_analytics.setObjectName("btn_export_analytics")
        for w in [self.cmb_analytics_period, self.date_analytics_from, self.date_analytics_to,
                  self.cmb_analytics_campaign, self.cmb_analytics_group, self.cmb_analytics_account,
                  self.btn_refresh_analytics, self.btn_export_analytics]:
            w.setFixedHeight(40)
            filters.addWidget(w)
        filters.addStretch()
        root.addWidget(self.filter_host)

        self.tab_analytics = QTabWidget(); self.tab_analytics.setObjectName("tab_analytics")
        self._charts: dict[tuple[str, str], BarChartWidget | DonutChartWidget | TrendChartWidget] = {}

        # -- Accounts -----------------------------------------------------
        accounts_tab = QWidget(); ag = QGridLayout(accounts_tab)
        self._charts[("Accounts", "health")] = DonutChartWidget([], "Account health distribution", "Accounts")
        self._charts[("Accounts", "connection")] = BarChartWidget([], "Connection reliability")
        self._charts[("Accounts", "activity")] = BarChartWidget([], "Account activity")
        ag.addWidget(self._charts[("Accounts", "health")], 0, 0)
        ag.addWidget(self._charts[("Accounts", "connection")], 0, 1)
        ag.addWidget(self._charts[("Accounts", "activity")], 1, 0, 1, 2)
        self.tab_analytics.addTab(accounts_tab, "Accounts")

        # -- Groups -------------------------------------------------------
        groups_tab = QWidget(); gg = QGridLayout(groups_tab)
        self._charts[("Groups", "status")] = BarChartWidget([], "Group status")
        self._charts[("Groups", "type")] = DonutChartWidget([], "Group type", "Groups")
        self._charts[("Groups", "access")] = DonutChartWidget([], "Access type", "Groups")
        gg.addWidget(self._charts[("Groups", "status")], 0, 0)
        gg.addWidget(self._charts[("Groups", "type")], 0, 1)
        gg.addWidget(self._charts[("Groups", "access")], 1, 0)
        self.tab_analytics.addTab(groups_tab, "Groups")

        # -- Campaigns ----------------------------------------------------
        campaigns_tab = QWidget(); cg = QGridLayout(campaigns_tab)
        self._charts[("Campaigns", "summary")] = BarChartWidget([], "Campaign summary")
        self._charts[("Campaigns", "delivery")] = DonutChartWidget([], "Delivery summary", "Deliveries")
        self._charts[("Campaigns", "delivery_trend")] = TrendChartWidget([], "Deliveries over time", "#2563EB")
        cg.addWidget(self._charts[("Campaigns", "summary")], 0, 0)
        cg.addWidget(self._charts[("Campaigns", "delivery")], 0, 1)
        cg.addWidget(self._charts[("Campaigns", "delivery_trend")], 1, 0, 1, 2)
        self.tab_analytics.addTab(campaigns_tab, "Campaigns")

        # -- Members ------------------------------------------------------
        members_tab = QWidget(); mg = QGridLayout(members_tab)
        self._charts[("Members", "eligibility")] = DonutChartWidget([], "Eligibility distribution", "Members")
        self._charts[("Members", "consent")] = DonutChartWidget([], "Consent distribution", "Members")
        self._charts[("Members", "growth")] = TrendChartWidget([], "Member pool growth", "#059669")
        mg.addWidget(self._charts[("Members", "eligibility")], 0, 0)
        mg.addWidget(self._charts[("Members", "consent")], 0, 1)
        mg.addWidget(self._charts[("Members", "growth")], 1, 0, 1, 2)
        self.tab_analytics.addTab(members_tab, "Members")

        # -- Jobs ---------------------------------------------------------
        jobs_tab = QWidget(); jg = QGridLayout(jobs_tab)
        self._charts[("Jobs", "status")] = DonutChartWidget([], "Job success / failure", "Jobs")
        self._charts[("Jobs", "type")] = BarChartWidget([], "Jobs by type")
        self._charts[("Jobs", "trend")] = TrendChartWidget([], "Jobs over time", "#7C3AED")
        jg.addWidget(self._charts[("Jobs", "status")], 0, 0)
        jg.addWidget(self._charts[("Jobs", "type")], 0, 1)
        jg.addWidget(self._charts[("Jobs", "trend")], 1, 0, 1, 2)
        self.tab_analytics.addTab(jobs_tab, "Jobs")

        root.addWidget(self.tab_analytics, 1)

        self.btn_refresh_analytics.clicked.connect(self.refresh)
        self.btn_export_analytics.clicked.connect(self.export)
        self._load_filter_options()
        self.refresh()

    # -- helpers ----------------------------------------------------------
    def _db(self):
        return self.context.database if self.context else None

    def _grouped(self, sql: str, params=()) -> list[tuple[str, int]]:
        db = self._db()
        if db is None:
            return []
        try:
            rows = db.fetch_all(sql, tuple(params))
        except Exception:
            return []
        out = []
        for r in rows:
            key = str(r[0] or "UNKNOWN")
            val = int(r[1] or 0)
            if val:
                out.append((key, val))
        return out

    def _load_filter_options(self):
        selected = (self.cmb_analytics_campaign.currentData(), self.cmb_analytics_group.currentData(), self.cmb_analytics_account.currentData())
        for combo in (self.cmb_analytics_campaign, self.cmb_analytics_group, self.cmb_analytics_account):
            combo.blockSignals(True)
        for combo, label in [(self.cmb_analytics_campaign, "All Campaigns"), (self.cmb_analytics_group, "All Groups"), (self.cmb_analytics_account, "All Accounts")]:
            combo.clear(); combo.addItem(label, None)
        if not self.context:
            for combo in (self.cmb_analytics_campaign, self.cmb_analytics_group, self.cmb_analytics_account):
                combo.blockSignals(False)
            return
        for c in self.context.campaign_repository.get_all(): self.cmb_analytics_campaign.addItem(c.name, c.id)
        for g in self.context.group_repository.get_all(): self.cmb_analytics_group.addItem(g.title, g.id)
        for a in self.context.account_repository.get_all(): self.cmb_analytics_account.addItem(a.first_name or a.username or f"Account {a.id}", a.id)
        for combo, value in zip((self.cmb_analytics_campaign, self.cmb_analytics_group, self.cmb_analytics_account), selected):
            index = combo.findData(value); combo.setCurrentIndex(index if index >= 0 else 0); combo.blockSignals(False)

    def refresh_filter_options(self):
        self._load_filter_options(); self.refresh()

    # -- data collection --------------------------------------------------
    def _collect(self) -> dict:
        db = self._db()
        data: dict = {}
        if db is None:
            return data

        cid = self.cmb_analytics_campaign.currentData()
        gid = self.cmb_analytics_group.currentData()
        aid = self.cmb_analytics_account.currentData()

        # Accounts
        data["accounts_health"] = self._grouped("SELECT COALESCE(health_status,'UNKNOWN'), COUNT(*) FROM telegram_accounts GROUP BY health_status")
        data["accounts_conn"] = self._grouped("SELECT COALESCE(connection_status,'OFFLINE'), COUNT(*) FROM telegram_accounts GROUP BY connection_status")
        data["accounts_activity"] = self._grouped("SELECT COALESCE(action_type,'OTHER'), COUNT(*) FROM account_activity GROUP BY action_type ORDER BY COUNT(*) DESC LIMIT 8")

        # Groups
        data["groups_status"] = self._grouped("SELECT COALESCE(status,'UNKNOWN'), COUNT(*) FROM groups GROUP BY status")
        data["groups_type"] = self._grouped("SELECT COALESCE(group_type,'UNKNOWN'), COUNT(*) FROM groups GROUP BY group_type")
        data["groups_access"] = self._grouped("SELECT COALESCE(access_type,'UNKNOWN'), COUNT(*) FROM groups GROUP BY access_type")

        # Campaigns
        data["campaigns_status"] = self._grouped("SELECT COALESCE(status,'UNKNOWN'), COUNT(*) FROM campaigns GROUP BY status")
        where = []; params = []
        if cid: where.append("d.campaign_id=?"); params.append(cid)
        if gid: where.append("t.group_id=?"); params.append(gid)
        if aid: where.append("t.account_id=?"); params.append(aid)
        clause = " WHERE " + " AND ".join(where) if where else ""
        data["deliveries_status"] = self._grouped(
            "SELECT COALESCE(d.status,'UNKNOWN'), COUNT(*) FROM campaign_deliveries d "
            "LEFT JOIN campaign_targets t ON t.id=d.campaign_target_id" + clause + " GROUP BY d.status", params)
        data["deliveries_trend"] = self._grouped(
            "SELECT substr(d.created_at,1,10), COUNT(*) FROM campaign_deliveries d "
            "LEFT JOIN campaign_targets t ON t.id=d.campaign_target_id" + clause +
            " GROUP BY substr(d.created_at,1,10) ORDER BY 1 DESC LIMIT 14", params)
        data["deliveries_trend"].reverse()

        # Members
        data["members_elig"] = self._grouped("SELECT COALESCE(eligibility_status,'UNKNOWN'), COUNT(*) FROM members GROUP BY eligibility_status")
        data["members_consent"] = self._grouped("SELECT COALESCE(consent_status,'UNKNOWN'), COUNT(*) FROM members GROUP BY consent_status")
        data["members_growth"] = self._grouped("SELECT substr(created_at,1,10), COUNT(*) FROM members GROUP BY substr(created_at,1,10) ORDER BY 1 DESC LIMIT 14")
        data["members_growth"].reverse()

        # Jobs
        data["jobs_status"] = self._grouped("SELECT COALESCE(status,'UNKNOWN'), COUNT(*) FROM jobs GROUP BY status")
        data["jobs_type"] = self._grouped("SELECT COALESCE(job_type,'OTHER'), COUNT(*) FROM jobs GROUP BY job_type ORDER BY COUNT(*) DESC LIMIT 8")
        data["jobs_trend"] = self._grouped("SELECT substr(created_at,1,10), COUNT(*) FROM jobs GROUP BY substr(created_at,1,10) ORDER BY 1 DESC LIMIT 14")
        data["jobs_trend"].reverse()

        return data

    def refresh(self):
        data = self._collect()
        self._charts[("Accounts", "health")].set_data(data.get("accounts_health", []))
        self._charts[("Accounts", "connection")].set_data(data.get("accounts_conn", []))
        self._charts[("Accounts", "activity")].set_data(data.get("accounts_activity", []))
        self._charts[("Groups", "status")].set_data(data.get("groups_status", []))
        self._charts[("Groups", "type")].set_data(data.get("groups_type", []))
        self._charts[("Groups", "access")].set_data(data.get("groups_access", []))
        self._charts[("Campaigns", "summary")].set_data(data.get("campaigns_status", []))
        self._charts[("Campaigns", "delivery")].set_data(data.get("deliveries_status", []))
        self._charts[("Campaigns", "delivery_trend")].set_data(data.get("deliveries_trend", []))
        self._charts[("Members", "eligibility")].set_data(data.get("members_elig", []))
        self._charts[("Members", "consent")].set_data(data.get("members_consent", []))
        self._charts[("Members", "growth")].set_data(data.get("members_growth", []))
        self._charts[("Jobs", "status")].set_data(data.get("jobs_status", []))
        self._charts[("Jobs", "type")].set_data(data.get("jobs_type", []))
        self._charts[("Jobs", "trend")].set_data(data.get("jobs_trend", []))
        return data

    def export(self):
        data = self.refresh()
        if not data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Analytics", "analytics.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(Path(path), "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["section", "label", "value"])
            for section, rows in data.items():
                for label, value in rows:
                    writer.writerow([section, label, value])
    def apply_license_features(self,feature_gate,limit_service=None):
        from app.license.feature_keys import FeatureKey
        basic=feature_gate.has_feature(FeatureKey.BASIC_CAMPAIGN_ANALYTICS)
        full=feature_gate.has_feature(FeatureKey.ADVANCED_ANALYTICS)
        if not basic:
            if self._license_lock is None:
                self._license_lock=LockedFeatureWidget("Analytics","Campaign analytics is available with SP Telegram Pro; full analytics is available with SP Telegram Ultimate.","PRO",["Basic Campaign Analytics","SP Telegram Ultimate adds full account/group/member/job analytics"],self)
                self._license_lock.upgradeRequested.connect(self.licenseUpgradeRequested);self.root_layout.insertWidget(1,self._license_lock)
            self._license_lock.show();self.filter_host.hide();self.tab_analytics.hide();self.btn_refresh_analytics.setEnabled(False);self.btn_export_analytics.setEnabled(False);return False
        if self._license_lock is not None:self._license_lock.hide()
        self.filter_host.show();self.tab_analytics.show();self.btn_refresh_analytics.setEnabled(True);self.btn_export_analytics.setEnabled(True)
        for i in range(self.tab_analytics.count()):
            name=self.tab_analytics.tabText(i);enabled=full or name=="Campaigns";self.tab_analytics.setTabEnabled(i,enabled);self.tab_analytics.setTabToolTip(i,"" if enabled else "Full analytics requires SP Telegram Ultimate.")
        if not full:
            idx=next((i for i in range(self.tab_analytics.count()) if self.tab_analytics.tabText(i)=="Campaigns"),-1)
            if idx>=0:self.tab_analytics.setCurrentIndex(idx)
        return True
