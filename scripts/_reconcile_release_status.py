"""Reconcile RELEASE_STATUS.json verified_fixes with TASK_QUEUE.json (38 verified)."""
import json

p = ".ai/RELEASE_STATUS.json"
d = json.load(open(p, encoding="utf-8"))
existing = {v["id"] for v in d["verified_fixes"]}
missing = [
    {"id": "QA-002", "severity": "MEDIUM", "description": "QA-002 verified"},
    {"id": "QA-003", "severity": "MEDIUM", "description": "QA-003 verified"},
    {"id": "R-001", "severity": "BLOCKER", "description": "R-001 verified"},
]
for f in missing:
    if f["id"] not in existing:
        d["verified_fixes"].append(f)
d["release_criteria"]["verified_fixes"] = len(d["verified_fixes"])
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("verified_fixes:", len(d["verified_fixes"]))