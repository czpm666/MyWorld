"""hd_types.py - the six civic / military building types of the Asura capital.

Owner: TYPES agent.  Do not edit hd_houses / hd_shops / hd_dense / capital.py.

WHAT THIS IS
------------
The city had houses, shops and a castle but no *military* or *civic* layer, so
it read as a merchant town instead of the seat of a kingdom at war.  This module
adds six types at real size:

    training_ground  52 x 40   open sanded yard, palisade, butts, racks, dummies
    barracks         34 x 22   arcaded stone-and-timber block, stair, belfry turret
    stable_yard      30 x 21   long stable, half-doors, hay loft, paddock, cart shed
    bathhouse        23 x 19   domed hypocaust hall, outdoor basin, awning
    mill             14 x 14   water wheel in a mill race, hoist gable
    chapel_small     14 x 23   single nave, bell cote, walled graveyard

Two scale problems are solved here, and both are deliberate:

1. **These buildings do not fit a house plot.**  `hd_dense` units are 4.6-12.8 m
   on either edge (`MAX_D = 12.5`, measured max short edge 12.71 m over the real
   layout.json).  A 52 x 40 m training ground cannot be squeezed into a 7 x 9 m
   unit, and the brief forbids resizing a type past its unit's quad.  So
   `place()` has two passes: an in-quad pass (a type that fits a unit replaces
   it in place, no geometry moves) and a **block pass**, which finds a rectangle
   that fits inside a block's *inset* polygon - the courtyard behind the
   frontage row - drops only the units that rectangle actually overlaps, and
   appends one new site unit there.  Frontage rows survive, so a training ground
   reads as a yard in the middle of a block, which is what it would be.
2. **A block is not a ruler.**  Sites are searched at three sizes (nominal,
   mid, brief minimum) and the first ladder step that yields enough candidates
   is used, so the type is always inside its brief footprint.

CONVENTIONS (identical to hd_houses / hd_shops)
-----------------------------------------------
* metres, Z up, z = 0 is the ground
* origin = footprint centre, local +Y = the facade / front
* every builder returns a flat list of already-linked MESH objects, in WORLD
  space once `build()` has baked its transform
* `build(kind, MAT, rng, x=, y=, rot=, z=)` takes `rot` in RADIANS (the city
  passes `p["yaw"]`, which is radians); `rz=` is accepted in DEGREES for
  compatibility with `hd_shops.build`.

The two yard types emit their own ground at z = 0.10 (the block slab is
0.05-0.09) and push a keep-out rect into `KEEPOUT`, which `keepouts()` exposes
so street furniture does not end up on the archery range.
"""

import math
import random

import bpy
from mathutils import Matrix, Vector

import medkit as K
import hd_common as H
import hd_houses as S
import hd_houses_parts as HP

Ts = K.T_at
TAU = 2.0 * math.pi
D2R = math.radians

# ==========================================================================
# 0.  palette
# ==========================================================================
_EXTRA = {}


def _flat_mat(name, hexcol, rough=0.8, metal=0.0):
    """One solid colour with a roughness - paint, cloth, iron."""
    if name in K._MAT_CACHE:
        return K._MAT_CACHE[name]
    m, b = K._new_mat(name)
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Roughness"], rough)
    K._put(b, ["Metallic"], metal)
    K._MAT_CACHE[name] = m
    return m


def extra_materials():
    """The materials these types need and the house palette does not have."""
    global _EXTRA
    if _EXTRA:
        return _EXTRA
    _EXTRA = {
        # yards: sand, trodden sand, the worn track, straw, dirt
        "ty_sand": K.mat_earth("ty_sand", "#a8875a", "#78613e", scale=2.2,
                               detail=6.0, bump=0.28, patch=0.55),
        "ty_sand_dk": K.mat_earth("ty_sand_dk", "#8a6c42", "#584733", scale=3.2,
                                  detail=6.0, bump=0.20, patch=0.45),
        "ty_track": K.mat_earth("ty_track", "#6b5636", "#3f3423", scale=3.0,
                                detail=6.0, bump=0.12, patch=0.35),
        "ty_grass": K.mat_earth("ty_grass", "#4c5733", "#333c22", scale=2.6,
                                detail=7.0, bump=0.20, patch=0.60),
        "ty_straw": K.mat_earth("ty_straw", "#c7a758", "#8b7233", scale=6.5,
                                detail=4.0, bump=0.40, patch=0.20),
        "ty_hay": K.mat_earth("ty_hay", "#bda052", "#87692c", scale=5.0,
                              detail=5.0, bump=0.45, patch=0.15),
        "ty_dirt": K.mat_earth("ty_dirt", "#8b7350", "#5b4931", scale=4.0,
                               detail=6.0, bump=0.28, patch=0.50),
        "ty_cobble": K.mat_cobble("ty_cobble", "#8a8374", "#4a443a", "#aaa18d"),
        "ty_paving": K.mat_flag("ty_paving", "#8c8374", "#4b453b", "#aaa290", 2.0),
        # cloth
        "ty_canvas": K.mat_cloth("ty_canvas", "#c8bb9c", 0.92),
        "ty_red": K.mat_cloth("ty_red", "#8e2b22", 0.88),
        "ty_blue": K.mat_cloth("ty_blue", "#2b3d69", 0.88),
        "ty_gold": K.mat_cloth("ty_gold", "#c6a02a", 0.78),
        "ty_linen": K.mat_cloth("ty_linen", "#cfc6b2", 0.94),
        # paint / misc
        "ty_white": _flat_mat("ty_white", "#d8d2c4", 0.72),
        "ty_ring_red": _flat_mat("ty_ring_red", "#9e2f24", 0.75),
        "ty_shield": K.mat_wood("ty_shield", "#5c3c27", "#805434", rough=0.70,
                                scale=11.0),
        "ty_wood_pale": K.mat_wood("ty_wood_pale", "#7a6144", "#9c815e", rough=0.80,
                                   scale=15.0),
        "ty_iron": _flat_mat("ty_iron", "#2a2a30", 0.52, 0.72),
        "ty_bronze": _flat_mat("ty_bronze", "#9a7326", 0.42, 0.85),
        "ty_water": K.mat_water("ty_water", "#31535c"),
        "ty_leaf": K.mat_foliage("ty_leaf", "#3c5c2e", "#5a8038", 6.0),
    }
    return _EXTRA


def palette(MAT=None):
    """Merge the city palette with the type palette, return a NEW dict.

    `hd_houses.house()` mutates nothing on MAT, and neither do we: the caller's
    dict (capital_hd_glue.house_mats output) is copied, so a type built here can
    never bleed a material back into the houses.
    """
    P = dict(MAT or {})
    for k, v in HP.house_materials().items():
        P.setdefault(k, v)
    P.update(extra_materials())
    if P.get("tile") is None:
        P["tile"] = K.mat_tile("ty_tile")
    try:
        # the same re-skin house() applies: medkit.mat_tile is a brick shader
        # and on a 50 deg slope reads as a masonry wall
        P["tile"] = HP.roof_materials(P["tile"])[1]
    except Exception:
        pass
    if P.get("stone") is None:
        P["stone"] = K.mat_stone("ty_stone", "#7b7264", "#484238", "#968d7e", 2.2)
    P.setdefault("slate", None)
    HP.bind(P)
    return P


def _m(P, key, fallback="stone"):
    v = P.get(key)
    if v is None:
        v = P.get(fallback)
    return v


# ==========================================================================
# 1.  small geometry helpers
# ==========================================================================
def _flat(x):
    """Flatten arbitrarily nested lists of objects, dropping None."""
    out = []
    for p in (x or ()):
        if isinstance(p, (list, tuple)):
            out.extend(_flat(p))
        elif p is not None:
            out.append(p)
    return out


def _wall(name, T, w, h, th, ops, mat, y=0.0):
    """A wall slab in the local XZ plane facing +Y, with real openings.

    `ops` = [(x, ow, z0, oh), ...].  Identical recipe to hd_houses._wall: the
    pier / sill / head boxes are merged into ONE mesh.
    """
    cy = y + th * 0.5
    specs = []
    cur = -w * 0.5
    for (ox, ow, z0, oh) in sorted(ops, key=lambda o: o[0]):
        lo, hi = ox - ow * 0.5, ox + ow * 0.5
        if lo - cur > 0.05:
            specs.append((T @ Ts((cur + lo) * 0.5, cy, h * 0.5), (lo - cur, th, h)))
        if z0 > 0.05:
            specs.append((T @ Ts(ox, cy, z0 * 0.5), (ow, th, z0)))
        top = z0 + oh
        if h - top > 0.05:
            specs.append((T @ Ts(ox, cy, (top + h) * 0.5), (ow, th, h - top)))
        cur = hi
    if w * 0.5 - cur > 0.05:
        specs.append((T @ Ts((cur + w * 0.5) * 0.5, cy, h * 0.5),
                      (w * 0.5 - cur, th, h)))
    if not specs:
        return []
    return [HP.boxmesh(name, specs, mat)]


def _arch_specs(T, half_w, spring_z, thick=0.26, n=9, band=0.24):
    """Voussoir boxes for a semicircular arch, as boxmesh specs on edge z=0."""
    r = half_w + band * 0.5
    out = []
    for i in range(n):
        a = math.pi * (i + 0.5) / n
        x = math.sin(a) * r
        z = spring_z + math.cos(a) * r
        out.append((T @ Ts(x, 0, z, ry=a), (band, thick, 2.0 * r * math.pi / n / 1.02)))
    return out


def _arch(name, T, half_w, spring_z, mat, stone=None, n=9, band=0.26, thick=0.30):
    """Arch band + its stone surround (keystone, springers)."""
    out = [HP.boxmesh(name, _arch_specs(T, half_w, spring_z, thick, n, band), mat,
                      bev=0.008)]
    if stone is not None:
        specs = [(T @ Ts(0, 0, spring_z + half_w + band * 0.5),
                  (band * 1.5, thick * 1.02, band * 1.5))]
        for sx in (-1, 1):
            specs.append((T @ Ts(sx * (half_w + band * 0.5), 0, spring_z - 0.05),
                          (band, thick * 1.02, 0.34)))
        out.append(HP.boxmesh(name + "_k", specs, stone, bev=0.008))
    return out


def _fence(name, T, length, h, wood, spacing=1.7, rails=2, rail_w=0.09):
    """Post-and-rail fence running along local X, centred on T."""
    n = max(1, int(round(length / spacing)))
    specs = []
    for i in range(n + 1):
        u = -length * 0.5 + i * length / n
        specs.append((T @ Ts(u, 0, h * 0.5), (0.13, 0.13, h)))
    for k in range(rails):
        z = h * (0.30 + 0.34 * k) if rails > 1 else h * 0.55
        specs.append((T @ Ts(0, 0, z), (length, rail_w, 0.105)))
    return [HP.boxmesh(name, specs, wood, bev=0.005)]


def _palisade(name, T, length, h, wood, dark, spacing=0.54, pointed=True):
    """Close-set pointed timber palisade along local X, one merged mesh.

    spacing 0.54 m: at 0.40 the ground alone was 130k tris after bevel, and from
    the 34 m game camera a denser palisade reads as a solid wall anyway.
    """
    n = max(2, int(length / spacing))
    specs = []
    for i in range(n):
        u = -length * 0.5 + (i + 0.5) * length / n
        specs.append((T @ Ts(u, 0, h * 0.5), (0.20, 0.17, h)))
        if pointed:
            specs.append((T @ Ts(u, 0, h + 0.14), (0.155, 0.11, 0.28)))
    rails = []
    for z in (h * 0.26, h * 0.74):
        rails.append((T @ Ts(0, 0.105, z), (length, 0.07, 0.15)))
    out = [HP.boxmesh(name + "_p", specs, wood, bev=0.004),
           HP.boxmesh(name + "_r", rails, dark, bev=0.004)]
    return out


def _stairs(name, T, w, n, rise, run, mat, rail=None):
    """Straight flight climbing towards local +Y, bottom step at z=0."""
    specs = []
    for i in range(n):
        specs.append((T @ Ts(0, i * run, (i + 1) * rise * 0.5),
                      (w, run * 1.02, (i + 1) * rise)))
    out = [HP.boxmesh(name, specs, mat, bev=0.006)]
    if rail is not None:
        rs = []
        for sx in (-1, 1):
            for i in range(0, n):
                rs.append((T @ Ts(sx * (w * 0.5 - 0.09), i * run, i * rise + 0.42),
                           (0.08, 0.08, 0.84)))
            rs.append((T @ Ts(sx * (w * 0.5 - 0.09), (n - 1) * run * 0.5,
                              n * rise * 0.5 + 0.86),
                       (0.09, n * run + 0.2, 0.09)))
        out.append(HP.boxmesh(name + "_r", rs, rail, bev=0.004))
    return out


def _rack(name, T, w, wood, iron, n=8, h=1.5, spear=2.35):
    """Weapon rack: two uprights, two rails, a row of spears leaning back."""
    specs = [(T @ Ts(sx * w * 0.5, 0, h * 0.5), (0.115, 0.115, h)) for sx in (-1, 1)]
    specs.append((T @ Ts(0, 0.02, h * 0.90), (w, 0.11, 0.115)))
    specs.append((T @ Ts(0, 0.06, 0.30), (w, 0.10, 0.10)))
    specs.append((T @ Ts(0, 0.03, 0.05), (w, 0.16, 0.10)))
    out = [HP.boxmesh(name + "_f", specs, wood, bev=0.005)]
    sp, tip = [], []
    for i in range(n):
        u = -w * 0.5 + (i + 0.5) * w / n
        sp.append((T @ Ts(u, 0.11, spear * 0.5 + 0.10, rx=D2R(-8.0)), 0.017, spear))
        tip.append((T @ Ts(u, 0.11 + spear * 0.5 * math.sin(D2R(8.0)),
                           spear + 0.16, rx=D2R(-8.0)), (0.05, 0.05, 0.19)))
    out.append(HP.cylmesh(name + "_s", sp, wood, seg=5))
    out.append(HP.boxmesh(name + "_t", tip, iron, bev=0.006))
    return out


