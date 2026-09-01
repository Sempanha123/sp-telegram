"""Verify sidebar fixes: active state + brand icon in both themes."""
from PIL import Image


def scan(path, label):
    img = Image.open(path).convert("RGB")
    px = img.load()
    print(f"=== {label} ===")
    # Find the checked nav item: scan x=30 column for a band distinct from sidebar base
    base = px[30, 500]
    bands = []
    cur = None
    for y in range(55, 560):
        c = px[30, y]
        diff = abs(c[0]-base[0]) + abs(c[1]-base[1]) + abs(c[2]-base[2])
        if diff > 40:
            if cur is None:
                cur = [y, y, c]
            else:
                cur[1] = y
        else:
            if cur is not None:
                bands.append(cur)
                cur = None
    if cur:
        bands.append(cur)
    # Filter to wide bands (button backgrounds, not text glyphs)
    wide = [b for b in bands if b[1]-b[0] >= 20]
    print(f"Wide bands (button backgrounds) at x=30:")
    for b in wide:
        y0, y1, c = b
        lb = px[1, (y0+y1)//2]
        print(f"  y={y0}-{y1} (h={y1-y0+1}) color={c} leftBorder={lb}")
    if not wide:
        print("  NONE — active state not visible!")
    # Brand icon region
    print("Brand icon region (x=14-52, y=14-52):")
    for y in [18, 26, 34, 42]:
        row = [px[x, y] for x in [16, 24, 32, 40, 48]]
        print(f"  y={y}: {row}")
    # Header area (right of brand icon) — should be sidebar gradient, not page bg
    print("Header area x=120 samples:")
    for y in [20, 30, 40, 50]:
        print(f"  y={y}: {px[120, y]}")
    print()


scan("screenshots/qa_dark4/dashboard_dark.png", "DARK")
scan("screenshots/qa_light10/dashboard_light.png", "LIGHT")