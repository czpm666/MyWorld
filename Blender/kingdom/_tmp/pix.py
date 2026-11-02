"""Palette census of a rendered frame: which colours actually dominate?

    python _tmp/pix.py <png> [top]
"""
import sys
from collections import Counter

from PIL import Image

path = sys.argv[1]
top = int(sys.argv[2]) if len(sys.argv) > 2 else 12
im = Image.open(path).convert("RGB")
w, h = im.size
small = im.resize((w // 6, h // 6))
c = Counter(small.getdata())
print("image", w, "x", h)
tot = sum(c.values())
for rgb, n in c.most_common(top):
    print("  #%02x%02x%02x  %5.1f%%  rgb%s" % (rgb[0], rgb[1], rgb[2], 100.0 * n / tot, rgb))


def patch(name, x0, y0, x1, y1):
    px = [im.getpixel((x, y)) for y in range(y0, y1, 3) for x in range(x0, x1, 3)]
    n = len(px)
    m = tuple(sum(p[i] for p in px) // n for i in range(3))
    print("  %-12s avg #%02x%02x%02x" % (name, m[0], m[1], m[2]))


print("patches (image coords):")
for arg in sys.argv[3:]:
    nm, box = arg.split("=")
    x0, y0, x1, y1 = (int(v) for v in box.split(","))
    patch(nm, x0, y0, x1, y1)
