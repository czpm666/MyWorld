"""hd_castle_int.py - the royal castle interior: throne hall, feast hall, stair tower.

Written for the keep in hd_castle.py.  That file's `keep()` is a solid
30.0 x 22.0 m box spanning z = CY(1.30) .. CY + KEEP_H(42.0) = 43.30, so the
usable void is 30.0 x 22.0 x 42.0 m.  This module's envelope is 28.5 x 20.5 x
30.9 m and therefore drops into it with 0.75 m to spare on every plan side:

    place at  origin = (0.0, -21.0)   (the keep's centre in hd_castle.py)
    lift by   z += 1.30              (CY - the courtyard level the keep stands on)

Everything is authored at its final size with the floor at z = 0 and identity
object transforms (like hd_castle.py, so the caller can `apply()` a transform).

    build(K, MAT, origin=(0,0), rot=0.0, scale=1.0, seed=3)  -> [objects]
    footprint() -> (28.5, 20.5)
    height()    -> 30.9

Axes
    +X  entrance end (the ceremonial door)      -X  throne end
    +Y  the screens side (faces hd_castle's great door, so entering the castle
        you arrive beside the hall and turn west toward the throne)
    +Z  up, floor = 0

Vertical section (design numbers, metres)
    0.00  floor                      9.20  blind-arcade arch apex
    0.48  stone bench seat          9.60  clerestory sill
    1.05  wainscot / dado top      13.40  clerestory head
    6.60  arcade capital           14.00  wall plate  <- NET HEIGHT 14.0
    6.60  arch springing           19.60  roof ridge
                                   20.20  feast-hall floor
Clear plan inside the walls: 26.0 (X) x 18.0 (Y).  NET WIDTH 18.0 m.

Why it is laid out this way: an 18 m clear span is a Westminster-Hall-class
hall, so the roof is a hammerbeam truss; the throne sits on a three-step dais
against the great east window, which is the only opening behind it, so the
window back-lights the throne and nothing competes with the silhouette.

Nothing floats: every truss sits on the wall plate, every banner hangs off a
truss or a wall bracket, every tapestry off a rail let into the wall, every
chandelier off a chain from a truss, every torch out of a niche.
"""

import math
import os
import random

import bpy
from mathutils import Matrix, Vector

import medkit as K
import hd_common as H

OUT = r"E:\My World\Blender\renders\kingdom\look"
TAU = math.pi * 2.0

# ---------------------------------------------------------------------------
# master dimensions
# ---------------------------------------------------------------------------
HX = 13.0                      # clear half length  (X: -13..+13)
HY = 9.0                       # clear half width   (Y: -9..+9)  -> 18.0 net
WT = 1.25                      # wall thickness, built OUTWARD from the clear box
Z_PLATE = 14.00                # net height to the underside of the wall plate
Z_RIDGE = 19.60
Z_FEAST = 20.20                # feast-hall floor
Z_FEAST_TOP = 28.40            # feast-hall clear head
Z_TOP = 30.90                  # top of the feast-hall roof structure

Z_BENCH = 0.48
Z_DADO = 1.05
Z_CAP = 6.60
Z_ARC_APEX = 9.20
Z_CLER_SILL = 9.60
Z_CLER_HEAD = 13.40

NBAY = 6
BAY = 2.0 * HX / NBAY          # 4.3333
BAYX = [-HX + i * BAY for i in range(NBAY + 1)]

# dais / throne
Z_STEP = 0.33
N_STEP = 3
STEP_D = 0.46
Z_DAIS = Z_STEP * N_STEP       # 0.99
DAIS_X0 = -HX                  # dais runs from the east wall
DAIS_X1 = -HX + 4.10
DAIS_HW = 5.60                 # half width of the platform
THR_X = -HX + 1.30             # throne centre
THR_Y = 0.0

# stair tower (a vice in the north-east corner, tangent to both walls)
ST_CX, ST_CY = HX - 3.55, HY - 3.55
ST_R = 3.55                    # outer radius of the shaft
ST_RIN = 2.62                  # clear radius inside
ST_WELL = 0.92                 # radius of the open newel well (the 天井)
ST_RISE = 0.18
ST_PER_REV = 16
ST_TOP = Z_TOP + 0.6
WELL_LAMPS = (13.40, 9.10, 4.70)   # hanging lamps down the stair well

# feast hall
FH_CX, FH_CY = 0.0, 0.0

EYE = 1.72

RZF = {"+y": 0.0, "-y": math.pi, "+x": -math.pi * 0.5, "-x": math.pi * 0.5}


def Ts(x=0.0, y=0.0, z=0.0, rz=0.0, ry=0.0, rx=0.0):
    return K.T_at(x, y, z, rz=rz, ry=ry, rx=rx)


def WF(x, y, z, n="+y"):
    """Frame on an interior wall face: local +X runs along the wall,
    local +Y points OUT of the room."""
    return Ts(x, y, z, rz=RZF[n])


# ---------------------------------------------------------------------------
# mesh helpers
# ---------------------------------------------------------------------------
def bx(nm, T, size, mat, bev=0.0):
    return K.box(nm, T, size, mat, bev=bev)


def cyl(nm, T, r, h, mat, seg=20, r2=None, bev=0.0):
    ob = K.cyl(nm, T, r, h, mat, seg=seg, r2=r2)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def prism_y(nm, T, poly, depth, mat, bev=0.0):
    """Closed polygon in local XZ, extruded along local Y (+-depth/2)."""
    n = len(poly)
    hd = depth * 0.5
    verts = [T @ Vector((u, -hd, v)) for (u, v) in poly]
    verts += [T @ Vector((u, hd, v)) for (u, v) in poly]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = K.mesh_obj(nm, verts, faces)
    K.assign(ob, mat)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def prism_z(nm, T, poly, depth, mat, bev=0.0):
    """Closed polygon in local XY, extruded along local Z (+-depth/2)."""
    n = len(poly)
    hd = depth * 0.5
    verts = [T @ Vector((u, v, -hd)) for (u, v) in poly]
    verts += [T @ Vector((u, v, hd)) for (u, v) in poly]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = K.mesh_obj(nm, verts, faces)
    K.assign(ob, mat)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def loft(nm, T, rings, mat, closed=True, cap0=False, cap1=False, smooth=True):
    """Bridge a list of equal-length point rings into a surface."""
    m = len(rings[0])
    verts = []
    for r in rings:
        for p in r:
            verts.append(T @ Vector(p))
    faces = []
    lim = m if closed else m - 1
    for i in range(len(rings) - 1):
        a, b = i * m, (i + 1) * m
        for j in range(lim):
            k = (j + 1) % m
            faces.append((a + j, a + k, b + k, b + j))
    if cap0:
        faces.append(tuple(range(m - 1, -1, -1)))
    if cap1:
        o = (len(rings) - 1) * m
        faces.append(tuple(range(o, o + m)))
    ob = K.mesh_obj(nm, verts, faces, smooth=smooth)
    K.assign(ob, mat)
    return ob


def arch_curve(hs, spring, rise, nseg=7):
    """Points along a symmetric arch, left springing -> apex -> right springing.

    `hs` half span, `spring` springing height, `rise` apex height above the
    springing.  rise >= hs gives a proper two-centred (pointed) arch; rise < hs
    gives a single-centre segmental arch, which is what the shallow blind
    arcades and the hammerbeam arch want.
    """
    half = []
    if rise >= hs * 0.999:
        R = (hs * hs + rise * rise) / (2.0 * hs)
        c = R - hs
        a_top = math.atan2(rise, -c) if abs(c) > 1e-9 else math.pi * 0.5
        for i in range(nseg + 1):
            a = math.pi + (a_top - math.pi) * i / nseg
            half.append((c + R * math.cos(a), spring + R * math.sin(a)))
    else:
        R = (hs * hs + rise * rise) / (2.0 * rise)
        zc = spring + rise - R
        for i in range(nseg + 1):
            x = -hs + hs * i / nseg
            half.append((x, zc + math.sqrt(max(0.0, R * R - x * x))))
    half[0] = (-hs, spring)
    half[-1] = (0.0, spring + rise)
    out = list(half)
    for (x, z) in reversed(half[:-1]):
        out.append((-x, z))
    return out


def spandrel(nm, T, u0, u1, spring, rise, top, depth, mat, nseg=7, bev=0.0):
    """Solid filling between a pointed arch head and a flat top edge."""
    hs = (u1 - u0) * 0.5
    uc = (u0 + u1) * 0.5
    top = max(top, spring + rise + 0.02)
    arc = arch_curve(hs, spring, rise, nseg)
    poly = [(u0, spring), (u0, top), (u1, top), (u1, spring)]
    for (x, z) in reversed(arc[1:-1]):
        poly.append((uc + x, min(top, z)))
    return prism_y(nm, T, poly, depth, mat, bev=bev)


def ring_voussoir(nm, T, hs, spring, rise, ring, depth, mat, nseg=7, bev=0.012):
    """Moulded voussoir band following a pointed arch, springing to springing."""
    arc = arch_curve(hs, spring, rise, nseg)
    m = len(arc)
    hd = depth * 0.5
    verts = []
    for (x, z) in arc:
        verts.append(T @ Vector((x, -hd, z)))
    for (x, z) in arc:
        verts.append(T @ Vector((x, hd, z)))
    for (x, z) in arc:
        verts.append(T @ Vector((x, -hd, z + ring)))
    for (x, z) in arc:
        verts.append(T @ Vector((x, hd, z + ring)))
    faces = []
    for i in range(m - 1):
        faces.append((i, i + 1, m + i + 1, m + i))                    # soffit
        faces.append((2 * m + i, 2 * m + i + 1, 3 * m + i + 1, 3 * m + i))
        faces.append((i, 2 * m + i, 2 * m + i + 1, i + 1))            # face
        faces.append((m + i, m + i + 1, 3 * m + i + 1, 3 * m + i))
    faces.append((0, m, 3 * m, 2 * m))
    faces.append((m - 1, 2 * m - 1, 3 * m - 1, 4 * m - 1))
    ob = K.mesh_obj(nm, verts, faces)
    K.assign(ob, mat)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def quad_strip(nm, T, rows, mat, closed=False, smooth=False):
    """Bridge a grid of points given as rows of equal length."""
    m = len(rows[0])
    verts = [T @ Vector(p) for r in rows for p in r]
    faces = []
    lim = m if closed else m - 1
    for i in range(len(rows) - 1):
        a, b = i * m, (i + 1) * m
        for j in range(lim):
            k = (j + 1) % m
            faces.append((a + j, a + k, b + k, b + j))
    ob = K.mesh_obj(nm, verts, faces, smooth=smooth)
    K.assign(ob, mat)
    return ob


