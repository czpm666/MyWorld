"""Debug the feast hall + stair lighting: 3 small frames, no hero shots."""
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
print("DBG meshes=%d" % len([o for o in P if o.type == "MESH"]), flush=True)

for ob in P:
    if ob.type == "LIGHT" and ob.location.z > 19.0:
        print("  LIGHT %-12s (%.2f, %.2f, %.2f) E=%.0f %s"
              % (ob.name.split(".")[0], ob.location.x, ob.location.y,
                 ob.location.z, ob.data.energy, ob.data.type), flush=True)

H.setup_engine(samples=32, res=(480, 270), gpu=True)
sc = bpy.context.scene
sc.view_settings.exposure = 0.22

L = bpy.data.lights.new("sun", "SUN")
L.energy = 260.0
L.angle = math.radians(1.2)
L.color = (1.0, 0.94, 0.86)
o = bpy.data.objects.new("sun", L)
K.link(o)
o.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))

w = sc.world or bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
bg.inputs[1].default_value = 0.10
vol = w.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.0020
vol.inputs["Anisotropy"].default_value = 0.4
out = w.node_tree.nodes["World Output"]
w.node_tree.links.new(vol.outputs[0], out.inputs["Volume"])

FZ0 = CI.Z_FEAST
SHOTS = [
    ("DBG_fp", (-8.6, 0.0, FZ0 + 1.60), (-12.95, 0.0, FZ0 + 1.10), 35.0),
    ("DBG_feast", (CI.HX - 1.8, -7.2, FZ0 + 1.72), (-8.0, 1.4, FZ0 + 1.90), 26.0),
    ("DBG_stair", (CI.ST_CX + 1.75 * math.cos(math.radians(250.0)),
                   CI.ST_CY + 1.75 * math.sin(math.radians(250.0)), 3.05),
                  (CI.ST_CX + 2.20 * math.cos(math.radians(300.0)),
                   CI.ST_CY + 2.20 * math.sin(math.radians(300.0)), 3.95), 22.0),
]
for nm, loc, look, lens in SHOTS:
    cam = CI._cam(nm, loc, look, lens)
    sc.camera = cam
    H.render_to(r"E:\My World\Blender\renders\kingdom\look\%s.png" % nm, cam)
    print("DBG saved", nm, flush=True)
