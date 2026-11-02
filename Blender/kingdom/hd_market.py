"""hd_market.py - the three civic landmarks of the capital's great market square.

    market_hall(MAT, rng) -> list    # 40 x 22 m, arcaded ground floor, jettied
                                     # timber great hall, 3 dormers, ridge belfry
    guild_hall(MAT, rng)  -> list    # 18 x 28 m, ashlar base, two jetties,
                                     # pointed gable + crest facing the square
    fountain(MAT, rng)    -> list    # 12 x 12 m octagonal basin, 2 bowls, bronze figure
    preview()                        # all three side by side, 3 views + 2 close-ups

Conventions: metres, Blender Z up, every part built in WORLD space through a
4x4 matrix (objects keep identity transforms, as the kit does).

WHY THE FRONT FACES -Y
`hd_common.setup_world()` puts the sun at euler (52, 0, 38), i.e. its light
travels along (-0.485, +0.621, -0.616): the sun is in the sky to -Y, so faces
whose normal is -Y are the lit ones.  `hd_common.three_views()` puts all three
cameras in the -Y hemisphere as well.  Therefore -Y is the only direction that
is BOTH visible and lit, and every building here is authored with its front on
-Y (the square side).  The initial framework docstring says +Y is the front;
that is only true for the older street-frontage kit, and using it here would
render the market hall's arcade as a black void.

Run:
    blender -b --factory-startup --python hd_market.py
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
from medkit import T_at as Ts, box, cyl, cone, sphere

OUT = H.OUT_DIR
RZ = lambda a: Matrix.Rotation(a, 4, "Z")


# ==========================================================================
# materials
# ==========================================================================
def _water_mat():
    """Slightly transparent water with a rippling normal (wave texture bump)."""
    m = bpy.data.materials.new("mkt_water")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    nt = m.node_tree
    K._put(b, ["Roughness"], 0.055)
    K._put(b, ["Metallic"], 0.0)
    K._put(b, ["Base Color"], K.c("#1e444d"))
    K._put(b, ["Transmission Weight"], 0.48)
    K._put(b, ["IOR"], 1.33)
    K._put(b, ["Alpha"], 0.70)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.55, 0.55, 0.55)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "RINGS"
    wv.bands_direction = "Z"
    wv.inputs["Scale"].default_value = 1.9
    wv.inputs["Distortion"].default_value = 6.5
    wv.inputs["Detail"].default_value = 3.0
    wv.inputs["Detail Scale"].default_value = 1.4
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 12.0
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "ADD"
    mix.inputs["Fac"].default_value = 0.35
    nt.links.new(wv.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(nz.outputs["Color"], mix.inputs["Color2"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.30
    bump.inputs["Distance"].default_value = 0.02
    nt.links.new(mix.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def _jet_mat():
    """Falling water: nearly white, high transmission, faint emission.

    A water jet is aerated, so it scatters more than the basin surface and
    reads almost white against dark stone - the previous blue-grey made it
    look like plastic tubing.
    """
    m = bpy.data.materials.new("mkt_water_jet")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    K._put(b, ["Base Color"], K.c("#e6f2f2"))
    K._put(b, ["Roughness"], 0.05)
    K._put(b, ["Transmission Weight"], 0.75)
    K._put(b, ["IOR"], 1.33)
    K._put(b, ["Emission Color"], K.c("#cfe4e6"))
    K._put(b, ["Emission Strength"], 0.30)
    K._put(b, ["Alpha"], 0.45)
    return m


def _veil_mat():
    """The thin sheet of water sliding over a bowl lip: mostly transparent."""
    m = bpy.data.materials.new("mkt_water_veil")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    K._put(b, ["Base Color"], K.c("#dceeee"))
    K._put(b, ["Roughness"], 0.04)
    K._put(b, ["Transmission Weight"], 0.85)
    K._put(b, ["IOR"], 1.33)
    K._put(b, ["Emission Color"], K.c("#c9e0e2"))
    K._put(b, ["Emission Strength"], 0.18)
    K._put(b, ["Alpha"], 0.20)
    return m


def _interior_mat():
    """Lit shop interior seen through an opening: dim warm emission.

    An arcade 3 m deep under a 5 m ceiling gets almost no sky light, so every
    opening reads as a black hole.  A dim emissive card behind each doorway is
    the cheapest honest stand-in for a stall lit by its own lamps.
    """
    m = bpy.data.materials.new("mkt_interior")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    K._put(b, ["Base Color"], K.c("#2b1f15"))
    K._put(b, ["Roughness"], 0.78)
    K._put(b, ["Emission Color"], K.c("#b8824e"))
    K._put(b, ["Emission Strength"], 0.20)
    return m


def _glow_mat():
    """Lantern flame: warm emissive glass behind an iron cage."""
    m = bpy.data.materials.new("mkt_glow")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    K._put(b, ["Base Color"], K.c("#ffd9a0"))
    K._put(b, ["Roughness"], 0.30)
    K._put(b, ["Emission Color"], K.c("#ffc171"))
    K._put(b, ["Emission Strength"], 7.0)
    return m


def _glass_mat():
    """Leaded glass that reads as glass from 50 m: sky-tinted, slightly
    reflective, with a faint interior glow so openings never go pure black."""
    m = bpy.data.materials.new("mkt_glass")
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    K._put(b, ["Base Color"], K.c("#b6cbd4"))
    K._put(b, ["Roughness"], 0.06)
    K._put(b, ["Metallic"], 0.10)
    K._put(b, ["Emission Color"], K.c("#93b3c0"))
    K._put(b, ["Emission Strength"], 1.45)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noi = nt.nodes.new("ShaderNodeTexNoise")
    K._put(noi, ["Scale"], 13.0)
    K._put(noi, ["Detail"], 1.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.28
    ramp.color_ramp.elements[0].color = K.c("#9db6c2")
    ramp.color_ramp.elements[1].position = 0.74
    ramp.color_ramp.elements[1].color = K.c("#cfdfe6")
    nt.links.new(tc.outputs["Object"], noi.inputs["Vector"])
    nt.links.new(noi.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def make_materials():
    MAT = {}
    # ---- masonry -------------------------------------------------------
    # the capital's square is warm sandstone over grey rubble: the pale/warm
    # stones carry a sand cast so the arcades do not read as cold concrete
    MAT["stone"] = K.mat_stone()                                     # grey ashlar
    MAT["stone_warm"] = K.mat_stone("mkt_stone_sand", base="#a08a63", dark="#6b5a3c",
                                    light="#bfa87c", scale=2.0)
    MAT["stone_pale"] = K.mat_stone("mkt_stone_pale", base="#b3a68b", dark="#7d7359",
                                    light="#d0c3a4", scale=2.8)
    MAT["stone_dark"] = K.mat_stone("mkt_stone_dark", base="#7a7060", dark="#4d4638",
                                    light="#96907a", scale=1.8)
    MAT["plaster"] = K.mat_plaster()
    MAT["plaster_warm"] = K.mat_plaster("mkt_plaster_ochre", base="#ddcba4",
                                        dirt="#bda87f", scale=4.0)
    # ---- timber --------------------------------------------------------
    MAT["wood"] = K.mat_wood()
    MAT["wood_dark"] = K.mat_wood("mkt_timber_dark", base="#34200f", light="#4d3119",
                                  scale=12)
    MAT["wood_light"] = K.mat_wood("mkt_timber_light", base="#7d5c3c", light="#a07c50",
                                   scale=16)
    MAT["wood_pale"] = K.mat_wood("mkt_timber_pale", base="#a2855e", light="#c0a37a",
                                  scale=20)
    # ---- roofs ---------------------------------------------------------
    MAT["tile"] = K.mat_tile()
    MAT["tile_dark"] = K.mat_tile("mkt_tile_dark", base="#7d3524", dark="#56241a",
                                  light="#9c4a32")
    MAT["tile_blue"] = K.mat_tile("mkt_tile_blue", base="#3f4f66", dark="#293545",
                                  light="#58697f")
    # a lighter blue for alternating courses: at 90 m a roof needs a real value
    # split between neighbouring tiles or the courses disappear
    MAT["tile_blue_lt"] = K.mat_tile("mkt_tile_blue_lt", base="#5c7089",
                                     dark="#41546b", light="#7b8ea5")
    MAT["slate"] = K.mat_tile("mkt_slate", base="#4a5560", dark="#333c46", light="#5f6d7a")
    # ---- metal / glass -------------------------------------------------
    # daylight glass has to catch the sky, otherwise every window is a black
    # hole once the camera is more than 20 m away
    MAT["glass"] = _glass_mat()
    MAT["iron"] = K.mat_metal()
    MAT["iron_warm"] = K.mat_metal("mkt_iron_warm", base="#4a4038", rough=0.38)
    MAT["gold"] = K.mat_gold()
    MAT["bronze"] = K.mat_metal("mkt_bronze", base="#5c7a5e", rough=0.42)
    MAT["lead"] = K.mat_metal("mkt_lead", base="#6c6f74", rough=0.52)
    MAT["void"] = K.mat_metal("mkt_void", base="#111216", rough=0.92)
    # ---- cloth ---------------------------------------------------------
    MAT["banner_red"] = K.mat_cloth("banner_red", "#8e2b26")
    MAT["banner_blue"] = K.mat_cloth("banner_blue", "#26405e")
    MAT["banner_gold"] = K.mat_cloth("banner_gold", "#b08b2e")
    MAT["banner_green"] = K.mat_cloth("banner_green", "#2f4a34")
    MAT["canvas"] = K.mat_cloth("mkt_canvas", "#b9ac90")
    MAT["canvas_red"] = K.mat_cloth("mkt_canvas_red", "#a2483a")
    MAT["produce"] = [K.mat_cloth("mkt_prod_%d" % i, h) for i, h in enumerate(
        ("#b8843a", "#8e3f2f", "#5a7a44", "#c9a94e", "#6d4b2a", "#7d3350"))]
    # ---- water / ground ------------------------------------------------
    MAT["water"] = _water_mat()
    MAT["water_jet"] = _jet_mat()
    MAT["water_veil"] = _veil_mat()
    MAT["interior"] = _interior_mat()
    MAT["glow"] = _glow_mat()
    MAT["ground"] = K.mat_flag("mkt_flag", base="#7d7565", dark="#403a30",
                               light="#9d9483", scale=2.4)
    MAT["ground_worn"] = K.mat_flag("mkt_flag_worn", base="#8a8170", dark="#57503f",
                                    light="#ada18b", scale=3.2)
    return MAT


# ==========================================================================
# mesh helpers
# ==========================================================================
def _flat(seq):
    """hd_common primitives return either an object or a list of them; the
    landmark functions promise a flat list, so unnest and drop Nones."""
    out = []
    for x in seq:
        if isinstance(x, (list, tuple)):
            out.extend(_flat(x))
        elif x is not None:
            out.append(x)
    return out


def _loft(name, T, rings, mat, seg=20, fold=0.0, folds=6, smooth=True,
          cap_bottom=True, cap_top=True):
    """Surface of revolution-ish loft: rings = [(z, rx, ry), ...] with an
    optional cos(folds*a) radius ripple, which is what makes drapery read as
    cloth instead of a cone.  A 2-tuple ring is read as lathe-style (r, z)."""
    rings = [r if len(r) == 3 else (r[1], r[0], r[0]) for r in rings]
    verts, faces = [], []
    n = len(rings)
    for (z, rx, ry) in rings:
        for i in range(seg):
            a = 2.0 * math.pi * i / seg
            k = 1.0 + fold * math.cos(folds * a)
            verts.append((rx * k * math.cos(a), ry * k * math.sin(a), z))
    for j in range(n - 1):
        for i in range(seg):
            i2 = (i + 1) % seg
            faces.append((j * seg + i, j * seg + i2, (j + 1) * seg + i2, (j + 1) * seg + i))
    if cap_bottom:
        c = len(verts)
        verts.append((0.0, 0.0, rings[0][0]))
        for i in range(seg):
            faces.append((c, (i + 1) % seg, i))
    if cap_top:
        c = len(verts)
        verts.append((0.0, 0.0, rings[-1][0]))
        b = (n - 1) * seg
        for i in range(seg):
            faces.append((c, b + i, b + (i + 1) % seg))
    ob = H.poly(name, verts, faces, mat, T)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def _seg(name, T, p0, p1, w, d, mat, bev=0.0, y=0.0):
    """A bar between two points given in the local XZ plane of T."""
    x0, z0 = p0
    x1, z1 = p1
    dx, dz = x1 - x0, z1 - z0
    L = math.hypot(dx, dz)
    if L < 1e-5:
        return None
    return box(name, T @ Ts((x0 + x1) * 0.5, y, (z0 + z1) * 0.5,
                            ry=-math.atan2(dz, dx)), (L, d, w), mat, bev=bev)


def _oct_pts(r, phase=math.pi / 8.0, jitter=0.0, rng=None):
    pts = []
    for i in range(8):
        a = phase + i * math.pi / 4.0
        rr = r
        if jitter and rng is not None:
            rr = r * (1.0 + rng.uniform(-jitter, jitter))
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return pts


def _arch(name, T, span, z0, thick, depth, mat, n=11, bev=0.012):
    """Semicircular arch ring of properly rotated voussoirs, springing at z0."""
    r = span * 0.5
    R = r + thick * 0.5
    out = []
    for i in range(n):
        a0 = math.pi * i / n
        a1 = math.pi * (i + 1) / n
        a = (a0 + a1) * 0.5
        L = 2.0 * R * math.sin((a1 - a0) * 0.5) * 1.12
        out.append(box(name + "_v%d" % i,
                       T @ Ts(-math.cos(a) * R, 0.0, z0 + math.sin(a) * R,
                              ry=a - math.pi * 0.5),
                       (L, depth, thick), mat, bev=bev))
    return _flat(out)


def _arcade_bay(name, T, cx, span, z_s, z_top, pw, thick, depth, mat, hb):
    """One bay: two half-piers + rotated arch + masonry haunches."""
    out = []
    r = span * 0.5
    out += _arch(name + "_a", T @ Ts(cx, 0, 0), span, z_s, thick, depth, mat)
    R = r + thick
    z = z_s
    while z < z_top - 1e-4:
        h = min(0.30, z_top - z)
        zc = z + h * 0.5
        dz = zc - z_s
        if dz >= R:
            out.append(box(name + "_c%d" % int(z * 100), T @ Ts(cx, 0, zc),
                           (2 * hb, depth, h), mat, bev=0.008))
        else:
            xo = math.sqrt(max(0.0, R * R - dz * dz))
            if hb - xo > 0.07:
                w = hb - xo
                out.append(box(name + "_c%da" % int(z * 100),
                               T @ Ts(cx - (xo + w * 0.5), 0, zc), (w, depth, h),
                               mat, bev=0.006))
                out.append(box(name + "_c%db" % int(z * 100),
                               T @ Ts(cx + (xo + w * 0.5), 0, zc), (w, depth, h),
                               mat, bev=0.006))
        z += h
    return _flat(out)


# ==========================================================================
# window / door / timber helpers
# ==========================================================================
def _win(name, T, w, h, frame, glass, dark, lights=3, arch=True, depth=0.30,
         hood=False, sill=True, lead=True, jamb=0.20, mull=0.09):
    """Mullioned window in a local +Y wall face.  Opening base at z=0.

    `h` is the springing height for an arched head (crown = h + w/2) and the
    full height for a flat head.
    """
    out = []
    hw = w * 0.5
    out.append(box(name + "_rev", T @ Ts(0, -depth * 1.15, h * 0.5),
                   (w * 0.995, depth * 1.10, h + (hw if arch else 0.0)), dark))
    # glazing, one pane per light
    for i in range(lights):
        x = -hw + (i + 0.5) * w / lights
        out.append(box(name + "_g%d" % i, T @ Ts(x, -depth * 0.52, h * 0.5),
                       (w / lights * 0.90, 0.035, h * 0.94), glass))
    # lead cames
    if lead:
        n = max(2, int(h / 0.30))
        for k in range(1, n):
            out.append(box(name + "_ld%d" % k, T @ Ts(0, -depth * 0.46, h * k / n),
                           (w * 0.95, 0.03, 0.028), frame))
    # mullions + transom
    for i in range(1, lights):
        x = -hw + i * w / lights
        out.append(box(name + "_m%d" % i, T @ Ts(x, -depth * 0.40, h * 0.5),
                       (mull, 0.13, h), frame, bev=0.008))
    out.append(box(name + "_tr", T @ Ts(0, -depth * 0.40, h * 0.62),
                   (w, 0.12, 0.075), frame))
    # stone / wood surround
    for s in (-1, 1):
        out.append(box(name + "_j%d" % s, T @ Ts(s * (hw + jamb * 0.5), 0, h * 0.5),
                       (jamb, depth + 0.08, h + jamb), frame, bev=0.012))
    if sill:
        out.append(box(name + "_si", T @ Ts(0, 0.05, -0.08),
                       (w + jamb * 2.2, depth + 0.24, 0.15), frame, bev=0.015))
        out.append(box(name + "_sl", T @ Ts(0, 0.17, -0.17),
                       (w + jamb * 1.8, 0.26, 0.09), frame, bev=0.01))
    if arch:
        out += _arch(name + "_ar", T, w, h, jamb * 1.15, depth + 0.06, frame, n=9)
        out.append(box(name + "_ty", T @ Ts(0, -depth * 0.52, h + hw * 0.42),
                       (w * 0.92, 0.05, hw * 0.78), glass))
    if hood:
        out += _arch(name + "_hd", T, w + jamb * 2.4, h + 0.06, 0.16, depth + 0.18,
                     frame, n=9)
        for s in (-1, 1):
            out.append(box(name + "_ls%d" % s,
                           T @ Ts(s * (hw + jamb * 1.2), 0.06, h + 0.06),
                           (0.24, 0.30, 0.22), frame, bev=0.02))
    return _flat(out)


def _oriel(name, T, w, h, d, wood, glass, dark, lights=3, sill_mat=None):
    """Projecting bay window (oriel).  Local +Y is outward, base at z=0.

    Front face width w, side cheeks at 45 deg, projection d.
    """
    out = []
    sill_mat = sill_mat or wood
    # corbelled underside
    out.append(box(name + "_cb", T @ Ts(0, d * 0.42, -0.22), (w + 0.26, d * 0.9, 0.30),
                   wood, bev=0.02))
    for i in range(3):
        x = (i - 1) * (w + 0.1) / 3.4
        out.append(box(name + "_k%d" % i, T @ Ts(x, d * 0.22, -0.52),
                       (0.22, d * 0.5, 0.42), wood, bev=0.015))
        out.append(box(name + "_kk%d" % i, T @ Ts(x, d * 0.18, -0.80),
                       (0.16, d * 0.28, 0.30), wood, bev=0.015))
    # moulded sill board
    out.append(box(name + "_sb", T @ Ts(0, d * 0.5, 0.06), (w + 0.34, d + 0.30, 0.14),
                   sill_mat, bev=0.02))
    # floor / head plates
    out.append(box(name + "_fp", T @ Ts(0, d * 0.5, 0.16), (w, d, 0.10), wood))
    out.append(box(name + "_hp", T @ Ts(0, d * 0.5, h - 0.14), (w + 0.16, d + 0.16, 0.24),
                   wood, bev=0.02))
    # front lights
    out += _win(name + "_f", T @ Ts(0, d, 0.22), w - 0.34, h - 0.62, wood, glass,
                dark, lights=lights, arch=False, depth=0.20, sill=False,
                jamb=0.10, mull=0.07)
    # angled cheeks
    cw = d * 1.4142 - 0.10
    for s in (-1, 1):
        Tc = T @ Ts(s * (w * 0.5), 0.0, 0.0) @ RZ(-s * math.pi * 0.25)
        out += _win(name + "_c%d" % s, Tc @ Ts(0, 0.0, 0.22), cw, h - 0.62, wood,
                    glass, dark, lights=1, arch=False, depth=0.20, sill=False,
                    jamb=0.10, mull=0.07)
    # small hipped lead roof
    out.append(box(name + "_rl", T @ Ts(0, d * 0.5, h + 0.06), (w + 0.5, d + 0.44, 0.10),
                   sill_mat, bev=0.015))
    out.append(H.prism(name + "_rp", T @ Ts(0, d * 0.5, h + 0.11),
                       [(-(w + 0.5) * 0.5, 0), ((w + 0.5) * 0.5, 0), (0, 0.62)],
                       d + 0.44, sill_mat, axis="y"))
    out.append(cyl(name + "_fin", T @ Ts(0, d * 0.5, h + 0.86), 0.045, 0.5, sill_mat,
                   seg=8))
    return _flat(out)


def _louvre(name, T, w, h, wood, dark, slats=7):
    """Slatted louvre opening in a local +Y face; keeps rain out and light in."""
    out = [box(name + "_dk", T @ Ts(0, -0.20, h * 0.5), (w, 0.16, h), dark)]
    for s in (-1, 1):
        out.append(box(name + "_p%d" % s, T @ Ts(s * (w * 0.5 + 0.06), 0, h * 0.5),
                       (0.12, 0.30, h + 0.12), wood))
    for i in range(slats):
        z = (i + 0.5) * h / slats
        out.append(box(name + "_s%d" % i, T @ Ts(0, 0.02, z, rx=math.radians(-36)),
                       (w * 0.98, 0.30, 0.045), wood, bev=0.006))
    return _flat(out)


def _frame_bay(name, T, w, h, wood, infill, stud=0.40, close_stud=True,
               braces=2, mid=0.85, postw=0.20, rng=None, patch_mat=None):
    """One close-studded half-timbered bay in a local +Y wall face.

    Returns (objects, inner_rect) where inner_rect is the clear rectangle above
    `mid` that a window should fill: (width, height, bottom_z).
    """
    out = []
    out.append(box(name + "_inf", T @ Ts(0, -0.10, h * 0.5), (w, 0.20, h), infill))
    out.append(box(name + "_sole", T @ Ts(0, 0.02, 0.13), (w + 0.06, 0.30, 0.26), wood,
                   bev=0.012))
    out.append(box(name + "_top", T @ Ts(0, 0.02, h - 0.15), (w + 0.06, 0.32, 0.30),
                   wood, bev=0.012))
    out.append(box(name + "_mid", T @ Ts(0, 0.02, mid), (w - 0.02, 0.28, 0.20), wood,
                   bev=0.01))
    for s in (-1, 1):
        out.append(box(name + "_p%d" % s, T @ Ts(s * (w * 0.5 - postw * 0.5), 0.02,
                                                 h * 0.5),
                       (postw, 0.32, h), wood, bev=0.012))
    # close studding below the mid rail
    if close_stud:
        n = max(2, int(w / stud))
        for i in range(1, n):
            x = -w * 0.5 + w * i / n
            out.append(box(name + "_s%d" % i, T @ Ts(x, 0.02, mid * 0.5),
                           (0.085, 0.24, mid - 0.20), wood))
    # a couple of studs above the window zone as framing
    for s in (-1, 1):
        out.append(box(name + "_u%d" % s, T @ Ts(s * (w * 0.5 - postw * 0.5), 0.03,
                                                 (h + mid) * 0.5),
                       (0.10, 0.26, h - mid - 0.20), wood))
    # diagonal braces in the lower storey
    if braces:
        bw = min(1.25, w * 0.34)
        for s in (-1, 1):
            x0 = s * (w * 0.5 - postw - 0.02)
            x1 = x0 - s * bw
            o = _seg(name + "_br%d" % s, T @ Ts(0, 0.05, 0), (x0, 0.26), (x1, mid - 0.06),
                     0.14, 0.22, wood, bev=0.008)
            if o:
                out.append(o)
    # wattle-and-daub panels are never flat: each bay gets a run of horizontal
    # laths (the scratch coat lines) and, on some bays, a repatched panel in a
    # different daub - the cheapest way to break up a field of blank rectangles
    if rng is not None:
        z0, z1 = 0.30, mid - 0.18
        nl = rng.randint(3, 5)
        lath = 0.035
        for k in range(nl):
            zz = z0 + (z1 - z0) * (k + 0.5) / nl
            out.append(box(name + "_lh%d" % k, T @ Ts(0, -0.005, zz),
                           (w - postw * 2.1, 0.035, lath), wood, bev=0.004))
        if patch_mat is not None and rng.random() < 0.55:
            ph = (z1 - z0) * rng.uniform(0.35, 0.6)
            pz = rng.uniform(z0 + ph * 0.5, z1 - ph * 0.5)
            pw = (w - postw * 2.2) * rng.uniform(0.45, 0.95)
            px = rng.uniform(-0.5 * (w - postw * 2.2 - pw), 0.5 * (w - postw * 2.2 - pw))
            out.append(box(name + "_pt", T @ Ts(px, 0.004, pz), (pw, 0.03, ph),
                           patch_mat))
    return out, (w - postw * 2.2, h - mid - 0.34, mid + 0.17)


def _jetty(name, T, length, out_, wood, axis="x", step=0.62, h=0.30):
    """Corbel row + fascia carrying a jettied floor.  axis='x' runs along X."""
    out = []
    n = max(2, int(length / step))
    for i in range(n):
        t = -length * 0.5 + (i + 0.5) * length / n
        if axis == "x":
            out.append(box(name + "_k%d" % i, T @ Ts(t, out_ * 0.5, -h * 0.55),
                           (0.20, out_ * 1.05, h * 0.9), wood, bev=0.01))
            out.append(box(name + "_kb%d" % i, T @ Ts(t, out_ * 0.95, -h * 1.15),
                           (0.26, out_ * 0.5, h * 0.55), wood, bev=0.008))
        else:
            out.append(box(name + "_k%d" % i, T @ Ts(out_ * 0.5, t, -h * 0.55),
                           (out_ * 1.05, 0.20, h * 0.9), wood, bev=0.01))
            out.append(box(name + "_kb%d" % i, T @ Ts(out_ * 0.95, t, -h * 1.15),
                           (out_ * 0.5, 0.26, h * 0.55), wood, bev=0.008))
    if axis == "x":
        out.append(box(name + "_fa", T @ Ts(0, out_ * 0.62, -h * 0.05),
                       (length + 0.1, out_ * 1.24, h * 0.36), wood, bev=0.02))
    else:
        out.append(box(name + "_fa", T @ Ts(out_ * 0.62, 0, -h * 0.05),
                       (out_ * 1.24, length + 0.1, h * 0.36), wood, bev=0.02))
    return _flat(out)


# ==========================================================================
# roof helpers
# ==========================================================================
def _tile_field(name, T, ridge_len, pitch, rh, hw, mats, tw=0.62, ch=0.40,
                thick=0.075, lift=0.055, rng=None, sides=(-1, 1), ridge_row=True):
    """Individual roof tiles over the pitched surface H.roof would draw.

    Local frame of T: ridge along Y at x=0, z=rh; eaves at x=+-hw, z=0 (so pass
    the same T as _roof with the eave height already folded in, plus the same
    pitch/verge-derived hw/rh).  Tiles are bucketed into one mesh per material,
    so a 6000-tile field costs only len(mats) objects.
    """
    out = []
    L = math.hypot(hw, rh)
    nrow = max(2, int(L / ch))
    ncol = max(2, int(ridge_len / tw))
    buf = [[] for _ in mats]
    for s in sides:
        # outward surface normal in the XZ plane (up and away from the ridge)
        nx, nz = s * rh / L, hw / L
        for i in range(nrow):
            ua = i / float(nrow) - 0.010
            ub = (i + 1.0) / float(nrow) + 0.004
            xa, za = s * hw * (1.0 - ua), rh * ua
            xb, zb = s * hw * (1.0 - ub), rh * ub
            for j in range(ncol):
                y0 = -ridge_len * 0.5 + j * ridge_len / ncol + 0.014
                y1 = y0 + ridge_len / ncol - 0.028
                zj = (rng.random() - 0.5) * 0.012 if rng is not None else 0.0
                ring = [(xa, y0, za + lift + zj), (xb, y0, zb + lift + zj),
                        (xb, y1, zb + lift + zj), (xa, y1, za + lift + zj)]
                vs = []
                for off in (-thick * 0.5, thick * 0.5):
                    for (cx, cy, cz) in ring:
                        vs.append((cx + nx * off, cy, cz + nz * off))
                f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                     (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
                k = 0 if rng is None else rng.randrange(len(mats))
                buf[k].append((vs, f))
    for k, chunk in enumerate(buf):
        if not chunk:
            continue
        verts, faces = [], []
        for vs, f in chunk:
            b = len(verts)
            verts.extend(vs)
            faces.extend([tuple(b + i for i in ff) for ff in f])
        out.append(H.poly("%s_t%d" % (name, k), verts, faces, mats[k], T))
    if ridge_row:
        # one continuous half-round ridge, not a row of short tubes: segmented
        # tubes read as a fence of posts along the skyline
        out.append(cyl("%s_rg" % name,
                       T @ Ts(0, 0, rh + 0.11) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
                       0.215, ridge_len + 0.06, mats[0], seg=10))
        nf = max(2, int(ridge_len / 3.1))
        for i in range(nf):
            y = -ridge_len * 0.5 + (i + 0.5) * ridge_len / nf
            out.append(H.lathe("%s_rfn%d" % (name, i),
                               [(0.11, 0.0), (0.11, 0.05), (0.05, 0.10), (0.035, 0.30),
                                (0.075, 0.37), (0.02, 0.44)],
                               mats[0], seg=8, T=T @ Ts(0, y, rh + 0.30),
                               smooth=False))
    return out


def _roof(name, T, span, ridge_len, eave_z, pitch, tile, wood, plaster,
          verge=0.55, course_h=0.36, gable_face=True, barge=True, fascia=True,
          alt=None, tile_w=0.62, tile_h=0.40, seed=7):
    """H.roof + a plaster gable face on both ends + real wood bargeboards.

    H.roof closes its gable ends with `deck_mat`; we pass plaster for the
    deck so the closing triangle already reads as the gable render, then put
    the bargeboards slightly outside it so the thin plaster rake boards the
    helper also emits stay hidden.

    NOTE `eave_z` is measured *from T's origin*, because H.roof adds it to the
    parts' local z.  Callers therefore pass T = Ts(0,0,<eave height>) together
    with eave_z=0.0, otherwise the eave height lands twice and the roof floats.
    """
    hw = span * 0.5 + verge
    rh = hw * math.tan(math.radians(pitch))
    hd = ridge_len * 0.5 + 0.4
    out = H.roof(name, T, span, ridge_len, eave_z, pitch, tile, plaster,
                 courses=False, course_h=course_h, verge=verge, ridge=False,
                 gable_ends=False)
    # real tiles instead of the helper's rails: alternating shades give the
    # roof the mottled, hand-made read that a flat tile material cannot
    talt = alt if alt is not None else tile
    trng = random.Random(seed)
    out += _tile_field(name + "_tf", T, ridge_len + 0.86, pitch, rh, hw,
                       [tile, talt, talt], tw=tile_w, ch=tile_h, rng=trng)
    if fascia:
        for s in (-1, 1):
            out.append(box(name + "_fa%d" % s,
                           T @ Ts(s * (hw + 0.02), 0, eave_z - 0.02),
                           (0.16, 2 * hd - 0.2, 0.30), wood, bev=0.012))
    if barge:
        rl = math.hypot(hw, rh)
        for sy in (-1, 1):
            for sx in (-1, 1):
                out.append(box(name + "_bg%d%d" % (sy, sx),
                               T @ Ts(sx * hw * 0.5, sy * (hd + 0.09),
                                      eave_z + rh * 0.5,
                                      ry=math.atan2(-rh, -sx * hw)),
                               (rl + 0.08, 0.11, 0.34), wood, bev=0.015))
    return out, hw, rh, hd


def _rafter_row(name, T, length, mat, step=0.46, w=0.30, h=0.26, d=0.20,
                axis="x", rng=None):
    """Projecting rafter ends under an eave (the 'cogged' shadow line).

    A bare eave meets the wall in a single straight line, which is why the
    roofs read as pasted-on slabs from 60 m.  A row of rafter ends throws a
    saw-tooth shadow along every eave and gives the roof a real edge.
    """
    out = []
    n = max(3, int(length / step))
    for i in range(n):
        u = -length * 0.5 + length * (i + 0.5) / n
        dz = 0.0 if rng is None else rng.uniform(-0.012, 0.012)
        if axis == "x":
            Tp = T @ Ts(u, 0.0, dz)
            sc = (w, d, h + dz * 0.5)
        else:
            Tp = T @ Ts(0.0, u, dz) @ RZ(math.pi * 0.5)
            sc = (w, d, h + dz * 0.5)
        out.append(box("%s%d" % (name, i), Tp, sc, mat, bev=0.008))
    # the wall plate the rafters sit on
    out.append(box(name + "_pl", T, (length + 0.2, d * 1.15, h * 0.62) if axis == "x"
                   else (d * 1.15, length + 0.2, h * 0.62), mat, bev=0.01))
    return _flat(out)


def _gable_frame(name, T, hw, rh, wood, plaster, z0=0.0, stud=0.62,
                 skip=(-1e9, 1e9), tie=True, collar=0.55):
    """Timber studding laid on a gable face (local +Y outward, base at z=z0)."""
    out = []
    if tie:
        out.append(box(name + "_tie", T @ Ts(0, 0.02, z0 + 0.16),
                       (2 * hw + 0.1, 0.30, 0.30), wood, bev=0.012))
    n = max(2, int(2 * hw / stud))
    for i in range(1, n):
        x = -hw + 2 * hw * i / n
        if skip[0] < x < skip[1]:
            continue
        top = rh * (1.0 - abs(x) / hw) - 0.22
        if top < 0.3:
            continue
        out.append(box(name + "_v%d" % i, T @ Ts(x, 0.03, z0 + top * 0.5),
                       (0.115, 0.24, top), wood))
    return _flat(out)


def _dormer(name, T, w, h, d, wall, roof_mat, wood, glass, dark, ridge_len=None):
    """Roof dormer, FRONT FACING -Y (like every other opening in this module).

    T's origin is the point where the dormer front meets the roof slope; the
    body runs back into the roof along +Y, so the caller only has to put the
    origin on the slope.  Rotate by RZ(+-90) for slopes that face X.
    """
    out = []
    yf = -0.25 * d                    # front face, relative to T
    out.append(box(name + "_b", T @ Ts(0, 0.25 * d, h * 0.5), (w, d, h), wall, bev=0.02))
    out.append(box(name + "_t", T @ Ts(0, 0.20 * d, h + 0.02), (w + 0.16, d * 0.9, 0.14),
                   wood, bev=0.015))
    # front gable, closing the top of the dormer
    rise = w * 0.5 * 0.92
    out.append(H.prism(name + "_gb", T @ Ts(0, yf + 0.02, h),
                       [(-w * 0.5, 0), (w * 0.5, 0), (0, rise)], 0.14, wall, axis="y"))
    for s in (-1, 1):
        out.append(box(name + "_vg%d" % s,
                       T @ Ts(s * w * 0.25, yf - 0.05, h + rise * 0.5,
                              ry=math.atan2(-rise, -s * w * 0.5)),
                       (math.hypot(w * 0.5, rise), 0.09, 0.20), wood, bev=0.01))
    # a little pitched roof over the dormer
    out += H.roof(name + "_r", T @ Ts(0, 0.25 * d, h + 0.04), w + 0.3, d + 0.2, 0.0,
                  math.degrees(math.atan(rise / (w * 0.5 + 0.15))), roof_mat, wall,
                  courses=False, verge=0.15, gable_ends=False)
    out += _win(name + "_w", T @ Ts(0, yf - 0.02, 0.20) @ RZ(math.pi), w * 0.52, h * 0.60,
                wood, glass, dark, lights=2, arch=False, depth=0.16, sill=False,
                jamb=0.08, mull=0.06)
    return _flat(out)


def _belfry(name, T, w, d, h, wood, lead, gold, iron, dark, bell_mat):
    """Timber louvred belfry straddling the ridge, lead cap, vane.

    The turret sits on a boarded base drum that runs down THROUGH the roof
    plane: without it the open frame's lower rails and louvre sills stop just
    above the tiles and the whole bell cote reads as blocks floating over the
    ridge.  T's origin is the top of that drum, so the frame above it is fully
    supported from every angle.
    """
    out = []
    # boarded base drum, buried in the ridge at the centre and emerging ~0.25 m
    # from the tiles at its outer corners
    out.append(box(name + "_base", T @ Ts(0, 0, -0.48), (w + 0.34, d + 0.34, 1.66),
                   wood, bev=0.02))
    for i in range(9):
        x = -(w + 0.34) * 0.5 + (w + 0.34) * (i + 0.5) / 9.0
        for sy in (-1, 1):
            out.append(box(name + "_bp%d%d" % (i, sy),
                           T @ Ts(x, sy * (d * 0.5 + 0.19), -0.46),
                           (0.055, 0.05, 1.58), wood))
    for sy in (-1, 1):
        out.append(box(name + "_br%d" % sy, T @ Ts(0, sy * (d * 0.5 + 0.19), 0.31),
                       (w + 0.42, 0.14, 0.16), wood, bev=0.012))
        out.append(box(name + "_bb%d" % sy, T @ Ts(0, sy * (d * 0.5 + 0.19), -1.27),
                       (w + 0.42, 0.14, 0.14), wood))
        # moulded batten across the drum face (kept as boards, not a dark
        # recess: a black panel on a dark drum read as a hole in the roof)
        out.append(box(name + "_bm%d" % sy, T @ Ts(0, sy * (d * 0.5 + 0.17), -0.62),
                       (w * 0.60, 0.06, 0.15), wood, bev=0.01))
    for sx in (-1, 1):
        out.append(box(name + "_bs%d" % sx, T @ Ts(sx * (w * 0.5 + 0.17), 0, -0.46),
                       (0.10, d + 0.38, 1.62), wood))
    # frame proper: four posts on the drum, two rails, corner braces
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_cp%d%d" % (sx, sy),
                           T @ Ts(sx * (w * 0.5 - 0.13), sy * (d * 0.5 - 0.13), h * 0.5),
                           (0.26, 0.26, h), wood, bev=0.012))
            out.append(box(name + "_kx%d%d" % (sx, sy),
                           T @ Ts(sx * (w * 0.5 - 0.62), sy * (d * 0.5 - 0.13),
                                  h - 0.62, ry=sx * math.radians(38)),
                           (0.16, 0.16, 0.86), wood))
    for z in (0.15, h - 0.16):
        out.append(box(name + "_fr%d" % int(z * 100), T @ Ts(0, 0, z),
                       (w + 0.34, d + 0.34, 0.30), wood, bev=0.018))
        for sx in (-1, 1):
            out.append(box(name + "_fb%d%d" % (int(z * 100), sx),
                           T @ Ts(sx * (w * 0.5 + 0.1), 0, z), (0.14, d + 0.34, 0.34),
                           wood, bev=0.012))
    # louvres on the two long faces, sills resting on the drum
    for s in (-1, 1):
        out += _louvre(name + "_lv%d" % s,
                       T @ Ts(0, s * (d * 0.5 - 0.02), 0.20) @ RZ(0 if s < 0 else math.pi),
                       w * 0.66, h - 0.46, wood, dark, slats=6)
    for s in (-1, 1):
        tc = T @ Ts(s * (w * 0.5 - 0.02), 0, 0.20) @ RZ(-s * math.pi * 0.5)
        out += _louvre(name + "_ls%d" % s, tc, d * 0.62, h - 0.46, wood, dark, slats=6)
    # the bell, hung from the top rail by a stock
    out.append(cyl(name + "_stk", T @ Ts(0, 0, h - 0.34), 0.075, 0.30, iron, seg=8))
    out.append(box(name + "_yk", T @ Ts(0, 0, h - 0.20), (0.86, 0.16, 0.13), iron))
    out.append(H.lathe(name + "_bell", [(0.30, 0.0), (0.34, 0.10), (0.28, 0.26),
                                        (0.20, 0.42), (0.12, 0.48)],
                       bell_mat, seg=16, T=T @ Ts(0, 0, h - 0.72), smooth=True))
    # lead cap
    cap = [(w * 0.86, 0.0), (w * 0.80, 0.16), (w * 0.34, 0.62), (0.06, 1.05)]
    out.append(H.lathe(name + "_cap", cap, lead, seg=4,
                       T=T @ Ts(0, 0, h) @ RZ(math.pi * 0.25), smooth=False))
    out.append(cyl(name + "_fin", T @ Ts(0, 0, h + 1.10), 0.05, 0.5, gold, seg=8))
    out.append(sphere(name + "_ball", T @ Ts(0, 0, h + 1.38), 0.11, gold, seg=12, ring=8))
    # weathercock: flat arrow + flag
    out.append(box(name + "_ar", T @ Ts(0, 0, h + 1.52), (0.9, 0.045, 0.05), iron))
    out.append(H.prism(name + "_fl", T @ Ts(0.34, 0, h + 1.66),
                       [(0, 0), (0.34, 0.16), (0.34, 0.34)], 0.04, gold, axis="y"))
    return _flat(out)


def _chimney(name, T, h, mat, pots=3, stone_mat=None):
    """Rubble/ashlar stack with a weathered cap and clustered pots."""
    stone_mat = stone_mat or mat
    out = []
    out.append(box(name + "_b", T @ Ts(0, 0, h * 0.46), (1.05, 0.92, h * 0.92), mat,
                   bev=0.02))
    out.append(box(name + "_sh", T @ Ts(0, 0, h * 0.20), (1.28, 1.12, h * 0.34),
                   stone_mat, bev=0.03))
    out.append(box(name + "_cap", T @ Ts(0, 0, h * 0.94), (1.30, 1.14, 0.16), stone_mat,
                   bev=0.02))
    out.append(box(name + "_cl", T @ Ts(0, 0, h + 0.03), (1.46, 1.26, 0.12), mat,
                   bev=0.02))
    for i in range(pots):
        x = (i - (pots - 1) * 0.5) * 0.42
        out.append(H.lathe(name + "_p%d" % i,
                           [(0.13, 0.0), (0.17, 0.10), (0.15, 0.36), (0.19, 0.46)],
                           mat, seg=10, T=T @ Ts(x, 0, h + 0.08), smooth=False))
    return _flat(out)


def _turret(name, T, r, h, stone, lead, glass, dark, wood):
    """Octagonal stair turret with corbelled head and a lead spirelet."""
    out = []
    out.append(H.lathe(name + "_pl", [(r * 1.12, 0.0), (r * 1.10, 0.30), (r * 1.06, 0.42)],
                       stone, seg=8, T=T @ RZ(math.pi / 8), smooth=False))
    out.append(H.lathe(name + "_sh", [(r * 1.06, 0.42), (r * 1.02, h * 0.55),
                                      (r * 1.0, h - 0.9), (r * 1.04, h - 0.6),
                                      (r * 0.98, h - 0.35)],
                       stone, seg=8, T=T @ RZ(math.pi / 8), smooth=False))
    for k in range(3):
        z = 2.2 + k * (h - 3.0) / 3.0
        out.append(H.lathe(name + "_bd%d" % k,
                           [(r * 1.05, z), (r * 1.10, z + 0.10), (r * 1.05, z + 0.22)],
                           stone, seg=8, T=T @ RZ(math.pi / 8), smooth=False))
        Tc = T @ RZ(math.radians(22.5 * (k * 2))) @ Ts(r * 0.99, 0, z + 0.55)
        out += H.window_slit(name + "_sl%d" % k, Tc @ RZ(math.pi * 0.5), mat=stone)
    # corbelled head
    n = 8
    for i in range(n):
        a = math.pi / 8 + i * math.pi / 4
        M = T @ Ts(math.cos(a) * r * 1.02, math.sin(a) * r * 1.02, h - 0.45) @ RZ(-a)
        out.append(box(name + "_cb%d" % i, M, (0.30, 0.26, 0.55), stone, bev=0.015))
    out.append(H.lathe(name + "_hd", [(r * 1.12, h - 0.22), (r * 1.22, h),
                                      (r * 1.10, h + 0.34)],
                       stone, seg=8, T=T @ RZ(math.pi / 8), smooth=False))
    for i in range(4):
        a = math.pi / 4 + i * math.pi * 0.5
        Tc = T @ RZ(a + math.pi * 0.5) @ Ts(r * 1.14, 0, h + 0.02)
        out += _win(name + "_w%d" % i, Tc, 0.62, 0.9, stone, glass, dark, lights=2,
                    arch=False, depth=0.22, sill=False, jamb=0.10, mull=0.05,
                    lead=False)
    out.append(H.lathe(name + "_sp", [(r * 1.30, h + 0.36), (r * 1.18, h + 0.5),
                                      (r * 0.72, h + 1.5), (r * 0.30, h + 2.3),
                                      (0.05, h + 2.9)],
                       lead, seg=8, T=T @ RZ(math.pi / 8), smooth=False))
    out.append(cyl(name + "_fi", T @ Ts(0, 0, h + 3.15), 0.05, 0.7, lead, seg=8))
    out.append(sphere(name + "_fb", T @ Ts(0, 0, h + 3.5), 0.09, wood, seg=10, ring=6))
    return _flat(out)


def _wall_open(name, T, length, height, thick, mat, openings, bev=0.0, z0=0.0):
    """Wall in the local XZ plane (T's +Y is the wall's thickness axis) with
    rectangular holes.  openings: [(cx, w, zbottom, ztop)] local coords."""
    ops = sorted(openings)
    segs = []
    x = -length * 0.5
    for (cx, w, zb, zt) in ops:
        a, b = cx - w * 0.5, cx + w * 0.5
        if a > x + 1e-4:
            segs.append((x, a, z0, z0 + height))
        if zb > z0 + 1e-3:
            segs.append((a, b, z0, zb))
        if zt < z0 + height - 1e-3:
            segs.append((a, b, zt, z0 + height))
        x = b
    if x < length * 0.5 - 1e-4:
        segs.append((x, length * 0.5, z0, z0 + height))
    out = []
    for i, (a, b, zb, zt) in enumerate(segs):
        w, h = b - a, zt - zb
        if w < 1e-3 or h < 1e-3:
            continue
        out.append(box(name + "_w%d" % i, T @ Ts((a + b) * 0.5, 0, (zb + zt) * 0.5),
                       (w, thick, h), mat, bev=bev))
    return _flat(out)


def _panel(name, T, w, h, mat, depth=0.10, z=0.0, frame=0.10, fr_mat=None):
    """Recessed carved wall panel (frame bars + a sunken field)."""
    fr_mat = fr_mat or mat
    out = [box(name + "_f", T @ Ts(0, -depth * 0.45, z + h * 0.5), (w, depth * 0.5, h),
               mat, bev=0.01)]
    for s in (-1, 1):
        out.append(box(name + "_s%d" % s, T @ Ts(s * (w * 0.5 - frame * 0.5), 0, z + h * 0.5),
                       (frame, depth, h), fr_mat, bev=0.01))
    out.append(box(name + "_t", T @ Ts(0, 0, z + h - frame * 0.5), (w, depth, frame),
                   fr_mat, bev=0.01))
    out.append(box(name + "_b", T @ Ts(0, 0, z + frame * 0.5), (w, depth, frame),
                   fr_mat, bev=0.01))
    return _flat(out)


def _oculus(name, T, r, stone, glass, n=20):
    """Small round window: glass disc + a ring of carved voussoir blocks."""
    out = [cyl(name + "_g", T @ Ts(0, -0.12, 0) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
               r * 0.98, 0.06, glass, seg=24)]
    for i in range(n):
        a = 2.0 * math.pi * i / n
        L = 2.0 * r * 1.10 * math.sin(math.pi / n) * 1.15
        out.append(box(name + "_v%d" % i,
                       T @ Ts(math.cos(a + math.pi / n) * r * 1.10,
                              math.sin(a + math.pi / n) * r * 1.10, 0.0,
                              rz=a + math.pi / n + math.pi * 0.5),
                       (0.16, r * 0.34, L), stone, bev=0.008))
    return _flat(out)


def _crest(name, T, w, h, gold, stone, cloth2, iron):
    """Guild crest, FRONT FACING -Y: stone cartouche, gold shield, chevron,
    three roundels, two heraldic supporters."""
    out = []
    out.append(H.prism(name + "_car", T @ Ts(0, 0.02, 0),
                       [(-w * 0.62, h * 1.02), (w * 0.62, h * 1.02), (w * 0.62, h * 0.20),
                        (0, -0.22), (-w * 0.62, h * 0.20)], 0.14, stone, axis="y"))
    out.append(H.prism(name + "_shd", T @ Ts(0, -0.09, 0.06),
                       [(-w * 0.5, h * 0.86), (w * 0.5, h * 0.86), (w * 0.5, h * 0.26),
                        (0, -0.06), (-w * 0.5, h * 0.26)], 0.10, gold, axis="y"))
    # chevron: two raked bars on the shield's face
    for s in (-1, 1):
        out.append(box(name + "_ch%d" % s, T @ Ts(s * w * 0.20, -0.155, h * 0.40,
                                                  ry=s * math.radians(34)),
                       (w * 0.52, 0.05, h * 0.13), cloth2))
    for i, sx in enumerate((-0.28, 0.0, 0.28)):
        out.append(cyl(name + "_rd%d" % i,
                       T @ Ts(sx * w, -0.165, h * 0.70) @ Matrix.Rotation(math.pi * 0.5, 4,
                                                                           "X"),
                       h * 0.075, 0.05, gold, seg=14))
    # supporters: two small heraldic beasts flanking the cartouche
    for s in (-1, 1):
        out.append(_loft(name + "_sp%d" % s, T @ Ts(s * w * 0.72, -0.02, h * 0.06),
                         [(0.0, 0.10, 0.10), (0.16, 0.13, 0.12), (0.34, 0.12, 0.11)],
                         stone, seg=10, cap_bottom=False, cap_top=False))
        out.append(sphere(name + "_sph%d" % s, T @ Ts(s * w * 0.72, -0.02, h * 0.46),
                          0.10, stone, seg=10, ring=7))
    return _flat(out)


def _great_door(name, T, w, h, wood, iron, stone, steps=3, dark=None):
    """Carved processional doorway: steps, two orders of jambs, hood, tympanum."""
    out = []
    # steps
    for i in range(steps):
        out.append(box(name + "_st%d" % i, T @ Ts(0, -0.34 * (steps - i), 0.09 + i * 0.17),
                       (w + 1.5 - i * 0.16, 0.40, 0.18 + i * 0.17), stone, bev=0.02))
    zb = steps * 0.17
    # door leaves
    out.append(box(name + "_dk", T @ Ts(0, -0.20, zb + h * 0.5), (w, 0.16, h), wood,
                   bev=0.012))
    for i in range(5):
        z = zb + h * (i + 0.6) / 6.0
        out.append(box(name + "_bd%d" % i, T @ Ts(0, -0.28, z), (w - 0.10, 0.05, 0.10),
                       iron))
    for s in (-1, 1):
        out.append(box(name + "_hg%d" % s, T @ Ts(s * w * 0.22, -0.31, zb + h * 0.44),
                       (0.10, 0.05, h * 0.60), iron))
        out.append(cyl(name + "_kn%d" % s, T @ Ts(s * w * 0.30, -0.36, zb + h * 0.46),
                       0.055, 0.10, iron, seg=8,
                       r2=None) if False else box(name + "_kn%d" % s,
                                                  T @ Ts(s * w * 0.30, -0.36, zb + h * 0.46),
                                                  (0.09, 0.09, 0.09), iron))
    # jamb orders + capitals
    for s in (-1, 1):
        for k in range(2):
            x = s * (w * 0.5 + 0.20 + k * 0.26)
            out.append(cyl(name + "_jb%d%d" % (s, k), T @ Ts(x, -0.14, zb + h * 0.5),
                           0.115 - k * 0.015, h, stone, seg=10))
            out.append(box(name + "_cp%d%d" % (s, k),
                           T @ Ts(x, -0.16, zb + h - 0.10),
                           (0.34 - k * 0.04, 0.34, 0.20), stone, bev=0.015))
            out.append(box(name + "_bs%d%d" % (s, k),
                           T @ Ts(x, -0.16, zb + 0.08),
                           (0.34 - k * 0.04, 0.34, 0.16), stone, bev=0.015))
    # outer rect jambs
    for s in (-1, 1):
        out.append(box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + 0.62), -0.10, zb + h * 0.5),
                       (0.42, 0.34, h + 0.1), stone, bev=0.02))
    # arched head + hood + tympanum
    out += _arch(name + "_ar", T @ Ts(0, -0.10, 0), w + 0.3, zb + h, 0.46, 0.36, stone, n=13)
    out += _arch(name + "_hd", T @ Ts(0, 0.06, 0), w + 1.5, zb + h, 0.22, 0.30, stone, n=13)
    rr = (w + 0.3) * 0.5
    out.append(box(name + "_ty", T @ Ts(0, -0.16, zb + h + rr * 0.42),
                   (w * 0.9, 0.06, rr * 0.66), stone, bev=0.01))
    for s in (-1, 1):
        out.append(box(name + "_ls%d" % s,
                       T @ Ts(s * (w * 0.5 + 0.78), 0.05, zb + h - 0.02),
                       (0.26, 0.34, 0.26), stone, bev=0.03))
    return out, zb + h + (w + 0.3) * 0.5 + 0.3


# ==========================================================================
# street furniture
# ==========================================================================
def _sign(name, T, w, h, iron, wood, board, mat_emblem, gold):
    """Hanging shop sign: two iron stays, chains, a painted board."""
    out = []
    for s in (-1, 1):
        out.append(box(name + "_st%d" % s, T @ Ts(s * w * 0.24, 0.55, 0.02),
                       (0.055, 1.20, 0.055), iron))
        out.append(box(name + "_br%d" % s, T @ Ts(s * w * 0.24, 0.32, -0.16,
                                                  rx=math.radians(38)),
                       (0.045, 0.72, 0.045), iron))
    out.append(box(name + "_rail", T @ Ts(0, 1.10, 0.02), (w + 0.30, 0.06, 0.06), iron))
    for s in (-1, 1):
        x = s * w * 0.34
        out.append(cyl(name + "_ch%d" % s, T @ Ts(x, 1.10, -0.16), 0.018, 0.30, iron, seg=6))
        for k in range(3):
            out.append(sphere(name + "_cl%d%d" % (s, k),
                              T @ Ts(x, 1.10, -0.05 - k * 0.10), 0.028, iron,
                              seg=6, ring=4))
    out.append(box(name + "_bd", T @ Ts(0, 1.10, -0.42), (w, 0.07, h), board, bev=0.012))
    out.append(box(name + "_bf", T @ Ts(0, 1.10, -0.42), (w + 0.09, 0.05, h + 0.09), wood))
    out.append(cyl(name + "_em", T @ Ts(0, 1.16, -0.42) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
                   w * 0.26, 0.03, mat_emblem, seg=14))
    out.append(cyl(name + "_gm", T @ Ts(0, 1.185, -0.42) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
                   w * 0.17, 0.03, gold, seg=12))
    return _flat(out)


def _cloth(name, T, w, d, mats, sag=0.16, folds=4, fold=0.045, seg=12, rows=4,
           scallop=0.055, rng=None, drop=0.0, thick=None):
    """Sagging cloth as a lofted grid in the local XY plane at z=0.

    The panel hangs in -Z: `sag` bows the middle down, `folds` ripples the
    surface across u, `scallop` cuts a wavy free edge along v=1, and `drop`
    makes it a valance that falls vertically instead of lying flat.
    Materials alternate per row so striped canopies stay cheap.
    """
    grid = []
    for j in range(rows + 1):
        v = j / float(rows)
        row = []
        for i in range(seg + 1):
            u = i / float(seg)
            x = (u - 0.5) * w
            y = (v - 0.5) * d
            z = -sag * math.sin(math.pi * u) * math.sin(math.pi * v * 0.85)
            z += fold * math.sin(2.0 * math.pi * folds * u) * min(1.0, v * 2.2)
            if v > 0.999:
                z -= scallop * (0.5 + 0.5 * abs(math.sin(2.0 * math.pi * folds * u * 0.5)))
            z -= drop * v * v
            if rng is not None:
                z += (rng.random() - 0.5) * 0.004
            row.append((x, y, z))
        grid.append(row)
    verts = []
    for row in grid:
        for p in row:
            verts.append(p)
    faces = []
    for j in range(rows):
        for i in range(seg):
            a = j * (seg + 1) + i
            faces.append((a, a + 1, a + seg + 2, a + seg + 1))
    out = [H.poly(name, verts, faces, mats[0], T)]
    if thick:
        verts2 = [(p[0], p[1], p[2] - thick) for row in grid for p in row]
        out.append(H.poly(name + "_b", verts2, faces, mats[-1], T))
    return out


def _limb(name, p0, p1, r0, r1, mat, seg=10, mid=None):
    """Tapered limb lofted from world point p0 to p1 (rest of the rig stays flat)."""
    d = Vector(p1) - Vector(p0)
    L = d.length
    if L < 1e-4:
        return []
    q = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized())
    T = Matrix.Translation(Vector(p0)) @ q.to_matrix().to_4x4()
    rm = mid if mid is not None else (r0 + r1) * 0.5
    rings = [(0.0, r0, r0), (L * 0.5, rm, rm), (L, r1, r1)]
    ob = _loft(name, T, rings, mat, seg=seg, cap_bottom=True, cap_top=True)
    return [ob] if ob is not None else []


def _jet_arc(name, T, r0, z0, r1, z1, mat, rad=0.035, rings=7, seg=7, bow=0.16,
             sway=0.0, flare=1.35):
    """Falling jet: a tube lofted along a parabola from a lip outward + down.

    `sway` wobbles the jet sideways so it does not read as a wire, and `flare`
    opens the tube out where it hits the water.
    """
    out = []
    verts, faces = [], []
    for i in range(rings + 1):
        t = i / float(rings)
        rr = r0 + (r1 - r0) * t
        zz = z0 + (z1 - z0) * t
        # bow the jet outward so it leaves the lip horizontally and falls
        rr += bow * math.sin(math.pi * t) * 0.6
        taper = rad * (1.0 - 0.45 * t) * (1.0 + (flare - 1.0) * t * t)
        cx = sway * math.sin(t * 9.0) * t
        cy = sway * math.cos(t * 7.0) * t * 0.6
        for k in range(seg):
            a = 2.0 * math.pi * k / seg
            verts.append((math.cos(a) * taper + rr + cx, math.sin(a) * taper + cy, zz))
    for i in range(rings):
        for k in range(seg):
            k2 = (k + 1) % seg
            a = i * seg + k
            b = i * seg + k2
            c = (i + 1) * seg + k2
            d = (i + 1) * seg + k
            faces.append((a, b, c, d))
    out.append(H.poly(name, verts, faces, mat, T))
    return out


def _awning(name, T, w, d, z_hi, z_lo, wood, cloth, iron, rng=None):
    """Wattle awning: a woven hurdle on raking standards plus a cloth valance.

    A single solid plate reads as a floating table top from any distance, so
    the hurdle is built as rafters + withies with the sky between them, and
    only the front third is covered by a scrap of canvas.
    """
    out = []
    ang = math.atan2(z_hi - z_lo, d)
    L = math.hypot(d, z_hi - z_lo)
    zc = (z_hi + z_lo) * 0.5
    # two raking standards to the wall, a front post pair with foot blocks
    for s in (-1, 1):
        out.append(box(name + "_po%d" % s, T @ Ts(s * (w * 0.5 - 0.06), d - 0.06,
                                                  z_lo * 0.5),
                       (0.09, 0.09, z_lo), wood, bev=0.006))
        out.append(box(name + "_fb%d" % s, T @ Ts(s * (w * 0.5 - 0.06), d - 0.06, 0.05),
                       (0.24, 0.24, 0.10), wood, bev=0.008))
        out.append(box(name + "_ra%d" % s, T @ Ts(s * (w * 0.5 - 0.06), d * 0.5, zc,
                                                  rx=ang),
                       (0.08, L, 0.08), wood))
        # a knee brace from the post to the raking standard
        o = _seg(name + "_kb%d" % s, T @ Ts(0, 0, 0),
                 (s * (w * 0.5 - 0.06), z_lo * 0.55),
                 (s * (w * 0.5 - 0.30), z_lo * 0.86), 0.055, 0.055, wood, bev=0.004)
        if o:
            out.append(o)
    # three rafters running down the slope, then withies woven across them
    for k in range(4):
        x = -w * 0.5 + w * (k + 0.5) / 4.0
        out.append(box(name + "_rf%d" % k, T @ Ts(x, d * 0.5, zc + 0.05, rx=ang),
                       (0.05, L + 0.05, 0.05), wood))
    for k in range(11):
        t = (k + 0.5) / 11.0
        out.append(box(name + "_wh%d" % k,
                       T @ Ts(0, d * t, z_hi + (z_lo - z_hi) * t + 0.085, rx=ang),
                       (w - 0.03, 0.032, 0.026), wood))
    # canvas over the whole hurdle: an awning is a covered frame, not a plate
    # plus a scrap, and a partly covered frame reads as scaffolding
    out += _cloth(name + "_cv", T @ Ts(0, d * 0.50,
                                       z_hi + (z_lo - z_hi) * 0.50 + 0.13, rx=ang),
                  w - 0.02, d - 0.05, [cloth], sag=0.055, folds=9, fold=0.024,
                  seg=18, rows=5, scallop=0.05, rng=rng)
    # cloth valance hanging off the front rail, sagging between the poles
    out += _cloth(name + "_cl", T @ Ts(0, d + 0.03, z_lo - 0.02) @
                  Matrix.Rotation(math.radians(-90), 4, "X"),
                  w - 0.06, 0.62, [cloth], sag=0.0, folds=6, fold=0.030, seg=16,
                  rows=4, scallop=0.05, drop=0.10, rng=rng)
    # trestle counter under the shelter, with produce and baskets
    out.append(box(name + "_cp", T @ Ts(0, d * 0.55, 0.86), (w - 0.5, 0.62, 0.08), wood,
                   bev=0.008))
    for s in (-1, 1):
        out.append(box(name + "_cl%d" % s, T @ Ts(s * (w * 0.5 - 0.34), d * 0.55, 0.43),
                       (0.08, 0.55, 0.86), wood, bev=0.006))
    for i in range(4):
        out.append(sphere(name + "_pg%d" % i,
                          T @ Ts(-w * 0.32 + i * (w - 0.6) / 4.0, d * 0.55 - 0.1,
                                 0.94), 0.10, cloth, seg=8, ring=5, squash=0.75))
    # a couple of hanging goods off the front rail
    for i in range(2):
        out.append(cyl(name + "_gd%d" % i,
                       T @ Ts(-w * 0.24 + i * w * 0.42, d - 0.02, z_lo - 0.22),
                       0.05, 0.26, iron, seg=6))
        out.append(sphere(name + "_gb%d" % i,
                          T @ Ts(-w * 0.24 + i * w * 0.42, d - 0.02, z_lo - 0.40),
                          0.12, iron, seg=9, ring=6, squash=1.2))
    return _flat(out)


def _stall(name, T, w, d, wood, cloth, cloth2, iron, goods, rng):
    """Market stall: trestle, striped awning, hanging cloth, produce on top."""
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_lg%d%d" % (sx, sy),
                           T @ Ts(sx * (w * 0.5 - 0.14), sy * (d * 0.5 - 0.14), 0.55),
                           (0.10, 0.10, 1.10), wood, bev=0.006))
        out.append(box(name + "_sp%d" % sx, T @ Ts(sx * (w * 0.5 - 0.14), 0, 1.16),
                       (0.10, d, 0.09), wood))
    out.append(box(name + "_tp", T @ Ts(0, 0, 1.02), (w, d, 0.09), wood, bev=0.01))
    # back trestle + goods
    out.append(box(name + "_bk", T @ Ts(0, -d * 0.32, 1.24), (w - 0.2, 0.10, 0.36), wood))
    for i in range(6):
        x = -w * 0.5 + w * (i + 0.5) / 6.0
        out.append(sphere(name + "_gd%d" % i,
                          T @ Ts(x, rng.uniform(-0.1, 0.1), 1.14), 0.13,
                          goods[rng.randrange(len(goods))], seg=9, ring=6, squash=0.8))
    # awning: two sagging cloth panels meeting at a ridge, with a wavy valance
    for s in (-1, 1):
        out += _cloth(name + "_aw%d" % s,
                      T @ Ts(0, s * d * 0.05, 2.46) @
                      Matrix.Rotation(-s * math.radians(24), 4, "X"),
                      w + 0.22, d * 0.98, [cloth if s > 0 else cloth2],
                      sag=0.075, folds=7, fold=0.035, seg=16, rows=4,
                      scallop=0.045, rng=rng)
        out += _cloth(name + "_av%d" % s,
                      T @ Ts(0, s * (d * 0.5 + 0.30), 2.42) @
                      Matrix.Rotation(-s * math.radians(90), 4, "X"),
                      w + 0.22, 0.26, [cloth if s > 0 else cloth2], sag=0.0,
                      folds=8, fold=0.022, seg=16, rows=2, scallop=0.05, rng=rng)
    for sx in (-1, 1):
        out.append(box(name + "_ap%d" % sx, T @ Ts(sx * (w * 0.5), 0, 2.52),
                       (0.09, 0.09, 2.0), wood))
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box(name + "_sk%d%d" % (sx, sy),
                           T @ Ts(sx * (w * 0.5 - 0.14), sy * (d * 0.5 - 0.14), 1.98),
                           (0.08, 0.08, 1.85), wood))
    return _flat(out)


def _crate_pile(name, T, rng, wood, goods, n=5):
    out = []
    for i in range(n):
        s = rng.uniform(0.42, 0.62)
        x = rng.uniform(-0.5, 0.5)
        y = rng.uniform(-0.4, 0.4)
        z = 0.02 + (i // 2) * 0.50
        rz = rng.uniform(-0.35, 0.35)
        out.append(H.crate(name + "_c%d" % i, T @ Ts(x, y, z + s * 0.5, rz=rz), s=s, wood=wood))
        if i % 2 == 0:
            out.append(sphere(name + "_p%d" % i, T @ Ts(x, y, z + s + 0.05), 0.14,
                              goods[rng.randrange(len(goods))], seg=10, ring=6,
                              squash=0.7))
    return _flat(out)


def _sacks(name, T, rng, cloth):
    out = []
    for i in range(4):
        x = (i % 2) * 0.62 - 0.31
        y = (i // 2) * 0.55 - 0.28
        out.append(_loft(name + "_s%d" % i, T @ Ts(x, y, 0.0),
                         [(0.0, 0.26, 0.20), (0.20, 0.30, 0.24), (0.42, 0.24, 0.19),
                          (0.54, 0.12, 0.10)], cloth, seg=9, fold=0.05, folds=5,
                         cap_top=False))
    return _flat(out)


def _pigeon(name, T, body, head, s=1.0):
    out = [sphere(name + "_b", T @ Ts(0, 0, 0.075 * s), 0.085 * s, body, seg=9, ring=6,
                  squash=0.82)]
    out.append(sphere(name + "_h", T @ Ts(0.075 * s, 0, 0.148 * s), 0.043 * s, head,
                      seg=8, ring=6))
    out.append(cone(name + "_k", T @ Ts(0.112 * s, 0, 0.146 * s) @
                    Matrix.Rotation(math.pi * 0.5, 4, "Y"), 0.013 * s, 0.05 * s, head,
                    seg=6))
    out.append(box(name + "_t", T @ Ts(-0.085 * s, 0, 0.10 * s, ry=math.radians(-24)),
                   (0.09 * s, 0.045 * s, 0.014 * s), head))
    for sy in (-1, 1):
        out.append(box(name + "_l%d" % sy, T @ Ts(0.01 * s, sy * 0.032 * s, 0.032 * s),
                       (0.014, 0.012, 0.065 * s), head))
    return _flat(out)


def _bench(name, T, w, stone):
    out = [box(name + "_t", T @ Ts(0, 0, 0.44), (w, 0.42, 0.12), stone, bev=0.02)]
    for s in (-1, 1):
        out.append(box(name + "_l%d" % s, T @ Ts(s * (w * 0.5 - 0.22), 0, 0.22),
                       (0.16, 0.36, 0.44), stone, bev=0.015))
    return _flat(out)


def _crane(name, T, wood, wd, iron, rope_mat, crate_mat, goods):
    """Crane beam projecting from a gable end, with pulley, rope and load."""
    out = []
    out.append(box(name + "_beam", T @ Ts(1.55, 0, 0), (4.0, 0.34, 0.34), wood, bev=0.02))
    out.append(box(name + "_br", T @ Ts(1.05, 0, -0.86, ry=math.radians(42)),
                   (2.6, 0.22, 0.22), wood, bev=0.012))
    out.append(box(name + "_br2", T @ Ts(0.35, 0, -1.35), (0.30, 0.28, 1.5), wood, bev=0.015))
    # pulley block
    out.append(box(name + "_pb", T @ Ts(2.95, 0, -0.30), (0.44, 0.30, 0.50), wd, bev=0.015))
    out.append(cyl(name + "_sh", T @ Ts(2.95, 0, -0.46) @
                   Matrix.Rotation(math.pi * 0.5, 4, "X"), 0.22, 0.34, iron, seg=14))
    out.append(cyl(name + "_rp", T @ Ts(2.95, 0, -0.46) @
                   Matrix.Rotation(math.pi * 0.5, 4, "X"), 0.235, 0.10, rope_mat, seg=14))
    # rope + hook + load
    out.append(cyl(name + "_cy", T @ Ts(2.95, 0, -2.10), 0.035, 3.0, rope_mat, seg=6))
    for i in range(3):
        out.append(cyl(name + "_cr%d" % i, T @ Ts(1.95 + i * 0.75, 0, -0.10),
                       0.055, 0.5, rope_mat, seg=6,
                       r2=0.03) if False else box(name + "_cr%d" % i,
                                                  T @ Ts(1.95 + i * 0.75, 0, -0.10),
                                                  (0.16, 0.16, 0.16), rope_mat))
    out.append(H.crate(name + "_ld", T @ Ts(2.95, 0, -3.95), s=0.78, wood=crate_mat))
    out.append(box(name + "_hk", T @ Ts(2.95, 0, -3.42), (0.10, 0.06, 0.34), iron))
    # winding drum + crank on the wall
    out.append(cyl(name + "_dr", T @ Ts(-0.30, 0, -2.10) @
                   Matrix.Rotation(math.pi * 0.5, 4, "X"), 0.34, 0.62, wood, seg=12))
    out.append(box(name + "_ck", T @ Ts(-0.30, 0.42, -2.10), (0.07, 0.30, 0.07), iron))
    out.append(box(name + "_gh", T @ Ts(-0.30, 0.60, -2.16), (0.06, 0.22, 0.06), iron))
    return _flat(out)


# ==========================================================================
# palette self-healing
# ==========================================================================
def _plain_mat(name, hexcol, rough=0.55, metal=0.0, emit=None, emit_str=0.0,
               alpha=1.0):
    """Lowest common denominator material: safe even if the kit changes."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            b = n
    if b is None:
        return m
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Roughness"], rough)
    K._put(b, ["Metallic"], metal)
    if alpha < 1.0:
        _put_alpha(b, alpha)
    if emit:
        K._put(b, ["Emission Color"], K.c(emit))
        K._put(b, ["Emission Strength"], emit_str)
    return m


