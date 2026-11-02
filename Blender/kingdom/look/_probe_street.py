"""Isolated top-down of the street ribbon, to check it is actually where it claims."""
import bpy, sys, math, os, time

root = r"E:\My World"
sys.path.insert(0, os.path.join(root, "Blender"))
sys.path.insert(0, os.path.join(root, "Blender", "kingdom"))


def arg(k, d=None):
    a = sys.argv
    return a[a.index(k) + 1] if k in a else d


cx, cy = 0.0, 0.0
_spot = arg("--spot", "0,0")
if _spot:
    _a, _b = _spot.split(",")
    cx, cy = float(_a), float(_b)
size = float(arg("--size", "150"))
out = arg("--out", r"E:\My World\Blender\renders\kingdom\look\_locate.png")
only = arg("--only", "")  # substring filter, keep only matching objects
hide = arg("--hide", "")  # substring filter, hide matching objects

if hide:
    for o in bpy.data.objects:
        if o.type == "MESH" and hide in o.name:
            o.hide_render = True
    print("[probe] hidden", sum(1 for o in bpy.data.objects if o.hide_render), "objects matching", hide, flush=True)

if arg("--flat", ""):
    # flat emissive: silhouettes only, so a wrong winding cannot hide geometry
    m = bpy.data.materials.new("FLAT")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (0.95, 0.55, 0.12, 1.0)
    em.inputs[1].default_value = 1.0
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], outn.inputs[0])
    n = 0
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render:
            o.data.materials.clear()
            o.data.materials.append(m)
            n += 1
    print("[probe] flattened", n, "objects", flush=True)

for name in ("streets_bed", "streets_gutter"):
    ob = bpy.data.objects.get(name)
    if ob is None:
        print("[probe] MISSING", name, flush=True)
        continue
    print("[probe] %-16s faces=%d verts=%d" % (name, len(ob.data.polygons), len(ob.data.vertices)), flush=True)
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    print("[probe]   x %.1f..%.1f  y %.1f..%.1f  z %.3f..%.3f  origin %s" % (
        min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), tuple(round(c, 2) for c in ob.location)), flush=True)

blk = [o for o in bpy.data.objects if o.name.startswith("blk_")]
print("[probe] block slabs", len(blk), flush=True)
if blk:
    zs = set()
    for o in blk[:400]:
        for v in o.data.vertices:
            zs.add(round(v.co.z, 3))
    print("[probe]   slab z values", sorted(zs)[:6], flush=True)

if only:
    keep = [o for o in bpy.data.objects if o.type == "MESH" and only in o.name]
    print("[probe] only", len(keep), "objects", flush=True)
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in keep:
            o.hide_render = True

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
sc.camera = cam

sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 3.0
sun = bpy.data.objects.new("sun", sun_data)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(40), 0.0, math.radians(30))

sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 900
sc.render.resolution_y = 900
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 8
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = out
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0

w = sc.world or bpy.data.worlds.new("W")
sc.world = w
bg = w.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
    bg.inputs[1].default_value = 1.0

t0 = time.time()
bpy.ops.render.render(write_still=True)
print("[probe] %.1f s -> %s" % (time.time() - t0, out), flush=True)
print("PROBE_DONE", flush=True)
