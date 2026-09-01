"""Comprehensive light dashboard body analysis."""
import sys
from pathlib import Path
from PIL import Image

img = Image.open("screenshots/qa_light14/dashboard_light.png").convert("RGB")
px = img.load()
w, h = img.size
print(f"Size: {w}x{h}")

# Sidebar is 240px. Body starts at x=240.
# Scan body background at various points (avoid cards)
print("Body background samples (x=250..1150):")
for y in (60, 120, 200, 300, 400, 500, 600, 700):
    row = [px[x, y] for x in range(250, 1150, 100)]
    print(f"  y={y}: {row}")

# Find the dominant background color in the body area
from collections import Counter
counter = Counter()
for y in range(50, h - 20, 4):
    for x in range(250, w - 20, 4):
        counter[px[x, y]] += 1
print("Top 8 colors in body area:")
for color, count in counter.most_common(8):
    print(f"  {color}: {count}")