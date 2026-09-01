"""Test: does base 'background: transparent' break the checked gradient?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

cases = {
    "base_transparent": (
        'QPushButton[nav="true"] { background: transparent; color: #9DA9BA; }',
        'QPushButton[nav="true"]:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: #F2F5F9; }',
    ),
    "base_none": (
        'QPushButton[nav="true"] { color: #9DA9BA; }',
        'QPushButton[nav="true"]:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: #F2F5F9; }',
    ),
    "base_solid": (
        'QPushButton[nav="true"] { background: #04060A; color: #9DA9BA; }',
        'QPushButton[nav="true"]:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: #F2F5F9; }',
    ),
    "checked_solid": (
        'QPushButton[nav="true"] { background: transparent; color: #9DA9BA; }',
        'QPushButton[nav="true"]:checked { background: #16243A; color: #F2F5F9; }',
    ),
}

w = QWidget()
w.setStyleSheet("background: #04060A;")
lay = QVBoxLayout(w)
btns = {}
for name, (base, checked) in cases.items():
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    b.setStyleSheet(base + "\n" + checked)
    lay.addWidget(b)
    btns[name] = b
w.resize(300, 220)
w.show()
app.processEvents()

for name, b in btns.items():
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    print(f"{name}: mid={mid}")