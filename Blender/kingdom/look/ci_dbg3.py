"""Lit-from-outside diagnostic for the feast hall: is the fireplace even there?"""
import math
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy

import hd_common as H
import hd_castle_int as CI
import medkit as K

K.reset_scene()
MAT = CI.prep(CI.make_mats())
P = CI.build(K, MAT)

names = {}
for ob in P:
    if ob.type != "MESH":
        continue
    a, b = H.bbox([ob])
    if a.z > 20.0 and "fp" in ob.name:
        names.setdefault(ob.name.split(".")[0], []).append((a.x, b.x, a.y, b.y, a.z, b.z))
for k, v in names.items():
    print("FP %-12s n=%d  x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f"
          % (k, len(v), v[0][0], v[0][1], v[0][2], v[0][3], v[0][4], v[0][5]), flush=True)

H.setup_engine(samples=16, res=(480, 270), gpu=True)
sc = bpy.context.scene
sc.view_settings.exposure = 0.0

w = sc.world or bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.25, 0.30, 0.40, 1.0)
bg.inputs[1].default_value = 0.60

FZ0 = CI.Z_FEAST
L = bpy.data.lights.new("head", "AREA")
L.energy = 24000.0
L.size = 3.0
o = bpy.data.objects.new("head", L)
K.link(o)
o.location = (-3.4, -6.4, FZ0 + 4.6)
d = bpy.data.objects.new("tgt", None)
cam = CI._cam("h", (-3.4, -6.4, FZ0 + 4.6), (-12.9, 0.0, FZ0 + 1.0), 24.0)
o.rotation_euler = cam.rotation_euler

for nm, loc, look, lens in (
        ("DBG_feast_lit", (-3.4, -6.4, FZ0 + 1.66), (-12.90, 0.0, FZ0 + 1.70), 24.0),
        ("DBG_fp", (-8.2, 0.0, FZ0 + 1.55), (-13.0, 0.0, FZ0 + 1.05), 30.0),
        ("DBG_ftop", (0.5, -3.0, FZ0 + 6.5), (-6.0, 1.0, FZ0 + 0.6), 18.0)):
    c = CI._cam(nm, loc, look, lens)
    sc.camera = c
    H.render_to(r"E:\My World\Blender\renders\kingdom\look\%s.png" % nm, c)
    print("DBG saved", nm, flush=True)
