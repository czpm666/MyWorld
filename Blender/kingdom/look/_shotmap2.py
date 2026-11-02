"""Second scene map pass: the things the first pass could not resolve.

`outer_gates` is ONE merged object holding all four gatehouses, so a prefix map
gives its bbox and nothing else.  The four avenues (`road_in0..3`) are separate
objects, so their individual bboxes hand back the four radial directions, which
is exactly what the gate landmark cameras need.  This script

  * prints the four radial avenue directions from `road_in*` / `road_out*`,
  * clusters the vertices of `outer_gates` into four gatehouses and prints the
    centre + size of each,
  * prints the same for `outer_wall` clusters (wall radius per direction),
  * prints the bbox of the `plaza*` slab objects as one union,
  * prints the height histogram of `city_blk*` (how tall the town actually is,
    which sets the eye-level and 52 deg sight lines).

    python look\\_shotrun.py --tag map2 --blend --script look\\_shotmap2.py
"""
import json
import math
import os
import sys

import bpy
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shotmap2.json")


def wbbox(ob):
    """World-space bbox of an object as (lo, hi) numpy arrays."""
    m = np.array(ob.matrix_world, dtype=np.float64)
    cs = np.array([list(c) for c in ob.bound_box], dtype=np.float64)
    cs = cs @ m[:3, :3].T + m[:3, 3]
    return cs.min(axis=0), cs.max(axis=0)


def wverts(ob):
    me = ob.data
    n = len(me.vertices)
    a = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", a)
    a = a.reshape(n, 3)
    m = np.array(ob.matrix_world, dtype=np.float64)
    return a @ m[:3, :3].T + m[:3, 3]


def cluster4(P):
    """Split points into four angular clusters; returns list of dicts."""
    ang = np.degrees(np.arctan2(P[:, 1], P[:, 0])) % 360.0
    hist, edges = np.histogram(ang, bins=360, range=(0, 360))
    # smooth so a gate spanning 20 deg reads as one peak
    k = np.array([1, 2, 3, 2, 1], dtype=np.float64)
    k /= k.sum()
    sm = np.convolve(np.r_[hist[-2:], hist, hist[:2]], k, mode="same")[2:-2]
    order = np.argsort(-sm)
    peaks = []
    for b in order:
        if sm[b] <= 0:
            continue
        if all(min(abs(b - p), 360 - abs(b - p)) > 30 for p in peaks):
            peaks.append(int(b))
        if len(peaks) == 4:
            break
    out = []
    for p in sorted(peaks):
        d = np.abs(((ang - (p + 0.5)) + 180.0) % 360.0 - 180.0)
        Q = P[d < 18.0]
        if len(Q) < 8:
            continue
        lo, hi = Q.min(axis=0), Q.max(axis=0)
        out.append(dict(
            n=int(len(Q)),
            deg=round(float(np.degrees(np.arctan2(Q[:, 1].mean(), Q[:, 0].mean())) % 360.0), 2),
            centre=[round(float(v), 2) for v in Q.mean(axis=0)],
            lo=[round(float(v), 2) for v in lo],
            hi=[round(float(v), 2) for v in hi],
            size=[round(float(v), 2) for v in (hi - lo)],
        ))
    return out


