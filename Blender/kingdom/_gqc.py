"""QC crop tool (temp, mine).  python _gqc.py <src> <x0> <y0> <x1> <y1> <scale> <dst> [grid]
Crop boxes are given in TOP-LEFT origin pixel coords of the source image.
An optional "grid" argument draws a 100 px lattice so coordinates can be read back.
"""
import sys
from PIL import Image, ImageDraw

src, x0, y0, x1, y1, scale, dst = (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
                                   int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]),
                                   sys.argv[7])
grid = "grid" in sys.argv[8:]
im = Image.open(src).convert("RGB")
W, H = im.size
x0 = max(0, x0); y0 = max(0, y0); x1 = min(W, x1); y1 = min(H, y1)
c = im.crop((x0, y0, x1, y1))
w, h = c.size
c = c.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
if grid:
    d = ImageDraw.Draw(c)
    step = int(100 * scale)
    for gx in range(0, c.size[0], step):
        d.line([(gx, 0), (gx, c.size[1])], fill=(255, 0, 255), width=1)
        d.text((gx + 2, 2), str(x0 + gx // int(scale)), fill=(255, 0, 255))
    for gy in range(0, c.size[1], step):
        d.line([(0, gy), (c.size[0], gy)], fill=(255, 0, 255), width=1)
        d.text((2, gy + 2), str(y0 + gy // int(scale)), fill=(255, 0, 255))
c.save(dst)
print("wrote %s  %dx%d  from %s [%d,%d %d,%d] x%.2f" % (dst, c.size[0], c.size[1], src,
                                                        x0, y0, x1, y1, scale))
