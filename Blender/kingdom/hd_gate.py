"""hd_gate.py - the royal city gate of the capital (Asura).

The player walks through it; the camera flies over it.  Local frame:

    origin  = centre of the threshold (the middle of the gate passage, ground)
    +Y      = OUT of the city (the road side, where the barbican and moat are)
    -Y      = INTO the city (wall-walk, stairs, guardhouse)
    +Z      = up, ground at z = 0

Everything is parametric; `build(MAT, rng)` returns the object list and
`preview()` renders a fixed set of views to Blender/renders/kingdom/.

Run:
    blender -b --factory-startup --python hd_gate.py
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import bpy
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
from medkit import T_at as Ts, box, cyl, cone, sphere

OUT_DIR = r"E:\My World\Blender\renders\kingdom"
PI = math.pi
TAU = math.tau

# --------------------------------------------------------------------------
#  master dimensions (metres)
# --------------------------------------------------------------------------
R_PASS = 2.75          # half width of the passage  (5.50 m wide)
Z_SPRING = 4.25        # springing of the barrel vault
Z_CROWN = Z_SPRING + R_PASS          # 7.00 m to the crown
GH_W = 13.2            # gatehouse half width
GH_D = 6.6             # gatehouse half depth  (13.2 m thick)
GH_H = 19.6            # gatehouse wall head / wall-walk floor
FP_W = 6.50            # forebuilding (porch block) half width
FP_Y0 = 6.35           # where the forebuilding starts, inside the gatehouse face
FP_Y1 = 9.25           # its front face: the arch stands 1.25 m proud of the drums
FP_H = 12.20           # its height (corbelled brattice on top)
TOW_X = 14.2           # tower centres
TOW_R = 8.0            # tower radius
TOW_TOP = 26.4         # top of the tower shaft (before the machicolation)
WALK = TOW_TOP + 0.55  # tower wall-walk level
WALL_H = 12.6          # curtain wall height
WALL_T = 1.7           # curtain wall half thickness
CURT_END = 28.2        # outer end of the curtain wall stub
MOAT_Y0, MOAT_Y1 = 15.0, 26.0
MOAT_Z = -1.25
MOAT_BOT = -2.75
BR_Y0, BR_Y1 = 13.0, 26.8
BR_HW = 3.7
BARB_X = 8.9
BARB_Y = 26.6          # barbican tower centres (the D's chord plane)
BARB_R = 4.1
BARB_H = 11.6
ROAD_HW = 3.5


def RotX(a):
    return Matrix.Rotation(a, 4, "X")


def RotY(a):
    return Matrix.Rotation(a, 4, "Y")


def RotZ(a):
    return Matrix.Rotation(a, 4, "Z")


def basis_T(x, y, z, p):
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0] = x[i]
        m[i][1] = y[i]
        m[i][2] = z[i]
        m[i][3] = p[i]
    return m


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------
#  materials
# --------------------------------------------------------------------------
def _glow(name, base, emis, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = K.c(base, 1.0)
            n.inputs["Roughness"].default_value = 0.5
            if "Emission Color" in n.inputs:
                n.inputs["Emission Color"].default_value = K.c(emis, 1.0)
                n.inputs["Emission Strength"].default_value = strength
    return m


def _bsdf_of(m):
    for nd in m.node_tree.nodes:
        if nd.type == "BSDF_PRINCIPLED":
            return nd
    return None


def _stone_mat(name, base, dark, light, scale=1.0, rough=0.84, bump=0.18):
    """Isotropic dressed stone: mottled tone plus a fine grain, no UV pattern.

    `medkit.mat_stone` paints a Brick texture through a swizzled (x + y, z)
    vector.  That is the right call for a flat wall, but on a cylinder the
    swizzle's derivative collapses towards +-45 deg, so the courses smear into
    vertical bands roughly twice as wide as they should be -- which is exactly
    the "camouflage" and the pale vertical column the drum towers showed.  The
    coursing here is real geometry (`ashlar`, `ring_ashlar`, `arch_order`), so
    the shader only has to supply stone, not joints: two isotropic noise fields
    multiplied together give blotches at wall scale and at stone scale, and a
    soft bump keeps the silhouette from reading flat.
    """
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf_of(m)
    b.inputs["Roughness"].default_value = rough
    for key in ("Metallic",):
        if key in b.inputs:
            b.inputs[key].default_value = 0.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 120)
    # coarse weathering, a few metres across
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.location = (-700, 300)
    n1.inputs["Scale"].default_value = 0.36 * scale
    n1.inputs["Detail"].default_value = 3.0
    n1.inputs["Roughness"].default_value = 0.50
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    r1 = nt.nodes.new("ShaderNodeValToRGB")
    r1.location = (-500, 300)
    r1.color_ramp.interpolation = "LINEAR"
    e = r1.color_ramp.elements
    e[0].position = 0.33
    e[0].color = K.c(dark)
    e[1].position = 0.76
    e[1].color = K.c(base)
    nt.links.new(n1.outputs["Fac"], r1.inputs["Fac"])
    # mid-scale tone patches, the size of a handful of stones
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.location = (-700, 40)
    n2.inputs["Scale"].default_value = 2.4 * scale
    n2.inputs["Detail"].default_value = 5.0
    n2.inputs["Roughness"].default_value = 0.60
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    r2 = nt.nodes.new("ShaderNodeValToRGB")
    r2.location = (-500, 40)
    e = r2.color_ramp.elements
    e[0].position = 0.36
    e[0].color = K.c(light)
    e[1].position = 0.70
    e[1].color = K.c(base)
    nt.links.new(n2.outputs["Fac"], r2.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.location = (-240, 200)
    mix.blend_type = "MIX"
    mix.inputs["Fac"].default_value = 0.32
    nt.links.new(r1.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(r2.outputs["Color"], mix.inputs["Color2"])
    # fine grain, breaks the flat per-stone colour without any direction
    n3 = nt.nodes.new("ShaderNodeTexNoise")
    n3.location = (-700, -220)
    n3.inputs["Scale"].default_value = 22.0 * scale
    n3.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], n3.inputs["Vector"])
    r3 = nt.nodes.new("ShaderNodeValToRGB")
    r3.location = (-500, -220)
    e = r3.color_ramp.elements
    e[0].position = 0.34
    e[0].color = K.c("#9d978a")
    e[1].position = 0.68
    e[1].color = K.c("#ffffff")
    nt.links.new(n3.outputs["Fac"], r3.inputs["Fac"])
    mix2 = nt.nodes.new("ShaderNodeMixRGB")
    mix2.location = (0, 120)
    mix2.blend_type = "MULTIPLY"
    mix2.inputs["Fac"].default_value = 0.55
    nt.links.new(mix.outputs["Color"], mix2.inputs["Color1"])
    nt.links.new(r3.outputs["Color"], mix2.inputs["Color2"])
    nt.links.new(mix2.outputs["Color"], b.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.location = (-240, -260)
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.035
    nt.links.new(n3.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def _glass_mat(name, base="#0f1820", rough=0.07, emis="#131e28", estr=0.20):
    """Dark leaded glass: almost black in the body, a broad sky sheen on top.

    The old window glass was `mat_glass`, whose brick-free but still fairly
    rough surface plus a buried backing made every opening read as a flat navy
    decal.  Deep-set dark glass with a mirror finish catches the sky instead,
    and the leaded bars in `pointed_window` give it scale.
    """
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = _bsdf_of(m)
    b.inputs["Base Color"].default_value = K.c(base, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    for key, val in (("IOR", 1.52), ("Specular IOR Level", 0.85)):
        if key in b.inputs:
            b.inputs[key].default_value = val
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = K.c(emis, 1.0)
        b.inputs["Emission Strength"].default_value = estr
    return m


def materials():
    M = {}
    M["stone"] = _stone_mat("stone", base="#7d7466", dark="#544e42",
                            light="#948b7c", scale=1.0)
    M["stone_warm"] = _stone_mat("stone_sand", base="#8d8168", dark="#635b4b",
                                 light="#a1957c", scale=1.15)
    M["stone_dark"] = _stone_mat("stone_dark", base="#5c554a", dark="#3b362d",
                                 light="#6f685a", scale=1.25, rough=0.88)
    M["stone_pale"] = _stone_mat("stone_pale", base="#a49a86", dark="#7b7365",
                                 light="#bcb3a0", scale=1.05)
    # the second tone of a rubble/ashlar face.  It has to differ from
    # stone_warm by a hair, not by a shade: a drum scattered with pale stones at
    # 16 % looked like camouflage paint, which is exactly what the author was
    # trying to avoid.  Real coursing varies by a few percent in value.
    M["stone_alt"] = _stone_mat("stone_sand_b", base="#877c64", dark="#5f5747",
                                light="#9a8e75", scale=1.3)
    M["wood"] = K.mat_wood()
    M["wood_dark"] = K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    M["tile"] = K.mat_tile()
    M["tile_blue"] = K.mat_tile("roof_blue", base="#3f5570", dark="#28374b",
                                light="#55708f")
    M["slate"] = K.mat_tile("roof_slate", base="#4a5560", dark="#333c46",
                            light="#5f6d7a")
    M["glass"] = _glass_mat("glass_window")
    # still water: dark, glassy, with two ripple scales so the sun breaks into
    # glints instead of one flat green facet.  Both noise textures read the
    # object-space coordinate, so the ripples are the same size in metres no
    # matter how big the water prism is (generated space would stretch them).
    wm = K.mat_water("water_moat", "#26382d")
    nt = wm.node_tree
    bsdf = _bsdf_of(wm)
    if bsdf is not None:
        bsdf.inputs["Roughness"].default_value = 0.032
        bsdf.inputs["Emission Strength"].default_value = 0.0
        for key, val in (("IOR", 1.333), ("Specular IOR Level", 0.90)):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-900, -320)
        swell = nt.nodes.new("ShaderNodeTexNoise")
        swell.location = (-700, -260)
        swell.inputs["Scale"].default_value = 0.55
        swell.inputs["Detail"].default_value = 3.0
        swell.inputs["Roughness"].default_value = 0.50
        nt.links.new(tc.outputs["Object"], swell.inputs["Vector"])
        chop = nt.nodes.new("ShaderNodeTexNoise")
        chop.location = (-700, -480)
        chop.inputs["Scale"].default_value = 8.5
        chop.inputs["Detail"].default_value = 4.0
        chop.inputs["Roughness"].default_value = 0.62
        nt.links.new(tc.outputs["Object"], chop.inputs["Vector"])
        b1 = nt.nodes.new("ShaderNodeBump")
        b1.location = (-480, -240)
        b1.inputs["Strength"].default_value = 0.40
        b1.inputs["Distance"].default_value = 0.16
        nt.links.new(swell.outputs["Fac"], b1.inputs["Height"])
        b2 = nt.nodes.new("ShaderNodeBump")
        b2.location = (-260, -340)
        b2.inputs["Strength"].default_value = 0.30
        b2.inputs["Distance"].default_value = 0.014
        nt.links.new(chop.outputs["Fac"], b2.inputs["Height"])
        nt.links.new(b1.outputs["Normal"], b2.inputs["Normal"])
        nt.links.new(b2.outputs["Normal"], bsdf.inputs["Normal"])
    M["water"] = wm
    # the line where water meets stone: a pale mineral scum line on the stone
    # right at the water level, so the moat has a waterline instead of a plane
    # that simply stops
    M["scum"] = _stone_mat("stone_scum", base="#7d7c62", dark="#53543f",
                           light="#93907a", scale=3.2, rough=0.55, bump=0.26)
    M["wet"] = _stone_mat("stone_wet", base="#39443c", dark="#212a24",
                          light="#4b5950", scale=1.6, rough=0.34, bump=0.24)
    # the damp stone of a footing that straddles the waterline: darker and greener
    # than the wall, but matte and mossy instead of a shiny black rubber belt
    M["wet_band"] = _stone_mat("stone_damp", base="#454e43", dark="#2f362d",
                               light="#565f52", scale=2.6, rough=0.90, bump=0.30)
    M["leaf"] = K.mat_earth("leaf", base="#46542f", dark="#2b361d", scale=4.5,
                            patch=0.6)
    # the meadow: three object-space octaves at roughly 18 m, 2.4 m and 0.3 m so
    # the field has broad grazing patches, mid mottling and fine grain.  A single
    # octave at this scale renders as flat green plastic, which is what made the
    # moat bank and the water read as the same surface.
    M["grass"] = _stone_mat("meadow", base="#424d2b", dark="#2b3419",
                            light="#566038", scale=0.15, rough=0.96, bump=0.34)
    # distant hills: paler and bluer, the way aerial perspective washes them out,
    # so they stop looking like green balloons parked behind the castle
    M["hill"] = _stone_mat("hill_far", base="#5e6d5c", dark="#4a5749",
                           light="#72806c", scale=0.07, rough=1.0, bump=0.0)
    M["iron"] = K.mat_metal("iron_cast", base="#4a4a52", rough=0.52)
    M["iron_dark"] = K.mat_metal("iron_black", base="#2a2a30", rough=0.60)
    M["gold"] = K.mat_gold("gold_leaf", base="#c9a227")
    M["plaster"] = K.mat_plaster("plaster_wall", base="#cdc3ad", dirt="#a99d86",
                                 scale=4.0)
    # heraldic fills and flag cloths.  They used to be flat cloth colours, and
    # at 30 m the blue quarters of the coat of arms read as a hole in the wall
    # (or a sky patch): a navy rectangle with zero internal variation.  A little
    # mottling fixes that, but the sheen has to stay cloth-soft -- flags are
    # cloth, so the bump is almost nil and the roughness is high; only the
    # colour noise is wanted here.
    M["banner_red"] = _stone_mat("livery_red", base="#7b2a24", dark="#4f1712",
                                 light="#9c3a30", scale=2.6, rough=0.90, bump=0.045)
    M["banner_blue"] = _stone_mat("livery_blue", base="#2a3d61", dark="#18253f",
                                  light="#3d5484", scale=2.6, rough=0.90, bump=0.045)
    M["flag"] = K.mat_cloth("flag_cloth", "#8b2e27", rough=0.90)
    # Paving is object-space stone like everything else now: the kit cobble is
    # UV/brick driven and, worse, fairly glossy -- on the 3.3 m discs that are
    # the barbican tower decks a specular sheen in the middle of a round plate
    # still reads as standing water from above, which is exactly the complaint
    # this whole pass is supposed to kill.
    M["cobble"] = _stone_mat("cobble_pave", base="#87806f", dark="#5c5649",
                             light="#a09784", scale=2.4, rough=0.94, bump=0.30)
    M["glow"] = _glow("torch_glow", "#ffb257", "#ff9a3c", 12.0)
    M["lamp"] = _glow("lamp_glow", "#ffe0a8", "#ffd27a", 4.0)
    return M


def make_materials():
    """Palette factory for the capital integrator: every key used by build()."""
    return materials()


MAT_KEYS = ("stone", "stone_warm", "stone_dark", "stone_pale", "wood", "wood_dark",
            "tile", "tile_blue", "slate", "glass", "iron", "iron_dark", "gold",
            "plaster", "banner_red", "banner_blue", "flag", "cobble", "water",
            "wet", "leaf", "grass", "glow", "lamp")


def _palette(MAT):
    """Fill in any key the caller's palette is missing, never override one it has."""
    if not MAT:
        return materials()
    out = materials()
    out.update(dict(MAT))
    return out


# --------------------------------------------------------------------------
#  low level mesh helpers
# --------------------------------------------------------------------------
def _blk(v, f, x0, x1, y0, y1, z0, z1):
    i = len(v)
    v.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    f.extend([(i, i + 3, i + 2, i + 1), (i + 4, i + 5, i + 6, i + 7),
              (i, i + 1, i + 5, i + 4), (i + 1, i + 2, i + 6, i + 5),
              (i + 2, i + 3, i + 7, i + 6), (i + 3, i, i + 4, i + 7)])


def _mk(name, verts, faces, mat, T=None, smooth=False):
    if T is not None:
        verts = [T @ Vector(v) for v in verts]
    ob = K.mesh_obj(name, [tuple(v) for v in verts], faces, smooth=smooth)
    if mat is not None:
        K.assign(ob, mat)
    return ob


ASH_BW = 0.80            # ashlar block width  (a legible ~0.8 m reading stone)
ASH_BH = 0.36            # ashlar course height
ASH_COURSE = 0.38        # course height on drums


def ashlar(name, T, w, h, mat, rng, bw=ASH_BW, bh=ASH_BH, gap=0.018, proud=0.022,
           z0=0.0, y_in=-0.05):
    """Proud dressed stones over a w x h face lying in the local XZ plane.

    Local +Y is the outward normal; stones stand `proud` out of the wall and
    the joints between them show the (darker) wall behind.  One mesh object.
    """
    v, f = [], []
    z = 0.0
    row = 0
    while z < h - 0.06:
        hh = min(bh, h - z)
        x = -w * 0.5 - (bw * 0.45 if row % 2 else 0.0) - rng.uniform(0.0, 0.3)
        while x < w * 0.5 - 0.05:
            ww = bw * rng.uniform(0.78, 1.28)
            a = max(x, -w * 0.5)
            b = min(x + ww, w * 0.5)
            if b - a > 0.16:
                pr = proud * rng.uniform(0.75, 1.15)
                _blk(v, f, a + gap * 0.5, b - gap * 0.5, y_in, pr,
                     z0 + z + gap * 0.5, z0 + z + hh - gap * 0.5)
            x += ww
        z += hh
        row += 1
    return [_mk(name, v, f, mat, T)]


def ring_stones(name, T, r, z, n, h, mat_a, mat_b, rng, thick=0.055, gap=0.028,
                a0=0.0, a1=TAU, skip=None, b_frac=0.16):
    """One course of proud stones around a cylinder -> two mesh objects.

    `skip` is a list of (ang_lo, ang_hi, z_lo, z_hi) boxes (radians / metres):
    stones overlapping one of them are left out, so the courses stop dead at a
    window reveal instead of floating across it (a boolean on this many shells
    is unreliable, omission is exact).

    `b_frac` is the share of stones handed to the second material.  It used to
    be a strict checkerboard, which put a pale stone next to a dark one on every
    single joint and turned a drum into camouflage; a sparse scatter (roughly
    one stone in six, and never two neighbours) lets the coursing read instead.
    """
    va, fa, vb, fb = [], [], [], []
    seg = (a1 - a0) / n
    last_b = False
    # stagger alternate courses by half a stone so the vertical joints do not
    # line up into continuous seams down the drum
    ph = gap * 0.5 / r + (seg * 0.5 if int(round(z / max(h, 1e-4))) % 2 else 0.0)
    for i in range(n):
        off = ph + rng.uniform(-0.002, 0.002)
        s0 = a0 + i * seg + off
        s1 = a0 + (i + 1) * seg - gap * 0.5 / r + off
        zz = z + rng.uniform(-0.004, 0.004)
        if skip:
            hit = False
            for (al, ah, zl, zh) in skip:
                if zz + h > zl and zz < zh and s1 > al and s0 < ah:
                    hit = True
                    break
            if hit:
                continue
        th = thick * rng.uniform(0.92, 1.08)
        vv = []
        for (rr, aa) in ((r, s0), (r + th, s0), (r + th, s1), (r, s1)):
            for zs in (zz, zz + h):
                vv.append((math.cos(aa) * rr, math.sin(aa) * rr, zs))
        vv = [T @ Vector(p) for p in vv]
        take_b = (rng.random() < b_frac) and not last_b
        last_b = take_b
        if take_b:
            base = len(vb)
            vb.extend(vv)
            fb.extend([(base + 1, base + 2, base + 6, base + 5),
                       (base + 0, base + 4, base + 7, base + 3),
                       (base + 0, base + 1, base + 5, base + 4),
                       (base + 3, base + 7, base + 6, base + 2),
                       (base + 4, base + 5, base + 6, base + 7),
                       (base + 0, base + 3, base + 2, base + 1)])
        else:
            base = len(va)
            va.extend(vv)
            fa.extend([(base + 1, base + 2, base + 6, base + 5),
                       (base + 0, base + 4, base + 7, base + 3),
                       (base + 0, base + 1, base + 5, base + 4),
                       (base + 3, base + 7, base + 6, base + 2),
                       (base + 4, base + 5, base + 6, base + 7),
                       (base + 0, base + 3, base + 2, base + 1)])
    out = []
    if fa:
        out.append(_mk(name + "_a", va, fa, mat_a))
    if fb:
        out.append(_mk(name + "_b", vb, fb, mat_b))
    return out


def ring_wall(name, T, r_in, r_out, z0, z1, mat, seg=64, batter=0.0):
    """Solid annulus wall (outer, inner, top, bottom).  `batter` widens the top."""
    prof = [(r_in, z0), (r_out, z0), (r_out + batter, z1), (r_in, z1)]
    return H.lathe(name, prof, mat, seg=seg, T=T, close_bottom=False, close_top=False)


def arch_tube(name, T, r, zc, y0, y1, thick, mat, seg=26, a0=0.0, a1=PI):
    """Solid half-tube: an arch soffit of radius r centred on (0, zc) in local XZ,
    extruded along local Y from y0 to y1."""
    v, f = [], []
    n = seg + 1
    for y in (y0, y1):
        for i in range(n):
            a = lerp(a0, a1, i / seg)
            v.append((math.cos(a) * r, y, zc + math.sin(a) * r))
    for y in (y0, y1):
        for i in range(n):
            a = lerp(a0, a1, i / seg)
            v.append((math.cos(a) * (r + thick), y, zc + math.sin(a) * (r + thick)))
    base = 2 * n
    for i in range(seg):
        f.append((i, i + 1, n + i + 1, n + i))                       # inner
        f.append((base + i, base + n + i, base + n + i + 1, base + i + 1))  # outer
    for o in (0, n):
        for i in range(seg):
            f.append((o + i, base + o + i, base + o + i + 1, o + i + 1))
    return _mk(name, v, f, mat, T)


def arch_notch_poly(w, h, r, zs, seg=26):
    """Rectangle with a round-headed doorway bitten out of the bottom centre."""
    pts = [(w, 0.0), (w, h), (-w, h), (-w, 0.0), (-r, 0.0), (-r, zs)]
    for i in range(1, seg):
        a = PI - PI * i / seg
        pts.append((math.cos(a) * r, zs + math.sin(a) * r))
    pts += [(r, zs), (r, 0.0)]
    return pts


def bridge_notch_poly(y0, y1, ztop, zbot, r, zc, half_span, seg=22):
    """Bridge body: a slab with a segmental arch bitten out of its underside."""
    a_spring = math.asin(max(-1.0, min(1.0, (zbot - zc) / r)))
    pts = [(y1, ztop), (y0, ztop), (y0, zbot)]
    for i in range(seg + 1):
        a = lerp(PI - a_spring, a_spring, i / seg)
        pts.append((math.cos(a) * r, zc + math.sin(a) * r))
    pts.append((y1, zbot))
    return pts


def arch_band(name, T, r_in, r_out, y0, y1, mat, seg=28, a0=0.0, a1=PI, zc=0.0):
    """Solid half-annulus band in the local XZ plane, extruded along Y.

    Used behind arch orders so the joints between voussoirs show stone, not
    the black inside of the vault tube."""
    pts = []
    for i in range(seg + 1):
        a = lerp(a0, a1, i / seg)
        pts.append((math.cos(a) * r_out, zc + math.sin(a) * r_out))
    for i in range(seg + 1):
        a = lerp(a1, a0, i / seg)
        pts.append((math.cos(a) * r_in, zc + math.sin(a) * r_in))
    return H.prism(name, T @ Ts(0, (y0 + y1) * 0.5, 0), pts, abs(y1 - y0), mat, axis="y")


def voussoir_ring(name, T, r_in, depth_ring, n, mat, y=0.0, zc=0.0,
                  a0=0.0, a1=PI, thick=0.10, gap=0.0):
    """Radial arch stones around a half circle in the local XZ plane."""
    v, f = [], []
    g = (gap / max(r_in, 0.2)) * 0.5
    for i in range(n):
        aa = lerp(a0, a1, i / n) + g
        ab = lerp(a0, a1, (i + 1) / n) - g
        rr = r_in
        for (ang, rad) in ((aa, rr), (aa, rr + depth_ring), (ab, rr + depth_ring), (ab, rr)):
            for yy in (-thick * 0.5, thick * 0.5):
                v.append((math.cos(ang) * rad, y + yy, zc + math.sin(ang) * rad))
    for i in range(n):
        b = i * 8
        f.extend([(b + 0, b + 1, b + 5, b + 4),
                  (b + 2, b + 6, b + 7, b + 3),
                  (b + 0, b + 4, b + 6, b + 2),
                  (b + 1, b + 3, b + 7, b + 5),
                  (b + 4, b + 5, b + 7, b + 6),
                  (b + 0, b + 2, b + 3, b + 1)])
    return _mk(name, v, f, mat, T)


def radial_T(x0, y0, z0, ang, r, y=0.0, zc=0.0):
    """Matrix whose local X is radial and local Z tangential, at angle `ang`."""
    ca, sa = math.cos(ang), math.sin(ang)
    R = Matrix(((ca, 0.0, -sa, 0.0), (0.0, 1.0, 0.0, 0.0),
                (sa, 0.0, ca, 0.0), (0.0, 0.0, 0.0, 1.0)))
    return Ts(x0 + ca * r, y0 + y, z0 + zc + sa * r) @ R


def face_T(x0, y0, z0, ang, r, lift=0.0):
    """Matrix whose local +Y points outward at angle `ang` on a drum."""
    return Ts(x0 + math.cos(ang) * (r + lift), y0 + math.sin(ang) * (r + lift), z0) \
        @ RotZ(ang - PI * 0.5)


def rcrenel(name, T, r, z, n, merlon=1.05, gap=0.55, h=1.25, depth=0.62,
            mat=None, a0=0.0, a1=TAU):
    """Battlement merlons around a circle as real rectangular blocks (one mesh)."""
    v, f = [], []
    step = (a1 - a0) / n
    for i in range(n):
        a = a0 + step * (i + 0.5)
        ca, sa = math.cos(a), math.sin(a)
        ux, uy = ca, sa          # radial
        tx, ty = -sa, ca         # tangential
        rr = r - depth * 0.5
        cx, cy = ux * rr, uy * rr
        hw, hd = merlon * 0.5, depth * 0.5
        b = len(v)
        # bottom four first, then the top four: the face list below assumes that
        # layout.  Emitting them interleaved by z (as this loop used to) makes
        # every side face a self-intersecting bow-tie, which is why every
        # battlement in the scene read as a criss-cross "X" block.
        for zz in (z, z + h):
            for (dt, du) in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
                v.append((cx + tx * dt + ux * du, cy + ty * dt + uy * du, zz))
        f.extend([(b + 0, b + 1, b + 2, b + 3),          # underside, -z
                  (b + 7, b + 6, b + 5, b + 4)])         # top, +z
        # the four sides, wound outward for the clockwise ring order above
        for k in range(4):
            j = (k + 1) % 4
            f.append((b + j, b + k, b + 4 + k, b + 4 + j))
    if not f:
        return []
    return [_mk(name, v, f, mat, T)]


def corbel_ring(name, T, r, z, n, mat, out=1.45, h=1.2, w=0.44, a0=0.0, a1=TAU,
                taper=0.35):
    """Ring of tapered corbels carrying a machicolation gallery (one mesh)."""
    v, f = [], []
    step = TAU / n
    for i in range(n):
        a = a0 + step * (i + 0.5)
        if a > a1:
            continue
        for (aa, rr) in ((a - w * 0.5 / r, r - 0.05), (a - w * 0.5 / r, r + out),
                         (a + w * 0.5 / r, r + out), (a + w * 0.5 / r, r - 0.05)):
            v.append((math.cos(aa) * rr, math.sin(aa) * rr, z))
        for (aa, rr) in ((a - w * 0.5 / r, r - 0.05), (a - w * 0.5 / r, r + out * taper),
                         (a + w * 0.5 / r, r + out * taper), (a + w * 0.5 / r, r - 0.05)):
            v.append((math.cos(aa) * rr, math.sin(aa) * rr, z + h))
        b = len(v) - 8
        f.extend([(b + 0, b + 1, b + 2, b + 3),          # underside, -z
                  (b + 7, b + 6, b + 5, b + 4)])         # top, +z
        # the four sides, wound outward for the clockwise ring order above
        for k in range(4):
            j = (k + 1) % 4
            f.append((b + j, b + k, b + 4 + k, b + 4 + j))
    if not f:
        return []
    return [_mk(name, v, f, mat, T)]


