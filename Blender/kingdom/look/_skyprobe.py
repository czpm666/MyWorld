# _skyprobe.py -- look at the sky itself: world node graph dump + sky-only renders.
import bpy, sys, os, math, json
sys.path.insert(0, r"E:\My World\Blender")
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_light as L
import hd_atmosphere as A


def log(*a):
    print("[sky]", *a)
    sys.stdout.flush()


def dump_world(w, tag=""):
    log("--- world %s  use_nodes=%s" % (tag, w.use_nodes))
    if not w.use_nodes:
        return
    nt = w.node_tree
    for n in nt.nodes:
        vals = []
        for s in n.inputs:
            try:
                v = s.default_value
                if hasattr(v, "__len__"):
                    v = tuple(round(float(x), 3) for x in v)
                else:
                    v = round(float(v), 3)
                vals.append("%s=%s" % (s.name, v))
            except Exception:
                pass
        log("  node %-22s %-24s %s" % (n.name, n.bl_idname, " ".join(vals[:6])))
    for lk in nt.links:
        log("  link %s.%s -> %s.%s" % (lk.from_node.name, lk.from_socket.name,
                                       lk.to_node.name, lk.to_socket.name))


def cam_up(loc, lens=20.0):
    cd = bpy.data.cameras.new("skycam")
    cd.lens = lens
    cd.clip_end = 20000.0
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    co = bpy.data.objects.new("skycam", cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (math.radians(70.0), 0.0, math.radians(34.0))
    bpy.context.scene.camera = co
    return co


def render(tag, out):
    sc = bpy.context.scene
    sc.render.filepath = out
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    log("wrote", out)


sc = bpy.context.scene
log("engine", sc.render.engine, "exposure", sc.view_settings.exposure,
    "look", sc.view_settings.look, "view", sc.view_settings.view_transform)
log("objects", len(bpy.data.objects))
log("haze objs:", [o.name for o in bpy.data.objects if "aze" in o.name or "Atmo" in o.name])

rep = L.apply("morning_town", sc)
log("apply ok:", rep.get("ok"), "fail:", rep.get("fail"))
dump_world(sc.world, "morning_town")

log("eevee vol shadows", sc.eevee.use_volumetric_shadows,
    "tile", sc.eevee.volumetric_tile_size, "custom_range", sc.eevee.use_volume_custom_range)

log("mist", sc.world.mist_settings.start, sc.world.mist_settings.depth, sc.world.mist_settings.falloff)

sc.render.resolution_x = 960
sc.render.resolution_y = 540
sc.render.resolution_percentage = 100
sc.eevee.taa_render_samples = 16

out = r"E:\My World\Blender\renders\kingdom\look"
cam_up((900.0, -1150.0, 600.0))
render("sky_with_haze", os.path.join(out, "_sky_a.png"))

for o in list(bpy.data.objects):
    if "aze" in o.name or "Atmo" in o.name:
        log("hide", o.name)
        o.hide_render = True
render("sky_no_haze", os.path.join(out, "_sky_b.png"))

# also a shot with the world only, no geometry at all
for o in list(bpy.data.objects):
    if o.type == "MESH":
        o.hide_render = True
render("world_only", os.path.join(out, "_sky_c.png"))

for l in [l for l in bpy.data.lights]:
    log("light", l.name, l.type, round(l.energy, 2), tuple(round(x, 3) for x in l.color))
log("DONE")
