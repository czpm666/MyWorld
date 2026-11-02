"""look/house_lab.py - fixed-camera render harness for the hd_houses rework.

One row of 12 houses (all 8 kinds, 9 m apart), the real game lighting and the
real game camera, so every judgement is made from the frame the player sees.

    blender -b --factory-startup --python look/house_lab.py -- new all
    blender -b --factory-startup --python look/house_lab.py -- old all
    blender -b --factory-startup --python look/house_lab.py -- new hero,roof

`old` swaps in the frozen baseline module (_hu_old_houses.py) and writes
look/hu_old_*.png; `new` writes look/hu_new_*.png.  Same geometry slots, same
rng seed, same light, same cameras -> a true before/after.

Game camera facts (hard requirement, from the brief):
    pitch 52 deg, distance 34 m, vertical FOV 30 deg.
    At 960x540 with a 36 mm sensor, 30 deg vertical is lens 37.8 mm.

Output: E:\\My World\\Blender\\renders\\kingdom\\look\\hu_<src>_<shot>.png
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
LENS_PLAYER = 37.8                 # 30 deg vertical FOV, 960x540, 36 mm sensor
RES = (960, 540)
SAMPLES = 32
STEP = 9.0

# The row.  Every kind appears, widths/depths/floors/frontages are fixed so the
# old and new modules are compared on identical footprints, and `variant` walks
# the 8 palettes capital_hd_glue.house_mats() actually uses in the city.
ROW = [
    # kind        w    d    floors frontage variant
    ("timber",    7.2,  9.0, 2, "eaves", 0),
    ("timber",    6.6,  8.6, 2, "gable", 4),
    ("stone",     7.6,  9.2, 2, "eaves", 1),
    ("craft",     6.8,  8.8, 2, "eaves", 5),
    ("shop",      7.4,  9.0, 2, "eaves", 2),
    ("inn",       8.2, 10.0, 3, "gable", 3),
    ("manor",     8.6, 10.4, 2, "eaves", 7),
    ("warehouse", 8.0, 11.0, 2, "eaves", 6),
    ("tower",     5.8,  5.8, 2, "eaves", 1),
    ("shop",      7.0,  8.8, 1, "eaves", 5),
    ("timber",    7.4,  9.2, 1, "eaves", 3),
    ("stone",     7.2,  9.0, 2, "gable", 0),
]


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def _mod(which):
    if which == "old":
        import _hu_old_houses as m
    else:
        import hd_houses as m
    return m


def _palette(mod, variant, back=False):
    """Exactly the city's palette path: make_mats -> weathering -> house_mats."""
    MAT = mod.make_mats()
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:                            # noqa: BLE001
        print("[lab] weathering skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    try:
        import capital_hd_glue as G
        return G.house_mats(MAT, variant, back)
    except Exception as exc:                            # noqa: BLE001
        print("[lab] house_mats skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
        return MAT


def build(mod, only_kind=None):
    H._clear()
    rng = random.Random(11)
    parts = []
    x0 = -(len(ROW) - 1) * STEP * 0.5
    per = []
    for i, (kind, w, d, fl, fr, var) in enumerate(ROW):
        if only_kind and kind != only_kind:
            continue
        MAT = _palette(mod, var)
        hp = mod.house(MAT, rng, kind=kind, w=w, d=d, floors=fl, frontage=fr)
        hp = H.apply(hp, Ts(x0 + i * STEP, 0, 0))
        n_polys = sum(len(o.data.polygons) for o in hp
                      if o is not None and o.type == "MESH")
        per.append((kind, w, d, fl, var, len(hp), n_polys, H.tri_count(hp)))
        parts += hp
    return parts, per, x0


def report(per, parts):
    tot = H.tri_count(parts)
    print("[lab] --- per house (base mesh, bevel modifiers NOT evaluated) ---",
          flush=True)
    for (kind, w, d, fl, var, nob, npoly, ntri) in per:
        print("  %-9s w=%.1f d=%.1f f=%d v=%d  objs=%3d polys=%4d tris=%5d"
              % (kind, w, d, fl, var, nob, npoly, ntri), flush=True)
    if per:
        print("[lab] mean tris/house = %.0f  mean polys = %.0f"
              % (tot / float(len(per)),
                 sum(p[6] for p in per) / float(len(per))), flush=True)


def eval_tris(parts):
    """Honest count: bevel / solidify modifiers applied."""
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


# --------------------------------------------------------------------------
# cameras
# --------------------------------------------------------------------------
def _aim(target, dist, pitch_deg):
    a = math.radians(pitch_deg)
    return (target[0], target[1] + dist * math.cos(a),
            target[2] + dist * math.sin(a))


def shots(x0):
    def at(i):
        return x0 + i * STEP

    hero_t = (at(4.6), 0.0, 4.6)
    hero2_t = (at(7.8), 0.0, 4.6)
    return [
        # the game camera: what the player actually looks at
        ("hero", _aim(hero_t, 34.0, 52.0), hero_t, LENS_PLAYER),
        ("hero2", _aim(hero2_t, 34.0, 52.0), hero2_t, LENS_PLAYER),
        # roof reading at the game pitch, closer
        ("roof", _aim((at(5.0), 0.0, 8.4), 18.0, 52.0),
         (at(5.0), 0.0, 8.4), LENS_PLAYER),
        # 1.72 m eye level, standing in the street
        ("eye", (at(4.6) + 1.0, 9.4, 1.72), (at(5.4), 0.0, 3.0), 30.0),
        # 3/4 close-up from outside the row, so nothing clips
        ("close", (at(4.5) + 4.5, 11.5, 5.4), (at(4.5), 0.0, 3.4), 35.0),
        # dormer / ridge inspection: above the eaves, close in
        ("dormer", (at(4.0) + 1.0, 7.0, 9.0), (at(4.0), 0.0, 7.6), 45.0),
        # whole row, read the type differentiation at a glance
        ("row", _aim((0.0, 0.0, 4.4), 62.0, 22.0), (0.0, 0.0, 4.4), 34.0),
    ]


def render(src, which, x0, only):
    os.makedirs(OUT, exist_ok=True)
    for (tag, loc, tgt, lens) in shots(x0):
        if only and tag not in only:
            continue
        cam = H.camera("cam_" + tag, loc, tgt, lens=lens)
        H.render_to(os.path.join(OUT, "hu_%s_%s.png" % (src, tag)), cam)
        bpy.data.objects.remove(cam, do_unlink=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    src = argv[0] if argv else "new"
    only = None
    if len(argv) > 1 and argv[1] != "all":
        only = set(argv[1].split(","))
    kind = None
    if "--kind" in argv:
        kind = argv[argv.index("--kind") + 1]

    global RES, SAMPLES
    if "--fast" in argv:
        RES = (480, 270)
        SAMPLES = 8

    mod = _mod(src)
    parts, per, x0 = build(mod, kind)
    lo, hi = H.bbox(parts)
    print("[lab] %s parts=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (src, len(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z), flush=True)
    report(per, parts)

    MAT = _palette(mod, 0)
    H.diorama_floor(MAT["stone"])
    sc = bpy.context.scene
    import hd_light as L
    import hd_sky as SKY
    L.apply("morning_town", sc, samples=SAMPLES, res=RES)
    SKY.world(sc, "morning_town")
    print("[lab] evaluated tris/house = %.0f (modifiers applied)"
          % (eval_tris(parts) / float(max(1, len(per)))), flush=True)
    render(src, src, x0, only)
    print("[lab] done", flush=True)


if __name__ == "__main__":
    main()
