"""Detailed scan of brand icon region and checked item left border."""
from PIL import Image


def scan(path, label):
    img = Image.open(path).convert("RGB")
    px = img.load()
    print(f"=== {label} ===")
    # Brand icon region: scan x=10..60, y=10..60
    print("Brand icon region (x=10..60, y=10..60):")
    for y in range(12, 56, 6):
        row = [px[x, y] for x in range(12, 56, 6)]
        print(f"  y={y}: {row}")
    # Checked item left border: find the checked band first
    base = px[30, 500]
    for y in range(55, 560):
        c = px[30, y]
        if abs(c[0]-base[0]) + abs(c[1]-base[1]) + abs(c[2]-base[2]) > 40:
            # found a band start; check left border at x=0..10
            print(f"Band at y={y}, color={c}")
            for x in range(0, 12):
                print(f"  x={x}: {px[x, y+20]}")
            break
    print()


scan("screenshots/qa_dark4/dashboard_dark.png", "DARK")
scan("screenshots/qa_light10/dashboard_light.png", "LIGHT")