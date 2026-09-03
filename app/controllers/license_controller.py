from __future__ import annotations

import json
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal


class LicenseController(QObject):
    PAYMENT_STORAGE_KEY = "license_pending_payment_v1"
    licenseChanged = Signal(object)
    licenseActivated = Signal(object)
    licenseValidationFailed = Signal(str)
    licenseStatusChanged = Signal(str)
    planChanged = Signal(str)
    featuresChanged = Signal()
    usageChanged = Signal()
    deviceListChanged = Signal(list)
    toast_requested = Signal(str, str)
    upgradeRequested = Signal(str, str)
    licenseError = Signal(str)

    # KHQR checkout signals. Invoice data never contains a Bakong token; it only
    # contains the public QR payload, invoice id and one-time claim token.
    paymentInvoiceReady = Signal(object)
    paymentStatusChanged = Signal(object)
    paymentCompleted = Signal(object)

    def __init__(self, service, feature_gate, limit_service, worker=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.feature_gate = feature_gate
        self.limit_service = limit_service
        self.worker = worker
        self._handlers = {}
        if worker:
            worker.operationCompleted.connect(self._done)
            worker.operationFailed.connect(self._failed)
            worker.finished.connect(self._on_worker_finished)

    def load_license_page(self): return self.service.get_license_summary()
    def current_state(self): return self.service.get_current_license()
    def activate_license(self, key, device_name=None): return self._submit(self.service.activate(key, device_name), 'license_activate', lambda r: self._activated(r))
    def refresh_license(self): return self._submit(self.service.refresh(), 'license_refresh', self._refreshed)

    def refresh_if_due(self):
        if self.service.needs_online_validation(): return self.refresh_license()
        return None

    def open_plan_details(self): return self.service.get_license_summary()

    def open_upgrade_dialog(self, feature_key='', required_plan=''):
        self.upgradeRequested.emit(str(feature_key), str(required_plan))
        return (feature_key, required_plan)

    def open_device_manager(self): return self._submit(self.service.get_devices(), 'license_devices', self._devices)

    def deactivate_device(self, device_id=None):
        state = self.service.get_current_license()
        if device_id and state.device_id and device_id != state.device_id:
            return self._submit(self.service.deactivate_device(device_id), 'license_device_deactivate', lambda r: self._device_deactivated(r))
        return self._submit(self.service.deactivate_current_device(), 'license_device_deactivate', lambda r: self._changed(self.service.get_current_license(), 'Device deactivated.'))

    def activation_device_summary(self):
        metadata = self.service.device_manager.metadata()
        return {**metadata, "masked_device_id": self.service.device_manager.mask_device_id(metadata.get("device_id"))}

    def copy_device_id(self): return self.service.device_manager.mask_device_id(self.service.device_manager.get_device_id())
    def choose_starter(self): return self._choose('STARTER')
    def choose_pro(self): return self._choose('PRO')
    def choose_ultimate(self): return self._choose('ULTIMATE')

    def _choose(self, plan):
        current = str(self.service.get_current_license().plan or '')
        if current == plan:
            self.toast_requested.emit(f'SP Telegram {plan.title()} is your current plan.', 'Info')
            return plan
        self.upgradeRequested.emit('PLAN_CHANGE', plan)
        return plan

    # ---------------- KHQR payment flow ----------------
    def get_pending_payment_invoice(self, plan: str | None = None):
        storage = getattr(self.service.device_manager, 'storage', None)
        if storage is None:
            return None
        try:
            raw = storage.get_secret(self.PAYMENT_STORAGE_KEY)
            data = json.loads(raw) if raw else None
            if not isinstance(data, dict):
                return None
            if plan and str(data.get('plan') or '').upper() != str(plan).upper():
                return None
            expires = data.get('expires_at')
            if expires:
                deadline = datetime.fromisoformat(str(expires).replace('Z', '+00:00')).astimezone(timezone.utc)
                if deadline <= datetime.now(timezone.utc):
                    self.clear_pending_payment_invoice()
                    return None
            return data
        except Exception:
            return None

    def clear_pending_payment_invoice(self):
        storage = getattr(self.service.device_manager, 'storage', None)
        if storage is None:
            return
        try:
            storage.delete_secret(self.PAYMENT_STORAGE_KEY)
        except Exception:
            pass

    def _save_pending_payment_invoice(self, data):
        storage = getattr(self.service.device_manager, 'storage', None)
        if storage is None:
            return
        try:
            # Includes the one-time claim token, so use Windows Credential
            # Manager/keyring rather than SQLite or plaintext settings.
            storage.set_secret(self.PAYMENT_STORAGE_KEY, json.dumps(data, separators=(',', ':'), default=str))
        except Exception:
            pass

    def create_payment_invoice(self, plan: str):
        return self._submit(self._create_payment_invoice(plan), 'license_payment_create', self._payment_invoice_ready)

    def check_payment_invoice(self, invoice_id: str, claim_token: str):
        return self._submit(self._check_payment_invoice(invoice_id, claim_token), 'license_payment_check', self._payment_checked)

    async def _create_payment_invoice(self, plan: str):
        from app.license.license_models import LicenseStatus

        state = self.service.get_current_license()
        device = self.service.device_manager.metadata(state.device_name)

        # An INVALID reference may belong to an old/dev license server.
        # Treat it as a fresh purchase instead of attempting a renewal.
        license_reference = state.license_reference or None

        if str(state.status) == LicenseStatus.INVALID:
            license_reference = None

        return await self.service.api.create_payment_invoice(
            str(plan).upper(),
            license_reference,
            device,
        )

    async def _check_payment_invoice(self, invoice_id: str, claim_token: str):
        state = self.service.get_current_license()
        device = self.service.device_manager.metadata(state.device_name)
        data = await self.service.api.check_payment_invoice(invoice_id, claim_token, device)
        if str(data.get('status') or '').upper() == 'PAID':
            license_key = str(data.get('license_key') or '').strip()
            if license_key:
                # A newly purchased license is returned only to the holder of
                # the invoice claim token, then immediately activated through
                # the normal signed-entitlement flow.
                await self.service.activate(license_key, state.device_name)
                data.pop('license_key', None)  # do not retain plaintext in UI state
            elif self.service.get_current_license().license_reference:
                await self.service.refresh()
            data['license_state'] = self.service.get_current_license()
        return data

    def _payment_invoice_ready(self, data):
        self._save_pending_payment_invoice(data)
        self.paymentInvoiceReady.emit(data)
        self.paymentStatusChanged.emit(data)
        return data

    def _payment_checked(self, data):
        if str(data.get('status') or '').upper() == 'PAID':
            self.clear_pending_payment_invoice()
            self._emit_all(self.service.get_current_license())
            self.paymentCompleted.emit(data)
            self.toast_requested.emit('Payment received. Your license is active.', 'Success')
        else:
            self.paymentStatusChanged.emit(data)
        return data

    # ---------------- existing license state ----------------
    def _activated(self, state):
        self.licenseActivated.emit(state)
        self._emit_all(state)
        self.toast_requested.emit('License activated successfully.', 'Success')

    def _refreshed(self, state):
        from app.license.license_models import LicenseStatus
        self._emit_all(state)
        if str(state.status) == LicenseStatus.OFFLINE_GRACE:
            self.toast_requested.emit('License service is unavailable. Offline grace is active.', 'Warning')
        elif str(state.status) == LicenseStatus.VALIDATION_REQUIRED:
            self.toast_requested.emit('Online license verification is required.', 'Warning')
        else:
            self.toast_requested.emit('License refreshed.', 'Success')
        return state

    def _changed(self, state, message='License updated.'):
        self._emit_all(state)
        self.toast_requested.emit(message, 'Success')
        return state

    def _devices(self, items): self.deviceListChanged.emit(items); return items

    def _device_deactivated(self, result):
        self._changed(self.service.get_current_license(), 'Device deactivated.')
        self.open_device_manager()
        return result

    def _emit_all(self, state):
        self.licenseChanged.emit(state)
        self.licenseStatusChanged.emit(str(state.status))
        self.planChanged.emit(str(state.plan or ''))
        self.featuresChanged.emit()
        self.usageChanged.emit()

    def _submit(self, coro, operation, success):
        if self.worker is None:
            self._error(Exception('License background runtime is unavailable.'), validation_failure=False)
            return None
        try:
            token = self.worker.submit_coroutine(coro, operation=operation, account_id=0)
            self._handlers[token] = (success, operation)
            return token
        except Exception as exc:
            try:
                coro.close()
            except Exception:
                pass
            self._error(exc, validation_failure=False)
            return None

    def _done(self, token, result):
        entry = self._handlers.pop(token, None)
        if entry: entry[0](result)

    def _failed(self, token, account_id, message):
        if token not in self._handlers:
            return
        entry = self._handlers.pop(token, None)
        operation = entry[1] if entry else ''
        self._emit_all(self.service.get_current_license())
        is_validation = operation in ('license_activate', 'license_refresh')
        self._error(Exception(message), validation_failure=is_validation)

    def _error(self, exc, validation_failure=False):
        message = str(exc) or 'Could not complete the license operation.'
        if validation_failure:
            self.licenseValidationFailed.emit(message)
        else:
            self.licenseError.emit(message)
        self.toast_requested.emit(message, 'Error')

    def _on_worker_finished(self) -> None:
        pending = dict(self._handlers)
        self._handlers.clear()
        for _token, (_success, operation) in pending.items():
            is_validation = operation in ('license_activate', 'license_refresh')
            message = 'The Telegram worker stopped unexpectedly.'
            if is_validation:
                self.licenseValidationFailed.emit(message)
            else:
                self.licenseError.emit(message)
        if pending:
            self.toast_requested.emit('The Telegram worker stopped. Pending license operations were cancelled.', 'Warning')
