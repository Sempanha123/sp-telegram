"""Regression tests for the campaign creation workflow.

Covers the user-verified bug where clicking "New Campaign" always created a
row with Status=Draft even when the user did not choose "Save Draft", and the
generic "The operation could not be completed..." error on invalid input.

Root cause: ``CreateCampaignDialog.data()`` hard-coded ``status='DRAFT'`` for
every finish mode. The workflow now maps explicit final actions to explicit
states (DRAFT / READY / SCHEDULED) and validates with specific errors.
"""

import pytest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from app.dialogs.create_campaign_dialog import CreateCampaignDialog
from app.models.entities import TelegramGroup, GroupAccount, Campaign
from app.services.campaign_service import CampaignService


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_group(title="Target Group", gid=10):
    g = TelegramGroup(id=gid, title=title, username="target", group_type="SUPERGROUP", is_managed=1)
    return g


def _make_mapping(account_id=5, can_post=True, can_send_media=True, is_primary=True):
    m = GroupAccount(
        group_id=10, account_id=account_id, account_name="Poster",
        can_post=1 if can_post else 0, can_send_media=1 if can_send_media else 0,
        is_primary=1 if is_primary else 0,
    )
    return m


def _make_target(gid=10, account_id=5, can_post=True):
    g = _make_group(gid=gid)
    m = _make_mapping(account_id=account_id, can_post=can_post)
    return {
        "group_id": gid, "group": g, "mapping": m, "mappings": [m],
        # account_id is only populated when the account has verified posting
        # permission; otherwise the dialog cannot choose an account.
        "account_id": account_id if can_post else None, "selectable": can_post,
    }


def _make_account(account_id=5):
    a = MagicMock()
    a.id = account_id
    a.first_name = "Poster"
    a.username = "poster"
    return a


class TestCreateCampaignDialogStatus:
    """data() must reflect the user's explicit final action."""

    def _dialog(self, qapp, **kwargs):
        targets = kwargs.pop("targets", [_make_target()])
        accounts = kwargs.pop("accounts", [_make_account()])
        d = CreateCampaignDialog(targets, accounts, smart_planner=None)
        d.le_campaign_name.setText("My Campaign")
        d.messages.append({"message_type": "TEXT", "body": "Hello"})
        d.tbl_campaign_target_selection.selectRow(0)
        return d

    def test_finish_creates_ready_not_draft(self, qapp):
        """BUG: 'Create Campaign' must NOT create a Draft."""
        d = self._dialog(qapp)
        d._finish_mode = "finish"
        data = d.data()
        assert data["status"] == "READY"
        assert data["finish_mode"] == "finish"

    def test_save_draft_creates_draft(self, qapp):
        """'Save Draft' is the ONLY path that creates a Draft."""
        d = self._dialog(qapp)
        d._finish_mode = "draft"
        data = d.data()
        assert data["status"] == "DRAFT"

    def test_schedule_creates_scheduled(self, qapp):
        """'Create & Schedule' creates a SCHEDULED campaign."""
        d = self._dialog(qapp)
        d._finish_mode = "schedule"
        data = d.data()
        assert data["status"] == "SCHEDULED"

    def test_run_creates_ready(self, qapp):
        """'Create & Run' creates a READY campaign (run is a separate step)."""
        d = self._dialog(qapp)
        d._finish_mode = "run"
        data = d.data()
        assert data["status"] == "READY"


