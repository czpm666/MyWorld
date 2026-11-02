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
            # The long stone reaches 0.10 PAST the corner and the short one only
            # 0.03, so the pair wraps round onto the flank and the corner reads
            # as alternating quoins from the side as well as from the street.
            # Zero extra faces - only the box extents move - and it is the one
            # cue that tells two identical terrace neighbours apart when you are
            # looking down the avenue at their side walls.
            if i % 2 == 0:
                specs.append((T @ Ts(sx * (w * 0.5 - 0.12), out * 0.5, z + hh * 0.5),
                              (0.44, 0.30 + out, hh)))
            else:
                specs.append((T @ Ts(sx * (w * 0.5 - 0.115), out * 0.5, z + hh * 0.5),
                              (0.29, 0.22 + out, hh)))
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


def _win_batch(name, T, xs, z0, w, h, trim, wood, glass, void, reveal,
               deep=0.16, bars=True, sill=True, hood=False, shut=None,
               rng=None, p=0.0, zs=None, hs=None, brick=None, brick_xs=(),
               shut_ang=0.42):
    """N identical windows on one wall -> a handful of merged meshes.

    Same read as hd_houses_parts.window() - dark void, recessed glass, a wood
    frame, a stone sill and drip, and a light lining to the opening - but the
    boxes are merged per material for the whole wall.  This is what makes the
    side and back walls affordable: a 28-house block has ~340 of these windows
    and one object each would blow the 3 s build budget.

    `zs` / `hs` give a sill height and an opening height per window, because a
    real flank has its openings at different heights, not on a grid.  Windows
    listed in `brick_xs` are blocked up with masonry (`brick` material) instead
    of glazed - one per flank is enough to say the elevation has a history.
    Shutters are hinged leaves swung off the wall by ~25 deg: a flat panel
    disappears at a grazing angle, a swung leaf keeps its shadow and its colour.
    """
    S = {"trim": [], "wood": [], "glass": [], "void": [], "rev": [], "shut": []}
    jamb = 0.08
    yf = -deep * 0.42
    yr = -deep * 0.5 + 0.02
    for i, x in enumerate(xs):
        zz = zs[i] if zs else z0
        hh = hs[i] if hs else h
        X = T @ Ts(x, 0, zz)
        blocked = brick is not None and i in brick_xs
        if blocked:
            # filled in with masonry: a recessed panel plus the old frame left
            # standing round it.  Cheap and it reads at 34 m as "was a window".
            S["trim"].append((X @ Ts(0, -0.05, hh * 0.5),
                              (w - 0.04, 0.10, hh - 0.04)))
        else:
            S["void"].append((X @ Ts(0, -deep - 0.05, hh * 0.5),
                              (w - 0.02, 0.06, hh - 0.02)))
            S["glass"].append((X @ Ts(0, -deep, hh * 0.5),
                               (w - 0.03, 0.03, hh - 0.02)))
        S["wood"].append((X @ Ts(-(w * 0.5 - jamb * 0.5), yf, hh * 0.5),
                          (jamb, 0.10, hh)))
        S["wood"].append((X @ Ts(w * 0.5 - jamb * 0.5, yf, hh * 0.5),
                          (jamb, 0.10, hh)))
        S["wood"].append((X @ Ts(0, yf, jamb * 0.45), (w, 0.10, jamb * 0.9)))
        S["wood"].append((X @ Ts(0, yf, hh - jamb * 0.45), (w, 0.10, jamb * 0.9)))
        if bars and not blocked:
            S["wood"].append((X @ Ts(0, yf - 0.01, hh * 0.5), (0.055, 0.09, hh)))
            S["wood"].append((X @ Ts(0, yf - 0.01, hh * 0.46), (w, 0.08, 0.045)))
        if reveal is not None:
            S["rev"].append((X @ Ts(-(w * 0.5 - 0.02), yr, hh * 0.5),
                             (0.045, deep, hh)))
            S["rev"].append((X @ Ts(w * 0.5 - 0.02, yr, hh * 0.5),
                             (0.045, deep, hh)))
            S["rev"].append((X @ Ts(0, yr, hh - 0.02), (w, deep, 0.045)))
        if sill:
            S["trim"].append((X @ Ts(0, 0.06, -0.06), (w + 0.34, 0.40, 0.14)))
            S["trim"].append((X @ Ts(0, 0.20, -0.15), (w + 0.26, 0.14, 0.07)))
        if hood:
            S["trim"].append((X @ Ts(0, 0.045, hh + 0.09), (w + 0.46, 0.22, 0.13)))
        # half-open shutters: each leaf is hinged at the reveal and swung out,
        # so it is a box with a real shadow instead of a decal on the wall
        if shut is not None and rng is not None and rng.random() < p:
            lw = w * 0.46
            for s in (-1, 1):
                ang = s * shut_ang * rng.uniform(0.55, 1.30)
                H = X @ Ts(s * (w * 0.5 + 0.045), 0.045, hh * 0.5)
                H = H @ Ts(0, 0, 0, rz=ang)
                S["shut"].append((H @ Ts(s * lw * 0.5, 0, 0),
                                  (lw, 0.05, hh * 0.96)))
    out = []
    for k, mat in (("trim", trim), ("wood", wood), ("glass", glass),
                   ("void", void), ("rev", reveal), ("shut", shut)):
        if S[k] and mat is not None:
            out.append(P.boxmesh("%s_%s" % (name, k), S[k], mat))
    return out