def _put_alpha(b, a):
    try:
        K._put(b, ["Alpha"], a)
    except Exception:
        pass


def _pf_stone(n, b, d, l):
    try:
        return K.mat_stone(n, base=b, dark=d, light=l, scale=2.4)
    except Exception:
        return _plain_mat(n, b, 0.62)


def _pf_tile(n, b, d, l):
    try:
        return K.mat_tile(n, base=b, dark=d, light=l)
    except Exception:
        return _plain_mat(n, b, 0.60)


def _pf_wood(n, b, l, r):
    try:
        return K.mat_wood(n, base=b, light=l, rough=r, scale=1.6)
    except Exception:
        return _plain_mat(n, b, r)


def _pf_cloth(n, h):
    try:
        return K.mat_cloth(n, h)
    except Exception:
        return _plain_mat(n, h, 0.78)


def _pf_plaster(n, b, d):
    try:
        return K.mat_plaster(n, base=b, dirt=d, scale=1.3)
    except Exception:
        return _plain_mat(n, b, 0.82)


def _pf_metal(n, b, r):
    try:
        return K.mat_metal(n, base=b, rough=r)
    except Exception:
        return _plain_mat(n, b, r, 0.85)


# every key the three builders touch, with a self-contained stand-in so a
# caller's stale palette can never raise KeyError mid-build
_PAL_SPEC = {
    "stone":         lambda: _pf_stone("pf_stone", "#8f8574", "#5f5749", "#b3a894"),
    "stone_warm":    lambda: _pf_stone("pf_stone_warm", "#a08a63", "#6b5a3c", "#bfa87c"),
    "stone_pale":    lambda: _pf_stone("pf_stone_pale", "#b3a68b", "#7d7359", "#d0c3a4"),
    "stone_dark":    lambda: _pf_stone("pf_stone_dark", "#7a7060", "#4d4638", "#96907a"),
    "wood":          lambda: _pf_wood("pf_wood", "#5a4030", "#7a5a42", 0.78),
    "wood_dark":     lambda: _pf_wood("pf_wood_dark", "#3d2a1e", "#56402e", 0.80),
    "wood_light":    lambda: _pf_wood("pf_wood_light", "#8a6a4c", "#a98460", 0.74),
    "wood_pale":     lambda: _pf_wood("pf_wood_pale", "#bda583", "#d4bd9c", 0.80),
    "tile":          lambda: _pf_tile("pf_tile", "#9c4a32", "#6d3324", "#bc6046"),
    "tile_dark":     lambda: _pf_tile("pf_tile_dark", "#7d3524", "#56241a", "#9c4a32"),
    "tile_blue":     lambda: _pf_tile("pf_tile_blue", "#4a5c74", "#33415a", "#62748c"),
    "tile_blue_lt":  lambda: _pf_tile("pf_tile_blue_lt", "#5c7089", "#41546b", "#7b8ea5"),
    "slate":         lambda: _pf_tile("pf_slate", "#4b4d52", "#33353a", "#64676d"),
    "plaster":       lambda: _pf_plaster("pf_plaster", "#ddd2ba", "#b3a68b"),
    "plaster_warm":  lambda: _pf_plaster("pf_plaster_warm", "#d6c3a2", "#a89474"),
    "glass":         _glass_mat,
    "iron":          lambda: _pf_metal("pf_iron", "#33363b", 0.44),
    "iron_warm":     lambda: _pf_metal("pf_iron_warm", "#4a3b32", 0.52),
    "gold":          lambda: _plain_mat("pf_gold", "#c9a227", 0.26, 1.0),
    "bronze":        lambda: _plain_mat("pf_bronze", "#5c7a5e", 0.40, 0.92),
    "lead":          lambda: _plain_mat("pf_lead", "#6d7378", 0.34, 0.85),
    "void":          lambda: _plain_mat("pf_void", "#1a1512", 0.90),
    "canvas":        lambda: _pf_cloth("pf_canvas", "#b9ac90"),
    "canvas_red":    lambda: _pf_cloth("pf_canvas_red", "#9c4534"),
    "banner_red":    lambda: _pf_cloth("pf_banner_red", "#8f2f28"),
    "banner_blue":   lambda: _pf_cloth("pf_banner_blue", "#2c4a72"),
    "banner_gold":   lambda: _pf_cloth("pf_banner_gold", "#c9a227"),
    "banner_green":  lambda: _pf_cloth("pf_banner_green", "#3e6b46"),
    "water":         _water_mat,
    "water_jet":     _jet_mat,
    "water_veil":    _veil_mat,
    "glow":          _glow_mat,
    "interior":      _interior_mat,
    "ground":        lambda: _pf_stone("pf_ground", "#7d7a70", "#55534b", "#a09c90"),
    "ground_worn":   lambda: _pf_stone("pf_ground_worn", "#8f8b7e", "#66635a", "#b0ab9c"),
    "produce":       lambda: [_pf_cloth("pf_prod%d" % i, h) for i, h in enumerate(
        ("#b8641f", "#a03028", "#6f8a2c", "#c9a227", "#7a4a8c", "#3e6b46"))],
}


