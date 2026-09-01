"""Fix stale statuses in TASK_QUEUE.json for cycle-7 fixes that were verified."""
import json
from datetime import datetime

p = ".ai/TASK_QUEUE.json"
d = json.load(open(p, encoding="utf-8"))
now = datetime.now().strftime("%Y-%m-%d")
fixes = {
    "SEC-004": ("VERIFIED", "Phone regex masks spaced/dashed international formats (cycle 7)."),
    "BUG-016": ("VERIFIED", "status() now async + acquires lock (cycle 7)."),
    "BUG-017": ("VERIFIED", "Handler cleanup on worker crash — all 6 controllers drain pending handlers (cycle 7)."),
    "BUG-018": ("VERIFIED", "Semicolon-compressed lines split for debuggability (cycle 7)."),
}
for t in d["tasks"]:
    if t["id"] in fixes:
        st, note = fixes[t["id"]]
        t["status"] = st
        t["verified_by"] = "AI #2"
        t["verified_at"] = t.get("verified_at") or now
        t["verification"] = note
s = d["summary"]
s["verified"] = sum(1 for t in d["tasks"] if t["status"] == "VERIFIED")
s["open"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN")
s["high"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN" and t["severity"] == "HIGH")
s["medium"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN" and t["severity"] == "MEDIUM")
s["low"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN" and t["severity"] == "LOW")
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("verified:", s["verified"], "open:", s["open"], "high:", s["high"], "medium:", s["medium"], "low:", s["low"])