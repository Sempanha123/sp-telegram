"""Precise pixel sampling to resolve layout confusion."""
from PIL import Image

for path, label in [
    ("screenshots/qa_dark3/dashboard_dark.png", "DARK"),
    ("screenshots/qa_light9/dashboard_light.png", "LIGHT"),
]:
    img = Image.open(path).convert("RGB")
    px = img.load()
    print(f"=== {label} ===")
    for y in [60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300]:
        print(f"  y={y}: x=5:{px[5,y]} x=30:{px[30,y]} x=60:{px[60,y]} x=120:{px[120,y]} x=200:{px[200,y]} x=235:{px[235,y]}")
    print()