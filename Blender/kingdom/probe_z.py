import bpy, os, sys
from mathutils import Vector

path = r"E:\My World\Blender\export\kingdom\mine\mine_a.fbx"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
for ob in sorted(bpy.context.scene.objects, key=lambda o: o.name):
    if ob.type != "MESH":
        continue
    zs = [(ob.matrix_world @ Vector(c))[2] for c in ob.bound_box]
    flag = "  <== ABOVE GROUND" if max(zs) > 0.001 else ""
    print("%-22s z[%7.3f %7.3f] %s" % (ob.name, min(zs), max(zs), flag))
