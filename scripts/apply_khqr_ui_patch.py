from __future__ import annotations

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "app" / "pages" / "license_page.py"

text = PAGE.read_text(encoding="utf-8")
pattern = re.compile(r"    def _upgrade_requested\(self,feature,required\):\n.*?(?=    def _choose_plan\(self,plan\):)", re.S)
replacement = '''    def _upgrade_requested(self,feature,required):
        try:
            plan = PlanKey(str(required or 'PRO').upper())
        except ValueError:
            plan = PlanKey.PRO
        feature_name = 'Plan change' if str(feature) == 'PLAN_CHANGE' else (feature or 'Selected feature')
        d = UpgradePlanDialog(
            str(self.controller.current_state().plan or 'Unlicensed'),
            feature_name,
            plan.value,
            controller=self.controller,
            parent=self,
        )
        d.viewPlansRequested.connect(lambda:self._scroll_plans(None))
        if d.exec():
            self.refresh()

'''
new_text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit("Could not find the expected _upgrade_requested block. Your license_page.py may have changed; merge manually.")
backup = PAGE.with_suffix(".py.before-khqr")
if not backup.exists():
    shutil.copy2(PAGE, backup)
PAGE.write_text(new_text, encoding="utf-8")
print(f"Patched {PAGE}")
print(f"Backup: {backup}")
