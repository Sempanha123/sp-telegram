"""Map light sidebar elements precisely."""
from PIL import Image

img = Image.open("screenshots/qa_light9/dashboard_light.png").convert("RGB")
px = img.load()

print("Light sidebar x=30 column, y=40..120 (every 2px):")
for y in range(40, 122, 2):
    c = px[30, y]
    print(f"  y={y}: {c}")

print("\nLight sidebar x=120 column, y=40..120 (every 2px):")
for y in range(40, 122, 2):
    c = px[120, y]
    print(f"  y={y}: {c}")