"""Tests for LicenseController - verifying proper error signal routing."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.controllers.license_controller import LicenseController


class MockLicenseService:
    """Mock license service for testing."""
    def __init__(self):
        self.device_manager = MagicMock()
        self.device_manager.get_device_id.return_value = "test-device-id"
        self.device_manager.mask_device_id.return_value = "test-device-id-masked"
        self.device_manager.metadata.return_value = {"device_id": "test-device-id"}
    
    def get_license_summary(self):
        return MagicMock()
    
    def get_current_license(self):
        state = MagicMock()
        state.status = MagicMock(value="ACTIVE")
        state.plan = MagicMock(value="STARTER")
        state.device_id = "test-device-id"
        return state
    
    def activate(self, key, device_name=None):
        return AsyncMock()
    
    def refresh(self):
        return AsyncMock()
    
    def needs_online_validation(self):
        return False
    
    def get_devices(self):
        return AsyncMock()
    
    def deactivate_device(self, device_id):
        return AsyncMock()
    
    def deactivate_current_device(self):
        return AsyncMock()


class MockWorker(QObject):
    """Mock background worker."""
    operationCompleted = Signal(object, object)
    operationFailed = Signal(object, object, str)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token_counter = 0

    def submit_coroutine(self, coro, operation, account_id):
        self._token_counter += 1
        return f"test-token-{self._token_counter}"


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance() or QApplication([])
    yield app


class TestLicenseController:
    """Tests for LicenseController error signal routing."""

    def setup_method(self):
        self.service = MockLicenseService()
        self.feature_gate = MagicMock()
        self.limit_service = MagicMock()
        self.worker = MockWorker()
        self.controller = LicenseController(
            self.service, self.feature_gate, self.limit_service, self.worker
        )

    def test_validation_failure_emits_license_validation_failed(self, qapp):
        """License validation failures should emit licenseValidationFailed."""
        validation_error_received = []
        self.controller.licenseValidationFailed.connect(validation_error_received.append)
        
        # Direct call to _error with validation_failure=True
        self.controller._error(Exception("Invalid license key"), validation_failure=True)
        
        assert len(validation_error_received) == 1
        assert validation_error_received[0] == "Invalid license key"

    def test_non_validation_error_emits_license_error_not_validation(self, qapp):
        """Non-validation errors should emit licenseError, not licenseValidationFailed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)
        
        # Direct call to _error with validation_failure=False (default)
        self.controller._error(Exception("Network error"), validation_failure=False)
        
        assert len(validation_errors) == 0
        assert len(generic_errors) == 1
        assert generic_errors[0] == "Network error"

    def test_worker_unavailable_emits_generic_error(self, qapp):
        """Worker unavailable should emit licenseError, not validation failed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)
        
        # Create controller without worker
        controller_no_worker = LicenseController(
            self.service, self.feature_gate, self.limit_service, worker=None
        )
        controller_no_worker.licenseValidationFailed.connect(validation_errors.append)
        controller_no_worker.licenseError.connect(generic_errors.append)
        
        controller_no_worker._submit(AsyncMock(), "test_op", lambda r: None)
        
        assert len(validation_errors) == 0
        assert len(generic_errors) == 1
        assert "background runtime is unavailable" in generic_errors[0]

    def test_activate_license_failure_is_validation_failure(self, qapp):
        """License activation failure should emit licenseValidationFailed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)

        # Manually trigger _submit with license_activate operation, then invoke _failed
        token = self.controller._submit(
            AsyncMock(), 'license_activate', lambda r: None
        )
        assert token is not None, "_submit should return a token"

        # Simulate worker failure for this token
        self.controller._failed(token, 0, 'Invalid license key')

        assert len(validation_errors) == 1, f"Expected 1 validation error, got {len(validation_errors)}"
        assert validation_errors[0] == 'Invalid license key'
        assert len(generic_errors) == 0, f"Expected 0 generic errors, got {len(generic_errors)}"

    def test_device_listing_failure_emits_license_error(self, qapp):
        """Device listing failure should emit licenseError, not licenseValidationFailed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)

        # Submit device listing operation
        token = self.controller._submit(
            AsyncMock(), 'license_devices', lambda r: None
        )
        assert token is not None

        # Simulate worker failure for device listing
        self.controller._failed(token, 0, 'Failed to fetch device list')

        assert len(validation_errors) == 0, f"Expected 0 validation errors, got {len(validation_errors)}"
        assert len(generic_errors) == 1, f"Expected 1 generic error, got {len(generic_errors)}"
        assert generic_errors[0] == 'Failed to fetch device list'

    def test_device_deactivate_failure_emits_license_error(self, qapp):
        """Device deactivation failure should emit licenseError, not licenseValidationFailed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)

        # Submit device deactivation operation
        token = self.controller._submit(
            AsyncMock(), 'license_device_deactivate', lambda r: None
        )
        assert token is not None

        # Simulate worker failure
        self.controller._failed(token, 0, 'Device deactivation failed')

        assert len(validation_errors) == 0
        assert len(generic_errors) == 1
        assert generic_errors[0] == 'Device deactivation failed'

    def test_refresh_license_failure_is_validation_failure(self, qapp):
        """License refresh failure should emit licenseValidationFailed."""
        validation_errors = []
        generic_errors = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)

        token = self.controller._submit(
            AsyncMock(), 'license_refresh', lambda r: None
        )
        assert token is not None

        self.controller._failed(token, 0, 'Refresh failed')

        assert len(validation_errors) == 1
        assert validation_errors[0] == 'Refresh failed'
        assert len(generic_errors) == 0

    def test_worker_finished_drains_pending_handlers(self, qapp):
        """BUG-017: worker.finished must drain pending handlers so _handlers
        never grows unboundedly after a worker crash."""
        validation_errors = []
        generic_errors = []
        toasts = []
        self.controller.licenseValidationFailed.connect(validation_errors.append)
        self.controller.licenseError.connect(generic_errors.append)
        self.controller.toast_requested.connect(lambda m, lvl: toasts.append((m, lvl)))

        # Submit two pending operations (one validation, one generic).
        token1 = self.controller._submit(AsyncMock(), 'license_activate', lambda r: None)
        token2 = self.controller._submit(AsyncMock(), 'license_devices', lambda r: None)
        assert token1 is not None and token2 is not None
        assert len(self.controller._handlers) == 2

        # Simulate the worker thread stopping unexpectedly.
        self.controller._on_worker_finished()

        # Handlers must be drained.
        assert len(self.controller._handlers) == 0
        # Each pending operation must produce an error signal.
        assert len(validation_errors) == 1
        assert len(generic_errors) == 1
        assert 'stopped unexpectedly' in validation_errors[0]
        assert 'stopped unexpectedly' in generic_errors[0]
        # A single warning toast is emitted for the batch.
        assert len(toasts) == 1
        assert toasts[0][1] == 'Warning'