def solid(ob, t=0.014):
    m = ob.modifiers.new("sol", "SOLIDIFY")
    m.thickness = t
    m.offset = 0.0
    return ob


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
def _emit(name, hexcol, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (0, 0)
    em.inputs["Color"].default_value = K.c(hexcol)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _litglass(name, hexcol, glow=0.55, rough=0.16, tint=1.0):
    """Stained glass: transmits a coloured beam and glows a little itself."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (0, 0)
    col = K.c(hexcol)
    b.inputs["Base Color"].default_value = (col[0] * tint, col[1] * tint,
                                           col[2] * tint, 1.0)
    for nm, val in (("Transmission Weight", 0.92), ("Transmission", 0.92),
                    ("Roughness", rough), ("IOR", 1.46)):
        inp = b.inputs.get(nm)
        if inp is not None:
            inp.default_value = val
    for nm in ("Emission Color", "Emission"):
        inp = b.inputs.get(nm)
        if inp is not None and "Color" in nm:
            inp.default_value = (col[0], col[1], col[2], 1.0)
    inp = b.inputs.get("Emission Strength")
    if inp is not None:
        inp.default_value = glow
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def _cloth(name, hexcol, rough=0.88, sheen=0.35, weave=26.0):
    """Cloth with a fine procedural weave so it is not a flat sheet."""
    m = K.mat_cloth(name, hexcol, rough=rough)
    try:
        nt = m.node_tree
        b = K._bsdf(m)
        if b is None:
            return m
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = weave
        noise.inputs["Detail"].default_value = 2.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.16
        bump.inputs["Distance"].default_value = 0.01
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
        inp = b.inputs.get("Sheen Weight")
        if inp is None:
            inp = b.inputs.get("Sheen")
        if inp is not None:
            try:
                inp.default_value = sheen
            except Exception:
                pass
    except Exception:
        pass
    return m


def make_mats():
    M = {}
    M["stone"] = K.mat_stone()
    M["stone_wall"] = K.mat_stone("int_ashlar", base="#9a927f", dark="#5d574a",
                                  light="#b8b09a", scale=1.7)
    M["stone_course"] = K.mat_stone("int_course", base="#87806f", dark="#565044",
                                    light="#a9a18c", scale=3.4)
    M["stone_light"] = K.mat_stone("int_light", base="#b3ab94", dark="#776f5c",
                                   light="#cfc7ae", scale=2.2)
    M["stone_dark"] = K.mat_stone("int_dark", base="#6b6456", dark="#3b372e",
                                  light="#8b8474", scale=2.6)
    M["stone_floor"] = K.mat_flag("int_paving", base="#8d8574", dark="#4a453b",
                                  light="#b0a893", scale=1.5)
    M["stone_step"] = K.mat_stone("int_step", base="#a39b86", dark="#665f4f",
                                  light="#c0b79f", scale=1.2)
    M["marble"] = K.mat_stone("int_marble", base="#c9c2b2", dark="#9a9486",
                             light="#e3ddcd", scale=5.5)
    M["plaster"] = K.mat_plaster("int_plaster", base="#d8cdb6", dirt="#b7ab90",
                                 scale=4.0)
    M["wood"] = K.mat_wood()
    M["wood_dark"] = K.mat_wood("int_timber", base="#3a2517", light="#553824",
                                scale=11.0)
    M["wood_beam"] = K.mat_wood("int_beam", base="#4a3122", light="#6b4a33",
                                scale=8.0)
    M["wood_floor"] = K.mat_wood("int_board", base="#5b3d28", light="#7d593c",
                                 scale=18.0)
    M["iron"] = K.mat_metal("int_iron", base="#38373d", rough=0.46)
    M["steel"] = K.mat_metal("int_steel", base="#8b8f96", rough=0.30)
    M["gold"] = K.mat_gold()
    M["brass"] = K.mat_gold("int_brass", base="#a8873a")
    M["leather"] = K.mat_cloth("int_leather", "#4a3220", rough=0.62)
    # glazing
    M["glass_gold"] = _litglass("int_glass_gold", "#e8b23a", glow=0.60)
    M["glass_blue"] = _litglass("int_glass_blue", "#3d6fc4", glow=0.40)
    M["glass_red"] = _litglass("int_glass_red", "#b8323a", glow=0.40)
    M["glass_green"] = _litglass("int_glass_green", "#3f8f5a", glow=0.36)
    M["glass_pale"] = _litglass("int_glass_pale", "#cfd9e0", glow=0.26, tint=1.1)
    M["glass_clear"] = _litglass("int_glass_clear", "#dfe8ee", glow=0.18, tint=1.15)
    # textiles
    M["carpet_red"] = _cloth("int_carpet", "#8e2320", rough=0.95, sheen=0.15,
                             weave=40.0)
    M["carpet_blue"] = _cloth("int_carpet_blue", "#26365e")
    M["cloth_red"] = _cloth("int_cloth_red", "#8d2a22")
    M["cloth_blue"] = _cloth("int_cloth_blue", "#2b3f66")
    M["cloth_gold"] = _cloth("int_cloth_gold", "#b8902c")
    M["cloth_white"] = _cloth("int_cloth_white", "#d6cdb8")
    M["tapestry"] = _cloth("int_tapestry", "#7d3a28", rough=0.94, weave=34.0)
    M["tapestry_blue"] = _cloth("int_tapestry_blue", "#2e3f5e", rough=0.94,
                                weave=34.0)
    M["tapestry_gold"] = _cloth("int_tapestry_gold", "#a07826", rough=0.94,
                                weave=34.0)
    # fire / light
    M["soot"] = _ashlar("ci_soot", (0.022, 0.021, 0.020),
                        (0.034, 0.032, 0.030), (0.012, 0.011, 0.010),
                        bw=0.90, bh=0.40, grime=0.2, bump=0.1)
    M["fire"] = _emit("int_fire", "#ff6a12", 4.6)
    M["fire_hot"] = _emit("int_fire_hot", "#ffb45c", 7.5)
    M["ember"] = _emit("int_ember", "#ff5a12", 22.0)
    M["candle"] = _emit("int_candle", "#ffd79a", 9.0)
    M["smoke"] = K.mat_cloth("int_smoke", "#5a5148", rough=1.0)
    return M


_FB = None


def _m(MAT, key):
    """MAT may be a caller dict; fall back to the registry so a partial dict works."""
    global _FB
    if key in MAT:
        return MAT[key]
    if _FB is None:
        _FB = make_mats()
    return _FB[key]


# ---------------------------------------------------------------------------
# more mesh helpers
# ---------------------------------------------------------------------------
def prism_x(nm, T, poly, depth, mat, bev=0.0):
    """Closed polygon in local YZ, extruded along local X (+-depth/2)."""
    n = len(poly)
    hd = depth * 0.5
    verts = [T @ Vector((-hd, u, v)) for (u, v) in poly]
    verts += [T @ Vector((hd, u, v)) for (u, v) in poly]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = K.mesh_obj(nm, verts, faces)
    K.assign(ob, mat)
    if bev > 0:
        K.bevel(ob, bev)
    return ob


def curved_brace(nm, T, p0, p1, p2, r0, r1, depth, mat, n=8, bev=0.008):
    """A curved (carpenter's) brace: an annular band swept about p2 in the YZ
    plane, between the radii r0 (inner) and r1 (outer), from the direction of p0
    to the direction of p1.  Points are (y, z)."""
    a0 = math.atan2(p0[1] - p2[1], p0[0] - p2[0])
    a1 = math.atan2(p1[1] - p2[1], p1[0] - p2[0])
    while a1 - a0 > math.pi:
        a1 -= TAU
    while a0 - a1 > math.pi:
        a1 += TAU
    poly = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        poly.append((p2[0] + math.cos(a) * r0, p2[1] + math.sin(a) * r0))
    for i in range(n + 1):
        a = a1 + (a0 - a1) * i / n
        poly.append((p2[0] + math.cos(a) * r1, p2[1] + math.sin(a) * r1))
    return prism_x(nm, T, poly, depth, mat, bev=bev)


def arch_halfwidth(hs, spring, rise, z):
    """Half width of an arch opening at height z (matches arch_curve)."""
    if z <= spring:
        return hs
    if z >= spring + rise:
        return 0.0
    if rise >= hs * 0.999:
        R = (hs * hs + rise * rise) / (2.0 * hs)
        c = R - hs
        s = min(1.0, (z - spring) / R)
        a = math.pi - math.asin(s)
        return max(0.0, -(c + R * math.cos(a)))
    R = (hs * hs + rise * rise) / (2.0 * rise)
    zc = spring + rise - R
    zz = z - zc
    return math.sqrt(max(0.0, R * R - zz * zz))


def cloth_panel(nm, T, w, h, mat, folds=6, amp=0.105, sag=0.05, rows=16,
                cols=11, notch=0.0, twist=0.0, thick=0.014, hem=0.0):
    """A hanging cloth with real depth: folds that open toward the hem, a sagging
    bottom edge and an optional swallow-tail notch.  Hangs from the local origin
    downward (-Z) and away from the wall in +Y."""
    pts = []
    for r in range(rows + 1):
        v = h * r / rows
        row = []
        for c in range(cols + 1):
            t = c / cols
            u = (t - 0.5) * w
            f = math.sin(math.pi * folds * t + twist) * amp
            f += 0.30 * amp * math.sin(math.pi * 2.3 * folds * t + 1.1 + twist)
            k = 0.12 + 0.88 * (v / h) ** 0.72
            dy = f * k
            dy += 0.03 * math.sin(math.pi * v / h) * (0.4 + 0.6 * abs(
                math.sin(math.pi * folds * t)))
            z = -v - sag * (1.0 - (2.0 * t - 1.0) ** 2) * (v / h) ** 1.4
            if notch > 0.0 and r >= rows - 1:
                lift = notch * max(0.0, -math.cos(TAU * t)) ** 1.3
                z += lift * (r - (rows - 1) if rows > 1 else 1) / max(1, rows - 1)
                if r == rows - 1:
                    z += lift * 0.55
            row.append((u, dy, z))
        pts.append(row)
    ob = quad_strip(nm, T, pts, mat, smooth=True)
    solid(ob, thick)
    return ob


def hang_rail(nm, T, w, mat, r=0.045):
    """Iron rod a cloth hangs from, along local X."""
    return cyl(nm, T @ Ts(0, 0, 0, ry=math.pi * 0.5), r, w, mat, seg=10)


# ---------------------------------------------------------------------------
# great hall - floor
# ---------------------------------------------------------------------------
def _cam(nm, loc, look, lens=35.0, ortho=None):
    """A camera that really points at `look` (hd_common's quat does not)."""
    c = H.camera(nm, loc, look, lens=lens, ortho=ortho)
    f = Vector(look) - Vector(loc)
    f.normalize()
    up = Vector((0.0, 0.0, 1.0))
    r = f.cross(up)
    if r.length < 1e-5:
        r = Vector((1.0, 0.0, 0.0))
    r.normalize()
    u = r.cross(f)
    Mx = Matrix(((r.x, u.x, -f.x, 0.0),
                 (r.y, u.y, -f.y, 0.0),
                 (r.z, u.z, -f.z, 0.0),
                 (0.0, 0.0, 0.0, 1.0)))
    Mx.translation = Vector(loc)
    c.matrix_world = Mx
    c.data.clip_start = 0.05
    c.data.clip_end = 400.0
    return c


def build_floor(M, rng):
    P = []
    P.append(bx("ci_slab", Ts(0, 0, -0.60), (2 * (HX + WT), 2 * (HY + WT), 1.20),
                _m(M, "stone_dark")))
    pw, pd = 1.02, 0.68
    nx = int(round(2 * HX / pw))
    ny = int(round(2 * HY / pd))
    sx, sy = 2 * HX / nx, 2 * HY / ny
    verts, faces = [], []
    ztop, zbot = 0.0, -0.13
    for j2 in range(ny):
        off = 0.5 * sx if j2 % 2 else 0.0
        for i2 in range(nx + 1):
            x0 = -HX + i2 * sx - off
            x1 = x0 + sx
            if x1 <= -HX or x0 >= HX:
                continue
            x0 = max(x0, -HX) + 0.009
            x1 = min(x1, HX) - 0.009
            y0 = -HY + j2 * sy + 0.009
            y1 = -HY + (j2 + 1) * sy - 0.009
            b = len(verts)
            for zz in (zbot, ztop):
                verts.append((x0, y0, zz))
                verts.append((x1, y0, zz))
                verts.append((x1, y1, zz))
                verts.append((x0, y1, zz))
            faces.append((b + 0, b + 3, b + 2, b + 1))
            faces.append((b + 4, b + 5, b + 6, b + 7))
            faces.append((b + 0, b + 1, b + 5, b + 4))
            faces.append((b + 1, b + 2, b + 6, b + 5))
            faces.append((b + 2, b + 3, b + 7, b + 6))
            faces.append((b + 3, b + 0, b + 4, b + 7))
    ob = K.mesh_obj("ci_flags", verts, faces)
    K.assign(ob, _m(M, "stone_floor"))
    P.append(ob)
    # a band of darker paving ringing the dais
    for (x0, x1, y0, y1) in ((-HX - WT, HX + WT, -HY - 0.0, -HY + 0.46),
                             (-HX - WT, HX + WT, HY - 0.46, HY),
                             (HX - 0.46, HX, -HY, HY)):
        P.append(bx("ci_kerb", Ts((x0 + x1) * 0.5, (y0 + y1) * 0.5, 0.012),
                    (x1 - x0, y1 - y0, 0.05), _m(M, "stone_step")))
    return P


def build_carpet(M):
    """The great red runner: entrance door -> dais, and on across the dais."""
    P = []
    w = 2.30
    x_bot = DAIS_X1 + STEP_D * N_STEP
    x_top = HX - 0.90
    P.append(bx("ci_carpet", Ts((x_bot + x_top) * 0.5, 0, 0.019),
                (x_top - x_bot, w, 0.030), _m(M, "carpet_red"), bev=0.006))
    # gold guard lines either side
    for s in (-1, 1):
        P.append(bx("ci_carpet_bor", Ts((x_bot + x_top) * 0.5, s * (w * 0.5 - 0.10), 0.037),
                    (x_top - x_bot, 0.075, 0.012), _m(M, "cloth_gold")))
    # treads and risers
    for k in range(N_STEP):
        xa = DAIS_X1 + STEP_D * (N_STEP - k - 1)
        zt = Z_STEP * (k + 1)
        P.append(bx("ci_carpet_td", Ts(xa + STEP_D * 0.5, 0, zt + 0.019),
                    (STEP_D, w, 0.030), _m(M, "carpet_red")))
        P.append(bx("ci_carpet_rs", Ts(xa, 0, zt - Z_STEP * 0.5),
                    (0.030, w, Z_STEP), _m(M, "carpet_red")))
    P.append(bx("ci_carpet_top", Ts((DAIS_X0 + DAIS_X1) * 0.5 - 0.55, 0, Z_DAIS + 0.020),
                (DAIS_X1 - DAIS_X0 - 1.10, w, 0.030), _m(M, "carpet_red"), bev=0.006))
    for s in (-1, 1):
        P.append(bx("ci_carpet_topb", Ts((DAIS_X0 + DAIS_X1) * 0.5 - 0.55,
                                         s * (w * 0.5 - 0.10), Z_DAIS + 0.038),
                    (DAIS_X1 - DAIS_X0 - 1.10, 0.075, 0.012), _m(M, "cloth_gold")))
    return P


# ---------------------------------------------------------------------------
# great hall - walls, arcade, clerestory
# ---------------------------------------------------------------------------
def side_wall(s, M, rng):
    """A long wall: bench, blind arcade of pointed niches, clerestory, plate.

    Local frame: +X runs along the wall, +Y points out of the room.
    """
    P = []
    n = "+y" if s > 0 else "-y"
    T = WF(0.0, s * HY, 0.0, n)
    U = HX + WT
    st = _m(M, "stone_wall")
    sl = _m(M, "stone_light")
    sc = _m(M, "stone_course")
    sd = _m(M, "stone_dark")
    PZ = 0.46
    SPR, RISE = 5.10, 2.10
    # ---- outer leaf of the wall and the plinth
    P.append(bx("ci_wall_out", T @ Ts(0, (PZ + WT) * 0.5, 4.60),
                (2 * U, WT - PZ, 9.20), st))
    P.append(bx("ci_plinth", T @ Ts(0, (WT - 0.07) * 0.5, 0.10),
                (2 * U, WT + 0.07, 0.20), sd, bev=0.012))
    # ---- piers, with a bundle of engaged shafts on the room face
    for x0 in BAYX:
        P.append(bx("ci_pier", T @ Ts(x0, PZ * 0.5, 4.60), (0.92, PZ, 9.20), st))
        P.append(cyl("ci_pier_sh", T @ Ts(x0, -0.075, 4.85), 0.185, 8.40, sl, seg=14))
        for dx in (-0.30, 0.30):
            P.append(cyl("ci_pier_sh2", T @ Ts(x0 + dx, -0.045, 4.85), 0.098, 8.40,
                         sl, seg=10))
        P.append(bx("ci_pier_base", T @ Ts(x0, -0.09, 0.31), (0.98, 0.50, 0.62), sc,
                    bev=0.014))
        P.append(bx("ci_pier_cap", T @ Ts(x0, -0.075, 7.42), (1.00, 0.48, 0.24), sc,
                    bev=0.014))
    # ---- the arcade: arch heads, archivolts, niche linings, stone seats
    for i in range(NBAY):
        u0, u1 = BAYX[i] + 0.46, BAYX[i + 1] - 0.46
        hs = (u1 - u0) * 0.5
        uc = (u0 + u1) * 0.5
        P.append(spandrel("ci_arc_span", T @ Ts(0, PZ * 0.5, 0), u0, u1, SPR, RISE,
                          9.20, PZ, st, nseg=10))
        P.append(ring_voussoir("ci_arc_ring", T @ Ts(uc, 0.04, 0), hs, SPR, RISE, 0.26,
                               0.20, sl, nseg=10, bev=0.008))
        P.append(bx("ci_arc_line", T @ Ts(uc, PZ - 0.03, 2.40), (2 * hs, 0.06, 4.64), sd))
        for s2 in (-1, 1):
            P.append(bx("ci_arc_jamb", T @ Ts(uc + s2 * (hs - 0.05), 0.02, 2.40),
                        (0.10, 0.10, 4.60), sl, bev=0.008))
        P.append(bx("ci_arc_seat", T @ Ts(uc, -0.16, 0.255), (2 * hs - 0.20, 0.50, 0.51),
                    sc))
        P.append(bx("ci_arc_seat_t", T @ Ts(uc, -0.17, 0.53), (2 * hs - 0.16, 0.52, 0.06),
                    sl, bev=0.012))
    # ---- string course at the clerestory sill
    P.append(bx("ci_sill", T @ Ts(0, WT * 0.5 - 0.10, 9.40),
                (2 * U, WT + 0.20, 0.40), sc, bev=0.016))
    # ---- clerestory
    for i in range(NBAY):
        b0, b1 = BAYX[i], BAYX[i + 1]
        u0, u1 = b0 + 0.62, b1 - 0.62
        hs = (u1 - u0) * 0.5
        uc = (u0 + u1) * 0.5
        P.append(bx("ci_cl_jamb", T @ Ts((b0 + u0) * 0.5, WT * 0.5, 11.80),
                    (u0 - b0, WT, 4.40), st))
        P.append(bx("ci_cl_jamb", T @ Ts((u1 + b1) * 0.5, WT * 0.5, 11.80),
                    (b1 - u1, WT, 4.40), st))
        P.append(spandrel("ci_cl_span", T @ Ts(0, WT * 0.5, 0), u0, u1, 11.90, 1.50,
                          Z_PLATE, WT, st, nseg=7))
        P.append(ring_voussoir("ci_cl_ring", T @ Ts(0, 0.02, 0), hs, 11.90, 1.50, 0.24,
                               0.30, sl, nseg=7, bev=0.010))
        for sx in (-1, 1):
            P.append(bx("ci_cl_order", T @ Ts(uc + sx * (hs + 0.12), 0.02, 10.75),
                        (0.24, 0.30, 2.30), sl, bev=0.010))
        P.append(bx("ci_cl_seat", T @ Ts(uc, WT * 0.5, 9.74),
                    (2 * hs + 0.10, WT - 0.28, 0.16), sl, bev=0.012))
        P.extend(glazed_window("ci_cl", T, uc, WT * 0.5, 9.80, hs, 11.90, 1.50, rng))
    # ---- wall plate and cornice
    P.append(bx("ci_plate", T @ Ts(0, 0.02, Z_PLATE + 0.17), (2 * U, 0.34, 0.34),
                _m(M, "wood_beam")))
    P.append(bx("ci_cornice", T @ Ts(0, -0.08, Z_PLATE - 0.10), (2 * U, 0.30, 0.20),
                sc, bev=0.012))
    return P


_GLASS_ORDER = ("glass_blue", "glass_blue", "glass_blue", "glass_gold",
                "glass_red", "glass_green", "glass_pale", "glass_gold")


def _arc_pts(hs, spring, rise, n=10):
    """Half a two-centred pointed arch, from (hs, spring) up to the apex."""
    P = []
    if rise < hs * 0.999:
        R = (hs * hs + rise * rise) / (2.0 * rise)
        zc = spring + rise - R
        for k in range(n + 1):
            x = hs * (1.0 - k / float(n))
            P.append((x, zc + math.sqrt(max(0.0, R * R - x * x))))
    else:
        R = (hs * hs + rise * rise) / (2.0 * hs)
        c = R - hs
        a_top = math.atan2(rise, c)
        for k in range(n + 1):
            a = a_top * k / float(n)
            P.append((-c + R * math.cos(a), spring + R * math.sin(a)))
    return P


def _glass_palette():
    return [(0.055, 0.105, 0.320), (0.560, 0.410, 0.115), (0.360, 0.045, 0.045),
            (0.055, 0.180, 0.105), (0.520, 0.570, 0.660), (0.230, 0.075, 0.210)]


def _glass_proc():
    """Stained glass: voronoi cells, leaded, a heraldic palette."""
    nm = "ci_glass_proc"
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 4.6
    vor2 = nt.nodes.new("ShaderNodeTexVoronoi")
    vor2.feature = "F1"
    vor2.inputs["Scale"].default_value = 4.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    pal = _glass_palette()
    e = ramp.color_ramp.elements
    while len(e) > 1:
        e.remove(e[-1])
    e[0].position = 0.0
    e[0].color = (pal[0][0], pal[0][1], pal[0][2], 1.0)
    for k in range(1, len(pal)):
        el = e.new(pal[k][0] * 0.0 + (k / float(len(pal))))
        el.color = (pal[k][0], pal[k][1], pal[k][2], 1.0)
    mask = nt.nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = 0.0
    mask.inputs["From Max"].default_value = 0.055
    mask.inputs["To Min"].default_value = 0.0
    mask.inputs["To Max"].default_value = 1.0
    dark = nt.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.blend_type = "MIX"
    dark.inputs["B"].default_value = (0.012, 0.012, 0.014, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], vor2.inputs["Vector"])
    nt.links.new(vor2.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(vor.outputs["Distance"], mask.inputs["Value"])
    nt.links.new(ramp.outputs["Color"], dark.inputs["A"])
    nt.links.new(mask.outputs["Result"], dark.inputs["Factor"])
    nt.links.new(dark.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(dark.outputs["Result"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.14
    bsdf.inputs["Transmission Weight"].default_value = 0.90
    bsdf.inputs["IOR"].default_value = 1.52
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def glazed_window(nm, T, uc, vc, z0, hs, spring, rise, rng, order=None):
    """Leaded glass filling an arched opening, with stone mullions in front."""
    P = []
    gm = _glass_proc()
    poly = [(-hs, z0), (hs, z0)]
    half = _arc_pts(hs, spring, rise, 9)
    poly += half
    poly += [(-x, z) for (x, z) in reversed(half)]
    P.append(prism_y(nm + "_glass", T @ Ts(uc, vc, 0), poly, 0.024, gm))
    ms = _m({}, "stone_light")
    for c in (1, 2):
        P.append(bx(nm + "_mull", T @ Ts(uc - hs + c * 2 * hs / 3.0, vc - 0.05,
                                        (z0 + spring) * 0.5 + 0.02),
                    (0.11, 0.13, spring - z0 + 0.06), ms, bev=0.006))
    P.append(bx(nm + "_trans", T @ Ts(uc, vc - 0.05, z0 + (spring - z0) * 0.60),
                (2 * hs, 0.10, 0.10), ms, bev=0.006))
    return P


def end_wall(sx, M, rng):
    """A short wall (the two ends).  Local +X along the wall, +Y out of the room."""
    P = []
    n = "+x" if sx > 0 else "-x"
    T = WF(sx * HX, 0.0, 0.0, n)
    V = HY + WT
    if sx > 0:
        # ---- entrance wall: one great doorway, two clerestory lights above
        hs, spring, rise = 1.80, 3.55, 1.85
        P.append(bx("ci_ew_l", T @ Ts(-(V + hs) * 0.5, WT * 0.5, 4.60),
                    (V - hs, WT, 9.20), _m(M, "stone_wall")))
        P.append(bx("ci_ew_r", T @ Ts((V + hs) * 0.5, WT * 0.5, 4.60),
                    (V - hs, WT, 9.20), _m(M, "stone_wall")))
        P.append(spandrel("ci_ew_span", T @ Ts(0, WT * 0.5, 0), -hs, hs, spring,
                          rise, 9.20, WT, _m(M, "stone_wall"), nseg=8))
        # doorway: two moulded orders and a tympanum
        for (o, d, mat, ring) in ((0.0, 0.42, "stone_light", 0.30),
                                  (-0.34, 0.34, "stone_course", 0.26)):
            P.append(ring_voussoir("ci_door_ring", T @ Ts(0, o + 0.03, 0),
                                   hs + 0.3, spring, rise, ring, d,
                                   _m(M, mat), nseg=8, bev=0.012))
            for s2 in (-1, 1):
                P.append(bx("ci_door_jamb", T @ Ts(s2 * (hs + 0.15), o + 0.03,
                                                   spring * 0.5 + 0.1),
                            (0.60, d, spring + 0.2), _m(M, mat), bev=0.010))
        # the door leaves themselves
        for s2 in (-1, 1):
            P.append(bx("ci_door", T @ Ts(s2 * 0.88, 0.26, 2.06),
                        (1.70, 0.20, 4.10), _m(M, "wood_dark"), bev=0.014))
            for zz in (0.75, 1.85, 2.95, 3.55):
                P.append(bx("ci_door_strap", T @ Ts(s2 * 0.88, 0.36, zz),
                            (1.55, 0.045, 0.13), _m(M, "iron")))
            P.append(bx("ci_door_brace", T @ Ts(s2 * 0.88, 0.36, 2.2),
                        (1.50, 0.030, 0.14), _m(M, "iron"), bev=0.006))
        P.append(cyl("ci_door_ring", T @ Ts(-0.18, 0.40, 1.85, rx=math.pi * 0.5),
                     0.16, 0.05, _m(M, "iron"), seg=16))
        # lintel course over the doorway
        P.append(bx("ci_ew_lint", T @ Ts(0, -0.06, 5.72), (2 * (hs + 1.5), 0.34, 0.30),
                    _m(M, "stone_course"), bev=0.014))
        # upper body + two lights
        P.append(bx("ci_ew_up", T @ Ts(0, WT * 0.5, 7.45), (2 * V, WT, 3.55),
                    _m(M, "stone_wall")))
        P.append(bx("ci_ew_sill", T @ Ts(0, WT * 0.5 - 0.09, 9.40),
                    (2 * V, WT + 0.18, 0.40), _m(M, "stone_course"), bev=0.016))
        for s2 in (-1, 1):
            uc = s2 * 3.9
            u0, u1 = uc - 1.05, uc + 1.05
            P.append(spandrel("ci_ew_span2", T @ Ts(0, WT * 0.5, 0), u0, u1, 11.90,
                              1.50, Z_PLATE, WT, _m(M, "stone_wall"), nseg=6))
            P.extend(glazed_window("ci_ew", T, uc, WT * 0.5, 9.74, 1.05, 11.90,
                                   1.50, rng))
        # fill the solid strips of the clerestory band
        for (c0, c1) in ((-V, -4.95), (-2.85, 2.85), (4.95, V)):
            P.append(bx("ci_ew_fill", T @ Ts((c0 + c1) * 0.5, WT * 0.5, 11.80),
                        (c1 - c0, WT, 4.40), _m(M, "stone_wall")))
    else:
        # ---- throne wall: the great window, and a blind arcade beneath it
        P.append(bx("ci_tw_lo", T @ Ts(0, WT * 0.5, 4.30), (2 * V, WT, 8.60),
                    _m(M, "stone_wall")))
        hs, spring, rise = 2.90, 11.60, 1.80
        u0, u1 = -hs - 0.75, hs + 0.75
        for s2 in (-1, 1):
            P.append(bx("ci_tw_j", T @ Ts(s2 * (V + abs(u0)) * 0.5, WT * 0.5, 11.80),
                        (V - abs(u0), WT, 4.40), _m(M, "stone_wall")))
        P.append(spandrel("ci_tw_span", T @ Ts(0, WT * 0.5, 0), u0, u1, spring, rise,
                          Z_PLATE, WT, _m(M, "stone_wall"), nseg=8))
        P.append(bx("ci_tw_sill", T @ Ts(0, WT * 0.5 - 0.09, 8.40),
                    (2 * V, WT + 0.20, 0.42), _m(M, "stone_course"), bev=0.018))
        for (o, d, mat, ring) in ((0.0, 0.46, "stone_light", 0.34),
                                  (-0.30, 0.36, "stone_course", 0.30)):
            P.append(ring_voussoir("ci_gw_ring", T @ Ts(0, o + 0.04, 0), hs, spring,
                                   rise, ring, d, _m(M, mat), nseg=8, bev=0.012))
        P.extend(glazed_window("ci_gw", T, 0.0, WT * 0.5, 8.80, hs, spring, rise,
                               rng))
        # stone mullions for the great window (3 lights)
        for s2 in (-1, 1):
            P.append(bx("ci_gw_mull", T @ Ts(s2 * 1.05, WT * 0.5 - 0.02, 9.95),
                        (0.20, 0.22, 2.60), _m(M, "stone_light"), bev=0.010))
        # blind arcade under the window, three tall niches
        for k in (-1, 0, 1):
            uc = k * 3.15
            ahs = 1.30
            P.append(ring_voussoir("ci_niche", T @ Ts(uc, 0.03, 0), ahs, 6.30, 1.55,
                                   0.28, 0.34, _m(M, "stone_light"), nseg=6))
            for s2 in (-1, 1):
                P.append(bx("ci_niche_j", T @ Ts(uc + s2 * (ahs + 0.14), 0.03, 4.0),
                            (0.28, 0.34, 4.6), _m(M, "stone_light"), bev=0.010))
        P.append(bx("ci_tw_plinth", T @ Ts(0, -0.12, 0.20), (2 * V, 0.34, 0.40),
                    _m(M, "stone_dark"), bev=0.014))
    P.append(bx("ci_ew_plate", T @ Ts(0, 0.02, Z_PLATE + 0.17), (2 * V, 0.34, 0.34),
                _m(M, "wood_beam")))
    P.append(bx("ci_ew_cor", T @ Ts(0, -0.08, Z_PLATE - 0.10), (2 * V, 0.30, 0.20),
                _m(M, "stone_course"), bev=0.012))
    # ---- gable above the plate: follows the roof pitch, with a rose light
    gz = Z_PLATE
    poly = [(-V, gz), (-V, gz + 0.42), (-HY, gz + 0.42), (0.0, Z_RIDGE + 0.16),
            (HY, gz + 0.42), (V, gz + 0.42), (V, gz)]
    P.append(prism_y("ci_gable", T @ Ts(0, WT * 0.5, 0), poly, WT,
                     _m(M, "stone_wall")))
    P.append(bx("ci_gable_cop", T @ Ts(0, WT * 0.5, gz + 0.46),
                (2 * V, WT + 0.16, 0.11), _m(M, "stone_course"), bev=0.012))
    # rose light in the gable
    rz = 16.55
    P.append(cyl("ci_rose_ring", T @ Ts(0, WT * 0.5, rz, rx=math.pi * 0.5), 0.98,
                 0.40, _m(M, "stone_light"), seg=24))
    P.append(cyl("ci_rose_hole", T @ Ts(0, WT * 0.5 - 0.10, rz, rx=math.pi * 0.5),
                 0.80, 0.52, _m(M, "stone_dark"), seg=24))
    P.append(cyl("ci_rose_glass", T @ Ts(0, WT * 0.5 + 0.02, rz, rx=math.pi * 0.5),
                 0.79, 0.05, _m(M, "glass_gold"), seg=24))
    for k in range(8):
        a = TAU * k / 8.0
        P.append(bx("ci_rose_spoke",
                    T @ Ts(0, WT * 0.5 + 0.05, rz, rx=math.pi * 0.5) @ Ts(
                        0, 0, 0, rz=a),
                    (0.09, 1.58, 0.05), _m(M, "iron")))
    P.append(cyl("ci_rose_hub", T @ Ts(0, WT * 0.5 + 0.03, rz, rx=math.pi * 0.5),
                 0.20, 0.10, _m(M, "stone_light"), seg=14))
    return [p for p in P if p is not None]


# ---------------------------------------------------------------------------
# great hall - the timber roof
# ---------------------------------------------------------------------------
def beam_x(nm, x, p0, p1, w, d, mat, bev=0.0):
    """A rectangular beam of section w (along X) x d, from p0=(y,z) to p1=(y,z)."""
    dy, dz = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dy, dz)
    ang = math.atan2(-dy, dz)
    T = Ts(x, (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, rx=ang)
    return bx(nm, T, (w, d, L), mat, bev=bev)


def arch_band_x(nm, x, hs, spring, rise, ring, depth, mat, nseg=8):
    """A curved timber arch in a YZ plane at `x` (band of thickness `ring`)."""
    arc = arch_curve(hs, spring, rise, nseg)
    poly = list(arc)
    for (y, z) in reversed(arc):
        poly.append((y, z + ring))
    return prism_x(nm, Ts(x, 0, 0), poly, depth, mat, bev=0.010)


def build_roof(M, rng):
    P = []
    zw = Z_PLATE
    ws = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    ww = _m(M, "wood")
    # ---- 7 hammerbeam trusses
    for i, x0 in enumerate(BAYX):
        nm = "ci_truss%d" % i
        for s2 in (-1, 1):
            P.append(beam_x(nm + "_raf", x0, (s2 * HY, zw), (0.0, Z_RIDGE),
                            0.30, 0.34, ws))
            P.append(bx(nm + "_wpost", Ts(x0, s2 * 8.78, zw + 0.72),
                        (0.34, 0.30, 1.44), ws))
            P.append(bx(nm + "_ham", Ts(x0, s2 * 7.95, zw + 1.42),
                        (0.34, 2.30, 0.36), ws))
            P.append(curved_brace(nm + "_hamcur", Ts(x0, 0, 0),
                                  (s2 * 6.90, zw + 1.40), (s2 * 8.55, zw + 0.02),
                                  (s2 * 8.55, zw + 1.40), 0.42, 0.80, 0.28, wd,
                                  n=6))
            P.append(bx(nm + "_hpost", Ts(x0, s2 * 6.90, zw + 2.10),
                        (0.30, 0.30, 1.40), ws))
            P.append(bx(nm + "_strut", Ts(x0, s2 * 5.10, zw + 3.22),
                        (0.20, 0.22, 0.90), wd))
        P.append(arch_band_x(nm + "_arch", x0, 6.90, zw + 2.80, 1.70, 0.34, 0.30, ws))
        P.append(bx(nm + "_collar", Ts(x0, 0, zw + 4.62), (0.30, 6.60, 0.30), ws))
        P.append(bx(nm + "_kpost", Ts(x0, 0, zw + 5.10), (0.26, 0.26, 0.90), ws))
        P.append(cyl(nm + "_boss", Ts(x0, 0, zw + 4.52), 0.24, 0.34,
                     _m(M, "gold"), seg=8))
    # ---- ridge and purlins
    P.append(bx("ci_ridge", Ts(0, 0, Z_RIDGE - 0.20), (2 * HX + 0.4, 0.34, 0.40), ws))
    for s2 in (-1, 1):
        for (yy, zz) in ((7.00, 15.24), (4.60, 16.73), (2.30, 18.16)):
            P.append(bx("ci_purlin", Ts(0, s2 * yy, zz), (2 * HX + 0.2, 0.24, 0.30),
                        wd))
    # ---- common rafters
    nraf = 40
    xs = [-HX + (2 * HX) * (i + 0.5) / nraf for i in range(nraf)]
    for s2 in (-1, 1):
        for x0 in xs:
            P.append(beam_x("ci_rafter", x0, (s2 * HY, zw), (0.0, Z_RIDGE), 0.12, 0.16, wd))
    # ---- boarding (the visible underside of the roof)
    for s2 in (-1, 1):
        rows = []
        for x0 in [-HX] + xs + [HX]:
            row = []
            for k in range(9):
                t = k / 8.0
                yy = s2 * HY * (1.0 - t)
                zz = zw + (Z_RIDGE - zw) * t + 0.10
                row.append((x0, yy, zz))
            rows.append(row)
        # transpose: rows along X, columns down the slope
        grid = []
        for k in range(9):
            grid.append([rows[i][k] for i in range(len(rows))])
        ob = quad_strip("ci_boards", Ts(0, 0, 0), grid, _m(M, "wood_dark"))
        K.bevel(ob, 0.0)
        P.append(ob)
    return P


# ---------------------------------------------------------------------------
# great hall - clustered responds against the side walls
# ---------------------------------------------------------------------------
def build_responds(M):
    P = []
    st = _m(M, "stone_light")
    sd = _m(M, "stone_dark")
    sc = _m(M, "stone_course")
    for s in (+1, -1):
        n = "+y" if s > 0 else "-y"
        T = WF(0.0, s * HY, 0.0, n)
        for x0 in BAYX:
            # main shaft + two subsidiary shafts = a bundle
            P.append(cyl("ci_resp", T @ Ts(x0, -0.215, 4.95), 0.180, 8.30, st, seg=14))
            for dx in (-0.315, 0.315):
                P.append(cyl("ci_resp", T @ Ts(x0 + dx, -0.145, 4.95), 0.105, 8.30, st, seg=10))
            # base, standing on the stone bench
            P.append(bx("ci_resp_b", T @ Ts(x0, -0.24, 0.665), (0.90, 0.62, 0.23), sd, bev=0.014))
            P.append(bx("ci_resp_b2", T @ Ts(x0, -0.235, 0.815), (0.80, 0.60, 0.07), sc, bev=0.010))
            # mid collar
            P.append(bx("ci_resp_col", T @ Ts(x0, -0.235, 6.58), (0.86, 0.58, 0.10), sc, bev=0.008))
            # capital + abacus at the clerestory sill
            P.append(cyl("ci_resp_cap", T @ Ts(x0, -0.215, 9.00), 0.180, 0.30, sc, seg=14, r2=0.30))
            P.append(bx("ci_resp_ab", T @ Ts(x0, -0.24, 9.19), (0.96, 0.66, 0.12), st, bev=0.012))
    return P


# ---------------------------------------------------------------------------
# great hall - the dais
# ---------------------------------------------------------------------------
def build_dais(M):
    P = []
    st = _m(M, "stone_step")
    sl = _m(M, "stone_light")
    mb = _m(M, "marble")
    for k in range(N_STEP):
        xa = DAIS_X1 + STEP_D * (N_STEP - k - 1)
        zt = Z_STEP * (k + 1)
        P.append(bx("ci_step", Ts(xa + STEP_D * 0.5, 0, zt * 0.5),
                    (STEP_D, 2 * DAIS_HW, zt), st))
        P.append(bx("ci_step_nose", Ts(xa + STEP_D - 0.045, 0, zt - 0.038),
                    (0.10, 2 * DAIS_HW, 0.076), sl, bev=0.012))
    P.append(bx("ci_dais", Ts((DAIS_X0 + DAIS_X1) * 0.5, 0, Z_DAIS * 0.5),
                (DAIS_X1 - DAIS_X0, 2 * DAIS_HW, Z_DAIS), st))
    P.append(bx("ci_dais_top", Ts((DAIS_X0 + DAIS_X1) * 0.5, 0, Z_DAIS - 0.035),
                (DAIS_X1 - DAIS_X0 - 0.06, 2 * DAIS_HW - 0.06, 0.07), mb, bev=0.008))
    # a moulded band round the platform nose
    P.append(bx("ci_dais_band", Ts((DAIS_X0 + DAIS_X1) * 0.5, 0, Z_DAIS - 0.11),
                (DAIS_X1 - DAIS_X0 + 0.04, 2 * DAIS_HW + 0.04, 0.09), sl, bev=0.012))
    # side cheeks of the dais
    for s in (-1, 1):
        P.append(bx("ci_dais_ck", Ts((DAIS_X0 + DAIS_X1) * 0.5, s * (DAIS_HW - 0.09),
                                     Z_DAIS * 0.5), (DAIS_X1 - DAIS_X0, 0.18, Z_DAIS),
                    _m(M, "stone_course")))
    return P


# ---------------------------------------------------------------------------
# great hall - the throne
# ---------------------------------------------------------------------------
def sph(nm, T, r, mat, seg=14, ring=8, squash=1.0):
    return K.sphere(nm, T, r, mat, seg=seg, ring=ring, squash=squash)


def build_throne(M, rng):
    """Three steps up, a tall narrow high-backed seat, gold, cloth of estate.

    The silhouette is deliberately vertical: a 1.38 m wide back standing 3.2 m
    over the dais, so it cannot be mistaken for an altar or a wall panel.
    """
    P = []
    T = Ts(THR_X, THR_Y, Z_DAIS)
    st = _m(M, "stone_light")
    sd = _m(M, "stone_dark")
    mb = _m(M, "marble")
    gd = _m(M, "gold")
    br = _m(M, "brass")
    rd = _m(M, "cloth_red")
    cd = _m(M, "cloth_gold")
    # ---- plinth, footpace
    P.append(bx("ci_thr_pl", T @ Ts(0.04, 0, 0.11), (1.96, 2.16, 0.22), sd, bev=0.018))
    P.append(bx("ci_thr_pl_g", T @ Ts(0.04, 0, 0.235), (2.00, 2.20, 0.05), gd, bev=0.008))
    P.append(bx("ci_thr_fp", T @ Ts(0.02, 0, 0.315), (1.78, 1.98, 0.16), mb, bev=0.012))
    # ---- seat block, cushion
    P.append(bx("ci_thr_seat", T @ Ts(-0.20, 0, 0.65), (1.06, 1.14, 0.50), mb, bev=0.018))
    P.append(bx("ci_thr_seat_ap", T @ Ts(0.26, 0, 0.66), (0.07, 1.06, 0.40), st, bev=0.008))
    P.append(bx("ci_thr_seat_g", T @ Ts(0.295, 0, 0.55), (0.035, 1.02, 0.13), gd, bev=0.006))
    P.append(bx("ci_thr_cus", T @ Ts(-0.22, 0, 0.955), (0.98, 1.06, 0.13), rd, bev=0.045))
    P.append(bx("ci_thr_fringe", T @ Ts(-0.22, 0, 0.888), (1.02, 1.10, 0.035), cd))
    # ---- the tall narrow back
    P.append(bx("ci_thr_back", T @ Ts(-0.72, 0, 1.80), (0.34, 1.38, 2.80), mb, bev=0.018))
    # velvet inset, gold frame, roundel
    P.append(bx("ci_thr_vel", T @ Ts(-0.545, 0, 1.92), (0.05, 1.04, 1.92), rd, bev=0.010))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_vel_fr", T @ Ts(-0.535, s2 * 0.555, 1.92),
                    (0.06, 0.10, 2.02), gd, bev=0.008))
    P.append(bx("ci_thr_vel_ft", T @ Ts(-0.535, 0, 2.90), (0.06, 1.20, 0.10), gd, bev=0.008))
    P.append(bx("ci_thr_vel_fb", T @ Ts(-0.535, 0, 0.96), (0.06, 1.20, 0.10), gd, bev=0.008))
    P.append(cyl("ci_thr_round", T @ Ts(-0.515, 0, 2.28, ry=math.pi * 0.5), 0.31, 0.05,
                 gd, seg=20))
    P.append(cyl("ci_thr_round2", T @ Ts(-0.505, 0, 2.28, ry=math.pi * 0.5), 0.22, 0.05,
                 rd, seg=20))
    # ---- crest rail, gable canopy, orb, finials
    P.append(bx("ci_thr_crest", T @ Ts(-0.72, 0, 3.245), (0.42, 1.46, 0.13), gd, bev=0.010))
    P.append(bx("ci_thr_crest2", T @ Ts(-0.72, 0, 3.13), (0.44, 1.50, 0.08), st, bev=0.010))
    P.append(prism_y("ci_thr_can", T @ Ts(-0.72, 0, 0),
                     [(-1.00, 3.31), (-1.00, 3.45), (-0.50, 3.86), (0.0, 4.02),
                      (0.50, 3.86), (1.00, 3.45), (1.00, 3.31)], 0.36, st, bev=0.012))
    P.append(bx("ci_thr_can_g", T @ Ts(-0.72, 0, 3.40), (0.40, 1.92, 0.07), gd, bev=0.006))
    P.append(sph("ci_thr_orb", T @ Ts(-0.72, 0, 4.16), 0.135, gd, seg=14, ring=8))
    for s2 in (-1, 1):
        P.append(cyl("ci_thr_pin", T @ Ts(-0.72, s2 * 0.80, 3.62), 0.078, 0.62, st, seg=10))
        P.append(cyl("ci_thr_pint", T @ Ts(-0.72, s2 * 0.80, 4.06), 0.11, 0.26, gd, seg=10,
                     r2=0.016))
    # ---- arms, lion heads, arm supports
    for s2 in (-1, 1):
        P.append(bx("ci_thr_arm", T @ Ts(0.02, s2 * 0.66, 1.36), (1.10, 0.22, 0.26),
                    mb, bev=0.014))
        P.append(bx("ci_thr_arm_g", T @ Ts(0.02, s2 * 0.66, 1.505), (1.04, 0.18, 0.05),
                    gd, bev=0.006))
        P.append(bx("ci_thr_arm_s", T @ Ts(-0.24, s2 * 0.66, 1.12), (0.20, 0.20, 0.36),
                    mb, bev=0.010))
        P.append(sph("ci_thr_lion", T @ Ts(0.55, s2 * 0.66, 1.40), 0.135, gd,
                     seg=14, ring=8, squash=0.92))
        P.append(bx("ci_thr_lion_e", T @ Ts(0.64, s2 * 0.66, 1.43), (0.05, 0.13, 0.07),
                    _m(M, "iron")))
    # ---- footstool
    P.append(bx("ci_thr_fst", T @ Ts(0.86, 0, 0.325), (0.62, 0.98, 0.15), st, bev=0.014))
    P.append(bx("ci_thr_fst_g", T @ Ts(0.86, 0, 0.405), (0.66, 1.02, 0.035), gd, bev=0.006))
    P.append(bx("ci_thr_fst_c", T @ Ts(0.86, 0, 0.445), (0.54, 0.90, 0.05), rd, bev=0.020))
    # ---- cloth of estate behind, and its hood
    Th = WF(-HX + 0.045, 0.0, 0.0, "-x") @ Ts(0, 0, 5.34, rz=math.pi)
    P.append(hang_rail("ci_thr_rail", Th @ Ts(0, -0.05, 0), 3.02, br, r=0.05))
    P.append(cloth_panel("ci_thr_hang", Th, 2.98, 4.28, rd,
                         folds=11, amp=0.115, sag=0.07, rows=22, cols=15, thick=0.016))
    P.append(bx("ci_thr_hang_g", Th @ Ts(0, 0.02, -4.22), (2.98, 0.09, 0.11), cd))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_hang_s", Th @ Ts(s2 * 1.46, -0.04, -2.14),
                    (0.09, 0.10, 4.28), cd))
    P.append(bx("ci_thr_hood", T @ Ts(-1.60, 0, 5.40), (1.02, 3.24, 0.20),
                _m(M, "wood_beam"), bev=0.014))
    P.append(bx("ci_thr_hood2", T @ Ts(-1.16, 0, 5.54), (0.16, 3.06, 0.34),
                _m(M, "wood_dark"), bev=0.012))
    for s2 in (-1, 1):
        P.append(bx("ci_thr_hood_br", T @ Ts(-1.30, s2 * 1.24, 4.84),
                    (0.16, 0.16, 1.20), _m(M, "wood_dark")))
    return P
def build_armour(nm, T, M, face=1.0, halberd=True):
    """A knight's harness on a stand: narrow waisted plate, ~2.10 m overall."""
    P = []
    stl = _m(M, "steel")
    ir = _m(M, "iron")
    wd = _m(M, "wood_dark")
    le = _m(M, "leather")
    P.append(bx(nm + "_base", T @ Ts(0, 0, 0.05), (0.78, 0.78, 0.10),
                _m(M, "stone_dark"), bev=0.014))
    P.append(bx(nm + "_stand", T @ Ts(0, 0, 0.12), (0.34, 0.20, 0.06), ir, bev=0.006))
    P.append(bx(nm + "_post", T @ Ts(0, 0, 0.86), (0.10, 0.10, 1.48), wd))
    for s2 in (-1, 1):
        # legs: greave, knee cop, sabaton
        P.append(cyl(nm + "_greave", T @ Ts(0.0, s2 * 0.125, 0.52), 0.078, 0.56, stl,
                     seg=9))
        P.append(sph(nm + "_knee", T @ Ts(0.01, s2 * 0.125, 0.80), 0.090, stl,
                     seg=9, ring=5, squash=0.9))
        P.append(bx(nm + "_cuisse", T @ Ts(0.0, s2 * 0.125, 0.94), (0.20, 0.17, 0.22),
                    stl, bev=0.018))
        P.append(bx(nm + "_sabat", T @ Ts(0.055, s2 * 0.125, 0.215), (0.30, 0.15, 0.09),
                    stl, bev=0.014))
        # arm: vambrace, elbow, gauntlet
        P.append(cyl(nm + "_vamb", T @ Ts(0.015, s2 * 0.255, 1.34, rx=s2 * 0.10),
                     0.052, 0.38, stl, seg=8))
        P.append(sph(nm + "_elb", T @ Ts(0.02, s2 * 0.265, 1.16), 0.065, stl,
                     seg=8, ring=5))
        P.append(sph(nm + "_gaunt", T @ Ts(0.035, s2 * 0.270, 1.06), 0.070, stl,
                     seg=8, ring=6, squash=1.15))
        # pauldron over the shoulder
        P.append(sph(nm + "_pauld", T @ Ts(0.005, s2 * 0.215, 1.60), 0.125, stl,
                     seg=11, ring=7, squash=0.78))
        P.append(bx(nm + "_pauld_l", T @ Ts(0.0, s2 * 0.245, 1.53), (0.15, 0.09, 0.10),
                    stl, bev=0.020))
    # cuirass: waist, breast, back
    P.append(bx(nm + "_fauld", T @ Ts(0, 0, 1.03), (0.28, 0.40, 0.17), stl, bev=0.024))
    P.append(bx(nm + "_belt", T @ Ts(0, 0, 1.13), (0.29, 0.42, 0.06), le))
    P.append(sph(nm + "_breast", T @ Ts(0.01, 0, 1.42), 0.205, stl, seg=13, ring=9,
                 squash=1.42))
    P.append(bx(nm + "_ridge", T @ Ts(0.145, 0, 1.44), (0.06, 0.10, 0.46), stl,
                bev=0.016))
    # gorget, helm, visor, crest
    P.append(cyl(nm + "_gorget", T @ Ts(0, 0, 1.74), 0.098, 0.10, stl, seg=11))
    P.append(cyl(nm + "_helm", T @ Ts(0, 0, 1.88), 0.128, 0.19, stl, seg=13, r2=0.120))
    P.append(sph(nm + "_helm_t", T @ Ts(0, 0, 1.955), 0.128, stl, seg=13, ring=7,
                 squash=0.85))
    P.append(bx(nm + "_eyeg", T @ Ts(0.108, 0, 1.905), (0.05, 0.19, 0.030), ir))
    P.append(bx(nm + "_nasal", T @ Ts(0.122, 0, 1.875), (0.035, 0.045, 0.14), ir,
                bev=0.006))
    P.append(cyl(nm + "_plume", T @ Ts(0, 0, 2.06), 0.032, 0.20, _m(M, "cloth_red"),
                 seg=7, r2=0.012))
    if halberd:
        P.append(cyl(nm + "_shaft", T @ Ts(0.24, 0.30, 1.30), 0.028, 2.62, wd, seg=7))
        P.append(cyl(nm + "_spike", T @ Ts(0.24, 0.30, 2.74), 0.038, 0.30, stl, seg=7,
                     r2=0.005))
        P.append(prism_y(nm + "_axe", T @ Ts(0.24, 0.30, 2.52),
                         [(-0.24, 0.09), (0.09, 0.18), (0.12, -0.12), (-0.22, -0.09)],
                         0.045, stl, bev=0.005))
    return P


def build_guards(M):
    P = []
    for s in (-1, 1):
        P.extend(build_armour("ci_guard", Ts(-10.55, s * 2.75, Z_DAIS, rz=s * 0.20),
                              M, halberd=True))
    return P


def build_braziers(M):
    """Iron fire baskets at the foot of the dais steps, with embers."""
    P = []
    ir = _m(M, "iron")
    em = _m(M, "ember")
    for s in (-1, 1):
        T = Ts(DAIS_X1 + STEP_D * N_STEP + 1.35, s * 4.35, 0.0)
        P.append(cyl("ci_braz_b", T @ Ts(0, 0, 0.62), 0.20, 0.42, ir, seg=12, r2=0.62))
        P.append(cyl("ci_braz_r", T @ Ts(0, 0, 0.84), 0.64, 0.09, ir, seg=14, r2=0.60))
        P.append(cyl("ci_braz_c", T @ Ts(0, 0, 0.80), 0.54, 0.06, em, seg=14))
        for k in range(3):
            a = TAU * k / 3.0 + 0.4
            P.append(cyl("ci_braz_l", T @ Ts(math.cos(a) * 0.32, math.sin(a) * 0.32, 0.30,
                                             rx=math.sin(a) * 0.30, ry=-math.cos(a) * 0.30),
                         0.048, 0.62, ir, seg=8))
        P.append(cyl("ci_braz_st", T @ Ts(0, 0, 0.06), 0.09, 0.12, ir, seg=8))
        # flames clear of the rim, or the bowl simply reads as an empty bucket
        fi = _m(M, "fire")
        ho = _m(M, "fire_hot")
        for (dx, dy, hh, rr, mm) in ((-0.13, 0.04, 0.34, 0.062, fi),
                                     (0.08, 0.09, 0.42, 0.068, fi),
                                     (0.05, -0.11, 0.29, 0.055, fi),
                                     (0.00, 0.02, 0.22, 0.046, ho)):
            P.append(cyl("ci_braz_f", T @ Ts(dx, dy, 0.88 + hh * 0.5), rr, hh,
                         mm, seg=9, r2=0.010))
    return P


def build_candles(M):
    """Tall standard candlesticks flanking the dais."""
    P = []
    ir = _m(M, "iron")
    br = _m(M, "brass")
    ca = _m(M, "candle")
    for s in (-1, 1):
        T = Ts(DAIS_X0 + 1.15, s * 3.95, Z_DAIS)
        P.append(cyl("ci_cs_base", T @ Ts(0, 0, 0.035), 0.32, 0.07, br, seg=14))
        P.append(cyl("ci_cs_stem", T @ Ts(0, 0, 0.42), 0.055, 0.76, br, seg=10))
        P.append(cyl("ci_cs_knop", T @ Ts(0, 0, 0.84), 0.11, 0.14, br, seg=10))
        P.append(cyl("ci_cs_cup", T @ Ts(0, 0, 0.94), 0.13, 0.06, br, seg=12, r2=0.16))
        for (dx, dy, h) in ((0, 0, 0.30), (0.20, 0.0, 0.22), (-0.20, 0.0, 0.22),
                            (0.0, 0.20, 0.22), (0.0, -0.20, 0.22)):
            if dx or dy:
                P.append(bx("ci_cs_arm", T @ Ts(dx * 0.5, dy * 0.5, 0.94),
                            (abs(dx) + 0.05, abs(dy) + 0.05, 0.035), br))
            P.append(cyl("ci_cs_c", T @ Ts(dx, dy, 0.97 + h * 0.5), 0.030, h, ca, seg=8))
            P.append(sph("ci_cs_fl", T @ Ts(dx, dy, 0.97 + h + 0.02), 0.028,
                         _m(M, "fire"), seg=8, ring=5))
    return P


# ---------------------------------------------------------------------------
# great hall - banners, tapestries, the courtyard door
# ---------------------------------------------------------------------------
def build_banners(M, rng):
    P = []
    rd = _m(M, "cloth_red")
    bl = _m(M, "cloth_blue")
    gd = _m(M, "cloth_gold")
    tp = _m(M, "tapestry")
    tb = _m(M, "tapestry_blue")
    for s in (+1, -1):
        n = "+y" if s > 0 else "-y"
        base = WF(0.0, s * HY, 0.0, n)
        for i in range(NBAY):
            xm = 0.5 * (BAYX[i] + BAYX[i + 1])
            if i in (0, 5):
                # a tapestry, wide and low
                T = base @ Ts(xm, -0.10 - 0.05 * (i in (0,)), 0, rz=math.pi) @ \
                    Ts(0, 0, 7.35)
                P.append(hang_rail("ci_tap_rail", T @ Ts(0, -0.06, 0), 3.55,
                                   _m(M, "wood_dark"), r=0.055))
                P.append(cloth_panel("ci_tap", T, 3.50, 5.55,
                                     tp if s > 0 else tb, folds=11, amp=0.085,
                                     sag=0.05, rows=22, cols=15, thick=0.015))
                for s2 in (-1, 1):
                    P.append(bx("ci_tap_bor", T @ Ts(s2 * 1.70, 0.06, -2.78),
                                (0.16, 0.10, 5.40), gd))
            else:
                # a swallow-tailed banner
                T = base @ Ts(xm, -0.10, 0, rz=math.pi) @ Ts(0, 0, 7.10)
                P.append(hang_rail("ci_ban_rail", T @ Ts(0, -0.06, 0), 1.95, gd,
                                   r=0.042))
                P.append(cloth_panel("ci_ban", T, 1.90, 3.30,
                                     rd if (i + (s > 0)) % 2 else bl, folds=6,
                                     amp=0.075, sag=0.04, rows=16, cols=9,
                                     notch=0.34, thick=0.014))
                P.append(bx("ci_ban_chief", T @ Ts(0, 0.07, -0.16),
                            (1.90, 0.03, 0.10), gd))
                P.append(sph("ci_ban_dev", T @ Ts(0, 0.16, -1.35), 0.26, gd,
                             seg=12, ring=7, squash=0.30))
    return P


def _void():
    m = bpy.data.materials.get("ci_void")
    if m is None:
        m = bpy.data.materials.new("ci_void")
        m.use_nodes = True
        bs = K._bsdf(m)
        if bs is not None:
            bs.inputs["Base Color"].default_value = (0.014, 0.013, 0.012, 1.0)
            bs.inputs["Roughness"].default_value = 0.95
    return m


def build_side_door(M):
    """The courtyard door in the +Y wall, on the keep's own entrance axis."""
    P = []
    n = "+y"
    T = WF(0.0, HY, 0.0, n)
    hs, spring, rise = 1.15, 2.45, 0.95
    wd = _m(M, "wood_dark")
    ir = _m(M, "iron")
    sl = _m(M, "stone_light")
    # the reveal: a dark box set back into the wall
    P.append(bx("ci_sd_void", T @ Ts(0, 0.50, 1.62), (2 * hs + 0.02, 0.10, 3.30),
                _void()))
    for (o, d, mat, ring) in ((0.0, 0.30, "stone_light", 0.22),
                              (-0.24, 0.26, "stone_course", 0.18)):
        P.append(ring_voussoir("ci_sd_ring", T @ Ts(0, o + 0.03, 0), hs, spring,
                               rise, ring, d, _m(M, mat), nseg=7, bev=0.010))
        for s2 in (-1, 1):
            P.append(bx("ci_sd_jamb", T @ Ts(s2 * (hs + 0.11), o + 0.03,
                                             spring * 0.5 + 0.05),
                        (0.44, d, spring + 0.10), _m(M, mat), bev=0.010))
    # the leaf, hung half open
    P.append(bx("ci_sd_leaf", T @ Ts(-0.36, 0.14, 1.62, rz=0.30),
                (1.90, 0.13, 3.24), wd, bev=0.014))
    for zz in (0.55, 1.55, 2.55):
        P.append(bx("ci_sd_strap", T @ Ts(-0.36, 0.22, zz, rz=0.30),
                    (1.72, 0.035, 0.11), ir))
    P.append(cyl("ci_sd_knob", T @ Ts(0.44, 0.24, 1.52, rx=math.pi * 0.5), 0.075, 0.09,
                 ir, seg=10))
    # a lamp in the reveal
    P.append(cyl("ci_sd_lamp", T @ Ts(0.92, 0.06, 2.30), 0.10, 0.20,
                 _m(M, "iron"), seg=8))
    P.append(cyl("ci_sd_flame", T @ Ts(0.92, 0.06, 2.46), 0.055, 0.16,
                 _m(M, "fire"), seg=8, r2=0.005))
    return P


# ===========================================================================
# PART D - the upper feast hall, and the stair tower that climbs to it
# ===========================================================================
FZ0 = Z_FEAST                 # 20.20  floor of the feast hall
FZ1 = Z_FEAST_TOP             # 28.40  its ceiling
FWT = 0.60                    # thickness of the upper storey walls
ST_SEG = 36
ST_DA = TAU / ST_SEG
ST_A0 = math.radians(200.0)   # the foot of the stair, facing into the hall
ST_STEP_A = math.radians(13.0)
ST_N = 112
ST_RISE = FZ0 / ST_N
ST_DB = (math.radians(190.0), math.radians(210.0))
ST_DT = (math.radians(206.0), math.radians(226.0))


def _pol(r, a):
    return (r * math.cos(a), r * math.sin(a))


def feast_poly(rad=0.0, n=18):
    """Plan of the upper storey: the room, with the tower bitten out."""
    P = [(-HX - rad, -HY - rad), (HX + rad, -HY - rad), (HX + rad, ST_CY)]
    for k in range(n + 1):
        a = (math.pi * 0.5) * k / n
        P.append((ST_CX + ST_R * math.cos(a), ST_CY + ST_R * math.sin(a)))
    P.append((-HX - rad, HY + rad))
    return P


def build_feast_floor(M, rng):
    P = []
    wf = _m(M, "wood_floor")
    st = _m(M, "stone_wall")
    # structural slab, top dressed with boards
    P.append(prism_z("ci_f_slab", Ts(0, 0, FZ0 - 0.24), feast_poly(), 0.48, st))
    P.append(prism_z("ci_f_deck", Ts(0, 0, FZ0 - 0.02), feast_poly(), 0.06, wf))
    # board joints, and the beam soffit showing under the edge
    for k in range(-14, 15):
        yy = k * 0.86
        if abs(yy) > HY - 0.3:
            continue
        xs = HX
        if yy > ST_CY - ST_R and yy < ST_CY + ST_R:
            xs = ST_CX - math.sqrt(max(0.0, ST_R ** 2 - (yy - ST_CY) ** 2))
        if xs < 0.5:
            continue
        P.append(bx("ci_f_joint", Ts(xs * 0.5, yy, FZ0 + 0.012),
                    (xs - 0.02, 0.024, 0.014), _m(M, "wood_dark")))
    return P


def _clip_x(yy):
    """Where an X-running ceiling member has to stop, short of the tower."""
    if abs(yy - ST_CY) >= ST_R:
        return HX
    return ST_CX - math.sqrt(max(0.0, ST_R ** 2 - (yy - ST_CY) ** 2))


def build_feast_ceiling(M, rng):
    P = []
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    pl = _m(M, "plaster")
    P.append(prism_z("ci_f_ceil", Ts(0, 0, FZ1 + 0.12), feast_poly(), 0.24, pl))
    for yy in (-7.5, -4.5, -1.5, 1.5, 4.5, 7.5):
        xe = _clip_x(yy)
        if xe < -HX + 1.0:
            continue
        P.append(bx("ci_f_beam", Ts((-HX + xe) * 0.5, yy, FZ1 - 0.22),
                    (xe + HX, 0.34, 0.44), wb))
        # braces at the ends
        for sx in (-1, 1):
            xb = -HX + 0.1 if sx < 0 else xe - 0.1
            P.append(bx("ci_f_brace", Ts(xb - sx * 0.42, yy, FZ1 - 0.72),
                        (0.16, 0.20, 0.72), wd))
    # cornice
    for s in (1, -1):
        P.append(bx("ci_f_corn", Ts(0, s * (HY - 0.06), FZ1 - 0.10),
                    (2 * HX, 0.30, 0.26), wb))
    return P


def feast_wall(s, M, rng):
    """Upper storey wall: wainscot, plaster, timber posts, leaded lights."""
    P = []
    n = "+x" if s > 0 else "-x"
    T = WF(s * HX, 0.0, 0.0, n) if s > 0 else WF(-HX, 0.0, 0.0, n)
    pl = _m(M, "plaster")
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    sl = _m(M, "stone_course")
    # the frame here runs +X along +Y for both ends, so build in (y, z)
    # room is y in [-HY, HY]
    H = FZ1 - FZ0
    # wainscot
    P.append(bx("ci_f_wsc", T @ Ts(0, 0.10, FZ0 + 0.70), (2 * HY, 0.22, 1.40), wb))
    P.append(bx("ci_f_wsc_c", T @ Ts(0, 0.02, FZ0 + 1.44), (2 * HY, 0.30, 0.12), wd,
                bev=0.012))
    for k in range(-9, 10):
        yy = k * 1.0
        P.append(bx("ci_f_stile", T @ Ts(yy, 0.05, FZ0 + 0.70), (0.10, 0.20, 1.34), wd))
    # plaster field
    P.append(bx("ci_f_pl", T @ Ts(0, FWT * 0.5, FZ0 + H * 0.5), (2 * HY, FWT, H), pl))
    # timber posts
    for yy in (-HY, -HY + 4.5, -HY + 9.0, -HY + 13.5, HY):
        P.append(bx("ci_f_post", T @ Ts(yy, -0.06, FZ0 + H * 0.5), (0.30, 0.34, H), wb))
    P.append(bx("ci_f_plate", T @ Ts(0, -0.02, FZ1 - 0.30), (2 * HY, 0.30, 0.34), wb))
    return P


def feast_long_wall(s, M, rng):
    """Upper storey long wall: piers, plaster, and four tall craft windows."""
    P = []
    n = "+y" if s > 0 else "-y"
    T = WF(0.0, s * HY, 0.0, n)
    U = HX
    pl = _m(M, "plaster")
    wb = _m(M, "wood_beam")
    wd = _m(M, "wood_dark")
    st = _m(M, "stone_wall")
    sl = _m(M, "stone_light")
    H = FZ1 - FZ0
    SP, RR = FZ0 + 4.15, 0.80
    # wainscot, and the band above the window heads
    P.append(bx("ci_f_lwsc", T @ Ts(0, 0.16, FZ0 + 0.77), (2 * U, 0.32, 1.54), wb))
    P.append(bx("ci_f_lwsc_c", T @ Ts(0, 0.10, FZ0 + 1.57), (2 * U, 0.40, 0.12), wd,
                bev=0.012))
    P.append(bx("ci_f_lwtop", T @ Ts(0, FWT * 0.5, FZ0 + (5.05 + H) * 0.5),
                (2 * U, FWT, H - 5.05), pl))
    P.append(bx("ci_f_lwplate", T @ Ts(0, -0.04, FZ1 - 0.30), (2 * U, 0.32, 0.34), wb))
    bw = 2 * U / 4.0
    for i in range(4):
        xc = -U + (i + 0.5) * bw
        hs = 1.50
        z0 = FZ0 + 1.60
        u0, u1 = xc - hs - 0.30, xc + hs + 0.30
        # solid piers either side of each window
        for (a0, a1) in ((-U + i * bw, u0), (u1, -U + (i + 1) * bw)):
            if a1 - a0 < 0.06:
                continue
            P.append(bx("ci_f_wpier", T @ Ts((a0 + a1) * 0.5, FWT * 0.5,
                                            FZ0 + (1.54 + 5.05) * 0.5),
                        (a1 - a0, FWT, 5.05 - 1.54), st))
        P.append(spandrel("ci_f_wspan", T @ Ts(0, FWT * 0.5, 0), u0, u1, SP, RR,
                          FZ0 + 5.05, FWT, pl, nseg=7))
        P.extend(glazed_window("ci_f_w", T, xc, 0.06, z0, hs, SP, RR, rng))
    return P


def build_fireplace(M, rng):
    """A hooded hearth on the -X wall of the feast hall, with a real fire."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    st = _m(M, "stone_wall")
    sc = _m(M, "stone_course")
    sd = _m(M, "stone_dark")
    fi = _m(M, "fire")
    em = _m(M, "ember")
    ir = _m(M, "iron")
    wd = _m(M, "wood_dark")
    HW = 1.25           # half width of the hearth opening
    DP = 0.95           # depth into the wall
    OH = 1.75           # opening height
    # ---- stone surround: cheeks, back, lintel, stepped hood to the ceiling
    P.append(bx("ci_fp_back", T @ Ts(0, DP + 0.20, FZ0 + 3.0), (2 * HW + 0.9, 0.50, 6.0), sd))
    P.append(bx("ci_fp_bk2", T @ Ts(0, DP - 0.01, FZ0 + (OH + 0.2) * 0.5),
                (2 * HW - 0.02, 0.06, OH + 0.2), _m(M, "soot")))
    for s3 in (-1, 1):
        P.append(bx("ci_fp_side", T @ Ts(s3 * (HW - 0.02), DP * 0.5, FZ0 + OH * 0.5),
                    (0.06, DP, OH), _m(M, "soot")))
    P.append(bx("ci_fp_top", T @ Ts(0, DP * 0.5, FZ0 + OH - 0.02),
                (2 * HW, DP, 0.06), _m(M, "soot")))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_cheek", T @ Ts(s2 * (HW + 0.34), DP * 0.5, FZ0 + 3.0),
                    (0.68, DP + 0.5, 6.0), st, bev=0.016))
        P.append(bx("ci_fp_pil", T @ Ts(s2 * (HW + 0.02), -0.05, FZ0 + (OH + 0.55) * 0.5),
                    (0.50, 0.22, OH + 0.55), sc, bev=0.014))
        P.append(bx("ci_fp_pc", T @ Ts(s2 * (HW + 0.02), -0.10, FZ0 + OH + 0.50),
                    (0.62, 0.32, 0.24), sc, bev=0.012))
    P.append(bx("ci_fp_lint", T @ Ts(0, DP * 0.5, FZ0 + OH + 0.26),
                (2 * HW + 1.4, DP + 0.55, 0.44), sc, bev=0.016))
    P.append(bx("ci_fp_lint2", T @ Ts(0, -0.10, FZ0 + OH + 0.06),
                (2 * HW + 1.1, 0.30, 0.16), sd, bev=0.010))
    for k in range(4):
        w = (2 * HW + 1.25) - k * 0.42
        P.append(bx("ci_fp_hood%d" % k,
                    T @ Ts(0, DP * 0.5 + 0.10 * k, FZ0 + OH + 0.72 + k * 0.60),
                    (w, DP + 0.15, 0.64), st if k % 2 else sc, bev=0.014))
    # ---- hearth floor, soot, kerb, andirons
    P.append(bx("ci_fp_floor", T @ Ts(0, DP * 0.5, FZ0 + 0.075), (2 * HW, DP, 0.15), sd,
                bev=0.012))
    P.append(bx("ci_fp_kerb", T @ Ts(0, -0.13, FZ0 + 0.16), (2 * HW + 0.8, 0.34, 0.32), sc,
                bev=0.014))
    for s2 in (-1, 1):
        P.append(bx("ci_fp_fd", T @ Ts(s2 * 0.62, DP * 0.42, FZ0 + 0.30),
                    (0.10, 0.34, 0.46), ir, bev=0.010))
        P.append(cyl("ci_fp_fdt", T @ Ts(s2 * 0.62, DP * 0.42, FZ0 + 0.54), 0.055, 0.20,
                     ir, seg=8))
    # ---- a stack of logs, three courses
    for k in range(6):
        yy = DP * 0.46 + rng.uniform(-0.20, 0.20)
        zz = FZ0 + 0.20 + 0.15 * (k // 2)
        P.append(cyl("ci_fp_log", T @ Ts(rng.uniform(-0.55, 0.55), yy, zz,
                                        ry=math.pi * 0.5),
                     0.095, 1.45, wd, seg=8))
    for k in range(14):
        P.append(sph("ci_fp_coal", T @ Ts(rng.uniform(-0.95, 0.95),
                                          DP * 0.42 + rng.uniform(-0.22, 0.22),
                                          FZ0 + 0.17), rng.uniform(0.06, 0.13), em, 8, 5, 0.5))
    # ---- flame tongues: a tall cluster at the front of the firebox
    hot = _m(M, "fire_hot")
    for (xx, yy, hh, rr, mm) in ((-0.46, 0.30, 0.50, 0.055, fi),
                                 (-0.20, 0.40, 0.62, 0.062, fi),
                                 (0.16, 0.32, 0.54, 0.058, fi),
                                 (0.42, 0.42, 0.40, 0.048, fi),
                                 (-0.05, 0.34, 0.34, 0.040, hot),
                                 (0.28, 0.28, 0.28, 0.034, hot)):
        P.append(cyl("ci_fp_flame", T @ Ts(xx, yy, FZ0 + 0.30), rr, hh, mm,
                     seg=7, r2=0.008))
    return P


def _smoke_mat():
    m = bpy.data.materials.get("ci_smoke_vol")
    if m:
        return m
    m = bpy.data.materials.new("ci_smoke_vol")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.62, 0.58, 0.54, 1.0)
    vol.inputs["Density"].default_value = 0.16
    vol.inputs["Anisotropy"].default_value = 0.52
    vol.inputs["Absorption Color"].default_value = (0.22, 0.20, 0.18, 1.0)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return m


def build_smoke(M):
    """A thin plume lifting off the hearth and curling into the room."""
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    sm = _smoke_mat()
    rings = []
    for k in range(6):
        t = k / 5.0
        z = FZ0 + 2.05 + t * 3.15
        r = 0.26 + t * 0.34
        yy = -0.06 - t * 0.42
        xx = math.sin(t * 3.1) * 0.20
        ring = []
        for j in range(10):
            a = TAU * j / 10.0
            ring.append(Vector((xx + r * math.cos(a), yy + r * 0.62 * math.sin(a), z)))
        rings.append(ring)
    ob = loft("ci_smoke", T, rings, sm, closed=True, cap0=False, cap1=False)
    P.append(ob)
    return P


def build_feast_tables(M, rng):
    P = []
    wb = _m(M, "wood")
    wd = _m(M, "wood_dark")
    cl = _m(M, "cloth_white")
    for s2 in (-1, 1):
        yc = s2 * 3.05
        x0, x1 = -9.6, 1.4
        L = x1 - x0
        # top, two boards
        for k in (-1, 1):
            P.append(bx("ci_t_top", Ts((x0 + x1) * 0.5, yc + k * 0.34, FZ0 + 0.76),
                        (L, 0.66, 0.09), wb, bev=0.008))
        P.append(bx("ci_t_rail", Ts((x0 + x1) * 0.5, yc, FZ0 + 0.68), (L - 0.5, 1.32, 0.10), wd))
        # trestles
        for k in range(3):
            xt = x0 + 0.9 + k * (L - 1.8) / 2.0
            P.append(bx("ci_t_leg", Ts(xt, yc, FZ0 + 0.36), (0.16, 0.20, 0.72), wd))
            P.append(bx("ci_t_foot", Ts(xt, yc, FZ0 + 0.05), (0.24, 1.14, 0.10), wd, bev=0.010))
            P.append(bx("ci_t_brace", Ts(xt, yc, FZ0 + 0.30), (0.12, 1.00, 0.14), wd,
                        bev=0.008))
        # benches either side
        for k in (-1, 1):
            yb = yc + k * 1.14
            P.append(bx("ci_t_bench", Ts((x0 + x1) * 0.5, yb, FZ0 + 0.46),
                        (L - 1.2, 0.34, 0.08), wb, bev=0.008))
            for j in range(3):
                xt = x0 + 1.2 + j * (L - 2.4) / 2.0
                P.append(bx("ci_t_bleg", Ts(xt, yb, FZ0 + 0.23), (0.12, 0.30, 0.46), wd))
        # a runner of linen and a couple of platters
        P.append(bx("ci_t_cloth", Ts((x0 + x1) * 0.5, yc, FZ0 + 0.815),
                    (L - 0.8, 0.66, 0.012), cl))
        for j in range(5):
            xt = x0 + 1.4 + j * (L - 2.8) / 4.0
            P.append(cyl("ci_t_plate", Ts(xt, yc + 0.10, FZ0 + 0.825), 0.19, 0.026,
                         _m(M, "brass"), seg=14))
            P.append(cyl("ci_t_mug", Ts(xt + 0.42, yc - 0.22, FZ0 + 0.86), 0.055, 0.16,
                         _m(M, "iron"), seg=10))
        for j in range(2):
            xt = x0 + 2.6 + j * 3.4
            P.append(cyl("ci_t_cand", Ts(xt, yc - 0.04, FZ0 + 0.88), 0.035, 0.22,
                         _m(M, "candle"), seg=8))
            P.append(cyl("ci_t_cstick", Ts(xt, yc - 0.04, FZ0 + 0.79), 0.09, 0.03,
                         _m(M, "brass"), seg=10))
    # a dresser against the -Y wall
    P.append(bx("ci_dr_body", Ts(-4.0, -HY + 0.42, FZ0 + 0.85), (3.2, 0.72, 1.30), wd))
    P.append(bx("ci_dr_top", Ts(-4.0, -HY + 0.42, FZ0 + 1.52), (3.4, 0.86, 0.10), wb,
                bev=0.012))
    for k in range(6):
        P.append(cyl("ci_dr_jug", Ts(-5.2 + k * 0.46, -HY + 0.40, FZ0 + 1.66), 0.11, 0.28,
                     _m(M, "brass") if k % 2 else _m(M, "iron"), seg=10))
    return P


def build_chandelier(M, rng):
    P = []
    ir = _m(M, "iron")
    cx, cy = -1.0, 0.0
    cz = FZ1 - 4.30
    for k in range(26):
        aa = TAU * k / 26.0
        chord = 2.0 * 1.34 * math.tan(math.pi / 26.0) * 1.05
        P.append(bx("ci_ch_ring", Ts(cx + 1.34 * math.cos(aa), cy + 1.34 * math.sin(aa),
                                     cz, rz=aa), (0.055, chord, 0.10), ir, bev=0.004))
    for k in range(20):
        aa = TAU * k / 20.0
        chord = 2.0 * 1.04 * math.tan(math.pi / 20.0) * 1.05
        P.append(bx("ci_ch_ring2", Ts(cx + 1.04 * math.cos(aa), cy + 1.04 * math.sin(aa),
                                      cz - 0.34, rz=aa), (0.045, chord, 0.07), ir,
                    bev=0.004))
    for k in range(8):
        a = TAU * k / 8.0
        xx, yy = cx + 1.20 * math.cos(a), cy + 1.20 * math.sin(a)
        P.append(cyl("ci_ch_arm", Ts(xx, yy, cz + 0.16), 0.030, 0.34, ir, seg=6))
        P.append(cyl("ci_ch_cup", Ts(xx, yy, cz + 0.34), 0.085, 0.06, ir, seg=10))
        P.append(cyl("ci_ch_cand", Ts(xx, yy, cz + 0.52), 0.042, 0.34, _m(M, "candle"),
                     seg=8))
    for k in range(3):
        a = TAU * k / 3.0 + 0.4
        top = Vector((cx, cy, FZ1 - 0.14))
        bot = Vector((cx + 1.10 * math.cos(a), cy + 1.10 * math.sin(a), cz + 0.05))
        P.append(cyl("ci_ch_chain", Ts(top.x, top.y, (top.z + bot.z) * 0.5), 0.014,
                     top.z - bot.z, ir, seg=5))
    P.append(cyl("ci_ch_hub", Ts(cx, cy, cz + 0.30), 0.12, 0.20, ir, seg=10))
    return P


def build_barrels(M, rng):
    P = []
    wd = _m(M, "wood")
    ir = _m(M, "iron")
    spots = [(-11.3, -6.9, 0.0), (-10.4, -7.5, 0.0), (-11.5, -5.8, 0.0),
             (-11.0, -7.2, 0.86), (-9.4, -6.4, 0.4)]
    for (xx, yy, up) in spots:
        if up > 0.2:
            T = Ts(xx, yy, FZ0 + up)
            P.append(cyl("ci_bar", T, 0.40, 0.86, wd, seg=16, r2=0.36))
            for zz in (-0.26, 0.0, 0.26):
                P.append(cyl("ci_bar_hoop", T @ Ts(0, 0, zz), 0.405, 0.05, ir, seg=16,
                             r2=0.385))
        else:
            T = Ts(xx, yy, FZ0 + 0.43)
            P.append(cyl("ci_bar", T, 0.40, 0.86, wd, seg=16, r2=0.36))
            for zz in (-0.26, 0.0, 0.26):
                P.append(cyl("ci_bar_hoop", T @ Ts(0, 0, zz), 0.405, 0.05, ir, seg=16,
                             r2=0.385))
    return P


def build_hound(nm, T, M, rng, mat_scale=1.0):
    P = []
    fu = _m(M, "leather")
    P.append(sph(nm + "_body", T @ Ts(0, 0, 0.46), 0.30, fu, 12, 8, 1.9))
    P.append(sph(nm + "_chest", T @ Ts(0.30, 0, 0.48), 0.24, fu, 12, 8, 1.15))
    P.append(cyl(nm + "_neck", T @ Ts(0.48, 0, 0.60, ry=-0.7), 0.13, 0.34, fu, seg=10))
    P.append(sph(nm + "_head", T @ Ts(0.62, 0, 0.70), 0.145, fu, 12, 8, 1.15))
    P.append(sph(nm + "_snout", T @ Ts(0.76, 0, 0.66), 0.085, fu, 10, 6, 1.5))
    for s2 in (-1, 1):
        P.append(bx(nm + "_ear", T @ Ts(0.58, s2 * 0.09, 0.80), (0.07, 0.05, 0.13), fu))
        for xs in (0.28, -0.24):
            P.append(cyl(nm + "_leg", T @ Ts(xs, s2 * 0.15, 0.22), 0.045, 0.42, fu, seg=7))
            P.append(bx(nm + "_paw", T @ Ts(xs + 0.03, s2 * 0.15, 0.035), (0.13, 0.09, 0.07), fu))
    P.append(cyl(nm + "_tail", T @ Ts(-0.44, 0, 0.58, ry=1.0), 0.035, 0.42, fu, seg=6))
    return P


def build_feast_props(M, rng):
    P = []
    T = WF(-HX, 0.0, 0.0, "-x")
    # two hounds asleep on the hearth
    P += build_hound("ci_hound1", Ts(-9.4, 1.30, FZ0, rz=0.5), M, rng)
    P += build_hound("ci_hound2", Ts(-9.7, -1.45, FZ0, rz=-0.35), M, rng)
    # a pair of standing iron candle stands by the hearth
    ir = _m(M, "iron")
    for s2 in (-1, 1):
        P.append(cyl("ci_stand", T @ Ts(s2 * 2.9, -0.8, FZ0 + 0.9), 0.055, 1.8, ir, seg=8))
        P.append(cyl("ci_stand_b", T @ Ts(s2 * 2.9, -0.8, FZ0 + 0.06), 0.22, 0.06, ir,
                     seg=12))
        P.append(cyl("ci_stand_c", T @ Ts(s2 * 2.9, -0.8, FZ0 + 1.86), 0.10, 0.06, ir,
                     seg=10))
        P.append(cyl("ci_stand_can", T @ Ts(s2 * 2.9, -0.8, FZ0 + 2.06), 0.048, 0.36,
                     _m(M, "candle"), seg=8))
    return P


# ---------------------------------------------------------------------------
# the stair tower
# ---------------------------------------------------------------------------
def build_stair_tower(M, rng):
    """A corner turret: helical treads round an open well, lit by torches."""
    P = []
    st = _m(M, "stone_wall")
    wd = _m(M, "wood_dark")
    sl = _m(M, "stone_light")
    sd = _m(M, "stone_dark")
    sc = _m(M, "stone_course")
    ir = _m(M, "iron")
    cx, cy = ST_CX, ST_CY
    ri, ro = ST_RIN + 0.30, ST_R          # inner face of the wall
    # ---- the wall itself, in segments, with doorways left open
    verts, faces = [], []

    def in_span(a, sp):
        return sp[0] - 1e-6 <= a + 1e-6 and a < sp[1] - 1e-6

    for i in range(ST_SEG):
        a0 = ST_A0 + i * ST_DA
        a1 = a0 + ST_DA
        for (z0, z1) in ((0.0, FZ0), (FZ0, Z_TOP)):
            if z0 == 0.0 and in_span(a0, ST_DB):
                continue
            if z0 > 0.0 and in_span(a0, ST_DT):
                continue
            b = len(verts)
            for (r, a, z) in ((ri, a0, z0), (ro, a0, z0), (ro, a1, z0), (ri, a1, z0)):
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
            for (r, a, z) in ((ri, a0, z1), (ro, a0, z1), (ro, a1, z1), (ri, a1, z1)):
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
            faces.append((b + 0, b + 3, b + 2, b + 1))       # underside
            faces.append((b + 4, b + 5, b + 6, b + 7))       # head
            faces.append((b + 0, b + 1, b + 5, b + 4))       # jamb a0
            faces.append((b + 3, b + 7, b + 6, b + 2))       # jamb a1
            faces.append((b + 0, b + 4, b + 6, b + 2))       # inner face
            faces.append((b + 1, b + 3, b + 7, b + 5))       # outer face
    ob = K.mesh_obj("ci_st_wall", verts, faces)
    K.assign(ob, st)
    P.append(ob)
    # ---- door surrounds, bottom and top
    for (ac, z0) in ((0.5 * (ST_DB[0] + ST_DB[1]), 0.0),
                     (0.5 * (ST_DT[0] + ST_DT[1]), FZ0)):
        for da in (-1, 1):
            aa = ac + da * math.radians(10.0)
            P.append(bx("ci_st_jamb", Ts(cx + (ri + 0.02) * math.cos(aa),
                                        cy + (ri + 0.02) * math.sin(aa), z0 + 1.30,
                                        rz=aa + math.pi * 0.5),
                        (0.30, 0.34, 2.60), sc, bev=0.014))
        aa = ac
        P.append(bx("ci_st_lint", Ts(cx + (ri + 0.02) * math.cos(aa),
                                    cy + (ri + 0.02) * math.sin(aa), z0 + 2.62,
                                    rz=aa + math.pi * 0.5),
                    (0.90, 0.36, 0.30), sc, bev=0.014))
    # ---- helical treads, one mesh
    verts, faces = [], []
    r0, r1 = ST_WELL, ST_R - 0.16
    for i in range(ST_N):
        a0 = ST_A0 + i * ST_STEP_A - ST_STEP_A * 0.5
        a1 = a0 + ST_STEP_A
        zt = ST_RISE * (i + 1)
        zb = zt - 0.17
        b = len(verts)
        for (r, a) in ((r0, a0), (r1, a0), (r1, a1), (r0, a1)):
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), zt))
        for (r, a) in ((r0, a0), (r1, a0), (r1, a1), (r0, a1)):
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), zb))
        faces.append((b + 0, b + 1, b + 2, b + 3))           # tread
        faces.append((b + 4, b + 7, b + 6, b + 5))           # soffit
        faces.append((b + 1, b + 5, b + 6, b + 2))           # outer cheek
        faces.append((b + 0, b + 3, b + 7, b + 4))           # inner cheek
        faces.append((b + 2, b + 6, b + 7, b + 3))           # riser
    ob = K.mesh_obj("ci_st_treads", verts, faces)
    K.assign(ob, sl)
    P.append(ob)
    # ---- the helical balustrade round the well (the open shaft)
    rings = []
    n = ST_N * 2
    for i in range(n + 1):
        a = ST_A0 + i * (ST_STEP_A * ST_N / n)
        z = ST_RISE * (i * ST_N / n) + 0.02
        ring = []
        for (r, dz) in ((ST_WELL - 0.30, 0.0), (ST_WELL, 0.0),
                        (ST_WELL, 1.02), (ST_WELL - 0.30, 1.02)):
            ring.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a), z + dz)))
        rings.append(ring)
    P.append(loft("ci_st_rail", Ts(0, 0, 0), rings, sc, closed=True, smooth=False))
    # ---- torches on iron brackets in shallow niches up the shaft
    rn = ri - 0.02
    rf = ri - 0.17
    for k in range(9):
        i2 = 6 + k * 12
        a = ST_A0 + i2 * ST_STEP_A
        z = ST_RISE * (i2 + 1) + 1.70
        P.append(bx("ci_st_niche", Ts(cx + rn * math.cos(a), cy + rn * math.sin(a), z,
                                      rz=a), (0.07, 0.56, 0.94), sd))
        for da in (-1, 1):
            aa = a + da * 0.32 / rn
            P.append(bx("ci_st_nch_c", Ts(cx + (rn - 0.05) * math.cos(aa),
                                          cy + (rn - 0.05) * math.sin(aa), z, rz=aa),
                        (0.15, 0.09, 1.00), sl, bev=0.008))
        P.append(bx("ci_st_nch_h", Ts(cx + (rn - 0.03) * math.cos(a),
                                      cy + (rn - 0.03) * math.sin(a), z + 0.55, rz=a),
                    (0.20, 0.72, 0.13), sl, bev=0.010))
        P.append(bx("ci_st_brack", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                      z - 0.06, rz=a), (0.26, 0.07, 0.07), ir))
        P.append(cyl("ci_st_torch", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                       z - 0.04), 0.044, 0.72, wd, seg=8))
        P.append(sph("ci_st_flame", Ts(cx + rf * math.cos(a), cy + rf * math.sin(a),
                                       z + 0.38), 0.115, _m(M, "fire"), 8, 5, 1.9))
    # ---- the lantern at the head of the shaft
    P.append(cyl("ci_st_cap", Ts(cx, cy, Z_TOP + 0.10), ri + 0.06, 0.20, sd, seg=28))
    P.append(sph("ci_st_lamp", Ts(cx, cy, Z_TOP - 0.55), 0.26, _m(M, "candle"), 10, 6, 1.0))
    return P


# ===========================================================================
# PART E - materials tuning, light rig, and the public build()
# ===========================================================================
def _ashlar(name, c1, c2, mortar, bw=1.15, bh=0.46, ms=0.020, rough=0.80,
            bump=0.30, grime=0.35):
    """Weathered keep stone.

    The projection has to be orientation-free: a Brick texture samples the XY
    plane of its vector, so on a wall (XZ) it stretches into 14 m tall smears.
    Two 3D noises -- one broad for the stone tone, one fine for the tooth --
    read correctly on every face and never repeat per object.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")

    def _rgba(v):
        v = tuple(v)
        return v if len(v) == 4 else (v[0], v[1], v[2], 1.0)

    big = nt.nodes.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = max(0.28, 1.6 / max(bw, 0.2))
    big.inputs["Detail"].default_value = 4.0
    big.inputs["Roughness"].default_value = 0.52
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.34
    ramp.color_ramp.elements[0].color = _rgba(c1)
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[1].color = _rgba(c2)
    nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    nt.links.new(big.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])

    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 3.2
    fine.inputs["Detail"].default_value = 5.0
    fine.inputs["Roughness"].default_value = 0.62
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.030
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m


def prep(MAT):
    """Swap in the interior's own stone, so the hall does not read as bricks."""
    M = dict(MAT)
    M["stone_wall"] = _ashlar("ci_ash_wall", (0.196, 0.183, 0.162),
                              (0.168, 0.157, 0.139), (0.062, 0.058, 0.052),
                              bw=1.40, bh=0.50, grime=0.26, bump=0.12)
    M["stone"] = M["stone_wall"]
    M["stone_light"] = _ashlar("ci_ash_light", (0.250, 0.235, 0.208),
                               (0.290, 0.272, 0.238), (0.150, 0.141, 0.124),
                               bw=0.62, bh=0.34, ms=0.012, rough=0.72, grime=0.30)
    M["stone_course"] = _ashlar("ci_ash_course", (0.300, 0.282, 0.250),
                                (0.340, 0.320, 0.282), (0.180, 0.170, 0.150),
                                bw=1.60, bh=0.30, ms=0.014, rough=0.68, grime=0.26)
    M["stone_dark"] = _ashlar("ci_ash_dark", (0.085, 0.080, 0.074),
                              (0.110, 0.104, 0.094), (0.045, 0.042, 0.038),
                              bw=0.90, bh=0.40, grime=0.5)
    M["stone_floor"] = _ashlar("ci_flag", (0.292, 0.276, 0.250),
                               (0.238, 0.224, 0.202), (0.062, 0.058, 0.052),
                               bw=1.02, bh=0.68, ms=0.016, rough=0.80, bump=0.18,
                               grime=0.22)
    M["stone_step"] = _ashlar("ci_step", (0.245, 0.230, 0.205),
                              (0.280, 0.262, 0.230), (0.120, 0.113, 0.100),
                              bw=1.30, bh=0.33, ms=0.010, rough=0.55)
    M["marble"] = _ashlar("ci_marble", (0.330, 0.315, 0.286),
                          (0.372, 0.355, 0.320), (0.232, 0.220, 0.198),
                          bw=1.70, bh=0.60, ms=0.006, rough=0.30, bump=0.10)
    return M


def build_lights(MAT, rng):
    """Warm points in the hall, the hearth, the torches and the feast hall."""
    P = []
    fire = (1.0, 0.42, 0.12)
    cand = (1.0, 0.74, 0.40)
    # braziers flanking the dais
    for s in (-1, 1):
        L = bpy.data.lights.new("ci_br_light", "POINT")
        L.energy = 900.0
        L.shadow_soft_size = 0.34
        L.color = fire
        o = bpy.data.objects.new("ci_br_light", L)
        o.location = (DAIS_X1 + STEP_D * N_STEP + 1.35, s * 4.35, 1.45)
        K.link(o)
        P.append(o)
    # candles on the dais
    for s in (-1, 1):
        L = bpy.data.lights.new("ci_cd_light", "POINT")
        L.energy = 260.0
        L.shadow_soft_size = 0.10
        L.color = cand
        o = bpy.data.objects.new("ci_cd_light", L)
        o.location = (DAIS_X0 + 1.15, s * 3.95, Z_DAIS + 1.55)
        K.link(o)
        P.append(o)
    # a key on the throne, so the seat and the crown read
    L = bpy.data.lights.new("ci_thr_key", "SPOT")
    L.energy = 3400.0
    L.spot_size = math.radians(52.0)
    L.spot_blend = 0.55
    L.shadow_soft_size = 0.30
    L.color = (1.0, 0.86, 0.66)
    o = bpy.data.objects.new("ci_thr_key", L)
    o.location = (THR_X + 4.6, 0.35, 6.30)
    o.rotation_euler = (math.radians(58.0), 0.0, math.radians(-96.0))
    K.link(o)
    P.append(o)
    # a cool rim from the great window behind the throne
    L = bpy.data.lights.new("ci_thr_rim", "AREA")
    L.energy = 1400.0
    L.size = 4.6
    L.size_y = 1.7
    L.color = (0.62, 0.74, 1.0)
    o = bpy.data.objects.new("ci_thr_rim", L)
    o.location = (-HX + 0.30, 0.0, 12.6)
    o.rotation_euler = (0.0, math.radians(-90.0), 0.0)
    K.link(o)
    P.append(o)
    # warm pools in the arcade, so the niches do not go dead
    for i in range(NBAY):
        xm = 0.5 * (BAYX[i] + BAYX[i + 1])
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_arc_light", "POINT")
            L.energy = 150.0
            L.shadow_soft_size = 0.22
            L.color = cand
            o = bpy.data.objects.new("ci_arc_light", L)
            o.location = (xm, s * (HY - 0.34), 3.9)
            K.link(o)
            P.append(o)
    # hearth in the feast hall
    L = bpy.data.lights.new("ci_fp_light", "POINT")
    L.energy = 2600.0
    L.shadow_soft_size = 0.45
    L.color = fire
    o = bpy.data.objects.new("ci_fp_light", L)
    o.location = (-HX + 0.20, 0.0, FZ0 + 0.55)
    K.link(o)
    P.append(o)
    L = bpy.data.lights.new("ci_fp_in", "POINT")
    L.energy = 800.0
    L.shadow_soft_size = 0.30
    L.color = fire
    o = bpy.data.objects.new("ci_fp_in", L)
    o.location = (-HX - 0.30, 0.0, FZ0 + 0.60)
    K.link(o)
    P.append(o)
    # chandelier
    L = bpy.data.lights.new("ci_ch_light", "POINT")
    L.energy = 2800.0
    L.shadow_soft_size = 0.40
    L.color = cand
    o = bpy.data.objects.new("ci_ch_light", L)
    o.location = (-1.0, 0.0, FZ1 - 3.70)
    K.link(o)
    P.append(o)
    # torches up the shaft, and the lantern over the well
    for k in range(9):
        i = 6 + k * 12
        a = ST_A0 + i * ST_STEP_A
        z = ST_RISE * (i + 1)
        rr = ST_RIN - 0.42
        L = bpy.data.lights.new("ci_st_light", "POINT")
        L.energy = 780.0
        L.shadow_soft_size = 0.34
        L.color = fire
        o = bpy.data.objects.new("ci_st_light", L)
        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a), z + 2.08)
        K.link(o)
        P.append(o)
    for (aa, zz) in ((186.0, 0.10), (214.0, 0.10)):
        a = math.radians(aa)
        rr = ST_RIN - 0.20
        P.append(cyl("ci_std_torch", Ts(ST_CX + rr * math.cos(a),
                                        ST_CY + rr * math.sin(a), zz + 1.55),
                     0.055, 1.90, _m(MAT, "wood_dark"), seg=8))
        P.append(cyl("ci_std_cup", Ts(ST_CX + rr * math.cos(a),
                                      ST_CY + rr * math.sin(a), zz + 2.56),
                     0.15, 0.26, _m(MAT, "iron"), seg=10, r2=0.20))
        P.append(sph("ci_std_fl", Ts(ST_CX + rr * math.cos(a),
                                     ST_CY + rr * math.sin(a), zz + 2.78),
                     0.20, _m(MAT, "fire"), seg=10, ring=6, squash=1.5))
        L = bpy.data.lights.new("ci_std_light", "POINT")
        L.energy = 900.0
        L.shadow_soft_size = 0.16
        L.color = (1.0, 0.46, 0.16)
        o = bpy.data.objects.new("ci_std_light", L)
        o.location = (ST_CX + rr * math.cos(a), ST_CY + rr * math.sin(a),
                      zz + 2.86)
        K.link(o)
        P.append(o)
    for zz in WELL_LAMPS:
        L = bpy.data.lights.new("ci_st_lampL", "POINT")
        L.energy = 1800.0
        L.shadow_soft_size = 0.30
        L.use_shadow = False
        L.color = (1.0, 0.55, 0.24)
        o = bpy.data.objects.new("ci_st_lampL", L)
        o.location = (ST_CX, ST_CY, zz + 0.14)
        K.link(o)
        P.append(o)
    # wall sconces down both long walls of the feast hall: an 8 m high room lit
    # only by two hearths reads as a black box from the far end
    for sx in (-7.60, -0.40, 6.80):
        for s in (-1, 1):
            yy = s * (HY - 0.30)
            P.append(bx("ci_f_sc_br", Ts(sx, yy - s * 0.10, FZ0 + 2.16),
                        (0.07, 0.34, 0.07), _m(MAT, "iron")))
            P.append(cyl("ci_f_sc_sh", Ts(sx, yy - s * 0.24, FZ0 + 2.34),
                         0.038, 0.46, _m(MAT, "wood_dark"), seg=8))
            P.append(sph("ci_f_sc_fl", Ts(sx, yy - s * 0.24, FZ0 + 2.64),
                         0.085, _m(MAT, "fire"), seg=9, ring=6, squash=1.7))
            L = bpy.data.lights.new("ci_f_sc_light", "POINT")
            L.energy = 1050.0
            L.shadow_soft_size = 0.16
            L.color = (1.0, 0.52, 0.20)
            o = bpy.data.objects.new("ci_f_sc_light", L)
            o.location = (sx, yy - s * 0.26, FZ0 + 2.70)
            K.link(o)
            P.append(o)
    L = bpy.data.lights.new("ci_well_lan", "POINT")
    L.energy = 2200.0
    L.shadow_soft_size = 0.26
    L.color = (1.0, 0.78, 0.48)
    o = bpy.data.objects.new("ci_well_lan", L)
    o.location = (ST_CX, ST_CY, 14.32)
    K.link(o)
    P.append(o)
    L = bpy.data.lights.new("ci_st_lampL", "POINT")
    L.energy = 900.0
    L.shadow_soft_size = 0.30
    L.color = (1.0, 0.82, 0.55)
    o = bpy.data.objects.new("ci_st_lampL", L)
    o.location = (ST_CX, ST_CY, Z_TOP - 0.70)
    K.link(o)
    P.append(o)
    # soft daylight fills just inside the clerestory, keyed to the sun.
    # An AREA lamp shines down its local -Z, so the +Y wall needs -90 about X
    # and the -Y wall +90: the old code aimed both into the stone.
    for i in range(NBAY):
        xm = 0.5 * (BAYX[i] + BAYX[i + 1])
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_win_fill", "AREA")
            L.energy = 300.0
            L.size = 2.6
            L.size_y = 3.2
            L.color = (0.80, 0.86, 1.0)
            L.use_shadow = False
            o = bpy.data.objects.new("ci_win_fill", L)
            o.location = (xm, s * (HY - 0.45), 11.6)
            o.rotation_euler = (math.radians(-90.0 if s > 0 else 90.0), 0.0, 0.0)
            K.link(o)
            P.append(o)
    # and for the feast hall windows
    for i in range(4):
        xc = -HX + (i + 0.5) * (2 * HX / 4.0)
        for s in (-1, 1):
            L = bpy.data.lights.new("ci_f_winfill", "AREA")
            L.energy = 1700.0
            L.size = 3.0
            L.size_y = 2.4
            L.color = (0.86, 0.90, 1.0)
            L.use_shadow = False
            o = bpy.data.objects.new("ci_f_winfill", L)
            o.location = (xc, s * (HY - 0.40), FZ0 + 3.10)
            o.rotation_euler = (math.radians(-90.0 if s > 0 else 90.0), 0.0, 0.0)
            K.link(o)
            P.append(o)
    # a big soft panel under the feast ceiling: eight window fills aimed
    # sideways leave the middle of an 8 m high room in the dark
    for xf in (-6.0, 4.0):
        L = bpy.data.lights.new("ci_f_roomfill", "AREA")
        L.energy = 5200.0
        L.size = 7.0
        L.size_y = 4.5
        L.color = (1.0, 0.90, 0.78)
        L.use_shadow = False
        o = bpy.data.objects.new("ci_f_roomfill", L)
        o.location = (xf, 0.0, FZ1 - 0.55)
        K.link(o)
        P.append(o)
    return P


