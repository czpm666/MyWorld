"""
Bake an averaged albedo colour per material.

Each material's procedural Base-Colour network is re-plugged into an Emission
shader and rendered as a flat tile of a single contact sheet (ONE Cycles render
for all materials).  The mean of each tile is the representative linear albedo.

  blender -b --factory-startup --python bake_palette.py -- \
      --blend <capital_v23.blend> --out <dir>/palette.json [--tile 64] [--show]

Writes { material_name : [r, g, b, roughness, metallic] }  (LINEAR rgb)
"""
import bpy, sys, os, json, time
import numpy as np

T0 = time.time()
def log(*a):
    print("[PAL %6.1fs]" % (time.time() - T0), *a); sys.stdout.flush()

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d

BLEND = arg("--blend")
OUT   = arg("--out")
SHOW  = "--show" in argv
TS    = int(arg("--tile", "56"))

bpy.ops.wm.open_mainfile(filepath=BLEND)
log("opened blend, materials:", len(bpy.data.materials))

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 0
scene.cycles.use_adaptive_sampling = False
scene.cycles.device = 'CPU'
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '32'
scene.render.image_settings.exr_codec = 'NONE'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

w = scene.world or bpy.data.worlds.new("PalWorld")
scene.world = w
w.use_nodes = True
for n in w.node_tree.nodes:
    if n.type == 'BACKGROUND':
        n.inputs[0].default_value = (0, 0, 0, 1)
        n.inputs[1].default_value = 0.0

# ---------------------------------------------------------------- emission override
def principled_of(nt):
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None

def out_node(nt):
    act = None
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            if n.is_active_output:
                return n
            act = act or n
    return act

mats = [m for m in bpy.data.materials if m.name and m.node_tree]
restore = []
for m in mats:
    nt = m.node_tree
    bsdf = principled_of(nt)
    on = out_node(nt)
    if on is None:
        continue
    surf = on.inputs.get("Surface")
    prev = surf.links[0].from_socket if surf.is_linked else None
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "__pal_em"
    em.inputs["Strength"].default_value = 1.0
    src = None
    if bsdf is not None:
        bc = bsdf.inputs.get("Base Color")
        if bc is not None and bc.is_linked:
            src = bc.links[0].from_socket
        elif bc is not None:
            em.inputs["Color"].default_value = bc.default_value
    elif prev is not None:
        src = prev
    if src is not None:
        nt.links.new(src, em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (0.7, 0.7, 0.7, 1)
    nt.links.new(em.outputs[0], surf)
    restore.append((m, nt, em, surf, prev))
log("emission overrides:", len(restore))

# ---------------------------------------------------------------- contact sheet
COLS = 16
rows = (len(mats) + COLS - 1) // COLS
SPACING = 1.25
HW = COLS * SPACING
HH = rows * SPACING
H  = 0.5 * SPACING * 0.98

verts, faces = [], []
for i, m in enumerate(mats):
    col, row = i % COLS, i // COLS
    cx = -HW / 2 + SPACING * (col + 0.5)
    cz =  HH / 2 - SPACING * (row + 0.5)
    b = len(verts)
    verts += [(cx - H, 0.0, cz - H), (cx + H, 0.0, cz - H),
              (cx + H, 0.0, cz + H), (cx - H, 0.0, cz + H)]
    faces.append((b, b + 1, b + 2, b + 3))

me = bpy.data.meshes.new("PalSheet")
me.from_pydata(verts, [], faces)
me.update()
for i, m in enumerate(mats):
    me.materials.append(m)
for i, p in enumerate(me.polygons):
    p.material_index = min(i, len(me.materials) - 1)
sheet = bpy.data.objects.new("PalSheet", me)
scene.collection.objects.link(sheet)

cam_data = bpy.data.cameras.new("PalCam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = max(HW, HH)
cam_data.clip_start = 0.1
cam_data.clip_end = 100.0
cam = bpy.data.objects.new("PalCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0, -6, 0)
cam.rotation_euler = (1.5707963, 0, 0)
scene.camera = cam

scene.render.resolution_x = COLS * TS
scene.render.resolution_y = rows * TS
scene.render.resolution_percentage = 100
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
exr = os.path.join(os.path.dirname(OUT) or ".", "_palsheet.exr")
scene.render.filepath = exr
log("rendering contact sheet %dx%d ..." % (scene.render.resolution_x, scene.render.resolution_y))
bpy.ops.render.render(write_still=True)

img = bpy.data.images.load(exr, check_existing=False)
px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
bpy.data.images.remove(img)
log("render read", px.shape)

RX, RY = scene.render.resolution_x, scene.render.resolution_y
res = {}
for i, m in enumerate(mats):
    col, row = i % COLS, i // COLS
    # world -> pixel
    cx = -HW / 2 + SPACING * (col + 0.5)
    cz =  HH / 2 - SPACING * (row + 0.5)
    fx = (cx + HW / 2) / HW
    fy = (cz + HH / 2) / HH
    x0 = int((fx - 0.30 / COLS) * RX); x1 = int((fx + 0.30 / COLS) * RX) + 1
    y0 = int((fy - 0.30 / rows) * RY); y1 = int((fy + 0.30 / rows) * RY) + 1
    x0, x1 = max(0, x0), min(RX, x1)
    y0, y1 = max(0, y0), min(RY, y1)
    tile = px[y0:y1, x0:x1, :3]
    c = tile.reshape(-1, 3).mean(axis=0) if tile.size else np.array([0.7, 0.7, 0.7], np.float32)
    nt = m.node_tree
    rough, metal = 0.6, 0.0
    b = principled_of(nt) if nt else None
    if b:
        ri = b.inputs.get("Roughness")
        if ri is not None and not ri.is_linked:
            rough = float(ri.default_value)
        mi = b.inputs.get("Metallic")
        if mi is not None and not mi.is_linked:
            metal = float(mi.default_value)
    res[m.name] = [round(float(c[0]), 4), round(float(c[1]), 4), round(float(c[2]), 4),
                   round(rough, 3), round(metal, 3)]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=0)
log("wrote", OUT, "materials:", len(res))
for k in sorted(res)[:24]:
    log("   %-26s %s" % (k, res[k][:3]))

if SHOW:
    sheet_img = os.path.join(os.path.dirname(OUT) or ".", "palsheet.png")
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = sheet_img
    bpy.ops.render.render(write_still=True)
    log("sheet png ->", sheet_img)
try:
    os.remove(exr)
except Exception:
    pass
