"""Object / triangle census for a saved capital .blend.

    blender -b --factory-startup --python _tmp/stats_blend.py -- [--blend <path>]

Prints per-prefix counts plus totals, so the report quotes numbers measured on
the saved file rather than on a partially built scene.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.join(os.path.dirname(HERE), "kingdom")
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                  # noqa: E402
import capital as C                                         # noqa: E402


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index(name) + 1] if name in a else default


blend = arg("--blend", os.path.join(C.OUT_PNG, "capital_full.blend"))
bpy.ops.wm.open_mainfile(filepath=blend)

PREFIX = ("ground", "wall", "wt_", "gate", "inner", "itw", "castle", "rock",
          "cath", "guild", "mkt", "fnt", "house", "street", "harbour", "quay",
          "hills", "h_", "sub", "tree", "field")

n_objs = n_mesh = faces = tris = verts = 0
per = Counter()
tri_per = Counter()
mats = set()
for ob in bpy.data.objects:
    n_objs += 1
    if ob.type != "MESH":
        continue
    n_mesh += 1
    me = ob.data
    np_ = len(me.polygons)
    nv = len(me.vertices)
    faces += np_
    verts += nv
    tris += sum(len(p.vertices) - 2 for p in me.polygons)
    key = "other"
    for p in PREFIX:
        if ob.name.lower().startswith(p):
            key = p
            break
    per[key] += 1
    tri_per[key] += sum(len(p.vertices) - 2 for p in me.polygons)
    for slot in ob.material_slots:
        if slot.material:
            mats.add(slot.material.name)

print("[stats] file      =", blend, flush=True)
print("[stats] objects   = %d (%d mesh, %d other)"
      % (n_objs, n_mesh, n_objs - n_mesh), flush=True)
print("[stats] faces     = %d" % faces, flush=True)
print("[stats] triangles = %d" % tris, flush=True)
print("[stats] vertices  = %d" % verts, flush=True)
print("[stats] materials = %d" % len(mats), flush=True)
print("[stats] --- objects / triangles by prefix ---", flush=True)
for k, v in per.most_common():
    print("[stats] %-10s objects=%-6d tris=%d" % (k, v, tri_per[k]), flush=True)
print("[stats] images    =", len([i for i in bpy.data.images if i.size[0]]), flush=True)
print("STATS_DONE", flush=True)
