from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.dialogs.activate_license_dialog import ActivateLicenseDialog
from app.dialogs.device_management_dialog import DeviceManagementDialog
from app.dialogs.license_details_dialog import LicenseDetailsDialog
from app.dialogs.upgrade_plan_dialog import UpgradePlanDialog
from app.license.feature_keys import FeatureKey, LimitKey
from app.license.license_models import LicenseStatus, PlanKey
from app.license.plan_config import (
    PLAN_CONFIG,
    PLAN_ORDER,
    format_plan_limit,
    plan_has_feature,
)
from app.widgets.page_header import PageHeaderWidget
from app.widgets.plan_badge import PlanBadge
from app.widgets.section_card import SectionCard
from app.widgets.status_badge import StatusBadge


class LicensePage(QWidget):
    toastRequested = Signal(str, str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("page_license")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        header = PageHeaderWidget(
            "License",
            "Manage your SP Telegram subscription and activated devices.",
        )
        self.btn_activate_license = QPushButton("Activate License")
        self.btn_activate_license.setObjectName("btn_activate_license")
        self.btn_activate_license.setProperty("primary", True)

        self.btn_refresh_license = QPushButton("Refresh")
        self.btn_refresh_license.setObjectName("btn_refresh_license")

        header.add_action(self.btn_refresh_license)
        header.add_action(self.btn_activate_license)
        root.addWidget(header)

        # Do not call this self.scroll because QWidget already has scroll().
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        host = QWidget()
        self.body = QVBoxLayout(host)
        self.body.setContentsMargins(0, 0, 4, 0)
        self.body.setSpacing(14)

        self.scroll_area.setWidget(host)
        root.addWidget(self.scroll_area, 1)

        self.current = SectionCard("SP Telegram License")
        top = QHBoxLayout()
        self.lbl_license_plan = QLabel("No Active License")
        self.lbl_license_plan.setProperty("summaryValue", True)
        self.badge = PlanBadge("")
        self.lbl_license_status = StatusBadge("Unlicensed")
        top.addWidget(self.lbl_license_plan)
        top.addWidget(self.badge)
        top.addStretch()
        top.addWidget(self.lbl_license_status)
        self.current.body.addLayout(top)

        self.lbl_license_summary = QLabel()
        self.lbl_license_summary.setWordWrap(True)
        self.lbl_license_summary.setProperty("secondary", True)
        self.current.body.addWidget(self.lbl_license_summary)

        actions = QHBoxLayout()
        self.btn_change_license = QPushButton("View Plans")
        self.btn_change_license.setObjectName("btn_change_license")
        self.btn_license_details = QPushButton("License Details")
        self.btn_license_details.setObjectName("btn_license_details")
        self.btn_manage_license_devices = QPushButton("Manage Devices")
        self.btn_manage_license_devices.setObjectName("btn_manage_license_devices")
        self.btn_copy_device_id = QPushButton("Copy Device ID")
        self.btn_copy_device_id.setObjectName("btn_copy_device_id")
        self.btn_deactivate_device = QPushButton("Deactivate This Device")
        self.btn_deactivate_device.setObjectName("btn_deactivate_device")
        self.btn_deactivate_device.setProperty("danger", True)

        for button in (
            self.btn_change_license,
            self.btn_license_details,
            self.btn_manage_license_devices,
            self.btn_copy_device_id,
            self.btn_deactivate_device,
        ):
            actions.addWidget(button)

        actions.addStretch()
        self.current.body.addLayout(actions)
        self.body.addWidget(self.current)

        self.usage = SectionCard("Plan Usage")
        self.usage_grid = QGridLayout()
        self._usage_rows = {}
        labels = [
            (LimitKey.MAX_ACCOUNTS, "Accounts"),
            (LimitKey.MAX_SOURCE_GROUPS, "Source Groups"),
            (LimitKey.MAX_TARGET_GROUPS, "Managed / Target Groups"),
            (LimitKey.MAX_MEMBER_POOL, "Members"),
            (LimitKey.MAX_TEMPLATES, "Templates"),
            (LimitKey.MAX_DEVICES, "Devices"),
        ]

        for row, (key, label) in enumerate(labels):
            name = QLabel(label)
            value = QLabel("—")
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setMaximumHeight(8)
            self.usage_grid.addWidget(name, row, 0)
            self.usage_grid.addWidget(value, row, 1)
            self.usage_grid.addWidget(bar, row, 2)
            self._usage_rows[str(key)] = (value, bar)

        self.usage.body.addLayout(self.usage_grid)
        self.body.addWidget(self.usage)

        plans = SectionCard("Choose Your Plan")
        self.plans_section = plans
        cards = QHBoxLayout()
        self._plan_buttons = {}

        for plan in PLAN_ORDER:
            cfg = PLAN_CONFIG[plan]
            limit_lines = [
                (
                    f"{format_plan_limit(plan, LimitKey.MAX_ACCOUNTS, compact=True)} Accounts*"
                    if plan == PlanKey.ULTIMATE
                    else f"{format_plan_limit(plan, LimitKey.MAX_ACCOUNTS, compact=True)} Accounts"
                ),
                (
                    f"{format_plan_limit(plan, LimitKey.MAX_SOURCE_GROUPS, compact=True)} Source Groups*"
                    if plan == PlanKey.ULTIMATE
                    else f"{format_plan_limit(plan, LimitKey.MAX_SOURCE_GROUPS, compact=True)} Source Groups"
                ),
                (
                    f"{format_plan_limit(plan, LimitKey.MAX_TARGET_GROUPS, compact=True)} Managed Groups*"
                    if plan == PlanKey.ULTIMATE
                    else f"{format_plan_limit(plan, LimitKey.MAX_TARGET_GROUPS, compact=True)} Managed Groups"
                ),
                (
                    f"{format_plan_limit(plan, LimitKey.MAX_MEMBER_POOL, compact=True)} Member Pool*"
                    if plan == PlanKey.ULTIMATE
                    else f"{format_plan_limit(plan, LimitKey.MAX_MEMBER_POOL, compact=True)} Member Pool"
                ),
            ]
            feature_lines = limit_lines + list(cfg.get("card_highlights", ()))

            card = QFrame()
            card.setProperty("pricingCard", True)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(18, 18, 18, 18)
            lay.setSpacing(9)

            row = QHBoxLayout()
            name = QLabel(cfg["name"])
            name.setProperty("sectionTitle", True)
            row.addWidget(name)
            row.addStretch()
            row.addWidget(PlanBadge(cfg["badge"] or plan.value))
            lay.addLayout(row)

            price = QLabel(f"${cfg['price_monthly']}  / month")
            price.setProperty("summaryValue", True)
            lay.addWidget(price)

            tagline = QLabel(cfg["tagline"])
            tagline.setWordWrap(True)
            tagline.setProperty("secondary", True)
            lay.addWidget(tagline)

            features = QLabel("\n".join(f"✓ {item}" for item in feature_lines))
            features.setProperty("secondary", True)
            lay.addWidget(features)
            lay.addStretch()

            button = QPushButton(f"Choose {plan.value.title()}")
            button.setObjectName(
                {
                    "STARTER": "btn_choose_starter",
                    "PRO": "btn_choose_pro",
                    "ULTIMATE": "btn_choose_ultimate",
                }[plan.value]
            )
            button.setProperty("primary", plan == PlanKey.PRO)
            lay.addWidget(button)
            self._plan_buttons[plan] = button
            cards.addWidget(card, 1)

        plans.body.addLayout(cards)
        self.body.addWidget(plans)

        compare = SectionCard("Plan Comparison")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        headers = ["Capability", "Starter", "Pro", "Ultimate"]
        for column, text in enumerate(headers):
            label = QLabel(text)
            label.setProperty("sectionTitle", column == 0)
            grid.addWidget(label, 0, column)

        def limit_row(label, key):
            return (label, *(format_plan_limit(plan, key) for plan in PLAN_ORDER))

        def feature_row(label, key):
            return (
                label,
                *("Included" if plan_has_feature(plan, key) else "—" for plan in PLAN_ORDER),
            )

        rows = [
            limit_row("Accounts", LimitKey.MAX_ACCOUNTS),
            limit_row("Source Groups", LimitKey.MAX_SOURCE_GROUPS),
            limit_row("Managed Groups", LimitKey.MAX_TARGET_GROUPS),
            limit_row("Member Pool", LimitKey.MAX_MEMBER_POOL),
            feature_row("Campaigns", FeatureKey.CAMPAIGNS),
            feature_row("Media Posts", FeatureKey.MEDIA_POSTING),
            feature_row("Schedule Once", FeatureKey.SCHEDULE_ONCE),
            feature_row("Recurring Schedule", FeatureKey.RECURRING_SCHEDULE),
            feature_row("Content Calendar", FeatureKey.CONTENT_CALENDAR),
            ("Analytics", "Basic dashboard", "Campaign", "Full"),
            feature_row("Automatic Backup", FeatureKey.AUTO_BACKUP),
            feature_row("App Lock", FeatureKey.APP_LOCK),
            feature_row("Security Audit", FeatureKey.SECURITY_AUDIT),
            limit_row("Devices", LimitKey.MAX_DEVICES),
        ]

        for row_index, row_data in enumerate(rows, 1):
            for column, text in enumerate(row_data):
                label = QLabel(text)
                label.setProperty("secondary", column > 0)
                grid.addWidget(label, row_index, column)

        compare.body.addLayout(grid)
        self.body.addWidget(compare)

        note = QLabel(
            "* Unlimited means no artificial SP Telegram plan limit. Telegram API availability, "
            "Telegram permissions/restrictions, database capacity and local computer resources still apply."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        self.body.addWidget(note)

        self.btn_activate_license.clicked.connect(self._activate)
        self.btn_refresh_license.clicked.connect(controller.refresh_license)
        self.btn_license_details.clicked.connect(self._details)
        self.btn_manage_license_devices.clicked.connect(controller.open_device_manager)
        self.btn_copy_device_id.clicked.connect(self._copy_device)
        self.btn_deactivate_device.clicked.connect(self._deactivate_current)
        self.btn_change_license.clicked.connect(lambda: self._scroll_plans(plans))
        self._plan_buttons[PlanKey.STARTER].clicked.connect(lambda: self._choose_plan(PlanKey.STARTER))
        self._plan_buttons[PlanKey.PRO].clicked.connect(lambda: self._choose_plan(PlanKey.PRO))
        self._plan_buttons[PlanKey.ULTIMATE].clicked.connect(lambda: self._choose_plan(PlanKey.ULTIMATE))

        controller.licenseChanged.connect(lambda *_: self.refresh())
        controller.deviceListChanged.connect(self._show_devices)
        controller.upgradeRequested.connect(self._upgrade_requested)
        self.refresh()

    def refresh(self):
        summary = self.controller.load_license_page()
        state = summary.state
        self.lbl_license_plan.setText(summary.plan_name)
        self.badge.set_plan(str(state.plan or "UNLICENSED"))
        status = str(state.status)
        self.lbl_license_status.setText(status.replace("_", " ").title())
        self.lbl_license_status.set_state(status)

        if status == LicenseStatus.UNLICENSED:
            self.lbl_license_summary.setText(
                "No active license. Activate a trusted license to unlock licensed creation and outgoing features. "
                "Existing local data is preserved."
            )
        elif status == LicenseStatus.OFFLINE_GRACE:
            self.lbl_license_summary.setText(
                f"Offline License Mode\nPreviously validated plan remains available until "
                f"{state.offline_grace_until or 'the grace deadline'}."
            )
        elif status == LicenseStatus.EXPIRED:
            self.lbl_license_summary.setText(
                f"License Expired\nExpired: {state.expires_at or '—'}\n"
                "Your local data remains stored safely. Renew to restore licensed creation and outgoing features."
            )
        elif status == LicenseStatus.SUSPENDED:
            self.lbl_license_summary.setText(
                "License Suspended\nThis license currently requires review. Your local data remains preserved. "
                "Refresh the license or review license details."
            )
        elif status == LicenseStatus.DEVICE_LIMIT:
            self.lbl_license_summary.setText(
                "Device Limit Reached\nManage an existing device activation before activating this computer. "
                "Telegram sessions are not affected."
            )
        elif status == LicenseStatus.VALIDATION_REQUIRED:
            self.lbl_license_summary.setText(
                "Online License Verification Required\nConnect to the internet and refresh your license. Existing "
                "local data, exports, backups and safety features remain available."
            )
        else:
            device_usage = summary.usage.get(
                str(LimitKey.MAX_DEVICES),
                {"current": 0, "limit": summary.device_limit},
            )
            device_limit = device_usage.get("limit")
            device_text = (
                f"{int(device_usage.get('current', 0))} / "
                f"{'Unlimited' if device_limit is None else int(device_limit or 0)}"
            )
            self.lbl_license_summary.setText(
                f"Price: ${summary.price_monthly}/month\n"
                f"Expires: {state.expires_at or '—'}   •   "
                f"Days Remaining: {summary.days_remaining if summary.days_remaining is not None else '—'}   •   "
                f"Devices: {device_text}\n"
                f"Last Verified: {state.last_validated_at or 'Never'}   •   "
                f"License Key: {state.license_key_masked or '—'}"
            )

        self.usage.setVisible(state.plan_key is not None)

        for key, (value, bar) in self._usage_rows.items():
            data = summary.usage.get(key, {"current": 0, "limit": 0})
            current = int(data.get("current", 0))
            limit = data.get("limit")

            if limit == 0:
                value.setText("Not included")
                bar.setVisible(False)
            else:
                if limit is None:
                    value.setText(f"{current:,} / Unlimited")
                elif current > int(limit):
                    value.setText(f"{current:,} / {int(limit):,}  •  Over Plan Limit")
                else:
                    value.setText(f"{current:,} / {int(limit):,}")

                bar.setVisible(limit is not None)
                bar.setMaximum(max(1, int(limit or 1)))
                bar.setValue(min(current, int(limit or 1)))

        for plan, button in self._plan_buttons.items():
            current = str(state.plan or "") == plan.value
            button.setText("Current Plan" if current else f"Choose {plan.value.title()}")
            button.setEnabled(not current)

        self.btn_deactivate_device.setEnabled(bool(state.license_reference and state.device_id))
        return summary

    def _activate(self):
        dialog = ActivateLicenseDialog(self.controller.activation_device_summary(), self)
        if dialog.exec():
            key, name = dialog.data()
            self.controller.activate_license(key, name)
            dialog.le_license_key.clear()

    def _details(self):
        LicenseDetailsDialog(self.controller.load_license_page(), self).exec()

    def _deactivate_current(self):
        summary = self.controller.load_license_page()
        name = summary.state.device_name or "Current Device"
        text = (
            "Deactivate Device?\n\n"
            f"{name}\n\n"
            "This computer will need to activate the license again before licensed features can be used. "
            "Telegram account sessions are separate and will not be deleted or logged out."
        )
        result = QMessageBox.question(
            self,
            "Deactivate Device",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.controller.deactivate_device()

    def _show_devices(self, devices):
        dialog = DeviceManagementDialog(devices, self)
        dialog.deactivateRequested.connect(self.controller.deactivate_device)
        dialog.exec()

    def _copy_device(self):
        value = self.controller.copy_device_id()
        QApplication.clipboard().setText(value)
        self.toastRequested.emit("Masked device ID copied.", "Success")

    def _upgrade_requested(self, feature, required):
        try:
            plan = PlanKey(str(required or "PRO").upper())
        except ValueError:
            plan = PlanKey.PRO

        feature_name = "Plan change" if str(feature) == "PLAN_CHANGE" else (feature or "Selected feature")
        dialog = UpgradePlanDialog(
            str(self.controller.current_state().plan or "Unlicensed"),
            feature_name,
            plan.value,
            controller=self.controller,
            parent=self,
        )
        dialog.viewPlansRequested.connect(lambda: self._scroll_plans(None))
        if dialog.exec():
            self.refresh()

    def _choose_plan(self, plan):
        summary = self.controller.load_license_page()
        current = summary.state.plan_key
        if current == plan:
            return

        target = PLAN_CONFIG[plan]
        over = []
        checks = [
            (LimitKey.MAX_ACCOUNTS, "Accounts"),
            (LimitKey.MAX_SOURCE_GROUPS, "Source Groups"),
            (LimitKey.MAX_TARGET_GROUPS, "Managed / Target Groups"),
            (LimitKey.MAX_MEMBER_POOL, "Members"),
            (LimitKey.MAX_TEMPLATES, "Templates"),
        ]

        for key, label in checks:
            data = summary.usage.get(str(key))
            limit = target["limits"][key]
            if data and limit is not None and int(data.get("current", 0)) > int(limit):
                over.append(f"{label}: {int(data['current']):,} / {int(limit):,}")

        if over:
            text = (
                "Your current usage exceeds the selected plan limits:\n\n"
                + "\n".join(over)
                + "\n\nYour existing data will NOT be deleted. New creation/sync may remain limited until usage "
                "is within the plan or you upgrade again.\n\nContinue to the trusted plan-change flow?"
            )
            result = QMessageBox.question(
                self,
                "Plan Limit Warning",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        {
            PlanKey.STARTER: self.controller.choose_starter,
            PlanKey.PRO: self.controller.choose_pro,
            PlanKey.ULTIMATE: self.controller.choose_ultimate,
        }[plan]()

    def _scroll_plans(self, _):
        self.scroll_area.ensureWidgetVisible(self.plans_section, 0, 12)