def _palette(MAT):
    """Copy the caller's palette and fill every key the builders need.

    The integrator's palette may predate this module, so anything missing is
    generated here rather than raising KeyError halfway through a build.
    """
    out = dict(MAT or {})
    for key, make in _PAL_SPEC.items():
        if out.get(key) is None:
            try:
                out[key] = make()
            except Exception:
                out[key] = _plain_mat("pf_fallback_" + key, "#8f8574")
    return out


# ==========================================================================
# 1. MARKET HALL
# ==========================================================================
def market_hall(MAT, rng):
    MAT = _palette(MAT)
    W = MAT
    stone = W["stone_warm"]
    pale = W["stone_pale"]
    wd = W["wood_dark"]
    wood = W["wood"]
    wl = W["wood_light"]
    wpale = W["wood_pale"]
    plaster = W["plaster"]
    glass = W["glass"]
    void = W["void"]
    iron = W["iron"]
    lead = W["lead"]
    gold = W["gold"]
    out = []

    GX, GY = 19.35, 10.35
    HX, HY = 20.00, 11.00
    # the arcade and the jettied timber hall below a 36 deg roof: the timber
    # storey gets 4.40 m of height instead of the old 3.85 m, which was too
    # thin to read under a roof this size
    Z0, ZC, ZE = 0.34, 5.05, 9.45
    PITCH = 36.0
    HW = HY + 0.55
    RH = HW * math.tan(math.radians(PITCH))
    RIDGE = ZE + RH
    PW = 0.95                       # arcade pier width
    NA = 10                         # arcade arches along the front
    LARC = 2.0 * (GX - 0.80)        # clear run between the end walls
    CLEAR = (LARC - (NA + 1) * PW) / NA
    ZS = Z0 + 2.44                  # arcade springing
    AY = -GY + 0.43                 # arcade front plane
    SHOP = -7.25                    # inner shopfront plane

    # ---------------------------------------------------------------- 1.1 base
    out.append(box("mh_plinth", Ts(0, 0, Z0 * 0.5), (2 * GX + 0.7, 2 * GY + 0.7, Z0),
                   pale, bev=0.03))
    for i in range(2):
        out.append(box("mh_ap%d" % i,
                       Ts(0, -GY - 0.30 - i * 0.36, (Z0 - 0.10 - i * 0.12) * 0.5),
                       (2 * GX + 0.9 + i * 0.7, 0.40, Z0 - 0.10 - i * 0.12), pale,
                       bev=0.02))
    for i in range(2):
        out.append(box("mh_tr%d" % i, Ts(0, GY + 0.30 + i * 0.36, (Z0 - 0.10) * 0.5 - i * 0.06 + 0.05),
                       (2 * GX + 0.9, 0.36, Z0 - 0.10), pale, bev=0.02))

    # ------------------------------------------------------- 1.2 ground storey
    # end walls, with blind arcading on the visible (+X) face
    for s in (-1, 1):
        x = s * (GX - 0.40)
        out.append(box("mh_ew%d" % s, Ts(x, 0, (Z0 + ZC) * 0.5),
                       (0.80, 2 * GY - 0.02, ZC - Z0), stone, bev=0.02))
        # plinth course + string course
        out.append(box("mh_ewb%d" % s, Ts(x, 0, Z0 + 0.22), (0.95, 2 * GY + 0.08, 0.44),
                       pale, bev=0.025))
        out.append(box("mh_ews%d" % s, Ts(x, 0, ZC - 0.22), (0.92, 2 * GY + 0.04, 0.30),
                       pale, bev=0.02))
        # blind arcade on the outer face
        Te = Ts(s * (GX + 0.02), 0, Z0) @ RZ(-s * math.pi * 0.5)
        for k in range(4):
            cy = -6.9 + k * 4.6
            Tc = Te @ Ts(cy, 0, 0)
            out += _arch("mh_ba%d_%d" % (s, k), Tc, 2.4, 2.28, 0.30, 0.36, pale, n=9)
            out.append(box("mh_bb%d_%d" % (s, k), Tc @ Ts(0, -0.06, 1.14),
                           (2.4, 0.16, 2.28), stone, bev=0.01))
            out.append(box("mh_bp%d_%d" % (s, k), Tc @ Ts(-1.55, 0, 1.30),
                           (0.44, 0.30, 2.60), pale, bev=0.015))
        out.append(box("mh_bp%d_e" % s, Te @ Ts(6.9, 0, 1.30), (0.44, 0.30, 2.60), pale,
                       bev=0.015))
        # a small door + window at each end, above the arcade crown
        out.append(box("mh_eg%d" % s, Te @ Ts(0.0, 0, 3.62), (1.5, 0.30, 2.0), void))
        Td = Te @ Ts(-2.9, -0.02, 0.0)
        out += H.door_arched("mh_ed%d" % s, Td @ Ts(0, 0, Z0 + 0.5) @ RZ(0 if s < 0 else 0),
                             1.30, 2.10, wood, iron, stone, steps=0, double=False)
        # quoins up the corner
        for k in range(11):
            out.append(box("mh_eq%d_%d" % (s, k),
                           Te @ Ts(-7.42 if k % 2 else 6.9, 0, 0.55 + k * 0.38),
                           (0.62 if k % 2 else 0.90, 0.22, 0.36), pale, bev=0.015))
    # back wall
    out.append(box("mh_bw", Ts(0, GY - 0.40, (Z0 + ZC) * 0.5), (2 * GX - 1.6, 0.80, ZC - Z0),
                   stone, bev=0.02))
    for i in range(4):
        x = -GX + 2.2 + i * (2 * GX - 4.4) / 3.0
        out.append(box("mh_but%d" % i, Ts(x, GY + 0.16, (Z0 + ZC) * 0.5),
                       (0.86, 0.55, ZC - Z0), pale, bev=0.025))
        out.append(H.window_slit("mh_bws%d" % i, Ts(x, GY - 0.02, Z0 + 1.6) @ RZ(math.pi),
                                 w=0.24, h=1.5, mat=void))

    # ------------------------------------------------------------ 1.3 arcade
    Tf = Ts(0, AY, 0)
    xcur = -LARC * 0.5
    piers = []
    arches = []
    for i in range(NA):
        piers.append(xcur + PW * 0.5)
        xcur += PW
        arches.append(xcur + CLEAR * 0.5)
        xcur += CLEAR
    piers.append(xcur + PW * 0.5)
    for i, px in enumerate(piers):
        out.append(box("mh_pier%d" % i, Tf @ Ts(px, 0, Z0 + (ZS - Z0) * 0.5),
                       (PW, 0.86, ZS - Z0), stone, bev=0.02))
        out.append(box("mh_pb%d" % i, Tf @ Ts(px, 0.02, Z0 + 0.26), (PW + 0.28, 1.02, 0.52),
                       pale, bev=0.025))
        out.append(box("mh_pc%d" % i, Tf @ Ts(px, 0.02, ZS - 0.30), (PW + 0.20, 0.98, 0.26),
                       pale, bev=0.02))
        out.append(box("mh_ps%d" % i, Tf @ Ts(px, 0.0, ZS - 0.62), (PW + 0.10, 0.92, 0.14),
                       pale, bev=0.012))
    for i, cx in enumerate(arches):
        out += _arcade_bay("mh_ab%d" % i, Tf, cx, CLEAR, ZS, ZC, PW, 0.30, 0.86, stone,
                           PW * 0.5 + CLEAR * 0.5)
        # keystone
        out.append(box("mh_ks%d" % i, Tf @ Ts(cx, 0.06, ZS + CLEAR * 0.5 + 0.30),
                       (0.26, 0.94, 0.46), pale, bev=0.02))
    # string course over the arcade
    out.append(box("mh_sc", Ts(0, AY + 0.02, ZC - 0.16), (LARC + 1.6, 1.02, 0.34), pale,
                   bev=0.025))

    # arcade floor, ceiling and joists
    out.append(box("mh_afl", Ts(0, (-GY + SHOP) * 0.5 - 0.2, Z0 + 0.04),
                   (LARC, GY + SHOP + 0.4, 0.16), pale, bev=0.02))
    out.append(box("mh_aceil", Ts(0, (-GY + SHOP) * 0.5 - 0.1, ZC - 0.30),
                   (LARC, GY + SHOP + 0.2, 0.12), plaster))
    njo = int(LARC / 0.58)
    for i in range(njo):
        x = -LARC * 0.5 + (i + 0.5) * LARC / njo
        out.append(box("mh_jo%d" % i, Ts(x, (-GY + SHOP) * 0.5 - 0.1, ZC - 0.44),
                       (0.13, GY + SHOP + 0.1, 0.20), wd, bev=0.006))
    out.append(box("mh_abeam", Ts(0, SHOP + 0.02, ZC - 0.22), (LARC, 0.30, 0.26), wd,
                   bev=0.012))

    # ------------------------------------------------- 1.4 inner shopfront wall
    Tw = Ts(0, SHOP, 0) @ RZ(math.pi)
    ops = []
    bay = LARC / 10.0
    for i in range(10):
        cx = -LARC * 0.5 + (i + 0.5) * bay
        if i % 2 == 0:
            ops.append((cx, 1.9, Z0, Z0 + 2.95))
        else:
            ops.append((cx, 1.75, Z0 + 1.05, Z0 + 2.90))
    out += _wall_open("mh_sw", Tw, LARC, ZC - Z0, 0.55, stone, ops, bev=0.015, z0=Z0)
    # lit interiors behind every opening, and a hanging lantern between piers:
    # without them the arcade is a black band across the whole facade
    for i, (cx, w, zb, zt) in enumerate(ops):
        Tgl = Tw @ Ts(cx, -0.36, zb + (zt - zb) * 0.5)
        out.append(box("mh_gi%d" % i, Tgl, (w * 0.92, 0.05, (zt - zb) * 0.88),
                       W["interior"]))
    for i in range(5):
        xl = -LARC * 0.5 + (i + 0.5) * LARC / 5.0
        out += K.lantern("mh_al%d" % i, Ts(xl, -8.55, ZC - 0.92), iron, W["glow"],
                         scale=0.62)
    for i, (cx, w, zb, zt) in enumerate(ops):
        hh = zt - zb
        Tc = Tw @ Ts(cx, -0.30, 0)
        if i % 2 == 0:
            out.append(box("mh_sd%d" % i, Tc @ Ts(0, 0, zb + hh * 0.5), (w, 0.10, hh),
                           wood, bev=0.01))
            out += _arch("mh_sda%d" % i, Tc @ Ts(0, 0.04, 0), w + 0.1, zb + hh,
                         0.16, 0.24, pale, n=7)
            for s in (-1, 1):
                out.append(box("mh_sdj%d" % (i * 2 + (s > 0)), Tc @ Ts(s * (w * 0.5 + 0.10), 0,
                                                                      zb + hh * 0.5),
                               (0.20, 0.24, hh), pale, bev=0.012))
        else:
            out += _win("mh_swn%d" % i, Tc @ Ts(0, 0, zb), w, hh, wd, glass, void,
                        lights=2, arch=False, depth=0.24, hood=False, sill=True,
                        jamb=0.12, mull=0.06)
            for s in (-1, 1):
                out.append(box("mh_sht%d_%d" % (i, s),
                               Tc @ Ts(s * (w * 0.5 + 0.20), 0.02, zb + hh * 0.5),
                               (0.34, 0.06, hh + 0.1), wl, bev=0.008))
    # fascia + brackets over the shopfronts
    out.append(box("mh_fas", Tw @ Ts(0, 0.14, ZC - Z0 - 0.30), (LARC, 0.30, 0.50), wd,
                   bev=0.015))
    ns = int(LARC / 1.2)
    for i in range(ns):
        x = -LARC * 0.5 + (i + 0.5) * LARC / ns
        out.append(box("mh_brk%d" % i, Tw @ Ts(x, 0.18, ZC - Z0 - 0.66), (0.14, 0.42, 0.30),
                       wd, bev=0.01))

    # ---------------------------------------------- 1.5 jetty + upper storey
    out += _jetty("mh_jf", Ts(0, -HY - 0.02, ZC + 0.16), 2 * HX + 0.1, 0.66, wd, axis="x")
    out += _jetty("mh_jb", Ts(0, HY + 0.02, ZC + 0.16) @ RZ(math.pi), 2 * HX + 0.1, 0.66,
                  wd, axis="x")
    for s in (-1, 1):
        out += _jetty("mh_js%d" % s, Ts(s * (HX + 0.02), 0, ZC + 0.16) @ RZ(-s * math.pi * 0.5),
                      2 * HY + 0.1, 0.66, wd, axis="x")
    out.append(box("mh_sillF", Ts(0, -HY + 0.10, ZC + 0.02), (2 * HX + 0.1, 0.40, 0.36), wd,
                   bev=0.02))
    out.append(box("mh_sillB", Ts(0, HY - 0.10, ZC + 0.02), (2 * HX + 0.1, 0.40, 0.36), wd,
                   bev=0.02))
    for s in (-1, 1):
        out.append(box("mh_sillS%d" % s, Ts(s * (HX - 0.10), 0, ZC + 0.02),
                       (0.40, 2 * HY, 0.36), wd, bev=0.02))

    ZH = ZE - ZC          # 3.85 timber storey height
    # --- front wall: 10 bays of 4.0 m
    front_kinds = ["solid", "win3", "oriel", "win4", "win4", "win4", "oriel", "win4",
                   "win3", "solid"]
    for i, kind in enumerate(front_kinds):
        xb = -HX + 2.0 + i * 4.0
        Tb = Ts(xb, -HY, ZC) @ RZ(math.pi)
        objs, rect = _frame_bay("mh_fb%d" % i, Tb, 4.0, ZH, wd, plaster,
                                braces=2, mid=0.80, rng=rng,
                                patch_mat=W["plaster_warm"])
        out += objs
        rw, rh2, zb = rect
        if kind == "win3":
            # timber-framed halls take square-headed windows; an arched head
            # with a hood here would punch through the roof plane (the panel
            # above the window head is only ~0.45 m deep)
            out += _win("mh_fw%d" % i, Tb @ Ts(0, 0.22, zb + 0.46), rw * 0.54,
                        rh2 - 0.92, wd, glass, void, lights=3, arch=False,
                        depth=0.34, hood=False, jamb=0.17)
            out.append(box("mh_fwl%d" % i, Tb @ Ts(0, 0.05, zb + 0.96),
                           (rw - 0.02, 0.30, 0.20), wd, bev=0.012))
        elif kind == "win4":
            # a window that fills the whole panel leaves nowhere for framing and
            # pushes the brace onto the glass: keep clear margins above and below
            out += _win("mh_fw%d" % i, Tb @ Ts(0, 0.22, zb + 0.62), rw * 0.60,
                        rh2 - 1.28, wd, glass, void, lights=4, arch=False,
                        depth=0.34, hood=False, jamb=0.16)
        elif kind == "oriel":
            out += _oriel("mh_fo%d" % i, Tb @ Ts(0, 0, zb - 0.10), 2.95, rh2 - 0.62, 0.78,
                          wd, glass, void, lights=3, sill_mat=wood)
    # --- end walls (22 m, 5 bays)
    for s in (-1, 1):
        Te = Ts(s * HX, 0, ZC) @ RZ(-s * math.pi * 0.5)
        kinds_e = ["win4", "solid", "win4", "solid", "win4"]
        for i, kind in enumerate(kinds_e):
            yb = -HY + 2.2 + i * 4.4
            Tb = Te @ Ts(yb, 0, 0)
            objs, rect = _frame_bay("mh_sb%d_%d" % (s, i), Tb, 4.4, ZH, wd, plaster,
                                    braces=2, mid=0.80, rng=rng,
                                    patch_mat=W["plaster_warm"])
            out += objs
            rw, rh2, zb = rect
            if kind != "solid":
                out += _win("mh_sw%d_%d" % (s, i), Tb @ Ts(0, 0.22, zb + 0.58), rw * 0.58,
                            rh2 - 1.20, wd, glass, void, lights=3, arch=False,
                            depth=0.34, jamb=0.16)
    # --- back wall (40 m, 10 bays, plain)
    for i in range(10):
        xb = -HX + 2.0 + i * 4.0
        Tb = Ts(xb, HY, ZC)
        objs, rect = _frame_bay("mh_bb%d" % i, Tb, 4.0, ZH, wd, plaster, braces=2,
                                mid=0.80, rng=rng, patch_mat=W["plaster_warm"])
        out += objs
        if i in (2, 5, 8):
            rw, rh2, zb = rect
            out += _win("mh_bw%d" % i, Tb @ Ts(0, 0.20, zb + 0.54), rw - 0.6, rh2 - 1.12,
                        wd, glass, void, lights=3, arch=False, depth=0.30, jamb=0.14)
    # corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box("mh_cp%d%d" % (sx, sy), Ts(sx * (HX - 0.14), sy * (HY - 0.14),
                                                      (ZC + ZE) * 0.5),
                           (0.34, 0.34, ZH), wd, bev=0.015))
    # eaves plate
    for s in (-1, 1):
        out.append(box("mh_ep%d" % s, Ts(0, s * (HY - 0.10), ZE - 0.16),
                       (2 * HX + 0.14, 0.34, 0.32), wd, bev=0.02))
        out.append(box("mh_epx%d" % s, Ts(s * (HX - 0.10), 0, ZE - 0.16),
                       (0.34, 2 * HY, 0.32), wd, bev=0.02))

    # ------------------------------------------------------------- 1.6 roof
    roof_objs, hw, rh, hd = _roof("mh_rf", Ts(0, 0, ZE) @ RZ(math.pi * 0.5),
                                  2 * HY, 2 * HX, 0.0, PITCH, W["tile"], wd, plaster,
                                  verge=0.55, course_h=0.36, alt=W["tile_dark"],
                                  tile_w=0.44, tile_h=0.30, seed=11)
    out += roof_objs
    # continuous lead ridge roll: a row of separately spaced blocks along the
    # skyline reads as posts stuck on the roof, not as cresting
    out.append(box("mh_roll", Ts(0, 0, RIDGE + 0.30), (2 * HX + 0.12, 0.52, 0.14),
                   lead, bev=0.02))
    for s in (-1, 1):
        out.append(cyl("mh_gt%d" % s, Ts(0, s * (hw - 0.06), ZE - 0.14) @
                       Matrix.Rotation(math.pi * 0.5, 4, "Y"), 0.11, 2 * hd - 0.4, lead,
                       seg=8))
        out.append(box("mh_gb%d" % s, Ts(0, s * (hw - 0.02), ZE - 0.26),
                       (2 * hd - 0.4, 0.20, 0.10), lead, bev=0.01))
        # projecting rafter ends along the eaves: the saw-tooth shadow line
        out += _rafter_row("mh_rt%d_" % s, Ts(0, s * (hw - 0.10), ZE - 0.30),
                           2 * hd - 0.5, wd, step=0.44, w=0.28, h=0.30, d=0.22,
                           axis="x", rng=rng)
    # joist ends carrying the jetty floor out over the arcade: a second,
    # denser saw-tooth course a storey lower, and the reason the overhang
    # reads as built rather than as a floating box
    for s in (-1, 1):
        out += _rafter_row("mh_je%d_" % s, Ts(0, s * (GY + 0.06), ZC - 0.32),
                           LARC - 0.2, wd, step=0.30, w=0.15, h=0.26, d=0.40,
                           axis="x", rng=rng)
        out += _rafter_row("mh_jex%d_" % s, Ts(s * (GX + 0.06), 0, ZC - 0.32),
                           2 * GY - 0.4, wd, step=0.30, w=0.15, h=0.26, d=0.40,
                           axis="y", rng=rng)
    # gable studding + windows
    for s in (-1, 1):
        Tg = Ts(s * (hd + 0.06), 0, ZE) @ RZ(-s * math.pi * 0.5)
        out += _gable_frame("mh_gf%d" % s, Tg, hw, rh, wd, plaster, stud=0.60,
                            skip=(-2.6, 2.6))
        # king post + collar
        out.append(box("mh_kp%d" % s, Tg @ Ts(0, 0.03, rh * 0.46), (0.24, 0.26, rh * 0.92),
                       wd, bev=0.012))
        out.append(box("mh_col%d" % s, Tg @ Ts(0, 0.03, rh * 0.56), (5.6, 0.26, 0.24), wd,
                       bev=0.012))
        for k in (-1, 1):
            o = _seg("mh_gl%d%d" % (s, k), Tg @ Ts(0, 0.03, 0), (k * 2.7, rh * 0.56),
                     (k * 4.6, rh * 0.30), 0.20, 0.24, wd, bev=0.008)
            if o:
                out.append(o)
        # big lunette window
        out += _win("mh_gw%d" % s, Tg @ Ts(0, 0.26, 1.55), 3.5, 1.9, wd, glass, void,
                    lights=5, arch=True, depth=0.34, hood=True, jamb=0.20)
        out += _oculus("mh_go%d" % s, Tg @ Ts(0, 0.22, 4.85), 0.92, wd, glass, n=20)
        # course of small lights either side
        for k in (-1, 1):
            out += _win("mh_gs%d%d" % (s, k), Tg @ Ts(k * 6.2, 0.22, 1.35), 1.05, 1.15,
                        wd, glass, void, lights=2, arch=False, depth=0.24, sill=True,
                        jamb=0.10, mull=0.05)
    # dormers on the square side: origin sits on the roof slope, so put it
    # where ZE + (HW-|y|)*tan(PITCH) = 10.58 -> |y| = 10.0
    for i, xd in enumerate((-11.4, 0.0, 11.4)):
        out += _dormer("mh_dm%d" % i, Ts(xd, -10.0, 10.58), 2.90, 2.20, 2.1,
                       plaster, W["tile"], wd, glass, void)
        out.append(box("mh_dms%d" % i, Ts(xd, -10.30, 10.48), (3.30, 0.55, 0.22), wood,
                       bev=0.015))
    # belfry on the ridge
    out += _belfry("mh_bf", Ts(0, 0, RIDGE - 1.30), 3.30, 2.70, 2.70, wood, lead, gold,
                   iron, void, W["bronze"])
    # chimneys
    for i, (cx, cy) in enumerate(((-12.4, 4.4), (12.4, 4.4))):
        out += _chimney("mh_ch%d" % i, Ts(cx, cy, 12.5), 6.4, stone, pots=3,
                        stone_mat=pale)
        out.append(box("mh_cfl%d" % i, Ts(cx, cy, 12.45), (1.9, 1.75, 0.30), lead,
                       bev=0.02))

    # -------------------------------------------------------- 1.7 fittings
    # hanging signs under the jetty
    for i, xb in enumerate((-14.0, -6.0, 6.0, 14.0)):
        out += _sign("mh_sg%d" % i, Ts(xb, -HY - 0.62, ZC - 0.02), 1.15, 0.95, iron, wd,
                     wd, W["gold"], gold)
    # wattle awnings leaning on the arcade face and projecting over the pavement
    # (attached at the pier line, not floating in the arch openings)
    for i, xb in enumerate((-11.0, 3.7, 15.0)):
        out += _awning("mh_aw%d" % i, Ts(xb, -GY + 0.12, 0) @ RZ(math.pi), 2.45, 2.55, 3.95, 2.80,
                       wl, W["canvas"], iron, rng)
    # stall market in front of the arcade: a front rank plus two end stalls
    # turned to face down the square
    rows = [(-16.5, -15.0, 0.05), (-8.0, -15.7, -0.12), (2.0, -15.2, 0.10),
            (11.0, -15.8, -0.08), (18.0, -14.6, 0.16)]
    for i, (sx, sy, sr) in enumerate(rows):
        cloth = W["banner_red"] if i % 2 == 0 else W["banner_blue"]
        cloth2 = W["canvas"] if i % 2 == 0 else W["canvas_red"]
        out += _stall("mh_st%d" % i, Ts(sx, sy, 0, rz=sr), 2.75, 1.6, wood, cloth, cloth2,
                      iron, W["produce"], rng)
    for i, (sx, sy, sr) in enumerate(((-20.4, -10.6, 1.42), (20.6, -10.0, -1.42))):
        out += _stall("mh_ste%d" % i, Ts(sx, sy, 0, rz=sr), 2.5, 1.5, wood,
                      W["banner_green"], W["canvas"], iron, W["produce"], rng)
    # produce, barrels, crates along the arcade
    for i, (cx, cy) in enumerate(((-17.6, -12.2), (-9.0, -12.6), (0.6, -12.4),
                                  (10.2, -12.7), (17.4, -12.3))):
        out += _crate_pile("mh_cr%d" % i, Ts(cx, cy, 0.36, rz=rng.uniform(-0.3, 0.3)),
                           rng, wl, W["produce"], n=4)
    for i in range(9):
        bx = -18.4 + i * 4.4 + rng.uniform(-0.4, 0.4)
        by = -11.2 + rng.uniform(-0.5, 0.5)
        out.append(H.barrel("mh_ba%d" % i, Ts(bx, by, Z0 + 0.42, rz=rng.uniform(0, 3)),
                            0.30, 0.84, wl, iron))
    for i, (cx, cy) in enumerate(((-19.6, -7.0), (19.4, -6.2))):
        out += _sacks("mh_sa%d" % i, Ts(cx, cy, Z0 + 0.40, rz=rng.uniform(0, 3)),
                      rng, W["canvas"])
    # carts
    out.append(H.cart("mh_ct0", Ts(-12.2, -16.4, 0, rz=0.35), wl, iron, L=2.5, W=1.3))
    out.append(H.cart("mh_ct1", Ts(6.8, -16.6, 0, rz=-0.22), wood, iron, L=2.2, W=1.1))
    # crane beam on the +X gable
    out += _crane("mh_cr", Ts(hd + 0.20, 0, ZE + 2.55), wood, wd, iron, W["canvas"], wl,
                  W["produce"])
    # external stair to the end door on -X
    out += H.stairs("mh_ext", Ts(-GX - 0.95, -4.5, Z0) @ RZ(-math.pi * 0.5), 1.6, 12,
                    rise=0.34, run=0.34, mat=pale)
    return _flat(out)


