"""Detailed light header scan to distinguish text from background."""
import sys
from pathlib import Path
from PIL import Image

img = Image.open("screenshots/qa_light13/dashboard_light.png").convert("RGB")
px = img.load()

print("Light header horizontal scan at y=20 (above text):")
print("  ", [px[x, 20] for x in range(10, 240, 10)])
print("Light header horizontal scan at y=40 (below text):")
print("  ", [px[x, 40] for x in range(10, 240, 10)])
print("Light header horizontal scan at y=30 (text row):")
print("  ", [px[x, 30] for x in range(10, 240, 10)])
print("Light header vertical scan at x=120:")
print("  ", [px[120, y] for y in range(10, 60, 5)])
print("Light header vertical scan at x=60:")
print("  ", [px[60, y] for y in range(10, 60, 5)])