"""_surf_probe_cells.py -- read _surf_brick_probe.png and characterise Brick.Color.

The probe renders a wall segment of Blender's Brick texture with Color1=black /
Color2=white / Mortar=0.5 at the exact medkit stone scale, through an emission
shader and the Standard view transform, so the PNG is a direct readout of the
node's Color output (sRGB encoded).

Bricks are found by segmenting out the mortar (exactly linear 0.5 -> sRGB 188),
so no grid reconstruction is needed.  Reported:

  * per-brick value distribution in LINEAR space (this is what a MULTIPLY sees)
  * intra-brick std (is a brick flat? -> can it drive a per-block tone?)
  * autocorrelation of the brick values at brick-grid shifts (short hash period?)

USAGE
    python _surf_probe_cells.py
"""

import os
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "..", "renders", "kingdom", "_surf_brick_probe.png")


def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def main():
    im = Image.open(PNG).convert("L")
    s = np.asarray(im, dtype=np.float64) / 255.0
    a = srgb_to_lin(s)
    h, w = a.shape

    mortar = np.abs(a - 0.5) < 0.02
    free = ~mortar
    print("mortar fraction %.2f%%" % (100.0 * mortar.mean()))

    # connected components (4-neighbour BFS; 262k px is fine in pure python)
    lab = np.zeros((h, w), dtype=np.int32)
    comps = []
    cur = 0
    for y in range(h):
        for x in range(w):
            if free[y, x] and lab[y, x] == 0:
                cur += 1
                q = deque([(y, x)])
                lab[y, x] = cur
                px = []
                while q:
                    cy, cx = q.popleft()
                    px.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and free[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            q.append((ny, nx))
                comps.append(px)

    vals, areas, stds = [], [], []
    for px in comps:
        if len(px) < 60:
            continue
        ys = np.array([p[0] for p in px])
        xs = np.array([p[1] for p in px])
        v = a[ys, xs]
        vals.append(v.mean())
        stds.append(v.std())
        areas.append(len(px))
    vals = np.array(vals)
    print("bricks: %d   area px  mean %.0f  min %d" %
          (len(vals), np.mean(areas), min(areas)))
    print("value linear  min %.3f  p10 %.3f  mean %.3f  p90 %.3f  max %.3f  std %.3f"
          % (vals.min(), np.percentile(vals, 10), vals.mean(),
             np.percentile(vals, 90), vals.max(), vals.std()))
    print("intra-brick std  mean %.4f  p95 %.4f  (0 = perfectly flat)"
          % (np.mean(stds), np.percentile(stds, 95)))
    hist, _ = np.histogram(vals, bins=10, range=(0, 1))
    print("decile histogram:", list(hist))

    # autocorrelation of the value map at brick-grid shifts.  Brick width and
    # row height are both 0.625 m on this probe (1.5/2.4 and 0.75/2.4), and the
    # 8 m ortho window is 512 px -> 0.015625 m/px -> one brick = 40 px.
    mpp = 8.0 / w
    bw_px = 0.625 / mpp
    rh_px = 0.3125 / mpp
    print("pixels per brick %.1f, per row %.1f" % (bw_px, rh_px))
    mask = free & (a < 0.98) & (a > 0.02)
    for kx in (1, 2, 3):
        for ky in (0, 1, 2, 4):
            dx = int(round(kx * bw_px))
            dy = int(round(ky * rh_px))
            a1 = a[dy:, dx:]
            a2 = a[:h - dy, :w - dx]
            m = mask[dy:, dx:] & mask[:h - dy, :w - dx]
            if m.sum() < 5000:
                continue
            x1 = a1[m]
            x2 = a2[m]
            c = np.corrcoef(x1, x2)[0, 1]
            print("  shift (bricks %d, rows %d) = (%3d,%3d) px  r %+.3f"
                  % (kx, ky, dx, dy, c))


main()
