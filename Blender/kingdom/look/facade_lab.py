"""look/facade_lab.py - FACADE round 2 lab: a STREET JUNCTION, not a row.

Why this lab exists
-------------------
Round 1 (this file's first life) built a continuous terrace plus the terrace
BACKS, and every shot came back clean.  The city render still showed a pale
unbroken plane over 40 % of the street frame.  The reason the old lab could not
see it is the same reason the city produces it:

    `capital.py row_along()` lays houses along a polyline, and a radial street
    cuts a hole in the ring row.  At that hole the last house of the segment
    turns its FLANK (the d-long side wall) to the avenue - and the avenue is
    exactly where the game camera stands.  A flank seen from the street is not
    the facade the old lab ever photographed: it is 3 storeys of plaster with a
    window every 3 m, and at 26.8 m up / 21 m out it is the biggest single
    surface in the frame.

So this lab builds the junction itself:

    east terrace  front plane x = +7.0 (ROAD_HALF 4.6 + PAVE 2.4), faces -X
    west terrace  front plane x = -7.0, faces +X
    back row      the city's 7.4 m alley behind the east terrace, city pitch
    junction      the terraces START at y = -2, so both ends show a full flank
                  to a camera standing south of them in the cross street

A 12.6 m x 10 m flank 16 m from a 34 mm lens is ~74 % of the frame width.  That
is the 40 % wall, reproduced on demand.

Shots
    game    pitch 52 deg / 34 m / 30 deg vFOV, flank on the RIGHT  <- the bug
    eye     1.72 m, standing in the junction, flank on the RIGHT    <- the bug
    ends    1.72 m, 16 m out, face-on to that flank
    end52   the same flank at the contract camera
    close   3/4 from 8 m: sill / reveal / pipe / plinth legibility
    row     22 deg, 62 m: is the party-wall joint visible at all?

`--audit` also raycasts a 140x79 grid from each camera and prints the share of
the frame taken by each part class (flank / back / front / roof / ...), so
"40 % flat wall" becomes a number instead of an opinion.

Usage (never run blender directly - it must go through the lock):

    python look/export_run.py fac2a 900 LIGHT -- -b --factory-startup \
        --python look/facade_lab.py -- before all --fast
    ... edit hd_houses.py / hd_houses_parts.py ...
    python look/export_run.py fac2b 900 LIGHT -- -b --factory-startup \
        --python look/facade_lab.py -- after all

`--fast` = 480x270 / 8 spp.  The first positional is just the output label:
run it BEFORE the edit and again AFTER with the same label set, same seeds,
same light, same cameras, and the pair is a true before/after.
"""
import math
import os
import random
import sys
import time

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

# ---- street geometry: exactly row_along()'s numbers ----------------------
ROAD_HALF = 4.6                    # capital.py passes road_half 4.5-4.65
PAVE = 2.4                         # off = road_half + 2.4 + d*0.5
FRONT = ROAD_HALF + PAVE           # 7.0 : the front wall plane
ALLEY = 7.4                        # row_along back_row gap
Y0 = -2.0                          # where both terraces start (the junction)

# kind, w, d, floors, frontage.  The depth IS the width of the flank the camera
# sees, so it sets the size of the bug.  w is the plot frontage; houses ABUT
# here (party wall, no slot).
#
# House 0 - the one every flank camera is pointed at - is deliberately the
# CITY's case and not the brief's: capital.py row_along() places houses at
# depth_range=(6.0, 9.0), so the real street builds d = 6-9 m with 2 storeys,
# which gives the narrowest flank and the least window room.  Round 1's lab
# used 10-13 m, which is why the lab passed and the city did not.
E_TERRACE = [
    ("timber", 7.4, 8.6, 2, "eaves"),          # <- the city case: d 6-9 m, 2 fl
    ("timber", 7.4, 12.6, 3, "eaves"),         # <- the brief case: d 10-13 m
    ("stone",  8.2, 11.4, 2, "gable"),
    ("timber", 6.8, 13.0, 3, "eaves"),
    ("craft",  7.0, 11.0, 2, "eaves"),
    ("shop",   7.6, 12.2, 3, "gable"),
    ("timber", 6.6, 10.8, 2, "eaves"),
]
W_TERRACE = [
    ("stone",  7.8, 11.6, 3, "gable"),
    ("timber", 7.0, 12.4, 2, "eaves"),
    ("craft",  8.4, 12.0, 2, "eaves"),
    ("timber", 6.9, 10.6, 3, "eaves"),
    ("timber", 7.2, 11.8, 2, "gable"),
]
# the block behind the east terrace: the city's own pitch, house 0.9 m narrower
# than its plot (capital.py place_house_hd does `ww = spec["w"] - 0.9`), which
# leaves a 0.9 m slot between neighbours instead of a party wall.
E_BACK = [
    ("timber", 6.8, 8.4, 2, "eaves"),
    ("stone",  7.4, 7.8, 2, "gable"),
    ("timber", 6.4, 8.8, 2, "eaves"),
    ("shop",   7.0, 7.6, 2, "eaves"),
    ("timber", 6.6, 8.2, 3, "gable"),
    ("craft",  7.2, 7.9, 2, "eaves"),
]