def _shield(name, T, r, face, rim, boss):
    """Round shield lying flat against a wall at T, face pointing local +Y."""
    out = [K.cyl(name + "_f", T, r, 0.055, face, seg=14),
           K.cyl(name + "_m", T @ Ts(0, 0.030, 0), r * 0.30, 0.06, boss, seg=10),
           K.cyl(name + "_r", T @ Ts(0, -0.012, 0), r * 1.03, 0.045, rim, seg=14)]
    return out


def _dummy(name, T, straw, wood, rope, cloth=None):
    """Padded straw training dummy on a post with a cross arm."""
    out = [K.cyl(name + "_p", T @ Ts(0, 0, 0.85), 0.075, 1.7, wood, seg=6),
           K.cyl(name + "_a", T @ Ts(0, 0, 1.44, ry=D2R(90)), 0.055, 1.15, wood, seg=6),
           K.sphere(name + "_b", T @ Ts(0, 0, 1.22), 0.27, straw, seg=9, ring=6,
                    squash=1.45),
           K.sphere(name + "_h", T @ Ts(0, 0, 1.70), 0.165, straw, seg=9, ring=6),
           K.cyl(name + "_r1", T @ Ts(0, 0, 1.02), 0.285, 0.045, rope, seg=10),
           K.cyl(name + "_r2", T @ Ts(0, 0, 1.42), 0.285, 0.045, rope, seg=10)]
    if cloth is not None:
        out.append(K.cyl(name + "_s", T @ Ts(0, 0, 1.30), 0.30, 0.30, cloth, seg=10))
    return out


def _butt(name, T, hay, board, rings, bale=1.15):
    """Archery butt: straw bale, plank face, painted rings."""
    out = [K.box(name + "_h", T @ Ts(0, 0, 0.32), (1.5, 0.95, 0.64), hay, bev=0.05),
           K.box(name + "_h2", T @ Ts(0, 0, 0.86), (1.35, 0.8, 0.5), hay, bev=0.05),
           K.box(name + "_b", T @ Ts(0, 0.30, 0.95, rx=D2R(7.0)),
                 (1.05, 0.13, 1.55), board, bev=0.01)]
    for k, (r, m) in enumerate(rings):
        out.append(K.cyl(name + "_r%d" % k, T @ Ts(0, 0.38 + 0.012 * k, 0.98,
                                                   rx=D2R(90.0 - 7.0)), r, 0.02, m,
                         seg=16))
    return out


def _stand(name, T, w, d, wood, cloth, trim, tiers=3):
    """Tiered viewing stand with a cloth canopy, facing local +Y."""
    specs = []
    for i in range(tiers):
        h = 0.40 * (i + 1)
        y = -d * 0.5 + (i + 0.5) * d / tiers
        specs.append((T @ Ts(0, y, h * 0.5), (w, d / tiers * 0.94, h)))
    out = [HP.boxmesh(name + "_t", specs, wood, bev=0.008)]
    ps = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            ps.append((T @ Ts(sx * (w * 0.5 - 0.14), sy * (d * 0.5 - 0.16), 1.16),
                       (0.14, 0.14, 2.32)))
    out.append(HP.boxmesh(name + "_p", ps, wood, bev=0.005))
    out.append(K.box(name + "_c", T @ Ts(0, 0, 2.42), (w + 0.42, d + 0.42, 0.06),
                     cloth, bev=0.01))
    out.append(K.box(name + "_v", T @ Ts(0, d * 0.5 + 0.20, 2.24),
                     (w + 0.42, 0.05, 0.30), trim))
    for sx in (-1, 1):
        out.append(K.box(name + "_vt%d" % sx, T @ Ts(sx * (w * 0.5 + 0.19), 0,
                                                     2.24), (0.05, d + 0.42, 0.30),
                         trim))
    return out


def _trough(name, T, w, d, stone, water, h=0.62):
    out = [K.box(name + "_b", T @ Ts(0, 0, h * 0.5), (w, d, h), stone, bev=0.02),
           K.box(name + "_w", T @ Ts(0, 0, h - 0.055), (w - 0.26, d - 0.26, 0.03),
                 water),
           K.box(name + "_l", T @ Ts(0, 0, h - 0.02), (w, 0.09, 0.10), stone)]
    return out


def _well(name, T, stone, wood, iron, water, r=0.95, h=0.85):
    out = [K.cyl(name + "_r", T @ Ts(0, 0, h * 0.5), r, h, stone, seg=14),
           K.cyl(name + "_w", T @ Ts(0, 0, h - 0.06), r * 0.78, 0.04, water, seg=14)]
    for sx in (-1, 1):
        out.append(K.box(name + "_p%d" % sx, T @ Ts(sx * (r + 0.10), 0, h + 1.0),
                         (0.14, 0.14, 2.0), wood))
    out.append(K.box(name + "_ax", T @ Ts(0, 0, h + 1.85), (2.4, 0.12, 0.12), wood))
    out.append(K.cyl(name + "_bu", T @ Ts(0, 0, h + 1.55, ry=D2R(90)), 0.13, 0.9,
                     wood, seg=8))
    out.append(K.cyl(name + "_pa", T @ Ts(0, 0, h + 1.05), 0.17, 0.30, wood, seg=8))
    out += HP.roof(name + "_rf", T @ Ts(0, 0, h + 2.05), 2.5, 2.1, 0.0, 42,
                   P_tile_tmp[0], wood, stone, ov_v=0.14, ov_g=0.14, course=0.22,
                   riser=0.04, ridge=False, moss=0.0)[0]
    return out


# `_well` needs the roof tile material; set by each builder before use.
P_tile_tmp = [None]


def _half_door(name, T, w, h, wood, iron, open_deg=72.0):
    """Dutch door: lower leaf shut, upper leaf swung out on its hinges."""
    out = [K.box(name + "_lo", T @ Ts(0, 0, h * 0.27), (w, 0.09, h * 0.54), wood,
                 bev=0.008)]
    for k in (0.34, 0.62, 0.90):
        out.append(K.box(name + "_lb%d" % int(k * 100),
                         T @ Ts(0, 0.05, h * 0.54 * k * 0.98), (w, 0.035, 0.05), iron))
    up = T @ Ts(0, 0.05, h * 0.56) @ Matrix.Rotation(-D2R(open_deg), 4, "X")
    out.append(K.box(name + "_up", up @ Ts(0, 0, h * 0.22), (w * 0.97, 0.07,
                                                            h * 0.44), wood, bev=0.008))
    for k in (0.30, 0.68):
        out.append(K.box(name + "_ub%d" % int(k * 100),
                         up @ Ts(0, 0.04, h * 0.44 * k), (w * 0.93, 0.03, 0.05), iron))
    for sx in (-1, 1):
        out.append(K.box(name + "_h%d" % sx, T @ Ts(sx * (w * 0.5 + 0.05), 0,
                                                     h * 0.52), (0.09, 0.10, 0.16), iron))
    return out


def _headstone(name, T, w, h, stone, rng, tilt=0.0):
    """Weathered gravestone: slab with a rounded top, always a little askew."""
    t = tilt or rng.uniform(-4.0, 4.0)
    M = T @ Matrix.Rotation(D2R(t), 4, "Y") @ Matrix.Rotation(D2R(t * 0.6), 4, "X")
    out = [K.box(name + "_s", M @ Ts(0, 0, h * 0.5 - 0.06), (w, 0.12, h), stone,
                 bev=0.012),
           K.box(name + "_t", M @ Ts(0, 0, h - 0.03), (w * 0.72, 0.115, 0.10), stone,
                 bev=0.02),
           K.box(name + "_b", T @ Ts(0, 0, 0.04), (w + 0.16, 0.30, 0.08), stone)]
    return out


def _bell(name, T, wood, bronze, r=0.34, h=0.55):
    out = [K.cyl(name + "_b", T @ Ts(0, 0, h * 0.5), r, h, bronze, seg=12, r2=r * 0.62),
           K.cyl(name + "_c", T @ Ts(0, 0, h + 0.03), r * 0.42, 0.10, bronze, seg=8),
           K.box(name + "_y", T @ Ts(0, 0, h + 0.34), (0.11, 0.11, 0.62), wood)]
    return out


def _domed_roof(name, T, r, h, tile, seg=26):
    """Hypocaust dome: lathe of overlapping tile rings, apex slightly flat."""
    prof = [(r, 0.0), (r * 0.995, 0.10), (r * 0.965, 0.26), (r * 0.90, 0.46),
            (r * 0.80, 0.62), (r * 0.66, 0.775), (r * 0.48, 0.885),
            (r * 0.28, 0.955), (r * 0.12, 0.99), (0.0, 1.0)]
    prof = [(rr, zz * h) for (rr, zz) in prof]
    out = [H.lathe(name, prof, tile, seg=seg, T=T, close_bottom=False, smooth=True)]
    bands = []
    for i in range(1, 6):
        t = i / 6.0
        rr = r * math.cos(t * math.pi * 0.5) * 0.99 + 0.05
        zz = h * math.sin(t * math.pi * 0.5) * 0.99
        bands.append((T @ Ts(0, 0, zz), max(0.10, r - rr) * 0.0 + 0.0))
    del bands
    return out


def _sacks(name, T, n, cloth, rng, spread=1.0):
    out = []
    for i in range(n):
        a = rng.uniform(0, TAU)
        d = rng.uniform(0.0, spread)
        out.append(K.sphere(name + "_%d" % i,
                            T @ Ts(math.cos(a) * d, math.sin(a) * d, 0.30,
                                   rz=rng.uniform(0, TAU)),
                            0.30, cloth, seg=9, ring=6, squash=1.05))
    return out


def _cart_shed(name, T, w, d, h, wood, dark, tile, trim):
    """Open-fronted lean-to on the local +Y side."""
    specs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            specs.append((T @ Ts(sx * (w * 0.5 - 0.15), sy * (d * 0.5 - 0.15),
                                 h * 0.5), (0.16, 0.16, h)))
    specs.append((T @ Ts(0, d * 0.5 - 0.15, h * 0.96), (w, 0.15, 0.16)))
    specs.append((T @ Ts(0, -d * 0.5 + 0.15, h * 0.70), (w, 0.15, 0.16)))
    for sx in (-1, 1):
        specs.append((T @ Ts(sx * (w * 0.5 - 0.15), 0, h * 0.83),
                      (0.14, d, 0.14)))
    out = [HP.boxmesh(name + "_f", specs, wood, bev=0.005)]
    # mono-pitch roof: one slab tilted so the front eave is the low side
    rw = w + 0.7
    rd = d / math.cos(D2R(16.0)) + 0.5
    M = T @ Ts(0, 0, h + 0.10) @ Matrix.Rotation(D2R(-16.0), 4, "X")
    out.append(K.box(name + "_r", M, (rw, rd, 0.13), tile, bev=0.01))
    out.append(K.box(name + "_fz", M @ Ts(0, -rd * 0.5 + 0.05, -0.10),
                     (rw, 0.10, 0.16), trim))
    return out


def _pool(name, T, w, d, stone, water, coping, wall=0.36, depth=0.55):
    """Sunken basin: stone rim, water at -0.16, steps on the local -Y side."""
    out = []
    for sx in (-1, 1):
        out.append(K.box(name + "_sx%d" % sx, T @ Ts(sx * (w * 0.5 + wall * 0.5), 0,
                                                     depth * 0.5 - 0.10),
                         (wall, d + wall * 2, depth + 0.20), stone, bev=0.02))
    for sy in (-1, 1):
        out.append(K.box(name + "_sy%d" % sy, T @ Ts(0, sy * (d * 0.5 + wall * 0.5),
                                                     depth * 0.5 - 0.10),
                         (w, wall, depth + 0.20), stone, bev=0.02))
    out.append(K.box(name + "_w", T @ Ts(0, 0, depth - 0.28), (w, d, 0.04), water))
    for sy in (-1, 1):
        out.append(K.box(name + "_cp%d" % sy,
                         T @ Ts(0, sy * (d * 0.5 + wall * 0.5), depth + 0.06),
                         (w + wall * 2 + 0.16, wall + 0.16, 0.10), coping, bev=0.014))
    for sx in (-1, 1):
        out.append(K.box(name + "_cpx%d" % sx,
                         T @ Ts(sx * (w * 0.5 + wall * 0.5), 0, depth + 0.06),
                         (wall + 0.16, d, 0.10), coping, bev=0.014))
    # two submerged steps into the water on the +Y side
    for i in range(2):
        out.append(K.box(name + "_st%d" % i,
                         T @ Ts(0, d * 0.5 - 0.30 - i * 0.42, depth - 0.30 - i * 0.18),
                         (w * 0.6, 0.42, 0.14), stone))
    return out


def _sign_board(name, T, w, h, board, face, iron):
    """Painted name board - used on the barracks gate and the mill."""
    out = [K.box(name + "_b", T @ Ts(0, 0, 0), (w, 0.07, h), board, bev=0.008),
           K.box(name + "_f", T @ Ts(0, 0.042, 0), (w * 0.86, 0.012, h * 0.72), face)]
    for sx in (-1, 1):
        out.append(K.box(name + "_n%d" % sx, T @ Ts(sx * w * 0.30, 0.05, h * 0.30),
                         (0.05, 0.02, 0.05), iron))
    return out


