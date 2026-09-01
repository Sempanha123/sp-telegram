"""Update UX task statuses in TASK_QUEUE.json after Cycle 8 UI-friendliness fixes."""
import json
from datetime import datetime

p = ".ai/TASK_QUEUE.json"
d = json.load(open(p, encoding="utf-8"))
now = datetime.now().strftime("%Y-%m-%d")
updates = {
    "UX-001": ("VERIFIED", "Page-jump QSpinBox added to PaginationBar (spin_page_jump); type page number + Enter."),
    "UX-002": ("VERIFIED", "Clear Filters button + active combo highlight (blue border) in BaseTablePage; empty-state Clear Filters action."),
    "UX-004": ("VERIFIED", "Topbar status chips now show state text (NET Online, TG Ready, DB Connected) not color-only."),
    "UX-005": ("VERIFIED", "LoadingOverlay instantiated in BaseTablePage + OperationsPage with set_loading(); shown during async diagnostics/audit."),
    "UX-006": ("VERIFIED", "Contextual empty states: filtered-to-zero shows 'No results match your filters' + Clear Filters action."),
    "UX-008": ("VERIFIED", "7 numbered step dots added to CreateCampaignDialog with done/current/todo states."),
    "UX-010": ("VERIFIED", "Indeterminate QProgressBar spinner added to LoadingOverlay."),
    "UX-011": ("VERIFIED", "Standardized bottom-right action placement in CampaignProgressDialog + LicenseDetailsDialog."),
    "UX-012": ("VERIFIED", "Settings search box filters/jumps to matching tab with match count hint."),
    "UX-013": ("VERIFIED", "Enter/Return on selected table row emits doubleClicked (all table pages)."),
}
for t in d["tasks"]:
    if t["id"] in updates:
        st, note = updates[t["id"]]
        t["status"] = st
        t["verified_by"] = "AI #2"
        t["verified_at"] = now
        t["verification"] = note
s = d["summary"]
s["verified"] = sum(1 for t in d["tasks"] if t["status"] == "VERIFIED")
s["open"] = sum(1 for t in d["tasks"] if t["status"] == "OPEN")
s["fixed_this_cycle"] = sum(1 for t in d["tasks"] if t.get("verified_at") == now)
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("updated. verified:", s["verified"], "open:", s["open"], "fixed_this_cycle:", s["fixed_this_cycle"])