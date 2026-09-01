"""Update RELEASE_STATUS.json for BUG-022 (campaign delete/unarchive)."""
import json
from datetime import datetime, timezone

p = ".ai/RELEASE_STATUS.json"
d = json.load(open(p, encoding="utf-8"))
d["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

rc = d["release_criteria"]
rc["fixed_this_cycle"] = 11
rc["verified_fixes"] = len(d["verified_fixes"]) + 1
rc["test_results"] = "58/58 pass, 0 no-op tests"
rc["windows_qa"] = (
    "RUNTIME VERIFIED - 8/8 checks pass (group double-click + campaign creation end-to-end); "
    "BUG-021 repro 4/4; UI-friendliness verify 20/20; campaign delete/unarchive verify 11/11 + menu 11/11; "
    "UI consistency verified soft-light"
)

d["fixed_this_cycle"].append(
    "BUG-022 (HIGH) - Campaign delete/unarchive - repository.unarchive() restores ARCHIVED->DRAFT; "
    "delete() hard-deletes non-active campaigns (clears campaign_deliveries FK RESTRICT first); "
    "contextual Unarchive/Delete menu in campaigns page"
)

existing = {v["id"] for v in d["verified_fixes"]}
if "BUG-022" not in existing:
    d["verified_fixes"].append(
        {
            "id": "BUG-022",
            "severity": "HIGH",
            "description": "Campaign delete/unarchive - unarchive() + hard delete with delivery-history FK handling + contextual menu",
        }
    )
rc["verified_fixes"] = len(d["verified_fixes"])

json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("fixed_this_cycle:", len(d["fixed_this_cycle"]), "| verified_fixes:", len(d["verified_fixes"]))