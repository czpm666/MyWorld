"""Debug: build, add a headlight, and look straight into the hearth."""
import os
import sys
import math

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy  # noqa: E402
import hd_common as H  # noqa: E402
import hd_castle_int as CI  # noqa: E402

K = __import__("medkit")

K.reset_scene()
MAT = CI.make_mats()
P = CI.build(K, MAT, origin=(0.0, 0.0), seed=3)
print("DBG parts=%d tris=%d" % (len(P), CI._tris(P)), flush=True)
H.setup_engine(samples=8, res=(480, 270), gpu=True)
sc = bpy.context.scene
sc.view_settings.view_transform = "AgX"

L = bpy.data.lights.new("dbg", "AREA")
L.energy = 2600.0
L.size = 3.0
L.color = (1.0, 0.96, 0.92)
o = bpy.data.objects.new("dbg", L)
o.location = (-9.6, 0.0, CI.FZ0 + 2.6)
o.rotation_euler = (0.0, math.radians(-72.0), 0.0)
K.link(o)

for nm, loc, look, lens in (
        ("DBG_fp", (-10.4, 0.0, CI.FZ0 + 1.30), (-13.2, 0.0, CI.FZ0 + 0.85), 26.0),
        ("DBG_fp2", (-9.2, 3.0, CI.FZ0 + 1.60), (-12.6, 0.6, CI.FZ0 + 1.00), 26.0),
):
    cam = CI._cam("dbg_" + nm, loc, look, lens=lens)
    sc.camera = cam
    sc.render.filepath = os.path.join(CI.OUT, nm + ".png")
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath, flush=True)
