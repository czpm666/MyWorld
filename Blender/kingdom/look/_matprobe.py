"""Ray-cast through the player camera and report the material of every hit.

Answers "which material is that navy roof actually using" without guessing from
the render.
"""
import math
import sys

sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender\kingdom\look")

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import render as RD  # noqa: E402

table = RD.shot_table()
spec = table["game"]
eye = Vector(spec["loc"])
look = Vector(spec["look"])

fwd = (look - eye).normalized()
right = fwd.cross(Vector((0.0, 0.0, 1.0))).normalized()
up = right.cross(fwd).normalized()

vfov = spec.get("vfov")
th = math.tan(math.radians(vfov) * 0.5) if vfov else 18.0 / spec.get("lens", 50.0)
tw = th * 16.0 / 9.0

dg = bpy.context.evaluated_depsgraph_get()
print("camera %s -> %s" % (tuple(round(v, 1) for v in eye), tuple(round(v, 1) for v in look)))
for gy in (-0.45, -0.15, 0.10, 0.35, 0.60):
    row = []
    for gx in (-0.55, -0.15, 0.20, 0.55):
        v = (fwd + right * (gx * tw) + up * (gy * th)).normalized()
        hit, loc, nrm, idx, ob, mtx = bpy.context.scene.ray_cast(dg, eye, v)
        if not hit:
            row.append("%+.2f,%+.2f sky" % (gx, gy))
            continue
        mat = "-"
        if ob and ob.type == "MESH" and len(ob.data.materials):
            poly = ob.data.polygons[idx] if idx < len(ob.data.polygons) else None
            slot = poly.material_index if poly else 0
            mat = ob.data.materials[slot].name if slot < len(ob.data.materials) else "?"
        row.append("%+.2f,%+.2f %-20s z=%4.1f nz=%+.2f" % (gx, gy, mat, loc.z, nrm.z))
    print(" || ".join(row))
print("done")
