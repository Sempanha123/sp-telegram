"""Test if ANY background renders on nav buttons in scroll area."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import (QApplication, QPushButton, QWidget, QVBoxLayout,
                               QScrollArea, QFrame)
from PySide6.QtCore import Qt

app = QApplication([])

qss = """
QWidget { background: #2563EB; }
QPushButton[nav="true"] { min-height: 40px; background: #FF0000; border: 0; color: white; padding: 0 11px; border-radius: 9px; margin: 1px 4px; }
QFrame#sidebar QScrollArea { background: transparent; border: 0; }
QFrame#sidebar QScrollArea > QWidget > QWidget { background: transparent; }
"""
app.setStyleSheet(qss)

w = QFrame()
w.setObjectName("sidebar")
lay = QVBoxLayout(w)
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setFrameShape(QFrame.Shape.NoFrame)
scroll.setStyleSheet("background: transparent; border: 0;")
scroll.viewport().setAutoFillBackground(False)
nav_host = QWidget()
nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
nav_host.setAutoFillBackground(False)
nav = QVBoxLayout(nav_host)
b = QPushButton("Dashboard")
b.setProperty("nav", True)
nav.addWidget(b)
scroll.setWidget(nav_host)
lay.addWidget(scroll)
w.resize(240, 120)
w.show()
app.processEvents()

img = w.grab().toImage()
gpos = b.mapTo(w, b.rect().topLeft())
print("button pos:", gpos.x(), gpos.y(), "size:", b.width(), b.height())
for y in range(gpos.y()+5, gpos.y()+b.height(), 6):
    row = [tuple(img.pixelColor(x, y).getRgb()[:3]) for x in [gpos.x()+5, gpos.x()+50, gpos.x()+150, gpos.x()+200]]
    print(f"  y={y}: {row}")