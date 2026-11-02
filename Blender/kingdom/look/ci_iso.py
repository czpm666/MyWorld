"""Same lights, two shading modes: is the leopard spot geometry or material?"""
import sys
import math

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy
import medkit as K
import hd_common as H
import hd_castle_int as INT

K.reset_scene()
M = INT.prep(INT.make_mats())
P = INT.build(K, M, origin=(0.0, 0.0), seed=3)
H.setup_engine(samples=48, res=(480, 270))
sc = bpy.context.scene
sc.view_settings.exposure = 0.22

sd = bpy.data.lights.new("t_sun", "SUN")
sd.energy = 260.0
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
nt.links.new(pv.outputs["Volume"], o.inputs["Volume"])
w = bpy.data.worlds.new("t_w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.10
sc.world = w

clay = bpy.data.materials.new("clay")
clay.use_nodes = True
bs = clay.node_tree.nodes["Principled BSDF"]
bs.inputs["Base Color"].default_value = (0.42, 0.40, 0.37, 1.0)
bs.inputs["Roughness"].default_value = 0.62

cam = INT._cam("isocam", (8.8, 0.0, 1.72), (-11.70, 0.0, 3.30), 37.0)
bpy.context.view_layer.material_override = clay
H.render_to(INT.OUT + r"\p1_ISO_clay.png", cam)
bpy.context.view_layer.material_override = None
H.render_to(INT.OUT + r"\p1_ISO_mat.png", cam)
print("ISO done")
