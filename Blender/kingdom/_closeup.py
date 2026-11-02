"""Close-up check renders from an existing variant .blend (no rebuild)."""
import bpy, os, sys, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
variant = argv[0] if argv else "port_a"
loc = tuple(float(v) for v in argv[1].split(",")) if len(argv) > 1 else (-16, 44, 13)
tgt = tuple(float(v) for v in argv[2].split(",")) if len(argv) > 2 else (-16, 14, 2)
lens = float(argv[3]) if len(argv) > 3 else 50.0
out = argv[4] if len(argv) > 4 else ""

B = r"E:\My World\Blender"
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, "kingdom", "%s.blend" % variant))
sc = bpy.context.scene
R = math.radians({"port_a": 0.0, "port_b": 90.0, "port_c": 180.0}[variant])
M = Vector((0, 0, 0))
cr, sr = math.cos(R), math.sin(R)
def rot(v):
    return Vector((v[0] * cr - v[1] * sr, v[0] * sr + v[1] * cr, v[2]))
cd = bpy.data.cameras.new("Chk")
cd.lens = lens
co = bpy.data.objects.new("Chk", cd)
bpy.context.collection.objects.link(co)
co.location = rot(loc)
co.rotation_euler = (rot(tgt) - rot(loc)).to_track_quat("-Z", "Y").to_euler()
sc.camera = co
sc.render.resolution_x, sc.render.resolution_y = 960, 540
path = out or os.path.join(B, "renders", "kingdom", "_check_%s.png" % variant)
sc.render.filepath = path
bpy.ops.render.render(write_still=True)
print("[chk] wrote", path)
