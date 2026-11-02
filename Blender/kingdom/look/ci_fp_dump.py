"""List the hearth boxes with their world bounds, to see what closes the firebox."""
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy  # noqa: E402
import hd_castle_int as CI  # noqa: E402

K = __import__("medkit")
K.reset_scene()
MAT = CI.make_mats()
P = CI.build(K, MAT, origin=(0.0, 0.0), seed=3)
names = {}
for ob in P:
    n = ob.name.split(".")[0]
    if not n.startswith("ci_fp"):
        continue
    bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    names.setdefault(n, []).append((min(xs), max(xs), min(ys), max(ys),
                                    min(zs), max(zs)))
for n in sorted(names):
    for b in names[n][:3]:
        print("%-16s x %7.2f..%7.2f  y %6.2f..%6.2f  z %6.2f..%6.2f"
              % (n, b[0], b[1], b[2], b[3], b[4], b[5]))
print("HX=%.2f FZ0=%.2f" % (CI.HX, CI.FZ0))
