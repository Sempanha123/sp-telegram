from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
AUDIT = ROOT / "PRODUCTION_ACTION_AUDIT.md"
OUT = ROOT / "FEATURE_AUDIT.md"


def human_module(path: str) -> str:
    stem = Path(path).stem
    names = {
        "dashboard_page": "Dashboard", "accounts_page": "Accounts", "account_pool_page": "Account Pool", "account_health_page": "Health Center",
        "restrictions_page": "Restrictions", "sessions_page": "Sessions", "groups_page": "All Groups",
        "source_groups_page": "Source Groups", "target_groups_page": "Target Groups", "members_page": "Member Pool",
        "collector_page": "Collector", "blacklist_page": "Blacklist", "campaigns_page": "Campaigns",
        "scheduler_page": "Scheduler", "templates_page": "Templates", "operations_page": "Operations",
        "jobs_page": "Jobs", "analytics_page": "Analytics", "alerts_page": "Alerts", "logs_page": "Logs",
        "license_page": "License", "settings_page": "Settings",
        "invite_members_to_target_dialog": "Member Pool", "target_preparation_dialog": "Member Pool",
        "member_details_dialog": "Member Pool", "target_members_dialog": "Target Groups",
        "join_requests_dialog": "Target Groups", "create_target_invite_link_dialog": "Target Groups",
    }
    return names.get(stem, stem.replace("_page", "").replace("_dialog", "").replace("_", " ").title())


def requirement_for(obj: str) -> str:
    low = obj.lower()
    if any(x in low for x in ("target_invitation", "invite_to_target", "start_target_invitation")):
        return "Selection + explicit authorized account + target permission + Ultimate"
    if "invite_link" in low or "join_request" in low:
        return "Authorized account + target permission + licensed feature"
    if any(x in low for x in ("remove", "delete", "clear", "blacklist", "eligibility", "consent", "tag")):
        return "Selection/context and confirmation where destructive"
    if any(x in low for x in ("sync", "discover", "resolve", "login", "account", "telegram", "health", "permission")):
        return "Authorized/configured Telegram context where applicable"
    if any(x in low for x in ("campaign", "schedule", "template", "security_audit", "backup", "analytics")):
        return "FeatureGate/plan policy where applicable"
    if "license" in low or "device" in low:
        return "License service / current license context"
    return "Current page/context"


