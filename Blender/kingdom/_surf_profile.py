"""_surf_profile.py -- vertical / horizontal profiles of RGB, luma and green.

Answers questions a single frame mean cannot: *where* did the surface change,
and is the change actually green rather than just darker?

USAGE
  python _surf_profile.py A.png [B.png] --x 40,760 --rows 10 [--band 300,360]

Prints one line per horizontal band: mean R,G,B, Rec.709 luma and the fraction
of pixels whose greenness G - max(R,B) exceeds 8.  With a second image it also
prints the per-band delta of luma and of the green fraction, which is how the
moss / splash bands are verified without squinting at the picture.
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def luma(rgb):
    return (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1]
            + 0.0722 * rgb[:, :, 2])


def green(rgb):
    return rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])


def band_stats(rgb, y0, y1, x0, x1):
    b = rgb[y0:y1, x0:x1]
    g = green(b)
    return (b[:, :, 0].mean(), b[:, :, 1].mean(), b[:, :, 2].mean(),
            luma(b).mean(), 100.0 * float((g > 8).mean()), g.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after", nargs="?")
    ap.add_argument("--x", default="", help="x0,x1 in pixels (default: 10%%..90%%)")
    ap.add_argument("--rows", type=int, default=10, help="band height in px")
    ap.add_argument("--band", default="", help="y0,y1 restrict to that range")
    a = ap.parse_args()

    ib = load(a.before)
    ia = load(a.after) if a.after else None
    h, w = ib.shape[:2]
    if a.x:
        x0, x1 = (int(v) for v in a.x.split(","))
    else:
        x0, x1 = int(w * 0.10), int(w * 0.90)
    if a.band:
        y0, y1 = (int(v) for v in a.band.split(","))
    else:
        y0, y1 = 0, h

    print("%% %s  x=%d..%d  bands of %d px" % (os.path.basename(a.before), x0, x1, a.rows))
    hdr = "   y0 %4s %4s %4s %6s %6s" % ("R", "G", "B", "luma", "grn%")
    if ia is not None:
        hdr += "  |  %6s %6s" % ("dLuma", "dGrn%")
    print(hdr)
    for yy in range(y0, y1, a.rows):
        sb = band_stats(ib, yy, min(yy + a.rows, y1), x0, x1)
        line = "  %4d %4.0f %4.0f %4.0f %6.2f %6.2f" % (yy, sb[0], sb[1], sb[2],
                                                      sb[3], sb[4])
        if ia is not None:
            sa = band_stats(ia, yy, min(yy + a.rows, y1), x0, x1)
            line += "  |  %+6.2f %+6.2f" % (sa[3] - sb[3], sa[4] - sb[4])
        print(line)


if __name__ == "__main__":
    main()