def torus(name, T, R, r, mat, seg=10, ring=5):
    v, f = [], []
    for i in range(seg):
        a = TAU * i / seg
        for j in range(ring):
            b = TAU * j / ring
            v.append(((R + r * math.cos(b)) * math.cos(a),
                      (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(ring):
            a0 = i * ring + j
            a1 = i * ring + (j + 1) % ring
            b0 = ((i + 1) % seg) * ring + j
            b1 = ((i + 1) % seg) * ring + (j + 1) % ring
            f.append((a0, b0, b1, a1))
    return _mk(name, v, f, mat, T, smooth=True)


def chain(name, p0, p1, sag, mat, links=11, R=0.075, r=0.026, up=Vector((0, 0, 1))):
    """A sagging chain of interlocking torus links between two points.

    `links` is a floor: the links are packed at roughly one outer link diameter
    apart so the result reads as a chain rather than a dotted line, whatever
    the span.
    """
    p0, p1 = Vector(p0), Vector(p1)
    out = []
    span = (p1 - p0).length + sag * 0.6
    links = max(int(links), int(round(span / (0.95 * 2.0 * (R + r)))), 3)

    def at(t):
        p = p0.lerp(p1, t)
        p.z -= sag * math.sin(PI * t)
        return p

    for i in range(links):
        t = (i + 0.5) / links
        p = at(t)
        d = (at(min(1.0, t + 0.02)) - at(max(0.0, t - 0.02)))
        if d.length < 1e-6:
            d = (p1 - p0)
        d.normalize()
        n1 = d.cross(up)
        if n1.length < 1e-4:
            n1 = d.cross(Vector((1.0, 0.0, 0.0)))
        n1.normalize()
        n2 = d.cross(n1).normalized()
        zax = n1 if i % 2 == 0 else n2
        xax = d
        yax = zax.cross(xax).normalized()
        T = basis_T(xax, yax, zax, p)
        out.append(torus(name + "_l%d" % i, T, R, r, mat, seg=8, ring=4))
    return out


def slit(name, T, h, mat, dark, w=0.30, sh=0.46):
    """Arrow loop: a dark slot sunk in a proud dressed surround."""
    p = [box(name + "_s", T @ Ts(0, 0.045, h * 0.5), (w, 0.10, h + 0.20), mat, bev=0.012),
         box(name + "_d", T @ Ts(0, 0.10, h * 0.5), (w * 0.42, 0.04, h), dark)]
    p.append(box(name + "_l", T @ Ts(0, 0.10, h * 0.5 + h * 0.18), (w * 0.16, 0.05, sh * 0.6), dark))
    return p


def flagstones(name, T, w, y0, y1, mat, rng, cw=1.15, cl=0.85, gap=0.03, h=0.12,
               rough=0.012, y_axis=True):
    """Coursed flagstone paving in the local XY plane, top at z=0 (one mesh)."""
    v, f = [], []
    y = y0
    row = 0
    while y < y1 - 0.05:
        ll = min(cl, y1 - y)
        x = -w * 0.5 - (cw * 0.5 if row % 2 else 0.0) - rng.uniform(0, 0.2)
        while x < w * 0.5 - 0.05:
            ww = cw * rng.uniform(0.75, 1.3)
            a = max(x, -w * 0.5)
            b = min(x + ww, w * 0.5)
            if b - a > 0.12:
                zz = -h + rng.uniform(-rough, rough)
                _blk(v, f, a + gap * 0.5, b - gap * 0.5, y + gap * 0.5, y + ll - gap * 0.5,
                     zz, 0.0)
            x += ww
        y += ll
        row += 1
    return [_mk(name, v, f, mat, T)]


def crenel_line(name, T, length, mat, merlon=1.0, gap=0.55, h=1.25, depth=0.62,
                z=0.0, axis="x"):
    """Straight battlement row (one mesh)."""
    v, f = [], []
    pitch = merlon + gap
    n = max(1, int(length / pitch))
    total = n * pitch - gap
    x0 = -total * 0.5 + merlon * 0.5
    for i in range(n):
        x = x0 + i * pitch
        if axis == "x":
            _blk(v, f, x - merlon * 0.5, x + merlon * 0.5, -depth * 0.5, depth * 0.5, z, z + h)
        else:
            _blk(v, f, -depth * 0.5, depth * 0.5, x - merlon * 0.5, x + merlon * 0.5, z, z + h)
    return [_mk(name, v, f, mat, T)]


# --------------------------------------------------------------------------
#  ornament
# --------------------------------------------------------------------------
def coat_of_arms(name, T, r, MAT):
    """Carved heraldic roundel in relief (local +Y is out of the wall)."""
    p = []
    sw, pale, blue, gold = MAT["stone_warm"], MAT["stone_pale"], MAT["banner_blue"], MAT["gold"]
    # moulded stone frame (lathe, axis turned to +Y)
    prof = [(r * 1.02, -0.05), (r * 1.21, -0.05), (r * 1.21, 0.09), (r * 1.13, 0.19),
            (r * 1.02, 0.19), (r * 1.02, 0.11), (r * 1.09, 0.09), (r * 1.09, 0.01),
            (r * 1.02, 0.01)]
    p.append(H.lathe(name + "_fr", prof, sw, seg=44, T=T @ RotX(-PI * 0.5),
                     close_bottom=False, close_top=False))
    # recessed field
    p.append(cyl(name + "_fd", T @ Ts(0, 0.05, 0) @ RotX(PI * 0.5), r * 1.02, 0.14, pale, seg=44))
    # four quarters, blue on the diagonals
    for i in range(4):
        a0 = i * PI * 0.5 + 0.02
        a1 = a0 + PI * 0.5 - 0.04
        pts = [(0.0, 0.0)]
        for k in range(9):
            a = lerp(a0, a1, k / 8.0)
            pts.append((math.cos(a) * r * 0.99, math.sin(a) * r * 0.99))
        p.append(H.prism(name + "_q%d" % i, T @ Ts(0, 0.13, 0), pts, 0.08,
                         blue if i % 2 == 0 else pale, axis="y"))
    # raised cross over the quarters
    p.append(box(name + "_cx", T @ Ts(0, 0.18, 0), (r * 1.98, 0.07, 0.26), sw, bev=0.012))
    p.append(box(name + "_cz", T @ Ts(0, 0.18, 0), (0.26, 0.07, r * 1.98), sw, bev=0.012))
    p.append(cyl(name + "_hub", T @ Ts(0, 0.23, 0) @ RotX(PI * 0.5), 0.23, 0.09, gold, seg=18))
    # crown resting on the frame
    cz = r * 1.23
    p.append(torus(name + "_crb", T @ Ts(0, 0.10, cz) @ RotX(PI * 0.5), 0.29, 0.065, gold,
                   seg=18, ring=5))
    for i in range(3):
        a = -0.62 + 0.62 * i
        p.append(cone(name + "_crp%d" % i, T @ Ts(math.sin(a) * 0.30, 0.10, cz + 0.30),
                      0.085, 0.26, gold, seg=6))
        p.append(sphere(name + "_crj%d" % i, T @ Ts(math.sin(a) * 0.30, 0.10, cz + 0.46),
                        0.052, gold, seg=8, ring=5))
    return p


def wall_banner(name, T, w, h, cloth, gold, iron):
    """Vertical banner hanging flat on a wall; T origin at the top centre."""
    p = []
    p.append(cyl(name + "_rod", T @ Ts(0, 0.19, 0) @ RotY(PI * 0.5), 0.05, w + 0.62, iron, seg=10))
    for s in (-1, 1):
        p.append(sphere(name + "_fin%d" % s, T @ Ts(s * (w * 0.5 + 0.34), 0.19, 0), 0.10,
                        gold, seg=10, ring=6))
        p.append(box(name + "_brk%d" % s, T @ Ts(s * w * 0.34, 0.10, 0.02), (0.10, 0.22, 0.12), iron))
    pts = [(-w * 0.5, 0.0), (w * 0.5, 0.0), (w * 0.5, -h), (0.0, -h * 0.80), (-w * 0.5, -h)]
    p.append(H.prism(name + "_cl", T @ Ts(0, 0.13, 0), pts, 0.05, cloth, axis="y"))
    for s in (-1, 1):
        p.append(box(name + "_bd%d" % s, T @ Ts(s * (w * 0.5 - 0.07), 0.155, -h * 0.5),
                     (0.13, 0.02, h * 0.98), gold))
    p.append(box(name + "_bdt", T @ Ts(0, 0.155, -0.07), (w, 0.02, 0.14), gold))
    p.append(cyl(name + "_em", T @ Ts(0, 0.165, -h * 0.46) @ RotX(PI * 0.5), w * 0.27, 0.03,
                 gold, seg=22))
    p.append(cyl(name + "_em2", T @ Ts(0, 0.175, -h * 0.46) @ RotX(PI * 0.5), w * 0.13, 0.03,
                 cloth, seg=18))
    for i in range(3):
        p.append(box(name + "_emb%d" % i, T @ Ts(0, 0.17, -h * 0.70 - i * 0.18),
                     (w * 0.46 - i * 0.06, 0.02, 0.09), gold))
    for i in range(5):
        x = -w * 0.5 + w * (i + 0.5) / 5.0
        p.append(torus(name + "_rg%d" % i, T @ Ts(x, 0.19, -0.02) @ RotY(PI * 0.5), 0.045, 0.012,
                       iron, seg=8, ring=4))
    return p


def _banner(name, T, x0, w, h, z_top, y_off, mat, seg=8, amp=0.075, droop=0.10):
    """One cloth panel hanging to +X off a mast, built as a rippled sheet.

    A flat box for a banner reads as a placard nailed to the pole at any normal
    viewing distance; half a wavelength of ripple plus a droop on the fly edge
    makes it read as cloth even in a 1400 px frame.
    """
    v, f = [], []
    for i in range(seg + 1):
        u = i / seg
        x = x0 + w * u
        sag = droop * u * u
        wy = y_off + amp * math.sin(PI * 1.15 * u)
        for j in range(3):
            vv = j / 2.0
            v.append((x, wy * (0.55 + 0.45 * vv), z_top - sag - h * vv))
    for i in range(seg):
        for j in range(2):
            a = i * 3 + j
            f.append((a, a + 3, a + 4, a + 1))
    return _mk(name, v, f, mat, T)


def flag(name, T, pole_h, w, h, cloth, gold, iron):
    """Vertical flagpole with a heraldic banner flying to +X."""
    p = [cyl(name + "_pole", T @ Ts(0, 0, pole_h * 0.5), 0.075, pole_h, iron, seg=10),
         sphere(name + "_knob", T @ Ts(0, 0, pole_h + 0.10), 0.13, gold, seg=10, ring=6),
         cyl(name + "_base", T @ Ts(0, 0, 0.16), 0.26, 0.32, iron, seg=12)]
    z0 = pole_h - 0.14
    p.append(_banner(name + "_cl", T, 0.06, w, h, z0, 0.0, cloth))
    p.append(_banner(name + "_bd", T, 0.075, w * 0.95, h * 0.905, z0 - h * 0.045,
                     0.030, gold))
    p.append(_banner(name + "_bd2", T, 0.090, w * 0.62, h * 0.500, z0 - h * 0.245,
                     0.040, cloth))
    return p


def guardian(name, T, h, MAT, spear=True):
    """Guardian figure for a niche: plinth, robe, mail, helm, spear, shield."""
    st = MAT["stone_warm"]
    p = []
    p.append(cyl(name + "_base", T @ Ts(0, 0, 0.12), 0.46, 0.24, st, seg=14))
    p.append(H.lathe(name + "_robe", [(0.40, 0.24), (0.33, h * 0.42), (0.30, h * 0.52),
                                      (0.26, h * 0.60)], st, seg=14, T=T,
                     close_bottom=False, close_top=False))
    p.append(H.lathe(name + "_mail", [(0.29, h * 0.55), (0.31, h * 0.66), (0.25, h * 0.74)],
                     st, seg=14, T=T, close_bottom=False, close_top=False))
    p.append(sphere(name + "_hd", T @ Ts(0, 0, h * 0.80), 0.155, st, seg=14, ring=9))
    p.append(H.lathe(name + "_helm", [(0.19, h * 0.80), (0.17, h * 0.87), (0.05, h * 0.90)],
                     st, seg=12, T=T, close_bottom=False, close_top=True))
    p.append(box(name + "_nas", T @ Ts(0, 0.15, h * 0.80), (0.05, 0.06, 0.16), st))
    for s in (-1, 1):
        p.append(box(name + "_arm%d" % s, T @ Ts(s * 0.30, 0.02, h * 0.64, ry=s * 0.12),
                     (0.11, 0.12, 0.42), st, bev=0.01))
        p.append(box(name + "_leg%d" % s, T @ Ts(s * 0.13, 0.02, 0.20), (0.14, 0.16, 0.34), st))
    # cloak
    p.append(H.prism(name + "_clk", T @ Ts(0, -0.12, 0),
                     [(-0.30, 0.24), (0.30, 0.24), (0.26, h * 0.66), (0.0, h * 0.72),
                      (-0.26, h * 0.66)], 0.09, st, axis="y"))
    if spear:
        p.append(cyl(name + "_sp", T @ Ts(0.40, 0.10, h * 0.46), 0.032, h * 0.98, st, seg=8))
        p.append(cone(name + "_tip", T @ Ts(0.40, 0.10, h * 0.97), 0.06, 0.26, st, seg=6))
    # shield
    p.append(H.prism(name + "_shd", T @ Ts(-0.34, 0.20, h * 0.52),
                     [(-0.24, 0.28), (0.24, 0.28), (0.24, -0.10), (0.0, -0.34), (-0.24, -0.10)],
                     0.10, st, axis="y"))
    return p


def niche(name, T, w, h, MAT, rng):
    """Projecting statue aedicule on a wall face (local +Y out, y=0 at the face).

    Everything sits at y >= 0 so it never fights the proud ashlar behind it.
    """
    st, sd = MAT["stone_warm"], MAT["stone_dark"]
    p = []
    p.append(box(name + "_back", T @ Ts(0, 0.07, h * 0.5), (w, 0.14, h), sd))
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + 0.15), 0.17, h * 0.5 + 0.05),
                     (0.30, 0.34, h + 0.30), st, bev=0.015))
    p.append(box(name + "_lin", T @ Ts(0, 0.20, h + 0.16), (w + 0.9, 0.16, 0.26), st, bev=0.02))
    p.append(voussoir_ring(name + "_arch", T @ Ts(0, 0.26, 0), w * 0.5, 0.24, 9, st,
                           y=0.0, zc=h, thick=0.34))
    p.append(box(name + "_hood", T @ Ts(0, 0.26, h + w * 0.5 + 0.34), (w + 1.0, 0.42, 0.22),
                 st, bev=0.02))
    for s in (-1, 1):
        p.append(box(name + "_cor%d" % s, T @ Ts(s * (w * 0.5 + 0.10), 0.24, 0.18),
                     (0.42, 0.46, 0.36), st, bev=0.025))
        p.append(cone(name + "_cod%d" % s, T @ Ts(s * (w * 0.5 + 0.10), 0.24, 0.02) @ RotX(PI),
                      0.26, 0.36, st, seg=4))
    p.append(box(name + "_sill", T @ Ts(0, 0.24, 0.36), (w + 0.56, 0.50, 0.18), st, bev=0.025))
    return p


def machic_line(name, T, length, MAT, n=None, out=1.0, wall_z=0.0, walk=0.42):
    """Corbelled machicolation gallery running along local X (one or few meshes).

    T is at the wall face, z=wall_z is the walk level.  Returns corbels, the
    overhanging floor, the parapet with a batter and the merlons.
    """
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    p = []
    v, f = [], []
    if n is None:
        n = max(2, int(length / 0.95))
    pitch = length / n
    for i in range(n):
        x = -length * 0.5 + pitch * (i + 0.5)
        w = min(pitch * 0.52, 0.42)
        _blk(v, f, x - w * 0.5, x + w * 0.5, -0.10, out * 0.86, wall_z - 1.55, wall_z - 0.30)
        _blk(v, f, x - w * 0.62, x + w * 0.62, -0.10, out, wall_z - 0.44, wall_z - 0.22)
    p.append(_mk(name + "_corb", v, f, sw, T))
    # overhanging floor slab
    p.append(box(name + "_gal", T @ Ts(0, (out - 0.55) * 0.5, wall_z - 0.10),
                 (length, out + 0.55, 0.34), pale, bev=0.02))
    # parapet with a batter (a trapezoid prism along X)
    pp = [(-0.52, 0.0), (out + 0.16, 0.0), (out - 0.02, 1.02), (-0.52, 1.02)]
    p.append(H.prism(name + "_par", T @ Ts(0, 0, wall_z + 0.07), pp, length, sw, axis="x"))
    p.append(box(name + "_cap", T @ Ts(0, (out - 0.36) * 0.5, wall_z + 1.09),
                 (length, out + 0.68, 0.13), pale, bev=0.015))
    p += crenel_line(name + "_mer", T @ Ts(0, out - 0.15, wall_z + 1.20), length - 0.2,
                     MAT["stone"], merlon=0.96, gap=0.50, h=1.20, depth=0.62)
    return p


# --------------------------------------------------------------------------
#  pointed windows (local primitive: H.window_arched hides its own glass)
# --------------------------------------------------------------------------
def pointed_loop(w, h, seg=10, k=0.30):
    """Opening outline (x, z) of a two-centred pointed arch: jambs + head."""
    hw = w * 0.5
    c = w * k
    R = hw + c
    hz = math.sqrt(max(R * R - c * c, 1e-6))
    aL = math.atan2(hz, -c)
    aR = math.atan2(hz, c)
    pts = [(-hw, 0.0), (-hw, h)]
    for i in range(1, seg + 1):
        a = PI + (aL - PI) * i / seg
        pts.append((c + R * math.cos(a), h + R * math.sin(a)))
    for i in range(1, seg + 1):
        a = aR * (1.0 - i / seg)
        pts.append((-c + R * math.cos(a), h + R * math.sin(a)))
    pts.append((hw, 0.0))
    return pts


def _tube(name, T, loop, y0, y1, mat):
    """Open tube: a closed 2D loop (x, z) swept along local Y (window reveal)."""
    n = len(loop)
    v, f = [], []
    for (x, z) in loop:
        v.append((x, y0, z))
        v.append((x, y1, z))
    for i in range(n):
        j = (i + 1) % n
        f.append((i * 2, j * 2, j * 2 + 1, i * 2 + 1))
    return _mk(name, v, f, mat, T)


def pointed_band(name, T, w, h, thick, y0, y1, mat, seg=10, k=0.30):
    """A moulded band following a pointed arch (architrave / hood mould)."""
    inner = pointed_loop(w, h, seg=seg, k=k)
    hw = w * 0.5
    c = w * k
    R = hw + c
    hz = math.sqrt(max(R * R - c * c, 1e-6))
    aL = math.atan2(hz, -c)
    aR = math.atan2(hz, c)
    Ro = R + thick
    outer = [(-hw - thick, h)]
    for i in range(1, seg + 1):
        a = PI + (aL - PI) * i / seg
        outer.append((c + Ro * math.cos(a), h + Ro * math.sin(a)))
    for i in range(1, seg + 1):
        a = aR * (1.0 - i / seg)
        outer.append((-c + Ro * math.cos(a), h + Ro * math.sin(a)))
    outer.append((hw + thick, h))
    pts = list(outer) + [(x, z) for (x, z) in reversed(inner[1:-1])]
    return H.prism(name, T @ Ts(0, (y0 + y1) * 0.5, 0), pts, y1 - y0, mat, axis="y")


def gothic_window(name, T, w, h, MAT, tracery=2, transom=0, hood=True, depth=0.46,
                  dark=None, glass=None, sill=True, seg=10, k=0.30):
    """Recessed pointed window: reveal, glass, mullions, architrave, hood.

    T sits at the SILL centre, local +Y points out of the wall.
    Total height = h + sqrt((w/2 + w*k)^2 - (w*k)^2).
    """
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    dk = dark or MAT["stone_dark"]
    gl = glass or MAT["glass"]
    hw = w * 0.5
    loop = pointed_loop(w, h, seg=seg, k=k)
    # the wall skin (ashlar) stands up to 0.05 proud of the wall plane, so the
    # whole window assembly is built proud of that skin: glazed panel first,
    # then the architrave, then the hood.  Works on any solid wall.
    fr = 0.115
    dep = max(0.22, depth)
    p = []
    p.append(_tube(name + "_rev", T, loop, fr, fr - dep, dk))
    p.append(H.prism(name + "_bk", T @ Ts(0, fr - dep, 0), loop, 0.05, dk, axis="y"))
    p.append(H.prism(name + "_gl", T @ Ts(0, fr - 0.035, 0), loop, 0.05, gl, axis="y"))
    n = max(1, int(tracery))
    for i in range(1, n):
        x = -hw + w * i / n
        p.append(box(name + "_m%d" % i, T @ Ts(x, fr + 0.045, h * 0.5),
                     (0.10, 0.13, h), pale, bev=0.01))
    for i in range(int(transom)):
        z = h * (0.40 + 0.30 * i)
        p.append(box(name + "_t%d" % i, T @ Ts(0, fr + 0.045, z),
                     (w, 0.13, 0.10), pale, bev=0.01))
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.15), 0.13, h * 0.5),
                     (0.30, 0.22, h + 0.02), sw, bev=0.015))
    p.append(pointed_band(name + "_ar", T, w, h, 0.30, 0.10, 0.24, sw, seg=seg, k=k))
    if sill:
        p.append(box(name + "_sl", T @ Ts(0, 0.17, -0.12), (w + 0.80, 0.40, 0.18), pale,
                     bev=0.02))
        p.append(box(name + "_sd", T @ Ts(0, 0.26, -0.24), (w + 0.58, 0.16, 0.06), dk))
    if hood:
        p.append(pointed_band(name + "_hd", T, w + 0.56, h, 0.36, 0.20, 0.40, pale,
                              seg=seg, k=k))
        for s in (-1, 1):
            p.append(box(name + "_hs%d" % s, T @ Ts(s * (hw + 0.46), 0.30, h - 0.16),
                         (0.30, 0.30, 0.34), pale, bev=0.02))
    return p


# ==========================================================================
#  PART 2 -- rebuilt gate complex
#
#  Layout (local frame, +Y = out of the city):
#
#      y = +52 .. +31.4   road, moat far bank
#      y = +31 .. +23     MOAT (8 m), timber DRAWBRIDGE on the axis
#      y = +23 .. +9.4    BARBICAN WARD: front wall + 2 towers at y=23,
#                         side walls at x=+-8.3, the porch at the back
#      y = +9.25 .. -6.6  the gatehouse + forebuilding (the main gate)
#      y = -6.6 .. -46    city street
#
#  Every walking surface (city street, passage, ward, drawbridge, road) is at
#  the same level, z = +0.12, so no ramp, step or seam is needed anywhere.
# ==========================================================================

RO = R_PASS + 0.10          # real opening radius of the gate passage (2.85)
ZC = Z_SPRING + RO          # 7.10 crown
DECK = 0.12                 # the one walking level of the whole complex
CITY_Z = 0.06               # city street surface (a 6 cm threshold step)
BARB_FRONT = 23.0           # outer face of the barbican front wall
BARB_BACK = 9.40            # inner face of the barbican side walls
BARB_Z = 10.60              # barbican wall-walk level
BARB_T = 1.70               # barbican wall thickness
BARB_X = 8.30               # barbican wall centre line
BTOW_R = 3.30               # barbican tower radius
BTOW_TOP = 12.60            # barbican tower shaft top
MOAT_A = 23.00              # near edge of the moat (= barbican front)
MOAT_B = 31.00              # far edge of the moat
WATER_Z = -0.48
MOAT_BED = -2.60
BRIDGE_X = 3.05             # drawbridge half width
CURT_X1 = 30.60             # outer end of the curtain wall
ROAD_X = 4.20               # road half width
ROAD_END = 52.0
CITY_END = -46.0


# --------------------------------------------------------------------------
#  boolean helpers (real openings, real reveals)
# --------------------------------------------------------------------------
def _join(obs, name):
    obs = [o for o in obs if o is not None]
    if not obs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def _bool(target, cutter):
    """Apply one EXACT difference and drop the cutter."""
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    md = target.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.solver = "EXACT"
    md.object = cutter
    try:
        bpy.ops.object.modifier_apply(modifier=md.name)
    except RuntimeError as exc:
        print("[gate] boolean failed on %s: %s" % (target.name, exc), flush=True)
        target.modifiers.remove(md)
    return target


def _cut(targets, cutter, label=""):
    """Cut one cutter out of every target, then delete it."""
    for t in targets:
        if t is not None:
            _bool(t, cutter)
    if cutter is not None and cutter.name in bpy.data.objects:
        bpy.data.objects.remove(cutter, do_unlink=True)


def _rect_cutter(name, T, w, h, depth, out=0.35):
    """A box cut into a wall face: local +Y is out of the wall."""
    return box(name, T @ Ts(0, out - depth * 0.5, h * 0.5), (w, depth, h), None)


def _loop_cutter(name, T, w, h, depth, out=0.35):
    """A pointed opening cut into a wall face (T at the sill centre)."""
    return H.prism(name, T @ Ts(0, out - depth * 0.5, 0), pointed_loop(w, h),
                   depth, None, axis="y")


def _recess(name, T, w, h, depth, loop=True, out=0.30):
    """A cutter whose bite into the wall is exactly `depth` metres.

    Both `_rect_cutter` and `_loop_cutter` span local y [out - depth, out], so
    passing a window's own depth straight in left the reveal 0.35 m shallower
    than the window: the glass and its dark backing ended up buried inside the
    masonry and every opening read as a blind stone niche with the wall's
    texture showing through it.  This makes the arithmetic explicit instead.
    """
    fn = _loop_cutter if loop else _rect_cutter
    return fn(name, T, w, h, depth + out, out=out)


def _frame(x, y, z, ang):
    """Face frame: local +Y points outward at angle `ang`, local X tangential."""
    return Ts(x, y, z) @ RotZ(ang - PI * 0.5)


def _arch_ring_pts(r0, r1, a0=0.0, a1=PI, seg=44):
    pts = []
    for i in range(seg + 1):
        a = lerp(a0, a1, i / seg)
        pts.append((math.cos(a) * r1, math.sin(a) * r1))
    for i in range(seg + 1):
        a = lerp(a1, a0, i / seg)
        pts.append((math.cos(a) * r0, math.sin(a) * r0))
    return pts


def _vring(name, T, r0, r1, n, thick, mat, y=0.0, a0=0.0, a1=PI, gap=0.016,
           sub=3, mat_b=None):
    """Voussoirs built as true annular sectors.

    The intrados and extrados are real arcs and the joints are exactly radial,
    so no stone can poke a corner into the opening (the old sawtooth bug).
    """
    p = []
    for i in range(n):
        aa = lerp(a0, a1, i / n)
        bb = lerp(a0, a1, (i + 1) / n)
        hg = (gap * 0.5) / max((r0 + r1) * 0.5, 0.05)
        aa, bb = aa + hg, bb - hg
        pts = []
        for k in range(sub + 1):
            a = lerp(aa, bb, k / sub)
            pts.append((math.cos(a) * r1, math.sin(a) * r1))
        for k in range(sub + 1):
            a = lerp(bb, aa, k / sub)
            pts.append((math.cos(a) * r0, math.sin(a) * r0))
        m = mat if (mat_b is None or i % 2 == 0) else mat_b
        p.append(H.prism(name + "_%02d" % i, T @ Ts(0, y, 0), pts, thick, m,
                         axis="y"))
    return p


def arch_order(name, T, r, MAT, n=23, w=0.55, depth=0.30, hood=True,
               keystone=True, a0=0.0, a1=PI):
    """A readable arch surround: backing ring, real voussoirs, hood, keystone.

    T is at the arch centre on the wall face, local +Y out.  The backing ring
    sits flush with the opening radius so no gap can ever show the dark vault
    through the joints (the sawtooth bug of the old build).
    """
    st, pale = MAT["stone"], MAT["stone_pale"]
    p = []
    # solid backing, buried in the wall
    p.append(H.prism(name + "_bk", T @ Ts(0, -0.06, 0), _arch_ring_pts(r - 0.02, r + w,
                   a0, a1), 0.24, st, axis="y"))
    # real voussoirs, each one a separate sector stone with true arcs
    p += _vring(name + "_vs", T, r + 0.012, r + w - 0.014, n, depth, pale,
                y=depth * 0.5 - 0.03, a0=a0, a1=a1, gap=0.017, sub=3,
                mat_b=MAT["stone_warm"])
    # impost blocks at the springing
    for s in (-1, 1):
        if 0.0 < (a0 if s < 0 else a1) < PI:
            p.append(box(name + "_imp%d" % s,
                         T @ Ts(s * math.cos(a0 if s < 0 else a1) * (r + w * 0.5),
                                depth * 0.5, math.sin(a0 if s < 0 else a1) * (r + w * 0.5)),
                         (0.62, depth + 0.14, 0.34), pale, bev=0.015))
    if hood:
        p.append(H.prism(name + "_hd", T @ Ts(0, 0.10, 0),
                         _arch_ring_pts(r + w + 0.03, r + w + 0.32, a0, a1),
                         0.30, pale, axis="y"))
        p.append(H.prism(name + "_hd2", T @ Ts(0, 0.02, 0),
                         _arch_ring_pts(r + w - 0.02, r + w + 0.05, a0, a1),
                         0.14, st, axis="y"))
        # label stops: the hood moulding steps down in two corbels and dies
        # into the wall.  It used to be one 0.34 cube hung off the end of the
        # arch, which at the portal read as a block stuck on for no reason.
        for s in (-1, 1):
            aa = a0 if s < 0 else a1
            R = r + w + 0.16
            base = T @ Ts(math.cos(aa) * R, 0.0, math.sin(aa) * R)
            p.append(box(name + "_ls%d" % s, base @ Ts(0, 0.06, 0.0),
                         (0.30, 0.30, 0.44), pale, bev=0.015))
            p.append(box(name + "_ls2%d" % s, base @ Ts(0, 0.03, -0.30),
                         (0.23, 0.24, 0.20), pale, bev=0.012))
            p.append(box(name + "_ls3%d" % s, base @ Ts(0, 0.005, -0.47),
                         (0.17, 0.18, 0.15), pale, bev=0.012))
    if keystone:
        p.append(box(name + "_ks", T @ Ts(0, depth * 0.5 + 0.10, r + w * 0.5),
                     (0.46, depth + 0.20, 0.78), pale, bev=0.02))
        p.append(box(name + "_ksb", T @ Ts(0, depth * 0.5 + 0.06, r + w * 0.5),
                     (0.60, depth + 0.10, 0.94), st, bev=0.02))
    return p


