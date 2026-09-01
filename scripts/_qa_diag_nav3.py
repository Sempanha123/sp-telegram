"""Minimal test: does the checked gradient background paint on a QPushButton?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

qss = """
QPushButton[nav="true"] { min-height: 40px; background: transparent; border: 0; color: #9DA9BA; }
QPushButton[nav="true"]:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: #F2F5F9; border-left: 3px solid #5B9BFF; }
"""
app.setStyleSheet(qss)

w = QWidget()
w.setStyleSheet("background: #04060A;")
lay = QVBoxLayout(w)
b1 = QPushButton("Dashboard")
b1.setProperty("nav", True)
b1.setCheckable(True)
b1.setChecked(True)
lay.addWidget(b1)
b2 = QPushButton("Accounts")
b2.setProperty("nav", True)
b2.setCheckable(True)
lay.addWidget(b2)
w.resize(240, 200)
w.show()
app.processEvents()

img = b1.grab().toImage()
print("b1 (checked) size:", img.width(), img.height())
for y in [5, 10, 15, 20, 25, 30, 35]:
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in [1, 3, 10, 30, 100, 200]]
    print(f"  y={y}: {row}")

img2 = b2.grab().toImage()
print("b2 (unchecked):")
for y in [10, 20, 30]:
    row = [tuple(img2.pixelColor(x, y).getRgb()[:3]) for x in [1, 3, 10, 30, 100, 200]]
    print(f"  y={y}: {row}")