class TestCreateCampaignDialogValidation:
    """Validation must report the exact missing field."""

    def _dialog(self, qapp):
        d = CreateCampaignDialog([_make_target()], [_make_account()], smart_planner=None)
        return d

    def test_missing_name(self, qapp):
        d = self._dialog(qapp)
        d.messages.append({"message_type": "TEXT", "body": "Hello"})
        d.tbl_campaign_target_selection.selectRow(0)
        errors = d._validate()
        assert any("Campaign name is required" in e for e in errors)

    def test_missing_target(self, qapp):
        d = self._dialog(qapp)
        d.le_campaign_name.setText("X")
        d.messages.append({"message_type": "TEXT", "body": "Hello"})
        errors = d._validate()
        assert any("Target is required" in e for e in errors)

    def test_missing_content(self, qapp):
        d = self._dialog(qapp)
        d.le_campaign_name.setText("X")
        d.tbl_campaign_target_selection.selectRow(0)
        errors = d._validate()
        assert any("Content is required" in e for e in errors)

    def test_missing_account_permission(self, qapp):
        d = CreateCampaignDialog(
            [_make_target(can_post=False)], [_make_account()], smart_planner=None
        )
        d.le_campaign_name.setText("X")
        d.messages.append({"message_type": "TEXT", "body": "Hello"})
        d.tbl_campaign_target_selection.selectRow(0)
        errors = d._validate()
        assert any("Account is required" in e for e in errors)


class TestCampaignServiceCreate:
    """Service must persist the requested status and validate content."""

    def _service(self):
        repo = MagicMock()
        repo.db.transaction.return_value.__enter__ = MagicMock(return_value=None)
        repo.db.transaction.return_value.__exit__ = MagicMock(return_value=None)
        created = Campaign(id=1, name="My Campaign", status="READY")
        # get_by_id must return whatever create() persisted, so the returned
        # aggregate reflects the requested status.
        holder = {}
        repo.create.side_effect = lambda item: holder.setdefault("item", item)
        repo.get_by_id.side_effect = lambda cid: holder.get("item", created)
        target_repo = MagicMock()
        message_repo = MagicMock()
        group_repo = MagicMock()
        group = _make_group()
        group_repo.get_by_id.return_value = group
        group_account_repo = MagicMock()
        mapping = _make_mapping()
        group_account_repo.get_primary_account.return_value = mapping
        group_account_repo.get_mapping.return_value = mapping
        svc = CampaignService(
            repo, target_repo, message_repo,
            group_repository=group_repo, group_account_repository=group_account_repo,
            media_service=MagicMock(),
        )
        return svc, repo

    def test_create_persists_ready_status(self):
        svc, repo = self._service()
        item = svc.create({
            "name": "My Campaign", "status": "READY",
            "messages": [{"message_type": "TEXT", "body": "Hello"}],
            "targets": [{"group_id": 10, "account_id": 5}],
        })
        assert item.status == "READY"
        # The persisted Campaign object must carry the requested status.
        assert repo.create.call_args[0][0].status == "READY"

    def test_create_persists_draft_status(self):
        svc, repo = self._service()
        item = svc.create({
            "name": "My Campaign", "status": "DRAFT",
            "messages": [{"message_type": "TEXT", "body": "Hello"}],
            "targets": [{"group_id": 10, "account_id": 5}],
        })
        assert item.status == "DRAFT"
        assert repo.create.call_args[0][0].status == "DRAFT"

    def test_create_requires_content(self):
        svc, _ = self._service()
        with pytest.raises(ValueError) as exc:
            svc.create({"name": "My Campaign", "status": "READY", "targets": []})
        assert "Content is required" in str(exc.value)

    def test_create_requires_name(self):
        svc, _ = self._service()
        with pytest.raises(ValueError) as exc:
            svc.create({"name": "", "status": "READY", "messages": [{"body": "x"}]})
        assert "Campaign name is required" in str(exc.value)

    def test_create_rolls_back_on_target_failure(self):
        """A failed create must not leave a partial campaign row behind."""
        svc, repo = self._service()
        # Target resolution fails inside the transaction (unmanaged group).
        svc.group_repository.get_by_id.return_value = None
        with pytest.raises(ValueError) as exc:
            svc.create({
                "name": "My Campaign", "status": "READY",
                "messages": [{"message_type": "TEXT", "body": "Hello"}],
                "targets": [{"group_id": 999, "account_id": 5}],
            })
        assert "managed groups" in str(exc.value)
        # The transaction context manager was exited so the rollback path ran.
        assert repo.db.transaction.return_value.__exit__.called