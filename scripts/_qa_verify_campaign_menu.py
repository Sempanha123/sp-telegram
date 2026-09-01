"""UI verification: CampaignsPage menu shows Unarchive for ARCHIVED and Delete otherwise."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from app.models.entities import Campaign
from app.models.campaign_table_model import CampaignTableModel
from app.pages.campaigns_page import CampaignsPage

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


def make_campaign(status, cid=1):
    return Campaign(id=cid, name=f"Camp {cid}", campaign_type="SINGLE_POST", status=status, schedule_type="SEND_NOW")


def main():
    app = QApplication.instance() or QApplication([])
    controller = MagicMock()
    controller.managed_targets.return_value = []
    controller.campaigns.return_value = []
    controller.pagination = MagicMock()
    controller.pagination.page = 1
    controller.pagination.page_size = 50
    controller.pagination.total_items = 0
    page = CampaignsPage(controller)
    page.resize(1200, 800)
    page.show()

    # ARCHIVED campaign -> menu must offer Unarchive (not Archive) + Delete
    page.model.replace_rows([make_campaign("ARCHIVED", 1)])
    page.table.selectRow(0)
    menu = page._menu()
    texts = [a.text() for a in menu.actions()]
    check("ARCHIVED menu has Unarchive", "Unarchive" in texts)
    check("ARCHIVED menu has no Archive", "Archive" not in texts)
    check("ARCHIVED menu has Delete", "Delete" in texts)
    check("ARCHIVED menu has no Delete Draft", "Delete Draft" not in texts)

    # DRAFT campaign -> menu must offer Archive + Delete Draft
    page.model.replace_rows([make_campaign("DRAFT", 2)])
    page.table.selectRow(0)
    menu = page._menu()
    texts = [a.text() for a in menu.actions()]
    check("DRAFT menu has Archive", "Archive" in texts)
    check("DRAFT menu has no Unarchive", "Unarchive" not in texts)
    check("DRAFT menu has Delete Draft", "Delete Draft" in texts)

    # COMPLETED campaign -> Delete (not Delete Draft)
    page.model.replace_rows([make_campaign("COMPLETED", 3)])
    page.table.selectRow(0)
    menu = page._menu()
    texts = [a.text() for a in menu.actions()]
    check("COMPLETED menu has Delete", "Delete" in texts)
    check("COMPLETED menu has no Delete Draft", "Delete Draft" not in texts)

    # Trigger unarchive action -> controller.unarchive called
    page.model.replace_rows([make_campaign("ARCHIVED", 4)])
    page.table.selectRow(0)
    menu = page._menu()
    unarchive_act = next(a for a in menu.actions() if a.text() == "Unarchive")
    unarchive_act.trigger()
    check("Unarchive action calls controller.unarchive", controller.unarchive.called)

    # Trigger delete action on COMPLETED -> controller.delete called
    page.model.replace_rows([make_campaign("COMPLETED", 5)])
    page.table.selectRow(0)
    menu = page._menu()
    delete_act = next(a for a in menu.actions() if a.text() == "Delete")
    # Patch QMessageBox.question to auto-confirm
    from PySide6.QtWidgets import QMessageBox
    orig = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        delete_act.trigger()
    finally:
        QMessageBox.question = orig
    check("Delete action calls controller.delete", controller.delete.called)

    page.close()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} PASS")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())