# ==========================================================================
# 2. GUILD HALL
# ==========================================================================
def guild_hall(MAT, rng):
    MAT = _palette(MAT)
    W = MAT
    stone = W["stone_warm"]
    pale = W["stone_pale"]
    warm = W["stone_warm"]
    wd = W["wood_dark"]
    wood = W["wood"]
    wl = W["wood_light"]
    plaster = W["plaster_warm"]
    glass = W["glass"]
    void = W["void"]
    iron = W["iron"]
    lead = W["lead"]
    gold = W["gold"]
    out = []

    GX, GY = 9.00, 14.00          # ground-floor half extents
    J1, J2 = 0.44, 0.44           # jetty steps
    U1X, U1Y = GX + J1, GY + J1
    U2X, U2Y = GX + J1 + J2, GY + J1 + J2
    Z0 = 0.34
    Z1 = 4.30                     # top of the stone storey
    Z2 = 7.05                     # top of the first timber storey
    ZE = 9.40                     # eave
    PITCH = 42.0
    SPAN = 2 * U2X
    HW = U2X + 0.55
    RH = HW * math.tan(math.radians(PITCH))
    RIDGE = ZE + RH
    RIDGE_LEN = 2 * (U2Y + 0.16)
    HD = RIDGE_LEN * 0.5 + 0.4

    # ---------------------------------------------------------------- 2.1 base
    out.append(box("gh_pl", Ts(0, 0, Z0 * 0.5), (2 * GX + 0.8, 2 * GY + 0.8, Z0), pale,
                   bev=0.03))
    for i in range(3):
        out.append(box("gh_st%d" % i, Ts(0, -GY - 0.55 - i * 0.42, (Z0 - 0.11 * (i + 1)) * 0.5),
                       (5.6 + i * 0.42, 0.44, Z0 - 0.11 * (i + 1)), pale, bev=0.02))

    # -------------------------------------------------------- 2.2 stone storey
    out.append(box("gh_core", Ts(0, 0, (Z0 + Z1) * 0.5), (2 * GX - 1.2, 2 * GY - 1.2,
                                                          Z1 - Z0), stone, bev=0.02))
    Tw = Ts(0, -GY, 0) @ RZ(math.pi)
    # front openings: door + 4 windows
    door_w, door_h = 2.45, 2.50
    ops = [(0.0, door_w, Z0, Z0 + door_h)]
    for s in (-1, 1):
        for k in range(2):
            ops.append((s * (3.05 + k * 3.25), 1.55, Z0 + 1.35, Z0 + 3.15))
    out += _wall_open("gh_fw", Tw, 2 * GX, Z1 - Z0, 0.85, stone, ops, bev=0.02, z0=Z0)
    # ashlar courses on the front
    for i in range(11):
        z = Z0 + 0.20 + i * 0.36
        if z > Z1 - 0.25:
            break
        for s in (-1, 1):
            out.append(box("gh_ac%d_%d" % (i, s), Tw @ Ts(s * 5.4, 0.03, z - Z0),
                           (7.2, 0.07, 0.30), pale if i % 2 else stone, bev=0.008))
    # great doorway
    do, dtop = _great_door("gh_dr", Tw @ Ts(0, 0, 0), door_w, door_h, wood, iron, pale,
                           steps=3)
    out += do                      # (the door parts must be registered, else they
                                   #  stay at local coords and float in the square)
    # windows either side
    for i, (cx, w, zb, zt) in enumerate(ops[1:]):
        hh = zt - zb
        out += _win("gh_wn%d" % i, Tw @ Ts(cx, 0.18, zb), w, hh - 0.42, pale, glass, void,
                    lights=2, arch=True, depth=0.44, hood=True, jamb=0.20)
        out += _panel("gh_wp%d" % i, Tw @ Ts(cx, 0.02, Z0 + 0.55 - Z0 + 0.05), 2.3, 0.62,
                      stone, fr_mat=pale)
    # the hood of the door carries a carved panel with a small crest, and the
    # guild's motto-board sits under dtop
    out += _panel("gh_dhp", Tw @ Ts(0, 0.06, dtop - 0.30), 3.9, 0.55, pale, depth=0.12,
                  frame=0.10, fr_mat=stone)
    out.append(box("gh_cor", Ts(0, -GY + 0.02, Z1 - 0.02), (2 * GX + 0.9, 0.94, 0.30),
                   pale, bev=0.025))
    for s in (-1, 1):
        out.append(box("gh_cors%d" % s, Ts(s * (GX - 0.02), 0, Z1 - 0.02),
                       (0.94, 2 * GY + 0.9, 0.30), pale, bev=0.025))
    # quoins + buttresses
    for s in (-1, 1):
        for k in range(11):
            out.append(box("gh_q%d_%d" % (s, k),
                           Ts(s * (GX - 0.05), -GY + (0.42 if k % 2 else 0.0),
                              Z0 + 0.20 + k * 0.36),
                           (0.30, 0.86 if k % 2 else 1.30, 0.34), pale, bev=0.015))
        for k in range(2):
            out.append(box("gh_bt%d_%d" % (s, k),
                           Ts(s * (GX + 0.24), -6.4 + k * 8.4, (Z0 + Z1) * 0.5),
                           (0.50, 1.15, Z1 - Z0), stone, bev=0.03))
            out.append(box("gh_btc%d_%d" % (s, k),
                           Ts(s * (GX + 0.30), -6.4 + k * 8.4, Z1 - 0.16),
                           (0.62, 1.28, 0.22), pale, bev=0.02))
    # side walls: 3 windows + 2 panels each
    for s in (-1, 1):
        Te = Ts(s * GX, 0, 0) @ RZ(-s * math.pi * 0.5)
        op2 = [(yy, 1.4, Z0 + 1.5, Z0 + 3.1) for yy in (-8.4, 0.0, 8.4)]
        out += _wall_open("gh_sw%d" % s, Te, 2 * GY, Z1 - Z0, 0.85, stone, op2, bev=0.02,
                          z0=Z0)
        for i, (yy, w, zb, zt) in enumerate(op2):
            out += _win("gh_swn%d_%d" % (s, i), Te @ Ts(yy, 0, zb), w, zt - zb - 0.4,
                        pale, glass, void, lights=2, arch=True, depth=0.40, hood=True,
                        jamb=0.18)
    # back wall of the stone storey (service side, kept plain but not bare)
    Tb = Ts(0, GY, 0)
    op3 = [(yy, 1.1, Z0 + 1.6, Z0 + 2.7) for yy in (-9.5, -3.2, 3.2, 9.5)]
    out += _wall_open("gh_bw", Tb, 2 * GX, Z1 - Z0, 0.85, stone, op3, bev=0.02, z0=Z0)
    for i, (yy, w, zb, zt) in enumerate(op3):
        out += H.window_slit("gh_bws%d" % i, Tb @ Ts(yy, 0.02, zb), w=0.26,
                             h=zt - zb, mat=void)

    # -------------------------------------------------- 2.3 first timber floor
    out += _jetty("gh_j1f", Ts(0, -GY - 0.02, Z1 + 0.16), 2 * GX + 0.1, J1, wd, axis="x")
    out += _jetty("gh_j1b", Ts(0, GY + 0.02, Z1 + 0.16) @ RZ(math.pi), 2 * GX + 0.1, J1,
                  wd, axis="x")
    for s in (-1, 1):
        out += _jetty("gh_j1s%d" % s, Ts(s * (GX + 0.02), 0, Z1 + 0.16) @ RZ(-s * math.pi * 0.5),
                      2 * GY + 0.1, J1, wd, axis="x")
    out.append(box("gh_s1f", Ts(0, -U1Y + 0.10, Z1 + 0.02), (2 * U1X + 0.1, 0.42, 0.36),
                   wd, bev=0.02))
    out.append(box("gh_s1b", Ts(0, U1Y - 0.10, Z1 + 0.02), (2 * U1X + 0.1, 0.42, 0.36),
                   wd, bev=0.02))
    for s in (-1, 1):
        out.append(box("gh_s1s%d" % s, Ts(s * (U1X - 0.10), 0, Z1 + 0.02),
                       (0.42, 2 * U1Y, 0.36), wd, bev=0.02))
    H1 = Z2 - Z1
    for i in range(5):
        xb = -U1X + 3.6 + i * 3.6
        Tb1 = Ts(0, -U1Y, Z1) @ RZ(math.pi)
        objs, rect = _frame_bay("gh_f1b%d" % i, Tb1 @ Ts(xb, 0, 0), 2 * U1X / 5.0, H1, wd,
                                plaster, braces=2, mid=0.72)
        out += objs
        rw, rh2, zb = rect
        if i in (1, 2, 3):
            out += _win("gh_f1w%d" % i, Tb1 @ Ts(xb, 0.20, zb + 0.50), rw * 0.60, rh2 - 1.05,
                        wd, glass, void, lights=3, arch=False, depth=0.34, jamb=0.15)
    for s in (-1, 1):
        Te1 = Ts(s * U1X, 0, Z1) @ RZ(-s * math.pi * 0.5)
        for i in range(5):
            yb = -U1Y + 3.6 + i * 3.6
            objs, rect = _frame_bay("gh_s1b%d_%d" % (s, i), Te1 @ Ts(yb, 0, 0),
                                    2 * U1Y / 5.0, H1, wd, plaster, braces=2, mid=0.72)
            out += objs
            if i in (1, 3):
                rw, rh2, zb = rect
                out += _win("gh_s1w%d_%d" % (s, i), Te1 @ Ts(yb, 0.20, zb + 0.40),
                            rw - 0.5, rh2 - 0.08, wd, glass, void, lights=3, arch=False,
                            depth=0.30, jamb=0.14)
    Tb1b = Ts(0, U1Y, Z1)
    for i in range(5):
        xb = -U1X + 3.6 + i * 3.6
        objs, rect = _frame_bay("gh_b1b%d" % i, Tb1b @ Ts(xb, 0, 0), 2 * U1X / 5.0, H1,
                                wd, plaster, braces=2, mid=0.72)
        out += objs

    # ------------------------------------------------ 2.4 second timber floor
    out += _jetty("gh_j2f", Ts(0, -U1Y - 0.02, Z2 + 0.16), 2 * U1X + 0.1, J2, wd, axis="x")
    out += _jetty("gh_j2b", Ts(0, U1Y + 0.02, Z2 + 0.16) @ RZ(math.pi), 2 * U1X + 0.1, J2,
                  wd, axis="x")
    for s in (-1, 1):
        out += _jetty("gh_j2s%d" % s,
                      Ts(s * (U1X + 0.02), 0, Z2 + 0.16) @ RZ(-s * math.pi * 0.5),
                      2 * U1Y + 0.1, J2, wd, axis="x")
    out.append(box("gh_s2f", Ts(0, -U2Y + 0.10, Z2 + 0.02), (2 * U2X + 0.1, 0.44, 0.38),
                   wd, bev=0.02))
    out.append(box("gh_s2b", Ts(0, U2Y - 0.10, Z2 + 0.02), (2 * U2X + 0.1, 0.44, 0.38),
                   wd, bev=0.02))
    for s in (-1, 1):
        out.append(box("gh_s2s%d" % s, Ts(s * (U2X - 0.10), 0, Z2 + 0.02),
                       (0.44, 2 * U2Y, 0.38), wd, bev=0.02))
    H2 = ZE - Z2
    Tb2 = Ts(0, -U2Y, Z2) @ RZ(math.pi)
    for i in range(5):
        xb = -U2X + 3.68 + i * 3.68
        objs, rect = _frame_bay("gh_f2b%d" % i, Tb2 @ Ts(xb, 0, 0), 2 * U2X / 5.0, H2, wd,
                                plaster, braces=2, mid=0.62, stud=0.34)
        out += objs
        rw, rh2, zb = rect
        if i == 2:
            out += _oriel("gh_or", Tb2, 3.4, 1.55, 0.72, wd, glass, void, lights=3,
                          sill_mat=wood)
        elif i in (1, 3):
            out += _win("gh_f2w%d" % i, Tb2 @ Ts(xb, 0.20, zb + 0.46), rw * 0.58, rh2 - 0.98,
                        wd, glass, void, lights=3, arch=False, depth=0.30, jamb=0.14)
        elif i in (0, 4):
            out += _oculus("gh_f2o%d" % i, Tb2 @ Ts(xb, 0.02, 1.30), 0.62, wd, glass, n=14)
    for s in (-1, 1):
        Te2 = Ts(s * U2X, 0, Z2) @ RZ(-s * math.pi * 0.5)
        for i in range(5):
            yb = -U2Y + 3.68 + i * 3.68
            objs, rect = _frame_bay("gh_s2b%d_%d" % (s, i), Te2 @ Ts(yb, 0, 0),
                                    2 * U2Y / 5.0, H2, wd, plaster, braces=2, mid=0.62,
                                    stud=0.34)
            out += objs
    Tb2b = Ts(0, U2Y, Z2)
    for i in range(5):
        xb = -U2X + 3.68 + i * 3.68
        objs, rect = _frame_bay("gh_b2b%d" % i, Tb2b @ Ts(xb, 0, 0), 2 * U2X / 5.0, H2,
                                wd, plaster, braces=2, mid=0.62, stud=0.34)
        out += objs
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box("gh_cp%d%d" % (sx, sy),
                           Ts(sx * (U2X - 0.15), sy * (U2Y - 0.15), (Z2 + ZE) * 0.5),
                           (0.36, 0.36, H2), wd, bev=0.015))

    # ------------------------------------------------------------- 2.5 roof
    roof_objs, hw, rh, hdg = _roof("gh_rf", Ts(0, 0, ZE), 2 * U2X, RIDGE_LEN, 0.0,
                                   PITCH, W["tile_blue"], wd, plaster, verge=0.55,
                                   course_h=0.34, alt=W["tile_blue_lt"], tile_w=0.38,
                                   tile_h=0.25, seed=23)
    out += roof_objs
    # projecting rafter ends along both eaves (the roof edge needs a shadow)
    for s in (-1, 1):
        out += _rafter_row("gh_rt%d_" % s, Ts(s * (hw - 0.10), 0, ZE - 0.28),
                           RIDGE_LEN - 0.5, wd, step=0.42, w=0.26, h=0.28, d=0.20,
                           axis="y", rng=rng)
    # joist ends under both jettied floors: each oversailing storey has to show
    # the ends of the joists that carry it, otherwise the jetty is a floating box
    for s in (-1, 1):
        out += _rafter_row("gh_je1%d_" % s, Ts(0, s * (U1Y - 0.02), Z1 - 0.26),
                           2 * U1X - 0.2, wd, step=0.28, w=0.14, h=0.22, d=0.34,
                           axis="x", rng=rng)
        out += _rafter_row("gh_jex1%d_" % s, Ts(s * (U1X - 0.02), 0, Z1 - 0.26),
                           2 * U1Y - 0.2, wd, step=0.28, w=0.14, h=0.22, d=0.34,
                           axis="y", rng=rng)
        out += _rafter_row("gh_je2%d_" % s, Ts(0, s * (U2Y - 0.02), Z2 - 0.24),
                           2 * U2X - 0.2, wd, step=0.28, w=0.13, h=0.20, d=0.30,
                           axis="x", rng=rng)
        out += _rafter_row("gh_jex2%d_" % s, Ts(s * (U2X - 0.02), 0, Z2 - 0.24),
                           2 * U2Y - 0.2, wd, step=0.28, w=0.13, h=0.20, d=0.30,
                           axis="y", rng=rng)
    # front gable (facing the square)
    for s in (-1, 1):
        Tg = Ts(0, s * (hdg + 0.06), ZE) @ (RZ(0) if s < 0 else RZ(math.pi))
        out += _gable_frame("gh_gf%d" % s, Tg, hw, rh, wd, plaster, stud=0.52,
                            skip=(-3.4, 3.4))
        out.append(box("gh_gkp%d" % s, Tg @ Ts(0, 0.03, rh * 0.44), (0.26, 0.28, rh * 0.88),
                       wd, bev=0.012))
        out.append(box("gh_gcol%d" % s, Tg @ Ts(0, 0.03, rh * 0.68), (7.4, 0.28, 0.26), wd,
                       bev=0.012))
        out.append(box("gh_gsp%d" % s, Tg @ Ts(0, 0.03, rh * 0.10), (6.4, 0.26, 0.24), wd,
                       bev=0.012))
        for k in (-1, 1):
            o = _seg("gh_gb%d%d" % (s, k), Tg @ Ts(0, 0.03, 0), (k * 3.55, rh * 0.55),
                     (k * 6.3, rh * 0.24), 0.20, 0.26, wd, bev=0.008)
            if o:
                out.append(o)
        # great gable window (kept clear of the collar and of the crest above it)
        # NOTE: _win builds its glazing on the local -Y side, so the -Y gable
        # needs the frame turned round or the dark reveal lands in front of the
        # panes and the window reads as a black panel
        Twg = Tg if s > 0 else Tg @ Matrix.Rotation(math.pi, 4, "Z")
        out += _win("gh_gw%d" % s, Twg @ Ts(0, 0.26, 1.45), 3.60, 1.90, wd, glass, void,
                    lights=5, arch=True, depth=0.36, hood=True, jamb=0.22)
        for k in (-1, 1):
            out += _win("gh_gs%d%d" % (s, k), Twg @ Ts(k * 6.0, 0.24, 1.15), 0.95, 1.35,
                        wd, glass, void, lights=2, arch=False, depth=0.24, jamb=0.10,
                        mull=0.05)
    # crest high on the gable, clear of the window head (window top = 5.30)
    out += _crest("gh_cr", Ts(0, -(hdg + 0.16), ZE + 5.72), 1.95, 1.85, gold, pale,
                  W["banner_blue"], iron)
    out.append(cyl("gh_fin", Ts(0, -(hdg + 0.16), ZE + 7.90), 0.055, 0.85, lead, seg=8))
    out.append(sphere("gh_fb", Ts(0, -(hdg + 0.16), ZE + 8.40), 0.13, gold, seg=12, ring=8))
    out.append(box("gh_fv", Ts(0, -(hdg + 0.16), ZE + 8.75), (0.06, 0.06, 0.5), iron))
    # carved bargeboards
    for s in (-1, 1):
        for k in (-1, 1):
            out.append(box("gh_bb%d%d" % (s, k),
                           Ts(k * hw * 0.5, s * (hdg + 0.20), ZE + rh * 0.5,
                              ry=math.atan2(-rh, -k * hw)),
                           (math.hypot(hw, rh), 0.12, 0.44), wd, bev=0.02))
            # scalloped cusps along the bargeboard
            nb = 9
            for j in range(nb):
                t = (j + 0.5) / nb
                out.append(box("gh_bc%d%d%d" % (s, k, j),
                               Ts(k * hw * (1 - t), s * (hdg + 0.28), ZE + rh * t),
                               (math.hypot(hw, rh) / nb * 0.55, 0.20, 0.20), wood,
                               bev=0.01))
    # turret at the +X front corner
    out += _turret("gh_tu", Ts(U2X + 0.55, -U2Y + 1.35, 0), 1.30, 12.2, stone, lead,
                   glass, void, gold)
    # dormers on both long slopes: front must land on the slope, so put the
    # origin at |x| = 10.43 - (10.83-9.40)/tan(42) = 8.84, and turn the front
    # (local -Y) to face +-X
    for i, yd in enumerate((-7.5, 2.0)):
        for s in (-1, 1):
            out += _dormer("gh_dm%d_%d" % (i, s),
                           Ts(s * 8.84, yd, 10.83) @ RZ(s * math.pi * 0.5),
                           1.90, 1.45, 1.5, plaster, W["slate"], wd, glass, void)
    # chimneys
    for i, yy in enumerate((-9.0, 8.0)):
        out += _chimney("gh_ch%d" % i, Ts(6.2, yy, 11.0), 5.4, stone, pots=3,
                        stone_mat=pale)
        out.append(box("gh_cfl%d" % i, Ts(6.2, yy, 10.95), (1.9, 1.75, 0.30), lead,
                       bev=0.02))

    # -------------------------------------------------------- 2.6 fittings
    # banner poles flanking the door
    for s in (-1, 1):
        out += H.banner("gh_bn%d" % s, Ts(s * 2.05, -GY - 0.55, Z1 + 0.30),
                        1.05, 2.6, W["banner_red"] if s < 0 else W["banner_blue"], iron,
                        pole_h=3.6)
    # ceremonial cloth hanging across the gable foot (a banner on a pole would
    # sit in front of the great gable window and read as a gold board)
    out += _cloth("gh_bn2", Ts(0, -(hdg + 0.30), ZE + 1.16) @
                  Matrix.Rotation(math.radians(-90), 4, "X"),
                  4.30, 0.74, [W["banner_gold"]], sag=0.02, folds=9, fold=0.018,
                  seg=22, rows=3, scallop=0.055, rng=rng)
    out.append(cyl("gh_bnr", Ts(0, -(hdg + 0.28), ZE + 1.18) @
                   Matrix.Rotation(math.pi * 0.5, 4, "Y"), 0.035, 4.5, iron, seg=8))
    for s in (-1, 1):
        out.append(box("gh_bpl%d" % s, Ts(s * 2.05, -GY - 0.55, Z1 + 0.62),
                       (0.30, 0.30, 0.26), pale, bev=0.02))
    # lantern over the door: K.lantern hangs its cage 0.40 out along local +Y,
    # so the bracket origin must be rotated to point at the square (-Y)
    out += K.lantern("gh_ln", Ts(0, -GY - 0.62, Z1 - 0.25) @ RZ(math.pi), iron,
                     W["glow"], scale=0.78)
    out += H.lantern_post("gh_lp", Ts(5.2, -GY - 1.5, 0), 3.2, iron, W["glow"])
    # hanging guild sign
    out += _sign("gh_sg", Ts(-5.6, -U2Y - 1.15, Z2 + 0.35), 1.25, 1.05, iron, wd, wd,
                 W["banner_gold"], gold)
    # benches, barrels, a cart, sacks
    for i, (bx, by) in enumerate(((-6.6, -16.2), (6.6, -16.2))):
        out += _bench("gh_be%d" % i, Ts(bx, by, 0, rz=0.0), 2.4, pale)
    for i in range(5):
        out.append(H.barrel("gh_ba%d" % i,
                            Ts(-GX - 0.9 + rng.uniform(-0.3, 0.3), -11.2 + i * 0.75,
                               0.42, rz=rng.uniform(0, 3)), 0.30, 0.84, wl, iron))
    out += _crate_pile("gh_cr", Ts(GX + 1.1, -10.4, 0, rz=0.2), rng, wl, W["produce"], n=4)
    out.append(H.cart("gh_ct", Ts(-2.0, -19.6, 0, rz=0.9), wl, iron, L=2.4, W=1.2))
    out += _sacks("gh_sa", Ts(GX + 1.0, -4.0, 0), rng, W["canvas"])
    for i, (px, py) in enumerate(((-3.1, -15.4), (4.0, -15.0), (1.2, -16.6),
                                  (-6.0, -14.6), (6.4, -16.4))):
        out += _pigeon("gh_pg%d" % i, Ts(px, py, 0.02, rz=rng.uniform(0, 6.2)),
                       W["slate"], W["iron_warm"])
    return _flat(out)


