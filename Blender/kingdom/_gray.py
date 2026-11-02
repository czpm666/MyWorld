"""What is actually behind a pixel?  Casts rays through a grid of pixels of a
named camera and reports the first object hit.

    blender -b --factory-startup --python _gray.py -- arch 860 40 960 150 5
"""
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_common as H                                          # noqa: E402
import hd_gate as G                                            # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
shot = argv[0]
x0, y0, x1, y1 = (int(v) for v in argv[1:5])
step = int(argv[5]) if len(argv) > 5 else 8

H._clear()
MAT = G.materials()
rng = random.Random(20261030)
G.build(MAT, rng)
scene = bpy.context.scene
res = {s[0]: s for s in G.SHOTS}[shot]
cam = H.camera("cam_" + shot, res[1], res[2], res[3])
scene.camera = cam
W, H_ = (1400, 900)
scene.render.resolution_x = W
scene.render.resolution_y = H_
dg = bpy.context.evaluated_depsgraph_get()
mw = cam.matrix_world
frame = cam.data.view_frame(scene=scene)     # 4 corners at z = -1 (tr, br, bl, tl)
tr, br, bl, tl = frame
org = mw.translation.copy()

print("[ray] camera at", tuple(round(v, 2) for v in org))
for py in range(y0, y1 + 1, step):
    row = []
    for px in range(x0, x1 + 1, step):
        u, v = px / (W - 1.0), py / (H_ - 1.0)
        top = tl.lerp(tr, u)
        bot = bl.lerp(br, u)
        pt = top.lerp(bot, v)
        d = (mw @ pt) - org
        d.normalize()
        hit, loc, nor, idx, ob, _m = scene.ray_cast(dg, org, d, distance=400.0)
        row.append((ob.name[:9], round(loc.z, 1)) if hit else ("-SKY-", 0))
    print("y=%4d " % py + " ".join("%s@%s" % r for r in row))
