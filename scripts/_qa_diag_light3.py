"""Isolate which base property breaks the checked background."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

cases = {
    "plain": 'QPushButton[nav="true"] { background: transparent; }',
    "border0": 'QPushButton[nav="true"] { background: transparent; border: 0; }',
    "radius": 'QPushButton[nav="true"] { background: transparent; border-radius: 9px; }',
    "border0_radius": 'QPushButton[nav="true"] { background: transparent; border: 0; border-radius: 9px; }',
    "margin": 'QPushButton[nav="true"] { background: transparent; margin: 1px 4px; }',
    "minheight": 'QPushButton[nav="true"] { background: transparent; min-height: 40px; }',
    "padding": 'QPushButton[nav="true"] { background: transparent; padding: 0 11px; }',
    "textalign": 'QPushButton[nav="true"] { background: transparent; text-align: left; }',
    "full": 'QPushButton[nav="true"] { min-height: 40px; text-align: left; background: transparent; border: 0; color: rgba(255,255,255,200); padding: 0 11px; border-radius: 9px; margin: 1px 4px; }',
}

w = QWidget()
w.setStyleSheet("background: #2563EB;")
lay = QVBoxLayout(w)
btns = {}
for name, base in cases.items():
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    b.setStyleSheet(base + '\nQPushButton[nav="true"]:checked { background: #FFFFFF; color: #1D4ED8; }')
    lay.addWidget(b)
    btns[name] = b
w.resize(300, 400)
w.show()
app.processEvents()

for name, b in btns.items():
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    print(f"{name}: mid={mid}")