# ==========================================================================
# 3. FOUNTAIN
# ==========================================================================
def _ring_slabs(name, T, r0, r1, n, mats, thick=0.055, z=0.0, gap=0.035, rng=None,
                a0=0.0, a1=math.pi * 2):
    """One concentric ring of paving slabs as a single mesh per material."""
    buf = [[] for _ in mats]
    for i in range(n):
        aa = a0 + (a1 - a0) * (i + 0.5) / n
        da = (a1 - a0) / n
        if abs(da) > math.pi * 2 - 1e-6:
            pass
        rin, rout = r0, r1
        c, s = math.cos(aa), math.sin(aa)
        ang = [aa - da * 0.5 + gap, aa + da * 0.5 - gap]
        ring = []
        for rr in (rin, rout):
            for a in ang:
                ring.append((math.cos(a) * rr, math.sin(a) * rr))
        vs = []
        for zz in (z, z + thick):
            for (x, y) in ring:
                vs.append((x, y, zz))
        f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        k = 0 if rng is None else rng.randrange(len(mats))
        buf[k].append((vs, f))
    out = []
    for k, chunk in enumerate(buf):
        if not chunk:
            continue
        verts, faces = [], []
        for vs, f in chunk:
            b = len(verts)
            verts.extend(vs)
            faces.extend([tuple(b + i for i in ff) for ff in f])
        out.append(H.poly("%s_%d" % (name, k), verts, faces, mats[k], T))
    return out


