"""Report the world bbox of named parts and their nearest neighbours."""
import math
import random
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_common as H                                          # noqa: E402
import hd_gate as G                                            # noqa: E402

H._clear()
MAT = G.materials()
OBS = [o for o in G.build(MAT, random.Random(20261030))
       if o is not None and o.type == "MESH"]
BY = {o.name: o for o in OBS}
dg = bpy.context.evaluated_depsgraph_get()


def bb(o):
    m = o.matrix_world
    pts = [m @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


for want in sys.argv[sys.argv.index("--") + 1:]:
    o = BY.get(want)
    if o is None:
        print("[probe] %s MISSING" % want, flush=True)
        continue
    lo, hi = bb(o)
    print("[probe] %-14s x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f  mat=%s"
          % (want, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z,
             o.data.materials[0].name if o.data.materials else "-"), flush=True)
    # nearest five objects by bbox distance
    ds = []
    for q in OBS:
        if q is o:
            continue
        ql, qh = bb(q)
        d = math.sqrt(max(ql.x - hi.x, lo.x - qh.x, 0) ** 2
                      + max(ql.y - hi.y, lo.y - qh.y, 0) ** 2
                      + max(ql.z - hi.z, lo.z - qh.z, 0) ** 2)
        ds.append((d, q.name))
    ds.sort()
    for d, n in ds[:5]:
        print("[probe]    %.3f  %s" % (d, n), flush=True)
