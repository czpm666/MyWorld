"""Trace one edge's placement walk: every attempt, its slot, and why it died."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hd_layout as L

lay = L.generate(radius=636.0, seed=20261022)
bl = sorted([b for b in lay["blocks"] if not b["open"]],
            key=lambda b: -b.get("buildings", 0))
b = bl[0]
poly = b["poly"]
n = len(poly)
print("block", b["id"], "area %.0f" % b["area"], "bld", b.get("buildings"),
      "verts", n)
print("poly", [(round(p[0], 1), round(p[1], 1)) for p in poly])

for i in range(n):
    fr = L._edge_frame(poly[i], poly[(i + 1) % n])
    (tx, ty), (nx, ny), Le = fr
    band = L.edge_band(poly, i, 2.8 + 14.5)
    ss = [(p[0] - poly[i][0]) * tx + (p[1] - poly[i][1]) * ty for p in band]
    print("edge %d L=%.1f band=%d band_s=[%.1f, %.1f]"
          % (i, Le, len(band), min(ss) if ss else 0, max(ss) if ss else 0))
    t = 0.0
    ok = 0
    tried = 0
    shown = 0
    while t < Le - 0.8 and tried < 400:
        tried += 1
        bw, bd = 8.45, 10.6        # timber house, unscaled
        pw = bw + 0.4
        if t + pw > Le - 0.6:
            break
        tc = t + pw * 0.5
        curb = (poly[i][0] + tx * tc, poly[i][1] + ty * tc)
        bpos = (curb[0] - nx * (2.8 + 0.5 + bd * 0.5),
                curb[1] - ny * (2.8 + 0.5 + bd * 0.5))
        pts = L.rect_pts(bpos[0], bpos[1], bw, bd, math.atan2(ny, nx))
        res = [L.point_in_convex(band, p, -0.02) for p in pts]
        if all(res):
            ok += 1
            t += pw
        else:
            if shown < 4:
                shown += 1
                print("      fail t=%.1f tc=%.1f res=%s pts=%s"
                      % (t, tc, res,
                         [(round(p[0], 1), round(p[1], 1)) for p in pts]))
            t += 0.8
    print("   -> fits %d of %d attempts at t up to %.1f" % (ok, tried, t))
