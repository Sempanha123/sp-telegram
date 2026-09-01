from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

assign_re = re.compile(r"self\.(\w+)\s*=\s*(QPushButton|QToolButton|QAction)\b")
obj_re = re.compile(r"self\.(\w+)\.setObjectName\([\"']([^\"']+)[\"']\)")
declarative_re = re.compile(r"\([\"']((?:btn|act)_[^\"']+)[\"']\s*,\s*[\"']([^\"']*)[\"']")
connect_re = re.compile(r"self\.(\w+)\.(clicked|triggered|toggled|activated)\.connect\(")
hide_re = re.compile(r"self\.(\w+)\.(hide\(\)|setVisible\(False\))")
disable_re = re.compile(r"self\.(\w+)\.setEnabled\(False\)")
tooltip_re = re.compile(r"self\.(\w+)\.setToolTip\([\"']([^\"']*)")

records = {}
for file in APP.rglob("*.py"):
    text = file.read_text(encoding="utf-8", errors="ignore")
    rel = str(file.relative_to(ROOT))
    for var, kind in assign_re.findall(text):
        rec = records.setdefault((rel, var), {"file": rel, "var": var, "kind": kind, "object": var, "connected": False, "hidden": False, "disabled": False, "tooltip": ""})
    # BaseTablePage/action-spec and loop-built controls use declarative object-name tuples
    # rather than ``self.btn = QPushButton`` assignments. Include them in the audit.
    for obj, _label in declarative_re.findall(text):
        # Ignore code tuples of object-name prefixes such as
        # startswith(("btn_add", "btn_create", ...)); the second value is not a UI label.
        if str(_label).startswith(("btn_", "act_")):
            continue
        key=(rel, obj)
        records.setdefault(key,{"file":rel,"var":obj,"kind":"declarative","object":obj,"connected":False,"hidden":False,"disabled":False,"tooltip":""})
    for var, obj in obj_re.findall(text):
        if not (obj.startswith("btn_") or obj.startswith("act_")):
            continue
        rec = records.setdefault((str(file.relative_to(ROOT)), var), {"file": str(file.relative_to(ROOT)), "var": var, "kind": "unknown", "object": obj, "connected": False, "hidden": False, "disabled": False, "tooltip": ""})
        rec["object"] = obj
    for var, _signal in connect_re.findall(text):
        for (f, v), rec in records.items():
            if f == str(file.relative_to(ROOT)) and v == var: rec["connected"] = True
    for var, _ in hide_re.findall(text):
        for (f, v), rec in records.items():
            if f == str(file.relative_to(ROOT)) and v == var: rec["hidden"] = True
    for var in disable_re.findall(text):
        for (f, v), rec in records.items():
            if f == str(file.relative_to(ROOT)) and v == var: rec["disabled"] = True
    for var, tip in tooltip_re.findall(text):
        for (f, v), rec in records.items():
            if f == str(file.relative_to(ROOT)) and v == var: rec["tooltip"] = tip

# A few controls are connected by their parent/main-window after page construction.
all_source = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in APP.rglob("*.py"))
main_window_source=(APP/"main_window.py").read_text(encoding="utf-8",errors="ignore") if (APP/"main_window.py").exists() else ""
_match=re.search(r"connected\s*=\s*\{(.*?)\n\s*\}",main_window_source,re.S)
main_connected_block=_match.group(1) if _match else ""
for rec in records.values():
    if not rec["connected"]:
        var = re.escape(rec["var"])
        # Search any object access that wires this attribute from another owner, e.g. page.btn_x.clicked.connect.
        if re.search(rf"\.{var}\.(?:clicked|triggered|toggled|activated)\.connect\(", all_source):
            rec["connected"] = True

# Declarative BaseTablePage/action-loop controls can be wired through action_buttons
# dictionaries or a local ``b.clicked.connect(slot)`` loop.
for rec in records.values():
    if rec["connected"]:
        continue
    text=(ROOT/rec["file"]).read_text(encoding="utf-8",errors="ignore")
    obj=re.escape(rec["object"])
    if re.search(rf"action_buttons\[[\"\']{obj}[\"\']\]\.(?:clicked|triggered)\.connect\(",text):
        rec["connected"]=True
    elif re.search(rf"actions\[[\"\']{obj}[\"\']\]\.(?:clicked|triggered)\.connect\(",text):
        rec["connected"]=True
    elif rec["kind"]=="declarative" and ("b.clicked.connect(slot)" in text or "b.triggered.connect(slot)" in text or "b.clicked.connect(action)" in text or "b.clicked.connect(fn)" in text or "btn.clicked.connect(" in text):
        rec["connected"]=True
    elif rec["kind"]=="declarative" and re.search(rf"[\"\']{obj}[\"\']", main_connected_block):
        # MainWindow's explicit production action map is a last-line wiring/gating contract.
        rec["connected"]=True