def pointed_window(name, T, w, h, MAT, tracery=2, transom=0, depth=0.55,
                   hood=True, sill=True, seg=10, k=0.30):
    """Glazing, mullions, sill and mouldings for an already-cut pointed hole.

    T sits at the sill centre on the wall face, local +Y out.  The reveal
    walls are the boolean cut faces, so this is a real recess.
    """
    sw, pale, sd = MAT["stone_warm"], MAT["stone_pale"], MAT["stone_dark"]
    loop = pointed_loop(w, h, seg=seg, k=k)
    hw = w * 0.5
    p = []
    p.append(H.prism(name + "_bk", T @ Ts(0, -depth + 0.03, 0), loop, 0.03, sd, axis="y"))
    p.append(H.prism(name + "_gl", T @ Ts(0, -depth + 0.09, 0), loop, 0.035,
                     MAT["glass"], axis="y"))
    # leaded glazing bars, just in front of the glass
    for i in range(1, 4):
        z = h * i / 4.0
        p.append(box(name + "_gb%d" % i, T @ Ts(0, -depth + 0.125, z),
                     (w * 0.94, 0.012, 0.035), MAT["iron_dark"]))
    # stone mullions and a transom, standing inside the reveal
    n = max(1, int(tracery))
    for i in range(1, n):
        x = -hw + w * i / n
        p.append(box(name + "_m%d" % i, T @ Ts(x, -depth * 0.46, h * 0.5),
                     (0.11, depth * 0.86, h), pale, bev=0.01))
    for i in range(int(transom)):
        z = h * (0.42 + 0.30 * i)
        p.append(box(name + "_t%d" % i, T @ Ts(0, -depth * 0.46, z),
                     (w, depth * 0.86, 0.10), pale, bev=0.01))
    # dressed surround: jambs + architrave, proud of the wall
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.16), 0.10, h * 0.5),
                     (0.32, 0.24, h + 0.02), sw, bev=0.015))
    p.append(pointed_band(name + "_ar", T, w, h, 0.30, 0.02, 0.18, sw, seg=seg, k=k))
    if sill:
        p.append(box(name + "_sl", T @ Ts(0, 0.16, -0.12), (w + 0.84, 0.46, 0.19),
                     pale, bev=0.02))
        p.append(box(name + "_sd", T @ Ts(0, 0.30, -0.24), (w + 0.60, 0.14, 0.07), sd))
    if hood:
        p.append(pointed_band(name + "_hd", T, w + 0.54, h, 0.34, 0.16, 0.34, pale,
                              seg=seg, k=k))
        for s in (-1, 1):
            p.append(box(name + "_hs%d" % s, T @ Ts(s * (hw + 0.42), 0.30, h - 0.14),
                         (0.30, 0.34, 0.36), pale, bev=0.02))
    return p


def arrow_loop(name, T, MAT, h=1.25, w=0.20, depth=0.42):
    """Dark slot, crosslet and sill for an already-cut arrow loop."""
    pale, sd = MAT["stone_pale"], MAT["stone_dark"]
    p = [box(name + "_d", T @ Ts(0, -depth + 0.04, h * 0.5),
             (w * 0.92, 0.035, h * 0.94), sd)]
    p.append(box(name + "_c", T @ Ts(0, 0.015, h * 0.52), (w * 1.55, 0.05, 0.10), pale))
    p.append(box(name + "_c2", T @ Ts(0, 0.015, h * 0.52), (0.10, 0.05, h * 1.15), pale))
    p.append(box(name + "_s", T @ Ts(0, 0.06, -0.06), (w + 0.46, 0.22, 0.13),
                 pale, bev=0.012))
    return p


def ashlar_panel(name, T, w, h, mat, rng, bw=ASH_BW, bh=ASH_BH, proud=0.055):
    """One ashlar panel object (a list) that can be booleaned afterwards."""
    return ashlar(name, T, w, h, mat, rng, bw=bw, bh=bh, proud=proud)


def ring_ashlar(name, T, r, z0, z1, mat_a, mat_b, rng, n=52, course=ASH_COURSE,
                thick=0.06, skip=None):
    """All ashlar courses on a drum, joined into one object (for booleaning)."""
    obs = []
    z = z0
    i = 0
    while z < z1 - 0.1:
        hh = min(course, z1 - z)
        obs += ring_stones(name + "_c%d" % i, T, r, z, n, hh, mat_a, mat_b, rng,
                           thick=thick, gap=0.03, skip=skip)
        z += hh
        i += 1
    return _join(obs, name + "_ash")


def gable_roof(name, T, w, d, h, tile, deck, ov=0.42):
    """A small gabled roof: ridge along local X, slopes to +-Y, slate slabs."""
    out = []
    hw, hd = w * 0.5, d * 0.5
    out.append(H.wedge(name + "_core", T, w, d, h, deck))
    L = math.hypot(hd + ov, h)
    ang = math.atan2(h, hd + ov)
    for s in (-1, 1):
        out.append(box(name + "_sl%d" % s,
                       T @ Ts(0, s * (hd + ov) * 0.5, h * 0.5 + 0.09, rx=-s * ang),
                       (w + 2 * ov, L, 0.16), tile, bev=0.012))
    out.append(box(name + "_rd", T @ Ts(0, 0, h + 0.16), (w + 2 * ov + 0.1, 0.34, 0.20),
                   tile, bev=0.012))
    return out


# --------------------------------------------------------------------------
#  the twin drum towers
# --------------------------------------------------------------------------
def build_tower(MAT, rng, side):
    p = []
    cx = side * TOW_X
    cy = 0.0
    tag = "twR" if side > 0 else "twL"
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale = MAT["stone_pale"]
    iron = MAT["iron_dark"]
    # ---- openings: declared first, so the ashlar courses can stop at them --
    WIN_TALL = [(52.0, 17.10, 2.15, 1.55), (80.0, 17.10, 2.15, 1.55),
                (108.0, 17.10, 2.15, 1.55)]
    WIN_LOW = [(44.0, 11.40, 1.60, 1.04), (80.0, 11.40, 1.60, 1.04),
               (116.0, 11.40, 1.60, 1.04)]
    LOOP = [(28.0, 4.60), (68.0, 4.60), (112.0, 4.60), (152.0, 4.60),
            (28.0, 9.00), (68.0, 9.00), (112.0, 9.00), (152.0, 9.00),
            (28.0, 13.20), (68.0, 13.20), (112.0, 13.20), (152.0, 13.20)]
    skip = []
    for (ang, zs, hh, ww) in WIN_TALL + WIN_LOW:
        a = math.radians(ang)
        ha = (ww * 0.5 + 0.12) / 8.0
        skip.append((a - ha, a + ha, zs - 0.08, zs + hh + 0.08))
    for (ang, zc) in LOOP:
        a = math.radians(ang)
        ha = (0.24 * 0.5 + 0.10) / 8.0
        skip.append((a - ha, a + ha, zc - 0.74, zc + 0.74))
    skip.append((math.radians(270.0) - 0.15, math.radians(270.0) + 0.15, 0.0, 2.35))

    # ---- plinth and shaft ------------------------------------------------
    p.append(H.lathe(tag + "_plinth",
                     [(0.0, 0.0), (8.62, 0.0), (8.62, 0.52), (8.28, 1.02),
                      (8.02, 1.16)], st, seg=96, T=Ts(cx, cy, 0),
                     close_bottom=True, close_top=False))
    p.append(cyl(tag + "_shaft", Ts(cx, cy, 13.6), 8.0, 25.3, st, seg=96))
    # 44 stones round a 50.27 m circumference = 1.14 m x 0.52 m courses, which
    # is the scale that reads as ashlar from 40 m.  n=64 made 0.79 x 0.42 m
    # stones that read as roof shingles on a 16 m drum, and the original n=40
    # gave 1.26 x 0.58 m slabs.
    ash = ring_ashlar(tag + "_ash", Ts(cx, cy, 0), 8.0, 1.16, 24.6, sw,
                      MAT["stone_alt"], rng,
                      n=44, course=0.52, thick=0.022, skip=skip)
    p.append(ash)

    # ---- real openings ---------------------------------------------------
    # NOTE: the cutters are applied ONE AT A TIME.  Joining them into a single
    # mesh first makes the exact solver produce an empty result (it silently
    # eats the whole drum), so each cutter gets its own boolean.  The ashlar is
    # never booleaned at all - the stones are simply left out where an opening
    # is, which is exact and costs nothing.
    wall_cut = []
    for i, (ang, zs, hh, ww) in enumerate(WIN_TALL):
        T = face_T(cx, cy, zs, math.radians(ang), 8.0)
        wall_cut.append(_loop_cutter(tag + "_wc%d" % i, T, ww, hh, 1.20))
    for i, (ang, zs, hh, ww) in enumerate(WIN_LOW):
        T = face_T(cx, cy, zs, math.radians(ang), 8.0)
        wall_cut.append(_loop_cutter(tag + "_wc2%d" % i, T, ww, hh, 1.00))
    for row, z in enumerate((4.6, 9.0, 13.2)):
        for j, ang in enumerate((28.0, 68.0, 112.0, 152.0)):
            T = face_T(cx, cy, z, math.radians(ang), 8.0)
            wall_cut.append(_rect_cutter(tag + "_lc%d_%d" % (row, j), T, 0.24, 1.32,
                                         0.90))
    for c in wall_cut:
        _cut([p[1]], c)
    # the city-side door, cut through the plinth as well
    Td = face_T(cx, cy, 0.10, math.radians(270.0), 8.0)
    _cut([p[1], p[0]], _loop_cutter(tag + "_dc", Td, 1.55, 2.05, 1.10))

    # ---- windows and loops ----------------------------------------------
    for i, (ang, zs, hh, ww) in enumerate(WIN_TALL):
        T = face_T(cx, cy, zs, math.radians(ang), 8.06)
        p += pointed_window(tag + "_w%d" % i, T, ww, hh, MAT, tracery=2,
                            transom=0, depth=0.58, hood=True)
    for i, (ang, zs, hh, ww) in enumerate(WIN_LOW):
        T = face_T(cx, cy, zs, math.radians(ang), 8.06)
        p += pointed_window(tag + "_w2%d" % i, T, ww, hh, MAT, tracery=1,
                            transom=0, depth=0.50, hood=True)
    for row, z in enumerate((4.6, 9.0, 13.2)):
        for j, ang in enumerate((28.0, 68.0, 112.0, 152.0)):
            T = face_T(cx, cy, z, math.radians(ang), 8.05)
            p += arrow_loop(tag + "_l%d_%d" % (row, j), T, MAT, depth=0.44)
    # the city door: timber leaf, iron straps, steps
    Td = face_T(cx, cy, 0.10, math.radians(270.0), 8.06)
    p += _arched_door(tag + "_door", Td, 1.55, 2.05, MAT, depth=0.34, steps=2)

    # ---- string courses --------------------------------------------------
    for k, z in enumerate((7.95, 15.15, 20.95)):
        p.append(H.lathe(tag + "_sc%d" % k,
                         [(8.0, 0.0), (8.20, 0.0), (8.20, 0.20), (8.06, 0.30),
                          (8.0, 0.30)], sw, seg=96, T=Ts(cx, cy, z),
                         close_bottom=False, close_top=False))

    # ---- bartizan on the outer shoulder ----------------------------------
    ang = math.radians(20.0) if side > 0 else math.radians(160.0)
    bx, by = cx + math.cos(ang) * 8.30, cy + math.sin(ang) * 8.30
    p.append(H.lathe(tag + "_btc",
                     [(0.26, -1.30), (0.78, -0.30), (0.94, 0.0), (0.94, 0.16)],
                     sw, seg=24, T=Ts(bx, by, 23.35), close_bottom=True,
                     close_top=False))
    p.append(cyl(tag + "_btd", Ts(bx, by, 24.60), 0.94, 2.30, sw, seg=24))
    for i in range(3):
        Tb = face_T(bx, by, 23.90 + i * 0.70, ang, 0.94)
        p += arrow_loop(tag + "_btl%d" % i, Tb, MAT, h=0.86, w=0.15, depth=0.28)
    p.append(H.lathe(tag + "_btr",
                     [(1.10, 25.72), (1.10, 25.86), (0.09, 28.30)], MAT["slate"],
                     seg=24, T=Ts(bx, by, 0), close_bottom=False, close_top=True))
    p.append(sphere(tag + "_btf", Ts(bx, by, 28.44), 0.12, MAT["gold"], seg=10, ring=6))

    # ---- machicolation head ---------------------------------------------
    p.append(corbel_ring(tag + "_corb", Ts(cx, cy, 0), 8.0, 24.60, 44, sw,
                         out=1.18, h=1.30, w=0.46, taper=0.30))
    p.append(ring_wall(tag + "_gal", Ts(cx, cy, 0), 7.30, 9.08, 25.90, 27.30, sw,
                       seg=96))
    p.append(ring_wall(tag + "_gal2", Ts(cx, cy, 0), 8.98, 9.10, 25.88, 27.42, pale,
                       seg=96))
    p.append(ring_wall(tag + "_par", Ts(cx, cy, 0), 8.56, 9.12, 27.30, 28.62, st,
                       seg=96))
    p.append(rcrenel(tag + "_mer", Ts(cx, cy, 0), 8.84, 28.62, 36, merlon=0.92,
                     gap=0.52, h=1.24, depth=0.56, mat=st))
    # walk floor ring (inside the parapet, outside the roof kerb)
    p.append(ring_wall(tag + "_walk", Ts(cx, cy, 0), 6.55, 8.62, 27.28, 27.42, pale,
                       seg=96))
    p.append(ring_wall(tag + "_kerb", Ts(cx, cy, 0), 6.44, 6.62, 27.38, 27.95, sw,
                       seg=96))

    # ---- steep conical roof ---------------------------------------------
    roof = [(0.0, 35.30), (6.68, 27.55)]
    p.append(H.lathe(tag + "_roof", roof, MAT["slate"], seg=96, T=Ts(cx, cy, 0),
                     close_bottom=False, close_top=True))
    p.append(ring_wall(tag + "_eave", Ts(cx, cy, 0), 6.62, 7.05, 27.34, 27.62, sd,
                       seg=96))
    # slate courses: five lapped bands climbing the cone so the roof reads
    # as laid slates and not as a smooth cast cone
    for k in range(5):
        z0 = 27.95 + k * 1.42
        z1 = z0 + 0.40
        r0 = 6.68 * (35.30 - z0) / 7.75
        r1 = 6.68 * (35.30 - z1) / 7.75
        p.append(H.lathe(tag + "_sc%d" % k,
                         [(r0 + 0.075, z0), (r1 + 0.075, z1), (r1 + 0.012, z1),
                          (r0 + 0.012, z0), (r0 + 0.075, z0)],
                         MAT["slate"], seg=72, T=Ts(cx, cy, 0),
                         close_bottom=False, close_top=False))
    # four hips up the cone
    for i in range(4):
        a = PI * 0.25 + i * PI * 0.5
        L = math.hypot(6.55, 7.7)
        p.append(box(tag + "_rib%d" % i,
                     Ts(cx + math.cos(a) * 3.28, cy + math.sin(a) * 3.28, 31.4,
                        rz=a - PI * 0.5, rx=-math.atan2(7.75, 6.55)),
                     (0.16, L, 0.10), sd, bev=0.01))
    # lucarne on the front slope
    lx, ly = cx, cy + 5.05
    p.append(box(tag + "_luc", Ts(lx, ly, 29.05), (1.30, 1.10, 1.55), sw, bev=0.02))
    p.append(H.prism(tag + "_lug",
                     Ts(lx, ly + 0.55, 29.82),
                     [(-0.78, 0.0), (0.78, 0.0), (0.0, 0.85)], 1.16, MAT["slate"],
                     axis="y"))
    p.append(box(tag + "_luw", Ts(lx, ly + 0.56, 29.02), (0.52, 0.06, 0.72),
                 MAT["glass"]))
    p.append(box(tag + "_lus", Ts(lx, ly + 0.60, 28.63), (0.80, 0.18, 0.09), pale))
    # finial, vane and flag
    p.append(cyl(tag + "_fin", Ts(cx, cy, 35.62), 0.075, 1.30, iron, seg=10))
    p.append(sphere(tag + "_fbl", Ts(cx, cy, 36.35), 0.17, MAT["gold"], seg=12, ring=7))
    p.append(box(tag + "_vn", Ts(cx + 0.32, cy, 35.95), (0.58, 0.03, 0.22), MAT["gold"]))
    p += flag(tag + "_flag", Ts(cx, cy, 36.45), 0.10, 2.05, 1.15,
              MAT["banner_red"], MAT["gold"], iron)

    # ---- ground-floor plinth details ------------------------------------
    for i in range(8):
        a = math.radians(22.5 + 45.0 * i)
        Tb = face_T(cx, cy, 0.35, a, 8.55)
        p.append(box(tag + "_bs%d" % i, Tb @ Ts(0, 0.10, 0.35),
                     (1.10, 0.26, 0.70), sd, bev=0.015))
    return p


# --------------------------------------------------------------------------
#  arched door in an already-cut opening
# --------------------------------------------------------------------------
def _arched_door(name, T, w, h, MAT, depth=0.32, steps=0, double=False,
                 arched=True):
    """Timber leaf + frame for a cut opening.  T at the sill, +Y out."""
    wood, wd = MAT["wood"], MAT["wood_dark"]
    iron = MAT["iron_dark"]
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    p = []
    hw = w * 0.5
    p.append(box(name + "_leaf", T @ Ts(0, -depth, h * 0.5), (w - 0.10, 0.13, h - 0.06),
                 wood, bev=0.012))
    # planks
    n = 5
    for i in range(n + 1):
        x = -hw + w * i / n
        p.append(box(name + "_pl%d" % i, T @ Ts(x, -depth + 0.075, h * 0.5),
                     (0.035, 0.02, h - 0.12), wd))
    for k in range(3):
        z = h * (0.20 + 0.28 * k)
        p.append(box(name + "_bd%d" % k, T @ Ts(0, -depth + 0.09, z),
                     (w * 0.94, 0.035, 0.13), iron))
        for s in (-1, 0, 1):
            p.append(cyl(name + "_bv%d_%d" % (k, s),
                         T @ Ts(s * w * 0.38, -depth + 0.11, z) @ RotX(PI * 0.5),
                         0.035, 0.03, iron, seg=8))
    if arched:
        p += _vring(name + "_vs", T @ Ts(0, 0, h), hw + 0.02, hw + 0.32, 11, 0.30,
                    pale, y=-0.02, gap=0.014, sub=3)
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.14), 0.06, h * 0.5),
                     (0.30, 0.22, h + 0.05), sw, bev=0.012))
    for i in range(steps):
        p.append(box(name + "_st%d" % i, T @ Ts(0, 0.30 + i * 0.30, -0.07 - i * 0.0),
                     (w + 0.50, 0.34, 0.16), pale, bev=0.012))
    return p


# --------------------------------------------------------------------------
#  the gatehouse and its forebuilding
# --------------------------------------------------------------------------
R_NOTCH = RO + 0.02      # the wall opening the vault tube sits inside
GH_TOP = 19.60
GH_KEEL = 19.74          # top of the roof walk slab


def _del(ob):
    if ob is not None and ob.name in bpy.data.objects:
        bpy.data.objects.remove(ob, do_unlink=True)


def build_gatehouse(MAT, rng):
    """The main gate: a tall block pierced by the passage, a forebuilding in
    front of it, twin drum towers butted into the flanks (built separately)."""
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]
    T0 = Ts(0, 0, 0)

    # ---- the body and the forebuilding -----------------------------------
    body = H.prism("gh_body", T0,
                   arch_notch_poly(GH_W, GH_TOP, R_NOTCH, Z_SPRING, seg=40),
                   2 * GH_D, st, axis="y")
    p.append(body)
    Tfp = Ts(0, (FP_Y0 + FP_Y1) * 0.5, 0)
    porch = H.prism("gh_fp", Tfp,
                    arch_notch_poly(FP_W, FP_H, R_NOTCH, Z_SPRING, seg=40),
                    FP_Y1 - FP_Y0, st, axis="y")
    p.append(porch)

    # ======================================================================
    #  CITY FACE   (local +Y = -Y, the face plane is y = -GH_D)
    # ======================================================================
    Tc = _frame(0, -GH_D, 0.0, 1.5 * PI)
    # ashlar field, cut for the passage mouth
    c_mouth = _rect_cutter("gh_cm", Tc, 7.44, 8.10, 1.20)
    asc = ashlar("gh_asc", Tc, 19.40, GH_TOP, sw, rng, bw=1.00, bh=0.44)[0]
    _bool(asc, c_mouth)
    _del(c_mouth)
    p.append(asc)
    # the walled-up postern beside the gate: a shallow blind recess, NOT a hole,
    # so the view through the passage is never blocked.  It must sit clear of the
    # great arch, though: at x=0 all three parts ended up inside the gate's own
    # opening, 1.68 m of air from the intrados, i.e. a pale band hanging in the
    # middle of the gateway.
    Tpost = Tc @ Ts(5.40, 0, 1.16)
    _cut([body, asc], _recess("gh_cp", Tpost, 1.70, 2.45, 0.34))
    p.append(H.prism("gh_post_bk", Tpost @ Ts(0, -0.30, 0), pointed_loop(1.62, 2.38),
                     0.04, sd, axis="y"))
    p.append(pointed_band("gh_post_fr", Tpost, 1.86, 2.56, 0.26, 0.02, 0.16, pale,
                          seg=9, k=0.32))
    # city-face openings
    c_win = _recess("gh_cwc", Tc @ Ts(0, 0, 11.40), 4.30, 3.00, 0.80)
    c_sm = []
    for s in (-1, 1):
        c_sm.append(_recess("gh_cwl%d" % s, Tc @ Ts(s * 5.85, 0, 8.55),
                            1.35, 1.85, 0.74, loop=False))
    for c in [c_win] + c_sm:
        _cut([body, asc], c)
    p += pointed_window("gh_cwin", Tc @ Ts(0, 0, 11.40), 4.30, 3.00, MAT,
                        tracery=3, transom=1, depth=0.80, hood=True)
    for s in (-1, 1):
        p += pointed_window("gh_cws%d" % s, Tc @ Ts(s * 5.85, 0, 8.55), 1.35, 1.85,
                            MAT, tracery=1, transom=0, depth=0.74, hood=True)
    p += coat_of_arms("gh_ccoa", Tc @ Ts(0, 0.0, 9.30), 1.22, MAT)
    # plinth, middle string and cornice
    p.append(box("gh_cpl", Ts(0, -GH_D - 0.12, 0.55), (19.40, 0.26, 1.10), sd, bev=0.02))
    p.append(box("gh_cpl2", Ts(0, -GH_D - 0.19, 0.10), (19.40, 0.14, 0.22), sd))
    p.append(box("gh_cco", Ts(0, -GH_D - 0.15, 19.02), (19.40, 0.32, 0.32), pale, bev=0.02))
    p.append(box("gh_cco2", Ts(0, -GH_D - 0.22, 18.84), (19.40, 0.14, 0.18), sd))
    # three high lancets above the great window
    c_hi = []
    for i, xx in enumerate((-4.40, 0.0, 4.40)):
        c_hi.append(_recess("gh_chc%d" % i, Tc @ Ts(xx, 0, 16.30), 1.06, 2.10,
                            0.78))
    for c in c_hi:
        _cut([body, asc], c)
    for i, xx in enumerate((-4.40, 0.0, 4.40)):
        p += pointed_window("gh_chw%d" % i, Tc @ Ts(xx, 0, 16.30), 1.06, 2.10, MAT,
                            tracery=1, transom=0, depth=0.78, hood=True)
    # corbel table under the cornice
    for i in range(18):
        xx = -8.35 + i * 0.98
        p.append(box("gh_ccb%d" % i, Tc @ Ts(xx, 0.20, 18.36), (0.32, 0.46, 0.52),
                     pale, bev=0.012))
    # stepped buttresses flanking the city portal
    for s in (-1, 1):
        p.append(box("gh_bt0_%d" % s, Ts(s * 4.62, -GH_D - 0.30, 3.35),
                     (0.98, 0.72, 6.40), sw, bev=0.02))
        p.append(box("gh_bt1_%d" % s, Ts(s * 4.62, -GH_D - 0.24, 6.95),
                     (0.86, 0.60, 0.70), sw, bev=0.02))
        p.append(box("gh_bt2_%d" % s, Ts(s * 4.62, -GH_D - 0.20, 7.52),
                     (0.74, 0.48, 0.44), pale, bev=0.015))
        p.append(box("gh_bt3_%d" % s, Ts(s * 4.62, -GH_D - 0.14, 0.09),
                     (0.98, 0.34, 0.18), sd))

    # ======================================================================
    #  ROAD FACE above the forebuilding   (y = +GH_D, but the porch hides
    #  everything below FP_H, so this starts at the porch roof)
    # ======================================================================
    Tf = _frame(0, GH_D, FP_H, PI * 0.5)
    c_fl = []
    for s in (-1, 1):
        c_fl.append(_recess("gh_fl%d" % s,
                            Tf @ Ts(s * 4.55, 0, 15.20 - FP_H), 1.15, 2.00, 0.86))
    asf = ashlar("gh_asft", Tf, 19.40, GH_TOP - FP_H, sw, rng)[0]
    for c in c_fl:
        _cut([body, asf], c)
    p.append(asf)
    for s in (-1, 1):
        p += pointed_window("gh_flw%d" % s, Tf @ Ts(s * 4.55, 0, 15.20 - FP_H),
                            1.15, 2.00, MAT, tracery=1, transom=0, depth=0.86,
                            hood=True)
    p += coat_of_arms("gh_fcoa", Tf @ Ts(0, 0.0, 16.65 - FP_H), 1.28, MAT)
    # the two flanking strips beside the forebuilding
    for s in (-1, 1):
        p += ashlar("gh_asf%d" % s, _frame(s * 8.09, GH_D, 0.0, PI * 0.5),
                    3.18, FP_H, sw, rng)
    p.append(box("gh_fsc", Ts(0, GH_D + 0.11, 14.55), (19.40, 0.30, 0.32), pale, bev=0.02))
    p.append(box("gh_fsc2", Ts(0, GH_D + 0.19, 14.36), (19.40, 0.13, 0.16), sd))

    # ======================================================================
    #  THE FOREBUILDING FRONT
    # ======================================================================
    Tp = _frame(0, FP_Y1, 0.0, PI * 0.5)
    cp_m = _rect_cutter("gh_pmc", Tp, 7.44, 8.10, 1.10)
    asp = ashlar("gh_asp", Tp, FP_W * 2, FP_H, sw, rng)[0]
    _bool(asp, cp_m)
    _del(cp_m)
    p.append(asp)
    # side faces of the forebuilding
    for s in (-1, 1):
        Tside = Ts(s * FP_W, (FP_Y0 + FP_Y1) * 0.5, 0.0) @ RotZ(-s * PI * 0.5)
        # NOTE: this used to be p.append(ashlar(...)) - `ashlar` already returns
        # a list of objects, so that put a list inside the part list.  _flat()
        # happens to recurse, so nothing was ever lost, but the nesting made the
        # part count wrong and left this the obvious suspect for orphaned slabs.
        p += ashlar("gh_asps%d" % s, Tside, FP_Y1 - FP_Y0, FP_H, sw, rng)
    # the great arch order
    p += arch_order("gh_arch", Ts(0, FP_Y1, Z_SPRING), RO, MAT, n=23, w=0.58,
                    depth=0.34, hood=True)
    p += arch_order("gh_archc", Ts(0, -GH_D - 0.01, Z_SPRING), RO, MAT, n=23, w=0.52,
                    depth=0.30, hood=True)
    # porch sculpture
    p += coat_of_arms("gh_pcoa", Ts(0, FP_Y1 + 0.02, 9.30), 1.30, MAT)
    for s in (-1, 1):
        p += niche("gh_nic%d" % s, Ts(s * 5.02, FP_Y1 + 0.01, 2.35), 1.48, 3.20, MAT, rng)
        p += guardian("gh_grd%d" % s, Ts(s * 5.02, FP_Y1 + 0.12, 2.58), 3.10, MAT)
    # porch roof: flat, with a low crenellated parapet
    p.append(box("gh_fproof", Ts(0, (FP_Y0 + FP_Y1) * 0.5 + 0.14, FP_H - 0.14),
                 (FP_W * 2 - 0.08, FP_Y1 - FP_Y0 + 0.28, 0.28), sd, bev=0.02))
    p.append(box("gh_fproof2", Ts(0, (FP_Y0 + FP_Y1) * 0.5 + 0.10, FP_H - 0.30),
                 (FP_W * 2 - 0.16, FP_Y1 - FP_Y0 + 0.10, 0.08), MAT["slate"]))
    p.append(box("gh_fpar", Ts(0, FP_Y1 - 0.22, FP_H + 0.34), (FP_W * 2, 0.44, 0.70),
                 st, bev=0.025))
    p.append(box("gh_fcop", Ts(0, FP_Y1 - 0.20, FP_H + 0.72), (FP_W * 2 + 0.10, 0.56,
                                                              0.13), pale, bev=0.015))
    p += crenel_line("gh_fmer", Ts(0, FP_Y1 - 0.24, FP_H + 0.78), FP_W * 2 - 0.20,
                     st, merlon=0.92, gap=0.50, h=0.86, depth=0.50)
    # porch parapet returns on the sides
    for s in (-1, 1):
        p.append(box("gh_fprs%d" % s, Ts(s * (FP_W - 0.22), (FP_Y0 + FP_Y1) * 0.5,
                                        FP_H + 0.34), (0.44, FP_Y1 - FP_Y0, 0.70), st,
                     bev=0.02))

    # ======================================================================
    #  ROOF WALK  (level with the tower walks)
    # ======================================================================
    p.append(box("gh_walk", Ts(0, 0, GH_TOP + 0.07), (2 * GH_W, 2 * GH_D, 0.14),
                 pale, bev=0.02))
    p.append(box("gh_walk2", Ts(0, 0, GH_TOP + 0.02), (2 * GH_W - 0.30, 2 * GH_D - 0.30,
                                                     0.10), sd))
    p += flagstones("gh_rfsN", Ts(0, 0, GH_TOP + 0.145), 2 * GH_W - 0.30, 0.22,
                    GH_D - 0.10, MAT["cobble"], rng, cw=1.10, cl=0.90, h=0.05)
    p += flagstones("gh_rfsW", Ts(-6.55, 0, GH_TOP + 0.145), 12.90, -GH_D + 0.10,
                    -0.22, MAT["cobble"], rng, cw=1.10, cl=0.90, h=0.05)
    p += machic_line("gh_mF", Ts(0, GH_D, 0), 12.60, MAT, out=1.02, wall_z=GH_TOP)
    p += machic_line("gh_mB", Ts(0, -GH_D, 0) @ RotZ(PI), 19.00, MAT, out=1.02,
                     wall_z=GH_TOP)
    # cap house (the guard room) on the walk
    chx, chy = 3.55, -2.30
    p.append(box("gh_ch", Ts(chx, chy, GH_TOP + 0.14 + 1.65), (5.30, 4.30, 3.30), sw,
                 bev=0.03))
    p.append(box("gh_chb", Ts(chx, chy, GH_TOP + 0.34), (5.66, 4.66, 0.40), sd, bev=0.02))
    p += gable_roof("gh_chr", Ts(chx, chy, GH_TOP + 0.14 + 3.30), 5.30, 4.30, 1.85,
                    MAT["slate"], sd)
    p.append(H.chimney("gh_chim", Ts(chx + 1.60, chy + 1.35, GH_TOP + 3.40), 2.50, sw))
    # cap-house door (on the walk, facing +Y) and a window
    p += _arched_door("gh_chd", _frame(chx + 1.55, chy + 2.16, GH_TOP + 0.16, PI * 0.5),
                      1.10, 1.95, MAT, depth=0.26, steps=0, arched=False)
    Tchw = _frame(chx - 1.20, chy + 2.16, GH_TOP + 1.62, PI * 0.5)
    p.append(box("gh_chwf", Tchw @ Ts(0, 0.04, 0.0), (1.05, 0.10, 1.10), sw, bev=0.01))
    p.append(box("gh_chwg", Tchw @ Ts(0, 0.075, 0.0), (0.85, 0.05, 0.92), MAT["glass"]))
    for i in range(2):
        p.append(box("gh_chwb%d" % i, Tchw @ Ts(0, 0.11, -0.28 + i * 0.56),
                     (0.90, 0.03, 0.05), iron))
    for i in range(2):
        p.append(box("gh_chs%d" % i, Ts(chx + 1.55, chy + 2.52 + i * 0.34,
                                        GH_TOP + 0.06), (1.50, 0.34, 0.16), pale,
                     bev=0.012))
    # bench, water butt, braziers
    p.append(box("gh_bench", Ts(-3.30, GH_D - 1.15, GH_TOP + 0.50), (2.60, 0.52, 0.12),
                 MAT["wood"], bev=0.02))
    for s in (-1, 1):
        p.append(box("gh_benchl%d" % s, Ts(-3.30 + s * 1.10, GH_D - 1.15, GH_TOP + 0.28),
                     (0.16, 0.44, 0.44), MAT["wood_dark"]))
    p.append(H.barrel("gh_butt", Ts(-5.30, GH_D - 0.90, GH_TOP + 0.14), 0.42, 1.05,
                      MAT["wood"], iron))
    for s in (-1, 1):
        p += brazier("gh_brz%d" % s, Ts(s * 5.55, GH_D - 0.85, GH_TOP + 0.14), MAT)
    # flag over the gate
    p += flag("gh_flag", Ts(0, -4.40, GH_KEEL + 0.10), 0.10, 2.60, 1.55,
              MAT["banner_blue"], MAT["gold"], iron)
    return p