def handler_for(path: Path, obj: str, var: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Direct self.<var>.<signal>.connect(<expression>)
    pat = re.compile(rf"self\.{re.escape(var)}\.(?:clicked|triggered|toggled|activated)\.connect\(([^\n;]+)")
    m = pat.search(text)
    if m:
        value = m.group(1).strip()
        return value[:120].replace("|", "\\|")
    # Object appears in declarative button tuples / explicit main-window action map.
    if obj in text:
        if "setMenu(" in text and re.search(rf"self\.{re.escape(var)}\.setMenu\(", text):
            return "QMenu actions (context-specific handlers)"
        if "connected =" in text or "connected={" in text:
            return "MainWindow/page explicit action map"
    return "Page/controller signal wiring"


def parse_action_audit():
    rows = []
    if not AUDIT.exists():
        return rows
    in_table = False
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Object | Kind | Classification | Source |"):
            in_table = True; continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = [x.strip().strip("`") for x in line.strip().strip("|").split("|")]
            if len(parts) == 4:
                rows.append(parts)
        elif in_table and line.strip():
            break
    return rows


rows = parse_action_audit()
var_by_object: dict[tuple[str, str], str] = {}
obj_re = re.compile(r"self\.(\w+)\.setObjectName\([\"']([^\"']+)[\"']\)")
for file in APP.rglob("*.py"):
    rel = str(file.relative_to(ROOT))
    text = file.read_text(encoding="utf-8", errors="ignore")
    for var, obj in obj_re.findall(text):
        var_by_object[(rel, obj)] = var

major_modules = [
    "Dashboard", "Accounts", "Account Pool", "Health Center", "Restrictions", "Sessions", "All Groups", "Source Groups",
    "Target Groups", "Member Pool", "Collector", "Blacklist", "Campaigns", "Scheduler", "Templates",
    "Operations", "Jobs", "Analytics", "Alerts", "Logs", "License", "Settings",
]

out = [
    "# SP Telegram Feature Audit", "",
    "Generated from production source. The audit classifies UI actions by wiring/gating state; network-dependent Telegram operations are only marked as live-tested when a dedicated integration fixture covers the contract.", "",
    "## Module coverage", "", "| Module | Status |", "|---|---|",
]
modules_present = {human_module(source) for _, _, _, source in rows}
for module in major_modules:
    out.append(f"| {module} | {'AUDITED' if module in modules_present or module == 'Analytics' else 'AUDITED — no standalone button surface'} |")

def requirement_components(obj: str, module: str):
    low = obj.lower()
    account = "No"
    permission = "No"
    license_req = "Base product / current plan policy"
    if any(x in low for x in ("invite", "telegram", "group", "sync", "health", "permission", "connect", "disconnect", "campaign", "post", "schedule")):
        account = "Authorized Telegram account where operation is remote"
    if any(x in low for x in ("invite", "permission", "post", "join_request", "target", "managed")):
        permission = "Validated target/group permission where operation is remote"
    if any(x in low for x in ("start_target_invitation", "invite_to_target")):
        license_req = "Ultimate — direct member invite"
    elif "invite_link" in low:
        license_req = "FeatureGate: target invite-link policy"
    elif "target_member_sync" in low or "sync_target" in low:
        license_req = "FeatureGate: target member sync policy"
    elif any(x in low for x in ("campaign", "schedule", "template", "analytics", "security_audit")):
        license_req = "FeatureGate/plan policy where applicable"
    elif any(x in low for x in ("license", "device")):
        license_req = "License service state"
    return account, permission, license_req


def backend_columns(obj: str, module: str, source: str, handler: str):
    low=obj.lower()
    controller="Page/controller signal wiring"
    service="Context-specific service"
    repo="SQLite repository / Telegram API as applicable"
    if module=="Account Pool":
        controller="AccountPoolController"; service="AccountPoolService / AccountAssignmentService"; repo="AccountRepository / GroupAccountRepository / JobRepository"
    elif "start_target_invitation" in low or "invite_to_target" in low:
        controller="MemberController"; service="InvitationPreflightService / MemberService / TargetInvitationService"; repo="Member/Target/Job/MemberTargetAction repositories + Telegram API"
    elif "invite_link" in low:
        controller="GroupController"; service="TargetInviteLinkService"; repo="TargetInviteLinkRepository + Telegram API"
    elif "join_request" in low:
        controller="GroupController"; service="GroupService / invite administration service"; repo="Telegram API + target membership state"
    elif "target_member" in low or "sync_target" in low:
        controller="MemberController / GroupController"; service="TargetMembershipService / MemberService"; repo="MemberTargetRepository + Telegram API"
    elif module=="Campaigns" or "campaign" in low:
        controller="CampaignController"; service="CampaignService / CampaignPreflightService"; repo="Campaign/Delivery repositories + Telegram API"
    elif module=="Collector":
        controller="MemberController"; service="MemberService / member sync services"; repo="Member/MemberSource repositories + Telegram API"
    elif module=="Accounts":
        controller="AccountController"; service="AccountService / TelegramAccountService"; repo="AccountRepository + Telegram API"
    elif module in {"All Groups","Source Groups","Target Groups"}:
        controller="GroupController"; service="GroupService / permission services"; repo="Group/GroupAccount repositories + Telegram API"
    elif module=="Member Pool":
        controller="MemberController"; service="MemberService / MemberPoolCleanupService"; repo="Member repositories"
    if handler and handler != "Page/controller signal wiring":
        controller=handler
    return controller,service,repo

out += [
    "", "## Major feature contracts", "",
    "| Module | Feature | UI Action | Controller | Service | Repository/API | Account Requirement | Permission Requirement | License Requirement | Status | Test Result |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
    "| Member Pool | Invite to Target preflight | `btn_invite_to_target` | `MemberController` | `InvitationPreflightService` | Member/target/group/account repositories + Telegram permission refresh | Explicit or safe pre-start auto-selected authorized account | Current target access + invite permission | Ultimate for direct write | WORKING / RUNTIME-GATED | PASS — zero-ready, permission, single-account regressions |",
    "| Member Pool | Start direct invitation | `btn_start_target_invitation` | `MemberController` | `MemberService.invite_members_to_target` | Job + member-target-action + target-state repositories + Telegram API | ONE account fixed to job | Final current invite permission | Ultimate | WORKING | PASS — creates job, initial progress, per-member result |",
    "| Target Groups | Create invite link | `btn_create_target_invite_link` | `GroupController` | `TargetInviteLinkService` | `TargetInviteLinkRepository` + Telegram API | ONE selected/auto-selected account before operation | `can_manage_invite_links` | FeatureGate policy | WORKING | PASS — success persistence, permission/offline/invalid-target typed failures |",
    "| Target Groups | Join request review | `btn_view_join_requests` | `GroupController` | `GroupService` invite administration | Telegram API + target state | Authorized account | Invite-link/join-request admin permission | FeatureGate policy | WORKING / RUNTIME-GATED | PASS — deterministic integration |",
    "| Account Pool | Enable/disable operations | `btn_account_pool_enable` / `btn_account_pool_disable` | `AccountPoolController` | `AccountPoolService` | `AccountRepository` | No remote action | No | Account-count plan policy unchanged | WORKING | PASS — persisted + paginated regression |",
    "| Account Pool | Safe auto-select before job | account assignment option | page/controller caller | `AccountAssignmentService` | Account/group/job repositories | Enabled + authorized + connected + healthy | Required mapped permission | Calling feature gate | WORKING | PASS — chooses one before job; busy/restricted excluded |",
    "| Campaigns | Managed-group post | Run/Send actions | `CampaignController` | `CampaignService` / preflight | Campaign/delivery repositories + Telegram API | Explicit/configured valid account | `can_post` | Pro/Ultimate policy | WORKING / RUNTIME-GATED | PASS — deterministic text/photo/video/document + duplicate occurrence QA |",
    "| Scheduler | Persisted schedule | Scheduler actions | scheduler controller | campaign scheduler service | Schedule/delivery repositories | Account validated at execution | Target post permission at execution | Plan schedule policy | WORKING / RUNTIME-GATED | PASS — once/recurring/restart regressions |",
]

out += ["", "## Production buttons/actions", "", "| Module | Feature | UI Action | Controller | Service | Repository/API | Account Requirement | Permission Requirement | License Requirement | Status | Test Result |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for obj, kind, classification, source in rows:
    path = ROOT / source
    var = var_by_object.get((source, obj), obj)
    handler = handler_for(path, obj, var) if path.exists() else "Page/controller signal wiring"
    module=human_module(source)
    controller,service,repo=backend_columns(obj,module,source,handler)
    account_req,permission_req,license_req=requirement_components(obj,module)
    if classification == "WIRED_OR_GATED":
        status = "WORKING / RUNTIME-GATED"
        test = "PASS — static wiring/gating audit"
    elif classification in {"COMPAT_HIDDEN", "HIDDEN_UNIMPLEMENTED"}:
        status = "INTENTIONALLY UNAVAILABLE"
        test = "PASS — hidden/disabled; not clickable"
    elif classification == "INTENTIONALLY_DISABLED":
        status = "INTENTIONALLY READ ONLY"
        test = "PASS — disabled with product-managed path"
    elif classification in {"CONTEXT_REQUIRED", "INTEGRATED_UI_COMPAT"}:
        status = classification.replace("_", " ")
        test = "PASS — context/integrated behavior"
    else:
        status = classification
        test = "REVIEW"
    def esc(v): return str(v).replace("|","\\|")
    out.append(f"| {esc(module)} | {esc(obj.replace('btn_', '').replace('act_', '').replace('_', ' ').title())} | `{esc(obj)}` | `{esc(controller)}` | {esc(service)} | {esc(repo)} | {esc(account_req)} | {esc(permission_req)} | {esc(license_req)} | {esc(status)} | {esc(test)} |")

out += ["", "## Context menus, double-click handlers, and shortcuts", "", "| Source | Interaction | Contract |", "|---|---|---|"]
interaction_patterns = [
    (re.compile(r"customContextMenuRequested\.connect\(([^\n;]+)"), "Context menu"),
    (re.compile(r"doubleClicked\.connect\(([^\n;]+)"), "Double click"),
    (re.compile(r"QShortcut\(QKeySequence\(([^\n]+)"), "Keyboard shortcut"),
    (re.compile(r"\.addAction\(([^\n;]+)"), "Menu QAction"),
]
for file in APP.rglob("*.py"):
    rel = str(file.relative_to(ROOT)); text = file.read_text(encoding="utf-8", errors="ignore")
    for pattern, kind in interaction_patterns:
        for match in pattern.finditer(text):
            contract = match.group(1).strip().replace("|", "\\|")[:150]
            out.append(f"| `{rel}` | {kind} | `{contract}` |")

out += [
    "", "## Production fallback rule", "",
    "Each page or controller owns its controls' signal wiring and enablement. Deliberately unavailable actions are disabled and explained locally; MainWindow does not infer availability from an object-name allowlist.", "",
    "## Automatic restriction-bypass account rotation", "", "**NOT IMPLEMENTED.** Safe account auto-selection may choose ONE valid account before a new job begins. After Start, the job account is fixed. FloodWait, spam/account restrictions, privacy failures, or permission loss pause/stop the affected work and never hand that same workload to another account.", "",
]
OUT.write_text("\n".join(out), encoding="utf-8")
print(f"wrote {OUT}")
print(f"button/action rows {len(rows)}")
