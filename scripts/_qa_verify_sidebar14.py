"""Analyze light topbar and body structure."""
import sys
from pathlib import Path
from PIL import Image

img = Image.open("screenshots/qa_light13/dashboard_light.png").convert("RGB")
px = img.load()
w, h = img.size

# Topbar area (y=0..64)
print("Topbar scan y=30 (x=250..1150):")
print("  ", [px[x, 30] for x in range(250, 1150, 100)])
print("Topbar scan y=60 (x=250..1150):")
print("  ", [px[x, 60] for x in range(250, 1150, 100)])

# Page header area (y=80..120)
print("Page header y=90 (x=250..1150):")
print("  ", [px[x, 90] for x in range(250, 1150, 100)])

# Accent cards area (y=140..260)
print("Accent cards y=180 (x=250..1150):")
print("  ", [px[x, 180] for x in range(250, 1150, 100)])

# Check the sidebar gradient at various y
print("Sidebar gradient x=120 (y=0..700):")
print("  ", [px[120, y] for y in range(0, 700, 50)])