# --------------------------------------------------------------------------
#  small iron / light fittings
# --------------------------------------------------------------------------
def torch(name, T, MAT, nx):
    """A pitch torch in an iron basket on a wall; T is the wall point and nx the
    direction it projects in (world X)."""
    iron, wood = MAT["iron_dark"], MAT["wood_dark"]
    p = []
    x = T.translation.x
    p.append(box(name + "_br", Ts(x + nx * 0.10, T.translation.y, T.translation.z - 0.30),
                 (0.34, 0.09, 0.09), iron))
    p.append(box(name + "_br2", Ts(x + nx * 0.26, T.translation.y, T.translation.z - 0.12),
                 (0.09, 0.09, 0.46), iron))
    p.append(cyl(name + "_cup", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.10), 0.13, 0.20,
                 iron, seg=10, r2=0.17))
    p.append(cyl(name + "_stk", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.24), 0.045, 0.36,
                 wood, seg=8))
    p.append(sphere(name + "_fl", Ts(x + nx * 0.26, T.translation.y, T.translation.z + 0.52), 0.11,
                    MAT["glow"], seg=8, ring=5, squash=1.6))
    for i in range(6):
        a = TAU * i / 6.0
        p.append(box(name + "_pr%d" % i,
                     Ts(x + nx * 0.26 + math.cos(a) * 0.13, T.translation.y + math.sin(a) * 0.13,
                        T.translation.z + 0.22), (0.035, 0.035, 0.20), iron))
    return p


def lantern(name, T, MAT):
    """A hanging lantern under the vault.  T is the hook point in the vault --
    the chain runs up into the stone and the cage hangs off its lower end, so
    nothing here can float free of what holds it."""
    iron, gold = MAT["iron_dark"], MAT["gold"]
    o = T.translation
    z = o.z - 0.38                      # top cap of the cage
    p = [chain(name + "_ch", o, o + Vector((0.0, 0.0, 0.30)), 0.0, iron,
               links=4, R=0.045, r=0.014)]
    p.append(box(name + "_hk", Ts(o.x, o.y, o.z + 0.02), (0.16, 0.16, 0.05), iron))
    p.append(sphere(name + "_kn", Ts(o.x, o.y, z - 0.02), 0.05, gold, seg=8, ring=5))
    p.append(cyl(name + "_top", Ts(o.x, o.y, z), 0.20, 0.10, iron, seg=8, r2=0.10))
    for i in range(4):
        a = TAU * i / 4.0 + PI * 0.25
        p.append(box(name + "_f%d" % i,
                     Ts(o.x + math.cos(a) * 0.19, o.y + math.sin(a) * 0.19, z - 0.34),
                     (0.045, 0.045, 0.48), iron))
    p.append(cyl(name + "_gl", Ts(o.x, o.y, z - 0.34), 0.155, 0.46, MAT["glow"],
                 seg=10))
    p.append(cyl(name + "_bot", Ts(o.x, o.y, z - 0.62), 0.16, 0.09, iron, seg=8,
                 r2=0.20))
    p.append(sphere(name + "_bf", Ts(o.x, o.y, z - 0.71), 0.06, gold, seg=8, ring=5))
    return p


def brazier(name, T, MAT):
    """A coal brazier on the roof walk."""
    iron, gold = MAT["iron_dark"], MAT["gold"]
    p = []
    p.append(H.lathe(name + "_bowl", [(0.0, 0.0), (0.34, 0.28), (0.40, 0.46),
                                      (0.36, 0.50)], iron, seg=16, T=Ts(T.translation.x, T.translation.y, T.translation.z),
                     close_bottom=True, close_top=False))
    for i in range(3):
        a = TAU * i / 3.0
        p.append(box(name + "_lg%d" % i,
                     Ts(T.translation.x + math.cos(a) * 0.28, T.translation.y + math.sin(a) * 0.28, T.translation.z - 0.04),
                     (0.07, 0.07, 0.30), iron))
    p.append(sphere(name + "_coal", Ts(T.translation.x, T.translation.y, T.translation.z + 0.42), 0.26, MAT["glow"],
                    seg=10, ring=6, squash=0.45))
    return p


# --------------------------------------------------------------------------
#  the passage
# --------------------------------------------------------------------------
def build_passage(MAT, rng):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron, wd = MAT["stone_pale"], MAT["iron_dark"], MAT["wood_dark"]
    y0, y1 = -GH_D - 0.02, FP_Y1 + 0.02

    # ---- floor -----------------------------------------------------------
    p += flagstones("ps_floor", Ts(0, 0, DECK), 2 * RO - 0.04, y0, y1, MAT["cobble"],
                    rng, cw=0.88, cl=0.72, h=0.17)
    for i, yy in enumerate((y0 + 0.34, y1 - 0.34)):
        p.append(box("ps_thr%d" % i, Ts(0, yy, DECK - 0.025),
                     (2 * RO - 0.04, 0.54, 0.07), pale, bev=0.015))
    # central drain with iron grates
    p.append(box("ps_drn", Ts(0, (y0 + y1) * 0.5, DECK - 0.045),
                 (0.46, y1 - y0 - 0.7, 0.03), sd))
    for i in range(6):
        yy = y0 + 2.5 + i * 1.95
        p.append(box("ps_grt%d" % i, Ts(0, yy, DECK - 0.012), (0.54, 0.64, 0.035), iron))
        for k in range(4):
            p.append(box("ps_gb%d_%d" % (i, k), Ts(-0.18 + k * 0.12, yy, DECK + 0.006),
                         (0.05, 0.58, 0.02), iron))

    # ---- side walls ------------------------------------------------------
    for s in (-1, 1):
        Tside = Ts(s * (RO + 0.006), (y0 + y1) * 0.5, DECK - 0.02) @ RotZ(-s * PI * 0.5)
        p.append(ashlar("ps_ash%d" % s, Tside, y1 - y0 - 0.12,
                        Z_SPRING - DECK + 0.12, sw, rng))
        p.append(box("ps_pl%d" % s, Ts(s * (RO - 0.07), (y0 + y1) * 0.5, DECK + 0.16),
                     (0.16, y1 - y0 - 0.24, 0.34), sd, bev=0.02))
        p.append(box("ps_sc%d" % s, Ts(s * (RO - 0.11), (y0 + y1) * 0.5,
                                       Z_SPRING - 0.13), (0.24, y1 - y0 - 0.24, 0.22),
                     pale, bev=0.02))

    # ---- vault -----------------------------------------------------------
    # The vault is built as two tubes with a slot between them at the portcullis
    # plane, and the slot is closed 0.24 m above the intrados.  That void is the
    # stone chase the raised grille disappears into.  It used to be one tube and
    # the grille simply stopped in mid-air under it, with a square collar on
    # every bar top: the "finial hanging in nothing" that gave the gate away.
    PC_Y = 5.45
    SLOT_W = 0.56
    p.append(arch_tube("ps_vault_a", Ts(0, 0, 0), RO, Z_SPRING, y0,
                       PC_Y - SLOT_W * 0.5, 0.58, st, seg=54))
    p.append(arch_tube("ps_vault_b", Ts(0, 0, 0), RO, Z_SPRING, PC_Y + SLOT_W * 0.5,
                       y1, 0.58, st, seg=54))
    p.append(arch_band("ps_slot", Ts(0, 0, Z_SPRING), RO + 0.24, RO + 0.58,
                       PC_Y - SLOT_W * 0.5, PC_Y + SLOT_W * 0.5, sd, seg=54))
    # transverse voussoir rings: the barrel is coursed stone, not a smooth clay
    # tube.  The rings stand 0.022 m proud of the backing tube, so the joints
    # between them read as recessed mortar and the ribs sit on top of them.
    _yy, _i = y0 + 0.30, 0
    while _yy < y1 - 0.24:
        if abs(_yy - PC_Y) > SLOT_W * 0.5 + 0.30:
            p.append(voussoir_ring("ps_vr%d" % _i, Ts(0, 0, Z_SPRING), RO - 0.022,
                                   0.46, 27, st, y=_yy, thick=0.56, gap=0.030))
            _i += 1
        _yy += 0.64
    for i in range(8):
        yy = y0 + 1.40 + i * 1.92
        p.append(arch_band("ps_rib%d" % i, Ts(0, yy, Z_SPRING), RO - 0.07, RO + 0.26,
                           -0.15, 0.15, pale, seg=30))
        p.append(box("ps_rks%d" % i, Ts(0, yy, Z_SPRING + RO + 0.05),
                     (0.34, 0.34, 0.28), sw, bev=0.02))
    p.append(box("ps_ridge_a", Ts(0, (y0 + PC_Y - SLOT_W * 0.5) * 0.5,
                                  Z_SPRING + RO + 0.01),
                 (0.30, PC_Y - SLOT_W * 0.5 - y0, 0.22), sw))
    p.append(box("ps_ridge_b", Ts(0, (PC_Y + SLOT_W * 0.5 + y1) * 0.5,
                                  Z_SPRING + RO + 0.01),
                 (0.30, y1 - PC_Y - SLOT_W * 0.5, 0.22), sw))
    for i in range(8):
        yy = y0 + 1.40 + i * 1.92
        p.append(sphere("ps_bs%d" % i, Ts(0, yy, Z_SPRING + RO - 0.05), 0.27,
                        pale, seg=10, ring=6, squash=0.55))
        p.append(sphere("ps_bg%d" % i, Ts(0, yy, Z_SPRING + RO - 0.15), 0.10,
                        MAT["gold"], seg=8, ring=5, squash=0.6))

    # ---- portcullis and windlass -----------------------------------------
    p += portcullis("ps_pc", Ts(0, PC_Y, 0), 2 * RO - 0.30, 3.55, Z_SPRING + RO + 0.20,
                    MAT, n=9, crown=(Z_SPRING, RO),
                    slot=(RO + 0.24, RO + 0.58))
    p.append(box("ps_pcs", Ts(0, PC_Y, 1.30), (2 * RO - 0.12, 0.46, 0.05), sd))
    p += windlass("ps_wl", Ts(0, 4.10, 0), 3.20, 6.40, MAT)

    # ---- the two leaves, standing open ----------------------------------
    p += door_leaf("ps_lfL", Ts(-2.76, 0.62, DECK), 2.62, 3.95, MAT, ang=95.0)
    p += door_leaf("ps_lfR", Ts(2.76, 0.62, DECK), 2.62, 3.95, MAT, ang=85.0)
    for s in (-1, 1):
        for k in range(3):
            p.append(cyl("ps_hn%d_%d" % (s, k), Ts(s * 2.82, 0.62, 1.15 + k * 1.30),
                         0.075, 0.24, iron, seg=10))

    # ---- doors set into the passage walls --------------------------------
    for s in (-1, 1):
        for k, yy in enumerate((-3.55, 1.85)):
            Td = Ts(s * (RO - 0.03), yy, DECK) @ RotZ(-s * PI * 0.5)
            for j, xx in ((-1, -0.74), (1, 0.74)):
                p.append(box("ps_dja%d_%d_%d" % (s, k, j), Td @ Ts(xx, 0.10, 1.12),
                             (0.26, 0.22, 2.24), pale, bev=0.015))
            p.append(box("ps_djl%d_%d" % (s, k), Td @ Ts(0, 0.10, 2.30),
                         (1.74, 0.22, 0.26), pale, bev=0.015))
            p.append(box("ps_dls%d_%d" % (s, k), Td @ Ts(0, 0.14, 0.06),
                         (1.74, 0.30, 0.12), sd, bev=0.015))
            p.append(box("ps_dlf%d_%d" % (s, k), Td @ Ts(0, 0.045, 1.06),
                         (1.20, 0.10, 2.10), MAT["wood_dark"], bev=0.01))
            for j in range(3):
                p.append(box("ps_dbd%d_%d_%d" % (s, k, j),
                             Td @ Ts(0, 0.10, 0.36 + j * 0.64), (1.18, 0.045, 0.11),
                             iron))
            p.append(sphere("ps_dkn%d_%d" % (s, k), Td @ Ts(0.40, 0.13, 1.06), 0.07,
                            MAT["gold"], seg=8, ring=5))

    # ---- lighting and fittings -------------------------------------------
    for i, (yy, s) in enumerate(((-5.30, -1), (-2.20, 1), (1.35, -1), (2.95, 1),
                                 (6.60, -1), (8.35, 1))):
        p += torch("ps_tch%d" % i, Ts(s * RO, yy, 3.05), MAT, -s)
    p += lantern("ps_lan", Ts(0, 3.30, Z_SPRING + RO - 0.01), MAT)
    p.append(box("ps_bench", Ts(-2.18, -1.10, DECK + 0.42), (0.46, 2.20, 0.12),
                 MAT["wood"], bev=0.02))
    for yy in (-2.10, -0.10):
        p.append(box("ps_bl", Ts(-2.18, yy, DECK + 0.21), (0.40, 0.14, 0.42),
                     MAT["wood_dark"]))
    p.append(H.barrel("ps_bar", Ts(2.26, -1.55, DECK), 0.32, 0.86, MAT["wood"], iron))
    p.append(H.crate("ps_crt", Ts(2.24, -0.55, DECK), 0.66, MAT["wood"]))
    for i in range(3):
        p.append(torus("ps_rg%d" % i, Ts(-(RO - 0.07), -4.4, 1.30 + i * 0.0)
                       @ RotZ(PI * 0.5) @ RotX(PI * 0.5), 0.16, 0.035, iron, seg=12,
                       ring=5))
    return p


def door_leaf(name, T, w, h, MAT, ang=95.0):
    """A heavy plank leaf hinged at T, swung open by `ang` degrees."""
    wood, wd, iron = MAT["wood"], MAT["wood_dark"], MAT["iron_dark"]
    gold, pale = MAT["gold"], MAT["stone_pale"]
    p = []
    Tw = T @ RotZ(math.radians(ang))
    p.append(box(name + "_lf", Tw @ Ts(-w * 0.5, 0, h * 0.5), (w, 0.15, h), wood,
                 bev=0.012))
    n = 6
    for i in range(n + 1):
        p.append(box(name + "_p%d" % i, Tw @ Ts(-w * i / n, 0.082, h * 0.5),
                     (0.035, 0.02, h - 0.10), wd))
    for k in range(4):
        z = h * (0.12 + 0.25 * k)
        p.append(box(name + "_b%d" % k, Tw @ Ts(-w * 0.5, 0.098, z),
                     (w * 0.96, 0.035, 0.11), iron))
        for j in range(6):
            p.append(cyl(name + "_s%d_%d" % (k, j),
                         Tw @ Ts(-w * 0.09 - j * w * 0.16, 0.118, z) @ RotX(PI * 0.5),
                         0.038, 0.03, iron, seg=7))
    for k in range(2):
        z = h * (0.22 + 0.46 * k)
        p.append(box(name + "_h%d" % k, Tw @ Ts(-0.05, 0.02, z), (0.34, 0.24, 0.14),
                     iron, bev=0.01))
        p.append(cyl(name + "_hp%d" % k, Tw @ Ts(0.0, 0.0, z), 0.055, 0.64, iron, seg=8))
    p.append(torus(name + "_rg", Tw @ Ts(-w + 0.28, 0.14, h * 0.46) @ RotX(PI * 0.5),
                   0.11, 0.026, gold, seg=12, ring=5))
    p.append(cyl(name + "_rk", Tw @ Ts(-w + 0.28, 0.11, h * 0.52) @ RotX(PI * 0.5),
                 0.055, 0.10, gold, seg=10))
    return p


def portcullis(name, T, w, zbot, ztop, MAT, n=9, crown=None, rails=4, channels=True,
               slot=None):
    """An iron grille with real thickness and spear points; z relative to T.

    `crown=(zc, r)` is the arch the grille is raised into.  With `slot=(r_in,
    r_out)` — the inner and outer radius of the stone chase cut above the
    soffit — the bars stop on a circle 0.06 m inside the chase's back stone, so
    every tip is housed in the slot and none can be silhouetted against the
    vault.  The horizontal rails are cut back to the soffit so their ends enter
    the haunch.  The square collars that used to cap every bar are gone: that
    was the "finial hanging in nothing" on the portal shots.
    """
    iron, iron2 = MAT["iron"], MAT["iron_dark"]
    pale = MAT["stone_pale"]
    p = []
    zc = r = None
    rt = 0.0
    if crown:
        zc, r = crown
        if slot:
            rt = slot[1] - 0.06          # 0.06 m of stone left above every tip
            ztop = zc + rt
        else:
            rt = r + 0.30                # tip buried in the chase, never in air
    pitch = w / (n - 1)

    def tip(x):
        if not crown:
            return ztop
        ins = rt * rt - x * x
        if ins <= 0.0:
            return None
        return min(ztop, zc + math.sqrt(ins))

    for i in range(n):
        x = -w * 0.5 + i * pitch
        zt = tip(x)
        if zt is None or zt <= zbot + 0.30:
            continue
        p.append(box(name + "_b%d" % i, T @ Ts(x, 0, (zbot + zt) * 0.5),
                     (0.075, 0.075, zt - zbot), iron))
        p.append(cone(name + "_sp%d" % i, T @ Ts(x, 0, zbot - 0.17), 0.055, 0.36, iron2,
                      seg=6))
    # horizontal rails: evenly spaced over the visible height and each clipped
    # to the soffit, so their ends enter the haunch instead of crossing it
    vis = (zc + r if crown else ztop) - zbot
    nr = rails if not crown else max(3, int(round(vis / 0.85)))
    for k in range(nr):
        z = zbot + (k + 0.5) * vis / nr
        hw = w * 0.5 + 0.05
        if crown:
            ins = r * r - (z - zc) ** 2
            if ins <= 0.04:
                continue
            hw = min(hw, math.sqrt(ins) - 0.05)
        if hw <= 0.30:
            continue
        p.append(box(name + "_h%d" % k, T @ Ts(0, 0.01, z), (2 * hw, 0.09, 0.10), iron))
    for s in (-1, 1):
        x = s * (w * 0.5 + 0.07)
        zt = tip(x)
        if zt is None:
            zt = ztop
        p.append(box(name + "_st%d" % s, T @ Ts(x, 0, (zbot + zt) * 0.5),
                     (0.13, 0.13, zt - zbot), iron2))
    if channels:
        # the iron channel each stile runs in, bolted to the jamb, and the
        # dressed stone guide blocks that frame its mouth
        for s in (-1, 1):
            x = s * (w * 0.5 + 0.07)
            p.append(box(name + "_ch%d" % s, T @ Ts(x, 0.0, (zbot - 0.60 + ztop) * 0.5),
                         (0.26, 0.22, ztop - zbot + 1.20), iron2, bev=0.01))
            for yy in (-0.55, 0.55, 1.65):
                p.append(box(name + "_cb%d_%.0f" % (s, yy * 10),
                             T @ Ts(x, 0.14, zbot + yy), (0.30, 0.10, 0.10), iron))
            if crown:
                zg = zc + 0.12
                p.append(box(name + "_gb%d" % s, T @ Ts(x, 0.02, zg),
                             (0.40, 0.34, 0.30), pale, bev=0.02))
    return p


def windlass(name, T, span, z, MAT):
    """A winch drum over the gate, with ratchet wheel, crank and two chains."""
    iron, iron2 = MAT["iron"], MAT["iron_dark"]
    wd = MAT["wood_dark"]
    p = []
    p.append(cyl(name + "_dr", T @ Ts(0, 0, z) @ RotY(PI * 0.5), 0.30, span, wd, seg=18))
    for s in (-1, 1):
        p.append(cyl(name + "_fl%d" % s, T @ Ts(s * span * 0.5, 0, z) @ RotY(PI * 0.5),
                     0.52, 0.10, iron, seg=20))
        p.append(box(name + "_br%d" % s, T @ Ts(s * span * 0.46, 0, z + 0.26),
                     (0.16, 0.34, 0.60), iron2, bev=0.01))
    p.append(cyl(name + "_rt", T @ Ts(-span * 0.40, 0, z) @ RotY(PI * 0.5), 0.62, 0.09,
                 iron2, seg=22))
    for i in range(10):
        a = TAU * i / 10.0
        p.append(box(name + "_rtt%d" % i,
                     T @ Ts(-span * 0.40, math.sin(a) * 0.60, z + math.cos(a) * 0.60,
                            ry=-a), (0.10, 0.10, 0.16), iron2))
    p.append(box(name + "_pw", T @ Ts(-span * 0.40, 0.52, z + 0.48, rx=0.5),
                 (0.10, 0.34, 0.56), iron2))
    p.append(cyl(name + "_ck", T @ Ts(span * 0.54, 0.0, z) @ RotY(PI * 0.5), 0.055, 0.34,
                 iron, seg=10))
    p.append(box(name + "_ck2", T @ Ts(span * 0.70, 0.0, z + 0.24), (0.09, 0.09, 0.62),
                 iron))
    p.append(cyl(name + "_ck3", T @ Ts(span * 0.70, 0.20, z + 0.52) @ RotX(PI * 0.5),
                 0.09, 0.36, wd, seg=10))
    for s in (-1, 1):
        p += chain(name + "_ch%d" % s,
                   T @ Vector((s * span * 0.36, -0.02, z - 0.24)),
                   T @ Vector((s * 1.05, 1.35, 6.98)), 0.14, iron, links=13,
                   R=0.085, r=0.028)
    return p


