"""Tests for AccountService.remove_account handling of pending-login placeholders.

A "Pending Telegram Login" row is transient: it only exists while a login wizard
is open (or was left behind by an interrupted login). Its activity history is
login-attempt noise, so deletion must not be blocked by has_related_history.
"""

import tempfile
from pathlib import Path

import pytest

from app.database.database import DatabaseManager
from app.database.repositories.account_activity_repository import AccountActivityRepository
from app.database.repositories.account_repository import AccountRepository
from app.models.entities import AccountActivity
from app.services.account_service import AccountService


@pytest.fixture
def db_manager():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    manager = DatabaseManager(path)
    manager.initialize()
    yield manager
    manager.close()
    if path.exists():
        path.unlink()


@pytest.fixture
def service(db_manager):
    repo = AccountRepository(db_manager)
    activity = AccountActivityRepository(db_manager)
    return AccountService(repo, activity, restriction_repository=None)


def _add_activity(service, account_id: int, count: int = 3):
    for i in range(count):
        service.record_activity(account_id, "LOGIN_ATTEMPT", "FAILED", f"attempt {i}")


class TestPendingLoginRemoval:
    def test_pending_login_account_is_deleted_despite_history(self, service):
        account = service.create_login_pending_account(phone="+85512345678")
        _add_activity(service, account.id, count=5)
        assert service.repository.has_related_history(account.id) is True

        mode = service.remove_account(account.id)

        assert mode == "deleted"
        assert service.repository.get_by_id(account.id) is None

    def test_pending_login_placeholder_with_login_required_is_deleted(self, service):
        # Simulate the leftover row the user hit: a placeholder that was marked
        # LOGIN_REQUIRED (session missing) instead of PENDING.
        account = service.create_login_pending_account(phone="+85598765432")
        service.repository.update_fields(account.id, {"authorization_status": "LOGIN_REQUIRED"})
        _add_activity(service, account.id, count=24)

        mode = service.remove_account(account.id)

        assert mode == "deleted"
        assert service.repository.get_by_id(account.id) is None

    def test_authorized_account_with_history_is_disabled_not_deleted(self, service):
        account = service.create_login_pending_account(phone="+85511112222")
        service.repository.update_fields(
            account.id,
            {"authorization_status": "AUTHORIZED", "first_name": "Real User"},
        )
        _add_activity(service, account.id, count=3)
        assert service.repository.has_related_history(account.id) is True

        mode = service.remove_account(account.id)

        assert mode == "disabled"
        assert service.repository.get_by_id(account.id) is not None
        assert service.repository.get_by_id(account.id).is_enabled == 0

    def test_account_without_history_is_deleted(self, service):
        account = service.create_login_pending_account(phone="+85533334444")
        service.repository.update_fields(
            account.id,
            {"authorization_status": "AUTHORIZED", "first_name": "Clean User"},
        )

        mode = service.remove_account(account.id)

        assert mode == "deleted"
        assert service.repository.get_by_id(account.id) is None