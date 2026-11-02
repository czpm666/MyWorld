"""Which merged pieces sit outside the curtain polygon?

    blender -b --factory-startup --python _tmp/chk_wallrow.py

The overview still shows red roofs beyond the wall, so classify every top-level
object by how far its geometry reaches past the enceinte.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                   # noqa: E402
import capital as C                                          # noqa: E402

C.HD["on"] = True
bpy.ops.wm.open_mainfile(filepath=os.path.join(C.OUT_PNG, "capital_full.blend"))

pts = C.outer_ring_pts()


def inside(x, y):
    """even-odd test against the curtain polygon"""
    c = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c


rows = []
for ob in bpy.data.objects:
    if ob.type != "MESH" or not ob.name.startswith(("wallrow", "city_blk", "suburb")):
        continue
    out = 0
    tot = 0
    rmax = 0.0
    for v in ob.data.vertices:
        w = ob.matrix_world @ v.co
        tot += 1
        r = math.hypot(w.x, w.y)
        rmax = max(rmax, r)
        if not inside(w.x, w.y):
            out += 1
    rows.append((ob.name, tot, out, rmax))

rows.sort(key=lambda t: -t[2])
print("%-14s %8s %8s %8s" % ("object", "verts", "outside", "rmax"), flush=True)
for name, tot, out, rmax in rows:
    print("%-14s %8d %8d %8.1f" % (name, tot, out, rmax), flush=True)
print("TOTAL outside verts", sum(r[2] for r in rows), flush=True)
print("CHK_DONE", flush=True)
