"""Is EEVEE still producing real pixels on this machine?

Renders the factory default scene (cube, camera, light) with EEVEE at two
exposures and reports the mean of each frame.  A working engine moves the mean
when the exposure moves; a broken one returns the identical frame.

    python look/export_run.py eevee_health 300 LIGHT -- -b --factory-startup \
        --python look/_eevee_health.py
"""
import os
import sys

import bpy

OUT = r"E:\My World\Blender\renders\kingdom\look"


def mean_of(path):
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    n = max(1, len(px) // 4)
    s = 0.0
    for i in range(0, len(px), 4):
        s += px[i] + px[i + 1] + px[i + 2]
    bpy.data.images.remove(img)
    return s / (3.0 * n)


def main():
    sc = bpy.context.scene
    print("[health] engines:", [i.identifier for i in
                                bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items])
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 160
    sc.render.resolution_y = 90
    sc.render.resolution_percentage = 100
    try:
        sc.eevee.taa_render_samples = 8
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    sc.render.use_compositing = False

    rows = []
    for name, ev in (("lo", -7.0), ("hi", 0.0)):
        sc.view_settings.exposure = ev
        path = os.path.join(OUT, "_health_eevee_%s.png" % name)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        rows.append((name, ev, mean_of(path), os.path.getsize(path)))
        print("[health] %s exposure=%+.1f mean=%.4f bytes=%d"
              % (name, ev, rows[-1][2], rows[-1][3]), flush=True)

    # workbench as a control: same scene, obviously different engine
    sc.render.engine = "BLENDER_WORKBENCH"
    path = os.path.join(OUT, "_health_workbench.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    wb = mean_of(path)
    print("[health] workbench mean=%.4f" % wb, flush=True)

    spread = abs(rows[0][2] - rows[1][2])
    print("[health] VERDICT eevee_exposure_spread=%.4f workbench=%.4f" % (spread, wb))
    print("[health] %s" % ("EEVEE IS BROKEN (frame does not respond to exposure)"
                           if spread < 0.005 else "eevee responds normally"))


if __name__ == "__main__":
    main()
