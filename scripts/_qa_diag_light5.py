"""Test app-level vs button-level checked background rendering."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout

app = QApplication([])

# App-level stylesheet with various selectors
qss = """
QPushButton:checked { background: #FFFFFF; }
QPushButton[nav="true"]:checked { background: #FFFFFF; }
QPushButton#special:checked { background: #FFFFFF; }
"""
app.setStyleSheet(qss)

w = QWidget()
w.setStyleSheet("background: #2563EB;")
lay = QVBoxLayout(w)

b1 = QPushButton("plain checked")
b1.setCheckable(True)
b1.setChecked(True)
lay.addWidget(b1)

b2 = QPushButton("nav checked")
b2.setProperty("nav", True)
b2.setCheckable(True)
b2.setChecked(True)
lay.addWidget(b2)

b3 = QPushButton("special checked")
b3.setObjectName("special")
b3.setCheckable(True)
b3.setChecked(True)
lay.addWidget(b3)

w.resize(300, 160)
w.show()
app.processEvents()

for name, b in [("plain", b1), ("nav", b2), ("special", b3)]:
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 15).getRgb()[:3])
    print(f"{name}: mid={mid}")