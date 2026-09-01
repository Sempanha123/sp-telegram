"""Test each scroll-area detail individually."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import (QApplication, QPushButton, QWidget, QVBoxLayout,
                               QScrollArea, QFrame)
from PySide6.QtCore import Qt

app = QApplication([])

qss = """
QWidget { background: #2563EB; }
QPushButton[nav="true"] { min-height: 40px; text-align: left; background: transparent; border: 0; color: rgba(255,255,255,200); padding: 0 11px; border-radius: 9px; margin: 1px 4px; }
QPushButton[nav="true"]:checked { background: #FFFFFF; color: #1D4ED8; font-weight: 700; }
QFrame#sidebar QScrollArea { background: transparent; border: 0; }
QFrame#sidebar QScrollArea > QWidget > QWidget { background: transparent; }
"""
app.setStyleSheet(qss)

def build(name, scroll_ss, autofill_viewport, autofill_host, styled_bg):
    w = QFrame()
    w.setObjectName("sidebar")
    lay = QVBoxLayout(w)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    if scroll_ss:
        scroll.setStyleSheet("background: transparent; border: 0;")
    if autofill_viewport:
        scroll.viewport().setAutoFillBackground(False)
    nav_host = QWidget()
    if styled_bg:
        nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    if autofill_host:
        nav_host.setAutoFillBackground(False)
    nav = QVBoxLayout(nav_host)
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    nav.addWidget(b)
    scroll.setWidget(nav_host)
    lay.addWidget(scroll)
    w.resize(240, 120)
    w.show()
    return w, b

cases = [
    ("baseline scroll", False, False, False, False),
    ("+ scroll_ss", True, False, False, False),
    ("+ autofill_viewport", False, True, False, False),
    ("+ autofill_host", False, False, True, False),
    ("+ styled_bg", False, False, False, True),
    ("+ scroll_ss + autofill_viewport", True, True, False, False),
]

for name, ss, av, ah, sb in cases:
    w, b = build(name, ss, av, ah, sb)
    app.processEvents()
    img = w.grab().toImage()
    gpos = b.mapTo(w, b.rect().topLeft())
    mid = tuple(img.pixelColor(gpos.x()+100, gpos.y()+20).getRgb()[:3])
    print(f"{name}: mid={mid}")
    w.close()