"""Map the layout: find sidebar bounds and colors in both themes."""
from pathlib import Path

from PIL import Image


def layout(path, label):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    print(f"=== {label} ({w}x{h}) ===")
    # Scan row y=100 across full width, print color every 20px
    print("Row y=100 across width:")
    for x in range(0, w, 20):
        print(f"  x={x}: {px[x, 100]}")
    # Find sidebar right edge: first x where color differs from sidebar base
    print()


layout("screenshots/qa_dark3/dashboard_dark.png", "DARK")
layout("screenshots/qa_light9/dashboard_light.png", "LIGHT")