"""Validate a placement list against the street network.

    python look/_check_plan.py 947 [cov_max]

Checks, for every unit:
  * its centre is at least (street half width + 0.3 m) from every street centre
    line - i.e. no house stands in the carriageway;
  * it does not overlap another unit;
  * it lies inside its own block polygon (allowing the terrace to overhang the
    kerb by up to SETBACK).

Prints the worst offenders and writes look/_plan_check.png with the failures
marked in red.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
sys.path.insert(0, KIND)

import hd_dense as DN       # noqa: E402
import hd_plan2 as P2       # noqa: E402


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


class Segs(object):
    def __init__(self, streets, cell=32.0):
        self.cell = cell
        self.g = {}
        for s in streets:
            hw = s["w"] * 0.5
            for sg in s["segs"]:
                x1, y1, x2, y2 = sg
                n = max(1, int(math.hypot(x2 - x1, y2 - y1) / cell))
                for i in range(n + 1):
                    t = i / float(n)
                    x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    self.g.setdefault((int(x // cell), int(y // cell)), []).append(
                        (x1, y1, x2, y2, hw))

    def worst(self, px, py, reach=2):
        best = 1e9
        cx, cy = int(px // self.cell), int(py // self.cell)
        for ix in range(cx - reach, cx + reach + 1):
            for iy in range(cy - reach, cy + reach + 1):
                for (x1, y1, x2, y2, hw) in self.g.get((ix, iy), ()):
                    d = seg_dist(px, py, x1, y1, x2, y2) - hw
                    if d < best:
                        best = d
        return best


def main(argv):
    R = float(argv[1]) if len(argv) > 1 else 947.0
    cov = float(argv[2]) if len(argv) > 2 else 0.36
    k = R / 636.0
    reserved = [(0.0, 205.0 * k, 96.0), (-152.0 * k, 58.0 * k, 74.0),
                (142.0 * k, 66.0 * k, 48.0), (0.0, -30.0 * k, 52.0)]
    res = P2.build(radius=R, seed=7, reserved=reserved)
    pl = DN.placements(res, foot_override=DN.FALLBACK_FOOT, seed=7, cov_max=cov)
    S = Segs(res["streets"])
    print("units %d" % len(pl))

    inroad = []
    for q in pl:
        gap = S.worst(q["x"], q["y"])
        if gap < 0.30:
            inroad.append((gap, q))
    inroad.sort(key=lambda t: t[0])
    print("in the carriageway (<0.30 m clear): %d  (%.2f %%)"
          % (len(inroad), 100.0 * len(inroad) / max(len(pl), 1)))
    for gap, q in inroad[:8]:
        print("   gap %+.2f m  at (%.0f, %.0f)  w=%.1f d=%.1f  %s"
              % (gap, q["x"], q["y"], q.get("w", 0.0), q.get("d", 0.0), q["kind"]))

    # overlaps between units of different blocks
    grid = {}
    cell = 24.0
    bad = 0
    for i, q in enumerate(pl):
        grid.setdefault((int(q["x"] // cell), int(q["y"] // cell)), []).append(i)
    for i, q in enumerate(pl):
        cx, cy = int(q["x"] // cell), int(q["y"] // cell)
        for ix in (cx - 1, cx, cx + 1):
            for iy in (cy - 1, cy, cy + 1):
                for j in grid.get((ix, iy), ()):
                    if j <= i:
                        continue
                    r = pl[j]
                    if r["block"] == q["block"]:
                        continue
                    if not DN._sep(q["quad"], r["quad"], 0.05):
                        bad += 1
    print("cross-block overlaps: %d" % bad)

    gaps = sorted(S.worst(q["x"], q["y"]) for q in pl)
    print("clearance p1 %+.2f  p10 %+.2f  median %+.2f  p90 %+.2f"
          % (gaps[len(gaps) // 100], gaps[len(gaps) // 10],
             gaps[len(gaps) // 2], gaps[9 * len(gaps) // 10]))

    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    px = 1400
    half = 300.0
    sc = px * 0.5 / half
    cx0, cy0 = pl[0]["x"], pl[0]["y"]
    img = Image.new("RGB", (px, px), (14, 15, 18))
    dr = ImageDraw.Draw(img)

    def T(x, y):
        return (px * 0.5 + (x - cx0) * sc, px * 0.5 - (y - cy0) * sc)

    for s in res["streets"]:
        for sg in s["segs"]:
            dr.line([T(sg[0], sg[1]), T(sg[2], sg[3])], fill=(70, 74, 82),
                    width=max(1, int(s["w"] * sc)))
    badset = set(id(q) for _g, q in inroad)
    for q in pl:
        col = (226, 60, 60) if id(q) in badset else (
            (232, 140, 92) if q["source"] == "shop" else (206, 202, 190))
        dr.polygon([T(*p) for p in q["quad"]], fill=col)
    out = os.path.join(HERE, "_plan_check.png")
    img.save(out)
    print("->", out)


if __name__ == "__main__":
    main(sys.argv)
