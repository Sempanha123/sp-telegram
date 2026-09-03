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
    plansChanged = Signal(object)
    promotionApplied = Signal(object)
    toast_requested = Signal(str, str)
    upgradeRequested = Signal(str, str)
    licenseError = Signal(str)

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
        self._payment_plans: dict[str, dict] = {}
        if worker:
            worker.operationCompleted.connect(self._done)
            worker.operationFailed.connect(self._failed)
            worker.finished.connect(self._on_worker_finished)

    def load_license_page(self):
        return self.service.get_license_summary()

    def current_state(self):
        return self.service.get_current_license()

    def activate_license(self, key, device_name=None):
        return self._submit(self.service.activate(key, device_name), "license_activate", lambda r: self._activated(r))

    def refresh_license(self):
        return self._submit(self.service.refresh(), "license_refresh", self._refreshed)

    def refresh_if_due(self):
        if self.service.needs_online_validation():
            return self.refresh_license()
        return None

    def open_plan_details(self):
        return self.service.get_license_summary()

    def open_upgrade_dialog(self, feature_key="", required_plan=""):
        self.upgradeRequested.emit(str(feature_key), str(required_plan))
        return (feature_key, required_plan)

    def open_device_manager(self):
        return self._submit(self.service.get_devices(), "license_devices", self._devices)

    def deactivate_device(self, device_id=None):
        state = self.service.get_current_license()
        if device_id and state.device_id and device_id != state.device_id:
            return self._submit(self.service.deactivate_device(device_id), "license_device_deactivate", lambda r: self._device_deactivated(r))
        return self._submit(self.service.deactivate_current_device(), "license_device_deactivate", lambda r: self._changed(self.service.get_current_license(), "Device deactivated."))

    def activation_device_summary(self):
        metadata = self.service.device_manager.metadata()
        return {**metadata, "masked_device_id": self.service.device_manager.mask_device_id(metadata.get("device_id"))}

    def copy_device_id(self):
        return self.service.device_manager.mask_device_id(self.service.device_manager.get_device_id())

    def choose_starter(self): return self._choose("STARTER")
    def choose_pro(self): return self._choose("PRO")
    def choose_ultimate(self): return self._choose("ULTIMATE")

    def _choose(self, plan):
        # Same-plan checkout is intentional: it lets existing customers renew
        # their current plan or apply promotion/free-trial codes.
        self.upgradeRequested.emit("PLAN_CHANGE", plan)
        return plan

    # -------- server plan pricing --------
    def refresh_payment_plans(self):
        return self._submit(self.service.api.get_payment_plans(), "license_plans", self._plans_ready)

    def payment_plan(self, plan: str):
        return self._payment_plans.get(str(plan or "").upper())

    def _plans_ready(self, rows):
        from app.license.license_models import PlanKey
        from app.license.plan_config import PLAN_CONFIG
        mapped: dict[str, dict] = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").upper()
            if not code:
                continue
            mapped[code] = dict(row)
            try:
                key = PlanKey(code)
            except ValueError:
                continue
            if row.get("price_monthly") is not None:
                PLAN_CONFIG[key]["price_monthly"] = float(row["price_monthly"])
            if row.get("device_limit") is not None:
                PLAN_CONFIG[key]["device_limit"] = int(row["device_limit"])
        self._payment_plans = mapped
        self.plansChanged.emit(mapped)
        return mapped

    # -------- promotions --------
    def apply_promotion(self, code: str, plan: str):
        return self._submit(self._apply_promotion(code, plan), "license_promotion_apply", self._promotion_applied)

    async def _apply_promotion(self, code: str, plan: str):
        state = self.service.get_current_license()
        device = self.service.device_manager.metadata(state.device_name)
        data = await self.service.api.apply_promotion(str(code).strip(), str(plan).upper(), device)
        if str(data.get("action") or "").upper() == "ACTIVATED":
            license_key = str(data.get("license_key") or "").strip()
            if not license_key:
                raise RuntimeError("The promotion server did not return an activation key.")
            await self.service.activate(license_key, state.device_name)
            data.pop("license_key", None)
            data["license_state"] = self.service.get_current_license()
        return data

    def _promotion_applied(self, data):
        action = str(data.get("action") or "").upper()
        if action == "ACTIVATED":
            self._emit_all(self.service.get_current_license())
            self.toast_requested.emit(f"Promotion redeemed. {data.get('trial_days', '')} day free access activated.", "Success")
        elif action == "DISCOUNT":
            self.toast_requested.emit(f"Promotion {data.get('promotion_code', '')} applied.", "Success")
        self.promotionApplied.emit(data)
        return data

    # -------- KHQR --------
    def get_pending_payment_invoice(self, plan: str | None = None):
        storage = getattr(self.service.device_manager, "storage", None)
        if storage is None:
            return None
        try:
            raw = storage.get_secret(self.PAYMENT_STORAGE_KEY)
            data = json.loads(raw) if raw else None
            if not isinstance(data, dict):
                return None
            if plan and str(data.get("plan") or "").upper() != str(plan).upper():
                return None
            expires = data.get("expires_at")
            if expires:
                deadline = datetime.fromisoformat(str(expires).replace("Z", "+00:00")).astimezone(timezone.utc)
                if deadline <= datetime.now(timezone.utc):
                    self.clear_pending_payment_invoice()
                    return None
            return data
        except Exception:
            return None

    def clear_pending_payment_invoice(self):
        storage = getattr(self.service.device_manager, "storage", None)
        if storage is None:
            return
        try:
            storage.delete_secret(self.PAYMENT_STORAGE_KEY)
        except Exception:
            pass

    def _save_pending_payment_invoice(self, data):
        storage = getattr(self.service.device_manager, "storage", None)
        if storage is None:
            return
        try:
            storage.set_secret(self.PAYMENT_STORAGE_KEY, json.dumps(data, separators=(",", ":"), default=str))
        except Exception:
            pass

    def create_payment_invoice(self, plan: str, promotion_code: str | None = None):
        return self._submit(self._create_payment_invoice(plan, promotion_code), "license_payment_create", self._payment_invoice_ready)

    def check_payment_invoice(self, invoice_id: str, claim_token: str):
        return self._submit(self._check_payment_invoice(invoice_id, claim_token), "license_payment_check", self._payment_checked)

    async def _create_payment_invoice(self, plan: str, promotion_code: str | None = None):
        from app.license.license_models import LicenseStatus
        state = self.service.get_current_license()
        device = self.service.device_manager.metadata(state.device_name)
        license_reference = state.license_reference or None
        if str(state.status) == LicenseStatus.INVALID:
            license_reference = None
        if promotion_code:
            return await self.service.api.create_payment_invoice(str(plan).upper(), license_reference, device, str(promotion_code).strip())
        return await self.service.api.create_payment_invoice(str(plan).upper(), license_reference, device)

    async def _check_payment_invoice(self, invoice_id: str, claim_token: str):
        state = self.service.get_current_license()
        device = self.service.device_manager.metadata(state.device_name)
        data = await self.service.api.check_payment_invoice(invoice_id, claim_token, device)
        if str(data.get("status") or "").upper() == "PAID":
            license_key = str(data.get("license_key") or "").strip()
            if license_key:
                await self.service.activate(license_key, state.device_name)
                data.pop("license_key", None)
            elif self.service.get_current_license().license_reference:
                await self.service.refresh()
            data["license_state"] = self.service.get_current_license()
        return data

    def _payment_invoice_ready(self, data):
        self._save_pending_payment_invoice(data)
        self.paymentInvoiceReady.emit(data)
        self.paymentStatusChanged.emit(data)
        return data

    def _payment_checked(self, data):
        if str(data.get("status") or "").upper() == "PAID":
            self.clear_pending_payment_invoice()
            self._emit_all(self.service.get_current_license())
            self.paymentCompleted.emit(data)
            self.toast_requested.emit("Payment received. Your license is active.", "Success")
        else:
            self.paymentStatusChanged.emit(data)
        return data

    def _activated(self, state):
        self.licenseActivated.emit(state)
        self._emit_all(state)
        self.toast_requested.emit("License activated successfully.", "Success")

    def _refreshed(self, state):
        from app.license.license_models import LicenseStatus
        self._emit_all(state)
        if str(state.status) == LicenseStatus.OFFLINE_GRACE:
            self.toast_requested.emit("License service is unavailable. Offline grace is active.", "Warning")
        elif str(state.status) == LicenseStatus.VALIDATION_REQUIRED:
            self.toast_requested.emit("Online license verification is required.", "Warning")
        else:
            self.toast_requested.emit("License refreshed.", "Success")
        return state

    def _changed(self, state, message="License updated."):
        self._emit_all(state)
        self.toast_requested.emit(message, "Success")
        return state

    def _devices(self, items):
        self.deviceListChanged.emit(items)
        return items

    def _device_deactivated(self, result):
        self._changed(self.service.get_current_license(), "Device deactivated.")
        self.open_device_manager()
        return result

    def _emit_all(self, state):
        self.licenseChanged.emit(state)
        self.licenseStatusChanged.emit(str(state.status))
        self.planChanged.emit(str(state.plan or ""))
        self.featuresChanged.emit()
        self.usageChanged.emit()

    def _submit(self, coro, operation, success):
        if self.worker is None:
            self._error(Exception("License background runtime is unavailable."), validation_failure=False)
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
        if entry:
            entry[0](result)

    def _failed(self, token, account_id, message):
        if token not in self._handlers:
            return
        entry = self._handlers.pop(token, None)
        operation = entry[1] if entry else ""
        self._emit_all(self.service.get_current_license())
        is_validation = operation in ("license_activate", "license_refresh")
        self._error(Exception(message), validation_failure=is_validation)

    def _error(self, exc, validation_failure=False):
        message = str(exc) or "Could not complete the license operation."
        if validation_failure:
            self.licenseValidationFailed.emit(message)
        else:
            self.licenseError.emit(message)
        self.toast_requested.emit(message, "Error")

    def _on_worker_finished(self) -> None:
        pending = dict(self._handlers)
        self._handlers.clear()
        for _token, (_success, operation) in pending.items():
            is_validation = operation in ("license_activate", "license_refresh")
            message = "The Telegram worker stopped unexpectedly."
            if is_validation:
                self.licenseValidationFailed.emit(message)
            else:
                self.licenseError.emit(message)
        if pending:
            self.toast_requested.emit("The Telegram worker stopped. Pending license operations were cancelled.", "Warning")
