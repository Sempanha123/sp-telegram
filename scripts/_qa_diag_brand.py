"""Test brand icon QLabel gradient rendering in sidebar structure."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import (QApplication, QLabel, QWidget, QVBoxLayout,
                               QHBoxLayout, QFrame)
from PySide6.QtCore import Qt

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

w = QFrame()
w.setObjectName("sidebar")
lay = QVBoxLayout(w)
lay.setContentsMargins(10, 14, 10, 10)
header = QFrame()
hl = QHBoxLayout(header)
hl.setContentsMargins(4, 0, 4, 8)
lbl = QLabel("SP")
lbl.setObjectName("lbl_brand_icon")
lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
hl.addWidget(lbl)
lay.addWidget(header)
w.resize(240, 120)
w.show()
app.processEvents()

img = w.grab().toImage()
print("Brand icon region (x=10..60, y=10..60):")
for y in range(12, 56, 6):
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in range(12, 56, 6)]
    print(f"  y={y}: {row}")