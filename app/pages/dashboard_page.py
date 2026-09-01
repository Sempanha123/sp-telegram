from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.icons import IconManager
from app.widgets.accent_card import AccentCard
from app.widgets.activity_feed import ActivityFeed
from app.widgets.page_header import PageHeaderWidget
from app.widgets.section_card import SectionCard
from app.widgets.stat_card import StatCard


class DashboardPage(QWidget):
    quickAction=Signal(str)
    LEGACY_CARDS=[
        ("Healthy","card_healthy_accounts",("accounts","healthy")),("Cooldown","card_cooldown_accounts",("accounts","cooldown")),("Restricted","card_restricted_accounts",("accounts","restricted")),
        ("Source Groups","card_source_groups",("groups","sources")),("Target Groups","card_target_groups",("groups","targets")),("Managed Groups","card_managed_groups",("groups","managed")),("Group Errors","card_group_errors",("groups","errors")),
        ("Eligible Members","card_eligible_members",("members","eligible")),("Unknown Members","card_unknown_members",("members","unknown")),("Do Not Contact","card_do_not_contact_members",("members","do_not_contact")),("Blacklisted","card_blacklisted_members",("members","blacklisted")),
        ("Scheduled Posts","card_scheduled_posts",("campaigns","scheduled")),("Running Jobs","card_running_jobs",("jobs","running")),("Critical Alerts","card_critical_alerts",("alerts","critical")),
    ]

    def __init__(self, controller, parent=None, *, activity_loader=None):
        super().__init__(parent); self.setObjectName("page_dashboard"); self.controller = controller
        root=QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(16)
        header=PageHeaderWidget("Dashboard","Overview of accounts, groups, members, campaigns and system health.")
        self.btn_quick_add_account=QPushButton("Add Account"); self.btn_quick_add_account.setObjectName("btn_quick_add_account"); self.btn_quick_add_account.setProperty("primary",True); self.btn_quick_add_account.setIcon(IconManager.get("plus"))
        self.btn_quick_add_group=QPushButton("Add Group"); self.btn_quick_add_group.setObjectName("btn_quick_add_group"); self.btn_quick_add_group.setIcon(IconManager.get("plus"))
        self.btn_quick_create_campaign=QPushButton("Create Campaign"); self.btn_quick_create_campaign.setObjectName("btn_quick_create_campaign"); self.btn_quick_create_campaign.setIcon(IconManager.get("campaigns"))
        self.btn_dashboard_quick_actions=QPushButton("Quick Actions"); self.btn_dashboard_quick_actions.setProperty("role","ghost"); self.btn_dashboard_quick_actions.setIcon(IconManager.get("more"))
        self.btn_quick_add_account.clicked.connect(lambda: self.quickAction.emit("accounts"))
        self.btn_quick_add_group.clicked.connect(lambda: self.quickAction.emit("groups"))
        self.btn_quick_create_campaign.clicked.connect(lambda: self.quickAction.emit("campaigns"))
        for button in (self.btn_quick_add_account, self.btn_quick_add_group, self.btn_quick_create_campaign):
            header.add_action(button)
        header.add_action(self.btn_dashboard_quick_actions); root.addWidget(header)
        self._secondary_quick=[]
        for obj,text,key in [("btn_quick_collect_members","Sync Members","collector"),("btn_quick_schedule_post","Schedule Post","scheduler"),("btn_quick_view_alerts","View Alerts","alerts"),("btn_quick_run_diagnostics","Run Diagnostics","operations")]:
            btn=QPushButton(text,self); btn.setObjectName(obj); btn.hide(); btn.clicked.connect(lambda _=False,k=key:self.quickAction.emit(k)); setattr(self,obj,btn); self._secondary_quick.append((btn,text))
        menu=QMenu(self.btn_dashboard_quick_actions)
        for btn,text in self._secondary_quick: menu.addAction(text,btn.click)
        self.btn_dashboard_quick_actions.setMenu(menu)

        self.banner=QFrame(); self.banner.setProperty("systemBanner",True); self.banner.setProperty("state","ok"); bl=QHBoxLayout(self.banner); bl.setContentsMargins(12,8,12,8)
        self.lbl_system_banner=QLabel("●  All Systems Operational"); self.lbl_system_banner.setObjectName("lbl_dashboard_system_banner"); self.lbl_system_banner.setProperty("systemBannerText",True); bl.addWidget(self.lbl_system_banner); bl.addStretch()
        self.btn_review_attention=QPushButton("Review"); self.btn_review_attention.setObjectName("btn_dashboard_review_attention"); self.btn_review_attention.setProperty("role","ghost"); self.btn_review_attention.setIcon(IconManager.get("arrow_right")); self.btn_review_attention.hide(); self.btn_review_attention.clicked.connect(self._review_attention); bl.addWidget(self.btn_review_attention); root.addWidget(self.banner)
        self._attention_target="account_health"

        # Colorful accent metric cards.
        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_accounts = AccentCard("Accounts", 0, "primary", "accounts", "card_total_accounts")
        self.card_groups = AccentCard("Groups", 0, "purple", "groups", "card_total_groups")
        self.card_members = AccentCard("Members", 0, "success", "members", "card_member_pool")
        self.card_campaigns = AccentCard("Campaigns", 0, "info", "campaigns", "card_active_campaigns")
        for col, card in enumerate((self.card_accounts, self.card_groups, self.card_members, self.card_campaigns)):
            cards.addWidget(card, 0, col)
        root.addLayout(cards)
        self.cards={}; self._legacy_cards=[]
        for title,name,path in self.LEGACY_CARDS:
            card=StatCard(title,0,name,self); card.hide(); self.cards[path]=card; self._legacy_cards.append(card)

        lower=QHBoxLayout(); lower.setSpacing(12)
        self.health_section=SectionCard("Account Health","View All"); self.health_section.btn_action.clicked.connect(lambda:self.quickAction.emit("account_health")); self._health_rows={}
        for key,label,tone in (("healthy","Healthy","success"),("cooldown","Cooldown","warning"),("restricted","Restricted","danger"),("offline","Offline","muted")):
            host=QWidget(); host.setProperty("transparentHost",True); row=QHBoxLayout(host); row.setContentsMargins(0,2,0,2); row.setSpacing(10)
            name=QLabel(label); name.setMinimumWidth(78); name.setProperty("secondary",True)
            bar=QProgressBar(); bar.setRange(0,100); bar.setValue(0); bar.setTextVisible(False); bar.setProperty("tone",tone)
            value=QLabel("0"); value.setFixedWidth(48); value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name); row.addWidget(bar,1); row.addWidget(value); self.health_section.body.addWidget(host); self._health_rows[key]=(host,bar,value)
        self.lbl_health_empty=QLabel("No account health data yet."); self.lbl_health_empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_health_empty.setProperty("muted",True); self.lbl_health_empty.setMinimumHeight(76); self.health_section.body.addWidget(self.lbl_health_empty)
        self.activity_section = SectionCard("Recent Activity")
        if activity_loader is not None:
            self.activity_feed = ActivityFeed(activity_loader, refresh_ms=4000, max_items=10)
            self.activity_section.body.addWidget(self.activity_feed, 1)
        else:
            self.activity_feed = None
            self.lbl_recent_activity = QLabel("No recent activity yet.")
            self.lbl_recent_activity.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_recent_activity.setProperty("muted", True)
            self.lbl_recent_activity.setWordWrap(True)
            self.lbl_recent_activity.setMinimumHeight(100)
            self.activity_section.body.addWidget(self.lbl_recent_activity)
        lower.addWidget(self.health_section,65); lower.addWidget(self.activity_section,35); root.addLayout(lower,1)

        self.schedule_section=SectionCard("Upcoming Scheduled Posts","View Scheduler"); self.schedule_section.btn_action.clicked.connect(lambda:self.quickAction.emit("scheduler")); self.lbl_upcoming=QLabel("No upcoming scheduled posts."); self.lbl_upcoming.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_upcoming.setProperty("muted",True); self.lbl_upcoming.setMinimumHeight(44); self.schedule_section.body.addWidget(self.lbl_upcoming); root.addWidget(self.schedule_section)
        controller.summaryChanged.connect(self.set_summary); self.set_summary(controller.summary())

    def set_summary(self,data):
        a=data.get("accounts",{}); g=data.get("groups",{}); m=data.get("members",{}); c=data.get("campaigns",{}); j=data.get("jobs",{}); alerts=data.get("alerts",{})
        for path,card in self.cards.items(): card.set_value(data.get(path[0],{}).get(path[1],0))
        self.card_accounts.set_value(int(a.get("total",0))); self.card_accounts.set_metrics([("Healthy",int(a.get("healthy",0)),"success"),("Cooldown",int(a.get("cooldown",0)),"warning"),("Restricted",int(a.get("restricted",0)),"danger"),("Offline",int(a.get("offline",0)),"muted")])
        self.card_groups.set_value(int(g.get("total",0))); self.card_groups.set_metrics([("Managed",int(g.get("managed",0)),"primary"),("Sources",int(g.get("sources",0)),"muted"),("Targets",int(g.get("targets",0)),"muted"),("Errors",int(g.get("errors",0)),"danger")])
        self.card_members.set_value(int(m.get("total",0))); self.card_members.set_metrics([("Eligible",int(m.get("eligible",0)),"success"),("Do Not Contact",int(m.get("do_not_contact",0)),"danger"),("Blacklisted",int(m.get("blacklisted",0)),"danger")])
        self.card_campaigns.set_value(int(c.get("active",0))); self.card_campaigns.set_metrics([("Active",int(c.get("active",0)),"primary"),("Scheduled",int(c.get("scheduled",0)),"purple"),("Running Jobs",int(j.get("running",0)),"success"),("Critical Alerts",int(alerts.get("critical",0)),"danger")])
        total=max(0,int(a.get("total",0)))
        self.lbl_health_empty.setVisible(total==0)
        for key,(host,bar,value) in self._health_rows.items():
            count=max(0,int(a.get(key,0))); host.setVisible(total>0); value.setText(f"{count:,}"); bar.setValue(round(count*100/total) if total else 0)
        attention=int(alerts.get("critical",0))+int(a.get("restricted",0))+int(a.get("offline",0))
        self.lbl_system_banner.setText("●  All Systems Operational" if attention==0 else f"●  Attention Required   {attention} item{'s' if attention!=1 else ''} need review")
        self._attention_target="alerts" if int(alerts.get("critical",0)) else "account_health"
        self.btn_review_attention.setVisible(attention>0)
        state="attention" if attention else "ok"
        if self.banner.property("state") != state:
            self.banner.setProperty("state",state)
            for widget in (self.banner,self.lbl_system_banner,self.btn_review_attention):
                widget.style().unpolish(widget); widget.style().polish(widget)

    def _review_attention(self):
        self.quickAction.emit(self._attention_target)

    def refresh(self): self.set_summary(self.controller.refresh())
