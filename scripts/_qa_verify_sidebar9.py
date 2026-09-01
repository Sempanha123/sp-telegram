"""Verify sidebar brand icon + header + checked state with real theme QSS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from app.widgets.sidebar import Sidebar
from app.styles.tokens import DARK, LIGHT

STYLES = Path(__file__).resolve().parent.parent / "app" / "styles"

def load_qss(theme):
    if theme == "light":
        return (STYLES / "light.qss").read_text(encoding="utf-8")
    base = (STYLES / "dark.qss").read_text(encoding="utf-8")
    comp = (STYLES / "components.qss").read_text(encoding="utf-8")
    return base + "\n" + comp

def test(theme):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(load_qss(theme))
    sb = Sidebar()
    sb.show()
    app.processEvents()
    lbl = sb.lbl_brand_icon
    gx, gy = lbl.geometry().x(), lbl.geometry().y()
    img = sb.grab().toImage()
    print(f"=== {theme.upper()} ===")
    print(f"brand icon geometry: ({gx},{gy}) {lbl.width()}x{lbl.height()}")
    # brand icon center
    mid = tuple(img.pixelColor(gx + 18, gy + 18).getRgb()[:3])
    print(f"brand_center: {mid}")
    # brand icon top-left corner (should be gradient, not sidebar bg)
    tl = tuple(img.pixelColor(gx + 3, gy + 3).getRgb()[:3])
    print(f"brand_topleft: {tl}")
    # header area (right of brand icon, should be sidebar gradient not #F3F6FB)
    hx = gx + 60
    hy = gy + 10
    hc = tuple(img.pixelColor(hx, hy).getRgb()[:3])
    print(f"header_area ({hx},{hy}): {hc}")
    # checked nav button (dashboard is checked by default)
    btn = sb._buttons["dashboard"]
    top_left = btn.mapTo(sb, btn.rect().topLeft())
    bx, by = top_left.x(), top_left.y()
    bc = tuple(img.pixelColor(bx + 20, by + 20).getRgb()[:3])
    print(f"checked_btn_center: {bc}")
    # left border of checked button
    bl = tuple(img.pixelColor(bx + 2, by + 20).getRgb()[:3])
    print(f"checked_btn_leftborder: {bl}")
    # left border at x=0..3 (should be accent color)
    for x in range(0, 6):
        print(f"  x={x}: {tuple(img.pixelColor(bx + x, by + 20).getRgb()[:3])}")
    sb.close()

test("dark")
test("light")