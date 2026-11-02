import bpy
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=r"E:\My World\Blender\renders\kingdom\capital_full.blend")

import sys
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import kcommon as KC

KC.clear_lights_cameras()
cam = KC.setup_camera((16.0, -31.0, 4.2), (0.0, 20.0, 11.0), 28.0)
bpy.context.view_layer.update()

dg = bpy.context.evaluated_depsgraph_get()
sx, sy = 1600, 900
for px, py in ((515, 140), (520, 145), (505, 130)):
    u = (px + 0.5) / sx * 2.0 - 1.0
    v = 1.0 - (py + 0.5) / sy * 2.0
    # camera-space ray through the sensor, using the camera's own matrix
    fr = cam.data.view_frame(scene=bpy.context.scene)
    tr, br, bl, tl = fr
    p = (bl + (br - bl) * ((u + 1) * 0.5)) + ((tl - bl) * ((v + 1) * 0.5))
    d = (cam.matrix_world.to_3x3() @ p).normalized()
    o = cam.matrix_world.translation
    hit, loc, nor, idx, ob, mat = bpy.context.scene.ray_cast(dg, o, d)
    print("[ray] %d,%d hit=%s loc=%s mat=%s" %
          (px, py, ob.name if hit else None,
           tuple(round(c, 2) for c in loc) if hit else None,
           mat.name if hit and mat else None), flush=True)
