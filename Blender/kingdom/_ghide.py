"""Render one shot with a set of objects hidden, to identify what is visible.

    blender -b --factory-startup --python _ghide.py -- moat bt_wt-1,bt_wt1 out.png
"""
import os
import random
import sys

import bpy

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_common as H                                          # noqa: E402
import hd_gate as G                                            # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
shot = argv[0] if argv else "moat"
hide = [n for n in (argv[1] if len(argv) > 1 else "").split(",") if n]
dest = argv[2] if len(argv) > 2 else "hide.png"

H._clear()
MAT = G.materials()
rng = random.Random(20261030)
OBS = G.build(MAT, rng)
for o in OBS:
    if o.name in hide:
        o.hide_render = True
        print("[hide] hid", o.name)
for n in hide:
    print("[hide]", n, "found" if n in bpy.data.objects else "MISSING")
if hide:
    mt = [m.name for o in OBS if o.name in hide for m in o.data.materials]
    print("[hide] materials:", mt)

H.setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0)
H.setup_engine(32, (900, 580), gpu=True)
res = {s[0]: s for s in G.SHOTS}
cam = res[shot]
bpy.context.scene.camera = H.camera("cam_" + shot, cam[1], cam[2], cam[3])
bpy.context.scene.render.filepath = dest
bpy.ops.render.render(write_still=True)
print("[hide] wrote", dest)
