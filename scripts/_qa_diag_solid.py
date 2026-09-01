"""Test solid vs transparent scroll area backgrounds for button rendering."""
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

def build(name, scroll_bg, nav_host_attrs):
    w = QFrame()
    w.setObjectName("sidebar")
    lay = QVBoxLayout(w)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    if scroll_bg == "transparent":
        scroll.setStyleSheet("background: transparent; border: 0;")
    elif scroll_bg == "solid":
        scroll.setStyleSheet("background: #2563EB; border: 0;")
    if nav_host_attrs:
        scroll.viewport().setAutoFillBackground(False)
        nav_host = QWidget()
        nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        nav_host.setAutoFillBackground(False)
    else:
        nav_host = QWidget()
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

for name, sb, attrs in [
    ("transparent + attrs", "transparent", True),
    ("solid + attrs", "solid", True),
    ("solid no attrs", "solid", False),
    ("no ss + attrs", None, True),
]:
    w, b = build(name, sb, attrs)
    app.processEvents()
    img = w.grab().toImage()
    gpos = b.mapTo(w, b.rect().topLeft())
    mid = tuple(img.pixelColor(gpos.x()+100, gpos.y()+20).getRgb()[:3])
    print(f"{name}: mid={mid}")
    w.close()