"""Test gradient stop syntax variants."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

variants = {
    "stop_decimal": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop: 0.0 #16243A, stop: 1.0 #101724);",
    "stop_int": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop: 0 #16243A, stop: 1 #101724);",
    "stop_pct": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop: 0% #16243A, stop: 100% #101724);",
    "two_colors": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724);",
    "rgba_stops": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(22,36,58,1), stop:1 rgba(16,23,36,1));",
    "no_stops": "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A);",
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
    b.setStyleSheet(f'QPushButton[nav="true"]:checked {{ {bg} color: #F2F5F9; }}')
    lay.addWidget(b)
    btns[name] = b
w.resize(300, 260)
w.show()
app.processEvents()

for name, b in btns.items():
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    print(f"{name}: mid={mid}")