"""
mine_town.py -- 山地矿镇 / mountain mining town, three layout variants.

Headless:
    blender.exe -b --factory-startup --python mine_town.py -- --variant mine_a

Layout model: everything is authored in a LANE-LOCAL frame (Frame class).
    u  runs along the lane
    v  runs ACROSS the lane;  v > 0 is always the terrace (hillside) side
`side` mirrors v into world space, `axis` decides which world axis u runs on,
so one generic builder produces three genuinely different plan layouts.

Terraces rise away from the lane:  tiers at v = 4 / 15.5 / 27 m, tops at
1.9 / 3.8 / 5.7 m, stone retaining walls with stairs cut through them.
The mine adit is cut into the end wall of the hill, rails run out of it.
"""
import bpy
import os
import sys
import math
import random
import time
from mathutils import Vector, Matrix, Euler

BASE = r"E:\My World\Blender"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import medkit
from medkit import (box, cyl, cone, sphere, gable_roof, roof_details, window,
                    door, lantern, mesh_obj, assign, bevel, T_at,
                    mat_plaster, mat_wood, mat_tile, mat_stone, mat_cobble,
                    mat_flag, mat_metal, mat_gold, mat_cloth, mat_glass,
                    mat_foliage, mat_water, mat_earth, reset_scene, c)
import medbuild

# ---- cheaper bevels -------------------------------------------------------
# medkit bevels every box with 2 segments; on a 200-part cottage that is most
# of the triangle budget.  Chamfer small parts with one segment and skip the
# tiny ones entirely -- invisible at town scale, saves ~60% of the faces.
_orig_bevel = medkit.bevel


def _cheap_bevel(ob, width=0.015, segments=2, angle=35):
    try:
        d = max(ob.dimensions)
    except Exception:
        d = 1.0
    if d < 2.8:
        return
    return _orig_bevel(ob, width=width, segments=2, angle=angle)


medkit.bevel = _cheap_bevel
if hasattr(medbuild, "bevel"):
    medbuild.bevel = _cheap_bevel
bevel = _cheap_bevel

SCRIPT_DIR = os.path.join(BASE, "kingdom")
EXPORT_DIR = os.path.join(BASE, "export", "kingdom", "mine")
RENDER_DIR = os.path.join(BASE, "renders", "kingdom")
DIAG_DIR = os.path.join(RENDER_DIR, "_diag")

TAU = math.tau
I4 = Matrix.Identity(4)
RNG = random.Random(20261022)

LANE_HALF = 3.2
TIER_RISE = 1.9
STAIR_TREAD = 0.34
STAIR_N = 10
STAIR_RUN = STAIR_TREAD * STAIR_N          # 3.40 m
NOTCH = STAIR_RUN + 0.9                    # fill is cut back this far at a gap


# --------------------------------------------------------------------------
# scene helpers
# --------------------------------------------------------------------------
def at(x, y, z=0.0, rz=0.0, ry=0.0, rx=0.0):
    return (Matrix.Translation((x, y, z))
            @ Euler((rx, ry, rz), "XYZ").to_matrix().to_4x4())


def join_group(parts, name):
    """Convert (apply modifiers) + join a sub-assembly into one mesh object."""
    keep = []
    for o in parts:
        if o is not None and o.name in bpy.data.objects:
            keep.append(o)
    if not keep:
        return None
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in keep:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = keep[0]
    if len(keep) > 1:
        try:
            bpy.ops.object.convert(target="MESH")
            bpy.ops.object.join()
        except RuntimeError as exc:
            print("[join] %s: %s" % (name, exc))
    ob = bpy.context.view_layer.objects.active
    if ob is None:
        return None
    ob.name = name
    ob.data.name = name
    return ob


# --------------------------------------------------------------------------
# palette  (every material is cached by name inside medkit)
# --------------------------------------------------------------------------
def _emissive(name, base_hex, em_hex, strength, rough=0.55, metallic=0.0):
    if name in medkit._MAT_CACHE:
        return medkit._MAT_CACHE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = medkit._bsdf(m)
    medkit._put(b, ["Base Color"], c(base_hex))
    medkit._put(b, ["Roughness"], rough)
    medkit._put(b, ["Metallic"], metallic)
    medkit._put(b, ["Emission Color"], c(em_hex))
    medkit._put(b, ["Emission Strength"], strength)
    medkit._MAT_CACHE[name] = m
    return m


def ST_WALL():
    return mat_stone("mine_stone", base="#736c60", dark="#443f36",
                     light="#948b7c", scale=2.0)


def ST_DARK():
    return mat_stone("mine_stone_dark", base="#5b5549", dark="#332f27",
                     light="#777062", scale=2.3)


def ST_DRESS():
    return mat_stone("mine_dressed", base="#8a8173", dark="#564f44",
                     light="#a9a08e", scale=3.0)


def ST_STEP():
    return mat_stone("mine_step", base="#8f8878", dark="#5b5447",
                     light="#ada596", scale=3.6)


def ST_RISER():
    """The dark vertical face of every retaining wall.

    Deliberately darker than the tread above it: at Unity overworld scale the
    terrace reads as a step only if riser and tread are different values.
    NOTE: the name is mine_stone_dark on purpose -- the Unity palette JSON only
    carries palette keys, and mine_riser was never dumped there.
    """
    return mat_stone("mine_stone_dark", base="#3a342b", dark="#1f1b16",
                     light="#4e4638", scale=2.6)


def ST_SHADOW():
    """Near-black band recessed under the coping, the crisp line of the step."""
    return mat_earth("mine_void", base="#0d0b08", dark="#050403")


def ST_LIP():
    """Pale dressed coping stone along the top of each retaining wall."""
    return mat_stone("mine_step", base="#a99e87", dark="#6d6455",
                     light="#c8bca2", scale=3.0)


def COBBLE():
    return mat_cobble("mine_cobble", base="#8a8272", mortar="#484238",
                      light="#a9a08e")


def DIRT():
    return mat_earth("mine_dirt", base="#6b5a42", dark="#4a3d2b")


def GRAVEL():
    return mat_earth("mine_gravel", base="#6d665a", dark="#4b463c")


def GRASS_D():
    return mat_foliage("mine_grass_dry", base="#414d2e", light="#5a6a3c")


def GRASS():
    return mat_foliage("mine_grass", base="#48552f", light="#5f7038")


def WOOD_D():
    return mat_wood("mine_timber", base="#3c2b1d", light="#57402a", scale=15)


def WOOD_M():
    return mat_wood("mine_wood", base="#5f4228", light="#7f5c37", scale=13)


def SHINGLE():
    return mat_wood("mine_shingle", base="#473626", light="#6a5136",
                    rough=0.86, scale=9)


def PLANK():
    return mat_wood("mine_plank", base="#775634", light="#967243", scale=10)


def IRON():
    return mat_metal("mine_iron", base="#38373d", rough=0.5)


def IRON_R():
    return mat_metal("mine_iron_rust", base="#5a4335", rough=0.78)


def SLATE():
    return mat_tile("mine_slate", base="#4c5760", dark="#353f48", light="#65727d")


def TERRA():
    return mat_tile("mine_terra", base="#7f4030", dark="#59291d", light="#9c563c")


def BROWN():
    return mat_tile("mine_tile_brown", base="#6b4c31", dark="#4a3220",
                    light="#86633e")


def ROPE():
    return mat_cloth("mine_rope", "#8d7852", rough=0.95)


def ORE():
    return mat_stone("mine_ore", base="#5f645c", dark="#3a3e38",
                     light="#7d8378", scale=3.4)


