"""Tests for AppLockDialog - verifying it cannot be bypassed."""

import pytest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest

from app.dialogs.app_lock_dialog import AppLockDialog


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance() or QApplication([])
    yield app


class TestAppLockDialog:
    """Tests for the application lock dialog security."""

    def test_reject_does_not_close_dialog(self, qapp):
        """reject() (Escape key) should not close the dialog."""
        service = MagicMock()
        service.unlock.return_value = False
        dialog = AppLockDialog(service)
        dialog.show()

        # Call reject (simulates Escape key)
        dialog.reject()

        # Dialog should still be visible/open
        assert dialog.isVisible()
        assert not dialog.result()

    def test_close_event_ignored(self, qapp):
        """closeEvent (window X button) should be ignored."""
        service = MagicMock()
        service.unlock.return_value = False
        dialog = AppLockDialog(service)
        dialog.show()

        # Create a close event
        event = QEvent(QEvent.Type.Close)
        dialog.closeEvent(event)

        # Event should be ignored
        assert event.isAccepted() is False

    def test_successful_unlock_closes_dialog(self, qapp):
        """Correct password should close dialog with Accepted result."""
        service = MagicMock()
        service.unlock.return_value = True
        dialog = AppLockDialog(service)
        dialog.show()

        # Enter correct password
        dialog.le_password.setText("correct_password")
        dialog._unlock()

        # Dialog should accept
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_incorrect_password_shows_error(self, qapp):
        """Incorrect password should show error and not close."""
        service = MagicMock()
        service.unlock.return_value = False
        dialog = AppLockDialog(service)
        dialog.show()

        # Enter incorrect password
        dialog.le_password.setText("wrong_password")
        dialog._unlock()

        # Dialog should still be open
        assert dialog.isVisible()
        assert dialog.lbl_error.text() == "Incorrect application-lock password."

    def test_exception_shows_storage_error(self, qapp):
        """Exception during unlock should show storage error."""
        service = MagicMock()
        service.unlock.side_effect = Exception("Keyring error")
        dialog = AppLockDialog(service)
        dialog.show()

        dialog.le_password.setText("any_password")
        dialog._unlock()

        # Should show storage error
        assert "Secure credential storage is unavailable" in dialog.lbl_error.text()