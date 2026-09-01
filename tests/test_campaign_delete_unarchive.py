"""Regression tests: campaign archive / unarchive / delete.

Covers the user-reported issue where campaigns could not be deleted (only
DRAFT/CANCELLED were deletable) and there was no way to unarchive a campaign.
"""
import tempfile
from pathlib import Path

import pytest

from app.database.database import DatabaseManager
from app.database.repositories.campaign_repository import CampaignRepository
from app.database.repositories.campaign_message_repository import CampaignMessageRepository
from app.database.repositories.campaign_target_repository import CampaignTargetRepository
from app.database.repositories.delivery_repository import DeliveryRepository
from app.models.entities import Campaign


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def repos(temp_db_path):
    db = DatabaseManager(temp_db_path)
    db.initialize()
    yield {
        "db": db,
        "campaign": CampaignRepository(db),
        "message": CampaignMessageRepository(db),
        "target": CampaignTargetRepository(db),
        "delivery": DeliveryRepository(db),
    }
    db.close()


def _make(status="DRAFT", name="QA Campaign"):
    return Campaign(name=name, campaign_type="SINGLE_POST", status=status, schedule_type="SEND_NOW")


class TestCampaignUnarchive:
    def test_unarchive_restores_archived_to_draft(self, repos):
        repo = repos["campaign"]
        created = repo.create(_make())
        repo.archive(created.id)
        assert repo.get_by_id(created.id).status == "ARCHIVED"
        repo.unarchive(created.id)
        assert repo.get_by_id(created.id).status == "DRAFT"

    def test_unarchive_unknown_id_is_noop(self, repos):
        repo = repos["campaign"]
        assert repo.unarchive(999999) is False


class TestCampaignDelete:
    def test_delete_draft_removes_row(self, repos):
        repo = repos["campaign"]
        created = repo.create(_make(status="DRAFT"))
        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_archived_removes_row(self, repos):
        repo = repos["campaign"]
        created = repo.create(_make(status="DRAFT"))
        repo.archive(created.id)
        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_completed_removes_row(self, repos):
        repo = repos["campaign"]
        created = repo.create(_make(status="COMPLETED"))
        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_running_cancels_instead_of_removing(self, repos):
        repo = repos["campaign"]
        created = repo.create(_make(status="RUNNING"))
        assert repo.delete(created.id) is True
        row = repo.get_by_id(created.id)
        assert row is not None and row.status == "CANCELLED"
        # Second delete (now CANCELLED) removes the row.
        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_archived_with_delivery_history(self, repos):
        """campaign_deliveries has ON DELETE RESTRICT — delete must clear it first."""
        repo = repos["campaign"]
        msg_repo = repos["message"]
        tgt_repo = repos["target"]
        del_repo = repos["delivery"]
        db = repos["db"]
        created = repo.create(_make(status="DRAFT"))
        msg = msg_repo.create(created.id, {"message_type": "TEXT", "body": "Hello"})
        # Need a real group for the target FK (RESTRICT).
        from app.utils.formatters import utc_now_iso
        now = utc_now_iso()
        db.execute(
            "INSERT INTO groups(title, group_type, is_managed, created_at, updated_at) "
            "VALUES('QA Group','SUPERGROUP',1,?,?)",
            (now, now),
        )
        gid = int(db.fetch_one("SELECT id FROM groups ORDER BY id DESC LIMIT 1")["id"])
        tgt_repo.replace_targets(created.id, [(gid, None)])
        tgt = tgt_repo.get_targets(created.id)[0]
        del_repo.create_delivery(created.id, tgt.id, msg.id, "qa-1", "hash")
        assert del_repo.get_campaign_deliveries(created.id)
        repo.archive(created.id)
        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None
        assert not del_repo.get_campaign_deliveries(created.id)