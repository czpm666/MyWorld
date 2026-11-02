"""Diagnose the ground plate: per-object bbox and, for anything standing above
grade, the vertical extent of each material so we can name the offender."""
import bpy
import os
import sys

KINGDOM = r"E:\My World\Blender\kingdom"
variant = "port_a"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if argv:
    variant = argv[0]

bpy.ops.wm.open_mainfile(filepath=os.path.join(KINGDOM, "%s.blend" % variant))

print("=== per-object bbox ===")
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    print("OBJ %-22s z %7.3f .. %7.3f  polys %5d"
          % (ob.name, min(zs), max(zs), len(ob.data.polygons)))

print("=== what stands above z=0.05, by material ===")
agg = {}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    mw = ob.matrix_world
    for p in me.polygons:
        vs = [mw @ me.vertices[i].co for i in p.vertices]
        zmax = max(v.z for v in vs)
        if zmax <= 0.05:
            continue
        name = me.materials[p.material_index].name if me.materials else "?"
        a = agg.setdefault(name, [1e9, -1e9, 0, ob.name])
        a[0] = min(a[0], min(v.z for v in vs))
        a[1] = max(a[1], zmax)
        a[2] += 1
for name in sorted(agg, key=lambda k: -agg[k][2])[:14]:
    lo, hi, n, obn = agg[name]
    print("MAT %-22s z %7.3f .. %7.3f  faces %5d  (%s)" % (name, lo, hi, n, obn))

for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.hide_render = True
print("DIAG done")