def _pave_disc(name, T, r_out, r_in, rings, n, mats, rng, thick=0.06, z=0.0):
    """Paved apron: rings of radial slabs between r_in and r_out."""
    out = []
    for k in range(rings):
        ra = r_in + (r_out - r_in) * k / rings
        rb = r_in + (r_out - r_in) * (k + 1) / rings
        nn = int(n * (ra + rb) * 0.5 / max(0.5, (r_out + r_in) * 0.5))
        nn = max(8, nn)
        out += _ring_slabs("%s%d" % (name, k), T, ra + 0.02, rb - 0.02, nn, mats,
                           thick=thick, z=z + (k % 2) * 0.004, rng=rng)
    return out


def _flag_field(name, T, x0, x1, y0, y1, cw, ch, mats, rng, gap=0.04,
                thick=0.05, wear=0.006):
    """Running-bond flagstones filling a rectangle, one mesh per material.

    A painted-on paving line reads as a stripe at distance; individually laid
    stones with a 4 cm joint and a little height jitter read as pavement even
    at 90 m because the joints shade differently on every course.
    """
    buckets = {i: ([], []) for i in range(len(mats))}
    nx = max(1, int((x1 - x0) / cw))
    ny = max(1, int((y1 - y0) / ch))
    for j in range(ny):
        yy = y0 + (y1 - y0) * j / ny
        hh = (y1 - y0) / ny
        shift = (cw * 0.5) if (j % 2) else 0.0
        for i in range(nx + 1):
            xx = x0 + (x1 - x0) * i / nx - shift
            ww = (x1 - x0) / nx
            xa, xb = max(x0, xx + gap * 0.5), min(x1, xx + ww - gap * 0.5)
            if xb - xa < 0.12:
                continue
            ya, yb = yy + gap * 0.5, yy + hh - gap * 0.5
            zz = rng.uniform(-wear, wear) + (0.0 if (i + j) % 3 else 0.004)
            k = rng.randrange(len(mats))
            v, f = buckets[k]
            b = len(v)
            v += [T @ Vector((xa, ya, zz)), T @ Vector((xb, ya, zz)),
                  T @ Vector((xb, yb, zz)), T @ Vector((xa, yb, zz)),
                  T @ Vector((xa, ya, zz - thick)), T @ Vector((xb, ya, zz - thick)),
                  T @ Vector((xb, yb, zz - thick)), T @ Vector((xa, yb, zz - thick))]
            f += [[b, b + 1, b + 2, b + 3], [b + 4, b + 7, b + 6, b + 5],
                  [b, b + 4, b + 5, b + 1], [b + 1, b + 5, b + 6, b + 2],
                  [b + 2, b + 6, b + 7, b + 3], [b + 3, b + 7, b + 4, b]]
    out = []
    for k, (v, f) in buckets.items():
        if v:
            out.append(H.poly("%s_%d" % (name, k), v, f, mats[k]))
    return out