# --------------------------------------------------------------------------
#  curtain walls and their end turrets
# --------------------------------------------------------------------------
def build_curtain(MAT, rng, side):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]
    x0, x1 = 19.80, CURT_X1          # the inner end is buried in the tower drum
    cx = (x0 + x1) * 0.5
    ln = x1 - x0
    h = WALL_H
    body = box("cw_body%d" % side, Ts(side * cx, 0, h * 0.5), (ln, WALL_T, h), st,
               bev=0.02)
    p.append(body)
    p.append(box("cw_pl%d" % side, Ts(side * cx, 0, 0.45), (ln, WALL_T + 0.30, 0.90),
                 sd, bev=0.025))
    # ashlar on both faces
    pan = {}
    for s in (-1, 1):
        T = _frame(side * cx, s * WALL_T * 0.5, 0.90, PI * 0.5 if s > 0 else 1.5 * PI)
        pan[s] = ashlar("cw_as%d_%d" % (side, s), T, ln - 0.10, h - 1.05, sw, rng)[0]
        p.append(pan[s])
        p.append(box("cw_sc%d_%d" % (side, s), Ts(side * cx, s * (WALL_T * 0.5 + 0.06),
                                                  6.95), (ln - 0.10, 0.20, 0.24), pale,
                     bev=0.02))
        p.append(box("cw_sc2%d_%d" % (side, s), Ts(side * cx, s * (WALL_T * 0.5 + 0.02),
                                                   6.78), (ln - 0.10, 0.10, 0.14), sd))
    # arrow loops on the road face: real cuts through the panel and the body
    for i in range(3):
        x = cx - 3.4 + i * 3.4
        T = _frame(side * x, WALL_T * 0.5, 8.55, PI * 0.5)
        # the cutter spans [out - depth, out], so ask for the 0.42 m recess the
        # dark backing plate at -0.38 sits inside, not a 0.27 m nick
        c = _rect_cutter("cw_lc%d_%d" % (side, i), T, 0.26, 1.35, 0.42 + 0.35,
                         out=0.35)
        _cut([body, pan[1]], c)
        p += arrow_loop("cw_lp%d_%d" % (side, i),
                        _frame(side * x, WALL_T * 0.5, 8.55, PI * 0.5), MAT, depth=0.42)
    # wall walk and parapets
    p.append(box("cw_walk%d" % side, Ts(side * cx, 0, h + 0.07),
                 (ln - 0.04, WALL_T + 0.20, 0.14), pale, bev=0.02))
    p += flagstones("cw_fs%d" % side, Ts(side * cx, 0, h + 0.145), ln - 0.12, -0.72,
                    0.73, MAT["cobble"], rng, cw=0.62, cl=0.50, h=0.05)
    p.append(box("cw_par%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 0.55),
                 (ln - 0.06, 0.44, 0.82), st, bev=0.02))
    p.append(box("cw_cop%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 1.00),
                 (ln - 0.02, 0.56, 0.12), pale, bev=0.015))
    p += crenel_line("cw_mer%d" % side, Ts(side * cx, WALL_T * 0.5 + 0.12, h + 1.06),
                     ln - 0.20, st, merlon=0.92, gap=0.52, h=1.05, depth=0.50)
    p.append(box("cw_par2%d" % side, Ts(side * cx, -(WALL_T * 0.5 + 0.09), h + 0.50),
                 (ln - 0.06, 0.40, 0.72), st, bev=0.02))
    p.append(box("cw_cop2%d" % side, Ts(side * cx, -(WALL_T * 0.5 + 0.09), h + 0.90),
                 (ln - 0.02, 0.52, 0.12), pale, bev=0.015))

    # ---- end turret ------------------------------------------------------
    tx = side * (CURT_X1 - 0.35)
    p.append(H.lathe("cw_tpl%d" % side,
                     [(0.0, 0.0), (2.95, 0.0), (2.95, 0.55), (2.72, 1.05),
                      (2.58, 1.10)], st, seg=44, T=Ts(tx, 0, 0),
                     close_bottom=True, close_top=False))
    shaft = cyl("cw_tsh%d" % side, Ts(tx, 0, 7.35), 2.58, 12.60, st, seg=44)
    p.append(shaft)
    ash = ring_ashlar("cw_tas%d" % side, Ts(tx, 0, 0), 2.58, 1.10, 12.60, sw,
                      MAT["stone_alt"], rng, n=20, course=ASH_COURSE, thick=0.05,
                      skip=[(math.radians(20.0 + 70.0 * i) - 0.12,
                             math.radians(20.0 + 70.0 * i) + 0.12,
                             9.30 - 0.70, 9.30 + 0.70) for i in range(2)])
    p.append(ash)
    for i in range(2):
        ang = math.radians(20.0 + 70.0 * i)
        c = _rect_cutter("cw_tlc%d_%d" % (side, i), face_T(tx, 0, 9.30, ang, 2.58),
                         0.22, 1.10, 0.44 + 0.35, out=0.35)
        _cut([shaft], c)
        p += arrow_loop("cw_tlp%d_%d" % (side, i), face_T(tx, 0, 9.30, ang, 2.60),
                        MAT, h=1.10, w=0.20, depth=0.44)
    p.append(corbel_ring("cw_tcor%d" % side, Ts(tx, 0, 0), 2.58, 12.60, 18, sw,
                         out=0.55, h=0.75, w=0.34, taper=0.30))
    p.append(ring_wall("cw_tgal%d" % side, Ts(tx, 0, 0), 2.40, 3.12, 13.30, 14.02, sw,
                       seg=44))
    p.append(ring_wall("cw_tpar%d" % side, Ts(tx, 0, 0), 2.86, 3.16, 14.02, 14.86, st,
                       seg=44))
    p.append(rcrenel("cw_tmer%d" % side, Ts(tx, 0, 0), 3.01, 14.86, 12, merlon=0.72,
                     gap=0.42, h=0.86, depth=0.46, mat=st))
    p.append(H.lathe("cw_troof%d" % side, [(2.98, 14.30), (0.02, 17.70)], MAT["slate"],
                     seg=44, T=Ts(tx, 0, 0), close_bottom=False, close_top=True))
    p.append(sphere("cw_tball%d" % side, Ts(tx, 0, 17.86), 0.16, MAT["gold"], seg=10,
                    ring=6))
    p.append(cyl("cw_tfin%d" % side, Ts(tx, 0, 18.20), 0.055, 0.90, iron, seg=8))
    return p


def build_stair(MAT, rng, side):
    """A solid straight flight down the city face of the curtain wall."""
    p = []
    sw, sd, pale = MAT["stone_warm"], MAT["stone_dark"], MAT["stone_pale"]
    x = side * 27.60
    w = 1.94
    y_top = -WALL_T * 0.5 - 0.12
    n = 42
    rise = 12.60 / n
    run = 14.0 / n
    for i in range(n):
        yy = y_top - run * (i + 0.5)
        zz = rise * (i + 1)
        p.append(box("st_s%d_%d" % (side, i), Ts(x, yy, zz * 0.5),
                     (w, run + 0.02, zz), sw, bev=0.006))
    # the face of the flight, stepped back into a battered mass
    p.append(box("st_bk%d" % side, Ts(x, y_top - 14.10, 1.40),
                 (w - 0.06, 0.30, 2.80), sd, bev=0.01))
    # raking side walls (built as short levels so they never float)
    for s in (-1, 1):
        for i in range(0, n, 2):
            yy = y_top - run * (i + 1)
            zz = rise * (i + 2)
            p.append(box("st_pw%d_%d_%d" % (side, s, i),
                         Ts(x + s * (w * 0.5 - 0.10), yy, zz * 0.5 + 0.55),
                         (0.30, run * 2.1, zz + 1.10), sw, bev=0.01))
    # newel and a lantern at the bottom
    p.append(cyl("st_new%d" % side, Ts(x, y_top + 0.30, 13.35), 0.36, 1.70, pale, seg=14))
    p.append(sphere("st_nb%d" % side, Ts(x, y_top + 0.30, 14.32), 0.32, pale, seg=12,
                    ring=7))
    p.append(H.lantern_post("st_lp%d" % side, Ts(x + side * 1.55,
                                                y_top - 14.6, 0.06), 2.70,
                            MAT["iron_dark"], MAT["glow"]))
    return p


# --------------------------------------------------------------------------
#  the barbican: a closed ward in front of the gate
# --------------------------------------------------------------------------
BARB_GATE_W = 5.00
BARB_GATE_R = 2.50
BARB_GATE_SPRING = 3.30


def build_barbican(MAT, rng):
    p = []
    st, sw, sd = MAT["stone"], MAT["stone_warm"], MAT["stone_dark"]
    pale, iron = MAT["stone_pale"], MAT["iron_dark"]

    # ---- side walls ------------------------------------------------------
    for s in (-1, 1):
        x = s * BARB_X
        ln = BARB_FRONT - 6.45
        cy = (6.45 + BARB_FRONT) * 0.5
        bsw = box("bb_sw%d" % s, Ts(x, cy, BARB_Z * 0.5), (BARB_T, ln, BARB_Z), st,
                  bev=0.02)
        p.append(bsw)
        p.append(box("bb_sp%d" % s, Ts(x, cy, 0.45), (BARB_T + 0.28, ln, 0.90), sd,
                     bev=0.025))
        bsa = {}
        for f in (-1, 1):
            oa = ashlar("bb_sa%d_%d" % (s, f),
                        Ts(x + f * BARB_T * 0.5, cy, 0.88) @ RotZ(-f * PI * 0.5),
                        ln - 0.08, BARB_Z - 1.02, sw, rng)
            bsa[f] = oa[0]
            p.append(oa)
            p.append(box("bb_ssc%d_%d" % (s, f),
                         Ts(x + f * (BARB_T * 0.5 + 0.05), cy, 6.60),
                         (0.18, ln - 0.10, 0.22), pale, bev=0.02))
        p.append(box("bb_swk%d" % s, Ts(x, cy, BARB_Z + 0.07),
                     (BARB_T + 0.16, ln, 0.14), pale, bev=0.02))
        p.append(box("bb_spar%d" % s, Ts(x, cy, BARB_Z + 0.55),
                     (BARB_T + 0.10, ln - 0.06, 0.82), st, bev=0.02))
        p.append(box("bb_scop%d" % s, Ts(x, cy, BARB_Z + 0.98),
                     (BARB_T + 0.22, ln - 0.02, 0.12), pale, bev=0.015))
        p += crenel_line("bb_smer%d" % s, Ts(x, cy, BARB_Z + 1.04), ln - 0.20, st,
                         merlon=0.88, gap=0.50, h=1.02, depth=0.52, axis="y")
        for i in range(3):
            yy = 9.2 + i * 3.4
            # local +Y is the outward normal: ang 0 faces +x, PI faces -x, so the
            # flank loops sit on the moat side of the barbican rather than buried
            # along the wall's length (they had no slot cut either)
            T = _frame(x + s * BARB_T * 0.5, yy, 8.10, 0.0 if s > 0 else PI)
            c = _rect_cutter("bb_slc%d_%d" % (s, i), T, 0.26, 1.22,
                             0.42 + 0.35, out=0.35)
            _cut([bsw, bsa[s]], c)
            p += arrow_loop("bb_sl%d_%d" % (s, i), T, MAT, depth=0.42)

    # ---- front wall with the barbican gate -------------------------------
    fw = H.prism("bb_fw", Ts(0, (BARB_FRONT + 21.30) * 0.5, 0),
                 arch_notch_poly(9.15, BARB_Z, BARB_GATE_R + 0.02,
                                 BARB_GATE_SPRING, seg=34), BARB_T, st, axis="y")
    # the same stone chase as the great gate: a radial groove cut into the
    # tunnel crown, 0.26 m deep and 0.52 m long, that the raised grille's bar
    # tips disappear into.  bb_fw is a closed prism, so the exact solver is safe.
    bb_slot = arch_band("bb_slot", Ts(0, 0, 0), BARB_GATE_R - 0.02,
                        BARB_GATE_R + 0.28, 21.89, 22.41, None, seg=40,
                        zc=BARB_GATE_SPRING)
    _bool(fw, bb_slot)
    _del(bb_slot)
    p.append(fw)
    for f, yy, ang in ((1, BARB_FRONT, PI * 0.5), (-1, 21.30, 1.5 * PI)):
        T = _frame(0, yy, 0.0, ang)
        ob = ashlar("bb_fa%d" % f, T, 18.30, BARB_Z, sw, rng)[0]
        _cut([ob], _rect_cutter("bb_fmc%d" % f, T, 5.36, 6.10, 1.10))
        p.append(ob)
        p.append(box("bb_fpl%d" % f, Ts(0, yy + f * 0.13, 0.45),
                     (18.30, 0.26, 0.90), sd, bev=0.02))
        p.append(box("bb_fsc%d" % f, Ts(0, yy + f * 0.09, 6.72),
                     (18.30, 0.20, 0.24), pale, bev=0.02))
    p.append(box("bb_fwk", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.07),
                 (18.30, BARB_T + 0.16, 0.14), pale, bev=0.02))
    p.append(box("bb_fpar", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.55),
                 (18.30, BARB_T + 0.10, 0.82), st, bev=0.02))
    p.append(box("bb_fcop", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 0.98),
                 (18.30, BARB_T + 0.22, 0.12), pale, bev=0.015))
    p += crenel_line("bb_fmer", Ts(0, (BARB_FRONT + 21.30) * 0.5, BARB_Z + 1.04),
                     18.10, st, merlon=0.90, gap=0.52, h=1.04, depth=0.54)
    p += arch_order("bb_ar", Ts(0, BARB_FRONT + 0.01, BARB_GATE_SPRING),
                    BARB_GATE_R, MAT, n=19, w=0.46, depth=0.26, hood=True)
    p += arch_order("bb_ar2", Ts(0, 21.29, BARB_GATE_SPRING), BARB_GATE_R, MAT,
                    n=19, w=0.40, depth=0.20, hood=False, keystone=False)
    p += portcullis("bb_pc", Ts(0, (BARB_FRONT + 21.30) * 0.5, 0), 4.70, 2.15,
                    BARB_GATE_SPRING + BARB_GATE_R + 0.16, MAT, n=9,
                    crown=(BARB_GATE_SPRING, BARB_GATE_R),
                    slot=(BARB_GATE_R - 0.02, BARB_GATE_R + 0.28))
    # barrel-vault ribs inside the gate tunnel
    for i, yy in enumerate((21.55, 22.15, 22.75)):
        p.append(arch_band("bb_trb%d" % i, Ts(0, yy, BARB_GATE_SPRING),
                           BARB_GATE_R - 0.05, BARB_GATE_R + 0.24, -0.09, 0.09, pale,
                           seg=26))
        p.append(box("bb_trk%d" % i, Ts(0, yy, BARB_GATE_SPRING + BARB_GATE_R + 0.04),
                     (0.30, 0.20, 0.24), sw, bev=0.02))
    p.append(box("bb_gf", Ts(0, (BARB_FRONT + 21.30) * 0.5, DECK * 0.5),
                 (BARB_GATE_W + 0.10, BARB_T + 0.02, DECK), MAT["cobble"], bev=0.01))
    p += coat_of_arms("bb_coa", Ts(0, BARB_FRONT + 0.02, 7.55), 1.10, MAT)
    for s in (-1, 1):
        p += wall_banner("bb_ban%d" % s, Ts(s * 5.85, BARB_FRONT + 0.10, 8.85), 1.35,
                         3.60, MAT["banner_red"] if s < 0 else MAT["banner_blue"],
                         MAT["gold"], iron)
        p += torch("bb_tch%d" % s, Ts(s * 2.62, 22.05, 3.30), MAT, -s)

    # corbel table under the barbican parapet, on both faces
    for f, yy, ang in ((1, BARB_FRONT, PI * 0.5), (-1, 21.30, 1.5 * PI)):
        T = _frame(0, yy, 0.0, ang)
        for i in range(20):
            xx = -8.55 + i * 0.90
            if abs(xx) < 1.30:
                continue
            p.append(box("bb_fcb%d_%d" % (f, i), T @ Ts(xx, 0.22, 9.90),
                         (0.34, 0.50, 0.58), pale, bev=0.012))
            p.append(box("bb_fcc%d_%d" % (f, i), T @ Ts(xx, 0.28, 10.22),
                         (0.42, 0.44, 0.14), sw, bev=0.01))
    # shrine niches flanking the ward side of the gate (empty: a dark back
    # panel reads better at this scale than a crude figure)
    Tn = _frame(0, 21.29, 0.0, 1.5 * PI)
    for s in (-1, 1):
        p += niche("bb_ni%d" % s, Tn @ Ts(s * 4.05, 0, 1.02), 1.12, 2.14, MAT, rng)
        p.append(box("bb_nib%d" % s, Tn @ Ts(s * 4.05, 0.02, 1.16),
                     (0.92, 0.03, 1.84), sd))

    # ---- the two corner towers -------------------------------------------
    for s in (-1, 1):
        tx, ty = s * BARB_X, 22.60
        p.append(H.lathe("bt_pl%d" % s,
                         [(0.0, -2.60), (BTOW_R + 0.42, -2.60), (BTOW_R + 0.42, 0.60),
                          (BTOW_R + 0.10, 1.10), (BTOW_R, 1.16)], st, seg=44,
                         T=Ts(tx, ty, 0), close_bottom=True, close_top=False))
        shaft = cyl("bt_sh%d" % s, Ts(tx, ty, 6.88), BTOW_R, 11.44, st, seg=44)
        p.append(shaft)
        # Leave angular gaps in the ashlar where the arrow loops go and cut only
        # the shaft, the way build_tower does it.  Booleaning the ashlar ring
        # itself "succeeded" but ate 30 courses down to four stones, so these two
        # towers were bare cylinders with three floating plate slots on them.
        skip = []
        for i in range(3):
            a = math.radians(30.0 + 60.0 * i)
            ha = (0.24 * 0.5 + 0.12) / BTOW_R
            skip.append((a - ha, a + ha, 8.30 - 0.72, 8.30 + 0.72))
        ash = ring_ashlar("bt_as%d" % s, Ts(tx, ty, 0), BTOW_R, 1.16, BTOW_TOP, sw,
                          MAT["stone_alt"], rng, n=24, course=ASH_COURSE, thick=0.05,
                          skip=skip)
        p.append(ash)
        for i in range(3):
            ang = math.radians(30.0 + 60.0 * i)
            c = _rect_cutter("bt_lc%d_%d" % (s, i),
                             face_T(tx, ty, 8.30, ang, BTOW_R), 0.24, 1.20,
                             0.44 + 0.35, out=0.35)
            _cut([shaft], c)
            p += arrow_loop("bt_lp%d_%d" % (s, i), face_T(tx, ty, 8.30, ang, BTOW_R),
                            MAT, h=1.20, w=0.22, depth=0.44)
        p.append(corbel_ring("bt_co%d" % s, Ts(tx, ty, 0), BTOW_R, BTOW_TOP, 20, sw,
                             out=0.62, h=0.80, w=0.36, taper=0.30))
        p.append(ring_wall("bt_ga%d" % s, Ts(tx, ty, 0), BTOW_R - 0.15, BTOW_R + 0.58,
                           BTOW_TOP + 0.55, BTOW_TOP + 1.30, sw, seg=44))
        p.append(ring_wall("bt_pa%d" % s, Ts(tx, ty, 0), BTOW_R + 0.30, BTOW_R + 0.60,
                           BTOW_TOP + 1.30, BTOW_TOP + 2.16, st, seg=44))
        p.append(rcrenel("bt_me%d" % s, Ts(tx, ty, 0), BTOW_R + 0.45, BTOW_TOP + 2.16,
                         13, merlon=0.74, gap=0.44, h=0.92, depth=0.48, mat=st))
        # waterline: a damp, weed-darkened footing where the tower meets the
        # moat.  It must stay FLUSH with the plinth (0.025 m proud) and matte:
        # a 0.26 m proud, half-shiny ring read as a black rubber collar round
        # the base instead of a water stain.  The thin pale scum ring
        # (gd_sclr, in build_ground) draws the actual waterline on top of it.
        p.append(ring_wall("bt_wt%d" % s, Ts(tx, ty, 0), BTOW_R - 0.02, BTOW_R + 0.025,
                           WATER_Z - 0.65, 0.60, MAT["wet_band"], seg=44))
        # the walk: a stone deck flush with the gallery ring.  What used to be
        # here was a 0.07 m slate plate 0.68 m LOWER than the walk, so from any
        # high camera the tower top read as a well full of black water.
        p.append(ring_wall("bt_wk%d" % s, Ts(tx, ty, 0), 0.0, BTOW_R - 0.12,
                           BTOW_TOP + 1.02, BTOW_TOP + 1.30, sw, seg=44))
        # flagging inset, slightly proud of the deck so the walk is not a clean
        # pale disc under the parapet
        p.append(ring_wall("bt_dk%d" % s, Ts(tx, ty, 0), 0.0, BTOW_R - 0.34,
                           BTOW_TOP + 1.30, BTOW_TOP + 1.375, MAT["cobble"], seg=44))
        # Real flags on top of that disc.  A smooth lathe disc inside a 0.9 m
        # parapet sits in shadow, turns teal under the sky fill and -- with no
        # joint lines anywhere on it -- reads as a pool of water from above,
        # which is the exact illusion this whole pass is meant to kill.  Laid
        # as a clipped grid so the joints are visible at 1x.
        for _iy in range(-4, 5):
            for _ix in range(-4, 5):
                _fx, _fy = _ix * 0.70, _iy * 0.70
                if _fx * _fx + _fy * _fy > 2.38 * 2.38:
                    continue
                p.append(box("bt_dkp%d_%d_%d" % (s, _ix + 4, _iy + 4),
                             Ts(tx + _fx, ty + _fy, BTOW_TOP + 1.375),
                             (0.62, 0.62, 0.10),
                             pale if ((_ix * 3 + _iy * 5) % 4) == 0 else sw,
                             bev=0.006))
        # and a flag that actually stands up: the old call passed pole_h=0.08,
        # which laid a 1.6 x 1.0 m banner flat across the deck like a drift log.
        p.append(flag("bt_fl%d" % s, Ts(tx, ty, BTOW_TOP + 1.425), 3.30, 1.55, 0.95,
                      MAT["banner_red"], MAT["gold"], iron))
        p.append(H.barrel("bt_br%d" % s, Ts(tx + 1.60, ty - 1.42, BTOW_TOP + 1.425),
                          0.30, 0.78, MAT["wood"], iron))
        p.append(torus("bt_rp%d" % s, Ts(tx - 1.35, ty + 1.05, BTOW_TOP + 1.49),
                       0.34, 0.075, MAT["wood"], seg=14, ring=6))

    # ---- the ward --------------------------------------------------------
    p += flagstones("bb_floor", Ts(0, 0, DECK), 2 * (BARB_X - BARB_T * 0.5),
                    9.15, 21.35, MAT["cobble"], rng, cw=0.86, cl=0.70, h=0.16)
    # the gate tunnel floor: without this the meadow shows through the sill
    p += flagstones("bb_tun", Ts(0, 0, DECK), 2 * BARB_GATE_R - 0.06, 21.32, 23.04,
                    MAT["cobble"], rng, cw=0.86, cl=0.60, h=0.16)
    for s in (-1, 1):
        p.append(box("bb_al%d" % s, Ts(s * 6.98, 7.95, DECK * 0.5),
                     (0.98, 2.70, DECK), MAT["cobble"], bev=0.01))
    # central gutter with iron grates
    p.append(box("bb_drn", Ts(0, 15.25, DECK - 0.05), (0.44, 11.40, 0.06), sd))
    for i in range(5):
        p.append(box("bb_grt%d" % i, Ts(0, 10.40 + i * 2.40, DECK - 0.015),
                     (0.54, 0.62, 0.04), iron))
    # stone trough fed by the well, and a bench along the wall
    p.append(box("bb_trg", Ts(-5.30, 15.30, DECK + 0.28), (1.72, 0.74, 0.56), pale,
                 bev=0.02))
    p.append(box("bb_trgi", Ts(-5.30, 15.30, DECK + 0.36), (1.44, 0.54, 0.42),
                 MAT["water"]))
    p.append(box("bb_bnc", Ts(6.40, 16.60, DECK + 0.42), (0.52, 2.60, 0.14),
                 MAT["wood"], bev=0.02))
    # a well
    p.append(cyl("bb_well", Ts(-5.30, 13.30, 0.55), 0.95, 1.10, sd, seg=18))
    p.append(ring_wall("bb_wellr", Ts(-5.30, 13.30, 0), 0.60, 0.95, 1.10, 1.22, pale,
                       seg=18))
    for i in range(2):
        p.append(cyl("bb_wlp%d" % i, Ts(-5.30 + (-1) ** i * 0.85, 13.30, 1.95), 0.06,
                     1.70, MAT["wood_dark"], seg=8))
    p.append(box("bb_wlb", Ts(-5.30, 13.30, 2.72), (1.90, 0.14, 0.14),
                 MAT["wood_dark"]))
    p.append(box("bb_wlh", Ts(-5.30, 13.30, 2.40), (0.10, 0.10, 0.70), iron))
    for i, (xx, yy) in enumerate(((6.10, 11.20), (6.10, 12.30), (5.20, 18.40))):
        p.append(H.barrel("bb_br%d" % i, Ts(xx, yy, DECK), 0.32, 0.86, MAT["wood"], iron))
    for i, (xx, yy) in enumerate(((-6.20, 11.00), (-5.10, 19.20))):
        p.append(H.crate("bb_cr%d" % i, Ts(xx, yy, DECK), 0.70, MAT["wood"]))
    p.append(H.crate("bb_cart", Ts(3.60, 16.60, DECK), 0.92, MAT["wood"]))
    for i, (xx, yy) in enumerate(((-7.00, 15.00), (7.00, 15.00))):
        p.append(H.lantern_post("bb_lp%d" % i, Ts(xx, yy, DECK), 2.90,
                                MAT["iron_dark"], MAT["glow"]))
    return p


# --------------------------------------------------------------------------
#  the drawbridge
# --------------------------------------------------------------------------
def build_drawbridge(MAT, rng):
    """A timber bridge lying down: level with the ward, the gate and the road."""
    p = []
    wood, wd, iron = MAT["wood"], MAT["wood_dark"], MAT["iron_dark"]
    w = BRIDGE_X * 2
    y0, y1 = 22.80, 31.15
    # the far bearing beam: closes the joint between the deck and the highway
    p.append(box("db_sill", Ts(0, 31.26, DECK - 0.055), (w + 0.30, 0.56, 0.11), wd,
                 bev=0.008))
    for s in (-1, 1):
        p.append(box("db_bm%d" % s, Ts(s * (BRIDGE_X - 0.22), (y0 + y1) * 0.5, DECK - 0.30),
                     (0.34, y1 - y0, 0.42), wd, bev=0.015))
    n = 9
    for i in range(n):
        yy = y0 + 0.5 + i * (y1 - y0 - 1.0) / (n - 1)
        p.append(box("db_j%d" % i, Ts(0, yy, DECK - 0.16), (w - 0.10, 0.24, 0.16), wd))
    n = 26
    for i in range(n):
        yy = y0 + 0.16 + i * (y1 - y0 - 0.32) / (n - 1)
        p.append(box("db_pk%d" % i, Ts(0, yy, DECK - 0.0475),
                     (w - 0.04, (y1 - y0 - 0.32) / (n - 1) - 0.035, 0.095), wood,
                     bev=0.006))
    for k in range(4):
        yy = y0 + 1.2 + k * 2.2
        p.append(box("db_st%d" % k, Ts(0, yy, DECK + 0.008), (w - 0.30, 0.14, 0.028),
                     iron))
        for j in range(6):
            p.append(cyl("db_bt%d_%d" % (k, j),
                         Ts(-w * 0.42 + j * w * 0.168, yy, DECK + 0.026), 0.036, 0.03,
                         iron, seg=6))
    for s in (-1, 1):
        p.append(box("db_rail%d" % s, Ts(s * (BRIDGE_X - 0.12), (y0 + y1) * 0.5,
                                         DECK + 0.42), (0.14, y1 - y0, 0.13), wd))
        for i in range(5):
            yy = y0 + 0.7 + i * 2.0
            p.append(box("db_post%d_%d" % (s, i),
                         Ts(s * (BRIDGE_X - 0.12), yy, DECK + 0.21),
                         (0.14, 0.14, 0.42), wd))
        # end standards: real newels a metre tall with a moulded cap and a
        # ball head, so the handrail dies into a post at both ends instead of
        # stopping in mid-air with a flat cap 0.16 m above the rail.
        for k, yy in enumerate((y0 + 0.14, y1 - 0.14)):
            p.append(box("db_esp%d_%d" % (s, k),
                         Ts(s * (BRIDGE_X - 0.12), yy, DECK + 0.50),
                         (0.24, 0.24, 1.00), wd, bev=0.012))
            p.append(box("db_ecp%d_%d" % (s, k),
                         Ts(s * (BRIDGE_X - 0.12), yy, DECK + 1.03),
                         (0.31, 0.31, 0.07), wd, bev=0.015))
            p.append(sphere("db_efn%d_%d" % (s, k),
                            Ts(s * (BRIDGE_X - 0.12), yy, DECK + 1.10), 0.095,
                            wd, seg=14, ring=8))
    # binder beams across the plank ends
    for k, yy in enumerate((y0 + 0.12, y1 - 0.12)):
        p.append(box("db_bind%d" % k, Ts(0, yy, DECK - 0.06), (w - 0.02, 0.20, 0.12),
                     wd, bev=0.01))
    # lifting gear: the chain is anchored at the hinge eye on the deck's outer
    # end face -- the point a bascule bridge is actually pulled from -- and runs
    # up into the guide ring on the winch drum.  Both ends are visible fittings
    # that the last link sits inside of, so nothing reads as a chain dangling
    # into the moat (the old anchor was a plate buried in the newel cap).
    for s in (-1, 1):
        hx = s * (BRIDGE_X - 0.55)          # inboard of the corner newel
        hy = y1 + 0.03                      # on the end face of the deck
        p.append(box("db_hng%d" % s, Ts(hx, hy, DECK + 0.30),
                     (0.46, 0.10, 0.72), iron, bev=0.012))
        p.append(box("db_hng2%d" % s, Ts(hx, hy + 0.055, DECK + 0.62),
                     (0.26, 0.14, 0.24), iron, bev=0.010))
        for k in (-1, 1):
            p.append(cyl("db_hb%d_%d" % (s, k), Ts(hx + k * 0.17, hy + 0.055,
                                                   DECK + 0.20) @ RotX(PI * 0.5),
                         0.035, 0.12, MAT["iron"], seg=6))
        eye = Vector((hx, hy + 0.125, DECK + 0.62))
        p.append(torus("db_ar%d" % s, Ts(eye.x, eye.y, eye.z) @ RotX(PI * 0.5),
                       0.115, 0.036, iron, seg=14, ring=6))
        drum = Vector((s * 4.30, 23.18, 8.40))   # centre of the guide ring db_tr
        # the path is pushed 0.12 m past each fitting so the first and last
        # links sit inside the eye and the guide ring instead of short of them
        d = (drum - eye).normalized()
        p += chain("db_ch%d" % s, eye - d * 0.12, drum + d * 0.12, 0.60, iron,
                   links=30, R=0.085, r=0.028)
        # the winch the chain disappears into, bolted flat on the barbican face
        p.append(box("db_hh%d" % s, Ts(s * 4.30, 23.04, 8.34),
                     (0.94, 0.40, 1.28), wd, bev=0.02))
        p.append(box("db_hhc%d" % s, Ts(s * 4.30, 23.02, 7.72),
                     (1.10, 0.30, 0.14), iron, bev=0.012))
        p.append(cyl("db_hd%d" % s, Ts(s * 4.30, 22.82, 8.46) @ RotX(PI * 0.5),
                     0.24, 0.86, iron, seg=16))
        p.append(torus("db_tr%d" % s, Ts(s * 4.30, 23.18, 8.46) @ RotZ(PI * 0.5)
                       @ RotX(PI * 0.5), 0.15, 0.038, iron, seg=10, ring=5))
    # hinge straps and pintles at the inboard end: the bridge is bolted down
    for s in (-1, 1):
        for k in range(2):
            yy = y0 + 0.55 + k * 0.90
            p.append(box("db_hg%d_%d" % (s, k), Ts(s * 1.55, yy, DECK + 0.030),
                         (2.60, 0.09, 0.05), iron, bev=0.006))
            p.append(box("db_hgp%d_%d" % (s, k), Ts(s * 1.55, y0 + 0.06, DECK + 0.10),
                         (0.22, 0.22, 0.30), MAT["iron_dark"], bev=0.01))
    # the far abutment
    p.append(box("db_ab", Ts(0, 31.45, -0.30), (w + 1.30, 0.90, 0.86),
                 MAT["stone_dark"], bev=0.03))
    p.append(box("db_ab2", Ts(0, 31.45, 0.16), (w + 1.10, 0.80, 0.10),
                 MAT["stone_pale"], bev=0.02))
    return p


