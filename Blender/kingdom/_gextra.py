import sys, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import bpy
import hd_common as H
import hd_gate as G
H._clear()
M = G.make_materials()
obs = G.build(M, random.Random(20261030))
flat = G._flat(obs)
ret = set(o.name for o in flat)
for o in bpy.data.objects:
    if o.type == "MESH" and o.name not in ret:
        bb = [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
        lo = tuple(round(min(v[i] for v in bb), 2) for i in range(3))
        hi = tuple(round(max(v[i] for v in bb), 2) for i in range(3))
        print("[extra] %-22s verts=%4d lo=%s hi=%s" % (o.name, len(o.data.vertices), lo, hi))
print("[extra] total meshes in scene =", len([o for o in bpy.data.objects if o.type == "MESH"]))
