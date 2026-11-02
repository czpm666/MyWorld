"""Is the wall mottling just 8-sample denoiser blotch? One image, 64 spp."""
import sys
import math

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy
import medkit as K
import hd_common as H
import hd_castle_int as INT

SPP = 64

K.reset_scene()
M = INT.prep(INT.make_mats())
P = INT.build(K, M, origin=(0.0, 0.0), seed=3)
H.setup_engine(samples=SPP, res=(480, 270))
sc = bpy.context.scene
sc.view_settings.exposure = 0.55

sd = bpy.data.lights.new("t_sun", "SUN")
sd.energy = 92.0
sd.angle = math.radians(2.0)
so = bpy.data.objects.new("t_sun", sd)
so.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))
K.link(so)

vol = bpy.data.materials.new("t_vol")
vol.use_nodes = True
nt = vol.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
o = nt.nodes.new("ShaderNodeOutputMaterial")
pv = nt.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.0022
pv.inputs["Anisotropy"].default_value = 0.40
pv.inputs["Color"].default_value = (0.92, 0.93, 0.97, 1.0)
nt.links.new(pv.outputs["Volume"], o.inputs["Volume"])
w = bpy.data.worlds.new("t_w")
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
bg.inputs[1].default_value = 0.10
sc.world = w

cam = INT._cam("sppcam", (8.8, 0.0, 1.72), (-11.70, 0.0, 3.30), 37.0)
H.render_to(INT.OUT + r"\p1_SPP_%d.png" % SPP, cam)
print("SPP", SPP, "done")