def _band(name, T, w, z, mat, h=0.16, proud=0.12):
    """Projecting string course on any wall face (T's local +Y is outward).

    `T` carries the wall's base height, `z` is relative to it.  This is the
    cheapest articulation there is - one box, 12 tris - and at 39.5 px/m the
    0.12 m projection throws a shadow line two pixels wide along the whole
    wall, which is exactly the cue that separates "wall" from "wall panel".
    """
    return [K.box(name, T @ Ts(0, proud * 0.5 - 0.02, z),
                  (w + 0.02, proud + 0.05, h), mat)]


def _pipe(name, T, z0, z1, iron, lead, r=0.05, brackets=4, hopper=True):
    """Iron downpipe standing 6 cm off a wall face (local +Y outward).

    One 8-sided cylinder plus a shoe, a hopper and four brackets: ~90 tris for
    a full-height vertical that reads at the game camera, because it is the
    only dark line on an otherwise empty flank.
    """
    h = max(0.5, z1 - z0)
    out = [K.cyl(name, T @ Ts(0, r + 0.035, z0 + h * 0.5), r, h, iron, seg=8)]
    out.append(K.box(name + "_shoe", T @ Ts(0, r + 0.03, z0 + 0.09),
                     (0.14, 0.16, 0.18), iron))
    if hopper:
        out.append(K.box(name + "_hop", T @ Ts(0, r + 0.05, z1 - 0.14),
                         (0.24, 0.18, 0.28), lead))
    for i in range(max(1, brackets)):
        zz = z0 + h * (i + 0.5) / max(1, brackets)
        out.append(K.box("%s_br%d" % (name, i), T @ Ts(0, r + 0.02, zz),
                         (0.09, 0.10, 0.055), lead))
    return out