def main():
    scn = bpy.context.scene
    res = {"roads": {}, "gates": {}, "walls": {}, "plaza": None, "tall": []}

    obs = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

    # --- the four radial avenues -------------------------------------------
    for pref in ("road_in", "road_out"):
        rows = []
        for name in sorted(obs):
            if not name.startswith(pref):
                continue
            lo, hi = wbbox(obs[name])
            c = (lo + hi) * 0.5
            r = float(math.hypot(c[0], c[1]))
            rows.append(dict(name=name, centre=[round(float(v), 2) for v in c],
                             size=[round(float(v), 2) for v in (hi - lo)],
                             r=round(r, 2),
                             deg=round(float(math.degrees(math.atan2(c[1], c[0])) % 360.0), 2),
                             u=[round(float(c[0] / r), 5), round(float(c[1] / r), 5)] if r else None))
        res["roads"][pref] = rows

    # --- gatehouses + curtain ----------------------------------------------
    for name, key in (("outer_gates", "gates"), ("outer_wall", "walls")):
        ob = obs.get(name)
        if ob is None:
            print("[map2] missing", name)
            continue
        P = wverts(ob)
        res[key][name] = dict(verts=int(len(P)), clusters=cluster4(P))
        print("[map2] %-12s %d verts -> %d clusters" % (name, len(P), len(res[key][name]["clusters"])))

    # --- plaza slab union ---------------------------------------------------
    lo = np.array([1e9, 1e9, 1e9])
    hi = -lo
    n = 0
    for name, ob in obs.items():
        if not name.startswith("plaza"):
            continue
        a, b = wbbox(ob)
        lo, hi = np.minimum(lo, a), np.maximum(hi, b)
        n += 1
    if n:
        res["plaza"] = dict(n=n, lo=[round(float(v), 2) for v in lo],
                            hi=[round(float(v), 2) for v in hi])

    # --- how tall is the town? ---------------------------------------------
    zs = []
    for name, ob in obs.items():
        if not name.startswith("city_blk"):
            continue
        a, b = wbbox(ob)
        zs.append((round(float(b[2]), 2), name, [round(float(v), 1) for v in (a + b) * 0.5]))
    zs.sort(reverse=True)
    res["tall"] = zs[:12]
    if zs:
        arr = np.array([z[0] for z in zs])
        res["tall_stats"] = dict(n=int(len(arr)), p50=float(np.percentile(arr, 50)),
                                 p90=float(np.percentile(arr, 90)),
                                 p99=float(np.percentile(arr, 99)), max=float(arr.max()))

    # --- what stands on the two rings? -------------------------------------
    # `hd_gates()` puts four gatehouses at r = R_WALL = 444, but the merged
    # `outer_wall` object turns out to sit at r ~ 947, so it is not obvious
    # whether a curtain exists at 444 at all.  Group every object whose bbox
    # centre falls in a ring band by name prefix and print the counts.
    ring = {}
    for name, ob in obs.items():
        a, b = wbbox(ob)
        c = (a + b) * 0.5
        r = float(math.hypot(c[0], c[1]))
        for lo_r, hi_r, key in ((360.0, 520.0, "inner"), (880.0, 1010.0, "outer")):
            if not (lo_r <= r <= hi_r):
                continue
            pref = name.rstrip("0123456789").rstrip("_")
            e = ring.setdefault(key, {}).setdefault(pref, dict(n=0, z=0.0, size=0.0))
            e["n"] += 1
            e["z"] = max(e["z"], round(float(b[2]), 1))
            e["size"] = max(e["size"], round(float(max(b[0] - a[0], b[1] - a[1])), 1))
    res["ring"] = ring

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)

    for pref, rows in res["roads"].items():
        for r in rows:
            print("[map2] %-10s centre %-22s size %-20s r=%7.1f deg=%6.1f u=%s"
                  % (r["name"], r["centre"], r["size"], r["r"], r["deg"], r["u"]))
    for key in ("gates", "walls"):
        for name, v in res[key].items():
            for c in v["clusters"]:
                print("[map2] %-11s deg %6.1f centre %-22s size %-20s n=%d"
                      % (name, c["deg"], c["centre"], c["size"], c["n"]))
    if res["plaza"]:
        print("[map2] plaza slab %s" % res["plaza"])
    for key, fams in res.get("ring", {}).items():
        for pref, e in sorted(fams.items(), key=lambda kv: -kv[1]["n"])[:24]:
            print("[map2] ring %-5s %-22s n=%4d top_z=%6.1f max_size=%6.1f"
                  % (key, pref, e["n"], e["z"], e["size"]))
    if "tall_stats" in res:
        print("[map2] city_blk top z: %s" % res["tall_stats"])
    print("[map2] wrote %s" % OUT)


main()
