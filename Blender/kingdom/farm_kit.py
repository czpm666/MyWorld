"""farm_kit.py -- Asura-era farm village builders on top of medkit / medbuild.

Everything is built in WORLD space through `T`, objects keep identity
transforms, ground stays at z = 0.  Units are metres.

Palette is intentionally one shared set across all three variants:
warm cream plaster, dark oak timber, terracotta tile, grey fieldstone,
green/blue shutters, straw gold.
"""
import math
import random

from mathutils import Vector, Matrix, Euler

import medkit
from medkit import (TAU, T_at, box, cyl, cone, sphere, gable_roof, roof_details,
                    window, door, lantern, flowerbox, mesh_obj, assign, bevel,
                    mat_plaster, mat_wood, mat_tile, mat_stone, mat_cobble,
                    mat_flag, mat_metal, mat_gold, mat_cloth, mat_glass,
                    mat_foliage, mat_water, mat_earth)
import medbuild
from medbuild import timber_frame, face_beam, tree, bush, barrel, crate, sack, cart


# --------------------------------------------------------------------------
# shared material set (rebuilt per variant; medkit caches datablocks)
# --------------------------------------------------------------------------
PLASTERS = [
    ("#e9dec6", "#ccbfa2"),
    ("#dfd3b6", "#c0b193"),
    ("#e8d2af", "#c9ad85"),
    ("#d9dbcd", "#b8bcaa"),
    ("#e3c9a4", "#c4a67f"),
    ("#ddcdb0", "#bfae8e"),
]
TILES = [
    ("#9c3f2b", "#6f2a1c", "#bd5539"),
    ("#8a3a26", "#61281a", "#a84c33"),
    ("#7d4630", "#57301f", "#9a5a3e"),
    ("#6f5a48", "#4e3f31", "#8a7159"),
]
SHUTTERS = [
    ("#3a5a44", "#4e7457"),      # green
    ("#3f5570", "#52708c"),      # blue
    ("#7b3b2c", "#99513d"),      # red oxide
    ("#5d5344", "#7a6c58"),      # grey brown
]

M = {}


def lamp_mat():
    """Warm lamp pane: matte amber glass with a little emission, so the lantern
    reads as lit rather than as a dark box."""
    m = mat_glass("lamp_warm", "#f0c877")
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Roughness"].default_value = 0.35
            try:
                n.inputs["Emission Color"].default_value = (1.0, 0.72, 0.32, 1.0)
                n.inputs["Emission Strength"].default_value = 1.6
            except KeyError:
                pass
    return m


def init_materials():
    """Build the shared palette once per scene (mutates M, so `from ... import M`
    in other modules stays live across variants)."""
    M.clear()
    M.update({
        "plaster": [mat_plaster("pl_%d" % i, base=b, dirt=d, scale=4.0 + 0.5 * i)
                    for i, (b, d) in enumerate(PLASTERS)],
        "tile": [mat_tile("tile_%d" % i, base=b, dark=d, light=l)
                 for i, (b, d, l) in enumerate(TILES)],
        "tile_barn": mat_tile("tile_barn", base="#6b4128", dark="#4a2b19",
                              light="#86543a"),
        "wood_frame": mat_wood("wood_frame", base="#573c26", light="#7b5535",
                               scale=13.0),
        "wood_barn": mat_wood("wood_barn", base="#3d2e22", light="#57412f",
                              scale=10.0),
        "wood_door": mat_wood("wood_door", base="#4a3220", light="#6b4a2c",
                              scale=15.0),
        "wood_board": mat_wood("wood_board", base="#6b4f31", light="#8a6a44",
                               scale=18.0),
        "wood_fence": mat_wood("wood_fence", base="#6a4c30", light="#8a663f",
                               scale=15.0),
        "shutter": [mat_wood("wood_shut_%d" % i, base=b, light=l, scale=12.0)
                    for i, (b, l) in enumerate(SHUTTERS)],
        "stone": mat_stone("stone_farm", base="#8a8272", dark="#55503f",
                           light="#a9a191", scale=2.6),
        "stone_step": mat_stone("stone_step", base="#7e7869", dark="#504b3f",
                                light="#9c9587", scale=2.4),
        "cobble": mat_cobble("cobble_lane", base="#665c48", mortar="#332f26",
                             light="#968c78"),
        "earth": mat_earth("earth_soil", base="#6b4f33", dark="#41301f",
                           scale=2.6, detail=2.5, bump=0.06, patch=0.55),
        "road": mat_earth("earth_road", base="#7d6146", dark="#463528",
                          scale=5.0, detail=6.0, bump=0.14, patch=0.45),
        "straw": mat_earth("straw", base="#c2a057", dark="#96783c",
                           scale=3.0, detail=3.0, bump=0.10, patch=0.40),
        "iron": mat_metal(),
        "gold": mat_gold(),
        "glass": mat_glass(),
        "water": mat_water(),
        "parchment": mat_cloth("parchment", "#e6dcbf"),
        "banner": mat_cloth("banner_crimson", "#7e1d29"),
        "banner_trim": mat_cloth("banner_trim", "#d9b45a"),
        "leaf": mat_foliage("leaf_farm", base="#3f6b32", light="#5f9440",
                            scale=7.0),
        "leaf2": mat_foliage("leaf_farm_hi", base="#4d7d38", light="#75a94c",
                             scale=8.0),
        "crop_wheat": mat_foliage("crop_wheat", base="#8f7a3a", light="#c0a862",
                                  scale=9.0),
        "crop_wheat2": mat_foliage("crop_wheat2", base="#7a6730", light="#a8924e",
                                   scale=11.0),
        "crop_green": mat_foliage("crop_green", base="#4e6b28", light="#6f9440",
                                  scale=8.0),
        "pasture": mat_foliage("pasture", base="#47602a", light="#65803a",
                               scale=1.15),
        "crop_cabbage": mat_foliage("crop_cabbage", base="#4c7534",
                                    light="#86a862", scale=10.0),
        "cloth_rag": mat_cloth("rag", "#8a7a5c"),
        "sackcloth": mat_cloth("sackcloth", "#c2b087"),
        "bark": mat_wood("wood_bark", base="#4a3a2a", light="#6b563f",
                         scale=16.0),
        "canvas": mat_cloth("canvas", "#a08a5e"),
        "lamp": lamp_mat(),
    })
    return M


# --------------------------------------------------------------------------
# accumulators
# --------------------------------------------------------------------------
class Assemblies(object):
    """Ordered named groups; each group is joined into one mesh on export."""

    def __init__(self):
        self.groups = []
        self._idx = {}

    def add(self, key, parts):
        if not isinstance(parts, (list, tuple)):
            parts = [parts]
        parts = [p for p in parts if p is not None]
        if not parts:
            return
        if key not in self._idx:
            self._idx[key] = len(self.groups)
            self.groups.append((key, []))
        self.groups[self._idx[key]][1].extend(parts)

    def keys(self):
        return [k for k, _ in self.groups]

    def count(self):
        return len(self.groups)


# --------------------------------------------------------------------------
# small merged-mesh helpers (one mesh, many little shapes -> cheap)
# --------------------------------------------------------------------------
def _cone_verts(T, cx, cy, cz, r, h, seg=5, spin=0.0):
    verts = [T @ Vector((cx, cy, cz + h))]
    for i in range(seg):
        a = spin + TAU * i / seg
        verts.append(T @ Vector((cx + math.cos(a) * r, cy + math.sin(a) * r, cz)))
    faces = [(0, 1 + i, 1 + (i + 1) % seg) for i in range(seg)]
    return verts, faces


def tufts(name, T, pts, r=0.10, h=0.30, mat=None, seg=5, rng=None):
    """One mesh holding a cone per (x, y, z) point -- crop / straw clumps."""
    rng = rng or random.Random(7)
    allv, allf = [], []
    for (x, y, z) in pts:
        v, f = _cone_verts(T, x, y, z, r * rng.uniform(0.75, 1.25),
                           h * rng.uniform(0.7, 1.3), seg, rng.uniform(0, TAU))
        off = len(allv)
        allv.extend(v)
        allf.extend([tuple(i + off for i in face) for face in f])
    ob = mesh_obj(name, allv, allf)
    if mat:
        assign(ob, mat)
    return ob


