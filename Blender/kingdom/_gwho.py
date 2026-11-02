"""List tall objects in the moat corner region (identify the mystery post)."""
import sys
import mathutils
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_gate as G
import random

H = G.H
H._clear()
MAT = G.materials()
rng = random.Random(20261030)
obs = G.build(MAT, rng)
for ob in obs:
    if ob is None or ob.type != "MESH":
        continue
    bb = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]
    ys = [v.y for v in bb]
    zs = [v.z for v in bb]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    h = max(zs) - min(zs)
    if 3.0 < cx < 26.0 and 17.0 < cy < 36.0 and h > 1.6:
        print("%-20s x[%6.2f %6.2f] y[%6.2f %6.2f] z[%6.2f %6.2f] h=%5.2f mat=%s"
              % (ob.name, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), h,
                 ob.active_material.name if ob.active_material else "-"))