def _stack(name, T, z0, z1, stone, pot, w=0.92, d=0.42, pots=2, soot=None):
    """Chimney / chimney breast standing on the OUTSIDE of a flank wall.

    Two brief items in one ~38-face object: a vertical that divides the biggest
    blank plane a house owns, and something that stands up out of the roof -
    which at 52 deg and 34 m is all the game camera can actually see.  T's
    local +Y is the wall's outward normal, x runs along the wall.
    """
    out = []
    h = max(0.60, z1 - z0)
    yb = d * 0.5 - 0.02
    out.append(K.box(name + "_b", T @ Ts(0, d * 0.5, z0 + 0.40),
                     (w + 0.18, d + 0.14, 0.80), stone))
    out.append(K.box(name + "_s", T @ Ts(0, yb, z0 + 0.80 + (h - 0.80) * 0.5),
                     (w, d, max(0.15, h - 0.80)), stone))
    out.append(K.box(name + "_c", T @ Ts(0, yb, z1 + 0.06),
                     (w + 0.26, d + 0.16, 0.15), stone))
    for i in range(max(1, pots)):
        if pots > 1:
            px = (i - (pots - 1) * 0.5) * (w * 0.58 / float(pots - 1))
        else:
            px = 0.0
        out.append(K.cyl("%s_pt%d" % (name, i), T @ Ts(px, yb, z1 + 0.34),
                         0.105, 0.42, pot, seg=8))
    if soot is not None:
        out.append(P.slab(name + "_st", T @ Ts(0, d + 0.008, z0 + 0.55 + h * 0.5),
                          w * 0.78, h * 0.78, 0.020, soot))
    return out


def _gable_dress(name, T, hw, rh, rng, wood, wood_dk, void, trim, door=False,
                 light=False):
    """Break up a gable triangle: barge boards, purlin ends, a louvred vent.

    The triangle is the largest single plane on the house - rh = hw*tan(pitch),
    i.e. 5 m tall over a 9 m frontage - and it sits at the TOP of the facade,
    which is exactly what the 52 deg camera looks at when it comes down an
    avenue.  It had no window and no vertical division on it at all, only the
    horizontal eave cornice underneath: that is the pale banded plane in the
    city shot.  T is the gable face (local +Y out, origin on the eave line,
    local X across the triangle, +Z up to the apex at rh).
    """
    out = []
    # barge boards on both rakes: two long diagonals that cut the triangle
    for s in (-1, 1):
        b = P.bar("%s_bb%d" % (name, s), T,
                  (s * (hw - 0.09), 0.045, 0.09), (0.0, 0.045, rh - 0.06),
                  0.15, wood, wide=0.24)
        if b is not None:
            out.append(b)
    # purlin ends: the roof frame showing through the gable face.  On a back
    # gable the 52 deg camera never sees the whole triangle, so `light` keeps
    # the barge boards and the vent and drops these.
    if not light:
        for i, k in enumerate((0.34, 0.68)):
            for s in (-1, 1):
                out.append(K.box("%s_pu%d%d" % (name, i, s),
                                 T @ Ts(s * (hw * (1.0 - k) - 0.17), 0.05,
                                        rh * k),
                                 (0.15, 0.10, 0.15), wood_dk))
    # louvred loft vent, high in the triangle where nothing else is
    V = T @ Ts(0, 0, rh * 0.44)
    out.append(K.box(name + "_vv", V @ Ts(0, -0.055, 0), (0.64, 0.10, 0.54), void))
    for i in range(3):
        out.append(K.box("%s_vs%d" % (name, i), V @ Ts(0, 0.022, -0.15 + i * 0.15),
                         (0.60, 0.05, 0.055), wood_dk))
    if not light:
        out.append(K.box(name + "_vl", V @ Ts(0, 0.030, 0.30), (0.78, 0.10, 0.11),
                         trim))
        out.append(K.box(name + "_vs2", V @ Ts(0, 0.030, -0.30), (0.78, 0.09, 0.09),
                         trim))
    if door:
        # plank loft door with its iron straps, the way a real gable is loaded
        D = T @ Ts(0, 0, rh * 0.20)
        out.append(K.box(name + "_ld", D @ Ts(0, 0.005, 0), (0.80, 0.09, 0.94),
                         wood_dk))
        for s in (-1, 1):
            out.append(K.box("%s_ls%d" % (name, s), D @ Ts(s * 0.24, 0.055, 0.10),
                             (0.09, 0.05, 0.74), wood))
        out.append(K.box(name + "_ll", D @ Ts(0, 0.035, 0.50), (0.94, 0.12, 0.10),
                         wood))
    return out


