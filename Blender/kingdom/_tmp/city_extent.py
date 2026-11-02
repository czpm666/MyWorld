import bpy, os, sys, math

blend = r"E:\My World\Blender\renders\kingdom\capital_full.blend"
bpy.ops.wm.open_mainfile(filepath=blend)

def radius_of(objs):
    import mathutils
    lo = 1e9
    hi = 0.0
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ mathutils.Vector(c)
            r = math.hypot(w.x, w.y)
            lo = min(lo, r)
            hi = max(hi, r)
    return lo, hi

groups = {}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    n = ob.name
    key = "city" if n.startswith("city_blk") else ("burbs" if n.startswith("sub") else
           ("outer" if n.startswith("outer") else ("ogate" if n.startswith("ogate") else
           ("props" if n.startswith("street_props") else ("fields" if n.startswith(("field", "hedge")) else
           ("walls" if n.startswith(("owall", "owt")) else "other"))))))
    groups.setdefault(key, []).append(ob)

for k, v in sorted(groups.items()):
    lo, hi = radius_of(v)
    print("GROUP %-8s n=%-5d r %.1f .. %.1f" % (k, len(v), lo, hi), flush=True)

# also the layout numbers the build printed
import hd_layout as L
print("layout radius attr:", getattr(L, "R_BUILD", None), getattr(L, "R_WALL", None))
print("DONE")