def posts_row(name, T, xs, w, h, mat, y=0.0, bev=0.008):
    verts, faces = [], []
    for x in xs:
        v, f = _box_verts(T, x, y, h * 0.5, w, w, h)
        off = len(verts)
        verts.extend(v)
        faces.extend([tuple(i + off for i in face) for face in f])
    ob = mesh_obj(name, verts, faces)
    assign(ob, mat)
    return ob


def _box_verts(T, cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    loc = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
           (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    verts = [T @ Vector((cx + v[0], cy + v[1], cz + v[2])) for v in loc]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return verts, faces


# --------------------------------------------------------------------------
# farmhouse (medbuild.house core + farm additions)
# --------------------------------------------------------------------------
def farmhouse(name, T, W=6.2, D=5.0, nF=1, FH=2.9, pitch=42.0, pi=0, ti=0,
              si=0, shutters=True, stone_ground=False, lean_to=0, ladder=False,
              ridge_along_front=True, rng=None, win_front=2, win_side=1,
              corner="timber", brace="alternate", dormers=0, firewood=True,
              loft_door=False):
    """Timber-framed farm cottage: stone plinth, tile roof, chimney, shutters."""
    rng = rng or random.Random(hash(name) & 0xFFFF)
    out = medbuild.house(
        name, T, W=W, D=D, FH=FH, nF=nF, jetty=0.16, pitch=pitch,
        walls=M["plaster"][pi], timber=M["wood_frame"], roof=M["tile"][ti],
        rng=rng, win_front=win_front, win_side=win_side, has_door=True,
        plinth=0.40, chimney=True, ridge_along_front=ridge_along_front,
        shutters=shutters, stone_ground=stone_ground,
        corner_style=("quoin" if corner == "quoin" else "timber"),
        brace_pattern=brace, dormers=dormers)

    # the shared house generator hard-codes a green shutter; farmhouses vary
    if shutters and si:
        sm = M["shutter"][si]
        for ob in out:
            if ob.name.startswith(name) and "_sh" in ob.name:
                ob.data.materials.clear()
                ob.data.materials.append(sm)

    eave_z = 0.40 + nF * FH
    wf = W + 2 * 0.16 * (nF - 1)
    df = D + 2 * 0.16 * (nF - 1)

    # ---- loft door in the gable + hoist beam
    if loft_door and not ridge_along_front:
        rh = (wf * 0.5 + 0.45) * math.tan(math.radians(pitch))
        lz = eave_z + rh * 0.34
        out.append(box(name + "_loft", T @ T_at(0, df * 0.5 + 0.055, lz),
                       (1.05, 0.12, 1.35), M["wood_barn"], bev=0.012))
        out.append(box(name + "_loftf", T @ T_at(0, df * 0.5 + 0.10, lz),
                       (1.20, 0.05, 1.50), M["wood_frame"], bev=0.01))
        for i in range(4):
            out.append(box(name + "_loftp%d" % i,
                           T @ T_at(-0.36 + 0.24 * i, df * 0.5 + 0.13, lz),
                           (0.05, 0.03, 1.28), M["iron"]))
        out.append(box(name + "_hoist", T @ T_at(0, df * 0.5 + 0.55,
                                                 eave_z + rh * 0.72),
                       (0.16, 1.25, 0.18), M["wood_frame"], bev=0.012))
        out.append(box(name + "_hoistb", T @ T_at(0, df * 0.5 + 1.06,
                                                  eave_z + rh * 0.52),
                       (0.05, 0.05, 0.42), M["iron"]))

    # ---- lean-to cart / wood shed against one gable side
    if lean_to:
        s = 1 if lean_to > 0 else -1
        LW = min(D * 0.62, 3.6)          # width along Y
        LD = 2.35                        # projection along X
        hb = 2.45                        # outer post height
        xt = s * (W * 0.5 + LD * 0.5)
        out.append(box(name + "_lt_b%d" % s,
                       T @ T_at(s * (W * 0.5 + LD), 0, hb * 0.5),
                       (0.14, LW, hb), M["wood_barn"], bev=0.01))
        for sy in (-1, 1):
            out.append(box(name + "_lt_s%d" % sy,
                           T @ T_at(xt, sy * LW * 0.5, hb * 0.5),
                           (LD, 0.12, hb), M["wood_barn"], bev=0.01))
            out.append(box(name + "_lt_p%d" % sy,
                           T @ T_at(s * (W * 0.5 + LD - 0.10),
                                    sy * (LW * 0.5 - 0.06), 1.18),
                           (0.13, 0.13, 2.36), M["wood_frame"], bev=0.01))
        # mono-pitch roof: high at the house wall, low at the outer edge
        drop = 0.95
        ang = math.atan2(drop, LD + 0.25)
        rl = math.hypot(LD + 0.30, drop)
        out.append(box(name + "_lt_r",
                       T @ T_at(s * (W * 0.5 + (LD + 0.30) * 0.5),
                                0, 3.05 - drop * 0.5, ry=s * ang),
                       (rl, LW + 0.55, 0.13), M["tile"][ti], bev=0.01))
        # a little firewood under it
        out += woodpile(name + "_lt_w", T @ T_at(xt, 0, 0), min(LW - 0.5, 2.2),
                        rows=3, along="y")

    # ---- firewood stacked along the back wall
    if firewood:
        wx = -wf * 0.5 + 1.0
        out += woodpile(name + "_wp", T @ T_at(wx, -D * 0.5 - 0.42, 0),
                        min(W * 0.34, 2.1))

    # ---- ladder up to the loft door
    if ladder:
        ang = math.radians(14)
        lz0, lz1 = 0.0, eave_z + 0.4
        ly = df * 0.5 + 0.95
        for sx in (-1, 1):
            out.append(box(name + "_ldr%d" % sx,
                           T @ T_at(sx * 0.26, ly - 0.5 + math.tan(ang) * lz1 * 0.5,
                                    lz1 * 0.5),
                           (0.07, 0.11, lz1 * 1.02), M["wood_frame"],
                           bev=0.006))
        for i in range(7):
            z = 0.45 + i * (lz1 - 0.6) / 6.0
            out.append(box(name + "_ldp%d" % i,
                           T @ T_at(0, ly - 0.5 + math.tan(ang) * z, z),
                           (0.56, 0.06, 0.06), M["wood_frame"]))
    return out


# --------------------------------------------------------------------------
# barn
# --------------------------------------------------------------------------
def barn(name, T, W=11.0, D=7.6, wall_h=4.6, pitch=40.0, ti=1,
         doors=True, loft=True, lean_to=0, rng=None):
    """Board-and-batten barn: stone footing, dark timber, wide doors, hay loft."""
    rng = rng or random.Random(hash(name) & 0xFFFF)
    out = []
    td = 0.38
    out.append(box(name + "_foot", T @ T_at(0, 0, td * 0.5),
                   (W + 0.30, D + 0.30, td), M["stone"], bev=0.02))
    out.append(box(name + "_wall", T @ T_at(0, 0, td + wall_h * 0.5),
                   (W, D, wall_h), M["wood_barn"]))

    # corner posts + top plate + mid girt
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_cp%d%d" % (sx, sy),
                           T @ T_at(sx * W * 0.5, sy * D * 0.5,
                                    td + wall_h * 0.5),
                           (0.28, 0.28, wall_h + 0.06), M["wood_frame"],
                           bev=0.012))
    out.append(box(name + "_plate", T @ T_at(0, 0, td + wall_h - 0.10),
                   (W + 0.22, D + 0.22, 0.20), M["wood_frame"], bev=0.012))
    out.append(box(name + "_sill", T @ T_at(0, 0, td + 0.12),
                   (W + 0.16, D + 0.16, 0.18), M["wood_frame"], bev=0.012))

    # board-and-batten: vertical battens on all four walls
    nb = max(6, int(W / 0.62))
    xs = [-W * 0.5 + (W / nb) * (i + 0.5) for i in range(nb)]
    nd = max(4, int(D / 0.62))
    for i, x in enumerate(xs):
        for sy in (-1, 1):
            out.append(box(name + "_bt%d%d" % (i, sy),
                           T @ T_at(x, sy * (D * 0.5 + 0.045),
                                    td + (wall_h - 0.1) * 0.5),
                           (0.075, 0.035, wall_h - 0.12), M["wood_frame"],
                           bev=0.006))
    for i in range(nd):
        y = -D * 0.5 + D * (i + 0.5) / nd
        for sx in (-1, 1):
            out.append(box(name + "_bs%d%d" % (i, sx),
                           T @ T_at(sx * (W * 0.5 + 0.045), y,
                                    td + (wall_h - 0.1) * 0.5),
                           (0.035, 0.075, wall_h - 0.12), M["wood_frame"],
                           bev=0.006))

    # big paired doors on the +Y gable end
    if doors:
        dw, dh = 1.55, 3.30
        for sx in (-1, 1):
            ox = sx * dw * 0.5
            out.append(box(name + "_dl%d" % sx,
                           T @ T_at(ox, D * 0.5 + 0.07, td + dh * 0.5),
                           (dw - 0.04, 0.10, dh), M["wood_board"], bev=0.012))
            # plank lines
            for k in range(3):
                out.append(box(name + "_dp%d%d" % (sx, k),
                               T @ T_at(ox - dw * 0.32 + k * dw * 0.32,
                                        D * 0.5 + 0.125, td + dh * 0.5),
                               (0.035, 0.03, dh * 0.94), M["wood_barn"]))
            # X bracing
            for sgn in (-1, 1):
                bl = math.hypot(dw * 0.72, dh * 0.66)
                out.append(box(name + "_dx%d%d" % (sx, sgn),
                               T @ T_at(ox, D * 0.5 + 0.15, td + dh * 0.5,
                                        ry=sgn * math.atan2(dw * 0.72, dh * 0.66)),
                               (0.10, 0.04, bl), M["wood_frame"], bev=0.006))
            for z in (td + 0.35, td + dh - 0.30):
                out.append(box(name + "_dh%d%.1f" % (sx, z),
                               T @ T_at(ox, D * 0.5 + 0.15, z),
                               (dw * 0.80, 0.05, 0.12), M["iron"], bev=0.006))
        # door head beam + threshold
        out.append(box(name + "_dhead", T @ T_at(0, D * 0.5 + 0.07, td + dh + 0.12),
                       (dw * 2 + 0.5, 0.16, 0.24), M["wood_frame"], bev=0.012))
        out.append(box(name + "_dsill", T @ T_at(0, D * 0.5 + 0.35, 0.06),
                       (dw * 2 + 0.7, 0.80, 0.12), M["stone_step"], bev=0.02))

    eave_z = td + wall_h
    rh = (W * 0.5 + 0.55) * math.tan(math.radians(pitch))

    # hay loft opening high in the +Y gable, with a hoist beam above
    if loft:
        lz = eave_z + rh * 0.30
        out.append(box(name + "_loft", T @ T_at(0, D * 0.5 + 0.09, lz),
                       (1.60, 0.10, 1.70), M["wood_barn"], bev=0.012))
        out.append(box(name + "_loftf", T @ T_at(0, D * 0.5 + 0.15, lz),
                       (1.80, 0.06, 1.90), M["wood_frame"], bev=0.01))
        for i in range(5):
            out.append(box(name + "_lp%d" % i,
                           T @ T_at(-0.60 + 0.30 * i, D * 0.5 + 0.19, lz),
                           (0.05, 0.03, 1.62), M["wood_frame"]))
        out.append(box(name + "_hoist", T @ T_at(0, D * 0.5 + 0.70,
                                                 eave_z + rh * 0.74),
                       (0.20, 1.55, 0.22), M["wood_frame"], bev=0.014))
        out.append(box(name + "_hoistk", T @ T_at(0, D * 0.5 + 1.34,
                                                  eave_z + rh * 0.56),
                       (0.06, 0.06, 0.62), M["iron"]))
        out.append(cyl(name + "_pulley", T @ T_at(0, D * 0.5 + 0.70,
                                                  eave_z + rh * 0.60,
                                                  ry=math.pi * 0.5),
                       0.16, 0.10, M["wood_frame"], seg=10))

    # roof: ridge along local Y so the gable (and the big doors) face +Y
    out.append(gable_roof(name + "_roof", T, W, D, eave_z, pitch,
                          M["tile_barn"] if ti is None else M["tile"][ti],
                          M["wood_barn"]))
    out += roof_details(name + "_rd", T, W, D, eave_z, pitch, M["iron"])

    # ridge vent
    out.append(box(name + "_vent", T @ T_at(0, -D * 0.22, eave_z + rh + 0.16),
                   (0.55, 1.10, 0.34), M["wood_barn"], bev=0.02))
    out.append(box(name + "_ventc", T @ T_at(0, -D * 0.22, eave_z + rh + 0.40),
                   (0.75, 1.30, 0.09), M["wood_frame"], bev=0.015))

    # animal lean-to on one long side
    if lean_to:
        s = 1 if lean_to > 0 else -1
        LW = D * 0.72
        LD = 2.6
        hb = 2.7
        xt = s * (W * 0.5 + LD * 0.5)
        out.append(box(name + "_lt_b", T @ T_at(s * (W * 0.5 + LD), 0, hb * 0.5),
                       (0.15, LW, hb), M["wood_barn"], bev=0.01))
        for sy in (-1, 1):
            out.append(box(name + "_lt_s%d" % sy,
                           T @ T_at(xt, sy * LW * 0.5, hb * 0.5),
                           (LD, 0.13, hb), M["wood_barn"], bev=0.01))
            out.append(box(name + "_lt_p%d" % sy,
                           T @ T_at(s * (W * 0.5 + LD - 0.12),
                                    sy * (LW * 0.5 - 0.08), 1.30),
                           (0.14, 0.14, 2.60), M["wood_frame"], bev=0.01))
        drop = 1.05
        ang = math.atan2(drop, LD + 0.3)
        rl = math.hypot(LD + 0.35, drop)
        out.append(box(name + "_lt_r",
                       T @ T_at(s * (W * 0.5 + (LD + 0.35) * 0.5),
                                0, eave_z - 0.35 - drop * 0.5, ry=s * ang),
                       (rl, LW + 0.6, 0.14), M["tile"][ti], bev=0.01))

    # a hay pile spilling out of the loft end
    if rng.random() < 0.5:
        out.append(box(name + "_hayb", T @ T_at(W * 0.30, D * 0.5 - 1.1, 0.55),
                       (2.2, 1.8, 1.10), M["straw"], bev=0.10))
    return out


