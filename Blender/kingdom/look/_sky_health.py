"""Does hd_sky (rewritten 11:28) blow the frame out?

ROCK reported that since the rewrite EEVEE returns a near-white frame from every
camera and every exposure -- identical sha256 at -2.2 and -7.0 EV, which is the
signature of something overwriting the exposure (or of a frame that is already
saturated past any toe the view transform could recover).

This renders the factory cube with hd_sky applied, then again with only the
dome removed, and reports the mean of each.  A working sky leaves the cube
visible; a broken one returns a flat bright field.

    python look/export_run.py sky_health 400 LIGHT -- -b --factory-startup \
        --python look/_sky_health.py
"""
import hashlib
import os
import sys

import bpy

sys.path.insert(0, r"E:\My World\Blender\kingdom")
OUT = r"E:\My World\Blender\renders\kingdom\look"


def mean_and_hash(path):
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    n = max(1, len(px) // 4)
    s = 0.0
    for i in range(0, len(px), 4):
        s += px[i] + px[i + 1] + px[i + 2]
    bpy.data.images.remove(img)
    with open(path, "rb") as fh:
        h = hashlib.sha256(fh.read()).hexdigest()[:12]
    return s / (3.0 * n), h


def render(sc, tag, exposure):
    sc.view_settings.exposure = exposure
    path = os.path.join(OUT, "_skyhealth_%s.png" % tag)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    m, h = mean_and_hash(path)
    print("[skyhealth] %-22s ev=%+.1f mean=%.4f sha=%s" % (tag, exposure, m, h),
          flush=True)
    return m, h


def main():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 200
    sc.render.resolution_y = 112
    sc.render.resolution_percentage = 100
    sc.render.use_compositing = False
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = 8
    except Exception:
        pass

    print("[skyhealth] baseline (no hd_sky)", flush=True)
    a = render(sc, "a_baseline_hi", 0.0)
    b = render(sc, "a_baseline_lo", -7.0)
    print("[skyhealth] baseline spread=%.4f" % abs(a[0] - b[0]), flush=True)

    import hd_sky
    names = []
    try:
        hd_sky.apply_all(sc, "morning_town")
    except Exception as exc:
        print("[skyhealth] apply_all raised: %r" % (exc,), flush=True)
    print("[skyhealth] scene exposure after apply_all = %+0.2f"
          % sc.view_settings.exposure, flush=True)
    print("[skyhealth] world=%r frames=%d objects=%d"
          % (sc.world.name if sc.world else None, sc.frame_end,
             len(bpy.data.objects)), flush=True)
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            names.append((ob.name, len(ob.data.polygons)))
    names.sort(key=lambda x: -x[1])
    print("[skyhealth] biggest meshes: %s" % (names[:4],), flush=True)

    c = render(sc, "b_sky_hi", 0.0)
    d = render(sc, "b_sky_lo", -7.0)
    print("[skyhealth] with-sky spread=%.4f  identical=%s"
          % (abs(c[0] - d[0]), c[1] == d[1]), flush=True)

    # now hide the biggest mesh (the dome) and re-render
    big = None
    for ob in bpy.data.objects:
        if ob.type == "MESH" and (big is None or len(ob.data.polygons)
                                  > len(big.data.polygons)):
            if len(ob.data.polygons) > 32:
                pass
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name != "Cube" and "Cube" not in ob.name:
            ob.hide_render = True
    e = render(sc, "c_nodome_hi", 0.0)
    print("[skyhealth] dome hidden mean=%.4f (cube visible = %s)"
          % (e[0], "yes" if 0.02 < e[0] < 0.95 else "NO"), flush=True)

    print("[skyhealth] VERDICT baseline_ok=%s sky_ok=%s"
          % (abs(a[0] - b[0]) > 0.01, abs(c[0] - d[0]) > 0.01), flush=True)


if __name__ == "__main__":
    main()