def mat_rock(name="rock", base="#6a6152", dark="#38342c", light="#8a7f6b",
             scale=0.55):
    """Natural, cracked rock -- voronoi edges, no masonry courses."""
    if name in medkit._MAT_CACHE:
        return medkit._MAT_CACHE[name]
    m, b = medkit._new_mat(name)
    medkit._put(b, ["Roughness"], 0.93)
    medkit._put(b, ["Metallic"], 0.0)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # two voronoi octaves multiplied together: boulder-scale cells broken by a
    # second, finer crack set, so the cliff never reads as one paving pattern
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    v2 = nt.nodes.new("ShaderNodeTexVoronoi")
    v2.feature = "DISTANCE_TO_EDGE"
    v2.inputs["Scale"].default_value = scale * 3.7
    nt.links.new(tc.outputs["Object"], v2.inputs["Vector"])
    v3 = nt.nodes.new("ShaderNodeTexVoronoi")
    v3.feature = "DISTANCE_TO_EDGE"
    v3.inputs["Scale"].default_value = scale * 11.0
    nt.links.new(tc.outputs["Object"], v3.inputs["Vector"])
    mm = nt.nodes.new("ShaderNodeMath")
    mm.operation = "MULTIPLY"
    mm.use_clamp = True
    nt.links.new(vor.outputs["Distance"], mm.inputs[0])
    nt.links.new(v2.outputs["Distance"], mm.inputs[1])
    mm2 = nt.nodes.new("ShaderNodeMath")
    mm2.operation = "MULTIPLY"
    mm2.use_clamp = True
    nt.links.new(mm.outputs[0], mm2.inputs[0])
    nt.links.new(v3.outputs["Distance"], mm2.inputs[1])
    r = medkit._ramp(nt, [(0.0, c(dark)), (0.010, c(base)), (0.075, c(base)),
                          (0.32, c(light))])
    nt.links.new(mm2.outputs[0], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    n = medkit._noise(nt, scale=scale * 5.0, detail=9.0, rough=0.72)
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    medkit._bump(nt, b, n.outputs["Fac"], strength=0.62, distance=0.12)
    medkit._MAT_CACHE[name] = m
    return m


def CLIFF():
    """Terrain riser rock: much darker than the gravel tread above it."""
    return mat_rock("mine_rock", base="#4a4338", dark="#2a251e",
                    light="#615848", scale=1.8)


def ROCK():
    return mat_rock("mine_rock", base="#6d6354", dark="#4a4234",
                    light="#8f846d", scale=2.0)


def CARTWOOD():
    return mat_wood("mine_cartwood", base="#3a2c1f", light="#4c3b28",
                    rough=0.92, scale=12)


def ORE_C():
    return mat_metal("mine_ore_copper", base="#6d5a42", rough=0.62)


def LAMP_DIM():
    return _emissive("mine_lampdim", "#2a1607", "#ff9440", 1.6, rough=0.8)


def FURNACE():
    return _emissive("mine_furnace", "#2a0f05", "#ff6a1e", 14.0, rough=0.6)


def EMBER():
    return _emissive("mine_ember", "#240d04", "#ff8a2a", 6.0, rough=0.7)


def LAMP():
    return _emissive("mine_lamp", "#33240f", "#ffb45a", 7.0, rough=0.6)


def VOID():
    return mat_earth("mine_void", base="#0a0806", dark="#030302")


# --------------------------------------------------------------------------
# lane frame
# --------------------------------------------------------------------------
class Frame(object):
    """Plan frame: u runs along the street (world yaw `ang`), v runs across it.

    ang = pi/2 puts u on +Y and v on +X, which is the town convention here:
    +Y north (into town), +X east.  A frame is normally created at the centre
    of the thing being built and then used with u = v = 0, so every existing
    builder places itself in world space at any yaw.
    """

    def __init__(self, ox=0.0, oy=0.0, ang=math.pi * 0.5):
        self.ox, self.oy, self.ang = ox, oy, ang
        self.ca = math.cos(ang)
        self.sa = math.sin(ang)

    def P(self, u, v, z=0.0):
        return (self.ox + u * self.ca + v * self.sa,
                self.oy + u * self.sa - v * self.ca, z)

    def D(self, du, dv):
        return (du * self.ca + dv * self.sa, du * self.sa - dv * self.ca)

    def size(self, su, sv, sz):
        return (sv, su, sz)

    def rz(self, du, dv):
        wx, wy = self.D(du, dv)
        return math.atan2(-wx, wy)

    def M(self, u, v, z=0.0, du=0.0, dv=-1.0):
        x, y, _ = self.P(u, v, z)
        return at(x, y, z, rz=self.rz(du, dv))

    def Mz(self, u, v, z=0.0, th=0.0):
        """World-space yaw at lane coordinates (for rubble/props/trees)."""
        x, y, _ = self.P(u, v, z)
        return at(x, y, z, rz=th)

    def Mb(self, u, v, z=0.0):
        """Matrix for a box whose local x is across and local y is along."""
        x, y, _ = self.P(u, v, z)
        return at(x, y, z, rz=self.ang - math.pi * 0.5)


def fbox(F, name, u, v, zb, su, sv, sz, mat, bev=0.0):
    """Box in the lane frame (su along u, sv across); zb = bottom height."""
    return box(name, F.Mb(u, v, zb + sz * 0.5), F.size(su, sv, sz), mat, bev=bev)


def fcyl(F, name, u, v, zb, r, h, mat, seg=12, r2=None, cap=True):
    x, y, _ = F.P(u, v, 0.0)
    return cyl(name, at(x, y, zb + h * 0.5), r, h, mat, seg=seg, cap=cap, r2=r2)


# --------------------------------------------------------------------------
# small generic props
# --------------------------------------------------------------------------
def rock(name, T, s, rng, mat, squash=0.72, jitter=0.30, seg=7, ring=4):
    ob = sphere(name, I4, s, mat, seg=seg, ring=ring, squash=squash)
    ph = rng.uniform(0.0, TAU)
    for vtx in ob.data.vertices:
        p = vtx.co
        k = 1.0 + jitter * (0.62 * math.sin(3.1 * p.x / s + ph)
                            * math.cos(2.7 * p.y / s + ph * 0.5)
                            + 0.38 * math.sin(4.3 * p.z / s + ph * 1.7))
        vtx.co = p * k
    ob.data.transform(T)
    return ob


def ladder(name, T, h=3.0, width=0.46, wood=None):
    wood = wood or WOOD_M()
    out = []
    for sx in (-1, 1):
        out.append(box(name + "_r%d" % sx, T @ T_at(sx * width * 0.5, 0, h * 0.5),
                       (0.07, 0.07, h), wood, bev=0.008))
    n = max(3, int(h / 0.32))
    for i in range(n):
        z = 0.24 + (h - 0.34) * i / max(1, n - 1)
        out.append(box(name + "_s%d" % i, T @ T_at(0, 0, z),
                       (width * 0.96, 0.05, 0.05), wood))
    return out


def rope_coil(name, T, r=0.26, mat=None):
    mat = mat or ROPE()
    out = []
    for i, rr in enumerate((r, r * 0.92, r * 0.84, r * 0.76)):
        out.append(cyl(name + "_c%d" % i, T @ T_at(0, 0, 0.05 + i * 0.065),
                       rr, 0.07, mat, seg=14, cap=False))
    out.append(cyl(name + "_post", T @ T_at(0, 0, 0.5), 0.05, 1.0, WOOD_D(), seg=8))
    return out


def plank_stack(name, T, n=6, L=2.6, rng=None):
    rng = rng or random.Random(5)
    out = []
    for sy in (-1, 1):
        out.append(box(name + "_b%d" % sy, T @ T_at(0, sy * L * 0.34, 0.09),
                       (L, 0.14, 0.18), WOOD_D(), bev=0.008))
    for i in range(n):
        out.append(box(name + "_p%d" % i,
                       T @ T_at(rng.uniform(-0.05, 0.05), 0,
                                0.20 + i * 0.075),
                       (L * rng.uniform(0.9, 1.0), 0.34, 0.06), PLANK(),
                       bev=0.006))
    return out


def pick_rack(name, T, rng=None):
    out = []
    for sx in (-1, 1):
        out.append(box(name + "_p%d" % sx, T @ T_at(sx * 0.62, 0, 0.72),
                       (0.11, 0.11, 1.44), WOOD_D(), bev=0.01))
    out.append(box(name + "_rail", T @ T_at(0, 0, 1.34), (1.36, 0.10, 0.10),
                   WOOD_D(), bev=0.008))
    out.append(box(name + "_rail2", T @ T_at(0, 0, 0.42), (1.36, 0.10, 0.10),
                   WOOD_D(), bev=0.008))
    for i in range(3):
        x = -0.42 + i * 0.42
        out.append(cyl(name + "_h%d" % i, T @ T_at(x, 0.10, 0.86), 0.042, 1.10,
                       PLANK(), seg=7, r2=0.036))
        out.append(box(name + "_hd%d" % i,
                       T @ T_at(x, 0.16, 1.40, ry=0.0),
                       (0.06, 0.10, 0.62), IRON_R(), bev=0.01))
        out.append(cone(name + "_pk%d" % i,
                        T @ T_at(x, 0.16, 1.70, rx=0.0),
                        0.05, 0.26, IRON_R(), seg=6))
    return out


def barrel_stack(name, T, rng):
    out = medbuild.barrel(name + "_a", T, rng=rng)
    out += medbuild.barrel(name + "_b", T @ T_at(0.62, 0.10, 0, rz=0.6),
                           r=0.27, h=0.74, rng=rng)
    out += medbuild.barrel(name + "_c", T @ T_at(0.10, 0.60, 0, rz=1.4),
                           r=0.25, h=0.70, rng=rng)
    return out


def crate_pile(name, T, rng):
    out = medbuild.crate(name + "_a", T, 0.64, rng)
    out += medbuild.crate(name + "_b", T @ T_at(0.02, 0.02, 0.64, rz=0.22),
                          0.58, rng)
    out += medbuild.crate(name + "_c", T @ T_at(0.66, 0.12, 0, rz=-0.3),
                          0.55, rng)
    return out


def mine_cart(name, T, rng, ore=True):
    """Steel-banded timber hopper on four flanged wheels."""
    out = []
    wood = CARTWOOD()
    iron = IRON_R()
    L, Wd, H = 1.55, 1.02, 0.62
    out.append(box(name + "_bed", T @ T_at(0, 0, 0.46), (Wd, L, 0.10), wood,
                   bev=0.01))
    for sx in (-1, 1):
        out.append(box(name + "_sd%d" % sx, T @ T_at(sx * Wd * 0.5, 0, 0.46 + H * 0.5),
                       (0.07, L, H), wood, bev=0.008))
        out.append(box(name + "_tp%d" % sx,
                       T @ T_at(sx * (Wd * 0.5 - 0.03), 0, 0.46 + H + 0.02),
                       (0.16, L, 0.06), iron))
    for sy in (-1, 1):
        out.append(box(name + "_en%d" % sy,
                       T @ T_at(0, sy * L * 0.5, 0.46 + H * 0.5),
                       (Wd, 0.07, H), wood, bev=0.008))
    # iron bands
    for sy in (-0.28, 0.28):
        out.append(box(name + "_bd%.2f" % sy,
                       T @ T_at(0, sy * L, 0.46 + H * 0.5),
                       (Wd + 0.05, 0.06, H * 1.02), iron))
    for sx in (-1, 1):
        for sy in (-1, 1):
            M = T @ T_at(sx * (Wd * 0.5 + 0.07), sy * L * 0.30, 0.28,
                         ry=math.pi * 0.5)
            out.append(cyl(name + "_w%d%d" % (sx, sy), M, 0.26, 0.08, IRON_R(),
                           seg=14))
            out.append(cyl(name + "_wh%d%d" % (sx, sy), M, 0.07, 0.12, IRON(),
                           seg=8))
    if ore:
        om = ORE()
        for i in range(7):
            out.append(rock(name + "_o%d" % i,
                            T @ T_at(rng.uniform(-0.34, 0.34),
                                     rng.uniform(-0.55, 0.55),
                                     0.46 + H * 0.62 + rng.uniform(-0.04, 0.16),
                                     rz=rng.uniform(0, TAU)),
                            rng.uniform(0.11, 0.19), rng,
                            ORE_C() if i % 3 == 0 else om))
    return out


def rail_line(F, name, u0, u1, vc, gauge=0.54):
    """Track: ballast, sleepers, two rails.  Runs along u."""
    out = []
    um = (u0 + u1) * 0.5
    L = abs(u1 - u0)
    out.append(fbox(F, name + "_ballast", um, vc, -0.02, L, 1.72, 0.10, GRAVEL()))
    n = max(2, int(L / 0.62))
    for i in range(n):
        u = min(u0, u1) + (i + 0.5) * (L / n)
        out.append(fbox(F, "%s_sl%d" % (name, i), u, vc, 0.02, 0.24, 1.42, 0.10,
                        WOOD_D(), bev=0.006))
    for s in (-1, 1):
        out.append(fbox(F, name + "_r%d" % s, um, vc + s * gauge * 0.5, 0.12,
                        L, 0.09, 0.09, IRON_R(), bev=0.004))
    return out


def lamp_post(F, name, u, v, h=3.05, face=(0, -1)):
    out = []
    out.append(fcyl(F, name + "_base", u, v, 0.0, 0.24, 0.22, ST_DRESS(), seg=12))
    out.append(fcyl(F, name + "_post", u, v, 0.20, 0.065, h - 0.2, IRON(), seg=10))
    out.append(fcyl(F, name + "_cap", u, v, h, 0.10, 0.10, IRON(), seg=10))
    M = F.M(u, v, h - 0.06, du=face[0], dv=face[1])
    out += lantern(name + "_ln", M, IRON(), LAMP(), scale=1.15)
    return out


def flare_post(name, T):
    """A small iron fire-basket on a post (mine yard lighting)."""
    out = [cyl(name + "_p", T @ T_at(0, 0, 0.85), 0.06, 1.7, IRON(), seg=8)]
    out.append(box(name + "_b", T @ T_at(0, 0, 1.78), (0.42, 0.42, 0.22), IRON(),
                   bev=0.02))
    out.append(box(name + "_f", T @ T_at(0, 0, 1.86), (0.30, 0.30, 0.10), EMBER()))
    return out


# --------------------------------------------------------------------------
# terraces
# --------------------------------------------------------------------------
def terrace(F, tag, u0, u1, v0, v1, ztop, gaps=(), top_mat=None,
            face_mat=None):
    """One terrace: stone retaining wall + fill + top surface + coping.

    gaps = [(u_lo, u_hi)] are openings for stairs; the fill behind them is
    cut back by NOTCH so the stair has somewhere to land.
    """
    out = []
    face_mat = face_mat or ST_RISER()
    top_mat = top_mat or COBBLE()
    gaps = sorted(gaps)
    # wall + fill segments between gaps
    cuts = [u0]
    for (a, b) in gaps:
        cuts += [a, b]
    cuts.append(u1)
    segs = [(cuts[i], cuts[i + 1]) for i in range(0, len(cuts) - 1, 2)]
    for si, (a, b) in enumerate(segs):
        if b - a < 0.05:
            continue
        um, L = (a + b) * 0.5, (b - a)
        out.append(fbox(F, "%s_w%d" % (tag, si), um, v0 + 0.35, 0.0, L, 0.70,
                        ztop, ST_RISER(), bev=0.02))
        # recessed near-black band under the coping: this is what makes the
        # step read when the terrace is only a few pixels tall on screen
        out.append(fbox(F, "%s_sh%d" % (tag, si), um, v0 + 0.33,
                        ztop - 0.46, L, 0.74, 0.32, ST_SHADOW()))
        # pale coping lip, proud of the wall face so it throws its own shadow
        out.append(fbox(F, "%s_cp%d" % (tag, si), um, v0 + 0.40,
                        ztop - 0.16, L, 1.06, 0.26, ST_LIP(), bev=0.012))
        out.append(fbox(F, "%s_f%d" % (tag, si), um, (v0 + 0.70 + v1) * 0.5, 0.0,
                        L, v1 - v0 - 0.70, ztop - 0.06, ST_DARK()))
        out.append(fbox(F, "%s_t%d" % (tag, si), um, (v0 + 0.70 + v1) * 0.5,
                        ztop - 0.07, L, v1 - v0 - 0.72, 0.09, top_mat))
        # buttresses every ~7 m
        nb = max(1, int(L / 7.0))
        for k in range(nb):
            ub = a + L * (k + 0.5) / nb
            out.append(fbox(F, "%s_bt%d%d" % (tag, si, k), ub, v0 + 0.05, 0.0,
                            0.62, 0.62, ztop - 0.02, ST_RISER(), bev=0.02))
    # stair openings
    for gi, (a, b) in enumerate(gaps):
        out.append(fbox(F, "%s_fn%d" % (tag, gi), (a + b) * 0.5,
                        (v0 + NOTCH + v1) * 0.5, 0.0, (b - a),
                        v1 - v0 - NOTCH, ztop - 0.06, ST_DARK()))
        out.append(fbox(F, "%s_tn%d" % (tag, gi), (a + b) * 0.5,
                        (v0 + NOTCH + v1) * 0.5, ztop - 0.07, (b - a),
                        v1 - v0 - NOTCH, 0.09, top_mat))
        # low cheek walls beside the opening (below the steps, hidden partly)
        for s in (-1, 1):
            out.append(fbox(F, "%s_ch%d%d" % (tag, gi, s),
                            (a + b) * 0.5 + s * ((b - a) * 0.5 + 0.16),
                            v0 + 0.32, 0.0, 0.30, 0.64, ztop, ST_RISER(), bev=0.015))
    return out


def stair_run(F, tag, u, v_front, z0, z1, width=2.35):
    """Stone stair climbing from z0 up to z1 as v increases."""
    out = []
    n = STAIR_N
    dz = (z1 - z0) / n
    for i in range(n):
        zz = z0 + dz * (i + 1)
        vv = v_front + STAIR_TREAD * (i + 0.5)
        out.append(fbox(F, "%s_s%d" % (tag, i), u, vv, z0, width, STAIR_TREAD,
                        zz - z0, ST_STEP(), bev=0.01))
        for s in (-1, 1):
            out.append(fbox(F, "%s_k%d%d" % (tag, i, s),
                            u + s * (width * 0.5 + 0.15), vv, z0, 0.28,
                            STAIR_TREAD, (zz - z0) + 0.52, ST_WALL(), bev=0.012))
    # landing slab at the top, inside the notch
    out.append(fbox(F, "%s_ld" % tag, u, v_front + STAIR_RUN + 0.55, z1 - 0.20,
                    width + 0.58, 1.15, 0.22, ST_STEP(), bev=0.015))
    return out


# --------------------------------------------------------------------------
# buildings
# --------------------------------------------------------------------------
PLASTERS = [
    ("mine_plaster_a", "#cfc3a8", "#b0a284"),
    ("mine_plaster_b", "#c3b79c", "#a3977a"),
    ("mine_plaster_c", "#ceb995", "#ae9371"),
    ("mine_plaster_d", "#b9bcae", "#9a9d8d"),
    ("mine_plaster_e", "#c9ae8b", "#aa8f6d"),
]
ROOFS = [SLATE, TERRA, BROWN, SLATE, TERRA]


def plaster(i):
    n, b, d = PLASTERS[i % len(PLASTERS)]
    return mat_plaster(n, base=b, dirt=d)


def cottage(F, tag, u, v, z0, W=5.2, D=4.8, kind=0, rng=None, face=(0, -1),
            extras=True, FH=2.55, pitch=41.0, nF=2, dorm=False):
    """A cramped miner's cottage: stone ground floor, jettied timber upper."""
    rng = rng or random.Random(hash(tag) & 0xFFFF)
    M = F.M(u, v, z0, du=face[0], dv=face[1])
    parts = medbuild.house(
        tag, M, W=W, D=D, FH=FH, nF=nF, jetty=0.17, pitch=pitch,
        walls=plaster(kind), timber=WOOD_D(), roof=ROOFS[kind % len(ROOFS)](),
        rng=rng, win_front=2 if W < 5.8 else 3, win_side=1, has_door=True,
        has_sign=False, plinth=0.26, chimney=True, ridge_along_front=True,
        shutters=(kind % 3 != 2), stone_ground=True, corner_style="timber",
        brace_pattern=["alternate", "herringbone", "cross", "vertical"][kind % 4],
        jetty_corbels=(kind % 2 == 0), eave_brackets=False,
        dormers=(1 if dorm else 0))
    if not extras:
        return parts
    # lean-to log store against one gable
    sx = 1 if kind % 2 else -1
    lx = sx * (W * 0.5 + 1.05)
    parts.append(box(tag + "_lew", M @ T_at(lx, -0.35, 1.05),
                     (2.1, D * 0.86, 2.1), WOOD_M(), bev=0.02))
    parts.append(box(tag + "_ler", M @ T_at(lx, -0.35, 2.20, ry=0.0),
                     (2.4, D * 0.92, 0.10), PLANK(), bev=0.01))
    for k in range(3):
        parts.append(cyl(tag + "_log%d" % k,
                         M @ T_at(lx + 0.55, -0.6 + k * 0.0, 0.18 + k * 0.28,
                                  rz=math.pi * 0.5),
                         0.13, 1.7, WOOD_M(), seg=8))
    # rain barrel + a stool by the door
    parts += [o for o in medbuild.barrel(tag + "_rb", M @ T_at(W * 0.5 - 0.45,
                                                               D * 0.5 + 0.55, 0),
                                        rng=rng)]
    # a ladder up to the loft hatch
    parts += ladder(tag + "_ld", M @ T_at(-W * 0.5 - 0.22, 0.35, 0, ry=-0.06,
                                          rz=math.pi * 0.5), h=3.4)
    return parts


def tavern(F, tag, u, v, z0, W=9.6, D=6.6, kind=0, rng=None, face=(0, -1),
           sign_text=True):
    """Company office / tavern: grander, says 'this is the town's hall'."""
    rng = rng or random.Random(hash(tag) & 0xFFFF)
    M = F.M(u, v, z0, du=face[0], dv=face[1])
    parts = medbuild.house(
        tag, M, W=W, D=D, FH=3.05, nF=2, jetty=0.24, pitch=43.0,
        walls=mat_plaster("mine_plaster_hall", base="#ddd4bd", dirt="#b8ac92"),
        timber=mat_wood("mine_timber_hall", base="#37281a", light="#513a24",
                        scale=13),
        roof=SLATE(), rng=rng, win_front=4, win_side=2, has_door=True,
        has_sign=False, plinth=0.40, chimney=True, ridge_along_front=True,
        shutters=True, stone_ground=True, corner_style="quoin",
        brace_pattern="cross", jetty_corbels=True, eave_brackets=True,
        dormers=2)
    # porch: two posts + a lean-to roof over the door
    py = D * 0.5 + 1.05
    for sx in (-1, 1):
        parts.append(box("%s_ppo%d" % (tag, sx), M @ T_at(sx * 1.55, py, 1.45),
                         (0.18, 0.18, 2.9), WOOD_D(), bev=0.012))
    parts.append(box(tag + "_pbeam", M @ T_at(0, py, 2.92),
                     (3.5, 0.20, 0.22), WOOD_D(), bev=0.012))
    parts.append(box(tag + "_proof", M @ T_at(0, py + 0.35, 3.30, rx=0.26),
                     (4.0, 1.9, 0.12), SLATE(), bev=0.01))
    for i in range(4):
        parts.append(box("%s_ppr%d" % (tag, i),
                         M @ T_at(-1.6 + i * 1.06, py + 1.05, 3.02),
                         (0.09, 0.9, 0.16), WOOD_D()))
    # big painted sign board on an iron bracket
    sz = 3.55
    parts.append(box(tag + "_sbrk", M @ T_at(W * 0.5 + 0.42, D * 0.5 + 0.10, sz),
                     (1.15, 0.09, 0.09), IRON(), bev=0.01))
    for sx in (-1, 1):
        parts.append(box("%s_ssup%d" % (tag, sx),
                         M @ T_at(W * 0.5 + 0.42, D * 0.5 + 0.10 + sx * 0.52, sz),
                         (1.15, 0.05, 0.05), IRON()))
    parts.append(box(tag + "_sbrd", M @ T_at(W * 0.5 + 0.55, D * 0.5 + 0.62, sz - 0.60),
                     (1.05, 0.06, 0.86), PLANK(), bev=0.012))
    parts.append(box(tag + "_sfrm", M @ T_at(W * 0.5 + 0.55, D * 0.5 + 0.66, sz - 0.60),
                     (1.15, 0.04, 0.96), IRON(), bev=0.008))
    # crossed picks emblem on the board
    for s in (-1, 1):
        parts.append(box("%s_sem%d" % (tag, s),
                         M @ T_at(W * 0.5 + 0.55, D * 0.5 + 0.70, sz - 0.60,
                                  ry=s * 0.7),
                         (0.72, 0.02, 0.075), IRON_R()))
    # bench + barrels outside
    parts.append(box(tag + "_bench", M @ T_at(-2.9, D * 0.5 + 0.62, 0.48),
                     (2.3, 0.44, 0.10), PLANK(), bev=0.012))
    for sx in (-1, 1):
        parts.append(box("%s_bl%d" % (tag, sx),
                         M @ T_at(-2.9 + sx * 0.95, D * 0.5 + 0.62, 0.24),
                         (0.12, 0.40, 0.48), WOOD_D()))
    parts += barrel_stack(tag + "_bs", M @ T_at(W * 0.5 - 1.6, D * 0.5 + 1.35, 0),
                          rng)
    return parts


# --------------------------------------------------------------------------
# mine adit
# --------------------------------------------------------------------------
def recess_mesh(F, name, u0, u1, vh, z0, z1, mat_dark, mat_back, lo, hi):
    """Open-fronted box (a tunnel) built in world space from lane coords."""
    x0, y0, _ = F.P(u0, -vh, 0)
    x1, y1, _ = F.P(u1, -vh, 0)
    x2, y2, _ = F.P(u1, vh, 0)
    x3, y3, _ = F.P(u0, vh, 0)
    verts = [(x0, y0, z0), (x1, y1, z0), (x2, y2, z0), (x3, y3, z0),
             (x0, y0, z1), (x1, y1, z1), (x2, y2, z1), (x3, y3, z1)]
    faces = [(0, 1, 2, 3),          # floor
             (7, 6, 5, 4),          # ceiling
             (0, 1, 5, 4),          # side v = -vh
             (3, 2, 6, 7),          # side v = +vh
             (1, 2, 6, 5)]          # back (u1)
    ob = mesh_obj(name, verts, faces)
    assign(ob, mat_dark, mat_back)
    ob.data.polygons[4].material_index = 1
    return ob


def adit(F, end, rng, u_face=None):
    """Mine entrance at u = end*44: portal, headframe, winch, rails, cart.

    Returns a list of (group_name, parts) so the hill mass and the machinery
    can be joined separately.
    """
    s = end
    if u_face is None:
        u_face = s * 44.0
    portal_hw = 2.15
    portal_h = 3.90
    sv_hood = math.radians(22)
    out_portal = []
    out_hill = []
    out_rail = []

    # ---- the rock cut the adit is driven into: three battered courses, each
    #      stepping back, so the face is a cut slope and not a billboard
    rockm = ROCK()
    FACE_H = 6.05
    courses = ((0.0, 2.30, 1.4, 2.8, 0.0),      # z0, z1, u centre, thickness, full?
               (2.30, 3.95, 2.0, 2.8, 0.0),
               (3.95, FACE_H, 2.6, 2.8, 1.0))
    for k, (z0, z1, uc, th, full) in enumerate(courses):
        hh = z1 - z0
        zc = (z0 + z1) * 0.5
        if full:
            out_hill.append(fbox(F, "adit_c%d" % k, u_face + s * uc, 4.0, z0,
                                 th, 34.0, hh, rockm))
            continue
        out_hill.append(fbox(F, "adit_c%da" % k, u_face + s * uc, -6.6, z0,
                             th, 9.2, hh, rockm))
        out_hill.append(fbox(F, "adit_c%db" % k, u_face + s * uc, 15.6, z0,
                             th, 26.8, hh, rockm))
    # hill stepping up and back behind the cut
    for k, (db, hh, vc, vw) in enumerate(((9.4, 7.6, 4.6, 33.0),
                                          (14.0, 9.2, 6.2, 29.0),
                                          (18.4, 10.6, 8.4, 26.0))):
        out_hill.append(fbox(F, "adit_mass%d" % k, u_face + s * db, vc,
                             -1.0, 7.4, vw, hh + 1.0, rockm))
    out_hill.append(fbox(F, "adit_mass_top", u_face + s * 19.4, 8.0,
                         9.55, 6.6, 22.0, 0.40, GRASS_D()))
    # crest rocks along every step so the silhouette stays broken
    for i in range(26):
        vv = rng.uniform(-9.0, 26.0)
        if abs(vv) < portal_hw + 1.2:
            vv += 5.0 * (1 if vv >= 0 else -1)
        out_hill.append(rock("adit_crest%d" % i,
                             F.Mz(u_face + s * rng.uniform(1.0, 6.5), vv,
                                  FACE_H - rng.uniform(0.3, 1.1),
                                  rng.uniform(0, TAU)),
                             rng.uniform(0.8, 2.3), rng, rockm, squash=0.62))
    for i in range(20):
        out_hill.append(rock("adit_foot%d" % i,
                             F.Mz(u_face - s * rng.uniform(0.1, 1.8),
                                  rng.choice((-1, 1)) * rng.uniform(2.5, 10.0),
                                  rng.uniform(0.0, 0.30),
                                  rng.uniform(0, TAU)),
                             rng.uniform(0.4, 1.2), rng,
                             rockm if i % 3 else ORE(), squash=0.55))
    # pines on the terraces of the hill
    for i in range(9):
        k = i % 3
        out_hill += conifer(F, "adit_p%d" % i,
                            u_face + s * (5.0 + k * 4.6),
                            rng.uniform(-3.0, 22.0),
                            (7.6, 9.2, 10.6)[k] - 0.4,
                            rng.uniform(6.0, 9.0), rng)
    # tunnel void
    out_hill.append(recess_mesh(F, "adit_void", u_face, u_face + s * 5.6,
                                portal_hw, 0.0, portal_h, ST_DARK(), VOID(),
                                (s > 0), (0, 0)))
    # a lantern burning on the drive wall: the entrance reads as a hole with a
    # warm point at the far end, not a glowing rectangle
    out_hill.append(fbox(F, "adit_ember", u_face + s * 5.6, -0.9, 0.50,
                         0.16, 0.26, 0.30, LAMP(), bev=0.0))
    out_hill += medkit.lantern("adit_glow",
                               F.M(u_face + s * 3.6, -(portal_hw - 0.30), 2.55,
                                   du=s, dv=0.0),
                               IRON(), LAMP(), scale=0.85)

    # ---- portal: two timber sets, collar planks, a hood and two lanterns
    for k, du in enumerate((0.0, s * 1.35)):
        nb = "adit_set%d" % k
        for sv in (-1, 1):
            out_portal.append(box("%s_p%d" % (nb, sv),
                                  at(*F.P(u_face - s * 0.15 + du,
                                          sv * (portal_hw + 0.02), 0),
                                     rz=F.rz(1, 0)),
                                  F.size(0.38, 0.38, portal_h + 0.15), WOOD_D(),
                                  bev=0.012))
        out_portal.append(fbox(F, "%s_l" % nb, u_face - s * 0.15 + du, 0.0,
                               portal_h - 0.24, 0.44, portal_hw * 2 + 0.62, 0.46,
                               WOOD_D(), bev=0.012))
        out_portal.append(fbox(F, "%s_pl" % nb, u_face - s * 0.15 + du, 0.0,
                               portal_h + 0.18, 0.34, portal_hw * 2 + 0.70, 0.16,
                               PLANK(), bev=0.008))
    # pitched hood over the mouth so rain does not run into the drive
    PM = F.M(u_face - s * 0.30, 0.0, 0.0, du=-s, dv=0.0)
    out_portal.append(box("adit_hood",
                          PM @ T_at(0, 0.60, portal_h + 0.86, rx=-sv_hood),
                          (portal_hw * 2 + 1.7, 1.85, 0.14), PLANK(), bev=0.01))
    for i in range(3):
        out_portal.append(box("adit_raft%d" % i,
                              PM @ T_at(-1.5 + i * 1.5, 0.55, portal_h + 0.62),
                              (0.13, 1.7, 0.13), WOOD_D(), bev=0.008))
    # two lanterns bracketed to the portal posts
    for sv in (-1, 1):
        out_portal += medkit.lantern("adit_lan%d" % sv,
                                     F.M(u_face - s * 0.55,
                                         sv * (portal_hw + 0.55), 2.62,
                                         du=-s, dv=0.0),
                                     IRON(), LAMP(), scale=1.05)
    # stone voussoir ring around the opening
    n = 9
    for i in range(n):
        a = math.pi * (i + 0.5) / n
        vv = math.cos(a) * (portal_hw + 0.20)
        zz = portal_h - 0.05 + math.sin(a) * 0.22
        out_portal.append(fbox(F, "adit_vs%d" % i, u_face - s * 0.32, vv, zz,
                               0.55, 0.42, 0.44, ST_DRESS(), bev=0.02))
    # low stone kerb each side of the tunnel mouth
    for sv in (-1, 1):
        out_portal.append(fbox(F, "adit_kb%d" % sv, u_face - s * 0.10,
                               sv * (portal_hw + 0.35), 0.0, 0.9, 0.7, 0.55,
                               ST_DRESS(), bev=0.02))

    # ---- headframe over its own shaft, set to one side of the portal
    leg_u = (u_face - s * 5.2, u_face - s * 1.7)
    leg_v = 2.45
    hv = 4.55           # the shaft sits beside the adit, not in its mouth
    top_z = 9.0
    # shaft collar: a low stone kerb ring with a dark drop inside
    out_portal.append(fbox(F, "hf_collar", (leg_u[0] + leg_u[1]) * 0.5, hv, 0.0,
                           2.5, 2.5, 0.34, ST_DRESS(), bev=0.02))
    out_portal.append(fbox(F, "hf_drop", (leg_u[0] + leg_u[1]) * 0.5, hv, 0.30,
                           1.5, 1.5, 0.10, VOID(), bev=0.0))
    for iu, lu in enumerate(leg_u):
        for sv in (-1, 1):
            # leaning legs: build as a chain of 3 boxes to fake the inward rake
            for k in range(3):
                t0 = k / 3.0
                t1 = (k + 1) / 3.0
                zc = top_z * (t0 + t1) * 0.5
                vv = hv + sv * (leg_v - 0.55 * (t0 + t1) * 0.5)
                uu = lu + s * 0.55 * (t0 + t1) * 0.5
                out_portal.append(fbox(F, "hf_leg%d%d%d" % (iu, (sv + 1) // 2, k),
                                       uu, vv, zc - 0.2, 0.32, 0.32, top_z / 3 + 0.3,
                                       WOOD_D(), bev=0.01))
    # top platform + cross braces
    hub_u = (leg_u[0] + leg_u[1]) * 0.5
    out_portal.append(fbox(F, "hf_deck", hub_u, hv, top_z - 0.20, 3.8, 3.4, 0.24,
                           PLANK(), bev=0.01))
    for sv in (-1, 1):
        out_portal.append(fbox(F, "hf_rail%d" % sv, hub_u, hv + sv * 1.35, top_z,
                               3.2, 0.10, 0.10, WOOD_D()))
        for k, zz in enumerate((2.3, 4.6)):
            out_portal.append(fbox(F, "hf_brace%d%d" % (sv, k), hub_u,
                                   sv * (leg_v - 0.30 - k * 0.15), zz,
                                   0.22, 0.22, 0.62, WOOD_D(), bev=0.008))
    for k, uu in enumerate((leg_u[0], leg_u[1])):
        out_portal.append(fbox(F, "hf_tie%d" % k, uu, hv, 4.55, 0.20, 4.3, 0.18,
                               WOOD_D()))
    # the winch wheel: axis across the lane, above the shaft mouth
    WM = F.M(hub_u, hv, top_z - 0.95, du=1, dv=0) @ T_at(0, 0, 0, ry=math.pi * 0.5)
    out_portal.append(cyl("hf_wheel", WM, 1.22, 0.16, IRON_R(), seg=22))
    out_portal.append(cyl("hf_hub", WM, 0.24, 0.34, IRON(), seg=12))
    for i in range(8):
        a = TAU * i / 8.0
        out_portal.append(box("hf_spk%d" % i,
                              WM @ T_at(math.cos(a) * 0.52, math.sin(a) * 0.52, 0,
                                        rz=a),
                              (0.98, 0.07, 0.07), WOOD_D()))
    # rope from the wheel down into the tunnel + a hanging cage
    out_portal.append(cyl("hf_rope", at(*F.P(hub_u, hv, 0)) @
                          T_at(0, 0, 3.9), 0.028, 4.6, ROPE(), seg=6))
    out_portal.append(fbox(F, "hf_cage", hub_u, hv, 1.2, 0.55, 0.55,
                           0.6, IRON_R(), bev=0.01))
    # a small winch house / tool lean-to beside the portal
    hx = u_face - s * 2.2
    for i, (du, dv) in enumerate(((0.0, -8.0), (0.0, -5.6), (2.6, -8.0), (2.6, -5.6))):
        out_portal.append(fbox(F, "wh_p%d" % i, hx + s * du, dv, 0.0, 0.20, 0.20,
                               2.9, WOOD_D(), bev=0.008))
    out_portal.append(fbox(F, "wh_roof", hx + s * 1.3, -6.8, 2.86, 3.3, 3.0, 0.14,
                           SHINGLE(), bev=0.01))
    out_portal.append(fbox(F, "wh_back", hx + s * 2.55, -6.8, 0.1, 0.10, 2.8,
                           2.7, PLANK()))

    # ---- spoil heap beside the portal
    for i in range(9):
        out_portal.append(rock("spoil%d" % i,
                               at(*F.P(u_face - s * (1.2 + rng.uniform(0, 3.0)),
                                       rng.choice((-1, 1)) * rng.uniform(3.1, 5.4),
                                       rng.uniform(0.0, 0.5))),
                               rng.uniform(0.30, 0.62), rng,
                               ORE() if i % 4 else ORE_C(), squash=0.62))

    # ---- track out of the tunnel
    rail_end = u_face - s * 19.0
    out_rail += rail_line(F, "adit_rail", u_face - s * 0.2, rail_end, 1.72)
    out_rail.append(fbox(F, "adit_buf", rail_end + s * 0.35, 1.72, 0.0, 0.30,
                         1.6, 0.55, WOOD_D(), bev=0.02))
    # a cart standing just outside the mouth
    out_rail += mine_cart("adit_cart", F.M(u_face - s * 7.0, 1.72, 0.22, du=1, dv=0),
                          rng)
    return [("adit_hill", out_hill), ("adit_portal", out_portal),
            ("adit_track", out_rail)]


# --------------------------------------------------------------------------
# smelter / forge
# --------------------------------------------------------------------------
def SMOKE():
    """Thin wood-smoke: soft, translucent, unlit-ish grey."""
    if "mine_smoke" in medkit._MAT_CACHE:
        return medkit._MAT_CACHE["mine_smoke"]
    m, b = medkit._new_mat("mine_smoke")
    b.inputs["Base Color"].default_value = (0.62, 0.63, 0.66, 1.0)
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Alpha"].default_value = 0.22
    for attr, val in (("surface_render_method", "BLENDED"),
                      ("blend_method", "BLEND"),
                      ("show_transparent_back", False),
                      ("use_backface_culling", False)):
        try:
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    m.use_nodes = True
    medkit._MAT_CACHE["mine_smoke"] = m
    return m


def smoke_plume(name, T, h, rng, n=7, wind=-1.0):
    """A lazy diagonal plume: spheres that grow and drift as they rise."""
    out = []
    sm = SMOKE()
    for i in range(n):
        t = i / float(n - 1)
        r = 0.45 + 1.35 * t ** 1.3
        dz = h * (0.16 + 0.95 * t) + i * 0.30
        dx = wind * (0.6 + 4.2 * t * t)
        dy = rng.uniform(-0.5, 0.5) * (0.4 + t)
        out.append(sphere("%s_s%d" % (name, i),
                          T @ T_at(dx, dy, dz, rng.uniform(0, TAU)),
                          r, sm, seg=10, ring=7, squash=0.70))
    return out

def smelter(F, tag, u, v, face=(0, -1), kind=0, rng=None):
    rng = rng or random.Random(9)
    out = []
    stone = ST_WALL()
    dress = ST_DRESS()
    iron = IRON()
    iron_r = IRON_R()
    M = F.M(u, v, 0.0, du=face[0], dv=face[1])

    # platform
    out.append(box(tag + "_plinth", M @ T_at(0, 0, 0.16), (8.4, 7.0, 0.34),
                   dress, bev=0.02))
    z = 0.34
    # furnace body, mouth faces local +Y (the lane)
    out.append(box(tag + "_furn", M @ T_at(-0.5, -1.1, z + 1.45),
                   (3.3, 2.7, 2.9), stone, bev=0.02))
    out.append(box(tag + "_furn2", M @ T_at(-0.5, -1.1, z + 2.95),
                   (3.9, 3.2, 0.32), dress, bev=0.02))
    # glowing mouth, 1.5 x 1.25
    mz = z + 1.05
    out.append(box(tag + "_mouth", M @ T_at(-0.5, 0.30, mz + 0.62),
                   (1.62, 0.30, 1.42), VOID(), bev=0.0))
    out.append(box(tag + "_glow", M @ T_at(-0.5, 0.44, mz + 0.52),
                   (1.34, 0.06, 1.16), FURNACE(), bev=0.0))
    out.append(box(tag + "_ember", M @ T_at(-0.5, 0.50, mz + 0.06),
                   (1.30, 0.10, 0.22), EMBER(), bev=0.0))
    # arch of voussoirs
    for i in range(9):
        a = math.pi * i / 8.0
        out.append(box("%s_arc%d" % (tag, i),
                       M @ T_at(-0.5 + math.cos(a) * 0.92, 0.34,
                                mz + 1.32 + math.sin(a) * 0.24, rz=0.0),
                       (0.34, 0.42, 0.44), dress, bev=0.02))
    for s in (-1, 1):
        out.append(box("%s_arcj%d" % (tag, s),
                       M @ T_at(-0.5 + s * 1.02, 0.30, mz + 0.60),
                       (0.40, 0.34, 1.30), dress, bev=0.02))
    # smoke hood over the mouth
    out.append(cyl("smk_hood", M @ T_at(-0.5, 0.10, z + 3.6, rz=math.pi * 0.25),
                   1.55, 1.30, stone, seg=4, r2=0.62))
    out.append(box(tag + "_hoodbr", M @ T_at(-0.5, -0.55, z + 2.98),
                   (2.5, 1.4, 0.20), dress, bev=0.015))
    # flue to the stack
    out.append(box(tag + "_flue", M @ T_at(-2.6, -1.6, z + 4.55),
                   (1.25, 1.0, 1.15), stone, bev=0.02))
    # chimney: tapered square stack to 15.8 m
    CH_H = 15.4
    QR = math.pi * 0.25
    out.append(cyl("smk_stack", M @ T_at(-2.6, -1.6, CH_H * 0.5 + 0.2, rz=QR),
                   1.46, CH_H, stone, seg=4, r2=1.08))
    out.append(cyl("smk_top", M @ T_at(-2.6, -1.6, CH_H + 0.62, rz=QR),
                   1.02, 0.55, ST_DARK(), seg=4))
    out.append(cyl("smk_hole", M @ T_at(-2.6, -1.6, CH_H + 0.98, rz=QR),
                   0.72, 0.16, VOID(), seg=4))
    for i, zz in enumerate((4.4, 8.2, 12.0)):
        r = 1.46 - (1.46 - 1.08) * (zz / CH_H)
        out.append(cyl("smk_band%d" % i, M @ T_at(-2.6, -1.6, zz, rz=QR),
                       r * 1.035, 0.13, iron_r, seg=4))
    # smoke plume disabled: alpha spheres read as floating blobs in EEVEE
    # quenching trough
    tx, ty = 2.55, 1.55
    out.append(box(tag + "_trough", M @ T_at(tx, ty, z + 0.32),
                   (2.9, 1.05, 0.62), dress, bev=0.02))
    out.append(box(tag + "_troughw", M @ T_at(tx, ty, z + 0.52),
                   (2.55, 0.78, 0.16), WATER(),
                   bev=0.0))
    # trough stand / drain
    out.append(box(tag + "_trd", M @ T_at(tx, ty + 0.62, z + 0.10),
                   (0.30, 0.30, 0.30), stone))
    # bellows
    bx, by = -2.9, 2.1
    out.append(box(tag + "_bel", M @ T_at(bx, by, z + 0.62), (1.15, 1.5, 1.05),
                   mat_wood("mine_leather", base="#4a3626", light="#63492f"),
                   bev=0.02))
    out.append(box(tag + "_belw", M @ T_at(bx, by + 0.78, z + 0.72),
                   (1.25, 0.16, 0.30), WOOD_M(), bev=0.01))
    out.append(cyl(tag + "_belt", M @ T_at(bx + 0.25, by + 1.1, z + 0.78),
                   0.10, 0.9, WOOD_D(), seg=8))
    # anvil on a stump
    ax, ay = 1.5, -0.55
    out.append(cyl(tag + "_stump", M @ T_at(ax, ay, z + 0.30), 0.34, 0.60,
                   WOOD_M(), seg=10))
    out.append(box(tag + "_anv", M @ T_at(ax, ay, z + 0.72), (0.72, 0.30, 0.24),
                   iron, bev=0.02))
    out.append(cone(tag + "_horn", M @ T_at(ax + 0.48, ay, z + 0.74,
                                           ry=-math.pi * 0.5), 0.15, 0.34,
                    iron, seg=8))
    # tool rack on the wall
    out.append(box(tag + "_tr", M @ T_at(-0.5, 0.34, z + 2.55),
                   (2.5, 0.12, 0.10), WOOD_D()))
    for i in range(4):
        out.append(cyl("%s_tl%d" % (tag, i),
                       M @ T_at(-1.5 + i * 0.62, 0.42, z + 2.20),
                       0.026, 0.8, iron, seg=5))
    # coal heap
    for i in range(8):
        out.append(rock("%s_coal%d" % (tag, i),
                        M @ T_at(rng_u(-3.3, 0.9, i), rng_u(1.0, 2.9, i + 40),
                                 z + rng_u(0.0, 0.28, i + 7)),
                        rng_u(0.13, 0.26, i + 3),
                        random.Random(i * 17 + 5), VOID(), squash=0.7))
    # gable roof over the working floor, ridge along the lane
    for i, (px, py) in enumerate(((-3.9, 3.0), (3.9, 3.0), (-3.9, -0.3),
                                  (3.9, -0.3))):
        out.append(box("%s_pp%d" % (tag, i), M @ T_at(px, py, z + 1.65),
                       (0.18, 0.18, 3.3), WOOD_D(), bev=0.01))
    RM2 = M @ T_at(0, 1.35, 0, rz=math.pi * 0.5)
    out.append(gable_roof(tag + "_pr", RM2, 6.2, 8.4, z + 3.30, 20.0,
                          BROWN(), WOOD_M(), ov_side=0.34, ov_gable=0.30,
                          thick=0.12))
    for i in range(5):
        out.append(box("%s_pb%d" % (tag, i), M @ T_at(-3.4 + i * 1.7, 2.6,
                                                      z + 2.95),
                       (0.10, 5.4, 0.12), WOOD_D()))
    out.append(box(tag + "_pw", M @ T_at(0, 1.55, z + 0.02),
                   (7.6, 5.6, 0.06), GRAVEL()))
    return out


def rng_u(a, b, seed):
    return random.Random(seed * 7919 + 13).uniform(a, b)


# --------------------------------------------------------------------------
# ore yard
# --------------------------------------------------------------------------
def ore_yard(F, tag, u, v, rng, w=9.0, d=13.0):
    out = []
    out.append(fbox(F, tag + "_pad", u, v, -0.03, w, d, 0.10, GRAVEL()))
    # sorting shed: posts + a plank gable roof, open sides
    sx, sy = 1.9, 2.6
    for i, (du, dv) in enumerate(((-sx, -sy), (sx, -sy), (-sx, sy), (sx, sy))):
        out.append(fbox(F, "%s_sh%d" % (tag, i), u + du, v + dv, 0.0, 0.20, 0.20,
                        3.0, WOOD_D(), bev=0.01))
    out.append(fbox(F, "%s_shb1" % tag, u, v - sy, 2.95, sx * 2 + 0.4, 0.20, 0.20,
                    WOOD_D()))
    out.append(fbox(F, "%s_shb2" % tag, u, v + sy, 2.95, sx * 2 + 0.4, 0.20, 0.20,
                    WOOD_D()))
    RM = F.M(u, v, 0.0, du=0, dv=-1)
    out.append(gable_roof(tag + "_sroof", RM, sx * 2 + 1.2, sy * 1.6 + 1.0, 3.15,
                          32.0, SHINGLE(), WOOD_D()))
    # sorting table
    out.append(fbox(F, tag + "_tbl", u - 0.4, v - 0.6, 0.76, 1.0, 3.4, 0.12,
                    PLANK(), bev=0.01))
    for i in range(4):
        out.append(fbox(F, "%s_tl%d" % (tag, i), u - 0.4 + (0.4 if i % 2 else -0.4),
                        v - 0.6 + (1.45 if i < 2 else -1.45), 0.0, 0.12, 0.12,
                        0.76, WOOD_D()))
    # sorted piles: pyramids of ore chunks
    for pi, (du, dv, n, rr) in enumerate(((-2.4, 2.6, 4, 0.20),
                                          (0.6, 3.4, 3, 0.17),
                                          (-1.4, -3.6, 4, 0.19))):
        for row in range(3):
            cnt = n - row
            for k in range(cnt):
                out.append(rock("%s_p%d_%d_%d" % (tag, pi, row, k),
                                F.Mz(u + du + (k - (cnt - 1) * 0.5) * rr * 2.1,
                                     v + dv, row * rr * 1.15,
                                     rng.uniform(0, TAU)),
                                rr * rng.uniform(0.85, 1.15), rng,
                                ORE_C() if (k + row) % 3 == 0 else ORE(),
                                squash=0.78))
    # a few big lumps on the pad
    for i in range(5):
        out.append(rock("%s_big%d" % (tag, i),
                        F.Mz(u + rng.uniform(-3.6, 3.6), v + rng.uniform(-5.4, 5.4),
                              0.0, rng.uniform(0, TAU)),
                        rng.uniform(0.28, 0.46), rng, ORE(), squash=0.66))
    # crates, sacks, a parked cart
    out += crate_pile(tag + "_cp", F.Mz(u + 3.1, v - 4.4, 0, 0.3), rng)
    out += medbuild.sack(tag + "_s1", F.Mz(u - 3.2, v - 1.9, 0, 0.4), rng=rng)
    out += medbuild.sack(tag + "_s2", F.Mz(u - 2.85, v - 2.35, 0, 1.1), rng=rng)
    out += medbuild.sack(tag + "_s3", F.Mz(u - 3.35, v - 2.5, 0, 2.2), rng=rng)
    out += mine_cart(tag + "_cart", F.M(u + 2.4, v + 0.2, 0, du=1, dv=0), rng,
                     ore=True)
    # a hand-cranked winch over the shaft-like hopper
    for s in (-1, 1):
        out.append(fbox(F, "%s_gh%d" % (tag, s), u - 3.6, v + 5.0 + s * 0.7, 0.0,
                        0.18, 0.18, 2.1, WOOD_D()))
    out.append(fbox(F, "%s_ghb" % tag, u - 3.6, v + 5.0, 2.0, 0.24, 1.9, 0.22,
                    WOOD_D()))
    out.append(cyl("oy_drum", F.M(u - 3.6, v + 5.0, 1.55, du=1, dv=0) @
                   T_at(0, 0, 0, ry=math.pi * 0.5), 0.30, 0.60, IRON_R(), seg=12))
    return out


# --------------------------------------------------------------------------
# well / cistern / bell
# --------------------------------------------------------------------------
def cistern(F, tag, u, v):
    """A sunken stone cistern with a plank cover and a bucket crane."""
    out = []
    stone = ST_DRESS()
    out.append(fbox(F, tag + "_rim", u, v, 0.0, 3.4, 3.4, 0.62, stone, bev=0.02))
    out.append(fbox(F, tag + "_wat", u, v, 0.40, 2.7, 2.7, 0.22,
                    mat_water("mine_water", base="#6d8d86")))
    for i, (du, dv) in enumerate(((-1.6, -1.6), (1.6, -1.6), (-1.6, 1.6), (1.6, 1.6))):
        out.append(fbox(F, "%s_p%d" % (tag, i), u + du, v + dv, 0.60, 0.16, 0.16,
                        2.5, WOOD_D()))
    out.append(fbox(F, tag + "_beam", u, v, 3.05, 3.7, 0.16, 0.18, WOOD_D()))
    out.append(cyl(tag + "_rope", at(*F.P(u, v, 0)) @ T_at(0, 0, 2.38),
                   0.02, 1.3, ROPE(), seg=5))
    out.append(fcyl(F, tag + "_bucket", u, v, 1.02, 0.20, 0.26, WOOD_M(), seg=10))
    out.append(fbox(F, tag + "_roof", u, v, 3.18, 4.1, 2.6, 0.12, PLANK(), bev=0.01))
    return out


def bell_post(F, tag, u, v, rng):
    out = []
    out.append(fbox(F, tag + "_b", u, v, 0.0, 1.2, 1.2, 0.34, ST_DRESS(), bev=0.02))
    out.append(fbox(F, tag + "_p", u, v, 0.30, 0.22, 0.22, 4.30, WOOD_D(), bev=0.01))
    out.append(fbox(F, tag + "_arm", u, v, 4.35, 1.9, 0.16, 0.18, WOOD_D()))
    out.append(fbox(F, tag + "_br", u - 0.78, v, 3.60, 0.12, 0.12, 0.80, WOOD_D(),
                    bev=0.008))
    # bell
    bm = F.M(u + 0.86, v, 4.18, du=1, dv=0)
    out.append(cone(tag + "_bell", bm @ T_at(0, 0, -0.26), 0.30, 0.52, IRON_R(),
                    seg=10))
    out.append(cyl(tag + "_bellt", bm @ T_at(0, 0, -0.02), 0.10, 0.10, IRON(),
                   seg=8))
    out.append(cyl(tag + "_rope", bm @ T_at(0, 0.30, -1.5), 0.018, 2.4, ROPE(),
                   seg=5))
    # little canopy
    out.append(gable_roof(tag + "_rf", F.M(u, v, 0), 2.4, 1.4, 4.62, 36.0,
                          BROWN(), WOOD_D(), ov_side=0.25, ov_gable=0.2))
    return out


# --------------------------------------------------------------------------
# scaffold
# --------------------------------------------------------------------------
def scaffold(F, tag, u, v, h=5.4, w=2.4, d=1.6):
    out = []
    for iu in (-1, 1):
        for iv in (-1, 1):
            out.append(fbox(F, "%s_p%d%d" % (tag, iu, iv), u + iu * w * 0.5,
                            v + iv * d * 0.5, 0.0, 0.14, 0.14, h, WOOD_M(),
                            bev=0.008))
    for k, zz in enumerate((1.7, 3.3, 5.0)):
        out.append(fbox(F, "%s_d%d" % (tag, k), u, v, zz, w + 0.4, d + 0.3, 0.10,
                        PLANK(), bev=0.008))
        for iu in (-1, 1):
            out.append(fbox(F, "%s_r%d%d" % (tag, k, iu), u + iu * w * 0.5,
                            v, zz + 0.52, 0.09, d + 0.3, 0.09, WOOD_M()))
    out += ladder(tag + "_ld", F.M(u + w * 0.5 + 0.1, v, 0, du=0, dv=-1), h=h,
                  wood=WOOD_M())
    return out


# --------------------------------------------------------------------------
# ground
# --------------------------------------------------------------------------
def ground(F, u_lo, u_hi, lane_mat, rng, v_lo=-17.0, v_hi=38.6,
           u_ext=60.0):
    """Returns (plate, lane, yard).

    The plate top is exactly z = 0.00 and it is extended downward as a 2 m
    buried skirt, so no exposed plinth stripe can read against the overworld
    terrain. Its side faces are natural rock, never a flat brown fill.
    """
    plate, lane, yard = [], [], []
    um = (u_lo + u_hi) * 0.5
    plate.append(fbox(F, "ground", 0.0, (v_lo + v_hi) * 0.5 + 0.30, -2.00,
                      u_ext * 2.0, v_hi - v_lo - 0.60, 2.00, ROCK()))
    plate.append(fbox(F, "ground_edge", 0.0, v_lo + 0.30, -2.00,
                      u_ext * 2.0, 0.60, 2.00, ROCK()))
    yard.append(fbox(F, "yard", 0.0, (v_lo + v_hi) * 0.5, -0.02,
                     u_ext * 2.0, v_hi - v_lo, 0.08, GRAVEL()))
    lane.append(fbox(F, "lane", um, 0.0, 0.05,
                     u_hi - u_lo, LANE_HALF * 2, 0.06, lane_mat))
    # wheel ruts / worn strips
    for s in (-1, 1):
        lane.append(fbox(F, "rut%d" % s, um, s * 1.35, 0.09,
                         u_hi - u_lo, 0.55, 0.02,
                         mat_earth("mine_rut", base="#6a6154", dark="#4b4438")))
    # muddy yard patches
    for i in range(12):
        yard.append(fbox(F, "patch%d" % i, rng.uniform(u_lo, u_hi),
                         rng.uniform(v_lo + 1.0, 4.2), 0.05,
                         rng.uniform(1.2, 3.0), rng.uniform(0.8, 2.2), 0.03,
                         mat_earth("mine_mud%d" % (i % 3), base="#5e5546",
                                   dark="#423b2f")))
    # drainage channel beside the lane
    lane.append(fbox(F, "gutter", um, -LANE_HALF - 0.20, 0.02,
                     u_hi - u_lo, 0.42, 0.06, ST_DARK()))
    return plate, lane, yard


def fence_line(F, tag, u0, u1, v, z, rail_mat=None, post_mat=None,
               spacing=2.25, h=1.12):
    """Post-and-rail fence: square posts with footings, thin rails.

    Rail section is 0.10 x 0.06 so the run can never read as a ladder; posts
    stand 0.16 m above the top rail and every post sits on its own footing.
    """
    out = []
    rail_mat = rail_mat or WOOD_D()
    post_mat = post_mat or WOOD_M()
    L = u1 - u0
    n = max(2, int(round(L / spacing)) + 1)
    step = L / (n - 1)
    pw = 0.13
    for i in range(n):
        u = u0 + step * i
        out.append(fbox(F, "%s_p%d" % (tag, i), u, v, z, pw, pw, h + 0.16,
                        post_mat, bev=0.008))
        out.append(fbox(F, "%s_f%d" % (tag, i), u, v, z, 0.34, 0.34, 0.14,
                        ST_DARK()))
    for i, zz in enumerate((0.60, 0.98)):
        out.append(fbox(F, "%s_r%d" % (tag, i), (u0 + u1) * 0.5, v,
                        z + zz, L, 0.06, 0.10, rail_mat))
    return out


def down_bench(F, tag, u0, u1, v_face, z_top, z_bench, depth, rng,
               wall_mat=None, top_mat=None, buttress=8.0):
    """Retaining wall holding up the lane bench, plus the bench it drops to."""
    out = []
    wm = wall_mat or ST_RISER()
    tm = top_mat or COBBLE()
    h = z_top - z_bench
    um = (u0 + u1) * 0.5
    L = u1 - u0
    out.append(fbox(F, tag + "_w", um, v_face + 0.35, z_bench,
                    L, 0.70, h + 0.08, wm, bev=0.02))
    out.append(fbox(F, tag + "_sh", um, v_face + 0.33, z_top - 0.46,
                    L, 0.74, 0.32, ST_SHADOW()))
    out.append(fbox(F, tag + "_cp", um, v_face + 0.40, z_top - 0.16,
                    L, 1.06, 0.26, ST_LIP(), bev=0.012))
    # the bench itself
    out.append(fbox(F, tag + "_f", um, v_face - depth * 0.5, z_bench - 0.30,
                    L, depth, 0.30, ST_DARK()))
    out.append(fbox(F, tag + "_t", um, v_face - depth * 0.5, z_bench - 0.05,
                    L, depth - 0.05, 0.10, tm))
    nb = max(1, int(L / buttress))
    for k in range(nb):
        ub = u0 + L * (k + 0.5) / nb
        out.append(fbox(F, tag + "_bt%d" % k, ub, v_face + 0.02, z_bench,
                        0.60, 0.66, h - 0.05, wm, bev=0.02))
    return out


def bench_scree(F, tag, u0, u1, v0, v1, z, rng):
    """Break up the empty lower bench: scree, timber stacks, a lean-to, pines."""
    out = []
    for i in range(22):
        out.append(rock("%s_rk%d" % (tag, i),
                        F.Mz(rng.uniform(u0, u1), rng.uniform(v0, v1), z,
                             rng.uniform(0, TAU)),
                        rng.uniform(0.28, 0.95), rng, ROCK(), squash=0.62))
    for i in range(3):
        uu = rng.uniform(u0 + 4.0, u1 - 4.0)
        vv = rng.uniform(v0 + 1.0, v1 - 1.0)
        out += plank_stack("%s_pl%d" % (tag, i), F.Mz(uu, vv, z, 0.0),
                           n=5, L=rng.uniform(1.8, 2.8), rng=rng)
    for i in range(4):
        uu = rng.uniform(u0 + 3.0, u1 - 3.0)
        vv = rng.uniform(v0 + 1.0, v1 - 1.0)
        out += medbuild.barrel("%s_br%d" % (tag, i), F.Mz(uu, vv, z, 0.0),
                               rng=rng)
    for i in range(6):
        out += conifer(F, "%s_pn%d" % (tag, i), rng.uniform(u0, u1),
                       rng.uniform(v0 + 0.5, v1 - 0.5), z - 0.05,
                       rng.uniform(6.0, 10.5), rng)
    return out

def valley(F, tag, u0, u1, v0, v1, z, rng):
    """The drop below the town: a dark valley floor with scree and pines."""
    out = []
    um = (u0 + u1) * 0.5
    out.append(fbox(F, tag + "_f", um, (v0 + v1) * 0.5, z - 1.2,
                    u1 - u0, v1 - v0, 1.2, GRASS_D()))
    for i in range(26):
        r = rng.uniform(0.4, 1.7)
        out.append(rock("%s_r%d" % (tag, i),
                        F.Mz(rng.uniform(u0, u1), rng.uniform(v0 + 1.0, v1 - 1.0),
                             z - 0.2, rng.uniform(0, TAU)),
                        r, rng, ST_DARK(), squash=0.55))
    # a dry stream bed winding along the valley floor
    vv = (v0 + v1) * 0.5
    for i in range(9):
        out.append(fbox(F, "%s_bed%d" % (tag, i), u0 + 4.0 + i * (u1 - u0 - 8) / 9.0,
                        vv + math.sin(i * 0.8) * 3.0, z - 0.05, 5.0, 2.4, 0.12,
                        mat_earth("mine_stream", base="#7d7466",
                                  dark="#5c554a")))
    for k in range(14):
        out += conifer(F, "%s_p%d" % (tag, k),
                       rng.uniform(u0 + 1.0, u1 - 1.0),
                       rng.uniform(v0 + 1.0, v1 - 1.0), z - 0.05,
                       rng.uniform(5.5, 9.5), rng)
    return out


def ridge(F, tag, u0, u1, v0, z0, rng, steps=3):
    """Mountain slope continuing up behind the top berm."""
    out = []
    v = v0
    z = z0
    for i in range(steps):
        run = 6.0 + i * 2.0
        rise = 3.2 + i * 1.4
        out.append(fbox(F, "%s_m%d" % (tag, i), (u0 + u1) * 0.5, v + run * 0.5,
                        0.0, u1 - u0, run, z + rise, CLIFF()))
        out.append(fbox(F, "%s_t%d" % (tag, i), (u0 + u1) * 0.5, v + run * 0.5,
                        z + rise - 0.06, u1 - u0, run, 0.12, GRAVEL()))
        out.append(fbox(F, "%s_l%d" % (tag, i), (u0 + u1) * 0.5, v + 0.55,
                        z + rise - 0.16, u1 - u0, 1.10, 0.24, ST_LIP()))
        for k in range(8):
            out.append(rock("%s_r%d%d" % (tag, i, k),
                            F.Mz(rng.uniform(u0, u1), v + rng.uniform(0.0, run),
                                 z + rise - 0.2, rng.uniform(0, TAU)),
                            rng.uniform(0.5, 1.8), rng, ROCK(), squash=0.6))
        for k in range(5):
            out += conifer(F, "%s_p%d%d" % (tag, i, k),
                           rng.uniform(u0 + 2.0, u1 - 2.0),
                           v + rng.uniform(1.5, run - 1.0),
                           z + rise - 0.05, rng.uniform(7.0, 11.5), rng)
        v += run
        z += rise
    return out, v, z


# --------------------------------------------------------------------------
# hillside berms beyond the top terrace
# --------------------------------------------------------------------------
def berms(F, tag, u0, u1, v0, z0, rng, steps=4):
    out = []
    z = z0
    v = v0
    for i in range(steps):
        rise = 2.0 + i * 0.7
        run = 4.2 + i * 0.6
        out.append(fbox(F, "%s_w%d" % (tag, i), (u0 + u1) * 0.5, v + 0.35, 0.0,
                        u1 - u0, 0.70, z, CLIFF(), bev=0.02))
        out.append(fbox(F, "%s_l%d" % (tag, i), (u0 + u1) * 0.5, v + 0.45,
                        z + rise - 0.16, u1 - u0, 0.95, 0.24, ST_LIP()))
        out.append(fbox(F, "%s_t%d" % (tag, i), (u0 + u1) * 0.5, v + run * 0.5 + 0.7,
                        0.0, u1 - u0, run, z + rise, DIRT()))
        out.append(fbox(F, "%s_g%d" % (tag, i), (u0 + u1) * 0.5, v + run * 0.5 + 0.7,
                        z + rise - 0.03, u1 - u0, run, 0.08, GRAVEL()))
        # scattered boulders along each riser
        for k in range(6):
            out.append(rock("%s_r%d%d" % (tag, i, k),
                            F.Mz(rng.uniform(u0, u1), v + rng.uniform(0.0, run),
                                 z + rise - 0.1, rng.uniform(0, TAU)),
                            rng.uniform(0.22, 0.55), rng, ROCK(), squash=0.65))
        # a few pines standing on every tread
        for k in range(3):
            hh = rng.uniform(6.0, 10.0)
            out += conifer(F, "%s_p%d%d" % (tag, i, k),
                           rng.uniform(u0 + 2.0, u1 - 2.0),
                           v + rng.uniform(1.4, run - 1.0),
                           z + rise - 0.05, hh, rng)
        z += rise
        v += run
    return out, v, z


def PINE():
    return mat_foliage("mine_pine", base="#16281b", light="#25412b", scale=6.0)


def conifer(F, tag, u, v, z, h, rng, leaf=None):
    """Dark, narrow mountain spruce — a hard-tapering spire of stacked skirts.

    medbuild.tree's conifer alternates a bright green second-tier material, which
    reads as a toy pine at town scale; this keeps one dark foliage material and a
    much narrower profile so the treeline stays behind the buildings.
    """
    leaf = leaf or PINE()
    T = F.Mz(u, v, z, rng.uniform(0, TAU))
    parts = [cyl(tag + "_tr", T @ T_at(0, 0, h * 0.30), 0.115, h * 0.62,
                 WOOD_D(), seg=8)]
    n = rng.randint(4, 6)
    r = h * rng.uniform(0.150, 0.185)
    for i in range(n):
        t = i / float(n - 1)
        zz = h * (0.20 + 0.72 * t)
        rr = r * (1.0 - 0.80 * t) * rng.uniform(0.90, 1.08)
        hh = h * (0.30 - 0.055 * t)
        jx = rng.uniform(-0.10, 0.10) * r
        parts.append(cone(tag + "_sk%d" % i,
                          T @ T_at(jx, rng.uniform(-0.07, 0.07) * r, zz),
                          rr, hh, leaf, seg=9))
    return parts



# ==========================================================================
# town layout v2 -- world space (+X east, +Y north, z up)
#
# The old layout authored everything in a lane frame and pushed whole terraces
# across the plate, which is why the town read as "houses standing on a gravel
# car park".  This one keeps the same vocabulary of builders but places them
# from a street spine: every house sits on the frontage line of a real road,
# the gaps between neighbours are closed by stone close-walls, and the whole
# core is paved by the town itself (plate + earth blanket + road/plaza/yard).
# ==========================================================================
R2 = math.pi * 0.5
HW = 2.40                 # main street half width -> 4.80 m clear
CORE = (0.0, 2.0)
CORE_R = 24.0

RUNS = []                 # wall runs, (p0, p1, name) for the attachment check
RECTS = []                # building footprints, (cx, cy, hw, hd, ang)
SOLIDS = []               # free-standing solid anchors, (x, y, r)
GROUPS = []


# ---------------------------------------------------------------- geometry
def fix_normals(ob):
    """Recalculate outward normals on a closed solid built by hand."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _solid(name, top, bot, mat):
    n = len(top)
    verts = [(x, y, z) for (x, y, z) in top] + [(x, y, z) for (x, y, z) in bot]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = mesh_obj(name, verts, faces)
    assign(ob, mat)
    fix_normals(ob)
    return ob


def plate(name, pts, z=0.0, zb=-2.0, flare=1.8, mat=None):
    """Town plate: flat paved top, 2 m buried skirt leaning outward.

    Top surface stays at exactly z = 0 -- the Unity prefab and the vegetation
    masks depend on that, so nothing here may lift it.
    """
    cx = sum(p[0] for p in pts) / float(len(pts))
    cy = sum(p[1] for p in pts) / float(len(pts))
    top = [(x, y, z) for (x, y) in pts]
    bot = []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        bot.append((x + dx / L * flare, y + dy / L * flare, zb))
    return _solid(name, top, bot, mat or ROCK())


def poly_slab(name, pts, z, thick=0.6, mat=None):
    top = [(x, y, z) for (x, y) in pts]
    bot = [(x, y, z - thick) for (x, y) in pts]
    return _solid(name, top, bot, mat or DIRT())


def ribbon(name, nodes, mat, z=0.05, depth=0.9, wob=0.0, seed=0):
    """One continuous paved surface along a polyline; nodes=(x, y, half_w)."""
    r = random.Random(seed)
    n = len(nodes)
    pts = [(p[0], p[1]) for p in nodes]
    norms = []
    for i in range(n):
        if i == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif i == n - 1:
            dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
        else:
            ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
            bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            la, lb = math.hypot(ax, ay) or 1.0, math.hypot(bx, by) or 1.0
            dx, dy = ax / la + bx / lb, ay / la + by / lb
        L = math.hypot(dx, dy) or 1.0
        norms.append((-dy / L, dx / L))
    verts = []
    for (p, nv, nd) in zip(pts, norms, nodes):
        hl = nd[2] + r.uniform(-wob, wob)
        hr = nd[2] + r.uniform(-wob, wob)
        verts.append((p[0] + nv[0] * hl, p[1] + nv[1] * hl, z))
        verts.append((p[0] - nv[0] * hr, p[1] - nv[1] * hr, z))
    m = 2 * n
    for i in range(n):
        x0, y0, _ = verts[2 * i]
        x1, y1, _ = verts[2 * i + 1]
        verts.append((x0, y0, z - depth))
        verts.append((x1, y1, z - depth))
    faces = []
    for i in range(n - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 2))
        faces.append((a + 1, a + 3, a + 2))
    for i in range(n - 1):
        for vi in (0, 1):
            p, q = 2 * i + vi, 2 * (i + 1) + vi
            pb, qb = m + 2 * i + vi, m + 2 * (i + 1) + vi
            faces.append((p, pb, q))
            faces.append((pb, qb, q))
    for i in (0, n - 1):
        a, b = 2 * i, 2 * i + 1
        ab, bb = m + 2 * i, m + 2 * i + 1
        faces.append((a, ab, b))
        faces.append((ab, bb, b))
    ob = mesh_obj(name, verts, faces, smooth=False)
    assign(ob, mat)
    fix_normals(ob)
    return ob


def beam(name, p0, p1, w, mat, w2=None, bev=0.0):
    """Square-section timber between two 3-D points (legs, braces, rails)."""
    a = Vector(p0)
    b = Vector(p1)
    d = b - a
    L = d.length
    if L < 1e-4:
        return None
    T = (Matrix.Translation((a + b) * 0.5)
         @ d.to_track_quat("Z", "Y").to_matrix().to_4x4())
    return box(name, T, (w, w2 if w2 else w, L), mat, bev=bev)


def wall(name, p0, p1, z, h=1.9, mat=None, thick=0.44, cap=True, piers=True):
    """Stone close-wall between two points: body + coping + end piers."""
    out = []
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 0.06:
        return out
    ang = math.atan2(-dx, dy)
    T = at((x0 + x1) * 0.5, (y0 + y1) * 0.5, z, rz=ang)
    m = mat or ST_WALL()
    out.append(box(name, T @ T_at(0, 0, h * 0.5), (thick, L, h), m, bev=0.02))
    if cap:
        out.append(box(name + "_cp", T @ T_at(0, 0, h + 0.07),
                       (thick + 0.18, L + 0.04, 0.15), ST_LIP(), bev=0.012))
    if piers:
        for s in (-1, 1):
            out.append(box("%s_p%d" % (name, s),
                           T @ T_at(0, s * (L * 0.5 - 0.16), (h + 0.30) * 0.5),
                           (thick + 0.12, 0.44, h + 0.30), m, bev=0.015))
    RUNS.append((Vector((x0, y0, z)), Vector((x1, y1, z)), name))
    return out


def hwall(name, p0, p1, z, h=1.15, mat=None):
    """Low parapet / kerb wall (no coping, no piers) for terrace edges."""
    out = []
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 0.06:
        return out
    T = at((x0 + x1) * 0.5, (y0 + y1) * 0.5, z, rz=math.atan2(-dx, dy))
    out.append(box(name, T @ T_at(0, 0, h * 0.5), (0.40, L, h), mat or ST_WALL(),
                   bev=0.015))
    out.append(box(name + "_cp", T @ T_at(0, 0, h + 0.05),
                   (0.52, L, 0.11), ST_LIP(), bev=0.01))
    RUNS.append((Vector((x0, y0, z)), Vector((x1, y1, z)), name))
    return out


def dbl_roof(name, T, w, d, rise, mat, over=0.34, thick=0.15):
    """Gable roof over a T whose local X is the ridge direction."""
    out = []
    hd = d * 0.5 + over
    sl = math.hypot(hd, rise)
    a = math.atan2(rise, hd)
    for s in (-1, 1):
        Tp = T @ T_at(0, s * hd * 0.5, rise * 0.5, rx=-s * a)
        out.append(box("%s_r%d" % (name, s), Tp,
                       (w + over * 2.0, sl, thick), mat, bev=0.008))
    out.append(box(name + "_rdg", T @ T_at(0, 0, rise + 0.02),
                   (w + over * 2.0, 0.24, 0.13), mat))
    return out


def ramp_bed(name, p0, p1, z0, z1, w, mat, thick=0.55):
    """Graded slab following (x0,y0,z0)->(x1,y1,z1); returns (ob, matrix)."""
    a = Vector((p0[0], p0[1], z0))
    b = Vector((p1[0], p1[1], z1))
    d = b - a
    L = d.length
    T = (Matrix.Translation((a + b) * 0.5)
         @ d.to_track_quat("Z", "Y").to_matrix().to_4x4())
    return box(name, T, (w, thick, L), mat), T, L


# ---------------------------------------------------------------- props
def well_plaza(name, x, y, z=0.07, rng=None):
    """Stone-ringed well: kerb ring, shaft, windlass, hood, trough, bench."""
    rng = rng or random.Random(5)
    out = []
    for i in range(18):
        a = TAU * i / 18.0
        T = at(x + 1.62 * math.cos(a), y + 1.62 * math.sin(a), z + 0.10, rz=-a)
        out.append(box("%s_kb%d" % (name, i), T, (0.32, 0.58, 0.24), ST_DRESS(),
                       bev=0.012))
    out.append(cyl(name + "_sh", at(x, y, z), 1.18, 0.94, ST_WALL(), seg=16))
    out.append(cyl(name + "_in", at(x, y, z + 0.62), 0.99, 0.14, ST_DARK(), seg=16))
    out.append(cyl(name + "_wa", at(x, y, z + 0.75), 0.93, 0.06,
                   WATER(), seg=16))
    out.append(cyl(name + "_rim", at(x, y, z + 0.92), 1.24, 0.16, ST_STEP(),
                   seg=16))
    for s in (-1, 1):
        out.append(box("%s_po%d" % (name, s), at(x + s * 1.28, y, z + 1.30),
                       (0.17, 0.17, 2.60), WOOD_D(), bev=0.01))
    out.append(beam(name + "_ax", (x - 1.30, y, z + 2.28), (x + 1.30, y, z + 2.28),
                    0.16, WOOD_D()))
    out.append(cyl(name + "_dr", at(x - 0.55, y, z + 2.34, rx=R2), 0.20, 1.10,
                   WOOD_M(), seg=12))
    out.append(beam(name + "_rp", (x - 0.05, y, z + 2.34), (x - 0.05, y, z + 1.62),
                    0.05, ROPE()))
    out.append(cyl(name + "_bk", at(x - 0.05, y, z + 1.20), 0.20, 0.30, PLANK(),
                   seg=10, r2=0.16))
    for s in (-1, 1):
        Tp = at(x, y + s * 0.98, z + 2.86, rz=R2, rx=s * 0.62)
        out.append(box("%s_rf%d" % (name, s), Tp, (3.5, 1.42, 0.10), SHINGLE(),
                       bev=0.008))
    out.append(box(name + "_rdg", at(x, y, z + 3.30), (3.6, 0.24, 0.12), PLANK()))
    # trough + bench, the well's little story
    out.append(box(name + "_tr", at(x + 2.55, y - 0.9, z + 0.34),
                   (0.90, 2.10, 0.62), ST_WALL(), bev=0.02))
    out.append(box(name + "_trw", at(x + 2.55, y - 0.9, z + 0.68),
                   (0.62, 1.82, 0.05), WATER()))
    out.append(box(name + "_bn", at(x - 2.35, y + 1.55, z + 0.48),
                   (1.85, 0.42, 0.11), PLANK(), bev=0.01))
    SOLIDS.append((x, y, 1.9))
    return out


def stall(name, x, y, ang=0.0, rng=None):
    """Market stall: four posts, plank counter, sack awning, baskets."""
    rng = rng or random.Random(9)
    F = Frame(x, y, R2 + ang)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(fbox(F, "%s_p%d%d" % (name, sx, sy), sx * 1.45,
                            sy * 1.05, 0.0, 0.14, 0.14, 2.30, WOOD_D(), bev=0.008))
    out.append(fbox(F, name + "_ct", 0.0, -0.15, 0.86, 3.10, 2.35, 0.12, PLANK(),
                    bev=0.01))
    out.append(fbox(F, name + "_cf", 0.0, -1.28, 0.0, 3.10, 0.10, 0.92, PLANK()))
    for s in (-1, 1):
        out.append(fbox(F, "%s_aw%d" % (name, s), 0.0, s * 0.72, 2.26,
                        3.5, 1.5, 0.09, mat_cloth("sack", "#c9b990",
                                                  rough=0.92), bev=0.0))
    for i in range(5):
        out.append(fbox(F, "%s_bk%d" % (name, i), -1.1 + i * 0.55,
                        rng.uniform(-0.6, 0.2), 0.98, 0.42, 0.40, 0.34,
                        mat_cloth("sack", "#c9b990", rough=0.92), bev=0.01))
    out.append(fbox(F, name + "_br", -1.15, -1.42, 0.0, 0.52, 0.52, 0.46,
                    PLANK(), bev=0.01))
    SOLIDS.append((x, y, 1.7))
    return out


def board(name, x, y, ang=0.0):
    """Notice board: two posts, a plank panel, three pale notices."""
    F = Frame(x, y, R2 + ang)
    out = []
    for s in (-1, 1):
        out.append(fbox(F, "%s_p%d" % (name, s), s * 0.92, 0.0, 0.0, 0.14, 0.14,
                        2.10, WOOD_D(), bev=0.008))
    out.append(fbox(F, name + "_bd", 0.0, 0.02, 1.02, 1.92, 0.09, 0.98, PLANK(),
                    bev=0.01))
    out.append(fbox(F, name + "_rf", 0.0, 0.10, 2.02, 2.16, 0.62, 0.08, SHINGLE(),
                    bev=0.006))
    for i in range(3):
        out.append(fbox(F, "%s_nt%d" % (name, i), -0.58 + i * 0.58, -0.04,
                        1.18, 0.42, 0.02, 0.52,
                        mat_cloth("sack", "#d8ccab", rough=0.9)))
    return out


def banner(name, x, y, z=0.0, h=5.2, ang=0.0):
    """Tall banner pole with a hanging cloth."""
    out = [cyl(name + "_po", at(x, y, z), 0.09, h, WOOD_D(), seg=8)]
    out.append(box(name + "_cb", at(x, y, z + h - 0.30), (0.06, 1.55, 0.06),
                   WOOD_D()))
    out.append(box(name + "_cl", at(x, y + 0.72, z + h - 1.30),
                   (0.05, 0.92, 1.72),
                   mat_cloth("bloom", "#8d3b32", rough=0.94), bev=0.0))
    out.append(box(name + "_kn", at(x, y, z + h + 0.06), (0.18, 0.18, 0.20),
                   IRON(), bev=0.01))
    SOLIDS.append((x, y, 0.4))
    return out


def laundry(name, p0, p1, z, rng=None):
    """Washing line between two posts, four cloths, a basket below."""
    rng = rng or random.Random(13)
    out = []
    for i, p in enumerate((p0, p1)):
        out.append(box("%s_p%d" % (name, i), at(p[0], p[1], z + 0.95),
                       (0.11, 0.11, 1.90), WOOD_D(), bev=0.008))
    d = Vector((p1[0] - p0[0], p1[1] - p0[1], 0.0))
    L = d.length
    if L < 0.3:
        return out
    ang = math.atan2(-d.x, d.y)
    T = at((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, z + 1.78, rz=ang)
    out.append(box(name + "_ln", T, (0.03, L, 0.03), ROPE()))
    for i in range(4):
        u = -L * 0.5 + 0.35 + i * (L - 0.7) / 3.0
        out.append(box("%s_cl%d" % (name, i),
                       T @ T_at(rng.uniform(-0.04, 0.04), u, -0.66),
                       (0.04, rng.uniform(0.42, 0.66), 1.28),
                       mat_cloth(["cloth_bloom", "cloth_sack"][i % 2],
                                 "#cfc4a6", rough=0.9), bev=0.0))
    return out


def woodpile(name, x, y, ang=0.0, rng=None, n=3):
    """Stacked firewood against a wall, with a plank lean-to roof."""
    rng = rng or random.Random(17)
    F = Frame(x, y, R2 + ang)
    out = [fbox(F, name + "_bk", 0.0, 0.30, 0.0, 2.70, 0.06, 1.35, ST_WALL())]
    for r in range(n):
        for i in range(4):
            out.append(fbox(F, "%s_l%d%d" % (name, r, i), -1.02 + i * 0.66,
                            0.0, 0.16 + r * 0.40, 0.30, 0.62, 0.28,
                            WOOD_M(), bev=0.006))
    out.append(fbox(F, name + "_rf", 0.0, -0.10, 1.42, 3.0, 0.78, 0.07,
                    PLANK(), bev=0.006))
    return out


def vegbed(name, x, y, w=2.2, d=1.4, ang=0.0, rng=None):
    """Raised kitchen bed with three rows of dry-green tops."""
    rng = rng or random.Random(19)
    F = Frame(x, y, R2 + ang)
    out = [fbox(F, name + "_sl", 0.0, 0.0, 0.0, w, d, 0.18, DIRT())]
    for k in range(3):
        for i in range(int(w / 0.34)):
            out.append(fcyl(F, "%s_v%d%d" % (name, k, i), -w * 0.5 + 0.20 + i * 0.34,
                            -d * 0.5 + 0.28 + k * (d - 0.5) / 2.0, 0.16,
                            rng.uniform(0.10, 0.16), rng.uniform(0.22, 0.38),
                            GRASS_D(), seg=5))
    return out


def coop(name, x, y, ang=0.0, rng=None):
    """Chicken hutch on legs, ramp, and a run of wattle fence."""
    rng = rng or random.Random(23)
    F = Frame(x, y, R2 + ang)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(fbox(F, "%s_l%d%d" % (name, sx, sy), sx * 0.62, sy * 0.68,
                            0.0, 0.11, 0.11, 0.46, WOOD_D()))
    out.append(fbox(F, name + "_bd", 0.0, 0.0, 0.44, 1.52, 1.62, 0.92, PLANK(),
                    bev=0.01))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, 1.36), 1.62, 1.80, 0.30,
                    SHINGLE())
    out.append(fbox(F, name + "_rm", 0.0, -0.92, 0.0, 0.62, 1.10, 0.05, PLANK()))
    return out


# ---------------------------------------------------------------- mine kit
def headframe(name, x, y, z=0.0, ang=0.0, h=14.6, rng=None, base_h=0.48):
    """Shaft headframe (井架): battered legs, sheave, cage, winding rope.

    The town's landmark.  Base is a stone plinth with three steps so it stands
    +0.45 m proud of the yard on top of the yard's own +0.90 m platform.
    """
    rng = rng or random.Random(29)
    F = Frame(x, y, R2 + ang)
    out = []
    # a 1.22 m masonry foundation, so the base reads from the town gate
    out.append(fbox(F, name + "_pl", 0.0, 0.0, z, 4.90, 4.90,
                    max(base_h - 0.16, 0.30), ST_WALL(), bev=0.02))
    out.append(fbox(F, name + "_pl2", 0.0, 0.0, z + max(base_h - 0.16, 0.30),
                    4.10, 4.10, 0.16, ST_DRESS(), bev=0.015))
    for i in range(3):
        out.append(fbox(F, "%s_st%d" % (name, i), 0.0, 3.10 - i * 0.32, z,
                        2.30, 0.36, 0.15 * (i + 1), ST_STEP(), bev=0.012))
    zb = z + max(base_h, 0.48)
    top = zb + h
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(beam("%s_lg%d%d" % (name, sx, sy),
                            F.P(sx * 1.52, sy * 1.52, zb),
                            F.P(sx * 0.58, sy * 0.58, top), 0.27, WOOD_D()))
    for k, zz in enumerate((zb + 3.6, zb + 7.2, zb + 10.6)):
        t = (zz - zb) / h
        r = 1.52 + (0.58 - 1.52) * t
        pts = [F.P(-r, -r, zz), F.P(r, -r, zz), F.P(r, r, zz), F.P(-r, r, zz)]
        for i in range(4):
            out.append(beam("%s_hb%d%d" % (name, k, i), pts[i], pts[(i + 1) % 4],
                            0.15, WOOD_M()))
        if k < 2:
            for i in (0, 2):
                out.append(beam("%s_xb%d%d" % (name, k, i), pts[i],
                                pts[(i + 1) % 4], 0.085, WOOD_M()))
                out.append(beam("%s_xc%d%d" % (name, k, i), pts[(i + 1) % 4],
                                pts[i], 0.085, WOOD_M()))
    # sheave deck + wheel
    out.append(fbox(F, name + "_dk", 0.0, 0.0, top, 2.30, 2.30, 0.22, WOOD_D(),
                    bev=0.01))
    ev = Vector((F.sa, -F.ca, 0.0))
    q = ev.to_track_quat("Z", "Y").to_matrix().to_4x4()
    wc = Vector(F.P(0.0, 0.0, top + 0.98))
    Tw = Matrix.Translation(wc - ev * 0.10) @ q
    out.append(cyl(name + "_wh", Tw, 0.86, 0.20, IRON_R(), seg=18))
    for i in range(6):
        a = TAU * i / 6.0
        p0 = wc + Vector((math.cos(a) * 0.12, 0, math.sin(a) * 0.12))
        p1 = wc + Vector((math.cos(a) * 0.74, 0, math.sin(a) * 0.74))
        out.append(beam("%s_sp%d" % (name, i), p0, p1, 0.075, IRON_R()))
    for s in (-1, 1):
        out.append(box("%s_sf%d" % (name, s), at(wc.x + s * 0.34, wc.y, wc.z),
                       (0.10, 0.34, 1.05), IRON(), bev=0.008))
    # cage (skip) hanging on four ropes
    cz = zb + 1.35
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(beam("%s_rp%d%d" % (name, sx, sy),
                            F.P(sx * 0.42, sy * 0.42, cz + 1.05),
                            F.P(0.0, 0.0, top + 0.10), 0.055, ROPE()))
    out.append(fbox(F, name + "_cg", 0.0, 0.0, cz, 1.28, 1.10, 0.92, IRON_R(),
                    bev=0.012))
    out.append(fbox(F, name + "_co", 0.0, 0.0, cz + 0.80, 1.10, 0.94, 0.22,
                    ORE(), bev=0.01))
    for s in (-1, 1):
        out.append(fbox(F, "%s_cb%d" % (name, s), 0.0, s * 0.52, cz + 0.10,
                        1.30, 0.07, 0.70, IRON(), bev=0.004))
    # roof over the sheave
    out.append(box(name + "_pr0", at(x, y, top + 1.86), (0.16, 0.16, 0.66),
                   WOOD_D()))
    for s in (-1, 1):
        out.append(box("%s_hr%d" % (name, s),
                       at(x + s * 0.0, y + s * 0.0, 0), (0, 0, 0), WOOD_D()))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, top + 2.12), 2.9, 3.4, 0.62,
                    SHINGLE())
    return out


def hoist_house(name, x, y, z=0.0, ang=0.0, rng=None):
    """Winding house: stone base, timber upper, open door with the drum."""
    rng = rng or random.Random(31)
    F = Frame(x, y, ang)
    out = []
    w, d, h = 4.60, 3.90, 3.40
    out.append(fbox(F, name + "_bs", 0.0, 0.0, z, w, d, 0.72, ST_WALL(), bev=0.02))
    out.append(fbox(F, name + "_up", 0.0, 0.0, z + 0.72, w - 0.12, d - 0.12,
                    h - 0.72, WOOD_D()))
    for i in range(5):
        out.append(fbox(F, "%s_pl%d" % (name, i), 0.0, -d * 0.5 - 0.03,
                        z + 0.72, w - 0.12, 0.06, h - 0.72, PLANK()))
    out.append(fbox(F, name + "_dr", 0.0, -d * 0.5 - 0.06, z, 2.30, 0.10, 2.55,
                    VOID()))
    out.append(fbox(F, name + "_df", 0.0, -d * 0.5 - 0.12, z + 2.55, 2.90, 0.30,
                    0.24, WOOD_D()))
    for s in (-1, 1):
        out.append(fbox(F, "%s_jb%d" % (name, s), s * 1.18, -d * 0.5 - 0.10, z,
                        0.20, 0.22, 2.55, WOOD_D()))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, z + h), w, d, 1.15, SLATE())
    out.append(fbox(F, name + "_ch", w * 0.34, d * 0.30, z + h, 0.52, 0.52, 1.55,
                    ST_WALL(), bev=0.01))
    # drum + rope inside the opening
    out.append(cyl(name + "_dr", at(x, y + d * 0.5 - 0.9, z + 0.95, rx=R2),
                   0.72, 2.10, WOOD_M(), seg=14))
    return out


def weigh_house(name, x, y, z=0.0, ang=0.0, rng=None):
    """Weigh house over the track: open front, scale beam, counter."""
    rng = rng or random.Random(37)
    F = Frame(x, y, ang)
    out = []
    w, d = 3.80, 3.30
    out.append(fbox(F, name + "_bs", 0.0, 0.0, z, w, d, 0.36, ST_WALL(), bev=0.015))
    for sx in (-1, 1):
        out.append(fbox(F, "%s_w%d" % (name, sx), sx * (w * 0.5 - 0.11), 0.0,
                        z + 0.36, 0.22, d, 2.35, PLANK()))
    out.append(fbox(F, name + "_bk", 0.0, d * 0.5 - 0.10, z + 0.36, w, 0.20, 2.35,
                    PLANK()))
    out.append(fbox(F, name + "_op", 0.0, -d * 0.5 + 0.06, z + 0.36, w - 0.5,
                    0.10, 2.05, VOID()))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, z + 2.72), w, d, 0.72, SHINGLE())
    out.append(fbox(F, name + "_sb", 0.0, -0.40, z + 1.15, 1.55, 0.10, 0.12,
                    IRON(), bev=0.004))
    out.append(fbox(F, name + "_sw", 1.05, -0.40, z + 1.02, 0.28, 0.24, 0.34,
                    IRON(), bev=0.006))
    out.append(fbox(F, name + "_ct", -1.05, 0.55, z + 1.00, 0.90, 0.62, 0.10,
                    PLANK(), bev=0.006))
    for s in (-1, 1):
        out.append(fbox(F, "%s_ct%d" % (name, s), -1.05 + s * 0.36, 0.55,
                        z + 0.36, 0.10, 0.58, 0.66, WOOD_D()))
    return out


def adit_portal(name, x, y, z, ang, w=2.55, h=3.15, rng=None):
    """Timber-framed adit mouth in a rock cut; +u points into the hill."""
    rng = rng or random.Random(41)
    F = Frame(x, y, ang)
    out = []
    # a stepped hill, not a slab: courses narrow and stagger as they rise, and
    # boulders sit on the faces and the crest so no big flat plane reads
    for i, (uu, ww, hh, sg) in enumerate(((0.90, 5.2, 4.4, 3.0),
                                          (2.05, 6.2, 5.9, 3.3),
                                          (3.35, 7.4, 7.1, 3.7),
                                          (4.85, 8.2, 8.1, 4.1))):
        out.append(fbox(F, "%s_rk%d" % (name, i), uu + sg * 0.10, 0.0, z,
                        ww * 0.42, ww, hh, CLIFF(), bev=0.06))
        for k in range(4):
            if k < 2:
                sv = (1.0 if k % 2 else -1.0) * (ww * 0.5 + rng.uniform(-0.25, 0.30))
                pos = F.M(uu + rng.uniform(-1.3, 1.3), sv, z + hh * 0.52)
            elif k == 2:
                pos = F.M(uu - ww * 0.42 - rng.uniform(0.05, 0.45),
                          rng.uniform(-ww * 0.34, ww * 0.34), z + hh * 0.46)
            else:
                pos = F.M(uu + ww * 0.42 + rng.uniform(0.05, 0.40),
                          rng.uniform(-ww * 0.34, ww * 0.34), z + hh * 0.40)
            out.append(rock("%s_rb%d%d" % (name, i, k), pos,
                            rng.uniform(1.25, 2.35), rng, CLIFF(), squash=0.88))
    for i in range(7):
        sv = (1.0 if i % 2 else -1.0) * rng.uniform(3.6, 5.1)
        out.append(rock("%s_sc%d" % (name, i),
                        F.M(rng.uniform(-0.4, 2.2), sv, z + 0.25),
                        rng.uniform(0.9, 1.7), rng, CLIFF(), squash=0.62))
    for i in range(10):
        out.append(rock("%s_cr%d" % (name, i),
                        F.M(rng.uniform(2.0, 7.6), rng.uniform(-3.6, 3.6),
                            z + 8.1 + rng.uniform(-0.15, 0.55)),
                        rng.uniform(1.1, 2.1), rng, CLIFF(), squash=0.80))
    for s in (-1, 1):
        out.append(fbox(F, "%s_po%d" % (name, s), -0.30, s * (w * 0.5 + 0.24), z,
                        0.28, 0.32, h + 0.46, WOOD_D(), bev=0.008))
    out.append(fbox(F, name + "_lt", -0.30, 0.0, z + h + 0.46, 0.32, w + 1.16,
                    0.34, WOOD_D(), bev=0.008))
    out.append(fbox(F, name + "_lt2", -0.30, 0.0, z + h + 0.80, 0.50, w + 1.66,
                    0.18, PLANK(), bev=0.006))
    out.append(fbox(F, name + "_dk", 0.22, 0.0, z, 0.12, w, h + 0.40, VOID()))
    out.append(fbox(F, name + "_fl", 0.02, 0.0, z - 0.04, 1.10, w + 0.10, 0.10,
                    GRAVEL()))
    # a lamp on the lintel and a rail stub into the dark
    for o in lamp_post(F, name + "_lp", -0.55, w * 0.5 + 0.55, h=2.5,
                       face=(1.0, 0.0)):
        o.location.z += z + h
        out.append(o)
    out.append(fbox(F, name + "_rl", 0.30, -0.27, z, 1.20, 0.09, 0.09, IRON_R()))
    out.append(fbox(F, name + "_rr", 0.30, 0.27, z, 1.20, 0.09, 0.09, IRON_R()))
    return out


def ramp(name, p0, p1, z0, z1, w=3.30, mat=None, rails=True, rng=None):
    """Inclined tramway: graded bed, stone cheeks, sleepers, two rails."""
    rng = rng or random.Random(43)
    out = []
    ob, T, L = ramp_bed(name + "_bed", p0, p1, z0, z1, w, mat or GRAVEL())
    out.append(ob)
    for s in (-1, 1):
        out.append(box("%s_ck%d" % (name, s), T @ T_at(s * (w * 0.5 + 0.18), -0.10, 0),
                       (0.42, 0.62, L), ST_WALL(), bev=0.015))
    if rails:
        n = max(3, int(L / 0.66))
        for i in range(n):
            out.append(box("%s_sl%d" % (name, i),
                           T @ T_at(0, 0.32, -L * 0.5 + (i + 0.5) * (L / n)),
                           (1.46, 0.10, 0.22), WOOD_D()))
        for s in (-1, 1):
            out.append(box("%s_rl%d" % (name, s), T @ T_at(s * 0.27, 0.42, 0),
                           (0.09, 0.09, L), IRON_R(), bev=0.004))
    return out


def ore_pile(name, x, y, s=2.0, rng=None, mat=None):
    """Conical ore heap with a few boulders spilled at the foot."""
    rng = rng or random.Random(47)
    out = [cone(name, at(x, y, 0.02), s, s * 0.72, mat or ORE(), seg=10)]
    for i in range(5):
        a = TAU * i / 5.0 + rng.uniform(-0.4, 0.4)
        rr = s * rng.uniform(0.72, 1.02)
        out.append(rock("%s_rk%d" % (name, i),
                        at(x + math.cos(a) * rr, y + math.sin(a) * rr, 0.10,
                           rz=rng.uniform(0, TAU)),
                        rng.uniform(0.36, 0.66), rng, mat or ORE()))
    return out


def spoil_heap(name, x, y, s=4.0, rng=None):
    """Spoil tip: three scree cones, rocks, a tipped cart on a stub track."""
    rng = rng or random.Random(53)
    out = []
    for i, (dx, dy, ss) in enumerate(((0.0, 0.0, 1.0), (-1.9, 1.1, 0.66),
                                      (1.7, 1.6, 0.55))):
        out.append(cone("%s_c%d" % (name, i),
                        at(x + dx * s, y + dy * s, -0.10), s * ss, s * ss * 0.58,
                        GRAVEL(), seg=11))
        for k in range(4):
            a = TAU * k / 4.0 + rng.uniform(-0.5, 0.5)
            rr = s * ss * rng.uniform(0.7, 1.05)
            out.append(rock("%s_r%d%d" % (name, i, k),
                            at(x + dx * s + math.cos(a) * rr,
                               y + dy * s + math.sin(a) * rr, 0.12,
                               rz=rng.uniform(0, TAU)),
                            rng.uniform(0.5, 1.0), rng, CLIFF()))
    return out


# ---------------------------------------------------------------- street kit
SPINE = []
WATER_KEY = "water"


def street_at(y):
    """(centre_x, yaw) of the main street at a given y."""
    p = SPINE
    if y <= p[0][1]:
        dx, dy = p[1][0] - p[0][0], p[1][1] - p[0][1]
        return p[0][0], math.atan2(dy, dx)
    for i in range(len(p) - 1):
        (x0, y0), (x1, y1) = p[i], p[i + 1]
        if y0 <= y <= y1:
            t = (y - y0) / max(1e-6, (y1 - y0))
            return x0 + (x1 - x0) * t, math.atan2(y1 - y0, x1 - x0)
    dx, dy = p[-1][0] - p[-2][0], p[-1][1] - p[-2][1]
    return p[-1][0], math.atan2(dy, dx)


def sx(y):
    return street_at(y)[0]


def edge(ys, side, off, n=8):
    """Polyline offset `off` metres to `side` (-1 west, +1 east) of the spine."""
    out = []
    for i in range(n + 1):
        y = ys[0] + (ys[1] - ys[0]) * i / float(n)
        out.append((sx(y) + side * off, y))
    return out


def WATER():
    m = medkit._MAT_CACHE.get(WATER_KEY)
    if m is None:
        m = mat_water(WATER_KEY, base="#7d9c95")
        medkit._MAT_CACHE[WATER_KEY] = m
    return m


def stairs(name, p0, p1, z0, z1, w=2.4, n=5, mat=None):
    """Flight of n stone steps climbing from p0 (z0) to p1 (z1)."""
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 0.2:
        return []
    out = []
    ang = math.atan2(-dx, dy)
    T0 = at(x0, y0, 0.0, rz=ang)
    rise = (z1 - z0) / float(n)
    run = L / float(n)
    for i in range(n):
        h = z0 + (i + 1) * rise
        T = T0 @ T_at(0, (i + 0.5) * run, h * 0.5)
        out.append(box("%s_s%d" % (name, i), T, (w, run + 0.02, h), mat or ST_STEP(),
                       bev=0.012))
    for s in (-1, 1):
        T = T0 @ T_at(s * (w * 0.5 + 0.13), L * 0.5, (z0 + z1) * 0.5 + 0.16)
        out.append(box("%s_ck%d" % (name, s), T, (0.26, L, (z1 - z0) + 0.46),
                       ST_WALL(), bev=0.012))
    return out


def tree_clump(name, x, y, r, n, rng, z=0.0, h=(5.0, 8.0)):
    out = []
    for i in range(n):
        a = rng.uniform(0, TAU)
        rr = r * math.sqrt(rng.random())
        px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
        out += conifer(Frame(px, py, rng.uniform(0, TAU)), "%s_t%d" % (name, i),
                       0.0, 0.0, z, rng.uniform(h[0], h[1]), rng)
    return out


def rock_band(name, pts, rng, s=(1.4, 3.4), z=0.0, mat=None):
    """Line of outcrops used to terminate a wall or a plate edge."""
    out = []
    for i, p in enumerate(pts):
        out.append(rock("%s_r%d" % (name, i),
                        at(p[0], p[1], z, rz=rng.uniform(0, TAU)),
                        rng.uniform(s[0], s[1]), rng, mat or CLIFF()))
    return out


def gate(name, x, y, ang, z=0.0, half=3.2, h=3.35, rng=None):
    """Town gate: two stone piers, timber lintel, slate cap, lanterns, banner."""
    rng = rng or random.Random(61)
    F = Frame(x, y, ang)
    out = []
    dep = 1.55                     # portal depth (walk-through reveal)
    clear = 2.62                   # clear opening under the soffit
    for s in (-1, 1):
        out.append(fbox(F, "%s_b%d" % (name, s), 0.0, s * half, z, 1.62, 1.62, 0.34,
                        ST_DRESS(), bev=0.02))
        out.append(fbox(F, "%s_p%d" % (name, s), -0.06, s * half, z + 0.34, 1.28, 1.28,
                        h - 0.34, ST_WALL(), bev=0.03))
        out.append(fbox(F, "%s_c%d" % (name, s), -0.06, s * half, z + h, 1.50, 1.50,
                        0.18, ST_STEP(), bev=0.015))
        out.append(fbox(F, "%s_lb%d" % (name, s), -0.06, s * half, z + h + 0.18,
                        0.34, 0.34, 0.26, IRON(), bev=0.01))
        out.append(fbox(F, "%s_gl%d" % (name, s), -0.06, s * half, z + h + 0.44,
                        0.21, 0.21, 0.24, LAMP(), bev=0.006))
        out.append(fbox(F, "%s_lc%d" % (name, s), -0.06, s * half, z + h + 0.68,
                        0.36, 0.36, 0.13, SLATE(), bev=0.01))
        # the reveal: a 1.55 m deep jamb on the inner face of each pier
        out.append(fbox(F, "%s_j%d" % (name, s), -dep * 0.5 - 0.02,
                        s * (half - 0.60), z + 0.02, dep, 0.46, clear - 0.02,
                        ST_DRESS(), bev=0.010))
        out.append(fbox(F, "%s_jt%d" % (name, s), -dep * 0.5 - 0.02,
                        s * (half - 0.60), z + clear - 0.02, dep + 0.10, 0.54, 0.20,
                        ST_STEP(), bev=0.008))
        px, py, _ = F.P(0.0, s * half, 0.0)
        SOLIDS.append((px, py, 1.2))
    # timber soffit closing the reveal, so the opening reads as a tunnel
    out.append(fbox(F, name + "_sf", -dep * 0.5 - 0.02, 0.0, z + clear,
                    dep + 0.10, 2 * (half - 0.80), 0.20, WOOD_D(), bev=0.012))
    out.append(fbox(F, name + "_sf2", -dep * 0.5 - 0.02, 0.0, z + clear + 0.20,
                    dep + 0.18, 2 * (half - 0.72), 0.14, PLANK(), bev=0.008))
    # paved threshold under the arch and a lamp under the soffit
    out.append(fbox(F, name + "_th", -dep * 0.5, 0.0, z, dep + 0.55,
                    2 * half - 0.55, 0.075, COBBLE(), bev=0.0))
    out.append(fbox(F, name + "_lp", -0.42, 0.0, z + clear - 0.42, 0.38, 0.38, 0.38,
                    LAMP(), bev=0.008))
    out.append(fbox(F, name + "_rf3", -dep * 0.5, 0.0, z + clear - 0.06,
                    dep, 2 * (half - 0.55), 0.06, ST_STEP(), bev=0.004))
    out.append(fbox(F, name + "_lpb", -0.42, 0.0, z + clear - 0.14, 0.16, 0.16, 0.06,
                    IRON(), bev=0.004))
    out.append(fbox(F, name + "_ln", 0.0, 0.0, z + h - 0.62, 0.54, 2 * half + 1.10,
                    0.42, WOOD_D(), bev=0.015))
    out.append(fbox(F, name + "_ln2", 0.0, 0.0, z + h - 0.98, 0.36, 2 * half + 0.30,
                    0.30, WOOD_D()))
    for s in (-1, 1):
        out.append(fbox(F, "%s_kn%d" % (name, s), 0.0, s * (half - 0.62),
                        z + h - 0.60, 0.62, 0.30, 0.34, WOOD_D(), bev=0.01))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, z + h), 2 * half + 1.9, 1.85,
                    0.58, SLATE(), over=0.30)
    out.append(fbox(F, name + "_bn", 0.0, 0.0, z + h - 0.92, 0.05, 1.95, 0.92,
                    mat_cloth("bloom", "#8d3b32"), bev=0.0))
    for s in (-1, 1):
        out.append(fbox(F, "%s_bnb%d" % (name, s), 0.0, s * 1.00, z + h - 0.42,
                        0.07, 0.07, 0.06, ROPE()))
    # wing walls: two low stepped runs each side, each end buried in a boulder
    for s in (-1, 1):
        p0 = F.P(0.0, s * half, 0.0)
        p1 = F.P(-1.1, s * (half + 1.9), 0.0)
        p2 = F.P(-1.6, s * (half + 3.9), 0.0)
        out += wall("%s_w%d" % (name, s), (p0[0], p0[1]), (p1[0], p1[1]), z, h=0.92,
                    piers=True)
        out += wall("%s_w2%d" % (name, s), (p1[0], p1[1]), (p2[0], p2[1]), z, h=0.58,
                    thick=0.40, piers=False)
        out.append(rock("%s_wr%d" % (name, s), at(p2[0], p2[1], z), 1.15, rng,
                        ROCK(), squash=0.60, seg=7, ring=4))
        SOLIDS.append((p1[0], p1[1], 0.70))
        SOLIDS.append((p2[0], p2[1], 1.10))
    return out


def weighbridge(name, x, y, ang, z=0.0):
    """Iron weighbridge plate set flush in the track, with a kerb."""
    F = Frame(x, y, ang)
    out = [fbox(F, name + "_pl", 0.0, 0.0, z, 1.90, 3.10, 0.06, IRON_R(), bev=0.0)]
    for s in (-1, 1):
        out.append(fbox(F, "%s_kb%d" % (name, s), 0.0, s * 1.02, z, 2.10, 0.16, 0.12,
                        ST_STEP(), bev=0.008))
    return out


# ---------------------------------------------------------------- rows
def place_row(tag, side, y0, specs, z, rng, sb0=0.7, extras=False):
    """Lay a row of cottages along the street; returns the placed houses."""
    placed = []
    y = y0
    for i, sp in enumerate(specs):
        W = sp.get("W", 6.0)
        D = sp.get("D", 4.9)
        sb = sp.get("sb", sb0)
        yc = y + W * 0.5
        xcs, ang = street_at(yc)
        xf = xcs + side * (HW + sb)
        xc = xf + side * D * 0.5
        F = Frame(xc, yc, ang)
        face = (0.0, -float(side))
        name = "%s_%d" % (tag, i)
        parts = cottage(F, name, 0.0, 0.0, z, W=W, D=D, kind=sp.get("kind", i),
                        rng=rng, face=face, dorm=sp.get("dorm", False),
                        FH=sp.get("FH", 2.55), extras=extras)
        GROUPS.append((name, parts))
        mz = F.rz(face[0], face[1])
        h = dict(name=name, x=xc, y=yc, W=W, D=D, ang=ang, F=F, face=face, z=z,
                 front=xf, side=side, mz=mz)
        placed.append(h)
        RECTS.append((xc, yc, W * 0.5, D * 0.5, mz))
        y += W + sp.get("gap", 1.0)
    return placed


def front_corners(h):
    M = h["F"].M(0.0, 0.0, 0.0, du=0.0, dv=h["face"][1])
    out = []
    for j in (-1, 1):
        out.append(Vector((M @ T_at(j * h["W"] * 0.5, h["D"] * 0.5, 0.0)).translation))
    return out


def close_row(prefix, houses, z, h=1.95, mat=None):
    """Stone close-wall between each pair of neighbours (no idle gaps)."""
    out = []
    for i in range(len(houses) - 1):
        ca = front_corners(houses[i])
        cb = front_corners(houses[i + 1])
        best = None
        for p in ca:
            for q in cb:
                d = (p - q).length
                if best is None or d < best[0]:
                    best = (d, p, q)
        d, p, q = best
        if d < 0.12 or d > 5.0:
            continue
        out += wall("%s_cw%d" % (prefix, i), (p.x, p.y), (q.x, q.y), z, h=h, mat=mat)
    return out


# ---------------------------------------------------------------- the town
def place_line(tag, xf, fd, y0, specs, z, rng, extras=False):
    """Row along a fixed front line x=xf; fd=+1 faces east, -1 faces west."""
    placed = []
    y = y0
    for i, sp in enumerate(specs):
        W, D = sp["W"], sp["D"]
        yc = y + W * 0.5
        xc = xf + fd * D * 0.5
        F = Frame(xc, yc, R2)
        face = (0.0, float(fd))
        kind = sp.get("kind", i % 5)
        parts = cottage(F, "%s%d" % (tag, i), 0.0, 0.0, z, W, D, kind, rng,
                        face=face, extras=extras, dorm=sp.get("dorm", False),
                        FH=sp.get("FH", 2.55))
        h = dict(tag="%s%d" % (tag, i), F=F, face=face, W=W, D=D, z=z,
                 kind=kind, parts=parts)
        placed.append(h)
        SOLIDS.append((xc, yc, max(W, D) * 0.55))
        RECTS.append((xc, yc, W * 0.5, D * 0.5, F.rz(0.0, float(fd))))
        y += W + sp.get("gap", 0.0)
    return placed


def build_town(cfg):
    global SPINE, WATER_KEY
    SPINE = cfg["spine"]
    WATER_KEY = cfg.get("water", "water")
    rng = random.Random(cfg["seed"])
    G = GROUPS

    def add(n, p):
        if p is None:
            return
        if not isinstance(p, (list, tuple)):
            p = [p]
        p = [o for o in p if o is not None and hasattr(o, "name")
             and o.name in bpy.data.objects]
        if p:
            G.append((n, p))

    lv = cfg.get("levels", (0.0, 0.45, 0.90, 2.70))
    z_ter, z_yard, z_bench = lv[1], lv[2], lv[3]

    # ---- ground: plate + earth blanket + all paving ----------------------
    add("ground", plate("ground", cfg["plate"], 0.0, -2.0, 1.8, ROCK()))
    add("apron", poly_slab("apron", cfg["apron"], 0.02, 0.40, DIRT()))

    # ---- approach lane, forecourt, gate ---------------------------------
    ax = cfg["apx"]
    add("approach", ribbon("approach",
                           [(ax, -44.0, 2.55), (ax, -34.0, 2.55), (ax, -24.0, 2.6),
                            (sx(-14.0), -14.0, 2.6)],
                           DIRT(), z=0.045, depth=0.45, wob=0.10, seed=5))
    add("approach_verge", ribbon("apv",
                                 [(ax, -44.0, 4.60), (ax, -34.0, 4.60),
                                  (ax, -24.0, 4.55), (sx(-14.0), -14.0, 4.40)],
                                 GRASS_D(), z=0.035, depth=0.40, wob=0.12, seed=9))
    for s in (-1, 1):
        add("ap_kerb_%d" % s,
            ribbon("apk%d" % s,
                   [(ax + s * 2.72, -44.0, 0.17), (ax + s * 2.72, -34.0, 0.17),
                    (ax + s * 2.72, -24.0, 0.17), (sx(-14.0) + s * 2.62, -14.0, 0.17)],
                   COBBLE(), z=0.075, depth=0.26, wob=0.02, seed=11))
    add("forecourt", poly_slab("forecourt", cfg["forecourt"], 0.055, 0.40, GRAVEL()))
    g = cfg["gate"]
    add("gate", gate("gate", g[0], g[1], street_at(g[1])[1], 0.0, 3.15, 3.35, rng))
    # (no loose boulders at the gate: the road verge is grass + kerb)
    # the pair of trees that frames the gate
    for s in (-1, 1):
        add("gate_tree_%d" % s, conifer(Frame(g[0] + s * 7.4, g[1] + 2.6, 0.3),
                                        "gtree%d" % s, 0.0, 0.0, 0.0,
                                        rng.uniform(9.0, 11.0), rng))
    # approach verges: three SHORT stepped retaining walls per side, each
    # segment drops 0.30 m, every segment ends in a buried stub or boulder.
    if cfg.get("approach_walls", True):
        for s in (-1, 1):
            x0 = g[0] + s * 4.30
            add("apw_%d" % s,
                wall("apw%d" % s, (x0, g[1] - 1.6), (x0 + s * 0.55, g[1] - 9.2),
                     0.0, h=0.58, thick=0.42, piers=False))
            add("apwb_%d" % s,
                rock("apwb%d" % s, at(x0 + s * 0.55, g[1] - 9.2, 0.0), 0.72,
                     rng, ROCK(), squash=0.55, seg=6, ring=3))
            SOLIDS.append((x0 + s * 0.55, g[1] - 9.2, 0.70))
            for j, yy in enumerate((-12.4, -17.6, -23.2)):
                add("apwt_%d_%d" % (s, j),
                    conifer(Frame(g[0] + s * (6.0 + 0.5 * j), yy, 0.0),
                            "apwt%d%d" % (s, j), 0.0, 0.0, 0.0,
                            rng.uniform(6.0, 8.5), rng))

    # ---- main street -----------------------------------------------------
    ys = cfg["street"]
    nodes = []
    n = 9
    for i in range(n + 1):
        y = ys[0] + (ys[1] - ys[0]) * i / float(n)
        nodes.append((sx(y), y, HW))
    add("street", ribbon("street", nodes, COBBLE(), z=0.06, depth=0.55, wob=0.03,
                         seed=7))

    # gutter stones both sides, following the spine
    for s in (-1, 1):
        gn = []
        for i in range(10):
            y = ys[0] + (ys[1] - ys[0]) * i / 9.0
            gn.append((sx(y) + s * (HW - 0.16), y, 0.17))
        add("gutter_%d" % s, ribbon("gut%d" % s, gn, ST_DARK(), z=0.085, depth=0.3))

    # ---- market square ---------------------------------------------------
    q = cfg["square"]
    add("square", poly_slab("square", q["poly"], 0.075, 0.50, ST_DRESS()))
    add("square_kerb", poly_slab("sqk", q["kerb"], 0.095, 0.40, COBBLE()))
    add("well", well_plaza("well", q["well"][0], q["well"][1], 0.10, rng))
    pps = []
    for i, (px, py) in enumerate(q["poly"]):
        pps.append(fbox(Frame(px, py, 0.0), "sqp_%d" % i, 0.0, 0.0, 0.0, 0.62, 0.62,
                        1.24, ST_WALL(), 0.02))
        pps.append(fbox(Frame(px, py, 0.0), "sqpc_%d" % i, 0.0, 0.0, 1.24, 0.78, 0.78,
                        0.14, ST_LIP(), 0.02))
        SOLIDS.append((px, py, 0.52))
    add("sq_piers", pps)
    for i, (x, y, a) in enumerate(q.get("stalls", ())):
        add("stall_%d" % i, stall("stl%d" % i, x, y, a, rng))
    if q.get("board"):
        add("board", board("brd", q["board"][0], q["board"][1], q["board"][2]))
    if q.get("banner"):
        add("banner", banner("bnr", q["banner"][0], q["banner"][1], 0.0,
                             q["banner"][2], q["banner"][3]))
    if q.get("tree"):
        add("sq_tree", tree_clump("sqt", q["tree"][0], q["tree"][1], 1.0, 2, rng,
                                  0.075, (7.0, 9.0)))
    if q.get("cart"):
        tt = mine_cart("sq_cart",
                       at(q["cart"][0], q["cart"][1], 0.0, rz=q["cart"][2]),
                       rng, ore=True)
        for o in tt:
            o.location.z += 0.09
        add("sq_cart", tt)
    Fw = Frame(q["well"][0], q["well"][1], 0.0)
    add("sq_props", barrel_stack("sq_bs", Fw.M(1.65, -1.05, 0.09), rng)
        + barrel_stack("sq_bs2", Fw.M(1.95, -1.55, 0.09), rng)
        + crate_pile("sq_cr", Fw.M(-1.75, -1.10, 0.09), rng))

    # ---- mine lane: paved road from the square up to the yard ------------
    for (pts, w) in cfg.get("lanes", ()):
        add("lane_%d" % len(G), ribbon("lane%d" % len(G),
                                       [(p[0], p[1], w * 0.5) for p in pts],
                                       COBBLE(), z=0.055, depth=0.5, wob=0.04,
                                       seed=len(G)))

    # ---- west terrace platform + retaining wall --------------------------
    if cfg.get("west_terrace"):
        wt = cfg["west_terrace"]
        if wt.get("terrace_x"):
            poly = [(wt["terrace_x"], wt["y"][0]), (wt["terrace_x"], wt["y"][1])]
        else:
            poly = edge((wt["y"][0], wt["y"][1]), -1, HW + wt["inset"], 10)
        poly = poly + [(poly[-1][0] - wt["depth"], poly[-1][1]),
                       (poly[0][0] - wt["depth"], poly[0][1])]
        add("west_terrace", poly_slab("wter", poly, z_ter, z_ter + 0.30, ST_DARK()))
        # retaining wall along the street edge, broken at the stairs
        cuts = sorted(wt.get("stairs", ()))
        yy = wt["y"][0]
        segs = []
        for cy in cuts:
            segs.append((yy, cy - 0.85))
            yy = cy + 0.85
        segs.append((yy, wt["y"][1]))
        for i, (a, b) in enumerate(segs):
            if b - a < 0.4:
                continue
            e0 = ((wt.get("terrace_x") or (sx(a) - HW)) - wt["inset"] + 0.10, a)
            e1 = ((wt.get("terrace_x") or (sx(b) - HW)) - wt["inset"] + 0.10, b)
            add("wter_wall_%d" % i, wall("wtw%d" % i, e0, e1, 0.0, h=z_ter + 0.72,
                                         piers=False))
        for i, cy in enumerate(cuts):
            xx = (wt.get("terrace_x") or (sx(cy) - HW)) - wt["inset"]
            add("wter_stair_%d" % i,
                stairs("wts%d" % i, (xx + 0.9, cy), (xx - 0.9, cy), 0.0, z_ter,
                       w=1.85, n=3))
            SOLIDS.append((xx, cy, 1.35))
        add("wter_parapet", hwall("wtp", (poly[-1][0], wt["y"][1] + 0.0),
                                  (poly[-2][0], wt["y"][1]), z_ter, 0.34))
        for cy in (wt["y"][0], wt["y"][1]):
            ex = (wt.get("terrace_x") or (sx(cy) - HW)) - wt["inset"] + 0.10
            add("wter_pier_%d" % int(cy),
                box("wtpr%d" % int(cy), at(ex, cy, (z_ter + 0.95) * 0.5),
                    (1.02, 1.02, z_ter + 0.95), ST_DRESS(), bev=0.02))
            SOLIDS.append((ex, cy, 0.92))
        add("wter_corner", box("wtc", at(poly[-2][0], wt["y"][1],
                                         (z_ter + 0.55) * 0.5),
                              (0.86, 0.86, z_ter + 0.55), ST_DRESS(), bev=0.02))
        SOLIDS.append((poly[-2][0], wt["y"][1], 0.8))

    # ---- axis lane: the continuation of the main street into the yard ----
    pl = cfg.get("plate")
    if pl and cfg.get("back_terrace", True):
        ys = [q[1] for q in pl]
        ylo, yhi = min(ys), max(ys)
        cut = ylo + (yhi - ylo) * 0.60
        rear = [q for q in pl if q[1] >= cut]
        if len(rear) >= 3:
            cx = sum(q[0] for q in pl) / float(len(pl))
            cy = sum(q[1] for q in pl) / float(len(pl))
            yv0 = cfg.get("yard") or {}
            add("back_terrace", back_terrace("bt", rear, 0.0, (cx, cy),
                                             skip=yv0.get("adit")))

    al = cfg.get("axis_lane")
    if al:
        axx, ay0, ay1, ahw = al
        add("axis_lane", ribbon("axl", [(axx, ay0, ahw), (axx, ay0 + 3.0, ahw),
                                        (axx, ay1, ahw)],
                                COBBLE(), z=0.075, depth=0.45, wob=0.02, seed=13))
        for sd in (-1, 1):
            add("axis_kerb_%d" % sd,
                ribbon("axk%d" % sd,
                       [(axx + sd * (ahw + 0.02), ay0, 0.16),
                        (axx + sd * (ahw + 0.02), ay1, 0.16)],
                       ST_DRESS(), z=0.10, depth=0.20, wob=0.01, seed=17))
        for sd, px in ((-1, axx - ahw - 0.20), (1, axx + ahw + 0.20)):
            pp = [fbox(Frame(px, ay0 + 0.55, 0.0), "axp%d" % sd, 0.0, 0.0, 0.0,
                       0.58, 0.58, 1.22, ST_DRESS(), 0.02),
                  fbox(Frame(px, ay0 + 0.55, 0.0), "axpc%d" % sd, 0.0, 0.0, 1.22,
                       0.74, 0.74, 0.14, ST_STEP(), 0.015)]
            add("axis_post_%d" % sd, pp)
            SOLIDS.append((px, ay0 + 0.55, 0.50))
        for sd in (-1, 1):
            hinge_x = axx + sd * (ahw + 0.20)
            lf = []
            for k, (dz, ww) in enumerate(((0.12, 1.02), (0.92, 1.02))):
                lf.append(fbox(Frame(hinge_x - sd * 0.52, ay0 + 0.55, 0.0),
                               "axgl%d%d" % (sd, k), 0.0, 0.0, dz, ww, 0.075,
                               0.80, WOOD_D(), 0.006))
            add("axis_leaf_%d" % sd, lf)
        add("axis_lamp", lamp_post(Frame(axx - ahw - 0.45, ay0 + 6.2, 0.0),
                                   "axlp", 0.0, 0.0, 3.05, (0, -1)))
        add("axis_wood", woodpile("axwd", axx + ahw + 0.75, ay0 + 8.6, 1.57, rng, 3))
        add("axis_veg", vegbed("axvg", axx - ahw - 1.45, ay0 + 3.1, 1.9, 1.2, 0.0,
                               rng))

    # ---- house rows ------------------------------------------------------
    rows = cfg["rows"]
    all_rows = []
    for ln in cfg.get("lines", ()):
        hs = place_line(ln["tag"], ln["xf"], ln["fd"], ln["y0"],
                        ln["specs"], ln.get("z", 0.0), rng,
                        ln.get("extras", False))
        for h in hs:
            add(h["tag"], h["parts"])
        all_rows.append(hs)
    for ri, row in enumerate(rows):
        hs = place_row(row["tag"], row["side"], row["y0"], row["specs"], row.get("z", 0.0),
                       rng, row.get("sb", 0.7), row.get("extras", False))
        all_rows.append(hs)
        if row.get("close", True):
            add("row_wall_%d" % ri, close_row(row["tag"], hs, row.get("z", 0.0),
                                              h=row.get("wh", 1.95)))
    # tie the row ends to solid things
    for row, hs in zip(rows, all_rows):
        if not hs or not row.get("tie"):
            continue
        z = row.get("z", 0.0)
        cs = front_corners(hs[0] if row["tie"][0] < 0 else hs[-1])
        tgt = row["tie"][1]
        p = min(cs, key=lambda v: (Vector((tgt[0], tgt[1], 0)) - v).length)
        add("row_tie_%s" % row["tag"],
            wall("rt_%s" % row["tag"], (p.x, p.y), tgt, z, h=row.get("wh", 1.95)))

    # ---- detached buildings ---------------------------------------------
    for b in cfg.get("buildings", ()):
        x, y, W, D = b["x"], b["y"], b["W"], b["D"]
        z = b.get("z", 0.0)
        F = frame_front(x, y, b.get("front", (0.0, -1.0)))
        face = (0.0, -1.0)
        mz = F.rz(0.0, -1.0)
        nm = b["tag"]
        if b["type"] == "cottage":
            parts = cottage(F, nm, 0.0, 0.0, z, W=W, D=D, kind=b.get("kind", 3),
                            rng=rng, face=face, dorm=b.get("dorm", False),
                            extras=b.get("extras", True))
        elif b["type"] == "tavern":
            parts = tavern(F, nm, 0.0, 0.0, z, W=W, D=D, kind=3, rng=rng, face=face)
        elif b["type"] == "hoist":
            parts = hoist_house(nm, x, y, z, F.ang, rng)
        elif b["type"] == "weigh":
            parts = weigh_house(nm, x, y, z, F.ang, rng)
        elif b["type"] == "smelter":
            parts = smelter(F, nm, 0.0, 0.0, face, 0, rng)
        elif b["type"] == "oreyard":
            parts = ore_yard(F, nm, 0.0, 0.0, rng, b.get("W", 9.0), b.get("D", 13.0))
        elif b["type"] == "shed":
            parts = open_shed(nm, x, y, z, F.ang, b.get("W", 4.0), b.get("D", 3.0),
                              rng)
        else:
            parts = None
        add(nm, parts)
        if b.get("solid", True):
            SOLIDS.append((x, y, max(W, D) * 0.6))
        if b.get("rect", True):
            RECTS.append((x, y, W * 0.5, D * 0.5, mz))

    # ---- square boundary walls (tie the paving to the house corners) -----
    for i, (p0, p1) in enumerate(cfg.get("square_walls", ())):
        add("sq_wall_%d" % i, wall("sqw%d" % i, p0, p1, 0.0, h=1.15,
                                    thick=0.44, piers=False))

    # ---- mine yard -------------------------------------------------------
    mine_yard(cfg, add, rng)
    outskirts(cfg, add, rng)

    # ---- outskirts: rock shoulders + tree clumps -------------------------
    for i, p in enumerate(cfg.get("clumps", ())):
        add("clump_%d" % i, tree_clump("cl%d" % i, p[0], p[1], p[2], p[3], rng,
                                       0.0, (5.5, 9.0)))
    for i, p in enumerate(cfg.get("rocks", ())):
        add("outrock_%d" % i, rock_band("ork%d" % i, p[0], rng, (1.6, 3.2)))

    return G


def open_shed(name, x, y, z, ang, w=4.0, d=3.0, rng=None):
    """Three-sided work shed with a lean-to roof and a plank door."""
    rng = rng or random.Random(71)
    F = Frame(x, y, ang)
    out = [fbox(F, name + "_bs", 0.0, 0.0, z, w, d, 0.34, ST_WALL(), bev=0.015)]
    for s in (-1, 1):
        out.append(fbox(F, "%s_w%d" % (name, s), 0.0, s * (d * 0.5 - 0.09), z + 0.34,
                        w, 0.18, 2.55, PLANK()))
    out.append(fbox(F, name + "_bk", 0.0, d * 0.5 - 0.09, z + 0.34, w, 0.18, 2.55,
                    PLANK()))
    out.append(fbox(F, name + "_dk", 0.0, -d * 0.5 + 0.10, z + 0.34, 1.30, 0.12,
                    2.10, VOID()))
    out += dbl_roof(name + "_rf", F.Mb(0.0, 0.0, z + 2.90), w, d, 0.62, SHINGLE())
    return out


# --------------------------------------------------------------------------
# render / export
# --------------------------------------------------------------------------
def setup_lighting():
    sc = bpy.context.scene
    for ob in [o for o in bpy.data.objects if o.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(ob, do_unlink=True)

    sd = bpy.data.lights.new("sun", "SUN")
    sd.energy = 5.0
    sd.angle = math.radians(2.0)
    sd.color = (1.0, 0.94, 0.82)
    so = bpy.data.objects.new("sun", sd)
    sc.collection.objects.link(so)
    so.rotation_euler = Euler((math.radians(48), 0, math.radians(197)), "XYZ")

    wd = sc.world
    if wd is None:
        wd = bpy.data.worlds.new("World")
        sc.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    bg = None
    for n in nt.nodes:
        if n.type == "BACKGROUND":
            bg = n
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.40, 0.55, 0.74, 1.0)
    bg.inputs[1].default_value = 0.50

    ad = bpy.data.lights.new("fill", "AREA")
    ad.energy = 620.0
    ad.size = 36.0
    ad.color = (0.72, 0.84, 1.0)
    ao = bpy.data.objects.new("fill", ad)
    sc.collection.objects.link(ao)
    ao.location = (-30.0, -40.0, 26.0)
    ao.rotation_euler = Euler((math.radians(58), 0, math.radians(35)), "XYZ")


def add_warm_fill(cam_loc, look_at):
    """Broad warm bounce from camera-left: the shadow side was going dead."""
    sc = bpy.context.scene
    ld = bpy.data.lights.new("warmfill", "AREA")
    ld.energy = 1100.0
    ld.size = 34.0
    ld.color = (1.0, 0.80, 0.58)
    lo = bpy.data.objects.new("warmfill", ld)
    sc.collection.objects.link(lo)
    cc = Vector(cam_loc)
    tt = Vector(look_at)
    d = (tt - cc).normalized()
    left = d.cross(Vector((0.0, 0.0, 1.0))).normalized()
    p = cc + left * 30.0 + Vector((0.0, 0.0, 12.0))
    lo.location = p
    lo.rotation_euler = (tt - p).to_track_quat("-Z", "Y").to_euler()
    return lo


def add_furnace_light(F, cfg):
    """One warm point light in the smelter mouth so it lights the yard."""
    sc = bpy.context.scene
    ld = bpy.data.lights.new("furnace_glow", "POINT")
    ld.energy = 260.0
    ld.color = (1.0, 0.45, 0.14)
    ld.shadow_soft_size = 1.2
    lo = bpy.data.objects.new("furnace_glow", ld)
    sc.collection.objects.link(lo)
    sm = cfg["smelter"]
    face = sm[2]
    M = F.M(sm[0], sm[1], 0.0, du=face[0], dv=face[1])
    p = M @ Vector((-0.5 * 0.0, 1.2, 1.5))
    # M is a rotated/translated frame: offset in local +Y (front) by 1.2
    p = (M @ Vector((0, 0, 0))) + (M.to_3x3() @ Vector((-0.5, 1.2, 1.5)))
    lo.location = p
    return lo


def setup_render(w=1280, h=720, samples=64):
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    print("[render] engine=", sc.render.engine)
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    for attr, val in (("taa_render_samples", samples), ("use_raytracing", True),
                      ("use_shadows", True), ("shadow_ray_count", 2),
                      ("shadow_step_count", 6)):
        try:
            setattr(sc.eevee, attr, val)
        except (AttributeError, TypeError):
            pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = 0.85
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    # glow on the emissive furnace / lanterns
    try:
        nt = None
        for attr in ("compositing_node_group", "node_tree"):
            nt = getattr(sc, attr, None)
            if nt is not None:
                break
        if nt is None:
            nt = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
            sc.compositing_node_group = nt
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        rl = nt.nodes.new("CompositorNodeRLayers")
        gl = nt.nodes.new("CompositorNodeGlare")
        gl.glare_type = "FOG_GLOW"
        gl.quality = "HIGH"
        gl.threshold = 1.0
        gl.size = 7
        cp = nt.nodes.new("CompositorNodeComposite")
        nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
        nt.links.new(gl.outputs["Image"], cp.inputs["Image"])
        sc.render.use_compositing = True
    except Exception as exc:      # compositor API drift across versions
        print("[render] compositor skipped:", exc)


def setup_camera(loc, look_at, lens=35.0):
    sc = bpy.context.scene
    for ob in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(ob, do_unlink=True)
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    co = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(co)
    co.location = Vector(loc)
    d = Vector(look_at) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    return co


def render_to(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


# ---------------------------------------------------------------- mine yard
def back_terrace(name, pts, z, cen, h1=2.30, h2=1.30, depth=2.35, skip=None):
    """Terraced stone edge closing the town's rear; grass stays on the shelf.

    The polyline is mitred at every vertex, so consecutive wall runs share their
    end points exactly (the self-check then finds no loose ends).  Shelf width
    tapers to nothing at both ends of a run, and a boulder anchors each end.
    """
    out = []
    segs = []
    for i in range(len(pts) - 1):
        px, py = pts[i]
        qx, qy = pts[i + 1]
        dx, dy = qx - px, qy - py
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        mx, my = (px + qx) * 0.5, (py + qy) * 0.5
        if (mx + nx - cen[0]) ** 2 + (my + ny - cen[1]) ** 2 > \
           (mx - nx - cen[0]) ** 2 + (my - ny - cen[1]) ** 2:
            nx, ny = -nx, -ny
        segs.append((px, py, qx, qy, nx, ny))
    runs = []
    cur = []
    for i, sg in enumerate(segs):
        mx, my = (sg[0] + sg[2]) * 0.5, (sg[1] + sg[3]) * 0.5
        if skip and math.hypot(mx - skip[0], my - skip[1]) < 9.5:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
            continue
        cur.append(i)
    if len(cur) >= 2:
        runs.append(cur)
    for ri, idx in enumerate(runs):
        vn = []
        for k, i in enumerate(idx):
            sg = segs[i]
            if k == 0:
                vn.append((sg[4], sg[5]))
            else:
                pv = segs[idx[k - 1]]
                nx, ny = pv[4] + sg[4], pv[5] + sg[5]
                L = math.hypot(nx, ny) or 1.0
                nx, ny = nx / L, ny / L
                d = max(0.62, nx * sg[4] + ny * sg[5])
                vn.append((nx / d, ny / d))
        last = segs[idx[-1]]
        vn.append((last[4], last[5]))
        vs = [(segs[i][0], segs[i][1]) for i in idx] + [(last[2], last[3])]
        low = [(v[0] + n[0] * 1.10, v[1] + n[1] * 1.10)
               for v, n in zip(vs, vn)]
        for k in range(len(low) - 1):
            out += wall("%sw%d_%d" % (name, ri, k), low[k], low[k + 1], z,
                        h=h1, thick=0.55, piers=False)
        up = []
        for k, (v, n) in enumerate(zip(vs, vn)):
            w = depth if 0 < k < len(vs) - 1 else 0.06
            up.append((v[0] + n[0] * (1.10 + w), v[1] + n[1] * (1.10 + w)))
        for k in range(len(up) - 1):
            out.append(poly_slab("%sg%d_%d" % (name, ri, k),
                                 [low[k], low[k + 1], up[k + 1], up[k]],
                                 z + h1, 0.30, GRASS_D()))
            ux0, uy0 = up[k]
            ux1, uy1 = up[k + 1]
            sl = math.hypot(ux1 - ux0, uy1 - uy0)
            if sl > 0.10:
                ub = at((ux0 + ux1) * 0.5, (uy0 + uy1) * 0.5, z + h1 - 0.06,
                        rz=math.atan2(-(ux1 - ux0), uy1 - uy0))
                out.append(box("%su%d_%d" % (name, ri, k),
                               ub @ T_at(0, 0, h2 * 0.5), (0.48, sl, h2),
                               ST_WALL(), bev=0.015))
                out.append(box("%su%d_%dc" % (name, ri, k),
                               ub @ T_at(0, 0, h2 + 0.06),
                               (0.62, sl + 0.03, 0.15), ST_LIP(), bev=0.01))
        for k in (0, len(low) - 1):
            out.append(rock("%sa%d_%d" % (name, ri, k),
                            at(low[k][0], low[k][1], z + 0.30,
                               rz=RNG.uniform(0.0, 6.28)),
                            1.30, RNG, CLIFF(), squash=0.78, jitter=0.24,
                            seg=6, ring=3))
            SOLIDS.append((low[k][0], low[k][1], 1.45))
    return out


def frame_front(x, y, fdir):
    """Frame whose local -v direction points along fdir (world unit vector)."""
    return Frame(x, y, math.atan2(-fdir[0], fdir[1]))


def rail(name, p0, p1, z=0.0, gauge=0.54, lift=0.0):
    """Straight double track between two plan points, lifted to a platform."""
    x0, y0 = p0[0], p0[1]
    x1, y1 = p1[0], p1[1]
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 0.6:
        return []
    F = Frame((x0 + x1) * 0.5, (y0 + y1) * 0.5, math.atan2(y1 - y0, x1 - x0))
    parts = rail_line(F, name, -L * 0.5, L * 0.5, 0.0, gauge)
    for o in parts:
        o.location.z += z + lift
    return parts


def cart_at(name, x, y, z, ang, rng, ore=True):
    return mine_cart(name, at(x, y, z, rz=ang), rng, ore)


def arch(name, x, y, ang, z, w=3.9, h=3.5, rng=None):
    """Stone arch through a retaining wall, rails passing under it."""
    rng = rng or random.Random(79)
    F = Frame(x, y, ang)
    out = []
    for s in (-1, 1):
        out.append(fbox(F, "%s_j%d" % (name, s), 0.0, s * (w * 0.5 + 0.55), z,
                        1.20, 1.10, h, ST_WALL(), bev=0.02))
    out.append(fbox(F, name + "_ln", 0.0, 0.0, z + h, 1.20, w + 2.2, 0.62, ST_WALL(),
                    bev=0.02))
    for i in range(5):
        a = -1.0 + i * 0.5
        out.append(fbox(F, "%s_v%d" % (name, i), 0.0, a * (w * 0.44), z + h + 0.62,
                        1.26, 0.46, 0.30, ST_DRESS(), bev=0.01))
    out.append(fbox(F, name + "_cp", 0.0, 0.0, z + h + 0.92, 1.34, w + 2.4, 0.16,
                    ST_LIP(), bev=0.01))
    out.append(fbox(F, name + "_dk", 0.0, 0.0, z, 1.40, w, h + 0.1, VOID()))
    return out



def fence_rect(name, x, y, w, d, ang, z=0.0, spacing=2.3):
    """Closed post-and-rail rectangle: four runs meeting at the corners."""
    out = []
    F1 = Frame(x, y, ang)
    F2 = Frame(x, y, ang + R2)
    for s in (-1, 1):
        out += fence_line(F1, "%s_a%d" % (name, s), -w * 0.5, w * 0.5,
                          s * d * 0.5, z, spacing=spacing)
        out += fence_line(F2, "%s_b%d" % (name, s), -d * 0.5, d * 0.5,
                          s * w * 0.5, z, spacing=spacing)
    return out


def haystack(name, x, y, z=0.0, s=1.7, rng=None):
    rng = rng or random.Random(11)
    out = [cone(name + "_h", at(x, y, z + s * 0.85), s, s * 1.7, GRASS_D(), seg=11)]
    out.append(cyl(name + "_b", at(x, y, z + 0.16), s * 0.62, 0.32, WOOD_D(), seg=10))
    out.append(beam(name + "_p", (x, y, z + s * 1.55), (x + 0.16, y + 0.1, z + s * 2.1),
                    0.09, WOOD_D()))
    return out


def orchard(name, x, y, w, d, ang, rng, rows=2, cols=3):
    out = fence_rect(name + "_f", x, y, w, d, ang, 0.0, 2.6)
    F = Frame(x, y, ang)
    for r in range(rows):
        for c in range(cols):
            u = -w * 0.5 + (w / float(cols)) * (c + 0.5)
            v = -d * 0.5 + (d / float(rows)) * (r + 0.5)
            px, py, _ = F.P(u, v, 0.0)
            out += conifer(Frame(px, py, rng.uniform(0, TAU)), "%s_t%d%d" % (name, r, c),
                           0.0, 0.0, 0.0, rng.uniform(3.6, 4.8), rng)
    return out


def stackyard(name, x, y, w, d, ang, rng):
    out = fence_rect(name + "_f", x, y, w, d, ang, 0.0, 2.4)
    F = Frame(x, y, ang)
    out += plank_stack(name + "_pl", F.M(-w * 0.25, 0.0, 0.0), 7, 3.0, rng)
    out += haystack(name + "_hs", x + w * 0.22, y - d * 0.16, 0.0, 1.8, rng)
    out += barrel_stack(name + "_bs", F.M(w * 0.30, d * 0.22, 0.0), rng)
    out += crate_pile(name + "_cr", F.M(-w * 0.18, d * 0.26, 0.0), rng)
    return out


def outskirts(cfg, add, rng):
    for i, o in enumerate(cfg.get("outskirts", ())):
        kind = o[0]
        if kind == "orchard":
            add("orchard_%d" % i, orchard("orc%d" % i, o[1], o[2], o[3], o[4], o[5], rng))
        elif kind == "stack":
            add("stack_%d" % i, stackyard("stk%d" % i, o[1], o[2], o[3], o[4], o[5], rng))
        elif kind == "copse":
            add("copse_%d" % i, tree_clump("cp%d" % i, o[1], o[2], o[3], o[4], rng, 0.0,
                                           (5.5, 8.5)))
        elif kind == "rock":
            add("orock_%d" % i, rock_band("ork%d" % i, o[1], rng, o[2], 0.0))
        elif kind == "wall":
            add("owall_%d" % i, wall("ow%d" % i, o[1], o[2], 0.0, h=o[3]))


def tie_ends(add, rng):
    """Every wall run must end on a house, another wall, or a post: add piers."""
    parts = []
    for i, (a, b, nm) in enumerate(RUNS):
        for k, e in enumerate((a, b)):
            ok = False
            for (cx, cy, hw, hd, ang) in RECTS:
                dx, dy = e.x - cx, e.y - cy
                ca, sa = math.cos(-ang), math.sin(-ang)
                lx, ly = dx * ca - dy * sa, dx * sa + dy * ca
                if abs(lx) <= hw + 0.6 and abs(ly) <= hd + 0.6:
                    ok = True
                    break
            if not ok:
                for (x, y, r) in SOLIDS:
                    if math.hypot(e.x - x, e.y - y) <= r + 0.55:
                        ok = True
                        break
            if not ok:
                for j, (a2, b2, nm2) in enumerate(RUNS):
                    if j != i and ((e - a2).length <= 0.6 or (e - b2).length <= 0.6):
                        ok = True
                        break
            if not ok:
                F = Frame(e.x, e.y, 0.0)
                parts.append(fbox(F, "pier_%d%d" % (i, k), 0.0, 0.0, 0.0, 0.54, 0.54,
                                  1.20, ST_WALL(), 0.02))
                parts.append(fbox(F, "pierc_%d%d" % (i, k), 0.0, 0.0, 1.20, 0.68, 0.68,
                                  0.13, ST_LIP(), 0.02))
                SOLIDS.append((e.x, e.y, 0.46))
    if parts:
        add("pier", parts)


def mine_yard(cfg, add, rng):
    """Yard platform, headframe, hoist, weigh house, adit bench and tramway."""
    yv = cfg["yard"]
    zy, zb = yv["z"], yv["bench_z"]
    x0, x1 = yv["x"]
    y0, y1 = yv["y"]

    add("yard_platform", poly_slab("yplat", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                   zy, zy + 0.45, GRAVEL()))
    # south retaining wall with the street ramp opening
    gx = sx(y0)
    add("yard_wall_w", wall("yww", (x0 - 0.2, y0), (gx - 2.75, y0), 0.0, h=zy + 0.85))
    add("yard_wall_e", wall("ywe", (gx + 2.75, y0), (x1 + 0.2, y0), 0.0, h=zy + 0.85))
    add("street_ramp", ramp_bed("sramp", (gx, y0 - 4.6), (gx, y0 + 0.3),
                                0.07, zy + 0.02, 4.9, COBBLE()))
    for s in (-1, 1):
        add("street_ramp_ck_%d" % s,
            box("src%d" % s, at(gx + s * 2.72, y0 - 2.15, zy * 0.5 + 0.28, rz=0.0),
                (0.34, 4.9, zy + 0.5), ST_WALL(), bev=0.015))
        SOLIDS.append((gx + s * 2.72, y0 - 2.15, 2.55))
    add("street_ramp_steps", stairs("srst", (gx + 2.6, y0 - 3.4), (gx + 2.6, y0 - 0.2),
                                    0.0, zy, 1.5, 3))

    # headframe on its plinth, dead on the street axis
    hx, hy = yv["head"]
    add("headframe", headframe("hfr", hx, hy, zy, 0.0, yv.get("hf_h", 14.6), rng,
                              base_h=yv.get("base_h", 1.22)))
    add("yard_lamp", lamp_post(Frame(hx + 3.35, hy - 1.4, zy), "ylp", 0.0, 0.0, 3.25,
                               (0, -1)))
    SOLIDS.append((hx, hy, 3.0))
    # the plinth stair comes down to the yard on the -u side already

    # hoist house east of it, door facing the collar
    hh = yv["hoist"]
    add("hoist", hoist_house("hst", hh[0], hh[1], zy, frame_front(0, 0, (0, -1)).ang,
                             rng))
    SOLIDS.append((hh[0], hh[1], 3.2))
    RECTS.append((hh[0], hh[1], 2.3, 1.95, math.pi))

    # weigh house + weighbridge on the yard track
    wh = yv["weigh"]
    add("weigh", weigh_house("wgh", wh[0], wh[1], zy,
                             frame_front(0, 0, (1, 0)).ang, rng))
    SOLIDS.append((wh[0], wh[1], 2.4))
    RECTS.append((wh[0], wh[1], 1.9, 1.65, math.pi * 0.5))
    add("weighbridge", weighbridge("wgb", wh[0] + 2.6, wh[1], R2, zy))

    # ore stock piles + spoil tip
    for i, p in enumerate(yv.get("ore", ())):
        add("ore_%d" % i, ore_pile("ore%d" % i, p[0], p[1], p[2], rng))
    sp = yv["spoil"]
    add("spoil", spoil_heap("spl", sp[0], sp[1], sp[2], rng))

    # track: ramp foot -> weighbridge -> collar, plus a spur to the hoist
    tk = yv["track"]
    add("track", rail("trk", tk[0], tk[1], zy, 0.54, 0.16))
    add("track2", rail("trk2", (wh[0] + 1.2, wh[1]), (hx - 0.7, hy - 0.6), zy, 0.54,
                       0.16))
    add("cart_yard", cart_at("cyt", (tk[0][0] + tk[1][0]) * 0.5,
                             (tk[0][1] + tk[1][1]) * 0.5, zy + 0.26,
                             math.atan2(tk[1][1] - tk[0][1], tk[1][0] - tk[0][0]), rng))

    # north retaining wall (bench face) with the tramway arch
    rb = yv["ramp"]
    ax = (rb[0][0] + rb[1][0]) * 0.5
    add("bench_wall_w", wall("bww", (x0 - 0.2, y1), (ax - 2.2, y1), 0.0,
                             h=(zb - zy) + 2.6))
    add("bench_wall_e", wall("bwe", (ax + 2.2, y1), (x1 + 0.2, y1), 0.0,
                             h=(zb - zy) + 2.6))
    add("tram_arch", arch("arch", ax, y1, 0.0, zy, 4.0, (zb - zy) + 1.0, rng))
    SOLIDS.append((ax, y1, 2.35))
    # the inclined tramway from the adit bench down through the arch
    add("tram", ramp("tram", (rb[0][0], rb[0][1]), (rb[1][0], rb[1][1]),
                     rb[0][2], rb[1][2], 3.4, GRAVEL(), True, rng))
    add("tram_cart", cart_at("tct", (rb[0][0] + rb[1][0]) * 0.5,
                             (rb[0][1] + rb[1][1]) * 0.5,
                             (rb[0][2] + rb[1][2]) * 0.5 + 0.30,
                             math.atan2(rb[1][1] - rb[0][1], rb[1][0] - rb[0][0]), rng))

    # adit bench: platform + retaining face + the portal itself
    bx0, bx1 = yv["bench_x"]
    by0, by1 = yv["bench_y"]
    add("bench_platform", poly_slab("bplat", [(bx0, by0), (bx1, by0), (bx1, by1),
                                              (bx0, by1)], zb, zb + 0.40, GRAVEL()))
    # corner piers close every yard-wall end
    for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1), (bx0, by1), (bx1, by1)):
        add("yard_pier_%d_%d" % (int(cx * 10), int(cy * 10)),
            box("yp%d%d" % (int(cx), int(cy)), at(cx, cy, 1.15),
                (0.92, 0.92, 2.4), ST_DRESS(), bev=0.02))
        SOLIDS.append((cx, cy, 0.85))
    ad = yv["adit"]
    add("adit", adit_portal("adit", ad[0], ad[1], zb, ad[2], 2.55, 3.15, rng))
    add("adit_rock", rock_band("adr", [(ad[0] - 4.6, ad[1] - 3.2),
                                       (ad[0] + 5.4, ad[1] - 2.6),
                                       (ad[0] + 6.2, ad[1] + 2.4)], rng, (1.8, 3.0),
                                zb))
    add("adit_spoil", ore_pile("asp", ad[0] - 4.4, ad[1] + 1.2, 1.7, rng, GRAVEL()))


# ---------------------------------------------------------------- materials
def dedupe_materials(objs):
    """Collapse mat.001/mat.002 duplicates onto the palette base names."""
    import re
    canon = {}
    for m in bpy.data.materials:
        root = re.sub(r"\.\d{3}$", "", m.name)
        if root != m.name and root in bpy.data.materials:
            canon[m.name] = root
    for ob in objs:
        for slot in ob.material_slots:
            if slot.material and slot.material.name in canon:
                slot.material = bpy.data.materials[canon[slot.material.name]]
    for name, root in canon.items():
        m = bpy.data.materials.get(name)
        if m is not None and m.users == 0:
            bpy.data.materials.remove(m)
    return len(canon)


GROUND_MATS = ("mine_cobble", "mine_dirt", "mine_gravel", "mine_dressed",
               "mine_step", "mine_stone", "mine_stone_dark", "mine_rock",
               "mine_cliff", "mine_mud0", "mine_mud1", "mine_mud2", "mine_rut",
               "stone", "stone_step")
GRASS_MATS = ("mine_grass_dry", "mine_pine", "leaf")


def self_check(core=CORE, radius=CORE_R, n=200, seed=7):
    """Statutory check: n random core points, what surface is under each?"""
    import re as _re
    deps = bpy.context.evaluated_depsgraph_get()
    r = random.Random(seed)
    tally = {"hard": 0, "built": 0, "grass": 0, "void": 0}
    for i in range(n):
        a = r.uniform(0.0, TAU)
        rr = radius * math.sqrt(r.random())
        x, y = core[0] + rr * math.cos(a), core[1] + rr * math.sin(a)
        hit, loc, nor, idx, ob, mw = bpy.context.scene.ray_cast(
            deps, (x, y, 60.0), (0.0, 0.0, -1.0))
        if not hit:
            tally["void"] += 1
            continue
        mat = ""
        try:
            mat = ob.data.materials[ob.data.polygons[idx].material_index].name
        except Exception:
            pass
        mat = _re.sub(r"\.\d{3}$", "", mat)
        if mat in GRASS_MATS:
            tally["grass"] += 1
        elif mat in GROUND_MATS:
            tally["hard"] += 1
        else:
            tally["built"] += 1
    pct = {k: 100.0 * v / float(n) for k, v in tally.items()}
    return pct, tally


def verify_walls():
    """Every wall end must land on a building, another wall end, or a solid."""
    ends = []
    for (p0, p1, nm) in RUNS:
        ends.append((p0, nm))
        ends.append((p1, nm))
    bad = []
    for (p, nm) in ends:
        ok = False
        for (cx, cy, hw, hd, mz) in RECTS:
            dx, dy = p.x - cx, p.y - cy
            lx = dx * math.cos(mz) + dy * math.sin(mz)
            ly = -dx * math.sin(mz) + dy * math.cos(mz)
            if abs(lx) <= hw + 0.6 and abs(ly) <= hd + 0.6:
                ok = True
                break
        if not ok:
            for (q, nm2) in ends:
                if nm2 != nm and (q - p).length < 0.6:
                    ok = True
                    break
        if not ok:
            for (sxx, syy, sr) in SOLIDS:
                if (Vector((sxx, syy, 0.0)) - p).length < sr + 0.5:
                    ok = True
                    break
        if not ok:
            _near = sorted([((q - p).length, nm2) for (q, nm2) in ends])[:3]
            print("[dbg] loose %s at (%.2f,%.2f) nearest %s solids %d" % (nm, p.x, p.y, [(round(d,2), n2) for d, n2 in _near], len(SOLIDS)))
            bad.append((nm, round(p.x, 2), round(p.y, 2)))
    return bad


def stats():
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    tris = 0
    xs, ys, zs = [], [], []
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        for v in me.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    mats = sorted({s.material.name for o in objs for s in o.material_slots
                   if s.material})
    if not xs:
        return dict(objects=0, tris=0, mats=mats, bbox=(0, 0, 0, 0, 0, 0))
    bb = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    return dict(objects=len(objs), tris=tris, mats=mats, bbox=bb)


def headframe_visible():
    """Height of the headframe foundation visible from the gate camera."""
    from mathutils import Vector
    ob = None
    for o in bpy.data.objects:
        if o.type == "MESH" and "headframe" in o.name:
            ob = o
            break
    if ob is None:
        return 0.0
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    z0 = min(v.z for v in bb)
    zt = max(v.z for v in bb)
    fx = (min(v.x for v in bb) + max(v.x for v in bb)) * 0.5
    fy = min(v.y for v in bb) + 0.30
    cam = Vector((0.0, -20.0, 2.2))
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    z = z0 + 0.05
    while z < z0 + 3.5:
        tgt = Vector((fx, fy, z))
        d = (tgt - cam)
        dist = d.length
        ok, loc, nor, idx, hit, mx = sc.ray_cast(dg, cam, d.normalized(),
                                                 distance=dist + 0.45)
        if ok and "headframe" in hit.name:
            return max(0.0, z - z0)
        z += 0.02
    return 0.0


def export_fbx(path):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True,
                             object_types={"MESH"}, global_scale=1.0,
                             apply_unit_scale=True, use_mesh_modifiers=True,
                             axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", path_mode="AUTO",
                             embed_textures=False, bake_space_transform=False)


def build_one(name, do_render=True, do_export=True, do_save=True):
    cfg = VARIANTS[name]
    t0 = time.time()
    reset_scene()
    medkit._MAT_CACHE.clear()
    del RUNS[:]
    del RECTS[:]
    del SOLIDS[:]
    del GROUPS[:]
    build_town(cfg)

    for (gname, parts) in list(GROUPS):
        if parts:
            join_group(parts, "%s_%s" % (name, gname))

    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    fixed = dedupe_materials(objs)
    bpy.context.view_layer.update()
    st = stats()
    pct, tally = self_check(cfg.get("core", CORE), cfg.get("core_r", CORE_R))
    bad = verify_walls()
    print("[mine] %s objects=%d tris=%d mats=%d remapped=%d"
          % (name, st["objects"], st["tris"], len(st["mats"]), fixed))
    print("[mine] %s bbox x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]"
          % ((name,) + st["bbox"]))
    print("[mine] %s core hard=%.1f%% built=%.1f%% grass=%.1f%% void=%.1f%% "
          "isolated_fences=%d" % (name, pct["hard"], pct["built"], pct["grass"],
                                  pct["void"], len(bad)))
    if bad:
        print("[mine] %s LOOSE WALL ENDS: %s" % (name, bad[:12]))
    print("[mine] %s build %.1fs" % (name, time.time() - t0))

    if do_export:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        export_fbx(os.path.join(EXPORT_DIR, name + ".fbx"))

    hv = headframe_visible()
    print("[mine] %s headframe base visible from gate = %.2f m" % (name, hv))

    if do_render:
        setup_lighting()
        setup_render(1280, 720, 64)
        cams = [("", cfg["cam"][0], cfg["cam"][1], cfg["cam"][2]),
                ("_player", (0.0, -13.5, 17.3), (0.0, 0.5, 0.0), 40.0),
                ("_eye", (2.2, -9.0, 1.7), (0.0, 3.5, 2.2), 35.0),
                ("_gate", (0.0, -20.0, 2.2), (0.0, 4.0, 0.0), 28.0),
                ("_wide", cfg["wide"][0], cfg["wide"][1], cfg["wide"][2])]
        for (suf, loc, look, lens) in cams:
            if suf != "":
                add_warm_fill(loc, look)
            setup_camera(loc, look, lens)
            render_to(os.path.join(RENDER_DIR, name + suf + ".png"))

    if do_save:
        os.makedirs(os.path.join(BASE, "kingdom"), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(
            filepath=os.path.join(BASE, "kingdom", name + ".blend"))
    return st


# ---------------------------------------------------------------- variants
SPINE_A = [(-0.6, -46.0), (-0.4, -36.0), (-0.2, -26.0), (0.0, -16.0), (0.0, -8.0),
           (0.0, 0.0), (0.4, 8.0), (0.8, 16.0), (1.0, 24.0), (1.2, 32.0)]

A = dict(
    seed=20261022, water="water", core=(0.0, 12.0),
    spine=SPINE_A,
    plate=[(-26.0, -43.0), (8.6, -43.0), (9.6, -34.0), (10.6, -26.0), (13.0, -18.0),
           (19.6, -10.0), (25.4, -2.0), (26.4, 8.0), (25.0, 18.0), (21.5, 26.0),
           (18.0, 32.0), (13.6, 38.0), (5.0, 41.0), (-5.0, 39.4), (-13.0, 34.4),
           (-19.4, 27.0), (-24.4, 18.0), (-26.4, 8.0), (-25.8, -4.0), (-21.6, -14.0),
           (-17.6, -24.0), (-21.0, -34.0)],
    apron=[(-24.4, -43.0), (7.0, -43.0), (8.0, -34.0), (9.0, -26.0), (11.4, -18.0),
           (18.0, -10.0), (23.8, -2.0), (24.8, 8.0), (23.4, 18.0), (19.9, 26.0),
           (16.4, 31.4), (12.0, 36.6), (4.4, 39.4), (-4.4, 37.9), (-12.4, 33.2),
           (-18.6, 26.0), (-23.6, 17.4), (-24.8, 8.0), (-24.2, -4.0), (-20.0, -14.0),
           (-16.0, -24.0), (-19.4, -33.0)],
    apx=-0.30,
    forecourt=[(-6.5, -40.2), (6.3, -40.2), (6.8, -33.2), (-7.0, -33.2)],
    gate=(0.0, -6.0),
    street=(-6.0, 14.0),
    square=dict(
        poly=[(-7.2, 0.4), (7.4, 0.4), (7.4, 13.2), (-7.2, 13.2)],
        kerb=[(-6.6, 1.0), (6.8, 1.0), (6.8, 12.6), (-6.6, 12.6)],
        well=(2.4, 4.4),
        stalls=[(-4.9, 2.6, 0.15), (-4.6, 9.4, -0.30), (5.2, 9.8, 0.22)],
        board=(-6.4, 11.2, 1.45),
        banner=(5.1, 1.2, 5.4, 0.25),
        tree=(-4.9, 8.4)),
    west_terrace=dict(y=(0.2, 13.4), inset=0.10, depth=8.6, terrace_x=-7.2,
                      stairs=(5.0, 10.4)),
    rows=[
        dict(tag="ws", side=-1, y0=-5.6, z=0.45, sb=0.5,
             specs=[dict(W=5.6, D=5.0, kind=1, gap=0.0, FH=2.5)]),
        dict(tag="es", side=1, y0=-5.4, z=0.0, sb=0.45,
             specs=[dict(W=5.6, D=4.8, kind=2, gap=0.0, FH=2.5)]),
    ],
    lines=[
        dict(tag="pw", xf=-7.85, fd=1, y0=2.4, z=0.45,
             specs=[dict(W=6.0, D=4.9, kind=1, gap=1.0, dorm=True),
                    dict(W=5.6, D=4.7, kind=4, gap=0.0)]),
        dict(tag="pe", xf=8.05, fd=-1, y0=2.6, z=0.0,
             specs=[dict(W=5.8, D=4.8, kind=2, gap=1.1),
                    dict(W=5.2, D=4.6, kind=0, gap=0.0, dorm=True)]),
    ],
    buildings=[
        dict(tag="tav", type="tavern", x=7.20, y=17.20, W=9.6, D=6.6,
             front=(0, -1), z=0.0),
        dict(tag="forge", type="cottage", x=-11.0, y=18.00, W=5.4, D=4.6,
             front=(1, 0), kind=2, z=0.45, extras=False),
        dict(tag="smelt", type="smelter", x=-13.6, y=27.00, W=8.4, D=7.0,
             front=(1, 0), z=0.45),
    ],
    lanes=[([(-7.2, 13.0), (-9.6, 14.6), (-9.6, 20.4), (-9.4, 23.4)], 2.45)],
    square_walls=[((-2.60, 0.30), (-7.2, 0.4)), ((2.60, 0.12), (7.4, 0.4)),
                  ((-0.65, 13.90), (-7.4, 13.2)), ((2.8, 13.90), (7.6, 13.2))],
    outskirts=[("orchard", -17.5, 6.0, 9.0, 12.0, 0.0),
               ("orchard", 17.0, 18.0, 8.0, 9.0, R2),
               ("stack", -16.0, -12.0, 7.5, 6.0, 0.3),
               ("stack", 15.5, -2.0, 7.0, 6.0, -0.2),
               ("copse", -18.0, -20.0, 3, 4),
               ("copse", -21.0, 16.0, 2, 3),
               ("copse", 14.0, 30.0, 2, 4),
               ("rock", [(-23.0, -6.0), (-22.0, 12.0), (21.0, 26.0)], (2.2, 3.6)),
               ],
    yard=dict(x=(-12.4, 9.4), y=(23.2, 31.2), z=0.90, bench_z=2.70,
              head=(0.9, 25.9), hoist=(6.2, 24.7), weigh=(-6.0, 24.6),
              ore=[(3.2, 29.4, 2.1), (-2.4, 29.6, 1.7), (7.4, 29.6, 1.4)],
              spoil=(-9.4, 29.4, 3.6),
              track=((6.2, 29.2), (2.2, 28.2)),
              ramp=((6.40, 32.20, 2.70), (4.20, 27.60, 0.90)),
              bench_x=(1.0, 13.0), bench_y=(31.2, 38.0),
              adit=(7.00, 33.40, math.pi * 0.25)),
    axis_lane=(0.90, 13.20, 23.10, 1.35),
    cam=((31.0, -33.0, 29.0), (0.5, 10.0, 3.5), 34.0),
    wide=((22.0, -30.0, 26.0), (0.5, 12.0, 3.0), 36.0),
)

SPINE_B = [(-1.2, -46.0), (-1.0, -36.0), (-0.8, -26.0), (-0.5, -16.0), (-0.2, -8.0),
           (0.2, 0.0), (0.8, 8.0), (1.2, 16.0), (1.4, 24.0), (1.5, 32.0)]

B = dict(
    seed=20261023, water="mine_water", core=(0.0, 11.0),
    spine=SPINE_B,
    plate=[(-24.6, -43.0), (7.6, -43.0), (8.6, -34.0), (10.4, -22.0), (12.4, -12.0),
           (13.4, -2.0), (16.0, 6.0), (22.0, 12.0), (22.8, 20.0), (20.2, 27.0),
           (16.4, 33.0), (11.4, 38.0), (3.0, 40.0), (-5.0, 37.6), (-11.0, 31.0),
           (-16.4, 25.0), (-21.4, 18.0), (-24.6, 8.0), (-24.8, -2.0), (-22.0, -12.0),
           (-19.0, -24.0), (-21.0, -34.0)],
    apron=[(-23.0, -43.0), (6.0, -43.0), (7.0, -34.0), (8.8, -22.0), (10.8, -12.0),
           (11.8, -2.0), (14.4, 6.0), (20.4, 12.0), (21.2, 20.0), (18.6, 26.6),
           (14.8, 32.4), (10.0, 36.6), (2.6, 38.4), (-4.4, 36.0), (-10.4, 29.8),
           (-14.8, 24.2), (-19.8, 17.4), (-23.0, 7.6), (-23.2, -2.0), (-20.4, -12.0),
           (-17.4, -24.0), (-19.4, -33.0)],
    apx=-0.55,
    forecourt=[(-7.0, -40.2), (5.6, -40.2), (6.0, -33.2), (-7.4, -33.2)],
    gate=(-0.5, -6.0),
    street=(-6.0, 14.4),
    square=dict(
        poly=[(-6.6, 0.6), (8.6, 0.6), (8.6, 13.0), (-6.6, 13.0)],
        kerb=[(-6.0, 1.2), (8.0, 1.2), (8.0, 12.4), (-6.0, 12.4)],
        well=(3.4, 5.0),
        stalls=[(-4.6, 2.8, 0.15), (-4.4, 9.2, -0.3), (6.2, 9.8, 0.22)],
        board=(-5.8, 11.0, 1.45),
        banner=(6.0, 1.6, 5.2, 0.25),
        tree=None, cart=(-3.30, 1.70, 0.35)),
    west_terrace=dict(y=(0.4, 13.2), inset=0.10, depth=8.0, terrace_x=-6.6,
                      stairs=(5.2, 10.6)),
    rows=[
        dict(tag="ws", side=-1, y0=-5.6, z=0.45, sb=0.5,
             specs=[dict(W=5.8, D=5.0, kind=2, gap=0.0, FH=2.5)]),
        dict(tag="es", side=1, y0=-5.4, z=0.0, sb=0.45,
             specs=[dict(W=5.4, D=4.8, kind=0, gap=0.0, FH=2.5)]),
    ],
    lines=[
        dict(tag="pw", xf=-7.25, fd=1, y0=1.4, z=0.45,
             specs=[dict(W=5.8, D=4.9, kind=3, gap=1.0, dorm=True),
                    dict(W=5.4, D=4.7, kind=1, gap=0.0)]),
        dict(tag="pe", xf=9.25, fd=-1, y0=1.6, z=0.0,
             specs=[dict(W=5.6, D=4.8, kind=2, gap=1.1),
                    dict(W=5.0, D=4.6, kind=4, gap=0.0, dorm=True)]),
    ],
    buildings=[
        dict(tag="tav", type="tavern", x=8.00, y=17.20, W=9.6, D=6.6,
             front=(0, -1), z=0.0),
        dict(tag="forge", type="cottage", x=-11.2, y=18.20, W=5.4, D=4.6,
             front=(1, 0), kind=1, z=0.45, extras=False),
        dict(tag="smelt", type="smelter", x=-13.8, y=27.20, W=8.4, D=7.0,
             front=(1, 0), z=0.45),
        dict(tag="whs", type="shed", x=17.40, y=-4.00, W=4.2, D=3.2,
             front=(0, -1), z=0.0),
    ],
    lanes=[([(-6.6, 12.4), (-9.4, 14.0), (-9.4, 20.6), (-9.2, 23.4)], 2.45)],
    square_walls=[((-2.60, 0.50), (-6.6, 0.6)), ((2.85, 0.04), (8.6, 0.6)),
                  ((-0.65, 13.70), (-6.8, 13.0)), ((3.2, 13.70), (8.8, 13.0))],
    outskirts=[("orchard", -16.5, 6.5, 8.5, 11.0, 0.0),
               ("orchard", 17.5, 20.0, 7.5, 8.0, R2),
               ("stack", -15.0, -13.0, 7.0, 6.0, 0.3),
               ("stack", 16.0, 1.0, 6.5, 6.0, -0.2),
               ("copse", -17.5, -21.0, 3, 4),
               ("copse", 13.0, 30.0, 2, 3),
               ("rock", [(-22.5, -6.0), (-21.5, 12.0), (20.5, 26.0)], (2.2, 3.4)),
               ],
    yard=dict(x=(-12.0, 9.0), y=(23.2, 31.0), z=0.90, bench_z=3.30,
              head=(0.8, 25.7), hoist=(6.0, 24.6), weigh=(-5.8, 24.5),
              ore=[(3.0, 29.2, 2.0), (-2.2, 29.4, 1.6), (7.0, 29.4, 1.4)],
              spoil=(-9.0, 29.2, 3.4),
              track=((6.0, 29.0), (2.0, 28.0)),
              ramp=((6.20, 31.80, 3.30), (4.10, 27.40, 0.90)),
              bench_x=(1.0, 12.4), bench_y=(31.0, 37.4),
              adit=(6.80, 32.80, math.pi * 0.25)),
    axis_lane=(0.90, 13.10, 23.10, 1.35),
    cam=((30.0, -32.0, 28.0), (0.5, 10.0, 3.5), 34.0),
    wide=((21.0, -29.0, 25.0), (0.5, 12.0, 3.0), 36.0),
)

SPINE_C = [(-0.8, -46.0), (-0.6, -36.0), (-0.4, -26.0), (-0.2, -16.0), (0.0, -8.0),
           (0.2, 0.0), (0.4, 8.0), (0.6, 16.0), (0.7, 24.0), (0.8, 32.0)]

C = dict(
    seed=20261024, water="water", core=(0.0, 12.0),
    spine=SPINE_C,
    plate=[(-25.0, -43.0), (7.6, -43.0), (8.6, -34.0), (10.6, -24.0), (12.2, -14.0),
           (13.2, -4.0), (16.0, 4.0), (22.2, 10.0), (23.2, 18.0), (20.4, 26.0),
           (15.6, 32.4), (10.4, 37.4), (4.0, 39.4), (-3.4, 36.8), (-9.4, 31.2),
           (-18.4, 24.4), (-23.6, 16.0), (-25.2, 6.0), (-25.2, -6.0), (-22.2, -16.0),
           (-19.2, -26.0), (-21.0, -34.0)],
    apron=[(-23.4, -43.0), (6.0, -43.0), (7.0, -34.0), (9.0, -24.0), (10.6, -14.0),
           (11.6, -4.0), (14.4, 4.0), (20.6, 10.0), (21.6, 17.8), (18.8, 25.4),
           (14.0, 31.8), (9.0, 36.2), (3.4, 38.0), (-2.8, 35.4), (-8.8, 30.0),
           (-17.4, 23.4), (-22.4, 15.6), (-23.8, 6.0), (-23.8, -6.0), (-20.8, -16.0),
           (-17.8, -26.0), (-19.4, -33.0)],
    apx=-0.35,
    forecourt=[(-6.8, -40.2), (5.8, -40.2), (6.2, -33.2), (-7.2, -33.2)],
    gate=(0.0, -6.0),
    street=(-6.0, 14.0),
    square=dict(
        poly=[(-6.2, 0.4), (7.0, 0.4), (7.0, 12.8), (-6.2, 12.8)],
        kerb=[(-5.6, 1.0), (6.4, 1.0), (6.4, 12.2), (-5.6, 12.2)],
        well=(2.2, 4.2),
        stalls=[(-4.4, 2.4, 0.15), (-4.2, 9.0, -0.3)],
        board=(-5.6, 10.8, 1.45),
        banner=(4.8, 1.4, 5.4, 0.25),
        tree=(-4.4, 7.6), cart=(-3.10, 1.55, 0.30)),
    west_terrace=dict(y=(0.2, 13.0), inset=0.10, depth=7.4, terrace_x=-6.2,
                      stairs=(4.8, 10.0)),
    rows=[
        dict(tag="ws", side=-1, y0=-5.6, z=0.90, sb=0.6,
             specs=[dict(W=5.6, D=5.0, kind=3, gap=0.0, FH=2.5)]),
        dict(tag="es", side=1, y0=-5.4, z=0.0, sb=0.45,
             specs=[dict(W=5.4, D=4.8, kind=1, gap=0.0, FH=2.5)]),
    ],
    lines=[
        dict(tag="pw", xf=-6.85, fd=1, y0=1.2, z=0.90,
             specs=[dict(W=5.6, D=4.9, kind=0, gap=1.0, dorm=True),
                    dict(W=5.2, D=4.7, kind=2, gap=0.0)]),
        dict(tag="pe", xf=7.65, fd=-1, y0=1.4, z=0.0,
             specs=[dict(W=5.4, D=4.8, kind=4, gap=1.1),
                    dict(W=4.8, D=4.6, kind=0, gap=0.0, dorm=True)]),
    ],
    buildings=[
        dict(tag="tav", type="tavern", x=6.60, y=16.90, W=9.4, D=6.4,
             front=(0, -1), z=0.45),
        dict(tag="forge", type="cottage", x=-10.6, y=17.80, W=5.4, D=4.6,
             front=(1, 0), kind=3, z=0.90, extras=False),
        dict(tag="smelt", type="smelter", x=-13.2, y=26.80, W=8.4, D=7.0,
             front=(1, 0), z=0.90),
    ],
    lanes=[([(-6.2, 12.2), (-9.0, 13.8), (-9.0, 20.2), (-8.8, 22.8)], 2.45)],
    square_walls=[((-2.60, 0.36), (-6.2, 0.4)), ((2.85, 0.02), (7.0, 0.4)),
                  ((-0.65, 13.50), (-6.4, 12.8)), ((1.9, 13.50), (7.2, 12.8))],
    outskirts=[("orchard", -17.0, 5.0, 8.0, 11.0, 0.0),
               ("orchard", 16.5, 17.0, 7.0, 8.0, R2),
               ("stack", -15.5, -13.5, 7.0, 6.0, 0.3),
               ("stack", 15.0, -2.0, 6.5, 5.5, -0.2),
               ("copse", -18.0, -22.0, 3, 4),
               ("copse", -20.0, 15.0, 2, 3),
               ("copse", 12.5, 29.0, 2, 3),
               ("rock", [(-23.2, -4.0), (-22.6, 13.0), (19.5, 25.0)], (2.4, 3.8)),
               ],
    yard=dict(x=(-11.6, 8.6), y=(22.8, 30.6), z=1.35, bench_z=4.50,
              head=(0.7, 25.3), hoist=(5.8, 24.2), weigh=(-5.6, 24.1),
              ore=[(2.8, 28.8, 2.0), (-2.2, 29.0, 1.5)],
              spoil=(-8.8, 28.8, 3.2),
              track=((5.8, 28.6), (1.8, 27.6)),
              ramp=((6.00, 31.40, 4.50), (3.90, 27.00, 1.35)),
              bench_x=(0.8, 12.0), bench_y=(30.6, 37.0),
              adit=(6.60, 32.40, math.pi * 0.25)),
    axis_lane=(0.80, 12.90, 22.90, 1.35),
    cam=((29.0, -31.0, 27.0), (0.5, 10.0, 3.5), 34.0),
    wide=((20.0, -28.0, 24.0), (0.5, 12.0, 3.0), 36.0),
)

VARIANTS = {"mine_a": A, "mine_b": B, "mine_c": C}


def main():
    import argparse
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all")
    ap.add_argument("--norender", action="store_true")
    a = ap.parse_args(argv)
    names = sorted(VARIANTS) if a.variant == "all" else [a.variant]
    for nm in names:
        build_one(nm, do_render=not a.norender)


if __name__ == "__main__":
    main()

