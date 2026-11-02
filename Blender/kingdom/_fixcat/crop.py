"""temp crop/zoom tool for QC  (system python, PIL)

usage:  python crop.py SRC OUT X Y W H [SCALE]
        python crop.py SRC OUT --grid N        (split into NxN tiles at 2x)
"""
import sys
import os
from PIL import Image, ImageDraw


def main(argv):
    src, out = argv[0], argv[1]
    im = Image.open(src).convert("RGB")
    W, H = im.size
    args = argv[2:]
    if args and args[0] == "--grid":
        n = int(args[1])
        sc = 2 if len(args) < 3 else int(args[2])
        base = os.path.splitext(out)[0]
        for i in range(n):
            for j in range(n):
                x0 = int(W * i / n)
                y0 = int(H * j / n)
                x1 = int(W * (i + 1) / n)
                y1 = int(H * (j + 1) / n)
                c = im.crop((x0, y0, x1, y1))
                c = c.resize((c.width * sc, c.height * sc), Image.NEAREST)
                c.save("%s_%d%d.png" % (base, i, j))
                print("wrote %s_%d%d.png  src=(%d,%d)-(%d,%d)" % (base, i, j, x0, y0, x1, y1))
        return
    x, y = int(args[0]), int(args[1])
    w, h = int(args[2]), int(args[3])
    sc = int(args[4]) if len(args) > 4 else 4
    c = im.crop((x, y, x + w, y + h))
    c = c.resize((c.width * sc, c.height * sc), Image.LANCZOS)
    c.save(out)
    print("src %dx%d -> crop (%d,%d,%d,%d) x%d -> %s %dx%d"
          % (W, H, x, y, w, h, sc, out, c.width, c.height))


if __name__ == "__main__":
    main(sys.argv[1:])
