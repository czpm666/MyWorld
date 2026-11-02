"""look/_fac_dbg.py - one-off: why does every facade render come out flat?

    python look/_fac_shot.py dbg --fast

Prints every light in the rig, then re-renders the hero camera with the haze
volume hidden, then with the whole hd_light rig removed, then with no world.
The frame stats after each step say which one is flooding the image.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_KING, os.path.dirname(_KING), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                              # noqa: E402
import hd_common as H                                   # noqa: E402
import facade_lab as F                                  # noqa: E402


def _shot(cam, tag, note):
    p = os.path.join(F.OUT, "fac_dbg_%s.png" % tag)
    H.render_to(p, cam)
    print("[dbg] %-22s -> %s" % (note, F._stats(p)), flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--fast" in argv:
        F.RES = (480, 270)
        F.SAMPLES = 8
    parts, per, lay = F.build(F._mod("old"))
    F.report(per, parts)
    H.diorama_floor(F._palette(F._mod("old"), 0)["stone"])
    sc = bpy.context.scene
    import hd_light as L
    L.apply("morning_town", sc, samples=F.SAMPLES, res=F.RES)
    cam = H.camera("cam_dbg", (0.0, 20.9, 31.4), (0.0, 0.0, 4.6),
                   lens=F.LENS_PLAYER)
    sc.camera = cam
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.render.use_compositing = False

    print("[dbg] --- lights ---", flush=True)
    for ob in bpy.data.objects:
        if ob.type == "LIGHT":
            d = ob.data
            print("[dbg] light %-14s %-6s E=%-10.4g size=%s loc=%s"
                  % (ob.name, d.type, d.energy,
                     round(getattr(d, "size", 0.0), 2),
                     tuple(round(v, 1) for v in ob.location)), flush=True)
    print("[dbg] --- materials of LIGHT_* meshes ---", flush=True)
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name.startswith("LIGHT"):
            print("[dbg] %s mats=%s dims=%s"
                  % (ob.name, [m.name for m in ob.data.materials],
                     tuple(round(v, 0) for v in ob.dimensions)), flush=True)

    _shot(cam, "a_asis", "as-is (std, no comp)")
    haz = bpy.data.objects.get("LIGHT_Haze")
    if haz:
        haz.hide_render = True
        _shot(cam, "b_nohaze", "haze hidden")
    for ob in [o for o in bpy.data.objects if o.name.startswith("LIGHT")]:
        ob.hide_render = True
    _shot(cam, "c_norig", "whole LIGHT_* rig hidden")
    sc.world = None
    _shot(cam, "d_noworld", "no world either")
    sc.world = bpy.data.worlds["World"] if "World" in bpy.data.worlds else sc.world
    if haz:
        haz.hide_render = False
    for ob in [o for o in bpy.data.objects if o.name.startswith("LIGHT")]:
        ob.hide_render = False
    # colour management: the rig's own exposure, one look at a time
    sc.view_settings.exposure = -2.55
    for look in ("None", "AgX - Base Contrast", "AgX - Punchy", "AgX - Medium High Contrast"):
        for vt in ("AgX", "Standard"):
            sc.view_settings.view_transform = vt
            try:
                sc.view_settings.look = look
            except Exception as exc:                    # noqa: BLE001
                print("[dbg] look %r refused: %s" % (look, exc), flush=True)
                continue
            _shot(cam, "e_%s_%s" % (vt, look.replace(" ", "_")),
                  "%s / %s / -2.55" % (vt, look))
    print("[dbg] done", flush=True)


if __name__ == "__main__":
    main()
