"""Add BUG-022 (campaign delete/unarchive) to TASK_QUEUE.json and update summary."""
import json
from datetime import datetime

p = ".ai/TASK_QUEUE.json"
d = json.load(open(p, encoding="utf-8"))
now = datetime.now().strftime("%Y-%m-%d")

new_task = {
    "id": "BUG-022",
    "status": "VERIFIED",
    "severity": "HIGH",
    "file": "app/pages/campaigns_page.py, app/database/repositories/campaign_repository.py, app/services/campaign_service.py, app/controllers/campaign_controller.py",
    "component": "UI/Campaigns",
    "description": "USER-VERIFIED: campaigns could not be deleted (only DRAFT/CANCELLED were deletable; ARCHIVED/COMPLETED/FAILED raised 'Only unused drafts or cancelled campaigns can be deleted') and there was no way to unarchive a campaign.",
    "evidence": "campaign_deliveries has ON DELETE RESTRICT so hard delete failed; no unarchive method existed anywhere.",
    "expected": "Users can delete archived/completed/failed/cancelled/draft campaigns (with confirmation) and unarchive archived campaigns.",
    "actual": "Delete only worked for DRAFT/CANCELLED; ARCHIVED campaigns were stuck forever.",
    "required_fix": "Add repository.unarchive(); make repository.delete() hard-delete non-active campaigns (clear campaign_deliveries first, then cascade); wire unarchive + contextual Delete in campaigns page menu.",
    "required_test": "Repository tests for archive/unarchive/delete across statuses incl. delivery-history path; UI menu test for Unarchive/Delete context.",
    "attempts": 1,
    "fixed_by": "AI #2",
    "fixed_at": now,
    "fix": "campaign_repository.unarchive() restores ARCHIVED->DRAFT; repository.delete() now hard-deletes DRAFT/CANCELLED/ARCHIVED/COMPLETED/FAILED/PARTIAL_SUCCESS (deletes campaign_deliveries first to satisfy FK RESTRICT, then the campaign row cascades targets/messages) while RUNNING/SCHEDULED/PAUSED still cancel. Added service.unarchive() + controller.unarchive(); campaigns page menu now shows Unarchive for ARCHIVED (instead of Archive) and contextual Delete/Delete Draft with status-aware confirmation.",
    "verified_by": "AI #2",
    "verified_at": now,
    "verification": "7/7 new tests in tests/test_campaign_delete_unarchive.py PASS. Full suite 58/58 PASS. compileall PASS. Runtime scripts PASS: scripts/_qa_verify_campaign_delete_unarchive.py 11/11 (archive->unarchive->delete incl. delivery-history FK path), scripts/_qa_verify_campaign_menu.py 11/11 (Unarchive/Delete context menu).",
}

# Replace or append
tasks = d["tasks"]
tasks = [t for t in tasks if t["id"] != "BUG-022"]
tasks.append(new_task)
d["tasks"] = tasks

s = d["summary"]
s["total"] = len(tasks)
s["verified"] = sum(1 for t in tasks if t["status"] == "VERIFIED")
s["open"] = sum(1 for t in tasks if t["status"] == "OPEN")
s["blocker"] = sum(1 for t in tasks if t["status"] == "OPEN" and t["severity"] == "BLOCKER")
s["critical"] = sum(1 for t in tasks if t["status"] == "OPEN" and t["severity"] == "CRITICAL")
s["high"] = sum(1 for t in tasks if t["status"] == "OPEN" and t["severity"] == "HIGH")
s["medium"] = sum(1 for t in tasks if t["status"] == "OPEN" and t["severity"] == "MEDIUM")
s["low"] = sum(1 for t in tasks if t["status"] == "OPEN" and t["severity"] == "LOW")
s["fixed_this_cycle"] = 11  # 10 UX + BUG-022
s["tests_passing"] = "58/58"
s["new_this_audit"] = s.get("new_this_audit", 3) + 1

json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("total:", s["total"], "verified:", s["verified"], "open:", s["open"],
      "high:", s["high"], "medium:", s["medium"], "low:", s["low"],
      "fixed_this_cycle:", s["fixed_this_cycle"], "tests:", s["tests_passing"])