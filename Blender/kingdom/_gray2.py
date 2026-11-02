import random, sys
import bpy
from mathutils import Vector
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_common as H
import hd_gate as G
H._clear()
MAT = G.materials()
rng = random.Random(20261030)
G.build(MAT, rng)
sc = bpy.context.scene
res = {s[0]: s for s in G.SHOTS}["south"]
cam = H.camera("cam_south", res[1], res[2], res[3])
sc.camera = cam
W, Hh = 1400, 900
sc.render.resolution_x, sc.render.resolution_y = W, Hh
dg = bpy.context.evaluated_depsgraph_get()
mw = cam.matrix_world
tr, br, bl, tl = cam.data.view_frame(scene=sc)
org = mw.translation.copy()
for py in (580, 590, 600):
    for px in (690, 700, 710, 720):
        u, v = px / (W - 1.0), py / (Hh - 1.0)
        pt = tl.lerp(tr, u).lerp(bl.lerp(br, u), v)
        d = (mw @ pt) - org
        d.normalize()
        hit, loc, nor, idx, ob, _m = sc.ray_cast(dg, org, d, distance=400.0)
        print("[hit] %d,%d %-14s at (%.2f, %.2f, %.2f)" %
              (px, py, ob.name if hit else "-sky-", loc.x, loc.y, loc.z))
