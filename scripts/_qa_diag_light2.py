"""Test exact light.qss nav rules to find why checked white doesn't render."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

# Exact light.qss nav rules
qss = """
QPushButton[nav="true"] { min-height: 40px; text-align: left; background: transparent; border: 0; color: rgba(255,255,255,200); padding: 0 11px; border-radius: 9px; margin: 1px 4px; }
QPushButton[nav="true"]:hover { background: rgba(255,255,255,28); color: #FFFFFF; }
QPushButton[nav="true"]:checked { background: #FFFFFF; color: #1D4ED8; font-weight: 700; }
"""
app.setStyleSheet(qss)

w = QWidget()
w.setStyleSheet("background: #2563EB;")
lay = QVBoxLayout(w)
b1 = QPushButton("Dashboard")
b1.setProperty("nav", True)
b1.setCheckable(True)
b1.setChecked(True)
lay.addWidget(b1)
w.resize(240, 100)
w.show()
app.processEvents()

img = b1.grab().toImage()
print("checked button pixels:")
for y in [5, 10, 15, 20, 25, 30, 35]:
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in [2, 10, 30, 100, 200]]
    print(f"  y={y}: {row}")