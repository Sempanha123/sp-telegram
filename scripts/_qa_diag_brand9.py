"""Test WA_StyledBackground effect on QLabel/QWidget with global QWidget bg rule."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import (QApplication, QLabel, QWidget, QVBoxLayout,
                               QHBoxLayout, QFrame)
from PySide6.QtCore import Qt

app = QApplication([])

qss = """
QWidget { background: #F3F6FB; }
QFrame#sidebar { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #6D28D9); }
QFrame#sidebar_header { background: transparent; }
QLabel#lbl_app_name { color: #FFFFFF; }
"""
app.setStyleSheet(qss)

w = QFrame()
w.setObjectName("sidebar")
lay = QVBoxLayout(w)
lay.setContentsMargins(10, 14, 10, 10)
header = QFrame()
header.setObjectName("sidebar_header")
hl = QHBoxLayout(header)
hl.setContentsMargins(4, 0, 4, 8)
lbl = QLabel("SP")
lbl.setObjectName("lbl_brand_icon")
lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
lbl.setFixedSize(36, 36)
brand_text = QWidget()
brand_text.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
brand_text.setAutoFillBackground(False)
bl = QVBoxLayout(brand_text)
bl.setContentsMargins(0, 0, 0, 0)
app_name = QLabel("SP Telegram")
app_name.setObjectName("lbl_app_name")
app_name.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
app_name.setAutoFillBackground(False)
bl.addWidget(app_name)
hl.addWidget(lbl)
hl.addWidget(brand_text, 1)
lay.addWidget(header)
w.resize(240, 120)
w.show()
app.processEvents()

img = w.grab().toImage()
print("Header scan y=30:")
print("  ", [tuple(img.pixelColor(x, 30).getRgb()[:3]) for x in range(10, 240, 20)])