import bpy, sys, mathutils
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G
H = G.H
H._clear()
MAT = G.materials()
import random
rng = random.Random(7)
obs = G.build(MAT, rng, with_ground=False, with_props=False)
print("---- objects in the far mouth of the passage ----")
for ob in obs:
    if ob.type != 'MESH':
        continue
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    if max(ys) > -7.6 and min(ys) < -4.0 and min(xs) < 3.2 and max(xs) > -3.2 \
       and min(zs) < 5.0 and max(zs) > 0.2:
        print("%-16s tris~%4d x[%6.2f %6.2f] y[%7.2f %6.2f] z[%5.2f %5.2f] %s"
              % (ob.name, len(ob.data.polygons), min(xs), max(xs), min(ys), max(ys),
                 min(zs), max(zs), ob.data.materials[0].name if ob.data.materials else "-"))