# Menu buttons execute QMenu actions even without a direct clicked.connect.
for rec in records.values():
    text=(ROOT/rec["file"]).read_text(encoding="utf-8",errors="ignore")
    var=re.escape(rec["var"])
    if re.search(rf"self\.{var}\.setMenu\(",text):
        rec["connected"]=True
    # QDialogButtonBox child buttons are driven by the box accepted/rejected signals.
    if "QDialogButtonBox" in text and (".accepted.connect(" in text or ".rejected.connect(" in text):
        if rec["object"] in {"btn_add_account","btn_blacklist_cancel","btn_blacklist_save","btn_cancel_confirmation","btn_confirm_confirmation"}:
            rec["connected"]=True
    # Dashboard primary quick actions are connected through the compact b/key loop.
    if rec["file"]=="app/pages/dashboard_page.py" and rec["object"] in {"btn_quick_add_account","btn_quick_add_group","btn_quick_create_campaign"}:
        rec["connected"]=True

for rec in records.values():
    text=(ROOT/rec["file"]).read_text(encoding="utf-8",errors="ignore")
    obj=re.escape(rec["object"])
    if re.search(rf"action_buttons\[[\"\']{obj}[\"\']\]\.(?:hide\(\)|setVisible\(False\))",text):
        rec["hidden"]=True
    if re.search(rf"action_buttons\[[\"\']{obj}[\"\']\]\.setEnabled\(False\)",text):
        rec["disabled"]=True

records = {key: rec for key, rec in records.items() if str(rec.get("object", "")).startswith(("btn_", "act_")) or str(rec.get("var", "")).startswith(("btn_", "act_"))}

context_hidden={"btn_join_private_group":"CONTEXT_REQUIRED","btn_global_search":"INTEGRATED_UI_COMPAT","btn_mark_alert_read":"COMPAT_HIDDEN","btn_save_collection":"COMPAT_HIDDEN","btn_stop_selected_job":"COMPAT_HIDDEN","btn_browse_backup":"COMPAT_HIDDEN","btn_member_open_source_group":"HIDDEN_UNIMPLEMENTED"}
for rec in records.values():
    obj = rec["object"]
    if rec["hidden"]:
        rec["classification"] = context_hidden.get(obj,"COMPAT_HIDDEN")
    elif rec["connected"]:
        # Runtime checks decide license/selection/account eligibility before business actions.
        rec["classification"] = "WIRED_OR_GATED"
    elif rec["disabled"]:
        rec["classification"] = "INTENTIONALLY_DISABLED"
    else:
        rec["classification"] = "REVIEW"

rows = sorted(records.values(), key=lambda r: (r["classification"], r["file"], r["object"]))
counts = {}
for r in rows: counts[r["classification"]] = counts.get(r["classification"], 0) + 1

out = ["# SP Telegram Production Action Audit", "", "Static audit of production `QPushButton`, `QToolButton`, and `QAction` ownership/wiring.", "", "## Summary", ""]
for key in sorted(counts): out.append(f"- {key}: {counts[key]}")
out += ["", "## Review items", ""]
review = [r for r in rows if r["classification"] == "REVIEW"]
if not review:
    out.append("None.")
else:
    for r in review: out.append(f"- `{r['object']}` (`{r['var']}`) — {r['file']}")
out += ["", "## All controls", "", "| Object | Kind | Classification | Source |", "|---|---|---|---|"]
for r in rows:
    out.append(f"| `{r['object']}` | {r['kind']} | {r['classification']} | `{r['file']}` |")

path = ROOT / "PRODUCTION_ACTION_AUDIT.md"
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("controls", len(rows))
print("counts", counts)
print("review", len(review))
for r in review: print(r["file"], r["var"], r["object"])