def _water_disc(name, T, r, mat, seg=64, rings=14, amp=0.012, wl=0.9, thick=0.03):
    """Water surface as a displaced disc: real ripples, not a flat plane."""
    verts, faces = [], []
    for ri in range(rings + 1):
        rr = r * ri / rings
        for si in range(seg):
            a = 2.0 * math.pi * si / seg
            dz = amp * math.sin(rr / wl * 6.283) * math.cos(a * 3.0 + rr * 0.7)
            verts.append(T @ Vector((math.cos(a) * rr, math.sin(a) * rr,
                                     dz + (0.0 if ri else 0.0))))
    for ri in range(rings):
        for si in range(seg):
            s2 = (si + 1) % seg
            a = ri * seg + si
            b = ri * seg + s2
            c = (ri + 1) * seg + s2
            d = (ri + 1) * seg + si
            faces.append((a, b, c, d))
    return [H.poly(name, verts, faces, mat)]


def fountain(MAT, rng):
    MAT = _palette(MAT)
    W = MAT
    stone = W["stone_warm"]
    pale = W["stone_pale"]
    warm = W["stone_warm"]
    dark = W["stone_dark"]
    bronze = W["bronze"]
    gold = W["gold"]
    iron = W["iron"]
    water = W["water"]
    jet = W["water_jet"]
    lead = W["lead"]
    out = []
    T0 = Ts(0, 0, 0)

    R_OUT, R_IN = 5.16, 4.55
    # ------------------------------------------------------------- 3.1 steps
    # five worn treads rather than three: a 12 m octagon needs a shallow rise
    # to read as something you can walk up
    steps = [(5.95, 0.085), (5.80, 0.085), (5.66, 0.085), (5.53, 0.085),
             (5.42, 0.085)]
    z = 0.0
    for i, (r, h) in enumerate(steps):
        pts = _oct_pts(r, phase=math.pi / 8, jitter=0.014, rng=rng)
        out.append(H.prism("ft_st%d" % i, T0 @ Ts(0, 0, z + h * 0.5), pts, h, pale,
                           axis="z"))
        z += h
        # a chipped nosing block every 20 degrees on each tread
        for k in range(18):
            a = math.pi / 18 + k * math.pi / 9
            out.append(box("ft_sn%d_%d" % (i, k),
                           Ts(math.cos(a) * (r - 0.05), math.sin(a) * (r - 0.05),
                              z - 0.014, rz=a),
                           (0.44, 0.10, 0.035), warm, bev=0.006))
    ZT = z
    # kerb ring of small blocks around the lowest step (worn treads)
    n = 40
    for i in range(n):
        a = math.pi * 2 * i / n
        rr = 5.97
        out.append(box("ft_kb%d" % i,
                       T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, 0.05, rz=a),
                       (0.30, 0.22, 0.10), warm, bev=0.012))

    # ------------------------------------------------------- 3.2 basin and lip
    prof = [(R_OUT, 0.00), (R_OUT, 0.40), (R_OUT + 0.13, 0.46), (R_OUT + 0.13, 0.57),
            (R_OUT - 0.04, 0.64), (R_IN + 0.30, 0.64), (R_IN + 0.06, 0.55),
            (R_IN, 0.40), (R_IN, 0.05), (R_OUT, 0.00)]
    out.append(H.lathe("ft_bsn", prof, stone, seg=8,
                       T=T0 @ Ts(0, 0, ZT) @ RZ(math.pi / 8), smooth=False,
                       close_bottom=False, close_top=False))
    # carved panels on the eight outer faces
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        rr = R_OUT + 0.01
        Tp = T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT) @ RZ(a + math.pi * 0.5)
        out += _panel("ft_pn%d" % i, Tp, 1.95, 0.40, stone, depth=0.10, z=0.07,
                      frame=0.07, fr_mat=pale)
        out.append(box("ft_pb%d" % i, Tp @ Ts(0, -0.02, 0.30), (0.34, 0.10, 0.24), pale,
                       bev=0.01))
    # rope moulding under the lip: ring of half-round blocks
    nb = 88
    for i in range(nb):
        a = 2 * math.pi * i / nb
        rr = R_OUT + 0.14
        out.append(box("ft_rm%d" % i,
                       T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT + 0.44, rz=a),
                       (0.06, 0.16, 0.13), pale, bev=0.02))
    # dentil course under the rope and modillions over it
    for i in range(64):
        a = 2 * math.pi * (i + 0.5) / 64
        rr = R_OUT + 0.10
        out.append(box("ft_dt%d" % i,
                       T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT + 0.30, rz=a),
                       (0.10, 0.09, 0.08), pale, bev=0.006))
    for i in range(16):
        a = 2 * math.pi * i / 16
        rr = R_OUT + 0.20
        out.append(box("ft_md%d" % i,
                       T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT + 0.55, rz=a),
                       (0.22, 0.24, 0.09), pale, bev=0.01))
    # eight carved lion masks on the outer face, feeding the basin
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        rr = R_OUT + 0.10
        Tp = T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT + 0.20) @ RZ(a + math.pi * 0.5)
        out.append(box("ft_lh%d" % i, Tp @ Ts(0, -0.10, 0), (0.40, 0.20, 0.34), pale,
                       bev=0.03))
        out.append(box("ft_ls%d" % i, Tp @ Ts(0, -0.22, -0.04), (0.24, 0.16, 0.18), pale,
                       bev=0.02))
        for s in (-1, 1):
            out.append(sphere("ft_le%d_%d" % (i, s), Tp @ Ts(s * 0.10, -0.20, 0.08),
                              0.045, pale, seg=8, ring=6))
            out.append(box("ft_lm%d_%d" % (i, s), Tp @ Ts(s * 0.17, -0.04, 0.02),
                           (0.10, 0.16, 0.20), stone, bev=0.02))
    # basin floor
    out.append(cyl("ft_flr", T0 @ Ts(0, 0, ZT + 0.06), R_IN + 0.02, 0.08, dark, seg=8))
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        out.append(H.prism("ft_fp%d" % i,
                           T0 @ Ts(math.cos(a) * 3.0, math.sin(a) * 3.0, ZT + 0.11, rz=a),
                           [(-1.0, -0.7), (1.0, -0.7), (1.0, 0.7), (-1.0, 0.7)], 0.04,
                           stone, axis="z"))

    # water surface in the basin: a displaced disc so the ripples are real
    # geometry as well as a bump-mapped normal
    out += _water_disc("ft_wt", Ts(0, 0, ZT + 0.50), R_IN + 0.01, water, seg=96,
                       rings=26, amp=0.016, wl=1.05)
    # concentric ripple rings on the surface (flat annuli, not discs: discs read
    # as lily pads from above)
    for i in range(12):
        rr = 0.72 + i * 0.31
        out.append(H.lathe("ft_wr%d" % i,
                           [(rr, 0.0), (rr + 0.09, 0.0), (rr + 0.09, 0.012),
                            (rr, 0.012), (rr, 0.0)],
                           water, seg=64, T=Ts(0, 0, ZT + 0.515), smooth=False,
                           close_bottom=False, close_top=False))

    # --------------------------------------------------------- 3.3 spout heads
    for i in range(4):
        a = math.pi * 0.5 * i
        rr = R_IN - 0.02
        Tp = T0 @ Ts(math.cos(a) * rr, math.sin(a) * rr, ZT + 0.50) @ RZ(a + math.pi * 0.5)
        # carved beast head on the inner face of the lip
        out.append(box("ft_hd%d" % i, Tp @ Ts(0, -0.20, 0.06), (0.46, 0.44, 0.40), pale,
                       bev=0.03))
        out.append(box("ft_hs%d" % i, Tp @ Ts(0, -0.44, 0.02), (0.30, 0.30, 0.26), pale,
                       bev=0.025))
        out.append(box("ft_hj%d" % i, Tp @ Ts(0, -0.60, -0.02), (0.20, 0.24, 0.16), pale,
                       bev=0.02))
        for s in (-1, 1):
            out.append(sphere("ft_he%d_%d" % (i, s), Tp @ Ts(s * 0.14, -0.34, 0.20),
                              0.055, pale, seg=8, ring=6))
        out.append(cyl("ft_hw%d" % i, Tp @ Ts(0, -0.44, -0.30), 0.045, 0.55, jet, seg=8))
        out.append(sphere("ft_hp%d" % i, Tp @ Ts(0, -0.44, -0.62), 0.11, jet, seg=8,
                          ring=6, squash=0.5))

    # ------------------------------------------------------------ 3.4 central pier
    ZP = ZT + 0.10
    pier_prof = [(1.30, 0.00), (1.30, 0.20), (1.08, 0.26), (0.98, 0.40), (0.72, 0.48),
                 (0.66, 0.60), (0.62, 1.55), (0.56, 1.62), (0.60, 1.70), (0.52, 1.78),
                 (0.50, 2.05), (0.64, 2.14), (0.66, 2.22), (0.44, 2.28), (0.40, 2.55)]
    out.append(H.lathe("ft_pr", pier_prof, stone, seg=8,
                       T=T0 @ Ts(0, 0, ZP) @ RZ(math.pi / 8), smooth=False))
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        Tp = T0 @ Ts(math.cos(a) * 0.63, math.sin(a) * 0.63, ZP) @ RZ(a + math.pi * 0.5)
        out += _panel("ft_pp%d" % i, Tp, 0.52, 0.72, stone, depth=0.09, z=0.72,
                      frame=0.06, fr_mat=pale)

    # ----------------------------------------------------------- 3.5 bowls
    # lower bowl
    ZB1 = ZP + 2.28
    b1 = [(0.20, 0.00), (0.95, 0.04), (1.30, 0.16), (1.72, 0.40), (1.94, 0.62),
          (2.00, 0.72), (1.94, 0.80), (1.80, 0.72), (1.60, 0.46), (1.12, 0.22),
          (0.34, 0.16)]
    out.append(_loft("ft_bl1", T0 @ Ts(0, 0, ZB1), b1, pale, seg=52, smooth=True,
                     cap_bottom=False, cap_top=False))
    # a carved band under the bowl, so the underside is not a bare dark cone
    out.append(H.lathe("ft_bu1", [(0.30, 0.00), (0.86, -0.10), (0.94, -0.16),
                                  (0.88, -0.22), (0.26, -0.12)],
                       stone, seg=24, T=T0 @ Ts(0, 0, ZB1 + 0.06), smooth=True,
                       close_bottom=False, close_top=False))
    for i in range(16):
        a = 2 * math.pi * i / 16
        out.append(box("ft_bg1%d" % i,
                       T0 @ Ts(math.cos(a) * 1.93, math.sin(a) * 1.93, ZB1 + 0.70, rz=a),
                       (0.06, 0.14, 0.14), pale, bev=0.02))
    # gadroons: carved ribs on the underside cone, so the bowl is not a smooth
    # glazed dish when a low camera sees it from below
    for i in range(24):
        a = 2 * math.pi * i / 24.0
        out += _limb("ft_gr1%d" % i,
                     T0 @ Vector((math.cos(a) * 1.76, math.sin(a) * 1.76, ZB1 + 0.64)),
                     T0 @ Vector((math.cos(a) * 0.40, math.sin(a) * 0.40, ZB1 + 0.20)),
                     0.045, 0.030, stone, seg=6)
    out += _water_disc("ft_w1", Ts(0, 0, ZB1 + 0.63), 1.80, water, seg=72, rings=18,
                       amp=0.010, wl=0.7)
    # upper bowl
    ZB2 = ZP + 3.28
    b2 = [(0.16, 0.00), (0.62, 0.03), (0.90, 0.13), (1.14, 0.30), (1.28, 0.44),
          (1.32, 0.52), (1.26, 0.59), (1.14, 0.52), (1.02, 0.34), (0.72, 0.16),
          (0.26, 0.12)]
    out.append(_loft("ft_bl2", T0 @ Ts(0, 0, ZB2), b2, pale, seg=46, smooth=True,
                     cap_bottom=False, cap_top=False))
    out.append(H.lathe("ft_bu2", [(0.24, 0.00), (0.66, -0.07), (0.72, -0.12),
                                  (0.66, -0.17), (0.22, -0.09)],
                       stone, seg=22, T=T0 @ Ts(0, 0, ZB2 + 0.04), smooth=True,
                       close_bottom=False, close_top=False))
    for i in range(12):
        a = 2 * math.pi * i / 12
        out.append(box("ft_bg2%d" % i,
                       T0 @ Ts(math.cos(a) * 1.26, math.sin(a) * 1.26, ZB2 + 0.51, rz=a),
                       (0.05, 0.11, 0.11), pale, bev=0.015))
    for i in range(16):
        a = 2 * math.pi * i / 16.0
        out += _limb("ft_gr2%d" % i,
                     T0 @ Vector((math.cos(a) * 1.12, math.sin(a) * 1.12, ZB2 + 0.48)),
                     T0 @ Vector((math.cos(a) * 0.30, math.sin(a) * 0.30, ZB2 + 0.16)),
                     0.036, 0.024, stone, seg=6)
    out += _water_disc("ft_w2", Ts(0, 0, ZB2 + 0.45), 1.20, water, seg=60, rings=14,
                       amp=0.008, wl=0.5)
    # spirelet / finial column carrying the figure
    ZS2 = ZB2 + 0.58
    out.append(H.lathe("ft_col", [(0.30, 0.0), (0.26, 0.10), (0.22, 0.50), (0.26, 0.60),
                                  (0.22, 0.72)], stone, seg=12,
                       T=T0 @ Ts(0, 0, ZS2), smooth=False))

    # ------------------------------------------------------------ 3.6 figure
    ZF = ZS2 + 0.74
    SH = ZF + 1.42                      # shoulder line
    out.append(H.lathe("ft_fpl", [(0.46, 0.0), (0.47, 0.06), (0.42, 0.11),
                                  (0.36, 0.14)], stone, seg=16,
                       T=T0 @ Ts(0, 0, ZF - 0.15), smooth=False))
    # robe: heavy hem, flared skirt, deep vertical folds
    robe = [(0.00, 0.42, 0.37), (0.06, 0.41, 0.36), (0.16, 0.38, 0.33),
            (0.32, 0.34, 0.29), (0.52, 0.30, 0.26), (0.74, 0.27, 0.23),
            (0.94, 0.25, 0.21), (1.04, 0.23, 0.20)]
    out.append(_loft("ft_robe", T0 @ Ts(0, 0, ZF), robe, bronze, seg=44, fold=0.070,
                     folds=9))
    out.append(H.lathe("ft_hem", [(0.43, 0.0), (0.44, 0.035), (0.42, 0.075),
                                  (0.40, 0.10)], bronze, seg=44,
                       T=T0 @ Ts(0, 0, ZF - 0.01), smooth=True,
                       close_bottom=False, close_top=False))
    # torso with a chest and a narrow waist
    torso = [(1.04, 0.23, 0.20), (1.14, 0.26, 0.19), (1.26, 0.27, 0.18),
             (1.36, 0.26, 0.17), (1.44, 0.22, 0.15), (1.50, 0.16, 0.12)]
    out.append(_loft("ft_tor", T0 @ Ts(0, 0, ZF), torso, bronze, seg=28, fold=0.018,
                     folds=5))
    for s in (-1, 1):
        out.append(sphere("ft_sh%d" % s, T0 @ Ts(s * 0.19, 0, SH), 0.115, bronze,
                          seg=12, ring=8, squash=0.92))
    # cloak falling off the left shoulder down the back: the cloth's scalloped
    # free edge has to end at the hem, so the sheet is rotated the other way
    # round (a +94 deg tilt puts the cusped edge round the figure's head and
    # reads as a crown of spikes)
    out += _cloth("ft_clk", T0 @ Ts(-0.16, 0.09, SH + 0.04) @
                  Matrix.Rotation(math.radians(-94), 4, "X"),
                  0.60, 1.16, [bronze], sag=0.035, folds=6, fold=0.026, seg=12,
                  rows=8, scallop=0.07, thick=0.02)
    # right arm raised out and up, ewer in the hand
    p_sh_r = T0 @ Vector((0.19, 0.0, SH - 0.02))
    p_hd_r = T0 @ Vector((0.60, 0.03, SH + 0.50))
    out += _limb("ft_ua1", p_sh_r, p_hd_r, 0.078, 0.052, bronze, seg=12)
    out.append(sphere("ft_el1", Matrix.Translation(p_hd_r), 0.055, bronze, seg=10, ring=6))
    p_ew = T0 @ Vector((0.66, 0.02, SH + 0.58))
    out += _limb("ft_fa1", p_hd_r, p_ew, 0.052, 0.045, bronze, seg=10)
    # left arm hangs down and forward, gripping the staff
    p_sh_l = T0 @ Vector((-0.19, 0.0, SH - 0.02))
    p_hd_l = T0 @ Vector((-0.33, 0.10, SH - 0.52))
    out += _limb("ft_ua2", p_sh_l, p_hd_l, 0.078, 0.052, bronze, seg=12)
    out.append(sphere("ft_el2", Matrix.Translation(p_hd_l), 0.055, bronze, seg=10, ring=6))
    p_st = T0 @ Vector((-0.37, 0.13, SH - 0.62))
    out += _limb("ft_fa2", p_hd_l, p_st, 0.052, 0.042, bronze, seg=10)
    # the ewer, tipped so it pours into the top bowl
    Tew = Matrix.Translation(p_ew) @ Matrix.Rotation(math.radians(-24), 4, "Y")
    out.append(H.lathe("ft_ew", [(0.09, 0.0), (0.16, 0.10), (0.15, 0.26),
                                 (0.08, 0.34), (0.10, 0.42)], bronze, seg=14,
                       T=Tew, smooth=True, close_bottom=True))
    out.append(box("ft_ewh", Tew @ Ts(0.19, 0, 0.30, ry=math.radians(-34)),
                   (0.09, 0.06, 0.28), bronze))
    out.append(box("ft_ews", Tew @ Ts(-0.17, 0, 0.34, ry=math.radians(30)),
                   (0.06, 0.05, 0.22), bronze))
    # head in a deep cowl, with a face plane and a beard
    out.append(cyl("ft_nk", T0 @ Ts(0, 0, SH + 0.10), 0.062, 0.12, bronze, seg=10))
    out.append(sphere("ft_hd", T0 @ Ts(0, -0.01, SH + 0.24), 0.125, bronze, seg=16,
                      ring=12))
    out.append(_loft("ft_cowl", T0 @ Ts(0, 0.01, SH + 0.10),
                     [(0.0, 0.20, 0.19), (0.13, 0.21, 0.20), (0.26, 0.18, 0.17),
                      (0.34, 0.12, 0.11)], bronze, seg=16, cap_bottom=False))
    out.append(box("ft_face", T0 @ Ts(0, -0.11, SH + 0.23), (0.15, 0.05, 0.17),
                   bronze, bev=0.02))
    out.append(cone("ft_brd", T0 @ Ts(0, -0.10, SH + 0.10) @
                    Matrix.Rotation(math.radians(-10), 4, "X"), 0.085, 0.22, bronze,
                    seg=8))
    # staff in the left hand, with a gold orb
    out.append(cyl("ft_stf", T0 @ Ts(-0.56, 0.20, SH - 0.46), 0.030, 2.30, iron, seg=8))
    out.append(sphere("ft_stb", T0 @ Ts(-0.56, 0.20, SH + 0.70), 0.075, gold, seg=10,
                      ring=6))
    # falling jets: thin arcs that leave each lip and land in the water below
    out += _jet_arc("ft_j1", T0, 0.70, SH + 0.44, 0.58, ZB2 + 0.46, jet, rad=0.018,
                    rings=10, seg=6, bow=0.08, sway=0.012)
    for i in range(8):
        a = 2 * math.pi * i / 8
        out += _jet_arc("ft_j2_%d" % i, T0 @ RZ(a), 1.28, ZB2 + 0.55, 1.80,
                        ZB1 + 0.68, jet, rad=0.014, rings=8, seg=6, bow=0.12,
                        sway=0.010)
        out.append(sphere("ft_sp%d" % i,
                          T0 @ Ts(math.cos(a) * 1.80, math.sin(a) * 1.80, ZB1 + 0.68),
                          0.075, jet, seg=8, ring=6, squash=0.30))
    for i in range(10):
        a = 2 * math.pi * i / 10
        out += _jet_arc("ft_j3_%d" % i, T0 @ RZ(a), 1.96, ZB1 + 0.74, 2.40,
                        ZT + 0.54, jet, rad=0.013, rings=9, seg=6, bow=0.15,
                        sway=0.012)
        out.append(sphere("ft_sq%d" % i,
                          T0 @ Ts(math.cos(a) * 2.40, math.sin(a) * 2.40, ZT + 0.54),
                          0.090, jet, seg=8, ring=6, squash=0.24))
    # (the over-lip veils were removed: a bright translucent band floating just
    # above each lip read as a sheet of acetate, and the jets alone carry it)

    # ------------------------------------------------- 3.7 surroundings
    # paved apron: concentric rings of worn slabs, laid radially around the
    # octagon so the fountain sits in a real paved platform
    out += _pave_disc("ft_pv", Ts(0, 0, 0.015), 6.32, 5.55, 14, 140,
                      [pale, stone, warm], rng, thick=0.055)
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        out.append(box("ft_pk%d" % i,
                       Ts(math.cos(a) * 6.36, math.sin(a) * 6.36, 0.06, rz=a),
                       (0.30, 1.60, 0.12), warm, bev=0.02))
    out.append(cyl("ft_kerb", T0 @ Ts(0, 0, 0.03), 6.18, 0.09, warm, seg=8))
    # bollards with a sagging chain ring the pavement
    for i in range(16):
        a = 2 * math.pi * i / 16
        bx, by = math.cos(a) * 6.16, math.sin(a) * 6.16
        out.append(H.lathe("ft_bl%d" % i,
                           [(0.16, 0.0), (0.15, 0.10), (0.11, 0.16), (0.10, 0.62),
                            (0.13, 0.70), (0.09, 0.78)],
                           warm, seg=8, T=Ts(bx, by, 0.0), smooth=False))
        out.append(sphere("ft_bb%d" % i, Ts(bx, by, 0.86), 0.11, iron, seg=8, ring=6))
        a2 = 2 * math.pi * (i + 0.5) / 16
        for k in range(3):
            b1 = a + (a2 - a) * (0.25 + k * 0.25)
            out.append(sphere("ft_bc%d_%d" % (i, k),
                              Ts(math.cos(b1) * 6.16, math.sin(b1) * 6.16,
                                 0.60 - 0.07 * abs(k - 1)),
                              0.045, iron, seg=6, ring=4, squash=0.5))
    for i, (bx, by, rz) in enumerate(((-5.4, -5.0, 0.0), (5.4, -5.0, 0.0),
                                      (0.0, 6.1, math.pi))):
        out += _bench("ft_bn%d" % i, Ts(bx, by, 0, rz=rz), 2.4, pale)
    for i, (px, py) in enumerate(((-2.2, -4.9), (2.6, -4.6), (0.4, -5.3), (-3.4, 2.4),
                                  (3.8, 2.0), (1.2, 5.2), (-1.6, 5.4), (4.4, -1.2),
                                  (-4.6, -1.8), (5.2, 3.4), (-5.2, 3.0), (2.2, -2.6),
                                  (-2.8, 0.6), (3.0, 4.6), (-3.9, 4.2), (0.8, 2.9),
                                  (4.9, 4.9), (-5.6, -3.6), (5.7, -4.2), (1.9, -4.0),
                                  (-0.9, -3.4), (3.4, 0.4), (-4.2, 0.2), (0.2, 4.4),
                                  (-1.1, -1.6), (2.8, -0.8))):
        on = i % 3
        zz = (ZT + 0.64) if on == 0 else (ZT + 0.13 if on == 1 else 0.02)
        out += _pigeon("ft_pg%d" % i,
                       Ts(px * 1.02, py * 1.02, zz, rz=rng.uniform(0, 6.2)),
                       W["slate"], W["iron_warm"])
    # a pair of stone urns flanking the basin
    for s in (-1, 1):
        out.append(H.lathe("ft_urn%d" % s,
                           [(0.26, 0.0), (0.30, 0.10), (0.20, 0.20), (0.16, 0.28),
                            (0.30, 0.46), (0.34, 0.62), (0.36, 0.70), (0.30, 0.74),
                            (0.32, 0.80)],
                           pale, seg=16, T=T0 @ Ts(s * 6.5, 3.4, 0.0), smooth=True))
        out.append(box("ft_urb%d" % s, T0 @ Ts(s * 6.5, 3.4, 0.06), (0.72, 0.72, 0.12),
                       pale, bev=0.02))
    return _flat(out)