# --------------------------------------------------------------------------
#  ground, moat, roads
# --------------------------------------------------------------------------
SITE_X = 46.0
FRONT_Y = 56.0
BACK_Y = -46.0
PLAZA_Y = -13.0
STREET_X = 5.20


def _prism_z(name, pts, z0, z1, mat):
    """A vertical prism from a 2-D (x, y) polygon."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        xa, ya = pts[i]
        xb, yb = pts[(i + 1) % n]
        area += xa * yb - xb * ya
    if area < 0.0:
        pts = list(reversed(pts))
    verts = [(x, y, z0) for (x, y) in pts] + [(x, y, z1) for (x, y) in pts]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return _mk(name, verts, faces, mat)


def _strip(name, p0, p1, w, z0, z1, mat):
    """A straight box between two ground points, w wide."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    ang = math.atan2(dx, dy)
    mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
    return box(name, Ts(mx, my, (z0 + z1) * 0.5, rz=ang), (w, ln, z1 - z0), mat,
               bev=0.01)


def _plane(name, x0, x1, y0, y1, z, mat, t=0.10):
    """A ground plate; thin so it never fights with the objects on it."""
    return box(name, Ts((x0 + x1) * 0.5, (y0 + y1) * 0.5, z - t * 0.5),
               (x1 - x0, y1 - y0, t), mat)


