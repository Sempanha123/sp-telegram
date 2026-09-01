"""Find white/checked regions in the light sidebar."""
from PIL import Image

img = Image.open("screenshots/qa_light9/dashboard_light.png").convert("RGB")
px = img.load()

# Scan the sidebar (x=0-240) for near-white pixels (checked item = white bg)
print("Light sidebar white-region scan (x=0-240):")
for y in range(50, 560, 4):
    row = []
    for x in range(0, 240, 8):
        c = px[x, y]
        if c[0] > 235 and c[1] > 235 and c[2] > 235:
            row.append("W")
        elif c[0] > 200 and c[1] > 200 and c[2] > 200:
            row.append("w")
        else:
            row.append(".")
    line = "".join(row)
    if "W" in line or "w" in line:
        print(f"  y={y}: {line}")

# Also check dark theme for any lighter-than-base regions
img2 = Image.open("screenshots/qa_dark3/dashboard_dark.png").convert("RGB")
px2 = img2.load()
print("\nDark sidebar lighter-region scan (x=0-240):")
for y in range(50, 560, 4):
    row = []
    for x in range(0, 240, 8):
        c = px2[x, y]
        # lighter than base (4,6,10) by a lot
        if c[0] + c[1] + c[2] > 90:
            row.append("L")
        else:
            row.append(".")
    line = "".join(row)
    if "L" in line:
        print(f"  y={y}: {line}")