def build_seals(M):
    """Two things the set needs that are not furniture: a sealed roof gap and
    a stone vault closing the head of the stair well."""
    P = []
    # a black backing plate under the feast-hall floor: kills every light leak
    # between the great hall roof and the floor above
    P.append(bx("ci_roof_seal", Ts(0, 0, 19.60),
                (2 * (HX + WT), 2 * (HY + WT), 0.26), _m(M, "stone_dark")))
    # the well head: a corbelled stone vault closing the shaft at 15.5 m, with a
    # hanging iron lantern under it, so the well is a lit 15 m shaft
    P.append(cyl("ci_st_vault", Ts(ST_CX, ST_CY, 15.62), ST_RIN + 0.16, 0.30,
                 _m(M, "stone_course"), seg=36))
    P.append(cyl("ci_st_vault2", Ts(ST_CX, ST_CY, 15.32), ST_RIN - 0.14, 0.34,
                 _m(M, "stone_light"), seg=36, r2=ST_RIN + 0.10))
    P.append(cyl("ci_st_vk", Ts(ST_CX, ST_CY, 15.05), ST_WELL + 0.10, 0.22,
                 _m(M, "stone_dark"), seg=24))
    # lantern: iron cage, four bars, a warm flame inside
    P.append(cyl("ci_st_lan_t", Ts(ST_CX, ST_CY, 15.02), 0.16, 0.10,
                 _m(M, "iron"), seg=10))
    P.append(cyl("ci_st_lan_b", Ts(ST_CX, ST_CY, 14.06), 0.24, 0.10,
                 _m(M, "iron"), seg=12))
    P.append(sph("ci_st_lan_fl", Ts(ST_CX, ST_CY, 14.32), 0.19,
                 _m(M, "fire"), seg=12, ring=7, squash=1.25))
    for k in range(4):
        a = TAU * k / 4.0 + 0.4
        P.append(bx("ci_st_lan_bar", Ts(ST_CX + 0.28 * math.cos(a),
                                       ST_CY + 0.28 * math.sin(a), 14.30),
                    (0.035, 0.035, 0.46), _m(M, "iron")))
    # three more lamps on long chains down the shaft: a 15 m open well with one
    # lamp at the very top reads as a black hole from the bottom of the stair
    for zz in WELL_LAMPS:
        P.append(cyl("ci_st_chain", Ts(ST_CX, ST_CY, (zz + 15.02) * 0.5),
                     0.020, 15.02 - zz, _m(M, "iron"), seg=6))
        P.append(cyl("ci_st_lamp_b", Ts(ST_CX, ST_CY, zz), 0.30, 0.16,
                     _m(M, "iron"), seg=12, r2=0.22))
        P.append(cyl("ci_st_lamp_f", Ts(ST_CX, ST_CY, zz + 0.15), 0.15, 0.26,
                     _m(M, "fire"), seg=10, r2=0.020))
    return P


