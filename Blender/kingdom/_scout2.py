"""_scout2.py - grid-search good street / plaza camera positions."""
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


def rays(loc, look, nx=9, ny=5, maxd=600.0):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    loc = Vector(loc)
    fwd = (Vector(look) - loc).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    near = 0
    dmin = 1e9
    for iy in range(ny):
        for ix in range(nx):
            u = ((ix + 0.5) / nx * 2 - 1) * 0.55
            v = ((iy + 0.5) / ny * 2 - 1) * 0.32
            d = (fwd + right * u + up * v).normalized()
            ok, hit, nor, idx, ob, mat = sc.ray_cast(dg, loc + d * 0.1, d, distance=maxd)
            if ok:
                dd = (hit - loc).length
                dmin = min(dmin, dd)
                if dd < 3.0:
                    near += 1
    return near / float(nx * ny), (dmin if dmin < 1e8 else maxd)


def main():
    d = json.load(open(LAYOUT, encoding="utf-8"))
    st67 = [s for s in d["streets"] if s["id"] == 67][0]
    print("ST67", st67["name"].encode("utf-8", "replace"), st67["w"],
          st67["segs"][:2], flush=True)
    # the seg that starts at (-360.1,-221.1)
    seg = None
    for s in st67["segs"]:
        if abs(s[0] + 360.1) < 1.0 and abs(s[1] + 221.1) < 1.0:
            seg = s
            break
    if seg is None:
        seg = max(st67["segs"], key=lambda s: math.hypot(s[2] - s[0], s[3] - s[1]))
    print("SEG", seg, flush=True)
    p = Vector((seg[0], seg[1]))
    q = Vector((seg[2], seg[3]))
    fwd = (q - p).normalized()
    az = math.degrees(math.atan2(fwd.x, -fwd.y)) % 360.0
    print("ST67 view azim %.1f  len %.1f" % (az, (q - p).length), flush=True)

    # walk along the street from p and find the best eye position
    best = []
    for t in range(0, 12):
        for dz in (1.7,):
            base = p + fwd * (t * 6.0)
            nf, dmin = rays((base.x, base.y, dz),
                            (base.x + fwd.x * 100, base.y + fwd.y * 100, dz + 6.0))
            if nf < 0.10 and dmin > 12:
                best.append((dmin, nf, t, base.x, base.y))
    best.sort(key=lambda b: -b[0])
    for dmin, nf, t, x, y in best[:6]:
        print("ST67POS t=%-2d (%8.1f,%8.1f) near=%.2f dmin=%.1f" % (t, x, y, nf, dmin),
              flush=True)

    # market square: ring around the plaza centre
    cx, cy = 9.197, 68.394
    mbest = []
    for r in (18, 24, 30, 36, 44, 54):
        for a in range(0, 360, 20):
            px = cx + r * math.cos(math.radians(a))
            py = cy + r * math.sin(math.radians(a))
            for hz in (7.0, 10.0, 14.0):
                nf, dmin = rays((px, py, hz), (cx, cy + 26, 5.0))
                if nf < 0.10 and dmin > 18:
                    mbest.append((dmin, nf, r, a, px, py, hz))
    mbest.sort(key=lambda b: -b[0])
    for dmin, nf, r, a, px, py, hz in mbest[:10]:
        vaz = math.degrees(math.atan2(cx - px, -(cy + 26 - py))) % 360.0
        print("MKT r=%-3d a=%-3d h=%-4.1f (%7.1f,%7.1f) near=%.2f dmin=%5.1f vaz=%.0f"
              % (r, a, hz, px, py, nf, dmin, vaz), flush=True)


main()
