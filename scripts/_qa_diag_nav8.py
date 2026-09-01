"""Confirm: gradient fails only with pseudo-state on QPushButton."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

w = QWidget()
w.setStyleSheet("background: #04060A;")
lay = QVBoxLayout(w)

def make(name, qss, checked=False):
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(checked)
    b.setStyleSheet(qss)
    lay.addWidget(b)
    return b

g = "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: white;"

b1 = make("prop no pseudo", f'QPushButton[nav="true"] {{ {g} }}')
b2 = make("pseudo no prop", f'QPushButton:checked {{ {g} }}')
b3 = make("prop+pseudo", f'QPushButton[nav="true"]:checked {{ {g} }}')
b4 = make("no selector", f'QPushButton {{ {g} }}')
b5 = make("hover", f'QPushButton[nav="true"]:hover {{ {g} }}')

w.resize(300, 260)
w.show()
app.processEvents()

for name, b in [("prop no pseudo", b1), ("pseudo no prop", b2), ("prop+pseudo", b3), ("no selector", b4), ("hover", b5)]:
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    print(f"{name}: mid={mid}")