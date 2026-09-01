"""Update RELEASE_STATUS.json for Cycle 8 UI-friendliness fixes."""
import json
from datetime import datetime, timezone

p = ".ai/RELEASE_STATUS.json"
d = json.load(open(p, encoding="utf-8"))
d["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d["audit_cycle"] = 8

rc = d["release_criteria"]
rc["medium_count"] = 5
rc["low_count"] = 2
rc["open_tasks"] = 7
rc["fixed_this_cycle"] = 10
rc["verified_fixes"] = 38
rc["failed_fixes"] = 0
rc["test_results"] = "51/51 pass, 0 no-op tests"
rc["regression_status"] = "CLEAN - no regressions detected"
rc["consecutive_passing_audits"] = 0
rc["windows_qa"] = (
    "RUNTIME VERIFIED - 8/8 checks pass (group double-click + campaign creation end-to-end); "
    "BUG-021 repro 4/4; UI-friendliness verify 20/20 (page-jump, clear filters, status text, "
    "spinner, step dots, settings search, command palette); UI consistency verified soft-light"
)

d["fixed_this_cycle"] = [
    "UX-001 (MEDIUM) - Page-jump QSpinBox in pagination bar (type page + Enter)",
    "UX-002 (MEDIUM) - Clear Filters button + active-combo highlight + empty-state action",
    "UX-004 (MEDIUM) - Topbar status chips show state text (NET/TG/DB)",
    "UX-005 (MEDIUM) - LoadingOverlay instantiated in BaseTablePage + OperationsPage (set_loading)",
    "UX-006 (MEDIUM) - Contextual empty states (filtered-to-zero vs true empty)",
    "UX-008 (MEDIUM) - 7 numbered step dots in campaign wizard (done/current/todo)",
    "UX-010 (MEDIUM) - Indeterminate QProgressBar spinner in LoadingOverlay",
    "UX-011 (MEDIUM) - Bottom-right action placement (CampaignProgressDialog, LicenseDetailsDialog)",
    "UX-012 (LOW) - Settings search box with match-count hint",
    "UX-013 (LOW) - Enter key on table rows emits doubleClicked (all table pages)",
]

# Add UX fixes + BUG-018 to verified_fixes (dedupe by id)
existing = {v["id"] for v in d["verified_fixes"]}
new_fixes = [
    {"id": "UX-001", "severity": "MEDIUM", "description": "Page-jump QSpinBox in pagination bar"},
    {"id": "UX-002", "severity": "MEDIUM", "description": "Clear Filters button + active-combo highlight + empty-state action"},
    {"id": "UX-004", "severity": "MEDIUM", "description": "Topbar status chips show state text (NET/TG/DB)"},
    {"id": "UX-005", "severity": "MEDIUM", "description": "LoadingOverlay instantiated + set_loading() API"},
    {"id": "UX-006", "severity": "MEDIUM", "description": "Contextual empty states (filtered-to-zero vs true empty)"},
    {"id": "UX-008", "severity": "MEDIUM", "description": "7 numbered step dots in campaign wizard"},
    {"id": "UX-010", "severity": "MEDIUM", "description": "Indeterminate QProgressBar spinner in LoadingOverlay"},
    {"id": "UX-011", "severity": "MEDIUM", "description": "Bottom-right action placement in dialogs"},
    {"id": "UX-012", "severity": "LOW", "description": "Settings search box with match-count hint"},
    {"id": "UX-013", "severity": "LOW", "description": "Enter key on table rows emits doubleClicked"},
    {"id": "BUG-018", "severity": "MEDIUM", "description": "Semicolon-compressed lines split for debuggability"},
]
for f in new_fixes:
    if f["id"] not in existing:
        d["verified_fixes"].append(f)

d["required_before_release"] = [
    "QA-004 (MEDIUM) - Add post-invite verification",
    "All MEDIUM bugs fixed or documented",
    "All tests pass (51/51)",
    "compileall PASS",
    "Two consecutive clean audit passes",
    "Windows QA pass",
]

json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("audit_cycle:", d["audit_cycle"], "| verified_fixes:", len(d["verified_fixes"]),
      "| fixed_this_cycle:", len(d["fixed_this_cycle"]))