# --- screen-audit classification -----------------------------------------
# first two letters of the part name -> class.  Order matters only in that the
# dict is looked up by the 2-char prefix, so "gsb" is "gs" -> flank.
_K2 = {
    "sd": "flank", "sw": "flank", "sb": "flank", "gs": "flank",
    "tg": "flank", "sp": "flank", "wo": "flank",
    "tf": "frame", "tb": "frame",
    "ec": "cornice", "qk": "quoin",
    "ub": "back", "bw": "back", "bb": "back", "gb": "back", "bp": "back",
    "bd": "back",
    "gw": "front", "uw": "front", "dr": "front", "sc": "front",
    "sh": "front", "jt": "front", "gf": "front", "in": "front",
    "pl": "plinth",
    "rf": "roof", "at": "roof", "ch": "roof", "cs": "roof", "dm": "roof",
    "gt": "roof", "sk": "roof", "ri": "roof",
    # round-2 additions, kept in their own classes so the audit shows how much
    # of the frame the new articulation actually buys
    "fd": "flankart", "fk": "flankart", "fp": "flankart",
    "gz": "gable",
}


def _cls(name):
    return _K2.get(name[:2].lower(), "other")


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def _mod(which):
    import hd_houses as m
    return m


_PAL = {}


def _palette(mod, variant=0, back=False):
    """Exactly the city's palette path: make_mats -> weathering -> house_mats.

    Cached per (variant, back): make_mats() mints fresh materials every call,
    and _age() keys on the material NAME, so a second call would hand back an
    un-weathered plaster while hd_houses believed it had already aged it.
    """
    key = (variant, bool(back))
    hit = _PAL.get(key)
    if hit is not None:
        return hit
    MAT = mod.make_mats()
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:                            # noqa: BLE001
        print("[fac] weathering skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    try:
        import capital_hd_glue as G
        MAT = G.house_mats(MAT, variant, back)
    except Exception as exc:                            # noqa: BLE001
        print("[fac] house_mats skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    _PAL[key] = MAT
    return MAT


def _tag(parts):
    for ob in parts:
        if ob is None:
            continue
        ob["fc"] = _cls(ob.name)
    return parts


def _place(parts, T):
    for ob in parts:
        if ob is None:
            continue
        ob.matrix_world = T @ ob.matrix_world
    return parts


def _terrace(mod, rows, side, y0, pitch="abut", tag="E", depth_bias=0.0):
    """Lay one row of houses down +Y, fronts toward x=0.

    pitch="abut"  -> advance by w   (party wall: two houses share the flank)
    pitch="city"  -> advance by plot, house is plot-0.9 wide (place_house_hd)
    """
    parts, per = [], []
    y = y0
    for i, (kind, w, d, fl, fr) in enumerate(rows):
        if pitch == "city":
            plot = w
            hw = max(4.6, plot - 0.9)
        else:
            plot = w
            hw = w
        cy = y + plot * 0.5
        cx = side * (FRONT + d * 0.5 + depth_bias)
        rot = math.radians(90.0) * side          # front (+Y) faces the street
        MAT = _palette(mod, 0, False)            # the city is variant 0 always
        t0 = time.perf_counter()
        hp = mod.house(MAT, random.Random(1000 + (0 if side > 0 else 500) + i),
                       kind=kind, w=hw, d=d, floors=fl, frontage=fr)
        dt = time.perf_counter() - t0
        _tag(hp)
        _place(hp, Ts(cx, cy, 0.0, rz=rot))
        npoly = sum(len(o.data.polygons) for o in hp
                    if o is not None and o.type == "MESH")
        per.append(("%s%d" % (tag, i), kind, hw, d, fl, len(hp), npoly,
                    H.tri_count(hp), dt))
        parts += hp
        y += plot + (0.05 + 0.30 * (i % 3) / 2.0 if pitch == "city" else 0.0)
    return parts, per, y


def build(mod):
    H._clear()
    parts, per = [], []
    p, q, yend = _terrace(mod, E_TERRACE, +1, Y0, "abut", "E")
    parts += p
    per += q
    p, q, yend2 = _terrace(mod, W_TERRACE, -1, Y0, "abut", "W")
    parts += p
    per += q
    p, q, _ = _terrace(mod, E_BACK, +1, Y0 - 3.0, "city", "B",
                       depth_bias=12.6 + ALLEY)
    parts += p
    per += q
    lay = {"yend": max(yend, yend2)}
    return parts, per, lay


def report(per, parts):
    print("[fac] --- per house ---", flush=True)
    for (tag, kind, w, d, fl, nob, npoly, ntri, dt) in per:
        print("  %-4s %-9s w=%.1f d=%.1f f=%d objs=%4d polys=%5d tris=%6d %5.0f ms"
              % (tag, kind, w, d, fl, nob, npoly, ntri, dt * 1000.0), flush=True)
    if per:
        n = float(len(per))
        mt = sum(p[7] for p in per) / n
        print("[fac] mean tris/house = %.0f  (round-1 baseline 4037 -> %+d)"
              % (mt, int(round(mt - 4037.0))), flush=True)
        print("[fac] mean objs/house = %.0f  mean build = %.0f ms/house"
              % (sum(p[5] for p in per) / n,
                 1000.0 * sum(p[8] for p in per) / n), flush=True)
    print("[fac] scene tris = %d" % H.tri_count(parts), flush=True)


# --------------------------------------------------------------------------
# screen audit: what is actually in the frame?
# --------------------------------------------------------------------------
def audit(cam, label="", res=(140, 79)):
    from mathutils import Vector
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    nx, ny = res
    mw = cam.matrix_world.copy()
    R = mw.to_3x3()
    origin = mw.translation.copy()
    aspect = float(RES[0]) / float(RES[1])
    hx = 0.5 * cam.data.sensor_width / cam.data.lens
    hy = hx / aspect
    tally, big, dims = {}, {}, {}
    miss = 0
    for j in range(ny):
        v = ((j + 0.5) / ny) * 2.0 - 1.0
        for i in range(nx):
            u = ((i + 0.5) / nx) * 2.0 - 1.0
            d = R @ Vector((u * hx, v * hy, -1.0))
            d.normalize()
            hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, origin, d)
            if not hit:
                miss += 1
                continue
            c = ob.get("fc") or "?"
            tally[c] = tally.get(c, 0) + 1
            k = (c, ob.name)
            big[k] = big.get(k, 0) + 1
            dims[ob.name] = tuple(round(x, 1) for x in ob.dimensions)
    n = float(nx * ny)
    print("[fac] AUDIT %-6s %d rays" % (label, int(n)), flush=True)
    for c, k in sorted(tally.items(), key=lambda kv: -kv[1]):
        print("    %-8s %5.1f %%  %5d px  %5.1f m^2 at 34 m"
              % (c, 100.0 * k / n, k, (100.0 * k / n) * 0.01 * 34.0 * 34.0
                 * 0.0576 * 1.78), flush=True)
    print("    %-8s %5.1f %%" % ("sky", 100.0 * miss / n), flush=True)
    for (c, nm), k in sorted(big.items(), key=lambda kv: -kv[1])[:8]:
        print("    . %-7s %-16s %5.1f %%  dims=%s"
              % (c, nm, 100.0 * k / n, dims.get(nm)), flush=True)


# --------------------------------------------------------------------------
# cameras
# --------------------------------------------------------------------------
def _aim(target, dist, pitch_deg):
    """Contract camera placed at +Y of the target, looking toward -Y."""
    a = math.radians(pitch_deg)
    return (target[0], target[1] + dist * math.cos(a),
            target[2] + dist * math.sin(a))


def _aim_b(target, dist, pitch_deg):
    """Same, from -Y: looking NORTH, so the terrace ends face the camera."""
    a = math.radians(pitch_deg)
    return (target[0], target[1] - dist * math.cos(a),
            target[2] + dist * math.sin(a))


def shots(lay):
    yend = lay["yend"]
    # the flank under the microscope: east terrace house 0, south wall, at
    # y = Y0, spanning x = FRONT .. FRONT+d.
    fx = FRONT + E_TERRACE[0][2] * 0.5   # centre of that flank in x
    fz = 4.0
    # The contract camera stands 20.93 m behind its target, and the visible
    # ground band starts 11.4 m ahead of it.  Aiming AT the junction therefore
    # makes 54 % of the frame empty wet street.  Aiming 11 m up the street puts
    # the flank 10 m ahead - inside the near clip of the ground band, running
    # off the bottom of frame - which is exactly what the city shot looks like.
    gx, gz = 5.6, 4.6
    return [
        # the contract camera, looking north: the flank is on the RIGHT and
        # runs off the bottom of the frame - this is the frame the city gets
        # wrong (v25a_game_avenue_north.png, lower right)
        ("game", _aim_b((gx, Y0 + 8.0, gz), 34.0, 52.0),
         (gx, Y0 + 8.0, gz), LENS_PLAYER),
        # 1.72 m eye height standing in the junction
        ("eye", (0.4, Y0 - 10.0, 1.72), (1.6, Y0 + 14.0, 3.6), 28.0),
        # face-on to the flank, 16 m out
        ("ends", (fx, Y0 - 16.0, 1.72), (fx, Y0, fz), 34.0),
        # the flank at the game camera's pitch, from over the street: the
        # composition that made the pale wall 40 % of the city frame
        ("end52", (fx - 13.0, Y0 - 12.0, 29.4), (fx, Y0 + 2.0, 5.0),
         LENS_PLAYER),
        # 3/4 close: sill, reveal, pipe, plinth
        ("close", (FRONT - 4.6, Y0 - 7.0, 3.10), (fx, Y0 - 0.2, 3.30), 40.0),
        # the whole terrace: is the party-wall joint visible at all?
        ("row", _aim((0.0, Y0 + 18.0, 4.4), 62.0, 22.0),
         (0.0, Y0 + 18.0, 4.4), 34.0),
    ]


# --------------------------------------------------------------------------
def _stats(path):
    """min / max / mean of a rendered PNG, straight off disk."""
    try:
        img = bpy.data.images.load(path, check_existing=False)
        px = list(img.pixels)
        bpy.data.images.remove(img)
    except Exception as exc:                            # noqa: BLE001
        return "unreadable: %s" % exc
    if not px:
        return "empty"
    step = max(1, len(px) // 40000)
    vals = px[::step]
    return "min=%.3f max=%.3f mean=%.3f" % (min(vals), max(vals),
                                            sum(vals) / len(vals))


def _ground(mod):
    """Lab-only ground disc: bleached limestone makes every wall look darker."""
    return K.mat_stone("fac_ground_lab", "#5f5849", "#3e382f", "#736b5a", 2.0)


# --------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    src = argv[0] if argv else "after"
    only = None
    if len(argv) > 1 and argv[1] != "all":
        only = set(argv[1].split(","))

    global RES, SAMPLES
    if "--fast" in argv:
        RES = (480, 270)
        SAMPLES = 8
    elif "--big" in argv:
        # delivery size, same sample count: 4x the pixels, 4x the time, and
        # Cycles' denoiser already resolves 8 spp cleanly at 270p
        RES = (960, 540)
        SAMPLES = 8

    mod = _mod(src)
    import hd_light as L

    parts, per, lay = build(mod)
    report(per, parts)
    H.diorama_floor(_ground(mod))
    sc = bpy.context.scene
    # hd_light.apply() *is* the city's rig (sky/sun/bounce/haze/post/cycles) and
    # is what look/render.py's build_rig() does.  Do not layer hd_sky.world() on
    # top: on 2026-11-02 that combination blew every frame to pure white, and the
    # city's own shots run with sky=None anyway (look/render.py: sky=o.get("sky")).
    L.apply("morning_town", sc, samples=SAMPLES, res=RES)

    os.makedirs(OUT, exist_ok=True)
    for (tag, loc, tgt, lens) in shots(lay):
        if only and tag not in only:
            continue
        cam = H.camera("cam_" + tag, loc, tgt, lens=lens)
        p = os.path.join(OUT, "fac2_%s_%s.png" % (src, tag))
        H.render_to(p, cam)
        print("[fac] %-8s %s" % (tag, _stats(p)), flush=True)
        if "--audit" in argv and tag in ("game", "eye", "ends", "end52", "row"):
            try:
                audit(cam, tag)
            except Exception as exc:                    # noqa: BLE001
                print("[fac] audit failed: %s: %s" % (type(exc).__name__, exc),
                      flush=True)
        bpy.data.objects.remove(cam, do_unlink=True)
    print("[fac] done", flush=True)


if __name__ == "__main__":
    main()
