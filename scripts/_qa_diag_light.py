"""Test light theme checked nav rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication

from app.theme import apply_theme
from app.widgets.sidebar import Sidebar

app = QApplication([])
apply_theme(app, "light")
sb = Sidebar()
sb.resize(240, 900)
sb.show()
app.processEvents()

btn = sb._buttons["dashboard"]
print("checked:", btn.isChecked())
print("geometry:", btn.geometry())
gpos = btn.mapTo(sb, btn.rect().topLeft())
print("global pos:", gpos.x(), gpos.y())

sbimg = sb.grab().toImage()
print("sidebar img:", sbimg.width(), sbimg.height())
for y in range(gpos.y(), gpos.y() + btn.height(), 4):
    row = []
    for x in [gpos.x()+2, gpos.x()+10, gpos.x()+30, gpos.x()+100, gpos.x()+200]:
        c = sbimg.pixelColor(x, y)
        row.append((c.red(), c.green(), c.blue()))
    print(f"  y={y}: {row}")

# Also check the header area (brand)
print("\nHeader area (brand) samples:")
for y in [16, 24, 32, 40, 48, 56]:
    row = []
    for x in [5, 30, 60, 120, 200]:
        c = sbimg.pixelColor(x, y)
        row.append((c.red(), c.green(), c.blue()))
    print(f"  y={y}: {row}")