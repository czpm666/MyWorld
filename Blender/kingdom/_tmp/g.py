import bpy
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")
for ob in bpy.data.objects:
    if ob.type!="MESH" or not ob.data or not ob.name.startswith("gh_asps1"): continue
    co=[ob.matrix_world @ v.co for v in ob.data.vertices]
    xs=[c.x for c in co]; ys=[c.y for c in co]; zs=[c.z for c in co]
    print("[g] %-14s x %6.1f..%6.1f y %6.1f..%6.1f z %5.1f..%5.1f verts=%d" % (ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), len(co)))