# --------------------------------------------------------------------------
# windmill
# --------------------------------------------------------------------------
def windmill(name, T, tower_h=6.8, r_base=2.95, r_top=2.05, sail_len=5.4,
             sail_ang=0.36, pitch=48.0):
    """Stone tower mill: battered tower, tiled cap, four lattice sails."""
    out = []
    rng = random.Random(hash(name) & 0xFFF)
    out.append(box(name + "_base", T @ T_at(0, 0, 0.22),
                   (r_base * 2.35, r_base * 2.35, 0.44), M["stone"], bev=0.02))
    out.append(cyl(name + "_tower", T @ T_at(0, 0, 0.44 + tower_h * 0.5),
                   r_base, tower_h, M["stone"], seg=18, cap=False, r2=r_top))
    # stone course rings
    for i, t in enumerate((0.30, 0.62)):
        rr = r_base + (r_top - r_base) * t
        out.append(cyl(name + "_ring%d" % i,
                       T @ T_at(0, 0, 0.44 + tower_h * t),
                       rr * 1.035, 0.16, M["stone"], seg=18, cap=False))
    # door + windows on the +Y face
    dz = 0.44 + 1.05
    out.append(box(name + "_door", T @ T_at(0, r_base * 0.97, dz),
                   (1.05, 0.16, 2.05), M["wood_door"], bev=0.012))
    out.append(box(name + "_doorf", T @ T_at(0, r_base * 1.02, dz),
                   (1.30, 0.07, 2.22), M["wood_frame"], bev=0.01))
    for i, zz in enumerate((0.44 + tower_h * 0.42, 0.44 + tower_h * 0.66)):
        rr = r_base + (r_top - r_base) * ((zz - 0.44) / tower_h)
        out += window(name + "_w%d" % i,
                      T @ T_at(0, rr * 0.94, zz, ry=-0.10), 0.50, 0.66,
                      M["wood_frame"], M["glass"], None, mullions=1)
    # cap: drum + tiled cone + finial
    cap_z = 0.44 + tower_h
    out.append(cyl(name + "_drum", T @ T_at(0, 0, cap_z + 0.30),
                   r_top * 1.09, 0.62, M["wood_barn"], seg=18))
    out.append(cone(name + "_cap", T @ T_at(0, 0, cap_z + 1.62),
                    r_top * 1.20, 2.05, M["tile_barn"], seg=18))
    out.append(sphere(name + "_fin", T @ T_at(0, 0, cap_z + 2.70), 0.14,
                      M["iron"], seg=10, ring=6))
    # tail pole down the back
    out.append(box(name + "_tail", T @ T_at(0, -r_top - 0.55, cap_z - 1.55,
                                            ry=math.radians(26)),
                   (0.13, 2.30, 0.13), M["wood_frame"], bev=0.01))

    # ---- sails: hub on the +Y face, arms in the local XZ plane
    hub_z = cap_z - 0.05
    hub_y = r_top * 0.94 + 0.30
    HUB = T @ T_at(0, hub_y, hub_z)
    out.append(cyl(name + "_hub", HUB @ T_at(0, 0.10, 0, rx=math.pi * 0.5),
                  0.34, 0.55, M["wood_frame"], seg=12))
    out.append(cyl(name + "_axle", HUB @ T_at(0, -0.35, 0, rx=math.pi * 0.5),
                  0.16, 0.90, M["iron"], seg=10))
    A = sail_ang
    for arm in range(4):
        a = A + arm * math.pi * 0.5
        AM = HUB @ T_at(0, 0.16, 0, rz=0.0) @ T_at(0, 0, 0, ry=a)
        # main spar
        out.append(box(name + "_sp%d" % arm,
                       AM @ T_at(sail_len * 0.52, 0, 0),
                       (sail_len * 1.04, 0.16, 0.20), M["wood_frame"],
                       bev=0.01))
        # lattice frame: two rails + cross slats
        half = sail_len * 0.44
        for sgn in (-1, 1):
            out.append(box(name + "_sr%d%d" % (arm, sgn),
                           AM @ T_at(sail_len * 0.55, 0, sgn * half * 0.62),
                           (sail_len * 0.86, 0.09, 0.12),
                           M["wood_frame"], bev=0.006))
        ns = 7
        for k in range(ns):
            u = sail_len * 0.16 + (sail_len * 0.80) * k / (ns - 1.0)
            out.append(box(name + "_ss%d%d" % (arm, k),
                           AM @ T_at(u, 0, 0),
                           (0.09, 0.07, half * 1.30), M["wood_frame"],
                           bev=0.005))
        # sail cloth between the slats (a thin panel, reads from a distance)
        out.append(box(name + "_sc%d" % arm,
                       AM @ T_at(sail_len * 0.55, 0.02, 0),
                       (sail_len * 0.84, 0.03, half * 1.16),
                       M["canvas"], bev=0.004))
        # spar tip counterweight
        out.append(box(name + "_st%d" % arm,
                       AM @ T_at(sail_len * 0.98, 0, 0),
                       (0.22, 0.24, 0.34), M["wood_board"], bev=0.01))
    return out


