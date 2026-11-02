import bpy, mathutils, math

bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")

for nm in ("street_props", "wells", "outer_wall", "outer_gates"):
    ob = bpy.data.objects.get(nm)
    if ob is None:
        print("MISSING", nm)
        continue
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    rs = [math.hypot(v.x, v.y) for v in vs]
    print("%-14s verts=%-7d r %.1f..%.1f  x %.1f..%.1f  z %.1f..%.1f"
          % (nm, len(vs), min(rs), max(rs), min(v.x for v in vs), max(v.x for v in vs),
             min(v.z for v in vs), max(v.z for v in vs)), flush=True)

# how many objects start with lp/br/cr/ct (props that never got merged)
n = sum(1 for o in bpy.data.objects if o.name.split(".")[0] in ("lp", "br", "cr", "ct"))
print("loose prop objects:", n)
print("DONE")
