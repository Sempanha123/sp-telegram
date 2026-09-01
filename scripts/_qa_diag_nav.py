"""Diagnose why nav checked style isn't applying."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from app.widgets.sidebar import Sidebar

app = QApplication([])
apply_theme(app, "dark")
sb = Sidebar()
btn = sb._buttons["dashboard"]
print("dashboard checked:", btn.isChecked())
print("nav property:", btn.property("nav"), type(btn.property("nav")))
print("objectName:", btn.objectName())
# Check the effective stylesheet rules that match this button
style = app.style()
opt = btn.style()
# Try to see if the checked pseudo-state style is applied by checking the palette/background
print("autoFillBackground:", btn.autoFillBackground())
print("stylesheet:", btn.styleSheet()[:200] if btn.styleSheet() else "(none on button)")
# Force re-polish
btn.style().unpolish(btn)
btn.style().polish(btn)
print("after repolish, still checked:", btn.isChecked())

# Check what the app stylesheet contains for nav checked
ss = app.styleSheet()
import re
for m in re.finditer(r'QPushButton\[nav="true"\][^{]*\{[^}]*\}', ss):
    print("RULE:", m.group(0).replace("\n", " ")[:200])