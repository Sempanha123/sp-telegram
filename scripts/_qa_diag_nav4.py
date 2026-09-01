"""Test which background syntax paints on a checked QPushButton."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

variants = {
    "solid": "background: #16243A;",
    "gradient_nospace": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724);",
    "gradient_space": "background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #16243A, stop: 1 #101724);",
    "gradient_rgba": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(22,36,58,255), stop:1 rgba(16,23,36,255));",
    "bgcolor_gradient": "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724);",
}

w = QWidget()
w.setStyleSheet("background: #04060A;")
lay = QVBoxLayout(w)
btns = {}
for name, bg in variants.items():
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    b.setStyleSheet(f'QPushButton[nav="true"]:checked {{ {bg} color: #F2F5F9; border-left: 3px solid #5B9BFF; }}')
    lay.addWidget(b)
    btns[name] = b
w.resize(300, 260)
w.show()
app.processEvents()

for name, b in btns.items():
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    left = tuple(img.pixelColor(1, 20).getRgb()[:3])
    print(f"{name}: mid={mid} left={left}")