def build(KM, MAT, origin=(0.0, 0.0), rot=0.0, scale=1.0, seed=3, lights=True,
          z=0.0):
    """Build the whole keep interior and return its objects.

    The module is modelled with its floor at z=0, centred on x=0, spanning
    y -HY..+HY; its +X end is the entrance.  Inside hd_castle.keep() the void
    is 30 x 22 x 42 m at (0, -21) with its floor at CY = 1.30, so::

        parts = hd_castle_int.build(medkit, MAT, origin=(0.0, -21.0),
                                   rot=0.0, scale=1.0, seed=3, z=1.30)

    which leaves 0.75 m clear on all four sides and tops out at 32.20 m -- far
    below the 44.6 m ceiling of the void.  ``lights`` also returns the 60 lamps,
    already transformed; pass lights=False to light the hall yourself.

    ``KM`` must be the **medkit module** (``import medkit as K``).  It is bound
    to the module-level ``K`` that every helper builds through, so passing
    something else raises immediately instead of quietly building nothing.
    """
    global K
    if KM is not None:
        for _req in ("mesh_obj", "assign", "bevel", "T_at", "link"):
            if not hasattr(KM, _req):
                raise TypeError("hd_castle_int.build(): K must be the medkit "
                                "module, %r has no %r" % (KM, _req))
        K = KM
    rng = random.Random(seed)
    M = prep(MAT)
    P = []
    P += build_floor(M, rng)
    P += side_wall(1, M, rng)
    P += side_wall(-1, M, rng)
    P += end_wall(1, M, rng)
    P += end_wall(-1, M, rng)
    P += build_roof(M, rng)
    P += build_dais(M)
    P += build_throne(M, rng)
    P += build_guards(M)
    P += build_braziers(M)
    P += build_candles(M)
    P += build_banners(M, rng)
    P += build_side_door(M)
    P += build_carpet(M)
    P += build_stair_tower(M, rng)
    P += build_feast_floor(M, rng)
    P += build_feast_ceiling(M, rng)
    P += feast_wall(1, M, rng)
    P += feast_wall(-1, M, rng)
    P += feast_long_wall(1, M, rng)
    P += feast_long_wall(-1, M, rng)
    P += build_fireplace(M, rng)
    P += build_smoke(M)
    P += build_feast_tables(M, rng)
    P += build_chandelier(M, rng)
    P += build_barrels(M, rng)
    P += build_feast_props(M, rng)
    P += build_seals(M)
    if lights:
        P += build_lights(M, rng)
    P = [o for o in P if o is not None]
    T = (Matrix.Translation((origin[0], origin[1], z))
         @ Matrix.Rotation(rot, 4, "Z") @ Matrix.Scale(scale, 4))
    H.apply(P, T)
    # Lamps are placed with .location/.rotation_euler, which only reach the
    # evaluated matrix_world after a depsgraph update.  Reading it before that
    # update hands back the identity, and writing T @ identity then *wipes* the
    # location -- which is how every one of the 66 lamps silently ended up at
    # the origin (the feast hall read as a black box with a bright floor
    # underside).  Update first, then transform.
    bpy.context.view_layer.update()
    for ob in P:
        if ob is not None and ob.type != "MESH":
            ob.matrix_world = T @ ob.matrix_world
    return P


