# -*- coding: utf-8 -*-
"""_cint_test.py - build hd_castle_int in an empty scene and audit it.

Reports mesh / evaluated triangle counts, the measured envelope, clear widths
at eye height, and a geometric support audit: every part must either stand on
the floor, be touched from below by another part, or hang from something above
it.  Also dumps the triangle budget per part family so detail can be steered.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_UP = os.path.dirname(_HERE)
if _UP not in sys.path:
    sys.path.insert(0, _UP)

import hd_castle_int as CI  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)

MAT = CI.make_mats()
rng = random.Random(20261030)
objs = CI.build(MAT, rng)
print("OBJECTS %d" % len(objs))


def ntris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


mesh_tris = sum(ntris(o.data) for o in objs)
dg = bpy.context.evaluated_depsgraph_get()
ev_tris = 0
for o in objs:
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    ev_tris += ntris(me)
    oe.to_mesh_clear()
print("TRIS mesh %d  evaluated %d" % (mesh_tris, ev_tris))

# ---------------------------------------------------------------- envelope
LO = [1e9] * 3
HI = [-1e9] * 3
B = []
for o in objs:
    mw = o.matrix_world
    cs = [mw @ Vector(c) for c in o.bound_box]
    lo = Vector((min(c[i] for c in cs) for i in range(3)))
    hi = Vector((max(c[i] for c in cs) for i in range(3)))
    B.append((lo, hi))
    for i in range(3):
        LO[i] = min(LO[i], lo[i])
        HI[i] = max(HI[i], hi[i])
print("ENVELOPE x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f"
      % (LO[0], HI[0], LO[1], HI[1], LO[2], HI[2]))
print("CLEARANCE long %.2f  wide %.2f  high %.2f"
      % (HI[1] - LO[1], HI[0] - LO[0], HI[2] - LO[2]))
print("FOOTPRINT %s  HEIGHT %.2f" % (str(CI.footprint()), CI.height()))

for k, (lo, hi) in enumerate(B):
    if lo[1] < -26.005 or hi[1] > 26.005 or abs(lo[0]) > 15.005 or abs(hi[0]) > 15.005:
        print("   OUTSIDE FOOTPRINT %-22s x %6.2f..%6.2f y %7.2f..%7.2f"
              % (objs[k].name, lo[0], hi[0], lo[1], hi[1]))

# ---------------------------------------------------------------- clear widths
EYE = 1.70
inner = 9.9
blockers = []
for k, (lo, hi) in enumerate(B):
    if (lo[2] <= 1.55 and hi[2] >= 0.25 and abs(lo[0]) < 4.0
            and hi[1] > -17.0 and lo[1] < 16.0):
        edge = None
        if lo[0] > 0.02:
            edge = lo[0]
        elif hi[0] < -0.02:
            edge = -hi[0]
        if edge is not None:
            blockers.append((edge, objs[k].name))
            inner = min(inner, edge)
print("CENTRAL AISLE at eye height: %.2f m wide (free x +-%.2f)" % (2 * inner, inner))
blockers.sort()
print("   blockers: %s" % ", ".join("%s@%.2f" % (n, e) for e, n in blockers[:6]))

seat = 0.0
for k, (lo, hi) in enumerate(B):
    if objs[k].name.split("_")[0][:2] in ("bn", "tb") and 2.00 < lo[0] < 8.75 and hi[2] < 1.60:
        seat = max(seat, hi[0])
print("SEATING BLOCK reaches x %.2f -> clear gap to pier face x=%.2f : %.2f m"
      % (seat, CI.XNAVE, CI.XNAVE - seat))

# ---------------------------------------------------------------- support audit
# one BVH over every triangle in the hall; a part is borne when some other
# part's surface lies within 5 cm of it (that is a joint, not a gap)
from mathutils.bvhtree import BVHTree  # noqa: E402

allv = []
allp = []
towner = []
for k, o in enumerate(objs):
    mw = o.matrix_world
    base = len(allv)
    allv.extend([mw @ v.co for v in o.data.vertices])
    me = o.data
    me.calc_loop_triangles()
    for lt in me.loop_triangles:
        allp.append((base + lt.vertices[0], base + lt.vertices[1], base + lt.vertices[2]))
        towner.append(k)
bvh = BVHTree.FromPolygons(allv, allp, all_triangles=True)
print("BVH tris %d" % len(allp))

floating = []
for k, o in enumerate(objs):
    lo, hi = B[k]
    if lo[2] < 0.055 and k < len(objs):
        pass
    mw = o.matrix_world
    me2 = o.data
    me2.calc_loop_triangles()
    vs = [mw @ v.co for v in me2.vertices]
    vs += [mw @ ((me2.vertices[lt.vertices[0]].co
                  + me2.vertices[lt.vertices[1]].co
                  + me2.vertices[lt.vertices[2]].co) / 3.0)
           for lt in me2.loop_triangles[:40]]
    if not vs:
        continue
    if len(vs) > 150:
        vs.sort(key=lambda c: c.z)
        sample = vs[::max(1, len(vs) // 150)][:150]
    else:
        sample = vs
    best = 99.0
    for co in sample:
        for (loc, nor, idx, dist) in bvh.find_nearest_range(co, 0.10):
            if towner[idx] == k:
                continue
            if dist < best:
                best = dist
                if best <= 0.05:
                    break
        if best <= 0.05:
            break
    if best > 0.05 and lo[2] > 0.055:
        floating.append((best, o.name, lo, hi))
floating.sort()
print("FLOATING %d  (no other surface within 5 cm)" % len(floating))
for d, nm, lo, hi in floating[:30]:
    print("   %5.3f %-24s x %6.2f..%6.2f y %7.2f..%7.2f z %6.2f..%6.2f"
          % (d, nm, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))

# ---------------------------------------------------------------- budget
fam = {}
for o in objs:
    nm = o.name
    base = nm.split("_")[0]
    while base and base[-1].isdigit():
        base = base[:-1]
    fam[base] = fam.get(base, 0) + ntris(o.data)
top = sorted(fam.items(), key=lambda kv: -kv[1])
print("FAMILIES %d" % len(top))
for nm, t in top[:24]:
    print("   %-12s %7d" % (nm, t))
print("MATERIALS %d" % len(bpy.data.materials))