def _flank_dress(name, T, T_lo, w, z_lo, z_hi, rng, patch_m, moss_m, lead,
                 wood, eave=None, rafters=True):
    """Everything that keeps a d x 9 m flank from reading as a banded panel.

    All of it is either a hole, a colour change or a 2 cm shadow line, so it
    survives the near-grazing angle the avenue shots give a side wall: repair
    patches, damp at the foot, a lead apron under the eave, rafter ends, and -
    on some houses - climbing ivy and a pilaster.  ~40-90 faces a flank.

    `z_lo`/`z_hi` bound the band this call covers (one storey), because the
    flank plane moves out by the jetty on the first floor; `eave` is passed only
    for the topmost band, which is where the apron and the rafter ends live.
    """
    out = []
    z_lo = max(0.55, z_lo)
    z_hi = max(z_lo + 0.60, z_hi)
    # repair patches: different stone or a cement skim over old plaster, 2.6 cm
    # proud so they throw a shadow, sized and placed at random
    for i in range(1 + (1 if rng.random() < 0.50 else 0)):
        pw = rng.uniform(0.55, 1.45)
        ph = rng.uniform(0.45, 1.00)
        px = rng.uniform(-w * 0.5 + pw * 0.55, w * 0.5 - pw * 0.55)
        pz = rng.uniform(z_lo, z_hi)
        out.append(P.slab("%s_rp%d" % (name, i), T @ Ts(px, 0.013, pz),
                          pw, ph, 0.026, patch_m))
    # damp and moss climbing out of the plinth, on the GROUND-floor plane
    if T_lo is not None:
        for i in range(1 if rng.random() < 0.65 else 2):
            dw = rng.uniform(1.10, 2.40)
            dh = rng.uniform(0.30, 0.72)
            dx = rng.uniform(-w * 0.5 + dw * 0.5, w * 0.5 - dw * 0.5)
            out.append(P.slab("%s_dm%d" % (name, i),
                              T_lo @ Ts(dx, 0.013, z_lo - 0.40 + dh * 0.5),
                              dw, dh, 0.026, moss_m))
    # climbing ivy up one corner: a dark green mass on a pale wall is the
    # cheapest plane-breaker in the file (6 faces a clump)
    if rng.random() < 0.34:
        cs = rng.choice((-1, 1))
        n = rng.randint(3, 5)
        for i in range(n):
            t = i / float(max(1, n - 1))
            zz = z_lo + t * (z_hi - z_lo) * rng.uniform(0.55, 1.0)
            lw = rng.uniform(0.50, 1.05) * (1.0 - 0.35 * t)
            lh = rng.uniform(0.38, 0.80)
            xx = cs * (w * 0.5 - rng.uniform(0.28, 1.30))
            out.append(P.slab("%s_iv%d" % (name, i), T @ Ts(xx, 0.016, zz),
                              lw, lh, 0.030, moss_m))
    # pilaster: one clean vertical that divides the face corner to corner
    if rng.random() < 0.30:
        bx = rng.uniform(-w * 0.26, w * 0.26)
        hz = max(0.60, z_hi + 0.45 - z_lo)
        out.append(K.box(name + "_pl", T @ Ts(bx, 0.085, z_lo + hz * 0.5 - 0.20),
                         (0.52, 0.17, hz), patch_m))
    # lead apron / gutter along the top of the wall, plus the rafter ends that
    # carry the eave - only reached on the topmost band
    if eave is not None:
        out.append(K.box(name + "_gu", T @ Ts(0, 0.05, eave - 0.055),
                         (w + 0.02, 0.15, 0.10), lead))
        if rafters:
            # rafter ends every 1.7 m: at 34 m one rafter is ~6 px wide, so a
            # 16 cm pitch (which is what the file's other houses use) would be
            # paid for in faces and never seen
            n = max(3, int(w / 1.70))
            for i in range(n):
                rx = -w * 0.5 + (i + 0.5) * w / n
                out.append(K.box("%s_ra%d" % (name, i),
                                 T @ Ts(rx, 0.11, eave - 0.17),
                                 (0.10, 0.26, 0.13), wood))
    return out


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
    # Projecting trim (sill / drip / lintel / string course / cornice) in stone.
    # On plaster the dressing must be DARKER than the wall; on an ashlar wall,
    # which bleaches to a pale grey in sun, it has to be darker still - a sill
    # in the wall's own material is invisible at 34 m and the window collapses
    # into a black rectangle in a grey plane.
    stone_t = MAT.get("stone_trim") or stone_w
    stone_d = MAT.get("stone_dark") or stone_t
    trim_m = stone_d if is_stone else stone_t

    th = 0.40                       # wall thickness
    fh = st["fh"]
    pl_h = st["plinth"]
    nfl = max(2, min(4, int(floors)))
    # openings per flank (long face, d) and per back wall (wide face, w).  One
    # 0.86 m hole in the middle of a 9 m flank is the "45 % blank wall" the
    # gate shot shows; two or three is what makes the face read as a building
    # rather than a retaining wall.
    # Openings per flank.  This threshold is where the "40 % flat wall" bug
    # came from: capital.py row_along() builds d = 6.0-9.0 m, not the 10-13 m
    # the brief quoted, so a real city flank fell into the old `d >= 7.2` slot
    # and got TWO windows on a 7 m face - and from a grazing avenue angle, none.
    nsw = 3 if d >= 8.8 else (2 if d >= 6.2 else 1)
    nsb = 3 if w >= 8.6 else (2 if w >= 5.6 else 1)
    if kind == "tower":
        nsw = nsb = 1
    elif kind == "warehouse":
        nsw = min(nsw, 2)
        nsb = min(nsb, 2)
    # Window size for the faces that are not the street: bigger than the old
    # 0.86 m hole.  At 34 m a 0.86 m opening is 25 px of black - it reads as a
    # hole in the wall, not as a window, and with no frame or shutter around it
    # the flank stays a blank panel.
    wwin = 1.02 if d >= 6.4 else 0.88
    whin = max(0.95, st["wh"] - 0.06)
    # Which flank carries the chimney breast, and where along it.  One per
    # house: a stack is the only thing in this kit that is BOTH a vertical
    # division of the flank and a silhouette above the roof, which is the only
    # kind of detail the 52 deg camera can resolve at 34 m.
    stack_sx = rng.choice((-1, 1))
    stack_lx = (d * 0.5) - 0.74
    out = []

    # capital_hd_glue.house_mats() creates its per-variant plaster AFTER
    # capital.py has already run SFC.apply_weathering(MAT), so the HD house
    # walls reach the render with a flat, untextured, un-grimed surface.  Age
    # them here instead: weather_material() is idempotent and the material is
    # cached per variant, so this costs one pass per variant for the whole city.
    _age(plaster, "plaster", 1.85)
    _age(stone, "stone", 1.20)
    _age(stone_w, "stone_warm", 1.20)
    _age(stone_t, "stone", 0.80)
    _age(stone_d, "stone", 0.80)
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
                        bars=(2, 1), deep=0.16, trim=trim_m, reveal=plaster,
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
                            bars=(2, 1), deep=0.17, trim=trim_m, reveal=plaster,
                            flower=bool(kind == "inn" and rng.random() < 0.4),
                            rng=rng)
        if st["frame"]:
            out += P.timber_frame("tf%d" % f, Ts(0, 0, z), ww, fh, wood_dk,
                                  ops=[(x - ww_ * 0.5 - 0.15, x + ww_ * 0.5 + 0.15)
                                       for x in xs],
                                  y=dd * 0.5 + 0.015, stud=st["stud"], rng=rng)
        else:
            out += _string("sc%d" % f, Ts(0, 0, 0), ww, dd, z + 0.04, stone)
        # ---- flanks ------------------------------------------------------
        # This is the face a player walks past all day.  It used to be one
        # `_wall` box with a single 0.86 m hole, which at the game camera reads
        # as a blank panel (see renders/kingdom/look/fac_old_flank.png).  Now:
        # two openings, stone sills, a lit reveal, a string course at the floor
        # line, corner stones and - on the timber kinds - a real stud frame.
        for sx in (-1, 1):
            TT = Ts(sx * ww * 0.5, 0, z, rz=-sx * math.radians(90))
            skip = (stack_lx, 0.74) if sx == stack_sx else None
            sxs = _win_xs(dd, nsw, margin=0.85, min_gap=1.05, skip=skip)
            # A real flank does not put its openings on a grid: vary the sill
            # and the opening height window by window, and block one up with
            # masonry so the elevation has a history to read.
            wzs = [z0 + rng.choice((0.0, 0.0, 0.0, 0.14, -0.08)) for _ in sxs]
            whs = [whin * rng.choice((1.0, 1.0, 0.92, 1.10)) for _ in sxs]
            brick_i = ()
            if len(sxs) > 1 and rng.random() < 0.34:
                brick_i = (rng.randrange(len(sxs)),)
            out += _wall("sd%d_%d" % (f, sx), TT, dd, fh, th,
                         [(x, wwin, wzs[i], whs[i]) for i, x in enumerate(sxs)],
                         wall, y=-th)
            out += _win_batch("sw%d_%d" % (f, sx), TT, sxs, z0, wwin, whin,
                              trim_m, trim, glass, MAT.get("void"), plaster,
                              hood=bool(st["hood"]), shut=wood, rng=rng,
                              p=max(st["shut"], 0.45), zs=wzs, hs=whs,
                              brick=stone_d, brick_xs=brick_i)
            out += _band("sb%d_%d" % (f, sx), TT, dd, fh - 0.28, trim_m, h=0.20,
                         proud=0.11)
            if st["frame"]:
                out += P.timber_frame("tfs%d_%d" % (f, sx), TT, dd, fh, wood_dk,
                                      ops=[(x - 0.70, x + 0.70) for x in sxs],
                                      y=0.015, stud=st["stud"], rng=rng)
        # ---- back wall ----------------------------------------------------
        # was a single featureless box: two neighbours with the same palette
        # then formed one 15 m plane with no visible joint (the gate shot).
        BT = Ts(0, 0, z, rz=math.pi)
        # _wall() puts the wall between y and y+thick, so its OUTER face is at
        # y+thick: the face frames must start on the outer plane, not at the
        # house centre, or every sill and cornice ends up buried in the middle
        # of the building (invisible, and paid for).
        BTF = Ts(0, -(dd * 0.5), z, rz=math.pi)
        bxs = _win_xs(ww, nsb, margin=0.90, min_gap=1.10)
        out += _wall("ub%d" % f, BT, ww, fh, th,
                     [(x, wwin, z0, whin) for x in bxs], wall,
                     y=dd * 0.5 - th)
        out += _win_batch("bw%d" % f, BTF, bxs, z0, wwin, whin, trim_m,
                          trim, glass, MAT.get("void"), plaster,
                          hood=bool(st["hood"]), shut=wood, rng=rng,
                          p=st["shut"])
        out += _band("bb%d" % f, BTF, ww, fh - 0.28, trim_m, h=0.20, proud=0.11)
        z += fh

    # ---- ground-floor flanks and back ------------------------------------
    # Same treatment one storey down: a small barred window on each flank, a
    # back door and a back window, plus the stone band under the jetty.
    for sx in (-1, 1):
        TT = Ts(sx * w * 0.5, 0, pl_h, rz=-sx * math.radians(90))
        gx = _win_xs(d, 2 if d >= 7.0 else 1, margin=1.05, min_gap=1.60)
        out += _wall("gs%d" % sx, TT, d, fh, th,
                     [(x, 1.02, 1.16, 1.16) for x in gx], wall, y=-th)
        out += _win_batch("gsw%d" % sx, TT, gx, 1.16, 1.02, 1.16, trim_m,
                          trim, glass, MAT.get("void"), plaster,
                          shut=wood, rng=rng, p=0.55)
        out += _band("gsb%d" % sx, TT, d, fh - 0.34, trim_m, h=0.18, proud=0.10)
        # sole plate: the dark timber at the foot of the wall.  When wall and
        # plinth are both stone the base of the house has no edge at all.
        out += _band("spl%d" % sx, TT, d, 0.11, wood_dk, h=0.20, proud=0.07)
        # the same stud frame the street front gets: without it the ground-floor
        # flank is one blank panel between the plinth and the first-floor band,
        # and that is the part of the wall a player stands next to.
        if st["frame"]:
            out += P.timber_frame("tgfs%d" % sx, TT, d, fh, wood_dk,
                                  ops=[(x - 0.70, x + 0.70) for x in gx],
                                  y=0.015, stud=st["stud"], rng=rng)
    bdx = w * 0.5 - 1.35
    bx = -w * 0.5 + 1.25
    BTg = Ts(0, 0, pl_h, rz=math.pi)
    BTgf = Ts(0, -(d * 0.5), pl_h, rz=math.pi)
    out += _wall("gb", BTg, w, fh, th,
                 [(bdx, 1.06, 0.0, 2.10), (bx, 0.92, 1.28, 1.06)], wall,
                 y=d * 0.5 - th)
    out += P.door("bdr", BTgf @ Ts(bdx, 0, 0), w=1.06, h=2.10, wood=wood_dk,
                  iron=iron, stone=stone_w if is_stone else stone, steps=1,
                  arch=False, lamp=False, rng=rng)
    out += _win_batch("gbw", BTgf, [bx], 1.28, 0.92, 1.06, trim_m, trim, glass,
                      MAT.get("void"), plaster)
    out += _band("gbb", BTgf, w, fh - 0.34, trim_m, h=0.18, proud=0.10)
    out += _band("splb", BTgf, w, 0.11, wood_dk, h=0.20, proud=0.07)

    # ---- cornice under the eaves ----------------------------------------
    # Nothing framed the top of a flank or back wall: the tiles simply stopped
    # and the wall was a bare rectangle.  A corbelled course two hand-spans
    # under the eave throws a shadow line that reads at 34 m and closes the
    # wall off at the top the way a plinth closes it at the bottom.
    eave_z = pl_h + fh * nfl
    for sx in (-1, 1):
        out += _band("ec%d" % sx, Ts(sx * ww * 0.5, 0, 0, rz=-sx * math.radians(90)),
                     dd, eave_z - 0.34, trim_m, h=0.34, proud=0.26)
    out += _band("ecb", Ts(0, -(dd * 0.5), 0, rz=math.pi), ww, eave_z - 0.34,
                 trim_m, h=0.34, proud=0.26)

    # ---- flank articulation ---------------------------------------------
    # The flank is the biggest blank plane a house owns, and the avenue shots
    # look straight along it: two storeys of plaster with a window every 3.5 m
    # is, at that grazing angle, a wall with no windows at all.  Everything
    # below is 6-40 faces and every piece of it is a hole, a colour change or a
    # vertical, so it survives the angle instead of flattening into a band.
    lead_m = MAT.get("lead") or iron
    moss_m = MAT.get("moss") or stone_d
    patch_m = stone_d if not is_stone else plaster
    jt = float(st["jetty"])
    for sx in (-1, 1):
        sgn = -sx * math.radians(90)
        TL = Ts(sx * w * 0.5, 0, 0, rz=sgn)
        for k in range(1, nfl):
            ov = jt if k == 1 else 0.0
            TU = Ts(sx * (w * 0.5 + ov), 0, 0, rz=sgn)
            top = (k == nfl - 1)
            out += _flank_dress(
                "fd%d_%d" % (sx, k), TU, (TL if k == 1 else None),
                d + 2.0 * ov,
                pl_h + fh * k + 0.42, pl_h + fh * (k + 1) - 0.50,
                rng, patch_m, moss_m, lead_m, wood_dk,
                eave=(eave_z if top else None),
                rafters=(frontage == "gable"))
    # chimney breast on ONE flank, rising past the roof: the vertical division
    # and the roof silhouette that the 52 deg camera actually resolves
    TJ = Ts(stack_sx * w * 0.5, 0, 0, rz=-stack_sx * math.radians(90))
    out += _stack("fk", TJ @ Ts(stack_lx, 0, 0), pl_h + fh - 0.25,
                  eave_z + 2.10 + rng.uniform(0.0, 0.42),
                  stone_w if is_stone else stone,
                  MAT.get("pot") or stone_w,
                  d=0.42 + jt, pots=(3 if w >= 8.6 else 2),
                  soot=MAT.get("soot"))
    # downpipe at the opposite corner: the one dark vertical on a 12 m face
    TP = Ts(-stack_sx * w * 0.5, 0, 0, rz=stack_sx * math.radians(90))
    out += _pipe("fp", TP @ Ts(-stack_lx, 0, 0), pl_h + 0.22, eave_z - 0.30,
                 iron, lead_m, r=0.060, brackets=2 + nfl)

    # ---- downpipe on a back corner ---------------------------------------
    # The street pipe comes from _gutter(); the back one is what stops a flank
    # from being an unbroken vertical.  It runs on the plane of the wall it is
    # fixed to, so a jettied house gets it from the jetty up instead of a pipe
    # hanging in mid-air behind the ground floor.
    pxs = w * 0.5 - 0.32 if rng.random() < 0.5 else -(w * 0.5 - 0.32)
    pz0 = pl_h + fh if st["jetty"] > 0.0 else pl_h
    pz1 = pl_h + fh * nfl - 0.34
    out += _pipe("bp", Ts(pxs, -(dd * 0.5), 0, rz=math.pi), pz0, pz1,
                 iron, MAT.get("lead") or iron, r=0.065,
                 brackets=2 + nfl, hopper=True)
    # quoins wrap all four corners, not just the two street corners: the corner
    # is the only thing that tells two identical neighbours apart, and on a
    # terrace the corners are the joints a player walks past.
    if st["quoin"] or kind in ("stone", "manor", "tower"):
        qh = pl_h + fh * nfl - 0.08
        out += _quoins("qk_f", Ts(0, d * 0.5, 0), w, qh, trim_m, step=0.58,
                       out=0.05)
        out += _quoins("qk_b", Ts(0, -(d * 0.5), 0, rz=math.pi), w, qh, trim_m,
                       step=0.58, out=0.05)
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

    # ---- gable face -----------------------------------------------------
    # The gable triangle is the largest single plane on the house -
    # rh = hw*tan(pitch), i.e. ~5 m tall over a 9 m frontage - and it sits at
    # the TOP of the facade, which is the part a 52 deg camera sees face-on.
    # It had no window and no vertical division on it at all: only the eave
    # cornice underneath and, on frame kinds, three posts and one brace.  That
    # is exactly the pale banded plane in the avenue shot, so it gets a hole, a
    # louvred vent, purlin ends and two raking barge boards.
    if not hip:
        if frontage == "gable":
            # the street gable already carries the loft door and its straps
            out += _gable_dress("gzf", rT @ Ts(0, length * 0.5 + 0.05, top),
                                hw, rh, rng, wood_dk, wood_dk, MAT.get("void"),
                                trim_m, door=False)
        else:
            for sy in (-1, 1):
                FG = rT @ Ts(0, sy * (length * 0.5 + 0.05), top,
                             rz=(0.0 if sy > 0 else math.pi))
                out += _gable_dress("gz%d" % sy, FG, hw, rh, rng, wood_dk,
                                    wood_dk, MAT.get("void"), trim_m,
                                    door=(sy > 0), light=(sy < 0))

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
