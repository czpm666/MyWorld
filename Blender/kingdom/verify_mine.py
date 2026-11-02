"""Fresh-process verification of the exported mine FBX files.

Usage:  blender -b --factory-startup --python verify_mine.py -- mine_a mine_b mine_c
Prints per file: object count, total triangles, material count, world bbox,
root empties/transforms (Unity contract: root scale 100, rotation 270,0,0).
"""
import bpy
import os
import sys
from mathutils import Vector

EXPORT_DIR = r"E:\My World\Blender\export\kingdom\mine"


def measure(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    tris = 0
    mats = set()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in meshes:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
        for m in ob.data.materials:
            if m:
                mats.add(m.name)
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])

    roots = [o for o in bpy.context.scene.objects
             if o.parent is None and o.type != "MESH"]
    root_info = []
    for r in roots:
        s = r.matrix_world.to_scale()
        e = r.matrix_world.to_euler()
        root_info.append(
            "root '%s' type=%s scale=(%.3f,%.3f,%.3f) rot_deg=(%.1f,%.1f,%.1f)"
            % (r.name, r.type, s.x, s.y, s.z,
               e.x * 57.29578, e.y * 57.29578, e.z * 57.29578))

    print("[verify] file      : %s" % path)
    print("[verify] bytes     : %d" % os.path.getsize(path))
    print("[verify] objects   : %d mesh, %d total" % (len(meshes), len(bpy.context.scene.objects)))
    print("[verify] triangles : %d" % tris)
    print("[verify] materials : %d" % len(mats))
    print("[verify] bbox min  : (%.2f, %.2f, %.2f)" % (lo.x, lo.y, lo.z))
    print("[verify] bbox max  : (%.2f, %.2f, %.2f)" % (hi.x, hi.y, hi.z))
    print("[verify] bbox size : (%.2f, %.2f, %.2f)" % (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z))
    for line in root_info:
        print("[verify] " + line)
    if not root_info:
        print("[verify] root      : (none - flat scene, no empties)")
    return len(meshes), tris, len(mats)


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
for name in argv:
    measure(os.path.join(EXPORT_DIR, name + ".fbx"))
    print("")
