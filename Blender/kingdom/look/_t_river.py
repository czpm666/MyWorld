"""Smoke test hd_river + hd_street on a factory scene (no city build).

    blender -b --factory-startup --python look/_t_river.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
for p in (os.path.dirname(KIND), KIND, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy
import medkit as K
import capital as C

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

MAT = {}
C.init_mats()
MAT = C.MAT

t0 = time.time()
try:
    import hd_river as HR
    objs = HR.build(K, MAT, C.outer_gaps())
    o = f = 0
    for ob in objs:
        if ob.type == 'MESH':
            o += 1
            f += len(ob.data.polygons)
    print("[t] hd_river ok: %d objects, %d faces, %.1f s" % (o, f, time.time() - t0))
    for ob in objs:
        print("    %-18s %7d faces" % (ob.name, len(ob.data.polygons)))
except Exception:
    import traceback
    traceback.print_exc()
print("[t] done %.1f s" % (time.time() - t0))
