"""Is the feast hall merely underexposed, or are the lights blocked?"""
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
H.setup_engine(samples=24, res=(480, 270), gpu=True)
sc = bpy.context.scene

w = sc.world or bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
bg.inputs[1].default_value = 0.10
vol = w.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.0026
vol.inputs["Anisotropy"].default_value = 0.4
nt = w.node_tree
nt.links.new(vol.outputs[0], nt.nodes["World Output"].inputs["Volume"])

L = bpy.data.lights.new("sun", "SUN")
L.energy = 260.0
L.color = (1.0, 0.93, 0.80)
o = bpy.data.objects.new("sun", L)
K.link(o)
o.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))

FZ0 = CI.Z_FEAST
cam = CI._cam("cx", (CI.HX - 2.30, -5.60, FZ0 + 1.72),
              (-9.20, 0.60, FZ0 + 2.10), 24.0)
sc.camera = cam

for ex in (0.22, 1.40, 3.00):
    sc.view_settings.exposure = ex
    H.render_to(r"E:\My World\Blender\renders\kingdom\look\DBG_exp_%s.png"
                % str(ex).replace(".", "_"), cam)
    print("DBG exposure", ex, flush=True)