def _cobble_apron(name, T, w, d, mat, z=0.10):
    """A ground patch: n-gon at z, used for yards, terraces, grave plots."""
    hw, hd = w * 0.5, d * 0.5
    c = min(0.9, min(hw, hd) * 0.20)
    pts = [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
           (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]
    vs = [(T @ Vector((x, y, 0.0))).to_tuple() for (x, y) in pts]
    vs = [(v[0], v[1], z) for v in vs]
    ob = K.mesh_obj(name, vs, [tuple(range(len(vs)))])
    K.assign(ob, mat)
    return ob


# ==========================================================================
# 2.  training_ground   (52 x 40 nominal, brief 46-60 x 34-46)
# ==========================================================================
def training_ground(MAT, rng, w=52.0, d=40.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    sand, sdk = P["ty_sand"], P["ty_sand_dk"]
    track, straw, dirt = P["ty_track"], P["ty_straw"], P["ty_dirt"]
    wood, dark = P["ty_wood_pale"], P["wood_dark"]
    stone, iron = P["stone"], P["iron"]
    hay, board = P["ty_hay"], P["ty_wood_pale"]
    red, blue, canvas = P["ty_red"], P["ty_blue"], P["ty_canvas"]
    white, ring = P["ty_white"], P["ty_ring_red"]
    out = []

    # ---- ground: sand bed, worn track, raked drill square, straw ----------
    out.append(_cobble_apron("tg_sand", Ts(0, 0, 0), w - 1.0, d - 1.0, sand, 0.100))
    curb = []
    for sy in (-1, 1):
        curb.append((Ts(0, sy * (hd - 0.5), 0.16), (w - 1.0, 0.42, 0.13)))
    for sx in (-1, 1):
        curb.append((Ts(sx * (hw - 0.5), 0, 0.16), (0.42, d - 1.0, 0.13)))
    out.append(HP.boxmesh("tg_curb", curb, stone, bev=0.01))

    # worn running track: a rectangle ring of packed dirt
    tw = 1.5
    ring_specs = []
    ix, iy = hw - 3.6, hd - 3.6
    for sy in (-1, 1):
        ring_specs.append((Ts(0, sy * iy, 0.108), (2 * ix + tw * 2, tw, 0.02)))
    for sx in (-1, 1):
        ring_specs.append((Ts(sx * ix, 0, 0.108), (tw, 2 * iy - tw * 2, 0.02)))
    out.append(HP.boxmesh("tg_track", ring_specs, track))

    # raked rows in the drill square (the sand is *the subject* from 34 m up)
    rake = []
    ny = max(8, int((hd * 0.90) / 1.85))
    for i in range(ny):
        y = -hd * 0.54 + i * (hd * 0.92) / ny
        rake.append((Ts(-hw * 0.06, y, 0.111), (w * 0.56, 0.34, 0.016)))
    out.append(HP.boxmesh("tg_rake", rake, track, bev=0.0))
    # dark trodden band under the palisade: without it the yard reads as one
    # uniform pale rectangle from the game camera
    band = []
    for sy in (-1, 1):
        band.append((Ts(0, sy * (hd - 2.3), 0.107), (w - 2.6, 2.4, 0.014)))
    for sx in (-1, 1):
        band.append((Ts(sx * (hw - 2.3), 0, 0.107), (2.4, d - 2.6, 0.014)))
    out.append(HP.boxmesh("tg_band", band, sdk, bev=0.0))
    # duelling ring: 14 stones on a 4.2 m circle, the one graphic that says
    # "people practise here" even at 34 m
    ring_s = []
    for k in range(14):
        a = TAU * k / 14.0
        ring_s.append((Ts(math.cos(a) * 4.2 - hw * 0.02,
                          math.sin(a) * 4.2 - 1.0, 0.17, rz=a),
                       (0.46, 0.26, 0.34)))
    out.append(HP.boxmesh("tg_ring", ring_s, dark, bev=0.006))
    # churned sand: small dark scuffs where feet actually go
    for i in range(10):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(2.0, min(hw, hd) - 4.0)
        out.append(HP.blob("tg_ch%d" % i,
                           Ts(math.cos(a) * rr * 1.25, math.sin(a) * rr - 1.0, 0.105),
                           rng.uniform(0.9, 1.9), rng.uniform(0.6, 1.3), sdk, n=7,
                           jitter=0.45, rng=rng))
    for i in range(4):
        a = rng.uniform(0, TAU)
        d2 = rng.uniform(1.0, hd * 0.42)
        out.append(HP.blob("tg_wear%d" % i,
                           Ts(math.cos(a) * d2 * 1.2, math.sin(a) * d2, 0.106),
                           2.4, 1.7, track, n=8, jitter=0.4, rng=rng))
    for i in range(3):
        out.append(HP.blob("tg_straw%d" % i,
                           Ts(-hw * 0.55 + i * 2.6, -hd * 0.62 + rng.uniform(-1, 1),
                              0.109), 1.5, 1.1, straw, n=7, jitter=0.5, rng=rng))

    # ---- palisade: three sides + the front split by a gate ----------------
    out += _palisade("tg_pal_s", Ts(0, -hd + 0.30, 0), w - 0.8, 2.55, wood, dark)
    out += _palisade("tg_pal_w", Ts(-hw + 0.30, 0, 0, rz=D2R(90)), d - 0.8, 2.55,
                     wood, dark)
    out += _palisade("tg_pal_e", Ts(hw - 0.30, 0, 0, rz=D2R(90)), d - 0.8, 2.55,
                     wood, dark)
    gate_w = 7.2
    seg = (w - gate_w) * 0.5 - 0.4
    out += _palisade("tg_pal_nw", Ts(-(gate_w * 0.5 + seg * 0.5), hd - 0.30, 0), seg,
                     2.55, wood, dark)
    out += _palisade("tg_pal_ne", Ts(gate_w * 0.5 + seg * 0.5, hd - 0.30, 0), seg,
                     2.55, wood, dark)
    # gate piers, caps, leaves swung open
    for sx in (-1, 1):
        x = sx * gate_w * 0.5
        out.append(K.box("tg_gp%d" % sx, Ts(x, hd - 0.35, 2.25), (1.35, 1.35, 4.5),
                         stone, bev=0.02))
        out.append(K.box("tg_gc%d" % sx, Ts(x, hd - 0.35, 4.60), (1.65, 1.65, 0.22),
                         stone, bev=0.02))
        out += HP.corbel_table("tg_gcb%d" % sx, Ts(x, hd - 0.35, 4.20), 1.3, stone, n=2)
        M = Ts(x - sx * 0.68, hd - 0.35, 0) @ Matrix.Rotation(D2R(78.0 * sx), 4, "Z")
        leaf = []
        for k in range(4):
            leaf.append((M @ Ts(sx * (0.4 + k * 0.55), 0, 1.25), (0.5, 0.09, 2.35)))
        leaf.append((M @ Ts(sx * 1.35, 0, 0.30), (2.5, 0.11, 0.14)))
        leaf.append((M @ Ts(sx * 1.35, 0, 2.15), (2.5, 0.11, 0.14)))
        out.append(HP.boxmesh("tg_gl%d" % sx, leaf, dark, bev=0.005))
    # lintel + name board over the gate
    out.append(K.box("tg_lintel", Ts(0, hd - 0.35, 4.95), (gate_w - 0.5, 0.5, 0.55),
                     dark, bev=0.02))
    out += _sign_board("tg_board", Ts(0, hd - 0.06, 4.95), 4.6, 0.62, dark, P["ty_gold"],
                       iron)

    # ---- archery: backstop, butts, bale stack ----------------------------
    by = -hd + 1.6
    back = []
    for i in range(int((w * 0.74) / 0.55)):
        back.append((Ts(-w * 0.37 + i * 0.55, by, 1.35), (0.5, 0.30, 2.7)))
    out.append(HP.boxmesh("tg_res", back, dark, bev=0.006))
    out.append(K.box("tg_res_c", Ts(0, by, 2.74), (w * 0.76, 0.42, 0.16), wood))
    for sx in (-1, 1):
        out.append(K.box("tg_res_b%d" % sx, Ts(sx * w * 0.34, by + 0.55, 0.5),
                         (0.5, 0.5, 1.0), stone, bev=0.02))
    for i, fx in enumerate((-0.30, -0.10, 0.10, 0.30)):
        out += _butt("tg_butt%d" % i, Ts(fx * w, by + 3.1, 0), hay, board,
                     ((0.46, white), (0.30, ring), (0.15, P["ty_gold"])))
    # stacked straw bales beside the butts
    for i in range(5):
        out.append(K.box("tg_bale%d" % i,
                         Ts(w * 0.42 + (i % 2) * 0.9, by + 3.4 + (i // 2) * 0.8,
                            0.32 + (i % 2) * 0.0), (1.05, 0.72, 0.62), hay, bev=0.04))

    # ---- weapons: racks, shed, dummies, pells ----------------------------
    out += _rack("tg_rack_l", Ts(-w * 0.26, -hd + 8.2, 0), 3.4, wood, iron, n=9)
    out += _rack("tg_rack_r", Ts(w * 0.24, -hd + 8.2, 0), 3.4, wood, iron, n=9)
    # long low shed along the west side, open towards the yard
    # (kept at 12 m: at 15 m it swallowed the west stand, which sits at y +15)
    shed_d = min(12.0, d - 12.0)
    sx0 = -hw + 3.35
    out += _shed("tg_shed", Ts(sx0, 0.5, 0), 6.0, shed_d, 2.55, wood, dark,
                 P["tile"], stone, open_side=1)
    for i in range(7):
        out += _rack("tg_srack%d" % i, Ts(sx0 - 0.6, -shed_d * 0.36 + i * shed_d * 0.12,
                                          0), 1.5, wood, iron, n=5, h=1.35, spear=2.2)
    # dummies: a row of six, then two pairs on the flanks
    for i in range(6):
        out += _dummy("tg_dum%d" % i, Ts(-w * 0.20 + i * w * 0.075, -hd + 11.4, 0),
                      straw, wood, P["ty_linen"], red if i % 3 == 1 else None)
    for i in range(2):
        for sx in (-1, 1):
            out += _dummy("tg_dumf%d%d" % (i, sx),
                          Ts(sx * (w * 0.30 + i * 0.1), hd * 0.10 - i * 2.4, 0),
                          straw, wood, P["ty_linen"], None)
    # pells: four padded posts in the middle of the yard
    for i, (px, py) in enumerate(((-4.5, -2.0), (-1.5, -2.0), (1.5, -2.0), (4.5, -2.0))):
        out.append(K.cyl("tg_pell%d" % i, Ts(px, py, 0.78), 0.16, 1.55, wood, seg=8))
        out.append(K.cyl("tg_pellp%d" % i, Ts(px, py, 1.42), 0.29, 0.72, straw, seg=10))
        out.append(K.cyl("tg_pellr%d" % i, Ts(px, py, 1.06), 0.235, 0.07, P["ty_linen"],
                         seg=10))

    # ---- spectators: two stands facing the yard -------------------------
    for sx in (-1, 1):
        M = Ts(sx * (hw - 3.0), hd * 0.06 + 9.0, 0, rz=D2R(-90 * sx))
        out += _stand("tg_stand%d" % sx, M, 8.0, 2.6, wood, canvas, blue)

    # ---- flags, braziers, water -----------------------------------------
    for sx in (-1, 1):
        out += H.banner("tg_ban%d" % sx, Ts(sx * gate_w * 0.5, hd - 0.35, 4.72),
                        2.1, 1.5, red, iron, pole_h=3.2)
        out += H.banner("tg_ban2%d" % sx,
                        Ts(sx * (w * 0.30), -hd + 2.9, 0), 1.7, 1.25, blue, iron,
                        pole_h=6.4)
    out += _trough("tg_trough", Ts(-hw + 3.6, hd - 2.5, 0), 2.4, 0.85, stone,
                   P["ty_water"])
    for i in range(3):
        out += H.barrel("tg_bar%d" % i, Ts(sx0 + 3.4 + (i % 2) * 0.7,
                                           -shed_d * 0.5 + i * 0.7, 0),
                        0.30, 0.86, P["wood"], iron)
    for sx in (-1, 1):
        out.append(K.cyl("tg_brz%d" % sx, Ts(sx * (gate_w * 0.5 + 2.4), hd - 1.5, 0.62),
                         0.34, 0.5, iron, seg=10))
        out.append(K.cone("tg_brzf%d" % sx, Ts(sx * (gate_w * 0.5 + 2.4), hd - 1.5,
                                              0.95), 0.36, 0.34, P["ty_gold"], seg=10))
    return out


def _shed(name, T, w, d, h, wood, dark, tile, stone, open_side=1):
    """Long open-fronted shed: three walls, front posts, gable roof along Y.

    w runs along X (the shed's width), d along Y (its length); the open side
    faces local +X for open_side=1.  The roof ridge runs along Y, so the gable
    triangles land on the two end walls - the walls are boxes, not _wall()
    slabs, because a slab spanning `d` would stick out past a 6 m wide shed.
    """
    hw, hd = w * 0.5, d * 0.5
    out = []
    th = 0.24
    out.append(K.box(name + "_b", T @ Ts(-hw + th * 0.5, 0, h * 0.5), (th, d, h),
                     stone, bev=0.01))
    for sy in (-1, 1):
        out.append(K.box(name + "_e%d" % sy,
                         T @ Ts(0, sy * (hd - th * 0.5), h * 0.5), (w, th, h),
                         wood, bev=0.008))
    specs = []
    for i in range(max(2, int(d / 3.2)) + 1):
        u = -hd + i * d / max(2, int(d / 3.2))
        specs.append((T @ Ts(open_side * (hw - 0.14), u, h * 0.5),
                      (0.17, 0.17, h)))
    out.append(HP.boxmesh(name + "_p", specs, wood, bev=0.005))
    rp, _info = HP.roof(name + "_rf", T @ Ts(0, 0, 0), w, d, h, 40.0, tile, dark,
                        stone, ov_v=0.34, ov_g=0.36, moss=0.30, rng=None)
    out += rp
    # working bench inside
    out.append(K.box(name + "_bn", T @ Ts(-open_side * (hw - 1.3), 0, 0.82),
                     (0.75, d * 0.7, 0.12), wood, bev=0.01))
    return out


# ==========================================================================
# 3.  barracks   (34 x 22 nominal, brief 30-40 x 18-26)
# ==========================================================================
def barracks(MAT, rng, w=34.0, d=22.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    stone, st_w = P["stone"], P["stone_warm"]
    st_t, st_d = P["stone_trim"], P["stone_dark"]
    plaster = P["plaster"]
    wood, dark = P["wood"], P["wood_dark"]
    iron, glass, void = P["iron"], P["glass"], P["void"]
    tile, red, gold = P["tile"], P["ty_red"], P["ty_gold"]
    out = []

    fh1, fh2, fh3 = 3.55, 2.85, 2.85
    pl_h = 0.38
    eave = pl_h + fh1 + fh2 + fh3
    bw, bd = w - 7.0, 10.0
    bx, by = -2.0, -hd + bd * 0.5 + 0.6
    fy = by + bd * 0.5                      # the facade plane of the block
    th = 0.46

    # ---- plinth + arcade -------------------------------------------------
    out += HP.plinth("bk_pl", Ts(bx, by, 0), bw, bd, pl_h, st_w, moss=P["moss"],
                     rng=rng, spout=True)
    z0 = pl_h
    loggia = 2.45                            # depth of the open ground floor
    nbay = 5
    bay = (bw - 1.6) / nbay
    pier_w = 1.10
    spring = 2.15
    half = (bay - pier_w) * 0.5
    # back wall of the loggia (the real ground-floor wall)
    gops = [(-bw * 0.5 + 3.0, 1.5, 0, 2.35), (0.0, 1.35, 0.55, 1.55),
            (bw * 0.5 - 3.4, 1.5, 0, 2.35)]
    out += _wall("bk_gw", Ts(bx, by, z0), bw, fh1, th, gops, st_w,
                 y=bd * 0.5 - loggia - th)
    for (gx, gw, gz, gh) in gops:
        out += HP.door("bk_gd%d" % int(gx * 10), Ts(bx + gx, by + bd * 0.5 - loggia,
                                                    z0 + gz),
                       w=gw, h=gh, wood=dark, iron=iron, stone=st_d, steps=0,
                       arch=True, rng=rng)
    # piers + arches + spandrel over them
    piers, arches, span = [], [], []
    for i in range(nbay + 1):
        x = -bw * 0.5 + 0.8 + i * bay
        piers.append((Ts(bx + x, fy - 0.5, z0 + spring * 0.5),
                      (pier_w, 0.95, spring)))
        if i < nbay:
            cx = x + bay * 0.5
            arches += _arch("bk_ar%d" % i, Ts(bx + cx, fy - 0.5, z0), half, spring,
                            st_w, st_d, n=9, band=0.30, thick=0.98)
            span.append((Ts(bx + cx, fy - 0.5, z0 + spring + half + 0.10),
                         (bay - pier_w + 0.5, 0.95, fh1 - spring - half - 0.10)))
    out.append(HP.boxmesh("bk_pier", piers, st_w, bev=0.012))
    out += arches
    # the spandrel is what carries floor 2 over the loggia
    span.append((Ts(bx, fy - 0.5, z0 + spring + half + 0.10 + (fh1 - spring - half) * 0.5),
                 (bw, 0.95, max(0.12, fh1 - spring - half - 0.20))))
    out.append(HP.boxmesh("bk_span", span, st_w, bev=0.01))
    out.append(K.box("bk_slab", Ts(bx, by + bd * 0.5 - loggia * 0.5, z0 + fh1 - 0.14),
                     (bw, loggia + 0.2, 0.28), dark, bev=0.008))
    # shields and spears under the arcade
    for i in range(8):
        x = -bw * 0.5 + 1.6 + i * (bw - 3.2) / 7.0
        if any(abs(x - g) < 1.6 for (g, _w, _z, _h) in gops):
            continue
        out += _shield("bk_sh%d" % i,
                       Ts(bx + x, by + bd * 0.5 - loggia - th - 0.04, z0 + 1.55,
                          rx=D2R(90)),
                       0.46, P["ty_shield"], iron, gold)
    for i in range(2):
        out += _rack("bk_rk%d" % i, Ts(bx - 4.0 + i * 8.0,
                                       by + bd * 0.5 - loggia - 0.9, z0), 2.6, dark,
                     iron, n=7)

    # ---- floors 2 and 3 --------------------------------------------------
    z = pl_h + fh1
    for f, (fz, fh) in enumerate(((z, fh2), (z + fh2, fh3))):
        xs = [(-bw * 0.5 + 2.1) + i * (bw - 4.2) / 5.0 for i in range(6)]
        ops = [(x, 1.02, 0.86, 1.42) for x in xs]
        out += _wall("bk_fw%d" % f, Ts(bx, by, fz), bw, fh, th, ops, plaster,
                     y=bd * 0.5 - th)
        for i, x in enumerate(xs):
            out += HP.window("bk_win%d_%d" % (f, i), Ts(bx + x, fy, fz + 0.86), 1.02,
                             1.42, frame=st_d, glass=glass, wall_mat=plaster,
                             arch=None, shutters=wood if i % 2 == 0 else None,
                             sill=True, hood=True, bars=(2, 1), deep=0.18,
                             trim=st_t, reveal=st_t, rng=rng)
        out += HP.timber_frame("bk_tf%d" % f, Ts(bx, by, fz), bw, fh, dark,
                               ops=[(x - 0.62, x + 0.62) for x in xs],
                               y=bd * 0.5 + 0.015, stud=0.98, rng=rng)
        out.append(K.box("bk_band%d" % f, Ts(bx, by + bd * 0.5 + 0.02, fz - 0.04),
                         (bw + 0.34, 0.22, 0.20), st_d, bev=0.01))
        out += HP.jetty("bk_jt%d" % f, Ts(bx, by, 0), bw, bd * 0.5, bd * 0.5 + 0.26,
                        fz, dark, iron=iron) if f == 0 else []

    # side walls: stone up to the eaves, with two windows a floor
    for sx in (-1, 1):
        TT = Ts(bx + sx * bw * 0.5, by, 0, rz=D2R(-90 * sx))
        out += _wall("bk_sw%d" % sx, TT @ Ts(0, 0, pl_h), bd, eave - pl_h, th,
                     [(0.0, 1.06, 3.4, 1.35), (-2.9, 1.06, 1.9, 1.3),
                      (2.9, 1.06, 1.9, 1.3)], st_w, y=-th)
        for (u, ww, zz, hh) in ((0.0, 1.06, 3.4, 1.35), (-2.9, 1.06, 1.9, 1.3),
                                (2.9, 1.06, 1.9, 1.3)):
            out += HP.window("bk_sww%d%d" % (sx, int(u * 10)),
                             TT @ Ts(u, -th, pl_h + zz), ww, hh, frame=st_d,
                             glass=glass, wall_mat=st_w, arch="seg", sill=True,
                             trim=st_d, reveal=st_t, bars=(2, 1), deep=0.20, rng=rng)
        for k in range(5):
            out.append(K.box("bk_quo%d%d" % (sx, k),
                             Ts(bx + sx * (bw * 0.5 + 0.03),
                                by - bd * 0.5 + k * bd / 5.0, pl_h + (eave - pl_h) * 0.5),
                             (0.16, bd / 5.0 * 0.92, eave - pl_h), st_d, bev=0.008))
    # back wall
    out += _wall("bk_bw", Ts(bx, by, 0, rz=math.pi), bw, eave, th,
                 [(x, 0.95, zz, 1.2) for x in (-6.0, 0.0, 6.0)
                  for zz in (pl_h + 1.35, pl_h + fh1 + 1.2)], st_w, y=-bd * 0.5)

    # ---- roof ------------------------------------------------------------
    # pitch 46 on an 11 m span put a 5.7 m tiled slab in front of every camera:
    # the roof read as the building. 34 deg keeps the ridge at 13.0 and lets the
    # turret clear it, which is the silhouette that has to say "barracks".
    rp, info = HP.roof("bk_rf", Ts(bx, by, 0, rz=D2R(90)), bd, bw, eave, 34.0, tile,
                       dark, st_w, ov_v=0.46, ov_g=0.52, moss=0.55, rng=rng)
    out += rp
    for i in range(2):
        out += HP.chimney("bk_ch%d" % i, Ts(bx - bw * 0.28 + i * bw * 0.56, by, 0),
                          eave - 0.6, eave + 2.5, st_w, P["pot"], soot=P["soot"],
                          pots=2, rng=rng)

    # ---- bell / lookout turret ------------------------------------------
    tx = bx + bw * 0.5 - 2.4
    ty = by
    tz0 = eave - 1.0
    tw = 3.9
    out.append(K.box("bk_tw", Ts(tx, ty, tz0 + 3.0), (tw, tw, 6.0), st_w, bev=0.02))
    out += HP.corbel_table("bk_tc", Ts(tx, ty, tz0 + 5.55), tw + 0.5, st_d, n=5)
    out.append(K.box("bk_tr", Ts(tx, ty, tz0 + 5.78), (tw + 0.55, tw + 0.55, 0.22),
                     st_d, bev=0.012))
    # belfry openings on all four faces
    for k, ang in enumerate((0.0, 90.0, 180.0, 270.0)):
        M = Ts(tx, ty, tz0 + 4.05, rz=D2R(ang)) @ Ts(0, tw * 0.5 - 0.12, 0)
        out.append(K.box("bk_bf%d" % k, M, (1.65, 0.30, 1.85), void))
        out += _arch("bk_bfa%d" % k, M @ Ts(0, -0.10, 0.92), 0.82, 0.0, st_w, None,
                     n=7, band=0.22, thick=0.34)
    # crenels read as a red box on the roof from 34 m; a tiled pyramid cap is
    # the shape that says "bell tower" at that distance
    out.append(K.cone("bk_tcap", Ts(tx, ty, tz0 + 6.94, rz=D2R(45)),
                      (tw + 0.5) * 0.72, 2.10, tile, seg=4))
    out.append(K.sphere("bk_tball", Ts(tx, ty, tz0 + 8.10), 0.16, gold, seg=8, ring=6))
    out += _bell("bk_bell", Ts(tx, ty, tz0 + 4.55), dark, P["ty_bronze"])
    out += H.banner("bk_ban", Ts(tx, ty, tz0 + 8.05), 1.9, 3.2, red, iron, pole_h=2.9)

    # ---- external stair to floor 2, yard side ---------------------------
    stx = bx + bw * 0.5 - 1.2
    sty = by + bd * 0.5 + 0.1
    nstep = 10
    out += _stairs("bk_stair", Ts(stx, sty, 0), 1.55, nstep, 0.181, 0.33, st_w, st_d)
    out.append(K.box("bk_land", Ts(stx, sty + nstep * 0.33 + 0.55, z0 + fh1 - 0.12),
                     (1.9, 1.3, 0.24), st_w, bev=0.012))
    for sx in (-1, 1):
        out.append(K.box("bk_lp%d" % sx,
                         Ts(stx + sx * 0.98, sty + nstep * 0.33 + 0.55,
                            z0 + fh1 + 0.42), (0.12, 1.35, 0.95), st_d, bev=0.01))
    out.append(K.box("bk_lp_f", Ts(stx, sty + nstep * 0.33 + 1.18, z0 + fh1 + 0.42),
                     (2.06, 0.12, 0.95), st_d, bev=0.01))
    out.append(K.box("bk_sdoor", Ts(stx, fy + 0.02, z0 + fh1), (1.15, 0.14, 2.15),
                     dark, bev=0.01))

    # ---- muster yard -----------------------------------------------------
    yard_d = d - bd - 1.2
    out.append(_cobble_apron("bk_yard", Ts(0, hd - yard_d * 0.5 - 0.3, 0.10),
                            w - 0.9, yard_d - 0.4, P["ty_paving"], 0.101))
    out += _well("bk_well", Ts(-bw * 0.22, hd - yard_d * 0.55, 0), st_w, dark, iron,
                 P["ty_water"], r=0.92)
    out += _trough("bk_trough", Ts(bw * 0.30, hd - yard_d * 0.60, 0), 2.6, 0.9,
                   st_w, P["ty_water"])
    for i in range(3):
        out += H.barrel("bk_bar%d" % i, Ts(bx + bw * 0.34 + i * 0.75,
                                           hd - yard_d * 0.22, 0), 0.31, 0.88, wood,
                        iron)
    for i in range(2):
        out += H.crate("bk_crate%d" % i, Ts(bx - bw * 0.36 - i * 0.72,
                                            hd - yard_d * 0.24, 0), 0.66, wood)
    out += _rack("bk_yrack", Ts(bx + bw * 0.12, hd - yard_d * 0.20, 0), 3.0, dark, iron,
                 n=9)
    out += H.lantern_post("bk_lamp", Ts(gate_x0(bw), hd - 1.2, 0), 3.5, iron,
                          P["glow"])
    out += _sign_board("bk_board", Ts(gate_x0(bw), hd - 1.05, 3.05), 1.9, 0.56, dark,
                       gold, iron)
    return out


def gate_x0(bw):
    """Gate position helper so the lantern and board agree on one number."""
    return -bw * 0.5 + 0.8 + (bw - 1.6) * 0.5


# ==========================================================================
# 4.  stable_yard   (30 x 21 nominal, brief 26-34 x 18-24)
# ==========================================================================
def stable_yard(MAT, rng, w=30.0, d=21.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    stone, st_w, st_t = P["stone"], P["stone_warm"], P["stone_trim"]
    wood, dark, pale = P["wood"], P["wood_dark"], P["ty_wood_pale"]
    iron, tile, straw, hay = P["iron"], P["tile"], P["ty_straw"], P["ty_hay"]
    dirt, linen = P["ty_dirt"], P["ty_linen"]
    out = []

    # ---- the yard floor --------------------------------------------------
    out.append(_cobble_apron("sy_ground", Ts(0, 0, 0), w - 0.8, d - 0.8, dirt, 0.100))
    out.append(HP.boxmesh("sy_cob", [
        (Ts(-1.0, -1.4, 0.106), (w - 2.6, 2.6, 0.02))], P["ty_cobble"]))
    for i in range(4):
        out.append(HP.blob("sy_str%d" % i,
                           Ts(-6.0 + i * 3.4, -0.6 + rng.uniform(-0.6, 0.6),
                              0.109), 1.3, 0.85, straw, n=7, jitter=0.5, rng=rng))

    # ---- long stable + hay loft -----------------------------------------
    sw, sd = min(22.0, w - 7.0), 8.0
    sxp, syp = -1.0, -hd + sd * 0.5 + 0.9
    fy = syp + sd * 0.5
    eave = 4.95
    out += HP.plinth("sy_pl", Ts(sxp, syp, 0), sw, sd, 0.30, st_w, moss=P["moss"],
                     rng=rng)
    doors = [-sw * 0.5 + 2.0 + i * (sw - 4.0) / 4.0 for i in range(5)]
    ops = [(x, 1.52, 0.0, 0.0) for x in doors]
    ops = [(x, 1.52, 0.30, 2.32) for x in doors]
    for i in range(5):
        ops.append((doors[i], 0.62, 3.75, 0.55))
    ops.append((0.0, 2.30, 2.62, 1.95))
    out += _wall("sy_fw", Ts(sxp, syp, 0), sw, eave, 0.40, ops, st_w, y=sd * 0.5 - 0.40)
    for i, x in enumerate(doors):
        out += _half_door("sy_hd%d" % i, Ts(sxp + x, fy, 0.30), 1.46, 2.28, dark, iron,
                          70.0)
        out += HP.window("sy_lw%d" % i, Ts(sxp + x, fy, 3.75), 0.62, 0.55, frame=dark,
                         glass=P["glass"], wall_mat=st_w, sill=True, bars=(1, 0),
                         deep=0.16, trim=st_t, reveal=st_t, rng=rng)
    # hay loft opening + plank hoist beam
    out.append(K.box("sy_hd_dk", Ts(sxp, fy - 0.22, 3.60), (2.26, 0.10, 1.90),
                     P["void"]))
    hf = []
    for sx in (-1, 1):
        hf.append((Ts(sxp + sx * 1.20, fy - 0.06, 3.60), (0.14, 0.16, 2.05)))
    hf.append((Ts(sxp, fy - 0.06, 4.62), (2.60, 0.16, 0.15)))
    out.append(HP.boxmesh("sy_hf", hf, dark, bev=0.006))
    out.append(K.box("sy_hoist", Ts(sxp, fy + 0.85, 5.55), (0.22, 2.1, 0.22), dark,
                     bev=0.01))
    out.append(K.box("sy_hoist_s", Ts(sxp, fy + 0.35, 5.10), (0.16, 0.16, 1.0), dark))
    out.append(K.cyl("sy_pul", Ts(sxp, fy + 1.75, 5.42, rx=D2R(90)), 0.20, 0.10, iron,
                     seg=10))
    out.append(K.cyl("sy_rope", Ts(sxp, fy + 1.75, 4.35), 0.025, 2.1, linen, seg=5))
    out.append(K.sphere("sy_sack", Ts(sxp, fy + 1.75, 3.25), 0.34, linen, seg=9,
                        ring=6, squash=1.15))
    # timber frame on the loft storey + roof
    out += HP.timber_frame("sy_tf", Ts(sxp, syp, 3.10), sw, eave - 3.10, dark,
                           ops=[(x - 0.85, x + 0.85) for x in doors] +
                               [(-1.3, 1.3)],
                           y=sd * 0.5 + 0.015, stud=1.05, rng=rng)
    rp, _i = HP.roof("sy_rf", Ts(sxp, syp, 0, rz=D2R(90)), sd, sw, eave, 40.0, tile,
                     dark, st_w, ov_v=0.44, ov_g=0.50, moss=0.50, rng=rng)
    out += rp
    for sx in (-1, 1):
        TT = Ts(sxp + sx * sw * 0.5, syp, 0, rz=D2R(-90 * sx))
        out += _wall("sy_ew%d" % sx, TT, sd, eave, 0.40,
                     [(0.0, 1.05, 1.55, 1.25), (2.4, 0.55, 3.80, 0.50)], st_w, y=-0.40)
        out += HP.window("sy_eww%d" % sx, TT @ Ts(0, -0.40, 1.55), 1.05, 1.25,
                         frame=dark, glass=P["glass"], wall_mat=st_w, arch="seg",
                         sill=True, trim=st_t, reveal=st_t, deep=0.18, rng=rng)
    out += _wall("sy_bw", Ts(sxp, syp, 0, rz=math.pi), sw, eave, 0.40,
                 [(x, 0.55, 2.30, 0.60) for x in (-6.0, 0.0, 6.0)], st_w,
                 y=-sd * 0.5)
    out += HP.chimney("sy_ch", Ts(sxp + sw * 0.30, syp, 0), eave - 0.4, eave + 1.9,
                      st_w, P["pot"], soot=P["soot"], pots=1, rng=rng)

    # ---- paddock ---------------------------------------------------------
    px0, px1 = 4.6, hw - 1.1
    py0, py1 = 1.2, hd - 1.0
    pwy, pwx = px1 - px0, py1 - py0
    cx, cy = (px0 + px1) * 0.5, (py0 + py1) * 0.5
    out += _fence("sy_pf_n", Ts(cx, py1, 0), pwx, 1.35, pale, 1.8)
    out += _fence("sy_pf_e", Ts(px1, cy, 0, rz=D2R(90)), pwy, 1.35, pale, 1.8)
    out += _fence("sy_pf_s", Ts(cx, py0, 0), pwx, 1.35, pale, 1.8)
    out += _fence("sy_pf_w", Ts(px0, py0 + pwy * 0.5, 0, rz=D2R(90)), pwy, 1.35, pale,
                  1.8)
    out += _trough("sy_trough", Ts(px1 - 1.9, py0 + 1.5, 0), 1.9, 0.8, stone,
                   P["ty_water"])
    out += H.haystack("sy_hay", Ts(px1 - 2.4, py1 - 2.2, 0), 1.35, 1.9, hay)
    out += H.barrel("sy_bh", Ts(px1 - 1.0, py1 - 4.4, 0), 0.34, 0.95, wood, iron)

    # ---- cart shed, muck heap, sacks ------------------------------------
    out += _cart_shed("sy_cs", Ts(-hw + 5.0, hd - 5.6, 0), 8.2, 4.6, 2.55, pale, dark,
                      tile, dark)
    out += H.cart("sy_cart", Ts(-hw + 4.4, hd - 5.4, 0), dark, iron, 2.4, 1.25)
    out += _sacks("sy_sack", Ts(-hw + 8.4, hd - 4.0, 0), 4, linen, rng, 0.9)
    out.append(K.sphere("sy_muck", Ts(6.4, -hd + 2.4, 0.36), 1.15, dirt, seg=12,
                        ring=7, squash=0.55))
    out.append(K.sphere("sy_muck2", Ts(5.2, -hd + 2.9, 0.26), 0.8, straw, seg=10,
                        ring=6, squash=0.5))
    for i in range(3):
        out += H.barrel("sy_br%d" % i, Ts(-hw + 2.0, -hd + 1.6 + i * 0.8, 0), 0.30,
                        0.86, wood, iron)
    out += H.lantern_post("sy_lamp", Ts(-hw + 1.4, hd - 1.4, 0), 3.4, iron, P["glow"])
    return out


# ==========================================================================
# 5.  bathhouse   (23 x 19 nominal, brief 20-26 x 16-22)
# ==========================================================================
def bathhouse(MAT, rng, w=23.0, d=19.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    stone, st_w, st_t, st_d = P["stone"], P["stone_warm"], P["stone_trim"], P["stone_dark"]
    wood, dark = P["wood"], P["wood_dark"]
    iron, tile = P["iron"], P["tile"]
    water, canvas, linen = P["ty_water"], P["ty_canvas"], P["ty_linen"]
    glass, void, plaster = P["glass"], P["void"], P["plaster"]
    out = []

    # ---- terrace ---------------------------------------------------------
    out.append(_cobble_apron("ba_terr", Ts(0, 0, 0), w - 0.8, d - 0.8, P["ty_paving"],
                            0.100))
    out.append(HP.boxmesh("ba_kerb", [
        (Ts(0, hd - 0.4, 0.16), (w - 0.8, 0.36, 0.13)),
        (Ts(0, -hd + 0.4, 0.16), (w - 0.8, 0.36, 0.13))], st_d, bev=0.01))

    # ---- the hall, drum and dome ----------------------------------------
    hw2, hd2 = 6.5, 5.0
    hx, hy = -2.6, -1.4
    pl_h = 0.34
    fh = 4.10
    out += HP.plinth("ba_pl", Ts(hx, hy, 0), 2 * hw2, 2 * hd2, pl_h, st_w,
                     moss=P["moss"], rng=rng)
    wins = [(-4.2, 1.20, 2.30), (-1.6, 1.20, 2.30), (1.6, 1.20, 2.30),
            (4.2, 1.20, 2.30)]
    ops = []
    for (x, ww, zz) in wins:
        if abs(x) > hw2 - 1.4:
            continue
        ops.append((x, ww, zz, 1.35))
    out += _wall("ba_fw", Ts(hx, hy, pl_h), 2 * hw2, fh, 0.48, ops, st_w,
                 y=hd2 - 0.48)
    for (x, ww, zz) in wins:
        if abs(x) > hw2 - 1.4:
            continue
        out += HP.window("ba_ww%d" % int(x * 10), Ts(hx + x, hy + hd2, pl_h + zz), ww,
                         1.35, frame=st_d, glass=glass, wall_mat=st_w, arch="round",
                         sill=True, trim=st_t, reveal=st_t, bars=(1, 1), deep=0.22,
                         rng=rng)
    # door in the middle of the front
    out.append(K.box("ba_dk", Ts(hx, hy + hd2 - 0.12, pl_h + 1.35), (2.0, 0.12, 2.7),
                     void))
    out += HP.door("ba_dr", Ts(hx, hy + hd2, pl_h), w=1.95, h=2.66, wood=dark,
                   iron=iron, stone=st_d, steps=1, arch=True, double=True, rng=rng)
    for sx in (-1, 1):
        TT = Ts(hx + sx * hw2, hy, 0, rz=D2R(-90 * sx))
        out += _wall("ba_sw%d" % sx, TT @ Ts(0, 0, pl_h), 2 * hd2, fh, 0.48,
                     [(-2.5, 1.05, 2.35, 1.20), (2.5, 1.05, 2.35, 1.20)], st_w,
                     y=-0.48)
        for u in (-2.5, 2.5):
            out += HP.window("ba_sww%d%d" % (sx, int(u * 10)),
                             TT @ Ts(u, -0.48, pl_h + 2.35), 1.05, 1.20, frame=st_d,
                             glass=glass, wall_mat=st_w, arch="seg", sill=True,
                             trim=st_t, reveal=st_t, deep=0.20, rng=rng)
    out += _wall("ba_bw", Ts(hx, hy, pl_h, rz=math.pi), 2 * hw2, fh, 0.48,
                 [(-3.4, 1.05, 2.35, 1.20), (3.4, 1.05, 2.35, 1.20)], st_w,
                 y=-hd2)
    # ---- flat roof terrace + lead dome -----------------------------------
    # A tiled gable over the hall made a 5 m red slab that read as a barn with a
    # tent on it. A bathhouse is a low stone box with a parapet terrace and a
    # lead dome growing out of it - that silhouette is the whole point.
    z_r = pl_h + fh
    out.append(K.box("ba_cor", Ts(hx, hy, z_r), (2 * hw2 + 0.5, 2 * hd2 + 0.5, 0.26),
                     st_d, bev=0.012))
    out.append(K.box("ba_pav", Ts(hx, hy, z_r + 0.20), (2 * hw2 - 0.3, 2 * hd2 - 0.3,
                                                        0.14), P["ty_paving"]))
    par, cop = [], []
    for dx, dy, px, py in ((0, hd2, 2 * hw2 + 0.4, 0.46),
                           (0, -hd2, 2 * hw2 + 0.4, 0.46),
                           (hw2, 0, 0.46, 2 * hd2 + 0.4),
                           (-hw2, 0, 0.46, 2 * hd2 + 0.4)):
        par.append((Ts(hx + dx, hy + dy, z_r + 0.67), (px, py, 0.68)))
        cop.append((Ts(hx + dx, hy + dy, z_r + 1.06), (px + 0.10, py + 0.10, 0.12)))
    out.append(HP.boxmesh("ba_par", par, st_w, bev=0.01))
    out.append(HP.boxmesh("ba_parc", cop, st_t, bev=0.008))
    z_d = z_r + 0.27
    out.append(K.cyl("ba_drum", Ts(hx, hy, z_d + 0.48), 3.78, 0.96, st_w, seg=28))
    out.append(K.cyl("ba_drum2", Ts(hx, hy, z_d + 0.99), 3.92, 0.14, st_d, seg=28))
    out += _domed_roof("ba_dome", Ts(hx, hy, z_d + 1.06), 3.52, 1.62,
                       P.get("lead", st_d))
    # lantern at the apex, then the hot-air column: the thing that says
    # "bathhouse" from across the street
    z_l = z_d + 2.68
    out.append(K.cyl("ba_lp", Ts(hx, hy, z_l + 0.30), 0.56, 0.62, st_w, seg=12))
    out.append(K.cyl("ba_lp2", Ts(hx, hy, z_l + 0.64), 0.70, 0.14, st_d, seg=12))
    for k in range(6):
        a = TAU * k / 6.0
        out.append(K.box("ba_pp%d" % k,
                         Ts(hx + math.cos(a) * 0.48, hy + math.sin(a) * 0.48,
                            z_l + 0.92), (0.10, 0.10, 0.60), st_w))
    out.append(K.cone("ba_lpc", Ts(hx, hy, z_l + 1.42), 0.78, 0.54, P.get("lead", st_d),
                      seg=12))
    for k, (rr, zz) in enumerate(((0.40, 0.9), (0.29, 1.6), (0.19, 2.2))):
        out.append(K.cyl("ba_stm%d" % k, Ts(hx, hy, z_l + 1.7 + zz), rr, 0.8,
                         P["ty_canvas"], seg=10))

    # ---- porch, awning, basin -------------------------------------------
    # the porch hangs off the real wall plane (hy + hd2), not off hd2 - the old
    # value left a 2.3 m gap that read as a floating roof
    porch_w = 8.0
    pcy = hy + hd2 + 1.72
    for i in range(4):
        x = hx - porch_w * 0.5 + i * porch_w / 3.0
        out.append(K.cyl("ba_col%d" % i, Ts(x, pcy + 1.52, pl_h + 1.65), 0.26, 3.3,
                         st_w, seg=10))
        out.append(K.box("ba_colb%d" % i, Ts(x, pcy + 1.52, 0.22), (0.62, 0.62, 0.44),
                         st_d, bev=0.012))
        out.append(K.box("ba_colc%d" % i, Ts(x, pcy + 1.52, pl_h + 3.42),
                         (0.50, 0.50, 0.16), st_d, bev=0.01))
    out.append(K.box("ba_ent", Ts(hx, pcy + 0.74, pl_h + 3.70), (porch_w + 0.9, 1.05,
                                                                 0.44), st_t, bev=0.014))
    rp, _i = HP.roof("ba_pr", Ts(hx, pcy, 0, rz=D2R(90)), 3.44, porch_w + 1.0,
                     pl_h + 3.94, 26.0, tile, dark, st_t, ov_v=0.30, ov_g=0.34,
                     moss=0.20, rng=rng)
    out += rp
    awx = hx + hw2 + 2.6
    aw = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            aw.append((Ts(awx + sx * 2.5, 4.4 + sy * 2.05, 2.55),
                       (0.11, 0.11, 2.2)))
    out.append(HP.boxmesh("ba_awp", aw, wood, bev=0.004))
    out.append(K.box("ba_aw", Ts(awx, 4.4, 3.62), (5.4, 4.5, 0.05), canvas, bev=0.01))
    out.append(K.box("ba_awv", Ts(awx, 4.4 + 2.2, 3.44), (5.4, 0.05, 0.32), linen))
    for i in range(2):
        out += H.barrel("ba_bn%d" % i, Ts(hx + 4.4 + i * 0.8, 2.2, 0), 0.30, 0.80,
                        wood, iron)
    out += _pool("ba_pool", Ts(awx, 3.4, 0), 4.4, 2.9, st_w, water, st_d)
    out.append(K.cyl("ba_spout", Ts(awx + 2.1, 5.3, 0.95, rz=D2R(90)), 0.08, 1.1,
                     P["ty_bronze"], seg=8))
    out.append(K.sphere("ba_lion", Ts(awx + 2.1, 5.5, 1.05), 0.20, st_d, seg=8, ring=6,
                        squash=0.9))

    # ---- apodyterium wing ------------------------------------------------
    wx, wy = 6.6, -5.6
    ww2, wd2 = 2.75, 2.75
    out += HP.plinth("ba_wpl", Ts(wx, wy, 0), 2 * ww2, 2 * wd2, 0.26, st_w, rng=rng)
    out += _wall("ba_wwall", Ts(wx, wy, 0.26), 2 * ww2, 3.05, 0.40,
                 [(0.0, 1.15, 0.0, 2.05)], plaster, y=wd2 - 0.40)
    out += HP.door("ba_wdoor", Ts(wx, wy + wd2, 0.26), w=1.12, h=2.02, wood=dark,
                   iron=iron, stone=st_d, steps=1, arch=None, rng=rng)
    for sx in (-1, 1):
        TT = Ts(wx + sx * ww2, wy, 0, rz=D2R(-90 * sx))
        out += _wall("ba_wsw%d" % sx, TT @ Ts(0, 0, 0.26), 2 * wd2, 3.05, 0.38,
                     [(-1.5, 0.85, 1.55, 1.05)], st_w, y=-0.38)
    out += _wall("ba_wbw", Ts(wx, wy, 0.26, rz=math.pi), 2 * ww2, 3.05, 0.38, [], st_w,
                 y=-wd2)
    out.append(K.box("ba_wcor", Ts(wx, wy, 3.42), (2 * ww2 + 0.42, 2 * wd2 + 0.42,
                                                   0.22), st_d, bev=0.012))
    rp2, _i2 = HP.roof("ba_wr", Ts(wx, wy, 0, rz=D2R(90)), 2 * wd2, 2 * ww2, 3.53,
                       22.0, tile, dark, st_w, ov_v=0.32, ov_g=0.36, moss=0.25,
                       rng=rng)
    out += rp2
    for i in range(3):
        out.append(K.box("ba_ben%d" % i, Ts(wx - 1.5 + i * 1.5, wy + 0.4, 0.72),
                         (0.42, 1.9, 0.10), wood, bev=0.008))
        out.append(K.box("ba_benl%d" % i, Ts(wx - 1.5 + i * 1.5, wy + 0.4, 0.36),
                         (0.34, 1.7, 0.72), dark))
    out += H.lantern_post("ba_lamp", Ts(wx - ww2 - 1.1, wy + wd2 - 0.4, 0), 3.2, iron,
                          P["glow"])
    # towel rail
    out.append(K.box("ba_towel", Ts(hx + 3.6, 5.6, 1.62), (3.0, 0.10, 0.10), wood))
    for i in range(3):
        out.append(K.box("ba_tw%d" % i, Ts(hx + 2.4 + i * 1.2, 5.60, 1.28),
                         (0.55, 0.06, 0.66), linen))
    return out


# ==========================================================================
# 6.  mill   (14 x 14 nominal, brief 12-16 x 12-16)
# ==========================================================================
def mill(MAT, rng, w=14.0, d=14.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    stone, st_w, st_t, st_d = P["stone"], P["stone_warm"], P["stone_trim"], P["stone_dark"]
    wood, dark, pale = P["wood"], P["wood_dark"], P["ty_wood_pale"]
    iron, tile, water = P["iron"], P["tile"], P["ty_water"]
    glass, void, linen, hay = P["glass"], P["void"], P["ty_linen"], P["ty_hay"]
    out = []

    # ---- yard + race -----------------------------------------------------
    out.append(_cobble_apron("ml_ground", Ts(0, 0, 0), w - 0.6, d - 0.6, P["ty_dirt"],
                             0.100))
    rx0, rx1 = -hw + 0.1, -hw + 2.0            # the race channel, along Y
    rcx = (rx0 + rx1) * 0.5
    out.append(K.box("ml_bed", Ts(rcx, 0, 0.06), (rx1 - rx0, d - 1.0, 0.10), st_d,
                     bev=0.0))
    out.append(K.box("ml_water", Ts(rcx, 0, 0.28), (rx1 - rx0 - 0.1, d - 1.4, 0.04),
                     water))
    for sx in (-1, 1):
        x = rx1 if sx > 0 else rx0
        specs = []
        n = 9
        for i in range(n):
            y = -hd + 0.7 + i * (d - 1.4) / (n - 1)
            specs.append((Ts(x, y, 0.62), (0.42, (d - 1.4) / (n - 1) * 1.02, 1.24)))
        out.append(HP.boxmesh("ml_rw%d" % sx, specs, st_w, bev=0.014))
    # sluice gate upstream (+Y)
    out.append(K.box("ml_sgf", Ts(rcx, hd - 0.9, 1.35), (rx1 - rx0 + 0.9, 0.28, 2.3),
                     st_d, bev=0.012))
    for i in range(3):
        out.append(K.box("ml_sgp%d" % i, Ts(rcx, hd - 0.75, 0.55 + i * 0.45),
                         (rx1 - rx0 - 0.15, 0.14, 0.40), dark))
    out.append(K.cyl("ml_sgs", Ts(rcx, hd - 0.75, 2.15), 0.07, 1.2, iron, seg=8))
    out.append(K.cyl("ml_sgw", Ts(rcx, hd - 0.75, 2.78, rx=D2R(90)), 0.34, 0.10, iron,
                     seg=10))

    # ---- mill house ------------------------------------------------------
    # pushed to +X so the race and the wheel sit clear of the west wall: at
    # mx -1.0 the house overlapped its own water channel by 1.6 m.
    mw, md = 7.4, 7.0
    mx, my = 1.0, 0.4
    pl_h = 0.32
    fh1, fh2 = 3.10, 2.50
    eave = pl_h + fh1 + fh2
    out += HP.plinth("ml_pl", Ts(mx, my, 0), mw, md, pl_h, st_w, moss=P["moss"],
                     rng=rng)
    gops = [(-1.9, 1.25, 0, 2.20)]
    out += _wall("ml_gw", Ts(mx, my, pl_h), mw, fh1, 0.44, gops, st_w,
                 y=md * 0.5 - 0.44)
    out += HP.door("ml_dr", Ts(mx - 1.9, my + md * 0.5, pl_h), w=1.18, h=2.16,
                   wood=dark, iron=iron, stone=st_d, steps=1, arch=True, rng=rng)
    uops = [(x, 0.95, 0.72, 1.20) for x in (-2.0, 0.0, 2.0)]
    out += _wall("ml_uw", Ts(mx, my, pl_h + fh1), mw, fh2, 0.44, uops, P["plaster"],
                 y=md * 0.5 - 0.44)
    for i, x in enumerate((-2.0, 0.0, 2.0)):
        out += HP.window("ml_win%d" % i, Ts(mx + x, my + md * 0.5, pl_h + fh1 + 0.72),
                         0.95, 1.20, frame=dark, glass=glass, wall_mat=P["plaster"],
                         sill=True, trim=st_t, shutters=wood, deep=0.18, rng=rng)
    out += HP.timber_frame("ml_tf", Ts(mx, my, pl_h + fh1), mw, fh2, dark,
                           ops=[(x - 0.60, x + 0.60) for x in (-2.0, 0.0, 2.0)],
                           y=md * 0.5 + 0.015, stud=1.0, rng=rng)
    for sx in (-1, 1):
        TT = Ts(mx + sx * mw * 0.5, my, 0, rz=D2R(-90 * sx))
        out += _wall("ml_sw%d" % sx, TT, md, eave, 0.44,
                     [(-1.6, 1.0, 1.55, 1.30), (1.6, 0.55, 3.90, 0.50)], st_w, y=-0.44)
        out += HP.window("ml_sww%d" % sx, TT @ Ts(-1.6, -0.44, 1.55), 1.0, 1.30,
                         frame=st_d, glass=glass, wall_mat=st_w, arch="seg", sill=True,
                         trim=st_t, reveal=st_t, deep=0.20, rng=rng)
    out += _wall("ml_bw", Ts(mx, my, 0, rz=math.pi), mw, eave, 0.44, [], st_w,
                 y=-md * 0.5)
    rp, info = HP.roof("ml_rf", Ts(mx, my, 0, rz=D2R(90)), md, mw, eave, 44.0, tile,
                       dark, st_w, ov_v=0.42, ov_g=0.50, moss=0.40, rng=rng)
    out += rp
    # gable hoist: beam, pulley, rope, sack
    gy = md * 0.5
    out.append(K.box("ml_beam", Ts(mx, my + gy + 1.05, eave + 1.55), (0.24, 2.5, 0.24),
                     dark, bev=0.012))
    out.append(K.cyl("ml_pul", Ts(mx, my + gy + 2.05, eave + 1.30, rx=D2R(90)), 0.22,
                     0.12, iron, seg=10))
    out.append(K.cyl("ml_rope", Ts(mx, my + gy + 2.05, eave + 0.25), 0.028, 2.1, linen,
                     seg=5))
    out.append(K.sphere("ml_sack", Ts(mx, my + gy + 2.05, eave - 0.95), 0.32, linen,
                        seg=9, ring=6, squash=1.1))
    out.append(K.box("ml_sdoor", Ts(mx, my + gy - 0.06, eave - 0.55),
                     (1.9, 0.10, 1.85), void))
    for sx in (-1, 1):
        out.append(K.box("ml_sdj%d" % sx, Ts(mx + sx * 0.95, my + gy - 0.02,
                                             eave - 0.55), (0.14, 0.14, 1.95), dark))

    # ---- the wheel -------------------------------------------------------
    # hangs off the west wall (mx - mw/2 = -2.7) and dips into the race
    wx = -4.20
    wr = 2.95
    wz = 3.05
    out.append(K.cyl("ml_axle", Ts(wx, my, wz, ry=D2R(90)), 0.19, 2.6, iron, seg=10))
    for sx in (-1, 1):
        out.append(HP.torus("ml_rim%d" % sx, Ts(wx + sx * 0.62, my, wz, ry=D2R(90)),
                            wr, 0.14, wood, nseg=10, nring=5))
    spokes = []
    for k in range(10):
        a = TAU * k / 10.0
        for sx in (-1, 1):
            p0 = (wx + sx * 0.62, my + math.cos(a) * 0.22, wz + math.sin(a) * 0.22)
            p1 = (wx + sx * 0.62, my + math.cos(a) * wr * 0.98,
                  wz + math.sin(a) * wr * 0.98)
            spokes.append((Ts((p0[0]), 0, 0), p0, p1))
    for i, (T0, p0, p1) in enumerate(spokes):
        b = HP.bar("ml_spoke%02d" % i, Matrix.Identity(4), p0, p1, 0.10, wood, wide=0.09)
        if b is not None:
            out.append(b)
    pads = []
    for k in range(10):
        a = TAU * k / 10.0
        for sx in (-1, 1):
            pads.append((Ts(wx + sx * 1.28, my + math.cos(a) * wr,
                            wz + math.sin(a) * wr, rx=-a), (0.10, 0.34, 0.72)))
    out.append(HP.boxmesh("ml_pad", pads, pale, bev=0.006))

    # ---- yard props ------------------------------------------------------
    out += _cart_shed("ml_lt", Ts(hw - 3.4, hd - 3.0, 0), 4.4, 3.4, 2.30, pale, dark,
                      tile, dark)
    out += _sacks("ml_sacks", Ts(hw - 3.6, hd - 2.6, 0), 5, linen, rng, 0.7)
    out += H.cart("ml_cart", Ts(hw - 3.0, hd - 6.4, 0), dark, iron, 2.2, 1.1)
    for i in range(2):
        out += H.barrel("ml_bar%d" % i, Ts(hw - 1.4, 1.0 + i * 0.8, 0), 0.31, 0.90,
                        wood, iron)
    out += H.haystack("ml_hay", Ts(hw - 2.0, -hd + 2.0, 0), 1.0, 1.5, hay)
    out += H.lantern_post("ml_lamp", Ts(hw - 1.2, hd - 1.2, 0), 3.2, iron, P["glow"])
    return out


# ==========================================================================
# 7.  chapel_small   (14 x 23 nominal, brief 12-16 x 20-26)
# ==========================================================================
def chapel_small(MAT, rng, w=14.0, d=23.0):
    P = palette(MAT)
    P_tile_tmp[0] = P["tile"]
    hw, hd = w * 0.5, d * 0.5
    stone, st_w, st_t, st_d = P["stone"], P["stone_warm"], P["stone_trim"], P["stone_dark"]
    wood, dark = P["wood"], P["wood_dark"]
    iron, tile, glass = P["iron"], P["tile"], P["glass"]
    out = []

    # ---- nave ------------------------------------------------------------
    # 9 x 11.5 nave + 4.6 lower chancel: two roof masses instead of one 15 m
    # slab, which is what made the first version read as a barn.
    nw, nd = 9.0, 11.5
    nx, ny = -w * 0.5 + nw * 0.5 + 0.35, -hd + 4.75 + nd * 0.5
    pl_h = 0.30
    fh = 5.95
    out.append(_cobble_apron("ch_gnd", Ts(nx, ny, 0), nw + 1.4, nd + 2.4,
                             P["ty_paving"], 0.098))
    out += HP.plinth("ch_pl", Ts(nx, ny, 0), nw, nd, pl_h, st_w, moss=P["moss"], rng=rng)
    lops = [(y, 1.05, 2.05, 2.55) for y in (-3.9, 0.0, 3.9)]
    for sx in (-1, 1):
        TT = Ts(nx + sx * nw * 0.5, ny, 0, rz=D2R(-90 * sx))
        out += _wall("ch_sw%d" % sx, TT @ Ts(0, 0, pl_h), nd, fh, 0.48, lops, st_w,
                     y=-0.48)
        for i, u in enumerate((-3.9, 0.0, 3.9)):
            out += HP.window("ch_lw%d%d" % (sx, i), TT @ Ts(u, -0.48, pl_h + 2.05),
                             1.05, 2.55, frame=st_d, glass=glass, wall_mat=st_w,
                             arch="round", sill=True, trim=st_t, reveal=st_t,
                             bars=(1, 1), deep=0.26, rng=rng)
        for k, u in enumerate((-5.0, -2.5, 0.0, 2.5, 5.0)):
            M = TT @ Ts(u, 0, 0) @ Matrix.Rotation(D2R(-90 * sx), 4, "Z")
            out += _buttress("ch_bt%d%d" % (sx, k), TT @ Ts(u, 0.0, 0), fh * 0.86,
                             0.62, st_w, st_d)
    # front (south) gable wall + portal + rose
    out += _wall("ch_fw", Ts(nx, ny, pl_h), nw, fh, 0.50,
                 [(0.0, 2.0, 0.0, 3.05)], st_w, y=nd * 0.5 - 0.50)
    out.append(K.box("ch_pdk", Ts(nx, ny + nd * 0.5 - 0.20, pl_h + 1.55),
                     (1.96, 0.14, 3.0), P["void"]))
    out += HP.door("ch_dr", Ts(nx, ny + nd * 0.5, pl_h), w=1.9, h=2.95, wood=dark,
                   iron=iron, stone=st_d, steps=2, arch=True, double=True, rng=rng)
    out.append(K.box("ch_rose_dk", Ts(nx, ny + nd * 0.5 - 0.10, pl_h + 4.55),
                     (2.3, 0.16, 2.3), P["void"]))
    out += H.rose_window("ch_rose", Ts(nx, ny + nd * 0.5, pl_h + 4.55), 1.12, st_d,
                         glass, lobes=10, depth=0.44, seg=28)
    out += _wall("ch_bw", Ts(nx, ny, pl_h, rz=math.pi), nw, fh, 0.50, [], st_w,
                 y=-nd * 0.5)
    rp, info = HP.roof("ch_rf", Ts(nx, ny, 0), nw, nd, pl_h + fh, 46.0, tile, dark,
                       st_w, ov_v=0.44, ov_g=0.52, moss=0.55, rng=rng)
    out += rp

    # ---- chancel: lower box butting the nave's back wall ------------------
    cw, cd = 7.2, 4.6
    cx = nx
    cy = ny - nd * 0.5 - cd * 0.5 + 0.10
    cfh = 4.15
    out += HP.plinth("ch_cpl", Ts(cx, cy, 0), cw, cd, pl_h, st_w, moss=P["moss"],
                     rng=rng)
    cops = [(0.0, 1.15, 1.95, 2.25)]
    for sx in (-1, 1):
        TT = Ts(cx + sx * cw * 0.5, cy, 0, rz=D2R(-90 * sx))
        out += _wall("ch_csw%d" % sx, TT @ Ts(0, 0, pl_h), cd, cfh, 0.48, cops, st_w,
                     y=-0.48)
        out += HP.window("ch_cw%d" % sx, TT @ Ts(0.0, -0.48, pl_h + 1.95), 1.15,
                         2.25, frame=st_d, glass=glass, wall_mat=st_w, arch="round",
                         sill=True, trim=st_t, reveal=st_t, bars=(1, 1), deep=0.26,
                         rng=rng)
    # east (rear) wall: one big lancet - the light the altar wants
    out += _wall("ch_cew", Ts(cx, cy, pl_h, rz=math.pi), cw, cfh, 0.50,
                 [(0.0, 1.35, 1.75, 2.55)], st_w, y=-cd * 0.5)
    out += HP.window("ch_cewin", Ts(cx, cy - cd * 0.5, pl_h + 1.75), 1.35, 2.55,
                     frame=st_d, glass=glass, wall_mat=st_w, arch="round", sill=True,
                     trim=st_t, reveal=st_t, bars=(1, 2), deep=0.28, rng=rng)
    rpc, _ic = HP.roof("ch_crf", Ts(cx, cy, 0), cw, cd + 0.2, pl_h + cfh, 38.0, tile,
                       dark, st_w, ov_v=0.40, ov_g=0.42, moss=0.45, rng=rng)
    out += rpc
    # bell cote on the front gable
    bx, by = nx, ny + nd * 0.5 - 0.30
    bz = pl_h + fh + 1.95
    for sx in (-1, 1):
        out.append(K.box("ch_bcp%d" % sx, Ts(bx + sx * 0.62, by, bz + 0.95),
                         (0.34, 0.62, 1.9), st_w, bev=0.012))
    out += _arch("ch_bca", Ts(bx, by, bz + 1.90), 0.45, 0.0, st_w, None, n=7, band=0.22,
                 thick=0.62)
    out.append(K.box("ch_bcr", Ts(bx, by, bz + 2.62), (1.72, 0.72, 0.20), st_d,
                     bev=0.012))
    out += _bell("ch_bell", Ts(bx, by, bz + 1.28), dark, P["ty_bronze"], 0.28, 0.5)
    out.append(K.box("ch_cross_v", Ts(bx, by, bz + 3.25), (0.12, 0.12, 1.05), st_d,
                     bev=0.006))
    out.append(K.box("ch_cross_h", Ts(bx, by, bz + 3.52), (0.62, 0.12, 0.12), st_d,
                     bev=0.006))
    # porch
    px, py = nx, ny + nd * 0.5 + 1.35
    out += HP.plinth("ch_ppl", Ts(px, py, 0), 3.4, 2.7, 0.22, st_w, rng=rng)
    for sx in (-1, 1):
        out.append(K.box("ch_pp%d" % sx, Ts(px + sx * 1.45, py + 0.9, 1.55),
                         (0.30, 0.30, 3.1), st_w, bev=0.012))
        out.append(K.box("ch_ps%d" % sx, Ts(px + sx * 1.45, py - 0.95, 1.55),
                         (0.30, 0.30, 3.1), st_w, bev=0.012))
    rp2, _i2 = HP.roof("ch_pr", Ts(px, py, 0, rz=D2R(0)), 3.5, 3.0, 3.10, 44.0, tile,
                       dark, st_w, ov_v=0.24, ov_g=0.28, moss=0.20, rng=rng)
    out += rp2
    out.append(K.box("ch_pdk2", Ts(px, py + 1.28, 1.30), (1.95, 0.10, 2.6), P["void"]))

    # ---- graveyard -------------------------------------------------------
    gx0, gx1 = nx + nw * 0.5 + 0.35, hw - 0.6
    gy0, gy1 = -hd + 1.5, hd - 1.3
    gcx, gcy = (gx0 + gx1) * 0.5, (gy0 + gy1) * 0.5
    gwd, gdd = gx1 - gx0, gy1 - gy0
    out.append(_cobble_apron("ch_gvy", Ts(gcx, gcy, 0), gwd, gdd, P["ty_grass"],
                             0.104))
    for (nm, T, ln) in (("n", Ts(gcx, gy1, 0), gwd),
                        ("s", Ts(gcx, gy0, 0), gwd),
                        ("e", Ts(gx1, gcy, 0, rz=D2R(90)), gdd)):
        out += _wall("ch_gw_" + nm, T, ln, 0.95, 0.36, [], st_w, y=-0.36)
        out.append(K.box("ch_gwc_" + nm, T @ Ts(0, -0.36 + 0.18, 0.98),
                         (ln + 0.18, 0.48, 0.12), st_t, bev=0.01))
    # lych gate on the north side
    out.append(K.box("ch_lp1", Ts(gcx - 0.85, gy1, 1.15), (0.24, 0.30, 2.3), dark,
                     bev=0.008))
    out.append(K.box("ch_lp2", Ts(gcx + 0.85, gy1, 1.15), (0.24, 0.30, 2.3), dark,
                     bev=0.008))
    out.append(K.box("ch_lr", Ts(gcx, gy1, 2.36), (2.5, 0.62, 0.14), dark, bev=0.008))
    out.append(K.box("ch_lr2", Ts(gcx, gy1, 2.58), (2.1, 0.46, 0.10), tile, bev=0.008))
    # headstones: three columns turned to face +X (east) - 15 of them, so the
    # churchyard reads as a churchyard and not as a strip of dirt
    for i in range(5):
        for j in range(3):
            hx = gx0 + 0.72 + j * 1.10 + rng.uniform(-0.10, 0.10)
            hy = gy0 + 1.9 + i * (gdd - 3.8) / 4.0 + rng.uniform(-0.16, 0.16)
            out += _headstone("ch_hs%d_%d" % (i, j), Ts(hx, hy, 0.105, rz=D2R(90)),
                              0.50 + rng.uniform(-0.06, 0.10),
                              0.76 + rng.uniform(-0.10, 0.28),
                              st_t if (i + j) % 3 else st_w, rng)
    for i in range(2):
        cx2 = gx0 + 1.5 + i * 1.9
        cy2 = gy0 + 2.1 + i * (gdd - 4.0)
        out.append(K.box("ch_cr%d" % i, Ts(cx2, cy2, 0.75), (0.10, 0.10, 1.15), dark,
                         bev=0.006))
        out.append(K.box("ch_crh%d" % i, Ts(cx2, cy2, 1.02), (0.46, 0.10, 0.10), dark,
                         bev=0.006))
    for i in range(2):
        out.append(K.sphere("ch_yew%d" % i, Ts(gx0 + 0.7 + i * (gwd - 1.4),
                                               gy0 + 1.0 if i == 0 else gy1 - 1.4,
                                               0.85), 0.85, P["ty_leaf"], seg=10,
                            ring=7, squash=1.25))
    out.append(K.box("ch_gbench", Ts(gcx, gy0 + 0.9, 0.52), (1.9, 0.44, 0.10), st_t,
                     bev=0.01))
    for sx in (-1, 1):
        out.append(K.box("ch_gben%d" % sx, Ts(gcx + sx * 0.75, gy0 + 0.9, 0.26),
                         (0.18, 0.40, 0.52), st_w))
    return out


def _buttress(name, T, h, depth, mat, cap=None, stages=3):
    """Stepped buttress against a wall at T, projecting +Y."""
    out = []
    specs = []
    for i in range(stages):
        z0 = h * i / stages
        z1 = h * (i + 1) / stages
        dd = depth * (1.0 - 0.22 * i)
        specs.append((T @ Ts(0, dd * 0.5, (z0 + z1) * 0.5), (0.62, dd, z1 - z0)))
    out.append(HP.boxmesh(name, specs, mat, bev=0.012))
    if cap is not None:
        out.append(K.box(name + "_c", T @ Ts(0, depth * 0.34, h + 0.05),
                         (0.70, depth * 0.78, 0.16), cap, bev=0.01))
    return out


# ==========================================================================
# 8.  public entry points
# ==========================================================================
FOOT = {
    "training_ground": (52.0, 40.0, 8.4),
    "barracks": (34.0, 22.0, 16.0),
    "stable_yard": (30.0, 21.0, 10.5),
    "bathhouse": (23.0, 19.0, 9.8),
    "mill": (14.0, 14.0, 10.6),
    "chapel_small": (14.0, 23.0, 13.2),
}

#: (min, max) footprint per axis, straight out of Docs/BRIEF_TYPES.md
LIMITS = {
    "training_ground": ((46.0, 60.0), (34.0, 46.0)),
    "barracks": ((30.0, 40.0), (18.0, 26.0)),
    "stable_yard": ((26.0, 34.0), (18.0, 24.0)),
    "bathhouse": ((20.0, 26.0), (16.0, 22.0)),
    "mill": ((12.0, 16.0), (12.0, 16.0)),
    "chapel_small": ((12.0, 16.0), (20.0, 26.0)),
}

ORDER = ("training_ground", "barracks", "stable_yard", "bathhouse", "mill",
         "chapel_small")

_MAKERS = {
    "training_ground": training_ground,
    "barracks": barracks,
    "stable_yard": stable_yard,
    "bathhouse": bathhouse,
    "mill": mill,
    "chapel_small": chapel_small,
}


def kinds():
    return list(ORDER)


def footprint(kind):
    return FOOT[kind]


def _dims(kind, w=None, d=None):
    """Clamp a requested size into the brief's range."""
    (lo_w, hi_w), (lo_d, hi_d) = LIMITS[kind]
    fw, fd = FOOT[kind][0], FOOT[kind][1]
    ww = fw if w is None else max(lo_w, min(hi_w, float(w)))
    dd = fd if d is None else max(lo_d, min(hi_d, float(d)))
    return ww, dd


def build(kind, MAT=None, rng=None, at=None, rz=0.0, x=0.0, y=0.0, rot=None,
          z=0.0, w=None, d=None, **kw):
    """Build one type; returns linked MESH objects already in WORLD space.

    kind   one of `kinds()`
    MAT    the city material dict (capital_hd_glue house_mats output); merged
           with this module's palette, never mutated
    at     (x, y, z) - overrides x / y / z
    rot    yaw in RADIANS (what capital.py carries as p["yaw"])
    rz     yaw in DEGREES (hd_shops.build compatibility); ignored when rot given
    """
    if kind not in _MAKERS:
        raise KeyError("hd_types: unknown kind %r (have %s)" % (kind, ", ".join(ORDER)))
    r = random.Random(7) if rng is None else rng
    ww, dd = _dims(kind, w, d)
    parts = _flat(_MAKERS[kind](MAT, r, ww, dd, **kw))
    ax = float(at[0]) if at else float(x)
    ay = float(at[1]) if at else float(y)
    az = float(at[2]) if at else float(z)
    ang = D2R(float(rz)) if rot is None else float(rot)
    if ax or ay or az or abs(ang) > 1e-9:
        H.apply(parts, Ts(ax, ay, az, rz=ang))
    return parts


def _shim(kind):
    """BUILDERS[kind]: accepts (kind, MAT, rng, ...) or (MAT, rng, ...)."""
    def fn(*a, **kw):
        if a and isinstance(a[0], str):
            a = a[1:]
        return build(kind, *a, **kw)
    fn.__name__ = "build_" + kind
    fn.__doc__ = build.__doc__
    return fn


BUILDERS = dict((k, _shim(k)) for k in ORDER)


def types(kind, MAT, rng, x=0.0, y=0.0, rot=0.0, z=0.0, **kw):
    """capital_hd_glue.types() body: the exact shape of glue.shop()."""
    return build(kind, MAT, rng, x=x, y=y, rot=rot, z=z, **kw)


def type_mats(MAT):
    """Palette for the glue (merge once per build, like shop_mats())."""
    return palette(MAT)


def selftest(MAT=None, seed=7):
    """Build all six at the origin and print sizes - used by look/types_lab.py."""
    MAT = dict(MAT or {})
    rows = []
    for k in ORDER:
        rng = random.Random(seed + 17)
        parts = build(k, MAT, rng, 0.0, 0.0, 0.0)
        lo, hi = H.bbox(parts)
        rows.append((k, len(parts), H.tri_count(parts), hi.x - lo.x, hi.y - lo.y,
                     hi.z - lo.z))
        for ob in list(parts):
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
            except Exception:
                pass
    print("[types] kind              objs    tris    w      d      h", flush=True)
    for (k, n, t, w, d, h) in rows:
        print("[types] %-16s %5d %8d  %5.1f  %5.1f  %5.1f" % (k, n, t, w, d, h),
              flush=True)
    return rows


# ==========================================================================
# 9.  placement
# ==========================================================================
#: district -> allowed (the brief's list, plus the neighbours that read the same)
DISTRICT_OK = {
    "training_ground": ("palace", "guild", "outer", "craft"),
    "barracks": ("palace", "guild", "outer"),
    "stable_yard": ("dock", "craft", "outer"),
    "bathhouse": ("residential", "guild", "craft", "artisan"),
    "mill": ("outer", "craft", "dock"),
    "chapel_small": ("palace", "guild", "temple", "residential", "craft", "artisan",
                     "outer", "dock", "ward"),
}

#: how many of each the city gets at share = 0.055
QUOTA = {
    "training_ground": 2,
    "barracks": 3,
    "stable_yard": 4,
    "bathhouse": 3,
    "mill": 4,
    "chapel_small": 5,
}

#: where a type belongs radially: 1 = wall/gate ring, 0 = the core.  Used to
#: score block sites; the brief asks for military ground in the outer ring and
#: guild quarter, the bathhouse in the inner city, the mill by the water gates.
RADIAL = {
    "training_ground": 0.86,
    "barracks": 0.80,
    "stable_yard": 0.80,
    "bathhouse": 0.38,
    "mill": 0.74,
    "chapel_small": 0.55,
}

#: district preference weight (lower = better) when scoring a block site
_ROLE_RANK = {"palace": 0, "guild": 1, "ward": 2, "temple": 2, "craft": 3,
              "residential": 3, "artisan": 3, "outer": 4, "dock": 5}

KEEPOUT = []


def keepouts():
    """Yard rectangles that street furniture must not enter.

    One dict per placed training_ground / stable_yard:
        {"kind", "x", "y", "yaw", "w", "d"}
    `yaw` is radians, the same convention as the unit's.
    """
    return list(KEEPOUT)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _quad_wd(q):
    """(frontage, depth) of a unit quad laid out by hd_dense._obb."""
    return (_dist(q[2], q[3]), _dist(q[1], q[2]))


def _rect(cx, cy, rz, w, d):
    fx, fy = math.cos(rz), math.sin(rz)
    tx, ty = -fy, fx
    hw, hd = w * 0.5, d * 0.5
    return ((cx - tx * hw - fx * hd, cy - ty * hw - fy * hd),
            (cx + tx * hw - fx * hd, cy + ty * hw - fy * hd),
            (cx + tx * hw + fx * hd, cy + ty * hw + fy * hd),
            (cx - tx * hw + fx * hd, cy - ty * hw + fy * hd))


def _yaw_of(rz):
    """hd_dense's yaw for a facade normal rz (see hd_dense._obb)."""
    return math.atan2(-math.cos(rz), math.sin(rz))


def _in_poly(px, py, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if (yi > py) != (yj > py):
            x = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x:
                inside = not inside
        j = i
    return inside


def _rect_fits(poly, cx, cy, rz, w, d):
    """Every sampled point of the rectangle inside `poly` (12 samples)."""
    q = _rect(cx, cy, rz, w, d)
    for (x, y) in q:
        if not _in_poly(x, y, poly):
            return False
    for i in range(4):
        ax, ay = q[i]
        bx, by = q[(i + 1) % 4]
        for t in (0.25, 0.5, 0.75):
            if not _in_poly(ax + (bx - ax) * t, ay + (by - ay) * t, poly):
                return False
    return _in_poly(cx, cy, poly)


def _sep(a, b, tol=0.0):
    """Separating axis test for two convex quads.  True when they are apart."""
    for poly in (a, b):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, -(x2 - x1)
            L = math.hypot(nx, ny)
            if L < 1e-9:
                continue
            nx, ny = nx / L, ny / L
            amin = amax = None
            for (px, py) in a:
                v = px * nx + py * ny
                amin = v if amin is None else min(amin, v)
                amax = v if amax is None else max(amax, v)
            bmin = bmax = None
            for (px, py) in b:
                v = px * nx + py * ny
                bmin = v if bmin is None else min(bmin, v)
                bmax = v if bmax is None else max(bmax, v)
            if amax + tol < bmin or bmax + tol < amin:
                return True
    return False


def _longest_edge_dir(poly):
    best, ang = -1.0, 0.0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        L = math.hypot(bx - ax, by - ay)
        if L > best:
            best, ang = L, math.atan2(by - ay, bx - ax)
    return ang


def _cand_centres(poly, w, d, cap=70):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    out = [(cx, cy)]
    step = max(2.4, min(w, d) / 4.5)
    nx = max(1, int((max(xs) - min(xs)) / step))
    ny = max(1, int((max(ys) - min(ys)) / step))
    grid = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            gx = min(xs) + (i + 0.5) * (max(xs) - min(xs)) / (nx + 1)
            gy = min(ys) + (j + 0.5) * (max(ys) - min(ys)) / (ny + 1)
            grid.append((math.hypot(gx - cx, gy - cy), gx, gy))
    grid.sort()
    out.extend([(g[1], g[2]) for g in grid[:cap]])
    return out


def _site_in_block(poly, w, d, taken, budget=60):
    """Best rectangle of w x d inside the inset block polygon, or None."""
    try:
        import hd_dense as DN
        inner = DN._offset(DN._ccw(poly), DN.SETBACK + 1.15)
        area = abs(DN._area(inner))
    except Exception:
        inner, area = list(poly), 0.0
    if len(inner) < 3 or area < w * d:
        return None
    ang = _longest_edge_dir(inner)
    # facade normal is the outward normal of the longest edge, and its mirror
    for rz in (math.atan2(-math.cos(ang), math.sin(ang)) * 0.0 + ang + math.pi * 0.5,
               ang - math.pi * 0.5, ang + math.pi, ang):
        for (cx, cy) in _cand_centres(inner, w, d):
            if not _rect_fits(inner, cx, cy, rz, w, d):
                continue
            q = _rect(cx, cy, rz, w, d)
            if any(not _sep(q, t, 0.0) for t in taken):
                continue
            return (cx, cy, rz, q)
    return None


def _blocks(res):
    if not isinstance(res, dict):
        try:
            res = dict(res or {})
        except Exception:
            return []
    out = []
    for b in (res.get("blocks") or ()):
        poly = b.get("poly") or ()
        if len(poly) < 3 or b.get("open"):
            continue
        out.append(b)
    return out


def _quotas(share, quota=None):
    f = 1.0 if not share else max(0.2, float(share) / 0.055)
    q = dict((k, max(1, int(round(v * f)))) for (k, v) in QUOTA.items())
    if quota:
        q.update(quota)
    return q


def _wanted(only):
    if not only:
        return list(ORDER)
    if isinstance(only, str):
        only = [s.strip() for s in only.replace(";", ",").split(",")]
    return [k for k in ORDER if k in set(only)]


def place(units, res, seed=7, share=0.055, only=None, sites=True, quota=None,
          margin=0.6):
    """Return a NEW list of unit dicts with `kind` swapped on a few of them.

    Two passes, both deterministic for a given seed:

    1. IN-QUAD.  A unit whose quad is at least the type's minimum footprint
       (plus `margin`) is converted in place: kind, `foot_override`, and
       nothing else changes - x / y / yaw / quad stay exactly as hd_dense made
       them.  A type that does not fit is skipped, never resized.
    2. BLOCK SITE.  These six types are 14-52 m across and no house plot is
       wider than 12.8 m, so the big ones can only live at block scale: a
       rectangle is fitted inside a block's *inset* polygon (the backland behind
       the frontage row), the units that rectangle actually overlaps are
       dropped from the returned list, and one new unit is appended at the site
       with `source="types_site"` and `foot_override=(w, d)`.  Frontage rows
       survive, so a training ground reads as a yard in the middle of a block.
       Pass `sites=False` to get pass 1 only.

    `share` scales the per-kind quotas (QUOTA at share=0.055); `only` limits the
    kinds.  `KEEPOUT` is refreshed with every yard that was placed.
    """
    U = [dict(u) for u in (units or ())]
    if not U:
        return U
    del KEEPOUT[:]
    rng = random.Random(int(seed) * 7919 + 101)
    wanted = _wanted(only)
    q = _quotas(share, quota)
    try:
        city_r = float(((res or {}).get("city") or {}).get("radius") or 636.0)
    except Exception:
        city_r = 636.0

    # ---- pass 1: in-quad conversion --------------------------------------
    order = sorted(range(len(U)),
                   key=lambda i: (U[i].get("block") or 0, U[i].get("x") or 0.0,
                                  U[i].get("y") or 0.0))
    for kind in wanted:
        got = 0
        (lo_w, hi_w), (lo_d, hi_d) = LIMITS[kind]
        for i in order:
            if got >= q.get(kind, 0):
                break
            u = U[i]
            if u.get("foot_override") or u.get("source") in ("shop", "types_site"):
                continue
            if (u.get("district") or "") not in DISTRICT_OK[kind]:
                continue
            quad = u.get("quad")
            if not quad or len(quad) != 4:
                continue
            uw, ud = _quad_wd(quad)
            if uw < lo_w + margin or ud < lo_d + margin:
                continue
            ww = min(hi_w, uw - margin)
            dd = min(hi_d, ud - margin)
            u["kind"] = kind
            u["foot_override"] = (round(ww, 2), round(dd, 2))
            u["source"] = "types"
            got += 1
            KEEPOUT.append({"kind": kind, "x": u["x"], "y": u["y"],
                            "yaw": u["yaw"], "w": ww, "d": dd})

    # ---- pass 2: block sites --------------------------------------------
    if sites:
        blocks = _blocks(res)
        taken = []
        for u in U:
            if u.get("foot_override") and u.get("source") == "types_site":
                taken.append(u.get("quad"))
        taken = [t for t in taken if t]
        for kind in wanted:
            need = q.get(kind, 0) - sum(1 for u in U if u.get("kind") == kind)
            if need <= 0 or not blocks:
                continue
            (lo_w, hi_w), (lo_d, hi_d) = LIMITS[kind]
            fw, fd = FOOT[kind][0], FOOT[kind][1]
            ladder = [(fw, fd), ((fw + lo_w) * 0.5, (fd + lo_d) * 0.5),
                      (lo_w, lo_d)]
            got = []
            for (sw, sd) in ladder:
                if len(got) >= need:
                    break
                cands = []
                for b in blocks:
                    role = b.get("role")
                    if role not in DISTRICT_OK[kind]:
                        continue
                    poly = b.get("poly") or ()
                    if len(poly) < 3:
                        continue
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    if (max(xs) - min(xs)) < sw + 2.0 or (max(ys) - min(ys)) < sd + 2.0:
                        continue
                    cxb = sum(xs) / len(xs)
                    cyb = sum(ys) / len(ys)
                    rad = math.hypot(cxb, cyb) / max(city_r, 1.0)
                    site = _site_in_block(poly, sw, sd, taken)
                    if site is None:
                        continue
                    score = (_ROLE_RANK.get(role, 6) * 100.0
                             + abs(rad - RADIAL[kind]) * 260.0
                             + rng.random() * 30.0)
                    cands.append((score, b, site, cxb, cyb, rad))
                cands.sort(key=lambda c: c[0])
                for (score, b, site, cxb, cyb, rad) in cands:
                    if len(got) >= need:
                        break
                    (cx, cy, rz, quad) = site
                    if any(not _sep(quad, t, 0.0) for t in taken):
                        continue
                    taken.append(quad)
                    got.append((b, cx, cy, rz, quad, sw, sd))
            for (b, cx, cy, rz, quad, sw, sd) in got:
                yaw = _yaw_of(rz)
                U = [u for u in U
                     if not u.get("quad") or _sep(u["quad"], quad, 0.0)]
                nu = {"kind": kind, "x": cx, "y": cy, "z": 0.0, "yaw": yaw,
                      "block": b.get("id"), "ring": 0, "tier": b.get("tier"),
                      "district": b.get("role"), "scale": 1.0,
                      "seed": rng.randrange(1, 1 << 30), "quad": quad,
                      "w": sw, "d": sd, "floors": 1, "variant": "gable",
                      "source": "types_site", "foot_override": (round(sw, 2),
                                                               round(sd, 2))}
                U.append(nu)
                KEEPOUT.append({"kind": kind, "x": cx, "y": cy, "yaw": yaw,
                                "w": sw, "d": sd})
    return U


def report(units):
    """Count the types in a placement list (used by the lab and by capital)."""
    import collections
    c = collections.Counter(u.get("kind") for u in units
                            if u.get("foot_override"))
    print("[types] placed: " + ", ".join("%s=%d" % (k, c[k]) for k in ORDER if c[k]),
          flush=True)
    return c
