"""Verify full-app captures: sidebar brand, active state, header, body bg."""
import sys
from pathlib import Path
from PIL import Image

def analyze(path, label):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    print(f"=== {label} ({w}x{h}) ===")
    px = img.load()
    # Sidebar is ~240px wide
    # Brand icon: x=14..50, y=14..50 (approx)
    print("Brand icon row y=30:")
    print("  ", [px[x, 30] for x in range(14, 52, 4)])
    # Header area right of brand (x=120, y=30)
    print(f"header_area (120,30): {px[120, 30]}")
    # Active nav (dashboard) - find it: first nav button after header+collapse
    # scan down the sidebar for the checked band
    print("Sidebar column x=20 scan (y=60..200):")
    for y in range(60, 200, 10):
        print(f"  y={y}: {px[20, y]}")
    # Body area (right of sidebar)
    print(f"body_area (500, 200): {px[500, 200]}")
    print(f"body_area (800, 400): {px[800, 400]}")
    print()

analyze("screenshots/qa_dark6/dashboard_dark.png", "DARK")
analyze("screenshots/qa_light13/dashboard_light.png", "LIGHT")