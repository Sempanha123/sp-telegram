"""Test removing WA_StyledBackground from nav_host."""
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

def build(name, styled_bg):
    w = QFrame()
    w.setObjectName("sidebar")
    lay = QVBoxLayout(w)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("background: transparent; border: 0;")
    scroll.viewport().setAutoFillBackground(False)
    nav_host = QWidget()
    if styled_bg:
        nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    nav_host.setAutoFillBackground(False)
    nav = QVBoxLayout(nav_host)
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    nav.addWidget(b)
    # add a spacer to see the gradient below the button
    nav.addStretch()
    scroll.setWidget(nav_host)
    lay.addWidget(scroll)
    w.resize(240, 200)
    w.show()
    return w, b

for name, styled_bg in [("WITH WA_StyledBackground=False", True), ("WITHOUT WA_StyledBackground", False)]:
    w, b = build(name, styled_bg)
    app.processEvents()
    img = w.grab().toImage()
    gpos = b.mapTo(w, b.rect().topLeft())
    mid = tuple(img.pixelColor(gpos.x()+100, gpos.y()+20).getRgb()[:3])
    # sample below the button (should be sidebar gradient if nav_host transparent)
    below = tuple(img.pixelColor(120, gpos.y()+b.height()+30).getRgb()[:3])
    print(f"{name}: button_mid={mid} below_button={below}")
    w.close()