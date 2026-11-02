"""Why does scene.ray_cast hit almost nothing in capital_v24.blend?

Prints: Blender version, view-layer/collection state, hide flags, object and
material counts, then casts a handful of rays three ways (numpy vs mathutils,
with and without clearing hide_viewport) and times 200 casts.

    python look/_shotrun.py --tag probe -- @blend --python look/_shotprobe.py
"""
import os
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                                             # noqa: E402


def cast(dg, o, d):
    return bpy.context.scene.ray_cast(dg, o, d)


def main():
    print("[p] blender", bpy.app.version_string, flush=True)
    sc = bpy.context.scene
    print("[p] scene %r objects %d meshes %d materials %d"
          % (sc.name, len(bpy.data.objects),
             sum(1 for o in bpy.data.objects if o.type == "MESH"),
             len(bpy.data.materials)), flush=True)
    vl = bpy.context.view_layer
    print("[p] view_layer %r" % vl.name, flush=True)
    for lc in vl.layer_collection.children:
        print("[p]   layer_collection %-24s exclude=%s hide_viewport=%s"
              % (lc.name, lc.exclude, lc.hide_viewport), flush=True)
    print("[p] scene collection children:",
          [c.name for c in sc.collection.children], flush=True)
    print("[p] top-level objects:", sum(1 for o in sc.collection.objects), flush=True)
    hv = sum(1 for o in bpy.data.objects if o.hide_viewport)
    hr = sum(1 for o in bpy.data.objects if o.hide_render)
    hg = sum(1 for o in bpy.data.objects if o.hide_get())
    print("[p] hide_viewport=%d hide_render=%d hide_get=%d" % (hv, hr, hg), flush=True)
    # where are the objects?
    zs = []
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n += 1
        if n > 4000:
            break
        zs.append(o.location.z)
    if zs:
        print("[p] first %d meshes: z min %.1f max %.1f" % (len(zs), min(zs), max(zs)),
              flush=True)
    # biggest objects by face count: these are the things a ray must hit
    big = sorted((o for o in bpy.data.objects if o.type == "MESH"),
                 key=lambda o: len(o.data.polygons), reverse=True)[:8]
    for o in big:
        print("[p] big %-30s faces %8d  loc %s  hide_vp=%s"
              % (o.name[:30], len(o.data.polygons),
                 tuple(round(v, 1) for v in o.location), o.hide_viewport), flush=True)

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    print("[p] depsgraph objects %d" % len(dg.object_instances), flush=True)

    tests = [((0.0, 0.0, 300.0), (0.0, 0.0, -1.0), "down at origin"),
             ((0.0, -46.0, 1.72), (0.0, 1.0, 0.0), "plaza south, horizontal +Y"),
             ((-204.0, -22.0, 1.72), (0.0, 1.0, 0.0), "street pick1, horizontal +Y"),
             ((0.0, -46.0, 1.72), (0.0, 1.0, -0.1), "plaza south, slightly down")]
    for (o, d, label) in tests:
        r1 = cast(dg, Vector(o), Vector(d).normalized())
        r2 = cast(dg, np.array(o, dtype=np.float64), np.array(d, dtype=np.float64))
        print("[p] %-34s mathutils hit=%s d=%s | numpy hit=%s d=%s"
              % (label, r1[0],
                 round((Vector(r1[1]) - Vector(o)).length, 1) if r1[0] else "-",
                 r2[0],
                 round(float(np.linalg.norm(np.array(r2[1]) - np.array(o))), 1)
                 if r2[0] else "-"), flush=True)

    # ---- does clearing hide_viewport change anything? ----
    if hv:
        t0 = time.time()
        for o in bpy.data.objects:
            if o.hide_viewport:
                o.hide_viewport = False
        bpy.context.view_layer.update()
        dg2 = bpy.context.evaluated_depsgraph_get()
        print("[p] cleared hide_viewport on %d objects in %.1f s"
              % (hv, time.time() - t0), flush=True)
        for (o, d, label) in tests:
            r1 = cast(dg2, Vector(o), Vector(d).normalized())
            print("[p] after-clear %-28s hit=%s d=%s mat=%s"
                  % (label, r1[0],
                     round((Vector(r1[1]) - Vector(o)).length, 1) if r1[0] else "-",
                     (r1[4].data.materials[0].name
                      if r1[0] and r1[4] and r1[4].data.materials else "")), flush=True)
        dg = dg2

    # ---- throughput ----
    eye = Vector((0.0, -46.0, 1.72))
    t0 = time.time()
    hits = 0
    for i in range(200):
        a = i * 0.0314
        v = Vector((np.cos(a) * 0.3, 1.0, -0.2)).normalized()
        if cast(dg, eye, v)[0]:
            hits += 1
    dt = time.time() - t0
    print("[p] 200 casts in %.2f s (%.2f ms each), %d hits"
          % (dt, dt * 1000.0 / 200.0, hits), flush=True)

    # ---- what materials exist ----
    names = sorted(m.name for m in bpy.data.materials)
    print("[p] %d materials; first 60: %s" % (len(names), ", ".join(names[:60])),
          flush=True)
    print("[p] more: %s" % ", ".join(names[60:160]), flush=True)


if __name__ == "__main__":
    main()
