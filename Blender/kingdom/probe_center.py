"""Ray-probe the 1600x900 overview camera at a few pixels and name what is hit.

Run:  blender.exe -b --factory-startup --python probe_center.py -- --stage mass
The point is to identify that dark disc in the middle of ars_overview.png.
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
from mathutils import Vector

import capital as CAP
import kcommon as KC


def cam_rays(cam, u, v, W=1600, H=900):
    """u,v in 0..1 with (0,0) = top-left."""
    lens = cam.data.lens
    tan_h = 18.0 / lens
    tan_v = tan_h * float(H) / float(W)
    m = cam.matrix_world
    right = m.to_3x3() @ Vector((1, 0, 0))
    up = m.to_3x3() @ Vector((0, 1, 0))
    fwd = m.to_3x3() @ Vector((0, 0, -1))
    d = (fwd + right * ((u - 0.5) * 2.0 * tan_h) + up * ((0.5 - v) * 2.0 * tan_v))
    return m.translation.copy(), d.normalized()


def main(argv):
    stage = "mass"
    if "--stage" in argv:
        stage = argv[argv.index("--stage") + 1]
    CAP.build(stage)
    KC.clear_lights_cameras()
    name, loc, look, lens = CAP.SHOTS[0]
    KC.setup_camera(loc, look, lens)
    cam = bpy.context.scene.camera
    dg = bpy.context.evaluated_depsgraph_get()
    pts = [(0.50, 0.50), (0.45, 0.47), (0.40, 0.45), (0.50, 0.44),
           (0.55, 0.52), (0.45, 0.55), (0.62, 0.60), (0.50, 0.40)]
    for u, v in pts:
        o, d = cam_rays(cam, u, v)
        hit, p, nor, idx, ob, mw = bpy.context.scene.ray_cast(dg, o, d, distance=5000.0)
        if hit:
            me = ob.data
            print("[probe] u=%.2f v=%.2f -> %-22s at (%.1f, %.1f, %.2f) mats=%s faces=%d"
                  % (u, v, ob.name, p.x, p.y, p.z,
                     ",".join(m.name for m in me.materials if m) if me else "-",
                     len(me.polygons) if me else -1))
        else:
            print("[probe] u=%.2f v=%.2f -> MISS" % (u, v))
    # also: every flat object that covers the origin, sorted by area
    print("[probe] --- flat objects covering (0,0) ---")
    rows = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        vs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        xs = [v.x for v in vs]
        ys = [v.y for v in vs]
        zs = [v.z for v in vs]
        if not (min(xs) <= 0 <= max(xs) and min(ys) <= 0 <= max(ys)):
            continue
        dz = max(zs) - min(zs)
        if dz > 8.0 or min(zs) > 8.0:
            continue
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        mats = ",".join(m.name for m in ob.data.materials if m)
        rows.append((area, ob.name, dz, min(zs), max(zs), ob.dimensions.x, ob.dimensions.y, mats))
    rows.sort(reverse=True)
    for area, nm, dz, z0, z1, dx, dy, mats in rows[:25]:
        print("[flat] %-22s area=%8.0f m2  z=[%.2f..%.2f]  dims=%.1fx%.1f  mats=%s"
              % (nm, area, z0, z1, dx, dy, mats))
    print("PROBE_DONE")


if __name__ == "__main__":
    main(sys.argv)
