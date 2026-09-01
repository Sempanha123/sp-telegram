"""Runtime verification: campaign archive -> unarchive -> delete against the real DB.

Creates throwaway campaigns, archives, unarchives, and deletes them (including
the hard-delete-with-delivery-history path that previously hit the FK RESTRICT).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database.database import DatabaseManager
from app.database.repositories.campaign_repository import CampaignRepository
from app.database.repositories.campaign_message_repository import CampaignMessageRepository
from app.database.repositories.campaign_target_repository import CampaignTargetRepository
from app.database.repositories.delivery_repository import DeliveryRepository
from app.models.entities import Campaign
from app.utils.formatters import utc_now_iso

DB_PATH = ROOT / "data" / "tg_control.db"
checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


def main():
    db = DatabaseManager(DB_PATH)
    repo = CampaignRepository(db)
    msg_repo = CampaignMessageRepository(db)
    tgt_repo = CampaignTargetRepository(db)
    del_repo = DeliveryRepository(db)

    # 1. Create a throwaway campaign
    item = Campaign(name="__qa_delete_unarchive__", campaign_type="SINGLE_POST", status="DRAFT", schedule_type="SEND_NOW")
    created = repo.create(item)
    cid = created.id
    check("create throwaway campaign", cid is not None and cid > 0)

    # 2. Archive it
    repo.archive(cid)
    archived = repo.get_by_id(cid)
    check("archive sets ARCHIVED", archived and archived.status == "ARCHIVED")

    # 3. Unarchive it (new feature)
    repo.unarchive(cid)
    restored = repo.get_by_id(cid)
    check("unarchive restores to DRAFT", restored and restored.status == "DRAFT")

    # 4. Delete a DRAFT campaign -> hard delete
    check("delete DRAFT campaign", repo.delete(cid) is True)
    check("DRAFT row removed", repo.get_by_id(cid) is None)

    # 5. Delete a RUNNING campaign -> cancels, then second delete removes it
    item2 = Campaign(name="__qa_cancel__", campaign_type="SINGLE_POST", status="RUNNING", schedule_type="SEND_NOW")
    created2 = repo.create(item2)
    repo.delete(created2.id)
    row2 = repo.get_by_id(created2.id)
    check("RUNNING delete cancels instead of removing", row2 is not None and row2.status == "CANCELLED")
    repo.delete(created2.id)
    check("CANCELLED delete removes row", repo.get_by_id(created2.id) is None)

    # 6. Hard delete an ARCHIVED campaign WITH delivery history (FK RESTRICT path)
    item3 = Campaign(name="__qa_archived_delete__", campaign_type="SINGLE_POST", status="DRAFT", schedule_type="SEND_NOW")
    created3 = repo.create(item3)
    cid3 = created3.id
    msg = msg_repo.create(cid3, {"message_type": "TEXT", "body": "Hello"})
    # Need a real group for the target FK (RESTRICT). Use any existing group.
    group = db.fetch_one("SELECT id FROM groups LIMIT 1")
    if group:
        gid = int(group["id"])
        tgt_repo.replace_targets(cid3, [(gid, None)])
        tgt = tgt_repo.get_targets(cid3)[0]
        del_repo.create_delivery(cid3, tgt.id, msg.id, "qa-1", "hash")
        check("delivery history exists", bool(del_repo.get_campaign_deliveries(cid3)))
        repo.archive(cid3)
        check("delete archived campaign with history", repo.delete(cid3) is True)
        check("campaign row removed", repo.get_by_id(cid3) is None)
        check("deliveries removed", not del_repo.get_campaign_deliveries(cid3))
    else:
        # No groups in DB — just verify the archived delete without history.
        repo.archive(cid3)
        check("delete archived campaign (no groups present)", repo.delete(cid3) is True)
        check("archived row removed", repo.get_by_id(cid3) is None)

    db.close()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} PASS")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())