def _tris(parts):
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        for p in ob.data.polygons:
            n += max(1, len(p.vertices) - 2)
    return n


def preview(samples=64, res=(480, 270), tag="ci", shots=None):
    """Build in an empty scene, light it, and render the design shots."""
    K.reset_scene()
    MAT = make_mats()
    t0 = __import__("time").time()
    P = build(K, MAT, origin=(0.0, 0.0), seed=3)
    print("PREVIEW parts=%d tris=%d build=%.1fs"
          % (len(P), _tris(P), __import__("time").time() - t0), flush=True)
    H.setup_engine(samples=samples, res=res, gpu=True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    w = bpy.data.worlds.new("ci_W")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.40, 0.48, 0.62, 1.0)
    bg.inputs[1].default_value = 0.055
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.0055
    vol.inputs["Anisotropy"].default_value = 0.55
    vol.inputs["Color"].default_value = (0.92, 0.93, 0.97, 1.0)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    sd = bpy.data.lights.new("ci_preview_sun", "SUN")
    sd.energy = 260.0
    sd.angle = math.radians(0.6)
    sd.color = (1.0, 0.93, 0.80)
    so = bpy.data.objects.new("ci_preview_sun", sd)
    K.link(so)
    so.rotation_euler = (math.radians(52.0), 0.0, math.radians(38.0))
    if shots is None:
        shots = [
            ("A_door", (8.8, 0.0, EYE), (-11.70, 0.0, 3.30), 37.0, 0.0022),
            ("B_throne", (-4.0, 2.30, 2.45), (-11.35, 0.10, 2.62), 33.0, 0.0022),
            ("C_feast", (HX - 2.30, -5.60, FZ0 + 1.72), (-9.20, 0.60, FZ0 + 2.10),
             24.0, 0.0026),
            ("D_stair", (ST_CX + 0.36, ST_CY - 0.30, 1.05),
             (ST_CX - 0.12, ST_CY + 0.16, 12.60), 14.0, 0.0030),
            ("E_torch", (ST_CX + 1.24 * math.cos(math.radians(247.0)),
                         ST_CY + 1.24 * math.sin(math.radians(247.0)), 2.30),
             (ST_CX + 2.86 * math.cos(math.radians(279.0)),
              ST_CY + 2.86 * math.sin(math.radians(279.0)), 3.02), 19.0, 0.0042),
            ("F_shaft", (-10.5, -5.5, 1.72), (6.0, 2.0, 7.0), 20.0, 0.0150,
             0.10, 1500.0),
        ]
    sc.view_settings.exposure = 0.22
    # the lamp rig is tuned for a candle-lit room; for the shaft shot the fill
    # lights have to get out of the way or the sunbeams are washed out
    base = {}
    for ob in P:
        if ob is not None and ob.type == "LIGHT":
            base[ob.name] = ob.data.energy
    FILLS = ("ci_win_fill", "ci_arc_light", "ci_candle_light", "ci_st_lampL",
             "ci_f_winfill", "ci_f_sc_light", "ci_f_roomfill")
    for shot in shots:
        nm, loc, look, lens, dens = shot[:5]
        fill = shot[5] if len(shot) > 5 else 1.0
        sd.energy = shot[6] if len(shot) > 6 else 260.0
        for ob in P:
            if ob is not None and ob.type == "LIGHT" and ob.name in base:
                k = ob.name.split(".")[0]
                ob.data.energy = base[ob.name] * (fill if k in FILLS else 1.0)
        vol.inputs["Density"].default_value = dens
        cam = _cam("ci_" + nm, loc, look, lens=lens)
        H.render_to(os.path.join(OUT, "%s_%s.png" % (tag, nm)), cam)
    print("PREVIEW done %.1fs" % (__import__("time").time() - t0), flush=True)
    return P


if __name__ == "__main__":
    preview()
