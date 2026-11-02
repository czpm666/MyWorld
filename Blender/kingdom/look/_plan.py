"""Schematic check for the capital plan at an arbitrary radius.

    python look/_plan.py 947 [cov_max]

Prints the packing numbers and writes look/_plan_<R>.png (whole city) plus
look/_plan_<R>_zoom.png (a 500 m window around a busy block).  Pure python --
no bpy -- so it costs a few seconds and can be iterated freely.
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
sys.path.insert(0, KIND)

import hd_layout as L          # noqa: E402
import hd_dense as DN          # noqa: E402
import hd_plan2 as P2          # noqa: E402


def area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i][0], pts[i][1]
        x2, y2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def main(argv):
    R = float(argv[1]) if len(argv) > 1 else 947.0
    cov = float(argv[2]) if len(argv) > 2 else 0.36
    plan = argv[3] if len(argv) > 3 else "2"
    if plan == "2":
        k = R / 636.0
        reserved = [(0.0, 205.0 * k, 96.0), (-152.0 * k, 58.0 * k, 74.0),
                    (142.0 * k, 66.0 * k, 48.0), (0.0, -30.0 * k, 52.0)]
        res = P2.build(radius=R, seed=7, reserved=reserved)
    else:
        res = L.layout_city(dict(radius=R))
    pl = DN.placements(res, foot_override=DN.FALLBACK_FOOT, seed=7, cov_max=cov)

    blocks = res["blocks"]
    streets = res["streets"]
    ba = sum(area(b["poly"]) for b in blocks if len(b["poly"]) >= 3 and not b.get("open"))
    pa = sum(q["w"] * q["d"] for q in pl if q["source"] == "house")
    nh = sum(1 for q in pl if q["source"] == "house")
    ns = len(pl) - nh
    print("radius %.0f  cov_max %.2f" % (R, cov))
    print("  blocks %d   streets %d   units %d (houses %d / shops %d)"
          % (len(blocks), len(streets), len(pl), nh, ns))
    print("  block area %.0f m2   house area %.0f m2   coverage %.1f %%"
          % (ba, pa, 100.0 * pa / max(ba, 1.0)))
    bs = sorted(area(b["poly"]) for b in blocks if len(b["poly"]) >= 3 and not b.get("open"))
    if bs:
        print("  block area p10 %.0f  median %.0f  p90 %.0f"
              % (bs[len(bs) // 10], bs[len(bs) // 2], bs[9 * len(bs) // 10]))
    widths = sorted(s["w"] for s in streets)
    print("  street width median %.1f m, total length %.0f m"
          % (widths[len(widths) // 2], sum(s.get("length", 0.0) for s in streets)))
    rmax = max(max(abs(p[0]), abs(p[1])) for b in blocks for p in b["poly"])
    print("  plan extent +-%.0f m" % rmax)
    print("  rows %d  edge_len %.0f m  placed %d  collide %d  skip %d  short %d  guard %d"
          % (DN._STATS["rows"], DN._STATS["edge_len"], DN._STATS["placed"],
             DN._STATS["collide"], DN._STATS["skip"], DN._STATS["short"],
             DN._STATS["guard"]))

    try:
        from PIL import Image, ImageDraw
    except Exception:
        print("(no PIL)")
        return

    def draw(px, centre, half, path, label):
        img = Image.new("RGB", (px, px), (14, 15, 18))
        dr = ImageDraw.Draw(img)
        sc = px * 0.5 / half

        def T(x, y):
            return (px * 0.5 + (x - centre[0]) * sc, px * 0.5 - (y - centre[1]) * sc)

        for b in blocks:
            if len(b["poly"]) >= 3:
                dr.polygon([T(*p) for p in b["poly"]], fill=(33, 36, 44))
        # streets, drawn by width so the network reads at a glance
        for s in streets:
            w = s["w"]
            px_w = max(1, int(round(w * sc)))
            col = (104, 108, 118) if s["kind"] == "main" else (
                (86, 90, 100) if s["kind"] == "secondary" else (68, 71, 79))
            for seg in (s.get("segs") or []):
                dr.line([T(seg[0], seg[1]), T(seg[2], seg[3])], fill=col, width=px_w)
        for q in pl:
            col = (232, 140, 92) if q["source"] == "shop" else (206, 202, 190)
            dr.polygon([T(*p) for p in q["quad"]], fill=col)
        # walls
        for rr, c in ((L.R_BUILD, (150, 90, 70)), (R * 0.98, (120, 70, 56))):
            dr.ellipse([T(-rr, rr), T(rr, -rr)], outline=c, width=2)
        dr.text((10, 10), label, fill=(220, 220, 220))
        img.save(path)
        print("  ->", path)

    out1 = os.path.join(HERE, "_plan_%d.png" % R)
    draw(1600, (0.0, 0.0), rmax * 1.03, out1,
         "r=%.0f  units %d  cov %.0f%%" % (R, len(pl), 100.0 * pa / max(ba, 1.0)))
    # zoom on the block with the most units
    cnt = {}
    for q in pl:
        cnt[q["block"]] = cnt.get(q["block"], 0) + 1
    if cnt:
        bid = max(cnt, key=lambda k: cnt[k])
        b = next(b for b in blocks if b["id"] == bid)
        cx = sum(p[0] for p in b["poly"]) / len(b["poly"])
        cy = sum(p[1] for p in b["poly"]) / len(b["poly"])
        draw(1200, (cx, cy), 260.0, os.path.join(HERE, "_plan_%d_zoom.png" % R),
             "block %d  %d units" % (bid, cnt[bid]))


if __name__ == "__main__":
    main(sys.argv)
