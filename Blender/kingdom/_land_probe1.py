"""Probe capital_v23.blend: what actually exists, and where."""
import bpy, os, sys, math, json

bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_v23.blend")

groups = {}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    n = ob.name
    pre = ""
    for i, ch in enumerate(n):
        if ch.isdigit() or ch == "_":
            pre = n[:i]
            break
    else:
        pre = n
    pre = pre.rstrip("_") or n
    bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    g = groups.setdefault(pre, dict(n=0, f=0, x0=1e9, x1=-1e9, y0=1e9, y1=-1e9, z0=1e9, z1=-1e9, zc=0.0))
    g["n"] += 1
    g["f"] += len(ob.data.polygons)
    g["x0"] = min(g["x0"], min(xs)); g["x1"] = max(g["x1"], max(xs))
    g["y0"] = min(g["y0"], min(ys)); g["y1"] = max(g["y1"], max(ys))
    g["z0"] = min(g["z0"], min(zs)); g["z1"] = max(g["z1"], max(zs))
    g["zc"] += ob.matrix_world.translation.z

print("== TOTAL objects", len(bpy.data.objects), "meshes", len(bpy.data.meshes))
print("== %-22s %5s %10s  %-42s %s" % ("prefix", "n", "faces", "xy bbox", "z bbox"))
for k in sorted(groups, key=lambda k: -groups[k]["n"]):
    g = groups[k]
    print("%-24s %5d %10d  x[%7.1f,%7.1f] y[%7.1f,%7.1f]  z[%6.2f,%6.2f] zc=%6.2f"
          % (k, g["n"], g["f"], g["x0"], g["x1"], g["y0"], g["y1"], g["z0"], g["z1"],
             g["zc"] / max(1, g["n"])))

print("== materials", len(bpy.data.materials))
print("== objects named ground* / hill* / road_out* / field* / hedge* / river*")
for ob in bpy.data.objects:
    n = ob.name
    if n.startswith(("ground", "hill", "road_out", "field", "hedge", "river", "quay")):
        bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
        xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
        mats = [m.name if m else None for m in ob.data.materials]
        print("  %-16s %-12s %6d f  x[%8.1f,%8.1f] y[%8.1f,%8.1f] z[%6.2f,%6.2f]  %s"
              % (n, ob.type, len(ob.data.polygons), min(xs), max(xs), min(ys), max(ys),
                 min(zs), max(zs), mats))

# any object at all with y < -600 ?
print("== objects with min y < -600")
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
    if min(v.y for v in bb) < -600:
        print("   ", ob.name, min(v.y for v in bb), max(v.y for v in bb))
