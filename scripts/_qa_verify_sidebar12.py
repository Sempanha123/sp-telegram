"""Fine scan for app name text visibility in light header."""
import sys
from pathlib import Path
from PIL import Image

img = Image.open("screenshots/qa_light13/dashboard_light.png").convert("RGB")
px = img.load()

# Scan app name area for white-ish pixels (text)
print("Light app name area (x=60..200, y=14..40) white pixel count:")
white = 0
for y in range(14, 41):
    for x in range(60, 201):
        r, g, b = px[x, y]
        if r > 200 and g > 200 and b > 200:
            white += 1
print(f"  white pixels: {white}")

# Show a few rows in the app name area
print("Rows y=20,24,28,32 in x=60..180:")
for y in (20, 24, 28, 32):
    row = [px[x, y] for x in range(60, 181, 6)]
    print(f"  y={y}: {row}")