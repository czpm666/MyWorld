"""_streetfind.py - find street segments with a long, clear, straight view."""
import os
import sys
import json
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
from mathutils import Vector

LAYOUT = os.path.join(HERE, "layout.json")
OUT = r"E:\My World\Blender\renders\kingdom"


def clear_len(origin, d, maxd=220.0):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    ok, loc, nor, idx, ob, mat = sc.ray_cast(dg, Vector(origin) + d * 0.5, d, distance=maxd)
    if not ok:
        return maxd, None
    return (loc - Vector(origin)).length, ob.name if ob else None


def main():
    d = json.load(open(LAYOUT, encoding="utf-8"))
    cands = []
    for st in d["streets"]:
        if st["w"] < 9.0 or st["length"] < 90.0:
            continue
        for seg in st["segs"]:
            x1, y1, x2, y2 = seg
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 60.0:
                continue
            cands.append((st["id"], st["name"], st["w"], st["kind"],
                          (x1, y1), (x2, y2), L))
    cands.sort(key=lambda c: -c[6])
    print("STREET %d candidate segs" % len(cands), flush=True)
    seen = set()
    best = []
    for sid, name, w, kind, a, b, L in cands[:160]:
        if sid in seen:
            continue
        seen.add(sid)
        # midpoint, both directions
        mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        for tag, (p, q) in (("ab", (a, b)), ("ba", (b, a))):
            dirv = Vector((q[0] - p[0], q[1] - p[1], 0.0)).normalized()
            dist, ob = clear_len((p[0], p[1], 1.7), dirv)
            if dist > 70.0:
                best.append((dist, sid, name, w, kind, (p[0], p[1]), tag))
    best.sort(key=lambda c: -c[0])
    for dist, sid, name, w, kind, p, tag in best[:26]:
        print("STREET clear=%6.1f id=%-4d w=%4.1f %-6s from=(%8.1f,%8.1f) %s"
              % (dist, sid, w, kind, p[0], p[1], tag), flush=True)


main()