# --------------------------------------------------------------------------
# small structures
# --------------------------------------------------------------------------
def well(name, T, r=0.95):
    """Stone-rimmed village well with timber posts and a tiled cap."""
    out = []
    out.append(cyl(name + "_ring", T @ T_at(0, 0, 0.44), r, 0.88,
                   M["stone"], seg=16, cap=False))
    out.append(cyl(name + "_rim", T @ T_at(0, 0, 0.90), r * 1.09, 0.13,
                   M["stone"], seg=16))
    out.append(cyl(name + "_w", T @ T_at(0, 0, 0.48), r * 0.82, 0.05,
                   M["water"], seg=16))
    for sx in (-1, 1):
        out.append(box(name + "_p%d" % sx, T @ T_at(sx * r * 0.82, 0, 1.42),
                       (0.14, 0.14, 2.10), M["wood_frame"], bev=0.012))
    out.append(cyl(name + "_bar", T @ T_at(0, 0, 2.18, ry=math.pi * 0.5),
                   0.08, r * 1.75, M["wood_frame"], seg=10))
    out.append(cyl(name + "_crank", T @ T_at(r * 0.94, 0, 2.18,
                                             ry=math.pi * 0.5),
                   0.05, 0.34, M["iron"], seg=8))
    rh = 0.94
    for sx in (-1, 1):
        out.append(box(name + "_rl%d" % sx,
                       T @ T_at(sx * r * 0.58, 0, 2.62, ry=sx * 0.62),
                       (1.30, r * 2.05, 0.10), M["tile"][1], bev=0.01))
    out.append(box(name + "_rk", T @ T_at(0, 0, 3.22), (0.16, r * 2.1, 0.10),
                   M["iron"], bev=0.01))
    out.append(cyl(name + "_rope", T @ T_at(0, 0, 1.62), 0.014, 0.75,
                   M["iron"], seg=6))
    out.append(cyl(name + "_bucket", T @ T_at(0, 0, 1.12), 0.20, 0.30,
                   M["wood_fence"], seg=12))
    out.append(box(name + "_trough", T @ T_at(r + 1.30, 0.30, 0.22),
                   (1.55, 0.62, 0.44), M["stone_step"], bev=0.03))
    out.append(box(name + "_troughw", T @ T_at(r + 1.30, 0.30, 0.40),
                   (1.35, 0.44, 0.06), M["water"]))
    return out


def notice_board(name, T, w=2.5):
    out = []
    for sx in (-1, 1):
        out.append(box(name + "_p%d" % sx, T @ T_at(sx * w * 0.5, 0, 1.10),
                       (0.13, 0.13, 2.20), M["wood_frame"], bev=0.01))
    out.append(box(name + "_b", T @ T_at(0, 0.06, 1.42), (w, 0.10, 1.15),
                   M["wood_board"], bev=0.012))
    for sz in (-1, 1):
        out.append(box(name + "_f%d" % sz, T @ T_at(0, 0.10, 1.42 + sz * 0.56),
                       (w + 0.14, 0.06, 0.11), M["wood_frame"], bev=0.008))
    # pinned notices
    rng = random.Random(hash(name) & 0xFF)
    for i in range(4):
        x = -w * 0.34 + i * (w * 0.68 / 3.0)
        out.append(box(name + "_n%d" % i,
                       T @ T_at(x, 0.13, 1.35 + rng.uniform(-0.10, 0.16),
                                rz=rng.uniform(-0.06, 0.06)),
                       (0.34, 0.012, 0.44), M["parchment"]))
    # little tiled hood
    for sx in (-1, 1):
        out.append(box(name + "_r%d" % sx, T @ T_at(sx * w * 0.26, 0, 2.34,
                                                    ry=sx * 0.45),
                       (w * 0.62, 0.90, 0.08), M["tile"][1], bev=0.008))
    out.append(box(name + "_rk", T @ T_at(0, 0, 2.52), (0.12, 0.94, 0.08),
                   M["iron"]))
    return out


