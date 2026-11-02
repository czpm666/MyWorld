"""list bbox of objects matching a prefix after build():  blender -b --factory-startup --python probe.py -- pre=ci_r"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for p in (KING, os.path.dirname(KING)):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                    # noqa: E402
import hd_common as H                                         # noqa: E402
import hd_cathedral_int as C                                  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
o = dict(t.split("=", 1) for t in a if "=" in t)
pre = o.get("pre", "ci_r")

H._clear()
import medkit as K                                            # noqa: E402
K._MAT_CACHE.clear()
M = C._ensure({})
C.build(M, __import__("random").Random(11))
bpy.context.view_layer.update()

for ob in sorted(bpy.data.objects, key=lambda x: x.name):
    if not ob.name.startswith(pre):
        continue
    bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    print("%-14s x %7.2f..%7.2f  y %7.2f..%7.2f  z %7.2f..%7.2f  v=%d" %
          (ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
           len(ob.data.vertices)))
