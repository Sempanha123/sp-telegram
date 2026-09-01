from __future__ import annotations
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import QFrame,QGridLayout,QHBoxLayout,QLabel,QMessageBox,QProgressBar,QPushButton,QScrollArea,QVBoxLayout,QWidget
from app.dialogs.activate_license_dialog import ActivateLicenseDialog
from app.dialogs.license_details_dialog import LicenseDetailsDialog
from app.dialogs.upgrade_plan_dialog import UpgradePlanDialog
from app.dialogs.device_management_dialog import DeviceManagementDialog
from app.license.feature_keys import FeatureKey, LimitKey
from app.license.license_models import LicenseStatus,PlanKey
from app.license.plan_config import PLAN_CONFIG, PLAN_ORDER, format_plan_limit, plan_has_feature
from app.widgets.page_header import PageHeaderWidget
from app.widgets.plan_badge import PlanBadge
from app.widgets.section_card import SectionCard
from app.widgets.status_badge import StatusBadge

class LicensePage(QWidget):
    toastRequested=Signal(str,str)
    def __init__(self,controller,parent=None):
        super().__init__(parent);self.controller=controller;self.setObjectName('page_license');root=QVBoxLayout(self);root.setContentsMargins(24,24,24,24);root.setSpacing(14)
        header=PageHeaderWidget('License','Manage your SP Telegram subscription and activated devices.');self.btn_activate_license=QPushButton('Activate License');self.btn_activate_license.setObjectName('btn_activate_license');self.btn_activate_license.setProperty('primary',True);self.btn_refresh_license=QPushButton('Refresh');self.btn_refresh_license.setObjectName('btn_refresh_license');header.add_action(self.btn_refresh_license);header.add_action(self.btn_activate_license);root.addWidget(header)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame);host=QWidget();self.body=QVBoxLayout(host);self.body.setContentsMargins(0,0,4,0);self.body.setSpacing(14);self.scroll.setWidget(host);root.addWidget(self.scroll,1)
        self.current=SectionCard('SP Telegram License');top=QHBoxLayout();self.lbl_license_plan=QLabel('No Active License');self.lbl_license_plan.setProperty('summaryValue',True);self.badge=PlanBadge('');self.lbl_license_status=StatusBadge('Unlicensed');top.addWidget(self.lbl_license_plan);top.addWidget(self.badge);top.addStretch();top.addWidget(self.lbl_license_status);self.current.body.addLayout(top);self.lbl_license_summary=QLabel();self.lbl_license_summary.setWordWrap(True);self.lbl_license_summary.setProperty('secondary',True);self.current.body.addWidget(self.lbl_license_summary);actions=QHBoxLayout();self.btn_change_license=QPushButton('View Plans');self.btn_change_license.setObjectName('btn_change_license');self.btn_license_details=QPushButton('License Details');self.btn_license_details.setObjectName('btn_license_details');self.btn_manage_license_devices=QPushButton('Manage Devices');self.btn_manage_license_devices.setObjectName('btn_manage_license_devices');self.btn_copy_device_id=QPushButton('Copy Device ID');self.btn_copy_device_id.setObjectName('btn_copy_device_id');self.btn_deactivate_device=QPushButton('Deactivate This Device');self.btn_deactivate_device.setObjectName('btn_deactivate_device');self.btn_deactivate_device.setProperty('danger',True)
        for b in (self.btn_change_license,self.btn_license_details,self.btn_manage_license_devices,self.btn_copy_device_id,self.btn_deactivate_device):actions.addWidget(b)
        actions.addStretch();self.current.body.addLayout(actions);self.body.addWidget(self.current)
        self.usage=SectionCard('Plan Usage');self.usage_grid=QGridLayout();self._usage_rows={};labels=[(LimitKey.MAX_ACCOUNTS,'Accounts'),(LimitKey.MAX_SOURCE_GROUPS,'Source Groups'),(LimitKey.MAX_TARGET_GROUPS,'Managed / Target Groups'),(LimitKey.MAX_MEMBER_POOL,'Members'),(LimitKey.MAX_TEMPLATES,'Templates'),(LimitKey.MAX_DEVICES,'Devices')]
        for row,(key,label) in enumerate(labels):name=QLabel(label);value=QLabel('—');bar=QProgressBar();bar.setTextVisible(False);bar.setMaximumHeight(8);self.usage_grid.addWidget(name,row,0);self.usage_grid.addWidget(value,row,1);self.usage_grid.addWidget(bar,row,2);self._usage_rows[str(key)]=(value,bar)
        self.usage.body.addLayout(self.usage_grid);self.body.addWidget(self.usage)
        plans=SectionCard('Choose Your Plan');self.plans_section=plans;cards=QHBoxLayout();self._plan_buttons={}
        for plan in PLAN_ORDER:
            cfg=PLAN_CONFIG[plan]
            limit_lines = [
                f"{format_plan_limit(plan, LimitKey.MAX_ACCOUNTS, compact=True)} Accounts*" if plan == PlanKey.ULTIMATE else f"{format_plan_limit(plan, LimitKey.MAX_ACCOUNTS, compact=True)} Accounts",
                f"{format_plan_limit(plan, LimitKey.MAX_SOURCE_GROUPS, compact=True)} Source Groups*" if plan == PlanKey.ULTIMATE else f"{format_plan_limit(plan, LimitKey.MAX_SOURCE_GROUPS, compact=True)} Source Groups",
                f"{format_plan_limit(plan, LimitKey.MAX_TARGET_GROUPS, compact=True)} Managed Groups*" if plan == PlanKey.ULTIMATE else f"{format_plan_limit(plan, LimitKey.MAX_TARGET_GROUPS, compact=True)} Managed Groups",
                f"{format_plan_limit(plan, LimitKey.MAX_MEMBER_POOL, compact=True)} Member Pool*" if plan == PlanKey.ULTIMATE else f"{format_plan_limit(plan, LimitKey.MAX_MEMBER_POOL, compact=True)} Member Pool",
            ]
            feature_lines = limit_lines + list(cfg.get('card_highlights', ()))
            card=QFrame();card.setProperty('pricingCard',True);lay=QVBoxLayout(card);lay.setContentsMargins(18,18,18,18);lay.setSpacing(9);r=QHBoxLayout();name=QLabel(cfg['name']);name.setProperty('sectionTitle',True);r.addWidget(name);r.addStretch();r.addWidget(PlanBadge(cfg['badge'] or plan.value));lay.addLayout(r);price=QLabel(f"${cfg['price_monthly']}  / month");price.setProperty('summaryValue',True);lay.addWidget(price);tag=QLabel(cfg['tagline']);tag.setWordWrap(True);tag.setProperty('secondary',True);lay.addWidget(tag);fl=QLabel('\n'.join(f'✓ {x}' for x in feature_lines));fl.setProperty('secondary',True);lay.addWidget(fl);lay.addStretch();btn=QPushButton(f'Choose {plan.value.title()}');btn.setObjectName({'STARTER':'btn_choose_starter','PRO':'btn_choose_pro','ULTIMATE':'btn_choose_ultimate'}[plan.value]);btn.setProperty('primary',plan==PlanKey.PRO);lay.addWidget(btn);self._plan_buttons[plan]=btn;cards.addWidget(card,1)
        plans.body.addLayout(cards);self.body.addWidget(plans)
        compare=SectionCard('Plan Comparison');grid=QGridLayout();grid.setHorizontalSpacing(18);grid.setVerticalSpacing(8);headers=['Capability','Starter','Pro','Ultimate']
        for c,text in enumerate(headers):lab=QLabel(text);lab.setProperty('sectionTitle',c==0);grid.addWidget(lab,0,c)
        def limit_row(label, key):
            return (label, *(format_plan_limit(plan, key) for plan in PLAN_ORDER))
        def feature_row(label, key):
            return (label, *("Included" if plan_has_feature(plan, key) else "—" for plan in PLAN_ORDER))
        rows=[
            limit_row('Accounts', LimitKey.MAX_ACCOUNTS),
            limit_row('Source Groups', LimitKey.MAX_SOURCE_GROUPS),
            limit_row('Managed Groups', LimitKey.MAX_TARGET_GROUPS),
            limit_row('Member Pool', LimitKey.MAX_MEMBER_POOL),
            feature_row('Campaigns', FeatureKey.CAMPAIGNS),
            feature_row('Media Posts', FeatureKey.MEDIA_POSTING),
            feature_row('Schedule Once', FeatureKey.SCHEDULE_ONCE),
            feature_row('Recurring Schedule', FeatureKey.RECURRING_SCHEDULE),
            feature_row('Content Calendar', FeatureKey.CONTENT_CALENDAR),
            ('Analytics', 'Basic dashboard', 'Campaign', 'Full'),
            feature_row('Automatic Backup', FeatureKey.AUTO_BACKUP),
            feature_row('App Lock', FeatureKey.APP_LOCK),
            feature_row('Security Audit', FeatureKey.SECURITY_AUDIT),
            limit_row('Devices', LimitKey.MAX_DEVICES),
        ]
        for r,row in enumerate(rows,1):
            for c,text in enumerate(row):lab=QLabel(text);lab.setProperty('secondary',c>0);grid.addWidget(lab,r,c)
        compare.body.addLayout(grid);self.body.addWidget(compare)
        note=QLabel('* Unlimited means no artificial SP Telegram plan limit. Telegram API availability, Telegram permissions/restrictions, database capacity and local computer resources still apply.');note.setWordWrap(True);note.setProperty('muted',True);self.body.addWidget(note)
        self.btn_activate_license.clicked.connect(self._activate);self.btn_refresh_license.clicked.connect(controller.refresh_license);self.btn_license_details.clicked.connect(self._details);self.btn_manage_license_devices.clicked.connect(controller.open_device_manager);self.btn_copy_device_id.clicked.connect(self._copy_device);self.btn_deactivate_device.clicked.connect(self._deactivate_current);self.btn_change_license.clicked.connect(lambda:self._scroll_plans(plans));self._plan_buttons[PlanKey.STARTER].clicked.connect(lambda:self._choose_plan(PlanKey.STARTER));self._plan_buttons[PlanKey.PRO].clicked.connect(lambda:self._choose_plan(PlanKey.PRO));self._plan_buttons[PlanKey.ULTIMATE].clicked.connect(lambda:self._choose_plan(PlanKey.ULTIMATE))
        controller.licenseChanged.connect(lambda *_:self.refresh());controller.deviceListChanged.connect(self._show_devices);controller.upgradeRequested.connect(self._upgrade_requested);self.refresh()
    def refresh(self):
        summary=self.controller.load_license_page();s=summary.state;self.lbl_license_plan.setText(summary.plan_name);self.badge.set_plan(str(s.plan or 'UNLICENSED'));status=str(s.status);self.lbl_license_status.setText(status.replace('_',' ').title());self.lbl_license_status.set_state(status)
        if status==LicenseStatus.UNLICENSED:self.lbl_license_summary.setText('No active license. Activate a trusted license to unlock licensed creation and outgoing features. Existing local data is preserved.')
        elif status==LicenseStatus.OFFLINE_GRACE:self.lbl_license_summary.setText(f'Offline License Mode\nPreviously validated plan remains available until {s.offline_grace_until or "the grace deadline"}.')
        elif status==LicenseStatus.EXPIRED:self.lbl_license_summary.setText(f'License Expired\nExpired: {s.expires_at or "—"}\nYour local data remains stored safely. Renew to restore licensed creation and outgoing features.')
        elif status==LicenseStatus.SUSPENDED:self.lbl_license_summary.setText('License Suspended\nThis license currently requires review. Your local data remains preserved. Refresh the license or review license details.')
        elif status==LicenseStatus.DEVICE_LIMIT:self.lbl_license_summary.setText('Device Limit Reached\nManage an existing device activation before activating this computer. Telegram sessions are not affected.')
        elif status==LicenseStatus.VALIDATION_REQUIRED:self.lbl_license_summary.setText('Online License Verification Required\nConnect to the internet and refresh your license. Existing local data, exports, backups and safety features remain available.')
        else:
            device_usage=summary.usage.get(str(LimitKey.MAX_DEVICES),{'current':0,'limit':summary.device_limit})
            device_text=f"{int(device_usage.get('current',0))} / {'Unlimited' if device_usage.get('limit') is None else int(device_usage.get('limit') or 0)}"
            self.lbl_license_summary.setText(f'Price: ${summary.price_monthly}/month\nExpires: {s.expires_at or "—"}   •   Days Remaining: {summary.days_remaining if summary.days_remaining is not None else "—"}   •   Devices: {device_text}\nLast Verified: {s.last_validated_at or "Never"}   •   License Key: {s.license_key_masked or "—"}')
        self.usage.setVisible(s.plan_key is not None)
        for key,(value,bar) in self._usage_rows.items():
            data=summary.usage.get(key,{"current":0,"limit":0});current=int(data.get('current',0));limit=data.get('limit')
            if limit == 0:
                value.setText('Not included');bar.setVisible(False)
            else:
                value.setText(f'{current:,} / Unlimited' if limit is None else (f'{current:,} / {int(limit):,}  •  Over Plan Limit' if current>int(limit) else f'{current:,} / {int(limit):,}'));bar.setVisible(limit is not None);bar.setMaximum(max(1,int(limit or 1)));bar.setValue(min(current,int(limit or 1)))
        for plan,btn in self._plan_buttons.items():
            current=str(s.plan or '')==plan.value;btn.setText('Current Plan' if current else f'Choose {plan.value.title()}');btn.setEnabled(not current)
        self.btn_deactivate_device.setEnabled(bool(s.license_reference and s.device_id))
        return summary
    def _activate(self):
        d=ActivateLicenseDialog(self.controller.activation_device_summary(), self)
        if d.exec():key,name=d.data();self.controller.activate_license(key,name);d.le_license_key.clear()
    def _details(self):LicenseDetailsDialog(self.controller.load_license_page(),self).exec()
    def _deactivate_current(self):
        summary=self.controller.load_license_page();name=summary.state.device_name or 'Current Device'
        text=f"Deactivate Device?\n\n{name}\n\nThis computer will need to activate the license again before licensed features can be used. Telegram account sessions are separate and will not be deleted or logged out."
        if QMessageBox.question(self,'Deactivate Device',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.controller.deactivate_device()
    def _show_devices(self,devices):
        d=DeviceManagementDialog(devices,self);d.deactivateRequested.connect(self.controller.deactivate_device);d.exec()
    def _copy_device(self):
        from PySide6.QtWidgets import QApplication
        value=self.controller.copy_device_id();QApplication.clipboard().setText(value);self.toastRequested.emit('Masked device ID copied.','Success')
    def _upgrade_requested(self,feature,required):
        if str(feature)=="PLAN_CHANGE":
            try:plan=PlanKey(str(required));cfg=PLAN_CONFIG[plan]
            except (ValueError,KeyError):plan=PlanKey.PRO;cfg=PLAN_CONFIG[plan]
            QMessageBox.information(self,'Trusted Plan Change Required',f"{cfg['name']} is ${cfg['price_monthly']}/month.\n\nPlan changes are controlled by the SP Telegram license service. This desktop application never upgrades itself locally.\n\nUse your purchase/account channel or an administrator-issued updated license, then refresh the license here.")
            return
        d=UpgradePlanDialog(str(self.controller.current_state().plan or 'Unlicensed'),feature or 'Selected feature',required or 'PRO',parent=self);d.viewPlansRequested.connect(lambda:self._scroll_plans(None));d.exec()
    def _choose_plan(self,plan):
        summary=self.controller.load_license_page();current=summary.state.plan_key
        if current==plan:return
        target=PLAN_CONFIG[plan];over=[]
        for key,label in [(LimitKey.MAX_ACCOUNTS,'Accounts'),(LimitKey.MAX_SOURCE_GROUPS,'Source Groups'),(LimitKey.MAX_TARGET_GROUPS,'Managed / Target Groups'),(LimitKey.MAX_MEMBER_POOL,'Members'),(LimitKey.MAX_TEMPLATES,'Templates')]:
            data=summary.usage.get(str(key));limit=target['limits'][key]
            if data and limit is not None and int(data.get('current',0))>int(limit):over.append(f"{label}: {int(data['current']):,} / {int(limit):,}")
        if over:
            text='Your current usage exceeds the selected plan limits:\n\n'+'\n'.join(over)+'\n\nYour existing data will NOT be deleted. New creation/sync may remain limited until usage is within the plan or you upgrade again.\n\nContinue to the trusted plan-change flow?'
            if QMessageBox.question(self,'Plan Limit Warning',text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        {PlanKey.STARTER:self.controller.choose_starter,PlanKey.PRO:self.controller.choose_pro,PlanKey.ULTIMATE:self.controller.choose_ultimate}[plan]()
    def _scroll_plans(self,_):self.scroll.ensureWidgetVisible(self.plans_section,0,12)
