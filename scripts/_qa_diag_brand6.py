"""Test real Sidebar widget brand icon rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from app.widgets.sidebar import Sidebar

app = QApplication([])

qss = """
QWidget { background: #070A11; }
QFrame#sidebar { background: #04060A; }
QFrame#sidebar QFrame { background: transparent; }
QLabel#lbl_brand_icon {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5B9BFF, stop:0.55 #8B5CF6, stop:1 #B495FF);
    color: white;
    border-radius: 9px;
    font-size: 14px;
    font-weight: 800;
    min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
}
"""
app.setStyleSheet(qss)

sb = Sidebar()
sb.show()
app.processEvents()

lbl = sb.lbl_brand_icon
print("lbl geometry:", lbl.geometry())
print("lbl global pos:", lbl.mapToGlobal(lbl.rect().topLeft()))
print("sidebar pos:", sb.mapToGlobal(sb.rect().topLeft()))

img = sb.grab().toImage()
print("sidebar grab size:", img.width(), img.height())
# scan the brand icon area based on geometry
gx, gy = lbl.geometry().x(), lbl.geometry().y()
print(f"Brand icon region (x={gx}..{gx+36}, y={gy}..{gy+36}):")
for y in range(gy, gy + 36, 6):
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in range(gx, gx + 36, 6)]
    print(f"  y={y}: {row}")