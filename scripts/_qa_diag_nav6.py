"""Test: gradient on QLabel vs QPushButton, and border interaction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QWidget, QVBoxLayout

app = QApplication([])

w = QWidget()
w.setStyleSheet("background: #04060A;")
lay = QVBoxLayout(w)

# QLabel with gradient
lbl = QLabel("LABEL")
lbl.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5B9BFF, stop:0.55 #8B5CF6, stop:1 #B495FF); color: white;")
lay.addWidget(lbl)

# QPushButton with gradient, no border
b1 = QPushButton("BTN no border")
b1.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: white;")
lay.addWidget(b1)

# QPushButton with gradient + border-left
b2 = QPushButton("BTN border-left")
b2.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: white; border-left: 3px solid #5B9BFF;")
lay.addWidget(b2)

# QPushButton with gradient + full border
b3 = QPushButton("BTN full border")
b3.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16243A, stop:1 #101724); color: white; border: 1px solid #5B9BFF;")
lay.addWidget(b3)

w.resize(300, 220)
w.show()
app.processEvents()

for name, b in [("LABEL", lbl), ("BTN no border", b1), ("BTN border-left", b2), ("BTN full border", b3)]:
    img = b.grab().toImage()
    mid = tuple(img.pixelColor(img.width()//2, 20).getRgb()[:3])
    left = tuple(img.pixelColor(1, 20).getRgb()[:3])
    print(f"{name}: mid={mid} left={left}")