"""Final comprehensive sidebar + theme verification."""
import sys
from pathlib import Path
from PIL import Image

def analyze(path, label):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    print(f"=== {label} ({w}x{h}) ===")
    # Brand icon row
    print("Brand icon y=30:", [px[x, 30] for x in range(14, 52, 4)])
    # Header area (right of brand, should be sidebar bg not global bg)
    print(f"Header x=120 y=20: {px[120, 20]}")
    # Active nav (dashboard) - scan sidebar column
    active = None
    for y in range(60, 220, 5):
        c = px[20, y]
        if label == "DARK" and c == (22, 36, 58):
            active = y
            break
        if label == "LIGHT" and c == (255, 255, 255):
            active = y
            break
    print(f"Active nav found at y={active}")
    if active:
        print(f"  left border x=0..5: {[px[10 + x, active + 20] for x in range(0, 6)]}")
    # Body background
    print(f"Body bg (500, 300): {px[500, 300]}")
    print()

analyze("screenshots/qa_dark7/dashboard_dark.png", "DARK")
analyze("screenshots/qa_light15/dashboard_light.png", "LIGHT")