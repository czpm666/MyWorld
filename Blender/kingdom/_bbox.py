import bpy, sys
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\kingdom\port_a.blend")
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        for i in range(3):
            lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    print("%-22s x[%7.2f %7.2f] y[%7.2f %7.2f] z[%6.2f %6.2f]" % (
        ob.name, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z))
