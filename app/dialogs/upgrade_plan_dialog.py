from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from app.dialogs.dialog_compat import *
from app.license.license_models import PlanKey
from app.license.plan_config import PLAN_CONFIG
from app.utils.qr_renderer import render_qr_pixmap


class UpgradePlanDialog(QDialog):
    """Trusted KHQR checkout UI.

    The desktop renders a QR payload supplied by the license service. Payment
    status is confirmed server-side against Bakong; clicking/checking locally can
    never grant a plan by itself.
    """

    viewPlansRequested = Signal()

    def __init__(
        self,
        current_plan=None,
        feature_name='Plan change',
        required_plan='PRO',
        usage_warning=None,
        *,
        controller=None,
        parent=None,
    ):
        super().__init__(parent)
        self.controller = controller
        try:
            self.plan = PlanKey(str(required_plan).upper())
        except ValueError:
            self.plan = PlanKey.PRO
        self.invoice_id = ''
        self.claim_token = ''
        self.expires_at = None
        self._checking = False
        self._creating = False

        cfg = PLAN_CONFIG[self.plan]
        self.setWindowTitle('Secure KHQR Checkout')
        self.setMinimumWidth(560)
        self.setObjectName('khqr_checkout_dialog')
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(14)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(f"Upgrade to {cfg['name']}")
        title.setProperty('dialogTitle', True)
        subtitle = QLabel('Secure payment · Verified by the SP Telegram license server')
        subtitle.setProperty('secondary', True)
        title_box.addWidget(title); title_box.addWidget(subtitle)
        top.addLayout(title_box); top.addStretch()
        badge = QLabel('KHQR')
        badge.setProperty('status', 'active')
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMinimumWidth(64)
        top.addWidget(badge)
        root.addLayout(top)

        info = QFrame(); info.setProperty('pricingCard', True)
        info_layout = QHBoxLayout(info); info_layout.setContentsMargins(16, 14, 16, 14)
        left = QVBoxLayout()
        self.lbl_plan = QLabel(cfg['name']); self.lbl_plan.setProperty('sectionTitle', True)
        self.lbl_price = QLabel(f"${cfg['price_monthly']} / 30 days"); self.lbl_price.setProperty('summaryValue', True)
        self.lbl_current = QLabel(f"Current: {current_plan or 'No active license'}"); self.lbl_current.setProperty('secondary', True)
        left.addWidget(self.lbl_plan); left.addWidget(self.lbl_price); left.addWidget(self.lbl_current)
        info_layout.addLayout(left); info_layout.addStretch()
        root.addWidget(info)

        if usage_warning:
            warn = QLabel(usage_warning); warn.setWordWrap(True); warn.setProperty('warning', True); root.addWidget(warn)

        self.qr_frame = QFrame(); self.qr_frame.setProperty('sectionCard', True)
        ql = QVBoxLayout(self.qr_frame); ql.setContentsMargins(18, 18, 18, 18); ql.setSpacing(10)
        self.lbl_qr = QLabel('Creating secure invoice…')
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setMinimumSize(280, 280)
        ql.addWidget(self.lbl_qr, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_amount = QLabel('')
        self.lbl_amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_amount.setProperty('summaryValue', True)
        ql.addWidget(self.lbl_amount)
        self.lbl_invoice = QLabel('')
        self.lbl_invoice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_invoice.setProperty('muted', True)
        ql.addWidget(self.lbl_invoice)
        root.addWidget(self.qr_frame)

        status_row = QHBoxLayout()
        self.lbl_status_dot = QLabel('●')
        self.lbl_status = QLabel('Preparing KHQR…')
        self.lbl_status.setProperty('secondary', True)
        self.lbl_timer = QLabel('')
        self.lbl_timer.setProperty('muted', True)
        status_row.addWidget(self.lbl_status_dot); status_row.addWidget(self.lbl_status); status_row.addStretch(); status_row.addWidget(self.lbl_timer)
        root.addLayout(status_row)

        help_text = QLabel('Scan with a KHQR-compatible banking app. The app activates only after the server verifies the Bakong transaction amount, currency, receiver and transaction hash.')
        help_text.setWordWrap(True); help_text.setProperty('secondary', True); root.addWidget(help_text)

        buttons = QHBoxLayout()
        self.btn_view_plans = QPushButton('Back to Plans')
        self.btn_view_plans.setObjectName('btn_upgrade_view_plans')
        self.btn_check = QPushButton('Check Payment')
        self.btn_check.setProperty('primary', True)
        self.btn_check.setEnabled(False)
        self.btn_close = QPushButton('Close')
        buttons.addWidget(self.btn_view_plans); buttons.addStretch(); buttons.addWidget(self.btn_close); buttons.addWidget(self.btn_check)
        root.addLayout(buttons)

        self.btn_close.clicked.connect(self.reject)
        self.btn_view_plans.clicked.connect(self._back_to_plans)
        self.btn_check.clicked.connect(self.check_payment)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(7000)
        self.poll_timer.timeout.connect(self.check_payment)
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)

        if self.controller:
            self.controller.paymentInvoiceReady.connect(self._invoice_ready)
            self.controller.paymentStatusChanged.connect(self._payment_status)
            self.controller.paymentCompleted.connect(self._payment_complete)
            self.controller.licenseError.connect(self._payment_error)
            QTimer.singleShot(0, self._resume_or_create)
        else:
            self._payment_error('License controller is unavailable.')

    def _resume_or_create(self):
        pending = self.controller.get_pending_payment_invoice(self.plan.value) if self.controller else None
        if pending:
            self._invoice_ready(pending)
            self.lbl_status.setText('Resumed pending KHQR payment')
        else:
            self.create_invoice()

    def create_invoice(self):
        if self._creating or not self.controller:
            return
        self._creating = True
        self.btn_check.setEnabled(False)
        self.lbl_status.setText('Creating secure KHQR invoice…')
        self.controller.create_payment_invoice(self.plan.value)

    def check_payment(self):
        if not self.controller or not self.invoice_id or not self.claim_token or self._checking:
            return
        self._checking = True
        self.btn_check.setEnabled(False)
        self.lbl_status.setText('Checking Bakong payment…')
        self.controller.check_payment_invoice(self.invoice_id, self.claim_token)

    def _invoice_ready(self, data):
        # Ignore another checkout if multiple windows somehow exist.
        if str(data.get('plan') or '').upper() != self.plan.value:
            return
        self._creating = False
        self.invoice_id = str(data.get('invoice_id') or '')
        self.claim_token = str(data.get('claim_token') or '')
        qr = str(data.get('khqr_payload') or '')
        if not self.invoice_id or not self.claim_token or not qr:
            self._payment_error('The server returned an incomplete payment invoice.')
            return
        self.lbl_qr.setText('')
        self.lbl_qr.setPixmap(render_qr_pixmap(qr, 280))
        amount = data.get('amount')
        currency = str(data.get('currency') or 'USD')
        self.lbl_amount.setText(f"Pay {amount} {currency}")
        self.lbl_invoice.setText(f"Invoice {data.get('invoice_code') or self.invoice_id[:12]}")
        self.expires_at = self._parse_time(data.get('expires_at'))
        self.lbl_status.setText('Waiting for payment')
        self.btn_check.setEnabled(True)
        self.poll_timer.start()
        self.clock_timer.start()
        self._update_clock()

    def _payment_status(self, data):
        if self.invoice_id and str(data.get('invoice_id') or '') != self.invoice_id:
            return
        self._checking = False
        status = str(data.get('status') or 'PENDING').upper()
        if status == 'PENDING':
            self.lbl_status.setText('Waiting for payment')
            self.btn_check.setEnabled(True)
        elif status == 'EXPIRED':
            self.lbl_status.setText('Invoice expired. Close and create a new payment.')
            self.btn_check.setEnabled(False)
            self.poll_timer.stop()
        elif status == 'PAID':
            self._payment_complete(data)
        else:
            self.lbl_status.setText(status.replace('_', ' ').title())
            self.btn_check.setEnabled(True)

    def _payment_complete(self, data):
        if self.invoice_id and str(data.get('invoice_id') or '') != self.invoice_id:
            return
        self._checking = False
        self.poll_timer.stop(); self.clock_timer.stop()
        self.lbl_status_dot.setText('✓')
        self.lbl_status.setText(f"Payment verified · {self.plan.value.title()} activated")
        self.lbl_timer.setText('Complete')
        self.btn_check.setText('Activated')
        self.btn_check.setEnabled(False)
        QTimer.singleShot(1200, self.accept)

    def _payment_error(self, message):
        self._creating = False; self._checking = False
        self.lbl_status.setText(str(message))
        self.btn_check.setEnabled(bool(self.invoice_id))

    @staticmethod
    def _parse_time(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    def _update_clock(self):
        if not self.expires_at:
            self.lbl_timer.setText('')
            return
        seconds = max(0, int((self.expires_at - datetime.now(timezone.utc)).total_seconds()))
        hours, rest = divmod(seconds, 3600); minutes, sec = divmod(rest, 60)
        self.lbl_timer.setText(f"Expires in {hours:02d}:{minutes:02d}:{sec:02d}")
        if seconds <= 0:
            self.poll_timer.stop(); self.btn_check.setEnabled(False); self.lbl_status.setText('Invoice expired')

    def _back_to_plans(self):
        self.viewPlansRequested.emit()
        self.reject()

    def closeEvent(self, event):
        self.poll_timer.stop(); self.clock_timer.stop()
        super().closeEvent(event)


if not hasattr(UpgradePlanDialog, 'Accepted'):
    UpgradePlanDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(UpgradePlanDialog, 'Rejected'):
    UpgradePlanDialog.Rejected = QDialog.DialogCode.Rejected