def build_ground(MAT, rng):
    p = []
    st, sd, pale = MAT["stone"], MAT["stone_dark"], MAT["stone_pale"]
    grass, cob, water = MAT["grass"], MAT["cobble"], MAT["water"]
    BIG = 240.0
    # ---- meadow: four plates leaving a hole for the moat ------------------
    p.append(_plane("gd_grS", -BIG, BIG, -BIG, MOAT_A - 0.40, 0.0, grass))
    p.append(_plane("gd_grN", -BIG, BIG, MOAT_B + 0.40, BIG, 0.0, grass))
    p.append(_plane("gd_grW", -BIG, -SITE_X, MOAT_A - 0.40, MOAT_B + 0.40, 0.0, grass))
    p.append(_plane("gd_grE", SITE_X, BIG, MOAT_A - 0.40, MOAT_B + 0.40, 0.0, grass))

    # ---- the moat --------------------------------------------------------
    p.append(box("gd_bed", Ts(0, (MOAT_A + MOAT_B) * 0.5, MOAT_BED - 0.10),
                 (SITE_X * 2, MOAT_B - MOAT_A, 0.20), sd, bev=0.02))
    # the water runs around the two corner towers standing in the ditch
    wr = BTOW_R + 0.52
    wy = MOAT_A + 0.05
    dy = wy - 22.60
    dx = math.sqrt(max(wr * wr - dy * dy, 0.0))
    a_lo = math.atan2(dy, dx)
    a_hi = math.atan2(dy, -dx)
    wt = [(-SITE_X + 0.05, wy)]
    for cx in (-BARB_X, BARB_X):
        for i in range(15):
            a = a_hi + (a_lo - a_hi) * i / 14.0
            wt.append((cx + math.cos(a) * wr, 22.60 + math.sin(a) * wr))
    wt += [(SITE_X - 0.05, wy), (SITE_X - 0.05, MOAT_B - 0.05),
           (-SITE_X + 0.05, MOAT_B - 0.05)]
    p.append(_prism_z("gd_water", wt, WATER_Z - 0.06, WATER_Z, water))
    # waterline: a damp band on the stone just above the surface plus a pale
    # mineral scum line exactly at it, on both banks and round both tower bases.
    # Without these the moat read as a green plane that simply stopped in space.
    for tag, yy in (("gd_dmp0", MOAT_A + 0.02), ("gd_dmp1", MOAT_B - 0.02)):
        p.append(box(tag, Ts(0, yy, WATER_Z - 0.10), (SITE_X * 2 - 0.2, 0.07, 0.52),
                     MAT["wet"]))
    for tag, yy in (("gd_scl0", MOAT_A + 0.035), ("gd_scl1", MOAT_B - 0.035)):
        p.append(box(tag, Ts(0, yy, WATER_Z - 0.005), (SITE_X * 2 - 0.2, 0.07, 0.075),
                     MAT["scum"]))
    for s in (-1, 1):
        p.append(ring_wall("gd_sclr%d" % s, Ts(s * BARB_X, 22.60, 0), BTOW_R + 0.39,
                           BTOW_R + 0.575, WATER_Z - 0.05, WATER_Z + 0.028,
                           MAT["scum"], seg=44))
    # revetments (both banks) and the two end walls
    for tag, y0, y1 in (("gd_rvn", MOAT_A - 0.40, MOAT_A),
                        ("gd_rvf", MOAT_B, MOAT_B + 0.40)):
        p.append(box(tag, Ts(0, (y0 + y1) * 0.5, MOAT_BED * 0.5),
                     (SITE_X * 2, y1 - y0, abs(MOAT_BED)), sd, bev=0.02))
        p.append(box(tag + "_cop", Ts(0, (y0 + y1) * 0.5, 0.06),
                     (SITE_X * 2, y1 - y0 + 0.16, 0.12), MAT["stone_warm"],
                     bev=0.015))
    for s in (-1, 1):
        p.append(box("gd_rve%d" % s, Ts(s * (SITE_X - 0.20), (MOAT_A + MOAT_B) * 0.5,
                                        MOAT_BED * 0.5),
                     (0.40, MOAT_B - MOAT_A, abs(MOAT_BED)), sd, bev=0.02))
    # dressed masonry on the moat walls, the band that shows above the water
    for tag, yy, aa in (("gd_ra0", MOAT_A, PI * 0.5),
                        ("gd_ra1", MOAT_B, 1.5 * PI)):
        p += ashlar(tag, _frame(0, yy, WATER_Z - 0.30, aa), SITE_X * 2 - 0.60,
                    1.04, MAT["stone_warm"], rng, bw=1.24, bh=0.44)

    # reeds and low scrub along the waterline
    for i in range(44):
        xx = -SITE_X + 2.4 + i * 2.02 + rng.uniform(-0.35, 0.35)
        if abs(xx) < BRIDGE_X + 0.6:
            continue
        for bank, yy in ((0, MOAT_A + 0.17), (1, MOAT_B - 0.17)):
            for k in range(3):
                hh = rng.uniform(0.55, 1.20)
                p.append(box("gd_rd%d_%d_%d" % (i, bank, k),
                             Ts(xx + rng.uniform(-0.24, 0.24),
                                yy + rng.uniform(-0.09, 0.09),
                                WATER_Z - 0.18 + hh * 0.5) @ RotZ(rng.uniform(0.0, PI)),
                             (0.042, 0.042, hh), MAT["leaf"]))

    # ---- approach road: bridge throat then the highway -------------------
    # the far coping at y 30.92..31.48 is the joint: the road starts behind it
    road = [(2.70, 31.48), (2.70, 31.90), (4.20, 33.60), (4.20, ROAD_END),
            (-4.20, ROAD_END), (-4.20, 33.60), (-2.70, 31.90), (-2.70, 31.48)]
    p.append(_prism_z("rd_body", road, 0.0, DECK, cob))
    for s in (-1, 1):
        p.append(_strip("rd_kr%dA" % s, (s * 2.70, 31.48), (s * 2.70, 31.90),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("rd_kr%dB" % s, (s * 2.70, 31.90), (s * 4.20, 33.60),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("rd_kr%dC" % s, (s * 4.20, 33.60), (s * 4.20, ROAD_END),
                        0.30, 0.0, 0.17, pale))
    # paved highway, laid as real stones, with the cart ruts worn through it
    p += flagstones("rd_fs", Ts(0, 0, DECK + 0.004), 8.10, 33.75, ROAD_END - 0.10,
                    MAT["cobble"], rng, cw=0.80, cl=0.62, h=0.05)
    for s in (-1, 1):
        p.append(box("rd_rut%d" % s, Ts(s * 0.78, (33.60 + ROAD_END) * 0.5,
                                       DECK + 0.056),
                     (0.34, ROAD_END - 33.60, 0.006), MAT["stone_dark"]))
    # the far abutment, buried under the joint
    p.append(box("rd_ab", Ts(0, 31.20, MOAT_BED * 0.5),
                 (9.20, 0.95, abs(MOAT_BED) + 0.02), sd, bev=0.02))

    # ---- city street and the plaza --------------------------------------
    p.append(_prism_z("ct_st", [(-STREET_X, BACK_Y), (STREET_X, BACK_Y),
                                (STREET_X, PLAZA_Y), (-STREET_X, PLAZA_Y)],
                      0.0, DECK, cob))
    p.append(_prism_z("ct_pl", [(-11.0, PLAZA_Y), (11.0, PLAZA_Y),
                                (11.0, -GH_D), (-11.0, -GH_D)], 0.0, DECK, cob))
    for s in (-1, 1):
        p.append(_strip("ct_kr%d" % s, (s * STREET_X, BACK_Y), (s * STREET_X, PLAZA_Y),
                        0.30, 0.0, 0.17, pale))
        p.append(_strip("ct_kp%d" % s, (s * 11.0, PLAZA_Y), (s * 11.0, -GH_D),
                        0.30, 0.0, 0.17, pale))
    # paving in front of the gate, laid as real stones
    p += flagstones("ct_fs0", Ts(0, 0, DECK + 0.005), 10.10, BACK_Y + 0.10, -22.10,
                    MAT["cobble"], rng, cw=0.86, cl=0.66, h=0.05)
    p += flagstones("ct_fs1", Ts(0, 0, DECK + 0.005), 21.0, PLAZA_Y + 0.4, -GH_D + 0.4,
                    MAT["cobble"], rng, cw=0.94, cl=0.74, h=0.05)
    p += flagstones("ct_fs2", Ts(0, 0, DECK + 0.005), 9.6, -22.0, PLAZA_Y - 0.2,
                    MAT["cobble"], rng, cw=0.90, cl=0.72, h=0.05)
    # stone aprons at the two tower doors
    for s in (-1, 1):
        p.append(_prism_z("ct_ap%d" % s,
                          [(s * 10.6, -GH_D - 0.6), (s * 18.4, -GH_D - 0.6),
                           (s * 18.4, -11.2), (s * 10.6, -11.2)],
                          0.0, 0.08, pale))
    return p


# --------------------------------------------------------------------------
#  props: the road is alive, the gate is guarded
# --------------------------------------------------------------------------
def _hut(name, T, w, d, h, MAT):
    p = []
    sw, wd, pale = MAT["stone_warm"], MAT["wood_dark"], MAT["stone_pale"]
    p.append(box(name + "_w", T @ Ts(0, 0, h * 0.5), (w, d, h), sw, bev=0.02))
    p += gable_roof(name + "_rf", T @ Ts(0, 0, h), w, d, h * 0.34, MAT["tile_blue"], wd)
    p.append(box(name + "_d", T @ Ts(0, -d * 0.5 - 0.02, 0.90), (0.90, 0.10, 1.80),
                 wd, bev=0.01))
    p.append(box(name + "_dm", T @ Ts(0, -d * 0.5 - 0.08, 1.86), (1.10, 0.10, 0.12),
                 pale))
    for s in (-1, 1):
        p.append(box(name + "_sh%d" % s, T @ Ts(s * w * 0.30, -d * 0.5 - 0.03, 1.45),
                     (0.70, 0.06, 0.60), MAT["glass"]))
    return p


def _market_stall(name, T, MAT, rng, w=2.40, d=1.50):
    """A market stall in which every part is carried by another part.

    Posts stand on the ground, the counter board is pierced by the posts, the
    awning frame rests on the post tops, both canvas slopes overlap that frame
    and the valance hangs off their front edge.  (The kit stall in hd_common
    leaves its awning 0.25 m clear of everything, which the geometric audit
    rightly reports as a floating part.)
    """
    wd, cr = MAT["wood"], MAT["wood_dark"]
    cloth, cloth2 = MAT["banner_red"], MAT["banner_blue"]
    p = []
    px, py = w * 0.42, d * 0.42
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(cyl("%s_p%d%d" % (name, sx, sy),
                         T @ Ts(sx * px, sy * py, 1.12), 0.062, 2.24, wd, seg=8))
    p.append(box(name + "_top", T @ Ts(0, 0, 1.02), (w, d, 0.09), cr, bev=0.01))
    p.append(box(name + "_apr", T @ Ts(0, -d * 0.5, 0.86), (w * 0.92, 0.06, 0.30), wd))
    # awning frame, sitting on the post tops
    for sx in (-1, 1):
        p.append(box("%s_fr%d" % (name, sx), T @ Ts(sx * (w * 0.5), 0, 2.16),
                     (0.09, d + 0.52, 0.09), cr))
    for sy in (-1, 1):
        p.append(box("%s_fc%d" % (name, sy), T @ Ts(0, sy * (d * 0.5 + 0.26), 2.16),
                     (w + 0.14, 0.09, 0.09), cr))
    # two canvas slopes meeting at a ridge over the frame
    half = d * 0.5 + 0.26
    ang = math.atan2(0.26, half)
    for sy in (-1, 1):
        p.append(box("%s_aw%d" % (name, sy),
                     T @ Ts(0, sy * half * 0.5, 2.29, rx=-sy * ang),
                     (w + 0.62, half + 0.08, 0.035), cloth))
    p.append(box(name + "_val", T @ Ts(0, half + 0.02, 1.99),
                 (w + 0.62, 0.035, 0.38), cloth2))
    for i in range(7):
        x = (i - 3) * (w + 0.62) / 7.0
        p.append(box("%s_sc%d" % (name, i), T @ Ts(x, half + 0.02, 1.72),
                     ((w + 0.62) / 9.0, 0.04, 0.24), cloth, bev=0.008))
    # goods on the counter and sacks on the ground
    goods = (MAT["tile"], MAT["plaster"], MAT["wood_dark"], MAT["tile_blue"])
    for i in range(4):
        x = -w * 0.30 + i * w * 0.20
        p.append(box("%s_g%d" % (name, i),
                     T @ Ts(x, rng.uniform(-0.18, 0.18), 1.15),
                     (0.30, 0.30, 0.20), goods[i]))
    for i, sx in enumerate((-1, 1)):
        p.append(sphere("%s_sk%d" % (name, i),
                        T @ Ts(sx * (w * 0.5 + 0.34), d * 0.30, 0.26), 0.27,
                        MAT["plaster"], seg=12, ring=8, squash=0.92))
    return p


def build_props(MAT, rng):
    p = []
    iron, wd, wood = MAT["iron_dark"], MAT["wood_dark"], MAT["wood"]
    st, pale = MAT["stone"], MAT["stone_pale"]
    # ---- just outside the barbican --------------------------------------
    for s in (-1, 1):
        p.append(cyl("pr_bol%d" % s, Ts(s * 3.90, 31.70, 0.30), 0.22, 0.70, st, seg=12))
        p.append(sphere("pr_bob%d" % s, Ts(s * 3.90, 31.70, 0.68), 0.22, pale, seg=12,
                        ring=6))
    p += _hut("pr_hut", Ts(-12.0, 36.20, 0), 3.20, 2.70, 2.50, MAT)
    p.append(H.lantern_post("pr_lp0", Ts(4.90, 33.20, 0.0), 3.10, iron, MAT["glow"]))
    p.append(H.lantern_post("pr_lp1", Ts(-4.90, 39.00, 0.0), 3.10, iron, MAT["glow"]))
    p.append(H.lantern_post("pr_lp2", Ts(4.90, 45.00, 0.0), 3.10, iron, MAT["glow"]))
    # fence along the meadow edge of the road
    for s in (-1, 1):
        for i in range(7):
            yy = 33.20 + i * 2.10
            p.append(box("pr_fp%d_%d" % (s, i), Ts(s * 5.30, yy, 0.52),
                         (0.13, 0.13, 1.04), wd))
        for k, zz in enumerate((0.46, 0.88)):
            p.append(box("pr_fr%d_%d" % (s, k), Ts(s * 5.30, 39.50, zz),
                         (0.09, 13.00, 0.10), wd))
    # a cart, coming in from the fields
    p.append(H.cart("pr_cart", Ts(-7.60, 41.20, 0.0, rz=PI + 0.55), wood, iron, L=2.6,
                    W=1.3))
    p.append(H.barrel("pr_br0", Ts(6.40, 36.20, 0.0), 0.34, 0.92, wood, iron))
    p.append(H.barrel("pr_br1", Ts(7.10, 36.55, 0.0), 0.32, 0.86, wood, iron))
    p.append(H.crate("pr_cr0", Ts(-5.90, 33.10, 0.0), 0.74, wood))
    p.append(H.haystack("pr_hay", Ts(-15.0, 41.0, 0.0), 2.30, 3.40, MAT["grass"]))
    # signpost at the fork
    p.append(cyl("pr_sp", Ts(-6.10, 32.30, 1.35), 0.09, 2.70, wd, seg=10))
    p.append(box("pr_sb0", Ts(-6.10, 32.18, 2.36), (1.20, 0.08, 0.30), wood, bev=0.01))
    p.append(box("pr_sb1", Ts(-6.10, 32.42, 1.94), (0.95, 0.08, 0.26), wood, bev=0.01))
    p.append(sphere("pr_sc", Ts(-6.10, 32.30, 2.78), 0.14, iron, seg=10, ring=6))
    # milestone
    p.append(box("pr_ms", Ts(4.75, 35.80, 0.34), (0.52, 0.34, 0.68), pale, bev=0.02))
    p.append(box("pr_ms2", Ts(4.75, 35.80, 0.70), (0.60, 0.42, 0.08), st))

    # ---- inside the city ------------------------------------------------
    for i, (xx, yy) in enumerate(((7.60, -20.0), (-7.60, -26.0))):
        p += _market_stall("pr_mk%d" % i, Ts(xx, yy, DECK, rz=0.0 if xx > 0 else PI),
                           MAT, rng)
    p.append(H.barrel("pr_br2", Ts(-4.40, -15.20, 0.0), 0.34, 0.90, wood, iron))
    p.append(H.barrel("pr_br3", Ts(-3.60, -15.60, 0.0), 0.32, 0.86, wood, iron))
    p.append(H.crate("pr_cr1", Ts(4.60, -16.40, 0.0), 0.72, wood))
    p.append(H.crate("pr_cr2", Ts(4.60, -15.60, 0.0), 0.60, wood))
    for s in (-1, 1):
        p.append(H.lantern_post("pr_lc%d" % s, Ts(s * 5.80, -16.0, 0.0), 3.00, iron,
                                MAT["glow"]))
    p.append(box("pr_bench", Ts(-9.40, -12.40, DECK + 0.42), (0.50, 2.40, 0.14), wood,
                 bev=0.02))
    for yy in (-13.30, -11.50):
        p.append(box("pr_bl", Ts(-9.40, yy, DECK + 0.21), (0.44, 0.16, 0.42), wd))
    return p


# --------------------------------------------------------------------------
#  assembly
# --------------------------------------------------------------------------
def _flat(obs):
    """Recursive flatten of the part lists; drops None."""
    out = []
    for o in obs:
        if o is None:
            continue
        if isinstance(o, (list, tuple)):
            out += _flat(o)
        else:
            out.append(o)
    return out


def build(MAT, rng, **kw):
    """Return every object of the gate complex (origin at the footprint centre,
    +Y out of the city, ground at z = 0)."""
    with_ground = kw.get("with_ground", True)
    with_props = kw.get("with_props", True)
    obs = []
    obs += build_gatehouse(MAT, rng)
    # The passage fittings (floor, side ashlar, barrel vault, ribs and bosses,
    # the portcullis in its chase, the windlass, the doors, the wall lamps) were
    # written but never called from here, so the gate had no floor at all: the
    # meadow showed straight through the tunnel and only the barbican grille
    # existed.  Dead code is not a feature.
    obs += build_passage(MAT, rng)
    for s in (-1, 1):
        obs += build_tower(MAT, rng, s)
        obs += build_curtain(MAT, rng, s)
        obs += build_stair(MAT, rng, s)
    obs += build_barbican(MAT, rng)
    obs += build_drawbridge(MAT, rng)
    if with_ground:
        obs += build_ground(MAT, rng)
    if with_props:
        obs += build_props(MAT, rng)
    return _flat(obs)


def footprint():
    """(x, y) extent of the whole complex in metres."""
    return (2.0 * (CURT_X1 + 2.95), MOAT_B + 1.90 - (-16.40))


def eval_tris(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in objs:
        if ob is None or ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


# --------------------------------------------------------------------------
#  preview-only context: a slice of the city behind the gate
# --------------------------------------------------------------------------
def _tree(name, x, y, r, MAT):
    """A tree whose seven canopy lobes all sit on one trunk.

    (The original loop put the main lobe on MAT["grass"], so the biggest blob
    rendered as an untextured balloon while only the small ones were leaf.)
    """
    p = []
    wd, leaf = MAT["wood_dark"], MAT["leaf"]
    trunk_h = 2.60 + r * 0.45
    p.append(cyl(name + "_tr", Ts(x, y, trunk_h * 0.5), 0.20 + r * 0.03,
                 trunk_h, wd, seg=8))
    for k, (ox, oy, oz, sc) in enumerate(((0.00, 0.00, 0.00, 0.84),
                                          (0.62, 0.12, -0.30, 0.66),
                                          (-0.55, -0.26, -0.24, 0.62),
                                          (0.14, -0.60, 0.30, 0.56),
                                          (-0.20, 0.52, 0.42, 0.52),
                                          (0.46, 0.50, -0.06, 0.48),
                                          (-0.42, 0.26, -0.50, 0.44))):
        p.append(sphere(name + "_c%d" % k,
                        Ts(x + ox * r, y + oy * r, trunk_h + r * 0.55 + oz * r),
                        r * sc, leaf, seg=12, ring=8, squash=0.86))
    return p


def _context(MAT, rng):
    p = []
    pl, tile, ti, wd = MAT["plaster"], MAT["tile"], MAT["tile_blue"], MAT["wood_dark"]
    for i in range(7):
        for s in (-1, 1):
            x = s * (13.5 + rng.uniform(0.0, 1.6) + (i % 3) * 2.4)
            y = -16.0 - i * 5.6
            w = rng.uniform(6.0, 8.4)
            d = rng.uniform(5.2, 6.6)
            h = rng.uniform(5.0, 7.6)
            T = Ts(x, y, 0, rz=rng.uniform(-0.10, 0.10))
            p.append(box("cx_w%d_%d" % (i, s), T @ Ts(0, 0, h * 0.5), (w, d, h), pl,
                         bev=0.02))
            p += gable_roof("cx_r%d_%d" % (i, s), T @ Ts(0, 0, h), w, d,
                            rng.uniform(1.8, 2.6), tile if i % 2 else ti, wd)
            p.append(box("cx_pl%d_%d" % (i, s), T @ Ts(0, 0, 0.28),
                         (w + 0.16, d + 0.16, 0.56), MAT["stone_dark"]))
            for k in range(2):
                p.append(box("cx_wn%d_%d_%d" % (i, s, k),
                             T @ Ts(-w * 0.22 + k * w * 0.44, -d * 0.5 - 0.02,
                                    h * 0.58), (1.10, 0.10, 1.50), MAT["glass"]))
            if i % 3 == 0:
                p.append(H.chimney("cx_ch%d_%d" % (i, s), T @ Ts(w * 0.26, d * 0.18, h),
                                   2.20, MAT["stone_dark"], pots=2))
    # a town gate closing the view down the street, so the axial view out of
    # the passage ends in architecture instead of empty meadow
    Tt = Ts(0, -46.80, 0)
    p.append(H.prism("cx_tg", Tt, arch_notch_poly(8.20, 8.20, 2.10, 2.60, seg=18), 1.30,
                     MAT["stone_warm"], axis="y"))
    for s in (-1, 1):
        p.append(cyl("cx_tgt%d" % s, Ts(s * 8.10, -46.80, 4.20), 1.90, 8.40,
                     MAT["stone_warm"], seg=20))
        p.append(cone("cx_tgr%d" % s, Ts(s * 8.10, -46.80, 8.35), 2.16, 2.60,
                      MAT["slate"], seg=20))
    # The notion of the town gate was right, the execution was not: the arch was
    # left open, so the axial view out of the great passage went straight through
    # both openings at 120 m of bare meadow and read as a green pane standing in
    # the gate.  Shut the leaves, iron-band them and hang a lamp over them, so
    # the view ends on wood and warm light like every other gate in the module.
    _dr, _dz = 2.06, 2.60
    _dp = [(-_dr, 0.0), (_dr, 0.0)]
    _dp += [(_dr * math.cos(PI * k / 16.0), _dz + _dr * math.sin(PI * k / 16.0))
            for k in range(17)]
    p.append(H.prism("cx_tgd", Ts(0, -46.66, 0), _dp, 0.26, MAT["wood_dark"],
                     axis="y"))
    for i, zz in enumerate((1.05, 2.20, 3.35)):
        p.append(box("cx_tgb%d" % i, Ts(0, -46.72, zz), (4.12, 0.10, 0.20),
                     MAT["iron_dark"]))
    p.append(box("cx_tgs", Ts(0, -46.72, 2.10), (0.09, 0.14, 4.18),
                 MAT["iron_dark"]))
    p.append(box("cx_tglb", Ts(0, -46.58, 5.06), (0.10, 0.62, 0.10),
                 MAT["iron_dark"]))
    p.append(sphere("cx_tgl", Ts(0, -46.24, 4.98), 0.20, MAT["lamp"], seg=12,
                    ring=8))
    # a green and a few trees along the approach
    p.append(_plane("cx_gr", -26.0, 26.0, 33.0, 40.0, 0.02, MAT["grass"], t=0.04))
    for i, (x, y, r) in enumerate(((16.5, 45.0, 2.0), (-17.0, 48.0, 2.2),
                                   (22.0, 41.0, 1.8), (-23.0, 40.0, 2.0),
                                   (-28.0, 50.5, 2.3), (28.0, 50.5, 2.1),
                                   (31.0, 34.0, 1.7), (-31.0, 34.5, 1.8))):
        p += _tree("cx_tr%d" % i, x, y, r, MAT)
    # Meadow clumps.  In every wide shot the open ground was an empty green
    # plane with a straight horizon; a few clumps give it scale, and a horizon
    # to measure the drums against.  Kept clear of the road and of both the
    # `road` and `a` camera positions so nothing blocks a delivery frame.
    _ti = 0
    for cx0, cy0, cn in ((72.0, 34.0, 6), (88.0, 10.0, 5), (-70.0, 26.0, 6),
                         (-84.0, 44.0, 5), (60.0, -34.0, 5), (-64.0, -30.0, 5),
                         (58.0, 66.0, 4), (-58.0, 62.0, 4)):
        for _k in range(cn):
            _x = cx0 + (0.0 if not _k else rng.uniform(-7.0, 7.0))
            _y = cy0 + (0.0 if not _k else rng.uniform(-6.0, 6.0))
            p += _tree("cx_mt%d" % _ti, _x, _y, rng.uniform(1.9, 3.1), MAT)
            _ti += 1
    # distant hills so the meadow does not end in a razor-straight horizon
    for i, (x, y, r, h) in enumerate(((-190.0, -175.0, 120.0, 20.0),
                                      (20.0, -235.0, 150.0, 27.0),
                                      (185.0, -160.0, 105.0, 17.0),
                                      (-300.0, -30.0, 130.0, 23.0),
                                      (280.0, -60.0, 125.0, 21.0),
                                      (-120.0, 195.0, 100.0, 14.0),
                                      (95.0, 205.0, 110.0, 16.0))):
        p.append(sphere("cx_hill%d" % i, Ts(x, y, 0.0), r, MAT["hill"],
                        seg=20, ring=12, squash=h / r))
    return p


# --------------------------------------------------------------------------
#  lighting and cameras
# --------------------------------------------------------------------------
def _lights(MAT):
    def lamp(name, loc, energy, size=0.6, color=(1.0, 0.72, 0.42)):
        ld = bpy.data.lights.new(name, "POINT")
        ld.energy = energy
        ld.color = color
        ld.shadow_soft_size = size
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        bpy.context.collection.objects.link(ob)
        return ob
    # the passage, the barbican tunnel and the ward.  The lamp colour used to be
    # (1.0, 0.72, 0.42): strong enough in the orange that a stone vault read as a
    # brown wooden tube.  A little whiter and a lot brighter keeps the firelight
    # warmth without turning the ashlar to mud.
    for i, (yy, zz, e) in enumerate(((-5.00, 3.10, 85.0), (-1.20, 3.10, 85.0),
                                     (2.80, 3.10, 85.0), (6.90, 3.10, 70.0))):
        lamp("lt_ps%d" % i, (0.0, yy, zz), e, 0.6, (1.0, 0.82, 0.60))
    lamp("lt_bg0", (0.0, 22.15, 3.00), 150.0, 0.7, (1.0, 0.84, 0.66))
    lamp("lt_wd0", (0.0, 15.00, 4.20), 150.0, 1.2, (1.0, 0.90, 0.80))
    lamp("lt_wd1", (-5.30, 13.30, 2.10), 40.0, 0.4)

    def area(name, loc, energy, size, color=(1.0, 0.93, 0.82)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.shape = "SQUARE"
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        bpy.context.collection.objects.link(ob)
        return ob

    # skylight falling into the ward: enough to read, not enough to flatten it
    for i, yy in enumerate((12.4, 18.6)):
        area("lt_wa%d" % i, (0.0, yy, 10.4), 420.0, 6.0)
    area("lt_wb0", (0.0, 1.0, 12.0), 420.0, 8.0)
    # a soft fill from the city side so the back never goes black
    ld = bpy.data.lights.new("fill_city", "SUN")
    ld.energy = 1.10
    ld.angle = math.radians(12.0)
    ld.color = (0.72, 0.82, 1.0)
    ob = bpy.data.objects.new("fill_city", ld)
    ob.rotation_euler = (math.radians(58.0), 0.0, math.radians(198.0))
    bpy.context.collection.objects.link(ob)
    # The key sun comes from the city side, so every camera on the road side
    # (`south`, `a`, `b`, `road`) looked at an unlit grey box: no relief in the
    # ashlar, no modelling on the drums.  A shadowless counter-fill from the
    # front costs nothing and is the difference between a flat elevation and a
    # gatehouse.
    ld = bpy.data.lights.new("fill_front", "SUN")
    ld.energy = 1.55
    ld.angle = math.radians(20.0)
    ld.color = (1.0, 0.95, 0.88)
    if hasattr(ld, "use_shadow"):
        ld.use_shadow = False
    ob = bpy.data.objects.new("fill_front", ld)
    ob.rotation_euler = (math.radians(-62.0), 0.0, math.radians(14.0))
    bpy.context.collection.objects.link(ob)


SHOTS = [
    ("a",        (52.0, 78.0, 22.0),   (0.0, 10.0, 14.0),  45.0),
    ("b",        (0.0, 104.0, 12.0),   (0.0, 12.0, 13.0),  45.0),
    ("c",        (-50.0, 72.0, 38.0),  (0.0, 10.0, 13.0),  45.0),
    ("south",    (0.0, 112.0, 7.00),   (0.0, 10.0, 13.0),  38.0),
    ("road",     (34.0, 74.0, 14.0),   (0.0, 16.0, 9.0),   40.0),
    ("portal",   (0.0, 44.00, 2.00),   (0.0, 6.0, 6.00),   45.0),
    ("through",  (0.0, 36.50, 1.70),   (0.0, -20.0, 3.20), 40.0),
    ("arch",     (5.50, 26.00, 3.00),  (0.0, 22.6, 5.40),  50.0),
    ("barbican", (17.0, 12.0, 26.0),   (0.0, 15.5, 3.50),  40.0),
    ("back",     (0.0, -33.0, 1.90),   (0.0, -2.0, 9.00),  45.0),
    ("city",     (-17.0, -29.0, 10.0), (0.0, 0.0, 12.0),   42.0),
    ("citywide", (-46.0, -46.0, 26.0), (0.0, 2.0, 12.0),   45.0),
    ("top",      (34.0, 54.0, 68.0),   (0.0, 10.0, 8.0),   45.0),
    ("ward",     (0.0, 8.20, 5.40),    (0.0, 22.5, 4.40),  32.0),
    ("porch",    (0.0, 12.90, 2.00),   (0.0, 9.10, 6.20),  60.0),
    ("moat",     (22.0, 36.50, 3.20),  (-3.0, 24.5, 0.20), 40.0),
]

WIDE = [
    ("w_a",  (78.0, 120.0, 34.0),  (0.0, 12.0, 12.0),  55.0),
    ("w_b",  (0.0, 150.0, 26.0),   (0.0, 14.0, 12.0),  62.0),
    ("w_c",  (16.0, 44.0, 118.0),  (0.0, 4.0, 6.0),    42.0),
]


def preview(samples=64, res=(1400, 900), final=False, only=None, wide_only=False):
    import random
    H._clear()
    MAT = materials()
    rng = random.Random(20261030)
    obs = build(MAT, rng)
    nparts = len([o for o in obs if o is not None])
    ntris = sum(len(o.data.loop_triangles) if o.data.loop_triangles else 0
                for o in obs if o is not None and o.type == "MESH")
    for o in obs:
        if o is not None and o.type == "MESH":
            o.data.calc_loop_triangles()
    ntris = sum(len(o.data.loop_triangles) for o in obs
                if o is not None and o.type == "MESH")
    neval = eval_tris(obs)
    lo, hi = H.bbox(obs)
    print("[gate] parts=%d tris=%d tris_eval=%d" % (nparts, ntris, neval), flush=True)
    print("[gate] bbox lo=(%.2f, %.2f, %.2f) hi=(%.2f, %.2f, %.2f)"
          % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]), flush=True)

    _context(MAT, rng)
    H.setup_world(sun_energy=4.2, sky="#9fc4e8", fill=0.0)
    _lights(MAT)
    H.setup_engine(samples=samples, res=res, gpu=True)
    shots = WIDE if wide_only else SHOTS
    for name, loc, look, lens in shots:
        if only and name not in only:
            continue
        cam = H.camera("cam_" + name, loc, look, lens)
        H.render_to(os.path.join(OUT_DIR, "hd_gate_%s.png" % name), cam)
        print("[gate] wrote %s" % name, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--stats" in argv or "--quick" in argv:
        H._clear()
        _m = materials()
        _r = __import__("random").Random(20261030)
        _o = build(_m, _r)
        for _ob in _o:
            if _ob is not None and _ob.type == "MESH":
                _ob.data.calc_loop_triangles()
        _nt = sum(len(_ob.data.loop_triangles) for _ob in _o
                  if _ob is not None and _ob.type == "MESH")
        _ne = eval_tris(_o)
        _lo, _hi = H.bbox(_o)
        print("[gate] stats parts=%d tris=%d tris_eval=%d" % (len(_o), _nt, _ne),
              flush=True)
        print("[gate] bbox lo=(%.2f, %.2f, %.2f) hi=(%.2f, %.2f, %.2f)"
              % (_lo[0], _lo[1], _lo[2], _hi[0], _hi[1], _hi[2]), flush=True)
        print("[gate] footprint=(%.1f, %.1f)" % footprint(), flush=True)
        if "--stats" in argv:
            sys.exit(0)
        sys.exit(0)
    preview(samples=192 if "--final" in argv else 64,
            res=(1600, 900) if "--final" in argv else (1400, 900),
            final="--final" in argv,
            only=None, wide_only="--wide" in argv)


# ==========================================================================
#  GATE v3 -- 2026-11-02
#
#  The 2026-10 handoff lists three P0s on this landmark:
#    1. moat water cutting the turret bases ("角楼顶是敞口水池"),
#    2. a portcullis floating 155 px above the passage floor,
#    3. a gatehouse that does not read as "a gate" from the game camera.
#  The legacy builders above are the record of two earlier passes; they stay in
#  the file but nothing calls them any more -- build_gatehouse() and build()
#  are redefined at the end of this block.
#
#  Public contract (unchanged, capital_hd_glue.gatehouse() depends on it):
#      build_gatehouse(MAT, rng) -> [bpy MESH, ...] in the local frame
#          origin = threshold centre at ground, +Y out of the city, -Y in.
#  New, for whoever owns the curtain wall:
#      curtain_run(name, p0, p1, MAT, rng, out=(ox,oy), ...) -> [MESH, ...]
#      gate_keepout() -> [(x, y, r), ...] circles the moat must not flood
#      g3_weather(MAT) -> MAT      (hd_surface.apply_weathering wrapper)
#
#  Why it now reads as a gate at the 52 deg / 34 m game camera: two battered
#  drums stand 1.3 m PROUD of the wall face and 4.5 m into the moat, so the
#  16.4 m passage mouth sits in a shadow slot between two round masses; the
#  grille is down on a stone sill; the dropped drawbridge with slack chains
#  spans the water; every mass is a closed solid.
# ==========================================================================

G3 = {
    # passage (clear opening) ------------------------------------------------
    "R_PASS": 3.40, "Z_SPRING": 4.60,          # crown at 8.00
    "Y_OUT": 7.40, "Y_IN": -9.00,              # 16.4 m of depth
    # gate body (the block the passage is pierced through) -------------------
    "BW": 15.40, "BZ": 14.20,
    # drum towers -----------------------------------------------------------
    "TOW_R": 5.30, "TOW_X": 11.60, "TOW_Y": 3.40,
    "TOW_TOP": 18.60, "TOW_PAR": 21.05, "TUR_Z": 16.80, "TUR_H": 6.40,
    # upper storey over the passage ----------------------------------------
    "UP_HW": 6.60, "UP_Y0": -2.60, "UP_Y1": 3.40, "UP_TOP": 27.40,
    "ROOF_H": 6.30,                            # 27.40 + 6.30 = 33.70 m
    # moat ------------------------------------------------------------------
    "MOAT_Y0": 6.40, "MOAT_Y1": 18.20, "MOAT_X": 46.00,
    "WATER_Z": -0.62, "BED_Z": -2.60, "QUAY_Z": 0.14,
    # curtain wall ----------------------------------------------------------
    "CURT_H": 10.00, "CURT_T": 2.40, "CURT_X1": 15.20,
    "BAST_W": 8.00, "BAST_D": 3.40, "BAST_UP": 1.40,
    # threshold / portcullis ------------------------------------------------
    "SILL_Z": 0.52, "SILL_W": 1.10, "SILL_Y": 4.20,
}
# the plinth radius of a drum at water level, and the radius the moat water
# mesh is cut away by (plinth + 0.3 m of joint + 0.15 m of tolerance)
G3["WATER_R"] = G3["TOW_R"] + 2.05 - 0.50 * (1.0 + G3["WATER_Z"] / 2.90)
G3["KEEP_R"] = G3["WATER_R"] + 0.55


_G3_CACHE = {}


def _g3_mat(key, **spec):
    m = _G3_CACHE.get(key)
    if m is None:
        m = _stone_mat("gate3_" + key, **spec)
        _G3_CACHE[key] = m
    return m


def _g3_P(MAT):
    """The caller's palette + the handful of materials only the gate needs.

    It never builds the module's own palette when a caller hands one in: those
    materials are shared with every house in the city, and re-tuning them from
    here would repaint the capital.
    """
    P = dict(MAT) if MAT else materials()
    st = P.get("stone")
    if st is None:
        st = _g3_mat("stone", base="#7d7466", dark="#544e42", light="#948b7c", scale=1.0)
    for k in ("stone", "stone_warm", "stone_dark", "stone_pale", "iron", "iron_dark",
              "wood", "wood_dark", "tile", "slate", "gold", "plaster", "banner_red",
              "banner_blue", "water", "cobble", "glow", "glass", "ground", "grass",
              "earth"):
        if P.get(k) is None:
            P[k] = st
    if P.get("void") is None:
        P["void"] = _g3_mat("void", base="#101116", dark="#07080b", light="#1a1c22",
                            scale=4.0, rough=0.86, bump=0.0)
    if P.get("floor_wet") is None:
        P["floor_wet"] = _g3_mat("floor_wet", base="#6e6656", dark="#403a30",
                                 light="#8d8474", scale=1.9, rough=0.32, bump=0.09)
    if P.get("sill") is None:
        P["sill"] = _g3_mat("sill", base="#918a77", dark="#615a4b",
                            light="#aaa28d", scale=3.4, rough=0.60, bump=0.18)
    if P.get("gate_shaft") is None:
        P["gate_shaft"] = _g3_mat("shaft", base="#837a6b", dark="#5a5346",
                                  light="#9b9282", scale=1.6, rough=0.86, bump=0.20)
    if P.get("moss") is None:
        P["moss"] = _g3_mat("moss", base="#3d4a2c", dark="#242e1a",
                            light="#556439", scale=1.1, rough=0.96, bump=0.34)
    if P.get("wet_shelf") is None:
        P["wet_shelf"] = _g3_mat("wetshelf", base="#48433a", dark="#28251e",
                                 light="#5f584a", scale=2.2, rough=0.26, bump=0.10)
    return P


def g3_weather(MAT, strength=1.0, seed=7):
    """Age a MAT dict in place with hd_surface (idempotent, never raises)."""
    try:
        import hd_surface as SFC
        SFC.apply_weathering(MAT, strength=strength, seed=seed)
    except Exception as exc:                                    # noqa: BLE001
        print("[gate3] weathering skipped: %s: %s" % (type(exc).__name__, exc),
              flush=True)
    return MAT


# --------------------------------------------------------------------------
#  small local-frame helpers
# --------------------------------------------------------------------------
def _g3_pyr(name, T, hw, hd, z0, h, mat):
    """Four-sided pyramid, eave at z0, apex at z0+h."""
    v = [(-hw, -hd, z0), (hw, -hd, z0), (hw, hd, z0), (-hw, hd, z0), (0.0, 0.0, z0 + h)]
    f = [(0, 3, 2, 1), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return _mk(name, v, f, mat, T)


def _g3_loop(name, T, MAT, w=0.22, h=1.30, d=0.60, idx=0):
    """An arrow loop: a dark slot sunk into the wall plus a pale splayed surround.

    No boolean: the slot is a void box seated 0.06 m behind the face, which at
    any distance past 8 m is indistinguishable from a real cut and cannot leave
    a hole in the wall if the mesh is later joined.
    """
    dark = MAT["void"]
    pale = MAT["stone_pale"]
    p = [box(name + "_v%d" % idx, T @ Ts(0.0, -d * 0.5 - 0.02, 0.0), (w, d, h), dark)]
    for k, (dx, dz, sx, sz) in enumerate((
            (-w * 0.5 - 0.075, 0.0, 0.15, h + 0.30),
            (w * 0.5 + 0.075, 0.0, 0.15, h + 0.30),
            (0.0, h * 0.5 + 0.085, w + 0.30, 0.17),
            (0.0, -h * 0.5 - 0.085, w + 0.30, 0.17))):
        p.append(box(name + "_f%d_%d" % (idx, k), T @ Ts(dx, 0.015, dz),
                     (sx, 0.11, sz), pale, bev=0.012))
    return p


def _g3_batter(name, T, L, y_face, zB, bat, mat, rng, bh=0.55, bw=1.55, y_back=0.70):
    """Coursed blocks stepping back on a battered face (the wall footing).

    The face at height z is at y = y_face + bat * (1 - z/zB); each course is a
    row of blocks whose outer plane is that face at the row's bottom, so the
    courses read as a rustic footing instead of a sloped plastic skirt.
    """
    v, f = [], []
    z = 0.0
    row = 0
    while z < zB - 0.04:
        hh = min(bh, zB - z)
        yf = y_face + bat * (1.0 - z / zB)
        x = -L * 0.5 - (bw * 0.45 if row % 2 else 0.0) - rng.uniform(0.0, 0.24)
        while x < L * 0.5 - 0.05:
            ww = bw * rng.uniform(0.80, 1.25)
            a = max(x, -L * 0.5)
            b = min(x + ww, L * 0.5)
            if b - a > 0.20:
                _blk(v, f, a + 0.012, b - 0.012, yf - y_back, yf,
                     z + 0.012, z + hh - 0.012)
            x += ww
        z += hh
        row += 1
    return [_mk(name, v, f, mat, T)]


def _g3_courses(name, MAT, rng, cx, cy, r_base, r_top, z0, z1, a0=0.0, a1=TAU,
                bh=0.42, thin=0.075, big=None):
    """Proud stone courses round a drum, radius interpolated per course.

    The radius is recomputed for every course, so a battered shaft steps back
    like real coursed masonry instead of carrying a cylinder of stones that
    would float off a taper.
    """
    out = []
    z = z0
    i = 0
    while z < z1 - 0.10:
        hh = min(bh, z1 - z)
        t = 0.0 if z1 <= z0 else (z + hh * 0.5 - z0) / (z1 - z0)
        r = r_base + (r_top - r_base) * t
        n = max(6, int((a1 - a0) * r / 1.05))
        out += ring_stones(name + "_c%d" % i,
                           Ts(cx, cy, 0.0, rz=0.0), r, z, n, hh,
                           MAT["stone"], MAT["stone_warm"] if not big else big,
                           rng, thick=thin, a0=a0, a1=a1, b_frac=0.14)
        z += hh
        i += 1
    return out


# --------------------------------------------------------------------------
#  the parts
# --------------------------------------------------------------------------
def _g3_arch_head(name, T, r, zs, h, y0, y1, mat, seg=28):
    """The spandrel above a round-headed opening, as a closed shell.

    hd_common.prism() triangulates its cap with a fan, so a concave notch comes
    back FILLED -- which is how the previous gate ended up with a stone disc
    sealing its own passage.  This builds the one genuinely non-convex piece by
    hand: two fan caps around a point that sees the whole arc, plus the outer
    rim.  The soffit is left open on purpose: arch_tube() lines it.
    """
    v, f = [], []
    n = max(6, seg)

    def cap(y, flip):
        base = len(v)
        v.append((-r, y, h))                                   # 0: fan apex
        v.append((r, y, h))                                    # 1
        for i in range(n + 1):
            a = PI * i / n
            v.append((r * math.cos(a), y, zs + r * math.sin(a)))   # 2..n+2
        for i in range(1, n + 1):
            tri = (base, base + i, base + i + 1)
            f.append(tri[::-1] if flip else tri)
        return base

    a0 = cap(y0, False)
    a1 = cap(y1, True)
    f.append((a0, a1, a1 + 1, a0 + 1))                         # top face
    f.append((a0 + 1, a0 + 2, a1 + 2, a1 + 1))                 # right cheek
    f.append((a0, a0 + n + 2, a1 + n + 2, a1))                 # left cheek
    return _mk(name, v, f, mat, T)


def _g3_patches(name, T, w, h, mat, rng, n=None, proud=0.022, z0=0.0):
    """Sparse proud blocks: repairs and replacements, not a full ashlar sheet.

    The coursing itself comes from hd_surface's weathered material; a full
    geometric ashlar on top of it doubles the joints and reads as a white grid
    (exactly the 2026-10 complaint about this facade).
    """
    v, f = [], []
    n = int(max(4, w * h / 12.0)) if n is None else n
    for _ in range(n):
        bw2 = rng.uniform(0.70, 1.85)
        bh2 = rng.uniform(0.30, 0.55)
        if w - bw2 < 0.1 or h - bh2 < 0.05:
            continue
        x = rng.uniform(-w * 0.5 + bw2 * 0.5, w * 0.5 - bw2 * 0.5)
        z = z0 + rng.uniform(0.0, max(0.01, h - bh2))
        pr = proud * rng.uniform(0.35, 1.15)
        _blk(v, f, x - bw2 * 0.5, x + bw2 * 0.5, -0.07, pr, z, z + bh2)
    return [_mk(name, v, f, mat, T)]


def _g3_banner(name, T, P, cloth, cloth_h=3.40, w=0.90):
    """A cloth banner hung flat on a wall from an iron rod.

    Deliberately LOW: at the game camera's 52 deg pitch the top of the frame is
    8 m up the facade, so anything hung at 12 m is never seen by a player.
    """
    p = [box(name + "_rod", T @ Ts(0.0, 0.12, 0.12), (w + 0.34, 0.09, 0.09),
             P["iron_dark"])]
    for s in (-1, 1):
        p.append(box(name + "_br%d" % (s + 2),
                     T @ Ts(s * (w * 0.5 + 0.13), 0.02, 0.12),
                     (0.08, 0.34, 0.08), P["iron_dark"]))
    p.append(box(name + "_cl", T @ Ts(0.0, 0.17, -cloth_h * 0.5 + 0.05),
                 (w, 0.05, cloth_h), cloth))
    p.append(box(name + "_hm", T @ Ts(0.0, 0.19, -cloth_h + 0.14),
                 (w + 0.05, 0.07, 0.20), P["gold"]))
    return _flat(p)


def _g3_pole(name, T, P, h=4.60, cloth=None):
    """A painted banner pole: the cheapest vertical that shouts 'gate'."""
    p = [cyl(name + "_p", T @ Ts(0.0, 0.0, h * 0.5), 0.085, h, P["wood_dark"], seg=8)]
    p.append(cone(name + "_t", T @ Ts(0.0, 0.0, h + 0.16), 0.10, 0.32, P["gold"], seg=8))
    p.append(box(name + "_cl", T @ Ts(0.34, 0.0, h - 0.80), (0.66, 0.04, 1.40),
                 cloth or P["banner_red"]))
    return _flat(p)


def g3_body(P, rng, **kw):
    """The pierced block: 30.8 m wide, 16.4 m deep, 14.2 m to the wall walk.

    It is assembled from three CONVEX masses (two piers and the spandrel), so
    the opening is a real hole and not a triangulated disc.
    """
    bw, bz = G3["BW"], G3["BZ"]
    r, zs = G3["R_PASS"], G3["Z_SPRING"]
    y0, y1 = G3["Y_IN"], G3["Y_OUT"]
    mid = (y0 + y1) * 0.5
    p = []
    for s, tag in ((-1, "l"), (1, "r")):
        p.append(box("g3_pier_" + tag, Ts(s * (bw + r) * 0.5, mid, bz * 0.5),
                     (bw - r, y1 - y0, bz), P["stone_dark"]))
        p += _g3_patches("g3_front_" + tag,
                         Ts(s * (bw + r) * 0.5, y1 + 0.004, 0.0), bw - r, bz,
                         P["stone"], rng, n=int((bw - r) * bz / 7.0))
        # a battered foot across each pier face: the facade has a base, and the
        # foot frames the mouth without stepping into the roadway
        p += _g3_batter("g3_fbat_" + tag, Ts(s * (bw + r) * 0.5, y1, 0.0),
                        bw - r, 0.0, 1.45, 0.50, P["stone_warm"], rng,
                        bh=0.34, bw=1.75, y_back=0.40)
    p.append(_g3_arch_head("g3_head", Ts(0.0, 0.0, 0.0), r, zs, bz, y0, y1,
                           P["stone_dark"], seg=30))
    p += _g3_patches("g3_front_top", Ts(0.0, y1 + 0.004, 0.0), 2.0 * r, bz - zs - r,
                     P["stone_warm"], rng, n=26, z0=zs + r)
    # arch order: voussoirs 0.55 m deep standing proud of the face
    p.append(voussoir_ring("g3_arch", Ts(0.0, y1 - 0.06, zs), r + 0.02, 0.55, 25,
                           P["stone"], y=0.0, zc=0.0, thick=0.34, gap=0.020))
    p.append(arch_band("g3_archband", Ts(0.0, 0.0, zs), r + 0.02, r + 0.60,
                       y1 - 0.14, y1 - 0.02, P["stone_dark"], seg=28, zc=0.0))
    # jambs: dressed ashlar lining the outer 0.9 m of each reveal
    for s, tag in ((-1, "l"), (1, "r")):
        p += ashlar("g3_jamb_" + tag,
                    Ts(s * (r + 0.30 - 0.275), y1 - 0.45, 0.0, rz=s * PI * 0.5),
                    0.90, zs, P["stone"], rng, bw=0.72, bh=0.44, gap=0.014,
                    proud=0.018, z0=0.0, y_in=-0.06)
    # crest over the arch, at the height the road actually sees
    p += coat_of_arms("g3_crest", Ts(0.0, y1 + 0.02, 9.95), 1.34, P)
    # two long banners flanking the mouth at eye level, in the band of the
    # facade the game camera can actually see
    for s, mat in ((-1, P["banner_red"]), (1, P["banner_blue"])):
        p += _g3_banner("g3_banm%d" % (s + 2), Ts(s * 5.35, y1, 8.30), P, mat)
    # string course under the wall walk, and the parapet over it
    p.append(box("g3_bcord", Ts(0.0, y1 + 0.09, bz - 1.02),
                 (2.0 * bw, 0.22, 0.34), P["stone"], bev=0.02))
    p.append(box("g3_bpar", Ts(0.0, 1.0, bz + 0.42), (2.0 * bw, 1.05, 0.84),
                 P["stone"], bev=0.02))
    p += crenel_line("g3_bcren", Ts(0.0, 0.15, bz + 0.84), 2.0 * bw - 0.4,
                     P["stone"], merlon=1.42, gap=0.62, h=1.20, depth=1.05)
    return p


def g3_passage(P, rng, **kw):
    """Floor, sill, dark vault lining, ribs, the inner portal and two lamps."""
    r, zs = G3["R_PASS"], G3["Z_SPRING"]
    y0, y1 = G3["Y_IN"], G3["Y_OUT"]
    mid = (y0 + y1) * 0.5
    half = (y1 - y0) * 0.5
    p = []
    # floor: wet courses, so the arch mouth throws a reflection on the ground
    p += flagstones("g3_floor", Ts(0.0, mid, 0.0), 2.0 * r + 0.02, -half, half,
                    P["floor_wet"], rng, cw=1.22, cl=0.92, gap=0.026, h=0.18)
    # the portcullis sill: the grille lands on THIS, not on air
    sz = G3["SILL_Z"]
    sy = G3["SILL_Y"]
    p.append(box("g3_sill", Ts(0.0, sy, sz * 0.5), (2.0 * r + 0.20, G3["SILL_W"], sz),
                 P["sill"], bev=0.03))
    p.append(box("g3_sill_lip", Ts(0.0, sy - G3["SILL_W"] * 0.5 - 0.09, 0.06),
                 (2.0 * r + 0.20, 0.18, 0.12), P["stone_dark"], bev=0.02))
    # dark vault: a lining exactly filling the 0.30 m chase left by the cut
    p.append(arch_tube("g3_vault", Ts(0.0, 0.0, zs), r, 0.0, y0, y1, 0.30,
                       P["stone_dark"], seg=26))
    for s in (-1, 1):
        p.append(box("g3_wall%d" % (s + 2), Ts(s * (r + 0.15), mid, zs * 0.5),
                     (0.30, y1 - y0, zs), P["stone_dark"]))
    # transverse ribs every 3.2 m: the cheapest depth cue in a dark tunnel
    n = 0
    yy = y0 + 1.8
    while yy < y1 - 1.2:
        p.append(arch_tube("g3_rib%d" % n, Ts(0.0, 0.0, zs), r - 0.13, 0.0,
                           yy - 0.17, yy + 0.17, 0.13, P["stone"], seg=20))
        yy += 3.2
        n += 1
    # the city end is pierced by a smaller postern, 4.70 x 3.90, with a timber
    # lintel.  A far opening the same size as the near one is what made the
    # passage read as a pipe; this leaves one small bright patch low in frame
    # and a dark vault above it.
    ri_i, zi_i = 2.35, 3.90
    p.append(box("g3_imass", Ts(0.0, y0 + 0.55, (zi_i + G3["BZ"]) * 0.5),
                 (2.0 * G3["R_PASS"], 1.10, G3["BZ"] - zi_i), P["stone_dark"]))
    for s in (-1, 1):
        p.append(box("g3_ipier%d" % (s + 2),
                     Ts(s * (G3["R_PASS"] + ri_i) * 0.5, y0 + 0.55, zi_i * 0.5),
                     (G3["R_PASS"] - ri_i, 1.10, zi_i), P["stone_dark"]))
    p.append(box("g3_ilint", Ts(0.0, y0 + 0.55, zi_i + 0.19),
                 (2.0 * ri_i + 0.60, 1.15, 0.38), P["wood_dark"], bev=0.02))
    # inner portal: the doors are folded back against the passage walls, and
    # the tunnel stays open to the ward behind them
    for s, tag in ((-1, "l"), (1, "r")):
        p.append(box("g3_leaf_" + tag,
                     Ts(s * (r - 0.22), y0 + 2.20, 2.10, rz=s * 0.10),
                     (0.16, 3.70, 4.20), P["wood_dark"], bev=0.03))
        for k, zz in enumerate((0.70, 2.10, 3.50)):
            p.append(box("g3_leafb_%s%d" % (tag, k),
                         Ts(s * (r - 0.13), y0 + 2.20, zz, rz=s * 0.10),
                         (0.07, 3.55, 0.16), P["iron_dark"], bev=0.01))
    # two wall lanterns: the warm pool they throw on the wet flags is what makes
    # the mouth read as depth rather than as a hole
    for i, yy2 in enumerate((y0 + 3.4, y1 - 3.4)):
        p.append(cyl("g3_lp%d" % i, Ts(-r + 0.42, yy2, 0.0), 0.075, 3.05,
                     P["iron_dark"], seg=8))
        p.append(box("g3_lb%d" % i, Ts(-r + 0.42, yy2, 3.10), (0.34, 0.34, 0.16),
                     P["iron_dark"], bev=0.01))
        p.append(box("g3_lg%d" % i, Ts(-r + 0.42, yy2, 2.96), (0.26, 0.26, 0.24),
                     P["glow"]))
    return p


def g3_towers(P, rng, **kw):
    """Two battered drums, 1.3 m proud of the wall face, standing in the moat."""
    R = G3["TOW_R"]
    cx = G3["TOW_X"]
    cy = G3["TOW_Y"]
    top = G3["TOW_TOP"]
    bed = G3["BED_Z"] - 0.30
    # a stepped footing rather than a cone -- two wide steps and one long
    # batter, because five equal steps read as a wedding cake
    prof = [
        (R + 1.90, bed), (R + 1.90, -0.55), (R + 1.45, -0.55),
        (R + 1.45, 0.80), (R + 1.05, 0.80), (R, 3.90), (R, 16.40),
        (R + 0.30, 16.40), (R + 0.30, 16.85), (R, 16.85),
        (R, top), (R + 0.62, top + 0.35), (R + 0.62, top + 0.75),
        (R + 0.36, G3["TOW_PAR"]),
    ]
    p = []
    for s, tag in ((-1, "w"), (1, "e")):
        x = s * cx
        p.append(H.lathe("g3_tow_" + tag, prof, P["gate_shaft"], seg=44,
                         T=Ts(x, cy, 0.0), close_bottom=True, close_top=False))
        # the parapet walk, so the drum is not an open pipe from above
        p.append(cyl("g3_towdeck_" + tag, Ts(x, cy, G3["TOW_PAR"] - 0.08), R + 0.34,
                     0.16, P["cobble"], seg=40))
        p.append(rcrenel("g3_towcr_" + tag, Ts(x, cy, 0.0), R + 0.36,
                         G3["TOW_PAR"], 15, merlon=1.28, gap=0.56, h=1.32,
                         depth=0.56, mat=P["stone"]))
        # coursing on a cylinder: a per-block ring of stones reads as fish
        # scales at 480p, and the weathered brick smears along a lathe, so the
        # drum gets fine course lines instead -- 18 hairlines that read as
        # coursed ashlar from 20 m and cost 2.5k tris a tower.
        def _rr(z):
            if z <= 0.80:
                return R + 1.45
            if z <= 3.90:
                return R + 1.05 - (z - 0.80) / 3.10 * 1.05
            return R
        for zc in (4.60, 8.55, 12.45):
            p.append(torus("g3_towband_%s_%d" % (tag, int(zc * 10)), Ts(x, cy, zc),
                           R + 0.045, 0.075, P["stone_warm"], seg=40, ring=6))
        for i in range(18):
            zc = 4.75 + i * 0.65
            p.append(torus("g3_towcl_%s_%d" % (tag, i), Ts(x, cy, zc),
                           _rr(zc) - 0.018, 0.042, P["stone_dark"],
                           seg=30, ring=5))
        # string course at 16.4 m
        p.append(torus("g3_towsc_" + tag, Ts(x, cy, 16.58), R + 0.10, 0.11,
                       P["stone_pale"], seg=40, ring=6))
        # arrow loops on the field side (angles measured from +X)
        for i, (a, z) in enumerate(((PI * 0.5 - 0.72, 6.30),
                                    (PI * 0.5 - 0.26, 6.30),
                                    (PI * 0.5 + 0.26, 6.30),
                                    (PI * 0.5 + 0.72, 6.30),
                                    (PI * 0.5 - 0.42, 9.55),
                                    (PI * 0.5 + 0.42, 9.55),
                                    (PI * 0.5, 12.60))):
            p += _g3_loop("g3_tlp_" + tag, face_T(x, cy, 0.0, a, R, lift=0.02),
                          P, w=0.20, h=1.24, d=0.52, idx=i)
        # the corner bartizan: the silhouette spike that says "gatehouse"
        p.append(H.round_tower("g3_tur_" + tag,
                               Ts(x + s * (R - 0.55), cy - 0.85, G3["TUR_Z"]),
                               1.16, G3["TUR_H"], P["stone"],
                               roof_mat=P["slate"], cap="cone", cone_h=2.55))
        # machicolation corbels under the parapet
        p.append(rcrenel("g3_corb_" + tag, Ts(x, cy, 0.0), R + 0.66,
                         top + 0.02, 22, merlon=0.20, gap=0.62, h=0.34,
                         depth=0.60, mat=P["stone_dark"]))
    return p


def g3_upper(P, rng, **kw):
    """The storey over the passage, its roof, two windows and the banners."""
    hw = G3["UP_HW"]
    y0, y1 = G3["UP_Y0"], G3["UP_Y1"]
    z0, zt = G3["BZ"] - 0.30, G3["UP_TOP"]
    p = []
    p.append(box("g3_up", Ts(0.0, (y0 + y1) * 0.5, (z0 + zt) * 0.5),
                 (2.0 * hw, y1 - y0, zt - z0), P["stone_pale"], bev=0.05))
    # corner pilasters
    for sx in (-1, 1):
        for sy, yy in ((-1, y0 + 0.30), (1, y1 - 0.30)):
            p.append(box("g3_pil_%d%d" % (sx + 1, sy + 1),
                         Ts(sx * (hw - 0.24), yy, (z0 + zt) * 0.5),
                         (0.62, 0.62, zt - z0), P["stone"], bev=0.03))
    # cornice + pyramid roof + finial
    p.append(box("g3_corn", Ts(0.0, (y0 + y1) * 0.5, zt + 0.22),
                 (2.0 * hw + 0.72, y1 - y0 + 0.72, 0.44), P["stone"], bev=0.02))
    p.append(_g3_pyr("g3_roof", Ts(0.0, (y0 + y1) * 0.5, 0.0), hw + 0.26,
                     (y1 - y0) * 0.5 + 0.26, zt + 0.44, G3["ROOF_H"], P["slate"]))
    p.append(sphere("g3_fin", Ts(0.0, (y0 + y1) * 0.5, zt + 0.44 + G3["ROOF_H"] + 0.16),
                    0.20, P["gold"], seg=12, ring=8))
    p.append(cone("g3_fink", Ts(0.0, (y0 + y1) * 0.5,
                                zt + 0.44 + G3["ROOF_H"] + 0.62),
                  0.075, 0.62, P["gold"], seg=8))
    # windows on the front, one above the other
    p.append(H.window_arched("g3_win1", Ts(0.0, y1, 18.85), 1.55, 2.70,
                             P["stone_pale"], P["glass"], tracery=2))
    for sx in (-1, 1):
        p.append(H.window_arched("g3_win2_%d" % (sx + 1), Ts(sx * 3.9, y1, 23.10),
                                 1.15, 2.10, P["stone_pale"], P["glass"], tracery=1))
    # banners on the front face, both sides of the crest
    for sx, mat in ((-1, P["banner_red"]), (1, P["banner_blue"])):
        p.append(H.banner("g3_ban_%d" % (sx + 1), Ts(sx * 9.4, G3["Y_OUT"], 12.20),
                          0.92, 2.60, mat, P["iron_dark"]))
    return p


def _g3_grille(name, T, w, z_floor, z_top, zc, r, MAT, n=11, rails=6):
    """An iron grille that provably touches the floor.

    The legacy portcullis() measured its lowest point from an internal offset
    and settled 0.55 m INTO the sill; every bar here is built from z_floor and
    every spear point is a hand-made pyramid whose apex is exactly z_floor, so
    the measured gap to the sill is 0.000 by construction.
    """
    iron, iron2 = MAT["iron"], MAT["iron_dark"]
    p = []
    pitch = w / float(n - 1)
    for i in range(n):
        x = -w * 0.5 + i * pitch
        ins = r * r - x * x
        if ins <= 0.04:
            continue
        zt = min(z_top, zc + math.sqrt(ins) - 0.06)
        if zt <= z_floor + 0.42:
            continue
        p.append(box(name + "_b%d" % i, T @ Ts(x, 0.0, (z_floor + 0.30 + zt) * 0.5),
                     (0.085, 0.085, zt - z_floor - 0.30), iron))
        v = [(x - 0.055, -0.055, z_floor + 0.30), (x + 0.055, -0.055, z_floor + 0.30),
             (x + 0.055, 0.055, z_floor + 0.30), (x - 0.055, 0.055, z_floor + 0.30),
             (x, 0.0, z_floor)]
        f = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2, 1)]
        p.append(_mk(name + "_t%d" % i, v, f, iron2, T))
    for k in range(rails):
        z = z_floor + 0.55 + (z_top - z_floor - 0.55) * (k / float(max(1, rails - 1)))
        ins = r * r - (z - zc) ** 2
        if ins <= 0.09:
            continue
        hw = min(w * 0.5 + 0.05, math.sqrt(ins) - 0.06)
        if hw <= 0.30:
            continue
        p.append(box(name + "_r%d" % k, T @ Ts(0.0, 0.01, z), (2.0 * hw, 0.095, 0.11),
                     iron))
    # stiles and the iron channels bolted to each jamb; both stop on the sill
    for s in (-1, 1):
        x = s * (w * 0.5 + 0.10)
        p.append(box(name + "_st%d" % s, T @ Ts(x, 0.0, (z_floor + z_top) * 0.5),
                     (0.14, 0.14, z_top - z_floor), iron2))
        p.append(box(name + "_ch%d" % s, T @ Ts(x, 0.02, (z_floor + z_top) * 0.5),
                     (0.30, 0.24, z_top - z_floor), iron2, bev=0.01))
    return p


def g3_portcullis(P, rng, **kw):
    """The grille, DOWN, its spear points on the sill.  Nothing hangs in air."""
    r, zs = G3["R_PASS"], G3["Z_SPRING"]
    p = _g3_grille("g3_pc", Ts(0.0, G3["SILL_Y"], 0.0), w=2.0 * r - 0.18,
                   z_floor=G3["SILL_Z"], z_top=zs + r, zc=zs, r=r, MAT=P,
                   n=11, rails=6)
    return p


def g3_bridge(P, rng, **kw):
    """The dropped drawbridge: deck, trestles, and two slack chains."""
    y_out, y_in = G3["Y_OUT"], G3["MOAT_Y1"]
    w = 5.40
    zt = 0.58
    p = []
    # deck, in three leaves so the timber reads
    span = y_in - y_out + 0.70
    p.append(box("g3_deck", Ts(0.0, y_out + span * 0.5, zt - 0.16),
                 (w, span, 0.32), P["wood"], bev=0.02))
    for i in range(11):
        yy = y_out + 0.35 + i * (span - 0.6) / 10.0
        p.append(box("g3_pl%d" % i, Ts(0.0, yy, zt - 0.02), (w - 0.06, 0.30, 0.09),
                     P["wood_dark"]))
    for s in (-1, 1):
        p.append(box("g3_beam%d" % (s + 2), Ts(s * (w * 0.5 - 0.22),
                                              y_out + span * 0.5, zt - 0.40),
                     (0.30, span, 0.26), P["wood_dark"], bev=0.02))
    # two trestles standing in the bed: the deck does not float over the water
    for i, yy in enumerate((10.4, 14.6)):
        for s in (-1, 1):
            p.append(box("g3_post%d%d" % (i, s + 2), Ts(s * (w * 0.5 - 0.55), yy,
                                                       (G3["BED_Z"] + zt) * 0.5 - 0.15),
                         (0.26, 0.26, zt - G3["BED_Z"] + 0.30), P["wood_dark"]))
        p.append(box("g3_brk%d" % i, Ts(0.0, yy, zt - 0.52),
                     (w - 0.70, 0.22, 0.22), P["wood_dark"]))
    # slack chains from the tower faces down to the deck's outer corners
    for s in (-1, 1):
        p0 = Vector((s * (G3["TOW_X"] - G3["TOW_R"] * 0.55), G3["TOW_Y"] + 4.6, 13.40))
        p1 = Vector((s * (w * 0.5 - 0.10), y_in - 0.15, zt + 0.62))
        p += chain("g3_chain%d" % (s + 2), p0, p1, 0.85, P["iron_dark"],
                   links=24, R=0.115, r=0.042)
    # banner poles at the bridgehead: from the approach they frame the mouth
    for s in (-1, 1):
        p += _g3_pole("g3_bpo%d" % (s + 2), Ts(s * 4.15, y_in + 1.05, G3["QUAY_Z"]),
                      P, cloth=P["banner_red"] if s < 0 else P["banner_blue"])
    # a stone abutment on the far bank, so the bridge lands on something
    p.append(box("g3_abut", Ts(0.0, y_in + 0.30, (G3["QUAY_Z"] + zt) * 0.5 - 0.10),
                 (w + 1.60, 1.30, abs(zt - G3["QUAY_Z"]) + 0.60),
                 P["stone_pale"], bev=0.03))
    return p


# --------------------------------------------------------------------------
#  the moat (lab + hand-off to hd_river)
# --------------------------------------------------------------------------
def gate_keepout():
    """Circles the moat water must be cut away by, in the gate's local frame."""
    return [(-G3["TOW_X"], G3["TOW_Y"], G3["KEEP_R"]),
            (G3["TOW_X"], G3["TOW_Y"], G3["KEEP_R"])]


def _g3_water(name, P, x0, x1, y0, y1, keep, cell=0.80):
    """One water mesh with the tower plinths bitten out of it.

    Every cell whose centre falls inside a keep-out circle is dropped, so no
    part of the water plane can pass through a plinth.  The jagged rim this
    leaves is hidden under the wet shelf the drums get (see g3_moat).
    """
    v, f = [], []
    nx = max(1, int((x1 - x0) / cell))
    ny = max(1, int((y1 - y0) / cell))
    dx = (x1 - x0) / nx
    dy = (y1 - y0) / ny
    for j in range(ny):
        cy = y0 + (j + 0.5) * dy
        for i in range(nx):
            cx = x0 + (i + 0.5) * dx
            hit = False
            for (kx, ky, kr) in keep:
                if (cx - kx) ** 2 + (cy - ky) ** 2 < kr * kr:
                    hit = True
                    break
            if hit:
                continue
            b = len(v)
            v.extend([(cx - dx * 0.5, cy - dy * 0.5, 0.0),
                      (cx + dx * 0.5, cy - dy * 0.5, 0.0),
                      (cx + dx * 0.5, cy + dy * 0.5, 0.0),
                      (cx - dx * 0.5, cy + dy * 0.5, 0.0)])
            f.append((b, b + 1, b + 2, b + 3))
    return [_mk(name, v, f, P["water"], Ts(0.0, 0.0, G3["WATER_Z"]))]


def g3_moat(P, rng, x_half=None, **kw):
    """Channel, revetments, bed, water cut round the plinths, wet shelves."""
    mx = G3["MOAT_X"] if x_half is None else x_half
    y0, y1 = G3["MOAT_Y0"], G3["MOAT_Y1"]
    wz, bz, qz = G3["WATER_Z"], G3["BED_Z"], G3["QUAY_Z"]
    p = []
    # bed + revetments
    p.append(_plane("g3_bed", -mx, mx, y0, y1, bz + 0.30, P["moss"], t=0.60))
    p.append(box("g3_rev_in", Ts(0.0, y0 + 0.45, (bz + qz) * 0.5),
                 (2.0 * mx, 0.90, qz - bz), P["stone_dark"]))
    p.append(box("g3_rev_out", Ts(0.0, y1 - 0.45, (bz + qz) * 0.5),
                 (2.0 * mx, 0.90, qz - bz), P["stone_dark"]))
    p.append(box("g3_cop_in", Ts(0.0, y0 + 0.45, qz + 0.09),
                 (2.0 * mx, 1.15, 0.18), P["stone_pale"], bev=0.02))
    p.append(box("g3_cop_out", Ts(0.0, y1 - 0.45, qz + 0.09),
                 (2.0 * mx, 1.15, 0.18), P["stone_pale"], bev=0.02))
    # the waterline apron round each drum: wet stone, not a lawn.  It hides the
    # scalloped rim the water grid leaves, and the moss is a single hairline at
    # the waterline itself rather than a 1.5 m green ring.
    for i, (kx, ky, kr) in enumerate(gate_keepout()):
        prof = [(G3["WATER_R"] - 0.36, 0.0), (kr + 0.65, 0.0),
                (kr + 0.65, 0.07), (G3["WATER_R"] - 0.36, 0.11)]
        p.append(H.lathe("g3_shelf%d" % i, prof, P["wet_shelf"], seg=40,
                         T=Ts(kx, ky, wz), close_bottom=False, close_top=False))
        p.append(torus("g3_algae%d" % i, Ts(kx, ky, wz + 0.02),
                       G3["WATER_R"] + 0.06, 0.075, P["moss"], seg=36, ring=5))
    # water
    p += _g3_water("g3_water", P, -mx, mx, y0, y1, gate_keepout(), cell=0.80)
    # end walls, so the channel does not simply stop in mid-air
    for s in (-1, 1):
        p.append(box("g3_mw%d" % (s + 2), Ts(s * (mx - 0.45), (y0 + y1) * 0.5,
                                             (bz + qz) * 0.5),
                     (0.90, y1 - y0, qz - bz), P["stone_dark"]))
    return p


# --------------------------------------------------------------------------
#  curtain wall run
# --------------------------------------------------------------------------
def curtain_run(name, p0, p1, MAT, rng, out=None, h=None, t=None,
                crenels=True, bastions=True, step=30.0, ashl=True, batter=True):
    """One straight curtain-wall run between two polyline points.

    Local frame: X along p0->p1 (origin at the middle), +Y = outward.  `out`
    is an (ox, oy) hint for the outward direction; the default is the
    right-hand normal of p0->p1 ((dy, -dx)), which is outward for a ring that
    is walked clockwise seen from above.  Returns [MESH, ...] already baked in
    world space, so it can be dropped straight into a city build.
    """
    P = _g3_P(MAT)
    h = G3["CURT_H"] if h is None else h
    t = G3["CURT_T"] if t is None else t
    x0, y0 = p0[0], p0[1]
    dx, dy = p1[0] - x0, p1[1] - y0
    L = math.hypot(dx, dy)
    if L < 1.0:
        return []
    # local +Y must be the outward direction and local +X the run direction.
    # The run is centred on the MIDPOINT of p0/p1: centring on p0+L/2 put the
    # west wall at +14.8 and drove it straight across the gate.
    ux, uy = dx / L, dy / L
    ox, oy = -uy, ux                         # left normal of the run
    if out is not None:
        m = math.hypot(out[0], out[1]) or 1.0
        if (out[0] / m) * ox + (out[1] / m) * oy < 0.0:
            ox, oy = uy, -ux                 # right normal instead
    rz = math.atan2(-ox, oy)                 # local +Y -> (ox, oy)
    T = Ts((x0 + p1[0]) * 0.5, (y0 + p1[1]) * 0.5, 0.0, rz=rz)
    zB = 3.20
    bat = 0.92
    p = []
    # ---- body: vertical above zB, battered below
    prof = [(-t * 0.5, 0.0), (t * 0.5 + bat, 0.0), (t * 0.5, zB),
            (t * 0.5, h - 0.26), (-t * 0.5, h - 0.26)]
    p.append(H.prism(name + "_body", T, prof, L, P["stone_dark"], axis="x"))
    # ---- walk: 3.0 m slab, corbelled 0.6 m over the city side
    p.append(box(name + "_walk", T @ Ts(0.0, -0.30, h - 0.13), (L, 3.00, 0.26),
                 P["cobble"], bev=0.015))
    for i in range(max(2, int(L / 1.55))):
        x = -L * 0.5 + (i + 0.5) * (L / max(2, int(L / 1.55)))
        p.append(box(name + "_cb%d" % i, T @ Ts(x, -t * 0.5 - 0.10, h - 0.34),
                     (0.34, 0.62, 0.42), P["stone_pale"], bev=0.02))
    # ---- outer parapet + crenels
    if crenels:
        p.append(box(name + "_par", T @ Ts(0.0, t * 0.5 - 0.31, h + 0.40),
                     (L, 0.62, 0.80), P["stone"], bev=0.02))
        p += crenel_line(name + "_cr", T @ Ts(0.0, t * 0.5 - 0.31, h + 0.80), L,
                         P["stone"], merlon=1.44, gap=0.62, h=0.90, depth=0.62)
        # inner parapet (the low one you can lean on)
        p.append(box(name + "_inp", T @ Ts(0.0, -1.58, h + 0.45),
                     (L, 0.44, 0.90), P["stone"], bev=0.02))
    # ---- dressed facing on the field side: scattered repairs over the
    # material's own coursing, not a second grid of joints on top of it
    if ashl:
        p += _g3_patches(name + "_ash", T @ Ts(0.0, t * 0.5 + 0.004, 0.0), L,
                         h - zB, P["stone_warm"], rng, z0=zB, proud=0.045)
    if batter:
        p += _g3_batter(name + "_bat", T, L, t * 0.5, zB, bat, P["stone_warm"],
                        rng, bh=0.55, bw=1.60)
    # ---- arrow loops and drains
    nl = max(1, int(L / 9.5))
    for i in range(nl):
        x = -L * 0.5 + (i + 0.5) * (L / nl)
        p += _g3_loop(name + "_lp", T @ Ts(x, t * 0.5 + 0.004, 5.40), P,
                      w=0.21, h=1.28, d=0.56, idx=i)
    nd = max(1, int(L / 12.0))
    for i in range(nd):
        x = -L * 0.5 + (i + 0.6) * (L / nd)
        p.append(box(name + "_dr%d" % i, T @ Ts(x, t * 0.5 + 0.20, h - 0.62),
                     (0.24, 0.62, 0.24), P["stone_pale"], bev=0.02))
    # ---- bastions (马面)
    if bastions and L > 12.0:
        n = max(1, int(L / step))
        for i in range(n):
            xb = -L * 0.5 + (i + 0.5) * (L / n)
            p += _g3_bastion(name + "_ba%d" % i, T @ Ts(xb, 0.0, 0.0), P, rng,
                             t, h, bat)
    return _flat(p)


def _g3_bastion(name, T, P, rng, t, h, bat):
    """A solid rectagonal tower on the field face: stepped plinth, crenels, loops."""
    top = h + G3["BAST_UP"]
    d = G3["BAST_D"]
    hw = G3["BAST_W"] * 0.5
    y_back = -t * 0.5
    y_face = t * 0.5 + d
    p = []
    # a five-step plinth: each step is a real box, so the batter is coursed
    steps = 5
    zstep = 2.60 / steps
    for i in range(steps):
        fr = 1.0 - (i + 1.0) / steps
        wi = hw + 0.86 * fr
        yf = y_face + 0.86 * fr
        p.append(box(name + "_pl%d" % i,
                     T @ Ts(0.0, (y_back + yf) * 0.5, zstep * (i + 0.5)),
                     (2.0 * wi, yf - y_back, zstep + 0.02), P["stone_warm"],
                     bev=0.02))
    p.append(box(name + "_bd", T @ Ts(0.0, (y_back + y_face) * 0.5,
                                      (2.60 + top) * 0.5),
                 (2.0 * hw, y_face - y_back, top - 2.60), P["stone"], bev=0.03))
    # crenels on the three exposed sides
    p += crenel_line(name + "_crf", T @ Ts(0.0, y_face - 0.31, top), 2.0 * hw,
                     P["stone"], merlon=1.40, gap=0.60, h=1.10, depth=0.62)
    for s in (-1, 1):
        p += crenel_line(name + "_crs%d" % (s + 1),
                         T @ Ts(s * (hw - 0.31), (y_back + y_face) * 0.5, top),
                         y_face - y_back - 0.6, P["stone"], merlon=1.38, gap=0.60,
                         h=1.10, depth=0.62, axis="y")
    # two arrow loops on each storey of the field face
    for i, s in enumerate((-1, 1)):
        for j, z in enumerate((6.20, 9.00)):
            p += _g3_loop(name + "_bl%d%d" % (i, j),
                          T @ Ts(s * 2.20, y_face, z), P, w=0.21, h=1.26,
                          d=0.56, idx=j)
    return _flat(p)


# --------------------------------------------------------------------------
#  assembly
# --------------------------------------------------------------------------
def build_gatehouse(MAT, rng, **kw):
    """Return the gatehouse as a flat list of MESH objects in the local frame.

    Never raises: each stage is guarded, so one broken ornament cannot cost the
    city its gate (capital_hd_glue.guard() would otherwise drop all of it).
    """
    P = _g3_P(MAT)
    if kw.get("weather"):
        g3_weather(P, strength=kw.get("weather_strength", 1.0),
                   seed=kw.get("weather_seed", 7))
    out = []
    stages = (("body", g3_body), ("passage", g3_passage), ("towers", g3_towers),
              ("upper", g3_upper), ("portcullis", g3_portcullis),
              ("bridge", g3_bridge))
    for label, fn in stages:
        try:
            out += _flat(fn(P, rng, **kw))
        except Exception as exc:                                # noqa: BLE001
            print("[gate3] %s FAILED: %s: %s" % (label, type(exc).__name__, exc),
                  flush=True)
    return _flat(out)


def build(MAT, rng, **kw):
    """The whole 150 m slice: gate, two curtain runs, moat, banks, road.

    Origin at the threshold, +Y out of the city, ground at z = 0.  This is the
    lab scene; the city only ever calls build_gatehouse() and its own wall
    builder (curtain_run() is offered for that).
    """
    P = _g3_P(MAT)
    with_ground = kw.pop("with_ground", True)
    with_moat = kw.pop("with_moat", True)
    run = kw.pop("run", 60.0)
    obs = build_gatehouse(P, rng, **kw)
    obs += curtain_run("g3_curt_e", (G3["CURT_X1"], 0.0),
                       (G3["CURT_X1"] + run, 0.0), P, rng, out=(0.0, 1.0))
    obs += curtain_run("g3_curt_w", (-G3["CURT_X1"], 0.0),
                       (-G3["CURT_X1"] - run, 0.0), P, rng, out=(0.0, 1.0))
    if with_moat:
        obs += g3_moat(P, rng)
    if with_ground:
        try:
            obs += _g3_site(P, rng)
        except Exception as exc:                                # noqa: BLE001
            print("[gate3] site FAILED: %s: %s" % (type(exc).__name__, exc),
                  flush=True)
    return _flat(obs)


def _g3_site(P, rng):
    """Ground plates, the road, and the two stairs up to the wall walk."""
    obs = []
    mx = G3["MOAT_X"]
    # inside the ward (0.04 m under the passage flags, or they z-fight),
    # the berm plates, and the far bank
    obs.append(_plane("g3_g_in", -mx - 30.0, mx + 30.0, -46.0, G3["MOAT_Y0"],
                      -0.04, P["ground"], t=0.40))
    obs.append(_plane("g3_g_out", -mx - 30.0, mx + 30.0, G3["MOAT_Y1"], 62.0,
                      G3["QUAY_Z"], P["ground"], t=0.40))
    for s in (-1, 1):
        obs.append(_plane("g3_g_s%d" % (s + 2), s * mx, s * (mx + 30.0),
                          G3["MOAT_Y0"], G3["MOAT_Y1"], 0.0, P["ground"],
                          t=0.40))
    # the road: from the inner gate, over the bridge, and away
    obs.append(_plane("g3_road", -3.60, 3.60, G3["MOAT_Y1"], 60.0,
                      G3["QUAY_Z"] + 0.02, P["cobble"], t=0.10))
    obs.append(_plane("g3_road_in", -3.60, 3.60, -44.0, G3["Y_IN"],
                      0.02, P["cobble"], t=0.10))
    # stairs from the ward up to the wall walk: they run ALONG the inner face
    # (rz 0 / pi), not out into the moat, and land flush with the walk at 10 m
    for s in (-1, 1):
        obs.append(H.stairs("g3_st%d" % (s + 2),
                            Ts(s * 40.0, -2.35, 0.0, rz=0.0 if s > 0 else PI),
                            2.20, 40, rise=0.25, run=0.33, mat=P["stone"]))
    return obs


def footprint():
    """(x, y) extent of the whole lab complex in metres."""
    return (2.0 * (G3["CURT_X1"] + 60.0 + 2.4),
            G3["MOAT_Y1"] + 62.0 - (-46.0))

