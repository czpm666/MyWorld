"""hd_weather_diag.py -- why is every weather frame after the first black?

Not part of the deliverable; a probe.  Run with

    blender -b --factory-startup --python hd_weather_diag.py

It renders the same town through several isolation variants (same state twice,
compositor off, fog object deleted) and prints the mean pixel of each frame, so
"black" can be attributed to a cause instead of guessed at.
"""
import os
import sys

KING = r"E:\My World\Blender\kingdom"
for p in (KING, os.path.dirname(KING), os.path.join(KING, "look")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy                                                  # noqa: E402
import hd_common as H                                       # noqa: E402
import hd_light as L                                        # noqa: E402
import render as R                                          # noqa: E402
import weather_lab as WL                                    # noqa: E402

TMP = r"E:\My World\Logs\wxdiag"
os.makedirs(TMP, exist_ok=True)
# NB: _town() calls H._clear() (read_factory_settings), which *replaces* the
# scene datablock -- so the scene must always be re-fetched, never cached.


def mean_of(path):
    im = bpy.data.images.load(path, check_existing=False)
    px = list(im.pixels[:])
    n = len(px) // 4
    v = sum(px[i * 4] + px[i * 4 + 1] + px[i * 4 + 2] for i in range(n)) / (3.0 * n)
    bpy.data.images.remove(im)
    return v


def shot(tag, cam):
    sc = bpy.context.scene
    path = os.path.join(TMP, tag + ".png")
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    lights = [o for o in bpy.data.objects if o.type == "LIGHT"]
    print("[diag] %-18s objects=%4d lights=%d world=%s comp=%s mean=%.4f"
          % (tag, len(bpy.data.objects), len(lights),
             sc.world.name if sc.world else None,
             "on" if getattr(sc, "compositing_node_group", None) else "off",
             mean_of(path)), flush=True)


parts, MAT, trees, n_houses = WL._town()
R.setup_engine("eevee", samples=6, res=(320, 180))
L.post("morning_town", bpy.context.scene)
print("[diag] engine", bpy.context.scene.render.engine, flush=True)

spec = WL._cam_specs()["wide"]


def one(name):
    cam = H.camera("wx_cam_%s" % name, spec["loc"], spec["look"], lens=spec["lens"])
    st = WL.cast(name, (parts, MAT, trees, n_houses), eye=spec["loc"])
    print("[diag] cast %-8s objs=%d" % (name, st["objects"]), flush=True)
    return cam


cam = one("clear")
shot("clear_a", cam)
bpy.data.objects.remove(cam, do_unlink=True)

cam = one("clear")
shot("clear_b", cam)                     # same state twice -> isolates "2nd call"
bpy.data.objects.remove(cam, do_unlink=True)

cam = one("hazy")
shot("hazy_on", cam)
bpy.context.scene.compositing_node_group = None         # test the grade chain
shot("hazy_nocomp", cam)
for ob in list(bpy.data.objects):
    if ob.name.startswith("WX_Fog"):
        print("[diag] removing", ob.name, flush=True)
        bpy.data.objects.remove(ob, do_unlink=True)
shot("hazy_nofog", cam)
print("[diag] done", flush=True)
