"""Test exact light nav rules with whole-window render."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

qss = """
QWidget { background: #2563EB; }
QPushButton[nav="true"] { min-height: 40px; text-align: left; background: transparent; border: 0; color: rgba(255,255,255,200); padding: 0 11px; border-radius: 9px; margin: 1px 4px; }
QPushButton[nav="true"]:hover { background: rgba(255,255,255,28); color: #FFFFFF; }
QPushButton[nav="true"]:checked { background: #FFFFFF; color: #1D4ED8; font-weight: 700; }
"""
app.setStyleSheet(qss)

w = QWidget()
lay = QVBoxLayout(w)
b = QPushButton("Dashboard")
b.setProperty("nav", True)
b.setCheckable(True)
b.setChecked(True)
lay.addWidget(b)
w.resize(300, 120)
w.show()
app.processEvents()

img = w.grab().toImage()
gpos = b.mapTo(w, b.rect().topLeft())
print("button pos:", gpos.x(), gpos.y(), "size:", b.width(), b.height())
for y in range(gpos.y()+5, gpos.y()+b.height(), 6):
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in [gpos.x()+5, gpos.x()+50, gpos.x()+150, gpos.x()+250]]
    print(f"  y={y}: {row}")