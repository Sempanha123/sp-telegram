"""Analyze dark theme screenshot pixels to verify darker + more colorful UI."""
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

img = Image.open("screenshots/qa_dark2/dashboard_dark.png").convert("RGB")
w, h = img.size
px = img.load()

# Sample the main background (top-left area, away from sidebar)
bg_samples = [px[200, 30], px[400, 100], px[600, 200], px[800, 50]]
print("Background samples:", bg_samples)
bg_avg = tuple(sum(c[i] for c in bg_samples) // len(bg_samples) for i in range(3))
print("Background average:", bg_avg)

# Sidebar sample (left edge)
sidebar = px[20, 300]
print("Sidebar sample:", sidebar)

# Brand icon (top-left of sidebar) — should be blue→purple gradient
brand = px[18, 20]
print("Brand icon sample:", brand)

# Nav active item (left sidebar, ~100px down) — should have blue tint
nav_active = px[20, 100]
print("Nav active sample:", nav_active)

# Scan the sidebar column for the brand gradient (blue/purple hues)
brand_colors = set()
for y in range(8, 40):
    r, g, b = px[18, y]
    if b > r and b > 100:  # blue/purple dominant
        brand_colors.add((r, g, b))
print("Brand gradient colors found:", len(brand_colors))

# Scan the whole image for saturated accent colors and report their locations
accent_locations = {}
for y in range(0, h, 4):
    for x in range(0, w, 4):
        r, g, b = px[x, y]
        mx, mn = max(r, g, b), min(r, g, b)
        if mx - mn > 80 and mx > 120:  # saturated accent
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            accent_locations.setdefault(key, []).append((x, y))
print("Saturated color clusters found:", len(accent_locations))
for key, locs in sorted(accent_locations.items(), key=lambda kv: -len(kv[1]))[:10]:
    xs = [p[0] for p in locs]
    ys = [p[1] for p in locs]
    print(f"  color~{key}: {len(locs)} px, x[{min(xs)}-{max(xs)}] y[{min(ys)}-{max(ys)}]")

# Check for colorful pixels (high saturation) across the image
colorful = 0
total = 0
for y in range(0, h, 8):
    for x in range(0, w, 8):
        r, g, b = px[x, y]
        mx, mn = max(r, g, b), min(r, g, b)
        if mx - mn > 60 and mx > 90:  # saturated, not too dark
            colorful += 1
        total += 1
print(f"Colorful pixel ratio: {colorful}/{total} = {colorful/total:.3f}")

# Compare with old dark theme if available
old = Path("screenshots/dark/dashboard_dark.png")
if old.exists():
    img2 = Image.open(old).convert("RGB")
    px2 = img2.load()
    old_bg = [px2[200, 30], px2[400, 100], px2[600, 200], px2[800, 50]]
    old_avg = tuple(sum(c[i] for c in old_bg) // len(old_bg) for i in range(3))
    print("OLD background average:", old_avg)
    print(f"Background darker: {sum(old_avg) > sum(bg_avg)}")
else:
    print("No old screenshot to compare")