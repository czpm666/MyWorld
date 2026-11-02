"""Render quick orthographic/perspective debug views of an existing .blend."""
import bpy
import os
import sys
import math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
blend_path = argv[0]
out_dir = argv[1]
tag = argv[2] if len(argv) > 2 else "dbg"

bpy.ops.wm.open_mainfile(filepath=blend_path)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 900
sc.render.resolution_y = 600
sc.render.resolution_percentage = 100
try:
    sc.eevee.taa_render_samples = 16
except Exception:
    pass
sc.view_settings.view_transform = "AgX"

# make sure there is exactly one sun
for ob in [o for o in bpy.data.objects if o.type in ("LIGHT", "CAMERA")]:
    bpy.data.objects.remove(ob, do_unlink=True)
ld = bpy.data.lights.new("sun", "SUN")
ld.energy = 4.0
ld.angle = math.radians(4)
lo = bpy.data.objects.new("sun", ld)
sc.collection.objects.link(lo)
lo.rotation_euler = (math.radians(50), 0, math.radians(35))

if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.45, 0.58, 0.78, 1)
    bg.inputs[1].default_value = 1.0

cd = bpy.data.cameras.new("c")
co = bpy.data.objects.new("c", cd)
sc.collection.objects.link(co)
sc.camera = co


def shot(name, loc, look, ortho=None, lens=32.0):
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.type = "PERSP"
        cd.lens = lens
    co.location = Vector(loc)
    co.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(out_dir, "%s_%s.png" % (tag, name))
    bpy.ops.render.render(write_still=True)
    print("[dbg]", sc.render.filepath)


shot("top", (0, 0, 150), (0, 0, 0), ortho=126.0)
shot("fromA", (-58, -46, 44), (2, 4, 4))
shot("front", (-0.001, -110, 18), (0, 0, 6), lens=55.0)
shot("side", (-110, 0.001, 24), (0, 0, 6), lens=55.0)
shot("adit", (-10, 6, 12), (44, 4, 4), lens=45.0)
print("DBG_DONE")
