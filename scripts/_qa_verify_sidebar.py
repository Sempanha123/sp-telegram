"""Analyze sidebar active state + brand icon in dark and light themes."""
from pathlib import Path

from PIL import Image


def analyze(path, label):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    print(f"=== {label} ({path}) ===")
    # Sidebar is the left ~240px. Scan for the active nav item (distinct bg).
    # Sample a vertical strip at x=30 (inside sidebar, left of text).
    print("Sidebar strip x=30 samples (y=60..300 step 20):")
    for y in range(60, 320, 20):
        print(f"  y={y}: {px[30, y]}")
    # Brand icon region (top-left, ~x=14-52, y=14-52)
    print("Brand icon region samples:")
    for y in range(16, 52, 8):
        row = [px[x, y] for x in range(16, 52, 8)]
        print(f"  y={y}: {row}")
    # Find the active item: scan for a horizontal band with a distinct bg
    # different from the sidebar base color.
    base = px[30, 300]
    active_rows = []
    for y in range(60, 500):
        c = px[30, y]
        if abs(c[0] - base[0]) + abs(c[1] - base[1]) + abs(c[2] - base[2]) > 40:
            active_rows.append((y, c))
    if active_rows:
        print(f"Active-state rows found: {len(active_rows)}")
        print(f"  first: y={active_rows[0][0]} color={active_rows[0][1]}")
        print(f"  last:  y={active_rows[-1][0]} color={active_rows[-1][1]}")
    else:
        print("NO active-state rows found (active item blends with background!)")
    print()


analyze("screenshots/qa_dark3/dashboard_dark.png", "DARK")
analyze("screenshots/qa_light9/dashboard_light.png", "LIGHT")