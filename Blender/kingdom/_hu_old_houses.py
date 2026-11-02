"""hd_houses.py - high-detail street houses and town buildings for the capital.

Every house is built as a facade with REAL window openings (the wall is built
around a list of openings), so windows sit in a hole instead of floating on a
flat box.  Style follows the capital's palette: stone plinths, plaster or
ashlar walls, visible timber framing, jettied upper floors, tiled/slate roofs
with courses, dormers, chimneys, shop fronts and street clutter.

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
from mathutils import Vector

import hd_common as H
import medkit as K

Ts = K.T_at
TAU = 2.0 * math.pi


# --------------------------------------------------------------------------
# facade helpers
# --------------------------------------------------------------------------
def _wall(name, T, w, h, thick, openings, mat, y=0.0):
    """A wall slab in the local XZ plane facing +Y, with real openings.

    `openings` = [(x, ow, z0, oh), ...] in facade coordinates.
    """
    out = []
    cy = y + thick * 0.5
    ops = sorted(openings, key=lambda o: o[0])
    cur = -w * 0.5
    for (ox, ow, z0, oh) in ops:
        lo = ox - ow * 0.5
        hi = ox + ow * 0.5
        if lo - cur > 0.05:
            out.append(K.box("%s_pier_%.2f" % (name, lo), T @ Ts((cur + lo) * 0.5, cy, h * 0.5),
                             (lo - cur, thick, h), mat, bev=0.015))
        if z0 > 0.05:
            out.append(K.box("%s_sill_%.2f" % (name, lo), T @ Ts(ox, cy, z0 * 0.5),
                             (ow, thick, z0), mat, bev=0.015))
        top = z0 + oh
        if h - top > 0.05:
            out.append(K.box("%s_head_%.2f" % (name, lo), T @ Ts(ox, cy, (top + h) * 0.5),
                             (ow, thick, h - top), mat, bev=0.015))
        cur = hi
    if w * 0.5 - cur > 0.05:
        out.append(K.box("%s_pier_r" % name, T @ Ts((cur + w * 0.5) * 0.5, cy, h * 0.5),
                         (w * 0.5 - cur, thick, h), mat, bev=0.015))
    return out


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
        out += H.window_arched("%s_w%d" % (i, i), T @ Ts(x, y, z0), ww, wh, frame, glass,
                               tracery=2, hood=hood, arch=arched, shutters=shutters,
                               depth=0.36)
    return out


def _rect_window(name, T, w, h, frame, glass, y=0.0, mullions=2, shutters=None):
    """Four-centred stone window with a flat head (for ashlar houses)."""
    out = []
    out.append(K.box(name + "_back", T @ Ts(0, y - 0.20, h * 0.5), (w, 0.12, h), glass))
    j = 0.22
    for s in (-1, 1):
        out.append(K.box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + j * 0.5), y - 0.04, h * 0.5),
                         (j, 0.34, h + j * 1.6), frame, bev=0.02))
    out.append(K.box(name + "_lin", T @ Ts(0, y - 0.04, h + j * 0.8), (w + j * 2.2, 0.36, 0.26),
                     frame, bev=0.02))
    out.append(K.box(name + "_sil", T @ Ts(0, y + 0.02, -0.08), (w + j * 2.6, 0.42, 0.16),
                     frame, bev=0.02))
    for i in range(1, mullions):
        out.append(K.box(name + "_m%d" % i, T @ Ts(-w * 0.5 + w * i / mullions, y - 0.08, h * 0.5),
                         (0.07, 0.20, h), frame))
    for i in range(1, 3):
        out.append(K.box(name + "_t%d" % i, T @ Ts(0, y - 0.10, h * i / 3.0), (w, 0.16, 0.055),
                         frame))
    if shutters is not None:
        for s in (-1, 1):
            out.append(K.box(name + "_sh%d" % s, T @ Ts(s * (w * 0.5 + j + 0.14), y + 0.10, h * 0.5),
                             (0.15, 0.05, h * 0.96), shutters, bev=0.01))
    return out


def _timber_frame(T, w, z0, z1, y, mat, openings=(), stud=1.05, rails=()):
    """Close-studded framing with corner braces, proud of the plaster."""
    out = []
    h = z1 - z0
    # vertical studs
    n = max(2, int(w / stud))
    xs = [-w * 0.5 + w * (i + 0.5) / n for i in range(n)]
    blocked = []
    for (ox, ow, oz0, ozh) in openings:
        blocked.append((ox - ow * 0.5 - 0.25, ox + ow * 0.5 + 0.25))
    for i, x in enumerate(xs):
        if any(a <= x <= b for (a, b) in blocked):
            continue
        out.append(K.box("%s_s%d" % ("tf", i), T @ Ts(x, y, z0 + h * 0.5),
                         (0.16, 0.10, h), mat, bev=0.008))
    # horizontal rails
    for z in list(rails) + [z0 + 0.06, z1 - 0.06]:
        out.append(K.box("tf_r%.2f" % z, T @ Ts(0, y, z), (w, 0.10, 0.17), mat, bev=0.008))
    # corner braces
    for s in (-1, 1):
        out.append(K.box("tf_b%d" % s, T @ Ts(s * (w * 0.5 - 0.72), y, z0 + h * 0.5,
                                              ry=s * math.radians(40)),
                         (0.14, 0.09, h * 0.55), mat, bev=0.008))
    return out


def _jetty(T, w, d, z, over=0.34, beam=None, corbels=6):
    """Bressumer + corbels carrying a jettied upper floor."""
    beam = beam or K.mat_wood("beam")
    out = [K.box("jt_beam", T @ Ts(0, d * 0.5 + over * 0.5, z - 0.12),
                 (w + over * 2, over + 0.3, 0.30), beam, bev=0.02)]
    for i in range(corbels):
        x = -w * 0.5 + (i + 0.5) * w / corbels
        out.append(K.box("jt_c%d" % i, T @ Ts(x, d * 0.5 + 0.02, z - 0.34),
                         (0.18, 0.42, 0.34), beam, bev=0.01))
    for s in (-1, 1):
        out.append(K.box("jt_s%d" % s, T @ Ts(s * (w * 0.5 + over * 0.5), 0, z - 0.12),
                         (over + 0.3, d + over * 2, 0.30), beam, bev=0.02))
    return out


def _shop_front(T, w, z, mat_wood, cloth, cloth2=None, awn_len=1.6, counter=True):
    """Open ground-floor shop: counter boards, awning, hanging sign."""
    out = []
    out.append(K.box("shop_counter", T @ Ts(0, 0.42, z + 0.48), (w * 0.86, 0.85, 0.16),
                     mat_wood, bev=0.02))
    for s in (-1, 1):
        out.append(K.box("shop_leg%d" % s, T @ Ts(s * w * 0.36, 0.42, z + 0.24),
                         (0.12, 0.75, 0.48), mat_wood))
    # awning: two sloped panels meeting at the outer edge
    for i, cm in enumerate((cloth, cloth2 or cloth)):
        y0 = 0.15 + awn_len * (0.55 if i else 0.0)
        out.append(K.box("shop_awn%d" % i,
                         T @ Ts(0, y0 + (awn_len * 0.28 if i else 0), z + 1.62 + (0.22 if i else 0),
                                rx=math.radians(28 if i else -18)),
                         (w, awn_len * 0.62, 0.05), cm))
    # hanging sign
    out.append(K.box("shop_sgn_arm", T @ Ts(w * 0.42, 0.55, z + 2.3), (0.09, 1.15, 0.09),
                     mat_wood))
    out.append(K.box("shop_sgn", T @ Ts(w * 0.42, 1.05, z + 2.02), (0.06, 0.72, 0.52),
                     cloth, bev=0.01))
    return out


def _door(T, w=1.25, h=2.35, wood=None, iron=None, stone=None, steps=2):
    wood = wood or K.mat_wood("door_wood")
    iron = iron or K.mat_metal()
    return H.door_arched("door", T, w, h, wood, iron, stone=stone, steps=steps)


# --------------------------------------------------------------------------
# the house builder
# --------------------------------------------------------------------------
def house(MAT, rng, kind="timber", w=7.0, d=8.6, floors=2, frontage="eaves"):
    stone = MAT["stone"]
    plaster = MAT.get("plaster") or K.mat_plaster()
    timber = MAT.get("wood_dark") or K.mat_wood()
    glass = MAT["glass"]
    tile = MAT.get("slate") if MAT.get("slate") and rng.random() < 0.35 else MAT["tile"]
    if kind == "stone" or kind == "tower":
        wall_mat = stone
    elif kind == "manor":
        wall_mat = stone
    else:
        wall_mat = plaster

    parts = []
    th = 0.42                      # wall thickness
    fh = 2.95 if kind not in ("warehouse", "tower") else 3.15
    plinth_h = 0.42
    total_h = plinth_h + fh * floors

    # ---- plinth
    parts.append(K.box("plinth", Ts(0, 0, plinth_h * 0.5), (w + 0.26, d + 0.26, plinth_h),
                       stone, bev=0.02))

    # ---- per-floor facades
    # ground floor openings
    door_x = -w * 0.22 if kind in ("timber", "stone", "manor") else 0.0
    open_w = 1.45 if kind in ("shop", "craft") else 0.0
    g_ops_front = []
    if open_w > 0.0:
        g_ops_front.append((0.0, open_w + 1.2, plinth_h, fh - 0.25))
        win_g = 0
    else:
        g_ops_front.append((door_x, 1.35, plinth_h, 2.55))
        win_g = 2 if w >= 6.5 else 1
        if win_g:
            span = (w * 0.5 - 1.0)
            right = [0.9 + i * 2.0 for i in range(win_g)]
            # arched windows need a hole that reaches the top of the arch,
            # otherwise the arch is drawn on solid plaster and reads as a
            # blind arch above a flat window (the "blind arch" defect).
            gh = 1.55 * 0.9 + (1.05 * 0.86) * 0.5 + 0.15
            for x in right:
                if x < span:
                    g_ops_front.append((x, 1.05, plinth_h + 1.05, gh))
            for x in (-right[0],):
                if abs(x) < span and abs(x - door_x) > 1.6:
                    g_ops_front.append((x, 1.05, plinth_h + 1.05, gh))

    parts += _wall("gw", Ts(0, 0, 0), w, fh, th, [(x, ow, z0 - plinth_h, oh)
                                                  for (x, ow, z0, oh) in g_ops_front],
                   wall_mat, y=d * 0.5 - th)
    # windows in the holes
    for (x, ow, z0, oh) in g_ops_front:
        if ow < 1.2 and kind not in ("shop", "craft"):
            parts += H.window_arched("gw_w", Ts(x, d * 0.5 - 0.02, z0),
                                     ow * 0.86, oh * 0.9, stone, glass, tracery=2,
                                     hood=True, shutters=timber if rng.random() < 0.4 else None,
                                     depth=0.34)
    # door
    if open_w == 0.0:
        parts += _door(Ts(door_x, d * 0.5 + 0.02, plinth_h), stone=stone,
                       steps=2 if kind != "manor" else 4)
    else:
        parts += _shop_front(Ts(0, d * 0.5, plinth_h), w, 0.0,
                             K.mat_wood("shop_wood"), MAT.get("banner_red", MAT["plaster"]),
                             MAT.get("banner_gold"))

    # sides + back (plain, a couple of windows)
    for s in (-1, 1):
        parts.append(K.box("side%d" % s,
                           Ts(s * (w * 0.5 - th * 0.5), 0, plinth_h + fh * 0.5),
                           (th, d, fh), wall_mat, bev=0.02))
        parts += _rect_window("side_win%d" % s,
                              Ts(s * (w * 0.5 + 0.01), d * 0.10, plinth_h + fh * 0.55,
                                 rz=math.radians(90 * s)),
                              1.0, 1.35, stone, glass, y=0.0, mullions=2)
    parts.append(K.box("backw", Ts(0, -(d * 0.5 - th * 0.5), plinth_h + fh * 0.5),
                       (w, th, fh), wall_mat, bev=0.02))

    # ---- upper floors
    z = plinth_h + fh
    for f in range(1, floors):
        over = 0.30 if f == 1 else 0.0
        ww = w + over * 2.0
        dd = d + over * 2.0
        if over:
            parts += _jetty(Ts(0, 0, 0), w, d, z, over=over,
                            beam=MAT.get("wood_dark") or K.mat_wood("beam"))
        # facade openings
        nwin = max(2, int(w / 2.1))
        win_w = 1.05 if kind != "tower" else 0.85
        z0 = z + 0.85
        wh = fh - 1.6
        ops = []
        span = ww - 1.7
        for i in range(nwin):
            x = -span * 0.5 + span * (i + 0.5) / nwin
            ops.append((x, win_w, 0.85, wh))
        parts += _wall("uw%d" % f, Ts(0, 0, z), ww, fh, th,
                       [(x, ow, zz, oh) for (x, ow, zz, oh) in ops],
                       wall_mat, y=dd * 0.5 - th)
        for (x, ow, zz, oh) in ops:
            if kind == "stone" or kind == "manor" or kind == "tower":
                parts += _rect_window("uw_w%d" % int(x * 100), Ts(x, dd * 0.5 + 0.01, z + zz),
                                      ow, oh, stone, glass, mullions=2,
                                      shutters=timber if rng.random() < 0.35 else None)
            else:
                parts += H.window_arched("uw_wa%d" % int(x * 100),
                                         Ts(x, dd * 0.5 + 0.01, z + zz), ow, oh, stone, glass,
                                         tracery=2, hood=kind in ("timber", "inn"),
                                         shutters=timber if rng.random() < 0.45 else None,
                                         depth=0.34)
        # timber framing between the windows
        if wall_mat is plaster:
            parts += _timber_frame(Ts(0, 0, 0), ww, z, z + fh, dd * 0.5 + 0.03, timber,
                                   openings=[(x, ow, z + zz, oh) for (x, ow, zz, oh) in ops],
                                   stud=1.0)
        else:
            parts.append(K.box("string%d" % f, Ts(0, dd * 0.5 - 0.02, z + 0.06),
                               (ww + 0.18, 0.30, 0.20), stone, bev=0.02))
        # sides / back of this floor
        for s in (-1, 1):
            parts.append(K.box("us%d_%d" % (f, s), Ts(s * (ww * 0.5 - th * 0.5), 0, z + fh * 0.5),
                               (th, dd, fh), wall_mat, bev=0.02))
        parts.append(K.box("ub%d" % f, Ts(0, -(dd * 0.5 - th * 0.5), z + fh * 0.5),
                           (ww, th, fh), wall_mat, bev=0.02))
        z += fh

    # ---- roof
    if kind == "tower":
        # crenellated parapet instead of a roof
        parts.append(K.box("parapet", Ts(0, 0, z + 0.30), (w + 0.5, d + 0.5, 0.60), stone,
                           bev=0.02))
        parts += H.crenel("cr", Ts(0, 0, z + 0.60), w + 0.5, mat=stone, depth=0.5)
        for s in (-1, 1):
            parts += H.crenel("cr2%d" % s, Ts(s * (w * 0.5 + 0.25), 0, z + 0.60, rz=math.radians(90)),
                              d + 0.5, mat=stone, depth=0.5)
        return parts

    pitch = 46 if kind != "warehouse" else 52
    roof_over = 0.42
    barge = MAT["wood_dark"] if "wood_dark" in MAT else timber
    # H.tiled_roof adds 0.45 m of verge on top of the span we hand it, so the
    # real slope half-span is span*0.5 + 0.45 and the gable end plane sits at
    # d*0.5 + roof_over*0.6 + ov_gable.  The plaster gable triangle has to be
    # built against THOSE numbers: built against span*0.5 alone it under-fills
    # the roof by ~0.47 m at the apex and the roof's end cap shows through as a
    # plain dark board.
    if frontage == "gable":
        span = w + roof_over * 2
        parts += H.tiled_roof("roof", Ts(0, 0, 0), span, d + roof_over * 1.2, z, pitch,
                              tile, barge, course_h=0.34, verge=0.45,
                              gable_ends=False, end_mat=wall_mat)
        hw = span * 0.5 + 0.45
        rh = hw * math.tan(math.radians(pitch))
        gable_y = d * 0.5 + roof_over * 0.6 + 0.40 - 0.12
        # gable walls (front/back triangles), flush with the roof end plane
        for sy in (-1, 1):
            parts.append(H.prism("gable%d" % sy, Ts(0, sy * gable_y, z),
                                 [(-hw + 0.06, 0.0), (hw - 0.06, 0.0), (0.0, rh - 0.10)],
                                 0.24, wall_mat, axis="y"))
    else:
        # ridge along X: build the roof rotated 90 deg and swap w/d
        span = d + roof_over * 2
        parts += H.tiled_roof("roof", Ts(0, 0, 0, rz=math.radians(90)), span,
                              w + roof_over * 1.2, z, pitch, tile, barge,
                              course_h=0.34, verge=0.45, gable_ends=False,
                              end_mat=wall_mat)
        hw = span * 0.5 + 0.45
        rh = hw * math.tan(math.radians(pitch))
        gable_x = w * 0.5 + roof_over * 0.6 + 0.40 - 0.12
        for sx in (-1, 1):
            parts.append(H.prism("gable%d" % sx,
                                 Ts(sx * gable_x, 0, z, rz=math.radians(90)),
                                 [(-hw + 0.06, 0.0), (hw - 0.06, 0.0), (0.0, rh - 0.10)],
                                 0.24, wall_mat, axis="y"))

    # chimney + dormers: both stand ON the slope, so their z must come from the
    # surface equation z = eave + rh*(1 - |u|/hw).  A fixed z buries them -- the
    # chimney used to poke out as an 8 px stub and the dormer as a grey chevron.
    ch_x = w * 0.28 * (1 if rng.random() < 0.5 else -1)
    ch_y = -d * 0.16
    ch_u = abs(ch_x) if frontage == "gable" else abs(ch_y)
    ch_surf = z + rh * max(0.0, 1.0 - ch_u / hw)
    ch_base = ch_surf - 1.0
    parts += H.chimney("chim", Ts(ch_x, ch_y, ch_base), (z + rh + 1.35) - ch_base,
                       MAT.get("stone_warm", stone), pots=2)
    do_dorm = rng.random() < 0.55
    if do_dorm and frontage == "eaves":
        dy = d * 0.5 * 0.55
        parts += H.dormer("dorm", Ts(w * 0.18, dy, z + rh * (1.0 - dy / hw) - 0.20),
                          wall=wall_mat, frame=timber, glass=glass, roof_mat=tile)
    # shop awning bar and clutter at the door
    if kind in ("timber", "shop", "inn"):
        parts += H.barrel("barrel", Ts(w * 0.5 - 0.75, d * 0.5 + 0.55, 0),
                          wood=MAT.get("wood"), hoop=MAT.get("iron"))
        parts += H.crate("crate", Ts(-w * 0.5 + 0.55, d * 0.5 + 0.45, 0.31), s=0.62,
                         wood=MAT.get("wood"))
    if kind == "inn":
        parts += H.lantern_post("lantern", Ts(w * 0.5 + 0.1, d * 0.5 + 0.75, 0), 2.6,
                                MAT["iron"], MAT.get("glow_warm"))
        parts.append(K.box("inn_sign", Ts(w * 0.42, d * 0.5 + 0.5, 2.35), (0.06, 0.9, 0.62),
                           MAT.get("banner_gold")))
    return parts


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
    return MAT


def build_set(MAT, rng):
    out = []
    kinds = ["timber", "stone", "shop", "inn", "manor", "tower", "warehouse", "craft"]
    x = -22.0
    for i, kind in enumerate(kinds):
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
          % (len(parts), H.tri_count(parts), lo.x, lo.y, lo.z, hi.x, hi.y, hi.z), flush=True)
    H.diorama_floor(MAT["stone"])
    H.setup_world(fill=2.1)
    H.setup_engine(samples=192, res=(1600, 900))
    cx = (lo.x + hi.x) * 0.5
    R = "E:/My World/Blender/renders/kingdom/hd_houses_%s.png"
    # the street frontage is +Y; every camera has to be on that side or the
    # shots come back as blank rear walls (backw has no openings at all)
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