def shrine(name, T, w=2.2):
    """Small roadside shrine to the Sword: stone steps, posts, statue."""
    out = []
    for i, (sw, sh) in enumerate(((w + 0.9, 0.16), (w + 0.5, 0.16))):
        out.append(box(name + "_st%d" % i, T @ T_at(0, 0, 0.08 + i * 0.16),
                       (sw, sw * 0.78, sh), M["stone_step"], bev=0.02))
    z0 = 0.32
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_p%d%d" % (sx, sy),
                           T @ T_at(sx * w * 0.42, sy * w * 0.34,
                                    z0 + 1.00),
                           (0.13, 0.13, 2.00), M["wood_frame"], bev=0.01))
    out.append(box(name + "_alt", T @ T_at(0, 0, z0 + 0.55), (w * 0.62, w * 0.5,
                                                             0.55),
                   M["stone"], bev=0.025))
    # statue: cloak, torso, head, sword held point-down
    out.append(cyl(name + "_cloak", T @ T_at(0, 0, z0 + 1.18), 0.33, 0.90,
                   M["stone"], seg=12, r2=0.19))
    out.append(sphere(name + "_head", T @ T_at(0, 0, z0 + 1.70), 0.15,
                      M["stone"], seg=12, ring=8))
    out.append(box(name + "_blade", T @ T_at(0, 0.10, z0 + 1.02, ry=0.10),
                   (0.09, 0.03, 1.05), M["iron"], bev=0.006))
    out.append(box(name + "_guard", T @ T_at(0, 0.10, z0 + 1.52),
                   (0.42, 0.05, 0.07), M["gold"]))
    out.append(box(name + "_grip", T @ T_at(0, 0.10, z0 + 1.62),
                   (0.06, 0.05, 0.20), M["wood_frame"]))
    # roof
    eave = z0 + 2.10
    rh = (w * 0.5 + 0.45) * math.tan(math.radians(34))
    for sx in (-1, 1):
        out.append(box(name + "_r%d" % sx,
                       T @ T_at(sx * w * 0.30, 0, eave + rh * 0.5,
                                ry=sx * math.radians(34)),
                       (math.hypot(w * 0.5 + 0.45, rh), w * 1.35, 0.09),
                       M["tile"][1], bev=0.008))
    out.append(box(name + "_rk", T @ T_at(0, 0, eave + rh + 0.04),
                   (0.13, w * 1.4, 0.09), M["iron"]))
    # offerings
    rng = random.Random(hash(name) & 0x77)
    for i in range(5):
        out.append(sphere(name + "_fl%d" % i,
                          T @ T_at(rng.uniform(-0.55, 0.55), 0.45,
                                   z0 + 0.10 + rng.uniform(0, 0.05)),
                          0.055, M["banner"], seg=6, ring=5))
    return out


def banner(name, T, h=5.0, cloth=None, drop=2.9, w=1.35):
    """Tall banner pole with a swallow-tailed cloth and a gold emblem."""
    cloth = cloth or M["banner"]
    out = []
    out.append(cyl(name + "_pole", T @ T_at(0, 0, h * 0.5), 0.085, h,
                   M["wood_frame"], seg=10))
    out.append(box(name + "_base", T @ T_at(0, 0, 0.10), (0.42, 0.42, 0.20),
                   M["stone_step"], bev=0.02))
    out.append(sphere(name + "_fin", T @ T_at(0, 0, h + 0.06), 0.10,
                      M["gold"], seg=10, ring=6))
    out.append(box(name + "_bar", T @ T_at(w * 0.55, 0, h - 0.16),
                   (w * 1.15, 0.06, 0.06), M["wood_frame"]))
    # cloth: two quads forming a swallowtail
    zt, zb = h - 0.22, h - 0.22 - drop
    x0, x1, xm = 0.10, 0.10 + w, 0.10 + w * 0.5
    verts = [T @ Vector((x0, 0, zt)), T @ Vector((xm, 0, zt)),
             T @ Vector((x1, 0, zt)), T @ Vector((x1, 0, zb)),
             T @ Vector((xm, 0, zb + drop * 0.30)), T @ Vector((x0, 0, zb))]
    faces = [(0, 1, 4, 5), (1, 2, 3, 4)]
    ob = mesh_obj(name + "_cloth", verts, faces)
    assign(ob, cloth)
    out.append(ob)
    # emblem: gold disc + two crossed blades
    out.append(cyl(name + "_em", T @ T_at(xm, 0.02, zt - drop * 0.42,
                                          rx=math.pi * 0.5),
                   0.26, 0.03, M["gold"], seg=14))
    for sgn in (-1, 1):
        out.append(box(name + "_cr%d" % sgn,
                       T @ T_at(xm, 0.05, zt - drop * 0.42,
                                ry=sgn * math.radians(40)),
                       (0.46, 0.02, 0.05), M["iron"]))
    # fringe
    for i in range(5):
        out.append(box(name + "_fr%d" % i,
                       T @ T_at(x0 + w * (i + 0.5) / 5.0, 0, zb - 0.04),
                       (0.09, 0.02, 0.10), M["banner_trim"]))
    return out


def simple_tree(name, T, h=7.0, rng=None, leaf=None, leaf2=None, seg=10):
    """Broadleaf tree at ~700 faces: proper trunk, two branch stubs, three lobes.

    medbuild.tree() looks great but costs ~2.3k faces each, which dominates a
    whole village of twenty trees; at map scale three lobes read the same.
    """
    rng = rng or random.Random(hash(name) & 0xFFF)
    leaf = leaf or M["leaf"]
    leaf2 = leaf2 or M["leaf2"]
    out = []
    tr = 0.036 * h
    th = 0.62 * h
    out.append(cyl(name + "_tk0", T @ T_at(0, 0, th * 0.30), tr * 1.22,
                   th * 0.60, M["bark"], seg=8, r2=tr * 0.92))
    out.append(cyl(name + "_tk1", T @ T_at(0, 0, th * 0.72), tr * 0.92,
                   th * 0.45, M["bark"], seg=8, r2=tr * 0.55))
    out.append(cone(name + "_rt", T @ T_at(0, 0, 0.10), tr * 1.9, 0.34,
                    M["bark"], seg=8))
    for i, (rx, ry) in enumerate(((-0.55, 0.22), (0.60, -0.18))):
        out.append(cyl(name + "_br%d" % i,
                       T @ T_at(math.cos(i * 2.5) * tr * 0.6,
                                math.sin(i * 2.5) * tr * 0.6, th * 0.55,
                                rz=rx, ry=ry),
                       tr * 0.42, th * 0.42, M["bark"], seg=6,
                       r2=tr * 0.22))
    # four overlapping lobes, sized as a fraction of tree height: at 0.30·h the
    # canopy read as three balls on a stick from the aerial camera.
    lobes = ((0.00, 0.00, 0.88, 0.30, 0.84),
             (0.44, 0.12, 0.76, 0.25, 0.80),
             (-0.36, -0.16, 0.77, 0.24, 0.82),
             (0.05, -0.36, 0.71, 0.22, 0.78))
    for i, (dx, dy, zf, rf, sq) in enumerate(lobes):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.0, 0.5) * h * (0.0 if i == 0 else 0.05)
        out.append(sphere(name + "_c%d" % i,
                          T @ T_at(dx * h * 0.10 + math.cos(a) * rr,
                                   dy * h * 0.10 + math.sin(a) * rr,
                                   h * (zf - 0.10)),
                          rf * h, leaf if i % 2 == 0 else leaf2,
                          seg=seg, ring=max(6, seg - 2), squash=sq))
    return out


def haystack(name, T, r=1.55, h=2.15, rng=None):
    rng = rng or random.Random(hash(name) & 0x3F)
    out = []
    out.append(cyl(name + "_b", T @ T_at(0, 0, h * 0.24), r, h * 0.48,
                   M["straw"], seg=14, r2=r * 0.98))
    out.append(cone(name + "_c", T @ T_at(0, 0, h * 0.66), r * 1.02,
                    h * 0.62, M["straw"], seg=14))
    out.append(cyl(name + "_t", T @ T_at(0, 0, h * 0.90), 0.15, 0.34,
                   M["wood_fence"], seg=8))
    pts = []
    for i in range(9):
        a = rng.uniform(0, TAU)
        pts.append((math.cos(a) * r * rng.uniform(0.55, 0.92),
                    math.sin(a) * r * rng.uniform(0.55, 0.92),
                    h * rng.uniform(0.10, 0.55)))
    out.append(tufts(name + "_tu", T, pts, 0.16, 0.55, M["straw"], rng=rng))
    return out


