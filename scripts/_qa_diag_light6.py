"""Render whole window and sample checked button position."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout
from PySide6.QtGui import QImage

app = QApplication([])

qss = """
QWidget { background: #2563EB; }
QPushButton:checked { background: #FFFFFF; color: #1D4ED8; }
"""
app.setStyleSheet(qss)

w = QWidget()
lay = QVBoxLayout(w)
b = QPushButton("Checked Button")
b.setCheckable(True)
b.setChecked(True)
lay.addWidget(b)
w.resize(300, 120)
w.show()
app.processEvents()

# Render whole window
img = w.grab().toImage()
print("window img:", img.width(), img.height())
# Find button position
gpos = b.mapTo(w, b.rect().topLeft())
print("button pos:", gpos.x(), gpos.y(), "size:", b.width(), b.height())
for y in range(gpos.y(), gpos.y() + b.height(), 5):
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in [gpos.x()+5, gpos.x()+50, gpos.x()+150, gpos.x()+250]]
    print(f"  y={y}: {row}")