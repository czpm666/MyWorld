"""_diag2.py - is the street camera position the problem?"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
import numpy as np
from mathutils import Vector

OUT = r"E:\My World\Blender\renders\kingdom"
import hd_light as L


def shot_stats(tag):
    p = os.path.join(OUT, "_diag2_%s.png" % tag)
    sc = bpy.context.scene
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)
    bpy.data.images.remove(img)
    rgb = a[:, :, :3]
    print("D2 %-18s mean=%.4f max=%.4f  %dKB"
          % (tag, float(rgb.mean()), float(rgb.max()),
             os.path.getsize(p) // 1024), flush=True)


def manual_cam(loc, look, lens=28.0):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("MC")
    cd.lens = lens
    cd.clip_start = 0.08
    cd.clip_end = 9000
    co = bpy.data.objects.new("MC", cd)
    sc.collection.objects.link(co)
    co.location = Vector(loc)
    d = Vector(look) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    bpy.context.view_layer.update()
    print("D2 cam matrix", [round(v, 2) for v in co.matrix_world.translation],
          "rot", [round(math.degrees(v), 1) for v in co.rotation_euler], flush=True)
    return co


def main():
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.render.image_settings.file_format = "PNG"
    sc.render.use_compositing = False
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    sc.cycles.samples = 12
    sc.cycles.use_denoising = False
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ("OPTIX", "CUDA")
    except Exception:  # noqa: BLE001
        pass

    # 1. manual camera at the street position, no hd_light at all
    manual_cam((51, 51, 1.7), (14, 72, 3), 28)
    shot_stats("manual_street")
    # 2. same but 3 m higher
    manual_cam((51, 51, 6.0), (14, 72, 3), 28)
    shot_stats("manual_street_up")
    # 3. hd_light camera object
    L.camera("main_street")
    c = sc.camera
    print("D2 hd cam", c.name, "in view layer",
          c.name in [o.name for o in bpy.context.view_layer.objects],
          "hide_render", c.hide_render, "hide_viewport", c.hide_viewport, flush=True)
    print("D2 hd matrix", [round(v, 2) for v in c.matrix_world.translation],
          "rot", [round(math.degrees(v), 1) for v in c.rotation_euler], flush=True)
    shot_stats("hd_cam")
    # 4. hd camera raised
    c.location.z = 6.0
    bpy.context.view_layer.update()
    shot_stats("hd_cam_up")
    # 5. what does the ray hit?  cast from the street position
    dg = bpy.context.evaluated_depsgraph_get()
    for dz in (1.7, 6.0, 20.0):
        hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, Vector((51, 51, dz)),
                                                  Vector((-37, 21, 1.3)).normalized())
        print("D2 ray z=%.1f hit=%s %s dist=%.2f" % (
            dz, hit, ob.name if ob else None,
            (loc - Vector((51, 51, dz))).length if hit else -1), flush=True)


main()