def scarecrow(name, T, h=2.35):
    out = []
    out.append(box(name + "_post", T @ T_at(0, 0, h * 0.5), (0.10, 0.10, h),
                   M["wood_fence"], bev=0.006))
    out.append(box(name + "_arm", T @ T_at(0, 0, h * 0.72), (1.55, 0.08, 0.09),
                   M["wood_fence"], bev=0.006))
    out.append(cyl(name + "_torso", T @ T_at(0, 0, h * 0.50), 0.33, 0.78,
                   M["cloth_rag"], seg=10, r2=0.21))
    out.append(sphere(name + "_head", T @ T_at(0, 0, h * 0.86), 0.19,
                      M["sackcloth"], seg=12, ring=8))
    out.append(cone(name + "_brim", T @ T_at(0, 0, h * 0.99), 0.42, 0.13,
                    M["straw"], seg=12))
    out.append(cyl(name + "_crown", T @ T_at(0, 0, h * 1.06), 0.20, 0.22,
                   M["straw"], seg=10, r2=0.17))
    for sx in (-1, 1):
        out.append(box(name + "_sl%d" % sx,
                       T @ T_at(sx * 0.72, 0, h * 0.72), (0.12, 0.14, 0.16),
                       M["straw"]))
        pts = [(sx * 0.80, 0, h * 0.72)]
        out.append(tufts(name + "_st%d" % sx, T, pts, 0.11, 0.30,
                         M["straw"], rng=random.Random(4)))
    rng = random.Random(hash(name) & 0x1F)
    for i in range(6):
        a = TAU * i / 6.0
        out.append(box(name + "_rag%d" % i,
                       T @ T_at(math.cos(a) * 0.22, math.sin(a) * 0.22,
                                h * 0.14 - rng.uniform(0, 0.06),
                                rz=a),
                       (0.11, 0.02, 0.30), M["cloth_rag"]))
    return out


def woodpile(name, T, w=2.0, rows=4, along="x"):
    """Stacked firewood: rows of logs, triangular pile."""
    out = []
    r = 0.105
    for row in range(rows):
        n = rows - row
        span = w * (0.42 + 0.58 * n / float(rows))
        z = r + row * r * 1.72
        for i in range(n):
            u = -span * 0.5 + span * (i + 0.5) / n
            if along == "x":
                Mx = T @ T_at(u, 0, z, ry=math.pi * 0.5)
                out.append(cyl(name + "_l%d%d" % (row, i), Mx, r,
                               w * 0.92, M["wood_fence"], seg=7))
            else:
                Mx = T @ T_at(0, u, z, rx=math.pi * 0.5)
                out.append(cyl(name + "_l%d%d" % (row, i), Mx, r,
                               w * 0.92, M["wood_fence"], seg=7))
    # two leaning poles
    out.append(box(name + "_p0", T @ T_at(-w * 0.5 - 0.1, 0, 0.55, ry=0.30),
                   (0.10, 0.10, 1.35), M["wood_fence"]))
    return out


def fence_run(name, T, length, wood=None, gap=2.2, h=1.10, rails=(0.38, 0.80),
              footing=True):
    """Post-and-rail fence: square posts every `gap`, light rails between.

    Rails are kept to 0.10 x 0.08 m and each post shoulders 0.30 m above the top
    rail over a small footing, otherwise at map distance the fence reads as a
    ladder of planks lying on the grass.
    """
    wood = wood or M["wood_fence"]
    out = []
    n = max(2, int(round(length / gap)))
    for i in range(n + 1):
        u = -length * 0.5 + length * i / n
        out.append(box(name + "_p%d" % i, T @ T_at(u, 0, h * 0.5),
                       (0.15, 0.15, h), wood, bev=0.0))
        if footing:
            out.append(box(name + "_pf%d" % i, T @ T_at(u, 0, 0.07),
                           (0.32, 0.32, 0.14), M["stone_step"], bev=0.0))
    for z in rails:
        out.append(box(name + "_r%.2f" % z, T @ T_at(0, 0, z),
                       (length, 0.075, 0.10), wood, bev=0.0))
    return out


def gate(name, T, w=3.0, wood=None, iron_mat=None, swing=0.35):
    """Five-bar field gate hanging open between two posts."""
    wood = wood or M["wood_fence"]
    iron_mat = iron_mat or M["iron"]
    out = []
    for sx in (-1, 1):
        out.append(box(name + "_p%d" % sx, T @ T_at(sx * w * 0.5, 0, 0.62),
                       (0.17, 0.17, 1.30), wood, bev=0.012))
        out.append(sphere(name + "_pf%d" % sx,
                          T @ T_at(sx * w * 0.5, 0, 1.30), 0.10, iron_mat,
                          seg=8, ring=6))
    GM = T @ T_at(-w * 0.5, 0, 0, rz=swing)
    for i in range(5):
        z = 0.22 + i * 0.20
        out.append(box(name + "_b%d" % i, GM @ T_at(w * 0.49, 0, z),
                       (w * 0.98, 0.06, 0.075), wood, bev=0.005))
    for u, hh in ((0.03, 1.02), (0.97, 1.02)):
        out.append(box(name + "_v%.2f" % u, GM @ T_at(w * u, 0, 0.53),
                       (0.08, 0.07, hh), wood, bev=0.005))
    out.append(box(name + "_dg", GM @ T_at(w * 0.50, 0, 0.53, ry=0.74),
                   (1.35, 0.05, 0.07), wood))
    # hinges
    for z in (0.24, 0.86):
        out.append(box(name + "_h%.2f" % z, GM @ T_at(0.06, 0, z),
                       (0.30, 0.09, 0.06), iron_mat))
    return out


def lantern_post(name, T, h=2.5):
    """Timber post with a wrought-iron lantern: open frame, glowing panes.

    medkit.lantern() boxes the glass fully inside a solid iron box, which reads
    as a black cube. This builds an open cage so the warm pane is visible.
    """
    out = []
    out.append(box(name + "_post", T @ T_at(0, 0, h * 0.5), (0.135, 0.135, h),
                   M["wood_frame"], bev=0.01))
    out.append(box(name + "_cap", T @ T_at(0, 0, h + 0.04), (0.26, 0.26, 0.10),
                   M["iron"], bev=0.01))
    out.append(box(name + "_brace", T @ T_at(0, 0.13, h - 0.34, rx=0.60),
                   (0.07, 0.34, 0.07), M["wood_frame"], bev=0.006))
    # hanging bracket + lantern, offset out from the post
    zc = h - 0.44
    H = T @ T_at(0, 0.30, zc)
    out.append(box(name + "_arm", T @ T_at(0, 0.15, h - 0.14),
                   (0.06, 0.34, 0.06), M["iron"], bev=0.0))
    out.append(box(name + "_hook", H @ T_at(0, 0, 0.26), (0.035, 0.035, 0.10),
                   M["iron"], bev=0.0))
    out.append(box(name + "_pane", H @ T_at(0, 0, 0.02), (0.15, 0.15, 0.30),
                   M["lamp"], bev=0.0))
    out.append(box(name + "_top", H @ T_at(0, 0, 0.19), (0.23, 0.23, 0.035),
                   M["iron"], bev=0.0))
    out.append(box(name + "_bot", H @ T_at(0, 0, -0.15), (0.21, 0.21, 0.035),
                   M["iron"], bev=0.0))
    for i, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
        out.append(box(name + "_p%d" % i,
                       H @ T_at(sx * 0.083, sy * 0.083, 0.02),
                       (0.026, 0.026, 0.31), M["iron"], bev=0.0))
    out.append(cone(name + "_roof", H @ T_at(0, 0, 0.245), 0.17, 0.11,
                    M["iron"], seg=4))
    return out


def cart_ruts(name, T, length, w=0.16, gauge=0.85):
    """Two wheel ruts running along local X, spaced gauge apart in Y."""
    out = []
    for sx in (-1, 1):
        out.append(box(name + "_%d" % sx, T @ T_at(0, sx * gauge, -0.0015),
                       (length, w * 0.55, 0.004), M["earth"], bev=0.0))
    return out


# --------------------------------------------------------------------------
# fields
# --------------------------------------------------------------------------
def crop_ridge(name, T, length, radius=0.28, mat=None, seg=5, z=None):
    z = radius * 0.62 if z is None else z
    Mx = T @ T_at(0, 0, z, ry=math.pi * 0.5)
    return cyl(name, Mx, radius, length, mat, seg=seg, cap=True)


