"""Asura Kingdom capital -- Ars (the king's city on the river).

Headless build:
  blender.exe -b --factory-startup --python capital.py -- --stage mass
  blender.exe -b --factory-startup --python capital.py -- --stage full --render

Coordinate plan (metres, origin = Grand Market plaza, +Y = towards the castle):
    outer wall        radius 300, height 10
    inner wall        radius 150 around the castle district
    castle rock       centre (0, 205), top z = 18
    cathedral         (-150, 60)
    adventurers guild (140, 70)
    harbour suburb    outside the south gate, on the river at y = -350
"""
import os
import sys
import math
import random
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
for p in (BL, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import medkit as K
from medkit import (T_at, box, cyl, cone, sphere, gable_roof, window, door,
                    lantern, mat_plaster, mat_wood, mat_tile, mat_stone,
                    mat_cobble, mat_flag, mat_metal, mat_gold, mat_glass,
                    mat_foliage, mat_water, mat_earth, mat_cloth)
import medbuild as B
import kcommon as KC

OUT_FBX = os.path.join(BL, "export", "capital")
OUT_PNG = os.path.join(BL, "renders", "kingdom")

# ------------------------------------------------------------------ layout
# One number decides how big the capital is.  Every radius below is quoted at
# CITY_SCALE = 1.0 (the 636 m reference city) and multiplied here, so the wall,
# the gates, the castle rock, the cathedral plot and the layout engine all stay
# in agreement when the city grows.  hd_layout.set_scale() applies the same
# factor to its own constants; the two must be changed together.
CITY_SCALE = 1.48
R_WALL = 300.0 * CITY_SCALE
WALL_H = 10.0
WALL_T = 2.4
R_INNER = 150.0 * CITY_SCALE
INNER_H = 8.0
ROCK_C = (0.0, 205.0 * CITY_SCALE)
ROCK_R = 82.0
ROCK_TOP = 18.0
# Declared with the other geometry constants, i.e. before any function that may
# read it: the build reaches build_castle_hd thirteen minutes in, and a NameError
# there cost two full runs before this moved up here.
HD_INT = {"on": False}
CATH_C = (-152.0 * CITY_SCALE, 58.0 * CITY_SCALE)
GUILD_C = (142.0 * CITY_SCALE, 66.0 * CITY_SCALE)
# the channel used to sit at y = -352, i.e. straight through the middle of the
# walled town, where it was a 2 m box under the 1284 m ground plate: completely
# buried, so the capital has always rendered as an inland town with no water.
# It now runs outside the enceinte (wall radius 620-666), on the approach to the
# south gate, where it can actually be seen - see hd_river.py
RIVER_Y = -762.0
RIVER_W = 92.0
GATE_R = R_WALL
RING_R = (72.0, 112.0, 150.0, 192.0, 236.0, 272.0)
RADIAL_N = 8
ST_W = 8.0           # street half-ish width used for occupancy
SEED = 20261022

rng = random.Random(SEED)

# occupancy raster (1 m cells) -- keeps buildings out of streets & each other
CELL = 1.0
GRID = 900
_occ = {}


def gkey(x, y):
    return (int(math.floor(x / CELL)), int(math.floor(y / CELL)))


def mark_disc(cx, cy, r, pad=0.0):
    r2 = (r + pad) ** 2
    x0, x1 = int((cx - r - pad) / CELL), int((cx + r + pad) / CELL)
    y0, y1 = int((cy - r - pad) / CELL), int((cy + r + pad) / CELL)
    for gx in range(x0, x1 + 1):
        for gy in range(y0, y1 + 1):
            dx = (gx + 0.5) * CELL - cx
            dy = (gy + 0.5) * CELL - cy
            if dx * dx + dy * dy <= r2:
                _occ[(gx, gy)] = 1


def mark_rect(cx, cy, w, d, rot=0.0, pad=0.0):
    hw, hd = w * 0.5 + pad, d * 0.5 + pad
    ca, sa = math.cos(-rot), math.sin(-rot)
    r = math.hypot(hw, hd)
    x0, x1 = int((cx - r) / CELL), int((cx + r) / CELL)
    y0, y1 = int((cy - r) / CELL), int((cy + r) / CELL)
    for gx in range(x0, x1 + 1):
        for gy in range(y0, y1 + 1):
            px = (gx + 0.5) * CELL - cx
            py = (gy + 0.5) * CELL - cy
            lx = px * ca - py * sa
            ly = px * sa + py * ca
            if abs(lx) <= hw and abs(ly) <= hd:
                _occ[(gx, gy)] = 1


def is_free(cx, cy, w, d, rot=0.0):
    hw, hd = w * 0.5, d * 0.5
    ca, sa = math.cos(-rot), math.sin(-rot)
    # sample the four corners + centre
    for sx, sy in ((0, 0), (hw, hd), (-hw, hd), (hw, -hd), (-hw, -hd),
                   (hw, 0), (-hw, 0), (0, hd), (0, -hd)):
        px, py = sx * ca - sy * sa, sx * sa + sy * ca
        if (gkey(cx + px, cy + py)) in _occ:
            return False
    return True


# ------------------------------------------------------------------ material set
MAT = {}


def init_mats():
    K._MAT_CACHE.clear()
    MAT["plaster"] = mat_plaster()
    MAT["plaster2"] = mat_plaster("plaster_warm", base="#ddcdb2", dirt="#c2b090", scale=4.4)
    MAT["wood"] = mat_wood()
    MAT["wood_dark"] = mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    MAT["tile"] = mat_tile()
    MAT["tile_blue"] = mat_tile("roof_slate", base="#4a5560", dark="#333c46", light="#5f6d7a")
    MAT["stone"] = mat_stone()
    MAT["stone_warm"] = mat_stone("stone_sand", base="#8d8168", dark="#5b5342", light="#a89b7f", scale=2.0)
    # castle rock: darker and much coarser than dressed masonry, so the rock does
    # not read as a second kind of wall
    MAT["rock"] = mat_stone("rock_cliff", base="#6a6357", dark="#3b382f", light="#8b8474", scale=0.9)
    MAT["cobble"] = mat_cobble()
    MAT["flag"] = mat_flag()
    MAT["iron"] = mat_metal()
    MAT["gold"] = mat_gold()
    MAT["glass"] = mat_glass()
    MAT["leaf"] = mat_foliage()
    MAT["leaf_dark"] = mat_foliage("leaf_dark", base="#2f4f28", light="#4a7135", scale=6.0)
    MAT["water"] = mat_water()
    MAT["earth"] = mat_earth(scale=4.0, detail=4.0, bump=0.18, patch=0.45)
    # town ground: the same earth, but cooled a little and broken into broad
    # patches instead of pepper grain -- a whole 1.2 km disc of the field material
    # reads as an orange carpet under the houses
    MAT["town_ground"] = mat_earth("town_ground", base="#8b8069", dark="#5d5546",
                                   scale=1.9, detail=3.0, bump=0.12, patch=0.62)
    # the castle rock: broad patches and a heavy bump instead of the masonry
    # courses the stone material gives at 3 m per ring
    MAT["cliff"] = mat_earth("cliff_rock", base="#8a8172", dark="#4e483c",
                             scale=0.55, detail=7.0, bump=0.60, patch=0.78)
    # the street has to sit DARKER than the yards it runs between, or the whole
    # town reads as a chalk drawing: trodden stone and mud in the joints
    MAT["street"] = mat_cobble("town_street", base="#6f6a60", mortar="#3b372f",
                               light="#8a8378")
    MAT["grass"] = mat_earth("grass_dry", base="#6d7448", dark="#4d5433",
                             scale=2.2, detail=2.5, bump=0.06, patch=0.60)
    MAT["hill"] = mat_earth("hill_far", base="#5c6b4a", dark="#42503a",
                            scale=1.6, detail=2.0, bump=0.04, patch=0.55)
    MAT["hill_dark"] = mat_earth("hill_far_dark", base="#4b5a42", dark="#354234",
                                 scale=1.6, detail=2.0, bump=0.04, patch=0.55)
    MAT["banner_red"] = mat_cloth("banner_red", "#8e2b26")
    MAT["banner_gold"] = mat_cloth("banner_gold", "#b9882c")
    MAT["banner_blue"] = mat_cloth("banner_blue", "#2f4a74")
    MAT["cloth_a"] = mat_cloth("cloth_a", "#a8543f")
    MAT["cloth_b"] = mat_cloth("cloth_b", "#3f5a56")
    MAT["cloth_c"] = mat_cloth("cloth_c", "#8f7a3e")
    MAT["glow"] = mat_glow("torch_glow", "#ffb057", 12.0)
    MAT["glow_warm"] = mat_glow("lamp_glow", "#ffd79a", 7.0)


def mat_glow(name, hexcol, strength=8.0):
    """Emissive material (Principled emission channel, no shader rewiring)."""
    old = bpy.data.materials.get(name)
    if old is not None:
        return old
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
            break
    if bsdf is not None:
        for key in ("Base Color", "Base Colour"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = K.c(hexcol, 1.0)
                break
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                try:
                    bsdf.inputs[key].default_value = K.c(hexcol, 1.0)
                except TypeError:
                    pass
                break
        for key in ("Emission Strength",):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = strength
                break
    return mat


# ------------------------------------------------------------------ primitives
def disc(name, r, z, mat, seg=128, cx=0.0, cy=0.0):
    verts = [(cx, cy, z)]
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    faces = [(0, 1 + i, 1 + (i + 1) % seg) for i in range(seg)]
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    return ob


def annulus(name, r0, r1, z, mat, seg=160):
    verts, faces = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        verts.append((r0 * ca, r0 * sa, z))
        verts.append((r1 * ca, r1 * sa, z))
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    return ob


def wall_ring(name, r, h, t, mat, seg=192, merlon=True, merlon_h=1.25, z=0.0,
              cx=0.0, cy=0.0):
    """Cylindrical curtain wall with crenellations, built from one mesh."""
    verts, faces = [], []
    ri, ro = r - t * 0.5, r + t * 0.5
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        verts += [(cx + ri * ca, cy + ri * sa, z), (cx + ro * ca, cy + ro * sa, z),
                  (cx + ri * ca, cy + ri * sa, z + h), (cx + ro * ca, cy + ro * sa, z + h)]
    for i in range(seg):
        j = (i + 1) % seg
        b, c = 4 * i, 4 * j
        faces += [(b + 0, b + 1, c + 1, c + 0),      # bottom
                  (b + 2, c + 2, c + 3, b + 3),      # top
                  (b + 1, b + 3, c + 3, c + 1),      # outer
                  (b + 0, c + 0, c + 2, b + 2)]      # inner
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    parts = [ob]
    if merlon:
        step = 2.6
        n = int(2 * math.pi * r / step)
        for i in range(n):
            if i % 2:
                continue
            a = 2 * math.pi * i / n
            cx_, cy_ = r * math.cos(a), r * math.sin(a)
            parts.append(box("%s_m%d" % (name, i), T_at(cx + cx_, cy + cy_, z + h + merlon_h * 0.5, rz=a),
                             (t * 1.05, 1.35, merlon_h), mat, bev=0.03))
    return parts


def rock_mass(name, cx, cy, R, z_top, mat, seed=7, seg=72, levels=7, taper=0.20):
    """Irregular castle rock: a jittered stack of rings, not a smooth cone.

    A plain `cyl` reads as a concrete wedding cake from any distance, so the
    radius gets a per-angle sine plus per-vertex noise and each ring gets a
    small random height wobble.
    """
    rr = random.Random(seed)
    verts, faces = [], []
    z0 = -2.0
    for l in range(levels):
        t = l / float(levels)
        z = z0 + (z_top - z0) * t
        base = R * (1.0 - taper * t)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            j = (1.0 + 0.10 * math.sin(a * 5.0 + seed * 0.7)
                 + 0.065 * math.sin(a * 11.0 + 1.3)
                 + 0.045 * rr.uniform(-1.0, 1.0))
            verts.append((cx + base * j * math.cos(a),
                          cy + base * j * math.sin(a),
                          z + rr.uniform(-0.70, 0.70) * (1.0 - t)))
    # ledge ring at the top, slightly inset, so walls have a lip to sit on
    top_r = R * (1.0 - taper)
    for i in range(seg):
        a = 2 * math.pi * i / seg
        j = 1.0 + 0.05 * math.sin(a * 7.0 + seed)
        verts.append((cx + top_r * 0.98 * j * math.cos(a),
                      cy + top_r * 0.98 * j * math.sin(a), z_top + 0.35))
    for l in range(levels - 1):
        for i in range(seg):
            n = (i + 1) % seg
            a0, a1 = l * seg + i, l * seg + n
            b0, b1 = (l + 1) * seg + i, (l + 1) * seg + n
            faces.append((a0, a1, b1, b0))
    last = (levels - 1) * seg
    topbase = levels * seg
    for i in range(seg):
        n = (i + 1) % seg
        faces.append((last + i, last + n, topbase + n, topbase + i))
    # cap
    centre = len(verts)
    verts.append((cx, cy, z_top + 0.5))
    for i in range(seg):
        n = (i + 1) % seg
        faces.append((topbase + i, topbase + n, centre))
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    return ob


def tower(name, x, y, r=7.0, h=17.0, mat=None, roof_mat=None, roof=True, seg=24, z=0.0):
    mat = mat or MAT["stone"]
    roof_mat = roof_mat or MAT["tile_blue"]
    parts = [cyl(name + "_body", T_at(x, y, z + h * 0.5), r, h, mat, seg=seg),
             cyl(name + "_cor", T_at(x, y, z + h - 0.25), r * 1.14, 0.7, mat, seg=seg)]
    if roof:
        parts.append(cone(name + "_roof", T_at(x, y, z + h + r * 0.05), r * 1.12, r * 1.45,
                          roof_mat, seg=seg))
        # gilded tip: sunk into the cone so it reads as a finial, not as a ball
        # floating above a needle-shaped spire that vanishes at distance
        parts.append(sphere(name + "_knob", T_at(x, y, z + h + r * 1.5 - 0.36), 0.32,
                            MAT["gold"], seg=10, ring=8))
    return parts


def gatehouse(name, ang, r=R_WALL, w=26.0, d=13.0, h=15.0):
    """Gate through the curtain wall at polar angle `ang`.

    The tunnel is only ~13 m deep and carries a paved floor plus torches on both
    jambs: an unlit 16 m hole renders as a BLACK VOID (no bounce light in EEVEE),
    which was read as a broken mesh.
    """
    x, y = r * math.cos(ang), r * math.sin(ang)
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    # two flanking towers, opening 11 m wide between them
    for s in (-1, 1):
        dx, dy = -math.sin(ang) * s, math.cos(ang) * s
        px, py = x + dx * (w * 0.5 - 4.0), y + dy * (w * 0.5 - 4.0)
        out += tower(name + "_tw%d" % (s + 1), px, py, r=6.4, h=h + 3.0)
    # gate block: two piers + lintel, so there is a real 11 m hole
    for s in (-1, 1):
        out.append(box(name + "_pier%d" % (s + 1),
                       T_at(x - math.sin(ang) * s * 7.6, y + math.cos(ang) * s * 7.6, h * 0.5, rz=ang),
                       (d, 4.6, h), MAT["stone"], bev=0.05))
    out.append(box(name + "_lintel", T_at(x, y, h - 1.6, rz=ang), (d, w - 4.4, 3.2),
                   MAT["stone"], bev=0.05))
    out.append(box(name + "_merlons", T_at(x, y, h + 0.6, rz=ang), (d * 0.9, w, 1.2),
                   MAT["stone"], bev=0.05))
    # portcullis bars
    for i in range(9):
        out.append(box(name + "_bar%d" % i,
                       T_at(x, y, h * 0.5, rz=ang).__matmul__(
                           T_at(0.0, -4.6 + i * 1.15, 0.0)),
                       (0.22, 0.22, h - 3.2), MAT["iron"]))
    # banners on the gate face
    for s in (-1, 1):
        bx = x + (-math.sin(ang) * s * 9.0) + ca * (d * 0.5 + 0.2)
        by = y + (math.cos(ang) * s * 9.0) + sa * (d * 0.5 + 0.2)
        out.append(box(name + "_ban%d" % (s + 1), T_at(bx, by, h - 3.4, rz=ang),
                       (0.10, 2.2, 5.0), MAT["banner_red"]))
    # paved floor through the tunnel + aprons outside, so the road does not stop
    # at the wall line and the hole is not a black gap over bare grass
    out.append(box(name + "_road", T_at(x, y, 0.07, rz=ang),
                   (d + 26.0, 11.2, 0.14), MAT["cobble"]))
    # torches on both jambs of the tunnel, at the outer and inner mouth
    for s in (-1, 1):
        for k in (0, 1):
            along = (d * 0.5 - 2.0) - k * 1.4          # + outward, - inward
            ox = x + ca * along - sa * s * 5.15
            oy = y + sa * along + ca * s * 5.15
            out.append(box(name + "_torch_br%d%d" % (s + 1, k),
                           T_at(ox, oy, 3.1, rz=ang), (0.16, 0.55, 0.16), MAT["iron"]))
            out.append(box(name + "_torch_fl%d%d" % (s + 1, k),
                           T_at(ox - sa * s * 0.22, oy + ca * s * 0.22, 3.46, rz=ang),
                           (0.34, 0.34, 0.55), MAT["glow"]))
    mark_rect(x, y, w * 1.1, d * 1.3, rot=-ang, pad=2.0)
    return out


# ------------------------------------------------------------------ ground
def build_ground():
    if HD["on"]:
        return ground_hd()
    out = [disc("ground_outer", 640.0, -0.35, MAT["grass"], seg=140),
           disc("ground_town", R_WALL + 2.0, 0.0, MAT["flag"], seg=160)]
    # paving rings & radial avenues
    for i, rr in enumerate(RING_R):
        w = ST_W * (1.25 if rr in (112.0, 192.0) else 0.85)
        out.append(annulus("ring_%d" % i, rr - w * 0.5, rr + w * 0.5, 0.06, MAT["cobble"]))
    for i in range(RADIAL_N):
        a = 2 * math.pi * i / RADIAL_N
        L = R_WALL - 6.0
        out.append(box("ave_%d" % i, T_at(L * 0.5 * math.cos(a), L * 0.5 * math.sin(a), 0.06, rz=a),
                       (L, ST_W * 1.1, 0.05), MAT["cobble"]))
    # mark the streets as occupied so no house lands on them
    for rr in RING_R:
        w = ST_W * (1.25 if rr in (112.0, 192.0) else 0.85)
        seg = 260
        for i in range(seg):
            a = 2 * math.pi * i / seg
            mark_rect(rr * math.cos(a), rr * math.sin(a), (2 * math.pi * rr / seg) * 1.6, w, rot=-a)
    for i in range(RADIAL_N):
        a = 2 * math.pi * i / RADIAL_N
        L = R_WALL
        n = int(L / 2.0)
        for k in range(n):
            t = (k + 0.5) * L / n
            mark_rect(t * math.cos(a), t * math.sin(a), L / n * 1.4, ST_W * 1.1, rot=-a)
    # grand market plaza (paved, reserved)
    out.append(box("plaza", T_at(0, 0, 0.08), (78, 78, 0.06), MAT["flag"]))
    mark_rect(0, 0, 82, 82, pad=1.0)
    # distant hills / mountain ring so the horizon is not a flat green dish
    hr = random.Random(SEED + 11)
    for i in range(22):
        a = 2 * math.pi * i / 22 + hr.uniform(-0.08, 0.08)
        rad = hr.uniform(400.0, 620.0)
        px, py = rad * math.cos(a), rad * math.sin(a)
        if py < RIVER_Y + RIVER_W + 30.0:
            continue
        rr = hr.uniform(70.0, 150.0)
        hh = hr.uniform(26.0, 58.0)
        out.append(sphere("hill%d" % i, T_at(px, py, -2.0), rr,
                          MAT["hill"] if i % 2 else MAT["hill_dark"],
                          seg=20, ring=10, squash=hh / rr))
    return out


# ------------------------------------------------------------------ castle
def build_castle():
    out = []
    cx, cy = ROCK_C
    # rock: one irregular mass (stacked truncated cones read as a concrete cake)
    out.append(rock_mass("rock_mass", cx, cy, ROCK_R, ROCK_TOP, MAT["rock"], seed=11))
    # boulders and broken ledges around the foot so the base is not a clean circle
    rb = random.Random(SEED + 31)
    for i in range(18):
        a = 2 * math.pi * i / 18.0 + rb.uniform(-0.12, 0.12)
        rad = ROCK_R * rb.uniform(0.86, 1.06)
        out.append(box("rock_boul%d" % i,
                       T_at(cx + rad * math.cos(a), cy + rad * math.sin(a),
                            rb.uniform(-0.5, 1.8), rz=a + rb.uniform(-0.5, 0.5),
                            rx=rb.uniform(-0.25, 0.25)),
                       (rb.uniform(3.0, 7.0), rb.uniform(2.5, 5.5), rb.uniform(1.6, 4.2)),
                       MAT["rock"], bev=0.18))
    # courtyard floor on top of the rock: a thin cylinder, not a single-sided disc,
    # so it still has a face when seen from the ramp below the rim
    out.append(cyl("rock_top", T_at(cx, cy, ROCK_TOP + 0.05), 51.5, 0.9, MAT["stone_warm"], seg=64))
    z = ROCK_TOP
    # castle curtain wall + towers on the rock
    out += wall_ring("castle_wall", 52.0, 9.0, 2.2, MAT["stone_warm"], seg=96,
                     z=z, cx=cx, cy=cy)
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 8
        out += tower("castle_tw%d" % i, cx + 52.0 * math.cos(a), cy + 52.0 * math.sin(a),
                     r=5.2, h=13.0, z=z)
    # gate towards the city (-Y side)
    out += tower("castle_g1", cx - 9.0, cy - 50.0, r=5.0, h=15.0, z=z)
    out += tower("castle_g2", cx + 9.0, cy - 50.0, r=5.0, h=15.0, z=z)
    out.append(box("castle_gate", T_at(cx, cy - 50.0, z + 6.0), (14, 4.0, 12.0),
                   MAT["stone_warm"], bev=0.05))
    # ramp down the rock to the city level
    ramp_l = math.hypot(64.0, z)
    out.append(box("castle_bridge",
                   T_at(cx, cy - 50.0 - 32.0, z * 0.5) @ T_at(0, 0, 0, rx=-math.atan2(z, 64.0)),
                   (9.0, ramp_l, 1.2), MAT["stone_warm"], bev=0.03))
    for i in range(9):
        out.append(box("castle_bridge_p%d" % i,
                       T_at(cx - 4.2 + (i % 2) * 8.4, cy - 52.0 - i * 6.6,
                            z * (1.0 - (i * 6.6 + 2.0) / 64.0) + 1.4),
                       (0.8, 0.8, 3.2), MAT["stone_warm"]))
    # keep
    kx, ky = cx, cy + 12.0
    out.append(box("keep_body", T_at(kx, ky, z + 17.0), (26, 22, 34), MAT["stone_warm"], bev=0.06))
    for s in (-1, 1):
        out.append(box("keep_wing%d" % (s + 1), T_at(kx + s * 17.0, ky + 6.0, z + 11.0),
                       (10, 14, 22), MAT["stone_warm"], bev=0.05))
        out += tower("keep_t%d" % (s + 1), kx + s * 14.6, ky - 12.2, r=3.8, h=38.0,
                     mat=MAT["stone_warm"], roof_mat=MAT["tile_blue"], z=z)
    out.append(box("keep_merlons", T_at(kx, ky, z + 34.6), (26.6, 22.6, 1.4),
                   MAT["stone_warm"], bev=0.04))
    for i in range(11):
        out.append(box("keep_m%d" % i, T_at(kx - 12.0 + i * 2.4, ky - 11.4, z + 35.9),
                       (1.3, 1.0, 1.6), MAT["stone_warm"]))
    # great hall + courtyard buildings
    out.append(box("hall", T_at(kx - 22.0, ky - 16.0, z + 6.0), (20, 13, 12),
                   MAT["stone_warm"], bev=0.05))
    out.append(gable_roof("hall_roof", T_at(kx - 22.0, ky - 16.0, 0.0), 20.0, 13.0, 12.0,
                          44.0, MAT["tile_blue"], MAT["stone_warm"]))
    out.append(box("stable", T_at(kx + 24.0, ky - 20.0, z + 4.5), (16, 10, 9), MAT["stone_warm"]))
    out.append(gable_roof("stable_roof", T_at(kx + 24.0, ky - 20.0, z), 16.0, 10.0, 9.0,
                          38.0, MAT["tile"], MAT["wood"]))
    # windows on the keep face towards the city (with sills, big enough to read)
    for f in range(4):
        for i in range(5):
            out.append(window("keep_w%d%d" % (f, i),
                              T_at(kx - 9.0 + i * 4.5, ky - 11.0, z + 6.0 + f * 7.0, rz=math.pi),
                              1.8, 2.9, MAT["stone_warm"], MAT["glass"]))
            out.append(box("keep_sill%d%d" % (f, i),
                           T_at(kx - 9.0 + i * 4.5, ky - 11.6, z + 3.7 + f * 7.0),
                           (2.4, 0.9, 0.35), MAT["stone_warm"], bev=0.05))
    # banner poles standing ON the front merlons, banners hanging from the top
    for s in (-1, 1):
        out.append(cyl("pole%d" % (s + 1), T_at(kx + s * 13.0, ky - 11.0, z + 42.3), 0.18, 13.0,
                       MAT["wood_dark"], seg=8))
        out.append(box("banner%d" % (s + 1),
                       T_at(kx + s * 13.0 + 1.3, ky - 11.0, z + 45.2),
                       (2.4, 0.09, 7.4), MAT["banner_red"]))
    mark_disc(cx, cy, ROCK_R + 6.0)
    return out


# ------------------------------------------------------------------ mesh packing
def join_parts(name, parts):
    """Merge a list of built objects into ONE mesh (pure data, no depsgraph).

    Deliberately avoids `evaluated_depsgraph_get()`: calling it while the scene
    is being mutated crashed Blender 5.2 with EXCEPTION_ACCESS_VIOLATION inside
    `deg_flush_updates_and_refresh`.  The trade-off is that Bevel *modifiers* on
    the merged parts are dropped, so this is only used for cheap fill (houses,
    trees); landmarks keep their own objects and their bevels.
    """
    verts, faces, fmat = [], [], []
    slots, mats = {}, []
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        me = ob.data
        base = len(verts)
        for v in me.vertices:
            verts.append(tuple(v.co))
        local = []
        for m in me.materials:
            if m is None:
                m = MAT.get("plaster")
            key = m.name if m else "fallback"
            if key not in slots:
                slots[key] = len(mats)
                mats.append(m)
            local.append(slots[key])
        for p in me.polygons:
            faces.append(tuple(base + i for i in p.vertices))
            fmat.append(local[p.material_index] if local else 0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    for m in mats:
        if m is not None:
            me.materials.append(m)
    if len(me.polygons) == len(fmat):
        top = max(0, len(me.materials) - 1)
        for p, mi in zip(me.polygons, fmat):
            p.material_index = min(mi, top)
    ob = K.link(bpy.data.objects.new(name, me))
    # bulk-remove the sources: deleting one by one is O(n) per object in bpy.data
    # and made house building take ~4.5 s each on a 3 000-object file
    dead = [o for o in parts if o is not None and o.type == "MESH"]
    try:
        bpy.data.batch_remove(dead)
    except Exception:
        for o in dead:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass
    return ob


# ------------------------------------------------------------------ lower city
HOUSE_KIND = ("plain", "shop", "stone", "tall", "narrow")
BUDGET = {"houses": 100000, "placed": 0}

# ------------------------------------------------------------------ hd switch
# --hd swaps the greybox landmarks for the hand-modelled hd_* modules.  The
# default path is untouched: HD["on"] stays False, every branch below keeps the
# legacy geometry, and capital_hd_glue is never imported.
HD = {"on": False}
HG = None          # capital_hd_glue module, imported on first use
_HD_MAT = None     # capital MAT + the extra keys the hd modules ask for
_HD_PLAN = None    # house kind / frontage planner


def hd_glue():
    global HG
    if HG is None:
        import capital_hd_glue
        HG = capital_hd_glue
    return HG


def hd_mat():
    global _HD_MAT
    if _HD_MAT is None:
        _HD_MAT = hd_glue().hd_materials(MAT)
    return _HD_MAT


def hd_house_plan(w, d, nf):
    """Kind / frontage for the next hd house (alternating gables, mixed kinds)."""
    global _HD_PLAN
    if _HD_PLAN is None:
        _HD_PLAN = hd_glue().HousePlanner(rng)
    return _HD_PLAN.next(w, d, nf)


def place_house(name, x, y, rot, w, d, nf, kind, r):
    if HD["on"]:
        return place_house_hd(name, x, y, rot, w, d, nf, kind, r)
    stone_ground = kind == "stone"
    parts = B.house(name, T_at(x, y, 0.0, rz=rot), W=w, D=d, FH=3.1, nF=nf,
                    pitch=rng.choice((38.0, 41.0, 44.0)),
                    walls=MAT["plaster"] if r < 0.5 else MAT["plaster2"],
                    timber=MAT["wood"], roof=MAT["tile"] if r < 0.72 else MAT["tile_blue"],
                    rng=rng, win_front=max(1, int(w / 2.4)), win_side=max(1, int(d / 3.0)),
                    has_sign=(kind == "shop"), stone_ground=stone_ground,
                    corner_style="quoin" if r > 0.6 else "timber",
                    dormers=1 if (nf >= 3 and r > 0.4) else 0,
                    jetty_corbels=(r > 0.5), eave_brackets=(r > 0.7))
    # a chimney pot and a shop sign board
    if kind == "shop":
        parts.append(box(name + "_sign", T_at(x, y, 3.3, rz=rot).__matmul__(T_at(0.0, d * 0.5 + 0.35, 0.0)),
                         (2.1, 0.14, 0.9), MAT["wood_dark"], bev=0.02))
    if kind == "tall":
        parts.append(box(name + "_attic", T_at(x, y, 3.1 * nf + 1.2, rz=rot), (w * 0.8, d * 0.8, 2.4),
                         MAT["plaster"], bev=0.03))
    # back yard: without it every plot is bare paving and the city reads as
    # houses dropped on a grey floor (no figure / ground at aerial distance)
    parts.append(box(name + "_yard",
                     T_at(x, y, 0.05, rz=rot) @ T_at(0.0, -(d * 0.5 + 3.4), 0.0),
                     (w * 0.94, 6.2, 0.06),
                     rng.choice((MAT["earth"], MAT["grass"], MAT["earth"]))))
    mark_rect(x, y, w, d, rot=-rot, pad=0.9)
    _yd = d * 0.5 + 3.4
    mark_rect(x + _yd * math.sin(rot), y - _yd * math.cos(rot),
              w * 0.94, 6.2, rot=-rot, pad=0.2)
    BUDGET["placed"] += 1
    if BUDGET["placed"] % 25 == 0:
        print("[capital] houses placed =", BUDGET["placed"], flush=True)
    return [join_parts(name, parts)]


def place_house_hd(name, x, y, rot, w, d, nf, kind, r):
    """One hd_houses house in place of the medbuild greybox.

    hd_houses models the walls with real openings and keeps the legacy contract
    (+Y = front, origin = footprint centre, z = 0 = ground), so only the shell is
    swapped.  Its footprint is roughly (w+1.5) x (d+2.1) because of the eaves and
    the shop front props, hence the narrower request (rows are spaced by w) and
    the slightly larger reserved rect.
    """
    spec = hd_house_plan(w, d, nf)
    ww = max(4.6, spec["w"] - 0.9)
    dd = spec["d"]
    parts = hd_glue().house(hd_mat(), rng, x, y, rot, ww, dd, spec["floors"],
                            spec["kind"], spec["frontage"])
    # back yard: without it every plot is bare paving and the city reads as
    # houses dropped on a grey floor (no figure / ground at aerial distance)
    yd = dd * 0.5 + 4.2
    parts.append(box(name + "_yard",
                     T_at(x, y, 0.05, rz=rot) @ T_at(0.0, -yd, 0.0),
                     (ww * 0.94, 6.0, 0.06),
                     rng.choice((MAT["earth"], MAT["grass"], MAT["earth"]))))
    mark_rect(x, y, ww + 1.6, dd + 2.2, rot=-rot, pad=0.3)
    mark_rect(x + yd * math.sin(rot), y - yd * math.cos(rot),
              ww * 0.94, 6.0, rot=-rot, pad=0.2)
    BUDGET["placed"] += 1
    if BUDGET["placed"] % 25 == 0:
        print("[capital] houses placed =", BUDGET["placed"], flush=True)
    return parts


def row_along(points, name_prefix, side=1.0, depth_range=(6.0, 9.0),
              w_range=(6.5, 11.0), skip_cb=None, road_half=4.5, back_row=True):
    """Fill a polyline with adjoining town houses facing the line.

    `road_half` is half the street width: houses are pushed back by that plus a
    pavement plus half their own depth, otherwise the row overlaps the reserved
    street band and `is_free` rejects almost every plot (that bug left the capital
    with ~70 isolated houses on bare paving instead of street frontages).
    """
    out = []
    idx = 0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 4.0:
            continue
        ang = math.atan2(y1 - y0, x1 - x0)
        nx, ny = -math.sin(ang) * side, math.cos(ang) * side
        t = 0.0
        while t < seg_len - 5.0 and BUDGET["placed"] < BUDGET["houses"]:
            w = rng.uniform(*w_range)
            d = rng.uniform(*depth_range)
            if t + w > seg_len:
                break
            u = (t + w * 0.5) / seg_len
            px = x0 + (x1 - x0) * u
            py = y0 + (y1 - y0) * u
            for row, off in ((0, road_half + 2.4 + d * 0.5),
                             (1, road_half + 2.4 + d + 7.4 + d * 0.5)):
                if row and not back_row:
                    continue
                dd = d * (1.0 if row == 0 else 0.88)
                cx = px + nx * off
                cy = py + ny * off
                # the house front is local +Y, i.e. Rz(rot) maps +Y to
                # (-sin rot, cos rot): that equals the street-ward direction
                # only with rot = atan2(-(px-cx), py-cy).  The legacy mirrors it
                # (correct for north-south streets only) and is left as is; hd
                # houses have real doors, so they need the true facing.
                if HD["on"]:
                    rot = math.atan2(-(px - cx), (py - cy))
                else:
                    rot = math.atan2(px - cx, py - cy)
                name = "%s_%d_%d" % (name_prefix, idx, row)
                if (not skip_cb or not skip_cb(cx, cy)) and is_free(cx, cy, w, dd, rot):
                    r = rng.random()
                    nf = 2 if r < 0.42 else (3 if r < 0.86 else 4)
                    kind = rng.choices(HOUSE_KIND, weights=(44, 22, 14, 12, 8))[0]
                    if nf == 4:
                        kind = "tall"
                    out += place_house(name, cx, cy, rot, w, dd, nf, kind, r)
            idx += 1
            # party walls: rows are continuous, so houses only nudge, never gap
            t += w + rng.uniform(0.05, 0.35)
    return out


def ring_half(i, rr):
    return (ST_W * (1.25 if rr in (112.0, 192.0) else 0.85)) * 0.5


def build_lower_city():
    out = []
    # ring frontages, both sides
    for i, rr in enumerate(RING_R):
        seg = 52
        pts = [(rr * math.cos(2 * math.pi * k / seg), rr * math.sin(2 * math.pi * k / seg))
               for k in range(seg + 1)]
        for side in (1.0, -1.0):
            out += row_along(pts, "rh%d%s" % (i, "a" if side > 0 else "b"), side=side,
                             road_half=ring_half(i, rr),
                             skip_cb=lambda x, y: (math.hypot(x, y) > R_WALL - 4.0))
    # radial frontages
    for i in range(RADIAL_N):
        a = 2 * math.pi * i / RADIAL_N
        pts = []
        r = 40.0
        while r <= R_WALL - 8.0:
            pts.append((r * math.cos(a), r * math.sin(a)))
            r += 24.0
        if len(pts) > 1:
            for side in (1.0, -1.0):
                out += row_along(pts, "ra%d%s" % (i, "a" if side > 0 else "b"), side=side,
                                 road_half=ST_W * 1.1 * 0.5,
                                 depth_range=(6.0, 8.5), w_range=(6.0, 9.0))
    return out


# ------------------------------------------------------------------ landmarks
def build_cathedral():
    out = []
    cx, cy = CATH_C
    L, W = 46.0, 19.0
    # nave
    out.append(box("cath_nave", T_at(cx, cy, 10.0), (W, L, 20.0), MAT["stone_warm"], bev=0.05))
    out.append(gable_roof("cath_roof", T_at(cx, cy, 0.0), W, L, 20.0, 52.0,
                          MAT["tile_blue"], MAT["stone_warm"]))
    # aisles
    for s in (-1, 1):
        out.append(box("cath_aisle%d" % (s + 1), T_at(cx + s * (W * 0.5 + 4.4), cy - 2.0, 6.0),
                       (8.8, L - 10.0, 12.0), MAT["stone_warm"], bev=0.04))
        out.append(gable_roof("cath_aisleroof%d" % (s + 1),
                              T_at(cx + s * (W * 0.5 + 4.4), cy - 2.0, 0.0),
                              8.8, L - 10.0, 12.0, 30.0, MAT["tile_blue"], MAT["stone_warm"]))
        # buttresses
        n = 6
        for k in range(n):
            t = (k + 0.5) / n
            out.append(box("cath_bt%d%d" % (s + 1, k),
                           T_at(cx + s * (W * 0.5 + 9.2), cy - L * 0.5 + t * L, 5.2),
                           (1.6, 1.9, 10.4), MAT["stone_warm"], bev=0.03))
    # west front + towers
    wy = cy - L * 0.5 - 2.0
    out.append(box("cath_front", T_at(cx, wy, 11.0), (W + 17.0, 5.0, 22.0), MAT["stone_warm"], bev=0.05))
    for s in (-1, 1):
        tx = cx + s * (W * 0.5 + 4.0)
        out.append(box("cath_tw%d" % (s + 1), T_at(tx, wy, 20.0), (8.0, 8.0, 40.0),
                       MAT["stone_warm"], bev=0.05))
        out.append(cone("cath_spire%d" % (s + 1), T_at(tx, wy, 40.0), 5.6, 16.0,
                        MAT["tile_blue"], seg=8))
        # gilt cross: two boxes + a small orb. Spheres alone left two gold dots
        # hanging in the sky because the thin bars disappear at distance.
        out.append(box("cath_crossv%d" % (s + 1), T_at(tx, wy, 58.2), (0.34, 0.34, 3.0),
                       MAT["gold"], bev=0.02))
        out.append(box("cath_crossh%d" % (s + 1), T_at(tx, wy, 58.9), (0.34, 2.3, 0.34),
                       MAT["gold"], bev=0.02))
        out.append(sphere("cath_orb%d" % (s + 1), T_at(tx, wy, 56.4), 0.42, MAT["gold"],
                          seg=10, ring=8))
    # rose window (recessed disc + ring)
    out.append(cyl("cath_rose_bg", T_at(cx, wy - 2.6, 15.0, rx=math.pi * 0.5), 4.4, 0.6,
                   MAT["glass"], seg=32))
    out.append(cyl("cath_rose_ring", T_at(cx, wy - 2.9, 15.0, rx=math.pi * 0.5), 4.8, 0.9,
                   MAT["stone_warm"], seg=32, r2=4.5))
    # portal + steps
    out.append(box("cath_door", T_at(cx, wy - 2.9, 4.2), (5.0, 0.8, 8.4), MAT["wood_dark"], bev=0.03))
    for i in range(4):
        out.append(box("cath_step%d" % i, T_at(cx, wy - 4.0 - i * 1.3, 0.25 - i * 0.0),
                       (16.0, 1.3, 0.5 + i * 0.0), MAT["stone_warm"]))
    mark_rect(cx, cy, W + 22.0, L + 8.0)
    return out


def build_guild_hall():
    out = []
    cx, cy = GUILD_C
    out.append(box("guild_body", T_at(cx, cy, 8.0), (24.0, 15.0, 16.0), MAT["stone_warm"], bev=0.05))
    out.append(box("guild_upper", T_at(cx, cy, 17.5), (24.8, 15.8, 3.0), MAT["wood_dark"], bev=0.03))
    out.append(gable_roof("guild_roof", T_at(cx, cy, 0.0, rz=math.pi * 0.5), 15.8, 24.8, 19.0, 46.0,
                          MAT["tile"], MAT["plaster"]))
    for i in range(3):
        out.append(box("guild_door%d" % i, T_at(cx - 5.0 + i * 5.0, cy - 7.7, 2.6), (2.6, 0.3, 5.2),
                       MAT["wood_dark"], bev=0.02))
    for f in range(2):
        for i in range(4):
            out.append(window("guild_w%d%d" % (f, i), T_at(cx - 7.5 + i * 5.0, cy - 7.6, 6.0 + f * 5.2),
                              1.5, 2.2, MAT["wood_dark"], MAT["glass"]))
    # hanging sign + banners flanking the doors
    out.append(box("guild_signarm", T_at(cx + 9.0, cy - 8.4, 9.0), (0.16, 1.6, 0.16), MAT["iron"]))
    out.append(box("guild_sign", T_at(cx + 9.0, cy - 9.3, 7.4), (0.14, 2.0, 1.7), MAT["gold"], bev=0.02))
    for s in (-1, 1):
        out.append(cyl("guild_pole%d" % (s + 1), T_at(cx + s * 11.4, cy - 8.6, 8.0), 0.14, 16.0,
                       MAT["wood_dark"], seg=8))
        out.append(box("guild_ban%d" % (s + 1), T_at(cx + s * 11.4 + 0.9, cy - 8.6, 11.0),
                       (1.7, 0.07, 6.4), MAT["banner_blue"]))
    mark_rect(cx, cy, 26.0, 17.0)
    return out


def build_market():
    out = []
    # colonnade hall on the north edge of the plaza
    hy = 34.0
    out.append(box("mkt_floor", T_at(0, hy, 0.6), (54.0, 20.0, 1.2), MAT["stone_warm"]))
    for i in range(9):
        for s in (-1, 1):
            out.append(cyl("mkt_col%d%d" % (i, s + 1),
                           T_at(-24.0 + i * 6.0, hy + s * 9.0, 4.6), 0.46, 8.2,
                           MAT["stone_warm"], seg=10))
    out.append(gable_roof("mkt_gable", T_at(0, hy, 0.0, rz=math.pi * 0.5), 22.0, 56.0, 9.2, 26.0,
                          MAT["tile"], MAT["plaster"]))
    mark_rect(0, hy, 56.0, 22.0)
    # fountain in the middle of the plaza
    out.append(cyl("fnt_basin", T_at(0, 0, 0.55), 6.2, 1.1, MAT["stone_warm"], seg=28))
    out.append(cyl("fnt_water", T_at(0, 0, 1.02), 5.6, 0.2, MAT["water"], seg=28))
    out.append(cyl("fnt_pillar", T_at(0, 0, 2.4), 1.1, 4.2, MAT["stone_warm"], seg=14))
    out.append(sphere("fnt_top", T_at(0, 0, 4.7), 1.5, MAT["stone_warm"], seg=16, ring=10))
    # market stalls in two rows
    idx = 0
    for row in (-1, 1):
        for i in range(6):
            sx = -22.0 + i * 8.6
            sy = row * 15.0
            if math.hypot(sx, sy) < 9.0:
                continue
            out += B.market_stall("stall_%d" % idx, T_at(sx, sy, 0.0,
                                                        rz=math.pi * 0.5 if row > 0 else -math.pi * 0.5),
                                  w=3.4, d=2.3, cloth=MAT["cloth_a"] if idx % 2 else MAT["cloth_b"])
            idx += 1
            mark_rect(sx, sy, 3.6, 2.6)
    # carts & barrels around the plaza edge
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.4
        px, py = 30 * math.cos(a), 30 * math.sin(a)
        if i % 2:
            out += B.cart("mkt_cart%d" % i, T_at(px, py, 0.0, rz=a))
        else:
            out += B.barrel_cluster("mkt_bar%d" % i, T_at(px, py, 0.0, rz=a), rng)
        mark_rect(px, py, 3.0, 2.0)
    return out


# ------------------------------------------------------------------ harbour
def build_harbour():
    out = []
    # the water, the quay wall and the landing stairs are built by hd_river.py;
    # what is left here is the working harbour on the town bank: jetties,
    # warehouses, a crane and boats
    for i in range(3):
        px = -110.0 + i * 96.0
        out.append(box("pier%d" % i, T_at(px, RIVER_Y + 12.0, 0.9), (9.0, 40.0, 0.5),
                       MAT["wood_dark"]))
        for k in range(6):
            for s in (-1, 1):
                out.append(cyl("pier%d_p%d%d" % (i, k, s + 1),
                               T_at(px + s * 4.0, RIVER_Y + 12.0 - 18.0 + k * 7.0, -2.2),
                               0.26, 6.0, MAT["wood_dark"], seg=8))
    # warehouses behind the quay
    for i in range(4):
        px = -150.0 + i * 100.0
        py = RIVER_Y + RIVER_W * 0.5 + 26.0
        out.append(box("wh%d" % i, T_at(px, py, 6.0), (30.0, 17.0, 12.0), MAT["stone"], bev=0.04))
        out.append(gable_roof("wh%d_roof" % i, T_at(px, py, 0.0, rz=math.pi * 0.5), 17.0, 30.0, 12.0,
                              38.0, MAT["tile"], MAT["wood"]))
        out.append(box("wh%d_door" % i, T_at(px, py - 8.7, 3.4), (6.0, 0.4, 6.8), MAT["wood_dark"]))
        mark_rect(px, py, 32.0, 19.0)
    # crane (timber A-frame with a jib)
    cx = 40.0
    cy = RIVER_Y + RIVER_W * 0.5 + 5.0
    for s in (-1, 1):
        out.append(box("crane_leg%d" % (s + 1), T_at(cx + s * 3.2, cy, 5.0, rz=0, ry=math.radians(9 * s)),
                       (0.7, 0.7, 10.0), MAT["wood_dark"]))
    out.append(box("crane_jib", T_at(cx, cy - 6.0, 9.6, rx=math.radians(12)), (0.5, 13.0, 0.5),
                   MAT["wood_dark"]))
    out.append(cyl("crane_rope", T_at(cx, cy - 12.0, 6.0), 0.06, 7.0, MAT["iron"], seg=6))
    out.append(box("crane_hook", T_at(cx, cy - 12.0, 2.2), (0.7, 0.4, 1.0), MAT["iron"]))
    # boats
    for i, (bx, by, br) in enumerate(((-110.0, RIVER_Y + 6.0, 0.06),
                                      (0.0, RIVER_Y - 4.0, -0.10),
                                      (96.0, RIVER_Y + 7.5, 0.03))):
        out += boat("boat%d" % i, bx, by, br)
    return out


def hull_loft(name, T, L, W, H, mat, seg=12, ztop=0.62, zbot=-1.25):
    """Lofted boat hull: a tapered box tube, so the ends come to a stem.

    The old version was a plain box + two smaller boxes, which read as a raft /
    a floating crate ("hull-less boat" in review).
    """
    verts, faces = [], []
    for i in range(seg + 1):
        t = -1.0 + 2.0 * i / seg
        yy = t * L * 0.5
        k = (1.0 - abs(t) ** 2.1) ** 0.5
        hw = max(0.20, W * 0.5 * k)
        zb = zbot * (0.32 + 0.68 * k)
        for (lx, lz) in ((hw, ztop), (-hw, ztop), (-hw, zb), (hw, zb)):
            w = T @ Vector((lx, yy, lz))
            verts.append((w.x, w.y, w.z))
    for i in range(seg):
        a, b = i * 4, (i + 1) * 4
        for k in range(4):
            faces.append((a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k))
    faces.append((3, 2, 1, 0))
    o = seg * 4
    faces.append((o, o + 1, o + 2, o + 3))
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    return ob


def boat(name, x, y, rz):
    T = T_at(x, y, 0.0, rz=rz)
    out = []
    L, W, H = 17.0, 5.0, 1.9
    out.append(hull_loft(name + "_hull", T, L, W, H, MAT["wood_dark"]))
    # deck planks follow the taper, so the rim does not overhang the hull
    out.append(hull_loft(name + "_deck", T @ T_at(0, 0, 0.02), L * 0.9, W * 0.86, 0.0,
                         MAT["wood"], seg=10, ztop=0.02, zbot=-0.10))
    # gunwale rails
    for s in (-1, 1):
        out.append(box(name + "_rail%d" % (s + 1), T @ T_at(s * W * 0.46, 0.0, 0.72),
                       (0.16, L * 0.72, 0.22), MAT["wood_dark"]))
    out.append(cyl(name + "_mast", T @ T_at(0, 1.0, 4.6), 0.16, 8.0, MAT["wood_dark"], seg=8))
    out.append(box(name + "_yard", T @ T_at(0, 1.0, 7.4), (6.6, 0.14, 0.14), MAT["wood_dark"]))
    # a furled sail under the yard
    out.append(box(name + "_sail", T @ T_at(0, 1.1, 6.9), (5.6, 0.35, 0.9), MAT["cloth_a"]))
    for i in range(3):
        out.append(box(name + "_cargo%d" % i, T @ T_at(-1.2 + i * 1.2, -2.0 + i * 2.0, 1.35),
                       (1.1, 1.1, 1.0), MAT["wood"]))
    return out


def build_suburbs():
    out = []
    # roads leaving the four gates
    for i in range(4):
        a = math.pi * 0.5 * i
        for side in (1.0, -1.0):
            pts = []
            r = R_WALL + 12.0
            while r < 470.0:
                pts.append((r * math.cos(a), r * math.sin(a)))
                r += 26.0
            out += row_along(pts, "sub%d%s" % (i, "a" if side > 0 else "b"), side=side,
                             depth_range=(6.0, 8.0), w_range=(6.0, 9.5),
                             skip_cb=lambda x, y: math.hypot(x, y) < R_WALL + 8.0
                             or abs(y - RIVER_Y) < 34.0)
    # fields outside the wall: crop patches
    rr = random.Random(SEED + 7)
    for i in range(26):
        a = rr.uniform(0, 2 * math.pi)
        rad = rr.uniform(R_WALL + 40.0, 600.0)
        px, py = rad * math.cos(a), rad * math.sin(a)
        if abs(py - RIVER_Y) < 40.0:
            continue
        w, d = rr.uniform(26.0, 46.0), rr.uniform(20.0, 34.0)
        if not is_free(px, py, w, d, a):
            continue
        out.append(box("field%d" % i, T_at(px, py, 0.06, rz=a), (w, d, 0.12),
                       MAT["grass"] if i % 3 else MAT["earth"]))
        for k in range(7):
            out.append(box("field%d_row%d" % (i, k),
                           T_at(px, py, 0.22, rz=a).__matmul__(T_at(0.0, -d * 0.5 + (k + 0.5) * d / 7.0, 0.0)),
                           (w * 0.92, 0.5, 0.22), MAT["grass"]))
        mark_rect(px, py, w, d, rot=-a)
    # trees beyond the wall and in the plazas
    for i in range(90):
        a = rr.uniform(0, 2 * math.pi)
        rad = rr.uniform(40.0, 620.0)
        px, py = rad * math.cos(a), rad * math.sin(a)
        if abs(py - RIVER_Y) < 26.0:
            continue
        if rad < R_WALL and not (rr.random() < 0.10):
            continue
        if not is_free(px, py, 5.0, 5.0, 0.0):
            continue
        out += B.tree("tree%d" % i, T_at(px, py, 0.0, rz=rr.uniform(0, 6.28)), h=rr.uniform(3.6, 6.4),
                      rng=rr, leaf_mat=MAT["leaf"] if i % 3 else MAT["leaf_dark"])
        mark_disc(px, py, 2.6)
    return out


# ------------------------------------------------------------------ hd build
HD_GATE_HALF = 14.4          # hd gatehouse is 29.4 m wide: half the wall opening


def wrap_pi(a):
    """Wrap an angle into (-pi, pi]."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def hd_curtain_walls():
    """Outer curtain with a gate-sized opening at each of the four gates.

    The hd gatehouse is a solid 29.4 m wall block with a 5.5 m arch through it,
    so the curtain has to butt into its flanks.  The legacy ring ran straight
    through the passage and then a greybox gatehouse was parked on top of it,
    which is exactly the double-masonry the hd version must not have.
    """
    out = []
    M = hd_mat()
    gap = math.asin(min(1.0, HD_GATE_HALF / R_WALL))
    for k in range(4):
        out += hd_glue().wall_arc("outer_wall%d" % k, R_WALL, WALL_H, WALL_T,
                                  M["stone"], k * math.pi * 0.5 + gap,
                                  (k + 1) * math.pi * 0.5 - gap, seg_deg=1.2)
    rw = random.Random(SEED + 3)
    # buttresses break the "necklace of beads" read of an evenly spaced ring
    for i in range(72):
        a = 2 * math.pi * i / 72.0 + math.pi / 72.0
        if abs(a - round(a / (math.pi * 0.5)) * math.pi * 0.5) < gap * 1.2:
            continue
        out.append(box("wt_butt%d" % i,
                       T_at((R_WALL + 1.15) * math.cos(a), (R_WALL + 1.15) * math.sin(a),
                            WALL_H * 0.46, rz=a),
                       (3.2, 2.6, WALL_H * 0.92), M["stone"], bev=0.05))
    for i in range(16):
        a = 2 * math.pi * i / 16 + math.pi / 16
        if i % 4 == 0:
            continue
        rr = 7.2 + rw.uniform(-1.5, 1.8)
        hh = WALL_H + 6.0 + rw.uniform(-2.5, 5.0)
        out += tower("wt%d" % i, (R_WALL - 0.6) * math.cos(a), (R_WALL - 0.6) * math.sin(a),
                     r=rr, h=hh)
    return out


def hd_gates():
    """One hd gatehouse per gate; local +Y = outside the city."""
    M = hd_mat()
    out = []
    for k in range(4):
        a = k * math.pi * 0.5
        out += hd_glue().gatehouse(M, rng, R_WALL * math.cos(a), R_WALL * math.sin(a),
                                   a - math.pi * 0.5, 0.0, name="gate%d" % k)
    return out


# ------------------------------------------------------- the outer town (b5)
# A capital is not an island on a plinth: a 16..24 sided enceinte far outside
# the core, four radial roads from the core gates, field strips in the ring
# between the two walls and one roadside hamlet at each exit.  The core keeps
# its own hd curtain + hd gatehouses; this is the later, outer fortification.
R_OUTER = 640.0 * CITY_SCALE
OUTER_N = 20
OUTER_JIT = 0.03
_ORING = {"pts": None, "gaps": None}


def _axis_hit(p0, p1, ang):
    """Point where the ray at `ang` crosses the segment p0->p1 (or None)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ux, uy = math.cos(ang), math.sin(ang)
    den = ux * dy - uy * dx
    if abs(den) < 1e-9:
        return None
    s = (p0[0] * dy - p0[1] * dx) / den
    if s <= 0.0:
        return None
    t = (s * ux - p0[0]) * dx + (s * uy - p0[1]) * dy
    t /= dx * dx + dy * dy
    if not (0.0 < t < 1.0):
        return None
    return (s * ux, s * uy)


def outer_ring_pts():
    """Polygon enceinte, taken from the plan's own rim when plan2 is active.

    A circle drawn at 0.985 R cuts through the outermost terraces wherever the
    plan bulges and leaves a ring of bare ground where it pinches in, because
    hd_plan2 warps its rings by up to +-15 % of the radius.  hd_plan2 hands
    back the exact kerb of its outermost ring, so the wall sits on the houses
    instead of guessing.  The jittered circle stays as the fallback for the
    old layout engine.
    """
    if _ORING["pts"] is None:
        rim = None
        try:
            rim = ((HD_LAY.get("res") or {}).get("city") or {}).get("rim")
        except Exception:
            rim = None
        if rim and len(rim) > 8:
            n = len(rim)
            pts = []
            for k in range(OUTER_N):
                f = k * n / float(OUTER_N)
                i0 = int(f) % n
                i1 = (i0 + 1) % n
                t = f - math.floor(f)
                pts.append((rim[i0][0] * (1.0 - t) + rim[i1][0] * t,
                            rim[i0][1] * (1.0 - t) + rim[i1][1] * t))
            _ORING["pts"] = pts
        else:
            rw = random.Random(SEED + 61)
            pts = []
            for k in range(OUTER_N):
                a = 2.0 * math.pi * (k + 0.5) / OUTER_N + rw.uniform(-0.02, 0.02)
                r = R_OUTER * (1.0 + rw.uniform(-OUTER_JIT, OUTER_JIT))
                pts.append((r * math.cos(a), r * math.sin(a)))
            _ORING["pts"] = pts
    return _ORING["pts"]


def outer_gaps():
    """(point, outward angle) of the four gate openings on the outer ring."""
    if _ORING["gaps"] is None:
        pts = outer_ring_pts()
        gates = None
        try:
            gates = ((HD_LAY.get("res") or {}).get("city") or {}).get("gates")
        except Exception:
            gates = None
        gaps = []
        if gates:
            # plan2 rotates the whole plan, so its avenues no longer leave on
            # the mathematical axes.  Put the gatehouse on the avenue it
            # belongs to or the gate opens onto a terrace.
            for (gp, ga) in gates:
                gaps.append(((float(gp[0]), float(gp[1])), float(ga)))
        else:
            for k in range(4):
                ang = k * math.pi * 0.5
                for i in range(len(pts)):
                    hit = _axis_hit(pts[i], pts[(i + 1) % len(pts)], ang)
                    if hit:
                        gaps.append((hit, ang))
                        break
        _ORING["gaps"] = gaps
    return _ORING["gaps"]


def outer_wall():
    """Straight runs between the fold points, a tower over every fold."""
    G = hd_glue()
    M = hd_mat()
    pts = outer_ring_pts()
    gaps = outer_gaps()
    out = []
    n = 0
    for i in range(len(pts)):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1.0:
            continue
        ux, uy = dx / L, dy / L
        cuts = []
        for (gp, ang) in gaps:
            tt = (gp[0] - p0[0]) * ux + (gp[1] - p0[1]) * uy
            perp = abs((gp[0] - p0[0]) * (-uy) + (gp[1] - p0[1]) * ux)
            if 0.0 < tt < L and perp < 1.5:
                cuts.append(tt)
        breaks = [0.0]
        for tt in sorted(cuts):
            breaks += [max(0.0, tt - HD_GATE_HALF), min(L, tt + HD_GATE_HALF)]
        breaks.append(L)
        for j in range(0, len(breaks) - 1, 2):
            s0, s1 = breaks[j], breaks[j + 1]
            if s1 - s0 < 3.0:
                continue
            out += G.wall_seg("owall%d_%d" % (i, n),
                              (p0[0] + ux * s0, p0[1] + uy * s0),
                              (p0[0] + ux * s1, p0[1] + uy * s1),
                              WALL_H, WALL_T, M["stone"])
            n += 1
        # the tower sits on the OUTSIDE of the fold, so the wall reads as a
        # battered face with the towers standing proud of it
        rr = math.hypot(p0[0], p0[1])
        toe = 0.0 if rr < 1.0 else (5.2 / rr)
        out += tower("owt%d" % i, p0[0] * (1.0 + toe), p0[1] * (1.0 + toe),
                     r=7.5 + (i % 3) * 0.6,
                     h=WALL_H + 6.0 + (i % 4) * 1.4, mat=M["stone"])
    return out


def outer_gates():
    """An hd gatehouse on each of the four outer openings, +Y out of the city."""
    M = hd_mat()
    out = []
    for k, (gp, ang) in enumerate(outer_gaps()):
        # 1.16x so the gate still lifts 3-5 m above the flanking towers
        out += hd_glue().gatehouse(M, rng, gp[0], gp[1], ang - math.pi * 0.5, 0.0,
                                   name="ogate%d" % k, scale=1.16)
    return out


def radial_roads():
    """Cobbled carriageway core gate -> outer gate, dirt track beyond it."""
    out = []
    for (gp, ang) in outer_gaps():
        ux, uy = math.cos(ang), math.sin(ang)
        r_gate = math.hypot(gp[0], gp[1])
        # the avenue runs from the market square to the gate mouth: this is the
        # corridor _reserved() keeps free of houses
        r0 = r_gate * 0.52
        L0 = r_gate - r0 - 24.0
        if L0 > 4.0:
            c = r0 + L0 * 0.5
            out.append(box("road_in%d" % len(out), T_at(ux * c, uy * c, 0.07, rz=ang),
                           (L0, 11.0, 0.09), MAT["cobble"]))
        c1 = r_gate + 18.0 + 110.0
        out.append(box("road_out%d" % len(out), T_at(ux * c1, uy * c1, 0.07, rz=ang),
                       (220.0, 7.0, 0.09), MAT["earth"]))
    return out


def ring_fields():
    """Field strips outside the wall: the capital sits in farmland, not on a disc."""
    rw = random.Random(SEED + 71)
    out = []
    n = 0
    tries = 0
    while n < 52 and tries < 900:
        tries += 1
        a = rw.uniform(0.0, 2.0 * math.pi)
        r = rw.uniform(R_OUTER + 48.0, 930.0)
        x, y = r * math.cos(a), r * math.sin(a)
        if min(abs(x), abs(y)) < 26.0:          # keep the radial roads clear
            continue
        if y < RIVER_Y + RIVER_W + 34.0:
            continue
        w = rw.uniform(20.0, 38.0)
        d = rw.uniform(15.0, 28.0)
        rot = a + rw.uniform(-0.45, 0.45)
        out.append(box("field%d" % n, T_at(x, y, 0.05, rz=rot), (w, d, 0.10),
                       rw.choice((MAT["earth"], MAT["grass"], MAT["hill"]))))
        # hedgerow on one long edge: fields need boundaries or they read as decals
        out.append(box("hedge%d" % n,
                       T_at(x - math.sin(rot) * d * 0.5, y + math.cos(rot) * d * 0.5,
                            0.45, rz=rot), (w, 0.7, 0.85), MAT["leaf_dark"]))
        n += 1
    return out


def suburbs_hd():
    """One roadside hamlet per exit: houses, a mill and a threshing floor."""
    G = hd_glue()
    M = hd_mat()
    out = []
    rw = random.Random(SEED + 81)
    for k, (gp, ang) in enumerate(outer_gaps()):
        ux, uy = math.cos(ang), math.sin(ang)
        px, py = -uy, ux
        r0 = math.hypot(gp[0], gp[1]) + 34.0
        buf, chunks = [], []
        n = 14 + 4 * (k % 3)
        for i in range(n):
            along = r0 + i * 12.5 + rw.uniform(-2.0, 2.0)
            side = 1.0 if i % 2 == 0 else -1.0
            off = 10.0 + rw.uniform(0.0, 3.0)
            cx = ux * along + px * off * side
            cy = uy * along + py * off * side
            if cy < RIVER_Y + RIVER_W + 20.0:
                continue
            yaw = math.atan2(side * px, -side * py)
            ob = G.house(M, rw, cx, cy, yaw, rw.uniform(5.6, 7.4),
                         rw.uniform(6.6, 8.6), 1 if rw.random() < 0.45 else 2,
                         rw.choice(("timber", "timber", "craft", "stone")), "eaves")
            if isinstance(ob, (list, tuple)):
                buf.extend(ob)
            elif ob:
                buf.append(ob)
            if len(buf) >= 700:
                m = G.merge_objects("sub%d_a%d" % (k, i), buf)
                if m is not None:
                    chunks.append(m)
                buf = []
        # ten cottages on a lawn read as dropped props; ten cottages on a paved
        # lane with a well read as a village
        length = (n - 1) * 12.5 + 30.0
        lx = ux * (r0 - 6.0 + length * 0.5)
        ly = uy * (r0 - 6.0 + length * 0.5)
        buf.append(box("sub%d_lane" % k, T_at(lx, ly, 0.035, rz=math.atan2(uy, ux)),
                       (length, 7.6, 0.05), MAT["cobble"]))
        wx_, wy_ = lx + px * 5.4, ly + py * 5.4
        buf += G.well("sub%d_well" % k, T_at(wx_, wy_, 0.0), M)
        hw = random.Random(SEED + 97 + k)
        for j in range(3):
            hx = wx_ + px * (8.0 + 7.0 * j) + ux * hw.uniform(4.0, 14.0)
            hy = wy_ + py * (8.0 + 7.0 * j) + uy * hw.uniform(4.0, 14.0)
            buf.append(cone("hay%d_%d" % (k, j), T_at(hx, hy, 0.0),
                            hw.uniform(1.8, 2.6), hw.uniform(2.0, 3.0),
                            MAT["earth"], seg=10))
        # the mill stands across the road, the floor opposite it
        mx, my = ux * (r0 + 26.0) + px * 30.0, uy * (r0 + 26.0) + py * 30.0
        if my > RIVER_Y + RIVER_W + 20.0:
            buf += [cyl("mill%d_body" % k, T_at(mx, my, 4.6), 3.4, 9.2, M["stone_warm"], seg=16),
                    cone("mill%d_roof" % k, T_at(mx, my, 9.2), 3.9, 4.6, MAT["tile"], seg=16),
                    box("mill%d_door" % k, T_at(mx, my - 3.35, 1.2), (1.6, 0.4, 2.4),
                        MAT["wood_dark"])]
            # the lane needs a green edge or the cottages read as boxes on a lawn
            for j in range(5):
                hx = ux * (r0 + 4.0 + j * 11.0) + px * 15.4
                hy = uy * (r0 + 4.0 + j * 11.0) + py * 15.4
                buf.append(box("hedge%d_%d" % (k, j), T_at(hx, hy, 0.55, rz=math.atan2(uy, ux)),
                               (10.0, 1.3, 1.1), MAT["leaf_dark"], bev=0.25))
                hx2 = ux * (r0 + 9.0 + j * 11.0) - px * 16.0
                hy2 = uy * (r0 + 9.0 + j * 11.0) - py * 16.0
                buf.append(box("hedge2%d_%d" % (k, j), T_at(hx2, hy2, 0.55, rz=math.atan2(uy, ux)),
                               (9.0, 1.3, 1.1), MAT["leaf_dark"], bev=0.25))
            for j in range(2):
                tx = ux * (r0 + 18.0 + j * 26.0) + px * 22.0 * (1 if j % 2 else -1)
                ty = uy * (r0 + 18.0 + j * 26.0) + py * 22.0 * (1 if j % 2 else -1)
                buf += B.tree("ftree%d_%d" % (k, j), T_at(tx, ty, 0.0, rz=rw.uniform(0, 6.28)),
                              h=rw.uniform(4.6, 6.2), rng=rw,
                              species=rw.choice(("broad", "poplar")),
                              leaf_mat=MAT["leaf"] if rw.random() < 0.6 else MAT["leaf_dark"])
        tx, ty = ux * (r0 + 30.0) - px * 30.0, uy * (r0 + 30.0) - py * 30.0
        buf.append(cyl("thresh%d" % k, T_at(tx, ty, 0.06), 10.5, 0.10, MAT["earth"], seg=24))
        ob = G.merge_objects("sub%d" % k, buf) if buf else None
        if chunks:
            ob = chunks[0] if len(chunks) == 1 else G.merge_objects("sub%d_all" % k, chunks + ([ob] if ob else []))
        if ob is not None:
            out.append(ob)
    return out


def city_wells(picked, count=10):
    """A well in the open space of the densest quarters, never in a plot."""
    G = hd_glue()
    M = hd_mat()
    rw = random.Random(SEED + 97)
    pts = [(float(p["x"]), float(p["y"])) for p in picked]
    out = []
    tries = 0
    while len(out) < count and tries < 4000:
        tries += 1
        a = rw.uniform(0.0, 2.0 * math.pi)
        r = math.sqrt(rw.uniform(0.02, 1.0)) * (R_WALL - 30.0)
        x, y = r * math.cos(a), r * math.sin(a)
        if math.hypot(x, y) < 26.0:
            continue
        if min((x - qx) ** 2 + (y - qy) ** 2 for qx, qy in pts) < 49.0:
            continue
        if any((x - ox) ** 2 + (y - oy) ** 2 < 196.0 for ox, oy in
               [(float(p.get("x") or 0), float(p.get("y") or 0)) for p in []]):
            continue
        out += G.well("well%d" % len(out), G._T(x, y, 0.0, rw.uniform(0, 3.14)), M)
        out.append(box("well_pad%d" % (len(out) // 6), T_at(x, y, 0.05), (4.2, 4.2, 0.08),
                       MAT["flag"]))
    return out


def build_castle_hd():
    """hd_castle lifted onto the rock, plus the approach ramp it cannot know about.

    hd_castle is modelled with z = 0 = its own courtyard and the main gate on
    local +Y; on the city it has to stand on the rock cap (18.35..18.5) and look
    down at the city, so it is rotated by pi and lifted by 18.45.
    """
    M = hd_mat()
    cx, cy = ROCK_C
    # taper 0.30 instead of 0.20: at 0.20 the cap is 64 m across while the castle
    # is 97 m, so a 14 m flat collar of sawn stone ringed the walls and the whole
    # thing read as a table with a model on it
    out = [rock_mass("rock_mass", cx, cy, ROCK_R, ROCK_TOP, MAT["cliff"], seed=11,
                     taper=0.30, seg=96, levels=10)]
    rb = random.Random(SEED + 31)
    for i in range(18):
        a = 2 * math.pi * i / 18.0 + rb.uniform(-0.12, 0.12)
        rad = ROCK_R * rb.uniform(0.86, 1.06)
        out.append(box("rock_boul%d" % i,
                       T_at(cx + rad * math.cos(a), cy + rad * math.sin(a),
                            rb.uniform(-0.5, 1.8), rz=a + rb.uniform(-0.5, 0.5),
                            rx=rb.uniform(-0.25, 0.25)),
                       (rb.uniform(3.0, 7.0), rb.uniform(2.5, 5.5), rb.uniform(1.6, 4.2)),
                       MAT["rock"], bev=0.18))
    # a ring of fallen blocks along the rim breaks the machined circle of the
    # plateau edge: without them the silhouette is a perfect disc from every
    # angle, which is the one shape nature never produces
    rt = ROCK_R * 0.72
    for i in range(26):
        a = 2 * math.pi * i / 26.0 + rb.uniform(-0.09, 0.09)
        rad = rt + rb.uniform(-1.5, 4.5)
        out.append(box("rock_rim%d" % i,
                       T_at(cx + rad * math.cos(a), cy + rad * math.sin(a),
                            ROCK_TOP + rb.uniform(-1.2, 0.35), rz=a,
                            rx=rb.uniform(-0.3, 0.3), ry=rb.uniform(-0.3, 0.3)),
                       (rb.uniform(2.4, 5.2), rb.uniform(2.0, 4.0), rb.uniform(1.2, 2.8)),
                       MAT["rock"], bev=0.22))
    out.append(cyl("rock_top", T_at(cx, cy, ROCK_TOP + 0.05), 49.0, 0.9, MAT["stone_warm"], seg=64))
    # hd_rock replaces everything above with a mass whose bedding planes, joint
    # columns and talus are analytic functions of world position, so the shader
    # (same dip, same Object coordinates) stays in register with the geometry.
    # A stack of noise-perturbed cylinders never read as rock: geometry, not
    # noise, is what the eye checks.  Kept behind try/except because the fallback
    # above still works -- a broken rock must not cost a 15 minute build.
    try:
        import hd_rock as RK
        _t0 = time.time()
        _rock = RK.build(K=K, MAT=MAT, cx=cx, cy=cy, r=ROCK_R, top_z=ROCK_TOP, seed=11)
        if _rock:
            for _ob in out:
                if _alive(_ob) and _ob.name.startswith(("rock_mass", "rock_boul", "rock_rim", "rock_top")):
                    bpy.data.objects.remove(_ob, do_unlink=True)
            _mesh = [p for p in _rock if getattr(p, "type", "") == "MESH"]
            _faces = sum(len(p.data.polygons) for p in _mesh)
            print("[capital] rock: %d objects / %d faces / %.1f s (hd_rock)"
                  % (len(_mesh), _faces, time.time() - _t0), flush=True)
            out = [p for p in out if _alive(p)] + list(_rock)
        else:
            print("[capital] rock: hd_rock returned nothing, keeping the old mass", flush=True)
    except Exception as _exc:
        print("[capital] rock FAILED: %r" % (_exc,), flush=True)
    z = ROCK_TOP + 0.45
    # 1.15: on a 115 m plateau a 97 m curtain left the castle looking like an
    # ornament on a tray; the ramp has to move out by the same factor
    CS = 1.15
    out += hd_glue().castle(M, rng, cx, cy, math.pi, z, CS)
    # hd_castle's causeway deck ends at local y = 47.2 (world y = 157.8, z ~ 21):
    # the ramp starts just behind that so the two decks overlap, and its flanks
    # reach the ground (the rock face is steeper than any walkable grade).
    # Drawn with the castle's own palette so ramp and castle read as one mass.
    out += hd_glue().wedge_ramp(hd_glue().castle_mats(M), "castle_ramp", cx,
                                y_top=cy - 47.6 * CS, z_top=z + 2.55,
                                y_bot=cy - 80.5, z_bot=0.0, w=11.5)
    # globals().get, not HD_INT["on"]: this function is reached 13 minutes into
    # a build and a NameError here once cost two complete runs.  Reading the
    # flag defensively turns "typo kills the build" into "interiors stay off".
    if globals().get("HD_INT", {}).get("on"):
        # The throne hall.  hd_castle_int is authored in hd_castle's local frame
        # (keep void centre at local (0,-21), floor at local z=+1.30) and its
        # build() applies Translation(origin,z) @ Rotation(rot) @ Scale(scale)
        # in exactly the same order as place(), so the castle's own rot/scale
        # carry over unchanged.  It must NOT go through place()/castle(): those
        # filter on ob.type == "MESH" and would drop the ~60 lamps, leaving them
        # stacked at the world origin.
        try:
            import hd_castle_int as CINT
            lx, ly, lz = 0.0, -21.0, 1.30
            _c, _s = math.cos(math.pi), math.sin(math.pi)
            ox = cx + CS * (lx * _c - ly * _s)
            oy = cy + CS * (lx * _s + ly * _c)
            oz = z + CS * lz
            _t0 = time.time()
            _in = CINT.build(K, M, origin=(ox, oy), rot=math.pi, scale=CS,
                             z=oz, seed=3)
            _mesh = [o for o in _in if getattr(o, "type", "") == "MESH"]
            _lit = [o for o in _in if getattr(o, "type", "") == "LIGHT"]
            _faces = sum(len(o.data.polygons) for o in _mesh)
            print("[capital] castle interior: %d meshes / %d lights / %d faces / "
                  "%.1f s (origin %.2f,%.2f,%.2f)"
                  % (len(_mesh), len(_lit), _faces, time.time() - _t0,
                     ox, oy, oz), flush=True)
            out += _mesh
        except Exception as _exc:
            print("[capital] castle interior FAILED: %r" % (_exc,), flush=True)
    mark_disc(cx, cy, ROCK_R + 6.0)
    return out


def build_cathedral_hd():
    """hd_cathedral on the old close; local +Y = west front, turned city-ward."""
    cx, cy = CATH_C
    out = hd_glue().cathedral(hd_mat(), rng, cx, cy, math.pi, 0.0)
    # interior: the shell is placed rot=pi because *its* local +Y is the west
    # front, so its apse ends up on the city's +Y.  hd_cathedral_int's own frame
    # has +Y = apse already, so it takes rot=0.0 -- passing pi here would swing
    # the apse to the west.  Both crossings land on CATH_C + (0, +7.5); the
    # agent measured the overlap, it is not an estimate.  Its Z_LIFT=1.10 already
    # sits on Z_FLOOR, so the parts arrive at the right height and must not be
    # lifted again.  Lights come back separately because place() drops them.
    if globals().get("HD_INT", {}).get("on"):
        _t0 = time.time()
        try:
            import hd_cathedral_int as CI
            _mesh = CI.build(None, hd_mat(), origin=CATH_C, rot=0.0, scale=1.0, seed=5)
            _lit = CI.interior_lights()
            _faces = sum(len(p.data.polygons) for p in _mesh if p.type == "MESH")
            print("[capital] cathedral interior: %d meshes / %d lights / %d faces / "
                  "%.1f s" % (len(_mesh), len(_lit), _faces, time.time() - _t0), flush=True)
            # lights stay out of the group list: report() reads p.data.polygons and
            # join_group() would drop them anyway, while _purge_orphans only ever
            # deletes meshes, so an unfiled light survives on its own
            out = list(out) + list(_mesh)
        except Exception as _exc:
            print("[capital] cathedral interior FAILED: %r" % (_exc,), flush=True)
    # module footprint is 49.6 x 93.6: reserve the close plus a forecourt, or the
    # row builder packs houses against the portal steps
    mark_rect(cx, cy, 50.0, 94.0, pad=1.0)
    mark_rect(cx, cy - 47.0 - 8.0, 54.0, 16.0, pad=0.5)
    return out


def build_guild_hd():
    cx, cy = GUILD_C
    out = hd_glue().guild_hall(hd_mat(), rng, cx, cy, 0.0, 0.0)
    mark_rect(cx, cy, 23.0, 38.0, pad=0.8)
    return out


def build_market_hd():
    """hd market hall + fountain, keeping the legacy stalls / carts around them."""
    M = hd_mat()
    hy = 34.0
    out = hd_glue().market_hall(M, rng, 0.0, hy, 0.0, 0.0)
    mark_rect(0.0, hy, 44.0, 30.0, pad=0.6)
    out += hd_glue().fountain(M, rng, 0.0, 0.0, 0.0, 0.0)
    mark_disc(0.0, 0.0, 10.6)
    # stalls: the hall's front props reach y = 16.35, so the rows move in to 卤13
    idx = 0
    for row in (-1, 1):
        for i in range(6):
            sx = -22.0 + i * 8.6
            sy = row * 13.0
            if math.hypot(sx, sy) < 9.0:
                continue
            out += B.market_stall("stall_%d" % idx,
                                  T_at(sx, sy, 0.0, rz=math.pi * 0.5 if row > 0 else -math.pi * 0.5),
                                  w=3.4, d=2.3, cloth=MAT["cloth_a"] if idx % 2 else MAT["cloth_b"])
            idx += 1
            mark_rect(sx, sy, 3.6, 2.6)
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.4
        px, py = 30 * math.cos(a), 30 * math.sin(a)
        if i % 2:
            out += B.cart("mkt_cart%d" % i, T_at(px, py, 0.0, rz=a))
        else:
            out += B.barrel_cluster("mkt_bar%d" % i, T_at(px, py, 0.0, rz=a), rng)
        mark_rect(px, py, 3.0, 2.0)
    return out


# ------------------------------------------------------------------ hd city
# The old city lined concentric rings, so every house sat at the same distance
# from the plaza -- exactly the "all buildings on identical rings" look the new
# brief rejects.  In --hd mode the street network and the plots come from
# hd_layout (BSP street cutting, hd_layout.py); capital.py only meshes the
# placements it returns.  The plan is bigger than the time budget allows to
# mesh, so `hd_pick` spends the budget on street frontage (a lined street with a
# hollow courtyard still reads as a city; an empty street does not).
HD_CAP = {"houses": 4200}       # the whole plan; ~0.12 s per hd house
HD_LAY = {"res": None, "picked": None}
# the stock layout packs plots with a 3.6 m setback and 4 m between neighbours,
# which fills 21 % of every block; hd_dense re-tiles the blocks as continuous
# frontage walls instead.  Off by default so the old plan stays reproducible.
HD_DENSE = {"on": False}
HD_PLAN = {"plan2": False}
# set to a filepath (CLI --insurance PATH) to write a copy of the scene just
# before the post-processing tail that killed the v24 run
HD_INS = {"path": None}
# HD_INT is declared near ROCK_TOP, before any function that reads it.


def _plaza_dress(res):
    """Give the three squares a block record so street life can dress them.

    hd_plan2 keeps the plazas as *reserved discs*, not blocks, and
    hd_streetlife only lays out market stalls on blocks whose role is
    "square" / "plaza".  The result was a 96 m and a 78 m paved square with a
    single lonely stall in the corner (V24_cathedral.png, V24_plaza.png):
    the emptiest, most obviously unfinished thing in every wide shot.  Adding
    a synthetic block per square costs nothing -- hd_dense skips these roles,
    so no house can appear on them -- and hands the whole stall-row layout
    over to the module that already knows how to do it.
    """
    blocks = res.get("blocks")
    if not blocks:
        return
    nid = max((b.get("id", 0) for b in blocks), default=0) + 1
    for _c, _r in (((0.0, 0.0), 96.0), (CATH_C, 78.0), (GUILD_C, 52.0)):
        pts = []
        for k in range(32):
            a = 2.0 * math.pi * k / 32.0
            pts.append((_c[0] + _r * math.cos(a), _c[1] + _r * math.sin(a)))
        blocks.append(dict(id=nid, poly=pts, role="square", tier="core",
                           area=math.pi * _r * _r))
        nid += 1


def hd_layout_res():
    if HD_LAY["res"] is None:
        t0 = time.time()
        if HD_PLAN["plan2"]:
            # hd_plan2 plans the roads first (rings + radials + lanes) and cuts
            # blocks on the kerb lines; hd_layout grew streets as random chords,
            # which left blocks that were voronoi leftovers and streets that
            # vanished from the game camera.
            import hd_plan2 as P2
            res = P2.build(
                radius=R_OUTER, seed=SEED,
                reserved=((ROCK_C[0], ROCK_C[1], ROCK_R + 16.0),
                          (CATH_C[0], CATH_C[1], 78.0),
                          (GUILD_C[0], GUILD_C[1], 52.0),
                          (0.0, 0.0, 96.0)))
            HD_LAY["res"] = res
            _plaza_dress(res)
            st = (res.get("city") or {}).get("stats") or {}
            print("[capital] plan2: %d blocks / %d streets in %.1f s"
                  % (st.get("blocks", len(res["blocks"])),
                     st.get("streets", len(res["streets"])),
                     time.time() - t0), flush=True)
            return res
        import hd_layout as L
        specs = L.capital_layout_specs(
            seed=SEED, r_core=R_OUTER - 4.0, radius=R_OUTER,
            plaza=(0.0, 0.0, 84.0),
            castle=(ROCK_C[0], ROCK_C[1], ROCK_R + 12.0),
            cathedral=(CATH_C[0], CATH_C[1], 54.0, 98.0),
            guild=(GUILD_C[0], GUILD_C[1], 26.0, 44.0),
            market_hall=(0.0, 34.0, 48.0, 34.0),
            fountain=(0.0, 0.0, 26.0),
            gates=tuple((gp[0], gp[1]) for (gp, ang) in outer_gaps()),
            outer=True)
        res = L.layout_city(specs)
        HD_LAY["res"] = res
        st = res["stats"]
        print("[capital] hd layout: %d blocks / %d sub-blocks / %d plots "
              "(houses %d, shops %d) in %.1f s"
              % (st["blocks"], st["sub_blocks"], st["buildings"], st["houses"],
                 st["shops"], time.time() - t0), flush=True)
    return HD_LAY["res"]


def poly_slab(name, pts, z, mat):
    """Flat slab from a footprint polygon (block paving / garden floor)."""
    pts = [(float(p[0]), float(p[1])) for p in pts]
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    if a < 0.0:
        pts.reverse()
    verts = [(p[0], p[1], z) for p in pts]
    faces = [(0, i, i + 1) for i in range(1, len(pts) - 1)]
    ob = K.mesh_obj(name, verts, faces)
    K.assign(ob, mat)
    return ob


def _spread(seq, n):
    """n items out of seq, evenly spaced: keeps street rhythm, no clumps."""
    if n >= len(seq):
        return list(seq)
    if n <= 0:
        return []
    step = len(seq) / float(n)
    return [seq[int(i * step)] for i in range(n)]


def _reserved(x, y, pad=7.0):
    """True if (x, y) sits inside a landmark the capital builds by hand.

    hd_layout generates its own plaza and landmark sites, which do not line up
    with the castle/cathedral/market/gate positions this file has always used;
    without this the engine drops a shop in the middle of the market square.
    """
    S = CITY_SCALE
    if abs(x) < (44.0 + pad) * S and abs(y) < (44.0 + pad) * S:  # plaza + fountain
        return True
    if abs(x) < (26.0 + pad) * S and (16.0 - pad) * S < y < (52.0 + pad) * S:
        return True                                          # market hall
    # the cathedral is 50 x 94 m, so the old 62 m disc reserved twice its own
    # area in lawn; a rectangle keeps the clearance where the walls are and
    # hands the plots back where the building is not
    cxc, cyc = CATH_C
    if abs(x - cxc) < (27.0 + pad) * S and abs(y - cyc) < (49.0 + pad) * S:
        return True
    gxc, gyc = GUILD_C
    if abs(x - gxc) < (11.5 + pad) * S and abs(y - gyc) < (16.0 + pad) * S:
        return True
    if math.hypot(x - ROCK_C[0], y - ROCK_C[1]) < ROCK_R + (3.0 + pad) * S:
        return True
    if abs(x) < (12.0 + pad) * S and (118.0 - pad) * S < y < (162.0 + pad) * S:
        return True                                          # castle ramp
    for (gp, ang) in outer_gaps():
        if math.hypot(x - gp[0], y - gp[1]) < (26.0 + pad) * S:
            return True
        # the avenue: every gate is the mouth of a road into the city, and a
        # gate that opens onto a row of house backs is the one thing that makes
        # a walled town read as fake
        rr = math.hypot(gp[0], gp[1]) or 1.0
        ux, uy = gp[0] / rr, gp[1] / rr
        along = x * ux + y * uy                      # metres from the centre
        if rr * 0.52 < along < rr - 30.0:
            perp = abs(-x * uy + y * ux)
            if perp < 6.5 + pad * 0.28:
                return True
    return False


def _ring_no(p):
    """Ring index of a placement; hd_layout may hand back an int or a word."""
    r = p.get("ring", 0)
    try:
        return int(r)
    except (TypeError, ValueError):
        s = str(r).lower()
        return 0 if ("front" in s or s in ("0", "", "street")) else 1


def hd_pick():
    if HD_LAY["picked"] is not None:
        return HD_LAY["picked"]
    res = hd_layout_res()
    if HD_DENSE["on"]:
        import hd_dense as DN
        foot = {}
        try:
            import hd_shops as HS
            foot = dict(HS.FOOTPRINT)
        except Exception:
            foot = {}
        t0 = time.time()
        try:
            import hd_shops as _HS
            _HS.YARD_FENCE = False        # no rail fence across the carriageway
        except Exception:
            pass
        pl = DN.placements(res, foot_override=foot, seed=SEED, cov_max=0.36)
        n0 = len(pl)
        pl = [p for p in pl if not _reserved(p["x"], p["y"], 3.0)]
        pl = [p for p in pl
              if math.hypot(p["x"], p["y"]) < R_OUTER * 0.985]
        HD_LAY["picked"] = pl
        n_c = sum(1 for p in pl if p.get("source") == "shop")
        print("[capital] hd_dense: %d placements (%d shops), %d dropped by "
              "reservations/wall, %.1f s"
              % (len(pl), n_c, n0 - len(pl), time.time() - t0), flush=True)
        return pl
    pl = [p for p in res["placements"]
          if p["source"] == "house" or p["source"] == "shop"]
    pl = [p for p in pl if not _reserved(p["x"], p["y"], 6.0)]
    # nothing may stand outside the outer curtain: the engine plans its own
    # 636 m outline and a handful of plots land past the wall line
    pl = [p for p in pl
          if math.hypot(p["x"], p["y"]) < R_OUTER * 0.958]
    cap = int(HD_CAP["houses"])
    # take whole blocks, nearest the centre first with a ragged jitter: an
    # evenly sprinkled subset is what makes a plan read as "houses dropped on a
    # lawn", a dense core with a ragged edge reads as a city
    by_block = {}
    for p in pl:
        by_block.setdefault(str(p.get("block")), []).append(p)
    jr = random.Random(SEED + 5)

    def _bkey(item):
        ps = item[1]
        cx = sum(q["x"] for q in ps) / float(len(ps))
        cy = sum(q["y"] for q in ps) / float(len(ps))
        return math.hypot(cx, cy) + jr.uniform(-70.0, 70.0)

    blocks = sorted(by_block.items(), key=_bkey)
    picked = []
    shop_cap = int(cap * 0.30)
    n_shop = 0
    # Walk every block, not just the nearest ones until the budget runs out.
    # Whole-block-nearest-first left the outer half of the town an empty field
    # with a diagonal streak of houses down the middle; the density has to fall
    # off smoothly instead, so each block keeps a fraction of its plots:
    # ~100 % inside 0.45 R, ~42 % at the wall, with a ragged per-block jitter.
    dens = []
    for _bid, ps in blocks:
        cx = sum(q["x"] for q in ps) / float(len(ps))
        cy = sum(q["y"] for q in ps) / float(len(ps))
        u = min(1.0, math.hypot(cx, cy) / (R_OUTER * 0.98))
        keep = 1.0 if u < 0.45 else 1.0 - 0.62 * ((u - 0.45) / 0.55) ** 1.15
        keep = max(0.16, keep * jr.uniform(0.78, 1.12))
        dens.append((_bid, ps, keep))
    target = sum(min(len(ps), int(round(len(ps) * k))) for _b, ps, k in dens)
    scale = min(1.0, float(cap) / float(max(1, target)))
    for _bid, ps, keep in dens:
        room = cap - len(picked)
        if room <= 0:
            break
        want = min(len(ps), int(round(len(ps) * keep * scale)))
        if want <= 0:
            continue
        take = []
        for p in ps:
            if len(take) >= min(want, room):
                break
            if p.get("source") == "shop":
                # a city that is nothing but shop fronts reads as a market, and
                # the engine over-produces them
                if n_shop >= shop_cap:
                    continue
                n_shop += 1
            take.append(p)
        picked.extend(take)
    if len(picked) < cap:                        # nothing left in the blocks
        seen = set(id(p) for p in picked)
        picked += [p for _b, ps in blocks for p in ps
                   if id(p) not in seen][:cap - len(picked)]
    HD_LAY["picked"] = picked
    n_c = sum(1 for p in picked if p.get("source") == "shop")
    print("[capital] hd build budget: %d of %d plots (%d shops, %d blocks)"
          % (len(picked), len(pl), n_c, len(blocks)), flush=True)
    return picked


def _built_blocks(picked, res):
    """Blocks that are dense enough in the build to be paved as town, not garden."""
    tot, hit = {}, {}
    # hd_plan2 has no plot list of its own: the dense packer is the plan, and
    # every block it leaves empty is a square / yard and must stay unsealed
    src = res.get("placements") or ()
    for p in src:
        b = str(p.get("block"))
        tot[b] = tot.get(b, 0) + 1
    for p in picked:
        b = str(p.get("block"))
        hit[b] = hit.get(b, 0) + 1
    return set(b for b in hit if hit[b] >= 0.30 * max(1, tot.get(b, 1)))


def ground_hd():
    """Paving for the layout city: street = the gap between two block slabs."""
    out = [disc("ground_town", R_OUTER + 2.0, 0.0, MAT["town_ground"], seg=200)]
    # the outer plate is split along the two river banks and the channel is
    # walled, watered and bridged: the harbour has always been built, but its
    # river was buried under this plate
    try:
        import hd_river as HR
        out += HR.build(K, MAT, outer_gaps())
        print("[capital] river: channel at y=%.0f w=%.0f" % (HR.RIVER_Y, HR.RIVER_W),
              flush=True)
    except Exception as exc:
        print("[capital] river: %s: %s" % (type(exc).__name__, exc), flush=True)
        out.append(disc("ground_outer", 980.0, -0.35, MAT["grass"], seg=150))
    res = hd_layout_res()
    town = _built_blocks(hd_pick(), res)
    # cobbles only where people walk: a paved disc under the whole town reads as
    # "houses dropped on a car park" from the air, and the street corridors are
    # what actually carries the eye
    # a crowned cobble carriageway with a worn centre channel, following each
    # street's own polyline; the old version laid one flat box per street between
    # its two end points, which cut every bend and left the town looking paved
    # with pale rectangles
    import hd_street as HS
    out += HS.build(K, MAT, res.get("streets") or ())
    for i, b in enumerate(res["blocks"]):
        pts = b.get("poly") or b.get("polygon") or b.get("pts")
        if not pts:
            continue
        # inside the wall every block is walked on: a block the build budget did
        # not reach must read as an empty yard, not as a lawn in the middle of town
        cx = sum(p[0] for p in pts) / float(len(pts))
        cy = sum(p[1] for p in pts) / float(len(pts))
        inside = math.hypot(cx, cy) < R_OUTER - 8.0
        if str(b.get("id")) in town:
            mat = MAT["town_ground"]
        elif inside:
            mat = MAT["town_ground"]
        else:
            mat = MAT["grass"]
        out.append(poly_slab("blk_%d" % i, pts, 0.09, mat))
    # The market square used to be a 78 m box of flagstones, which left a ring
    # of bare dirt between the paving and the reserved disc (r = 96 m) and read
    # from the air as a bald patch at the centre of the city.  Pave the whole
    # reserved disc instead, plus the cathedral close and the guild forecourt:
    # one n-gon each, so the flagstone material tiles in object space at its
    # real 0.5 m joint pitch instead of being stretched.
    for _name, _c, _r in (("plaza_centre", (0.0, 0.0), 96.0),
                          ("plaza_cath", CATH_C, 78.0),
                          ("plaza_guild", GUILD_C, 52.0)):
        out.append(disc(_name, _r, 0.10, MAT["flag"], seg=160,
                        cx=_c[0], cy=_c[1]))
        # a kerb so the square reads as a built edge and not a decal
        _nk = 48
        for _i in range(_nk):
            _a = 2.0 * math.pi * _i / _nk
            out.append(box("kerb_%s_%d" % (_name, _i),
                           T_at(_c[0] + (_r + 0.30) * math.cos(_a),
                                _c[1] + (_r + 0.30) * math.sin(_a), 0.14,
                                rz=_a),
                           (2.0 * math.pi * _r / _nk * 1.06, 0.62, 0.16),
                           MAT["stone"]))

    hr = random.Random(SEED + 11)
    for i in range(22):
        a = 2 * math.pi * i / 22 + hr.uniform(-0.08, 0.08)
        rad = hr.uniform(R_OUTER + 240.0, 930.0)
        px, py = rad * math.cos(a), rad * math.sin(a)
        if py < RIVER_Y + RIVER_W + 30.0:
            continue
        rr = hr.uniform(70.0, 150.0)
        out.append(sphere("hill%d" % i, T_at(px, py, -2.0), rr,
                          MAT["hill"] if i % 2 else MAT["hill_dark"],
                          seg=20, ring=10, squash=hr.uniform(26.0, 58.0) / rr))
    return out


def _house_kind(kind):
    """Map a layout kind ("house_stone", "stone", ...) onto hd_houses' 8 kinds."""
    k = str(kind or "")
    if k.startswith("house_"):
        k = k[6:]
    return k if k in ("timber", "stone", "shop", "inn", "manor", "tower",
                      "warehouse", "craft") else "timber"


def _house_dims(kind):
    """(w, d, floors) for a layout kind; the layout module knows the real ones."""
    try:
        import hd_layout as L
        w, d, nf = L.house_dims(kind)
        return float(w), float(d), int(nf)
    except Exception:
        order = (0, 2, 1, 2, 3, 2, 0, 1)
        k = _house_kind(kind)
        idx = ("timber", "stone", "shop", "inn", "manor", "tower",
               "warehouse", "craft").index(k)
        return (7.0, 8.5, (2, 2, 3, 2, 3, 2, 1, 2)[order[idx]])


def build_city_hd():
    G = hd_glue()
    M = hd_mat()
    picked = hd_pick()
    by_block = {}
    for p in picked:
        by_block.setdefault(str(p.get("block")), []).append(p)
    out = []
    t0 = time.time()
    n_h = n_s = n_fail = 0
    for k, bi in enumerate(sorted(by_block)):
        # merge every CHUNK buildings instead of once per block: a live part
        # count in the thousands makes every bpy.data.objects.new() scan for a
        # free name, which is what turned 0.1 s/house into 3 s/house
        CHUNK = 3
        chunks = []
        buf = []
        t_b = time.time()
        for i, p in enumerate(by_block[bi]):
            if p["source"] == "shop":
                ob = G.shop(p["kind"], M, rng, p["x"], p["y"], p["yaw"], p["z"])
                n_s += 1 if ob else 0
            else:
                # hd_layout may describe a house either way (wall size + floors,
                # or just a kind that maps to a stock footprint)
                hw, hd_, hf = p.get("w"), p.get("d"), p.get("floors")
                if hw is None or hd_ is None:
                    hw, hd_, hf0 = _house_dims(p["kind"])
                    hf = hf0 if hf is None else hf
                sc = float(p.get("scale") or 1.0)
                # one roof/wall tint per block, with a slow drift across the
                # town: a colour that changes every house reads as confetti, and
                # one colour everywhere reads as a monopoly
                vv = (abs(int(p["x"] * 0.028)) * 7 + abs(int(p["y"] * 0.031)) * 3
                      + sum(bytearray(str(p.get("block")).encode())) % 5) % 8
                ob = G.house(M, rng, p["x"], p["y"], p["yaw"],
                             max(4.6, float(hw) * sc - 0.5), float(hd_) * sc,
                             int(hf), _house_kind(p["kind"]),
                             p.get("variant") or "eaves",
                             variant=vv, back=_ring_no(p) >= 1)
                n_h += 1 if ob else 0
            if ob:
                # hd_houses/hd_shops hand back a LIST of ~260 part objects, not
                # one object: flatten it or the merge below silently gets no
                # meshes, leaves 250 k orphans in the scene and everything crawls
                if isinstance(ob, (list, tuple)):
                    buf.extend(ob)
                else:
                    buf.append(ob)
            else:
                n_fail += 1
            if len(buf) >= CHUNK or i == len(by_block[bi]) - 1:
                m = G.merge_objects("c%d_%d" % (k, i), buf)
                if m is not None:
                    chunks.append(m)
                buf = []
        t_m = time.time()
        # one object per block in the end: 260 objects per house would be 1 M
        # objects for the full plan and every render pass would pay for it
        ob = chunks[0] if len(chunks) == 1 else G.merge_objects("city_blk%02d" % k, chunks)
        if ob is not None:
            out.append(ob)
        print("[capital] hd city blk %d/%d  %d buildings  build %.1f s  merge %.1f s"
              "  objs %d  meshes %d"
              % (k + 1, len(by_block), len(by_block[bi]), t_m - t_b, time.time() - t_m,
                 len(bpy.data.objects), len(bpy.data.meshes)),
              flush=True)
    o, f, t = hd_glue().stats(out)
    print("[capital] hd city done: %d buildings (houses %d / shops %d / failed %d)"
          " objects=%d faces=%d tris=%d in %.0f s"
          % (n_h + n_s, n_h, n_s, n_fail, o, f, t, time.time() - t0), flush=True)
    return out


def city_trees():
    """Trees in the town, not just on the fields outside it.

    An all-stone city reads as a car park that has been swept; a few crowns over
    the roofs are what make the scale legible from the air.  Trees are kept
    where they cannot stand in a doorway: the plaza edge, the avenue verges,
    courtyard centres and the castle rim.
    """
    G = hd_glue()
    tr = random.Random(SEED + 101)
    out = []
    pal = [("broad", 0.42), ("poplar", 0.46), ("conifer", 0.04), ("dead", 0.08)]

    def pick_species():
        r = tr.random()
        acc = 0.0
        for sp, w in pal:
            acc += w
            if r <= acc:
                return sp
        return "broad"

    def put(x, y, kind="tree", s=1.0, z=0.0):
        # hd_nature's builders get slower with every call in the same session
        # (0.04 s for the first bush, 24 s for the twenty-fourth), so the
        # integration layer uses medbuild's tree: same tower of meshes, constant
        # cost, and it is the code the suburbs already ship
        h = {"tree": tr.uniform(5.2, 7.6), "bush": tr.uniform(1.1, 2.0),
             "tuft": tr.uniform(0.4, 0.8)}.get(kind, 6.4) * s
        parts = B.tree("tree_%d" % len(out),
                       T_at(x, y, z, rz=tr.uniform(0.0, 6.28)),
                       h=h, rng=tr, species=pick_species(),
                       leaf_mat=MAT["leaf"] if tr.random() < 0.66 else MAT["leaf_dark"])
        out.extend(parts)

    # plaza edge: eight crowned trees behind the paving
    for i in range(8):
        a = 2 * math.pi * i / 8.0 + math.pi / 8.0
        put(54.0 * math.cos(a), 54.0 * math.sin(a), "tree", tr.uniform(0.9, 1.15))
    # avenues: a row down each verge, out past the ring of houses
    for gp, ang in outer_gaps():
        ux, uy = math.cos(ang), math.sin(ang)
        r_gate = math.hypot(gp[0], gp[1])
        t = r_gate * 0.55
        while t < r_gate - 40.0:
            for side in (-1.0, 1.0):
                px = ux * t - uy * 9.0 * side
                py = uy * t + ux * 9.0 * side
                if not _reserved(px, py, -2.0):
                    put(px, py, "tree", tr.uniform(0.8, 1.05))
            t += 38.0
    # courtyard centres: the inside of a block is the one place a tree is safe
    res = hd_layout_res()
    picked = HD_LAY.get("picked") or []
    for b in res.get("blocks") or ():
        if b.get("open"):
            continue
        pts = b.get("poly") or b.get("polygon") or b.get("pts")
        if not pts:
            continue
        cx = sum(p[0] for p in pts) / float(len(pts))
        cy = sum(p[1] for p in pts) / float(len(pts))
        if math.hypot(cx, cy) > R_OUTER - 40.0 or _reserved(cx, cy, 0.0):
            continue
        if tr.random() > 0.30:
            continue
        near = min((math.hypot(p["x"] - cx, p["y"] - cy) for p in picked), default=99.0)
        if near < 9.0:
            continue
        put(cx + tr.uniform(-3, 3), cy + tr.uniform(-3, 3),
            "tree", tr.uniform(0.8, 1.1))
    # castle rim: scrub on the rock, where nothing else can grow
    for i in range(16):
        a = 2 * math.pi * i / 16.0 + tr.uniform(-0.1, 0.1)
        rad = ROCK_R * 0.74 + tr.uniform(-2.0, 3.0)
        put(ROCK_C[0] + rad * math.cos(a), ROCK_C[1] + rad * math.sin(a),
            "bush" if i % 3 else "tree", tr.uniform(0.7, 1.0), ROCK_TOP + 0.2)
    o, f, t = hd_glue().stats(out)
    merged = hd_glue().merge_objects("city_trees", out)
    print("[capital] hd trees: %d picks objects=%d faces=%d tris=%d"
          % (len(out), o, f, t), flush=True)
    return [merged] if merged is not None else out


STREET_BUDGET = 3950000


def street_life():
    """Everything that turns a row of houses into a street people live in.

    hd_streetlife owns the vocabulary (barrels, carts, stalls, awnings, signs,
    laundry, wells, wattle fences, kitchen gardens, a little crowd) and batches
    it into one mesh per 56 m cell, so the object count stays flat.  It also
    lays the cobble pads and garden beds: the bare beige plate of a block
    interior was the single largest dead area in every game-camera frame.
    """
    t0 = time.time()
    units = hd_pick()
    res = hd_layout_res()
    try:
        import hd_streetlife as SL
        objs = SL.build(hd_mat(), units, res, seed=SEED, density=1.0,
                        cell=56.0, budget=STREET_BUDGET)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print("[capital] streetlife FAILED:", exc, flush=True)
        return []
    st = {}
    try:
        st = SL.stats()
    except Exception:
        pass
    print("[capital] streetlife: %s props / %s tris / %d objects in %.1f s"
          % (st.get("props", "?"), st.get("faces", "?"), len(objs),
             time.time() - t0), flush=True)
    return objs


def wall_row():
    """Houses with their backs to the curtain, fronts on the ring street.

    The plot engine stops short of the wall, which left a 30..40 m band of bare
    ground inside the enceinte -- the one ring of a medieval town that is never
    empty.  Placed straight against the polygon so they follow its 20 sides.
    """
    G = hd_glue()
    M = hd_mat()
    wr = random.Random(SEED + 131)
    pts = outer_ring_pts()
    out, buf = [], []
    n = 0
    # the plot engine's outer blocks reach the same band: a house dropped on a
    # house is worse than a gap, so keep a coarse bucket of what is already built
    grid = {}
    for q in HD_LAY.get("picked") or ():
        grid.setdefault((int(q["x"] // 14.0), int(q["y"] // 14.0)), []).append(q)

    def _blocked(x, y):
        gx, gy = int(x // 14.0), int(y // 14.0)
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for q in grid.get((ix, iy), ()):
                    if math.hypot(q["x"] - x, q["y"] - y) < 9.5:
                        return True
        return False
    for i in range(len(pts)):
        p0, p1 = pts[i], pts[(i + 1) % len(pts)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 6.0:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        if math.hypot(mx + nx * 20.0, my + ny * 20.0) > math.hypot(mx, my):
            nx, ny = -nx, -ny                    # n must point at the town
        t = 11.0
        while t < L - 11.0:
            w = wr.uniform(5.8, 7.8)
            d = wr.uniform(6.4, 8.2)
            if wr.random() < 0.16:               # a yard, not a wall of houses
                t += w + 8.0
                continue
            cx = p0[0] + ux * t + nx * (7.5 + d * 0.5)
            cy = p0[1] + uy * t + ny * (7.5 + d * 0.5)
            if math.hypot(cx, cy) > R_OUTER - 4.0 or _reserved(cx, cy, 2.0):
                t += w + 1.2
                continue
            if _blocked(cx, cy):
                t += w + 1.2
                continue
            yaw = math.atan2(-nx, ny)            # local +Y -> (nx, ny), town side
            ob = G.house(M, wr, cx, cy, yaw, w, d,
                         2 if wr.random() < 0.72 else 3,
                         wr.choice(("timber", "timber", "craft", "stone", "shop")),
                         "eaves", variant=int(abs(t) * 0.7) % 5)
            if isinstance(ob, (list, tuple)):
                buf.extend(ob)
            elif ob:
                buf.append(ob)
            n += 1
            if len(buf) >= 9000:
                m = G.merge_objects("wallrow_%d" % len(out), buf)
                if m is not None:
                    out.append(m)
                buf = []
            t += w + wr.uniform(0.5, 2.2)
    m = G.merge_objects("wallrow_tail", buf) if buf else None
    if m is not None:
        out.append(m)
    print("[capital] wall row: %d houses, %d objects" % (n, len(out)), flush=True)
    return out


# ------------------------------------------------------------------ assembly
def _alive(ob):
    """True while the object still exists.  A removed StructRNA raises on any
    attribute access, so `getattr(ob, "name", "")` is not safe either."""
    try:
        ob.name
    except ReferenceError:
        return False
    return True


def _prune_dead(groups):
    """Forget objects that another module deleted.

    hd_landscape.strip_old() removes the hill spheres and the old outer plate,
    and those are exactly what ground_hd() put in groups["ground"]; a stale
    StructRNA then blows up every later pass over the groups.
    """
    n = 0
    for k, v in list(groups.items()):
        if isinstance(v, (list, tuple)):
            keep = [p for p in v if _alive(p)]
            n += len(v) - len(keep)
            groups[k] = keep
    if n:
        print("[capital] pruned %d objects that a builder deleted" % n, flush=True)
    return n


def _purge_orphans(groups):
    """Drop geometry a builder left behind at the world origin.

    Some hd helpers (hd_gate's ashlar block, at least) create the object and
    hand back a copy, so the original stays linked at (0, 0) -- in the city it
    reads as a 12 m pillar standing in the middle of the market square.
    Everything a builder returns lives in `groups`; anything else parked inside
    the plaza is debris.
    """
    keep = set()
    for v in groups.values():
        for p in flatten([v]):
            if not _alive(p):
                continue
            keep.add(p.name)
    dead = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.name in keep:
            continue
        me = ob.data
        if not me or not me.vertices or len(me.vertices) > 4000:
            continue
        co = [ob.matrix_world @ v.co for v in me.vertices]
        cx = sum(c.x for c in co) / len(co)
        cy = sum(c.y for c in co) / len(co)
        if abs(cx) < 46.0 and abs(cy) < 46.0:
            dead.append(ob)
    for ob in dead:
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    if dead:
        print("[capital] purged %d orphan objects from the plaza" % len(dead),
              flush=True)
    return len(dead)


def _finish_materials():
    """Rebuild the roof covers.  This has to run last: the house and landmark
    modules create their own `hu_roof_*` / `tile_*` materials while they build,
    and those were flat colour with a bit of noise -- while roofs are the
    largest surface in every 2.5D frame (52 deg from 34 m, the front three
    houses fill the picture)."""
    # Weathering is applied to MAT before the city exists, so every material a
    # builder mints later (hd_plaster_c*, hd_tile_terra*, hu_*, mkt_*) came out
    # of the oven clean and paper white.  Sweep the whole datablock list here:
    # hd_surface skips what it has already aged and skips roofs / ground.
    try:
        import hd_surface as SFC
        SFC.apply_weathering({m.name: m for m in bpy.data.materials})
    except Exception as exc:
        print("[capital] weathering sweep: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    try:
        import hd_roof as RF
        RF.rebuild(verbose=True)
    except Exception as exc:
        print("[capital] roofs: %s: %s" % (type(exc).__name__, exc), flush=True)


def build(stage="full"):
    K.reset_scene()
    init_mats()
    # ground materials are rebuilt from scratch: medkit's five paving materials
    # all rendered as the same flat beige (measured in look/matlab.py), and the
    # ground is half of every 2.5D frame
    try:
        import hd_paving as PV
        PV.rebuild(MAT)
    except Exception as exc:
        print("[capital] paving: %s: %s" % (type(exc).__name__, exc), flush=True)
    # weathering: nine physical passes over every stone / plaster / timber
    # material (hd_surface.py had never been called from anywhere)
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT)
    except Exception as exc:
        print("[capital] weathering: %s: %s" % (type(exc).__name__, exc), flush=True)
    groups = {}
    groups["ground"] = build_ground()
    if HD["on"]:
        # the hd modules take `rng`, but a 60k-line build must be reproducible
        # even if a helper somewhere reaches for the global generator
        random.seed(SEED)
        # CITY FIRST.  bpy.data.objects.new() scans for a free name whenever the
        # name is taken, so the cost of every part is O(live objects): with the
        # 30 k-object landmark set already in the file a house costs 3 s instead
        # of 0.05 s.  The plot engine already reserves the landmark footprints,
        # so nothing here depends on the occupancy grid being marked first.
        if stage in ("full", "city"):
            groups["city"] = build_city_hd()
            groups["wallrow"] = wall_row()
            groups["trees"] = city_trees()
            # street life belongs to the town, not to the far field, so it is
            # built here and shows up in a --stage city build too
            groups["props"] = street_life()
        # a ground + houses only build, for judging the town itself without
        # waiting for the landmarks (~4 min instead of ~13)
        if stage == "city":
            _finish_materials()
            return groups
        # The city is the expensive half (~14 of ~20 minutes) and everything
        # after it is cheap.  Saving here means a crash in a landmark module
        # still leaves a usable file: the last two runs died 13 minutes in and
        # produced nothing at all.  --stage full only, so the city-only path
        # keeps its own --save behaviour.
        if HD_INS.get("path"):
            try:
                bpy.ops.wm.save_as_mainfile(filepath=HD_INS["path"], copy=True)
                print("[capital] city checkpoint -> %s" % HD_INS["path"], flush=True)
            except Exception as _exc:
                print("[capital] city checkpoint FAILED: %r" % (_exc,), flush=True)
        # the plot engine fills the whole R_OUTER outline, so a 300 m ring would
        # run through the middle of the town: the polygon enceinte is the wall,
        # and its four openings are the city gates
        groups["walls"] = []
        groups["gates"] = []
        # the far town: the core is only the old enceinte; the capital kept
        # growing, so the outer polygon wall, its four gates, the roads out of
        # the core gates, farmland in the ring and a hamlet at each exit all
        # have to exist before the town stops reading as an island
        _G = hd_glue()
        ow = outer_wall()
        m = _G.merge_objects("outer_wall", ow)
        groups["outer"] = [m] if m is not None else ow
        og = outer_gates()
        m = _G.merge_objects("outer_gates", og)
        groups["ogates"] = [m] if m is not None else og
        groups["roads"] = radial_roads()
        groups["fields"] = ring_fields()
        _picked = hd_pick()
        wl = city_wells(_picked)
        m = _G.merge_objects("wells", wl)
        groups["wells"] = [m] if m is not None else wl
        groups["burbs"] = suburbs_hd() if stage == "full" else []
        # the far field: a 7.2 km heightfield with mountain ranges, farmland,
        # roads and hamlets, replacing the flat olive plate and the 22 squashed
        # spheres that made every wide shot read as a diorama on a table
        if stage == "full":
            try:
                import hd_landscape as LS
                LS.FLAT_IN = R_OUTER + 60.0
                LS.FLAT_OUT = R_OUTER + 190.0
                LS.strip_old()
                info = LS.build(MAT, res=20.0, seed=1337)
                groups["land"] = info.get("objects") or []
                print("[capital] landscape: %s objects %s faces %s tris %.1f s"
                      % (info.get("count"), info.get("faces"),
                         info.get("tris"), info.get("seconds", 0.0)), flush=True)
                _prune_dead(groups)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                print("[capital] landscape FAILED:", exc, flush=True)
                groups["land"] = []
            # The town is a 947 m disc at z=0 and the terrain is flat out to
            # 1007 m, so the seam between them is grass-to-grass: from the air
            # it reads as the edge of a green plate, which is the single most
            # "unfinished world" cue left in the wide shots.  hd_rock lays a
            # broken rock bank on that seam -- outcrops dying into the ground on
            # the inside, a 6-15 m crest just behind the outer wall, bedding
            # steps and a scree fan on the outside -- and opens it up wherever
            # a road leaves, so the four avenues are not walled in twice.
            try:
                import hd_rock as RK
                _t0 = time.time()
                _rim = RK.cliff_ring(K=K, MAT=MAT, r=R_OUTER, seed=23, gates=outer_gaps())
                groups["rim"] = [p for p in (_rim or []) if getattr(p, "type", "") == "MESH"]
                _rf = sum(len(p.data.polygons) for p in groups["rim"])
                print("[capital] rim: %d objects / %d faces / %.1f s"
                      % (len(groups["rim"]), _rf, time.time() - _t0), flush=True)
            except Exception as exc:
                groups["rim"] = []
                print("[capital] rim FAILED: %r" % (exc,), flush=True)
        # the inner ring is dropped: it runs through the castle rock (55 m from
        # its centre against a 82 m footprint) and it would slice the new 93.6 m
        # cathedral; the hd castle brings its own curtain wall anyway
        groups["inner"] = []
        groups["castle"] = build_castle_hd()
        groups["cathedral"] = build_cathedral_hd()
        groups["guild"] = build_guild_hd()
        groups["market"] = build_market_hd()
        print("[capital] hd: 4 gatehouses, castle, cathedral, guild hall, market",
              flush=True)
        _purge_orphans(groups)
    else:
        groups["walls"] = wall_ring("outer_wall", R_WALL, WALL_H, WALL_T, MAT["stone"], seg=220)
        rw = random.Random(SEED + 3)
        # buttresses break the "necklace of beads" read of an evenly spaced ring
        for i in range(72):
            a = 2 * math.pi * i / 72.0 + math.pi / 72.0
            groups["walls"].append(box("wt_butt%d" % i,
                                       T_at((R_WALL + 1.15) * math.cos(a), (R_WALL + 1.15) * math.sin(a),
                                            WALL_H * 0.46, rz=a),
                                       (3.2, 2.6, WALL_H * 0.92), MAT["stone"], bev=0.05))
        for i in range(16):
            a = 2 * math.pi * i / 16 + math.pi / 16
            if i % 4 == 0:
                continue
            rr = 7.2 + rw.uniform(-1.5, 1.8)
            hh = WALL_H + 6.0 + rw.uniform(-2.5, 5.0)
            groups["walls"] += tower("wt%d" % i, (R_WALL - 0.6) * math.cos(a),
                                     (R_WALL - 0.6) * math.sin(a), r=rr, h=hh)
        gates = []
        for i in range(4):
            gates += gatehouse("gate%d" % i, math.pi * 0.5 * i)
        groups["gates"] = gates
        groups["inner"] = wall_ring("inner_wall", R_INNER, INNER_H, 2.0, MAT["stone_warm"], seg=140)
        for i in range(6):
            a = 2 * math.pi * i / 6 + math.pi / 6
            groups["inner"] += tower("itw%d" % i, R_INNER * math.cos(a), R_INNER * math.sin(a),
                                     r=5.0, h=12.0, mat=MAT["stone_warm"])
        groups["castle"] = build_castle()
        groups["cathedral"] = build_cathedral()
        groups["guild"] = build_guild_hall()
        groups["market"] = build_market()
    groups["harbour"] = build_harbour()
    if stage == "full":
        if not HD["on"]:
            groups["city"] = build_lower_city()
        groups["suburbs"] = [] if HD["on"] else build_suburbs()
    else:
        groups["city"] = []
        groups["suburbs"] = []
    _finish_materials()
    if HD_INS["path"]:
        # crash insurance: the v24 build ran 25 minutes, then died in
        # _purge_orphans on a StructRNA reference and lost everything because
        # --save had not run yet.  Writing a copy here costs ~40 s and turns a
        # late crash from "lose the run" into "reload and re-render".
        try:
            bpy.ops.wm.save_as_mainfile(filepath=HD_INS["path"], copy=True)
            print("[capital] insurance copy -> %s" % HD_INS["path"], flush=True)
        except Exception as exc:
            print("[capital] insurance copy failed: %s: %s"
                  % (type(exc).__name__, exc), flush=True)
    return groups


def flatten(seq):
    out = []
    for it in seq or ():
        if isinstance(it, (list, tuple)):
            out += flatten(it)
        elif it is not None:
            out.append(it)
    return out


def report(groups):
    tot_o = tot_t = 0
    for k, parts in groups.items():
        parts = flatten(parts)
        groups[k] = parts
        t = 0
        for p in parts:
            me = p.data
            t += len(me.polygons) if me else 0
        tot_o += len(parts)
        tot_t += t
        print("[capital] %-10s objects=%-6d faces=%d" % (k, len(parts), t))
    print("[capital] TOTAL objects=%d faces=%d" % (tot_o, tot_t))
    return tot_o, tot_t


_D45 = math.radians(45.0)
SHOTS = (
    ("ars_overview", (430.0, -560.0, 330.0), (0.0, 20.0, 0.0), 34.0),
    ("ars_castle", (150.0, -60.0, 120.0), (-10.0, 190.0, 40.0), 40.0),
    # eye level, looking down the south avenue towards the gate: this is the shot
    # that has to prove street frontages. The old camera sat at radius 152, i.e.
    # inside the inner curtain wall, so the frame was solid masonry.
    ("ars_street", (0.0, -168.0, 1.75), (0.0, -262.0, 2.6), 26.0),
    ("ars_street2", (84.8, 84.8, 1.75), (126.0, 126.0, 2.8), 26.0),
    ("ars_plaza", (36.0, -34.0, 6.2), (0.0, 20.0, 7.5), 34.0),
    ("ars_market", (60.0, -60.0, 34.0), (0.0, 10.0, 4.0), 38.0),
    ("ars_harbour", (-40.0, -250.0, 26.0), (10.0, -350.0, 2.0), 40.0),
    ("ars_gate", (10.0, -390.0, 12.0), (0.0, -300.0, 12.0), 42.0),
)

# --hd renders its own set: same 16:9 frame, aimed at the new landmarks.
HD_SHOTS = (
    # the gate is shot from inside: south of the wall the river + quay wall sit
    # only 26 m out, so an outside camera cannot see the gatehouse at all
    ("b5_gate_in", (6.0, 545.0, 1.7), (0.0, 640.0, 13.0), 32.0),
    ("b5_castle", (95.0, 40.0, 62.0), (0.0, 196.0, 44.0), 40.0),
    ("b5_cathedral", (-238.0, -90.0, 25.0), (-152.0, 40.0, 36.0), 22.0),
    ("b5_plaza", (0.0, -34.0, 11.0), (0.0, 18.0, 10.0), 30.0),
    # a ring-road street: the first rows to fill are always the innermost ring
    ("b5_street", (51.0, 51.0, 1.7), (14.0, 72.0, 3.0), 20.0),
    ("b5_overview", (900.0, -1150.0, 600.0), (0.0, -20.0, 10.0), 34.0),
    # the outer town: enceinte + the hamlet outside the east gate
    ("b5_outer", (330.0, -260.0, 210.0), (600.0, 90.0, 16.0), 30.0),
    ("b5_suburb", (626.0, -96.0, 24.0), (764.0, 4.0, 5.0), 30.0),
)


def hd_shots():
    """HD shot list with the street shot derived from the actual layout.

    A hand-placed eye point is a gamble: with the new plot engine the camera
    would end up inside somebody's parlour.  Instead stand 6 m off a real
    facade, on the street side, and look down the street past it.
    """
    shots = list(HD_SHOTS)
    picked = [p for p in (HD_LAY.get("picked") or []) if p.get("source") == "house"]
    if not picked:
        return tuple(shots)
    # the busiest corner of the plan, not the first plot: block 0 may front the
    # reserved plaza and leave the camera standing on an empty slab
    spot, best = None, -1
    step = max(1, len(picked) // 150)
    for i in range(0, len(picked), step):
        q = picked[i]
        n = 0
        for r in picked:
            dx = r["x"] - q["x"]
            dy = r["y"] - q["y"]
            if dx * dx + dy * dy < 1600.0:
                n += 1
        if n > best:
            spot, best = q, n
    if spot is None:
        return tuple(shots)
    # the gate camera has to stand on the axis the plan keeps clear: a fixed
    # point 95 m inside ends up in somebody's front room
    try:
        for (gp, ang) in outer_gaps():
            if gp[1] > 0.0 and abs(gp[0]) < 1.0:
                eye = (gp[0], gp[1] - 84.0, 2.2)
                look = (gp[0], gp[1] - 8.0, 13.5)
                for i, s in enumerate(shots):
                    if s[0] == "b5_gate_in":
                        shots[i] = (s[0], eye, look, 40.0)
                break
    except Exception:
        pass
    yaw = float(spot["yaw"])
    fx, fy = -math.sin(yaw), math.cos(yaw)        # local +Y = facade normal
    tx, ty = math.cos(yaw), math.sin(yaw)         # along the street
    dist = float(spot.get("d", 9.0)) * 0.5 + 6.0
    eye = (float(spot["x"]) + fx * dist, float(spot["y"]) + fy * dist, 1.72)
    look = (eye[0] + fx * 10.0 + tx * 26.0, eye[1] + fy * 10.0 + ty * 26.0, 2.6)
    for i, s in enumerate(shots):
        if s[0] == "b5_street":
            shots[i] = ("b5_street", eye, look, 22.0)
    return tuple(shots)


def join_group(name, parts, batch=384):
    """Join a whole group into one multi-material mesh.

    Every piece is authored in world space with an identity transform, so a plain
    join changes nothing visually - it just removes tens of thousands of object
    overheads, which is what made the full-city build so slow.

    `bpy.ops.object.join()` is roughly quadratic in the number of selected
    objects: joining the castle's 18,189 pieces in one call took 21 minutes of
    the build.  Same merge, ~400 at a time, then merge the ~45 survivors: the
    result is one object with the same geometry, and the cost drops to seconds.
    """
    parts = [p for p in parts if p is not None and getattr(p, "type", "") == "MESH"]
    if not parts:
        return []
    if len(parts) > batch:
        merged = []
        n_chunks = (len(parts) + batch - 1) // batch
        t0 = time.time()
        for i in range(n_chunks):
            chunk = parts[i * batch:(i + 1) * batch]
            merged.extend(join_group("_j%d" % i, chunk, batch=batch))
        print("[capital] %s: %d parts -> %d batches in %.1f s"
              % (name, len(parts), len(merged), time.time() - t0), flush=True)
        parts = merged
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    ob = parts[0]
    ob.name = name
    bpy.ops.object.select_all(action="DESELECT")
    return [ob]


def main(argv):
    # Blender's stdout is block-buffered when redirected to a file, so a 40-minute
    # build shows an empty log and looks hung. Force line buffering and print
    # progress so the log is a real progress indicator.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    stage = "full"
    do_render = True
    export = True
    if "--stage" in argv:
        stage = argv[argv.index("--stage") + 1]
    if "--no-render" in argv:
        do_render = False
    if "--no-export" in argv:
        export = False
    if "--houses" in argv:
        BUDGET["houses"] = int(argv[argv.index("--houses") + 1])
    if "--hd" in argv:
        HD["on"] = True
    if "--cap" in argv:
        HD_CAP["houses"] = int(argv[argv.index("--cap") + 1])
    if "--dense" in argv:
        HD_DENSE["on"] = True
    if "--plan2" in argv:
        HD_PLAN["plan2"] = True
    if "--interiors" in argv:
        HD_INT["on"] = True
    if "--insurance" in argv:
        HD_INS["path"] = argv[argv.index("--insurance") + 1]
    print("[capital] house budget =", BUDGET["houses"], " hd =", HD["on"],
          " dense =", HD_DENSE["on"], " plan2 =", HD_PLAN["plan2"])

    groups = build(stage)
    if "--join" in argv:
        for k in list(groups.keys()):
            groups[k] = join_group("ars_" + k, flatten(groups[k]))
    elif "--join-landmarks" in argv:
        # Join only the hand-built landmarks.  The city is already one object per
        # block, props are one per 56 m cell and the landscape is a handful of
        # meshes, so joining those would only make the exporter's spatial chunking
        # worse.  The landmarks are the opposite case: 18k loose castle parts with
        # names like "k_t" / "_sl" are impossible to classify or LOD, and joining
        # them into ars_castle / ars_cathedral / ... is what the Unity importer
        # needs to see.
        for k in ("castle", "cathedral", "guild_hall", "market_hall", "fountain",
                  "gates", "inner", "harbour", "burbs"):
            if k in groups:
                before = len(flatten(groups[k]))
                groups[k] = join_group("ars_" + k, flatten(groups[k]))
                print("[capital] joined %s: %d parts -> %d" % (k, before, len(groups[k])),
                      flush=True)
    report(groups)

    # Save the built scene so render/export passes do not have to rebuild.
    # Rebuilding the capital costs 15-40 minutes; opening the .blend costs seconds.
    if "--save" in argv:
        blend = os.path.join(OUT_PNG, "capital_%s.blend" % stage)
        if "--save-name" in argv:
            blend = os.path.join(OUT_PNG, "%s.blend" % argv[argv.index("--save-name") + 1])
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        print("[save]", blend, os.path.getsize(blend), flush=True)

    KC.clear_lights_cameras()
    if HD["on"]:
        # 33 deg instead of 50: at a high sun every block gets a shadow the size
        # of its own footprint and the whole town lies flat on the ground
        KC.setup_lighting(sun_energy=5.8, elev=33.0, azim=34.0)
        fill = bpy.data.objects.get("fill")
        if fill is not None and fill.data is not None:
            fill.data.energy = 300.0
    else:
        KC.setup_lighting()
    KC.setup_render(w=1600, h=900, samples=32)

    if do_render:
        if HD["on"] and stage == "full":
            shots = hd_shots()
        else:
            shots = SHOTS if stage == "full" else SHOTS[:2]
        for name, loc, look, lens in shots:
            KC.setup_camera(loc, look, lens)
            print("[render]", KC.render_to(os.path.join(OUT_PNG, name + ".png")))

    if export:
        os.makedirs(OUT_FBX, exist_ok=True)
        for k, parts in groups.items():
            if not parts:
                continue
            p = os.path.join(OUT_FBX, "ars_%s.fbx" % k)
            KC.export_group(parts, p, "ars_" + k)
            print("[export]", p, os.path.getsize(p))
    print("CAPITAL_DONE")


if __name__ == "__main__":
    # Blender exits 0 even when the script raises, so a 25-minute build that
    # died at the first NameError looked like a success to the fleet runner
    # (build_v25 cost 1107 s and reported exit=0).  Fail loudly instead.
    try:
        main(sys.argv)
    except Exception:
        import traceback
        traceback.print_exc()
        print("CAPITAL_FAILED", flush=True)
        sys.exit(1)
