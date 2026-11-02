"""Hunt free-standing tall/thin meshes anywhere in the scene, plus objects that
share mesh data (accidental duplicates).  Run:
  blender -b --factory-startup --python _gdiag2.py
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

rows = []
for ob in obs:
    if ob is None or ob.type != "MESH":
        continue
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    rows.append((ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
                 ob.data.name))

print("=== tall (>8 m) and thin (footprint < 3.6 m in either axis):")
n = 0
for r in rows:
    w = r[2] - r[1]
    d = r[4] - r[3]
    h = r[6] - r[5]
    if h > 8.0 and (w < 3.6 or d < 3.6) and w * d < 26.0:
        n += 1
        if n < 40:
            print("   %-18s x[%7.2f %7.2f] y[%7.2f %7.2f] z[%6.2f %6.2f]  w%.2f d%.2f h%.2f"
                  % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], w, d, h))
print("   total: %d" % n)

names = {}
for r in rows:
    names.setdefault(r[7], []).append(r[0])
dup = {k: v for k, v in names.items() if len(v) > 1}
print("=== mesh datablocks shared by >1 object: %d" % len(dup))
for k, v in list(dup.items())[:10]:
    print("   %s  ->  %s" % (k, v[:6]))

print("=== anything whose mesh has 0 polygons: %d"
      % len([o for o in obs if o is not None and o.type == "MESH" and len(o.data.polygons) == 0]))
print("=== object count by name prefix:")
pref = {}
for r in rows:
    p = r[0].split("_")[0]
    pref[p] = pref.get(p, 0) + 1
for k in sorted(pref):
    print("   %-8s %d" % (k, pref[k]))
