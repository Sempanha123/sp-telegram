"""Test if scroll area / nav_host attributes break the checked background."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import (QApplication, QPushButton, QWidget, QVBoxLayout,
                               QScrollArea, QFrame)
from PySide6.QtCore import Qt

app = QApplication([])

qss = """
QPushButton[nav="true"] { min-height: 40px; text-align: left; background: transparent; border: 0; color: rgba(255,255,255,200); padding: 0 11px; border-radius: 9px; margin: 1px 4px; }
QPushButton[nav="true"]:checked { background: #FFFFFF; color: #1D4ED8; font-weight: 700; }
QFrame#sidebar QScrollArea { background: transparent; border: 0; }
QFrame#sidebar QScrollArea > QWidget > QWidget { background: transparent; }
"""
app.setStyleSheet(qss)

def make_btn(name):
    b = QPushButton(name)
    b.setProperty("nav", True)
    b.setCheckable(True)
    b.setChecked(True)
    return b

# Case 1: plain widget container
w1 = QWidget()
w1.setStyleSheet("background: #2563EB;")
lay1 = QVBoxLayout(w1)
lay1.addWidget(make_btn("plain container"))

# Case 2: scroll area with nav_host WA_StyledBackground False
w2 = QFrame()
w2.setObjectName("sidebar")
w2.setStyleSheet("background: #2563EB;")
lay2 = QVBoxLayout(w2)
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setFrameShape(QFrame.Shape.NoFrame)
scroll.setStyleSheet("background: transparent; border: 0;")
scroll.viewport().setAutoFillBackground(False)
nav_host = QWidget()
nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
nav_host.setAutoFillBackground(False)
nav = QVBoxLayout(nav_host)
nav.addWidget(make_btn("scroll container"))
scroll.setWidget(nav_host)
lay2.addWidget(scroll)

w1.resize(240, 120)
w2.resize(240, 120)
w1.show()
w2.show()
app.processEvents()

for name, w in [("plain container", w1), ("scroll container", w2)]:
    btn = w.findChild(QPushButton)
    img = btn.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    print(f"{name}: mid={mid}")