"""Which meshes sit on the throne-wall face (z-fighting suspects)?"""
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

from mathutils import Vector
import medkit as K
import hd_castle_int as INT

K.reset_scene()
M = INT.prep(INT.make_mats())
P = INT.build(K, M, origin=(0.0, 0.0), seed=3)

tests = ((-13.0, 0.0, 3.0), (-13.0, 0.0, 9.0), (-13.0, 6.0, 6.0),
         (-13.0, -6.0, 6.0), (-6.0, 9.0, 6.0), (0.0, 8.54, 6.0))
for pt in tests:
    print("== box around %s" % (pt,))
    for ob in P:
        if ob is None or ob.type != "MESH":
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb),
                     min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb),
                     max(v.z for v in bb)))
        tol = 0.03
        if (lo.x - tol <= pt[0] <= hi.x + tol and lo.y - tol <= pt[1] <= hi.y + tol
                and lo.z - tol <= pt[2] <= hi.z + tol):
            mats = ",".join(m.name if m else "?" for m in ob.data.materials)
            print("   x %8.3f %8.3f  y %7.3f %7.3f  z %6.3f %6.3f  %-18s %s"
                  % (lo.x, hi.x, lo.y, hi.y, lo.z, hi.z, ob.name, mats))
