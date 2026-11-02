"""How many closes the near belt gets, and what that costs.

Runs the pure-numpy half of the landscape (heightfield + the close mosaic)
without Blender, so a change of cell size or of the crop mix can be measured in
seconds instead of waiting for the render queue.

    python look/_land_carpet_probe.py [cell]
"""

import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import _land_stub

_land_stub.install()

import numpy as np

import hd_landscape as LS
import hd_landscape_near as NR


class FakeAcc(object):
    """Swallows the geometry so the probe only measures the layout pass."""

    def __init__(self):
        self.n = 0
        self.v = 0

    def quad(self, *a, **k):
        self.n += 1
        self.v += 4

    def tri(self, *a, **k):
        self.n += 1
        self.v += 3

    def poly(self, *a, **k):
        self.n += 1
        self.v += 4

    def add(self, LSm, V, F, *a, **k):
        self.n += len(F)
        self.v += len(V)

    def push(self, *a, **k):
        return None


def main():
    cell = float(sys.argv[1]) if len(sys.argv) > 1 else NR.CARPET
    NR.CARPET = cell
    res = 20.0
    t0 = time.time()
    n = int(round(2.0 * LS.HALF / res)) + 1
    xs = np.linspace(-LS.HALF, LS.HALF, n)
    X, Y = np.meshgrid(xs, xs)
    LS._Z = LS.heights(X, Y)
    LS._ZRES = res
    print("[probe] heightfield %dx%d in %.2fs" % (n, n, time.time() - t0))

    rng = random.Random(1337)
    rp = NR._road_pts(LS)
    NR._field_mask([], res=10.0, half=1700.0)

    # _carpet pushes through FLD.Bucket, which needs Blender to build a mesh;
    # swap in the fake so the same layout code runs unchanged.
    real = NR.FLD.Bucket
    NR.FLD.Bucket = FakeAcc
    try:
        t1 = time.time()
        ob, ncell = NR._carpet(LS, rng, rp, (0.0, 430.0), None)
        dt = time.time() - t1
    finally:
        NR.FLD.Bucket = real
    print("[probe] carpet cell %.1f m -> %d closes in %.2fs (%.0f us/close)"
          % (cell, ncell, dt, 1e6 * dt / max(1, ncell)))
    print("[probe] tris %d  verts %d  -> %.0f k tris"
          % (ncell * 2, ncell * 4, ncell * 2 / 1000.0))
    area = np.pi * ((LS.R_OUTER + 430.0) ** 2 - (LS.R_OUTER - 6.0) ** 2)
    print("[probe] belt area %.2f km2, coverage %.0f%%"
          % (area / 1e6, 100.0 * ncell * cell * cell / area))


if __name__ == "__main__":
    main()
