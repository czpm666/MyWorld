"""_diag.py - why is the Cycles frame black?"""
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


def stats(tag):
    import numpy as np
    p = os.path.join(OUT, "_diag_%s.png" % tag)
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
    print("DIAG %-16s mean=%.4f max=%.4f alpha=%.3f size=%dKB"
          % (tag, float(rgb.mean()), float(rgb.max()), float(a[:, :, 3].mean()),
             os.path.getsize(p) // 1024), flush=True)


def main():
    sc = bpy.context.scene
    vl = bpy.context.view_layer
    print("DIAG engine", sc.render.engine, flush=True)
    print("DIAG scene.camera", sc.camera, flush=True)
    print("DIAG viewlayer", vl.name, "objects", len(vl.objects), flush=True)
    print("DIAG scene objects", len(sc.objects), flush=True)
    print("DIAG collections", [c.name for c in bpy.data.collections][:12], flush=True)
    print("DIAG render.use_sequencer", sc.render.use_sequencer,
          "use_compositing", sc.render.use_compositing, flush=True)
    print("DIAG res", sc.render.resolution_x, sc.render.resolution_y,
          sc.render.resolution_percentage, flush=True)
    print("DIAG camera dof", sc.camera.data.dof.use_dof if sc.camera else None, flush=True)

    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.use_compositing = False
    try:
        sc.render.use_sequencer = False
    except Exception:  # noqa: BLE001
        pass

    # a guaranteed camera: 700 m up, looking straight down
    cd = bpy.data.cameras.new("DiagCam")
    cd.lens = 24
    cd.clip_start = 0.1
    cd.clip_end = 9000
    co = bpy.data.objects.new("DiagCam", cd)
    sc.collection.objects.link(co)
    co.location = (0, 0, 700)
    co.rotation_euler = (0, 0, 0)
    sc.camera = co
    bpy.context.view_layer.update()

    # EEVEE first
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [
        e.identifier for e in
        bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    print("DIAG eevee id", sc.render.engine, flush=True)
    stats("eevee_top")

    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    stats("cycles_cpu_top")

    sc.cycles.device = "GPU"
    sc.cycles.samples = 8
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type in ("OPTIX", "CUDA")
        print("DIAG devices", [(d.name, d.type, d.use) for d in prefs.devices], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("DIAG gpu fail", exc, flush=True)
    stats("cycles_gpu_top")

    # world only, camera looking at the sky
    for ob in [o for o in bpy.data.objects if o.type in ("MESH", "LIGHT")]:
        ob.hide_render = True
    co.location = (0, 0, 300)
    co.rotation_euler = (math.radians(80), 0, 0)
    bpy.context.view_layer.update()
    sc.cycles.samples = 8
    stats("cycles_gpu_sky")


main()
