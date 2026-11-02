"""Find objects that sit near the world origin (the reported orphan slabs) and
report the tallest ones.  Run:
  blender -b --factory-startup --python _gdiag.py
"""
import sys
import mathutils
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G

H = G.H
H._clear()
MAT = G.materials()
import random
rng = random.Random(20261030)
obs = G.build(MAT, rng)

print("=== total objects: %d" % len(obs))
rows = []
for ob in obs:
    if ob is None or ob.type != "MESH":
        continue
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    rows.append((ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
                 ob.data.materials[0].name if ob.data.materials else "-"))

near = [r for r in rows if abs(r[1]) < 0.5 and abs(r[2]) < 0.5 and abs(r[3]) < 0.5
        and abs(r[4]) < 0.5]
print("=== objects whose bbox is entirely within +-0.5 m of the origin: %d" % len(near))
for r in near:
    print("   %-18s x[%6.2f %6.2f] y[%6.2f %6.2f] z[%7.2f %6.2f] %s"
          % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))

tall = [r for r in rows if r[6] - r[5] > 8.0 and abs(r[1]) < 4 and abs(r[2]) < 4
        and abs(r[3]) < 4 and abs(r[4]) < 4]
print("=== tall (>8 m) objects within 4 m of the origin: %d" % len(tall))
for r in tall:
    print("   %-18s x[%6.2f %6.2f] y[%6.2f %6.2f] z[%7.2f %6.2f] %s"
          % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))

for k in ("gb_asps", "asps"):
    hits = [r for r in rows if k in r[0]]
    print("=== name contains %s: %d" % (k, len(hits)))
    for r in hits:
        print("   %-18s x[%6.2f %6.2f] y[%6.2f %6.2f] z[%7.2f %6.2f] %s"
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
print("=== objects with no material / no parent chain check done")
print("=== scene objects (all, incl. non-returned): %d" % len(list(G.bpy.data.objects)))
ret = set(ob.name for ob in obs if ob is not None)
extra = [ob for ob in G.bpy.data.objects if ob.name not in ret and ob.type == "MESH"]
print("=== mesh objects in the scene that build() did NOT return: %d" % len(extra))
for ob in extra[:40]:
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    zs = [v.z for v in bb]
    print("   %-18s x[%6.2f %6.2f] z[%7.2f %6.2f]" % (ob.name, min(xs), max(xs),
                                                      min(zs), max(zs)))
