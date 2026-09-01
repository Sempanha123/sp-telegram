"""Test real Sidebar brand icon with/without QFrame transparency rule."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from app.widgets.sidebar import Sidebar

app = QApplication([])

def test(name, include_qframe_rule):
    qss = """
QWidget { background: #070A11; }
QFrame#sidebar { background: #04060A; }
"""
    if include_qframe_rule:
        qss += "QFrame#sidebar QFrame { background: transparent; }\n"
    qss += """
QLabel#lbl_brand_icon {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5B9BFF, stop:0.55 #8B5CF6, stop:1 #B495FF);
    color: white;
    border-radius: 9px;
    font-size: 14px;
    font-weight: 800;
    min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
}
"""
    app.setStyleSheet(qss)
    sb = Sidebar()
    sb.show()
    app.processEvents()
    lbl = sb.lbl_brand_icon
    gx, gy = lbl.geometry().x(), lbl.geometry().y()
    img = sb.grab().toImage()
    # sample brand icon center
    mid = tuple(img.pixelColor(gx + 18, gy + 18).getRgb()[:3])
    print(f"{name}: brand_center=({gx+18},{gy+18}) -> {mid}")
    sb.close()

test("WITHOUT QFrame rule", False)
test("WITH QFrame rule", True)