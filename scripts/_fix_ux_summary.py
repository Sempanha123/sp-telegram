"""Fix TASK_QUEUE.json summary counts after UX task updates."""
import json

p = ".ai/TASK_QUEUE.json"
d = json.load(open(p, encoding="utf-8"))
s = d["summary"]
s["medium"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN" and t["severity"] == "MEDIUM")
s["low"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN" and t["severity"] == "LOW")
s["fixed_this_cycle"] = 10  # the 10 UX-friendliness fixes implemented this cycle
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("medium(open):", s["medium"], "low(open):", s["low"], "fixed_this_cycle:", s["fixed_this_cycle"])