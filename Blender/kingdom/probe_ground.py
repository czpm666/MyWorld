import bpy, os, sys
from mathutils import Vector

d = r"E:\My World\Blender\export\kingdom\mine"
for name in ("mine_a", "mine_b", "mine_c"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(d, name + ".fbx"))
    print("[z] ===", name)
    for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if ob.type != "MESH":
            continue
        lo = min((ob.matrix_world @ Vector(c)).z for c in ob.bound_box)
        hi = max((ob.matrix_world @ Vector(c)).z for c in ob.bound_box)
        if ob.name.split(".")[0] in ("ground", "ground_edge", "plate", "slab",
                                     "yard", "lane", "fence"):
            print("[z] %-12s min=%7.3f max=%7.3f  (max<=0.001: %s)"
                  % (ob.name, lo, hi, "PASS" if hi <= 0.001 else "fail"))
