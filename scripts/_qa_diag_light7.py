"""Compare grab() vs render() for the real Sidebar checked button."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter

from app.theme import apply_theme
from app.widgets.sidebar import Sidebar

app = QApplication([])
apply_theme(app, "light")
sb = Sidebar()
sb.resize(240, 900)
sb.show()
app.processEvents()

btn = sb._buttons["dashboard"]
gpos = btn.mapTo(sb, btn.rect().topLeft())
print("button pos:", gpos.x(), gpos.y(), "size:", btn.width(), btn.height())

# Method 1: grab()
img1 = sb.grab().toImage()
print("grab() samples:")
for y in range(gpos.y()+5, gpos.y()+btn.height(), 8):
    row = [tuple(img1.pixelColor(x, y).getRgb()[:3]) for x in [gpos.x()+5, gpos.x()+100]]
    print(f"  y={y}: {row}")

# Method 2: render() into QImage
img2 = QImage(sb.size(), QImage.Format.Format_ARGB32)
img2.fill(0)
painter = QPainter(img2)
sb.render(painter)
painter.end()
print("render() samples:")
for y in range(gpos.y()+5, gpos.y()+btn.height(), 8):
    row = [tuple(img2.pixelColor(x, y).getRgb()[:3]) for x in [gpos.x()+5, gpos.x()+100]]
    print(f"  y={y}: {row}")