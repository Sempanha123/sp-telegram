"""Detailed sidebar scan: find nav item bands and their colors + left borders."""
from pathlib import Path

from PIL import Image


def scan(path, label):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    print(f"=== {label} ===")
    base = px[30, 500]
    # Walk down x=30, group contiguous non-base rows into bands
    bands = []
    cur = None
    for y in range(55, 560):
        c = px[30, y]
        diff = abs(c[0]-base[0]) + abs(c[1]-base[1]) + abs(c[2]-base[2])
        if diff > 25:
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
    for b in bands:
        y0, y1, c = b
        # sample left border at x=1
        lb = px[1, (y0+y1)//2]
        # sample right side of band
        rc = px[200, (y0+y1)//2]
        print(f"  band y={y0}-{y1} (h={y1-y0+1}) center={c} leftBorder={lb} right={rc}")
    print()


scan("screenshots/qa_dark3/dashboard_dark.png", "DARK")
scan("screenshots/qa_light9/dashboard_light.png", "LIGHT")