"""hd_shops.py - functional town buildings for the Ars capital (Mushoku Tensei).

Why this file exists
--------------------
`hd_houses.py` produces one silhouette: a box with a pitched roof.  A capital
street made of eight of those reads as "a pile of houses", because nothing in
it tells the player which building sells bread and which one locks people up.
Every building here is a DIFFERENT volume first and a shop sign second:

    open colonnade + furnace stack   -> blacksmith / stable / armory
    crenellated corner turret        -> guild / knights' hall / guard post
    round turret + cone spire        -> magic shop
    dome + steam vent                -> bathhouse
    water wheel + flume              -> mill
    ridge monitor + hoist beam       -> store / warehouse
    bell turret + rose window        -> chapel
    peristyle + bidding platform     -> auction house
    enclosed yard + gatehouse        -> training ground / barracks / manor

Contract
--------
    MAT_KEYS                            list of material keys make_materials() fills
    make_materials()                    -> dict[str, bpy.types.Material]  (never KeyError)
    FOOTPRINT                           dict[kind] = (x, y, h), measured
    footprint(kind)                     -> (x, y)
    build(kind, MAT, rng=None, at=None, rz=0.0, **kw)
                                        -> list[Object]   origin = footprint centre,
                                                           ground z = 0, facade +Y
    kinds()                             -> sorted list of supported kinds
    preview(batch=1)                    4 street views at 1600x900 (a/b/c + 15 m d)

`at` bakes the placement into the mesh (H.apply), so the returned objects all
keep an identity matrix and a layout engine can join them without flattening
transforms first.  `rz` spins the building about its own origin, in degrees.
Every kind faces +Y, like hd_castle and hd_cathedral; hd_market faces -Y and
the glue layer has to flip it.

Openings are REAL: every door is a hole in a wall built from four pieces per
opening (so the door leaf sits 0.35 m inside it) and every window is a hole with
a dark reveal, glass at the back and mullions standing inside the reveal.  A
window is therefore never a decal on a slab -- see `_win` for the geometry.

Run:
    blender -b --factory-startup --python hd_shops.py -- --batch 1
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
import hd_houses as S          # _wall / _timber_frame / _jetty are the tested kit

# A rail fence in front of the facade is right for a manor standing in its own
# yard and wrong for a shop in a terrace: at front + 1.55 m it lands inside the
# carriageway and cuts the street in half.  capital.py turns it off when it
# packs the town as continuous frontage.
YARD_FENCE = True
import hd_castle as C          # shield() - the only heraldry helper in the kit

Ts = K.T_at
D2R = math.radians

OUT = "E:/My World/Blender/renders/kingdom/hd_shops_%s.png"

# --------------------------------------------------------------------------
# materials - every key has a factory, and both lookups self-heal
# --------------------------------------------------------------------------
MAT_KEYS = [
    "stone", "stone_warm", "stone_dark", "plaster", "plaster_white",
    "plaster_ochre", "plaster_rose", "wood",
    "wood_dark", "wood_light", "tile", "tile_soot", "slate", "thatch", "glass",
    "glass_warm", "glass_magic", "iron", "brass", "gold", "cloth_red",
    "cloth_blue", "cloth_gold", "cloth_green", "cloth_purple", "glow", "glow_warm",
    "glow_magic", "leaf", "water", "earth", "sand", "sand_dark", "soot", "void", "brick",
    "pave", "dirt",
]


def _palette():
    """name -> zero-argument factory.  Kept as thunks so make_materials() can
    swallow a bad keyword instead of taking the whole module down."""
    return {
        "stone": lambda: K.mat_stone(base="#7d7466", dark="#4a443a", light="#9a9284", scale=1.7),
        "stone_warm": lambda: K.mat_stone("stone_sand", base="#8d8168", dark="#5b5342",
                                          light="#a89b7f", scale=1.5),
        "stone_dark": lambda: K.mat_stone("stone_dark", base="#5d564a", dark="#332f28",
                                          light="#7a7263", scale=1.8),
        "plaster": lambda: K.mat_plaster(base="#e6dcc6", dirt="#cbbfa4", scale=5.0),
        "plaster_white": lambda: K.mat_plaster("plaster_white", base="#f0ece1",
                                               dirt="#d8d2c3", scale=6.0),
        # a street of nine white houses reads as one house nine times; these two
        # tints give the row a colour rhythm without leaving the palette
        "plaster_ochre": lambda: K.mat_plaster("plaster_ochre", base="#d9b483",
                                               dirt="#b8925f", scale=4.4),
        "plaster_rose": lambda: K.mat_plaster("plaster_rose", base="#d8ac9b",
                                              dirt="#b98a78", scale=4.6),
        "wood": lambda: K.mat_wood(base="#4a3223", light="#6b4a33", rough=0.78, scale=14.0),
        "wood_dark": lambda: K.mat_wood("timber_dark", base="#3a2517", light="#543823",
                                        scale=12.0),
        "wood_light": lambda: K.mat_wood("wood_light", base="#7a5a3b", light="#9d7a52",
                                         scale=11.0),
        "tile": lambda: K.mat_tile(base="#9c3f2b", dark="#6f2a1c", light="#bd5539"),
        "tile_soot": lambda: K.mat_tile("roof_soot", base="#4a3a34", dark="#2b211d",
                                        light="#635049"),
        "slate": lambda: K.mat_tile("roof_slate", base="#4a5560", dark="#333c46",
                                    light="#5f6d7a"),
        "thatch": lambda: K.mat_wood("thatch", base="#8a7346", light="#b09562",
                                     rough=0.95, scale=5.0),
        "glass": lambda: K.mat_glass(base="#3d5162"),
        "glass_warm": lambda: K.mat_glass("glass_warm", base="#6b5a3e"),
        "glass_magic": lambda: K.mat_glass("glass_magic", base="#4a3a6b"),
        "iron": lambda: K.mat_metal(base="#3b3a40", rough=0.42),
        "brass": lambda: K.mat_metal("brass", base="#8c7434", rough=0.5),
        "gold": lambda: K.mat_gold(base="#c9a227"),
        "cloth_red": lambda: K.mat_cloth("cloth_red", "#8e2b26"),
        "cloth_blue": lambda: K.mat_cloth("cloth_blue", "#2f4a70"),
        "cloth_gold": lambda: K.mat_cloth("cloth_gold", "#b98f3a"),
        "cloth_green": lambda: K.mat_cloth("cloth_green", "#3d5a3a"),
        "cloth_purple": lambda: K.mat_cloth("cloth_purple", "#4a2f63"),
        "glow": lambda: K.mat_metal("glow", "#ffe6b0", rough=0.3),
        "glow_warm": lambda: K.mat_metal("glow_warm", "#ffd9a0", rough=0.3),
        "glow_magic": lambda: K.mat_metal("glow_magic", "#8fd8e8", rough=0.3),
        "leaf": lambda: K.mat_foliage(base="#3e6b32", light="#5f9440", scale=7.0),
        "water": lambda: K.mat_water(base="#33606d"),
        "earth": lambda: K.mat_earth(base="#8a6a45", dark="#5c432b", scale=9.0),
        "sand": lambda: K.mat_earth("sand", base="#c2ab7e", dark="#9d8558", scale=14.0),
        "sand_dark": lambda: K.mat_earth("sand_dark", base="#a68f63", dark="#7d6a45",
                                         scale=11.0),
        "dirt": lambda: K.mat_earth("dirt", base="#6d6459", dark="#514a41", scale=6.0),
        "soot": lambda: K.mat_metal("soot", "#191614", rough=0.94),
        "void": lambda: K.mat_metal("void_mat", "#0e0d0e", rough=0.95),
        "brick": lambda: K.mat_stone("brick", base="#8a4a35", dark="#5a2b1e",
                                     light="#a8664c", scale=8.0),
        # wet-looking grey slabs read as concrete; the paving wants a warm,
        # slightly dirty stone with a big scale so it does not sparkle
        "pave": lambda: K.mat_stone("pave", base="#6b665c", dark="#494540",
                                    light="#847e72", scale=3.4),
    }


def make_materials():
    """Build every key in MAT_KEYS.  A factory that raises is replaced by a
    neutral plaster, so a medkit signature change can never KeyError a caller."""
    fallback = K.mat_plaster("fallback_plaster", base="#b3ab9c", dirt="#948c7d")
    MAT = {}
    for key, fac in _palette().items():
        try:
            MAT[key] = fac()
        except Exception as exc:                      # pragma: no cover - defensive
            print("[shops] material %r failed (%s) - using plaster" % (key, exc), flush=True)
            MAT[key] = fallback
    for key in MAT_KEYS:
        MAT.setdefault(key, fallback)
    return MAT


def _m(MAT, key):
    """Self-healing accessor: a MAT dict handed in from another module may be
    missing keys, and a KeyError in the middle of a build loses the whole scene."""
    m = MAT.get(key)
    if m is not None:
        return m
    try:
        m = _palette()[key]()
    except Exception:
        m = K.mat_plaster("fallback_plaster", base="#b3ab9c", dirt="#948c7d")
    MAT[key] = m
    return m


# --------------------------------------------------------------------------
# the opening kit
# --------------------------------------------------------------------------
def _win(name, T, w, h, frame, glass, dark, th=0.40, mull=2, transom=1,
         shutters=None, hood=False, sill=True, lit=None):
    """A window that lives INSIDE the wall hole cut by `_window`.

    Stack, from the street inward (local +Y is outward, the hole is `th` deep):

        y =  0.00  stone surround, sill and lintel - proud of the wall
        y = -0.18  mullions and transoms, standing free in the reveal
        y = -0.30  lead cames
        y = -0.35  glass
        y = -0.38  dark back plate

    The old `H.window_arched` puts a full-depth dark plate whose front face is
    flush with the wall, so every bar behind it is swallowed and the opening
    renders as one flat blue rectangle.  Nothing here sits behind a plate.
    """
    out = []
    hw = w * 0.5
    z0 = -h * 0.5
    out.append(K.box(name + "_bk", T @ Ts(0, -th + 0.04, 0), (w + 0.18, 0.05, h + 0.18), dark))
    out.append(K.box(name + "_gl", T @ Ts(0, -th + 0.12, 0), (w - 0.02, 0.04, h - 0.02),
                     lit or glass))
    nrow = max(2, int(h / 0.40))
    for k in range(nrow):
        z = z0 + h * (k + 0.5) / nrow
        out.append(K.box(name + "_cm%d" % k, T @ Ts(0, -th + 0.17, z),
                         (w - 0.10, 0.05, 0.035), frame))
    nm = max(1, int(mull))
    for i in range(1, nm):
        x = -hw + w * i / nm
        out.append(K.box(name + "_mu%d" % i, T @ Ts(x, -th * 0.45, 0),
                         (0.085, th * 0.72, h), frame, bev=0.008))
    for k in range(int(transom)):
        z = z0 + h * (0.42 + 0.40 * k)
        out.append(K.box(name + "_tr%d" % k, T @ Ts(0, -th * 0.45, z),
                         (w, th * 0.72, 0.09), frame, bev=0.008))
    for s in (-1, 1):
        out.append(K.box(name + "_j%d" % s, T @ Ts(s * (hw + 0.11), 0.03, 0),
                         (0.22, 0.20, h + 0.28), frame, bev=0.016))
    if sill:
        out.append(K.box(name + "_si", T @ Ts(0, 0.10, z0 - 0.10), (w + 0.62, 0.46, 0.15),
                         frame, bev=0.02))
    out.append(K.box(name + "_li", T @ Ts(0, 0.05, -z0 + 0.12), (w + 0.62, 0.22, 0.20),
                     frame, bev=0.02))
    if hood:
        out.append(K.box(name + "_hd", T @ Ts(0, 0.14, -z0 + 0.32), (w + 0.88, 0.36, 0.16),
                         frame, bev=0.022))
    if shutters is not None:
        for s in (-1, 1):
            out.append(K.box(name + "_sh%d" % s, T @ Ts(s * (hw + 0.44), 0.16, 0),
                             (0.30, 0.06, h * 0.94), shutters, bev=0.008))
    return out


def _window(name, T, x, y, zb, w, h, ops, th, frame, glass, dark, **kw):
    """Cut the hole in `ops` and return the window geometry for it.

    `ops` entries are (x, width, z_floor_relative, height); `T` is the building
    transform, `y` the wall plane, `zb` the hole's bottom in absolute z.
    """
    ops.append((x, w + 0.10, zb, h + 0.10))
    return _win(name, T @ Ts(x, y, zb + h * 0.5), w, h, frame, glass, dark, th=th, **kw)


def _door(name, T, x, y, zb, w, h, wood, iron, stone, steps=2, double=True):
    """Arched door leaf recessed 0.35 m into a hole in the wall."""
    return H.door_arched(name, T @ Ts(x, y + 0.01, zb), w, h, wood, iron,
                         stone=stone, steps=steps, double=double)


def _plinth(T, w, d, h, stone):
    return [K.box("plinth", T @ Ts(0, 0, h * 0.5), (w + 0.26, d + 0.26, h), stone, bev=0.02)]


def _roof(name, T, w, d, eave, pitch, tile, deck, frontage="eaves", end_mat=None,
          crest=False, ov_gable=0.42, course_h=0.26):
    """Wrapped tiled_roof.  Ridge along X for an eaves frontage (the usual
    street case), along Y for a gable front, which is the unrotated default.

    course_h 0.26 rather than the library default 0.34: at 15 m on a 5 m slope
    the coarse pitch reads as five planks, the finer one as tile courses.
    """
    kw = dict(course_h=course_h, gable_ends=False, end_mat=end_mat,
              ov_gable=ov_gable, crest=crest)
    if frontage == "gable":
        out = H.tiled_roof(name, T, w, d, eave, pitch, tile, deck, **kw)
        # gutter: a dark line under the eave on both flanks.  Without it a
        # rendered eave is a soft edge that melts into the wall at 15 m, and the
        # wall/roof junction is where the eye checks whether a building is
        # finished.
        gut = _m(MAT_CACHE, "iron")
        for s in (-1, 1):
            out.append(K.box(name + "_gut%d" % s,
                             T @ Ts(s * (w * 0.5 + 0.34), 0.0, eave + 0.02),
                             (0.14, d + 0.80, 0.13), gut, bev=0.006))
        return out
    out = H.tiled_roof(name, T @ Ts(0, 0, 0, rz=D2R(90)), d, w, eave, pitch, tile,
                       deck, **kw)
    gut = _m(MAT_CACHE, "iron")
    for s in (-1, 1):
        out.append(K.box(name + "_gut%d" % s, T @ Ts(0.0, s * (d * 0.5 + 0.34), eave + 0.02),
                         (w + 0.80, 0.14, 0.13), gut, bev=0.006))
    return out


def _ridge_z(w, d, eave, pitch, frontage="eaves"):
    across = w if frontage == "gable" else d
    return eave + (across * 0.5 + 0.45) * math.tan(D2R(pitch))


def _slope_z(w, d, eave, pitch, u, frontage="eaves"):
    """Roof surface height at distance `u` from the ridge line."""
    across = w if frontage == "gable" else d
    hw = across * 0.5 + 0.45
    rh = hw * math.tan(D2R(pitch))
    return eave + rh * max(0.0, 1.0 - abs(u) / hw)


def _chimney(name, T, x, y, z_base, z_top, mat, w=0.9, pots=1, cap_mat=None):
    out = [K.box(name, T @ Ts(x, y, (z_base + z_top) * 0.5), (w, w, z_top - z_base), mat,
                 bev=0.02)]
    out.append(K.box(name + "_cap", T @ Ts(x, y, z_top + 0.09), (w + 0.26, w + 0.26, 0.18),
                     cap_mat or mat, bev=0.02))
    for i in range(pots):
        px = x + (i - (pots - 1) * 0.5) * (w * 0.44)
        out.append(K.cyl(name + "_pot%d" % i, T @ Ts(px, y, z_top + 0.42), 0.16, 0.50,
                         _m(MAT_CACHE, "brick"), seg=10))
    return out


MAT_CACHE = {}


def _sign(name, T, w, h, board, frame, arm_len=0.95, z=2.9, x=0.0, double=False):
    """Hanging sign on an iron bracket, proud of the facade."""
    out = [K.box(name + "_a1", T @ Ts(x, arm_len * 0.5, z), (0.08, arm_len, 0.08), frame),
           K.box(name + "_a2", T @ Ts(x, 0.06, z - arm_len * 0.42),
                 (0.07, 0.07, arm_len * 0.82), frame)]
    out.append(K.box(name + "_b", T @ Ts(x, arm_len * 0.92, z - h * 0.5 - 0.28),
                     (w, 0.07, h), board, bev=0.012))
    if double:
        out.append(K.box(name + "_b2", T @ Ts(x, arm_len * 0.92, z - h * 0.5 - 0.28),
                         (0.07, w * 0.8, h), board, bev=0.012))
    return out


def _pict(name, T, y, z, s, kind):
    """Emblem for a hanging sign.  Shape over texture.

    At 15 m a painted symbol on a 0.6 m board is eight grey pixels; a silhouette
    that breaks the board's edge still reads.  Every icon is 2-6 primitives so
    twenty of them cost less than one window.
    """
    iron = _m(MAT_CACHE, "iron")
    gold = _m(MAT_CACHE, "gold")
    wood = _m(MAT_CACHE, "wood_dark")
    o = []
    if kind == "anvil":
        o.append(K.box(name + "_1", T @ Ts(0, y, z - s * 0.30), (s * 0.34, 0.08, s * 0.30), iron))
        o.append(K.box(name + "_2", T @ Ts(0, y, z - s * 0.02), (s * 0.76, 0.09, s * 0.22), iron))
        o.append(K.box(name + "_3", T @ Ts(s * 0.48, y, z + s * 0.02), (s * 0.22, 0.08, s * 0.11),
                       iron, bev=0.008))
    elif kind == "star":
        for i, a in enumerate((0, 60, 120)):
            o.append(K.box(name + "_%d" % i, T @ Ts(0, y, z, ry=D2R(a)),
                           (s * 0.72, 0.05, s * 0.11), gold, bev=0.004))
        o.append(K.cyl(name + "_c", T @ Ts(0, y, z, rx=D2R(90)), s * 0.13, 0.06, gold, seg=10))
    elif kind == "shears":
        for i, a in enumerate((32, -32)):
            o.append(K.box(name + "_%d" % i, T @ Ts(0, y, z + s * 0.10, ry=D2R(a)),
                           (s * 0.11, 0.05, s * 0.70), iron, bev=0.004))
        for i in (-1, 1):
            o.append(K.cyl(name + "_r%d" % i, T @ Ts(i * s * 0.17, y, z - s * 0.28, rx=D2R(90)),
                           s * 0.10, 0.05, iron, seg=10))
    elif kind == "mug":
        o.append(K.box(name + "_b", T @ Ts(-s * 0.04, y, z), (s * 0.42, 0.10, s * 0.50), gold))
        o.append(K.box(name + "_h", T @ Ts(s * 0.26, y, z), (s * 0.16, 0.08, s * 0.24), gold))
    elif kind == "bread":
        for i, dx in enumerate((-0.30, 0.0, 0.30)):
            o.append(K.sphere(name + "_%d" % i, T @ Ts(dx * s, y, z - s * 0.02),
                              s * 0.17, gold, seg=10, ring=6, squash=0.62))
    elif kind == "horseshoe":
        for i in range(5):
            a = math.radians(-150 + i * 60)
            o.append(K.box(name + "_%d" % i,
                           T @ Ts(math.cos(a) * s * 0.30, y, z + math.sin(a) * s * 0.30,
                                  ry=-a + math.pi * 0.5),
                           (s * 0.10, 0.05, s * 0.26), iron, bev=0.004))
    elif kind == "cross":
        o.append(K.box(name + "_v", T @ Ts(0, y, z), (s * 0.13, 0.06, s * 0.74), gold))
        o.append(K.box(name + "_h", T @ Ts(0, y, z + s * 0.14), (s * 0.50, 0.06, s * 0.13), gold))
    elif kind == "shield":
        o.append(K.box(name + "_s", T @ Ts(0, y, z), (s * 0.52, 0.06, s * 0.62), iron))
        o.append(K.box(name + "_c1", T @ Ts(0, y + 0.02, z), (s * 0.12, 0.04, s * 0.50), gold))
        o.append(K.box(name + "_c2", T @ Ts(0, y + 0.02, z + s * 0.06), (s * 0.40, 0.04, s * 0.11),
                       gold))
    elif kind == "barrel":
        o.append(K.cyl(name + "_b", T @ Ts(0, y, z, rx=D2R(90)), s * 0.28, s * 0.50, wood, seg=12))
        for i in (-1, 1):
            o.append(K.box(name + "_h%d" % i, T @ Ts(0, y, z + i * s * 0.18),
                           (s * 0.60, 0.05, s * 0.07), iron))
    elif kind == "sword":
        o.append(K.box(name + "_b", T @ Ts(0, y, z + s * 0.04), (s * 0.13, 0.05, s * 0.84), iron))
        o.append(K.box(name + "_g", T @ Ts(0, y, z - s * 0.36), (s * 0.50, 0.06, s * 0.09), gold))
        o.append(K.box(name + "_h", T @ Ts(0, y, z - s * 0.51), (s * 0.11, 0.06, s * 0.22), wood))
    elif kind == "moon":
        o.append(K.cyl(name + "_o", T @ Ts(0, y, z, rx=D2R(90)), s * 0.34, 0.05, gold, seg=16))
        o.append(K.cyl(name + "_i", T @ Ts(s * 0.13, y + 0.01, z, rx=D2R(90)), s * 0.28, 0.07,
                       _m(MAT_CACHE, "iron"), seg=16))
    elif kind == "book":
        o.append(K.box(name + "_a", T @ Ts(0, y, z), (s * 0.62, 0.05, s * 0.46), _m(MAT_CACHE,
                                                                                   "cloth_red")))
        o.append(K.box(name + "_s", T @ Ts(0, y + 0.03, z), (s * 0.07, 0.05, s * 0.48), gold))
        for i in (-1, 1):
            o.append(K.box(name + "_e%d" % i, T @ Ts(i * s * 0.24, y + 0.02, z),
                           (s * 0.10, 0.04, s * 0.40), _m(MAT_CACHE, "plaster_white")))
    elif kind == "coin":
        o.append(K.cyl(name + "_c", T @ Ts(0, y, z, rx=D2R(90)), s * 0.34, 0.06, gold, seg=16))
        o.append(K.cyl(name + "_d", T @ Ts(0, y + 0.035, z, rx=D2R(90)), s * 0.17, 0.03, wood, seg=12))
    elif kind == "wheel":
        o.append(K.cyl(name + "_r", T @ Ts(0, y, z, rx=D2R(90)), s * 0.34, 0.05, wood, seg=16))
        for i, a in enumerate((0, 45, 90, 135)):
            o.append(K.box(name + "_s%d" % i, T @ Ts(0, y, z, ry=D2R(a)),
                           (s * 0.64, 0.05, s * 0.06), wood))
        o.append(K.cyl(name + "_h", T @ Ts(0, y, z, rx=D2R(90)), s * 0.08, 0.06, iron, seg=10))
    elif kind == "bed":
        o.append(K.box(name + "_f", T @ Ts(0, y, z - s * 0.10), (s * 0.30, 0.06, s * 0.22), gold))
        o.append(K.box(name + "_m", T @ Ts(0, y, z + s * 0.06), (s * 0.58, 0.06, s * 0.44), iron))
        o.append(K.box(name + "_p", T @ Ts(0, y + 0.02, z - s * 0.20), (s * 0.56, 0.04, s * 0.36),
                       _m(MAT_CACHE, "plaster_white")))
    elif kind == "crate":
        o.append(K.box(name + "_b", T @ Ts(0, y, z), (s * 0.50, 0.06, s * 0.50), wood))
        for i in (-1, 1):
            o.append(K.box(name + "_a%d" % i, T @ Ts(i * s * 0.20, y + 0.02, z),
                           (s * 0.06, 0.04, s * 0.50), _m(MAT_CACHE, "iron")))
    elif kind == "wave":
        for i, dz in enumerate((-0.18, 0.0, 0.18)):
            o.append(K.box(name + "_w%d" % i, T @ Ts(0, y, z + s * dz, ry=D2R(6)),
                           (s * 0.52, 0.05, s * 0.07), _m(MAT_CACHE, "cloth_blue")))
    else:                                              # generic: a diamond
        o.append(K.box(name + "_d", T @ Ts(0, y, z, ry=D2R(45)), (s * 0.46, 0.06, s * 0.46), gold))
    return o


def _hang(name, T, x, z, kind, w=1.02, h=0.98, arm=0.92, y=None, double=True, flag=None):
    """Iron bracket + painted board + emblem, projecting from the facade.

    Signs on the wall plane vanish at street distance: the bracket has to put
    the board out into the light so it casts its own shadow and reads as an
    object.  The board is painted in the house colour rather than left as bare
    wood - at 20 m the colour is the identifier and the carved emblem is a
    detail that only resolves in the close-up.
    """
    y = 0.0 if y is None else y
    frame = _m(MAT_CACHE, "iron")
    board = flag if flag is not None else _m(MAT_CACHE, "wood_light")
    by = y + arm * 0.92
    bz = z - h * 0.5 - 0.22
    o = [K.box(name + "_arm", T @ Ts(x, y + arm * 0.5, z), (0.07, arm, 0.07), frame, bev=0.006),
         K.box(name + "_drop", T @ Ts(x, y + 0.04, z - arm * 0.42),
               (0.06, 0.06, arm * 0.90), frame, bev=0.004),
         K.box(name + "_brd", T @ Ts(x, by, bz), (w, 0.07, h), board, bev=0.014)]
    # iron edge band: without it a painted board has no fixed outline and
    # reads as a coloured patch on the wall
    for s in (-1, 1):
        o.append(K.box(name + "_fe%d" % s, T @ Ts(x + s * (w * 0.5 - 0.03), by, bz),
                       (0.06, 0.09, h + 0.02), frame, bev=0.006))
        o.append(K.box(name + "_ft%d" % s, T @ Ts(x, by, bz + s * (h * 0.5 - 0.03)),
                       (w + 0.02, 0.09, 0.06), frame, bev=0.006))
    s = min(w, h) * 0.60
    # `_pict` draws its glyphs at the origin of the transform it is handed, so
    # the bracket's own x offset has to be baked in here.  Passing the bare
    # building transform put every emblem back at the middle of the facade and
    # left every board a blank coloured square.
    o += _pict(name + "_p", T @ Ts(x, 0, 0), by + 0.055, bz, s, kind)
    if double:
        o += _pict(name + "_q", T @ Ts(x, 0, 0), by - 0.055, bz, s, kind)
    if flag is not None:
        # pennant on the bracket: still legible when the board is 20 px tall
        o.append(K.box(name + "_fl", T @ Ts(x, y + arm * 0.62, z + 0.26),
                       (0.05, 0.66, 0.50), flag))
        o.append(K.box(name + "_flb", T @ Ts(x, y + arm * 0.62, z + 0.52),
                       (0.04, 0.70, 0.05), frame, bev=0.004))
    return o


def _awning(T, w, y, z, depth=1.7, mat_a=None, mat_b=None, drop=0.55, stripe=4):
    """Striped canvas awning: alternating panels on a slight slope."""
    out = []
    n = max(2, stripe)
    for i in range(n):
        x = -w * 0.5 + w * (i + 0.5) / n
        m = mat_a if i % 2 == 0 else (mat_b or mat_a)
        out.append(K.box("awn%d" % i,
                         T @ Ts(x, y + depth * 0.5, z - drop * 0.5, rx=D2R(-14)),
                         (w / n * 1.02, depth, 0.05), m))
    out.append(K.box("awn_bar", T @ Ts(0, y + depth, z - drop - 0.06), (w + 0.2, 0.07, 0.07),
                     _m(MAT_CACHE, "wood")))
    for s in (-1, 1):
        out.append(K.box("awn_p%d" % s, T @ Ts(s * (w * 0.5 + 0.06), y + 0.06, z - 0.10),
                         (0.08, 0.08, 0.5), _m(MAT_CACHE, "wood")))
    return out


def _bench(T, x, y, z, wood, L=1.6):
    out = [K.box("bench_seat", T @ Ts(x, y, z + 0.44), (L, 0.42, 0.10), wood, bev=0.012)]
    for s in (-1, 1):
        out.append(K.box("bench_l%d" % s, T @ Ts(x + s * (L * 0.5 - 0.16), y, z + 0.22),
                         (0.12, 0.36, 0.44), wood))
    return out


def _basket(T, x, y, z, mat):
    return [K.cyl("basket", T @ Ts(x, y, z + 0.22), 0.26, 0.44, mat, seg=12),
            K.cyl("basket_r", T @ Ts(x, y, z + 0.46), 0.29, 0.07, mat, seg=12)]


def _sack(T, x, y, z, mat):
    return [K.box("sack", T @ Ts(x, y, z + 0.26), (0.46, 0.38, 0.52), mat, bev=0.09)]


# --------------------------------------------------------------------------
# the shell every building shares
# --------------------------------------------------------------------------
def _rafters(name, T, w, d, z, timber, gap=0.60, depth=0.36, h=0.15):
    """Rafter tails under both eaves.

    A rendered overhang without visible rafters is a soft grey blur at 15 m -
    the eye reads the eave as the place where the building was cut off.  These
    are the cheapest possible fix and they cast the scalloped shadow that says
    "there is a roof up there".
    """

    out = []
    n = max(4, int(w / gap))
    for s in (-1, 1):
        y = s * (d * 0.5 + 0.20)
        for i in range(n):
            x = -w * 0.5 + (i + 0.5) * w / n
            out.append(K.box("%s_rt%d_%d" % (name, s, i), T @ Ts(x, y, z - 0.13),
                             (0.15, depth, h), timber, bev=0.006))
    return out


def _downpipe(name, T, x, y, z0, z1, iron, inward=-1.0):
    """A rainwater pipe on a bracket run: 4 m of vertical line is what makes a
    facade look like it drains instead of ending."""

    out = [K.box("%s_dp" % name, T @ Ts(x, y, (z0 + z1) * 0.5), (0.11, 0.11, z1 - z0), iron,
                 bev=0.008)]
    for i in range(3):
        zz = z0 + (i + 0.75) * (z1 - z0) / 3.1
        out.append(K.box("%s_dpb%d" % (name, i), T @ Ts(x, y + inward * 0.09, zz),
                         (0.17, 0.12, 0.09), iron, bev=0.005))
    out.append(K.box("%s_dps" % name, T @ Ts(x, y + inward * 0.13, z0 + 0.14),
                     (0.14, 0.30, 0.14), iron, bev=0.008))
    return out


def _firewood(name, T, x, y, wood, logs=15, length=0.95):
    """A stacked woodpile: three courses of split logs.

    Cheap in faces, heavy in silhouette - and it is the single prop that makes a
    yard read as inhabited at 15 m, because the eye reads the round ends as a
    texture it already knows.
    """

    out = []
    for r in range(3):
        n = logs - r * 4
        for i in range(max(1, n)):
            xx = x + (i - (n - 1) * 0.5) * 0.17 + (0.08 if r % 2 else 0.0)
            out.append(K.cyl("%s_fw%d_%d" % (name, r, i),
                             T @ Ts(xx, y, 0.10 + r * 0.146, rx=D2R(90)),
                             0.072, length, wood, seg=8))
    return out


def _fence(name, T, x0, x1, y, wood, height=0.95, gap=0.24):
    """A rail fence: posts every `gap`, two rails through them."""
    out = []
    n = max(2, int(abs(x1 - x0) / gap))
    for i in range(n + 1):
        xx = x0 + (x1 - x0) * i / n
        out.append(K.box("%s_fn%d" % (name, i), T @ Ts(xx, y, height * 0.5),
                         (0.09, 0.09, height), wood, bev=0.005))
    for j, zz in enumerate((height * 0.34, height * 0.76)):
        out.append(K.box("%s_fnr%d" % (name, j), T @ Ts((x0 + x1) * 0.5, y, zz),
                         (abs(x1 - x0) + 0.09, 0.06, 0.09), wood, bev=0.005))
    return out


def _yard(name, T, w, front, MAT, seed=0, area=0.0, fence=True):
    """Street furniture in front of a facade: barrels, crates, sacks, timber, and
    on a big yard a woodpile and a rail fence.

    Every building on the street needs something at its base or the row reads as
    card cutouts standing on a plain - this is the difference between a facade
    and a place.  Slots are fixed so the scatter is repeatable, and they stop
    short of the party walls so two neighbours' barrels cannot interpenetrate.
    A wide yard (training ground, stable) carries more than a shopfront.
    """

    rng = random.Random(seed * 7919 + 13)
    wood = _m(MAT, "wood")
    iron = _m(MAT, "iron")
    sand = _m(MAT, "sand_dark")
    out = []
    slots = [-0.30, -0.17, 0.15, 0.28, 0.03, -0.05, 0.36, -0.42, 0.44, -0.24]
    want = 4 if area < 70.0 else (7 if area < 140.0 else 10)
    for i, f in enumerate(slots[:want]):
        x = f * w
        if abs(x) > w * 0.5 - 0.85:
            continue
        y = front + 0.50 + rng.uniform(0.0, 0.40)
        pick = (i + seed) % 4
        if pick == 0:
            out += H.barrel("%s_yb%d" % (name, i), T @ Ts(x, y, 0), 0.29, 0.84, wood, iron)
        elif pick == 1:
            out += H.crate("%s_yc%d" % (name, i), T @ Ts(x, y, 0), 0.58, wood)
            if rng.random() < 0.6:
                out += H.crate("%s_yc%db" % (name, i), T @ Ts(x + 0.06, y + 0.05, 0.58),
                               0.42, wood)
        elif pick == 2:
            out += _sack(T, x, y, 0, sand)
            if rng.random() < 0.5:
                out += _sack(T, x + 0.38, y + 0.12, 0, sand)
        else:
            # timber stack: four offcuts on two bearers
            for b in (-1, 1):
                out.append(K.box("%s_yt%d_%d" % (name, i, b), T @ Ts(x, y + b * 0.22, 0.09),
                                 (1.10, 0.10, 0.18), wood, bev=0.006))
            for k in range(3):
                out.append(K.box("%s_yt%d_%d" % (name, i, k + 2),
                                 T @ Ts(x + rng.uniform(-0.05, 0.05), y, 0.20 + k * 0.13),
                                 (1.16, 0.44, 0.12), wood, bev=0.006))
    if area >= 70.0:
        out += _firewood(name, T, -w * 0.42, front + 0.72 + rng.uniform(0.0, 0.30), wood)
    if area >= 130.0 and fence:
        out += _fence(name, T, -w * 0.46, -w * 0.20, front + 1.55 + rng.uniform(0.0, 0.4), wood)
    return out


def _shell(name, T, w, d, floors, fh, plinth_h, wall, stone, timber, glass, dark,
           g_holes=(), g_wins=None, u_wins=None, open_front=False,
           jetty=0.30, th=0.40, back_wins=0, side_wins=0, lit=None):
    """Plinth + floors + a wall with real holes + windows + side/back walls.

    Returns (parts, z_eave, ops_per_floor) so the caller can hang a roof and
    knows exactly where its own doors are.

    g_holes : [(x, w, z_abs, h)] holes the caller will fill with a door
    g_wins  : dict for the ground-floor window row (None = no row)
    u_wins  : dict for the upper rows (same spec on every upper floor)
    """
    parts = _plinth(T, w, d, plinth_h, stone)
    ops_all = []
    z = plinth_h

    # ---- ground floor -----------------------------------------------------
    if open_front:
        n = max(3, int(round(w / 2.5)))
        for i in range(n):
            x = -w * 0.5 + 0.62 + (w - 1.24) * i / (n - 1)
            parts.append(K.box(name + "_col%d" % i,
                               T @ Ts(x, d * 0.5 - 0.34, plinth_h + fh * 0.5),
                               (0.36, 0.36, fh * 0.97), timber, bev=0.015))
            parts.append(K.box(name + "_cap%d" % i,
                               T @ Ts(x, d * 0.5 - 0.34, plinth_h + fh - 0.10),
                               (0.50, 0.50, 0.20), stone, bev=0.015))
        parts.append(K.box(name + "_beam", T @ Ts(0, d * 0.5 - 0.34, plinth_h + fh - 0.34),
                           (w + 0.1, 0.40, 0.36), timber, bev=0.02))
        # dark interior: a back wall set 2.6 m in, so the colonnade reads as depth
        parts.append(K.box(name + "_inw", T @ Ts(0, d * 0.5 - 2.70, plinth_h + fh * 0.5),
                           (w - 0.1, 0.30, fh), wall, bev=0.01))
        parts.append(K.box(name + "_ind", T @ Ts(0, d * 0.5 - 2.54, plinth_h + fh * 0.5),
                           (w - 0.3, 0.06, fh * 0.94), dark))
        # A dark plate alone reads as a hole punched through the building.  A
        # counter, two shelf runs with goods on them and a warm glow behind
        # turn the same box into a shop you can see into.
        cy = d * 0.5 - 1.05
        parts.append(K.box(name + "_cnt", T @ Ts(0.6, cy, plinth_h + 0.92),
                           (w * 0.52, 0.62, 0.10), timber, bev=0.012))
        parts.append(K.box(name + "_cntf", T @ Ts(0.6, cy + 0.30, plinth_h + 0.46),
                           (w * 0.52, 0.09, 0.92), timber, bev=0.01))
        for i in range(2):
            sz = plinth_h + 1.62 + i * 0.62
            parts.append(K.box(name + "_shf%d" % i, T @ Ts(-0.5, d * 0.5 - 1.30, sz),
                               (w * 0.55, 0.42, 0.08), timber, bev=0.008))
            for k in range(5):
                gx = -w * 0.5 + w * 0.30 + k * (w * 0.52 / 4.0)
                gm = _m(MAT_CACHE, ("cloth_red", "cloth_gold", "glass_warm", "wood_light",
                                    "cloth_blue")[k % 5])
                gs = 0.16 + 0.05 * ((k + i) % 3)
                parts.append(K.box(name + "_gd%d_%d" % (i, k), T @ Ts(gx, d * 0.5 - 1.30, sz + gs * 0.5),
                                   (gs, 0.30, gs * 0.9), gm, bev=0.006))
        parts.append(K.box(name + "_lit", T @ Ts(-w * 0.24, d * 0.5 - 2.46, plinth_h + fh * 0.62),
                           (w * 0.30, 0.05, fh * 0.5), _m(MAT_CACHE, "glow_warm")))
        ops_all.append([])
    else:
        # the ground wall is built from z=0 (the plinth overlaps it), so its
        # openings stay in absolute z - subtracting the plinth height here
        # drops every doorway 0.34 m and buries the arch head in masonry.
        ops = [(x, ow, z0, oh) for (x, ow, z0, oh) in g_holes]
        gparts = []
        if g_wins:
            n = g_wins["n"]
            span = w - 1.5
            for i in range(n):
                x = -span * 0.5 + span * (i + 0.5) / n
                if any(abs(x - hx) < (hw_ + g_wins["w"]) * 0.6
                       for (hx, hw_, _a, _b) in g_holes):
                    continue
                gparts += _window(name + "_gw%d" % i, T, x, d * 0.5 + 0.01,
                                  plinth_h + g_wins.get("z", 1.05), g_wins["w"],
                                  g_wins["h"], ops, th, stone, glass, dark,
                                  mull=g_wins.get("mull", 2), hood=g_wins.get("hood", False),
                                  shutters=g_wins.get("shutters"), lit=lit)
        parts += S._wall(name + "_g", T, w, fh, th, ops, wall, y=d * 0.5 - th)
        parts += gparts
        ops_all.append(ops)
    z += fh

    # ---- upper floors -----------------------------------------------------
    for f in range(1, floors):
        over = jetty if f == 1 else 0.0
        ww = w + over * 2.0
        dd = d + over * 2.0
        if over:
            parts += S._jetty(T, w, d, z, over=over, beam=timber)
        ops = []
        uparts = []
        if u_wins:
            n = u_wins["n"]
            span = ww - 1.7
            ww_ = u_wins["w"]
            wh_ = u_wins["h"]
            zz = u_wins.get("z", 0.85)
            blocked = u_wins.get("skip", ())
            for i in range(n):
                x = -span * 0.5 + span * (i + 0.5) / n
                if any(abs(x - b) < 1.05 for b in blocked):
                    continue
                uparts += _window(name + "_uw%d_%d" % (f, i), T, x, dd * 0.5 + 0.01,
                                  z + zz, ww_, wh_, ops, th, stone, glass, dark,
                                  mull=u_wins.get("mull", 2), hood=u_wins.get("hood", False),
                                  shutters=u_wins.get("shutters"), lit=lit)
        # `_window` records its hole in absolute z (that is what the geometry
        # needs), but `_wall` is handed the floor transform and cuts openings
        # measured from the floor's own base.  Without this rebase the holes
        # land a floor too high, no hole is ever cut, and every upper window
        # renders as a stone frame glued to blank wall (the glass and the dark
        # back plate end up buried inside the masonry).
        ops = [(a, b, c - z, e) for (a, b, c, e) in ops]
        parts += S._wall(name + "_uw%d" % f, T @ Ts(0, 0, z), ww, fh, th, ops, wall,
                         y=dd * 0.5 - th)
        parts += uparts
        # Plaster walls get exposed framing by default; a stone or brick wall
        # with brown sticks painted on it was the single ugliest thing in the
        # earlier previews, so the test is the material, not a per-building
        # flag that someone will forget to set.
        if u_wins and u_wins.get("frame", not _is_stone(wall)):
            parts += S._timber_frame(T, ww, z, z + fh, dd * 0.5 + 0.03, timber,
                                     openings=[(x, ow, zz0, oh)
                                               for (x, ow, zz0, oh) in ops],
                                     stud=u_wins.get("stud", 1.05), rails=())
            parts += _rail(name + "_mr%d" % f, T, ww, z + fh * 0.46, dd * 0.5 + 0.03,
                           timber, ops, base=z)
        for s in (-1, 1):
            parts.append(K.box(name + "_us%d_%d" % (f, s),
                               T @ Ts(s * (ww * 0.5 - th * 0.5), 0, z + fh * 0.5),
                               (th, dd, fh), wall, bev=0.02))
        parts.append(K.box(name + "_ub%d" % f, T @ Ts(0, -(dd * 0.5 - th * 0.5), z + fh * 0.5),
                           (ww, th, fh), wall, bev=0.02))
        ops_all.append(ops)
        z += fh

    # ---- ground-floor sides and back (the upper ones were done per floor) --
    for s in (-1, 1):
        parts.append(K.box(name + "_gs%d" % s,
                           T @ Ts(s * (w * 0.5 - th * 0.5), 0, plinth_h + fh * 0.5),
                           (th, d, fh), wall, bev=0.02))
        for i in range(side_wins):
            parts += _rect_side(name + "_sw%d_%d" % (s, i),
                                T @ Ts(s * (w * 0.5 + 0.01), (i - (side_wins - 1) * 0.5) * 2.6,
                                       plinth_h + fh * 0.55, rz=D2R(90 * s)),
                                0.95, 1.20, stone, glass, dark)
    parts.append(K.box(name + "_gb", T @ Ts(0, -(d * 0.5 - th * 0.5), plinth_h + fh * 0.5),
                       (w, th, fh), wall, bev=0.02))
    for i in range(back_wins):
        parts.append(K.box(name + "_bw%d" % i,
                           T @ Ts((i - (back_wins - 1) * 0.5) * 2.4, -(d * 0.5 - 0.02),
                                  plinth_h + fh * 0.62), (0.9, 0.06, 1.05), _m(MAT_CACHE, "wood_dark")))
    # eave cornice: one proud band under the roof.  Flat facades have no
    # horizontal shadow anywhere, and a stone band is the cheapest line that
    # makes a wall read as masonry instead of a painted card.
    last_over = jetty if floors > 1 else 0.0
    bw, bd = w + last_over * 2.0, d + last_over * 2.0
    parts.append(K.box(name + "_corn", T @ Ts(0, bd * 0.5 + 0.02, z - 0.15),
                       (bw + 0.14, 0.18, 0.20), stone, bev=0.015))
    # quoins: alternating long/short blocks up the street corners of masonry
    # walls.  They are the reason a stone corner reads as load-bearing rather
    # than as a decal wrapped round a box, and at 15 m they are the only thing
    # that separates one stone facade from the next.
    if _is_stone(wall):
        qn = max(4, int((z - plinth_h) / 0.60))
        qw = _m(MAT_CACHE, "stone_warm")
        for sx in (-1, 1):
            for i in range(qn):
                longs = 0.66 if i % 2 == 0 else 0.44
                zz = plinth_h + (i + 0.5) * (z - plinth_h) / qn
                parts.append(K.box("%s_q%d_%d" % (name, sx, i),
                                   T @ Ts(sx * (bw * 0.5 - longs * 0.5 + 0.04),
                                          bd * 0.5 + 0.03, zz),
                                   (longs, 0.13, (z - plinth_h) / qn * 0.86), qw, bev=0.012))
                parts.append(K.box("%s_qs%d_%d" % (name, sx, i),
                                   T @ Ts(sx * (bw * 0.5 + 0.03),
                                          bd * 0.5 - longs * 0.5 + 0.04, zz),
                                   (0.13, longs, (z - plinth_h) / qn * 0.86), qw, bev=0.012))
    # ---- eaves and drainage ------------------------------------------------
    parts += _rafters(name, T, bw, bd, z, timber)
    for s in (-1, 1):
        parts += _downpipe("%s_dp%d" % (name, s), T, s * (bw * 0.5 - 0.16),
                           bd * 0.5 + 0.09, plinth_h + 0.02, z - 0.24,
                           _m(MAT_CACHE, "iron"))
    # a string course at every floor line, so a three-storey wall is not one
    # uninterrupted rectangle
    for i in range(1, floors):
        parts.append(K.box("%s_sc%d" % (name, i),
                           T @ Ts(0, bd * 0.5 + 0.05, plinth_h + i * fh),
                           (bw + 0.12, 0.14, 0.11), stone, bev=0.012))
    return parts, z, ops_all


def _rect_side(name, T, w, h, frame, glass, dark):
    """Window on a side wall: same reveal logic, 0.30 m deep, no surround."""
    out = [K.box(name + "_bk", T @ Ts(0, -0.22, 0), (w, 0.05, h), dark),
           K.box(name + "_gl", T @ Ts(0, -0.16, 0), (w - 0.02, 0.04, h - 0.02), glass)]
    for i in range(1, 3):
        out.append(K.box(name + "_m%d" % i, T @ Ts(-w * 0.5 + w * i / 3.0, -0.06, 0),
                         (0.07, 0.24, h), frame))
    for s in (-1, 1):
        out.append(K.box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + 0.09), 0.02, 0),
                         (0.18, 0.18, h + 0.24), frame, bev=0.014))
    out.append(K.box(name + "_si", T @ Ts(0, 0.08, -h * 0.5 - 0.09), (w + 0.5, 0.40, 0.13),
                     frame, bev=0.016))
    return out


def _rail(name, T, w, z, y, mat, openings=(), base=0.0, gap=0.08, thick=0.10, high=0.17):
    """A horizontal timber rail that stops at every opening.

    hd_houses._timber_frame draws its rails as single full-width boxes, so a
    mid rail on a plaster wall runs straight across the glass of every window
    it meets.  Breaking it at the holes is the difference between "framed wall"
    and "brown band nailed over the windows".
    """

    cuts = []
    for (ox, ow, oz0, ozh) in openings:
        if (oz0 + base) - high * 1.4 < z < (oz0 + base) + ozh + high * 1.4:
            cuts.append((ox - ow * 0.5 - gap, ox + ow * 0.5 + gap))
    cuts.sort()
    out = []
    x0 = -w * 0.5
    n = 0
    for (a, b) in cuts:
        if b <= x0:
            continue
        a = max(a, x0)
        if a - x0 > 0.14:
            out.append(K.box("%s_r%d" % (name, n), T @ Ts((x0 + a) * 0.5, y, z),
                             (a - x0, thick, high), mat, bev=0.008))
            n += 1
        x0 = max(x0, b)
    if w * 0.5 - x0 > 0.14:
        out.append(K.box("%s_r%d" % (name, n), T @ Ts((x0 + w * 0.5) * 0.5, y, z),
                         (w * 0.5 - x0, thick, high), mat, bev=0.008))
    return out


def _pier(name, T, x, y, z0, z1, w, dpt, mat, cap=None, stages=2):
    """A wall buttress with a weathered shoulder instead of a spire.

    hd_common.buttress() tops every buttress with a cone pinnacle, so a stone
    facade ends up ringed by four free-standing obelisks - they read as
    monuments in a graveyard, not as wall thickening.  This one steps back
    twice and finishes with a slab and a sloped weathering.
    """

    cap = cap or mat
    out = []
    h = z1 - z0
    # lower stage, then a narrower upper stage that steps back into the wall
    out.append(K.box("%s_b0" % name, T @ Ts(x, y, z0 + h * 0.275),
                     (w, dpt, h * 0.55 + 0.02), mat, bev=0.012))
    out.append(K.box("%s_b1" % name, T @ Ts(x, y, z0 + h * 0.775),
                     (w * 0.84, dpt * 0.80, h * 0.45 + 0.02), mat, bev=0.012))
    out.append(K.box("%s_cap" % name, T @ Ts(x, y + dpt * 0.02, z1 + 0.02),
                     (w * 0.86, dpt * 0.92, 0.14), cap, bev=0.01))
    out.append(K.box("%s_wea" % name, T @ Ts(x, y + dpt * 0.22, z1 + 0.15, rx=D2R(26)),
                     (w * 0.82, dpt * 0.80, 0.13), cap, bev=0.008))
    return out


def _is_stone(mat):
    """True for the masonry materials.

    A half-timbered gable on a stone tower is the one detail that instantly
    reads as "asset pack": stone walls, brown studs.  Gables are therefore
    framed only when the wall they sit on is plaster or boarding.
    """
    try:
        n = (getattr(mat, "name", "") or "").lower()
    except Exception:
        return False
    return n.startswith(("stone", "brick", "pave", "granite", "ashlar"))


def _gable_wall(name, T, w, d, eave, rh, wall, timber, frontage="eaves", th=0.40,
                frame=True):
    """Gable triangles: timber-framed on plaster, plain masonry on stone.

    A bare triangle this size is the largest featureless surface on the street,
    so every gable gets studs, a collar and a loft hatch: without them the eye
    reads the triangle as a hole in the facade.
    """
    out = []
    hw = (w if frontage == "gable" else d) * 0.5 + 0.40
    pts = [(-hw + 0.05, 0.0), (hw - 0.05, 0.0), (0.0, rh - 0.08)]
    stone_gable = _is_stone(wall)
    for sy in (-1, 1):
        y = sy * (d * 0.5 + 0.42 - 0.14)
        out.append(H.prism(name + "_gm%d" % sy, T @ Ts(0, y, eave), pts, 0.26, wall,
                           axis="y"))
        if stone_gable:
            # Masonry gable: no studs, but a bare triangle is the largest
            # unbroken surface a street facade offers, and pale stone at 15 m
            # reads as a hole in the wall.  Give it a raking string course, a
            # small attic window and a datestone.
            if sy > 0 or frontage != "gable":
                ty = y + sy * 0.14
                ap = rh - 0.10
                warm = _m(MAT_CACHE, "stone_warm")
                dark_st = _m(MAT_CACHE, "stone")
                for i, (frac, wide) in enumerate(((0.30, 0.74), (0.66, 0.40))):
                    out.append(K.box(name + "_gsb%d_%d" % (sy, i), T @ Ts(0, ty, eave + ap * frac),
                                     (hw * wide * 2.0, 0.11, 0.20), dark_st, bev=0.012))
                # attic window at mid-gable: any lower and it disappears behind
                # the eave cornice and the roof's own overhang
                wz = eave + ap * 0.50
                out.append(K.box(name + "_gwg%d" % sy, T @ Ts(0, ty - sy * 0.02, wz),
                                 (0.68, 0.06, 0.82), _m(MAT_CACHE, "void")))
                # the surround is four bars, not one slab: a solid stone box
                # here simply covers the very reveal it is supposed to frame
                for bx in (-0.42, 0.42):
                    out.append(K.box(name + "_gwa%d_%.2f" % (sy, bx),
                                     T @ Ts(bx, ty + sy * 0.04, wz), (0.16, 0.16, 1.06), warm,
                                     bev=0.012))
                for bz in (-0.51, 0.51):
                    out.append(K.box(name + "_gwb%d_%.2f" % (sy, bz),
                                     T @ Ts(0, ty + sy * 0.04, wz + bz), (1.00, 0.16, 0.16), warm,
                                     bev=0.012))
                out.append(K.box(name + "_gwm%d" % sy, T @ Ts(0, ty + sy * 0.06, wz),
                                 (0.08, 0.06, 0.82), _m(MAT_CACHE, "iron")))
                out.append(K.box(name + "_gwt%d" % sy, T @ Ts(0, ty + sy * 0.06, wz + 0.16),
                                 (0.68, 0.06, 0.08), _m(MAT_CACHE, "iron")))
                out.append(K.box(name + "_gwk%d" % sy, T @ Ts(0, ty + sy * 0.02, wz - 0.68),
                                 (0.98, 0.12, 0.16), warm, bev=0.01))
            continue
        if not frame:
            continue
        # Frame the street-facing gable only; the back triangle is never in
        # shot and every box there is ~500 tris of nothing.
        if sy < 0 and frontage == "gable":
            continue
        ty = y + sy * 0.15
        ap = rh - 0.10
        span = hw * 2.0
        # Close studding: a stud roughly every 0.62 m, each climbing to the
        # underside of the two rafters.  Three studs and a rail (the old
        # version) reads as a giant brown H pasted on the plaster - the single
        # most repeated "same building" motif on the street.
        n = max(3, int(span / 0.62))
        for k in range(n + 1):
            tx = -hw + span * k / n
            ht = ap * max(0.0, 1.0 - abs(tx) / hw)
            if ht < 0.34:
                continue
            out.append(K.box(name + "_gt%d_%d" % (sy, k), T @ Ts(tx, ty, eave + ht * 0.5),
                             (0.12, 0.10, ht - 0.06), timber, bev=0.008))
        # collar: the tie between the studs, clipped to the triangle at its height
        cz = eave + ap * 0.42
        cw = hw * (1.0 - 0.42) * 2.0 * 1.04
        out.append(K.box(name + "_gc%d" % sy, T @ Ts(0, ty, cz),
                         (cw, 0.11, 0.16), timber, bev=0.008))
        # two short raking braces into the collar.  Long ones from the eaves
        # up to mid-height turn the gable into a giant spider - the plainer
        # the triangle, the more the roof silhouette reads.
        for s in (-1, 1):
            x0, z0 = s * hw * 0.70, eave + 0.16
            x1, z1 = s * hw * 0.42, cz - 0.10
            ln = math.hypot(x1 - x0, z1 - z0)
            ang = math.atan2(x1 - x0, z1 - z0)
            out.append(K.box(name + "_gb%d_%d" % (sy, s), T @ Ts((x0 + x1) * 0.5, ty, (z0 + z1) * 0.5,
                                                                ry=-ang),
                             (0.12, 0.09, ln), timber, bev=0.006))
        if hw >= 2.8:
            # loft hatch: dark opening, timber frame, hoist beam above it.
            # Narrow gables skip it - a hatch on a 4 m triangle reads as a
            # brown square pasted on the plaster.
            hz = cz + 0.02
            out.append(K.box(name + "_gh%d" % sy, T @ Ts(0, ty + sy * 0.02, hz),
                             (0.50, 0.07, 0.64), _m(MAT_CACHE, "wood_dark"), bev=0.008))
            for s in (-1, 1):
                out.append(K.box(name + "_ghj%d_%d" % (sy, s), T @ Ts(s * 0.30, ty, hz),
                                 (0.10, 0.12, 0.78), timber))
            out.append(K.box(name + "_ghl%d" % sy, T @ Ts(0, ty, hz + 0.40),
                             (0.82, 0.12, 0.12), timber))
            # hoist beam + a brace under it: an unsupported stub projecting from
            # a gable reads as a stick stuck in the plaster, and the brace is
            # what turns it into a hay hoist
            out.append(K.box(name + "_ghb%d" % sy, T @ Ts(0, ty + sy * 0.22, hz + 0.54),
                             (0.11, 0.44, 0.11), timber))
            out.append(K.box(name + "_ghbr%d" % sy,
                             T @ Ts(0, ty + sy * 0.16, hz + 0.30, rx=D2R(sy * 42)),
                             (0.08, 0.52, 0.08), timber))
            out.append(K.cyl(name + "_ghp%d" % sy, T @ Ts(0, ty + sy * 0.40, hz + 0.44),
                             0.075, 0.09, _m(MAT_CACHE, "iron"), seg=8))
            out.append(K.cyl(name + "_ghr%d" % sy, T @ Ts(0, ty + sy * 0.40, hz - 0.06),
                             0.012, 0.90, _m(MAT_CACHE, "sand_dark"), seg=5))
    return out


# --------------------------------------------------------------------------
# 1. blacksmith - open colonnade, furnace stack, anvil
# --------------------------------------------------------------------------
def blacksmith(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 9.6, 7.6, 2.95, 0.42, 40
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    brick = _m(MAT, "brick")
    parts = []
    parts, z_eave, _ops = _shell("bs", T, w, d, 2, fh, pl, _m(MAT, "stone_dark"),
                                 stone, timber, glass,
                                 dark, open_front=True,
                                 u_wins={"n": 3, "w": 1.05, "h": 1.35, "z": 0.80,
                                         "mull": 2, "shutters": timber, "frame": True},
                                 back_wins=1, side_wins=1)
    # --- furnace against the interior back wall
    fx, fy = -2.15, d * 0.5 - 2.42
    parts.append(K.box("bs_forge", T @ Ts(fx, fy, pl + 0.62), (2.0, 0.90, 1.24), brick,
                       bev=0.02))
    parts.append(K.box("bs_fmouth", T @ Ts(fx, fy + 0.44, pl + 0.58), (1.10, 0.14, 0.72),
                       dark))
    parts.append(K.box("bs_fire", T @ Ts(fx, fy + 0.40, pl + 0.44), (0.92, 0.12, 0.34),
                       _m(MAT, "glow")))
    parts.append(K.box("bs_fhearth", T @ Ts(fx, fy + 0.78, pl + 0.06), (2.3, 0.80, 0.12),
                       stone, bev=0.02))
    # hood, tapering to the stack
    parts.append(K.cyl("bs_hood", T @ Ts(fx, fy, pl + 1.62), 0.78, 0.62, stone, seg=4,
                       r2=0.50))
    # --- the stack: a tall sooty brick chimney well above the ridge
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    parts += _chimney("bs_stack", T, fx, fy, pl + 1.55, ridge + 1.55, brick, w=1.05, pots=0)
    parts.append(K.box("bs_stack_c", T @ Ts(fx, fy, ridge + 1.66), (1.30, 1.30, 0.18), stone,
                       bev=0.02))
    # --- roof, sooty tiles, gable ends in plaster
    parts += _roof("bs_r", T, w, d, z_eave, pitch, _m(MAT, "tile_soot"),
                   _m(MAT, "wood_dark"), "eaves", end_mat=wall, ov_gable=0.46)
    parts += _gable_wall("bs_g", T, w, d, z_eave, _ridge_z(w, d, z_eave, pitch) - z_eave,
                         wall, timber, "eaves")
    # --- anvil on a stump, in front of the open bay
    ax, ay = 2.05, d * 0.5 + 0.55
    parts.append(K.cyl("bs_stump", T @ Ts(ax, ay, 0.30), 0.34, 0.60, _m(MAT, "wood"), seg=12))
    parts.append(K.box("bs_anvil", T @ Ts(ax, ay, 0.72), (0.86, 0.34, 0.24), _m(MAT, "iron"),
                       bev=0.02))
    parts.append(K.box("bs_anvil_b", T @ Ts(ax, ay, 0.58), (0.44, 0.26, 0.14),
                       _m(MAT, "iron")))
    parts.append(K.cyl("bs_horn", T @ Ts(ax + 0.52, ay, 0.72, ry=D2R(90)), 0.13, 0.42,
                       _m(MAT, "iron"), seg=8, r2=0.03))
    # quench barrel + water trough
    parts += H.barrel("bs_quench", T @ Ts(-3.55, d * 0.5 + 0.70, 0), r=0.34, h=0.92,
                      wood=_m(MAT, "wood"), hoop=_m(MAT, "iron"))
    parts.append(K.box("bs_trough", T @ Ts(3.85, d * 0.5 + 0.62, 0.26), (1.30, 0.62, 0.52),
                       _m(MAT, "wood"), bev=0.02))
    parts.append(K.box("bs_tw", T @ Ts(3.85, d * 0.5 + 0.62, 0.47), (1.18, 0.50, 0.10),
                       _m(MAT, "water")))
    # tool rack on the right post
    parts.append(K.box("bs_rack", T @ Ts(2.9, d * 0.5 - 0.34, pl + 1.55),
                       (0.10, 0.16, 1.30), _m(MAT, "wood")))
    for i in range(3):
        parts.append(K.box("bs_tool%d" % i, T @ Ts(2.9, d * 0.5 - 0.26, pl + 1.18 + i * 0.36),
                           (0.06, 0.08, 0.44), _m(MAT, "iron")))
    # hanging sign: a horseshoe on a bracket
    parts += _sign("bs_sg", T, 0.62, 0.62, _m(MAT, "wood"), _m(MAT, "iron"),
                   arm_len=1.05, z=3.55, x=w * 0.5 - 0.55)
    for i, a in enumerate((-1.25, -0.85, -0.45, 0.45, 0.85, 1.25)):
        parts.append(K.box("bs_hs%d" % i,
                           T @ Ts(w * 0.5 - 0.55 + math.sin(a) * 0.24, 1.62,
                                  3.55 - 0.60 + math.cos(a) * 0.24, ry=-a),
                           (0.10, 0.07, 0.20), _m(MAT, "iron")))
    return parts


# --------------------------------------------------------------------------
# 2. adventurers' guild - portico, banner, crenellated turret
# --------------------------------------------------------------------------
def adventurers_guild(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 11.0, 9.0, 3.25, 0.46, 44
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    red = _m(MAT, "cloth_red")
    gold = _m(MAT, "cloth_gold")
    parts = []
    dh = 2.55
    holes = [(0.0, 2.05, pl, dh + 0.65)]
    parts, z_eave, _ops = _shell("ag", T, w, d, 2, fh, pl, stone, stone, timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 2, "w": 1.05, "h": 1.55, "z": 0.55,
                                         "mull": 2, "hood": True},
                                 u_wins={"n": 5, "w": 1.10, "h": 1.70, "z": 0.80,
                                         "mull": 3, "hood": True},
                                 back_wins=2, side_wins=2)
    parts += _door("ag_dr", T, 0.0, d * 0.5, pl, 2.05, dh + 0.55, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=3)
    # --- portico: two columns + entablature over the door
    for s in (-1, 1):
        parts.append(K.cyl("ag_col%d" % s, T @ Ts(s * 1.65, d * 0.5 + 1.15, pl + 1.65),
                           0.26, 3.30, stone, seg=16, r2=0.22))
        parts.append(K.box("ag_colb%d" % s, T @ Ts(s * 1.65, d * 0.5 + 1.15, pl + 0.09),
                           (0.70, 0.70, 0.18), stone, bev=0.02))
        parts.append(K.box("ag_colc%d" % s, T @ Ts(s * 1.65, d * 0.5 + 1.15, pl + 3.30),
                           (0.66, 0.66, 0.20), stone, bev=0.02))
    parts.append(K.box("ag_arch", T @ Ts(0, d * 0.5 + 1.15, pl + 3.62), (4.30, 1.35, 0.44),
                       stone, bev=0.03))
    parts.append(K.box("ag_arch2", T @ Ts(0, d * 0.5 + 1.15, pl + 3.92), (4.00, 1.15, 0.22),
                       _m(MAT, "stone_warm"), bev=0.02))
    # --- notice board beside the door
    parts.append(K.box("ag_nb", T @ Ts(3.35, d * 0.5 + 0.10, pl + 1.62), (1.55, 0.10, 1.05),
                       _m(MAT, "wood"), bev=0.012))
    parts.append(K.box("ag_nbp", T @ Ts(3.35, d * 0.5 + 0.02, pl + 1.62), (1.35, 0.08, 0.85),
                       _m(MAT, "plaster_white")))
    for i in range(3):
        parts.append(K.box("ag_np%d" % i, T @ Ts(3.35 + (i - 1) * 0.42, d * 0.5 + 0.09,
                                                 pl + 1.86 - (i % 2) * 0.30),
                           (0.34, 0.02, 0.40), _m(MAT, "plaster")))
    parts.append(K.box("ag_nbr", T @ Ts(3.35, d * 0.5 + 0.16, pl + 2.02), (1.62, 0.14, 0.12),
                       timber))
    # --- guild arms above the door + two banners
    parts += C.shield("ag_sh", T @ Ts(0, d * 0.5 + 0.20, pl + 4.62), 1.05, 1.30, red,
                      border=gold)
    for s in (-1, 1):
        parts += H.banner("ag_bn%d" % s, T @ Ts(s * 4.30, d * 0.5 + 0.22, pl + 4.10),
                          0.80, 1.90, red, _m(MAT, "iron"), pole_h=0.5)
    # --- corner turret with crenellation, rear-right, above the ridge
    tr = 1.55
    tx0, ty0 = w * 0.5 - 1.35, -d * 0.5 + 1.55
    tz = z_eave + 1.35
    parts.append(K.cyl("ag_tw", T @ Ts(tx0, ty0, tz * 0.5 + 0.9), tr, tz, stone, seg=24))
    parts.append(K.cyl("ag_twc", T @ Ts(tx0, ty0, tz + 0.9), tr + 0.24, 0.34, stone, seg=24))
    nm = 14
    for i in range(nm):
        a = math.tau * i / nm
        parts.append(K.box("ag_mr%d" % i,
                           T @ Ts(tx0 + math.cos(a) * (tr + 0.10),
                                  ty0 + math.sin(a) * (tr + 0.10), tz + 1.38, rz=a),
                           (0.46, 0.42, 0.62), stone, bev=0.015))
    # --- roof + dormers
    parts += _roof("ag_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), _m(MAT, "wood_dark"),
                   "eaves", end_mat=stone)
    rh = _ridge_z(w, d, z_eave, pitch) - z_eave
    parts += _gable_wall("ag_g", T, w, d, z_eave, rh, stone, timber, "eaves")
    for i, sx in enumerate((-2.6, 2.6)):
        dy = d * 0.5 * 0.52
        parts += H.dormer("ag_do%d" % i,
                          T @ Ts(sx, dy, _slope_z(w, d, z_eave, pitch, dy) - 0.20),
                          w=1.15, h=1.30, d=1.0, pitch=50, wall=stone,
                          roof_mat=_m(MAT, "slate"), frame=timber, glass=glass)
    return parts


# --------------------------------------------------------------------------
# 3. magic shop - narrow, turret + cone spire, glowing windows
# --------------------------------------------------------------------------
def magic_shop(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 6.4, 6.8, 3.05, 0.40, 50
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass_magic")
    dark = _m(MAT, "void")
    purple = _m(MAT, "cloth_purple")
    parts = []
    dh = 2.35
    holes = [(-0.55, 1.30, pl, dh + 0.50)]
    parts, z_eave, _ops = _shell("mg", T, w, d, 3, fh, pl, _m(MAT, "stone_dark"),
                                 _m(MAT, "stone_dark"), timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 2, "w": 1.00, "h": 1.50, "z": 0.60,
                                         "mull": 2, "hood": True, "lit": _m(MAT, "glass_magic")},
                                 u_wins={"n": 2, "w": 1.00, "h": 1.42, "z": 0.78,
                                         "mull": 2, "shutters": None},
                                 back_wins=0, side_wins=1, lit=_m(MAT, "glass_magic"))
    parts += _door("mg_dr", T, -0.55, d * 0.5, pl, 1.30, dh + 0.40, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=2)
    # --- corner turret, ground to above the ridge, with a cone spire
    tx, ty = w * 0.5 - 0.55, d * 0.5 - 0.55
    rh = _ridge_z(w, d, z_eave, pitch) - z_eave
    th_t = z_eave + rh * 0.55
    parts.append(K.cyl("mg_tw", T @ Ts(tx, ty, th_t * 0.5 + 0.30), 1.30, th_t,
                       _m(MAT, "stone_dark"), seg=22))
    parts.append(K.cyl("mg_tc", T @ Ts(tx, ty, th_t + 0.30), 1.52, 0.30, stone, seg=22))
    parts += H.spire("mg_sp", T @ Ts(tx, ty, th_t + 0.30), 1.45, 3.4,
                     _m(MAT, "slate"), seg=10, base_z=0.0)
    parts.append(K.sphere("mg_fin", T @ Ts(tx, ty, th_t + 3.95), 0.20, _m(MAT, "gold"), seg=14))
    # --- bay window on the first floor
    by = d * 0.5 + 0.42
    bz = pl + fh + 0.86
    parts.append(K.box("mg_bay", T @ Ts(-0.35, by, bz + 0.62), (2.10, 0.95, 1.55),
                       _m(MAT, "stone_dark"), bev=0.02))
    parts += _win("mg_bayg", T @ Ts(-0.35, by + 0.50, bz + 0.62), 1.55, 1.15, stone,
                  glass, dark, th=0.24, mull=2, sill=False, lit=_m(MAT, "glass_magic"))
    parts.append(K.box("mg_bayr", T @ Ts(-0.35, by, bz + 1.48), (2.40, 1.15, 0.16), stone,
                       bev=0.02))
    # --- armillary sign: three rings + a gilded core
    sx = w * 0.5 + 0.05
    parts.append(K.box("mg_arm", T @ Ts(sx, 0.55, pl + 2.95), (0.08, 1.10, 0.08),
                       _m(MAT, "iron")))
    for i, rz in enumerate((0, 60, 120)):
        parts.append(K.box("mg_ring%d" % i,
                           T @ Ts(sx, 0.95, pl + 3.42, ry=D2R(rz)), (0.44, 0.44, 0.05),
                           _m(MAT, "gold")))
    parts.append(K.sphere("mg_core", T @ Ts(sx, 0.95, pl + 3.42), 0.13, _m(MAT, "glow_magic"),
                          seg=12))
    # hanging herb bundles + a cauldron at the door
    for i in range(3):
        parts.append(K.box("mg_herb%d" % i, T @ Ts(-1.85 + i * 0.30, d * 0.5 + 0.42,
                                                   pl + 2.55), (0.20, 0.16, 0.55),
                           _m(MAT, "leaf")))
    parts.append(K.cyl("mg_cauld", T @ Ts(1.35, d * 0.5 + 0.62, 0.34), 0.42, 0.62,
                       _m(MAT, "iron"), seg=14, r2=0.50))
    parts.append(K.cyl("mg_cauld2", T @ Ts(1.35, d * 0.5 + 0.62, 0.68), 0.44, 0.10,
                       _m(MAT, "glow_magic"), seg=14))
    # --- roof: gable front so the spire and the gable read together
    parts += _roof("mg_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall, ov_gable=0.40)
    parts += _gable_wall("mg_g", T, w, d, z_eave, rh, wall, timber, "eaves")
    return parts


# --------------------------------------------------------------------------
# 4. clothier - dense half-timber, awning, clothes rail, shears sign
# --------------------------------------------------------------------------
def clothier(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 6.8, 7.0, 2.95, 0.40, 46
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_rose")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    parts = []
    holes = [(-1.35, 1.20, pl, 2.45)]
    parts, z_eave, _ops = _shell("cl", T, w, d, 2, fh, pl, _m(MAT, "plaster_rose"),
                                 stone, timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 1, "w": 1.05, "h": 1.30, "z": 1.05,
                                         "mull": 2, "hood": False, "shutters": timber},
                                 u_wins={"n": 3, "w": 0.98, "h": 1.30, "z": 0.85,
                                         "mull": 2, "shutters": timber, "frame": True,
                                         "stud": 0.92},
                                 back_wins=1, side_wins=1)
    parts += _door("cl_dr", T, -1.35, d * 0.5, pl, 1.20, 2.35, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=2)
    # shop window: a wide lit bay beside the door
    ow = 2.10
    parts.append(K.box("cl_shopw", T @ Ts(0.95, d * 0.5 + 0.06, pl + 1.30),
                       (ow + 0.5, 0.28, 1.95), _m(MAT, "stone_dark"), bev=0.02))
    parts += _win("cl_sg", T @ Ts(0.95, d * 0.5 + 0.05, pl + 1.30), ow, 1.55, stone,
                      _m(MAT, "glass_warm"), dark, th=0.26, mull=2, hood=False,
                      lit=_m(MAT, "glass_warm"))
    # striped awning over the front
    parts += _awning(T, w - 0.5, d * 0.5 + 0.30, pl + 2.62, depth=1.75,
                     mat_a=_m(MAT, "cloth_red"), mat_b=_m(MAT, "plaster"), stripe=6)
    # clothes rail with hanging garments
    ry = d * 0.5 + 1.15
    parts.append(K.box("cl_rail", T @ Ts(0.95, ry, pl + 2.30), (2.9, 0.07, 0.07),
                       _m(MAT, "iron")))
    for i, cm in enumerate(("cloth_blue", "cloth_green", "cloth_purple", "cloth_gold",
                            "cloth_red")):
        x = -0.45 + i * 0.62
        parts.append(K.box("cl_gar%d" % i, T @ Ts(x, ry, pl + 1.86),
                           (0.50, 0.06, 0.86), _m(MAT, cm), bev=0.01))
    # fabric rolls on the sill
    for i in range(3):
        parts.append(K.cyl("cl_roll%d" % i,
                           T @ Ts(0.35 + i * 0.52, d * 0.5 + 0.42, pl + 0.46,
                                  ry=D2R(90)),
                           0.13, 0.52, _m(MAT, ("cloth_red", "cloth_blue", "cloth_gold")[i]),
                           seg=10))
    # shears sign
    parts.append(K.box("cl_arm", T @ Ts(w * 0.5 - 0.35, 0.60, pl + 2.95),
                       (0.07, 1.20, 0.07), _m(MAT, "iron")))
    for s in (-1, 1):
        parts.append(K.box("cl_blade%d" % s,
                           T @ Ts(w * 0.5 - 0.35, 1.05, pl + 2.52, ry=D2R(s * 22)),
                           (0.05, 0.26, 0.86), _m(MAT, "iron")))
        parts.append(K.cyl("cl_ring%d" % s, T @ Ts(w * 0.5 - 0.35, 1.05, pl + 2.92),
                           0.13, 0.05, _m(MAT, "iron"), seg=10))
    # bench + basket by the door
    parts += _bench(T, -2.55, d * 0.5 + 0.62, 0, _m(MAT, "wood"), L=1.35)
    parts += _basket(T, 2.75, d * 0.5 + 0.55, 0, _m(MAT, "wood_light"))
    parts += _roof("cl_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "eaves",
                   end_mat=wall)
    parts += _gable_wall("cl_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch) - z_eave, wall, timber, "eaves")
    return parts


# --------------------------------------------------------------------------
# 5. general store - wide front, ridge monitor, hoist beam
# --------------------------------------------------------------------------
def general_store(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 10.8, 8.0, 3.05, 0.42, 42
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_ochre")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    parts = []
    holes = [(-2.6, 1.55, pl, 2.50), (1.9, 2.85, pl, 2.55)]
    parts, z_eave, _ops = _shell("gs", T, w, d, 2, fh, pl, _m(MAT, "plaster_ochre"),
                                 stone, timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 0, "w": 1.0, "h": 1.3, "z": 1.0},
                                 u_wins={"n": 4, "w": 1.05, "h": 1.35, "z": 0.85,
                                         "mull": 2, "shutters": timber},
                                 back_wins=2, side_wins=2)
    parts += _door("gs_dr", T, -2.6, d * 0.5, pl, 1.55, 2.40, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=2)
    # open loading bay with a counter
    parts.append(K.box("gs_bay", T @ Ts(1.9, d * 0.5 - 0.06, pl + 1.28),
                       (2.85, 0.30, 2.55), dark))
    parts.append(K.box("gs_cnt", T @ Ts(1.9, d * 0.5 + 0.30, pl + 0.48),
                       (2.75, 0.80, 0.14), _m(MAT, "wood"), bev=0.02))
    for s in (-1, 1):
        parts.append(K.box("gs_cl%d" % s, T @ Ts(1.9 + s * 1.25, d * 0.5 + 0.30, pl + 0.24),
                           (0.14, 0.70, 0.48), _m(MAT, "wood")))
    parts.append(K.box("gs_lint", T @ Ts(1.9, d * 0.5 + 0.10, pl + 2.66),
                       (3.10, 0.42, 0.22), _m(MAT, "wood"), bev=0.02))
    # ridge monitor with louvres
    ridge = _ridge_z(w, d, z_eave, pitch)
    parts.append(K.box("gs_mon", T @ Ts(0, 0, ridge + 0.34), (2.10, 1.40, 1.05), wall,
                       bev=0.02))
    parts.append(K.box("gs_monb", T @ Ts(0, 0, ridge + 0.94), (2.30, 1.60, 0.16),
                       _m(MAT, "wood_dark"), bev=0.02))
    for i, sy in enumerate((-1, 1)):
        for k in range(4):
            parts.append(K.box("gs_lv%d_%d" % (i, k),
                               T @ Ts(0, sy * 0.72, ridge + 0.16 + k * 0.20),
                               (1.80, 0.10, 0.15), _m(MAT, "wood_dark"), bev=0.006))
    for s in (-1, 1):
        parts.append(K.box("gs_monr%d" % s, T @ Ts(s * 1.10, 0, ridge + 0.62),
                           (0.14, 1.70, 0.90), _m(MAT, "wood_dark"), bev=0.012))
    # hoist beam + pulley from the front gable
    parts.append(K.box("gs_hoist", T @ Ts(w * 0.5 - 1.2, d * 0.5 + 0.85, z_eave + 0.95),
                       (0.20, 2.10, 0.22), _m(MAT, "wood"), bev=0.012))
    parts.append(K.cyl("gs_pul", T @ Ts(w * 0.5 - 1.2, d * 0.5 + 1.75, z_eave + 0.72,
                                       ry=D2R(90)),
                       0.17, 0.10, _m(MAT, "iron"), seg=12))
    parts.append(K.box("gs_rope", T @ Ts(w * 0.5 - 1.2, d * 0.5 + 1.75, z_eave + 0.10),
                       (0.04, 0.04, 1.20), _m(MAT, "iron")))
    # clutter: barrels, crates, sacks
    parts += H.barrel("gs_b1", T @ Ts(-4.35, d * 0.5 + 0.62, 0), r=0.32, h=0.88,
                      wood=_m(MAT, "wood"), hoop=_m(MAT, "iron"))
    parts += H.barrel("gs_b2", T @ Ts(-3.70, d * 0.5 + 0.95, 0), r=0.30, h=0.80,
                      wood=_m(MAT, "wood"), hoop=_m(MAT, "iron"))
    parts += H.crate("gs_c1", T @ Ts(4.35, d * 0.5 + 0.55, 0.31), s=0.62,
                     wood=_m(MAT, "wood"))
    parts += H.crate("gs_c2", T @ Ts(4.35, d * 0.5 + 0.55, 0.93), s=0.56,
                     wood=_m(MAT, "wood"))
    parts += _sack(T, -2.05, d * 0.5 + 0.52, 0, _m(MAT, "sand"))
    parts += _sack(T, -1.55, d * 0.5 + 0.72, 0, _m(MAT, "sand"))
    parts += _roof("gs_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "eaves",
                   end_mat=wall)
    parts += _gable_wall("gs_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "eaves")
    return parts


# --------------------------------------------------------------------------
# 6. tavern - two storeys + attic, double-sided sign, lantern string
# --------------------------------------------------------------------------
def tavern(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 10.4, 9.4, 3.10, 0.44, 46
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    warm = _m(MAT, "glass_warm")
    parts = []
    holes = [(-2.9, 1.45, pl, 2.45), (2.9, 1.15, pl, 2.20)]
    parts, z_eave, _ops = _shell("tv", T, w, d, 3, fh, pl, wall, stone, timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 2, "w": 1.10, "h": 1.45, "z": 0.95,
                                         "mull": 3, "hood": True, "lit": warm},
                                 u_wins={"n": 4, "w": 1.00, "h": 1.30, "z": 0.85,
                                         "mull": 2, "shutters": timber, "frame": True,
                                         "lit": warm},
                                 back_wins=2, side_wins=2)
    parts += _door("tv_dr", T, -2.9, d * 0.5, pl, 1.45, 2.35, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=2)
    parts += _door("tv_sd", T, 2.9, d * 0.5, pl, 1.15, 2.10, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=1, double=False)
    # --- big double-sided sign on a long iron bracket
    parts.append(K.box("tv_bk", T @ Ts(-0.75, 1.05, pl + 3.05), (0.10, 2.10, 0.10),
                       _m(MAT, "iron")))
    parts.append(K.box("tv_bk2", T @ Ts(-0.75, 0.12, pl + 2.50), (0.08, 0.08, 1.10),
                       _m(MAT, "iron")))
    for s in (-1, 1):
        parts.append(K.box("tv_sgn%d" % s, T @ Ts(-0.75, 1.80, pl + 2.42 + s * 0.0),
                           (1.55, 0.09, 0.95), _m(MAT, "cloth_gold"), bev=0.012))
    parts.append(K.box("tv_sgnf", T @ Ts(-0.75, 1.80, pl + 2.42), (1.75, 0.14, 1.12),
                       _m(MAT, "wood"), bev=0.014))
    parts += H.statue("tv_cup", T @ Ts(-0.75, 1.86, pl + 3.48), 0.42, _m(MAT, "gold"))
    # lantern string across the front
    for i in range(7):
        x = -w * 0.5 + 1.0 + (w - 2.0) * i / 6.0
        z = pl + 2.92 - 0.28 * math.sin(math.pi * i / 6.0)
        parts.append(K.box("tv_wire%d" % i, T @ Ts(x, d * 0.5 + 1.30, z + 0.16),
                           (1.35, 0.03, 0.03), _m(MAT, "iron")))
        parts.append(K.box("tv_lant%d" % i, T @ Ts(x, d * 0.5 + 1.30, z - 0.04),
                           (0.20, 0.20, 0.30), _m(MAT, "glow_warm")))
        parts.append(K.box("tv_lantc%d" % i, T @ Ts(x, d * 0.5 + 1.30, z + 0.14),
                           (0.24, 0.24, 0.05), _m(MAT, "iron")))
    # two chimneys on the slope
    for i, (cx, cy) in enumerate(((-2.0, -1.2), (2.4, 0.9))):
        parts += _chimney("tv_ch%d" % i, T, cx, cy, z_eave - 1.2,
                          _ridge_z(w, d, z_eave, pitch) + 0.95, stone, w=0.80, pots=1)
    # barrels + bench + vine
    parts += H.barrel("tv_b1", T @ Ts(-4.55, d * 0.5 + 0.62, 0), r=0.34, h=0.92,
                      wood=_m(MAT, "wood"), hoop=_m(MAT, "iron"))
    parts += H.barrel("tv_b2", T @ Ts(4.55, d * 0.5 + 0.72, 0), r=0.32, h=0.86,
                      wood=_m(MAT, "wood"), hoop=_m(MAT, "iron"))
    parts += _bench(T, 1.15, d * 0.5 + 0.60, 0, _m(MAT, "wood"), L=1.9)
    for i in range(4):
        parts.append(K.box("tv_vine%d" % i, T @ Ts(-w * 0.5 - 0.05, -1.2 + i * 1.1,
                                                   z_eave - 0.3 - (i % 2) * 0.25),
                           (0.22, 0.9, 0.22), _m(MAT, "leaf")))
    parts += _roof("tv_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "eaves",
                   end_mat=wall)
    parts += _gable_wall("tv_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch) - z_eave, wall, timber, "eaves")
    return parts


# --------------------------------------------------------------------------
# 7. bakery - white plaster, dome oven, bread rack
# --------------------------------------------------------------------------
def bakery(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 7.8, 7.2, 2.95, 0.40, 44
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_white")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    brick = _m(MAT, "brick")
    parts = []
    holes = [(-1.5, 1.30, pl, 2.40), (1.6, 1.85, pl, 1.55)]
    parts, z_eave, _ops = _shell("bk", T, w, d, 2, fh, pl, wall, stone, timber, glass,
                                 dark, g_holes=holes,
                                 g_wins={"n": 0, "w": 1.0, "h": 1.3, "z": 1.0},
                                 u_wins={"n": 3, "w": 1.00, "h": 1.28, "z": 0.85,
                                         "mull": 2, "shutters": timber, "frame": True},
                                 back_wins=1, side_wins=1)
    parts += _door("bk_dr", T, -1.5, d * 0.5, pl, 1.30, 2.30, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=2)
    # bread window: a deep lit counter opening
    parts.append(K.box("bk_cw", T @ Ts(1.6, d * 0.5 - 0.10, pl + 0.90),
                       (1.85, 0.55, 1.55), dark))
    parts.append(K.box("bk_cwc", T @ Ts(1.6, d * 0.5 + 0.16, pl + 0.86),
                       (1.95, 0.30, 0.12), _m(MAT, "wood"), bev=0.012))
    for i in range(5):
        parts.append(K.sphere("bk_loaf%d" % i,
                              T @ Ts(0.95 + i * 0.34, d * 0.5 + 0.16, pl + 1.02),
                              0.13, _m(MAT, "wood_light"), seg=10, squash=0.75))
    # --- dome oven on the right, with its flue
    ox, oy = w * 0.5 + 1.55, d * 0.5 - 2.2
    parts.append(K.box("bk_oven", T @ Ts(ox, oy, 0.72), (2.60, 2.60, 1.44), brick, bev=0.02))
    parts.append(K.sphere("bk_dome", T @ Ts(ox, oy, 1.46), 1.28, brick, seg=20, ring=10,
                          squash=0.62))
    parts.append(K.box("bk_omouth", T @ Ts(ox, oy + 1.20, 0.98), (0.95, 0.22, 0.80), dark))
    parts.append(K.box("bk_oglow", T @ Ts(ox, oy + 1.16, 0.72), (0.80, 0.12, 0.28),
                       _m(MAT, "glow")))
    parts += _chimney("bk_flue", T, ox, oy, 2.10, z_eave + 1.30, brick, w=0.62, pots=0)
    # smoke hood over the bread counter
    parts.append(K.box("bk_hood", T @ Ts(1.6, d * 0.5 - 0.40, z_eave - 0.55),
                       (2.20, 1.40, 0.90), _m(MAT, "wood_dark"), bev=0.02))
    parts.append(K.box("bk_hoodm", T @ Ts(1.6, d * 0.5 - 0.40, z_eave - 0.10),
                       (2.50, 1.60, 0.16), _m(MAT, "wood_dark"), bev=0.02))
    # bread rack outside
    for i in range(2):
        parts.append(K.box("bk_rk%d" % i, T @ Ts(3.35, d * 0.5 + 0.62, 0.60 + i * 0.52),
                           (1.55, 0.42, 0.07), _m(MAT, "wood"), bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("bk_rkl%d" % s, T @ Ts(3.35 + s * 0.70, d * 0.5 + 0.62, 0.55),
                           (0.09, 0.40, 1.10), _m(MAT, "wood")))
    for i in range(6):
        parts.append(K.sphere("bk_br%d" % i,
                              T @ Ts(3.05 + (i % 3) * 0.32, d * 0.5 + 0.62,
                                     0.70 + (i // 3) * 0.52),
                              0.12, _m(MAT, "wood_light"), seg=8, squash=0.72))
    parts += _awning(T, 3.0, d * 0.5 + 0.35, pl + 2.50, depth=1.35,
                     mat_a=_m(MAT, "cloth_gold"), mat_b=_m(MAT, "plaster_white"), stripe=4)
    parts += _roof("bk_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "eaves",
                   end_mat=wall)
    parts += _gable_wall("bk_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch) - z_eave, wall, timber, "eaves")
    return parts


# --------------------------------------------------------------------------
# 8. stable - open stalls, hayloft, trough
# --------------------------------------------------------------------------
def stable(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 11.5, 8.4, 2.85, 0.34, 40
    stone = _m(MAT, "stone")
    wall = _m(MAT, "wood")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    parts = []
    parts, z_eave, _ops = _shell("st", T, w, d, 2, fh, pl, _m(MAT, "wood"),
                                 _m(MAT, "wood_dark"), timber, glass,
                                 dark, open_front=True,
                                 u_wins={"n": 2, "w": 0.95, "h": 1.05, "z": 1.10,
                                         "mull": 2, "shutters": None},
                                 back_wins=0, side_wins=0)
    # stall partitions inside the open bay
    for i, x in enumerate((-3.4, -1.15, 1.15, 3.4)):
        parts.append(K.box("st_part%d" % i, T @ Ts(x, d * 0.5 - 1.35, pl + 1.05),
                           (0.16, 2.55, 2.10), _m(MAT, "wood")))
        parts.append(K.box("st_post%d" % i, T @ Ts(x, d * 0.5 - 0.14, pl + 1.05),
                           (0.18, 0.18, 2.10), _m(MAT, "wood")))
    # hayloft door in the gable above the stalls
    parts.append(K.box("st_hi", T @ Ts(0, d * 0.5 + 0.05, z_eave + 1.15),
                       (1.55, 0.14, 1.70), _m(MAT, "wood_dark"), bev=0.01))
    parts.append(K.box("st_hib", T @ Ts(0, d * 0.5 + 0.02, z_eave + 1.15),
                       (1.75, 0.10, 1.90), timber, bev=0.012))
    parts.append(K.box("st_hb", T @ Ts(0, d * 0.5 + 0.95, z_eave + 2.35),
                       (0.18, 1.90, 0.18), _m(MAT, "wood")))
    parts.append(K.box("st_hbf", T @ Ts(0, d * 0.5 + 0.02, z_eave + 2.62),
                       (1.95, 0.12, 0.22), _m(MAT, "wood")))
    # trough + hitching rail + hay bales
    parts.append(K.box("st_trough", T @ Ts(-4.55, d * 0.5 + 0.85, 0.30),
                       (1.90, 0.70, 0.58), _m(MAT, "wood"), bev=0.02))
    parts.append(K.box("st_tw", T @ Ts(-4.55, d * 0.5 + 0.85, 0.55),
                       (1.75, 0.56, 0.10), _m(MAT, "water")))
    for i in range(3):
        parts.append(K.cyl("st_hitch%d" % i, T @ Ts(1.9 + i * 1.6, d * 0.5 + 1.25, 0.62),
                           0.09, 1.24, _m(MAT, "wood"), seg=8))
    parts.append(K.box("st_hrail", T @ Ts(3.5, d * 0.5 + 1.25, 1.18),
                       (3.60, 0.10, 0.10), _m(MAT, "wood")))
    parts += H.haystack("st_hay", T @ Ts(4.75, d * 0.5 + 1.05, 0), r=1.05, h=1.35,
                        mat=_m(MAT, "thatch"))
    parts += H.cart("st_cart", T @ Ts(-w * 0.5 - 2.4, d * 0.5 - 0.6, 0),
                    _m(MAT, "wood"), _m(MAT, "iron"))
    parts += _roof("st_r", T, w, d, z_eave, pitch, _m(MAT, "thatch"), timber, "eaves",
                   end_mat=wall, course_h=0.55)
    parts += _gable_wall("st_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch) - z_eave, wall, timber, "eaves")
    # tack wall: pegs, two saddles and a coil of rope, straight on the front
    # posts.  A stable with bare walls is a shed.
    for i in range(5):
        tx = -w * 0.5 + 1.05 + i * 0.58
        parts.append(K.box("st_tk%d" % i, T @ Ts(tx, d * 0.5 - 0.34, 1.86),
                           (0.08, 0.16, 0.08), timber, bev=0.005))
        parts.append(K.box("st_tkf%d" % i, T @ Ts(tx, d * 0.5 - 0.26, 1.74),
                           (0.16, 0.05, 0.14), _m(MAT, "iron"), bev=0.005))
    for s in (-1, 1):
        parts.append(K.box("st_sdl%d" % s, T @ Ts(w * 0.5 - 1.40 + s * 0.62,
                                                  d * 0.5 - 0.30, 2.16),
                           (0.62, 0.22, 0.30), _m(MAT, "wood_dark"), bev=0.02))
        parts.append(K.box("st_sdls%d" % s, T @ Ts(w * 0.5 - 1.40 + s * 0.62,
                                                   d * 0.5 - 0.34, 1.98),
                           (0.30, 0.12, 0.22), _m(MAT, "wood_dark"), bev=0.014))
    parts.append(K.cyl("st_rope", T @ Ts(-w * 0.5 + 1.60, d * 0.5 - 0.26, 1.42, rx=D2R(90)),
                       0.17, 0.18, _m(MAT, "sand_dark"), seg=10))
    return parts


# --------------------------------------------------------------------------
# 9. chapel - pointed portal, rose window, bell turret
# --------------------------------------------------------------------------
def chapel(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 8.8, 13.5, 6.20, 0.44, 52
    stone = _m(MAT, "stone_warm")
    wall = _m(MAT, "plaster_white")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    parts = []
    dh = 3.10
    holes = [(0.0, 2.10, pl, dh + 0.80)]
    parts, z_eave, _ops = _shell("ch", T, w, d, 1, fh, pl, stone, stone, timber, glass,
                                 dark, g_holes=holes, back_wins=0, side_wins=0)
    parts += _door("ch_dr", T, 0.0, d * 0.5, pl, 2.10, dh + 0.70, _m(MAT, "wood"),
                   _m(MAT, "iron"), stone, steps=3)
    # --- pointed portal: three diminishing arches
    for i, (rr, dd) in enumerate(((2.35, 0.34), (2.70, 0.26), (3.05, 0.20))):
        for s in (-1, 1):
            parts.append(K.box("ch_av%d_%d" % (i, s),
                               T @ Ts(s * 1.30, d * 0.5 + 0.10 + i * 0.10, pl + dh + 0.95),
                               (0.34, dd, 1.70), stone, bev=0.02))
        parts.append(K.box("ch_ah%d" % i, T @ Ts(0, d * 0.5 + 0.10 + i * 0.10,
                                                 pl + dh + 1.72),
                           (rr * 1.10, dd, 0.30), stone, bev=0.02))
    # --- rose window above the portal
    parts += H.rose_window("ch_rose", T @ Ts(0, d * 0.5 - 0.02, pl + dh + 3.20), 1.45,
                           stone, glass, lobes=12, depth=0.50, seg=32)
    # --- corner buttresses
    for s in (-1, 1):
        parts += H.buttress("ch_bt%d" % s, T @ Ts(s * (w * 0.5 - 0.30), d * 0.5 - 0.30, 0),
                            fh + 1.0, 0.95, stages=4, mat=stone)
        parts += H.buttress("ch_bs%d" % s, T @ Ts(s * (w * 0.5 - 0.30), -(d * 0.5 - 0.30), 0),
                            fh * 0.8, 0.85, stages=3, mat=stone)
    # --- lancet windows down both flanks
    for i, yy in enumerate((-3.6, -0.9, 1.8)):
        for s in (-1, 1):
            parts += _win("ch_ln%d_%d" % (i, s),
                          T @ Ts(s * (w * 0.5 + 0.01), yy, pl + 3.30, rz=D2R(90 * s)),
                          0.85, 2.30, stone, glass, dark, th=0.36, mull=1,
                          transom=0, lit=_m(MAT, "glass_warm"))
    # --- bell turret at the front ridge
    ridge = _ridge_z(w, d, z_eave, pitch, "gable")
    bz = z_eave + (ridge - z_eave) * 0.62
    for s in (-1, 1):
        for t in (-1, 1):
            parts.append(K.box("ch_bp%d_%d" % (s, t), T @ Ts(s * 0.85, t * 0.85, bz + 1.10),
                               (0.28, 0.28, 2.20), stone, bev=0.012))
    parts.append(K.box("ch_bpl", T @ Ts(0, 0, bz + 2.20), (2.30, 2.30, 0.26), stone, bev=0.02))
    parts.append(K.cyl("ch_bell", T @ Ts(0, 0, bz + 1.95), 0.46, 0.70, _m(MAT, "brass"),
                       seg=14, r2=0.30))
    parts += H.spire("ch_bsp", T @ Ts(0, 0, bz + 2.33), 1.75, 2.30, _m(MAT, "slate"), seg=8)
    parts.append(K.cyl("ch_cross_v", T @ Ts(0, 0, bz + 4.80), 0.06, 0.80, _m(MAT, "gold"), seg=8))
    parts.append(K.box("ch_cross_h", T @ Ts(0, 0, bz + 4.95), (0.60, 0.08, 0.08),
                       _m(MAT, "gold")))
    # --- roof, gable to the street
    parts += _roof("ch_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "gable",
                   end_mat=wall, ov_gable=0.40)
    parts += _gable_wall("ch_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "gable")
    return parts


def _flat(parts):
    """Flatten a parts list that may contain nested lists.

    Some kit helpers (notably hd_common.buttress) append a helper's *list* into
    their own list, so a naive `parts += kit_fn()` leaves a list-of-lists that
    hd_common.bbox chokes on.  Flattening once at the boundary keeps every
    builder simple.
    """
    out = []
    for p in parts:
        if isinstance(p, (list, tuple)):
            out += _flat(p)
        else:
            out.append(p)
    return out


# --------------------------------------------------------------------------
# 10. training_ground - a walled yard: targets, pells, rack, viewing stand
#
# The brief for the军事 batch was "a different SILHOUETTE first": this one has
# no roof at all, which is exactly why it sits next to barracks and halls and
# still reads as its own building from 100 m.
# --------------------------------------------------------------------------
def training_ground(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d = 15.0, 12.5
    stone = _m(MAT, "stone")
    stone_d = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood")
    iron = _m(MAT, "iron")
    sand = _m(MAT, "sand")
    parts = []
    # sand pit for the melee ring, kerbed in stone.  A single flat slab of sand
    # reads as a pale carpet with a hard edge, so the surface is broken up with
    # raked ridges and a couple of scuffed patches.
    parts.append(K.box("tg_pit", T @ Ts(0, 1.2, 0.04), (w * 0.44, d * 0.34, 0.10), sand))
    for i in range(7):
        ry = 1.2 - d * 0.17 + 0.42 + i * (d * 0.34 - 0.84) / 6.0
        parts.append(K.box("tg_rake%d" % i, T @ Ts(-w * 0.44 * 0.5 + 0.35, ry, 0.098),
                           (w * 0.44 - 0.70, 0.12, 0.03), sand, bev=0.006))
    for i, (sx, sy, sr) in enumerate(((-2.9, 2.6, 0.62), (1.6, 3.4, 0.44), (3.2, 0.2, 0.52))):
        parts.append(K.cyl("tg_scuff%d" % i, T @ Ts(sx, 1.2 + sy * 0.7, 0.098), sr, 0.03,
                           _m(MAT, "sand_dark"), seg=12))
    for s in (-1, 1):
        parts.append(K.box("tg_kerb%d" % s, T @ Ts(0, 1.2 + s * (d * 0.17 + 0.10), 0.09),
                           (w * 0.46, 0.22, 0.18), stone, bev=0.014))
    # three sides of wall, open to the street
    hw = 2.45
    parts.append(K.box("tg_wb", T @ Ts(0, -d * 0.5, hw * 0.5), (w, 0.46, hw), stone, bev=0.02))
    for s in (-1, 1):
        parts.append(K.box("tg_ws%d" % s, T @ Ts(s * (w * 0.5 - 0.23), -0.4, hw * 0.5),
                           (0.46, d - 0.8, hw), stone, bev=0.02))
    parts.append(K.box("tg_capb", T @ Ts(0, -d * 0.5, hw + 0.09), (w + 0.10, 0.56, 0.18),
                       stone_d, bev=0.02))
    for s in (-1, 1):
        parts.append(K.box("tg_caps%d" % s, T @ Ts(s * (w * 0.5 - 0.23), -0.4, hw + 0.09),
                           (0.56, d - 0.8, 0.18), stone_d, bev=0.02))
    parts += H.crenel("tg_cren", T @ Ts(0, -d * 0.5, hw + 0.18), w, merlon=0.62, gap=0.52,
                      h=0.44, depth=0.44, mat=stone)
    # three target butts against the back wall
    for i, tx in enumerate((-3.4, 0.0, 3.4)):
        parts.append(K.cyl("tg_butt%d" % i, T @ Ts(tx, -d * 0.5 + 0.95, 1.45, rx=D2R(90)),
                           0.78, 0.46, _m(MAT, "sand"), seg=18))
        for k, (r, mat) in enumerate(((0.58, "cloth_red"), (0.36, "plaster_white"),
                                      (0.15, "cloth_gold"))):
            parts.append(K.cyl("tg_ring%d_%d" % (i, k),
                               T @ Ts(tx, -d * 0.5 + 1.20, 1.45, rx=D2R(90)), r, 0.05,
                               _m(MAT, mat), seg=18))
        parts.append(K.box("tg_leg%d" % i, T @ Ts(tx, -d * 0.5 + 0.72, 0.62),
                           (0.14, 0.14, 1.24), timber))
    # pells: padded posts on the sand
    for i, (px, py) in enumerate(((-2.6, 2.0), (0.4, 3.1), (2.9, 1.5))):
        parts.append(K.cyl("tg_pell%d" % i, T @ Ts(px, py, 1.05), 0.17, 2.10, timber, seg=10))
        parts.append(K.cyl("tg_pad%d" % i, T @ Ts(px, py, 1.72), 0.30, 0.42,
                           _m(MAT, "sand"), seg=12))
        for s in (-1, 1):
            parts.append(K.box("tg_arm%d_%d" % (i, s), T @ Ts(px + s * 0.42, py, 1.34),
                               (0.62, 0.12, 0.12), timber))
        parts.append(K.box("tg_base%d" % i, T @ Ts(px, py, 0.10), (0.60, 0.60, 0.20), stone_d))
    # weapon rack: two A-frames carrying spears
    for s in (-1, 1):
        parts.append(K.box("tg_rk%d" % s, T @ Ts(s * 1.15, -1.9, 0.62), (0.14, 0.14, 1.24), timber))
        parts.append(K.box("tg_rkb%d" % s, T @ Ts(s * 1.15, -1.9, 1.16), (0.14, 1.30, 0.13), timber))
    for i in range(7):
        sx = -1.05 + i * 0.35
        parts.append(K.cyl("tg_sp%d" % i, T @ Ts(sx, -1.9, 0.92, rx=D2R(9)),
                           0.045, 1.85, timber, seg=6))
        parts.append(K.box("tg_tp%d" % i, T @ Ts(sx, -1.9, 1.86, rx=D2R(9)),
                           (0.10, 0.10, 0.26), iron))
    # viewing stand at the left, canopy on four posts
    sx = -w * 0.5 + 2.4
    for i in range(3):
        parts.append(K.box("tg_st%d" % i, T @ Ts(sx, -3.0 + i * 0.85, 0.16 + i * 0.26),
                           (3.4, 0.90, 0.30), timber, bev=0.012))
    for i, (px, py) in enumerate(((-1.5, -3.4), (1.5, -3.4), (-1.5, -0.4), (1.5, -0.4))):
        parts.append(K.cyl("tg_spost%d" % i, T @ Ts(sx + px, py, 1.60), 0.10, 3.20, timber, seg=8))
    # A single flat sheet of pink cloth reads as a sticker.  Two shallow slopes
    # meeting on a ridge bar give it thickness and a shadow line, and the
    # valance hangs down so the far edge is not a razor cut.
    for s in (-1, 1):
        parts.append(K.box("tg_scan%d" % s, T @ Ts(sx, -1.9 + s * 1.02, 3.275,
                                                    rx=D2R(-8.0 * s)),
                           (3.9, 2.06, 0.12), _m(MAT, "cloth_red"), bev=0.008))
    parts.append(K.box("tg_sridge", T @ Ts(sx, -1.9, 3.42), (4.0, 0.14, 0.12), timber, bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("tg_sval%d" % s, T @ Ts(sx, -1.9 + s * 1.99, 3.00),
                           (3.9, 0.06, 0.32), _m(MAT, "cloth_red"), bev=0.006))
    # banners on the wall
    for s in (-1, 1):
        parts += H.banner("tg_bn%d" % s, T @ Ts(s * (w * 0.5 - 1.1), -d * 0.5 + 0.30, hw + 0.20),
                          0.85, 1.70, _m(MAT, "cloth_blue"), iron, pole_h=2.5)
    # two braziers: the yard is used at night and an empty sand pit reads as
    # unfinished ground, not as a training yard
    for s in (-1, 1):
        bx, by = s * (w * 0.5 - 1.6), -d * 0.5 + 2.2
        for i in range(3):
            parts.append(K.cyl("tg_brl%d_%d" % (s, i), T @ Ts(bx + (i - 1) * 0.24, by, 0.55),
                               0.045, 1.10, iron, seg=6))
        parts.append(K.cyl("tg_brb%d" % s, T @ Ts(bx, by, 1.20), 0.40, 0.30, iron, seg=12))
        parts.append(K.cyl("tg_brf%d" % s, T @ Ts(bx, by, 1.34), 0.30, 0.06,
                           _m(MAT, "glow_warm"), seg=12))
    # a free-standing fence closing the yard on the street side
    parts += _fence("tg_fn", T, -w * 0.5 + 0.4, -1.6, d * 0.5 + 2.6, timber, height=1.0)
    parts += _fence("tg_fn2", T, 1.6, w * 0.5 - 0.4, d * 0.5 + 2.6, timber, height=1.0)
    return parts


# --------------------------------------------------------------------------
# 11. barracks - long low block + watchtower + armoury lean-to
# --------------------------------------------------------------------------
def barracks(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 15.0, 8.4, 2.85, 0.34, 42
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    parts = []
    crest = 0.0
    parts, z_eave, _ops = _shell("br", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(-0.4, 1.45, pl, 2.35)],
                                 g_wins={"n": 4, "w": 0.85, "h": 1.15, "z": 1.05, "mull": 1},
                                 u_wins={"n": 8, "w": 0.78, "h": 1.05, "z": 0.72, "mull": 1},
                                 side_wins=2, back_wins=3, jetty=0.0)
    parts += _door("br_dr", T, -0.4, d * 0.5, pl, 1.45, 2.35, _m(MAT, "wood"), _m(MAT, "iron"),
                   stone, steps=2)
    parts += _roof("br_r", T, w, d, z_eave, pitch, _m(MAT, "tile_soot"), timber, "eaves",
                   end_mat=wall)
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # watchtower at the right end
    tw = 3.8
    tx = w * 0.5 + tw * 0.5 - 0.5
    th = 12.6
    parts.append(K.box("br_tw", T @ Ts(tx, 0.6, th * 0.5), (tw, tw, th), wall, bev=0.02))
    parts.append(K.box("br_twc", T @ Ts(tx, 0.6, th + 0.12), (tw + 0.42, tw + 0.42, 0.28),
                       stone, bev=0.02))
    for k, (rx, ry, rz) in enumerate(((0, tw * 0.5 + 0.18, 0), (0, -(tw * 0.5 + 0.18), 0),
                                      (tw * 0.5 + 0.18, 0, 90), (-(tw * 0.5 + 0.18), 0, 90))):
        parts += H.crenel("br_tcr%d" % k, T @ Ts(tx + rx, 0.6 + ry, th + 0.26, rz=D2R(rz)),
                          tw if k > 1 else tw, merlon=0.52, gap=0.44, h=0.62, depth=0.36,
                          mat=stone)
    for k in range(3):
        parts += _window("br_twn%d" % k, T, tx, 0.6 + tw * 0.5 + 0.01, 3.2 + k * 3.1, 0.62, 1.05,
                         [], 0.30, stone, glass, dark, mull=1)
    parts.append(K.box("br_twd", T @ Ts(tx, 0.6 - tw * 0.5 - 0.02, 0.0), (1.0, 0.10, 2.2),
                       _m(MAT, "wood_dark")))
    parts += H.banner("br_fl", T @ Ts(tx, 0.6, th + 0.80), 1.05, 1.90, _m(MAT, "cloth_red"),
                      _m(MAT, "iron"), pole_h=2.9)
    # armoury lean-to at the left end
    ax = -w * 0.5 - 1.6
    parts.append(K.box("br_arm", T @ Ts(ax, 1.4, 2.35), (4.2, 5.6, 4.70), wall, bev=0.02))
    parts.append(K.box("br_armr", T @ Ts(ax, 1.4, 5.05, rx=D2R(14)), (4.6, 6.2, 0.18),
                       _m(MAT, "slate"), bev=0.01))
    # the lean-to gets a real plank door: a flat void-coloured rectangle read as
    # a hole punched in the wall, not as a door.
    parts.append(K.box("br_armf", T @ Ts(ax, 4.19, 1.22), (1.44, 0.10, 2.44), stone, bev=0.01))
    for i in range(5):
        parts.append(K.box("br_armp%d" % i, T @ Ts(ax - 0.54 + i * 0.27, 4.23, 1.16),
                           (0.25, 0.07, 2.28), _m(MAT, "wood_dark")))
    for i in range(2):
        parts.append(K.box("br_armi%d" % i, T @ Ts(ax, 4.27, 0.62 + i * 0.98),
                           (1.16, 0.05, 0.11), _m(MAT, "iron")))
    parts.append(K.box("br_arms", T @ Ts(ax, 4.30, 0.05), (1.62, 0.52, 0.14), stone, bev=0.01))
    parts += H.barrel("br_b1", T @ Ts(2.6, d * 0.5 + 0.62, 0), 0.32, 0.86,
                      _m(MAT, "wood"), _m(MAT, "iron"))
    return parts


# --------------------------------------------------------------------------
# 12. knights_hq - gatehouse flanked by two towers, hall behind, flag row
# --------------------------------------------------------------------------
def knights_hq(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone")
    stone_d = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    parts = []
    # hall
    w, d, fh, pl, pitch = 11.0, 8.0, 3.15, 0.34, 48
    parts, z_eave, _ops = _shell("kn", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 1.6, pl, 2.5)],
                                 g_wins={"n": 2, "w": 0.95, "h": 1.45, "z": 1.15, "mull": 2},
                                 u_wins={"n": 3, "w": 1.0, "h": 1.35, "z": 0.75, "mull": 2},
                                 jetty=0.0)
    parts += _door("kn_dr", T, 0.0, d * 0.5, pl, 1.60, 2.50, _m(MAT, "wood"), iron, stone_d,
                   steps=3)
    parts += _roof("kn_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall)
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # gatehouse in front (+Y)
    gy = d * 0.5 + 3.4
    parts.append(K.box("kn_gc", T @ Ts(0, gy, 4.2), (6.4, 4.4, 8.4), wall, bev=0.02))
    parts.append(K.box("kn_gcc", T @ Ts(0, gy, 8.55), (6.9, 4.9, 0.30), stone_d, bev=0.02))
    parts += H.crenel("kn_gcr", T @ Ts(0, gy, 8.70), 6.9, merlon=0.62, gap=0.50, h=0.66,
                      depth=0.44, mat=stone_d)
    # the gate itself: a recessed arch + portcullis
    parts += H.door_arched("kn_gt", T @ Ts(0, gy + 2.21, 0.0), 2.90, 3.90,
                           _m(MAT, "wood_dark"), iron, stone=stone_d, steps=0, double=True)
    for i in range(4):
        parts.append(K.box("kn_pc%d" % i, T @ Ts(0, gy + 2.30, 1.10 + i * 0.62),
                           (2.70, 0.10, 0.09), iron))
    for s in (-1, 1):
        parts.append(K.cyl("kn_tw%d" % s, T @ Ts(s * 4.10, gy + 0.2, 5.6), 1.95, 11.2, wall,
                           seg=18))
        parts.append(K.box("kn_twc%d" % s, T @ Ts(s * 4.10, gy + 0.2, 11.30),
                           (4.30, 4.30, 0.30), stone_d, bev=0.02))
        for k in range(4):
            parts.append(K.box("kn_twm%d_%d" % (s, k),
                               T @ Ts(s * 4.10 + (-1.4 + k * 0.94), gy + 2.35, 11.72),
                               (0.52, 0.44, 0.62), stone_d, bev=0.012))
        parts += H.spire("kn_tws%d" % s, T @ Ts(s * 4.10, gy + 0.2, 11.60), 2.10, 3.10,
                         _m(MAT, "slate"), seg=10)
        parts += H.banner("kn_twb%d" % s, T @ Ts(s * 4.10, gy + 0.2, 14.70), 0.85, 1.60,
                          _m(MAT, "cloth_red"), iron, pole_h=2.2)
        for k in range(3):
            parts += _window("kn_twn%d_%d" % (s, k), T, s * 4.10 + 0.0, gy + 2.16,
                             3.0 + k * 3.0, 0.55, 1.0, [], 0.30, stone_d, glass, dark, mull=1)
    # flags along the hall facade
    for i, fx in enumerate((-3.6, -1.2, 1.2, 3.6)):
        parts += H.banner("kn_fl%d" % i, T @ Ts(fx, d * 0.5 + 0.35, ridge + 0.10), 0.70, 1.30,
                          _m(MAT, ["cloth_red", "cloth_blue", "cloth_red", "cloth_gold"][i]),
                          iron, pole_h=2.0)
    return parts


# --------------------------------------------------------------------------
# 13. guard_post - small jettied watch box + cell annex + notice wall
# --------------------------------------------------------------------------
def guard_post(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 4.4, 4.6, 2.55, 0.36, 40
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_ochre")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass_warm")
    dark = _m(MAT, "void")
    parts = []
    parts, z_eave, _ops = _shell("gp", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 1.10, pl, 2.10)],
                                 g_wins={"n": 0, "w": 0.9, "h": 1.0, "z": 1.0},
                                 u_wins={"n": 2, "w": 1.05, "h": 1.20, "z": 0.72, "mull": 2},
                                 jetty=0.40, side_wins=0)
    parts += _door("gp_dr", T, 0.0, d * 0.5, pl, 1.10, 2.10, _m(MAT, "wood"), _m(MAT, "iron"),
                   stone, steps=1)
    parts += _roof("gp_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "gable",
                   end_mat=wall)
    ridge = _ridge_z(w, d, z_eave, pitch, "gable")
    parts += _gable_wall("gp_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "gable")
    # cell annex behind: barred slit + iron door
    parts.append(K.box("gp_cell", T @ Ts(0, -(d * 0.5 + 1.7), 1.55), (3.6, 3.4, 3.10), stone,
                       bev=0.02))
    parts.append(K.box("gp_cellr", T @ Ts(0, -(d * 0.5 + 1.7), 3.20, rx=D2R(-16)),
                       (4.0, 4.0, 0.16), _m(MAT, "tile_soot"), bev=0.01))
    parts.append(K.box("gp_cd", T @ Ts(0, -(d * 0.5 + 0.02), 1.10), (0.95, 0.10, 2.05), dark))
    for i in range(4):
        parts.append(K.box("gp_cb%d" % i, T @ Ts(0, -(d * 0.5 - 0.04), 0.35 + i * 0.46),
                           (0.92, 0.06, 0.07), _m(MAT, "iron")))
    # notice wall on the left
    parts.append(K.box("gp_nb", T @ Ts(-w * 0.5 - 1.5, 0.6, 1.30), (2.4, 0.22, 2.6), timber,
                       bev=0.02))
    for i in range(3):
        parts.append(K.box("gp_np%d" % i, T @ Ts(-w * 0.5 - 1.5, 0.72, 1.95 - i * 0.55),
                           (1.05, 0.05, 0.42), _m(MAT, "plaster_white")))
    parts.append(K.box("gp_npr", T @ Ts(-w * 0.5 - 1.5, 0.60, 2.68), (2.7, 0.42, 0.16),
                       _m(MAT, "wood"), bev=0.014))
    parts += H.lantern_post("gp_lp", T @ Ts(w * 0.5 + 0.9, d * 0.5 + 0.7, 0), 2.9,
                            _m(MAT, "iron"), _m(MAT, "glow_warm"))
    # A heated two-storey post with no chimney is a hole in the silhouette that
    # an eye catches at once: the roof is the shape the player reads first.
    parts += _chimney("gp_ch", T, -w * 0.5 + 0.72, -(d * 0.5 - 0.62),
                      z_eave - 0.35, ridge + 0.62, _m(MAT, "brick"), w=0.72, pots=2,
                      cap_mat=stone)
    # spear rack beside the door: two trestles and four shafts
    for s in (-1, 1):
        parts.append(K.box("gp_spt%d" % s, T @ Ts(s * 0.62, d * 0.5 + 0.86, 0.52),
                           (0.10, 0.10, 1.04), _m(MAT, "wood"), bev=0.006))
        parts.append(K.box("gp_sptb%d" % s, T @ Ts(s * 0.62, d * 0.5 + 0.86, 0.98),
                           (0.14, 0.24, 0.09), _m(MAT, "wood"), bev=0.006))
    for i in range(4):
        parts.append(K.cyl("gp_sp%d" % i, T @ Ts(-0.42 + i * 0.24, d * 0.5 + 0.98, 1.28),
                           0.028, 2.30, _m(MAT, "wood_light"), seg=6))
        parts.append(K.cyl("gp_sph%d" % i, T @ Ts(-0.42 + i * 0.24, d * 0.5 + 0.98, 2.36),
                           0.045, 0.20, _m(MAT, "iron"), seg=6))
    # water butt against the right corner
    parts += H.barrel("gp_wb", T @ Ts(w * 0.5 + 0.42, d * 0.5 + 0.30, 0), 0.34, 1.05,
                      _m(MAT, "wood"), _m(MAT, "iron"))
    parts.append(K.box("gp_wbt", T @ Ts(w * 0.5 + 0.42, d * 0.5 + 0.10, 0.42),
                       (0.10, 0.16, 0.10), _m(MAT, "iron")))
    # watch gallery under the eave: the post is where the watch stands, and the
    # rail line across the facade is what separates it from a plain cottage
    parts.append(K.box("gp_gal", T @ Ts(0, d * 0.5 + 0.34, z_eave - 0.62),
                       (w + 0.10, 0.86, 0.14), _m(MAT, "wood"), bev=0.01))
    for i in range(7):
        gx = -w * 0.5 + 0.30 + i * (w - 0.60) / 6.0
        parts.append(K.box("gp_gbl%d" % i, T @ Ts(gx, d * 0.5 + 0.72, z_eave - 0.26),
                           (0.09, 0.09, 0.58), _m(MAT, "wood"), bev=0.005))
    parts.append(K.box("gp_grl", T @ Ts(0, d * 0.5 + 0.72, z_eave - 0.02),
                       (w + 0.10, 0.11, 0.11), _m(MAT, "wood"), bev=0.008))
    for s in (-1, 1):
        parts.append(K.box("gp_gbr%d" % s, T @ Ts(s * (w * 0.5 - 0.12), d * 0.5 + 0.34,
                                                  z_eave - 1.02),
                           (0.13, 0.72, 0.13), _m(MAT, "wood"), bev=0.006))
    # palisade across the compound, split by the gate
    for s in (-1, 1):
        x0, x1 = s * 1.05, s * (w * 0.5 + 2.35)
        parts += _fence("gp_pal%d" % s, T, x0, x1, d * 0.5 + 2.55, _m(MAT, "wood"),
                        height=1.75, gap=0.19)
    # alarm bell on the gable: the one thing a watch post has that a house does
    # not, and it sits exactly on the silhouette
    for s in (-1, 1):
        parts.append(K.box("gp_bp%d" % s, T @ Ts(s * 0.55, d * 0.5 + 0.10, ridge + 0.58),
                           (0.13, 0.13, 1.16), timber, bev=0.006))
    parts.append(K.box("gp_bh", T @ Ts(0, d * 0.5 + 0.10, ridge + 1.10), (1.36, 0.15, 0.14),
                       timber, bev=0.008))
    parts.append(K.cyl("gp_bell", T @ Ts(0, d * 0.5 + 0.10, ridge + 0.90), 0.24, 0.26,
                       _m(MAT, "brass"), seg=12, r2=0.15))
    parts.append(K.cyl("gp_bellh", T @ Ts(0, d * 0.5 + 0.10, ridge + 1.02), 0.035, 0.08,
                       _m(MAT, "iron"), seg=6))
    # two torches either side of the door
    for s in (-1, 1):
        parts.append(K.box("gp_tb%d" % s, T @ Ts(s * 1.05, d * 0.5 + 0.06, 2.32),
                           (0.10, 0.32, 0.10), _m(MAT, "iron"), bev=0.005))
        parts.append(K.cyl("gp_tf%d" % s, T @ Ts(s * 1.05, d * 0.5 + 0.20, 2.44),
                           0.06, 0.24, _m(MAT, "glow_warm"), seg=8))
    # gateway through the palisade
    for s in (-1, 1):
        parts.append(K.box("gp_gwp%d" % s, T @ Ts(s * 1.02, d * 0.5 + 2.55, 1.15),
                           (0.20, 0.24, 2.30), _m(MAT, "wood"), bev=0.01))
    parts.append(K.box("gp_gwl", T @ Ts(0, d * 0.5 + 2.55, 2.36), (2.42, 0.26, 0.20),
                       _m(MAT, "wood"), bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("gp_gwd%d" % s, T @ Ts(s * 0.50, d * 0.5 + 2.55, 1.10),
                           (0.96, 0.07, 1.86), _m(MAT, "wood_dark"), bev=0.008))
    # well in the compound: prisoners get water somewhere
    wx, wy = -(w * 0.5 + 1.30), d * 0.5 + 0.55
    parts.append(K.cyl("gp_wel", T @ Ts(wx, wy, 0.42), 0.52, 0.84, stone, seg=14))
    parts.append(K.cyl("gp_wew", T @ Ts(wx, wy, 0.86), 0.40, 0.06, dark, seg=14))
    for s in (-1, 1):
        parts.append(K.box("gp_wep%d" % s, T @ Ts(wx + s * 0.54, wy, 1.30),
                           (0.11, 0.11, 1.70), _m(MAT, "wood"), bev=0.006))
    parts.append(K.box("gp_wer", T @ Ts(wx, wy, 2.10, rx=D2R(22)), (1.34, 0.10, 0.92),
                       _m(MAT, "tile_soot"), bev=0.006))
    parts.append(K.cyl("gp_wex", T @ Ts(wx, wy, 1.78, ry=D2R(90)), 0.055, 1.12,
                       _m(MAT, "wood"), seg=8))
    parts.append(K.cyl("gp_werp", T @ Ts(wx, wy, 1.52), 0.012, 0.46, _m(MAT, "sand_dark"),
                       seg=5))
    parts.append(K.cyl("gp_webk", T @ Ts(wx, wy, 1.20), 0.13, 0.24, _m(MAT, "wood"), seg=10))
    # bench and two crates against the front
    parts.append(K.box("gp_bnch", T @ Ts(w * 0.5 - 1.15, d * 0.5 + 0.52, 0.52),
                       (1.70, 0.42, 0.10), _m(MAT, "wood"), bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("gp_bnl%d" % s, T @ Ts(w * 0.5 - 1.15 + s * 0.68,
                                                  d * 0.5 + 0.52, 0.26),
                           (0.12, 0.36, 0.52), _m(MAT, "wood"), bev=0.006))
    parts += H.crate("gp_cr1", T @ Ts(-w * 0.5 - 0.35, d * 0.5 + 0.62, 0), 0.52,
                     _m(MAT, "wood"))
    parts += H.crate("gp_cr2", T @ Ts(-w * 0.5 - 0.35, d * 0.5 + 0.62, 0.48), 0.40,
                     _m(MAT, "wood"))
    # shutters pinned open on the upper windows, and stores piled by the gate
    for i, gx in enumerate((-1.05, 1.05)):
        for s in (-1, 1):
            parts.append(K.box("gp_sh%d_%d" % (i, s), T @ Ts(gx + s * 0.86, d * 0.5 + 0.08,
                                                              pl + 0.72 + 0.90 + 0.60),
                               (0.34, 0.07, 1.22), _m(MAT, "wood"), bev=0.006))
        parts.append(K.box("gp_shl%d" % i, T @ Ts(gx, d * 0.5 + 0.08, pl + 0.72 + 2.26),
                           (1.52, 0.09, 0.12), _m(MAT, "wood"), bev=0.006))
    for i in range(3):
        parts += _sack(T, 1.55 + i * 0.34, d * 0.5 + 2.10, 0, _m(MAT, "sand_dark"))
    parts.append(K.box("gp_sth", T @ Ts(0, d * 0.5 + 0.42, 0.30), (1.55, 0.60, 0.16),
                       stone, bev=0.014))
    # hitching rail for the watch's own mounts, by the palisade gap
    for i in range(3):
        parts.append(K.box("gp_hr%d" % i, T @ Ts(-2.55 + i * 1.35, d * 0.5 + 1.72, 0.56),
                           (0.11, 0.11, 1.12), _m(MAT, "wood"), bev=0.006))
    parts.append(K.box("gp_hrr", T @ Ts(-1.20, d * 0.5 + 1.72, 1.02), (2.90, 0.09, 0.10),
                       _m(MAT, "wood"), bev=0.006))
    parts.append(K.cyl("gp_hbk", T @ Ts(2.15, d * 0.5 + 2.05, 0.42), 0.15, 0.34,
                       _m(MAT, "iron"), seg=10))
    # watch flag on the gallery rail: the post's colours, raised and lowered
    parts.append(K.cyl("gp_flp", T @ Ts(-(w * 0.5 + 0.55), d * 0.5 + 2.30, 1.60), 0.05, 3.20,
                       _m(MAT, "wood"), seg=6))
    parts.append(K.box("gp_flc", T @ Ts(-(w * 0.5 + 0.22), d * 0.5 + 2.30, 2.95),
                       (0.62, 0.04, 0.90), _m(MAT, "cloth_red"), bev=0.004))
    parts.append(K.sphere("gp_flk", T @ Ts(-(w * 0.5 + 0.55), d * 0.5 + 2.30, 3.24), 0.07,
                          _m(MAT, "brass"), seg=8, ring=5))
    return parts


# --------------------------------------------------------------------------
# 14. armory - open front, quenching trough, grindstone, armour stands
# --------------------------------------------------------------------------
def armory(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 8.2, 8.6, 2.95, 0.38, 44
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_dark")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    parts = []
    parts, z_eave, _ops = _shell("ar", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 open_front=True, jetty=0.32,
                                 u_wins={"n": 3, "w": 0.92, "h": 1.10, "z": 0.80, "mull": 2},
                                 side_wins=1)
    parts += _roof("ar_r", T, w, d, z_eave, pitch, _m(MAT, "tile_soot"), timber, "gable",
                   end_mat=wall)
    ridge = _ridge_z(w, d, z_eave, pitch, "gable")
    parts += _gable_wall("ar_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "gable")
    # quenching trough: a stone cistern with a water surface
    parts.append(K.box("ar_qt", T @ Ts(-2.3, d * 0.5 - 1.30, 0.46), (2.20, 0.90, 0.92), stone,
                       bev=0.02))
    parts.append(K.box("ar_qw", T @ Ts(-2.3, d * 0.5 - 1.30, 0.90), (1.95, 0.70, 0.06),
                       _m(MAT, "water")))
    # grindstone on a frame
    parts.append(K.cyl("ar_gs", T @ Ts(0.4, d * 0.5 - 1.10, 0.92, ry=D2R(90)), 0.62, 0.22,
                       stone, seg=18))
    for s in (-1, 1):
        parts.append(K.box("ar_gsf%d" % s, T @ Ts(0.4 + s * 0.36, d * 0.5 - 1.10, 0.55),
                           (0.10, 0.9, 0.9), timber))
    parts.append(K.cyl("ar_gsc", T @ Ts(0.4, d * 0.5 - 1.10, 0.20, rx=D2R(4)), 0.05, 0.62,
                       iron, seg=8))
    # two armour stands with plate on them
    for i, sx in enumerate((2.6, 3.5)):
        parts.append(K.box("ar_asr%d" % i, T @ Ts(sx, d * 0.5 - 1.5, 1.05), (0.10, 0.10, 2.10),
                           timber))
        parts.append(K.box("ar_ash%d" % i, T @ Ts(sx, d * 0.5 - 1.5, 1.86), (0.66, 0.34, 0.52),
                           _m(MAT, "iron"), bev=0.02))
        parts.append(K.box("ar_ast%d" % i, T @ Ts(sx, d * 0.5 - 1.5, 1.20), (0.52, 0.30, 0.56),
                           _m(MAT, "iron"), bev=0.02))
        parts.append(K.box("ar_asb%d" % i, T @ Ts(sx, d * 0.5 - 1.5, 0.42), (0.46, 0.28, 0.40),
                           _m(MAT, "brass"), bev=0.02))
    # weapon rack under the jetty
    for s in (-1, 1):
        parts.append(K.box("ar_wr%d" % s, T @ Ts(s * 1.05 + 2.9, d * 0.5 + 0.30, 0.85),
                           (0.12, 0.12, 1.70), timber))
    for i in range(6):
        parts.append(K.cyl("ar_bl%d" % i,
                           T @ Ts(2.9 - 0.52 + i * 0.21, d * 0.5 + 0.34, 1.35, rx=D2R(4)),
                           0.035, 1.05, iron, seg=6))
    # anvil by the trough
    parts.append(K.box("ar_anb", T @ Ts(-1.2, d * 0.5 + 0.55, 0.34), (0.36, 0.30, 0.68), timber))
    parts.append(K.box("ar_ant", T @ Ts(-1.2, d * 0.5 + 0.55, 0.76), (0.86, 0.34, 0.22), iron,
                       bev=0.012))
    # a rank of helms on pegs along the open front - an armoury with nothing
    # hanging up is a barn
    for i in range(6):
        hx = -2.55 + i * 0.62
        parts.append(K.sphere("ar_hm%d" % i, T @ Ts(hx, d * 0.5 + 0.16, 2.62), 0.19,
                              iron, seg=10, ring=6, squash=0.86))
        parts.append(K.box("ar_hv%d" % i, T @ Ts(hx, d * 0.5 + 0.16, 2.44),
                           (0.36, 0.10, 0.10), iron, bev=0.006))
        parts.append(K.box("ar_hpe%d" % i, T @ Ts(hx, d * 0.5 + 0.04, 2.74),
                           (0.07, 0.16, 0.06), timber))
    # tool stand: three hammers and a pair of tongs on a rail
    parts.append(K.box("ar_tsr", T @ Ts(1.05, d * 0.5 + 0.60, 1.72), (1.30, 0.09, 0.09), timber))
    for i in range(4):
        parts.append(K.box("ar_tst%d" % i, T @ Ts(0.55 + i * 0.33, d * 0.5 + 0.60, 1.30),
                           (0.05, 0.05, 0.80), timber))
        parts.append(K.box("ar_tsh%d" % i, T @ Ts(0.55 + i * 0.33, d * 0.5 + 0.60, 0.92),
                           (0.16, 0.05, 0.10), iron, bev=0.005))
    return parts





# --------------------------------------------------------------------------
# 15. weaponsmith - closed forge, counter bay, spear rail, grinding wheel
# --------------------------------------------------------------------------
def weaponsmith(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 7.8, 9.6, 3.05, 0.38, 46
    stone = _m(MAT, "stone_warm")
    wall = _m(MAT, "plaster_ochre")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    brick = _m(MAT, "brick")
    parts = []
    dh = 2.45
    parts, z_eave, _ops = _shell("wp", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(-2.0, 1.30, pl, dh + 0.55)],
                                 g_wins={"n": 1, "w": 1.80, "h": 1.10, "z": 1.15, "mull": 2},
                                 u_wins={"n": 4, "w": 0.92, "h": 1.30, "z": 0.76, "mull": 2},
                                 side_wins=1, back_wins=2, jetty=0.32)
    parts += _door("wp_dr", T, -2.0, d * 0.5, pl, 1.30, dh + 0.45, _m(MAT, "wood"), iron,
                   stone, steps=2)
    # the counter bay: a shutter board folded up over the opening, so the shop
    # sells over a counter instead of through a doorway
    cx = 1.85
    parts.append(K.box("wp_cb", T @ Ts(cx, d * 0.5 + 0.30, pl + 1.42),
                       (1.90, 0.62, 0.10), timber, bev=0.012))
    for i in range(3):
        parts.append(K.box("wp_cbs%d" % i, T @ Ts(cx - 0.55 + i * 0.55, d * 0.5 + 0.66,
                                                  pl + 2.42, rx=D2R(64)),
                           (0.52, 0.06, 1.05), timber, bev=0.01))
    for i in range(4):
        parts.append(K.box("wp_bl%d" % i, T @ Ts(cx - 0.62 + i * 0.42, d * 0.5 - 0.10,
                                                 pl + 1.60), (0.07, 0.05, 0.92), iron))
    parts += _roof("wp_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall, ov_gable=0.46)
    parts += _gable_wall("wp_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch, "eaves") - z_eave, wall, timber, "eaves")
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # forge stack rising from the back of the plot, soot-darkened at the crown
    parts += _chimney("wp_st", T, -2.85, -2.6, pl + 1.80, ridge + 1.10, brick, w=0.95, pots=1,
                      cap_mat=stone)
    parts.append(K.box("wp_stc", T @ Ts(-2.85, -2.6, ridge + 1.02), (1.20, 1.20, 0.20), _m(MAT,
                                                                                           "soot"),
                       bev=0.02))
    # spear rail: the thing a weaponsmith has that no other shop does
    parts.append(K.box("wp_rail", T @ Ts(-3.15, d * 0.5 + 0.66, pl + 1.72),
                       (0.10, 0.10, 0.10), iron))
    for i in range(5):
        sx = -3.95 + i * 0.40
        parts.append(K.cyl("wp_spe%d" % i, T @ Ts(sx, d * 0.5 + 0.70, pl + 1.30),
                           0.040, 2.30, _m(MAT, "wood"), seg=6))
        parts.append(K.box("wp_spt%d" % i, T @ Ts(sx, d * 0.5 + 0.70, pl + 2.52),
                           (0.10, 0.06, 0.30), iron, bev=0.006))
    # swords hanging on a rail beside the door
    for i in range(3):
        parts.append(K.box("wp_sw%d" % i, T @ Ts(-0.95 + i * 0.28, d * 0.5 + 0.24,
                                                 pl + 1.95), (0.075, 0.05, 0.92), iron))
        parts.append(K.box("wp_swg%d" % i, T @ Ts(-0.95 + i * 0.28, d * 0.5 + 0.24,
                                                  pl + 1.42), (0.26, 0.06, 0.07),
                           _m(MAT, "brass")))
    # grinding wheel on a trestle
    gx = 2.55
    parts.append(K.cyl("wp_gw", T @ Ts(gx, d * 0.5 + 1.25, 0.98, ry=D2R(90)), 0.55, 0.14,
                       stone, seg=18))
    for s in (-1, 1):
        parts.append(K.box("wp_gwl%d" % s, T @ Ts(gx, d * 0.5 + 1.25 + s * 0.42, 0.42),
                           (0.16, 0.14, 0.86), timber, bev=0.008))
    parts.append(K.cyl("wp_gwa", T @ Ts(gx, d * 0.5 + 1.25, 0.98, ry=D2R(90)), 0.05, 0.52,
                       iron, seg=8))
    parts.append(K.box("wp_gwt", T @ Ts(gx, d * 0.5 + 1.25, 0.10), (1.05, 0.90, 0.20), timber,
                       bev=0.01))
    parts.append(K.box("wp_gww", T @ Ts(gx, d * 0.5 + 1.25, 0.16), (0.85, 0.70, 0.06),
                       _m(MAT, "water")))
    parts += H.crate("wp_cr0", T @ Ts(-3.3, d * 0.5 + 0.55, 0), 0.60, _m(MAT, "wood"))
    return parts


# --------------------------------------------------------------------------
# 16. apothecary - oriel with bottles, herb bundles, still house
# --------------------------------------------------------------------------
def apothecary(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 6.6, 8.4, 3.02, 0.40, 50
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_white")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    leaf = _m(MAT, "leaf")
    parts = []
    dh = 2.40
    parts, z_eave, _ops = _shell("ap", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 1.20, pl, dh + 0.50)],
                                 g_wins={"n": 1, "w": 1.05, "h": 1.15, "z": 1.10, "mull": 2,
                                         "shutters": timber},
                                 u_wins=None, side_wins=1, back_wins=1, jetty=0.36)
    parts += _door("ap_dr", T, 0.0, d * 0.5, pl, 1.20, dh + 0.40, _m(MAT, "wood"), iron, stone,
                   steps=1)
    # --- oriel bay on the first floor: the apothecary's whole identity
    bz = pl + fh + 0.55
    ow, od = 2.15, 0.72
    parts.append(K.box("ap_orb", T @ Ts(0, d * 0.5 + od * 0.5, bz), (ow, od, 1.90), wall,
                       bev=0.02))
    parts.append(K.box("ap_orc", T @ Ts(0, d * 0.5 + od * 0.5, bz + 1.02), (ow + 0.26, od + 0.26,
                                                                            0.16), timber,
                       bev=0.012))
    parts.append(K.box("ap_ors", T @ Ts(0, d * 0.5 + od * 0.5, bz - 1.00), (ow + 0.22, od + 0.22,
                                                                            0.14), timber,
                       bev=0.012))
    for i in range(3):
        parts.append(K.box("ap_org%d" % i, T @ Ts(-0.66 + i * 0.66, d * 0.5 + od + 0.01, bz),
                           (0.54, 0.05, 1.24), glass))
        for s in (-1, 1):
            parts.append(K.box("ap_orm%d_%d" % (i, s), T @ Ts(-0.66 + i * 0.66 + s * 0.16,
                                                              d * 0.5 + od + 0.04, bz),
                               (0.05, 0.04, 1.24), timber, bev=0.004))
        parts.append(K.box("ap_ort%d" % i, T @ Ts(-0.66 + i * 0.66, d * 0.5 + od + 0.04, bz),
                           (0.54, 0.04, 0.06), timber, bev=0.004))
    # bottles: little coloured cylinders standing on the oriel sill
    for i, (bx, cm) in enumerate(((-0.72, "glass_magic"), (-0.30, "glass_warm"),
                                  (0.16, "cloth_green"), (0.62, "glass_warm"))):
        parts.append(K.cyl("ap_bo%d" % i, T @ Ts(bx, d * 0.5 + od + 0.22, bz - 0.70),
                           0.055, 0.20 + 0.05 * (i % 2), _m(MAT, cm), seg=8))
    # herb bundles hanging under the eaves
    for i, hx in enumerate((-2.55, -1.85, 1.55, 2.25, 2.75)):
        parts.append(K.box("ap_hb%d" % i, T @ Ts(hx, d * 0.5 + 0.24, z_eave - 0.30),
                           (0.03, 0.03, 0.34), timber))
        parts.append(K.sphere("ap_hs%d" % i, T @ Ts(hx, d * 0.5 + 0.24, z_eave - 0.62),
                              0.13 + 0.02 * (i % 3), leaf, seg=8, ring=5, squash=1.35))
    parts += _roof("ap_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "gable",
                   end_mat=wall, ov_gable=0.34)
    ridge = _ridge_z(w, d, z_eave, pitch, "gable")
    parts += _gable_wall("ap_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "gable")
    parts += _chimney("ap_ch", T, 2.15, -1.4, z_eave + 0.4, ridge + 0.55, stone, w=0.62, pots=1)
    # still house: a lean-to at the left with a copper still and a coil
    lx = -w * 0.5 - 1.35
    parts.append(K.box("ap_sh", T @ Ts(lx, 1.1, 1.35), (2.5, 4.2, 2.70), wall, bev=0.02))
    parts.append(K.box("ap_shr", T @ Ts(lx, 1.1, 2.78, rx=D2R(16)), (2.9, 4.6, 0.16),
                       _m(MAT, "tile"), bev=0.01))
    parts.append(K.box("ap_shd", T @ Ts(lx, 3.05, 0.70), (0.95, 0.10, 1.40), timber))
    parts.append(K.cyl("ap_stl", T @ Ts(lx, 1.60, 1.05), 0.26, 0.90, _m(MAT, "brass"), seg=14,
                       r2=0.16))
    parts.append(K.sphere("ap_sth", T @ Ts(lx, 1.60, 1.62), 0.22, _m(MAT, "brass"), seg=12,
                          ring=8, squash=0.85))
    parts.append(K.cyl("ap_stc", T @ Ts(lx, 1.60, 1.86), 0.045, 1.10, _m(MAT, "brass"), seg=8))
    parts += H.barrel("ap_br0", T @ Ts(lx + 1.55, 3.30, 0), 0.26, 0.72, _m(MAT, "wood"),
                      iron)
    parts.append(K.box("ap_fr0", T @ Ts(1.95, d * 0.5 + 0.42, 0.34), (1.20, 0.70, 0.68),
                       _m(MAT, "wood"), bev=0.02))
    for i in range(4):
        parts.append(K.cyl("ap_fb%d" % i, T @ Ts(1.62 + i * 0.24, d * 0.5 + 0.42, 0.74),
                           0.05, 0.20, _m(MAT, ("cloth_red", "glass_magic", "cloth_green",
                                                "glass_warm")[i]), seg=8))
    # drying bundles under the eave: the shop is defined by what hangs from it,
    # and at 15 m a row of small hanging shapes reads faster than any sign
    for i in range(5):
        hx = -1.90 + i * 0.72
        parts.append(K.cyl("ap_hs%d" % i, T @ Ts(hx, d * 0.5 + 0.30, 3.34), 0.012, 0.44,
                           timber, seg=5))
        for j in range(3):
            parts.append(K.cyl("ap_hb%d_%d" % (i, j), T @ Ts(hx + (j - 1) * 0.055,
                                                             d * 0.5 + 0.30, 3.02),
                               0.045, 0.30, _m(MAT, ("cloth_green", "cloth_red",
                                                     "sand_dark")[(i + j) % 3]), seg=6))
        parts.append(K.cyl("ap_ht%d" % i, T @ Ts(hx, d * 0.5 + 0.30, 3.20), 0.028, 0.06,
                           _m(MAT, "iron"), seg=6))
    return parts


# --------------------------------------------------------------------------
# 17. inn - three storeys, gallery balcony, coach arch to a rear yard
# --------------------------------------------------------------------------
def inn(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 12.2, 10.4, 2.95, 0.44, 42
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass_warm")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    parts = []
    dh = 2.50
    parts, z_eave, _ops = _shell("in", T, w, d, 3, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(-0.6, 1.55, pl, dh + 0.55),
                                          (4.05, 2.30, pl, 3.10)],
                                 g_wins={"n": 2, "w": 1.10, "h": 1.40, "z": 0.90, "mull": 2,
                                         "hood": True},
                                 u_wins={"n": 5, "w": 1.00, "h": 1.40, "z": 0.72, "mull": 2,
                                         "skip": (-0.6, 4.05)},
                                 side_wins=2, back_wins=3, jetty=0.34)
    parts += _door("in_dr", T, -0.6, d * 0.5, pl, 1.55, dh + 0.45, _m(MAT, "wood"), iron, stone,
                   steps=2, double=True)
    # coach arch: a real opening, dark passage behind, iron gates inside
    ax = 4.05
    parts += H.door_arched("in_ga", T @ Ts(ax, d * 0.5 + 0.01, pl), 2.30, 3.55,
                           _m(MAT, "wood_dark"), iron, stone=stone, steps=0, double=True)
    for i in range(5):
        parts.append(K.box("in_gt%d" % i, T @ Ts(ax, d * 0.5 + 0.30, pl + 0.35 + i * 0.62),
                           (2.05, 0.07, 0.08), iron))
    parts += _roof("in_r", T, w, d, z_eave, pitch, _m(MAT, "tile"), timber, "eaves",
                   end_mat=wall, ov_gable=0.48)
    parts += _gable_wall("in_g", T, w, d, z_eave,
                         _ridge_z(w, d, z_eave, pitch, "eaves") - z_eave, wall, timber, "eaves")
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # gallery: a timber balcony across the whole front at third-floor level.
    # An inn is the only building on the street with one, so the silhouette
    # reads from across the square.
    gy = d * 0.5 + 0.78
    parts.append(K.box("in_gd", T @ Ts(0, gy, pl + fh * 2 + 0.10), (w - 0.4, 1.30, 0.16),
                       timber, bev=0.012))
    parts.append(K.box("in_gr", T @ Ts(0, gy + 0.60, pl + fh * 2 + 0.62), (w - 0.4, 0.10, 0.12),
                       timber, bev=0.008))
    n = int((w - 0.6) / 0.34)
    for i in range(n):
        parts.append(K.box("in_gb%d" % i, T @ Ts(-w * 0.5 + 0.5 + i * (w - 1.0) / (n - 1),
                                                 gy + 0.60, pl + fh * 2 + 0.38),
                           (0.07, 0.07, 0.50), timber))
    for i, px in enumerate((-4.6, -0.6, 3.6)):
        parts.append(K.box("in_gp%d" % i, T @ Ts(px, gy + 0.58, pl + fh * 2 - 1.48),
                           (0.16, 0.16, 3.00), timber, bev=0.01))
    # lanterns on the gallery posts + a hanging bed sign is added by the registry
    for i, lx in enumerate((-3.2, 2.2)):
        parts.append(K.box("in_lb%d" % i, T @ Ts(lx, gy - 0.10, pl + fh * 2 - 0.10),
                           (0.07, 0.07, 0.30), iron))
        parts.append(K.box("in_lg%d" % i, T @ Ts(lx, gy - 0.10, pl + fh * 2 - 0.42),
                           (0.26, 0.26, 0.34), _m(MAT, "glow_warm"), bev=0.02))
    parts += _chimney("in_ch0", T, -3.9, -2.2, z_eave + 0.3, ridge + 0.95, stone, w=0.72, pots=2)
    parts += _chimney("in_ch1", T, 2.9, -3.4, z_eave + 0.3, ridge + 0.80, stone, w=0.66, pots=1)
    for i, bx in enumerate((-4.9, 4.9)):
        parts += H.banner("in_bn%d" % i, T @ Ts(bx, d * 0.5 + 0.30, pl + fh * 2 + 1.05),
                          0.70, 1.40, _m(MAT, ("cloth_red", "cloth_blue")[i]), iron, pole_h=2.2)
    parts += H.barrel("in_br0", T @ Ts(-3.3, d * 0.5 + 0.78, 0), 0.30, 0.86, _m(MAT, "wood"),
                      iron)
    parts += H.barrel("in_br1", T @ Ts(-2.55, d * 0.5 + 0.92, 0), 0.26, 0.74, _m(MAT, "wood"),
                      iron)
    parts += _bench(T, 2.55, d * 0.5 + 0.55, 0, _m(MAT, "wood"), 1.8)
    return parts


# --------------------------------------------------------------------------
# 18. bathhouse - dome, portico, steam stacks, water spout
# --------------------------------------------------------------------------
def bathhouse(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl = 11.0, 12.0, 5.20, 0.52
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster_white")
    timber = _m(MAT, "wood_dark")
    iron = _m(MAT, "iron")
    water = _m(MAT, "water")
    tile = _m(MAT, "slate")
    parts = []
    parts, z_eave, _ops = _shell("bt", T, w, d, 1, fh, pl, wall, stone, timber,
                                 _m(MAT, "glass_magic"), _m(MAT, "void"),
                                 g_holes=[(0.0, 2.60, pl, 3.60)],
                                 g_wins={"n": 2, "w": 0.95, "h": 1.75, "z": 1.35, "mull": 2,
                                         "shutters": None},
                                 open_front=False, jetty=0.0, side_wins=0, back_wins=0)
    # grand arched entrance, with a warm-lit interior behind it
    parts += H.door_arched("bt_dr", T @ Ts(0, d * 0.5 + 0.01, pl), 2.60, 3.55,
                           _m(MAT, "wood_dark"), iron, stone=stone, steps=3, double=True)
    # portico: four columns carrying an entablature
    for i, cx in enumerate((-3.9, -1.45, 1.45, 3.9)):
        parts.append(K.cyl("bt_col%d" % i, T @ Ts(cx, d * 0.5 + 1.55, pl + 1.85), 0.30, 3.70,
                           stone, seg=16, r2=0.26))
        parts.append(K.box("bt_clb%d" % i, T @ Ts(cx, d * 0.5 + 1.55, pl + 0.10),
                           (0.78, 0.78, 0.20), stone, bev=0.02))
        parts.append(K.box("bt_clc%d" % i, T @ Ts(cx, d * 0.5 + 1.55, pl + 3.76),
                           (0.74, 0.74, 0.18), stone, bev=0.02))
    parts.append(K.box("bt_ent", T @ Ts(0, d * 0.5 + 1.60, pl + 4.02), (9.60, 1.90, 0.52),
                       stone, bev=0.03))
    parts.append(K.box("bt_ent2", T @ Ts(0, d * 0.5 + 1.60, pl + 4.36), (9.10, 1.60, 0.20),
                       _m(MAT, "stone_warm"), bev=0.02))
    # parapet instead of a pitched roof: baths burn down, they do not need attics
    for s in (-1, 1):
        parts.append(K.box("bt_par%d" % s, T @ Ts(0, s * (d * 0.5 - 0.15), z_eave + 0.30),
                           (w + 0.30, 0.42, 0.60), stone, bev=0.02))
        parts.append(K.box("bt_parc%d" % s, T @ Ts(0, s * (d * 0.5 - 0.15), z_eave + 0.62),
                           (w + 0.46, 0.56, 0.14), _m(MAT, "stone_warm"), bev=0.02))
    parts.append(K.box("bt_deck", T @ Ts(0, 0, z_eave + 0.02), (w + 0.10, d + 0.10, 0.24),
                       stone, bev=0.02))
    # drum + dome + lantern: the silhouette nobody else on the street has
    dz = z_eave + 0.14
    parts.append(K.cyl("bt_drum", T @ Ts(0, -1.2, dz + 0.85), 3.55, 1.70, stone, seg=28))
    for i in range(12):
        a = math.tau * i / 12.0
        parts.append(K.box("bt_dsp%d" % i,
                           T @ Ts(math.cos(a) * 3.55, -1.2 + math.sin(a) * 3.55, dz + 0.85),
                           (0.16, 0.16, 1.70), _m(MAT, "stone_warm"), bev=0.006))
    parts.append(K.cyl("bt_ring", T @ Ts(0, -1.2, dz + 1.72), 3.72, 0.20, _m(MAT, "stone_warm"),
                       seg=28))
    parts.append(K.sphere("bt_dome", T @ Ts(0, -1.2, dz + 1.78), 3.62, tile, seg=28, ring=14,
                          squash=0.62))
    parts.append(K.cyl("bt_lan", T @ Ts(0, -1.2, dz + 4.05), 0.62, 0.86, stone, seg=12))
    parts.append(K.cone("bt_lanc", T @ Ts(0, -1.2, dz + 4.62), 0.78, 0.40, tile, seg=12))
    parts.append(K.cyl("bt_fin", T @ Ts(0, -1.2, dz + 4.95), 0.09, 0.34, _m(MAT, "brass"),
                       seg=8))
    # steam: two low stacks at the rear corners
    for s in (-1, 1):
        sx = s * (w * 0.5 - 1.10)
        parts += _chimney("bt_sm%d" % s, T, sx, -d * 0.5 + 1.20, z_eave, z_eave + 1.55,
                          stone, w=0.56, pots=0)
        for i in range(3):
            parts.append(K.sphere("bt_sp%d_%d" % (s, i),
                                  T @ Ts(sx + s * i * 0.16, -d * 0.5 + 1.20,
                                         z_eave + 1.75 + i * 0.52),
                                  0.22 + i * 0.13, _m(MAT, "plaster_white"), seg=10, ring=6))
    # water: a spout and a channel in front of the portico
    parts.append(K.box("bt_chan", T @ Ts(0, d * 0.5 + 2.05, 0.10), (7.40, 0.90, 0.20), stone,
                       bev=0.02))
    parts.append(K.box("bt_wat", T @ Ts(0, d * 0.5 + 2.05, 0.18), (7.10, 0.66, 0.08), water))
    parts.append(K.cyl("bt_spout", T @ Ts(-3.10, d * 0.5 + 1.30, 1.05, rx=D2R(90)), 0.11, 0.55,
                       iron, seg=10))
    parts += _bench(T, -4.60, d * 0.5 + 2.90, 0, _m(MAT, "wood"), 2.0)
    # towels on a rail
    parts.append(K.cyl("bt_twr", T @ Ts(4.55, d * 0.5 + 0.42, 1.90, rz=D2R(90)), 0.045, 2.20,
                       iron, seg=8))
    for i in range(4):
        parts.append(K.box("bt_tw%d" % i, T @ Ts(4.55, d * 0.5 + 0.42, 1.52 - i * 0.0),
                           (0.04, 0.34, 0.80), _m(MAT, ("plaster_white", "cloth_blue")[i % 2])))
    return parts


# --------------------------------------------------------------------------
# 19. mill - undershot water wheel, flume, sack hoist
# --------------------------------------------------------------------------
def mill(MAT, rng, T=None, **kw):
    # The wheel hangs off the flank, so shift the body inboard by the same
    # amount: the footprint stays centred on the plot even though the building
    # is not.

    T = (T or Ts(0, 0, 0)) @ Ts(-0.9, 0, 0)
    w, d, fh, pl, pitch = 8.6, 9.0, 3.10, 0.42, 48
    stone = _m(MAT, "stone")
    wall = _m(MAT, "plaster")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    wood = _m(MAT, "wood")
    water = _m(MAT, "water")
    parts = []
    dh = 2.45
    parts, z_eave, _ops = _shell("ml", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 1.35, pl, dh + 0.50)],
                                 g_wins={"n": 2, "w": 0.90, "h": 1.10, "z": 1.15, "mull": 1},
                                 u_wins={"n": 3, "w": 0.95, "h": 1.20, "z": 0.80, "mull": 2},
                                 side_wins=1, back_wins=1, jetty=0.30)
    parts += _door("ml_dr", T, 0.0, d * 0.5, pl, 1.35, dh + 0.40, wood, iron, stone, steps=2)
    parts += _roof("ml_r", T, w, d, z_eave, pitch, _m(MAT, "tile_soot"), timber, "gable",
                   end_mat=wall, ov_gable=0.34)
    ridge = _ridge_z(w, d, z_eave, pitch, "gable")
    parts += _gable_wall("ml_g", T, w, d, z_eave, ridge - z_eave, wall, timber, "gable")
    # --- the wheel: two rims, twelve paddles, an axle into the building.
    # It hangs off the +X flank, which is the end of the row, so the one
    # feature that says "mill" from 60 m is not hidden behind next door.
    wx = w * 0.5 + 1.55
    wy = -0.6
    wr, ww_ = 2.55, 1.05
    wcz = 2.45
    for s in (-1, 1):
        ry = wy + s * ww_ * 0.5
        for i in range(24):
            a0 = math.tau * i / 24.0
            parts.append(K.box("ml_rim%d_%d" % (s, i),
                               T @ Ts(wx + math.cos(a0) * wr, ry, wcz + math.sin(a0) * wr,
                                      rx=-a0),
                               (0.13, 0.13, 0.72), wood, bev=0.006))
    for i in range(12):
        a = math.tau * i / 12.0
        parts.append(K.box("ml_pad%d" % i,
                           T @ Ts(wx + math.cos(a) * (wr - 0.06), wy, wcz + math.sin(a) *
                                  (wr - 0.06), rx=-a),
                           (0.16, ww_ - 0.14, 0.92), wood, bev=0.008))
        parts.append(K.box("ml_spk%d" % i,
                           T @ Ts(wx + math.cos(a) * wr * 0.5, wy, wcz + math.sin(a) * wr * 0.5,
                                  rx=-a),
                           (0.11, 0.11, wr), wood))
    parts.append(K.cyl("ml_hub", T @ Ts(wx, wy, wcz, ry=D2R(90)), 0.30, ww_ + 0.40, iron, seg=14))
    parts.append(K.cyl("ml_axle", T @ Ts(wx - ww_ * 0.5 - 0.55, wy, wcz, ry=D2R(90)), 0.14, 1.90,
                       iron, seg=12))
    # --- flume above the wheel + the tail race below it
    parts.append(K.box("ml_flume", T @ Ts(wx - 0.55, wy, wcz + 3.05, rx=D2R(-9)),
                       (1.10, 1.30, 0.14), wood, bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("ml_fls%d" % s, T @ Ts(wx - 0.55, wy + s * 0.64, wcz + 3.10,
                                                  rx=D2R(-9)), (1.10, 0.10, 0.42), wood))
    parts.append(K.box("ml_race", T @ Ts(wx, wy, 0.12), (3.40, 1.70, 0.24), stone, bev=0.02))
    parts.append(K.box("ml_racew", T @ Ts(wx, wy, 0.22), (3.10, 1.44, 0.06), water))
    # --- sack hoist: a beam out of the gable with a rope and a hook.  It sits
    # at mid-height of the gable, where the wall is still a couple of metres
    # wide; up at ridge-0.35 the triangle is ~0.4 m across and the same beam
    # reads as a plank floating over the roof.
    hbz = z_eave + (ridge - z_eave) * 0.52
    hby = d * 0.5 + 1.30
    parts.append(K.box("ml_hb", T @ Ts(-0.4, hby, hbz), (0.20, 2.90, 0.22), timber, bev=0.01))
    parts.append(K.box("ml_hbr", T @ Ts(-0.4, d * 0.5 + 0.30, hbz - 0.62, rx=D2R(38)),
                       (0.14, 1.45, 0.16), timber))
    parts.append(K.box("ml_hbr2", T @ Ts(-0.4, hby - 0.10, hbz - 0.62),
                       (0.14, 0.14, 0.62), timber))
    parts.append(K.cyl("ml_hpu", T @ Ts(-0.4, hby + 1.05, hbz - 0.28, ry=D2R(90)), 0.15, 0.12,
                       iron, seg=10))
    parts.append(K.cyl("ml_hro", T @ Ts(-0.4, hby + 1.05, hbz - 1.35), 0.022, 2.10, iron,
                       seg=6))
    parts += _sack(T, -0.4, hby + 1.05, hbz - 2.55, _m(MAT, "sand"))
    parts += _sack(T, 2.45, d * 0.5 + 0.72, 0, _m(MAT, "sand"))
    parts += _sack(T, 2.95, d * 0.5 + 0.55, 0, _m(MAT, "sand"))
    parts += H.crate("ml_cr0", T @ Ts(3.35, d * 0.5 + 0.95, 0), 0.58, wood)
    return parts


# --------------------------------------------------------------------------
# 20. warehouse - three storeys of loading doors, hoist beam, beam scale
# --------------------------------------------------------------------------
def warehouse(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 13.0, 9.0, 3.00, 0.40, 40
    stone = _m(MAT, "stone")
    wall = _m(MAT, "brick")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    wood = _m(MAT, "wood")
    parts = []
    parts, z_eave, _ops = _shell("wh", T, w, d, 3, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(-4.10, 2.60, pl, 3.05), (2.20, 2.20, pl, 2.95)],
                                 g_wins={"n": 0, "w": 1.0, "h": 1.0, "z": 1.0},
                                 u_wins=None, side_wins=0, back_wins=2, jetty=0.0)
    for i, (dx, dw) in enumerate(((-4.10, 2.60), (2.20, 2.20))):
        parts += H.door_arched("wh_dd%d" % i, T @ Ts(dx, d * 0.5 + 0.01, pl), dw, 3.05, wood,
                               iron, stone=stone, steps=1, double=True)
    parts += _roof("wh_r", T, w, d, z_eave, pitch, _m(MAT, "tile_soot"), timber, "eaves",
                   end_mat=wall, ov_gable=0.40)
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # loading doors on the upper floors: big plain openings with iron jambs,
    # a plank leaf hanging open on the frame
    for f in range(1, 3):
        bz = pl + fh * f
        for i, dx in enumerate((-4.10, 2.20)):
            parts.append(K.box("wh_ld%d_%d" % (f, i), T @ Ts(dx, d * 0.5 + 0.03, bz + 1.05),
                               (1.90, 0.10, 2.10), dark))
            for s in (-1, 1):
                parts.append(K.box("wh_lj%d_%d_%d" % (f, i, s),
                                   T @ Ts(dx + s * 1.02, d * 0.5 + 0.08, bz + 1.05),
                                   (0.16, 0.20, 2.24), stone, bev=0.01))
            parts.append(K.box("wh_lh%d_%d" % (f, i), T @ Ts(dx, d * 0.5 + 0.10, bz + 2.18),
                               (2.30, 0.24, 0.20), stone, bev=0.01))
            parts.append(K.box("wh_lf%d_%d" % (f, i), T @ Ts(dx + 1.02, d * 0.5 + 0.42,
                                                             bz + 1.02, rz=D2R(-62)),
                               (1.70, 0.08, 2.00), wood, bev=0.01))
            parts.append(K.cyl("wh_lr%d_%d" % (f, i), T @ Ts(dx, d * 0.5 + 0.30, bz + 2.34,
                                                             ry=D2R(90)), 0.10, 2.30, iron, seg=8))
    # hoist beam projecting over the street with a block and fall.  At ridge
    # -0.55 the beam's root sits above the gable wall, so it reads as a plank
    # hanging in the sky (the same defect class as the old floating louvre on
    # the house roofs).  Mid-gable the wall is wide enough to socket it, and a
    # brace ties the outer end back down.
    hbz = z_eave + (ridge - z_eave) * 0.58
    parts.append(K.box("wh_hb", T @ Ts(-4.10, d * 0.5 + 1.55, hbz),
                       (0.26, 3.60, 0.26), timber, bev=0.012))
    parts.append(K.box("wh_hbx", T @ Ts(-4.10, d * 0.5 + 0.10, hbz - 1.05, rx=D2R(-40)),
                       (0.20, 2.10, 0.20), timber, bev=0.01))
    parts.append(K.box("wh_hbr", T @ Ts(-4.10, d * 0.5 + 3.05, hbz - 0.55), (0.18, 0.18, 1.05),
                       timber))
    parts.append(K.box("wh_hbb", T @ Ts(-4.10, d * 0.5 + 3.05, hbz - 1.20), (0.34, 0.30, 0.34),
                       iron, bev=0.02))
    parts.append(K.cyl("wh_hr", T @ Ts(-4.10, d * 0.5 + 3.05, hbz - 2.55), 0.03, 4.70, iron,
                       seg=6))
    parts += _sack(T, -4.10, d * 0.5 + 3.05, hbz - 4.85, _m(MAT, "sand_dark"))
    # beam scale in front of the doors, weights on the pan
    parts.append(K.box("wh_scp", T @ Ts(5.10, d * 0.5 + 1.05, 0.14), (1.50, 0.90, 0.28), stone,
                       bev=0.02))
    parts.append(K.box("wh_scu", T @ Ts(5.10, d * 0.5 + 1.05, 1.42), (0.16, 0.16, 2.60), timber))
    parts.append(K.box("wh_scb", T @ Ts(5.10, d * 0.5 + 1.05, 2.68), (2.60, 0.16, 0.16), timber,
                       bev=0.008))
    parts.append(K.cyl("wh_scd", T @ Ts(5.85, d * 0.5 + 1.05, 2.02), 0.03, 1.30, iron, seg=6))
    parts.append(K.box("wh_scp2", T @ Ts(5.85, d * 0.5 + 1.05, 1.32), (0.62, 0.62, 0.10), iron,
                       bev=0.01))
    for i in range(3):
        parts.append(K.cyl("wh_sw%d" % i, T @ Ts(5.85 + (i - 1) * 0.16, d * 0.5 + 1.05, 1.44),
                           0.09, 0.16, iron, seg=8))
    for i, (cx, cz) in enumerate(((-6.1, 0.0), (-6.1, 0.62), (-2.55, 0.0), (0.55, 0.0),
                                  (0.55, 0.60))):
        parts += H.crate("wh_cr%d" % i, T @ Ts(cx, d * 0.5 + 0.70 + (i % 2) * 0.55, cz),
                         0.62, wood)
    for i, bx in enumerate((-4.9, -4.15)):
        parts += H.barrel("wh_br%d" % i, T @ Ts(bx, d * 0.5 + 1.55, 0), 0.30, 0.86, wood, iron)
    parts += H.cart("wh_ct", T @ Ts(3.30, d * 0.5 + 2.40, 0, rz=D2R(14)), wood, iron)
    return parts


# --------------------------------------------------------------------------
# 21. library - buttressed stone front, tall traceried windows, stair turret
# --------------------------------------------------------------------------
def library(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 13.0, 10.0, 3.70, 0.50, 40
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_warm")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    parts = []
    dh = 2.85
    parts, z_eave, _ops = _shell("lb", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 2.00, pl, dh + 0.60)],
                                 g_wins={"n": 2, "w": 1.15, "h": 2.05, "z": 1.10, "mull": 2,
                                         "hood": True},
                                 u_wins={"n": 5, "w": 1.05, "h": 2.30, "z": 0.62, "mull": 3},
                                 side_wins=2, back_wins=3, jetty=0.0)
    parts += _door("lb_dr", T, 0.0, d * 0.5, pl, 2.00, dh + 0.50, _m(MAT, "wood"), iron, stone,
                   steps=4, double=True)
    parts += _roof("lb_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall, ov_gable=0.40)
    # buttresses between the bays: the only vertical rhythm a stone front has
    for bx in (-5.55, -2.75, 2.75, 5.55):
        parts += _pier("lb_bt%.1f" % bx, T, bx, d * 0.5 + 0.06, pl - 0.10, z_eave - 0.26,
                       0.84, 0.50, stone, _m(MAT, "stone_warm"))
    # oculus over the door + a stone band under the eaves
    parts += H.rose_window("lb_rs", T @ Ts(0, d * 0.5 + 0.02, pl + dh + 1.55), 0.72,
                           _m(MAT, "stone_warm"), glass, lobes=10, depth=0.40, seg=24)
    parts.append(K.box("lb_bd", T @ Ts(0, d * 0.5 + 0.06, z_eave - 0.20), (w + 0.16, 0.16,
                                                                          0.26), stone, bev=0.02))
    # stair turret at the left end, spired
    tx = -w * 0.5 - 1.55
    parts.append(K.cyl("lb_tw", T @ Ts(tx, -0.9, z_eave * 0.5 + 0.30), 1.55, z_eave + 1.10,
                       stone, seg=16))
    parts.append(K.cyl("lb_tc", T @ Ts(tx, -0.9, z_eave + 1.22), 1.78, 0.24,
                       _m(MAT, "stone_warm"), seg=16))
    parts += H.spire("lb_sp", T @ Ts(tx, -0.9, z_eave + 1.30), 1.72, 5.00, _m(MAT, "slate"),
                     seg=12)
    for i in range(3):
        parts.append(K.box("lb_td%d" % i, T @ Ts(tx + 1.28, -0.9 + (i - 1) * 1.30,
                                                  3.20 + i * 1.45), (0.16, 0.42, 0.78), dark))
    parts += H.statue("lb_st", T @ Ts(0, d * 0.5 + 2.40, 0), 1.85, _m(MAT, "stone_warm"))
    parts.append(K.box("lb_stp", T @ Ts(0, d * 0.5 + 2.40, 0.30), (1.30, 1.30, 0.60), stone,
                       bev=0.02))
    for i, bx in enumerate((-3.55, 3.55)):
        parts += _bench(T, bx, d * 0.5 + 0.72, 0, _m(MAT, "wood"), 1.7)
    return parts


# --------------------------------------------------------------------------
# 22. auction house - six-column portico, pediment, rostrum, vault gate
# --------------------------------------------------------------------------
def auction_house(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 12.0, 9.6, 3.55, 0.55, 38
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_warm")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    gold = _m(MAT, "gold")
    parts = []
    dh = 2.70
    parts, z_eave, _ops = _shell("ah", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 2.20, pl, dh + 0.60)],
                                 g_wins={"n": 2, "w": 1.10, "h": 1.60, "z": 0.85, "mull": 2,
                                         "hood": True},
                                 u_wins={"n": 5, "w": 1.00, "h": 1.70, "z": 0.70, "mull": 2},
                                 side_wins=2, back_wins=2, jetty=0.0)
    parts += _door("ah_dr", T, 0.0, d * 0.5, pl, 2.20, dh + 0.55, _m(MAT, "wood"), iron, stone,
                   steps=4, double=True)
    parts += _roof("ah_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall, ov_gable=0.40)
    # six-column portico across the whole front.  The porch roof has to stop
    # under the first-floor sills (4.62 m): carried any higher it passes in
    # front of the window bottoms and the urns on top of it sit on the sills.
    pz = pl + 2.95
    cols = (-5.05, -3.03, -1.01, 1.01, 3.03, 5.05)
    for i, cx in enumerate(cols):
        parts.append(K.cyl("ah_col%d" % i, T @ Ts(cx, d * 0.5 + 1.55, pz * 0.5 + 0.10),
                           0.30, pz, stone, seg=16, r2=0.26))
        parts.append(K.box("ah_cb%d" % i, T @ Ts(cx, d * 0.5 + 1.55, 0.16), (0.80, 0.80, 0.34),
                           stone, bev=0.02))
        parts.append(K.box("ah_cc%d" % i, T @ Ts(cx, d * 0.5 + 1.55, pz + 0.16),
                           (0.76, 0.76, 0.20), stone, bev=0.02))
    parts.append(K.box("ah_ent", T @ Ts(0, d * 0.5 + 1.55, pz + 0.42), (11.40, 2.10, 0.42),
                       stone, bev=0.03))
    parts.append(K.box("ah_ent2", T @ Ts(0, d * 0.5 + 1.55, pz + 0.70), (10.90, 1.80, 0.18),
                       _m(MAT, "stone_warm"), bev=0.02))
    # rostrum: a stone podium with a timber deck rail, not a crate
    rx, ry = -3.95, d * 0.5 + 2.55
    parts.append(K.box("ah_ros", T @ Ts(rx, ry, 0.55), (2.60, 1.90, 1.10), stone, bev=0.02))
    parts.append(K.box("ah_rost", T @ Ts(rx, ry, 1.12), (2.70, 2.00, 0.10), timber, bev=0.01))
    for i in range(3):
        parts.append(K.box("ah_rst%d" % i, T @ Ts(rx, ry + 1.06 + i * 0.30, 1.00 - i * 0.30),
                           (1.70, 0.32, 0.20), stone, bev=0.01))
    for s in (-1, 1):
        parts.append(K.box("ah_rr%d" % s, T @ Ts(rx, ry + s * 0.95, 1.34),
                           (2.70, 0.10, 0.34), timber, bev=0.01))
    parts.append(K.box("ah_lec", T @ Ts(rx, ry - 0.30, 1.82, rx=D2R(-16)), (0.72, 0.52, 0.10),
                       timber, bev=0.008))
    parts.append(K.box("ah_lec2", T @ Ts(rx, ry - 0.30, 1.41), (0.10, 0.10, 0.62), timber))
    # bell on a gallows frame over the rostrum
    for s in (-1, 1):
        parts.append(K.box("ah_bp%d" % s, T @ Ts(rx + s * 0.95, ry - 0.55, 1.10 + 1.55),
                           (0.13, 0.13, 3.10), timber, bev=0.01))
    parts.append(K.box("ah_bb", T @ Ts(rx, ry - 0.55, 4.42), (2.10, 0.16, 0.18), timber, bev=0.01))
    parts.append(K.cyl("ah_bell", T @ Ts(rx, ry - 0.55, 4.02), 0.28, 0.44, gold, seg=14, r2=0.36))
    # vault: an iron gate set in a stone arch beside the portico
    vx = 4.95
    parts.append(K.box("ah_vs", T @ Ts(vx, d * 0.5 + 0.05, pl + 1.35), (1.70, 0.16, 2.70), dark))
    for i in range(5):
        parts.append(K.box("ah_vg%d" % i, T @ Ts(vx - 0.60 + i * 0.30, d * 0.5 + 0.16,
                                                 pl + 1.35), (0.09, 0.09, 2.55), iron, bev=0.006))
    for i in range(3):
        parts.append(K.box("ah_vh%d" % i, T @ Ts(vx, d * 0.5 + 0.16, pl + 0.40 + i * 0.95),
                           (1.45, 0.07, 0.09), iron))
    parts.append(K.box("ah_vf", T @ Ts(vx, d * 0.5 + 0.24, pl + 1.35), (1.96, 0.18, 2.96), stone,
                       bev=0.02))
    return parts


# --------------------------------------------------------------------------
# 23. noble manor - gatehouse, courtyard, turret, crest
# --------------------------------------------------------------------------
def noble_manor(MAT, rng, T=None, **kw):
    T = T or Ts(0, 0, 0)
    w, d, fh, pl, pitch = 13.0, 9.0, 3.40, 0.50, 42
    stone = _m(MAT, "stone")
    wall = _m(MAT, "stone_warm")
    timber = _m(MAT, "wood_dark")
    glass = _m(MAT, "glass")
    dark = _m(MAT, "void")
    iron = _m(MAT, "iron")
    parts = []
    dh = 2.60
    parts, z_eave, _ops = _shell("nm", T, w, d, 2, fh, pl, wall, stone, timber, glass, dark,
                                 g_holes=[(0.0, 1.70, pl, dh + 0.60)],
                                 g_wins={"n": 2, "w": 1.10, "h": 1.55, "z": 1.00, "mull": 2,
                                         "hood": True},
                                 u_wins={"n": 5, "w": 1.05, "h": 1.55, "z": 0.72, "mull": 2},
                                 side_wins=2, back_wins=3, jetty=0.0)
    parts += _door("nm_dr", T, 0.0, d * 0.5, pl, 1.70, dh + 0.50, _m(MAT, "wood"), iron, stone,
                   steps=3, double=True)
    parts += _roof("nm_r", T, w, d, z_eave, pitch, _m(MAT, "slate"), timber, "eaves",
                   end_mat=wall, ov_gable=0.42)
    ridge = _ridge_z(w, d, z_eave, pitch, "eaves")
    # corner turret right of the door, spired like the castle's
    tx = 4.85
    parts.append(K.cyl("nm_tw", T @ Ts(tx, d * 0.5 + 0.30, z_eave * 0.55 + 0.30), 1.35,
                       z_eave * 1.10 + 0.60, wall, seg=16))
    parts.append(K.cyl("nm_tc", T @ Ts(tx, d * 0.5 + 0.30, z_eave * 1.10 + 0.80), 1.58, 0.26,
                       stone, seg=16))
    parts += H.crenel("nm_tcr", T @ Ts(tx, d * 0.5 + 0.30, z_eave * 1.10 + 1.02), 3.2,
                      merlon=0.34, gap=0.30, h=0.44, depth=0.34, mat=stone)
    parts += H.spire("nm_sp", T @ Ts(tx, d * 0.5 + 0.30, z_eave * 1.10 + 1.20), 1.52, 3.60,
                     _m(MAT, "slate"), seg=12)
    parts += H.banner("nm_bn", T @ Ts(tx, d * 0.5 + 0.30, z_eave * 1.10 + 1.32), 0.70, 1.30,
                      _m(MAT, "cloth_blue"), iron, pole_h=2.4)
    gy = d * 0.5 + 5.60          # the yard, behind the gatehouse
    gw = d * 0.5 + 1.10          # the gatehouse itself, on the street line
    parts.append(K.box("nm_gh", T @ Ts(0, gw, 2.55), (5.40, 1.40, 5.10), wall, bev=0.02))
    parts.append(K.box("nm_ghc", T @ Ts(0, gw, 5.22), (5.72, 1.62, 0.24), stone, bev=0.02))
    parts += H.crenel("nm_ghk", T @ Ts(0, gw, 5.34), 5.40, merlon=0.44, gap=0.38, h=0.42,
                      depth=1.10, mat=stone)
    parts += H.door_arched("nm_ga", T @ Ts(0, gw - 0.72, 0), 2.95, 3.45, _m(MAT, "wood_dark"),
                           iron, stone=stone, steps=1, double=True)
    for i in range(5):
        parts.append(K.box("nm_gi%d" % i, T @ Ts(0, gw - 0.66, 0.34 + i * 0.60),
                           (2.70, 0.07, 0.08), iron))
    parts += C.shield("nm_sh", T @ Ts(0, gw - 0.74, 4.18), 1.05, 1.28, _m(MAT, "cloth_blue"),
                      border=stone)
    half, gapi = w * 0.5 + 1.0, 2.70
    seg = half - gapi
    for s in (-1, 1):
        parts.append(K.box("nm_gw%d" % s, T @ Ts(s * (gapi + seg * 0.5), gw, 1.32),
                           (seg, 0.44, 2.64), wall, bev=0.02))
        parts.append(K.box("nm_gwc%d" % s, T @ Ts(s * (gapi + seg * 0.5), gw, 2.70),
                           (seg + 0.2, 0.60, 0.16), stone, bev=0.02))
    # fountain in the courtyard + two topiary
    parts.append(K.cyl("nm_fb", T @ Ts(-3.30, gy - 2.60, 0.34), 1.35, 0.68, stone, seg=18))
    parts.append(K.cyl("nm_fw2", T @ Ts(-3.30, gy - 2.60, 0.60), 1.16, 0.10, _m(MAT, "water"),
                       seg=18))
    parts.append(K.cyl("nm_fp", T @ Ts(-3.30, gy - 2.60, 1.05), 0.22, 1.30, stone, seg=10))
    parts.append(K.sphere("nm_fs", T @ Ts(-3.30, gy - 2.60, 1.72), 0.30, stone, seg=12, ring=8))
    for i, (px, py) in enumerate(((3.95, gy - 2.30), (3.95, gy - 3.90))):
        parts.append(K.cyl("nm_pt%d" % i, T @ Ts(px, py, 0.30), 0.26, 0.60, stone, seg=10))
        parts.append(K.sphere("nm_ps%d" % i, T @ Ts(px, py, 1.28), 0.62, _m(MAT, "leaf"), seg=12,
                              ring=8))
    parts += H.cart("nm_ct", T @ Ts(4.10, gy - 5.40, 0, rz=D2R(76)), _m(MAT, "wood"), iron)
    parts += H.lantern_post("nm_lp0", T @ Ts(-2.30, gy - 0.90, 0), 2.60, iron,
                            _m(MAT, "glow_warm"))
    parts += H.lantern_post("nm_lp1", T @ Ts(2.30, gy - 0.90, 0), 2.60, iron,
                            _m(MAT, "glow_warm"))
    return parts


# --------------------------------------------------------------------------
# registry - footprints, dispatch, street preview
# --------------------------------------------------------------------------
BUILDERS = {
    "blacksmith": blacksmith,
    "adventurers_guild": adventurers_guild,
    "magic_shop": magic_shop,
    "clothier": clothier,
    "general_store": general_store,
    "tavern": tavern,
    "bakery": bakery,
    "stable": stable,
    "chapel": chapel,
    # -- military / watch ---------------------------------------------------
    "training_ground": training_ground,
    "barracks": barracks,
    "knights_hq": knights_hq,
    "guard_post": guard_post,
    "armory": armory,
    # -- trade / service / civic --------------------------------------------
    "weaponsmith": weaponsmith,
    "apothecary": apothecary,
    "inn": inn,
    "bathhouse": bathhouse,
    "mill": mill,
    "warehouse": warehouse,
    "library": library,
    "auction_house": auction_house,
    "noble_manor": noble_manor,
}

# (w, d, h).  h is the tallest point of the silhouette (ridge, stack or spire),
# not the eave: the street layout and any scattered placement both size the
# camera off this, so it is the single source of truth.
FOOT = {
    "blacksmith": (10.6, 10.0, 11.6),
    "adventurers_guild": (12.0, 12.0, 12.0),
    "magic_shop": (8.4, 9.2, 17.2),
    "clothier": (7.6, 10.3, 10.6),
    "general_store": (11.8, 11.1, 11.6),
    "tavern": (11.4, 11.9, 16.7),
    "bakery": (11.2, 10.1, 10.4),
    "stable": (17.0, 11.6, 10.1),
    "chapel": (10.2, 16.3, 16.5),
    "training_ground": (16.0, 13.4, 5.6),
    "barracks": (23.6, 10.2, 16.2),
    "knights_hq": (12.4, 19.2, 17.8),
    "guard_post": (8.6, 10.6, 8.8),
    "armory": (9.4, 10.4, 11.4),
    "weaponsmith": (10.4, 12.3, 13.7),
    "apothecary": (10.0, 10.2, 12.1),
    "inn": (13.2, 13.7, 16.0),
    "bathhouse": (11.4, 15.2, 11.0),
    "mill": (12.8, 12.4, 12.1),
    "warehouse": (13.8, 13.6, 13.8),
    "library": (16.8, 13.7, 15.6),
    "auction_house": (13.0, 14.6, 12.0),
    "noble_manor": (15.2, 16.6, 14.2),
}

# Measured extents of a finished build, in the same (x, y, h) order as FOOT.
# Taken with H.bbox over a full build with the yard furniture switched off, so
# these are the building volumes the layout engine reserves; the barrels and
# crates stand up to ~1.2 m further out on +Y, in the street, which is where
# street furniture belongs.  An underestimate jams two buildings into each
# other, an overestimate opens an alley that is not in the scene.
FOOTPRINT = {
    "adventurers_guild": (12.0, 12.5, 11.9),
    "apothecary": (10.0, 11.1, 12.1),
    "armory": (9.5, 11.0, 11.0),
    "auction_house": (12.9, 15.6, 12.0),
    "bakery": (11.1, 10.8, 10.4),
    "barracks": (22.6, 11.1, 17.7),
    "bathhouse": (11.5, 16.4, 11.0),
    "blacksmith": (10.6, 10.3, 11.6),
    "chapel": (10.1, 16.5, 16.5),
    "clothier": (7.7, 10.9, 10.6),
    "general_store": (11.7, 11.9, 11.6),
    "guard_post": (9.6, 11.8, 9.0),
    "inn": (13.2, 13.8, 16.0),
    "knights_hq": (12.7, 14.6, 17.2),
    "library": (16.8, 14.6, 15.8),
    "magic_shop": (7.9, 9.5, 17.2),
    "mill": (13.4, 13.4, 12.6),
    "noble_manor": (15.2, 15.6, 14.2),
    "stable": (16.7, 12.3, 10.1),
    "tavern": (11.3, 12.8, 16.7),
    "training_ground": (15.1, 15.4, 5.4),
    "warehouse": (13.9, 13.9, 13.8),
    "weaponsmith": (10.3, 13.2, 13.7),
}

KINDS_1 = ["blacksmith", "adventurers_guild", "magic_shop", "clothier",
           "general_store", "tavern", "bakery", "stable", "chapel"]
KINDS_2 = ["training_ground", "barracks", "knights_hq", "guard_post", "armory"]
KINDS_3 = ["weaponsmith", "apothecary", "inn", "bathhouse", "warehouse",
           "library", "auction_house", "noble_manor", "mill"]


def kinds():
    return sorted(BUILDERS)


def footprint(kind):
    """(x, y) measured footprint of one building; height rides in FOOTPRINT."""
    if kind not in FOOTPRINT:
        raise KeyError("unknown shop kind %r; have %s" % (kind, ", ".join(kinds())))
    x, y, _h = FOOTPRINT[kind]
    return (x, y)


_SIGN_DEFAULT = (0.56, 3.70, "diamond", 0.92, "cloth_blue")

# kind -> (x as a fraction of the half-width, board height, icon, bracket arm)
# One hung sign per shop, at the same height so the street reads as a row of
# businesses rather than of houses.  Icons are silhouettes: see _pict().
SIGNS = {
    "blacksmith":        (0.62, 3.62, "horseshoe", 0.95, "cloth_red"),
    "adventurers_guild": (0.58, 3.72, "shield", 0.95, "cloth_blue"),
    "magic_shop":        (0.60, 3.95, "star", 0.90, "cloth_purple"),
    "clothier":          (0.56, 4.05, "shears", 0.90, "cloth_red"),
    "general_store":     (0.60, 3.70, "barrel", 0.95, "cloth_green"),
    "tavern":            (0.50, 3.78, "mug", 1.05, "cloth_green"),
    "bakery":            (0.58, 3.58, "bread", 0.90, "cloth_red"),
    "stable":            (0.55, 3.30, "horseshoe", 0.95, "cloth_green"),
    "chapel":            (0.50, 3.45, "cross", 0.85, "cloth_blue"),
    # The yard has no front wall to hang a bracket on - a sign floating at the
    # street edge would read as a bug, so it gets none.
    "training_ground":   None,
    "barracks":          (0.66, 3.30, "shield", 0.95, "cloth_blue"),
    # The gatehouse stands in front of the hall, so a bracket on the hall would
    # be inside it.  Identity comes from the arch, towers and flag row.
    "knights_hq":        None,
    "guard_post":        (0.58, 3.05, "shield", 0.85, "cloth_blue"),
    "armory":            (0.56, 3.35, "shield", 0.95, "cloth_red"),
    "weaponsmith":       (0.62, 3.50, "sword", 0.95, "cloth_red"),
    "apothecary":        (0.50, 3.55, "moon", 0.90, "cloth_green"),
    "inn":               (0.50, 3.60, "bed", 1.05, "cloth_green"),
    "bathhouse":         (0.50, 4.20, "wave", 0.90, "cloth_blue"),
    "mill":              (0.55, 3.40, "wheel", 0.95, "cloth_gold"),
    "warehouse":         (0.52, 4.20, "crate", 0.95, "cloth_blue"),
    "library":           (0.50, 3.60, "book", 0.90, "cloth_red"),
    "auction_house":     (0.50, 4.10, "coin", 0.95, "cloth_gold"),
    "noble_manor":       (0.56, 3.70, "shield", 0.95, "cloth_blue"),
}


def build(kind, MAT=None, rng=None, at=None, rz=0.0, **kw):
    """Build one building.  Origin = footprint centre, ground z = 0, facade +Y.

    at : optional (x, y) or (x, y, z) placement, in metres.  The transform is
         baked into the mesh with H.apply rather than left on the objects, so
         every returned object keeps an identity matrix and a layout engine can
         merge geometry without flattening transforms first.
    rz : spin about the building's own origin, in degrees.
    """
    if kind not in BUILDERS:
        raise KeyError("unknown shop kind %r; have %s" % (kind, ", ".join(kinds())))
    if MAT is None:
        MAT = make_materials()
    if rng is None:
        rng = random.Random(7)
    MAT_CACHE.clear()
    MAT_CACHE.update(MAT)
    parts = _flat(BUILDERS[kind](MAT, rng, **kw))
    lo, hi = H.bbox(parts)
    _sg = SIGNS.get(kind, _SIGN_DEFAULT)
    if _sg:
        _xf, _sz, _icon, _arm, _flag = _sg
        parts += _hang(kind + "sg", Ts(0, 0, 0), _xf * hi.x, _sz, _icon,
                       arm=_arm, y=hi.y, flag=_m(MAT, _flag))
    # += and not =: the yard is street furniture *besides* the building, and an
    # assignment here drops the building from the returned list while its 280
    # parts stay in the scene -- every shop then ships as bare barrels and the
    # city build leaks 280 objects per shop (measured: block 1 took 0.6 s and
    # block 18 took 55 s once those orphans piled up).
    parts += _yard(kind, Ts(0, 0, 0), (hi.x - lo.x), hi.y, MAT,
                   seed=sum(ord(c) for c in kind) % 97,
                   area=(hi.x - lo.x) * (hi.y - lo.y), fence=YARD_FENCE)
    if at is not None or rz:
        ax = ay = az = 0.0
        if at is not None:
            ax, ay = at[0], at[1]
            az = at[2] if len(at) > 2 else 0.0
        parts = H.apply(parts, Ts(ax, ay, az, rz=D2R(rz)))
    return parts


def _street(names, gaps=None, d_ref=10.0):
    """Lay the buildings along X, all facing +Y, fronts on one straight line.

    The origin of every building is the centre of its footprint, so a deep
    building's facade would otherwise sit several metres further forward than
    its neighbours'.  Each one is shifted back by (d_ref - d)/2 so the whole row
    shares a street line - a staggered frontage reads as "houses dropped on a
    field", a shared one reads as a street.

    gaps : per-gap spacing list (len(names) - 1); the default leaves real party
           walls and two alleys, because equal gaps are what makes a row look
           like a scatter.
    """
    MAT = make_materials()
    MAT_CACHE.update(MAT)
    rng = random.Random(11)
    if gaps is None:
        gaps = [0.55, 0.60, 2.30, 0.50, 0.55, 0.60, 1.70, 0.55][:len(names) - 1]
    total = sum(FOOT[k][0] for k in names) + sum(gaps)
    x = -total * 0.5
    out, spans = [], []
    for i, k in enumerate(names):
        w, d, h = FOOT[k]
        hp = build(k, MAT, rng)
        lo, hi = H.bbox(hp)
        print("[shops] %-17s parts=%4d tris=%6d  bbox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f"
              % (k, len(hp), H.tri_count(hp), lo.x, hi.x, lo.y, hi.y, lo.z, hi.z),
              flush=True)
        out += H.apply(hp, Ts(x + w * 0.5, (d_ref - d) * 0.5, 0))
        spans.append((x, x + w))
        x += w + (gaps[i] if i < len(gaps) else 0.6)
    return out, spans


def _paving(lo, hi, mat, rng=None):
    """Flagstone apron in front of the row.

    Without it the buildings read as objects dropped on an infinite plane, which
    is exactly the "pile of houses" look this module exists to avoid.

    The far edge is ragged on purpose.  A clean rectangle ends in a straight
    line across the ground and reads as a carpet someone unrolled; broken edges
    read as a plaza that keeps going past the frame.
    """
    rng = rng or random.Random(7)
    out = []
    y0 = 5.0
    i = 0
    x = lo.x - 1.4
    while x < hi.x + 1.4:
        # ragged far edge + ragged ends, but never shorter than the apron
        fade = math.sin((x - lo.x) * 0.13) * 1.6
        y1 = 13.6 + fade + rng.uniform(-0.55, 0.55)
        if x < lo.x - 0.2 or x > hi.x + 0.2:
            y1 -= rng.uniform(1.2, 4.0)
        j = 0
        y = y0
        while y < y1:
            w = 1.02 + (0.12 if (i + j) % 3 == 0 else 0.0)
            out.append(K.box("pave_%d_%d" % (i, j),
                             Ts(x + w * 0.5, y + 0.42, -0.03),
                             (w - 0.07, 0.78, 0.10), mat, bev=0.012))
            y += 0.86
            j += 1
        x += 1.08
        i += 1
    out.append(K.box("kerb", Ts((lo.x + hi.x) * 0.5, y0 - 0.20, 0.02),
                     (hi.x - lo.x + 2.0, 0.36, 0.16), mat, bev=0.02))
    return out


def preview(batch=1, samples=128):
    """Three 1600x900 street views of one batch of buildings."""
    names = KINDS_1 if batch <= 1 else (KINDS_2 if batch == 2 else KINDS_3)
    H._clear()
    MAT = make_materials()
    parts, spans = _street(names)
    lo, hi = H.bbox(parts)
    parts += _paving(lo, hi, _m(MAT, "pave"))
    print("[shops] TOTAL parts=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (len(parts), H.tri_count(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z),
          flush=True)
    H.diorama_floor(_m(MAT, "stone"))
    # A 24 m strip of paving in front of nine buildings still leaves the rest
    # of the frame an empty grey field, which is what makes a row read as a
    # display stand instead of a street.  A dirt apron under everything costs
    # 2 tris and fills the frame; cobbles are left to _paving, because a stone
    # texture stretched over 260 m tiles into long stripes that read as decking.
    ground = K.box("shops_ground", Ts(0, 0, 0.012), (260.0, 120.0, 0.024),
                   _m(MAT, "dirt"))
    H.setup_world(fill=2.1)
    # The shared key sun in hd_common comes from (+X, -Y), i.e. it lights every
    # building's BACK.  This row faces +Y, so the whole street rendered as a
    # grey slab.  Rotate the key 180 deg about Z so it rakes the facades - the
    # module keeps its own local +Y front, the preview just points the light at
    # it.  (Does not touch hd_common; the lamp is found by name.)
    _sun = bpy.data.objects.get("sun")
    if _sun is not None:
        _sun.rotation_euler = (math.radians(48), 0.0, math.radians(38 + 180))
        _sun.data.energy = 5.0
    H.setup_engine(samples=samples, res=(1600, 900))
    stem = "hd_shops" if batch == 1 else "hd_shops%d" % batch
    R = "E:/My World/Blender/renders/kingdom/%s_%%s.png" % stem
    cx = (lo.x + hi.x) * 0.5
    mid = spans[len(spans) // 2][0]
    halves = ((lo.x, mid), (mid, hi.x))
    views = [("a", (lo.x - 26.0, hi.y + 30.0, 15.0), (cx - 8.0, 0.0, 5.2), 24.0)]
    for tag, (x0, x1) in zip(("b", "c"), halves):
        span = x1 - x0
        views.append((tag, ((x0 + x1) * 0.5, span * 0.72 + 20.0, 8.2),
                      ((x0 + x1) * 0.5, 0.0, 6.4), 32.0))
    # The acceptance bar for this module is "would a player accept this from
    # 15 m", so one view is parked at exactly that distance on a mid-row
    # frontage.  Every distant view flatters a facade; this one cannot.
    mb = spans[len(spans) // 2]
    bxc = (mb[0] + mb[1]) * 0.5
    # 15 m is the distance the acceptance question is asked at, and a 42 mm
    # lens at 15 m frames about nine metres of wall - i.e. two windows, not a
    # building.  20 mm on a 36 mm sensor is ~54 deg vertical, which is what a
    # player actually sees standing that close.
    views.append(("d", (bxc + 5.2, 15.0, 4.6), (bxc, 0.0, 8.1), 20.0))
    for tag, loc, tgt, lens in views:
        H.render_to(R % tag, H.camera("cam_" + tag, loc, tgt, lens=lens))
    print("[shops] wrote %s{a,b,c}.png" % stem, flush=True)


def _args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    batch, samples = 1, 128
    for i, a in enumerate(argv):
        if a == "--batch" and i + 1 < len(argv):
            batch = int(argv[i + 1])
        if a == "--samples" and i + 1 < len(argv):
            samples = int(argv[i + 1])
    return batch, samples


if __name__ == "__main__":
    _b, _s = _args()
    preview(_b, _s)


