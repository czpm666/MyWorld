"""_surf_frozen.py -- prove that the frozen materials really did not move.

The acceptance test says roofs, glass and ground must change by less than 1 %,
but a rectangular region cannot prove that: a box drawn on a roof almost always
contains a bit of stone, and then the number says more about the box than about
the material.

This script builds the masks out of the BEFORE image itself -- blue tiles are
the pixels where B clearly beats R, red tiles where R clearly beats B, and so
on -- and reports the mean of exactly those pixels in both frames.  Same pixels,
same geometry, same light: only the material can have changed.

USAGE
    python _surf_frozen.py BEFORE.png AFTER.png
"""

import sys

import numpy as np

import _surf_stats as ST


def masks(rgb):
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lm = ST.luma(rgb)
    out = {}
    # slate / glazed blue roof tiles: clearly blue, clearly not sky (dark)
    out["roof_blue"] = (b - r > 14) & (b > 34) & (lm < 120) & (lm > 12)
    # terracotta: red dominates and it is not a banner
    out["roof_red"] = (r - b > 30) & (r > 55) & (lm < 150)
    # glass: the dark blue window panes inside stone reveals
    out["glass"] = (b - r > 6) & (lm < 40)
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    a = ST.load(sys.argv[1])
    b = ST.load(sys.argv[2])
    if a.shape != b.shape:
        print("size mismatch %s vs %s" % (a.shape, b.shape))
        return 1
    la, lb = ST.luma(a), ST.luma(b)
    print("=" * 72)
    print("frozen-surface check   %s -> %s" % (sys.argv[1], sys.argv[2]))
    print("  %-12s %8s %10s %10s %9s" % ("mask", "pixels", "before", "after", "d%"))
    for name, m in masks(a).items():
        n = int(m.sum())
        if n < 200:
            print("  %-12s %8d  (too few pixels to judge)" % (name, n))
            continue
        ma, mb = float(la[m].mean()), float(lb[m].mean())
        print("  %-12s %8d %10.2f %10.2f %+8.2f%%"
              % (name, n, ma, mb, 100.0 * (mb / ma - 1.0)))
    # everything that is NOT one of those: the masonry, as a reference
    anym = np.zeros(la.shape, dtype=bool)
    for m in masks(a).values():
        anym |= m
    rest = ~anym
    if rest.sum() > 500:
        ma, mb = float(la[rest].mean()), float(lb[rest].mean())
        print("  %-12s %8d %10.2f %10.2f %+8.2f%%"
              % ("stone+sky", int(rest.sum()), ma, mb, 100.0 * (mb / ma - 1.0)))
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
