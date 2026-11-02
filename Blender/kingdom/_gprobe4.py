"""Which part is nearest to a named part, and how far?"""
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


def wverts(o):
    me = o.evaluated_get(dg).to_mesh()
    m = o.matrix_world
    vs = [m @ v.co for v in me.vertices]
    fs = [list(p.vertices) for p in me.polygons]
    o.evaluated_get(dg).to_mesh_clear()
    return vs, fs


CACHE = {}


def tree_of(o):
    if o.name not in CACHE:
        vs, fs = wverts(o)
        CACHE[o.name] = BVHTree.FromPolygons(vs, fs, all_triangles=False) if fs else None
    return CACHE[o.name]


def bb(o):
    m = o.matrix_world
    pts = [m @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


BOX = {o.name: bb(o) for o in OBS}

for want in sys.argv[sys.argv.index("--") + 1:]:
    o = BY.get(want)
    if o is None:
        print("[probe] %s MISSING" % want, flush=True)
        continue
    lo, hi = BOX[want]
    print("[probe] %-14s x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f"
          % (want, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z), flush=True)
    vs, fs = wverts(o)
    probe = vs[:: max(1, len(vs) // 120)]
    probe += [o.matrix_world @ Vector((0.0, 0.0, 0.0))]
    res = []
    for q in OBS:
        if q is o:
            continue
        ql, qh = BOX[q.name]
        if (ql.x > hi.x + 0.8 or qh.x < lo.x - 0.8 or ql.y > hi.y + 0.8
                or qh.y < lo.y - 0.8 or ql.z > hi.z + 0.8 or qh.z < lo.z - 0.8):
            continue
        t = tree_of(q)
        if t is None:
            continue
        d = min(t.find_nearest(p)[3] for p in probe)
        res.append((d, q.name))
    res.sort()
    for d, n in res[:6]:
        print("[probe]    %.3f  %s" % (d, n), flush=True)
