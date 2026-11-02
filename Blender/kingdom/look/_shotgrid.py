"""Dump the REAL block footprints out of the blend, for look/spots.py.

Why this exists
---------------
spots.py used to rebuild the city in plain python (`hd_plan2.build(seed=7)`) and
score camera spots on that raster.  It does not match the blend:

    build_v24.log : [capital] plan2: 642 blocks / 63 streets
                    [capital] hd_dense: 12215 placements, 463 dropped
    spots.py      : seed 7        -> 326 blocks / 32 streets / 12922 units
                    seed 20261022 -> 331 blocks / 31 streets / 13853 units

so every clearance number spots.py computed described a city that does not
exist, and its first pick sat 2.55 m from a wall.  The blocks in the blend are
merged per block (`city_blk00..`), so their convex hull is the honest footprint
of what is actually standing there.  This script writes those hulls to
look/_shotblocks.json; spots.py rasterises them and never guesses again.

    python look\\_shotrun.py --tag grid --blend --script look\\_shotgrid.py
"""
import json
import os

import bpy
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shotblocks.json")


def hull2d(P, eps=0.05):
    """Convex hull (monotone chain) of 2D points, simplified to `eps` metres."""
    if len(P) < 3:
        return []
    Q = np.unique(np.round(P / eps) * eps, axis=0)
    if len(Q) < 3:
        return Q.tolist()
    idx = np.lexsort((Q[:, 1], Q[:, 0]))
    Q = Q[idx]

    def half(pts):
        out = []
        for p in pts:
            while len(out) >= 2:
                a, b = out[-2], out[-1]
                if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) <= 0.0:
                    out.pop()
                else:
                    break
            out.append(p)
        return out

    lower = half(Q)
    upper = half(Q[::-1])
    h = lower[:-1] + upper[:-1]
    return [[round(float(x), 2), round(float(y), 2)] for (x, y) in h]


def wverts(ob):
    me = ob.data
    n = len(me.vertices)
    a = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", a)
    a = a.reshape(n, 3)
    m = np.array(ob.matrix_world, dtype=np.float64)
    return a @ m[:3, :3].T + m[:3, 3]


def main():
    obs = [o for o in bpy.data.objects if o.type == "MESH"]
    blocks = []
    tot = 0
    for ob in obs:
        if not ob.name.startswith("city_blk"):
            continue
        P = wverts(ob)
        if not len(P):
            continue
        tot += len(P)
        h = hull2d(P[:, :2])
        if len(h) < 3:
            continue
        blocks.append(dict(name=ob.name, hull=h,
                           z=round(float(P[:, 2].max()), 2),
                           z0=round(float(P[:, 2].min()), 2),
                           nv=int(len(P))))
    blocks.sort(key=lambda b: b["name"])
    print("[grid] %d city_blk objects, %d verts, hulls written" % (len(blocks), tot))

    zs = np.array([b["z"] for b in blocks]) if blocks else np.zeros(1)
    stats = dict(n=len(blocks),
                 z_p50=round(float(np.percentile(zs, 50)), 2),
                 z_p90=round(float(np.percentile(zs, 90)), 2),
                 z_p99=round(float(np.percentile(zs, 99)), 2),
                 z_max=round(float(zs.max()), 2))

    # a couple of named landmarks, as polygons, so spots.py can keep cameras out
    # of the market hall / fountain / guild / cathedral without re-deriving them
    res = {"blocks": blocks, "stats": stats}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, separators=(",", ":"))
    print("[grid] block eave z: %s" % stats)
    print("[grid] wrote %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))


main()
