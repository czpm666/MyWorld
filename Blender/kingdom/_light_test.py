"""_light_test.py - harness for hd_light.py.

    blender.exe -b capital_full.blend -P _light_test.py -- <cmd> [args]

Commands
    one <preset> <cam> [w h spp]     render one frame to renders/kingdom/_lt_*.png
    sheet <preset> [w h spp]         all six cameras for one preset
    all [w h spp]                    the full 6 x 6 matrix
    stats <path>...                  histogram of existing PNGs
    calib_bounce                     measure BOUNCE_W_PER_RATIO
"""
import os
import sys
import math
import json

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
from mathutils import Vector

OUT = r"E:\My World\Blender\renders\kingdom"

import hd_light as L


def argv_after_ddash():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def _args(args):
    preset = args[0]
    cam = args[1]
    w = int(args[2]) if len(args) > 2 else 800
    h = int(args[3]) if len(args) > 3 else 450
    spp = int(args[4]) if len(args) > 4 else 64
    return preset, cam, (w, h), spp


def cmd_one(args):
    preset, cam, res, spp = _args(args)
    path = os.path.join(OUT, "_lt_%s_%s.png" % (preset, cam))
    L.shot(preset, cam, path, res=res, samples=spp)
    print("STATS", json.dumps(L.image_stats(path)), flush=True)
    return path


def cmd_sheet(args):
    preset = args[0]
    w = int(args[1]) if len(args) > 1 else 800
    h = int(args[2]) if len(args) > 2 else 450
    spp = int(args[3]) if len(args) > 3 else 48
    for cam in L.CAMERAS:
        path = os.path.join(OUT, "_lt_%s_%s.png" % (preset, cam))
        L.shot(preset, cam, path, res=(w, h), samples=spp)
        print("STATS", json.dumps(L.image_stats(path)), flush=True)


def cmd_all(args):
    w = int(args[0]) if len(args) > 0 else 1600
    h = int(args[1]) if len(args) > 1 else 900
    spp = int(args[2]) if len(args) > 2 else 192
    for preset in L.PRESETS:
        for cam in L.CAMERAS:
            path = os.path.join(OUT, "light_%s_%s.png" % (preset, cam))
            if os.path.exists(path) and "--skip" in args:
                continue
            L.shot(preset, cam, path, res=(w, h), samples=spp)
            print("STATS", json.dumps(L.image_stats(path)), flush=True)


def cmd_stats(args):
    for p in args:
        print("STATS", json.dumps(L.image_stats(p)), flush=True)


