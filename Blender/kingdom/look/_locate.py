"""Top-down ortho snapshot of one spot, to see what a camera would be standing in."""
import bpy, sys, math, os, time

root = r"E:\My World"
sys.path.insert(0, os.path.join(root, "Blender"))
sys.path.insert(0, os.path.join(root, "Blender", "kingdom"))

import hd_light as L


def arg(k, d=None):
    a = sys.argv
    if k in a:
        return a[a.index(k) + 1]
    return d


cx, cy = 0.0, 0.0
_spot = arg("--spot", "0,0")
if _spot:
    _a, _b = _spot.split(",")
    cx, cy = float(_a), float(_b)
size = float(arg("--size", "120"))
out = arg("--out", r"E:\My World\Blender\renders\kingdom\look\_locate.png")

sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in {"LIGHT", "CAMERA"}:
        bpy.data.objects.remove(o, do_unlink=True)

cam_data = bpy.data.cameras.new("loc")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size
cam_data.clip_start = 1.0
cam_data.clip_end = 2000.0
cam = bpy.data.objects.new("loc", cam_data)
sc.collection.objects.link(cam)
cam.location = (cx, cy, 400.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
sc.camera = cam

sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 3.0
sun = bpy.data.objects.new("sun", sun_data)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(40), 0.0, math.radians(30))

sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 900
sc.render.resolution_y = 900
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 8
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = out
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0

# a flat world so the shot reads as a map, not a render
w = sc.world or bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
    bg.inputs[1].default_value = 1.0

t0 = time.time()
bpy.ops.render.render(write_still=True)
print("[locate] %.1f s -> %s" % (time.time() - t0, out), flush=True)
print("LOCATE_DONE", flush=True)
