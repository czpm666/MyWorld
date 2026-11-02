"""_hu_shots.py - before/after render harness for the hd_houses rework.

Renders a FIXED set of cameras against either the frozen baseline module
(_hu_old_houses.py) or the live one (hd_houses.py), so old and new are judged
from identical geometry slots and identical light.

    blender -b --factory-startup --python _hu_shots.py -- new all
    blender -b --factory-startup --python _hu_shots.py -- old all

Player-camera facts (hard requirement): pitch 52 deg, distance 34 m,
vertical FOV 30 deg at 1280x720 -> 37.8 mm on a 36 mm sensor.  That is what
`hero` is; every other shot is a judgement close-up of one aspect.

Output: renders/kingdom/look/hu_<src>_<shot>.png
"""
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy

import hd_common as H
import medkit as K

Ts = K.T_at
OUT = r"E:\My World\Blender\renders\kingdom\look"
LENS_PLAYER = 37.8          # 30 deg vertical FOV, 1280x720, 36 mm sensor
RES = (1280, 720)
SAMPLES = 32

# street row used by hero / roof / facade / bay (all dimensions fixed, so the
# old and new modules are compared at exactly the same footprint)
STREET = [
    (-12.3, "timber", 7.4, 9.0, 2, "eaves"),
    (-4.1, "timber", 7.6, 9.2, 2, "eaves"),
    (4.1, "inn", 7.6, 9.2, 3, "eaves"),
    (12.3, "stone", 7.4, 9.0, 2, "gable"),
]


def _build(mod):
    H._clear()
    MAT = mod.make_mats()
    rng = random.Random(11)
    out = []
    for (x, kind, w, d, fl, fr) in STREET:
        out += H.apply(mod.house(MAT, rng, kind=kind, w=w, d=d, floors=fl, frontage=fr),
                       Ts(x, 0, 0))
    return out, MAT


def _build_types(mod):
    H._clear()
    MAT = mod.make_mats()
    return mod.build_set(MAT, random.Random(4)), MAT


def _aim(target, dist, pitch_deg):
    a = math.radians(pitch_deg)
    return (target[0], target[1] + dist * math.cos(a), target[2] + dist * math.sin(a))


def shots(src):
    """Fixed camera list: (tag, location, look_at, lens)."""
    if src == "types":
        return [
            ("types", _aim((13.0, 0.0, 5.0), 38.0, 30.0), (13.0, 0.0, 5.0), 50.0),
            ("types2", _aim((-6.0, 0.0, 4.5), 34.0, 34.0), (-6.0, 0.0, 4.5), 50.0),
        ]
    hero_t = (0.0, 0.0, 5.0)
    return [
        ("hero", _aim(hero_t, 34.0, 52.0), hero_t, LENS_PLAYER),
        ("roof", _aim((0.2, 0.0, 9.6), 16.0, 52.0), (0.2, 0.0, 9.6), 42.0),
        ("facade", _aim((-4.1, 0.6, 4.6), 21.0, 38.0), (-4.1, 0.6, 4.6), 42.0),
        ("bay", _aim((-4.1, 1.0, 2.6), 7.5, 26.0), (-4.1, 1.0, 2.6), 42.0),
        ("gable", _aim((12.3, 2.0, 8.0), 14.0, 44.0), (12.3, 2.0, 8.0), 42.0),
    ]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = argv[0] if argv else "new"
    group = argv[1] if len(argv) > 1 else "street"
    if which == "old":
        import _hu_old_houses as mod
    else:
        import hd_houses as mod

    if group == "types":
        parts, MAT = _build_types(mod)
        cam_src = "types"
    else:
        parts, MAT = _build(mod)
        cam_src = "street"

    lo, hi = H.bbox(parts)
    print("[hu] %s/%s parts=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (which, group, len(parts), H.tri_count(parts), lo.x, lo.y, lo.z,
             hi.x, hi.y, hi.z), flush=True)
    H.diorama_floor(MAT["stone"])
    H.setup_world(fill=2.1)
    H.setup_engine(samples=SAMPLES, res=RES)
    os.makedirs(OUT, exist_ok=True)
    for (tag, loc, tgt, lens) in shots(cam_src):
        cam = H.camera("cam_" + tag, loc, tgt, lens=lens)
        H.render_to(os.path.join(OUT, "hu_%s_%s.png" % (which, tag)), cam)
    print("[hu] done", flush=True)


if __name__ == "__main__":
    main()