def cmd_calib(args):
    """Measure the bounce card: irradiance on a vertical white card from the sky
    alone vs from the bounce card alone, at sky_strength = 1.0."""
    import numpy as np
    sc = bpy.context.scene
    # a neutral card standing on the street, facing +X, 4 m tall
    for ob in [o for o in bpy.data.objects if o.name.startswith("CALIB_")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(60.0, 60.0, 3.0),
                                     rotation=(math.radians(90), 0, math.radians(90)))
    card = bpy.context.object
    card.name = "CALIB_Card"
    m = bpy.data.materials.new("CALIB_White")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
            n.inputs["Roughness"].default_value = 0.9
    card.data.materials.append(m)
    # camera in front of it
    cd = bpy.data.cameras.new("CALIB_Cam")
    co = bpy.data.objects.new("CALIB_Cam", cd)
    sc.collection.objects.link(co)
    co.location = (68.0, 60.0, 3.0)
    co.rotation_euler = (math.radians(90), 0, math.radians(90))
    sc.camera = co
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ("OPTIX", "CUDA")
    except Exception:  # noqa: BLE001
        pass
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 96, 96
    sc.render.image_settings.file_format = "PNG"

    def mean_of(tag):
        p = os.path.join(OUT, "_lt_calib_%s.png" % tag)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(p, check_existing=False)
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(h, w, 4)[:, :, :3]
        bpy.data.images.remove(img)
        # only the middle of the card
        c = a[h // 4:3 * h // 4, w // 4:3 * w // 4]
        return float(c.mean())

    # sky only
    L.sky("morning_town", 40.0, 110.0)
    for ob in [o for o in bpy.data.objects if o.name.startswith(L._TAG + "Bounce")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()
    sky_mean = mean_of("sky")
    # bounce only
    for ob in [o for o in bpy.data.objects if o.name.startswith(L._TAG + "Sun")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    w = sc.world
    if w and w.use_nodes:
        for n in w.node_tree.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value = 0.0
    L.bounce("morning_town")
    # force the calibration wattage to 1.0 ratio units
    bd = bpy.data.objects.get(L._TAG + "Bounce")
    bd.data.energy = L.BOUNCE_W_PER_RATIO * 1.0 * 1.0
    bpy.context.view_layer.update()
    b_mean = mean_of("bounce")
    print("CALIB sky=%.5f bounce=%.5f  ratio_per_unit=%.5f" % (sky_mean, b_mean,
                                                               b_mean / max(1e-9, sky_mean)),
          flush=True)
    print("CALIB recommended BOUNCE_W_PER_RATIO = %.4g"
          % (L.BOUNCE_W_PER_RATIO * sky_mean / max(1e-9, b_mean)), flush=True)


def cmd_dbg(args):
    """Bisect a black frame: world / sun / haze / bounce, one at a time."""
    import numpy as np
    sc = bpy.context.scene
    L.apply("morning_town", None, 32.0, 112.0)
    L.camera("main_street")
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.cycles.samples = 16
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.render.use_compositing = False
    except Exception:  # noqa: BLE001
        pass

    w = sc.world
    print("  world:", w.name if w else None, "use_nodes", getattr(w, "use_nodes", None),
          flush=True)
    if w and w.use_nodes:
        for n in w.node_tree.nodes:
            print("   world node", n.bl_idname, n.name, flush=True)
        for lk in w.node_tree.links:
            print("   world link %s.%s -> %s.%s"
                  % (lk.from_node.name, lk.from_socket.name,
                     lk.to_node.name, lk.to_socket.name), flush=True)

    def grab(tag):
        p = os.path.join(OUT, "_lt_dbg_%s.png" % tag)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(p, check_existing=False)
        ww, hh = img.size
        buf = np.empty(ww * hh * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(hh, ww, 4)[:, :, :3]
        bpy.data.images.remove(img)
        print("DBG %-14s mean=%.4f max=%.4f" % (tag, float(a.mean()), float(a.max())),
              flush=True)

    def drop(prefix):
        for ob in [o for o in bpy.data.objects if o.name.startswith(prefix)]:
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.context.view_layer.update()

    drop(L._TAG + "Haze")
    drop(L._TAG + "Bounce")
    grab("world_only")
    L.sun("morning_town", 32.0, 112.0)
    grab("world_sun")
    L.bounce("morning_town")
    grab("world_sun_bnc")
    L.haze("morning_town", center=(51.0, 51.0), mul=1.0, extent=2600.0)
    grab("all")
    print("  world strength:", flush=True)
    if w and w.use_nodes:
        for n in w.node_tree.nodes:
            if n.type == "BACKGROUND":
                print("   bg strength", n.inputs["Strength"].default_value,
                      "color", tuple(n.inputs["Color"].default_value), flush=True)


def main():
    args = argv_after_ddash()
    cmd = args[0] if args else "stats"
    rest = args[1:]
    if cmd == "one":
        cmd_one(rest)
    elif cmd == "sheet":
        cmd_sheet(rest)
    elif cmd == "all":
        cmd_all(rest)
    elif cmd == "stats":
        cmd_stats(rest)
    elif cmd == "calib_bounce":
        cmd_calib(rest)
    elif cmd == "dbg":
        cmd_dbg(rest)


if __name__ == "__main__":
    main()