# ==========================================================================
# preview
# ==========================================================================
def _stats(label, parts):
    lo, hi = H.bbox(parts)
    print("[market] %-12s parts=%5d  tris=%6d  bbox=(%.1f,%.1f,%.1f)..(%.1f,%.1f,%.1f)  "
          "size=%.1f x %.1f x %.1f" % (label, len(parts), H.tri_count(parts),
                                      lo[0], lo[1], lo[2], hi[0], hi[1], hi[2],
                                      hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
    return H.tri_count(parts)


def preview():
    H._clear()
    try:
        K._MAT_CACHE.clear()
    except Exception:
        pass
    MAT = make_materials()
    rng = random.Random(20261030)
    H.setup_world(sun_energy=4.4, sky="#a8c8ea")

    print("[market] building landmarks ...")
    mh = market_hall(MAT, rng)
    gh = guild_hall(MAT, rng)
    ft = fountain(MAT, rng)
    tm = _stats("market_hall", mh)
    tg = _stats("guild_hall", gh)
    tf = _stats("fountain", ft)

    # place them on the square: the hall on the left, the guild hall right,
    # the fountain in the middle foreground
    H.apply(mh, Ts(-26.0, 0.0, 0.0))
    H.apply(gh, Ts(26.0, 4.0, 0.0))
    H.apply(ft, Ts(0.0, -31.0, 0.0))

    floor = H.diorama_floor(MAT["ground"], 340)
    pave = []
    prng = random.Random(7717)
    # the open square itself: laid flagstones over a worn bed, running bond,
    # 2.1 x 1.05 m courses so the joints still read at 90 m
    pave += _flag_field("pv_fl", Ts(0, 0, 0.012), -74.0, 74.0, -52.0, 44.0,
                        2.10, 1.05, [MAT["ground_worn"]] * 9 + [MAT["ground"]] * 3 +
                        [MAT["stone_pale"]], prng, gap=0.045, thick=0.10)
    # darker gutter channels running with the square, not painted stripes
    for i in range(3):
        yy = -34.0 + i * 26.0
        pave.append(box("pv_gt%d" % i, Ts(0, yy, 0.008), (150, 0.58, 0.045),
                        MAT["stone_dark"]))
        for s in (-1, 1):
            pave.append(box("pv_gk%d_%d" % (i, s), Ts(0, yy + s * 0.42, 0.016),
                            (150, 0.26, 0.062), MAT["stone_pale"]))
    # paved forecourts in front of each hall (worn, lighter than the road bed)
    pave += _flag_field("pv_fc1", Ts(-26.0, -18.0, 0.030), -21.0, 21.0, -6.6, 6.6,
                        1.60, 1.60, [MAT["stone_pale"]] * 4 + [MAT["stone_warm"]], prng,
                        gap=0.05, thick=0.06)
    pave += _flag_field("pv_fc2", Ts(26.0, -14.0, 0.030), -12.0, 12.0, -7.0, 7.0,
                        1.55, 1.55, [MAT["stone_pale"]] * 4 + [MAT["stone_warm"]], prng,
                        gap=0.05, thick=0.06)
    H.setup_engine(samples=192, res=(1600, 900), gpu=True)
    H.three_views("market", center=(0, 0, 8), size=(90, 50), dist=70)
    H.three_views("market_wide", center=(-3, -4, 8), size=(90, 50), dist=108)

    # close-up 1: the market hall arcade
    cam = H.camera("cu_arc", (-13.0, -31.0, 5.2), (-26.0, -10.0, 5.0), lens=44)
    H.render_to(os.path.join(OUT, "hd_market_arcade.png"), cam)
    # close-up 2: the fountain (framed so the figure, both bowls and the basin
    # all sit inside the frame; the earlier low camera cropped the head)
    cam = H.camera("cu_ft", (12.0, -45.0, 5.6), (0.0, -31.0, 3.6), lens=46)
    H.render_to(os.path.join(OUT, "hd_market_fountain.png"), cam)
    print("[market] done: %d + %d + %d tris = %d"
          % (tm, tg, tf, tm + tg + tf))
    return mh, gh, ft


# --------------------------------------------------------------- module API
# Palette keys this module reads.  The layout engine reconciles 20+ building
# modules against one shared palette, so the list is exported rather than
# discovered by trying keys and catching KeyError.
MAT_KEYS = ("stone", "stone_warm", "stone_pale", "stone_dark", "wood", "wood_dark",
            "wood_light", "wood_pale", "tile", "tile_dark", "tile_blue",
            "tile_blue_lt", "slate", "glass", "iron", "iron_warm", "gold", "bronze",
            "lead", "plaster", "plaster_warm", "banner_red", "banner_blue",
            "banner_gold", "banner_green", "canvas", "canvas_red", "water",
            "water_jet", "water_veil", "glow", "interior", "void", "ground",
            "ground_worn")

# (x, y) extents of each landmark, measured from the built geometry and used by
# the layout engine for spacing.  Market hall and guild hall include their
# street furniture; the fountain includes its paved apron.
FOOTPRINT = {
    "market_hall": (46.0, 29.3),
    "guild_hall": (22.6, 37.9),
    "fountain": (13.7, 12.6),
}

_BUILDERS = {"market_hall": None, "guild_hall": None, "fountain": None}


def footprint(kind):
    """Return (x, y) extents in metres for one of this module's landmarks."""
    return FOOTPRINT[kind]


def build(kind, MAT, rng, at=None, rz=0.0, **kw):
    """Uniform entry point: build one landmark, optionally placed.

    `kind` is one of "market_hall", "guild_hall", "fountain".  `at` is an
    optional (x, y, z) origin; when given the transform is baked into the mesh
    data (this module never leaves a non-identity object matrix behind, so the
    caller can merge or instance freely).  The three original build functions
    keep their signatures and are used directly by anything that predates this
    entry point.
    """
    if _BUILDERS["market_hall"] is None:
        _BUILDERS["market_hall"] = market_hall
        _BUILDERS["guild_hall"] = guild_hall
        _BUILDERS["fountain"] = fountain
    fn = _BUILDERS.get(kind)
    if fn is None:
        raise ValueError("hd_market.build: unknown kind %r (have %s)"
                         % (kind, ", ".join(sorted(_BUILDERS))))
    parts = fn(MAT, rng, **kw)
    if at is not None:
        T = Ts(at[0], at[1], at[2], rz=rz)
        H.apply(parts, T)
    return parts


if __name__ == "__main__":
    preview()