def field_block(name, T, w, d, crop_mats, soil=None, row_gap=1.22,
                ridge_r=0.30, tufts_prob=0.0, rng=None, tuft_h=0.34):
    """A ploughed field: soil slab, furrow ridges in alternating crop colours.
    The gap between ridges is kept near the ridge width so the furrows read
    from a high camera instead of merging into one yellow sheet."""
    rng = rng or random.Random(hash(name) & 0x7FF)
    soil = soil or M["earth"]
    out = [box(name + "_soil", T @ T_at(0, 0, 0.055), (w, d, 0.11), soil)]
    n = max(3, int((d - 1.6) / row_gap))
    for i in range(n):
        y = -d * 0.5 + (d - 1.6) * (i + 0.5) / n + 0.8 + rng.uniform(-0.06, 0.06)
        rw = w - 1.8 - rng.uniform(0.0, 1.3)
        x = rng.uniform(-0.35, 0.35)
        mat = crop_mats[i % len(crop_mats)]
        # break each furrow into stooked segments: one long prism reads as a
        # sawn plank from above, short offset pieces read as a crop in rows
        seg = max(2, int(rw / 3.6))
        for s in range(seg):
            sl = rw / seg - rng.uniform(0.10, 0.55)
            sx = -rw * 0.5 + (s + 0.5) * (rw / seg) + rng.uniform(-0.12, 0.12)
            smat = mat if rng.random() > 0.18 else crop_mats[(i + 1) % len(crop_mats)]
            out.append(crop_ridge(name + "_r%d_%d" % (i, s),
                                  T @ T_at(x + sx, y + rng.uniform(-0.05, 0.05), 0),
                                  sl, ridge_r * rng.uniform(0.88, 1.12), smat,
                                  seg=5))
        if tufts_prob > 0 and rng.random() < tufts_prob:
            pts = []
            k = max(3, int(rw / 2.0))
            for j in range(k):
                pts.append((-rw * 0.5 + rw * (j + 0.5) / k + rng.uniform(-0.55, 0.55),
                            rng.uniform(-0.22, 0.22),
                            ridge_r * 1.35))
            out.append(tufts(name + "_t%d" % i, T @ T_at(x, y, 0), pts,
                             ridge_r * 0.40, tuft_h, mat, rng=rng))
    return out


def wheat_field(name, T, w, d, mat=None, mat2=None, soil=None, rng=None,
                spacing=0.55, furrow_h=0.11):
    """Standing crop. Ploughed furrow lines stay low and earth-coloured and the
    gold comes from a dense scatter of stubble clumps: extruded ridges with a
    flat lit top read as sawn planks from a high camera, clumps do not."""
    rng = rng or random.Random(hash(name) & 0x3FF)
    mat = mat or M["crop_wheat"]
    mat2 = mat2 or M["crop_wheat2"]
    soil = soil or M["earth"]
    out = [ground_plate(name + "_soil", T, w, d, soil)]
    rows = max(3, int((d - 1.6) / 1.10))
    band = (d - 1.3) / rows
    for r in range(rows):
        y = -d * 0.5 + 0.65 + band * (r + 0.5)
        cm = mat if (r % 2 == 0) else mat2
        bw = band * rng.uniform(0.62, 0.94)
        if rng.random() < 0.14:
            continue                      # uncut / failed patch of the stand
        out.append(box(name + "_bd%d" % r,
                       T @ T_at(rng.uniform(-1.3, 1.3), y, 0.035),
                       (w - 1.3 - rng.uniform(0.0, 2.6), bw, 0.07), cm,
                       bev=0.03))
    pts_a, pts_b = [], []
    nx = max(2, int((w - 1.8) / spacing))
    ny = max(2, int((d - 1.8) / spacing))
    for iy in range(ny):
        y = -d * 0.5 + 0.9 + (d - 1.8) * (iy + 0.5) / ny
        for ix in range(nx):
            x = -w * 0.5 + 0.9 + (w - 1.8) * (ix + 0.5) / nx
            p = (x + rng.uniform(-0.09, 0.09), y + rng.uniform(-0.11, 0.11),
                 0.11)
            (pts_a if (iy % 2 == 0) else pts_b).append(p)
    out.append(tufts(name + "_a", T, pts_a, 0.27, 0.40, mat, seg=5, rng=rng))
    out.append(tufts(name + "_b", T, pts_b, 0.23, 0.35, mat2, seg=5, rng=rng))
    return out


def veg_rows(name, T, w, d, mat, mat2=None, rng=None, spacing=0.95,
             furrows=True):
    """Cabbage / bean plot: soil furrows with two sizes of leafy mound."""
    rng = rng or random.Random(hash(name) & 0x2FF)
    mat2 = mat2 or mat
    out = []
    rows = max(2, int((d - 1.2) / 1.10))
    if furrows:
        for r in range(rows + 1):
            y = -d * 0.5 + (d - 1.0) * r / rows
            out.append(crop_ridge(name + "_f%d" % r, T @ T_at(0, y, -0.02),
                                  w - 1.0, 0.17, M["earth"], seg=4))
    pts_a, pts_b = [], []
    for r in range(rows):
        y = -d * 0.5 + (d - 1.2) * (r + 0.5) / rows + 0.6
        cols = max(2, int((w - 1.2) / spacing))
        for c in range(cols):
            x = -w * 0.5 + (w - 1.2) * (c + 0.5) / cols + 0.6
            p = (x + rng.uniform(-0.16, 0.16), y + rng.uniform(-0.14, 0.14),
                 rng.uniform(-0.01, 0.03))
            (pts_a if rng.random() < 0.62 else pts_b).append(p)
    out.append(tufts(name + "_a", T, pts_a, 0.33, 0.44, mat, seg=6, rng=rng))
    out.append(tufts(name + "_b", T, pts_b, 0.24, 0.33, mat2, seg=5, rng=rng))
    return out


# --------------------------------------------------------------------------
# ground dressing (exported: lanes / aprons)
#
# Every ground plate is a slab whose TOP is at z and which continues DOWN 2 m.
# A thin floating plate shows an unshaded riser wherever the Unity terrain sits
# below z=0; with the skirt the side faces are buried and the town never looks
# like it stands on a plinth.
# --------------------------------------------------------------------------
PLATE_DEPTH = 2.0


def ground_plate(name, T, w, d, mat, top=0.0, rot=0.0, depth=PLATE_DEPTH):
    return box(name, T @ T_at(0, 0, top - depth * 0.5, rz=rot),
               (w, d, depth), mat, bev=0.0)


def lane_strip(name, T, w, d, mat=None, z=0.0):
    return ground_plate(name, T, w, d, mat or M["road"], top=z)


def apron(name, T, w, d, mat=None, z=0.0, rot=0.0):
    """Cobbled widening / farmyard surface (top flush with y=0)."""
    return ground_plate(name, T, w, d, mat or M["cobble"], top=z, rot=rot)


def path_to_door(name, T, length, w=1.25):
    """Cobbled run from the lane to a cottage door (T at the lane edge)."""
    return box(name, T @ T_at(0, length * 0.5, -PLATE_DEPTH * 0.5),
               (w, length, PLATE_DEPTH), M["cobble"])
# --------------------------------------------------------------------------
# Small service buildings and street furniture.
#
# Added for the farm-village relayout: a lean-to shed, a market bench, a
# laundry line and a stall. Every part reuses a material key that the palette
# already exports, so the Unity side needs no palette change.
# --------------------------------------------------------------------------


