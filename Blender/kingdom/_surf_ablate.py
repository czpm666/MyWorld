"""_surf_ablate.py -- how much does each hd_surface layer move the picture?

Compares every `_surf_wall_<layer>.png` (that one layer disabled) against
`_surf_wall_cur.png` (all layers on) over the wall face, and prints the mean,
the sigma and the green-pixel delta each layer is responsible for.  That is the
only honest way to keep the total inside the "-2 % .. 0 %" exposure budget and
to prove that the green comes from the moss layer and not from a global tint.

USAGE
    python _surf_ablate.py [--crop x0,y0,x1,y1]
"""

import argparse
import glob
import os

import numpy as np
from PIL import Image

R709 = np.array([0.2126, 0.7152, 0.0722])
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "renders", "kingdom")


def rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def luma(a):
    return a @ R709


def green_px(a):
    return int((a[:, :, 1] - np.maximum(a[:, :, 0], a[:, :, 2]) > 8).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", default="40,90,760,345")
    a = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.crop.split(","))

    def cut(a):
        return a[y0:y1, x0:x1]

    cb = cut(rgb(os.path.join(OUT, "_surf_wall_cur.png")))
    rb = cut(rgb(os.path.join(OUT, "_surf_wall_before.png")))
    lb, lc = luma(rb), luma(cb)
    print("crop (%d,%d)-(%d,%d)" % (x0, y0, x1, y1))
    print("pristine  mean %7.2f  sigma %6.2f  green %6d"
          % (lb.mean(), lb.std(), green_px(rb)))
    print("all-on    mean %7.2f  sigma %6.2f  green %6d   (%+.2f%%, sigma %+.1f%%, green x%.1f)"
          % (lc.mean(), lc.std(), green_px(cb), 100 * (lc.mean() / lb.mean() - 1),
             100 * (lc.std() / lb.std() - 1),
             green_px(cb) / max(1, green_px(rb))))
    print("  %-11s %7s %7s %7s %8s" % ("-layer", "dMean", "dSig", "dGreen", "luma%"))
    rows = []
    for p in sorted(glob.glob(os.path.join(OUT, "_surf_wall_no_*.png"))):
        tag = os.path.basename(p)[len("_surf_wall_"):-4]
        g = cut(rgb(p))
        lg = luma(g)
        rows.append((lg.mean() - lc.mean(), lg.std() - lc.std(),
                     green_px(g) - green_px(cb), tag,
                     100 * (lc.mean() / lg.mean() - 1)))
    for dm, ds, dg, tag, pct in sorted(rows, reverse=True):
        print("  %-11s %+7.2f %+7.2f %+7d %+7.2f%%   (removing it: mean %+.1f%%)"
              % (tag, dm, ds, dg, -pct, -pct))


if __name__ == "__main__":
    main()
