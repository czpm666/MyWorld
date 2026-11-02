"""hd_houses.py - high-detail street houses and town buildings for the capital.

Every house is built as a facade with REAL window openings (the wall is built
around a list of openings), so windows sit in a hole instead of floating on a
flat box.  Style follows the capital's palette: stone plinths, plaster or ashlar
walls, visible timber framing, jettied upper floors, tiled/slate roofs with
courses, dormers, chimneys, shop fronts and street clutter.

Detail kit
----------
The parametric parts (roof with real tile courses, recessed windows with
reveals/sills/shutters, planked doors, embedded timber framing, jetties,
plinths, dormers, chimneys, hoists, awnings, battlements) live in
`hd_houses_parts.py`.  This module is the composition layer: it decides what a
timber house, a manor or a warehouse actually looks like.

Budget note: at the player camera (pitch 52 deg, 34 m, vertical FOV 30 deg) the
frame is 39.5 px per metre.  Nothing smaller than ~0.05 m survives, so bevel
modifiers are pure cost here - the old file spent 23,658 evaluated triangles per
house on 1.5 cm bevels that are sub-pixel from the game camera.  This version
has no bevels at all and spends the budget on silhouette instead.

Public API
----------
house(MAT, rng, kind="timber", w=7.0, d=8.5, floors=2, frontage="eaves") -> list
    kind: timber | stone | shop | inn | manor | tower | warehouse | craft
    frontage: "eaves" (ridge parallel to the street) or "gable"
build_set(MAT, rng, count=8) -> list      # one of each kind, lined up for preview

Run:
    blender -b --factory-startup --python hd_houses.py -- --kind timber
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
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
import hd_houses_parts as P

Ts = K.T_at
TAU = 2.0 * math.pi


# --------------------------------------------------------------------------
# type signatures
# --------------------------------------------------------------------------
# One row per kind.  The eight kinds have to be separable at a glance from 34 m,
# so they differ in *all* of: storey height, wall material, roof pitch, roof
# type, jetty, ornament density and colour bias.  Nothing here is decoration
# for its own sake - each entry is a silhouette or tonal decision.
_STYLE = {
    # wall       pitch jetty  fh   frame stud  nw   ww    wh   shut  roof
    "timber": dict(wall="plaster", pitch=50, jetty=0.34, fh=2.88, frame=True,
                   stud=0.92, nw=2, ww=0.90, wh=1.18, shut=0.55, roof="gable",
                   plinth=0.40, moss=0.70, dormers=2, gutter=True, hood=True,
                   steps=3, slate=False, quoin=False, orn=2),
    "stone": dict(wall="stone", pitch=46, jetty=0.0, fh=3.02, frame=False,
                  stud=1.0, nw=3, ww=0.84, wh=1.36, shut=0.12, roof="gable",
                  plinth=0.55, moss=0.45, dormers=1, gutter=False, hood=False,
                  steps=3, slate=False, quoin=True, orn=1),
    "craft": dict(wall="plaster", pitch=48, jetty=0.30, fh=2.86, frame=True,
                  stud=0.98, nw=2, ww=0.88, wh=1.12, shut=0.45, roof="gable",
                  plinth=0.38, moss=0.60, dormers=1, gutter=True, hood=False,
                  steps=3, slate=False, quoin=False, orn=3),
    "shop": dict(wall="plaster", pitch=51, jetty=0.36, fh=2.94, frame=True,
                 stud=0.94, nw=2, ww=0.96, wh=1.24, shut=0.50, roof="gable",
                 plinth=0.42, moss=0.55, dormers=2, gutter=True, hood=True,
                 steps=3, slate=False, quoin=False, orn=4),
    "inn": dict(wall="plaster", pitch=52, jetty=0.38, fh=2.92, frame=True,
                stud=0.90, nw=2, ww=1.02, wh=1.30, shut=0.45, roof="gable",
                plinth=0.44, moss=0.60, dormers=3, gutter=True, hood=True,
                steps=4, slate=False, quoin=False, orn=5),
    "manor": dict(wall="stone", pitch=44, jetty=0.0, fh=3.28, frame=False,
                  stud=1.0, nw=3, ww=1.02, wh=1.58, shut=0.0, roof="hip",
                  plinth=0.62, moss=0.30, dormers=0, gutter=False, hood=False,
                  steps=4, slate=False, quoin=True, orn=4),
    "warehouse": dict(wall="stone", pitch=43, jetty=0.0, fh=3.34, frame=False,
                      stud=1.0, nw=3, ww=0.78, wh=1.06, shut=0.0, roof="gable",
                      plinth=0.30, moss=0.25, dormers=1, gutter=False, hood=False,
                      steps=2, slate=True, quoin=False, orn=2),
    "tower": dict(wall="stone", pitch=58, jetty=0.0, fh=3.16, frame=False,
                  stud=1.0, nw=2, ww=0.68, wh=1.02, shut=0.0, roof="crenel",
                  plinth=0.70, moss=0.35, dormers=0, gutter=False, hood=False,
                  steps=3, slate=True, quoin=True, orn=1),
}

_KINDS = ["timber", "stone", "shop", "inn", "manor", "tower", "warehouse", "craft"]


def _win_xs(w, n, skip=None, margin=0.95, min_gap=1.35):
    """Evenly spread `n` window centres across a facade, skipping the door."""
    span = w - margin * 2.0
    if n <= 0 or span <= 0.5:
        return []
    xs = []
    for i in range(n):
        x = -span * 0.5 + span * (i + 0.5) / n
        if skip is not None and abs(x - skip[0]) < skip[1]:
            continue
        if xs and abs(x - xs[-1]) < min_gap:
            continue
        xs.append(x)
    return xs


# --------------------------------------------------------------------------
# facade helpers (public API kept for hd_shops.py)
# --------------------------------------------------------------------------
def _wall(name, T, w, h, thick, openings, mat, y=0.0):
    """A wall slab in the local XZ plane facing +Y, with real openings.

    `openings` = [(x, ow, z0, oh), ...] in facade coordinates.
    Returns [one mesh] - the pier/sill/head boxes are merged so a three-storey
    facade is a single object instead of thirty.
    """
    cy = y + thick * 0.5
    specs = []
    ops = sorted(openings, key=lambda o: o[0])
    cur = -w * 0.5
    for (ox, ow, z0, oh) in ops:
        lo = ox - ow * 0.5
        hi = ox + ow * 0.5
        if lo - cur > 0.05:
            specs.append((T @ Ts((cur + lo) * 0.5, cy, h * 0.5),
                          (lo - cur, thick, h)))
        if z0 > 0.05:
            specs.append((T @ Ts(ox, cy, z0 * 0.5), (ow, thick, z0)))
        top = z0 + oh
        if h - top > 0.05:
            specs.append((T @ Ts(ox, cy, (top + h) * 0.5), (ow, thick, h - top)))
        cur = hi
    if w * 0.5 - cur > 0.05:
        specs.append((T @ Ts((cur + w * 0.5) * 0.5, cy, h * 0.5),
                      (w * 0.5 - cur, thick, h)))
    if not specs:
        return []
    return [P.boxmesh(name, specs, mat)]


def _plain_wall(name, T, w, h, thick, mat, y=0.0, openings=()):
    return _wall(name, T, w, h, thick, list(openings), mat, y)


def _window_grid(T, w, z0, wh, count, ww, frame, glass, y, arched=True,
                 shutters=None, hood=True, margin=0.9):
    """Evenly spread `count` windows across a facade of width `w`."""
    out = []
    if count <= 0:
        return out
    span = w - margin * 2.0
    step = span / count
    for i in range(count):
        x = -span * 0.5 + step * (i + 0.5)
        out += H.window_arched("wgrid_w%d" % i, T @ Ts(x, y, z0), ww, wh, frame,
                               glass, tracery=2, hood=hood, arch=arched,
                               shutters=shutters, depth=0.36)
    return out


def _rect_window(name, T, w, h, frame, glass, y=0.0, mullions=2, shutters=None):
    """Four-centred stone window with a flat head (for ashlar houses)."""
    out = []
    out.append(K.box(name + "_back", T @ Ts(0, y - 0.20, h * 0.5), (w, 0.12, h), glass))
    j = 0.22
    for s in (-1, 1):
        out.append(K.box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + j * 0.5), y - 0.04,
                                                  h * 0.5), (j, 0.34, h + j * 1.6), frame))
    out.append(K.box(name + "_lin", T @ Ts(0, y - 0.04, h + j * 0.8),
                     (w + j * 2.2, 0.36, 0.26), frame))
    out.append(K.box(name + "_sil", T @ Ts(0, y + 0.02, -0.08), (w + j * 2.6, 0.42, 0.16),
                     frame))
    for i in range(1, mullions):
        out.append(K.box(name + "_m%d" % i, T @ Ts(-w * 0.5 + w * i / mullions, y - 0.08,
                                                  h * 0.5), (0.07, 0.20, h), frame))
    for i in range(1, 3):
        out.append(K.box(name + "_t%d" % i, T @ Ts(0, y - 0.10, h * i / 3.0),
                         (w, 0.16, 0.055), frame))
    if shutters is not None:
        for s in (-1, 1):
            out.append(K.box(name + "_sh%d" % s, T @ Ts(s * (w * 0.5 + j + 0.14), y + 0.10,
                                                       h * 0.5), (0.15, 0.05, h * 0.96),
                             shutters))
    return out


def _timber_frame(T, w, z0, z1, y, mat, openings=(), stud=1.05, rails=()):
    """Close-studded framing with corner braces, proud of the plaster.

    `openings` = [(x, ow, z0, oh)] in the same space as z0/z1; only the x span
    is used, because a stud that meets a window head is cut by the plate.
    """
    ops = [(x - ow * 0.5 - 0.16, x + ow * 0.5 + 0.16)
           for (x, ow, oz0, ozh) in openings]
    out = P.timber_frame("tf", T @ Ts(0, 0, z0), w, z1 - z0, mat, ops=ops, y=y,
                         stud=stud)
    if rails:
        for z in rails:
            cut = sorted((a, b) for (a, b) in ops
                         if (z - z0) < 0.0 or True)
            x0 = -w * 0.5
            for (a, b) in cut:
                if a - x0 > 0.16:
                    out.append(K.box("tfr%.2f_%.2f" % (z, a), T @ Ts((x0 + a) * 0.5, y, z),
                                     (a - x0, 0.10, 0.16), mat))
                x0 = max(x0, b)
            if w * 0.5 - x0 > 0.16:
                out.append(K.box("tfr%.2f_e" % z, T @ Ts((x0 + w * 0.5) * 0.5, y, z),
                                 (w * 0.5 - x0, 0.10, 0.16), mat))
    return out


def _jetty(T, w, d, z, over=0.34, beam=None, corbels=6):
    """Bressumer + corbels carrying a jettied upper floor."""
    beam = beam or K.mat_wood("beam")
    return P.jetty("jt", T, w, d * 0.5, d * 0.5 + over, z, beam,
                   njoist=max(4, int(w / 0.52)), brackets=True)


def _shop_front(T, w, z, mat_wood, cloth, cloth2=None, awn_len=1.6, counter=True):
    """Open ground-floor shop: counter boards, awning, hanging sign."""
    out = []
    out.append(K.box("shop_counter", T @ Ts(0, 0.42, z + 0.48), (w * 0.86, 0.85, 0.16),
                     mat_wood))
    for s in (-1, 1):
        out.append(K.box("shop_leg%d" % s, T @ Ts(s * w * 0.36, 0.42, z + 0.24),
                         (0.12, 0.75, 0.48), mat_wood))
    for i, cm in enumerate((cloth, cloth2 or cloth)):
        y0 = 0.15 + awn_len * (0.55 if i else 0.0)
        out.append(K.box("shop_awn%d" % i,
                         T @ Ts(0, y0 + (awn_len * 0.28 if i else 0),
                                z + 1.62 + (0.22 if i else 0),
                                rx=math.radians(28 if i else -18)),
                         (w, awn_len * 0.62, 0.05), cm))
    out.append(K.box("shop_sgn_arm", T @ Ts(w * 0.42, 0.55, z + 2.3), (0.09, 1.15, 0.09),
                     mat_wood))
    out.append(K.box("shop_sgn", T @ Ts(w * 0.42, 1.05, z + 2.02), (0.06, 0.72, 0.52),
                     cloth))
    return out


def _door(T, w=1.25, h=2.35, wood=None, iron=None, stone=None, steps=2):
    wood = wood or K.mat_wood("door_wood")
    iron = iron or K.mat_metal()
    return H.door_arched("door", T, w, h, wood, iron, stone=stone, steps=steps)


# --------------------------------------------------------------------------
# articulation helpers
# --------------------------------------------------------------------------
def _quoins(name, T, w, h, mat, n=10, step=0.62, out=0.055, sides=(-1, 1)):
    """Alternating corner stones on the two street corners of an ashlar wall.

    Cheap (two merged meshes) and it is the one cue that says "cut stone"
    rather than "plaster painted grey" from 34 m.
    """
    out_p = []
    for sx in sides:
        specs = []
        z = 0.0
        i = 0
        while z < h - 0.06 and i < n:
            hh = min(step, h - z)
            cx = sx * (w * 0.5 - 0.17)
            if i % 2 == 0:
                specs.append((T @ Ts(cx, out * 0.5, z + hh * 0.5),
                              (0.34, 0.30 + out, hh)))
            else:
                specs.append((T @ Ts(sx * (w * 0.5 - 0.13), out * 0.5, z + hh * 0.5),
                              (0.26, 0.22 + out, hh)))
            z += hh
            i += 1
        if specs:
            out_p.append(P.boxmesh("%s_q%d" % (name, sx), specs, mat))
    return out_p


def _gutter(name, w, hw, eave_z, pl_h, x, lead, iron=None):
    """Lead gutter along the street eave + a corner downpipe.

    The brief asks for it and it earns its keep: a dark 0.17 m line under the
    eave separates roof from wall at the game camera, and the vertical pipe
    breaks up the facade without any window.
    """
    out = []
    out.append(K.box(name + "_g", Ts(0, hw - 0.06, eave_z - 0.055),
                     (w + 0.34, 0.17, 0.115), lead))
    out.append(K.box(name + "_gl", Ts(0, hw - 0.06, eave_z + 0.005),
                     (w + 0.34, 0.20, 0.03), lead))
    # corner downpipe: from the gutter end down the corner to the plinth
    px = x * (w * 0.5 + 0.055)
    py = hw - 0.10
    hgt = max(0.6, eave_z - pl_h - 0.10)
    out.append(K.cyl(name + "_p", Ts(px, py, pl_h + hgt * 0.5), 0.055, hgt,
                     iron or lead, seg=8))
    out.append(K.box(name + "_bend", Ts(px, py + 0.02, eave_z - 0.13),
                     (0.12, 0.16, 0.20), lead))
    return out


def _string(name, T, w, d, z, mat, proud=0.16):
    """Projecting stone band at a floor line."""
    return [K.box(name, T @ Ts(0, d * 0.5 - 0.02, z), (w + proud, 0.28, 0.17), mat)]


_AGED = set()


def _age(mat, kind, strength=1.0):
    """Apply the shared weathering recipe to one material, once per name.

    hd_surface.weather_material() is documented idempotent and bails out on
    FROZEN kinds (tile/slate/cobble/flag/ground), so calling this for every
    house is safe: only the first house of each palette variant does work.

    `strength` scales every layer of the recipe at once.  The plaster recipe
    ships deliberately faint (patch 0.14 at scale 0.22, bump 0.07), which on a
    single HD facade - rather than a whole city block - reads as an untextured
    plane.  HD houses are seen from 34 m at most, so they can afford roughly
    twice the contrast the city-wide pass uses.
    """
    if mat is None:
        return mat
    key = getattr(mat, "name", None) or id(mat)
    if key in _AGED:
        return mat
    _AGED.add(key)
    try:
        import hd_surface as SFC
        SFC.weather_material(mat, kind, strength=strength)
    except Exception as exc:
        print("[houses] weathering %s failed: %s" % (key, exc), flush=True)
    return mat


# --------------------------------------------------------------------------
# the house builder
# --------------------------------------------------------------------------
def house(MAT, rng, kind="timber", w=7.0, d=8.6, floors=2, frontage="eaves"):
    P.bind(MAT)
    st = dict(_STYLE.get(kind) or _STYLE["timber"])

    stone = MAT["stone"]
    stone_w = MAT.get("stone_warm") or stone
    plaster = MAT.get("plaster") or K.mat_plaster()
    wood = MAT.get("wood") or K.mat_wood()
    wood_dk = MAT.get("wood_dark") or wood
    glass = MAT["glass"]
    iron = MAT.get("iron") or K.mat_metal()
    tile = MAT["tile"]
    slate = MAT.get("slate")
    if slate and (st["slate"] or rng.random() < 0.20):
        tile = slate
    # medkit.mat_tile() is a brick shader evaluated in world-aligned object
    # space: on a 50 deg slope its rows run horizontally and the roof reads as
    # a masonry wall.  Re-skin it, keeping the variant colour family.
    tiles = P.roof_materials(tile)
    tile = tiles[1]
    is_stone = st["wall"] == "stone"
    wall = stone if is_stone else plaster
    trim = wood_dk

    th = 0.40                       # wall thickness
    fh = st["fh"]
    pl_h = st["plinth"]
    nfl = max(2, min(4, int(floors)))
    out = []

    # capital_hd_glue.house_mats() creates its per-variant plaster AFTER
    # capital.py has already run SFC.apply_weathering(MAT), so the HD house
    # walls reach the render with a flat, untextured, un-grimed surface.  Age
    # them here instead: weather_material() is idempotent and the material is
    # cached per variant, so this costs one pass per variant for the whole city.
    _age(plaster, "plaster", 1.85)
    _age(stone, "stone", 1.20)
    _age(stone_w, "stone_warm", 1.20)
    _age(wood, "wood", 1.35)
    _age(wood_dk, "wood_dark", 1.35)

    # ---- plinth ---------------------------------------------------------
    out += P.plinth("pl", Ts(0, 0, 0), w, d, pl_h,
                    stone_w if is_stone else stone,
                    moss=MAT.get("moss"), rng=rng,
                    spout=bool(st["gutter"] and rng.random() < 0.45))

    # ---- ground floor ---------------------------------------------------
    door_w = 1.22
    door_x = -w * 0.24
    shop_w = 2.60 if kind in ("shop", "craft") else 0.0
    g_ops = []
    win_xs = []
    if shop_w:
        g_ops.append((0.0, shop_w, 0.0, 2.30))
        door_x = w * 0.5 - 1.30
        g_ops.append((door_x, 1.12, 0.0, 2.18))
    else:
        g_ops.append((door_x, door_w, 0.0, 2.24))
        win_xs = _win_xs(w, st["nw"] + (1 if w > 8.2 else 0),
                         skip=(door_x, door_w * 0.5 + 1.15))
        for x in win_xs:
            g_ops.append((x, st["ww"], 1.02, st["wh"]))
    out += _wall("gw", Ts(0, 0, pl_h), w, fh, th, g_ops, wall, y=d * 0.5 - th)

    # door
    out += P.door("dr", Ts(door_x, d * 0.5, pl_h), w=door_w if not shop_w else 1.12,
                  h=2.18 if shop_w else 2.24, wood=wood_dk, iron=iron,
                  stone=stone_w if is_stone else stone, steps=st["steps"],
                  arch=bool(is_stone and kind != "warehouse"),
                  lamp=False, rng=rng)
    # ground-floor windows
    for i, x in enumerate(win_xs):
        out += P.window("gw%d" % i, Ts(x, d * 0.5, pl_h + 1.02), st["ww"], st["wh"],
                        frame=stone_w if is_stone else trim, glass=glass,
                        wall_mat=wall, arch="seg" if is_stone else None,
                        shutters=(wood if rng.random() < st["shut"] else None),
                        sill=True, hood=bool(st["hood"] and rng.random() < 0.6),
                        bars=(2, 1), deep=0.16,
                        flower=bool(kind == "inn" and rng.random() < 0.6), rng=rng)
    # shop front
    if shop_w:
        out.append(K.box("shp_dk", Ts(0, d * 0.5 - 0.30, pl_h + 1.16),
                         (shop_w - 0.02, 0.06, 2.28), MAT.get("void")))
        out += P.counter("shp_c", Ts(0, d * 0.5 - 0.08, pl_h), shop_w - 0.12, wood, iron)
        out += P.awning("shp_a", Ts(0, d * 0.5, pl_h + 2.44), shop_w + 0.55, 1.15,
                        tile, trim, drop=0.34, brackets=3)
        out += P.sign("shp_s", Ts(-w * 0.5 + 0.95, d * 0.5, pl_h + 3.02,
                                  rz=math.radians(90)),
                      w=0.92, h=0.60, board=wood_dk, iron=iron,
                      face=MAT.get("banner_gold"), kind="hang")
    # ground-floor timber: without this the ground floor is a blank panel and
    # the whole house reads as "walls are a different building from the top"
    if st["frame"]:
        gops = [(x - st["ww"] * 0.5 - 0.16, x + st["ww"] * 0.5 + 0.16) for x in win_xs]
        gops.append((door_x - door_w * 0.5 - 0.16, door_x + door_w * 0.5 + 0.16))
        if shop_w:
            gops.append((-shop_w * 0.5 - 0.18, shop_w * 0.5 + 0.18))
        out += P.timber_frame("tfg", Ts(0, 0, pl_h), w, fh, wood_dk, ops=gops,
                              y=d * 0.5 + 0.015, stud=st["stud"], rng=rng)

    # ---- upper floors ---------------------------------------------------
    z = pl_h + fh
    for f in range(1, nfl):
        over = st["jetty"] if f == 1 else 0.0
        ww = w + 2.0 * over
        dd = d + 2.0 * over
        if over:
            out += P.jetty("jt%d" % f, Ts(0, 0, 0), w, d * 0.5, d * 0.5 + over, z,
                           wood_dk, iron=iron, njoist=max(4, int(w / 0.52)))
        xs = _win_xs(ww, st["nw"] + (1 if ww > 8.4 else 0))
        ww_ = st["ww"]
        wh_ = st["wh"]
        z0 = 0.88
        ops = [(x, ww_, z0, wh_) for x in xs]
        out += _wall("uw%d" % f, Ts(0, 0, z), ww, fh, th, ops, wall, y=dd * 0.5 - th)
        for i, x in enumerate(xs):
            out += P.window("uw%d_%d" % (f, i), Ts(x, dd * 0.5, z + z0), ww_, wh_,
                            frame=stone_w if is_stone else trim, glass=glass,
                            wall_mat=wall, arch="seg" if is_stone else None,
                            shutters=(wood if rng.random() < st["shut"] else None),
                            sill=True, hood=bool(st["hood"] and rng.random() < 0.55),
                            bars=(2, 1), deep=0.17,
                            flower=bool(kind == "inn" and rng.random() < 0.4),
                            rng=rng)
        if st["frame"]:
            out += P.timber_frame("tf%d" % f, Ts(0, 0, z), ww, fh, wood_dk,
                                  ops=[(x - ww_ * 0.5 - 0.15, x + ww_ * 0.5 + 0.15)
                                       for x in xs],
                                  y=dd * 0.5 + 0.015, stud=st["stud"], rng=rng)
        else:
            out += _string("sc%d" % f, Ts(0, 0, 0), ww, dd, z + 0.04, stone)
        # sides: one real window per upper floor, on both flanks
        for sx in (-1, 1):
            out += _wall("sd%d_%d" % (f, sx),
                         Ts(sx * ww * 0.5, 0, z, rz=-sx * math.radians(90)),
                         dd, fh, th, [(0.0, 0.86, z0, wh_ - 0.10)], wall, y=-th)
            out += P.window("sw%d_%d" % (f, sx),
                            Ts(sx * ww * 0.5, 0, z + z0, rz=-sx * math.radians(90)),
                            0.86, wh_ - 0.10, frame=stone_w if is_stone else trim,
                            glass=glass, wall_mat=wall, sill=True, bars=(1, 1),
                            deep=0.16, rng=rng)
        out.append(K.box("ub%d" % f, Ts(0, -(dd * 0.5 - th * 0.5), z + fh * 0.5),
                         (ww, th, fh), wall))
        z += fh

    # ground-floor flanks and back
    for sx in (-1, 1):
        out.append(K.box("gs%d" % sx, Ts(sx * (w * 0.5 - th * 0.5), 0, pl_h + fh * 0.5),
                         (th, d, fh), wall))
    out.append(K.box("gb", Ts(0, -(d * 0.5 - th * 0.5), pl_h + fh * 0.5),
                     (w, th, fh), wall))

    # ---- roof -----------------------------------------------------------
    top = z
    if st["roof"] == "crenel":
        # tower: corbelled parapet, battlements, corner turret
        out += P.corbel_table("cbt", Ts(0, 0, top - 0.14), w + 0.24, stone, z=0.0)
        out.append(K.box("par", Ts(0, 0, top + 0.22), (w + 0.44, d + 0.44, 0.46), stone))
        out.append(K.box("deck", Ts(0, 0, top + 0.06), (w + 0.10, d + 0.10, 0.12),
                         stone_w))
        out += P.crenel_row("crn_f", Ts(0, d * 0.5 + 0.10, top + 0.44), w + 0.44, stone,
                            h=0.84, depth=0.40)
        out += P.crenel_row("crn_b", Ts(0, -(d * 0.5 + 0.10), top + 0.44), w + 0.44,
                            stone, h=0.84, depth=0.40)
        for sx in (-1, 1):
            out += P.crenel_row("crn_s%d" % sx,
                                Ts(sx * (w * 0.5 + 0.10), 0, top + 0.44,
                                   rz=math.radians(90)),
                                d + 0.44, stone, h=0.84, depth=0.40)
        out += P.bartizan("btz", Ts(-w * 0.5, d * 0.5, 0), top - 0.60, r=0.62, h=2.1,
                          stone=stone_w, tile=tile, end_mat=wall)
        for k, sx in enumerate((-1, 1)):
            out += P.arrow_slit("as%d" % k, Ts(sx * (w * 0.5 + 0.005), d * 0.22,
                                               top - 1.15, rz=-sx * math.radians(90)),
                                w=0.17, h=1.05, mat=stone, deep=0.24)
        return out

    pitch = st["pitch"]
    hip = st["roof"] == "hip"
    if frontage == "gable" and not hip:
        rT = Matrix.Identity(4)
        span, length = w, d
    else:
        rT = Ts(0, 0, 0, rz=math.radians(90))
        span, length = d, w
    if hip:
        rp, info = P.hip_roof("rf", rT, span, length, top, pitch, tile, trim, wall,
                              ov_v=0.34, ov_g=0.30, course=0.34, riser=0.09,
                              moss=st["moss"], rng=rng)
    else:
        rp, info = P.roof("rf", rT, span, length, top, pitch, tile, trim, wall,
                          ov_v=0.34, ov_g=0.22, course=0.34, riser=0.09,
                          moss=st["moss"], rng=rng, ridge=True, tiles=tiles)
    out += rp
    hw, rh = info["hw"], info["rh"]
    top_z = info["top_z"]

    # gable/attic volume: one wedge fills the whole roof and gives both gable
    # walls in 5 faces.  Without it the roof is a shell you can see into.
    # A hip roof is closed by its own four slopes, so it needs no wedge.
    if not hip:
        out.append(H.wedge("atc", rT @ Ts(0, 0, top), 2.0 * hw - 0.10, rh,
                           length + 0.06, wall))

    # timber in the street gable
    if st["frame"] and not hip:
        if frontage == "gable":
            out += P.gable_frame("gf", rT @ Ts(0, length * 0.5 + 0.04, top),
                                 hw - 0.06, rh, wood_dk)
        else:
            for sy in (-1, 1):
                out += P.gable_frame("gf%d" % sy,
                                     rT @ Ts(0, sy * (length * 0.5 + 0.04), top),
                                     hw - 0.06, rh, wood_dk)

    # ---- chimney --------------------------------------------------------
    # A capital chimney is a masonry mass, not a pipe: wide shaft, a corbelled
    # cap that overhangs, and a stack of pots.  It has to beat the ridge in
    # silhouette or it disappears at 34 m.  Keep it NEAR THE RIDGE: a stack
    # that starts half way down a 6 m slope has to be 3 m tall before it clears
    # the tiles, and then it reads as a factory flue rather than a chimney.
    big = kind in ("manor", "warehouse", "inn", "stone")
    lx = rng.choice((-1, 1)) * hw * rng.uniform(0.08, 0.26)
    ly = rng.uniform(-0.34, 0.34) * length
    surf = top + rh * (1.0 - abs(lx) / hw)
    ch_T = rT @ Ts(lx, ly, 0.0)
    ch_top = top_z + rng.uniform(0.30, 0.72)
    out += P.chimney("ch", ch_T, surf - 1.15, ch_top,
                     stone_w if is_stone else stone, MAT.get("pot") or stone_w,
                     soot=MAT.get("soot"), pots=(3 if big else 2),
                     w=(1.18 if big else 0.96), d=(0.96 if big else 0.80), rng=rng)
    if "F" in info:
        for k, s in enumerate((-1, 1)):
            F = rT @ info["F"][s]
            out += P.chimney_stain("cs%d" % k, F, abs(lx) * 0.85, ly * 0.6,
                                   MAT.get("soot"), length=1.4)

    # ---- dormers --------------------------------------------------------
    # At the player camera the roof plane is seen face-on, so course relief is
    # edge-on and nearly invisible.  What DOES read is anything that stands up
    # out of the slope, which makes dormers the highest-value roof detail.
    nd = int(st["dormers"])
    if frontage == "eaves" and "dormer_T" in info:
        du = info["sl"] * rng.uniform(0.26, 0.44)
        for k in range(nd):
            u = du
            v = (k - (nd - 1) * 0.5) * (length / float(nd + 1.2))
            dT = rT @ info["dormer_T"](1, u, v)
            out += P.dormer("dm%d" % k, dT, w=1.42, h=0.98, d=1.02, pitch=pitch,
                            wall=wall, trim=trim, tile=tile, frame_mat=trim,
                            glass=glass, rng=rng, tiles=tiles)
    elif frontage == "gable":
        # the street sees the gable triangle, so it gets a loft door and its
        # iron straps instead of a dormer
        gy = length * 0.5 + 0.045
        out.append(K.box("ldoor", rT @ Ts(0, gy, top + rh * 0.34),
                         (0.78, 0.10, 0.96), wood_dk))
        for i in (-1, 1):
            out.append(K.box("ldoor_b%d" % i,
                             rT @ Ts(i * 0.30, gy + 0.06, top + rh * 0.34),
                             (0.07, 0.05, 0.98), iron))
        out.append(K.box("ldoor_l", rT @ Ts(0, gy + 0.06, top + rh * 0.34 + 0.50),
                         (0.92, 0.09, 0.11), wood_dk))

    # ---- gutter ---------------------------------------------------------
    if st["gutter"] and frontage == "eaves":
        out += _gutter("gt", w, hw, top, pl_h, rng.choice((-1, 1)),
                       MAT.get("lead") or iron, iron)

    # ---- kind ornaments -------------------------------------------------
    yf = d * 0.5
    if kind == "warehouse":
        # cathead + pulley + loading door, tucked under the eave
        out += P.hoist("ho", Ts(-w * 0.30, yf, 0, rz=math.radians(90)), top - 0.34,
                       wood=wood_dk, iron=iron, load=False)
        out.append(K.box("ld", Ts(-w * 0.30, d * 0.5 - 0.02, z - 1.35),
                         (1.30, 0.10, 1.60), wood_dk))
        out.append(K.box("ld2", Ts(-w * 0.30, d * 0.5 + 0.02, z - 0.52),
                         (1.46, 0.16, 0.14), wood_dk))
    if kind in ("inn", "manor"):
        out += P.balcony("bal", Ts(0, d * 0.5 + st["jetty"], pl_h + fh * 1.02),
                         w * 0.52, 0.62, stone_w if is_stone else stone, iron=iron,
                         tile=tile, trim=trim)
    if kind == "inn":
        out += P.sign("in_s", Ts(w * 0.5 - 0.30, yf, pl_h + fh + 0.55,
                                 rz=math.radians(90)),
                      w=1.15, h=0.78, board=wood_dk, iron=iron,
                      face=MAT.get("banner_gold"), kind="hang")
        out += P.market_board("in_mb", Ts(w * 0.5 + 1.30, yf + 1.15, 0), w=1.30, h=0.80,
                              board=wood_dk, face=MAT.get("banner_red"), iron=iron)
    if kind in ("timber", "shop", "inn", "craft"):
        out += H.barrel("barrel", Ts(w * 0.5 - 0.80, yf + 0.62, 0),
                        wood=MAT.get("wood"), hoop=iron)
        out += H.crate("crate", Ts(-w * 0.5 + 0.62, yf + 0.52, 0.31), s=0.62,
                       wood=MAT.get("wood"))
    if kind == "manor":
        # symmetric wings: a short stone screen wall each side of the door
        for sx in (-1, 1):
            out.append(K.box("man%d" % sx, Ts(sx * (w * 0.5 - 0.55), yf + 0.16,
                                              pl_h + 0.55),
                             (0.62, 0.30, 1.10), stone_w))
            out.append(K.box("manc%d" % sx, Ts(sx * (w * 0.5 - 0.55), yf + 0.16,
                                               pl_h + 1.14),
                             (0.78, 0.42, 0.14), stone))
    return out


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------
def make_mats():
    MAT = {
        "stone": K.mat_stone(),
        "stone_warm": K.mat_stone("stone_sand", base="#8d8168", dark="#5b5342",
                                  light="#a89b7f", scale=2.0),
        "wood": K.mat_wood(),
        "wood_dark": K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12),
        "tile": K.mat_tile(),
        "slate": K.mat_tile("roof_slate", base="#4a5560", dark="#333c46", light="#5f6d7a"),
        "plaster": K.mat_plaster(),
        "glass": K.mat_glass(),
        "iron": K.mat_metal(),
        "banner_red": K.mat_cloth("banner_red", "#8e2b26"),
        "banner_gold": K.mat_cloth("banner_gold", "#b98f3a"),
        "glow_warm": K.mat_metal("glow_warm", "#ffd9a0"),
    }
    # the detail kit's own palette: oak, lead, void, moss, lichen, soot, pot,
    # glass, iron.  Merged here so capital_hd_glue.house_mats() carries it and
    # bind() finds it already present on every house.
    MAT.update(P.house_materials())
    return MAT


def build_set(MAT, rng):
    out = []
    x = -22.0
    for i, kind in enumerate(_KINDS):
        w = 6.4 + (i % 3) * 0.9
        d = 8.0 + (i % 2) * 1.2
        floors = 2 if kind not in ("inn", "warehouse", "tower") else 3
        front = "gable" if i % 3 == 0 else "eaves"
        hp = house(MAT, rng, kind=kind, w=w, d=d, floors=floors, frontage=front)
        out += H.apply(hp, Ts(x, 0, 0))
        x += w + 3.4
    return out


def preview():
    H._clear()
    MAT = make_mats()
    rng = random.Random(4)
    parts = build_set(MAT, rng)
    lo, hi = H.bbox(parts)
    print("[houses] parts=%d tris=%d bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
          % (len(parts), H.tri_count(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z),
          flush=True)
    H.diorama_floor(MAT["stone"])
    H.setup_world(fill=2.1)
    H.setup_engine(samples=192, res=(1600, 900))
    cx = (lo.x + hi.x) * 0.5
    R = "E:/My World/Blender/renders/kingdom/hd_houses_%s.png"
    views = [
        ("a", (cx - 40.0, 38.0, 17.0), (cx, 2.0, 6.2), 45.0),
        ("b", (cx, 42.0, 4.2), (cx, 2.0, 5.6), 32.0),
        ("c", (cx - 14.0, 30.0, 40.0), (cx, 2.0, 4.0), 40.0),
    ]
    for tag, loc, tgt, lens in views:
        H.render_to(R % tag, H.camera("cam_" + tag, loc, tgt, lens=lens))
    cam = H.camera("close", (0, 26, 2.2), (0, 0, 6.0), lens=42)
    H.render_to(R % "close", cam)
    cam2 = H.camera("row", (-3.0, 31.0, 4.4), (24.0, 0.0, 5.4), lens=40)
    H.render_to(R % "row", cam2)
    print("[houses] done", flush=True)


if __name__ == "__main__":
    preview()