def shed(name, T, w=3.8, d=2.6, h=2.4, side=-1, ti=1, rng=None):
    """Lean-to shed: three boarded walls, a mono-pitch tile roof, open front."""
    r = rng or random.Random(11)
    parts = []
    tw = 0.13
    parts.append(box(name + "_plinth", T @ T_at(0, 0, 0.08),
                     (w + 0.18, d + 0.18, 0.16), M["stone_step"], bev=0.0))
    parts.append(box(name + "_back", T @ T_at(0, d * 0.5, h * 0.5),
                     (w, tw, h), M["wood_barn"], bev=0.0))
    for s in (-1, 1):
        parts.append(box("%s_s%d" % (name, s),
                         T @ T_at(s * (w * 0.5 - tw * 0.5), 0, h * 0.5),
                         (tw, d, h), M["wood_barn"], bev=0.0))
    # corner posts of the open front
    for s in (-1, 1):
        parts.append(box("%s_p%d" % (name, s),
                         T @ T_at(s * (w * 0.5 - 0.10), -d * 0.5 + 0.10, h * 0.5),
                         (0.17, 0.17, h), M["wood_frame"], bev=0.0))
    parts.append(box(name + "_beam", T @ T_at(0, -d * 0.5 + 0.10, h - 0.06),
                     (w, 0.20, 0.18), M["wood_frame"], bev=0.0))
    # board-and-batten suggestion: a few straps across the back wall
    for i in range(3):
        parts.append(box("%s_str%d" % (name, i),
                         T @ T_at(-w * 0.30 + i * w * 0.30, d * 0.5 - tw,
                                  h * 0.5),
                         (0.10, 0.05, h * 0.94), M["wood_board"], bev=0.0))
    # mono-pitch roof, sloping towards the open front
    parts.append(box(name + "_roof",
                     T @ T_at(0, -0.02, h + 0.30, ry=-0.34),
                     (w + 0.55, d + 0.55, 0.14), M["tile"][ti], bev=0.01))
    parts.append(box(name + "_ridge", T @ T_at(0, d * 0.5 - 0.1, h + 0.30),
                     (w + 0.62, 0.20, 0.22), M["tile"][1], bev=0.0))
    return parts


def bench(name, T, L=1.9, h=0.47, wood=None):
    """Plain three-plank bench, seat at h, with a low back rail."""
    w = wood or M["wood_board"]
    parts = [box(name + "_seat", T @ T_at(0, 0, h), (L, 0.46, 0.09), w,
                 bev=0.006)]
    for s in (-1, 1):
        parts.append(box("%s_l%d" % (name, s),
                         T @ T_at(s * (L * 0.5 - 0.14), 0, h * 0.5),
                         (0.12, 0.42, h), M["wood_frame"], bev=0.0))
        parts.append(box("%s_b%d" % (name, s),
                         T @ T_at(s * (L * 0.5 - 0.14), 0.20, h + 0.30),
                         (0.09, 0.09, 0.62), M["wood_frame"], bev=0.0))
    parts.append(box(name + "_back", T @ T_at(0, 0.22, h + 0.44),
                     (L, 0.08, 0.20), w, bev=0.006))
    return parts


def laundry(name, T, L=3.2, h=2.05, rng=None):
    """Two posts and a sagging line with washing; the yard rule in one prop."""
    r = rng or random.Random(17)
    parts = []
    for s in (-1, 1):
        parts.append(box("%s_post%d" % (name, s),
                         T @ T_at(s * L * 0.5, 0, h * 0.5),
                         (0.13, 0.13, h), M["wood_frame"], bev=0.0))
        parts.append(box("%s_cross%d" % (name, s),
                         T @ T_at(s * L * 0.5, 0, h - 0.05),
                         (0.55, 0.11, 0.11), M["wood_frame"], bev=0.0))
    parts.append(box(name + "_line", T @ T_at(0, 0, h - 0.02),
                     (L - 0.12, 0.025, 0.025), M["iron"], bev=0.0))
    n = 3
    for i in range(n):
        x = -L * 0.30 + i * L * 0.30
        mat = M["cloth_rag"] if i % 2 == 0 else M["sackcloth"]
        ww = r.uniform(0.55, 0.80)
        parts.append(box("%s_cl%d" % (name, i),
                         T @ T_at(x, 0, h - 0.02 - r.uniform(0.30, 0.44),
                                  rz=r.uniform(-0.05, 0.05)),
                         (ww, 0.03, r.uniform(0.60, 0.86)), mat, bev=0.0))
    return parts


def stall(name, T, w=2.9, d=2.1, h=2.3, rng=None):
    """Market stall: four posts, plank counter, canvas awning, crates and sacks."""
    r = rng or random.Random(19)
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box("%s_p%d%d" % (name, sx, sy),
                             T @ T_at(sx * (w * 0.5 - 0.12), sy * (d * 0.5 - 0.12),
                                      h * 0.5),
                             (0.15, 0.15, h), M["wood_frame"], bev=0.0))
    # canopy: two slim canvas panels on exposed rafters, eave valances so the
    # awning reads as cloth stretched on a frame and not a floating slab
    for sx in (-1, 1):
        parts.append(box("%s_ra%d" % (name, sx),
                         T @ T_at(sx * w * 0.26, 0, h + 0.16, ry=sx * 0.21),
                         (w * 0.56, 0.11, 0.11), M["wood_frame"], bev=0.0))
        parts.append(box("%s_a%d" % (name, sx),
                         T @ T_at(sx * w * 0.26, 0, h + 0.21, ry=sx * 0.21),
                         (w * 0.50, d + 0.26, 0.035), M["canvas"], bev=0.0))
        parts.append(box("%s_val%d" % (name, sx),
                         T @ T_at(sx * (w * 0.50 + 0.02), 0, h + 0.03),
                         (0.05, d + 0.26, 0.20), M["canvas"], bev=0.0))
    parts.append(box(name + "_ridge", T @ T_at(0, 0, h + 0.29),
                     (0.11, d + 0.34, 0.09), M["wood_board"], bev=0.0))
    for sy in (-1, 1):
        parts.append(box("%s_ea%s" % (name, sy),
                         T @ T_at(0, sy * (d * 0.5 + 0.02), h + 0.10),
                         (w + 0.14, 0.12, 0.12), M["wood_board"], bev=0.0))
    # counter on the -Y side
    parts.append(box(name + "_ctr", T @ T_at(0, -d * 0.5 + 0.42, 0.86),
                     (w - 0.5, 0.62, 0.10), M["wood_board"], bev=0.008))
    parts.append(box(name + "_ctr2", T @ T_at(0, -d * 0.5 + 0.42, 0.78),
                     (w - 0.5, 0.52, 0.08), M["wood_board"], bev=0.0))
    for s in (-1, 1):
        parts.append(box("%s_ctrl%d" % (name, s),
                         T @ T_at(s * (w * 0.5 - 0.42), -d * 0.5 + 0.42, 0.43),
                         (0.12, 0.52, 0.86), M["wood_frame"], bev=0.0))
    # goods
    for i in range(2):
        parts.append(box("%s_cr%d" % (name, i),
                         T @ T_at(-w * 0.22 + i * 0.72, -d * 0.5 + 0.42, 0.99,
                                  rz=r.uniform(-0.2, 0.2)),
                         (0.52, 0.42, 0.30), M["wood_board"], bev=0.01))
    parts.append(box(name + "_sack", T @ T_at(w * 0.26, -d * 0.5 + 0.42, 0.96),
                     (0.34, 0.30, 0.22), M["sackcloth"], bev=0.02))
    parts.append(box(name + "_sign", T @ T_at(0, d * 0.5 - 0.10, h - 0.30),
                     (0.95, 0.06, 0.42), M["wood_board"], bev=0.01))
    return parts


def bollard(name, T, h=0.58, r=0.17, mat=None):
    """Stone kerb bollard: a short drum under a wider coping disc."""
    mat = mat or M["stone"]
    return [cyl(name + "_sh", T @ T_at(0, 0, h * 0.5), r, h, mat, seg=10),
            cyl(name + "_cap", T @ T_at(0, 0, h + 0.045), r * 1.16, 0.09,
                M["stone_step"], seg=10)]


def hitch_post(name, T, h=0.95, mat=None):
    """Stone post with an iron hitching ring on its street side."""
    mat = mat or M["stone"]
    out = [box(name + "_p", T @ T_at(0, 0, h * 0.5), (0.20, 0.20, h), mat,
               bev=0.012),
           box(name + "_c", T @ T_at(0, 0, h + 0.045), (0.27, 0.27, 0.09),
               M["stone_step"], bev=0.01)]
    for i in range(8):
        a = i * TAU / 8.0
        out.append(box(name + "_r%d" % i,
                       T @ T_at(math.cos(a) * 0.15, 0.225,
                                h * 0.62 + math.sin(a) * 0.15),
                       (0.055, 0.045, 0.055), M["iron"], bev=0.0))
    return out
