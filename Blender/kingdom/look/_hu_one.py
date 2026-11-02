"""look/_hu_one.py - single-house inspection bench.

One house at the origin, four guaranteed-clean cameras.  The row harness is
for "does the street read"; this one is for "is this part actually built".

    blender -b --factory-startup --python look/_hu_one.py -- shop
    blender -b --factory-startup --python look/_hu_one.py -- inn --hi
"""
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_KING, os.path.dirname(_KING), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                             # noqa: E402

import hd_common as H                                  # noqa: E402
import medkit as K                                     # noqa: E402

Ts = K.T_at
OUT = r"E:\My World\Blender\renders\kingdom\look"

SPEC = {
    "timber":    (7.2, 9.0, 2, "eaves", 0),
    "stone":     (7.6, 9.2, 2, "eaves", 1),
    "craft":     (6.8, 8.8, 2, "eaves", 5),
    "shop":      (7.4, 9.0, 2, "eaves", 2),
    "inn":       (8.2, 10.0, 3, "gable", 3),
    "manor":     (8.6, 10.4, 2, "eaves", 7),
    "warehouse": (8.0, 11.0, 2, "eaves", 6),
    "tower":     (5.8, 5.8, 2, "eaves", 1),
}


def palette(variant):
    import hd_houses as HOU
    MAT = HOU.make_mats()
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:                            # noqa: BLE001
        print("[one] weathering skipped: %s" % exc, flush=True)
    try:
        import capital_hd_glue as G
        return G.house_mats(MAT, variant, False)
    except Exception:                                   # noqa: BLE001
        return MAT


def _orbit(az, elev, dist, tgt=(0, 0, 3.2)):
    a = math.radians(az)
    e = math.radians(elev)
    return (tgt[0] + dist * math.cos(e) * math.sin(a),
            tgt[1] + dist * math.cos(e) * math.cos(a),
            tgt[2] + dist * math.sin(e))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kind = argv[0] if argv else "timber"
    hi = "--hi" in argv
    res = (960, 540) if hi else (480, 270)
    spp = 24 if hi else 8

    import hd_houses as HOU
    w, d, fl, fr, var = SPEC.get(kind, SPEC["timber"])
    H._clear()
    rng = random.Random(7)
    hp = HOU.house(palette(var), rng, kind=kind, w=w, d=d, floors=fl, frontage=fr)
    lo, hi2 = H.bbox(hp)
    print("[one] %s objs=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (kind, len(hp), H.tri_count(hp), lo.x, lo.y, lo.z, hi2.x, hi2.y, hi2.z),
          flush=True)

    H.diorama_floor(palette(var)["stone"])
    sc = bpy.context.scene
    import hd_light as L
    import hd_sky as SKY
    L.apply("morning_town", sc, samples=spp, res=res)
    SKY.world(sc, "morning_town")

    top = hi2.z
    tgt = (0.0, 0.0, top * 0.42)
    cams = [
        ("f34", _orbit(35, 24, max(14.0, top * 1.35), tgt), tgt, 40.0),
        ("side", _orbit(88, 20, max(13.0, top * 1.25), tgt), tgt, 40.0),
        ("game", _orbit(0, 52, 34.0, (0.0, 0.0, 4.6)), (0.0, 0.0, 4.6), 37.8),
        ("eye", (2.2, 10.5, 1.72), (0.0, 0.0, 2.6), 26.0),
    ]
    for tag, loc, t, lens in cams:
        if len(argv) > 1 and argv[1] in ("f34", "side", "game", "eye") \
                and argv[1] != tag:
            continue
        cam = H.camera("c_" + tag, loc, t, lens=lens)
        H.render_to(os.path.join(OUT, "hu1_%s_%s.png" % (kind, tag)), cam)
        bpy.data.objects.remove(cam, do_unlink=True)
    print("[one] done", flush=True)


if __name__ == "__main__":
    main()
