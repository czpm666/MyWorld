"""Flat clay render: separates shading bugs from geometry overlap."""
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

clay = bpy.data.materials.new("clay")
clay.use_nodes = True
bs = clay.node_tree.nodes["Principled BSDF"]
bs.inputs["Base Color"].default_value = (0.42, 0.40, 0.37, 1.0)
bs.inputs["Roughness"].default_value = 0.62
for ob in P:
    if ob is not None and ob.type == "MESH":
        ob.data.materials.clear()
        ob.data.materials.append(clay)

H.setup_engine(samples=8, res=(480, 270))
sc = bpy.context.scene
sd = bpy.data.lights.new("t_sun", "SUN")
sd.energy = 3.0
so = bpy.data.objects.new("t_sun", sd)
so.rotation_euler = (math.radians(50.0), 0.0, math.radians(160.0))
K.link(so)
sc.view_settings.exposure = 0.55

cam = INT._cam("claycam", (8.8, 0.0, 1.72), (-11.70, 0.0, 3.30), 37.0)
H.render_to(INT.OUT + r"\p1_CLA_axis.png", cam)
cam2 = INT._cam("claycam2", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0)
H.render_to(INT.OUT + r"\p1_CLA_throne.png", cam2)
print("CLAY done")
