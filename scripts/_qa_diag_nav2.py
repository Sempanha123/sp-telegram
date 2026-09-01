"""Render the checked nav button directly and inspect its pixels."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from app.theme import apply_theme
from app.widgets.sidebar import Sidebar

app = QApplication([])
apply_theme(app, "dark")
sb = Sidebar()
sb.resize(240, 900)
sb.show()
app.processEvents()

btn = sb._buttons["dashboard"]
print("checked:", btn.isChecked())
print("geometry:", btn.geometry())
img = btn.grab().toImage()
print("img size:", img.width(), img.height())
# Sample pixels
for y in [5, 10, 15, 20, 25, 30, 35]:
    row = []
    for x in [2, 5, 10, 20, 40, 80, 120, 160, 200, 230]:
        c = img.pixelColor(x, y)
        row.append((c.red(), c.green(), c.blue()))
    print(f"y={y}: {row}")

# Also render the whole sidebar
sbimg = sb.grab().toImage()
print("sidebar img:", sbimg.width(), sbimg.height())
# Find the button's global position
gpos = btn.mapTo(sb, btn.rect().topLeft())
print("button global pos in sidebar:", gpos.x(), gpos.y())
for y in range(gpos.y(), gpos.y() + btn.height(), 5):
    row = []
    for x in [gpos.x()+2, gpos.x()+10, gpos.x()+30, gpos.x()+100, gpos.x()+200]:
        c = sbimg.pixelColor(x, y)
        row.append((c.red(), c.green(), c.blue()))
    print(f"sidebar y={y}: {row}")